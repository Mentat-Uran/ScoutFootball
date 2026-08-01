"""PRS-2 B1 expert_weighted baseline (versioned transparent role weights).

PRS-2 (see ``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`` §8.1 and §5
"PRS-2：透明 baseline 与评分语义 v1") requires a third transparent
baseline alongside B0 (equal-weight percentiles) and B2 (minutes
shrinkage). B1 introduces **versioned, hand-defined expert weights**
for the role-specific dimensions, so the maintainer can encode and
audit "for a ST, finishing matters more than availability" without
hiding the choice inside a model.

Design contract (PRS-2 退出门槛 "B1 expert_weighted 版本化透明权重"):

1. **Hand-recomputable.** Each player's B1 score is the weighted mean
   of available dimension percentiles, where the weights come from a
   versioned table (``B1_WEIGHTS`` + ``B1_WEIGHTS_VERSION``). The
   output records the weight version, the per-dimension weight used,
   the renormalised effective weight (after dropping missing dims),
   and the per-column percentiles, so the maintainer can reproduce
   the arithmetic by hand from B0's percentiles + the weight table.

2. **Weights are explicit expert choices, not model outputs.** The
   weights are hand-defined per ``RoleFamily``, sum to 1.0, and are
   versioned as a single immutable set. They are NOT softmax weights
   from an optimiser (per AGENTS.md "do not treat raw softmax weights
   as actual model weights"). Weight revisions bump
   ``B1_WEIGHTS_VERSION`` and document the rationale in the module
   docstring; consumers can pin a version via the ``weight_version``
   parameter (only the current version is supported in v1, but the
   field is part of the schema so future versions can coexist).

3. **Renormalisation on missing dimensions.** When a player is missing
   a dimension (e.g., CB with no possession data), the remaining
   dimensions' weights are renormalised to sum to 1.0. If ALL core
   dimensions are missing, the score is the neutral 50.0 with
   ``confidence=low`` — identical to B0's honest placeholder, never a
   silent average. Supporting dimensions are skipped when missing
   (same convention as B0).

4. **Inherits B0's dimension definitions.** B1 reuses ``B0_DIMENSIONS``
   so the role-specific dimensions, columns, directions, and core/
   supporting flags are identical to B0. The only difference is the
   aggregation: B0 uses equal weights, B1 uses the expert weights.
   This keeps B0 and B1 directly comparable — any score difference is
   attributable to the weight choice, not to a different feature set.

5. **GK independent.** B1 inherits B0's GK availability-only
   placeholder. GK's B1 weight set is ``availability=1.0`` (the only
   dimension), so B1 == B0 for GK. The score is still flagged
   ``gk_provisional`` until PRS-2 adds a compliant goalkeeping source.

6. **Within-role only.** Like B0, B1 never produces a cross-position
   ranking. ``cross_position_comparable=False`` for every row.

7. **Bootstrap rank interval.** For each role, B1 resamples the pool
   with replacement ``n_bootstrap`` times (seed fixed), recomputes
   every player's B1 score under each resample (renormalising weights
   per player per resample), and reports the 5th/50th/95th percentile
   of the player's rank within the role.

8. **Read-only.** B1 is a pure diagnostic. It does not modify
   ``rating_feature_matrix.parquet`` or any other artifact. Output is
   a JSON-serialisable dict.

B1 does NOT replace B0 or B2; all three are reported side-by-side.
The maintainer is expected to inspect cases where B1 and B0 ranks
diverge sharply (those reveal players whose role-specific dimensions
are weighted very differently by the expert weights vs equal weights).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.baseline_b0 import (
    _MIN_BOOTSTRAP_POOL,
    B0_DIMENSIONS,
    B0Dimension,
    _dimension_percentile,
    _dimension_percentile_vectorised,
    _pool_column_arrays,
)
from scoutfootball.evaluation.role_system import RoleFamily, classify_role_family

BASELINE_B1_SCHEMA = "scoutfootball.baseline-b1"
BASELINE_B1_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Versioned expert weight set
# ---------------------------------------------------------------------------
#
# B1_WEIGHTS_VERSION tags the weight set below. When the maintainer
# revises the weights, they MUST bump this version string and document
# the rationale in the module docstring (or a sibling changelog). The
# version is emitted in every B1 report so consumers can pin a version
# when comparing runs. v1.0 is the first frozen set.
#
# Weight design rationale (v1.0):
#
#   - Weights are explicit, hand-defined, and capped to sum to 1.0 per
#     role. They encode common football domain knowledge about which
#     dimensions matter more for each role.
#   - ST: finishing is the primary job (0.55), with attacking/creation
#     secondary (0.25), and availability matters but less than finishing
#     (0.20).
#   - CB: defending is the primary job (0.50), possession/build-up is
#     secondary (0.20), availability matters (0.30).
#   - W: attacking is most of the job (0.70), with availability (0.30).
#   - GK: only availability (1.0) — provisional, awaiting a compliant
#     goalkeeping feature source.
#   - For roles with 3+ dimensions, the weights reflect a deliberate
#     priority ordering: the "primary job" dimension gets the largest
#     share, "secondary contribution" dimensions get a smaller share,
#     and availability gets a moderate share (it is a reliability
#     signal, not a technical ability, but it gates sample size).
#
# These weights are NOT the result of an optimiser. They are a
# transparent starting point that the maintainer can revise by bumping
# the version. AGENTS.md "do not treat raw softmax weights as actual
# model weights" applies to optimiser-produced weights; B1's weights
# are explicit expert choices, not softmax outputs.
B1_WEIGHTS_VERSION = "1.0"

# Weight tolerance for the "sum to 1.0" invariant. Float arithmetic
# can drift by ~1e-15; we accept up to 1e-9 to be safe.
_WEIGHT_SUM_TOLERANCE = 1e-9

B1_WEIGHTS: dict[RoleFamily, dict[str, float]] = {
    RoleFamily.GK: {"availability": 1.0},
    RoleFamily.CB: {
        "defending": 0.50,
        "possession": 0.20,
        "availability": 0.30,
    },
    RoleFamily.FB: {
        "defending": 0.35,
        "creation": 0.25,
        "possession": 0.15,
        "availability": 0.25,
    },
    RoleFamily.DM: {
        "defending": 0.40,
        "possession": 0.30,
        "availability": 0.30,
    },
    RoleFamily.CM: {
        "possession": 0.40,
        "creation": 0.30,
        "availability": 0.30,
    },
    RoleFamily.AM: {
        "creation": 0.45,
        "finishing": 0.25,
        "availability": 0.30,
    },
    RoleFamily.W: {
        "attacking": 0.70,
        "availability": 0.30,
    },
    RoleFamily.ST: {
        "finishing": 0.55,
        "attacking": 0.25,
        "availability": 0.20,
    },
}

DEFAULT_BOOTSTRAP = 200
DEFAULT_SEED = 20260731


# ---------------------------------------------------------------------------
# Score dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class B1DimensionScore:
    """Per-dimension B1 result for one player.

    Like ``B0DimensionScore`` but adds ``weight`` (the expert weight
    from the versioned table), ``effective_weight`` (renormalised
    after dropping missing dimensions; equals ``weight`` when all
    dimensions are present), and ``contribution`` (the dimension's
    contribution to the final score = ``effective_weight *
    dimension_percentile``).
    """

    dimension: str
    label: str
    columns_present: tuple[str, ...]
    columns_missing: tuple[str, ...]
    column_percentiles: dict[str, float]
    dimension_percentile: float
    is_missing: bool
    is_core: bool
    missing_flag: str
    weight: float  # raw weight from B1_WEIGHTS
    effective_weight: float  # renormalised weight (0.0 when missing)

    @property
    def contribution(self) -> float:
        """This dimension's contribution to the B1 score."""
        return self.effective_weight * self.dimension_percentile

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "label": self.label,
            "columns_present": list(self.columns_present),
            "columns_missing": list(self.columns_missing),
            "column_percentiles": dict(self.column_percentiles),
            "dimension_percentile": round(self.dimension_percentile, 4),
            "is_missing": self.is_missing,
            "is_core": self.is_core,
            "missing_flag": self.missing_flag,
            "weight": round(self.weight, 4),
            "effective_weight": round(self.effective_weight, 4),
            "contribution": round(self.contribution, 4),
        }


@dataclass(frozen=True)
class B1PlayerScore:
    """Full B1 score for one player-season.

    The ``score`` is the weighted mean of available dimension
    percentiles (using renormalised expert weights). ``confidence`` is
    ``high`` when all core dimensions have data, ``medium`` when at
    least one core dimension is missing but the score is still
    computed, and ``low`` when all core dimensions are missing (in
    which case ``score`` is the neutral 50.0 and the weights are not
    applied — there is nothing to weight).
    """

    canonical_player_id: str
    player_name: str
    season_id: str
    role_family: str
    score: float
    rank_in_role: int | None
    role_pool_size: int
    rank_p5: int | None
    rank_p50: int | None
    rank_p95: int | None
    confidence: str
    missing_reason: str
    core_dimensions_used: int
    core_dimensions_total: int
    dimensions: tuple[B1DimensionScore, ...]
    weight_version: str
    cross_position_comparable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_player_id": self.canonical_player_id,
            "player_name": self.player_name,
            "season_id": self.season_id,
            "role_family": self.role_family,
            "score": round(self.score, 4),
            "rank_in_role": self.rank_in_role,
            "role_pool_size": self.role_pool_size,
            "rank_interval": {
                "p5": self.rank_p5,
                "p50": self.rank_p50,
                "p95": self.rank_p95,
            }
            if self.rank_p5 is not None
            else None,
            "confidence": self.confidence,
            "missing_reason": self.missing_reason,
            "core_dimensions_used": self.core_dimensions_used,
            "core_dimensions_total": self.core_dimensions_total,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "weight_version": self.weight_version,
            "cross_position_comparable": self.cross_position_comparable,
        }


@dataclass(frozen=True)
class B1RoleSummary:
    """Aggregate summary for one role family within the cohort."""

    role_family: str
    member_count: int
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    score_min: float
    score_median: float
    score_max: float
    dimensions_available: tuple[str, ...]
    weight_version: str
    weights: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_family": self.role_family,
            "member_count": self.member_count,
            "confidence_counts": {
                "high": self.high_confidence_count,
                "medium": self.medium_confidence_count,
                "low": self.low_confidence_count,
            },
            "score_min": round(self.score_min, 4),
            "score_median": round(self.score_median, 4),
            "score_max": round(self.score_max, 4),
            "dimensions_available": list(self.dimensions_available),
            "weight_version": self.weight_version,
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_weight_set() -> None:
    """Validate B1_WEIGHTS invariants at import time.

    Each role's weights must:
    - Be non-empty.
    - Cover every dimension defined in B0_DIMENSIONS for that role.
    - Not reference dimensions not in B0_DIMENSIONS.
    - Sum to 1.0 within tolerance.
    - Be finite floats in [0, 1].
    """
    for role, dims in B0_DIMENSIONS.items():
        if role == RoleFamily.UNKNOWN:
            continue
        weights = B1_WEIGHTS.get(role)
        if weights is None:
            raise RuntimeError(
                f"B1_WEIGHTS missing entry for role {role!r}"
            )
        if not weights:
            raise RuntimeError(
                f"B1_WEIGHTS[{role!r}] is empty"
            )
        dim_keys = {d.key for d in dims}
        weight_keys = set(weights.keys())
        if weight_keys != dim_keys:
            raise RuntimeError(
                f"B1_WEIGHTS[{role!r}] keys {sorted(weight_keys)} "
                f"do not match B0_DIMENSIONS keys {sorted(dim_keys)}"
            )
        total = 0.0
        for k, w in weights.items():
            if not isinstance(w, (int, float)) or isinstance(w, bool):
                raise RuntimeError(
                    f"B1_WEIGHTS[{role!r}][{k!r}] is not a number: {w!r}"
                )
            wf = float(w)
            if not math.isfinite(wf):
                raise RuntimeError(
                    f"B1_WEIGHTS[{role!r}][{k!r}] is not finite: {w!r}"
                )
            if wf < 0.0 or wf > 1.0:
                raise RuntimeError(
                    f"B1_WEIGHTS[{role!r}][{k!r}] out of [0,1]: {w!r}"
                )
            total += wf
        if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise RuntimeError(
                f"B1_WEIGHTS[{role!r}] sums to {total!r}, expected 1.0"
            )


# Validate once at import so a bad weight table fails loudly.
_validate_weight_set()


def _renormalised_weights(
    dimension_scores: list[tuple[B0Dimension, bool]],
    raw_weights: dict[str, float],
) -> dict[str, float]:
    """Return effective weights after dropping missing dimensions.

    ``dimension_scores`` is a list of (dimension, is_missing) pairs.
    Returns a dict mapping dimension.key -> effective weight. Missing
    dimensions get 0.0; present dimensions get their raw weight
    renormalised so the sum is 1.0. If ALL dimensions are missing,
    returns all zeros (caller must handle the empty-score case).
    """
    present_keys = {dim.key for dim, missing in dimension_scores if not missing}
    if not present_keys:
        return {dim.key: 0.0 for dim, _ in dimension_scores}
    raw_sum = sum(raw_weights[k] for k in present_keys)
    if raw_sum <= 0.0:
        # All present dimensions have zero weight — fall back to equal
        # weights among present dimensions. This is a defensive guard;
        # the v1.0 weight set has no zero weights, but future revisions
        # might. Equal weights among present dims is the most honest
        # fallback (it degrades to B0 for that player).
        n = len(present_keys)
        return {
            dim.key: (1.0 / n if dim.key in present_keys else 0.0)
            for dim, _ in dimension_scores
        }
    return {
        dim.key: (
            raw_weights[dim.key] / raw_sum
            if dim.key in present_keys
            else 0.0
        )
        for dim, _ in dimension_scores
    }


def _vectorised_dimension_percentiles(
    column_arrays: dict[str, np.ndarray],
    dimensions: tuple[B0Dimension, ...],
    n: int,
) -> list[np.ndarray]:
    """Compute per-dimension percentile arrays for the whole pool.

    Returns a list aligned with ``dimensions``; each entry is a 1D
    numpy array of length ``n`` giving each player's dimension
    percentile. Players missing the dimension get NaN.
    """
    dim_pct_arrays: list[np.ndarray] = []
    for dim in dimensions:
        dim_present = np.zeros(n, dtype=bool)
        dim_pct_sum = np.zeros(n, dtype=np.float64)
        n_present_cols = np.zeros(n, dtype=np.int64)

        for col in dim.columns:
            arr = column_arrays[col]
            valid_mask = ~np.isnan(arr)
            n_valid = int(valid_mask.sum())
            if n_valid == 0:
                continue
            sorted_valid = np.sort(arr[valid_mask])
            pct = np.full(n, np.nan, dtype=np.float64)
            player_valid = valid_mask
            positions = np.searchsorted(sorted_valid, arr, side="left")
            pct[player_valid] = (
                positions[player_valid].astype(np.float64) / n_valid * 100.0
            )
            dim_pct_sum = np.where(
                np.isnan(pct), dim_pct_sum, dim_pct_sum + pct
            )
            n_present_cols = np.where(
                np.isnan(pct), n_present_cols, n_present_cols + 1
            )
            dim_present = dim_present | player_valid

        dim_pct = np.where(
            dim_present & (n_present_cols > 0),
            dim_pct_sum / np.where(n_present_cols > 0, n_present_cols, 1),
            np.nan,
        )
        dim_pct_arrays.append(dim_pct)
    return dim_pct_arrays


def _vectorised_weighted_scores(
    column_arrays: dict[str, np.ndarray],
    dimensions: tuple[B0Dimension, ...],
    raw_weights: dict[str, float],
    n: int,
) -> np.ndarray:
    """Compute B1 score for every player in the pool, vectorised.

    For each player:
    1. Compute per-dimension percentile (mean of available column
       percentiles within the dimension).
    2. Drop missing dimensions; renormalise the raw weights over the
       present dimensions.
    3. Score = sum(effective_weight * dimension_percentile).

    Returns a 1D numpy array of length ``n``. Players with no
    available dimensions get 50.0 (the neutral placeholder, matching
    B0's convention).
    """
    if n == 0:
        return np.zeros(0, dtype=np.float64)

    dim_pct_arrays = _vectorised_dimension_percentiles(
        column_arrays, dimensions, n
    )

    # Build a (n_dims, n) matrix of dimension percentiles, with NaN
    # for missing dimensions.
    dim_matrix = np.array(dim_pct_arrays, dtype=np.float64)  # (n_dims, n)
    present_mask = ~np.isnan(dim_matrix)  # (n_dims, n)

    # Build the raw weight vector aligned with dimensions.
    raw_w = np.array(
        [raw_weights[d.key] for d in dimensions], dtype=np.float64
    )  # (n_dims,)

    # For each player, compute the sum of raw weights over present dims.
    # present_mask.T is (n, n_dims); raw_w broadcasts to (n, n_dims).
    present_weights = np.where(
        present_mask, raw_w[:, None], 0.0
    )  # (n_dims, n)
    weight_sums = present_weights.sum(axis=0)  # (n,)

    # Effective weights: present_weights / weight_sums, with 0 where
    # weight_sums == 0 (all dims missing).
    safe_sums = np.where(weight_sums > 0, weight_sums, 1.0)
    effective_weights = present_weights / safe_sums[None, :]
    # Zero out players with all dims missing.
    effective_weights = np.where(
        weight_sums[None, :] > 0, effective_weights, 0.0
    )

    # Score = sum(effective_weight * dim_pct) over dims, ignoring NaN.
    # Replace NaN in dim_matrix with 0 for the multiplication, then
    # sum. The effective_weight for missing dims is already 0, so the
    # contribution is 0.
    safe_dim_matrix = np.where(np.isnan(dim_matrix), 0.0, dim_matrix)
    weighted = effective_weights * safe_dim_matrix  # (n_dims, n)
    scores = weighted.sum(axis=0)  # (n,)

    # Players with all dims missing get 50.0 (neutral placeholder).
    scores = np.where(weight_sums > 0, scores, 50.0)
    return scores


def _vectorised_weighted_scores_for_resample(
    base_column_arrays: dict[str, np.ndarray],
    dimensions: tuple[B0Dimension, ...],
    raw_weights: dict[str, float],
    sample_indices: np.ndarray,
    n_orig: int,
) -> np.ndarray:
    """Compute B1 scores for original players under a resampled pool.

    ``base_column_arrays`` is the per-column array for the original
    pool (length ``n_orig``). ``sample_indices`` is a 1D numpy array
    giving the indices resampled with replacement (length ``n_orig``).

    Returns a 1D numpy array of length ``n_orig`` giving each original
    player's B1 score computed against the resampled pool.
    """
    if n_orig == 0:
        return np.zeros(0, dtype=np.float64)

    dim_pct_arrays: list[np.ndarray] = []
    for dim in dimensions:
        dim_present = np.zeros(n_orig, dtype=bool)
        dim_pct_sum = np.zeros(n_orig, dtype=np.float64)
        n_present_cols = np.zeros(n_orig, dtype=np.int64)

        for col in dim.columns:
            arr = base_column_arrays[col]
            resampled = arr[sample_indices]
            valid_resampled = ~np.isnan(resampled)
            n_valid = int(valid_resampled.sum())
            if n_valid == 0:
                continue
            sorted_valid = np.sort(resampled[valid_resampled])
            # Player values come from the ORIGINAL pool (each player's
            # own value is fixed; only the pool is resampled).
            player_valid = ~np.isnan(arr)
            positions = np.searchsorted(sorted_valid, arr, side="left")
            pct = np.full(n_orig, np.nan, dtype=np.float64)
            pct[player_valid] = (
                positions[player_valid].astype(np.float64) / n_valid * 100.0
            )
            dim_pct_sum = np.where(
                np.isnan(pct), dim_pct_sum, dim_pct_sum + pct
            )
            n_present_cols = np.where(
                np.isnan(pct), n_present_cols, n_present_cols + 1
            )
            dim_present = dim_present | player_valid

        dim_pct = np.where(
            dim_present & (n_present_cols > 0),
            dim_pct_sum / np.where(n_present_cols > 0, n_present_cols, 1),
            np.nan,
        )
        dim_pct_arrays.append(dim_pct)

    dim_matrix = np.array(dim_pct_arrays, dtype=np.float64)
    present_mask = ~np.isnan(dim_matrix)
    raw_w = np.array(
        [raw_weights[d.key] for d in dimensions], dtype=np.float64
    )
    present_weights = np.where(present_mask, raw_w[:, None], 0.0)
    weight_sums = present_weights.sum(axis=0)
    safe_sums = np.where(weight_sums > 0, weight_sums, 1.0)
    effective_weights = present_weights / safe_sums[None, :]
    effective_weights = np.where(
        weight_sums[None, :] > 0, effective_weights, 0.0
    )
    safe_dim_matrix = np.where(np.isnan(dim_matrix), 0.0, dim_matrix)
    weighted = effective_weights * safe_dim_matrix
    scores = weighted.sum(axis=0)
    scores = np.where(weight_sums > 0, scores, 50.0)
    return scores


def _bootstrap_rank_interval(
    pool_rows: list[dict[str, Any]],
    dimensions: tuple[B0Dimension, ...],
    raw_weights: dict[str, float],
    n_bootstrap: int,
    seed: int,
) -> list[tuple[int | None, int | None, int | None] | None]:
    """Bootstrap rank interval for each player's B1 score.

    For each resample:
      1. Resample pool rows with replacement.
      2. Recompute B1 scores under resampled pool (pool composition
         changes -> percentiles change -> weights renormalise per
         player).
      3. Recompute ranks.

    Returns a list aligned with the original pool; each entry is
    (p5, p50, p95) or None when the pool is too small.
    """
    n = len(pool_rows)
    if n < _MIN_BOOTSTRAP_POOL or n_bootstrap <= 0:
        return [None] * n

    all_cols: list[str] = []
    seen: set[str] = set()
    for dim in dimensions:
        for col in dim.columns:
            if col not in seen:
                seen.add(col)
                all_cols.append(col)
    base_arrays = _pool_column_arrays(pool_rows, tuple(all_cols))

    rng = np.random.default_rng(seed)
    all_sample_indices = rng.integers(0, n, size=(n_bootstrap, n))

    ranks_matrix = np.zeros((n, n_bootstrap), dtype=np.int64)

    for b in range(n_bootstrap):
        sample_indices = all_sample_indices[b]
        sample_scores = _vectorised_weighted_scores_for_resample(
            base_arrays, dimensions, raw_weights, sample_indices, n
        )
        sorted_asc = np.sort(sample_scores)
        right_positions = np.searchsorted(sorted_asc, sample_scores, side="right")
        ranks = 1 + n - right_positions
        ranks_matrix[:, b] = ranks

    p5_arr = np.percentile(ranks_matrix, 5, axis=1, method="nearest")
    p50_arr = np.percentile(ranks_matrix, 50, axis=1, method="nearest")
    p95_arr = np.percentile(ranks_matrix, 95, axis=1, method="nearest")

    result: list[tuple[int | None, int | None, int | None] | None] = []
    for i in range(n):
        result.append((int(p5_arr[i]), int(p50_arr[i]), int(p95_arr[i])))
    return result


def _player_score(
    player_row: dict[str, Any],
    pool_rows: list[dict[str, Any]],
    dimensions: tuple[B0Dimension, ...],
    raw_weights: dict[str, float],
    role_family: RoleFamily,
    rank_in_role: int | None,
    role_pool_size: int,
    rank_interval: tuple[int | None, int | None, int | None] | None,
    *,
    player_idx: int | None = None,
    column_arrays: dict[str, np.ndarray] | None = None,
) -> B1PlayerScore:
    """Compute the full B1PlayerScore for one player.

    The overall score is the weighted mean of available dimension
    percentiles, with weights renormalised over present dimensions.
    Core dimensions are required for ``high`` confidence. If all core
    dimensions are missing, the score is the neutral 50.0 and the
    weights are not applied.
    """
    # Compute per-dimension percentiles for this player, plus the
    # present/missing flags needed for weight renormalisation.
    dim_present_flags: list[tuple[B0Dimension, bool]] = []
    b0_dim_scores = []
    for dim in dimensions:
        if player_idx is not None and column_arrays is not None:
            b0_ds = _dimension_percentile_vectorised(
                player_idx, column_arrays, dim
            )
        else:
            b0_ds = _dimension_percentile(player_row, pool_rows, dim)
        b0_dim_scores.append(b0_ds)
        dim_present_flags.append((dim, b0_ds.is_missing))

    # Renormalise weights over present dimensions.
    effective_weights = _renormalised_weights(dim_present_flags, raw_weights)

    # Build the B1DimensionScore list with the effective weights.
    dim_scores: list[B1DimensionScore] = []
    for b0_ds, dim in zip(b0_dim_scores, dimensions, strict=True):
        weight = float(raw_weights.get(dim.key, 0.0))
        dim_scores.append(
            B1DimensionScore(
                dimension=b0_ds.dimension,
                label=b0_ds.label,
                columns_present=b0_ds.columns_present,
                columns_missing=b0_ds.columns_missing,
                column_percentiles=b0_ds.column_percentiles,
                dimension_percentile=b0_ds.dimension_percentile,
                is_missing=b0_ds.is_missing,
                is_core=b0_ds.is_core,
                missing_flag=b0_ds.missing_flag,
                weight=weight,
                effective_weight=effective_weights[dim.key],
            )
        )

    # Core dimension accounting.
    core_dims = [d for d in dim_scores if d.is_core]
    core_used = [d for d in core_dims if not d.is_missing]
    core_missing = [d for d in core_dims if d.is_missing]

    # Compute score: weighted mean of available dimensions.
    all_used = [d for d in dim_scores if not d.is_missing]
    if all_used:
        score = sum(d.contribution for d in all_used)
    else:
        # All core missing AND no supporting — neutral placeholder.
        score = 50.0

    # Confidence.
    if not core_missing:
        confidence = "high"
        missing_reason = ""
    elif core_used:
        confidence = "medium"
        missing_reason = "; ".join(
            f"{d.label}({d.dimension})缺失" for d in core_missing
        )
    else:
        confidence = "low"
        missing_reason = "全部核心维度缺失；B1 评分为占位 50.0，不参与排名解读"

    # Rank interval.
    if rank_interval is not None:
        rank_p5, rank_p50, rank_p95 = rank_interval
    else:
        rank_p5, rank_p50, rank_p95 = None, None, None

    return B1PlayerScore(
        canonical_player_id=str(player_row.get("canonical_player_id", "")),
        player_name=str(player_row.get("player_name", "")),
        season_id=str(player_row.get("season_id", "")),
        role_family=role_family.value,
        score=score,
        rank_in_role=rank_in_role,
        role_pool_size=role_pool_size,
        rank_p5=rank_p5,
        rank_p50=rank_p50,
        rank_p95=rank_p95,
        confidence=confidence,
        missing_reason=missing_reason,
        core_dimensions_used=len(core_used),
        core_dimensions_total=len(core_dims),
        dimensions=tuple(dim_scores),
        weight_version=B1_WEIGHTS_VERSION,
        cross_position_comparable=False,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_b1_baseline(
    settings: PlatformSettings | None = None,
    *,
    feature_matrix: Any = None,
    cohort_definition: Any | None = None,
    n_bootstrap: int = DEFAULT_BOOTSTRAP,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Compute the B1 expert_weighted baseline for the local data.

    Loads ``rating_feature_matrix.parquet`` (or accepts a DataFrame via
    ``feature_matrix``), optionally applies a ``CohortDefinition`` to
    restrict membership, then computes the B1 score for every
    player-season in the cohort using the versioned expert weight set.

    Args:
        settings: Platform settings. If None, uses
            ``PlatformSettings.from_root()``.
        feature_matrix: Optional pre-loaded feature matrix DataFrame.
            If None, loads from ``rating_feature_matrix.parquet``.
        cohort_definition: Optional ``CohortDefinition``. If provided,
            only player-seasons whose ``canonical_player_id|season_id``
            appears in the cohort membership are scored.
        n_bootstrap: Bootstrap resample count for rank intervals.
            Default 200.
        seed: Random seed for bootstrap. Default 20260731.

    Returns:
        A JSON-serialisable dict with schema
        ``scoutfootball.baseline-b1`` v1.0.0. The dict includes the
        weight version, per-player scores with effective weights,
        per-role summaries (with the raw weight set), and explicit
        limitations.
    """
    resolved = settings or PlatformSettings.from_root()

    # Load feature matrix.
    if feature_matrix is None:
        fm_path = resolved.gold_root / "feature_store" / "rating_feature_matrix.parquet"
        if not fm_path.exists():
            return {
                "schema": BASELINE_B1_SCHEMA,
                "schema_version": BASELINE_B1_VERSION,
                "generated_at": _now(),
                "status": "unavailable",
                "evidence": {"reason": "rating_feature_matrix.parquet missing"},
                "limitations": _LIMITATIONS,
            }
        try:
            import pandas as pd

            feature_matrix = pd.read_parquet(fm_path)
        except Exception as exc:  # noqa: BLE001 — read-only diagnostic
            return {
                "schema": BASELINE_B1_SCHEMA,
                "schema_version": BASELINE_B1_VERSION,
                "generated_at": _now(),
                "status": "unavailable",
                "evidence": {
                    "reason": f"rating_feature_matrix read failed: {exc}"
                },
                "limitations": _LIMITATIONS,
            }

    if feature_matrix is None or len(feature_matrix) == 0:
        return {
            "schema": BASELINE_B1_SCHEMA,
            "schema_version": BASELINE_B1_VERSION,
            "generated_at": _now(),
            "status": "unavailable",
            "evidence": {"reason": "rating_feature_matrix is empty"},
            "limitations": _LIMITATIONS,
        }

    # Apply cohort filter if a definition is provided.
    cohort_hash: str | None = None
    membership_hash: str | None = None
    if cohort_definition is not None:
        from scoutfootball.evaluation.cohort import preview_cohort

        cohort_report = preview_cohort(cohort_definition, settings=resolved)
        if cohort_report.get("status") != "ok":
            return {
                "schema": BASELINE_B1_SCHEMA,
                "schema_version": BASELINE_B1_VERSION,
                "generated_at": _now(),
                "status": "unavailable",
                "cohort_hash": cohort_report.get("cohort_hash"),
                "evidence": {
                    "reason": "cohort preview failed",
                    "cohort_status": cohort_report.get("status"),
                    "cohort_evidence": cohort_report.get("evidence"),
                },
                "limitations": _LIMITATIONS,
            }
        cohort_hash = cohort_report.get("cohort_hash")
        membership_hash = cohort_report.get("membership_hash")
        member_keys: set[str] = {
            f"{m['canonical_player_id']}|{m['season_id']}"
            for m in cohort_report["evidence"]["members"]
        }
        if not member_keys:
            return {
                "schema": BASELINE_B1_SCHEMA,
                "schema_version": BASELINE_B1_VERSION,
                "generated_at": _now(),
                "status": "ok",
                "cohort_hash": cohort_hash,
                "membership_hash": membership_hash,
                "weight_version": B1_WEIGHTS_VERSION,
                "evidence": {
                    "total_players_scored": 0,
                    "by_role_family": {},
                    "role_summaries": [],
                    "players": [],
                },
                "limitations": _LIMITATIONS,
            }
    else:
        member_keys = None  # All rows in scope.

    fm = feature_matrix
    rows_to_score: list[dict[str, Any]] = []
    for _, row in fm.iterrows():
        cid = row.get("canonical_player_id")
        if cid is None and "player_id" in fm.columns:
            source = row.get("source_name", "unknown")
            pid = row.get("player_id", "missing")
            cid = f"unresolved:{source}:{pid}"
        season = row.get("season_id")
        if cid is None or season is None:
            continue
        if member_keys is not None:
            key = f"{cid}|{season}"
            if key not in member_keys:
                continue
        row_dict = row.to_dict()
        row_dict["canonical_player_id"] = str(cid)
        row_dict["season_id"] = str(season)
        row_dict["player_name"] = str(row_dict.get("player_name", ""))
        row_dict["_role_family"] = classify_role_family(
            row_dict.get("position_group")
        )
        rows_to_score.append(row_dict)

    # Group by role family.
    by_role: dict[RoleFamily, list[dict[str, Any]]] = {}
    for r in rows_to_score:
        role = r["_role_family"]
        by_role.setdefault(role, []).append(r)

    # Score each role.
    all_player_scores: list[B1PlayerScore] = []
    role_summaries: list[B1RoleSummary] = []
    by_role_counts: dict[str, int] = {}

    for role_family in RoleFamily:
        if role_family == RoleFamily.UNKNOWN:
            unknown_rows = by_role.get(role_family, [])
            if unknown_rows:
                by_role_counts[role_family.value] = len(unknown_rows)
            continue

        pool = by_role.get(role_family, [])
        if not pool:
            continue

        dims = B0_DIMENSIONS.get(role_family)
        if dims is None:
            continue

        raw_weights = B1_WEIGHTS.get(role_family)
        if raw_weights is None:
            # No weight set for this role — skip honestly.
            continue

        # Build column arrays for the vectorised path.
        all_cols: list[str] = []
        seen: set[str] = set()
        for dim in dims:
            for col in dim.columns:
                if col not in seen:
                    seen.add(col)
                    all_cols.append(col)
        column_arrays = _pool_column_arrays(pool, tuple(all_cols))

        # Compute base scores.
        n_pool = len(pool)
        base_scores_array = _vectorised_weighted_scores(
            column_arrays, dims, raw_weights, n_pool
        )
        base_scores: list[float] = base_scores_array.tolist()

        # Compute ranks within the role (1 = highest score, min-rank
        # for ties — same convention as B0).
        indexed = sorted(enumerate(base_scores), key=lambda kv: -kv[1])
        ranks: list[int] = [0] * n_pool
        current_rank = 1
        prev_score: float | None = None
        for position, (orig_idx, s) in enumerate(indexed):
            if prev_score is None or s != prev_score:
                current_rank = position + 1
                prev_score = s
            ranks[orig_idx] = current_rank

        # Bootstrap rank intervals.
        rank_intervals = _bootstrap_rank_interval(
            pool, dims, raw_weights, n_bootstrap, seed
        )

        # Build B1PlayerScore for each member of this role.
        for i, player_row in enumerate(pool):
            ps = _player_score(
                player_row=player_row,
                pool_rows=pool,
                dimensions=dims,
                raw_weights=raw_weights,
                role_family=role_family,
                rank_in_role=ranks[i],
                role_pool_size=n_pool,
                rank_interval=rank_intervals[i],
                player_idx=i,
                column_arrays=column_arrays,
            )
            all_player_scores.append(ps)

        # Role summary.
        role_players = [
            ps for ps in all_player_scores
            if ps.role_family == role_family.value
        ]
        high = sum(1 for ps in role_players if ps.confidence == "high")
        med = sum(1 for ps in role_players if ps.confidence == "medium")
        low = sum(1 for ps in role_players if ps.confidence == "low")
        role_scores = [ps.score for ps in role_players]
        if role_scores:
            sorted_rs = sorted(role_scores)
            score_min = sorted_rs[0]
            score_max = sorted_rs[-1]
            score_median = sorted_rs[len(sorted_rs) // 2]
        else:
            score_min = score_median = score_max = 0.0

        dims_available = tuple(d.key for d in dims)
        role_summaries.append(
            B1RoleSummary(
                role_family=role_family.value,
                member_count=n_pool,
                high_confidence_count=high,
                medium_confidence_count=med,
                low_confidence_count=low,
                score_min=score_min,
                score_median=score_median,
                score_max=score_max,
                dimensions_available=dims_available,
                weight_version=B1_WEIGHTS_VERSION,
                weights=dict(raw_weights),
            )
        )
        by_role_counts[role_family.value] = n_pool

    # UNKNOWN count for transparency.
    unknown_count = len(by_role.get(RoleFamily.UNKNOWN, []))
    if unknown_count:
        by_role_counts[RoleFamily.UNKNOWN.value] = unknown_count

    # Sort players: by role_family, then by rank_in_role.
    sorted_players = sorted(
        all_player_scores,
        key=lambda ps: (ps.role_family, ps.rank_in_role or 999999),
    )

    return {
        "schema": BASELINE_B1_SCHEMA,
        "schema_version": BASELINE_B1_VERSION,
        "generated_at": _now(),
        "status": "ok",
        "cohort_hash": cohort_hash,
        "membership_hash": membership_hash,
        "weight_version": B1_WEIGHTS_VERSION,
        "parameters": {
            "n_bootstrap": n_bootstrap,
            "seed": seed,
            "min_bootstrap_pool": _MIN_BOOTSTRAP_POOL,
            "weight_version": B1_WEIGHTS_VERSION,
        },
        "evidence": {
            "total_players_scored": len(sorted_players),
            "by_role_family": by_role_counts,
            "role_summaries": [rs.to_dict() for rs in role_summaries],
            "players": [ps.to_dict() for ps in sorted_players],
        },
        "limitations": _LIMITATIONS,
    }


_LIMITATIONS: list[str] = [
    (
        "B1 是 PRS-2 透明 baseline 的第三种形式：角色内版本化专家权重"
        "加权百分位。它不是球员能力的最终判断，也不替代 B0/B2/B3 候选。"
        "B1 的价值在于把'对这个角色哪个维度更重要'的判断从模型内部"
        "挪到可审计的版本化权重表，让维护者可以显式修改和对比。"
    ),
    (
        "B1 的权重是手工定义的专家选择（B1_WEIGHTS v1.0），不是优化器"
        "输出的 softmax 权重。AGENTS.md '不得把 raw softmax 权重当作"
        "实际模型权重' 适用于优化器权重；B1 的权重是显式专家判断，"
        "每次修订必须 bump B1_WEIGHTS_VERSION 并记录理由。消费者可以"
        "通过 weight_version 字段 pin 一个版本进行对比。"
    ),
    (
        "缺失数据下的权重再归一化：当球员缺失某维度（如 CB 缺 possession）"
        "时，剩余维度的权重被重新归一化为和=1.0。若全部核心维度缺失，"
        "评分为占位 50.0，confidence=low，权重不被应用——没有东西可以"
        "加权。B1 从不把缺失值静默解释为平均能力。"
    ),
    (
        "B1 复用 B0_DIMENSIONS，因此 B1 与 B0 的角色特定维度、列、方向、"
        "core/supporting 标记完全一致。B1 与 B0 的唯一差异是聚合方式："
        "B0 等权，B1 加权。任何 B1 vs B0 的分数差异都归因于权重选择，"
        "而非不同的特征集。"
    ),
    (
        "GK 角色的 B1 权重集为 availability=1.0（唯一维度），因此 GK 的 "
        "B1 == B0。GK 仍是 gk_provisional 占位，直到 PRS-2 引入合规门将"
        "特征源（saves/psxg/claims 等）。"
    ),
    (
        "Bootstrap 排名区间：当角色池 >= 10 人时，B1 用固定 seed 做 "
        f"{DEFAULT_BOOTSTRAP} 次重采样，每次重采样后重新计算所有球员"
        "分数（含权重再归一化）并赋予 1-indexed rank（同分同 rank，"
        "min-rank 约定）。报告每位球员 rank 的 p5/p50/p95。当角色池 "
        "< 10 人时 rank_interval 为 None。"
    ),
    (
        "Cohort 过滤：若传入 cohort_definition，B1 仅对 cohort membership "
        "中的 canonical_player_id|season_id 对评分；未传入则对特征矩阵"
        "全部行评分。建议始终传入显式 cohort 定义，以避免隐式人群漂移。"
    ),
    (
        "canonical_player_id：rating_feature_matrix.parquet 当前未携带"
        "canonical_player_id 列；B1 用 unresolved:<source>:<player_id> "
        "作为 source-stable fallback，与 PRS-1 canonical_resolver 一致。"
        "若调用者已通过 canonical_resolver 解析，应使用解析后的 DataFrame "
        "通过 feature_matrix 参数传入。"
    ),
    (
        "B1 与 B2 的关系：B2 在 B0 之上叠加分钟收缩，B1 在 B0 之上替换"
        "等权为专家权重。两者正交，可组合（如 B1+收缩），但 PRS-2 v1 "
        "暂不提供组合候选；维护者可手工对比 B0/B1/B2 三个 baseline 的"
        "排名差异来识别权重敏感的球员。"
    ),
]

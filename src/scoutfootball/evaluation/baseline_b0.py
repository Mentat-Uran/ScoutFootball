"""PRS-2 B0 raw_percentile baseline (transparent within-role percentile).

PRS-2 (see ``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`` §8.1 and §5
"PRS-2：透明 baseline 与评分语义 v1") requires a transparent, hand-
recomputable, uncertainty-bearing baseline before any complex candidate
is allowed to claim the "player rating" slot. B0 is the simplest such
baseline: it computes an equal-weighted average of within-role
percentiles for a small set of role-specific dimensions, all derived
from columns that actually exist in ``rating_feature_matrix.parquet``.

Design contract (PRS-2 退出门槛):

1. **Hand-recomputable.** Each player's B0 score is
   ``mean(dimension_percentile)`` where each dimension percentile is
   ``mean(column_percentile)`` across the dimension's available columns.
   A column percentile is the fraction of role-pool values strictly
   below the player's value, scaled to [0, 100]. The output records
   every raw value and per-column percentile so the maintainer can
   reproduce the arithmetic by hand from the parquet.

2. **Honest missing-data handling.** B0 never silently treats missing
   values as average ability. Each role's dimensions are split into
   "core" (must have at least one non-missing column for the score to
   be meaningful) and "supporting" (skipped entirely when missing). If
   all core columns are missing for a player, the player is returned
   with ``score=50.0``, ``confidence='low'`` and an explicit
   ``missing_reason`` — not bundled with confident scorers. The
   existing ``*_missing`` flags (defense_missing, possession_missing,
   xT_VAEP_missing, goalkeeper_missing) propagate into per-dimension
   ``missing_flags`` so the maintainer can see *why* a dimension was
   dropped.

3. **GK independent.** Per the PRS-2 gate "GK 不再使用外场防守代理作
   为核心指标", the GK role does not consume tackles/interceptions or
   any outfield metric. With the current ``rating_feature_matrix`` (no
   saves, psxg, claims, goal_kicks), the honest B0 for GK is
   availability-only and explicitly flagged as ``gk_provisional`` — a
   placeholder until PRS-2 adds a compliant goalkeeping feature source.
   This is intentionally unhelpful rather than falsely helpful.

4. **Within-role only.** B0 never produces a cross-position ranking.
   The output marks ``cross_position_comparable=False`` for every row.
   Cross-position comparison requires explicit calibration (B2 shrinkage
   and/or z-score standardisation), which is out of scope for B0.

5. **Bootstrap rank interval.** For each role, B0 resamples the role
   pool with replacement ``n_bootstrap`` times (default 200, seed
   fixed), recomputes every player's B0 score under each resample, and
   reports the 5th/50th/95th percentile of the player's *rank* within
   the role. This is the PRS-2 退出门槛 "同一 cohort 内榜单有
   bootstrap 排名区间".

This module is read-only and side-effect-free. It does not modify
``rating_feature_matrix.parquet`` or any other artifact. The output is
a JSON-serialisable dict suitable for CLI output and downstream
evaluation modules.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.role_system import RoleFamily

BASELINE_B0_SCHEMA = "scoutfootball.baseline-b0"
BASELINE_B0_VERSION = "1.0.0"

# Default bootstrap size. 200 is enough to get a usable 5th/50th/95th
# rank percentile for roles with ≥ 30 members without being CPU-heavy
# on a laptop. The seed is fixed per call so the same cohort + data
# always produces the same interval.
DEFAULT_BOOTSTRAP = 200
DEFAULT_SEED = 20260731

# Minimum role-pool size for which bootstrap is meaningful. Below this
# we still compute the score but report rank interval as None.
_MIN_BOOTSTRAP_POOL = 10


# ---------------------------------------------------------------------------
# Dimension definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class B0Dimension:
    """One B0 dimension (a group of columns + direction + role).

    A dimension's percentile is the mean of its available columns'
    percentiles. ``core`` dimensions must have at least one non-missing
    column for the player's score to be considered confident; supporting
    dimensions are skipped when fully missing.

    ``missing_flag`` is the ``*_missing`` column name in
    ``rating_feature_matrix`` that, when True, marks the dimension as
    structurally unavailable for that player. Empty string means "no
    structural-missing flag for this dimension".
    """

    key: str
    label: str
    columns: tuple[str, ...]
    direction: str = "higher_better"
    core: bool = True
    missing_flag: str = ""


# Role-specific B0 dimension maps.
#
# These maps ONLY reference columns that exist in the current
# ``rating_feature_matrix.parquet``. They are deliberately narrower than
# ``position_metrics.POSITION_DIMENSIONS`` (which references saves,
# psxg_minus_ga, progressive_passes, etc. — none of which are in the
# feature matrix today). When PRS-2 adds a compliant goalkeeping
# feature source, the GK map will be expanded; until then GK is
# availability-only and explicitly provisional.
B0_DIMENSIONS: dict[RoleFamily, tuple[B0Dimension, ...]] = {
    RoleFamily.GK: (
        B0Dimension(
            key="availability",
            label="出勤",
            columns=("minutes_played", "starts"),
            core=True,
        ),
    ),
    RoleFamily.CB: (
        B0Dimension(
            key="defending",
            label="防守",
            columns=("tackles", "interceptions"),
            core=True,
            missing_flag="defense_missing",
        ),
        B0Dimension(
            key="possession",
            label="控球",
            columns=("passes",),
            core=False,
            missing_flag="possession_missing",
        ),
        B0Dimension(
            key="availability",
            label="出勤",
            columns=("minutes_played", "starts"),
            core=True,
        ),
    ),
    RoleFamily.FB: (
        B0Dimension(
            key="defending",
            label="防守",
            columns=("tackles", "interceptions"),
            core=True,
            missing_flag="defense_missing",
        ),
        B0Dimension(
            key="creation",
            label="创造",
            columns=("assists", "xa"),
            core=False,
            missing_flag="xT_VAEP_missing",
        ),
        B0Dimension(
            key="possession",
            label="控球",
            columns=("passes",),
            core=False,
            missing_flag="possession_missing",
        ),
        B0Dimension(
            key="availability",
            label="出勤",
            columns=("minutes_played", "starts"),
            core=True,
        ),
    ),
    RoleFamily.DM: (
        B0Dimension(
            key="defending",
            label="防守",
            columns=("tackles", "interceptions"),
            core=True,
            missing_flag="defense_missing",
        ),
        B0Dimension(
            key="possession",
            label="控球",
            columns=("passes",),
            core=False,
            missing_flag="possession_missing",
        ),
        B0Dimension(
            key="availability",
            label="出勤",
            columns=("minutes_played", "starts"),
            core=True,
        ),
    ),
    RoleFamily.CM: (
        B0Dimension(
            key="possession",
            label="控球",
            columns=("passes",),
            core=True,
            missing_flag="possession_missing",
        ),
        B0Dimension(
            key="creation",
            label="创造",
            columns=("assists", "xa"),
            core=False,
            missing_flag="xT_VAEP_missing",
        ),
        B0Dimension(
            key="availability",
            label="出勤",
            columns=("minutes_played", "starts"),
            core=True,
        ),
    ),
    RoleFamily.AM: (
        B0Dimension(
            key="creation",
            label="创造",
            columns=("assists", "xa"),
            core=True,
            missing_flag="xT_VAEP_missing",
        ),
        B0Dimension(
            key="finishing",
            label="终结",
            columns=("goals", "npxg"),
            core=False,
        ),
        B0Dimension(
            key="availability",
            label="出勤",
            columns=("minutes_played", "starts"),
            core=True,
        ),
    ),
    RoleFamily.W: (
        B0Dimension(
            key="attacking",
            label="进攻",
            columns=("goals", "assists", "npxg", "xa"),
            core=True,
            missing_flag="xT_VAEP_missing",
        ),
        B0Dimension(
            key="availability",
            label="出勤",
            columns=("minutes_played", "starts"),
            core=True,
        ),
    ),
    RoleFamily.ST: (
        B0Dimension(
            key="finishing",
            label="终结",
            columns=("goals", "npxg"),
            core=True,
        ),
        B0Dimension(
            key="attacking",
            label="进攻",
            columns=("assists", "xa"),
            core=False,
            missing_flag="xT_VAEP_missing",
        ),
        B0Dimension(
            key="availability",
            label="出勤",
            columns=("minutes_played", "starts"),
            core=True,
        ),
    ),
}


# ---------------------------------------------------------------------------
# Score dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class B0DimensionScore:
    """Per-dimension B0 result for one player."""

    dimension: str
    label: str
    columns_present: tuple[str, ...]
    columns_missing: tuple[str, ...]
    column_percentiles: dict[str, float]
    dimension_percentile: float
    is_missing: bool
    is_core: bool
    missing_flag: str

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
        }


@dataclass(frozen=True)
class B0PlayerScore:
    """Full B0 score for one player-season.

    The ``score`` is the equal-weighted mean of *core* dimension
    percentiles (supporting dimensions are included only when not
    missing). ``confidence`` is ``high`` when all core dimensions have
    data, ``medium`` when at least one core dimension is missing but
    the score is still computed, and ``low`` when all core dimensions
    are missing (in which case ``score`` is the neutral 50.0).
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
    dimensions: tuple[B0DimensionScore, ...]
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
            "cross_position_comparable": self.cross_position_comparable,
        }


@dataclass(frozen=True)
class B0RoleSummary:
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
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_float(value: Any) -> float | None:
    """Coerce a value to float, returning None for NaN/None/non-numeric."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    try:
        f = float(value)
        if math.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _column_percentile(
    value: float,
    pool_values: list[float],
    direction: str = "higher_better",
) -> float:
    """Compute percentile rank of *value* within *pool_values* in [0, 100].

    Uses strict-less-than counting so ties get the lower percentile
    (matching ``position_metrics._single_column_percentile``). Empty
    pool returns 50.0 (neutral). For ``lower_better`` direction, inverts
    the comparison.
    """
    if not pool_values:
        return 50.0
    if direction == "higher_better":
        below = sum(1 for v in pool_values if v < value)
    else:
        below = sum(1 for v in pool_values if v > value)
    return (below / len(pool_values)) * 100.0


def _dimension_percentile(
    player_row: dict[str, Any],
    pool_rows: list[dict[str, Any]],
    dimension: B0Dimension,
) -> B0DimensionScore:
    """Compute one dimension's percentile for one player (legacy path).

    .. deprecated:: Used only when ``column_arrays`` is not available.
        The hot path uses ``_dimension_percentile_vectorised`` which
        reuses precomputed numpy arrays. This pure-Python version is
        retained for unit-test readability and as a cross-check.
    """
    columns_present: list[str] = []
    columns_missing: list[str] = []
    column_percentiles: dict[str, float] = {}

    for col in dimension.columns:
        player_val = _to_float(player_row.get(col))
        if player_val is None:
            columns_missing.append(col)
            continue
        # Build the pool of non-missing values for this column.
        pool_values: list[float] = []
        for row in pool_rows:
            v = _to_float(row.get(col))
            if v is not None:
                pool_values.append(v)
        if not pool_values:
            # Column exists for the player but pool has no data —
            # cannot compute a percentile. Treat as missing.
            columns_missing.append(col)
            continue
        pct = _column_percentile(player_val, pool_values, dimension.direction)
        column_percentiles[col] = pct
        columns_present.append(col)

    if column_percentiles:
        dim_pct = sum(column_percentiles.values()) / len(column_percentiles)
        is_missing = False
    else:
        dim_pct = 50.0
        is_missing = True

    return B0DimensionScore(
        dimension=dimension.key,
        label=dimension.label,
        columns_present=tuple(columns_present),
        columns_missing=tuple(columns_missing),
        column_percentiles=column_percentiles,
        dimension_percentile=dim_pct,
        is_missing=is_missing,
        is_core=dimension.core,
        missing_flag=dimension.missing_flag,
    )


def _dimension_percentile_vectorised(
    player_idx: int,
    column_arrays: dict[str, np.ndarray],
    dimension: B0Dimension,
) -> B0DimensionScore:
    """Compute one dimension's percentile for one player via numpy.

    Same arithmetic as ``_dimension_percentile`` but uses the
    precomputed per-column numpy arrays instead of iterating over
    pool rows. This is the hot path used by ``_player_score`` in
    ``compute_b0_baseline``.
    """
    columns_present: list[str] = []
    columns_missing: list[str] = []
    column_percentiles: dict[str, float] = {}

    for col in dimension.columns:
        arr = column_arrays[col]
        player_val = arr[player_idx]
        if np.isnan(player_val):
            columns_missing.append(col)
            continue
        valid_mask = ~np.isnan(arr)
        n_valid = int(valid_mask.sum())
        if n_valid == 0:
            columns_missing.append(col)
            continue
        sorted_valid = np.sort(arr[valid_mask])
        # searchsorted 'left' = count of values strictly less than player_val.
        # This matches the legacy _column_percentile which uses `v < value`.
        position = int(np.searchsorted(sorted_valid, player_val, side="left"))
        pct = (position / n_valid) * 100.0
        column_percentiles[col] = pct
        columns_present.append(col)

    if column_percentiles:
        dim_pct = sum(column_percentiles.values()) / len(column_percentiles)
        is_missing = False
    else:
        dim_pct = 50.0
        is_missing = True

    return B0DimensionScore(
        dimension=dimension.key,
        label=dimension.label,
        columns_present=tuple(columns_present),
        columns_missing=tuple(columns_missing),
        column_percentiles=column_percentiles,
        dimension_percentile=dim_pct,
        is_missing=is_missing,
        is_core=dimension.core,
        missing_flag=dimension.missing_flag,
    )


def _pool_column_arrays(
    pool_rows: list[dict[str, Any]],
    columns: tuple[str, ...],
) -> dict[str, np.ndarray]:
    """Build a float numpy array per column, with NaN for missing.

    Used by the vectorised score path so the bootstrap can run in
    seconds instead of minutes.
    """
    arrays: dict[str, np.ndarray] = {}
    for col in columns:
        arr = np.full(len(pool_rows), np.nan, dtype=np.float64)
        for i, row in enumerate(pool_rows):
            v = _to_float(row.get(col))
            if v is not None:
                arr[i] = v
        arrays[col] = arr
    return arrays


def _vectorised_scores(
    pool_rows: list[dict[str, Any]],
    dimensions: tuple[B0Dimension, ...],
    column_arrays: dict[str, np.ndarray] | None = None,
) -> np.ndarray:
    """Compute B0 score for every player in the pool, vectorised.

    Returns a 1D numpy array of length ``len(pool_rows)``. The score
    is the equal-weighted mean of available dimension percentiles
    (core + supporting, only dimensions with at least one non-missing
    column for that player).

    ``column_arrays`` is an optional pre-built cache from
    ``_pool_column_arrays``; if None, it is built from ``pool_rows``.
    The bootstrap path pre-builds the cache once for the original pool
    and uses index arithmetic to resample, avoiding repeated dict
    lookups.
    """
    n = len(pool_rows)
    if n == 0:
        return np.zeros(0, dtype=np.float64)

    # Gather the full set of columns we need.
    all_cols: list[str] = []
    seen: set[str] = set()
    for dim in dimensions:
        for col in dim.columns:
            if col not in seen:
                seen.add(col)
                all_cols.append(col)

    if column_arrays is None:
        column_arrays = _pool_column_arrays(pool_rows, tuple(all_cols))

    # Player values per column (same arrays — the "player" is each row
    # of the pool, so player_col == pool_col for the base score).
    scores = np.zeros(n, dtype=np.float64)
    counts = np.zeros(n, dtype=np.int64)

    for dim in dimensions:
        # Build a mask of players with at least one non-missing column
        # in this dimension.
        dim_present = np.zeros(n, dtype=bool)
        dim_pct_sum = np.zeros(n, dtype=np.float64)
        n_present_cols = np.zeros(n, dtype=np.int64)

        for col in dim.columns:
            arr = column_arrays[col]
            valid_mask = ~np.isnan(arr)
            n_valid = int(valid_mask.sum())
            if n_valid == 0:
                continue
            # For each player, if their value is non-NaN, compute the
            # percentile of their value against the non-NaN pool.
            sorted_valid = np.sort(arr[valid_mask])
            # searchsorted with 'left' gives count of values strictly
            # less than v (matches the legacy _column_percentile which
            # uses `v < value`). Ties get the lower percentile.
            pct = np.full(n, np.nan, dtype=np.float64)
            player_valid = valid_mask
            positions = np.searchsorted(
                sorted_valid, arr, side="left"
            )
            pct[player_valid] = (
                positions[player_valid].astype(np.float64) / n_valid * 100.0
            )
            # Accumulate.
            dim_pct_sum = np.where(
                np.isnan(pct), dim_pct_sum, dim_pct_sum + pct
            )
            n_present_cols = np.where(
                np.isnan(pct), n_present_cols, n_present_cols + 1
            )
            dim_present = dim_present | player_valid

        # Dimension percentile = mean of available column percentiles.
        # Players with no columns present get NaN (dimension is missing).
        dim_pct = np.where(
            dim_present & (n_present_cols > 0),
            dim_pct_sum / np.where(n_present_cols > 0, n_present_cols, 1),
            np.nan,
        )

        # Add to score accumulator (only for players where dim is present).
        valid_dim = ~np.isnan(dim_pct)
        scores = np.where(valid_dim, scores + dim_pct, scores)
        counts = np.where(valid_dim, counts + 1, counts)

    # Final score = sum / count. Players with 0 available dims get 50.0.
    final = np.where(counts > 0, scores / np.where(counts > 0, counts, 1), 50.0)
    return final


def _vectorised_scores_for_resample(
    base_column_arrays: dict[str, np.ndarray],
    dimensions: tuple[B0Dimension, ...],
    sample_indices: np.ndarray,
    n_orig: int,
) -> np.ndarray:
    """Compute B0 scores for the original players under a resampled pool.

    ``base_column_arrays`` is the per-column array for the original
    pool (length ``n_orig``). ``sample_indices`` is a 1D numpy array of
    length ``n_orig`` giving the indices resampled with replacement.

    Returns a 1D numpy array of length ``n_orig`` giving each original
    player's B0 score computed against the resampled pool.
    """
    if n_orig == 0:
        return np.zeros(0, dtype=np.float64)

    scores = np.zeros(n_orig, dtype=np.float64)
    counts = np.zeros(n_orig, dtype=np.int64)

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
            # side='left' matches the legacy strict-less-than semantics.
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
        valid_dim = ~np.isnan(dim_pct)
        scores = np.where(valid_dim, scores + dim_pct, scores)
        counts = np.where(valid_dim, counts + 1, counts)

    final = np.where(counts > 0, scores / np.where(counts > 0, counts, 1), 50.0)
    return final


def _player_score(
    player_row: dict[str, Any],
    pool_rows: list[dict[str, Any]],
    dimensions: tuple[B0Dimension, ...],
    role_family: RoleFamily,
    rank_in_role: int | None,
    role_pool_size: int,
    rank_interval: tuple[int | None, int | None, int | None] | None,
    *,
    player_idx: int | None = None,
    column_arrays: dict[str, np.ndarray] | None = None,
) -> B0PlayerScore:
    """Compute the full B0PlayerScore for one player.

    The overall score is the equal-weighted mean of *available*
    dimensions, but core dimensions are required for ``high`` confidence.
    If all core dimensions are missing, the score is the neutral 50.0
    and confidence is ``low``.

    Two paths:
    - **Vectorised** (``player_idx`` and ``column_arrays`` provided):
      uses ``_dimension_percentile_vectorised`` which reuses precomputed
      numpy arrays. This is the hot path used by ``compute_b0_baseline``.
    - **Legacy** (``player_idx`` is None): falls back to
      ``_dimension_percentile`` which iterates over ``pool_rows``. Used
      by unit tests for cross-checking against the vectorised path.
    """
    dim_scores: list[B0DimensionScore] = []
    for dim in dimensions:
        if player_idx is not None and column_arrays is not None:
            dim_scores.append(
                _dimension_percentile_vectorised(
                    player_idx, column_arrays, dim
                )
            )
        else:
            dim_scores.append(_dimension_percentile(player_row, pool_rows, dim))

    core_dims = [d for d in dim_scores if d.is_core]
    core_used = [d for d in core_dims if not d.is_missing]
    core_missing = [d for d in core_dims if d.is_missing]

    # Supporting dimensions are included only when not missing.
    supporting_used = [
        d for d in dim_scores if not d.is_core and not d.is_missing
    ]

    all_used = core_used + supporting_used

    if all_used:
        score = sum(d.dimension_percentile for d in all_used) / len(all_used)
    else:
        # All core missing AND no supporting — neutral placeholder.
        score = 50.0

    # Confidence
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
        missing_reason = "全部核心维度缺失；B0 评分为占位 50.0，不参与排名解读"

    # Rank interval
    if rank_interval is not None:
        rank_p5, rank_p50, rank_p95 = rank_interval
    else:
        rank_p5, rank_p50, rank_p95 = None, None, None

    return B0PlayerScore(
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
        cross_position_comparable=False,
    )


def _bootstrap_rank_interval(
    pool_rows: list[dict[str, Any]],
    player_scores: list[float],
    dimensions: tuple[B0Dimension, ...],
    n_bootstrap: int,
    seed: int,
) -> list[tuple[int | None, int | None, int | None] | None]:
    """Bootstrap rank interval for each player in the pool.

    For each bootstrap resample (sampling pool rows with replacement),
    recompute every player's B0 score under the resampled pool and
    record their rank. Then for each player compute the 5th/50th/95th
    percentile of their rank across all resamples.

    Returns a list aligned with ``player_scores``; each entry is either
    a (p5, p50, p95) tuple of ints (1-indexed ranks) or None if the
    pool was too small for bootstrap to be meaningful.

    Vectorised with numpy: the per-column arrays are built once, the
    random indices are drawn in a single batch, the ranking uses
    searchsorted (O(n log n) per resample), and the final percentiles
    are computed via np.percentile on the ranks matrix.
    """
    n = len(pool_rows)
    if n < _MIN_BOOTSTRAP_POOL or n_bootstrap <= 0:
        return [None] * len(player_scores)

    # Pre-build the per-column arrays once.
    all_cols: list[str] = []
    seen: set[str] = set()
    for dim in dimensions:
        for col in dim.columns:
            if col not in seen:
                seen.add(col)
                all_cols.append(col)
    base_arrays = _pool_column_arrays(pool_rows, tuple(all_cols))

    # Draw all bootstrap indices in one batch for speed.
    rng = np.random.default_rng(seed)
    # Shape (n_bootstrap, n): each row is one resample's indices.
    all_sample_indices = rng.integers(0, n, size=(n_bootstrap, n))

    # ranks_matrix[i, b] = rank of player i in bootstrap resample b.
    ranks_matrix = np.zeros((n, n_bootstrap), dtype=np.int64)

    for b in range(n_bootstrap):
        sample_indices = all_sample_indices[b]
        sample_scores = _vectorised_scores_for_resample(
            base_arrays, dimensions, sample_indices, n
        )
        # Rank sample_scores descending (higher score = better rank = 1).
        # Min-rank for ties: rank = 1 + (n - searchsorted(sorted_asc, s, 'right'))
        sorted_asc = np.sort(sample_scores)
        right_positions = np.searchsorted(sorted_asc, sample_scores, side="right")
        ranks = 1 + n - right_positions
        ranks_matrix[:, b] = ranks

    # Compute 5th/50th/95th percentile of each player's rank list.
    # np.percentile with nearest-rank method to match the legacy helper.
    p5_arr = np.percentile(ranks_matrix, 5, axis=1, method="nearest")
    p50_arr = np.percentile(ranks_matrix, 50, axis=1, method="nearest")
    p95_arr = np.percentile(ranks_matrix, 95, axis=1, method="nearest")

    result: list[tuple[int | None, int | None, int | None] | None] = []
    for i in range(n):
        result.append(
            (int(p5_arr[i]), int(p50_arr[i]), int(p95_arr[i]))
        )

    return result


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def compute_b0_baseline(
    settings: PlatformSettings | None = None,
    *,
    feature_matrix: Any = None,
    cohort_definition: Any | None = None,
    n_bootstrap: int = DEFAULT_BOOTSTRAP,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Compute the B0 raw_percentile baseline for the local data.

    Loads ``rating_feature_matrix.parquet`` (or accepts a DataFrame via
    ``feature_matrix``), optionally applies a ``CohortDefinition`` to
    restrict membership, then computes the B0 score for every
    player-season in the cohort.

    Args:
        settings: Platform settings. If None, uses
            ``PlatformSettings.from_root()``.
        feature_matrix: Optional pre-loaded feature matrix DataFrame.
            If None, loads from ``rating_feature_matrix.parquet``.
        cohort_definition: Optional ``CohortDefinition``. If provided,
            only player-seasons whose ``canonical_player_id|season_id``
            appears in the cohort membership are scored. This keeps B0
            honest about exactly which population it scored.
        n_bootstrap: Bootstrap resample count for rank intervals.
            Default 200.
        seed: Random seed for bootstrap. Default 20260731.

    Returns:
        A JSON-serialisable dict with schema
        ``scoutfootball.baseline-b0`` v1.0.0. The dict includes the
        cohort hash (if a definition was provided), per-player scores,
        per-role summaries, and explicit limitations.
    """
    resolved = settings or PlatformSettings.from_root()

    # Load feature matrix
    if feature_matrix is None:
        fm_path = resolved.gold_root / "feature_store" / "rating_feature_matrix.parquet"
        if not fm_path.exists():
            return {
                "schema": BASELINE_B0_SCHEMA,
                "schema_version": BASELINE_B0_VERSION,
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
                "schema": BASELINE_B0_SCHEMA,
                "schema_version": BASELINE_B0_VERSION,
                "generated_at": _now(),
                "status": "unavailable",
                "evidence": {
                    "reason": f"rating_feature_matrix read failed: {exc}"
                },
                "limitations": _LIMITATIONS,
            }

    if feature_matrix is None or len(feature_matrix) == 0:
        return {
            "schema": BASELINE_B0_SCHEMA,
            "schema_version": BASELINE_B0_VERSION,
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
                "schema": BASELINE_B0_SCHEMA,
                "schema_version": BASELINE_B0_VERSION,
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
                "schema": BASELINE_B0_SCHEMA,
                "schema_version": BASELINE_B0_VERSION,
                "generated_at": _now(),
                "status": "ok",
                "cohort_hash": cohort_hash,
                "membership_hash": membership_hash,
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

    # Determine role_family for each row using classify_role_family.
    from scoutfootball.evaluation.role_system import classify_role_family

    fm = feature_matrix
    # Build the list of rows to score. Each row is a dict with at
    # least canonical_player_id, season_id, player_name, position_group
    # and the B0 dimension columns.
    rows_to_score: list[dict[str, Any]] = []
    for _, row in fm.iterrows():
        cid = row.get("canonical_player_id")
        if cid is None and "player_id" in fm.columns:
            # rating_feature_matrix.parquet (pre-canonical) carries
            # player_id but not canonical_player_id. Use the source-
            # stable fallback so membership filtering still works for
            # callers that did not resolve canonical IDs.
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
    all_player_scores: list[B0PlayerScore] = []
    role_summaries: list[B0RoleSummary] = []
    by_role_counts: dict[str, int] = {}

    for role_family in RoleFamily:
        if role_family == RoleFamily.UNKNOWN:
            # UNKNOWN rows are not scored by B0; the limitations note
            # explains why. We still count them.
            unknown_rows = by_role.get(role_family, [])
            if unknown_rows:
                by_role_counts[role_family.value] = len(unknown_rows)
            continue

        pool = by_role.get(role_family, [])
        if not pool:
            continue

        dims = B0_DIMENSIONS.get(role_family)
        if dims is None:
            # No dimension map for this role — skip honestly.
            continue

        # Compute each player's base score (no bootstrap yet) using the
        # vectorised path. This is the same computation that the
        # bootstrap uses per resample, but with the original pool.
        base_scores_array = _vectorised_scores(pool, dims)
        base_scores: list[float] = base_scores_array.tolist()

        # Compute ranks within the role (1 = highest score).
        # Ties get the same rank (min-rank convention).
        n_pool = len(pool)
        indexed = sorted(
            enumerate(base_scores), key=lambda kv: -kv[1]
        )
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
            pool, base_scores, dims, n_bootstrap, seed
        )

        # Build B0PlayerScore for each member of this role.
        for i, player_row in enumerate(pool):
            ps = _player_score(
                player_row=player_row,
                pool_rows=pool,
                dimensions=dims,
                role_family=role_family,
                rank_in_role=ranks[i],
                role_pool_size=n_pool,
                rank_interval=rank_intervals[i],
            )
            all_player_scores.append(ps)

        # Role summary — gather only players in this role.
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
            B0RoleSummary(
                role_family=role_family.value,
                member_count=n_pool,
                high_confidence_count=high,
                medium_confidence_count=med,
                low_confidence_count=low,
                score_min=score_min,
                score_median=score_median,
                score_max=score_max,
                dimensions_available=dims_available,
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
        "schema": BASELINE_B0_SCHEMA,
        "schema_version": BASELINE_B0_VERSION,
        "generated_at": _now(),
        "status": "ok",
        "cohort_hash": cohort_hash,
        "membership_hash": membership_hash,
        "parameters": {
            "n_bootstrap": n_bootstrap,
            "seed": seed,
            "min_bootstrap_pool": _MIN_BOOTSTRAP_POOL,
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
        "B0 是 PRS-2 透明 baseline 的最简单形式：角色内等权百分位。"
        "它不是球员能力的最终判断，也不替代 PRS-2 后续的 B1/B2/B3 候选。"
        "B0 的价值在于可手工复算、缺失数据显式可见、不确定性通过 bootstrap "
        "排名区间呈现。"
    ),
    (
        "B0 仅在 RoleFamily 内排名，不产生跨位置可比分数。"
        "cross_position_comparable 字段对所有球员为 False；跨位置比较"
        "需要 PRS-2 后续的 B2 收缩或显式校准，B0 不提供。"
    ),
    (
        "B0_DIMENSIONS 只引用 rating_feature_matrix.parquet 当前实际"
        "存在的列（goals/assists/npxg/xa/tackles/interceptions/passes/"
        "minutes_played/starts 等）。position_metrics.POSITION_DIMENSIONS "
        "中引用的 saves/psxg/progressive_passes 等列在当前特征矩阵中"
        "不存在，因此 B0 维度定义比 POSITION_DIMENSIONS 更窄。当 PRS-2 "
        "新增合规特征源时，B0_DIMENSIONS 会同步扩展。"
    ),
    (
        "GK 角色的 B0 是 availability-only 占位：当前 rating_feature_matrix"
        "没有任何门将专属指标（saves/psxg/claims 等），PRS-2 退出门槛"
        "'GK 不再使用外场防守代理作为核心指标' 要求 GK 不消费 tackles/"
        "interceptions。在 PRS-2 引入合规门将特征源之前，GK 的 B0 分数"
        "仅有出勤维度，confidence 通常为 high 但分数本身没有评价意义，"
        "应在解读时显式标注 'gk_provisional'。"
    ),
    (
        "缺失数据处理：每个维度的 *_missing 标记（defense_missing/"
        "possession_missing/xT_VAEP_missing/goalkeeper_missing）会传入"
        "B0DimensionScore.missing_flag；若球员某核心维度全部列缺失，"
        "该球员 confidence 降为 medium，missing_reason 列出缺失维度；"
        "若全部核心维度缺失，confidence 降为 low，评分为占位 50.0，"
        "不参与排名解读。B0 从不把缺失值静默解释为平均能力。"
    ),
    (
        "Bootstrap 排名区间：当角色池 >= 10 人时，B0 用固定 seed 做 "
        f"{DEFAULT_BOOTSTRAP} 次重采样，每次重采样后重新计算所有球员"
        "分数并赋予 1-indexed rank（同分同 rank，min-rank 约定）。"
        "报告每位球员 rank 的 p5/p50/p95。当角色池 < 10 人时 rank_interval "
        "为 None；这种小样本不应被解读为稳健排名。"
    ),
    (
        "Cohort 过滤：若传入 cohort_definition，B0 仅对 cohort membership "
        "中的 canonical_player_id|season_id 对评分；未传入则对特征矩阵"
        "全部行评分。建议始终传入显式 cohort 定义，以避免隐式人群漂移。"
    ),
    (
        "canonical_player_id：rating_feature_matrix.parquet 当前未携带"
        "canonical_player_id 列；B0 用 unresolved:<source>:<player_id> "
        "作为 source-stable fallback，与 PRS-1 canonical_resolver 一致。"
        "若调用者已通过 canonical_resolver 解析，应使用解析后的 DataFrame "
        "通过 feature_matrix 参数传入。"
    ),
    (
        "B0 是 read-only 诊断；不修改 rating_feature_matrix.parquet 或"
        "任何其他产物。所有评分仅存在于返回的 dict 中，调用者可自行"
        "持久化到 data/reports/baseline_b0/ 或研究包。"
    ),
]


__all__ = [
    "BASELINE_B0_SCHEMA",
    "BASELINE_B0_VERSION",
    "DEFAULT_BOOTSTRAP",
    "DEFAULT_SEED",
    "B0Dimension",
    "B0_DIMENSIONS",
    "B0DimensionScore",
    "B0PlayerScore",
    "B0RoleSummary",
    "compute_b0_baseline",
]

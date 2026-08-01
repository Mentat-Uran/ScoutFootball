"""PRS-2 B2 minutes-based empirical Bayes shrinkage baseline.

PRS-2 (see ``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`` §8.1 and §8.4)
requires a minutes-based shrinkage baseline that addresses B0's biggest
known limitation: a player with 90 minutes and a high per-90 rate would
get the same B0 percentile as a player with 2000 minutes and the same
per-90 rate, even though the low-minute observation is far noisier.

B2 applies a transparent, hand-recomputable empirical Bayes shrinkage
to the B0 score. The model is:

    observed_score_i ~ N(true_score_i, sigma2_i)
    true_score_i     ~ N(prior_mean, tau2)               (role prior)

We assume the observation noise scales inversely with minutes played:

    sigma2_i = tau2 * (reference_minutes / minutes_played_i)

Under this assumption the posterior mean (shrinkage estimator) is:

    b2_score_i = w_i * prior_mean + (1 - w_i) * b0_score_i

where the shrinkage weight simplifies to:

    w_i = reference_minutes / (reference_minutes + minutes_played_i)

A player with ``reference_minutes`` (default 900 = 10 full matches) gets
50% shrinkage. A 90-minute player gets ~91% shrinkage (heavily pulled
toward the role prior). A 3000-minute player gets ~23% shrinkage (mostly
trusted). The formula is independent of tau2 because tau2 cancels —
the only tunable parameter is ``reference_minutes``.

The prior mean is computed from the "stable core" of the role pool:
players with ``minutes_played >= reference_minutes``. This avoids the
prior being contaminated by the very low-minute noise B2 is trying to
shrink. If no player meets the threshold (very small pool), B2 falls
back to the full pool mean and marks ``prior_source`` accordingly.

Design contract (PRS-2 退出门槛 "分钟收缩或样本量惩罚对低出场球员可见"):

1. **Hand-recomputable.** Every B2 score is a closed-form convex
   combination of the player's B0 score and their role-pool prior mean.
   The output records ``b0_score``, ``b2_score``, ``shrinkage_weight``,
   ``prior_mean``, ``prior_source``, and ``minutes_played`` so the
   maintainer can reproduce the arithmetic by hand from B0 + the
   parquet.

2. **Inherits B0's honest missing-data handling.** B2 does not weaken
   any of B0's confidence levels. If B0 returned ``confidence=low`` for
   a player (all core dimensions missing), B2 keeps that verdict and
   additionally applies full shrinkage (``b2_score = prior_mean``),
   because there is nothing in the player's own row to trust.

3. **Minutes-missing handling.** ``rating_feature_matrix.parquet``
   currently has ``minutes_played`` for every row (verified 2026-07-31),
   but B2 still defends against missing/zero minutes: it applies full
   shrinkage (``w = 1.0``, ``b2_score = prior_mean``) and marks
   ``minutes_input_missing=True``, capping confidence at ``medium``.

4. **GK independence.** B2 inherits B0's GK availability-only
   placeholder. GK's B2 still shrinks the availability-derived B0 score
   toward the GK prior; this is honest but should still be labelled
   ``gk_provisional`` until PRS-2 adds a compliant goalkeeping source.

5. **Within-role only.** Like B0, B2 never produces a cross-position
   ranking. ``cross_position_comparable=False`` for every row.

6. **Bootstrap rank interval on B2 scores.** For each role, B2
   resamples the pool with replacement ``n_bootstrap`` times (seed
   fixed). Each resample recomputes B0 scores (pool composition
   changes), the prior mean (which depends on which players meet the
   reference_minutes threshold in the resample), the shrinkage weights
   (which depend on minutes, which are fixed per player), and the B2
   scores. We then report each player's rank p5/p50/p95 across
   resamples.

7. **Read-only.** B2 is a pure diagnostic. It does not modify
   ``rating_feature_matrix.parquet`` or any other artifact. Output is a
   JSON-serialisable dict.

B2 does NOT replace B0; both are reported side-by-side. The maintainer
is expected to inspect cases where B2 and B0 ranks diverge sharply
(those are the low-minute players B2 is most skeptical of).
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
    BASELINE_B0_SCHEMA,
    BASELINE_B0_VERSION,
    B0Dimension,
    _player_score,
    _pool_column_arrays,
    _to_float,
    _vectorised_scores,
    _vectorised_scores_for_resample,
)
from scoutfootball.evaluation.role_system import RoleFamily, classify_role_family

BASELINE_B2_SCHEMA = "scoutfootball.baseline-b2"
BASELINE_B2_VERSION = "1.0.0"

# Default reference minutes: 10 full matches. At this point shrinkage = 50%.
# 900 is a transparent, defensible choice (FIFA recognizes 90 min as one
# match; 10 matches is a common "minimum reliable sample" heuristic).
# Per AGENTS.md "without real label verification, do not raise the
# availability cap back above 0.25" — the cap refers to using availability
# as a *score* component. B2 uses minutes as a *reliability* signal that
# only affects shrinkage, not as a direct score input, so the 0.25 cap
# does not apply. The shrinkage formula is monotonic and bounded.
DEFAULT_REFERENCE_MINUTES = 900

DEFAULT_BOOTSTRAP = 200
DEFAULT_SEED = 20260731


# ---------------------------------------------------------------------------
# Score dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class B2PlayerScore:
    """Full B2 score for one player-season, with B0 alongside.

    Fields are grouped: identity, B0 baseline (inherited), B2 shrinkage
    (new), and meta. All floats are stored at full precision and rounded
    only at ``to_dict`` time so the maintainer can cross-check arithmetic.
    """

    # Identity
    canonical_player_id: str
    player_name: str
    season_id: str
    role_family: str

    # B0 baseline (carried forward for transparency)
    b0_score: float
    b0_confidence: str
    b0_missing_reason: str
    b0_rank_in_role: int | None
    b0_role_pool_size: int
    b0_rank_p5: int | None
    b0_rank_p50: int | None
    b0_rank_p95: int | None

    # B2 shrinkage result
    b2_score: float
    b2_rank_in_role: int | None
    b2_role_pool_size: int
    b2_rank_p5: int | None
    b2_rank_p50: int | None
    b2_rank_p95: int | None
    shrinkage_weight: float  # 0..1; higher = more shrinkage to prior
    prior_mean: float
    prior_source: str  # "stable_core" | "fallback_full_pool" | "empty"
    minutes_played: float | None
    minutes_input_missing: bool

    # Confidence for B2 (may be lower than B0 if minutes missing or prior
    # is from fallback pool)
    b2_confidence: str
    b2_missing_reason: str

    cross_position_comparable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_player_id": self.canonical_player_id,
            "player_name": self.player_name,
            "season_id": self.season_id,
            "role_family": self.role_family,
            "b0_score": round(self.b0_score, 4),
            "b0_confidence": self.b0_confidence,
            "b0_missing_reason": self.b0_missing_reason,
            "b0_rank_in_role": self.b0_rank_in_role,
            "b0_role_pool_size": self.b0_role_pool_size,
            "b0_rank_interval": {
                "p5": self.b0_rank_p5,
                "p50": self.b0_rank_p50,
                "p95": self.b0_rank_p95,
            }
            if self.b0_rank_p5 is not None
            else None,
            "b2_score": round(self.b2_score, 4),
            "b2_rank_in_role": self.b2_rank_in_role,
            "b2_role_pool_size": self.b2_role_pool_size,
            "b2_rank_interval": {
                "p5": self.b2_rank_p5,
                "p50": self.b2_rank_p50,
                "p95": self.b2_rank_p95,
            }
            if self.b2_rank_p5 is not None
            else None,
            "shrinkage_weight": round(self.shrinkage_weight, 4),
            "prior_mean": round(self.prior_mean, 4),
            "prior_source": self.prior_source,
            "minutes_played": (
                round(self.minutes_played, 2)
                if self.minutes_played is not None
                else None
            ),
            "minutes_input_missing": self.minutes_input_missing,
            "b2_confidence": self.b2_confidence,
            "b2_missing_reason": self.b2_missing_reason,
            "cross_position_comparable": self.cross_position_comparable,
        }


@dataclass(frozen=True)
class B2RoleSummary:
    """Aggregate summary for one role family under B2."""

    role_family: str
    member_count: int
    stable_core_count: int  # players with minutes >= reference_minutes
    prior_mean: float
    prior_source: str
    b0_score_median: float
    b2_score_min: float
    b2_score_median: float
    b2_score_max: float
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    dimensions_available: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_family": self.role_family,
            "member_count": self.member_count,
            "stable_core_count": self.stable_core_count,
            "prior_mean": round(self.prior_mean, 4),
            "prior_source": self.prior_source,
            "b0_score_median": round(self.b0_score_median, 4),
            "b2_score_min": round(self.b2_score_min, 4),
            "b2_score_median": round(self.b2_score_median, 4),
            "b2_score_max": round(self.b2_score_max, 4),
            "confidence_counts": {
                "high": self.high_confidence_count,
                "medium": self.medium_confidence_count,
                "low": self.low_confidence_count,
            },
            "dimensions_available": list(self.dimensions_available),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compute_prior_mean(
    b0_scores: np.ndarray,
    minutes: np.ndarray,
    reference_minutes: float,
) -> tuple[float, str]:
    """Compute the prior mean for a role pool.

    Returns ``(prior_mean, prior_source)``. ``prior_source`` is
    ``"stable_core"`` when at least one player has minutes >=
    reference_minutes (preferred path), ``"fallback_full_pool"`` when no
    player meets the threshold (small pool edge case), or
    ``"empty"`` when the pool is empty.
    """
    n = len(b0_scores)
    if n == 0:
        return 50.0, "empty"

    stable_mask = minutes >= reference_minutes
    if stable_mask.any():
        # Use minutes-weighted mean of stable core. Weighting by minutes
        # within the stable core prevents a 901-minute player from
        # dominating a 3000-minute player in the prior.
        stable_scores = b0_scores[stable_mask]
        stable_minutes = minutes[stable_mask]
        # Guard against all-zero minutes (would cause div-by-zero).
        total_minutes = float(stable_minutes.sum())
        if total_minutes > 0:
            prior = float(np.average(stable_scores, weights=stable_minutes))
        else:
            prior = float(stable_scores.mean())
        return prior, "stable_core"

    # Fallback: no player meets threshold. Use simple mean of full pool.
    return float(b0_scores.mean()), "fallback_full_pool"


def _shrinkage_weight(minutes: float, reference_minutes: float) -> float:
    """Compute shrinkage weight in [0, 1].

    ``w = reference_minutes / (reference_minutes + minutes)``. Returns
    1.0 (full shrinkage) when minutes <= 0 or non-finite.
    """
    if not math.isfinite(minutes) or minutes <= 0:
        return 1.0
    return reference_minutes / (reference_minutes + minutes)


def _apply_shrinkage(
    b0_scores: np.ndarray,
    minutes: np.ndarray,
    prior_mean: float,
    reference_minutes: float,
) -> np.ndarray:
    """Vectorised shrinkage for an entire role pool.

    Returns a 1D array of B2 scores. Players with missing/non-positive
    minutes get full shrinkage (b2 = prior_mean).
    """
    n = len(b0_scores)
    if n == 0:
        return np.zeros(0, dtype=np.float64)

    # Guard: minutes may contain NaN or non-positive values. Replace
    # those with 0 so the weight formula returns 1.0 (full shrinkage).
    safe_minutes = np.where(
        np.isfinite(minutes) & (minutes > 0), minutes, 0.0
    )
    weights = reference_minutes / (reference_minutes + safe_minutes)
    # weights = 1.0 where safe_minutes = 0; b2 = prior_mean there.
    b2 = weights * prior_mean + (1.0 - weights) * b0_scores
    return b2


def _compute_ranks_min_rank(scores: np.ndarray) -> np.ndarray:
    """Compute 1-indexed ranks (1 = highest score) using min-rank for ties.

    Vectorised: O(n log n) via sort + searchsorted.
    """
    n = len(scores)
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    sorted_asc = np.sort(scores)
    # searchsorted 'right' gives count of values <= score; for min-rank
    # we want count of values strictly greater than score, plus 1.
    # rank = 1 + (n - searchsorted(sorted_asc, score, 'right'))
    #      = 1 + n - right_positions
    right_positions = np.searchsorted(sorted_asc, scores, side="right")
    return (1 + n - right_positions).astype(np.int64)


def _bootstrap_b2_rank_interval(
    pool_rows: list[dict[str, Any]],
    dimensions: tuple[B0Dimension, ...],
    minutes_array: np.ndarray,
    reference_minutes: float,
    n_bootstrap: int,
    seed: int,
) -> list[tuple[int | None, int | None, int | None] | None]:
    """Bootstrap rank interval for each player's B2 score.

    For each resample:
      1. Resample pool rows with replacement.
      2. Recompute B0 scores under resampled pool (pool composition
         changes -> percentiles change).
      3. Recompute prior_mean under resampled pool (which players meet
         the reference_minutes threshold may change).
      4. Recompute shrinkage weights (minutes are per-player and fixed;
         the formula only depends on minutes, so weights are the same
         as the original pool's. But we still recompute b2 because b0
         and prior changed).
      5. Recompute B2 scores and ranks.

    Returns a list aligned with the original pool; each entry is
    (p5, p50, p95) or None when the pool is too small.
    """
    n = len(pool_rows)
    if n < _MIN_BOOTSTRAP_POOL or n_bootstrap <= 0:
        return [None] * n

    # Pre-build the per-column arrays once for the original pool.
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

    # ranks_matrix[i, b] = rank of player i in bootstrap resample b.
    ranks_matrix = np.zeros((n, n_bootstrap), dtype=np.int64)

    for b in range(n_bootstrap):
        sample_indices = all_sample_indices[b]
        # B0 scores under resampled pool.
        sample_b0 = _vectorised_scores_for_resample(
            base_arrays, dimensions, sample_indices, n
        )
        # Prior mean under resampled pool. Use the resampled minutes
        # (some players may appear multiple times, others zero times).
        sample_minutes = minutes_array[sample_indices]
        prior_mean, _ = _compute_prior_mean(
            sample_b0, sample_minutes, reference_minutes
        )
        # B2 scores under resampled pool. Shrinkage weights use the
        # ORIGINAL player's minutes (the player is fixed; only the pool
        # is resampled). So we pass the original minutes_array, not the
        # resampled one.
        sample_b2 = _apply_shrinkage(
            sample_b0, minutes_array, prior_mean, reference_minutes
        )
        ranks_matrix[:, b] = _compute_ranks_min_rank(sample_b2)

    p5_arr = np.percentile(ranks_matrix, 5, axis=1, method="nearest")
    p50_arr = np.percentile(ranks_matrix, 50, axis=1, method="nearest")
    p95_arr = np.percentile(ranks_matrix, 95, axis=1, method="nearest")

    result: list[tuple[int | None, int | None, int | None] | None] = []
    for i in range(n):
        result.append((int(p5_arr[i]), int(p50_arr[i]), int(p95_arr[i])))
    return result


def _b2_confidence_from_b0(
    b0_confidence: str,
    minutes_input_missing: bool,
    prior_source: str,
) -> tuple[str, str]:
    """Compute B2 confidence and missing_reason from B0 confidence + B2 inputs.

    - B0 low -> B2 low (cannot trust a player whose core dims were all
      missing; full shrinkage to prior is honest but not informative).
    - B0 medium + (minutes missing OR prior fallback) -> B2 medium.
    - B0 medium + clean inputs -> B2 medium (B0 medium already signals
      incomplete dimensions; shrinkage does not add new data).
    - B0 high + minutes missing -> B2 medium (we can't trust shrinkage
      without minutes).
    - B0 high + prior fallback -> B2 medium (prior is unreliable in
      very small pools).
    - B0 high + clean inputs -> B2 high.
    """
    reasons: list[str] = []

    if b0_confidence == "low":
        return (
            "low",
            "B0 confidence=low (全部核心维度缺失)；B2 应用完全收缩 "
            "(b2_score=prior_mean)，仅作为占位，不参与排名解读",
        )

    if b0_confidence == "medium":
        reasons.append("B0 confidence=medium (部分核心维度缺失)")

    if minutes_input_missing:
        reasons.append("minutes_played 缺失或非正；B2 应用完全收缩")

    if prior_source == "fallback_full_pool":
        reasons.append(
            "prior_source=fallback_full_pool (角色池中无球员达到 "
            "reference_minutes 阈值；prior 不可靠)"
        )

    if reasons:
        return "medium", "；".join(reasons)

    return "high", ""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_b2_baseline(
    settings: PlatformSettings | None = None,
    *,
    feature_matrix: Any = None,
    cohort_definition: Any | None = None,
    reference_minutes: float = DEFAULT_REFERENCE_MINUTES,
    n_bootstrap: int = DEFAULT_BOOTSTRAP,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Compute the B2 minutes-shrinkage baseline.

    Loads ``rating_feature_matrix.parquet`` (or accepts a DataFrame via
    ``feature_matrix``), optionally applies a ``CohortDefinition``, then
    computes both B0 and B2 scores for every player-season in the
    cohort. B2 applies empirical Bayes shrinkage to B0 using
    minutes-based reliability.

    Args:
        settings: Platform settings. If None, uses
            ``PlatformSettings.from_root()``.
        feature_matrix: Optional pre-loaded feature matrix DataFrame.
        cohort_definition: Optional ``CohortDefinition`` for membership
            filtering.
        reference_minutes: Minutes at which shrinkage weight = 0.5.
            Default 900 (10 full matches). Lower = more aggressive
            shrinkage; higher = less aggressive.
        n_bootstrap: Bootstrap resample count for B2 rank intervals.
            Default 200.
        seed: Random seed for bootstrap. Default 20260731.

    Returns:
        JSON-serialisable dict with schema
        ``scoutfootball.baseline-b2`` v1.0.0. Includes both B0 and B2
        scores per player, per-role summaries (with prior mean and
        stable-core count), and explicit limitations.
    """
    resolved = settings or PlatformSettings.from_root()

    # Validate reference_minutes.
    if not math.isfinite(reference_minutes) or reference_minutes <= 0:
        return {
            "schema": BASELINE_B2_SCHEMA,
            "schema_version": BASELINE_B2_VERSION,
            "generated_at": _now(),
            "status": "unavailable",
            "evidence": {
                "reason": (
                    f"reference_minutes must be a positive finite number; "
                    f"got {reference_minutes!r}"
                )
            },
            "limitations": _LIMITATIONS,
        }

    # Load feature matrix.
    if feature_matrix is None:
        fm_path = resolved.gold_root / "feature_store" / "rating_feature_matrix.parquet"
        if not fm_path.exists():
            return {
                "schema": BASELINE_B2_SCHEMA,
                "schema_version": BASELINE_B2_VERSION,
                "generated_at": _now(),
                "status": "unavailable",
                "evidence": {
                    "reason": "rating_feature_matrix.parquet missing"
                },
                "limitations": _LIMITATIONS,
            }
        try:
            import pandas as pd

            feature_matrix = pd.read_parquet(fm_path)
        except Exception as exc:  # noqa: BLE001 — read-only diagnostic
            return {
                "schema": BASELINE_B2_SCHEMA,
                "schema_version": BASELINE_B2_VERSION,
                "generated_at": _now(),
                "status": "unavailable",
                "evidence": {
                    "reason": f"rating_feature_matrix read failed: {exc}"
                },
                "limitations": _LIMITATIONS,
            }

    if feature_matrix is None or len(feature_matrix) == 0:
        return {
            "schema": BASELINE_B2_SCHEMA,
            "schema_version": BASELINE_B2_VERSION,
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
                "schema": BASELINE_B2_SCHEMA,
                "schema_version": BASELINE_B2_VERSION,
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
                "schema": BASELINE_B2_SCHEMA,
                "schema_version": BASELINE_B2_VERSION,
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

    all_player_scores: list[B2PlayerScore] = []
    role_summaries: list[B2RoleSummary] = []
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

        n_pool = len(pool)

        # --- B0 scores on original pool ---
        b0_scores_array = _vectorised_scores(pool, dims)
        b0_scores: list[float] = b0_scores_array.tolist()

        # --- B0 ranks on original pool ---
        b0_ranks_array = _compute_ranks_min_rank(b0_scores_array)
        b0_ranks: list[int] = b0_ranks_array.tolist()

        # --- B0 bootstrap rank intervals (reuse B0 helper) ---
        from scoutfootball.evaluation.baseline_b0 import (
            _bootstrap_rank_interval as _b0_bootstrap,
        )

        b0_rank_intervals = _b0_bootstrap(
            pool, b0_scores, dims, n_bootstrap, seed
        )

        # --- B2 inputs: minutes per player ---
        minutes_array = np.full(n_pool, np.nan, dtype=np.float64)
        for i, row in enumerate(pool):
            v = _to_float(row.get("minutes_played"))
            if v is not None:
                minutes_array[i] = v

        # --- B2 prior mean ---
        prior_mean, prior_source = _compute_prior_mean(
            b0_scores_array, minutes_array, reference_minutes
        )

        # --- B2 scores ---
        b2_scores_array = _apply_shrinkage(
            b0_scores_array, minutes_array, prior_mean, reference_minutes
        )
        b2_scores: list[float] = b2_scores_array.tolist()

        # --- B2 ranks ---
        b2_ranks_array = _compute_ranks_min_rank(b2_scores_array)
        b2_ranks: list[int] = b2_ranks_array.tolist()

        # --- B2 bootstrap rank intervals ---
        b2_rank_intervals = _bootstrap_b2_rank_interval(
            pool,
            dims,
            minutes_array,
            reference_minutes,
            n_bootstrap,
            seed,
        )

        # --- Build B2PlayerScore per player ---
        # Pre-compute B0 dimension breakdown once per player (for the
        # B0PlayerScore that _player_score returns). We reuse the same
        # column_arrays that _vectorised_scores built implicitly; here
        # we rebuild them once for clarity (cost is small).
        all_cols: list[str] = []
        seen: set[str] = set()
        for dim in dims:
            for col in dim.columns:
                if col not in seen:
                    seen.add(col)
                    all_cols.append(col)
        column_arrays = _pool_column_arrays(pool, tuple(all_cols))

        role_b0_confidences: list[str] = []
        role_b2_confidences: list[str] = []
        role_b0_missing_reasons: list[str] = []

        for i, player_row in enumerate(pool):
            # Build B0PlayerScore for transparency (uses the same
            # vectorised dimension breakdown that B0 uses).
            b0_ps = _player_score(
                player_row=player_row,
                pool_rows=pool,
                dimensions=dims,
                role_family=role_family,
                rank_in_role=b0_ranks[i],
                role_pool_size=n_pool,
                rank_interval=b0_rank_intervals[i],
                player_idx=i,
                column_arrays=column_arrays,
            )

            # Minutes for this player.
            player_minutes_raw = _to_float(player_row.get("minutes_played"))
            minutes_input_missing = (
                player_minutes_raw is None
                or not math.isfinite(player_minutes_raw)
                or player_minutes_raw <= 0
            )
            player_minutes = (
                player_minutes_raw if player_minutes_raw is not None else None
            )

            # B2 confidence.
            b2_conf, b2_reason = _b2_confidence_from_b0(
                b0_ps.confidence, minutes_input_missing, prior_source
            )

            role_b0_confidences.append(b0_ps.confidence)
            role_b2_confidences.append(b2_conf)
            role_b0_missing_reasons.append(b0_ps.missing_reason)

            # B2 rank interval.
            if b2_rank_intervals[i] is not None:
                b2_p5, b2_p50, b2_p95 = b2_rank_intervals[i]  # type: ignore[misc]
            else:
                b2_p5, b2_p50, b2_p95 = None, None, None

            if b0_rank_intervals[i] is not None:
                b0_p5, b0_p50, b0_p95 = b0_rank_intervals[i]  # type: ignore[misc]
            else:
                b0_p5, b0_p50, b0_p95 = None, None, None

            # Shrinkage weight for this player (hand-recomputable).
            w = _shrinkage_weight(
                player_minutes_raw if player_minutes_raw is not None else 0.0,
                reference_minutes,
            )

            all_player_scores.append(
                B2PlayerScore(
                    canonical_player_id=player_row.get(
                        "canonical_player_id", ""
                    ),
                    player_name=player_row.get("player_name", ""),
                    season_id=player_row.get("season_id", ""),
                    role_family=role_family.value,
                    b0_score=b0_ps.score,
                    b0_confidence=b0_ps.confidence,
                    b0_missing_reason=b0_ps.missing_reason,
                    b0_rank_in_role=b0_ranks[i],
                    b0_role_pool_size=n_pool,
                    b0_rank_p5=b0_p5,
                    b0_rank_p50=b0_p50,
                    b0_rank_p95=b0_p95,
                    b2_score=b2_scores[i],
                    b2_rank_in_role=b2_ranks[i],
                    b2_role_pool_size=n_pool,
                    b2_rank_p5=b2_p5,
                    b2_rank_p50=b2_p50,
                    b2_rank_p95=b2_p95,
                    shrinkage_weight=w,
                    prior_mean=prior_mean,
                    prior_source=prior_source,
                    minutes_played=player_minutes,
                    minutes_input_missing=minutes_input_missing,
                    b2_confidence=b2_conf,
                    b2_missing_reason=b2_reason,
                    cross_position_comparable=False,
                )
            )

        # --- Role summary ---
        stable_core_count = int((minutes_array >= reference_minutes).sum())
        role_b2_scores = [ps.b2_score for ps in all_player_scores[-n_pool:]]
        role_b0_scores = [ps.b0_score for ps in all_player_scores[-n_pool:]]
        if role_b2_scores:
            sorted_b2 = sorted(role_b2_scores)
            sorted_b0 = sorted(role_b0_scores)
            b2_min = sorted_b2[0]
            b2_max = sorted_b2[-1]
            b2_med = sorted_b2[len(sorted_b2) // 2]
            b0_med = sorted_b0[len(sorted_b0) // 2]
        else:
            b2_min = b2_med = b2_max = 0.0
            b0_med = 0.0

        high = sum(1 for c in role_b2_confidences if c == "high")
        med = sum(1 for c in role_b2_confidences if c == "medium")
        low = sum(1 for c in role_b2_confidences if c == "low")

        dims_available = tuple(d.key for d in dims)
        role_summaries.append(
            B2RoleSummary(
                role_family=role_family.value,
                member_count=n_pool,
                stable_core_count=stable_core_count,
                prior_mean=prior_mean,
                prior_source=prior_source,
                b0_score_median=b0_med,
                b2_score_min=b2_min,
                b2_score_median=b2_med,
                b2_score_max=b2_max,
                high_confidence_count=high,
                medium_confidence_count=med,
                low_confidence_count=low,
                dimensions_available=dims_available,
            )
        )
        by_role_counts[role_family.value] = n_pool

    # UNKNOWN count for transparency.
    unknown_count = len(by_role.get(RoleFamily.UNKNOWN, []))
    if unknown_count:
        by_role_counts[RoleFamily.UNKNOWN.value] = unknown_count

    # Sort players: by role_family, then by b2_rank_in_role.
    sorted_players = sorted(
        all_player_scores,
        key=lambda ps: (ps.role_family, ps.b2_rank_in_role or 999999),
    )

    return {
        "schema": BASELINE_B2_SCHEMA,
        "schema_version": BASELINE_B2_VERSION,
        "generated_at": _now(),
        "status": "ok",
        "cohort_hash": cohort_hash,
        "membership_hash": membership_hash,
        "parameters": {
            "reference_minutes": reference_minutes,
            "n_bootstrap": n_bootstrap,
            "seed": seed,
            "min_bootstrap_pool": _MIN_BOOTSTRAP_POOL,
            "baseline_b0_schema": BASELINE_B0_SCHEMA,
            "baseline_b0_version": BASELINE_B0_VERSION,
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
        "B2 是 PRS-2 透明 baseline 的第二步：在 B0 角色内等权百分位之上"
        "叠加基于分钟的经验贝叶斯收缩。它不是球员能力的最终判断，也不"
        "替代 PRS-2 后续的 B1/B3 候选。B2 的价值在于低出场球员的分数"
        "向角色先验收缩，缓解 B0 把 90 分钟高表现与 2000 分钟高表现"
        "等价对待的偏差。"
    ),
    (
        "收缩公式：b2_score = w * prior_mean + (1 - w) * b0_score，"
        "其中 w = reference_minutes / (reference_minutes + minutes_played)。"
        "默认 reference_minutes=900（10 场 full match），此时 900 分钟球员"
        "w=0.5（50% 收缩），90 分钟球员 w≈0.91（重度收缩），3000 分钟球员"
        "w≈0.23（轻度收缩）。公式仅依赖 reference_minutes，与 tau2 无关，"
        "可手工复算。"
    ),
    (
        "先验来源：prior_mean 取角色池中 minutes_played >= reference_minutes "
        "的 'stable core' 球员的分钟加权 B0 分数均值。若角色池无任何球员"
        "达到阈值（极小池），fallback 到全部球员的简单均值并标记 "
        "prior_source=fallback_full_pool。B2 confidence 在 fallback 情况下"
        "降至 medium。"
    ),
    (
        "B2 不修改 B0 的缺失数据处理：B0 confidence=low 的球员（全部核心"
        "维度缺失）在 B2 中保持 low，并应用完全收缩 (b2_score=prior_mean)。"
        "minutes_played 缺失或非正的球员也应用完全收缩并标记 "
        "minutes_input_missing=True；B2 confidence 上限为 medium。"
        "rating_feature_matrix.parquet 当前 minutes_played 无缺失（26,747 行"
        "全部有值，verified 2026-07-31），但 B2 仍保留防御性处理。"
    ),
    (
        "GK 角色的 B2 仍是 gk_provisional：B0 GK 仅有 availability 维度，"
        "B2 在此基础上对 availability-derived 分数做收缩。这是诚实的但"
        "没有评价意义，应在解读时显式标注 'gk_provisional'。在 PRS-2 "
        "引入合规门将特征源（saves/psxg/claims 等）之前，GK 的 B2 不能"
        "作为门将能力判断。"
    ),
    (
        "B2 仅在 RoleFamily 内排名，不产生跨位置可比分数。"
        "cross_position_comparable 字段对所有球员为 False；跨位置比较需要"
        "PRS-2 后续的显式校准（B2 不提供）。B2 的收缩只在角色池内进行，"
        "prior_mean 是角色特定的。"
    ),
    (
        "Bootstrap 排名区间：当角色池 >= 10 人时，B2 用固定 seed 做 "
        f"{DEFAULT_BOOTSTRAP} 次重采样。每次重采样：(1) 重采样池行，"
        "(2) 在重采样池上重算 B0 分数，(3) 在重采样池上重算 prior_mean"
        "（哪些球员达到 reference_minutes 阈值可能变化），(4) 用原始"
        "球员的 minutes 计算 shrinkage weight 并应用收缩得到 B2 分数，"
        "(5) 重新排名。报告每位球员 B2 rank 的 p5/p50/p95。当角色池 "
        f"< {_MIN_BOOTSTRAP_POOL} 人时 b2_rank_interval 为 None。"
    ),
    (
        "B2_DIMENSIONS 复用 B0_DIMENSIONS（角色特定维度定义）。B2 不"
        "引入新的维度或新的特征列；它只是对 B0 分数施加基于 minutes 的"
        "收缩。当 PRS-2 新增合规特征源时，B0_DIMENSIONS 扩展，B2 自动"
        "继承扩展。"
    ),
    (
        "Cohort 过滤：若传入 cohort_definition，B2 仅对 cohort membership "
        "中的 canonical_player_id|season_id 对评分；未传入则对特征矩阵"
        "全部行评分。建议始终传入显式 cohort 定义，以避免隐式人群漂移。"
    ),
    (
        "canonical_player_id：rating_feature_matrix.parquet 当前未携带"
        "canonical_player_id 列；B2 用 unresolved:<source>:<player_id> "
        "作为 source-stable fallback，与 PRS-1 canonical_resolver 和 B0 "
        "一致。若调用者已通过 canonical_resolver 解析，应使用解析后的 "
        "DataFrame 通过 feature_matrix 参数传入。"
    ),
    (
        "B2 是 read-only 诊断；不修改 rating_feature_matrix.parquet 或"
        "任何其他产物。所有评分仅存在于返回的 dict 中，调用者可自行"
        "持久化到 data/reports/baseline_b2/ 或研究包。B2 报告同时包含"
        "B0 分数和 B0 rank，便于维护者对比 B0/B2 排名差异。"
    ),
]


__all__ = [
    "BASELINE_B2_SCHEMA",
    "BASELINE_B2_VERSION",
    "DEFAULT_REFERENCE_MINUTES",
    "DEFAULT_BOOTSTRAP",
    "DEFAULT_SEED",
    "B2PlayerScore",
    "B2RoleSummary",
    "compute_b2_baseline",
]

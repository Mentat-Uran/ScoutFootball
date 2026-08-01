"""B2 minutes-threshold sensitivity analysis (PRS-MODEL-012).

PRS-2 deliverable "coverage、uncertainty 和 sensitivity" (see
``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`` §PRS-2) requires a
sensitivity analysis so the maintainer knows how much the B2 ranking
depends on the specific choice of ``reference_minutes``. This module
implements the minutes-threshold sensitivity slice
(PRS-MODEL-012): it perturbs ``reference_minutes`` by configurable
absolute deltas, recomputes B2 scores, and measures ranking stability
versus the baseline.

Why this is a distinct slice from PRS-MODEL-011 (weight sensitivity):

- PRS-MODEL-011 perturbs B1's expert **weights** (a per-dimension
  multiplicative delta). The score formula is
  ``sum(effective_weight * dimension_percentile)`` — only the weights
  change, the percentiles are fixed.
- PRS-MODEL-012 perturbs B2's ``reference_minutes`` (a single scalar
  threshold). This has a **compound** effect:
  1. The shrinkage weight ``w = ref / (ref + minutes)`` changes for
     every player.
  2. The ``stable_core`` membership (``minutes >= ref``) may change —
     some players cross the threshold, altering the set of players
     that contribute to the prior.
  3. The ``prior_mean`` changes because both the membership and the
     weighting inside the stable core change.
  So perturbing ``reference_minutes`` is not a simple re-weighting; it
  shifts the entire shrinkage+prior machinery.

Design contract:

1. **Read-only.** The module never modifies ``B2_WEIGHTS`` (B2 has no
   weight set — it inherits B0_DIMENSIONS), the feature matrix, any
   parquet artifact, or the rating output. It only reads
   ``rating_feature_matrix.parquet`` and computes in-memory scores.

2. **Reuses B2 internals.** Shrinkage and prior computation are
   delegated to ``baseline_b2._compute_prior_mean`` and
   ``baseline_b2._apply_shrinkage`` so perturbed scores are
   byte-for-byte consistent with how B2 computes baseline scores — no
   second scoring implementation that could drift. B0 scores (the
   percentile layer) are computed once via
   ``baseline_b0._vectorised_scores`` and reused across all
   perturbations, because B0 does not depend on ``reference_minutes``.

3. **Absolute minute deltas.** Perturbations are additive in minutes
   (e.g. ``-600, -300, +300, +600``), not multiplicative. This is
   because ``reference_minutes`` is a minute quantity and additive
   deltas map directly to "what if we used 8 matches instead of 10?"
   semantics. The perturbed value is clamped to a minimum of 1
   (``reference_minutes`` must be positive); a delta that would push
   the value below 1 is clamped, not skipped.

4. **Ranking metrics.** Four complementary metrics are reported per
   perturbation (same family as PRS-MODEL-011 for comparability):

   - ``spearman_correlation``: Pearson correlation on ranks (1.0 =
     identical ordering, 0.0 = uncorrelated). Computed without scipy.
   - ``mean_abs_rank_shift``: mean of ``|baseline_rank - perturbed_rank|``.
   - ``max_abs_rank_shift``: worst-case rank change for any player.
   - ``top_n_overlap``: fraction of baseline top-N players that remain
     in top-N after perturbation (default N=10).

5. **Not a gate.** Sensitivity metrics are signals for the maintainer,
   not gates. A highly sensitive ranking is not a defect — it may
   reflect a genuine sample-size effect where low-minute players
   legitimately move when the threshold changes. The report helps the
   maintainer see *how much* the threshold choice matters so they can
   prioritise evidence collection and threshold justification.

6. **Prior-source tracking.** Each perturbation reports the
   ``prior_source`` (``stable_core`` / ``fallback_full_pool``) and
   ``stable_core_count`` so the maintainer can see whether a threshold
   change flips the prior into the fallback path — a qualitative
   change that rank metrics alone may not surface.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.baseline_b0 import B0_DIMENSIONS, _vectorised_scores
from scoutfootball.evaluation.baseline_b2 import (
    BASELINE_B2_SCHEMA,
    BASELINE_B2_VERSION,
    DEFAULT_REFERENCE_MINUTES,
    _apply_shrinkage,
    _compute_prior_mean,
    _compute_ranks_min_rank,
    _to_float,
)
from scoutfootball.evaluation.role_system import RoleFamily, classify_role_family

MINUTES_SENSITIVITY_SCHEMA = "scoutfootball.minutes-sensitivity"
MINUTES_SENSITIVITY_VERSION = "1.0.0"

# Default perturbation deltas in absolute minutes. ±150 ≈ 1.7 matches,
# ±300 ≈ 3.3 matches, ±600 ≈ 6.7 matches. These bracket the default
# reference_minutes=900 with meaningful but not absurd shifts.
DEFAULT_MINUTES_DELTAS: tuple[int, ...] = (-600, -300, -150, 150, 300, 600)
DEFAULT_TOP_N = 10

_LIMITATIONS: list[str] = [
    (
        "本诊断是 PRS-MODEL-012 B2 分钟门槛敏感性：衡量 B2 排名对 "
        "reference_minutes 参数选择的依赖程度。它不是评分正确性的证明，"
        "也不是 fail-closed 门禁——敏感性指标是信号不是门禁。高敏感性"
        "不一定是缺陷，可能反映低出场球员在不同门槛下合理的位置变动。"
    ),
    (
        "扰动是绝对分钟加法（如 -600/-300/+300/+600），不是乘法。"
        "perturbed_reference_minutes 钳位到最小 1（必须为正）；不会跳过"
        "任何 delta，但负 delta 使 reference_minutes 降到 1 时会报告"
        "clamped=True。"
    ),
    (
        "每个 delta 独立扰动 reference_minutes，不探索联合扰动空间"
        "（如同时改变 reference_minutes 和 B0 维度）。reference_minutes "
        "对 B2 有复合效应：收缩权重 w、stable_core 成员、prior_mean 三者"
        "都可能同时变化。"
    ),
    (
        "B0 分数（百分位层）不依赖 reference_minutes，在所有扰动中保持"
        "不变；只有收缩和先验变化。复用 baseline_b2._compute_prior_mean "
        "和 _apply_shrinkage 保证扰动分数与 B2 baseline 字节级一致。"
    ),
    (
        "GK 角色仍为 gk_provisional（availability-only），B2 对 GK 的"
        "收缩效应取决于 GK 池的 minutes_played 分布，不引入门将独立特征。"
        "cross_position_comparable=False；本诊断不改变这一事实。"
    ),
    (
        "read-only 诊断；不修改 rating_feature_matrix.parquet、B2 参数或"
        "任何 parquet 产物。不参与 fail-closed verdict。"
    ),
]


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _spearman_on_ranks(baseline_ranks: list[int], perturbed_ranks: list[int]) -> float:
    """Pearson correlation on ranks (= Spearman for complete data).

    Returns 1.0 when both rank lists are identical or when either list
    has zero variance (e.g. all players tied). Avoids scipy dependency.
    """
    n = len(baseline_ranks)
    if n < 2:
        return 1.0
    import numpy as np

    a = np.array(baseline_ranks, dtype=np.float64)
    b = np.array(perturbed_ranks, dtype=np.float64)
    a_mean = a.mean()
    b_mean = b.mean()
    a_dev = a - a_mean
    b_dev = b - b_mean
    denom = float(np.sqrt((a_dev ** 2).sum() * (b_dev ** 2).sum()))
    if denom == 0.0:
        return 1.0
    return float((a_dev * b_dev).sum() / denom)


def _top_n_overlap(
    baseline_ranks: list[int], perturbed_ranks: list[int], top_n: int
) -> float:
    """Fraction of baseline top-N players that remain in perturbed top-N."""
    n = len(baseline_ranks)
    if n == 0 or top_n <= 0:
        return 1.0
    effective_n = min(top_n, n)
    baseline_top = {i for i, r in enumerate(baseline_ranks) if r <= effective_n}
    perturbed_top = {i for i, r in enumerate(perturbed_ranks) if r <= effective_n}
    if not baseline_top:
        return 1.0
    overlap = len(baseline_top & perturbed_top)
    return overlap / len(baseline_top)


def _rank_shift_stats(
    baseline_ranks: list[int], perturbed_ranks: list[int]
) -> dict[str, float]:
    """Compute mean/max absolute rank shift."""
    n = len(baseline_ranks)
    if n == 0:
        return {"mean_abs_rank_shift": 0.0, "max_abs_rank_shift": 0.0}
    import numpy as np

    shifts = np.abs(
        np.array(baseline_ranks, dtype=np.float64)
        - np.array(perturbed_ranks, dtype=np.float64)
    )
    return {
        "mean_abs_rank_shift": float(shifts.mean()),
        "max_abs_rank_shift": float(shifts.max()),
    }


def _load_feature_matrix_rows(
    settings: PlatformSettings,
    feature_matrix: Any = None,
    cohort_definition: Any | None = None,
) -> tuple[list[dict[str, Any]], str | None, str | None, dict[str, Any]]:
    """Load the feature matrix and return rows ready for role grouping.

    Returns ``(rows, cohort_hash, membership_hash, error_report)``.
    If loading fails, ``rows`` is empty and ``error_report`` describes
    the failure. This mirrors the load logic in
    ``baseline_b2.compute_b2_baseline`` but stops before scoring.
    """
    if feature_matrix is None:
        fm_path = settings.gold_root / "feature_store" / "rating_feature_matrix.parquet"
        if not fm_path.exists():
            return [], None, None, {
                "status": "unavailable",
                "evidence": {"reason": "rating_feature_matrix.parquet missing"},
            }
        try:
            import pandas as pd

            feature_matrix = pd.read_parquet(fm_path)
        except Exception as exc:  # noqa: BLE001 — read-only diagnostic
            return [], None, None, {
                "status": "unavailable",
                "evidence": {"reason": f"rating_feature_matrix read failed: {exc}"},
            }

    if feature_matrix is None or len(feature_matrix) == 0:
        return [], None, None, {
            "status": "unavailable",
            "evidence": {"reason": "rating_feature_matrix is empty"},
        }

    cohort_hash: str | None = None
    membership_hash: str | None = None
    member_keys: set[str] | None = None
    if cohort_definition is not None:
        from scoutfootball.evaluation.cohort import preview_cohort

        cohort_report = preview_cohort(cohort_definition, settings=settings)
        if cohort_report.get("status") != "ok":
            return [], None, None, {
                "status": "unavailable",
                "cohort_hash": cohort_report.get("cohort_hash"),
                "evidence": {
                    "reason": "cohort preview failed",
                    "cohort_status": cohort_report.get("status"),
                    "cohort_evidence": cohort_report.get("evidence"),
                },
            }
        cohort_hash = cohort_report.get("cohort_hash")
        membership_hash = cohort_report.get("membership_hash")
        member_keys = {
            f"{m['canonical_player_id']}|{m['season_id']}"
            for m in cohort_report["evidence"]["members"]
        }
        if not member_keys:
            return [], cohort_hash, membership_hash, {
                "status": "ok",
                "evidence": {"reason": "cohort has 0 members"},
            }

    fm = feature_matrix
    rows: list[dict[str, Any]] = []
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
        rows.append(row_dict)

    return rows, cohort_hash, membership_hash, {"status": "ok"}


def _build_minutes_array(pool: list[dict[str, Any]]) -> Any:
    """Build a float numpy array of minutes_played for the pool.

    Missing/non-finite minutes are replaced with NaN (matching B2's
    convention). ``_apply_shrinkage`` handles NaN by applying full
    shrinkage.
    """
    import numpy as np

    n = len(pool)
    arr = np.full(n, np.nan, dtype=np.float64)
    for i, row in enumerate(pool):
        v = _to_float(row.get("minutes_played"))
        if v is not None:
            arr[i] = v
    return arr


def compute_minutes_sensitivity_report(
    settings: PlatformSettings | None = None,
    *,
    feature_matrix: Any = None,
    cohort_definition: Any | None = None,
    baseline_reference_minutes: float = DEFAULT_REFERENCE_MINUTES,
    perturbation_deltas: tuple[int, ...] = DEFAULT_MINUTES_DELTAS,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    """Build the B2 minutes-threshold sensitivity report (PRS-MODEL-012).

    For each role family with a B0 dimension set, computes the baseline
    B2 ranking at ``baseline_reference_minutes``, then perturbs
    ``reference_minutes`` by each delta, recomputes B2 scores, and
    measures ranking stability versus the baseline.

    Args:
        settings: Platform settings. If None, uses
            ``PlatformSettings.from_root()``.
        feature_matrix: Optional pre-loaded feature matrix DataFrame.
        cohort_definition: Optional ``CohortDefinition`` to restrict
            membership (same semantics as ``compute_b2_baseline``).
        baseline_reference_minutes: The baseline reference minutes to
            perturb around. Default 900 (matches B2 default).
        perturbation_deltas: Absolute minute deltas to apply. Default
            ``(-600, -300, -150, 150, 300, 600)``.
        top_n: Top-N overlap window. Default 10.

    Returns:
        A JSON-serialisable dict with schema
        ``scoutfootball.minutes-sensitivity`` v1.0.0.
    """
    resolved = settings or PlatformSettings.from_root()

    # Validate baseline_reference_minutes.
    if (
        not isinstance(baseline_reference_minutes, (int, float))
        or isinstance(baseline_reference_minutes, bool)
        or not math.isfinite(float(baseline_reference_minutes))
        or baseline_reference_minutes <= 0
    ):
        return {
            "schema": MINUTES_SENSITIVITY_SCHEMA,
            "schema_version": MINUTES_SENSITIVITY_VERSION,
            "generated_at": _now(),
            "status": "unavailable",
            "evidence": {
                "reason": (
                    "baseline_reference_minutes must be a positive finite "
                    f"number; got {baseline_reference_minutes!r}"
                )
            },
            "baseline_schema": BASELINE_B2_SCHEMA,
            "baseline_version": BASELINE_B2_VERSION,
            "baseline_reference_minutes": baseline_reference_minutes,
            "perturbation_deltas": list(perturbation_deltas),
            "top_n": top_n,
            "role_summaries": [],
            "limitations": _LIMITATIONS,
        }

    rows, cohort_hash, membership_hash, load_status = _load_feature_matrix_rows(
        resolved, feature_matrix=feature_matrix, cohort_definition=cohort_definition
    )

    if load_status["status"] != "ok":
        return {
            "schema": MINUTES_SENSITIVITY_SCHEMA,
            "schema_version": MINUTES_SENSITIVITY_VERSION,
            "generated_at": _now(),
            **load_status,
            "baseline_schema": BASELINE_B2_SCHEMA,
            "baseline_version": BASELINE_B2_VERSION,
            "baseline_reference_minutes": baseline_reference_minutes,
            "perturbation_deltas": list(perturbation_deltas),
            "top_n": top_n,
            "role_summaries": [],
            "limitations": _LIMITATIONS,
        }

    # Group by role family.
    by_role: dict[RoleFamily, list[dict[str, Any]]] = {}
    for r in rows:
        role = r["_role_family"]
        by_role.setdefault(role, []).append(r)

    role_summaries: list[dict[str, Any]] = []

    for role_family in RoleFamily:
        if role_family == RoleFamily.UNKNOWN:
            continue

        pool = by_role.get(role_family, [])
        if not pool:
            continue

        dims = B0_DIMENSIONS.get(role_family)
        if dims is None:
            continue

        n_pool = len(pool)

        # B0 scores are computed once — they do not depend on
        # reference_minutes. Reused across all perturbations.
        b0_scores_array = _vectorised_scores(pool, dims)

        # Minutes array for the pool.
        minutes_array = _build_minutes_array(pool)

        # Baseline B2 scores and ranks.
        baseline_prior_mean, baseline_prior_source = _compute_prior_mean(
            b0_scores_array, minutes_array, baseline_reference_minutes
        )
        baseline_b2_array = _apply_shrinkage(
            b0_scores_array,
            minutes_array,
            baseline_prior_mean,
            baseline_reference_minutes,
        )
        baseline_b2_ranks_array = _compute_ranks_min_rank(baseline_b2_array)
        baseline_ranks: list[int] = baseline_b2_ranks_array.tolist()
        baseline_stable_core_count = int(
            (minutes_array >= baseline_reference_minutes).sum()
        )

        perturbations: list[dict[str, Any]] = []
        worst_spearman: float | None = None
        best_spearman: float | None = None
        worst_delta: int | None = None
        best_delta: int | None = None

        for delta in perturbation_deltas:
            perturbed_ref_raw = baseline_reference_minutes + delta
            clamped = False
            if perturbed_ref_raw < 1:
                perturbed_ref_raw = 1
                clamped = True
            perturbed_ref = float(perturbed_ref_raw)

            # Recompute prior and B2 under perturbed reference_minutes.
            # prior_mean may change because stable_core membership and
            # the minutes-weighting inside stable_core both depend on
            # the threshold.
            perturbed_prior_mean, perturbed_prior_source = _compute_prior_mean(
                b0_scores_array, minutes_array, perturbed_ref
            )
            perturbed_b2_array = _apply_shrinkage(
                b0_scores_array,
                minutes_array,
                perturbed_prior_mean,
                perturbed_ref,
            )
            perturbed_ranks_array = _compute_ranks_min_rank(perturbed_b2_array)
            perturbed_ranks: list[int] = perturbed_ranks_array.tolist()

            spearman = _spearman_on_ranks(baseline_ranks, perturbed_ranks)
            shift_stats = _rank_shift_stats(baseline_ranks, perturbed_ranks)
            overlap = _top_n_overlap(baseline_ranks, perturbed_ranks, top_n)
            perturbed_stable_core_count = int(
                (minutes_array >= perturbed_ref).sum()
            )

            perturbations.append({
                "delta": delta,
                "perturbed_reference_minutes": perturbed_ref,
                "clamped": clamped,
                "prior_mean": round(perturbed_prior_mean, 6),
                "prior_source": perturbed_prior_source,
                "stable_core_count": perturbed_stable_core_count,
                "spearman_correlation": round(spearman, 6),
                "mean_abs_rank_shift": round(shift_stats["mean_abs_rank_shift"], 4),
                "max_abs_rank_shift": int(shift_stats["max_abs_rank_shift"]),
                "top_n_overlap": round(overlap, 6),
            })

            if worst_spearman is None or spearman < worst_spearman:
                worst_spearman = spearman
                worst_delta = delta
            if best_spearman is None or spearman > best_spearman:
                best_spearman = spearman
                best_delta = delta

        role_summaries.append({
            "role_family": role_family.value,
            "player_count": n_pool,
            "baseline_prior_mean": round(baseline_prior_mean, 6),
            "baseline_prior_source": baseline_prior_source,
            "baseline_stable_core_count": baseline_stable_core_count,
            "most_sensitive_delta": worst_delta,
            "least_sensitive_delta": best_delta,
            "min_spearman_correlation": worst_spearman,
            "max_spearman_correlation": best_spearman,
            "perturbations": perturbations,
        })

    return {
        "schema": MINUTES_SENSITIVITY_SCHEMA,
        "schema_version": MINUTES_SENSITIVITY_VERSION,
        "generated_at": _now(),
        "status": "ok",
        "cohort_hash": cohort_hash,
        "membership_hash": membership_hash,
        "baseline_schema": BASELINE_B2_SCHEMA,
        "baseline_version": BASELINE_B2_VERSION,
        "baseline_reference_minutes": baseline_reference_minutes,
        "perturbation_deltas": list(perturbation_deltas),
        "top_n": top_n,
        "role_summaries": role_summaries,
        "limitations": _LIMITATIONS,
    }


__all__ = [
    "DEFAULT_MINUTES_DELTAS",
    "DEFAULT_TOP_N",
    "MINUTES_SENSITIVITY_SCHEMA",
    "MINUTES_SENSITIVITY_VERSION",
    "compute_minutes_sensitivity_report",
]

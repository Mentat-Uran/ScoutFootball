"""B1 weight sensitivity analysis (PRS-MODEL-011).

PRS-2 deliverable "coverage、uncertainty 和 sensitivity" (see
``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`` §PRS-2) requires a
sensitivity analysis so the maintainer knows how much the ranking
depends on the specific expert weights in ``B1_WEIGHTS``. This module
implements the weight-sensitivity slice (PRS-MODEL-011): it perturbs
each dimension weight by configurable deltas, renormalises, recomputes
B1 scores, and measures ranking stability versus the baseline.

Design contract:

1. **Read-only.** The module never modifies ``B1_WEIGHTS``, the feature
   matrix, any parquet artifact, or the rating output. It only reads
   ``rating_feature_matrix.parquet`` and computes in-memory scores.

2. **Reuses B1 internals.** Scoring is delegated to
   ``baseline_b1._vectorised_weighted_scores`` so perturbed scores are
   byte-for-byte consistent with how B1 computes baseline scores — no
   second scoring implementation that could drift.

3. **Per-dimension isolation.** Each dimension is perturbed in
   isolation (one at a time). The report does not explore the full
   combinatorial space of joint perturbations; that is left to the
   maintainer's judgement guided by the per-dimension signals.

4. **Weight clamping.** Perturbed weights are clamped at 0 (negative
   weights are not meaningful for this baseline). If a perturbation
   zeros out the only non-zero weight, the perturbation is skipped and
   reported as ``skipped: all_weights_zero``.

5. **Ranking metrics.** Four complementary metrics are reported per
   perturbation:

   - ``spearman_correlation``: Pearson correlation on ranks (1.0 =
     identical ordering, 0.0 = uncorrelated). Computed without scipy.
   - ``mean_abs_rank_shift``: mean of ``|baseline_rank - perturbed_rank|``.
   - ``max_abs_rank_shift``: worst-case rank change for any player.
   - ``top_n_overlap``: fraction of baseline top-N players that remain
     in top-N after perturbation (default N=10).

6. **Not a gate.** Sensitivity metrics are signals for the maintainer,
   not gates. A highly sensitive dimension is not a defect — it may
   reflect a deliberate expert judgement that this dimension matters.
   The report helps the maintainer see *which* weights are load-bearing
   so they can prioritise review and evidence collection.

7. **GK caveat.** GK's B1 weight set is ``availability=1.0`` (single
   dimension). Perturbing it and renormalising always yields 1.0, so
   the ranking is trivially stable. The report includes GK for
   completeness but flags it as ``single_dimension: true``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.baseline_b0 import B0_DIMENSIONS, B0Dimension, _pool_column_arrays
from scoutfootball.evaluation.baseline_b1 import (
    B1_WEIGHTS,
    B1_WEIGHTS_VERSION,
    BASELINE_B1_SCHEMA,
    BASELINE_B1_VERSION,
    _vectorised_weighted_scores,
)
from scoutfootball.evaluation.role_system import RoleFamily, classify_role_family

WEIGHT_SENSITIVITY_SCHEMA = "scoutfootball.weight-sensitivity"
WEIGHT_SENSITIVITY_VERSION = "1.0.0"

DEFAULT_PERTURBATION_DELTAS: tuple[float, ...] = (-0.20, -0.10, 0.10, 0.20)
DEFAULT_TOP_N = 10


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _perturb_and_renormalise(
    raw_weights: dict[str, float],
    dim_key: str,
    delta: float,
) -> dict[str, float] | None:
    """Perturb one dimension's weight by ``delta`` and renormalise.

    Returns the perturbed+renormalised weight dict, or ``None`` if the
    perturbation zeros out all weights (in which case scoring would
    produce the neutral 50.0 placeholder for every player and the
    ranking comparison is meaningless).
    """
    perturbed = {
        k: max(0.0, v * (1.0 + delta)) if k == dim_key else v
        for k, v in raw_weights.items()
    }
    total = sum(perturbed.values())
    if total <= 0:
        return None
    return {k: v / total for k, v in perturbed.items()}


def _compute_ranks(scores: list[float]) -> list[int]:
    """Compute ranks (1 = highest score, min-rank for ties)."""
    n = len(scores)
    if n == 0:
        return []
    indexed = sorted(enumerate(scores), key=lambda kv: -kv[1])
    ranks = [0] * n
    current_rank = 1
    prev_score: float | None = None
    for position, (orig_idx, s) in enumerate(indexed):
        if prev_score is None or s != prev_score:
            current_rank = position + 1
            prev_score = s
        ranks[orig_idx] = current_rank
    return ranks


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
        # Zero variance in at least one list — ranks are constant.
        # If both are constant and equal, correlation is 1.0; otherwise
        # undefined, but we report 1.0 to avoid false alarm.
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


def _build_column_arrays_for_role(
    pool: list[dict[str, Any]], dims: tuple[B0Dimension, ...]
) -> dict[str, Any]:
    """Build the column arrays needed for vectorised scoring."""
    all_cols: list[str] = []
    seen: set[str] = set()
    for dim in dims:
        for col in dim.columns:
            if col not in seen:
                seen.add(col)
                all_cols.append(col)
    return _pool_column_arrays(pool, tuple(all_cols))


def _load_feature_matrix_rows(
    settings: PlatformSettings,
    feature_matrix: Any = None,
    cohort_definition: Any | None = None,
) -> tuple[list[dict[str, Any]], str | None, str | None, dict[str, Any]]:
    """Load the feature matrix and return rows ready for role grouping.

    Returns ``(rows, cohort_hash, membership_hash, error_report)``.
    If loading fails, ``rows`` is empty and ``error_report`` describes
    the failure. This mirrors the load logic in
    ``baseline_b1.compute_b1_baseline`` but stops before scoring.
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


def compute_weight_sensitivity_report(
    settings: PlatformSettings | None = None,
    *,
    feature_matrix: Any = None,
    cohort_definition: Any | None = None,
    perturbation_deltas: tuple[float, ...] = DEFAULT_PERTURBATION_DELTAS,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    """Build the B1 weight sensitivity report (PRS-MODEL-011).

    For each role family with a B1 weight set, perturbs each dimension
    weight by each delta, renormalises, recomputes B1 scores, and
    measures ranking stability versus the baseline.

    Args:
        settings: Platform settings. If None, uses
            ``PlatformSettings.from_root()``.
        feature_matrix: Optional pre-loaded feature matrix DataFrame.
        cohort_definition: Optional ``CohortDefinition`` to restrict
            membership (same semantics as ``compute_b1_baseline``).
        perturbation_deltas: Weight multipliers as ``(1 + delta)``.
            Default ``(-0.20, -0.10, 0.10, 0.20)``.
        top_n: Top-N overlap window. Default 10.

    Returns:
        A JSON-serialisable dict with schema
        ``scoutfootball.weight-sensitivity`` v1.0.0.
    """
    resolved = settings or PlatformSettings.from_root()

    rows, cohort_hash, membership_hash, load_status = _load_feature_matrix_rows(
        resolved, feature_matrix=feature_matrix, cohort_definition=cohort_definition
    )

    if load_status["status"] != "ok":
        return {
            "schema": WEIGHT_SENSITIVITY_SCHEMA,
            "schema_version": WEIGHT_SENSITIVITY_VERSION,
            "generated_at": _now(),
            **load_status,
            "baseline_schema": BASELINE_B1_SCHEMA,
            "baseline_version": BASELINE_B1_VERSION,
            "weight_version": B1_WEIGHTS_VERSION,
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

        raw_weights = B1_WEIGHTS.get(role_family)
        if raw_weights is None:
            continue

        n_pool = len(pool)
        column_arrays = _build_column_arrays_for_role(pool, dims)

        # Baseline scores and ranks.
        baseline_scores_array = _vectorised_weighted_scores(
            column_arrays, dims, raw_weights, n_pool
        )
        baseline_scores = baseline_scores_array.tolist()
        baseline_ranks = _compute_ranks(baseline_scores)

        dim_keys = [d.key for d in dims]
        is_single_dimension = len(dim_keys) <= 1

        per_dimension: dict[str, Any] = {}
        most_sensitive_dim: str | None = None
        least_sensitive_dim: str | None = None
        worst_spearman = 2.0  # above max
        best_spearman = -1.0  # below min

        for dim_key in dim_keys:
            perturbations: list[dict[str, Any]] = []
            dim_min_spearman: float | None = None
            dim_max_mean_shift: float = 0.0

            for delta in perturbation_deltas:
                perturbed_weights = _perturb_and_renormalise(
                    raw_weights, dim_key, delta
                )
                if perturbed_weights is None:
                    perturbations.append({
                        "delta": delta,
                        "status": "skipped",
                        "reason": "all_weights_zero",
                    })
                    continue

                perturbed_scores_array = _vectorised_weighted_scores(
                    column_arrays, dims, perturbed_weights, n_pool
                )
                perturbed_scores = perturbed_scores_array.tolist()
                perturbed_ranks = _compute_ranks(perturbed_scores)

                spearman = _spearman_on_ranks(baseline_ranks, perturbed_ranks)
                shift_stats = _rank_shift_stats(baseline_ranks, perturbed_ranks)
                overlap = _top_n_overlap(baseline_ranks, perturbed_ranks, top_n)

                perturbations.append({
                    "delta": delta,
                    "status": "ok",
                    "spearman_correlation": round(spearman, 6),
                    "mean_abs_rank_shift": round(shift_stats["mean_abs_rank_shift"], 4),
                    "max_abs_rank_shift": int(shift_stats["max_abs_rank_shift"]),
                    "top_n_overlap": round(overlap, 6),
                })

                if dim_min_spearman is None or spearman < dim_min_spearman:
                    dim_min_spearman = spearman
                if shift_stats["mean_abs_rank_shift"] > dim_max_mean_shift:
                    dim_max_mean_shift = shift_stats["mean_abs_rank_shift"]

            # Aggregate per-dimension: find the worst-case perturbation.
            ok_perts = [p for p in perturbations if p.get("status") == "ok"]
            if ok_perts:
                worst = min(ok_perts, key=lambda p: p["spearman_correlation"])
                per_dimension[dim_key] = {
                    "perturbations": perturbations,
                    "min_spearman_correlation": worst["spearman_correlation"],
                    "worst_delta": worst["delta"],
                    "max_mean_abs_rank_shift": max(
                        p["mean_abs_rank_shift"] for p in ok_perts
                    ),
                    "max_abs_rank_shift": max(
                        p["max_abs_rank_shift"] for p in ok_perts
                    ),
                    "min_top_n_overlap": min(
                        p["top_n_overlap"] for p in ok_perts
                    ),
                }
                # Track most/least sensitive by min Spearman.
                if worst["spearman_correlation"] < worst_spearman:
                    worst_spearman = worst["spearman_correlation"]
                    most_sensitive_dim = dim_key
                if worst["spearman_correlation"] > best_spearman:
                    best_spearman = worst["spearman_correlation"]
                    least_sensitive_dim = dim_key
            else:
                per_dimension[dim_key] = {
                    "perturbations": perturbations,
                    "min_spearman_correlation": None,
                    "worst_delta": None,
                    "max_mean_abs_rank_shift": None,
                    "max_abs_rank_shift": None,
                    "min_top_n_overlap": None,
                }

        role_summaries.append({
            "role_family": role_family.value,
            "player_count": n_pool,
            "dimensions_tested": dim_keys,
            "single_dimension": is_single_dimension,
            "most_sensitive_dimension": most_sensitive_dim,
            "least_sensitive_dimension": least_sensitive_dim,
            "per_dimension": per_dimension,
        })

    return {
        "schema": WEIGHT_SENSITIVITY_SCHEMA,
        "schema_version": WEIGHT_SENSITIVITY_VERSION,
        "generated_at": _now(),
        "status": "ok",
        "cohort_hash": cohort_hash,
        "membership_hash": membership_hash,
        "baseline_schema": BASELINE_B1_SCHEMA,
        "baseline_version": BASELINE_B1_VERSION,
        "weight_version": B1_WEIGHTS_VERSION,
        "perturbation_deltas": list(perturbation_deltas),
        "top_n": top_n,
        "role_summaries": role_summaries,
        "limitations": _LIMITATIONS,
    }


_LIMITATIONS: list[str] = [
    (
        "Weight sensitivity is a read-only diagnostic, not a gate. A "
        "highly sensitive dimension is not a defect — it may reflect a "
        "deliberate expert judgement that this dimension matters. The "
        "report helps the maintainer see which weights are load-bearing "
        "so they can prioritise review and evidence collection."
    ),
    (
        "Each dimension is perturbed in isolation. The report does not "
        "explore the full combinatorial space of joint perturbations; "
        "joint sensitivity may be higher or lower than the per-dimension "
        "worst case."
    ),
    (
        "Perturbed weights are clamped at 0 (negative weights are not "
        "meaningful for this baseline). Perturbations that zero out all "
        "weights are skipped and reported as all_weights_zero."
    ),
    (
        "Ranking metrics (Spearman correlation, mean/max rank shift, "
        "top-N overlap) are computed on the within-role ranking, not "
        "the cross-role ranking. B1 is role-internal by design "
        "(cross_position_comparable=False)."
    ),
    (
        "GK's B1 weight set is availability=1.0 (single dimension). "
        "Perturbing it and renormalising always yields 1.0, so GK's "
        "ranking is trivially stable. The report includes GK for "
        "completeness but flags it as single_dimension=true."
    ),
    (
        "The report reuses baseline_b1._vectorised_weighted_scores so "
        "perturbed scores are byte-for-byte consistent with how B1 "
        "computes baseline scores. Missing-dimension renormalisation "
        "is applied identically in baseline and perturbed runs."
    ),
    (
        "Spearman correlation is computed as Pearson on ranks without "
        "scipy. For n < 2 or zero-variance rank lists, it returns 1.0 "
        "to avoid false alarms on tiny pools."
    ),
]

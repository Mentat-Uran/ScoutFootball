"""B2 cohort subsampling sensitivity analysis (PRS-MODEL-013).

PRS-2 deliverable "coverage、uncertainty 和 sensitivity" (see
``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`` §PRS-2) requires a
sensitivity analysis so the maintainer knows how much the B2 ranking
depends on the specific cohort composition. This module implements the
cohort-sensitivity slice (PRS-MODEL-013): it randomly holds out a
fraction of players from each role pool, recomputes B0→B2 from scratch
on the remaining pool, and measures ranking stability on the common
players versus the baseline.

Why this is a distinct slice from PRS-MODEL-011 (weight sensitivity)
and PRS-MODEL-012 (minutes sensitivity):

- PRS-MODEL-011 perturbs B1's expert **weights** (a per-dimension
  multiplicative delta). The pool and B0 percentiles are fixed; only
  the aggregation weights change.
- PRS-MODEL-012 perturbs B2's ``reference_minutes`` (a single scalar
  threshold). B0 scores are fixed (they don't depend on
  ``reference_minutes``); only shrinkage weight, stable_core
  membership, and prior_mean change.
- PRS-MODEL-013 perturbs the **cohort membership** (which players are
  in the pool). This has the most fundamental effect: B0 percentiles
  change (because the reference pool changes), B2 prior changes
  (because stable_core membership changes), and B2 shrinkage changes
  (because the prior changes). The entire B0→B2 chain is recomputed
  on the reduced pool.

Design contract:

1. **Read-only.** The module never modifies the feature matrix, the
   cohort definition, any parquet artifact, or the rating output. It
   only reads ``rating_feature_matrix.parquet`` and computes in-memory
   scores on subsampled pools.

2. **Reproducible.** Each subsample is drawn from a deterministic
   ``numpy.random.Generator`` seeded from
   ``(base_seed, role_family_index, repeat_index)``. The same
   parameters always produce the same subsample, so the maintainer
   can re-run and verify.

3. **Common-players comparison.** When players are held out, ranks
   are compared only for players present in **both** the baseline and
   the perturbed pool. The report includes ``common_player_count`` so
   the maintainer can see how many players the stability metrics are
   based on. Ranks are 1-indexed within their respective pools (so a
   baseline rank of 3 out of 100 and a perturbed rank of 2 out of 80
   are both "near the top" — Spearman captures this monotonic
   relationship correctly).

4. **Holdout without replacement.** Unlike B2's bootstrap (which
   resamples *with* replacement to estimate rank uncertainty),
   cohort sensitivity holds out players *without* replacement. This
   answers a different question: "if the cohort had been slightly
   smaller, would the ranking change?" — not "what is the rank
   distribution under resampling?"

5. **Ranking metrics.** Four complementary metrics are reported per
   perturbation (same family as PRS-MODEL-011/012 for comparability),
   computed on the common players:

   - ``spearman_correlation``: Pearson correlation on ranks (1.0 =
     identical ordering, 0.0 = uncorrelated). Computed without scipy.
   - ``mean_abs_rank_shift``: mean of ``|baseline_rank - perturbed_rank|``.
   - ``max_abs_rank_shift``: worst-case rank change for any common
     player.
   - ``top_n_overlap``: fraction of baseline top-N common players
     that remain in perturbed top-N (default N=10). Only common
     players are considered, so held-out baseline top-N players do
     not penalise the overlap.

6. **Not a gate.** Sensitivity metrics are signals for the maintainer,
   not gates. A highly sensitive ranking is not a defect — it may
   reflect a genuine small-pool effect where removing one player
   legitimately changes the percentile landscape. The report helps
   the maintainer see *how much* cohort composition matters so they
   can prioritise cohort stability and evidence collection.

7. **Minimum pool size.** Perturbations are skipped for role pools
   smaller than ``min_pool_size`` (default 10) to avoid meaningless
   subsampling of tiny pools. The report still includes the role
   summary with ``skipped_reason="pool_too_small"`` so the maintainer
   sees the role was considered but excluded.
"""

from __future__ import annotations

import hashlib
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

COHORT_SENSITIVITY_SCHEMA = "scoutfootball.cohort-sensitivity"
COHORT_SENSITIVITY_VERSION = "1.0.0"

# Default holdout fractions: remove 5%, 10%, 20% of players. These
# bracket "a few players leave" (5%) to "a meaningful slice leaves"
# (20%) without shrinking the pool so much that ranks become noisy.
DEFAULT_HOLDOUT_FRACTIONS: tuple[float, ...] = (0.05, 0.10, 0.20)
DEFAULT_N_REPEATS = 5
DEFAULT_TOP_N = 10
DEFAULT_MIN_POOL_SIZE = 10
DEFAULT_SEED = 20260731

_LIMITATIONS: list[str] = [
    (
        "本诊断是 PRS-MODEL-013 B2 cohort 敏感性：衡量 B2 排名对 cohort "
        "成员组成的依赖程度。它不是评分正确性的证明，也不是 fail-closed "
        "门禁——敏感性指标是信号不是门禁。高敏感性不一定是缺陷，可能反映"
        "小池子中移除球员合理地改变了百分位分布。"
    ),
    (
        "扰动是 holdout without replacement（随机移除一定比例球员），"
        "不是 bootstrap with replacement。回答的问题是'如果 cohort 略小，"
        "排名会变吗'，而不是'重采样下排名分布如何'。后者由 B2 自身的 "
        "bootstrap 排名区间覆盖。"
    ),
    (
        "每个 holdout_fraction × repeat 独立抽样，不探索联合扰动空间。"
        "与 PRS-MODEL-011/012 不同，cohort 扰动有最根本的效应：B0 百分位"
        "变化（参考池变了）、B2 prior 变化（stable_core 成员变了）、B2 "
        "收缩变化（prior 变了）。整个 B0→B2 链在缩减池上重新计算。"
    ),
    (
        "排名比较只在 baseline 和 perturbed 池的公共球员上进行。"
        "common_player_count 报告每条扰动基于多少球员。被移除的球员"
        "不参与比较，也不惩罚 top_n_overlap。"
    ),
    (
        "种子确定性：每个 (base_seed, role_family_index, repeat_index) "
        "三元组通过 SHA256 派生独立种子，保证同参数同结果。"
        "默认 base_seed=20260731。"
    ),
    (
        "池子小于 min_pool_size（默认 10）的角色跳过扰动，报告 "
        "skipped_reason=pool_too_small，避免对微型池做无意义的子采样。"
    ),
    (
        "GK 角色仍为 gk_provisional（availability-only），B2 对 GK 的"
        "收缩效应取决于 GK 池的 minutes_played 分布，不引入门将独立特征。"
        "cross_position_comparable=False；本诊断不改变这一事实。"
    ),
    (
        "read-only 诊断；不修改 rating_feature_matrix.parquet、cohort "
        "定义或任何 parquet 产物。不参与 fail-closed verdict。"
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
    """Fraction of baseline top-N players that remain in perturbed top-N.

    Both rank lists must be over the **same** set of players (common
    players), indexed positionally. ``baseline_ranks[i]`` and
    ``perturbed_ranks[i]`` refer to the same player.
    """
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
    """Compute mean/max absolute rank shift over common players."""
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
    Mirrors the load logic in ``minutes_sensitivity._load_feature_matrix_rows``
    so both diagnostics operate on the same row format.
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


def _derive_seed(base_seed: int, role_family: RoleFamily, repeat_index: int) -> int:
    """Derive a deterministic 32-bit seed from (base_seed, role, repeat).

    Uses SHA256 so that adjacent role/repeat indices do not produce
    correlated streams. The seed fits in a 32-bit unsigned int as
    required by ``numpy.random.default_rng``.
    """
    raw = f"{base_seed}|{role_family.value}|{repeat_index}".encode()
    digest = hashlib.sha256(raw).hexdigest()
    # Take the first 8 hex chars (32 bits) and convert to int.
    return int(digest[:8], 16)


def _compute_b2_ranks_on_pool(
    pool: list[dict[str, Any]],
    dims: Any,
    reference_minutes: float,
) -> tuple[list[int], list[float], float, str]:
    """Compute B2 ranks on the given pool.

    Returns ``(ranks, b2_scores, prior_mean, prior_source)``. Ranks are
    1-indexed (rank 1 = highest B2 score). This recomputes the full
    B0→B2 chain from scratch on the pool — B0 percentiles are computed
    against this pool, not the baseline pool.
    """
    b0_scores_array = _vectorised_scores(pool, dims)
    minutes_array = _build_minutes_array(pool)
    prior_mean, prior_source = _compute_prior_mean(
        b0_scores_array, minutes_array, reference_minutes
    )
    b2_array = _apply_shrinkage(
        b0_scores_array, minutes_array, prior_mean, reference_minutes
    )
    ranks_array = _compute_ranks_min_rank(b2_array)
    return (
        ranks_array.tolist(),
        b2_array.tolist(),
        prior_mean,
        prior_source,
    )


def _player_key(row: dict[str, Any]) -> str:
    """Stable per-player key for matching baseline and perturbed ranks."""
    return f"{row['canonical_player_id']}|{row['season_id']}"


def compute_cohort_sensitivity_report(
    settings: PlatformSettings | None = None,
    *,
    feature_matrix: Any = None,
    cohort_definition: Any | None = None,
    baseline_reference_minutes: float = DEFAULT_REFERENCE_MINUTES,
    holdout_fractions: tuple[float, ...] = DEFAULT_HOLDOUT_FRACTIONS,
    n_repeats: int = DEFAULT_N_REPEATS,
    top_n: int = DEFAULT_TOP_N,
    min_pool_size: int = DEFAULT_MIN_POOL_SIZE,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Build the B2 cohort subsampling sensitivity report (PRS-MODEL-013).

    For each role family with a B0 dimension set, computes the baseline
    B2 ranking on the full pool, then for each holdout fraction and
    repeat, randomly holds out that fraction of players, recomputes
    B0→B2 on the reduced pool, and measures ranking stability on the
    common players versus the baseline.

    Args:
        settings: Platform settings. If None, uses
            ``PlatformSettings.from_root()``.
        feature_matrix: Optional pre-loaded feature matrix DataFrame.
        cohort_definition: Optional ``CohortDefinition`` to restrict
            membership (same semantics as ``compute_b2_baseline``).
        baseline_reference_minutes: The B2 ``reference_minutes`` used
            for both baseline and perturbed scores. Default 900.
        holdout_fractions: Fractions of players to hold out per
            perturbation. Default ``(0.05, 0.10, 0.20)``.
        n_repeats: Number of random subsamples per holdout fraction.
            Default 5.
        top_n: Top-N overlap window. Default 10.
        min_pool_size: Minimum pool size for perturbation. Pools
            smaller than this are skipped. Default 10.
        seed: Base random seed. Each (seed, role, repeat) triple
            derives an independent sub-seed. Default 20260731.

    Returns:
        A JSON-serialisable dict with schema
        ``scoutfootball.cohort-sensitivity`` v1.0.0.
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
            "schema": COHORT_SENSITIVITY_SCHEMA,
            "schema_version": COHORT_SENSITIVITY_VERSION,
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
            "holdout_fractions": list(holdout_fractions),
            "n_repeats": n_repeats,
            "top_n": top_n,
            "min_pool_size": min_pool_size,
            "seed": seed,
            "role_summaries": [],
            "limitations": _LIMITATIONS,
        }

    # Validate holdout_fractions.
    invalid_fractions = [
        f for f in holdout_fractions
        if not isinstance(f, (int, float))
        or isinstance(f, bool)
        or not math.isfinite(float(f))
        or f < 0
        or f >= 1
    ]
    if invalid_fractions:
        return {
            "schema": COHORT_SENSITIVITY_SCHEMA,
            "schema_version": COHORT_SENSITIVITY_VERSION,
            "generated_at": _now(),
            "status": "unavailable",
            "evidence": {
                "reason": (
                    "holdout_fractions must be in [0, 1); got invalid "
                    f"values: {invalid_fractions}"
                )
            },
            "baseline_schema": BASELINE_B2_SCHEMA,
            "baseline_version": BASELINE_B2_VERSION,
            "baseline_reference_minutes": baseline_reference_minutes,
            "holdout_fractions": list(holdout_fractions),
            "n_repeats": n_repeats,
            "top_n": top_n,
            "min_pool_size": min_pool_size,
            "seed": seed,
            "role_summaries": [],
            "limitations": _LIMITATIONS,
        }

    # Validate n_repeats.
    if (
        not isinstance(n_repeats, int)
        or isinstance(n_repeats, bool)
        or n_repeats < 0
    ):
        return {
            "schema": COHORT_SENSITIVITY_SCHEMA,
            "schema_version": COHORT_SENSITIVITY_VERSION,
            "generated_at": _now(),
            "status": "unavailable",
            "evidence": {
                "reason": (
                    f"n_repeats must be a non-negative integer; got {n_repeats!r}"
                )
            },
            "baseline_schema": BASELINE_B2_SCHEMA,
            "baseline_version": BASELINE_B2_VERSION,
            "baseline_reference_minutes": baseline_reference_minutes,
            "holdout_fractions": list(holdout_fractions),
            "n_repeats": n_repeats,
            "top_n": top_n,
            "min_pool_size": min_pool_size,
            "seed": seed,
            "role_summaries": [],
            "limitations": _LIMITATIONS,
        }

    rows, cohort_hash, membership_hash, load_status = _load_feature_matrix_rows(
        resolved, feature_matrix=feature_matrix, cohort_definition=cohort_definition
    )

    if load_status["status"] != "ok":
        return {
            "schema": COHORT_SENSITIVITY_SCHEMA,
            "schema_version": COHORT_SENSITIVITY_VERSION,
            "generated_at": _now(),
            **load_status,
            "baseline_schema": BASELINE_B2_SCHEMA,
            "baseline_version": BASELINE_B2_VERSION,
            "baseline_reference_minutes": baseline_reference_minutes,
            "holdout_fractions": list(holdout_fractions),
            "n_repeats": n_repeats,
            "top_n": top_n,
            "min_pool_size": min_pool_size,
            "seed": seed,
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

        # Compute baseline B2 ranks on the full pool.
        baseline_ranks_full, baseline_b2_scores, baseline_prior_mean, baseline_prior_source = (
            _compute_b2_ranks_on_pool(pool, dims, baseline_reference_minutes)
        )

        # Build a key -> baseline rank map for common-player matching.
        baseline_rank_by_key: dict[str, int] = {}
        for i, row in enumerate(pool):
            baseline_rank_by_key[_player_key(row)] = baseline_ranks_full[i]

        # Skip tiny pools.
        if n_pool < min_pool_size:
            role_summaries.append({
                "role_family": role_family.value,
                "player_count": n_pool,
                "baseline_prior_mean": round(baseline_prior_mean, 6),
                "baseline_prior_source": baseline_prior_source,
                "skipped_reason": "pool_too_small",
                "holdout_results": [],
                "min_spearman_correlation": None,
                "max_spearman_correlation": None,
                "worst_holdout_fraction": None,
                "worst_repeat_index": None,
            })
            continue

        holdout_results: list[dict[str, Any]] = []
        worst_spearman: float | None = None
        best_spearman: float | None = None
        worst_fraction: float | None = None
        worst_repeat: int | None = None

        for fraction in holdout_fractions:
            # Determine holdout count. Floor so we never hold out more
            # than the pool can spare. A fraction of 0 means "no holdout"
            # (still recomputes on the full pool, which is a useful
            # identity check).
            n_holdout = int(math.floor(n_pool * fraction))
            n_remaining = n_pool - n_holdout

            repeat_spearmans: list[float] = []
            repeat_summaries: list[dict[str, Any]] = []

            for repeat_idx in range(n_repeats):
                sub_seed = _derive_seed(seed, role_family, repeat_idx)
                import numpy as np

                rng = np.random.default_rng(sub_seed)

                if n_holdout == 0:
                    # No holdout — perturbed pool is the full pool.
                    perturbed_pool = list(pool)
                else:
                    # Randomly select indices to hold out (without replacement).
                    holdout_indices = set(
                        rng.choice(n_pool, size=n_holdout, replace=False).tolist()
                    )
                    perturbed_pool = [
                        row for i, row in enumerate(pool) if i not in holdout_indices
                    ]

                if len(perturbed_pool) < 2:
                    # Not enough players to compute meaningful ranks.
                    repeat_summaries.append({
                        "repeat_index": repeat_idx,
                        "held_out_count": n_holdout,
                        "remaining_count": len(perturbed_pool),
                        "common_player_count": 0,
                        "spearman_correlation": 1.0,
                        "mean_abs_rank_shift": 0.0,
                        "max_abs_rank_shift": 0,
                        "top_n_overlap": 1.0,
                        "skipped_reason": "perturbed_pool_too_small",
                    })
                    repeat_spearmans.append(1.0)
                    continue

                # Recompute B0→B2 on the perturbed pool.
                perturbed_ranks_full, _, perturbed_prior_mean, perturbed_prior_source = (
                    _compute_b2_ranks_on_pool(
                        perturbed_pool, dims, baseline_reference_minutes
                    )
                )

                # Build perturbed key -> rank map.
                perturbed_rank_by_key: dict[str, int] = {}
                for i, row in enumerate(perturbed_pool):
                    perturbed_rank_by_key[_player_key(row)] = perturbed_ranks_full[i]

                # Collect common players (in baseline order for stability).
                common_keys = [
                    _player_key(row) for row in pool
                    if _player_key(row) in perturbed_rank_by_key
                ]
                common_baseline_ranks = [
                    baseline_rank_by_key[k] for k in common_keys
                ]
                common_perturbed_ranks = [
                    perturbed_rank_by_key[k] for k in common_keys
                ]

                if len(common_keys) < 2:
                    spearman = 1.0
                    shift_stats = {"mean_abs_rank_shift": 0.0, "max_abs_rank_shift": 0.0}
                    overlap = 1.0
                else:
                    spearman = _spearman_on_ranks(
                        common_baseline_ranks, common_perturbed_ranks
                    )
                    shift_stats = _rank_shift_stats(
                        common_baseline_ranks, common_perturbed_ranks
                    )
                    overlap = _top_n_overlap(
                        common_baseline_ranks, common_perturbed_ranks, top_n
                    )

                repeat_summaries.append({
                    "repeat_index": repeat_idx,
                    "held_out_count": n_holdout,
                    "remaining_count": len(perturbed_pool),
                    "common_player_count": len(common_keys),
                    "perturbed_prior_mean": round(perturbed_prior_mean, 6),
                    "perturbed_prior_source": perturbed_prior_source,
                    "spearman_correlation": round(spearman, 6),
                    "mean_abs_rank_shift": round(shift_stats["mean_abs_rank_shift"], 4),
                    "max_abs_rank_shift": int(shift_stats["max_abs_rank_shift"]),
                    "top_n_overlap": round(overlap, 6),
                })
                repeat_spearmans.append(spearman)

                if worst_spearman is None or spearman < worst_spearman:
                    worst_spearman = spearman
                    worst_fraction = fraction
                    worst_repeat = repeat_idx
                if best_spearman is None or spearman > best_spearman:
                    best_spearman = spearman

            # Aggregate across repeats for this holdout fraction.
            if repeat_spearmans:
                min_sp = min(repeat_spearmans)
                max_sp = max(repeat_spearmans)
                mean_sp = sum(repeat_spearmans) / len(repeat_spearmans)
            else:
                min_sp = max_sp = mean_sp = None

            holdout_results.append({
                "holdout_fraction": fraction,
                "held_out_count": n_holdout,
                "remaining_count": n_remaining,
                "n_repeats": n_repeats,
                "min_spearman_correlation": round(min_sp, 6) if min_sp is not None else None,
                "max_spearman_correlation": round(max_sp, 6) if max_sp is not None else None,
                "mean_spearman_correlation": round(mean_sp, 6) if mean_sp is not None else None,
                "repeats": repeat_summaries,
            })

        role_summaries.append({
            "role_family": role_family.value,
            "player_count": n_pool,
            "baseline_prior_mean": round(baseline_prior_mean, 6),
            "baseline_prior_source": baseline_prior_source,
            "skipped_reason": None,
            "holdout_results": holdout_results,
            "min_spearman_correlation": (
                round(worst_spearman, 6) if worst_spearman is not None else None
            ),
            "max_spearman_correlation": (
                round(best_spearman, 6) if best_spearman is not None else None
            ),
            "worst_holdout_fraction": worst_fraction,
            "worst_repeat_index": worst_repeat,
        })

    return {
        "schema": COHORT_SENSITIVITY_SCHEMA,
        "schema_version": COHORT_SENSITIVITY_VERSION,
        "generated_at": _now(),
        "status": "ok",
        "cohort_hash": cohort_hash,
        "membership_hash": membership_hash,
        "baseline_schema": BASELINE_B2_SCHEMA,
        "baseline_version": BASELINE_B2_VERSION,
        "baseline_reference_minutes": baseline_reference_minutes,
        "holdout_fractions": list(holdout_fractions),
        "n_repeats": n_repeats,
        "top_n": top_n,
        "min_pool_size": min_pool_size,
        "seed": seed,
        "role_summaries": role_summaries,
        "limitations": _LIMITATIONS,
    }


__all__ = [
    "COHORT_SENSITIVITY_SCHEMA",
    "COHORT_SENSITIVITY_VERSION",
    "DEFAULT_HOLDOUT_FRACTIONS",
    "DEFAULT_N_REPEATS",
    "DEFAULT_TOP_N",
    "DEFAULT_MIN_POOL_SIZE",
    "DEFAULT_SEED",
    "compute_cohort_sensitivity_report",
]

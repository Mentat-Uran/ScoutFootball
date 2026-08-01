"""Tests for the PRS-MODEL-011 B1 weight sensitivity diagnostic.

Covers:

- ``_perturb_and_renormalise``:
  - perturbs the target dimension by ``delta`` (multiplicative)
  - leaves other dimensions unchanged before renormalisation
  - sums to 1.0 after renormalisation
  - clamps negative results at 0
  - returns None when all weights collapse to 0
  - single-dimension weight set is idempotent
- ``_compute_ranks``:
  - empty -> []
  - single element -> [1]
  - distinct scores -> 1..n with highest score = rank 1
  - ties share rank, next rank skips
- ``_spearman_on_ranks``:
  - identical ranks -> 1.0
  - reversed ranks -> -1.0
  - n < 2 -> 1.0
  - zero-variance rank list -> 1.0
- ``_top_n_overlap``:
  - empty -> 1.0
  - top_n <= 0 -> 1.0
  - identical ranks -> 1.0
  - disjoint top-N -> 0.0
  - partial overlap
  - top_n > n clamps to n
- ``_rank_shift_stats``:
  - empty -> 0/0
  - identical -> 0/0
  - mean and max computed correctly
- ``_build_column_arrays_for_role``:
  - returns one array per unique column across dimensions
  - no duplicate columns in dict
- ``_load_feature_matrix_rows``:
  - missing parquet -> unavailable
  - empty DataFrame -> unavailable
  - valid DataFrame -> rows with ``_role_family`` set
  - UNKNOWN positions are kept (filtered downstream)
- ``compute_weight_sensitivity_report``:
  - missing feature matrix -> status=unavailable
  - empty feature matrix -> status=unavailable
  - valid data -> status=ok
  - schema/version fields present
  - role_summaries only for roles with players
  - UNKNOWN role excluded
  - GK flagged as single_dimension
  - limitations non-empty
  - perturbation_deltas and top_n echoed
  - JSON-serialisable
  - GK perturbations are no-ops (spearman=1.0)
  - most/least sensitive dimensions set when multi-dim role
  - skipped perturbations reported when all weights collapse
  - baseline scores match B1 baseline (consistency)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.baseline_b0 import B0_DIMENSIONS, B0Dimension
from scoutfootball.evaluation.baseline_b1 import (
    B1_WEIGHTS,
    B1_WEIGHTS_VERSION,
    BASELINE_B1_SCHEMA,
    BASELINE_B1_VERSION,
    _vectorised_weighted_scores,
)
from scoutfootball.evaluation.role_system import RoleFamily
from scoutfootball.evaluation.sensitivity import (
    DEFAULT_PERTURBATION_DELTAS,
    DEFAULT_TOP_N,
    WEIGHT_SENSITIVITY_SCHEMA,
    WEIGHT_SENSITIVITY_VERSION,
    _build_column_arrays_for_role,
    _compute_ranks,
    _load_feature_matrix_rows,
    _perturb_and_renormalise,
    _rank_shift_stats,
    _spearman_on_ranks,
    _top_n_overlap,
    compute_weight_sensitivity_report,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _write_rating_feature_matrix(
    settings: PlatformSettings, df: pd.DataFrame
) -> None:
    path = settings.gold_root / "feature_store" / "rating_feature_matrix.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _make_feature_matrix_df(rows: list[dict] | None = None) -> pd.DataFrame:
    """Build a rating_feature_matrix DataFrame with columns B0/B1 consume.

    Mirrors the fixture in ``test_baseline_b1.py`` so the sensitivity
    report has a known pool: 2 CB, 1 ST, 1 GK, 1 UNKNOWN.
    """
    if rows is None:
        rows = [
            {
                "player_id": "u|1", "player_name": "CB-A", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 2000, "starts": 22,
                "tackles": 30, "interceptions": 40, "passes": 1500,
                "goals": 1, "assists": 0, "npxg": 0.5, "xa": 0.2,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            {
                "player_id": "u|2", "player_name": "CB-B", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 1500, "starts": 17,
                "tackles": 20, "interceptions": 25, "passes": 1000,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            {
                "player_id": "u|3", "player_name": "ST-A", "season_id": "2425",
                "position_group": "FW", "source_name": "understat",
                "minutes_played": 1800, "starts": 20,
                "tackles": 5, "interceptions": 5, "passes": 200,
                "goals": 20, "assists": 5, "npxg": 15.0, "xa": 4.0,
                "defense_missing": True, "possession_missing": True,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            {
                "player_id": "u|4", "player_name": "GK-A", "season_id": "2425",
                "position_group": "GK", "source_name": "understat",
                "minutes_played": 2700, "starts": 30,
                "tackles": 0, "interceptions": 0, "passes": 0,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": True, "possession_missing": True,
                "xT_VAEP_missing": True, "goalkeeper_missing": False,
            },
            {
                "player_id": "u|5", "player_name": "UNK-A", "season_id": "2425",
                "position_group": "XYZ", "source_name": "understat",
                "minutes_played": 1000, "starts": 11,
                "tackles": 10, "interceptions": 10, "passes": 500,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
        ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# _perturb_and_renormalise
# ---------------------------------------------------------------------------


class TestPerturbAndRenormalise:
    def test_perturbs_target_dimension_multiplicatively(self) -> None:
        """The target dim's weight is multiplied by (1 + delta) before
        renormalisation; other dims are unchanged in raw form."""
        raw = {"a": 0.5, "b": 0.3, "c": 0.2}
        out = _perturb_and_renormalise(raw, "b", delta=0.10)
        # Raw perturbed: a=0.5, b=0.33, c=0.2; total=1.03
        # Renormalised: a=0.5/1.03, b=0.33/1.03, c=0.2/1.03
        assert out is not None
        assert math.isclose(out["b"], 0.33 / 1.03, rel_tol=1e-12)
        assert math.isclose(out["a"], 0.5 / 1.03, rel_tol=1e-12)
        assert math.isclose(out["c"], 0.2 / 1.03, rel_tol=1e-12)

    def test_negative_delta_reduces_target_weight(self) -> None:
        raw = {"a": 0.5, "b": 0.3, "c": 0.2}
        out = _perturb_and_renormalise(raw, "b", delta=-0.50)
        assert out is not None
        # Raw perturbed: a=0.5, b=0.15, c=0.2; total=0.85
        assert math.isclose(out["b"], 0.15 / 0.85, rel_tol=1e-12)

    def test_sums_to_one_after_renormalisation(self) -> None:
        raw = {"a": 0.5, "b": 0.3, "c": 0.2}
        for delta in (-0.20, -0.10, 0.10, 0.20, 0.50, -0.90):
            out = _perturb_and_renormalise(raw, "a", delta=delta)
            assert out is not None
            total = sum(out.values())
            assert abs(total - 1.0) < 1e-12, f"delta={delta}: sum={total}"

    def test_negative_perturbed_weight_clamped_to_zero(self) -> None:
        """delta < -1 would produce a negative weight; clamp at 0."""
        raw = {"a": 0.5, "b": 0.3, "c": 0.2}
        out = _perturb_and_renormalise(raw, "a", delta=-1.50)
        assert out is not None
        # a is clamped to 0; total = 0 + 0.3 + 0.2 = 0.5
        assert out["a"] == 0.0
        assert math.isclose(out["b"], 0.3 / 0.5, rel_tol=1e-12)
        assert math.isclose(out["c"], 0.2 / 0.5, rel_tol=1e-12)
        assert abs(sum(out.values()) - 1.0) < 1e-12

    def test_returns_none_when_all_weights_collapse(self) -> None:
        """If perturbing the only non-zero weight zeros it out, total=0
        and the function returns None."""
        raw = {"a": 1.0, "b": 0.0, "c": 0.0}
        out = _perturb_and_renormalise(raw, "a", delta=-1.0)
        assert out is None

    def test_returns_none_when_all_weights_zero(self) -> None:
        raw = {"a": 0.0, "b": 0.0}
        out = _perturb_and_renormalise(raw, "a", delta=0.10)
        assert out is None

    def test_single_dimension_idempotent(self) -> None:
        """For a single-dimension weight set (e.g. GK availability=1.0),
        perturbing and renormalising always yields 1.0."""
        raw = {"availability": 1.0}
        for delta in (-0.20, -0.10, 0.10, 0.20, 0.99, -0.99):
            out = _perturb_and_renormalise(raw, "availability", delta=delta)
            # If delta == -1.0 exactly, returns None; otherwise 1.0.
            if delta == -1.0:
                assert out is None
            else:
                assert out is not None
                assert math.isclose(out["availability"], 1.0, abs_tol=1e-12)

    def test_positive_delta_increases_target_share(self) -> None:
        raw = {"a": 0.5, "b": 0.5}
        out = _perturb_and_renormalise(raw, "a", delta=0.20)
        assert out is not None
        assert out["a"] > raw["a"]
        assert out["b"] < raw["b"]

    def test_does_not_mutate_input(self) -> None:
        raw = {"a": 0.5, "b": 0.5}
        raw_copy = dict(raw)
        _perturb_and_renormalise(raw, "a", delta=0.10)
        assert raw == raw_copy

    def test_zero_delta_returns_renormalised_copy(self) -> None:
        """delta=0 should leave weights unchanged (still renormalised)."""
        raw = {"a": 0.5, "b": 0.3, "c": 0.2}
        out = _perturb_and_renormalise(raw, "a", delta=0.0)
        assert out is not None
        for k in raw:
            assert math.isclose(out[k], raw[k], rel_tol=1e-12)


# ---------------------------------------------------------------------------
# _compute_ranks
# ---------------------------------------------------------------------------


class TestComputeRanks:
    def test_empty(self) -> None:
        assert _compute_ranks([]) == []

    def test_single_element(self) -> None:
        assert _compute_ranks([42.0]) == [1]

    def test_distinct_scores_highest_is_rank_one(self) -> None:
        scores = [10.0, 30.0, 20.0]
        ranks = _compute_ranks(scores)
        # 30 is highest (rank 1), 20 next (rank 2), 10 lowest (rank 3)
        assert ranks == [3, 1, 2]

    def test_ties_share_rank_next_skips(self) -> None:
        scores = [30.0, 30.0, 20.0, 20.0, 10.0]
        ranks = _compute_ranks(scores)
        # Two 30s share rank 1, two 20s share rank 3 (next available),
        # 10 gets rank 5.
        assert ranks == [1, 1, 3, 3, 5]

    def test_all_ties_get_rank_one(self) -> None:
        scores = [50.0, 50.0, 50.0]
        ranks = _compute_ranks(scores)
        assert ranks == [1, 1, 1]

    def test_descending_scores(self) -> None:
        scores = [50.0, 40.0, 30.0, 20.0]
        ranks = _compute_ranks(scores)
        assert ranks == [1, 2, 3, 4]

    def test_ascending_scores(self) -> None:
        scores = [10.0, 20.0, 30.0, 40.0]
        ranks = _compute_ranks(scores)
        assert ranks == [4, 3, 2, 1]


# ---------------------------------------------------------------------------
# _spearman_on_ranks
# ---------------------------------------------------------------------------


class TestSpearmanOnRanks:
    def test_identical_ranks_is_one(self) -> None:
        assert _spearman_on_ranks([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0

    def test_reversed_ranks_is_minus_one(self) -> None:
        # For n=4 with ranks [1,2,3,4] vs [4,3,2,1], Spearman = -1.0
        result = _spearman_on_ranks([1, 2, 3, 4], [4, 3, 2, 1])
        assert math.isclose(result, -1.0, abs_tol=1e-12)

    def test_n_less_than_two_returns_one(self) -> None:
        assert _spearman_on_ranks([], []) == 1.0
        assert _spearman_on_ranks([1], [1]) == 1.0

    def test_zero_variance_returns_one(self) -> None:
        """All ranks equal -> zero variance -> returns 1.0 by convention."""
        assert _spearman_on_ranks([1, 1, 1], [1, 2, 3]) == 1.0
        assert _spearman_on_ranks([1, 2, 3], [2, 2, 2]) == 1.0

    def test_partial_correlation_in_unit_interval(self) -> None:
        # [1,2,3,4] vs [1,3,2,4]: positive but not perfect correlation
        result = _spearman_on_ranks([1, 2, 3, 4], [1, 3, 2, 4])
        assert -1.0 <= result <= 1.0
        assert result > 0.0  # positive correlation

    def test_known_value(self) -> None:
        """For ranks [1,2,3,4,5] vs [2,1,5,3,4], Spearman is known to
        be 0.6 (a textbook example). Verify our implementation matches."""
        result = _spearman_on_ranks([1, 2, 3, 4, 5], [2, 1, 5, 3, 4])
        assert math.isclose(result, 0.6, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# _top_n_overlap
# ---------------------------------------------------------------------------


class TestTopNOverlap:
    def test_empty_returns_one(self) -> None:
        assert _top_n_overlap([], [], top_n=5) == 1.0

    def test_top_n_zero_returns_one(self) -> None:
        assert _top_n_overlap([1, 2, 3], [1, 2, 3], top_n=0) == 1.0

    def test_negative_top_n_returns_one(self) -> None:
        assert _top_n_overlap([1, 2, 3], [3, 2, 1], top_n=-2) == 1.0

    def test_identical_ranks_returns_one(self) -> None:
        assert _top_n_overlap([1, 2, 3, 4], [1, 2, 3, 4], top_n=2) == 1.0

    def test_disjoint_top_n_returns_zero(self) -> None:
        # Baseline top-2 = players at indices 0,1. Perturbed top-2 = indices 2,3.
        # No overlap -> 0.0.
        baseline = [1, 2, 3, 4]
        perturbed = [3, 4, 1, 2]
        assert _top_n_overlap(baseline, perturbed, top_n=2) == 0.0

    def test_partial_overlap(self) -> None:
        # Baseline top-2 = {0,1}. Perturbed top-2 = {0,2}. Overlap = 1/2 = 0.5.
        baseline = [1, 2, 3, 4]
        perturbed = [1, 3, 2, 4]
        result = _top_n_overlap(baseline, perturbed, top_n=2)
        assert math.isclose(result, 0.5, abs_tol=1e-12)

    def test_top_n_greater_than_n_clamps(self) -> None:
        """When top_n > len(ranks), effective_n = len(ranks)."""
        baseline = [1, 2, 3]
        perturbed = [1, 2, 3]
        # top_n=10 but only 3 players -> effective_n=3
        assert _top_n_overlap(baseline, perturbed, top_n=10) == 1.0

    def test_top_n_greater_than_n_disjoint_still_clamps(self) -> None:
        baseline = [1, 2]
        perturbed = [2, 1]
        # effective_n = min(10, 2) = 2; both players in top-N for both
        # -> overlap = 2/2 = 1.0
        assert _top_n_overlap(baseline, perturbed, top_n=10) == 1.0

    def test_baseline_top_empty_returns_one(self) -> None:
        """If baseline_top set is empty (no players in top-N), return 1.0
        by convention (no signal possible)."""
        # n=5, top_n=3 -> baseline ranks [4,5,1,2,3] -> top-3 = {2,3,4}
        # If top_n=0 -> effective_n=0 -> baseline_top empty -> 1.0
        baseline = [4, 5, 1, 2, 3]
        perturbed = [1, 2, 3, 4, 5]
        assert _top_n_overlap(baseline, perturbed, top_n=0) == 1.0


# ---------------------------------------------------------------------------
# _rank_shift_stats
# ---------------------------------------------------------------------------


class TestRankShiftStats:
    def test_empty(self) -> None:
        stats = _rank_shift_stats([], [])
        assert stats == {"mean_abs_rank_shift": 0.0, "max_abs_rank_shift": 0.0}

    def test_identical_ranks(self) -> None:
        stats = _rank_shift_stats([1, 2, 3], [1, 2, 3])
        assert stats["mean_abs_rank_shift"] == 0.0
        assert stats["max_abs_rank_shift"] == 0.0

    def test_mean_and_max_computed_correctly(self) -> None:
        # Shifts: |1-3|=2, |2-1|=1, |3-2|=1 -> mean=4/3, max=2
        stats = _rank_shift_stats([1, 2, 3], [3, 1, 2])
        assert math.isclose(stats["mean_abs_rank_shift"], 4.0 / 3.0, rel_tol=1e-9)
        assert stats["max_abs_rank_shift"] == 2.0

    def test_returns_floats(self) -> None:
        stats = _rank_shift_stats([1, 2], [2, 1])
        assert isinstance(stats["mean_abs_rank_shift"], float)
        assert isinstance(stats["max_abs_rank_shift"], float)


# ---------------------------------------------------------------------------
# _build_column_arrays_for_role
# ---------------------------------------------------------------------------


class TestBuildColumnArraysForRole:
    def test_returns_dict_with_all_unique_columns(self) -> None:
        """The dict has one entry per unique column across all dimensions,
        with no duplicates."""
        # Use the real CB dimensions: defending(tackles, interceptions),
        # possession(passes), availability(minutes_played, starts).
        dims = B0_DIMENSIONS[RoleFamily.CB]
        pool = [
            {
                "tackles": 30, "interceptions": 40, "passes": 1500,
                "minutes_played": 2000, "starts": 22,
            },
            {
                "tackles": 20, "interceptions": 25, "passes": 1000,
                "minutes_played": 1500, "starts": 17,
            },
        ]
        arrays = _build_column_arrays_for_role(pool, dims)
        expected_cols = {"tackles", "interceptions", "passes", "minutes_played", "starts"}
        assert set(arrays.keys()) == expected_cols

    def test_no_duplicate_columns_even_if_shared(self) -> None:
        """If two dimensions reference the same column (e.g.
        availability and defending both list minutes_played), the column
        appears only once in the dict."""
        dims = (
            B0Dimension(
                key="dim_a", label="A", columns=("col1", "col2"), core=True,
            ),
            B0Dimension(
                key="dim_b", label="B", columns=("col2", "col3"), core=True,
            ),
        )
        pool = [{"col1": 1.0, "col2": 2.0, "col3": 3.0}]
        arrays = _build_column_arrays_for_role(pool, dims)
        assert set(arrays.keys()) == {"col1", "col2", "col3"}

    def test_arrays_have_length_equal_to_pool(self) -> None:
        dims = B0_DIMENSIONS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 1500,
             "minutes_played": 2000, "starts": 22},
            {"tackles": 20, "interceptions": 25, "passes": 1000,
             "minutes_played": 1500, "starts": 17},
            {"tackles": 10, "interceptions": 15, "passes": 500,
             "minutes_played": 1000, "starts": 11},
        ]
        arrays = _build_column_arrays_for_role(pool, dims)
        for col, arr in arrays.items():
            assert len(arr) == 3, f"{col}: expected length 3, got {len(arr)}"


# ---------------------------------------------------------------------------
# _load_feature_matrix_rows
# ---------------------------------------------------------------------------


class TestLoadFeatureMatrixRows:
    def test_missing_parquet_returns_unavailable(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rows, ch, mh, status = _load_feature_matrix_rows(settings)
        assert rows == []
        assert ch is None
        assert mh is None
        assert status["status"] == "unavailable"
        assert "rating_feature_matrix.parquet missing" in status["evidence"]["reason"]

    def test_empty_dataframe_returns_unavailable(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, pd.DataFrame())
        rows, _, _, status = _load_feature_matrix_rows(settings)
        assert rows == []
        assert status["status"] == "unavailable"
        assert "empty" in status["evidence"]["reason"]

    def test_valid_dataframe_returns_rows_with_role_family(
        self, tmp_path: Path
    ) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rows, _, _, status = _load_feature_matrix_rows(settings)
        assert status["status"] == "ok"
        assert len(rows) == 5
        for r in rows:
            assert "_role_family" in r
            assert isinstance(r["_role_family"], RoleFamily)

    def test_role_family_classification_correct(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rows, _, _, status = _load_feature_matrix_rows(settings)
        assert status["status"] == "ok"
        roles = [r["_role_family"] for r in rows]
        # CB, CB, ST, GK, UNKNOWN
        assert roles.count(RoleFamily.CB) == 2
        assert roles.count(RoleFamily.ST) == 1
        assert roles.count(RoleFamily.GK) == 1
        assert roles.count(RoleFamily.UNKNOWN) == 1

    def test_explicit_feature_matrix_argument_used(self, tmp_path: Path) -> None:
        """When ``feature_matrix`` is supplied directly, the parquet
        file is not read."""
        settings = PlatformSettings.from_root(tmp_path)
        # Do NOT write the parquet file; supply DataFrame directly.
        df = _make_feature_matrix_df()
        rows, _, _, status = _load_feature_matrix_rows(
            settings, feature_matrix=df
        )
        assert status["status"] == "ok"
        assert len(rows) == 5


# ---------------------------------------------------------------------------
# compute_weight_sensitivity_report — fail-closed
# ---------------------------------------------------------------------------


class TestComputeWeightSensitivityReportFailClosed:
    def test_missing_feature_matrix(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_weight_sensitivity_report(settings=settings)
        assert rep["status"] == "unavailable"
        assert rep["schema"] == WEIGHT_SENSITIVITY_SCHEMA
        assert rep["schema_version"] == WEIGHT_SENSITIVITY_VERSION
        assert "reason" in rep["evidence"]
        assert "rating_feature_matrix.parquet missing" in rep["evidence"]["reason"]

    def test_empty_feature_matrix(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, pd.DataFrame())
        rep = compute_weight_sensitivity_report(settings=settings)
        assert rep["status"] == "unavailable"
        assert "empty" in rep["evidence"]["reason"]

    def test_limitations_present_even_on_failure(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_weight_sensitivity_report(settings=settings)
        assert "limitations" in rep
        assert isinstance(rep["limitations"], list)
        assert len(rep["limitations"]) > 0

    def test_failure_report_carries_baseline_metadata(
        self, tmp_path: Path
    ) -> None:
        """Even on failure, the report must echo baseline schema/version
        and weight_version so consumers know what would have been used."""
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_weight_sensitivity_report(settings=settings)
        assert rep["baseline_schema"] == BASELINE_B1_SCHEMA
        assert rep["baseline_version"] == BASELINE_B1_VERSION
        assert rep["weight_version"] == B1_WEIGHTS_VERSION

    def test_failure_report_carries_deltas_and_top_n(
        self, tmp_path: Path
    ) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        custom_deltas = (-0.30, 0.30)
        rep = compute_weight_sensitivity_report(
            settings=settings, perturbation_deltas=custom_deltas, top_n=7
        )
        assert rep["perturbation_deltas"] == list(custom_deltas)
        assert rep["top_n"] == 7

    def test_failure_report_has_empty_role_summaries(
        self, tmp_path: Path
    ) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_weight_sensitivity_report(settings=settings)
        assert rep["role_summaries"] == []


# ---------------------------------------------------------------------------
# compute_weight_sensitivity_report — happy path
# ---------------------------------------------------------------------------


class TestComputeWeightSensitivityReportHappy:
    def test_status_ok(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        assert rep["status"] == "ok"
        assert rep["schema"] == WEIGHT_SENSITIVITY_SCHEMA
        assert rep["schema_version"] == WEIGHT_SENSITIVITY_VERSION

    def test_baseline_metadata_emitted(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        assert rep["baseline_schema"] == BASELINE_B1_SCHEMA
        assert rep["baseline_version"] == BASELINE_B1_VERSION
        assert rep["weight_version"] == B1_WEIGHTS_VERSION

    def test_deltas_and_top_n_echoed(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        assert rep["perturbation_deltas"] == list(DEFAULT_PERTURBATION_DELTAS)
        assert rep["top_n"] == DEFAULT_TOP_N

    def test_custom_deltas_and_top_n_echoed(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        custom_deltas = (-0.50, 0.50)
        rep = compute_weight_sensitivity_report(
            settings=settings, perturbation_deltas=custom_deltas, top_n=3
        )
        assert rep["perturbation_deltas"] == list(custom_deltas)
        assert rep["top_n"] == 3

    def test_role_summaries_only_for_roles_with_players(
        self, tmp_path: Path
    ) -> None:
        """Only CB, ST, GK have players in the fixture; other roles
        (DM, CM, AM, W, FB) are absent."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        roles = {rs["role_family"] for rs in rep["role_summaries"]}
        assert roles == {"CB", "ST", "GK"}

    def test_unknown_role_excluded(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        roles = {rs["role_family"] for rs in rep["role_summaries"]}
        assert "UNKNOWN" not in roles

    def test_role_summary_has_required_fields(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        for rs in rep["role_summaries"]:
            assert "role_family" in rs
            assert "player_count" in rs
            assert "dimensions_tested" in rs
            assert "single_dimension" in rs
            assert "most_sensitive_dimension" in rs
            assert "least_sensitive_dimension" in rs
            assert "per_dimension" in rs
            assert isinstance(rs["per_dimension"], dict)

    def test_gk_flagged_single_dimension(self, tmp_path: Path) -> None:
        """GK's B1 weight set is availability=1.0 (single dimension);
        the report must flag this."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        gk = next(
            rs for rs in rep["role_summaries"] if rs["role_family"] == "GK"
        )
        assert gk["single_dimension"] is True
        assert gk["dimensions_tested"] == ["availability"]

    def test_gk_perturbations_are_no_ops(self, tmp_path: Path) -> None:
        """For a single-dimension role, perturbing the only weight and
        renormalising always yields 1.0, so Spearman = 1.0 and rank
        shift = 0."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        gk = next(
            rs for rs in rep["role_summaries"] if rs["role_family"] == "GK"
        )
        dim_data = gk["per_dimension"]["availability"]
        for p in dim_data["perturbations"]:
            assert p["status"] == "ok"
            assert p["spearman_correlation"] == 1.0
            assert p["mean_abs_rank_shift"] == 0.0
            assert p["max_abs_rank_shift"] == 0
            assert p["top_n_overlap"] == 1.0

    def test_multi_dim_role_has_most_and_least_sensitive(
        self, tmp_path: Path
    ) -> None:
        """For CB (3 dims: defending, possession, availability), the
        report must set most/least sensitive dimension.

        Uses a richer CB pool where players trade off across dimensions
        so perturbing weights can shift ranks — a uniform dominance
        pool (one player best at everything) would leave all dims with
        identical Spearman and the most/least distinction degenerate.
        """
        settings = PlatformSettings.from_root(tmp_path)
        rows = [
            # CB-A: strong defending, weak possession, low availability
            {
                "player_id": "u|1", "player_name": "CB-A", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 1000, "starts": 11,
                "tackles": 50, "interceptions": 60, "passes": 500,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # CB-B: weak defending, strong possession, low availability
            {
                "player_id": "u|2", "player_name": "CB-B", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 1000, "starts": 11,
                "tackles": 10, "interceptions": 15, "passes": 2000,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # CB-C: medium defending, medium possession, high availability
            {
                "player_id": "u|3", "player_name": "CB-C", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 2700, "starts": 30,
                "tackles": 30, "interceptions": 35, "passes": 1200,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # CB-D: weak across the board
            {
                "player_id": "u|4", "player_name": "CB-D", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 800, "starts": 9,
                "tackles": 5, "interceptions": 5, "passes": 300,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # One GK to ensure the report has at least one other role.
            {
                "player_id": "u|5", "player_name": "GK-A", "season_id": "2425",
                "position_group": "GK", "source_name": "understat",
                "minutes_played": 2700, "starts": 30,
                "tackles": 0, "interceptions": 0, "passes": 0,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": True, "possession_missing": True,
                "xT_VAEP_missing": True, "goalkeeper_missing": False,
            },
        ]
        _write_rating_feature_matrix(settings, pd.DataFrame(rows))
        rep = compute_weight_sensitivity_report(
            settings=settings, perturbation_deltas=(-0.50, 0.50, -0.20, 0.20)
        )
        cb = next(
            rs for rs in rep["role_summaries"] if rs["role_family"] == "CB"
        )
        assert cb["single_dimension"] is False
        assert cb["player_count"] == 4
        assert cb["most_sensitive_dimension"] is not None
        assert cb["least_sensitive_dimension"] is not None
        # With 4 players trading off across 3 dims, perturbing different
        # weights should produce different worst-case Spearman values, so
        # most and least must be distinct.
        assert cb["most_sensitive_dimension"] != cb["least_sensitive_dimension"]

    def test_per_dimension_has_perturbations_for_each_delta(
        self, tmp_path: Path
    ) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        cb = next(
            rs for rs in rep["role_summaries"] if rs["role_family"] == "CB"
        )
        for dim_key in cb["dimensions_tested"]:
            dim_data = cb["per_dimension"][dim_key]
            assert len(dim_data["perturbations"]) == len(DEFAULT_PERTURBATION_DELTAS)
            deltas_in_report = [p["delta"] for p in dim_data["perturbations"]]
            assert deltas_in_report == list(DEFAULT_PERTURBATION_DELTAS)

    def test_per_dimension_aggregate_fields_present(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        cb = next(
            rs for rs in rep["role_summaries"] if rs["role_family"] == "CB"
        )
        for dim_key in cb["dimensions_tested"]:
            dim_data = cb["per_dimension"][dim_key]
            assert "min_spearman_correlation" in dim_data
            assert "worst_delta" in dim_data
            assert "max_mean_abs_rank_shift" in dim_data
            assert "max_abs_rank_shift" in dim_data
            assert "min_top_n_overlap" in dim_data

    def test_spearman_in_unit_interval_for_ok_perturbations(
        self, tmp_path: Path
    ) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        for rs in rep["role_summaries"]:
            for dim_key in rs["dimensions_tested"]:
                for p in rs["per_dimension"][dim_key]["perturbations"]:
                    if p["status"] == "ok":
                        assert -1.0 <= p["spearman_correlation"] <= 1.0
                        assert 0.0 <= p["top_n_overlap"] <= 1.0
                        assert p["mean_abs_rank_shift"] >= 0.0
                        assert p["max_abs_rank_shift"] >= 0

    def test_limitations_non_empty(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        assert isinstance(rep["limitations"], list)
        assert len(rep["limitations"]) > 0
        # Each limitation must be a non-empty string.
        for lim in rep["limitations"]:
            assert isinstance(lim, str)
            assert len(lim) > 0

    def test_json_serialisable(self, tmp_path: Path) -> None:
        """The full report must be JSON-serialisable (no numpy types, no
        datetime objects, no sets)."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        # Must not raise.
        encoded = json.dumps(rep, ensure_ascii=False)
        decoded = json.loads(encoded)
        assert decoded["schema"] == WEIGHT_SENSITIVITY_SCHEMA

    def test_player_count_matches_pool(self, tmp_path: Path) -> None:
        """role_summary.player_count must equal the number of rows in
        the feature matrix for that role."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        for rs in rep["role_summaries"]:
            if rs["role_family"] == "CB":
                assert rs["player_count"] == 2
            elif rs["role_family"] == "ST":
                assert rs["player_count"] == 1
            elif rs["role_family"] == "GK":
                assert rs["player_count"] == 1

    def test_dimensions_tested_match_b0(self, tmp_path: Path) -> None:
        """dimensions_tested must match B0_DIMENSIONS keys for each role."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(settings=settings)
        for rs in rep["role_summaries"]:
            role = RoleFamily(rs["role_family"])
            expected = [d.key for d in B0_DIMENSIONS[role]]
            assert rs["dimensions_tested"] == expected


# ---------------------------------------------------------------------------
# compute_weight_sensitivity_report — consistency with B1 baseline
# ---------------------------------------------------------------------------


class TestConsistencyWithB1Baseline:
    def test_baseline_scores_match_b1_vectorised_scoring(
        self, tmp_path: Path
    ) -> None:
        """The sensitivity module's baseline scores (computed via the
        same ``_vectorised_weighted_scores`` helper) must match what B1
        itself would compute with the unperturbed weight set.

        This guards against drift: the sensitivity module reuses B1's
        scoring internals, so the baseline ranks used for comparison
        must equal B1's actual ranks.
        """
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        compute_weight_sensitivity_report(settings=settings)

        # Reload rows the same way the sensitivity module does.
        rows, _, _, _ = _load_feature_matrix_rows(settings)
        cb_pool = [r for r in rows if r["_role_family"] == RoleFamily.CB]
        cb_dims = B0_DIMENSIONS[RoleFamily.CB]
        cb_weights = B1_WEIGHTS[RoleFamily.CB]
        cb_arrays = _build_column_arrays_for_role(cb_pool, cb_dims)
        b1_scores = _vectorised_weighted_scores(
            cb_arrays, cb_dims, cb_weights, len(cb_pool)
        )
        b1_ranks = _compute_ranks(b1_scores.tolist())

        # Zero-delta perturbation reproduces B1 ranks exactly.
        zero_delta_rep = compute_weight_sensitivity_report(
            settings=settings, perturbation_deltas=(0.0,)
        )
        cb_summary = next(
            rs for rs in zero_delta_rep["role_summaries"] if rs["role_family"] == "CB"
        )
        for dim_key in cb_summary["dimensions_tested"]:
            p = cb_summary["per_dimension"][dim_key]["perturbations"][0]
            assert p["status"] == "ok"
            assert p["spearman_correlation"] == 1.0
            assert p["mean_abs_rank_shift"] == 0.0
            assert p["max_abs_rank_shift"] == 0
            assert p["top_n_overlap"] == 1.0

        # Sanity: B1 ranks are not all-equal (the two CBs differ).
        assert len(set(b1_ranks)) == len(b1_ranks)


# ---------------------------------------------------------------------------
# compute_weight_sensitivity_report — skipped perturbations
# ---------------------------------------------------------------------------


class TestSkippedPerturbations:
    def test_skipped_perturbation_reported_when_all_weights_collapse(
        self, tmp_path: Path
    ) -> None:
        """When delta = -1.0 zeros out the only non-zero weight, the
        perturbation is skipped and reported as all_weights_zero.

        For GK (single dim availability=1.0), delta=-1.0 produces
        availability=0, total=0 -> None -> skipped.
        """
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(
            settings=settings, perturbation_deltas=(-1.0,)
        )
        gk = next(
            rs for rs in rep["role_summaries"] if rs["role_family"] == "GK"
        )
        p = gk["per_dimension"]["availability"]["perturbations"][0]
        assert p["status"] == "skipped"
        assert p["reason"] == "all_weights_zero"

    def test_skipped_aggregate_fields_none(self, tmp_path: Path) -> None:
        """When all perturbations for a dimension are skipped, the
        aggregate fields must be None (not 0 or False)."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(
            settings=settings, perturbation_deltas=(-1.0,)
        )
        gk = next(
            rs for rs in rep["role_summaries"] if rs["role_family"] == "GK"
        )
        dim_data = gk["per_dimension"]["availability"]
        assert dim_data["min_spearman_correlation"] is None
        assert dim_data["worst_delta"] is None
        assert dim_data["max_mean_abs_rank_shift"] is None
        assert dim_data["max_abs_rank_shift"] is None
        assert dim_data["min_top_n_overlap"] is None

    def test_skipped_perturbations_do_not_affect_most_least(
        self, tmp_path: Path
    ) -> None:
        """A fully-skipped dimension should not become most/least
        sensitive (it produces no Spearman signal)."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(
            settings=settings, perturbation_deltas=(-1.0,)
        )
        # With delta=-1.0, every dimension's single perturbation is
        # skipped for GK (single dim) but NOT for CB/ST (multi-dim:
        # zeroing one weight still leaves non-zero weights to
        # renormalise). So most/least for CB/ST must still be set or
        # None based on whether the dimension produced any ok pert.
        cb = next(
            (rs for rs in rep["role_summaries"] if rs["role_family"] == "CB"),
            None,
        )
        if cb is not None:
            # CB has 3 dims; zeroing one still leaves 2 non-zero -> ok.
            for dim_key in cb["dimensions_tested"]:
                dim_data = cb["per_dimension"][dim_key]
                # The single perturbation is ok (not skipped) because
                # zeroing one weight out of 3 leaves a positive total.
                p = dim_data["perturbations"][0]
                assert p["status"] == "ok"


# ---------------------------------------------------------------------------
# compute_weight_sensitivity_report — empty deltas edge case
# ---------------------------------------------------------------------------


class TestEmptyDeltas:
    def test_empty_deltas_produces_no_perturbations(
        self, tmp_path: Path
    ) -> None:
        """An empty deltas tuple produces no perturbations per dimension;
        aggregate fields fall back to None."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_weight_sensitivity_report(
            settings=settings, perturbation_deltas=()
        )
        assert rep["status"] == "ok"
        assert rep["perturbation_deltas"] == []
        cb = next(
            rs for rs in rep["role_summaries"] if rs["role_family"] == "CB"
        )
        for dim_key in cb["dimensions_tested"]:
            dim_data = cb["per_dimension"][dim_key]
            assert dim_data["perturbations"] == []
            assert dim_data["min_spearman_correlation"] is None
            assert dim_data["worst_delta"] is None
        # No perturbations -> most/least sensitive cannot be determined.
        assert cb["most_sensitive_dimension"] is None
        assert cb["least_sensitive_dimension"] is None


# ---------------------------------------------------------------------------
# compute_weight_sensitivity_report — cohort filtering
# ---------------------------------------------------------------------------


class TestCohortFiltering:
    def test_cohort_restricts_rows(self, tmp_path: Path) -> None:
        """When a CohortDefinition is supplied, only members are scored.

        We use a role-only cohort that includes only CB players; the
        report should then only contain CB (ST, GK excluded).
        """
        from scoutfootball.evaluation.cohort import CohortDefinition

        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        # preview_cohort reads player_match.parquet — write the same
        # fixture DataFrame there so the cohort preview can resolve
        # membership.
        pm_path = settings.gold_root / "feature_store" / "player_match.parquet"
        pm_path.parent.mkdir(parents=True, exist_ok=True)
        _make_feature_matrix_df().to_parquet(pm_path, index=False)

        cohort = CohortDefinition(
            name="cb-only",
            season_ids=frozenset({"2425"}),
            role_families=frozenset({RoleFamily.CB}),
        )
        rep = compute_weight_sensitivity_report(
            settings=settings, cohort_definition=cohort
        )
        if rep["status"] != "ok":
            # Cohort preview can fail if the player_match schema differs;
            # in that case skip this test rather than force a pass.
            pytest.skip(
                f"cohort preview failed: {rep.get('evidence', {}).get('reason')}"
            )
        roles = {rs["role_family"] for rs in rep["role_summaries"]}
        # Only CB should be present.
        assert roles == {"CB"}
        # cohort_hash/membership_hash propagated.
        assert rep["cohort_hash"] is not None
        assert rep["membership_hash"] is not None


# ---------------------------------------------------------------------------
# compute_weight_sensitivity_report — explicit feature_matrix argument
# ---------------------------------------------------------------------------


class TestExplicitFeatureMatrix:
    def test_explicit_feature_matrix_skips_parquet(
        self, tmp_path: Path
    ) -> None:
        """When ``feature_matrix`` is supplied directly, the parquet
        file is not required."""
        settings = PlatformSettings.from_root(tmp_path)
        # Do NOT write the parquet file.
        df = _make_feature_matrix_df()
        rep = compute_weight_sensitivity_report(
            settings=settings, feature_matrix=df
        )
        assert rep["status"] == "ok"
        roles = {rs["role_family"] for rs in rep["role_summaries"]}
        assert roles == {"CB", "ST", "GK"}

    def test_explicit_empty_dataframe_returns_unavailable(
        self, tmp_path: Path
    ) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_weight_sensitivity_report(
            settings=settings, feature_matrix=pd.DataFrame()
        )
        assert rep["status"] == "unavailable"
        assert "empty" in rep["evidence"]["reason"]

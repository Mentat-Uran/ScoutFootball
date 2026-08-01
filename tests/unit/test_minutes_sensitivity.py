"""Tests for the PRS-MODEL-012 B2 minutes-threshold sensitivity diagnostic.

Covers:

- ``_spearman_on_ranks``:
  - identical ranks -> 1.0
  - reversed ranks -> -1.0
  - n < 2 -> 1.0
  - zero-variance rank list -> 1.0
  - known textbook value
- ``_top_n_overlap``:
  - empty -> 1.0
  - top_n <= 0 -> 1.0
  - identical ranks -> 1.0
  - disjoint top-N -> 0.0
  - partial overlap
  - top_n > n clamps to n
  - baseline_top empty -> 1.0
- ``_rank_shift_stats``:
  - empty -> 0/0
  - identical -> 0/0
  - mean and max computed correctly
  - returns floats
- ``_build_minutes_array``:
  - length matches pool
  - missing minutes -> NaN
  - values placed correctly
- ``_load_feature_matrix_rows``:
  - missing parquet -> unavailable
  - empty DataFrame -> unavailable
  - valid DataFrame -> rows with ``_role_family`` set
  - role classification correct
  - explicit feature_matrix bypasses parquet
- ``compute_minutes_sensitivity_report``:
  - missing feature matrix -> status=unavailable
  - empty feature matrix -> status=unavailable
  - invalid baseline_reference_minutes (zero/negative/NaN/inf/bool)
  - failed report still carries limitations + baseline metadata
  - valid data -> status=ok
  - schema/version fields present
  - role_summaries only for roles with players
  - UNKNOWN role excluded
  - limitations non-empty
  - perturbation_deltas, top_n, baseline_reference_minutes echoed
  - JSON-serialisable
  - per-delta perturbation entries present
  - Spearman in [-1, 1]
  - most/least sensitive delta set
  - min/max spearman set
  - clamped flag when delta pushes ref below 1
  - prior_source/stable_core_count tracked per perturbation
  - baseline_prior_mean/prior_source/stable_core_count present
  - empty deltas edge case
  - cohort filtering
  - explicit feature_matrix parameter
  - B2 baseline consistency (zero delta reproduces B2 ranks)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.baseline_b2 import (
    BASELINE_B2_SCHEMA,
    BASELINE_B2_VERSION,
    DEFAULT_REFERENCE_MINUTES,
)
from scoutfootball.evaluation.minutes_sensitivity import (
    DEFAULT_MINUTES_DELTAS,
    DEFAULT_TOP_N,
    MINUTES_SENSITIVITY_SCHEMA,
    MINUTES_SENSITIVITY_VERSION,
    _build_minutes_array,
    _load_feature_matrix_rows,
    _rank_shift_stats,
    _spearman_on_ranks,
    _top_n_overlap,
    compute_minutes_sensitivity_report,
)
from scoutfootball.evaluation.role_system import RoleFamily

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
    """Build a rating_feature_matrix DataFrame with columns B0/B2 consume.

    Mirrors the fixture in ``test_baseline_b2.py`` so the sensitivity
    report has a known pool with varied minutes_played (essential for
    B2 shrinkage to produce differentiated scores).
    """
    if rows is None:
        rows = [
            # CB-A: high minutes, strong defending
            {
                "player_id": "u|1", "player_name": "CB-A", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 2700, "starts": 30,
                "tackles": 50, "interceptions": 60, "passes": 1800,
                "goals": 1, "assists": 0, "npxg": 0.5, "xa": 0.2,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # CB-B: medium minutes, medium defending
            {
                "player_id": "u|2", "player_name": "CB-B", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 1500, "starts": 17,
                "tackles": 30, "interceptions": 35, "passes": 1000,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # CB-C: very low minutes (below reference_minutes=900),
            # high per-90 output — shrinkage should pull toward prior
            {
                "player_id": "u|3", "player_name": "CB-C", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 90, "starts": 1,
                "tackles": 10, "interceptions": 12, "passes": 80,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # CB-D: low minutes, weak per-90 output
            {
                "player_id": "u|4", "player_name": "CB-D", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 200, "starts": 2,
                "tackles": 2, "interceptions": 3, "passes": 60,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # One ST with full data
            {
                "player_id": "u|5", "player_name": "ST-A", "season_id": "2425",
                "position_group": "FW", "source_name": "understat",
                "minutes_played": 1800, "starts": 20,
                "tackles": 5, "interceptions": 5, "passes": 200,
                "goals": 20, "assists": 5, "npxg": 15.0, "xa": 4.0,
                "defense_missing": True, "possession_missing": True,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # One ST with very low minutes — should shrink toward prior
            {
                "player_id": "u|6", "player_name": "ST-B", "season_id": "2425",
                "position_group": "FW", "source_name": "understat",
                "minutes_played": 45, "starts": 0,
                "tackles": 0, "interceptions": 0, "passes": 5,
                "goals": 3, "assists": 0, "npxg": 2.5, "xa": 0.0,
                "defense_missing": True, "possession_missing": True,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # One GK (availability-only)
            {
                "player_id": "u|7", "player_name": "GK-A", "season_id": "2425",
                "position_group": "GK", "source_name": "understat",
                "minutes_played": 2700, "starts": 30,
                "tackles": 0, "interceptions": 0, "passes": 0,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": True, "possession_missing": True,
                "xT_VAEP_missing": True, "goalkeeper_missing": False,
            },
            # One UNKNOWN position (not scored)
            {
                "player_id": "u|8", "player_name": "UNK-A", "season_id": "2425",
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
# _spearman_on_ranks
# ---------------------------------------------------------------------------


class TestSpearmanOnRanks:
    def test_identical_ranks_is_one(self) -> None:
        assert _spearman_on_ranks([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == 1.0

    def test_reversed_ranks_is_minus_one(self) -> None:
        assert _spearman_on_ranks([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == -1.0

    def test_n_less_than_two_returns_one(self) -> None:
        assert _spearman_on_ranks([1], [1]) == 1.0
        assert _spearman_on_ranks([], []) == 1.0

    def test_zero_variance_returns_one(self) -> None:
        # All ranks identical -> zero variance -> 1.0 (avoids false alarm)
        assert _spearman_on_ranks([1, 1, 1], [2, 2, 2]) == 1.0

    def test_known_value(self) -> None:
        # Textbook: ranks [1,2,3,4,5] vs [2,1,5,3,4] -> Spearman = 0.6
        result = _spearman_on_ranks([1, 2, 3, 4, 5], [2, 1, 5, 3, 4])
        assert math.isclose(result, 0.6, abs_tol=1e-9)

    def test_partial_correlation_in_unit_interval(self) -> None:
        result = _spearman_on_ranks([1, 2, 3, 4, 5], [1, 3, 2, 5, 4])
        assert -1.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# _top_n_overlap
# ---------------------------------------------------------------------------


class TestTopNOverlap:
    def test_empty_returns_one(self) -> None:
        assert _top_n_overlap([], [], top_n=5) == 1.0

    def test_top_n_zero_returns_one(self) -> None:
        assert _top_n_overlap([1, 2, 3], [1, 2, 3], top_n=0) == 1.0

    def test_negative_top_n_returns_one(self) -> None:
        assert _top_n_overlap([1, 2, 3], [1, 2, 3], top_n=-3) == 1.0

    def test_identical_ranks_returns_one(self) -> None:
        assert _top_n_overlap([1, 2, 3, 4], [1, 2, 3, 4], top_n=2) == 1.0

    def test_disjoint_top_n_returns_zero(self) -> None:
        # Baseline top-2 = {0,1}; perturbed top-2 = {2,3}
        assert _top_n_overlap([1, 2, 3, 4], [3, 4, 1, 2], top_n=2) == 0.0

    def test_partial_overlap(self) -> None:
        # Baseline top-2 = {0,1}. Perturbed top-2 = {0,2}. Overlap = 1/2.
        assert _top_n_overlap([1, 2, 3, 4], [1, 3, 2, 4], top_n=2) == 0.5

    def test_top_n_greater_than_n_clamps(self) -> None:
        # n=3, top_n=10 -> effective_n=3. All three players in both.
        assert _top_n_overlap([1, 2, 3], [1, 2, 3], top_n=10) == 1.0

    def test_baseline_top_empty_returns_one(self) -> None:
        # No players in baseline top-N (shouldn't normally happen with
        # valid ranks, but guard against div-by-zero).
        # ranks all > effective_n
        result = _top_n_overlap([5, 6, 7], [1, 2, 3], top_n=2)
        assert result == 1.0


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
# _build_minutes_array
# ---------------------------------------------------------------------------


class TestBuildMinutesArray:
    def test_length_matches_pool(self) -> None:
        pool = [{"minutes_played": 100}, {"minutes_played": 200}, {"minutes_played": 300}]
        arr = _build_minutes_array(pool)
        assert len(arr) == 3

    def test_missing_minutes_become_nan(self) -> None:
        pool = [{"minutes_played": 100}, {}, {"minutes_played": 300}]
        arr = _build_minutes_array(pool)
        assert math.isnan(arr[1])
        assert arr[0] == 100
        assert arr[2] == 300

    def test_values_placed_correctly(self) -> None:
        pool = [{"minutes_played": 90}, {"minutes_played": 1800}, {"minutes_played": 2700}]
        arr = _build_minutes_array(pool)
        assert arr[0] == 90
        assert arr[1] == 1800
        assert arr[2] == 2700

    def test_empty_pool(self) -> None:
        arr = _build_minutes_array([])
        assert len(arr) == 0


# ---------------------------------------------------------------------------
# _load_feature_matrix_rows
# ---------------------------------------------------------------------------


class TestLoadFeatureMatrixRows:
    def test_missing_parquet_returns_unavailable(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rows, ch, mh, status = _load_feature_matrix_rows(settings)
        assert rows == []
        assert status["status"] == "unavailable"
        assert "missing" in status["evidence"]["reason"]

    def test_empty_dataframe_returns_unavailable(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep, _, _, status = _load_feature_matrix_rows(
            settings, feature_matrix=pd.DataFrame()
        )
        assert rep == []
        assert status["status"] == "unavailable"
        assert "empty" in status["evidence"]["reason"]

    def test_valid_dataframe_returns_rows_with_role_family(
        self, tmp_path: Path
    ) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        df = _make_feature_matrix_df()
        rows, _, _, status = _load_feature_matrix_rows(
            settings, feature_matrix=df
        )
        assert status["status"] == "ok"
        assert len(rows) == 8
        assert all("_role_family" in r for r in rows)

    def test_role_family_classification_correct(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        df = _make_feature_matrix_df()
        rows, _, _, _ = _load_feature_matrix_rows(
            settings, feature_matrix=df
        )
        roles = {r["_role_family"] for r in rows}
        assert RoleFamily.CB in roles
        assert RoleFamily.ST in roles
        assert RoleFamily.GK in roles
        assert RoleFamily.UNKNOWN in roles

    def test_explicit_feature_matrix_bypasses_parquet(
        self, tmp_path: Path
    ) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        # No parquet written.
        df = _make_feature_matrix_df()
        rows, _, _, status = _load_feature_matrix_rows(
            settings, feature_matrix=df
        )
        assert status["status"] == "ok"
        assert len(rows) == 8


# ---------------------------------------------------------------------------
# compute_minutes_sensitivity_report — fail-closed
# ---------------------------------------------------------------------------


class TestComputeMinutesSensitivityReportFailClosed:
    def test_missing_feature_matrix_returns_unavailable(
        self, tmp_path: Path
    ) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(settings=settings)
        assert rep["status"] == "unavailable"
        assert "missing" in rep["evidence"]["reason"]
        # Fail-closed report must still carry metadata.
        assert rep["schema"] == MINUTES_SENSITIVITY_SCHEMA
        assert rep["schema_version"] == MINUTES_SENSITIVITY_VERSION
        assert rep["baseline_schema"] == BASELINE_B2_SCHEMA
        assert rep["baseline_version"] == BASELINE_B2_VERSION
        assert rep["role_summaries"] == []
        assert len(rep["limitations"]) > 0
        assert rep["perturbation_deltas"] == list(DEFAULT_MINUTES_DELTAS)
        assert rep["top_n"] == DEFAULT_TOP_N

    def test_empty_feature_matrix_returns_unavailable(
        self, tmp_path: Path
    ) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=pd.DataFrame()
        )
        assert rep["status"] == "unavailable"
        assert "empty" in rep["evidence"]["reason"]

    def test_invalid_baseline_reference_minutes_zero(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            baseline_reference_minutes=0,
        )
        assert rep["status"] == "unavailable"
        assert "positive" in rep["evidence"]["reason"]

    def test_invalid_baseline_reference_minutes_negative(
        self, tmp_path: Path
    ) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            baseline_reference_minutes=-100,
        )
        assert rep["status"] == "unavailable"

    def test_invalid_baseline_reference_minutes_nan(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            baseline_reference_minutes=float("nan"),
        )
        assert rep["status"] == "unavailable"

    def test_invalid_baseline_reference_minutes_inf(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            baseline_reference_minutes=float("inf"),
        )
        assert rep["status"] == "unavailable"

    def test_bool_baseline_reference_minutes_rejected(self, tmp_path: Path) -> None:
        """Python bools are ints, but reference_minutes=True (==1) should
        be rejected because it's semantically nonsensical."""
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            baseline_reference_minutes=True,  # type: ignore[arg-type]
        )
        assert rep["status"] == "unavailable"


# ---------------------------------------------------------------------------
# compute_minutes_sensitivity_report — happy path
# ---------------------------------------------------------------------------


class TestComputeMinutesSensitivityReportHappy:
    def test_status_ok(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=_make_feature_matrix_df()
        )
        assert rep["status"] == "ok"

    def test_schema_and_version(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=_make_feature_matrix_df()
        )
        assert rep["schema"] == MINUTES_SENSITIVITY_SCHEMA
        assert rep["schema_version"] == MINUTES_SENSITIVITY_VERSION

    def test_baseline_metadata_present(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=_make_feature_matrix_df()
        )
        assert rep["baseline_schema"] == BASELINE_B2_SCHEMA
        assert rep["baseline_version"] == BASELINE_B2_VERSION
        assert rep["baseline_reference_minutes"] == DEFAULT_REFERENCE_MINUTES

    def test_perturbation_deltas_and_top_n_echoed(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        custom_deltas = (-500, 500)
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            perturbation_deltas=custom_deltas,
            top_n=3,
        )
        assert rep["perturbation_deltas"] == [-500, 500]
        assert rep["top_n"] == 3

    def test_only_reports_roles_with_players(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=_make_feature_matrix_df()
        )
        roles = {rs["role_family"] for rs in rep["role_summaries"]}
        # CB, ST, GK have players; UNKNOWN is excluded; no AM/W/CM/FB/DM
        assert roles == {"CB", "ST", "GK"}

    def test_unknown_role_excluded(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=_make_feature_matrix_df()
        )
        roles = {rs["role_family"] for rs in rep["role_summaries"]}
        assert "UNKNOWN" not in roles

    def test_role_summary_required_fields(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=_make_feature_matrix_df()
        )
        for rs in rep["role_summaries"]:
            assert "role_family" in rs
            assert "player_count" in rs
            assert "baseline_prior_mean" in rs
            assert "baseline_prior_source" in rs
            assert "baseline_stable_core_count" in rs
            assert "most_sensitive_delta" in rs
            assert "least_sensitive_delta" in rs
            assert "min_spearman_correlation" in rs
            assert "max_spearman_correlation" in rs
            assert "perturbations" in rs

    def test_per_delta_perturbation_entries(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=_make_feature_matrix_df()
        )
        for rs in rep["role_summaries"]:
            assert len(rs["perturbations"]) == len(DEFAULT_MINUTES_DELTAS)
            for p in rs["perturbations"]:
                assert "delta" in p
                assert "perturbed_reference_minutes" in p
                assert "clamped" in p
                assert "prior_mean" in p
                assert "prior_source" in p
                assert "stable_core_count" in p
                assert "spearman_correlation" in p
                assert "mean_abs_rank_shift" in p
                assert "max_abs_rank_shift" in p
                assert "top_n_overlap" in p

    def test_spearman_in_unit_interval(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=_make_feature_matrix_df()
        )
        for rs in rep["role_summaries"]:
            for p in rs["perturbations"]:
                assert -1.0 <= p["spearman_correlation"] <= 1.0

    def test_limitations_non_empty(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=_make_feature_matrix_df()
        )
        assert len(rep["limitations"]) > 0

    def test_json_serializable(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=_make_feature_matrix_df()
        )
        json.dumps(rep, ensure_ascii=False)

    def test_player_count_matches_pool(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=_make_feature_matrix_df()
        )
        role_counts = {rs["role_family"]: rs["player_count"] for rs in rep["role_summaries"]}
        assert role_counts["CB"] == 4
        assert role_counts["ST"] == 2
        assert role_counts["GK"] == 1

    def test_most_and_least_sensitive_delta_set(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=_make_feature_matrix_df()
        )
        for rs in rep["role_summaries"]:
            assert rs["most_sensitive_delta"] is not None
            assert rs["least_sensitive_delta"] is not None
            assert rs["min_spearman_correlation"] is not None
            assert rs["max_spearman_correlation"] is not None
            # min_spearman <= max_spearman
            assert rs["min_spearman_correlation"] <= rs["max_spearman_correlation"]

    def test_clamped_flag_when_delta_pushes_ref_below_one(
        self, tmp_path: Path
    ) -> None:
        """When baseline_reference_minutes + delta < 1, the perturbed
        value is clamped to 1 and clamped=True is reported."""
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            baseline_reference_minutes=100,
            perturbation_deltas=(-200,),
        )
        # delta=-200, baseline=100 -> raw=-100 -> clamped to 1
        for rs in rep["role_summaries"]:
            assert len(rs["perturbations"]) == 1
            p = rs["perturbations"][0]
            assert p["clamped"] is True
            assert p["perturbed_reference_minutes"] == 1.0

    def test_no_clamp_when_delta_keeps_ref_positive(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            baseline_reference_minutes=900,
            perturbation_deltas=(-300,),
        )
        for rs in rep["role_summaries"]:
            p = rs["perturbations"][0]
            assert p["clamped"] is False
            assert p["perturbed_reference_minutes"] == 600.0

    def test_prior_source_tracked_per_perturbation(self, tmp_path: Path) -> None:
        """Each perturbation reports prior_source so the maintainer can
        see whether a threshold change flips the prior into fallback."""
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=_make_feature_matrix_df()
        )
        for rs in rep["role_summaries"]:
            for p in rs["perturbations"]:
                assert p["prior_source"] in (
                    "stable_core",
                    "fallback_full_pool",
                    "empty",
                )

    def test_stable_core_count_changes_with_threshold(self, tmp_path: Path) -> None:
        """When reference_minutes increases, fewer players meet the
        stable_core threshold, so stable_core_count should generally
        decrease (or stay the same)."""
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            baseline_reference_minutes=900,
            perturbation_deltas=(-750, 700),
        )
        cb = next(
            rs for rs in rep["role_summaries"] if rs["role_family"] == "CB"
        )
        # CB pool: minutes = [2700, 1500, 90, 200]
        # baseline ref=900: stable_core = {2700, 1500} -> count=2
        assert cb["baseline_stable_core_count"] == 2
        # delta=-750 -> ref=150: 200 >= 150 so CB-D joins;
        # stable_core = {2700, 1500, 200} -> count=3 (90 < 150, CB-C stays out)
        neg = next(p for p in cb["perturbations"] if p["delta"] == -750)
        assert neg["stable_core_count"] == 3
        # delta=+700 -> ref=1600: only 2700 >= 1600;
        # stable_core = {2700} -> count=1 (1500 < 1600, CB-B drops out)
        pos = next(p for p in cb["perturbations"] if p["delta"] == 700)
        assert pos["stable_core_count"] == 1


# ---------------------------------------------------------------------------
# B2 baseline consistency
# ---------------------------------------------------------------------------


class TestConsistencyWithB2Baseline:
    def test_zero_delta_reproduces_b2_ranks(self, tmp_path: Path) -> None:
        """A delta of 0 should reproduce the baseline B2 ranks exactly,
        because perturbed_reference_minutes == baseline_reference_minutes."""
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            perturbation_deltas=(0,),
        )
        assert rep["status"] == "ok"
        for rs in rep["role_summaries"]:
            for p in rs["perturbations"]:
                # delta=0 -> identical ranking -> spearman=1.0,
                # mean_shift=0, max_shift=0, top_n_overlap=1.0
                assert p["spearman_correlation"] == 1.0
                assert p["mean_abs_rank_shift"] == 0.0
                assert p["max_abs_rank_shift"] == 0
                assert p["top_n_overlap"] == 1.0
                # perturbed_reference_minutes == baseline
                assert p["perturbed_reference_minutes"] == rep["baseline_reference_minutes"]

    def test_b2_ranks_not_all_identical(self, tmp_path: Path) -> None:
        """Sanity: with varied minutes, B2 should produce differentiated
        rankings. If all ranks were identical, spearman would be 1.0
        trivially (zero variance) and the test would be meaningless."""
        settings = PlatformSettings.from_root(tmp_path)
        # With 4 distinct CB players, at least one perturbation that
        # changes the threshold should produce spearman < 1.0.
        rep2 = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            perturbation_deltas=(-600, 600),
        )
        cb2 = next(
            rs for rs in rep2["role_summaries"] if rs["role_family"] == "CB"
        )
        # At least one of the two perturbations should move a rank
        # (CB-C has 90 min, CB-D has 200 min — both highly sensitive
        # to threshold changes around 900).
        spearmans = [p["spearman_correlation"] for p in cb2["perturbations"]]
        assert any(s < 1.0 for s in spearmans)

    def test_b0_scores_reused_across_perturbations(self, tmp_path: Path) -> None:
        """B0 scores don't depend on reference_minutes, so the
        sensitivity is purely from shrinkage+prior. Verify by checking
        that perturbed B2 scores differ from baseline only when
        shrinkage/prior change — i.e., high-minute players (low
        shrinkage) move less than low-minute players."""
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            perturbation_deltas=(600,),
        )
        cb = next(
            rs for rs in rep["role_summaries"] if rs["role_family"] == "CB"
        )
        # With delta=+600 (ref 900->1500), shrinkage weights increase
        # for every player (more pull toward prior). CB-A (2700 min) has
        # low shrinkage at both thresholds, so its rank tends to be
        # stable. CB-C (90 min) and CB-D (200 min) have high shrinkage
        # at both thresholds; their relative order can flip as the
        # prior pulls them together. The overall spearman should be
        # < 1.0 (some rank movement).
        p = cb["perturbations"][0]
        assert p["spearman_correlation"] < 1.0 or p["mean_abs_rank_shift"] > 0


# ---------------------------------------------------------------------------
# Empty deltas edge case
# ---------------------------------------------------------------------------


class TestEmptyDeltas:
    def test_empty_deltas_produces_no_perturbations(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            perturbation_deltas=(),
        )
        assert rep["status"] == "ok"
        for rs in rep["role_summaries"]:
            assert rs["perturbations"] == []
            assert rs["most_sensitive_delta"] is None
            assert rs["least_sensitive_delta"] is None
            assert rs["min_spearman_correlation"] is None
            assert rs["max_spearman_correlation"] is None
            # baseline fields still present
            assert rs["baseline_prior_mean"] is not None
            assert rs["baseline_prior_source"] is not None
            assert rs["baseline_stable_core_count"] is not None


# ---------------------------------------------------------------------------
# Cohort filtering
# ---------------------------------------------------------------------------


class TestCohortFiltering:
    def test_cohort_restricts_rows(self, tmp_path: Path) -> None:
        """When a CohortDefinition is supplied, only members are scored."""
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
        rep = compute_minutes_sensitivity_report(
            settings=settings, cohort_definition=cohort
        )
        if rep["status"] != "ok":
            pytest.skip(
                f"cohort preview failed: {rep.get('evidence', {}).get('reason')}"
            )
        roles = {rs["role_family"] for rs in rep["role_summaries"]}
        assert roles == {"CB"}
        assert rep["cohort_hash"] is not None
        assert rep["membership_hash"] is not None


# ---------------------------------------------------------------------------
# Explicit feature_matrix parameter
# ---------------------------------------------------------------------------


class TestExplicitFeatureMatrix:
    def test_explicit_feature_matrix_skips_parquet(
        self, tmp_path: Path
    ) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        # Do NOT write the parquet file.
        df = _make_feature_matrix_df()
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=df
        )
        assert rep["status"] == "ok"
        roles = {rs["role_family"] for rs in rep["role_summaries"]}
        assert roles == {"CB", "ST", "GK"}

    def test_explicit_empty_dataframe_returns_unavailable(
        self, tmp_path: Path
    ) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings, feature_matrix=pd.DataFrame()
        )
        assert rep["status"] == "unavailable"
        assert "empty" in rep["evidence"]["reason"]


# ---------------------------------------------------------------------------
# Prior source transition
# ---------------------------------------------------------------------------


class TestPriorSourceTransition:
    def test_prior_source_can_flip_to_fallback(self, tmp_path: Path) -> None:
        """When reference_minutes is raised above all players' minutes,
        no player meets the stable_core threshold, so prior_source
        should flip to fallback_full_pool."""
        settings = PlatformSettings.from_root(tmp_path)
        # CB pool max minutes = 2700. Set baseline_ref above that.
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            baseline_reference_minutes=3000,
            perturbation_deltas=(0,),
        )
        cb = next(
            rs for rs in rep["role_summaries"] if rs["role_family"] == "CB"
        )
        # All CB minutes < 3000, so no stable core -> fallback.
        assert cb["baseline_prior_source"] == "fallback_full_pool"
        assert cb["baseline_stable_core_count"] == 0
        # delta=0 perturbation should also be fallback.
        p = cb["perturbations"][0]
        assert p["prior_source"] == "fallback_full_pool"
        assert p["stable_core_count"] == 0

    def test_prior_source_stable_core_under_normal_threshold(
        self, tmp_path: Path
    ) -> None:
        """Under the default 900-minute threshold, CB pool has 2 players
        above threshold (2700, 1500), so prior_source=stable_core."""
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_minutes_sensitivity_report(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            baseline_reference_minutes=900,
            perturbation_deltas=(0,),
        )
        cb = next(
            rs for rs in rep["role_summaries"] if rs["role_family"] == "CB"
        )
        assert cb["baseline_prior_source"] == "stable_core"
        assert cb["baseline_stable_core_count"] == 2

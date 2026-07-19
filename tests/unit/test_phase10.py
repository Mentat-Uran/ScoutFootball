"""Tests for Phase 10: validation, calibration, pipeline, API."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scoutfootball.evaluation.calibration import (
    brier_score,
    calibrate_probabilities_isotonic,
)
from scoutfootball.evaluation.validation import (
    ValidationCheckResult,
    ValidationReport,
    validate_no_null_keys,
    validate_parquet_exists,
    validate_row_count,
)


def _data_dir(tmp_path):
    return tmp_path / "data"


def _make_settings(tmp_path):
    from scoutfootball.config import PlatformSettings

    return PlatformSettings.from_root(tmp_path)


class TestValidationReport:
    def test_passed_when_all_pass(self):
        report = ValidationReport(
            checks=[
                ValidationCheckResult("a", True, "ok"),
                ValidationCheckResult("b", True, "ok"),
            ]
        )
        assert report.passed
        assert len(report.failures) == 0

    def test_failed_when_any_fails(self):
        report = ValidationReport(
            checks=[
                ValidationCheckResult("a", True, "ok"),
                ValidationCheckResult("b", False, "bad"),
            ]
        )
        assert not report.passed
        assert len(report.failures) == 1
        assert "FAIL" in report.summary()

    def test_empty_report_passes(self):
        report = ValidationReport()
        assert report.passed


class TestValidateParquetExists:
    def test_missing_file(self, tmp_path):
        result = validate_parquet_exists(
            "nonexistent.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Missing" in result.message

    def test_existing_file(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame({"x": [1, 2]})
        df.to_parquet(gold / "test.parquet")
        result = validate_parquet_exists(
            "gold/feature_store/test.parquet",
            settings=_make_settings(tmp_path),
        )
        assert result.passed


class TestValidateRowCount:
    def test_below_minimum(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame({"x": [1]})
        df.to_parquet(gold / "small.parquet")
        result = validate_row_count(
            "gold/feature_store/small.parquet",
            min_rows=10,
            settings=_make_settings(tmp_path),
        )
        assert not result.passed

    def test_above_minimum(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame({"x": range(20)})
        df.to_parquet(gold / "big.parquet")
        result = validate_row_count(
            "gold/feature_store/big.parquet",
            min_rows=10,
            settings=_make_settings(tmp_path),
        )
        assert result.passed


class TestValidateNoNullKeys:
    def test_with_nulls(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame({"match_id": ["a", None], "player_id": ["p1", "p2"]})
        df.to_parquet(gold / "nulls.parquet")
        result = validate_no_null_keys(
            "gold/feature_store/nulls.parquet",
            ("match_id", "player_id"),
            settings=_make_settings(tmp_path),
        )
        assert not result.passed

    def test_without_nulls(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame({"match_id": ["a", "b"], "player_id": ["p1", "p2"]})
        df.to_parquet(gold / "clean.parquet")
        result = validate_no_null_keys(
            "gold/feature_store/clean.parquet",
            ("match_id", "player_id"),
            settings=_make_settings(tmp_path),
        )
        assert result.passed


class TestCalibration:
    def test_isotonic_improves_or_maintains(self):
        rng = np.random.default_rng(99)
        y_true = rng.binomial(1, 0.3, size=500)
        y_prob = np.clip(y_true * 0.5 + rng.normal(0, 0.2, size=500), 0, 1)
        calibrated, result = calibrate_probabilities_isotonic(y_true, y_prob)
        assert result.method == "isotonic"
        assert result.brier_after <= result.brier_before + 1e-6
        assert len(calibrated) == len(y_prob)

    def test_brier_score_perfect(self):
        y_true = np.array([1.0, 0.0, 1.0])
        y_prob = np.array([1.0, 0.0, 1.0])
        assert brier_score(y_true, y_prob) == pytest.approx(0.0)

    def test_brier_score_worst(self):
        y_true = np.array([1.0, 0.0])
        y_prob = np.array([0.0, 1.0])
        assert brier_score(y_true, y_prob) == pytest.approx(1.0)

    def test_small_sample_returns_uncalibrated(self):
        y_true = np.array([1.0, 0.0])
        y_prob = np.array([0.8, 0.2])
        calibrated, result = calibrate_probabilities_isotonic(y_true, y_prob)
        assert result.improvement == 0.0


class TestPipeline:
    def test_daily_ingest_isolated_from_repository_data(self, tmp_path):
        from scoutfootball.pipeline import run_daily_ingest

        settings = _make_settings(tmp_path)
        results = run_daily_ingest(sources=("statsbomb_open",), settings=settings)

        assert results["statsbomb_open"] == "skipped: no cached StatsBomb match directory"
        assert not settings.raw_root.exists()

    def test_build_features_fails_gracefully_with_empty_local_data_root(self, tmp_path):
        from scoutfootball.pipeline import run_build_features

        settings = _make_settings(tmp_path)
        results = run_build_features(settings=settings)

        assert results["features"].startswith("failed:")
        assert not settings.gold_root.exists()

    def test_weekly_train_skips_on_validation_failure(self, tmp_path):
        from scoutfootball.pipeline import run_weekly_train

        results = run_weekly_train(
            skip_if_validation_fails=True,
            settings=_make_settings(tmp_path),
        )
        assert results.get("status") == "skipped"

    def test_build_team_match_filters_nan_goals_placeholder_rows(self, tmp_path):
        """Football-Data future-match placeholder rows (NaN FTHG/FTAG) must be
        filtered before entering team_match.parquet.

        Regression for the root cause behind the fit_dixon_coles NaN bug: the
        football-data.co.uk results CSVs include scheduled-but-not-yet-played
        matches with NaN FTHG/FTAG/FTR. Without filtering, these rows produce
        NaN goals_for/goals_against in team_match.parquet and silently corrupt
        downstream model training. See WORKFLOW_LOG.md reference workflow 3.
        """
        from scoutfootball.pipeline import _build_team_match_from_football_data

        settings = _make_settings(tmp_path)
        raw_fd_dir = settings.raw_root / "football_data"
        raw_fd_dir.mkdir(parents=True)
        input_path = raw_fd_dir / "combined_results.parquet"

        # Mix of valid rows and one future-match placeholder (NaN FTHG/FTAG/FTR).
        # The placeholder mirrors the real Bastia vs Red Star 2025-12-05 row
        # observed in data/raw/football_data/combined_results.parquet.
        rows = [
            {
                "Div": "E0", "Date": "01/01/2025", "HomeTeam": "Arsenal",
                "AwayTeam": "Chelsea", "FTHG": 2, "FTAG": 1, "FTR": "H",
                "league": "Premier League", "season": "2425",
            },
            {
                "Div": "E0", "Date": "02/01/2025", "HomeTeam": "Liverpool",
                "AwayTeam": "Man City", "FTHG": 1, "FTAG": 1, "FTR": "D",
                "league": "Premier League", "season": "2425",
            },
            # Future-match placeholder: NaN goals across the board.
            {
                "Div": "F2", "Date": "05/12/2025", "HomeTeam": "Bastia",
                "AwayTeam": "Red Star", "FTHG": pd.NA, "FTAG": pd.NA,
                "FTR": pd.NA, "league": "Ligue 2", "season": "2526",
            },
        ]
        pd.DataFrame(rows).to_parquet(input_path, index=False)

        team_match = _build_team_match_from_football_data(settings)

        # 2 valid matches × 2 teams per match = 4 rows; placeholder dropped.
        assert len(team_match) == 4
        assert team_match["goals_for"].notna().all()
        assert team_match["goals_against"].notna().all()
        # Placeholder teams must not appear in the output.
        assert "Bastia" not in set(team_match["team_name"])
        assert "Red Star" not in set(team_match["team_name"])

    def test_build_team_match_all_nan_raises(self, tmp_path):
        """If every Football-Data row has NaN goals, the build must fail loudly
        rather than producing an empty or NaN-filled team_match.parquet."""
        from scoutfootball.pipeline import _build_team_match_from_football_data

        settings = _make_settings(tmp_path)
        raw_fd_dir = settings.raw_root / "football_data"
        raw_fd_dir.mkdir(parents=True)
        input_path = raw_fd_dir / "combined_results.parquet"

        rows = [
            {
                "Div": "E0", "Date": "01/01/2025", "HomeTeam": "Arsenal",
                "AwayTeam": "Chelsea", "FTHG": pd.NA, "FTAG": pd.NA,
                "FTR": pd.NA, "league": "Premier League", "season": "2425",
            },
        ]
        pd.DataFrame(rows).to_parquet(input_path, index=False)

        with pytest.raises(ValueError, match="future-match placeholders"):
            _build_team_match_from_football_data(settings)


class TestAPI:
    def test_health_check(self):
        from scoutfootball.api import health_check

        resp = health_check()
        assert resp.status == "ok"
        assert resp.version == "1.0.3"

    def test_list_players(self):
        from scoutfootball.api import list_players

        resp = list_players()
        assert resp.player_count >= 0
        assert isinstance(resp.players, list)

    def test_list_teams(self):
        from scoutfootball.api import list_teams

        teams = list_teams()
        assert isinstance(teams, list)

    def test_get_match_prediction(self):
        from scoutfootball.api import get_match_prediction

        result = get_match_prediction("Arsenal", "Chelsea")
        if "error" in result:
            # If real data isn't available, verify error response structure
            assert isinstance(result["error"], str)
        else:
            assert "home_win" in result
            assert "away_win" in result
            assert result["home_team"] == "Arsenal"
            assert result["away_team"] == "Chelsea"

    def test_get_value_summary(self):
        from scoutfootball.api import get_value_summary

        result = get_value_summary()
        assert "sample_count" in result

    def test_get_artifacts_summary(self):
        from scoutfootball.api import get_artifacts_summary

        result = get_artifacts_summary()
        assert "player_match_rows" in result
        assert "artifacts" in result
        assert isinstance(result["artifacts"], list)

    def test_artifacts_license_attribution_covers_registered_sources(self):
        """license_attribution must cover all 6 architecture-registered sources."""
        from scoutfootball.api import get_artifacts_summary

        result = get_artifacts_summary()
        attribution = result.get("license_attribution", {})
        # The 6 sources registered in architecture.py planned_components
        required = {"statsbomb", "fbref", "football_data", "understat", "clubelo", "transfermarkt"}
        missing = required - set(attribution.keys())
        assert not missing, f"license_attribution missing registered sources: {missing}"

    def test_get_prediction_summary(self):
        from scoutfootball.api import get_prediction_summary

        result = get_prediction_summary()
        assert "poisson" in result
        assert "dixon_coles" in result
        assert "available_models" in result

    def test_get_model_runs(self):
        from scoutfootball.api import get_model_runs

        result = get_model_runs()
        assert "count" in result
        assert "runs" in result

    def test_get_watchlist(self):
        from scoutfootball.api import get_watchlist

        result = get_watchlist(limit=10)
        assert "count" in result
        assert "players" in result

    def test_get_shortlist(self):
        from scoutfootball.api import get_shortlist

        result = get_shortlist(limit=10)
        assert "count" in result
        assert "players" in result

    def test_get_action_value_summary(self):
        from scoutfootball.api import get_action_value_summary

        result = get_action_value_summary(limit=5)
        assert "status" in result
        assert "players" in result
        if result["status"] == "ok":
            assert len(result["xt_players"]) <= 5
            assert len(result["vaep_players"]) <= 5
            assert result["model_granularity"]["vaep"] == "player_team_career"
            assert result["identity_coverage"]["total_rows"] == result["metrics"]["vaep_rows"]

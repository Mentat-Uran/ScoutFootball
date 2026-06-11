"""Tests for evaluation/backtests.py — Poisson and Dixon-Coles rolling backtests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scoutfootball.evaluation.backtests import (
    DCCalibrationBacktestResult,
    DCDecayComparisonResult,
    DixonColesBacktestResult,
    PoissonBacktestResult,
    run_dc_backtest_with_calibration,
    run_dc_decay_comparison,
    run_dixon_coles_backtest,
    run_poisson_backtest,
)
from scoutfootball.models import TimeSplitConfig


def _make_team_match_df(n_teams: int = 6, n_seasons: int = 3) -> pd.DataFrame:
    """Create synthetic team-match data spanning multiple seasons for backtesting."""
    rng = np.random.default_rng(42)
    teams = [f"team_{i}" for i in range(n_teams)]
    rows = []
    match_id = 0
    for season in range(n_seasons):
        season_year = 2022 + season
        for round_num in range(4):
            for i in range(0, n_teams, 2):
                home, away = teams[i], teams[i + 1]
                hg = rng.poisson(1.5)
                ag = rng.poisson(1.1)
                match_date = f"{season_year}-{1 + round_num:02d}-{15 + i:02d}"
                rows.append({
                    "match_id": str(match_id),
                    "match_date": match_date,
                    "team_id": home,
                    "is_home": True,
                    "goals_for": hg,
                    "goals_against": ag,
                })
                rows.append({
                    "match_id": str(match_id),
                    "match_date": match_date,
                    "team_id": away,
                    "is_home": False,
                    "goals_for": ag,
                    "goals_against": hg,
                })
                match_id += 1
    return pd.DataFrame(rows)


class TestRunPoissonBacktest:
    def test_returns_result(self) -> None:
        df = _make_team_match_df()
        result = run_poisson_backtest(df, TimeSplitConfig(n_splits=3, gap=0))
        assert isinstance(result, PoissonBacktestResult)

    def test_has_predictions(self) -> None:
        df = _make_team_match_df()
        result = run_poisson_backtest(df, TimeSplitConfig(n_splits=3, gap=0))
        assert not result.predictions.empty

    def test_has_fold_metrics(self) -> None:
        df = _make_team_match_df()
        result = run_poisson_backtest(df, TimeSplitConfig(n_splits=3, gap=0))
        assert not result.fold_metrics.empty
        assert "fold" in result.fold_metrics.columns

    def test_has_overall_metrics(self) -> None:
        df = _make_team_match_df()
        result = run_poisson_backtest(df, TimeSplitConfig(n_splits=3, gap=0))
        assert "log_loss_exact" in result.metrics
        assert "brier_1x2" in result.metrics

    def test_prediction_columns(self) -> None:
        df = _make_team_match_df()
        result = run_poisson_backtest(df, TimeSplitConfig(n_splits=3, gap=0))
        required = {"match_id", "home_win_probability", "draw_probability", "away_win_probability"}
        assert required.issubset(set(result.predictions.columns))

    def test_probabilities_valid(self) -> None:
        df = _make_team_match_df()
        result = run_poisson_backtest(df, TimeSplitConfig(n_splits=3, gap=0))
        for _, row in result.predictions.iterrows():
            total = (
                row["home_win_probability"]
                + row["draw_probability"]
                + row["away_win_probability"]
            )
            assert total == pytest.approx(1.0, abs=0.05)

    def test_too_few_splits_raises(self) -> None:
        df = _make_team_match_df()
        with pytest.raises(ValueError, match="more matches"):
            run_poisson_backtest(df, TimeSplitConfig(n_splits=100))


class TestRunDixonColesBacktest:
    def test_returns_result(self) -> None:
        df = _make_team_match_df()
        result = run_dixon_coles_backtest(df, TimeSplitConfig(n_splits=3, gap=0))
        assert isinstance(result, DixonColesBacktestResult)

    def test_has_predictions(self) -> None:
        df = _make_team_match_df()
        result = run_dixon_coles_backtest(df, TimeSplitConfig(n_splits=3, gap=0))
        assert not result.predictions.empty

    def test_has_metrics(self) -> None:
        df = _make_team_match_df()
        result = run_dixon_coles_backtest(df, TimeSplitConfig(n_splits=3, gap=0))
        assert "log_loss_exact" in result.metrics

    def test_with_time_decay(self) -> None:
        df = _make_team_match_df()
        result = run_dixon_coles_backtest(
            df, TimeSplitConfig(n_splits=3, gap=0), half_life_days=180,
        )
        assert not result.predictions.empty

    def test_with_decay_parameter(self) -> None:
        df = _make_team_match_df()
        result = run_dixon_coles_backtest(
            df, TimeSplitConfig(n_splits=3, gap=0), decay=0.005,
        )
        assert not result.predictions.empty
        assert "log_loss_exact" in result.metrics


class TestRunDCDecayComparison:
    def test_returns_comparison_result(self) -> None:
        df = _make_team_match_df()
        result = run_dc_decay_comparison(
            df, TimeSplitConfig(n_splits=3, gap=0), decay=0.005,
        )
        assert isinstance(result, DCDecayComparisonResult)

    def test_comparison_has_metrics(self) -> None:
        df = _make_team_match_df()
        result = run_dc_decay_comparison(
            df, TimeSplitConfig(n_splits=3, gap=0), decay=0.005,
        )
        assert not result.comparison.empty
        assert "metric" in result.comparison.columns
        assert "no_decay" in result.comparison.columns

    def test_decay_value_stored(self) -> None:
        df = _make_team_match_df()
        result = run_dc_decay_comparison(
            df, TimeSplitConfig(n_splits=3, gap=0), decay=0.005,
        )
        assert result.decay_value == 0.005


class TestRunDCBacktestWithCalibration:
    def test_returns_result(self) -> None:
        df = _make_team_match_df()
        result = run_dc_backtest_with_calibration(
            df, TimeSplitConfig(n_splits=3, gap=0),
        )
        assert isinstance(result, DCCalibrationBacktestResult)

    def test_has_calibration_metrics(self) -> None:
        df = _make_team_match_df()
        result = run_dc_backtest_with_calibration(
            df, TimeSplitConfig(n_splits=3, gap=0),
        )
        assert "brier_1x2_before" in result.metrics
        assert "brier_1x2_after" in result.metrics
        assert "rps_before" in result.metrics
        assert "rps_after" in result.metrics

    def test_with_decay(self) -> None:
        df = _make_team_match_df()
        result = run_dc_backtest_with_calibration(
            df, TimeSplitConfig(n_splits=3, gap=0), decay=0.005,
        )
        assert result.metrics["n_matches"] > 0

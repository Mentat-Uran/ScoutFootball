"""Tests for ensemble prediction blending and calibration drift monitoring."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scoutfootball.evaluation.backtests import (
    CalibrationDriftReport,
    compute_calibration_drift,
)
from scoutfootball.models import (
    EnsemblePrediction,
    ensemble_prediction,
    fit_dixon_coles,
    fit_independent_poisson,
    optimize_ensemble_weights,
    predict_match,
    predict_match_dc,
)


def _make_team_match_df(n_teams: int = 6, n_seasons: int = 3) -> pd.DataFrame:
    """Create synthetic team-match data spanning multiple seasons."""
    rng = np.random.default_rng(42)
    teams = [f"team_{i}" for i in range(n_teams)]
    rows = []
    match_id = 0
    for season in range(n_seasons):
        season_year = 2022 + season
        for round_num in range(6):
            for i in range(0, n_teams, 2):
                home, away = teams[i], teams[i + 1]
                hg = int(rng.poisson(1.5))
                ag = int(rng.poisson(1.1))
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


def _make_predictions():
    """Fit Poisson and DC models and return a dict of predictions."""
    df = _make_team_match_df()
    poisson_model = fit_independent_poisson(df)
    dc_model = fit_dixon_coles(df)
    p_pred = predict_match(poisson_model, "team_0", "team_1")
    dc_pred = predict_match_dc(dc_model, "team_0", "team_1")
    return {"poisson": p_pred, "dixon_coles": dc_pred}


# ---------------------------------------------------------------------------
# Ensemble prediction
# ---------------------------------------------------------------------------


class TestEnsemblePrediction:
    def test_returns_result(self) -> None:
        preds = _make_predictions()
        ens = ensemble_prediction(preds)
        assert isinstance(ens, EnsemblePrediction)

    def test_empty_predictions_raises(self) -> None:
        with pytest.raises(ValueError, match="At least one prediction"):
            ensemble_prediction({})

    def test_equal_weights_when_none(self) -> None:
        preds = _make_predictions()
        ens = ensemble_prediction(preds)
        n = len(preds)
        for w in ens.weights.values():
            assert w == pytest.approx(1.0 / n)

    def test_weights_normalized(self) -> None:
        preds = _make_predictions()
        ens = ensemble_prediction(preds, weights={"poisson": 3.0, "dixon_coles": 1.0})
        assert ens.weights["poisson"] == pytest.approx(0.75)
        assert ens.weights["dixon_coles"] == pytest.approx(0.25)

    def test_zero_total_weights_raises(self) -> None:
        preds = _make_predictions()
        with pytest.raises(ValueError, match="positive value"):
            ensemble_prediction(preds, weights={"poisson": 0.0, "dixon_coles": 0.0})

    def test_probabilities_sum_to_one(self) -> None:
        preds = _make_predictions()
        ens = ensemble_prediction(preds)
        total = ens.home_win + ens.draw + ens.away_win
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_score_matrix_sums_to_one(self) -> None:
        preds = _make_predictions()
        ens = ensemble_prediction(preds)
        assert ens.score_matrix.to_numpy().sum() == pytest.approx(1.0, abs=1e-6)

    def test_blended_lambda_is_weighted_average(self) -> None:
        preds = _make_predictions()
        ens = ensemble_prediction(preds, weights={"poisson": 0.5, "dixon_coles": 0.5})
        expected = 0.5 * preds["poisson"].home_lambda + 0.5 * preds["dixon_coles"].home_lambda
        assert ens.home_lambda == pytest.approx(expected, rel=1e-6)

    def test_model_predictions_stored(self) -> None:
        preds = _make_predictions()
        ens = ensemble_prediction(preds)
        assert set(ens.model_predictions.keys()) == set(preds.keys())
        for name, pred in preds.items():
            mp = ens.model_predictions[name]
            assert mp["home_lambda"] == pytest.approx(pred.home_lambda)
            assert mp["home_win"] == pytest.approx(pred.summary.home_win)

    def test_single_model_ensemble_matches_input(self) -> None:
        preds = _make_predictions()
        single = {"poisson": preds["poisson"]}
        ens = ensemble_prediction(single)
        assert ens.home_lambda == pytest.approx(preds["poisson"].home_lambda)
        assert ens.home_win == pytest.approx(preds["poisson"].summary.home_win)

    def test_custom_weights_applied(self) -> None:
        preds = _make_predictions()
        ens = ensemble_prediction(preds, weights={"poisson": 0.8, "dixon_coles": 0.2})
        expected_lambda = (
            0.8 * preds["poisson"].home_lambda
            + 0.2 * preds["dixon_coles"].home_lambda
        )
        assert ens.home_lambda == pytest.approx(expected_lambda, rel=1e-6)

    def test_over_2_5_in_valid_range(self) -> None:
        preds = _make_predictions()
        ens = ensemble_prediction(preds)
        assert 0.0 <= ens.over_2_5 <= 1.0

    def test_btts_yes_in_valid_range(self) -> None:
        preds = _make_predictions()
        ens = ensemble_prediction(preds)
        assert 0.0 <= ens.btts_yes <= 1.0


# ---------------------------------------------------------------------------
# Optimize ensemble weights
# ---------------------------------------------------------------------------


class TestOptimizeEnsembleWeights:
    def test_returns_dict_with_three_keys(self) -> None:
        df = _make_team_match_df()
        weights = optimize_ensemble_weights(df)
        assert set(weights.keys()) == {"poisson", "dixon_coles", "dixon_coles_form"}

    def test_weights_sum_to_one(self) -> None:
        df = _make_team_match_df()
        weights = optimize_ensemble_weights(df)
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)

    def test_weights_non_negative(self) -> None:
        df = _make_team_match_df()
        weights = optimize_ensemble_weights(df)
        for w in weights.values():
            assert w >= -1e-9


# ---------------------------------------------------------------------------
# Calibration drift monitoring
# ---------------------------------------------------------------------------


def _make_predictions_df(n_matches: int = 60, drift: bool = False) -> pd.DataFrame:
    """Create a synthetic predictions DataFrame for drift testing.

    If drift=True, the latest window's predictions are degraded so drift
    should be detected.
    """
    rng = np.random.default_rng(42)
    rows = []
    for i in range(n_matches):
        # Simulate dates spanning ~6 months with 90-day windows
        date = pd.Timestamp("2024-01-01") + pd.Timedelta(days=int(i * 3))
        actual = rng.choice(["home_win", "draw", "away_win"], p=[0.45, 0.25, 0.30])

        # Well-calibrated probabilities for early windows
        if drift and i >= n_matches * 0.7:
            # Degraded probabilities in the latest window (always predict away win)
            home_p, draw_p, away_p = 0.05, 0.05, 0.90
        else:
            home_p, draw_p, away_p = 0.45, 0.25, 0.30

        rows.append({
            "match_id": str(i),
            "match_date": date,
            "home_goals": int(actual == "home_win"),
            "away_goals": int(actual == "away_win"),
            "home_win_probability": home_p,
            "draw_probability": draw_p,
            "away_win_probability": away_p,
            "actual_outcome": actual,
        })
    return pd.DataFrame(rows)


class TestComputeCalibrationDrift:
    def test_returns_report(self) -> None:
        df = _make_predictions_df()
        report = compute_calibration_drift(df)
        assert isinstance(report, CalibrationDriftReport)

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"match_date": [pd.Timestamp("2024-01-01")]})
        with pytest.raises(ValueError, match="missing columns"):
            compute_calibration_drift(df)

    def test_empty_df_returns_empty_windows(self) -> None:
        df = _make_predictions_df(n_matches=0)
        # Need at least the required columns
        df = pd.DataFrame({
            "match_date": pd.Series(dtype="datetime64[ns]"),
            "home_win_probability": pd.Series(dtype=float),
            "draw_probability": pd.Series(dtype=float),
            "away_win_probability": pd.Series(dtype=float),
            "actual_outcome": pd.Series(dtype=object),
        })
        report = compute_calibration_drift(df)
        assert report.windows == []
        assert report.latest_window is None
        assert report.drift_detected is False

    def test_overall_metrics_computed(self) -> None:
        df = _make_predictions_df()
        report = compute_calibration_drift(df)
        assert "rps_1x2" in report.overall_metrics
        assert "brier_1x2" in report.overall_metrics
        assert "log_loss_exact" in report.overall_metrics

    def test_windows_non_empty(self) -> None:
        df = _make_predictions_df()
        report = compute_calibration_drift(df)
        assert len(report.windows) >= 1
        for w in report.windows:
            assert "start_date" in w
            assert "end_date" in w
            assert "n_matches" in w

    def test_latest_window_is_last(self) -> None:
        df = _make_predictions_df()
        report = compute_calibration_drift(df)
        assert report.latest_window is not None
        assert report.latest_window["start_date"] == report.windows[-1]["start_date"]

    def test_no_drift_on_stable_data(self) -> None:
        df = _make_predictions_df(drift=False)
        report = compute_calibration_drift(df, drift_threshold=1.0)
        # With a high threshold (100%), drift should not be detected
        assert report.drift_detected is False

    def test_drift_detected_on_degraded_data(self) -> None:
        df = _make_predictions_df(drift=True)
        report = compute_calibration_drift(df, drift_threshold=0.01)
        # With a very low threshold (1%), drift should be detected
        assert report.drift_detected is True

    def test_custom_drift_metric(self) -> None:
        df = _make_predictions_df()
        report = compute_calibration_drift(df, drift_metric="brier_1x2")
        assert report.drift_metric == "brier_1x2"

    def test_custom_window_size(self) -> None:
        df = _make_predictions_df()
        report_90 = compute_calibration_drift(df, window_size="90D")
        report_30 = compute_calibration_drift(df, window_size="30D")
        # Smaller windows should produce more (or equal) windows
        assert len(report_30.windows) >= len(report_90.windows)

    def test_drift_threshold_stored(self) -> None:
        df = _make_predictions_df()
        report = compute_calibration_drift(df, drift_threshold=0.15)
        assert report.drift_threshold == 0.15

    def test_window_metrics_valid(self) -> None:
        df = _make_predictions_df()
        report = compute_calibration_drift(df)
        for w in report.windows:
            assert w["rps_1x2"] >= 0.0
            assert w["brier_1x2"] >= 0.0
            assert w["log_loss_exact"] >= 0.0

    def test_per_window_match_counts_sum(self) -> None:
        df = _make_predictions_df()
        report = compute_calibration_drift(df)
        total = sum(w["n_matches"] for w in report.windows)
        assert total == len(df)

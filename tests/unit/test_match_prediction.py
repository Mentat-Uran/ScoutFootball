"""Tests for models/match_prediction.py — Independent Poisson and Dixon-Coles models."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scoutfootball.models.match_prediction import (
    CalibrationReport,
    DixonColesModel,
    IndependentPoissonModel,
    MatchProbabilitySummary,
    PoissonPrediction,
    _dc_tau_scalar,
    calibrate_predictions,
    fit_dixon_coles,
    fit_independent_poisson,
    predict_match,
    predict_match_dc,
)


def _make_team_match_df(n_teams: int = 6, n_rounds: int = 4) -> pd.DataFrame:
    """Create a synthetic team-match DataFrame for testing."""
    rng = np.random.default_rng(42)
    teams = [f"team_{i}" for i in range(n_teams)]
    rows = []
    match_id = 0
    for _r in range(n_rounds):
        for i in range(0, n_teams, 2):
            home, away = teams[i], teams[i + 1]
            hg = rng.poisson(1.5)
            ag = rng.poisson(1.1)
            rows.append({"match_id": str(match_id), "team_id": home, "is_home": True,
                         "goals_for": hg, "goals_against": ag})
            rows.append({"match_id": str(match_id), "team_id": away, "is_home": False,
                         "goals_for": ag, "goals_against": hg})
            match_id += 1
    return pd.DataFrame(rows)


class TestFitIndependentPoisson:
    def test_returns_model(self) -> None:
        df = _make_team_match_df()
        model = fit_independent_poisson(df)
        assert isinstance(model, IndependentPoissonModel)

    def test_model_has_all_teams(self) -> None:
        df = _make_team_match_df(n_teams=6)
        model = fit_independent_poisson(df)
        # Home attack only has home teams (3), away attack only has away teams (3)
        assert len(model.home_attack_strength) == 3
        assert len(model.away_attack_strength) == 3
        # Defense lookups have the opposing teams
        assert len(model.home_defense_strength) == 3
        assert len(model.away_defense_strength) == 3
        # All 6 unique team_ids should appear across both home and away
        all_teams = set(model.home_attack_strength) | set(model.away_attack_strength)
        assert len(all_teams) == 6

    def test_league_rates_positive(self) -> None:
        df = _make_team_match_df()
        model = fit_independent_poisson(df)
        assert model.league_home_rate > 0
        assert model.league_away_rate > 0

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"team_id": ["A"], "is_home": [True]})
        with pytest.raises(ValueError, match="missing required columns"):
            fit_independent_poisson(df)

    def test_no_away_rows_raises(self) -> None:
        df = pd.DataFrame({
            "team_id": ["A"], "is_home": [True],
            "goals_for": [2], "goals_against": [1],
        })
        with pytest.raises(ValueError, match="both home and away"):
            fit_independent_poisson(df)


class TestPredictMatch:
    def test_returns_prediction(self) -> None:
        df = _make_team_match_df()
        model = fit_independent_poisson(df)
        pred = predict_match(model, "team_0", "team_1")
        assert isinstance(pred, PoissonPrediction)

    def test_score_matrix_shape(self) -> None:
        df = _make_team_match_df()
        model = fit_independent_poisson(df)
        pred = predict_match(model, "team_0", "team_1", max_goals=5)
        assert pred.score_matrix.shape == (6, 6)

    def test_probabilities_sum_to_one(self) -> None:
        df = _make_team_match_df()
        model = fit_independent_poisson(df)
        pred = predict_match(model, "team_0", "team_1")
        total = pred.score_matrix.values.sum()
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_summary_probabilities(self) -> None:
        df = _make_team_match_df()
        model = fit_independent_poisson(df)
        pred = predict_match(model, "team_0", "team_1")
        s = pred.summary
        assert isinstance(s, MatchProbabilitySummary)
        assert s.home_win + s.draw + s.away_win == pytest.approx(1.0, abs=1e-6)
        assert s.over_2_5 + s.under_2_5 == pytest.approx(1.0, abs=1e-6)
        assert s.btts_yes + s.btts_no == pytest.approx(1.0, abs=1e-6)

    def test_max_goals_must_be_positive(self) -> None:
        df = _make_team_match_df()
        model = fit_independent_poisson(df)
        with pytest.raises(ValueError, match="max_goals must be positive"):
            predict_match(model, "team_0", "team_1", max_goals=0)

    def test_unknown_team_uses_baseline(self) -> None:
        df = _make_team_match_df()
        model = fit_independent_poisson(df)
        pred = predict_match(model, "unknown_team", "team_0")
        assert pred.home_lambda > 0


class TestFitDixonColes:
    def test_returns_model(self) -> None:
        df = _make_team_match_df(n_teams=6, n_rounds=4)
        model = fit_dixon_coles(df)
        assert isinstance(model, DixonColesModel)

    def test_rho_in_range(self) -> None:
        df = _make_team_match_df(n_teams=6, n_rounds=4)
        model = fit_dixon_coles(df)
        assert -1.0 <= model.rho <= 0.0

    def test_home_advantage_positive(self) -> None:
        df = _make_team_match_df(n_teams=6, n_rounds=4)
        model = fit_dixon_coles(df)
        assert model.home_advantage > 0

    def test_num_matches_correct(self) -> None:
        df = _make_team_match_df(n_teams=6, n_rounds=4)
        model = fit_dixon_coles(df)
        expected_matches = 6 * 4 // 2  # n_teams/2 * n_rounds
        assert model.num_matches == expected_matches

    def test_team_params_normalized(self) -> None:
        df = _make_team_match_df(n_teams=6, n_rounds=4)
        model = fit_dixon_coles(df)
        attacks = list(model.team_attack.values())
        assert np.mean(attacks) == pytest.approx(0.0, abs=1e-6)

    def test_time_decay(self) -> None:
        df = _make_team_match_df(n_teams=6, n_rounds=4)
        df["match_date"] = "2025-01-01"
        model = fit_dixon_coles(df, half_life_days=180)
        assert model.half_life_days == 180

    def test_decay_parameter(self) -> None:
        df = _make_team_match_df(n_teams=6, n_rounds=4)
        df["match_date"] = "2025-01-01"
        model = fit_dixon_coles(df, decay=0.005)
        assert model.decay is not None
        assert model.decay == pytest.approx(0.005)

    def test_decay_precedence_over_half_life(self) -> None:
        df = _make_team_match_df(n_teams=6, n_rounds=4)
        df["match_date"] = "2025-01-01"
        model = fit_dixon_coles(df, half_life_days=180, decay=0.005)
        # When both are set, decay takes precedence; half_life_days should be None
        assert model.decay is not None
        assert model.half_life_days is None

    def test_decay_affects_parameters(self) -> None:
        """Time decay should produce different parameters than no decay."""
        rng = np.random.default_rng(42)
        teams = [f"team_{i}" for i in range(6)]
        rows = []
        match_id = 0
        for season in range(3):
            season_year = 2022 + season
            for round_num in range(4):
                for i in range(0, 6, 2):
                    home, away = teams[i], teams[i + 1]
                    hg = rng.poisson(1.5)
                    ag = rng.poisson(1.1)
                    match_date = f"{season_year}-{1 + round_num:02d}-{15 + i:02d}"
                    rows.append({"match_id": str(match_id), "match_date": match_date,
                                 "team_id": home, "is_home": True,
                                 "goals_for": hg, "goals_against": ag})
                    rows.append({"match_id": str(match_id), "match_date": match_date,
                                 "team_id": away, "is_home": False,
                                 "goals_for": ag, "goals_against": hg})
                    match_id += 1
        df = pd.DataFrame(rows)
        model_no_decay = fit_dixon_coles(df)
        model_with_decay = fit_dixon_coles(df, decay=0.01)
        # Parameters should differ
        assert model_no_decay.team_attack != model_with_decay.team_attack

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"team_id": ["A"], "is_home": [True]})
        with pytest.raises(ValueError, match="missing required columns"):
            fit_dixon_coles(df)


class TestPredictMatchDC:
    def test_returns_prediction(self) -> None:
        df = _make_team_match_df(n_teams=6, n_rounds=4)
        model = fit_dixon_coles(df)
        pred = predict_match_dc(model, "team_0", "team_1")
        assert isinstance(pred, PoissonPrediction)

    def test_probabilities_sum_to_one(self) -> None:
        df = _make_team_match_df(n_teams=6, n_rounds=4)
        model = fit_dixon_coles(df)
        pred = predict_match_dc(model, "team_0", "team_1")
        total = pred.score_matrix.values.sum()
        assert total == pytest.approx(1.0, abs=1e-4)

    def test_summary_valid(self) -> None:
        df = _make_team_match_df(n_teams=6, n_rounds=4)
        model = fit_dixon_coles(df)
        pred = predict_match_dc(model, "team_0", "team_1")
        s = pred.summary
        assert s.home_win + s.draw + s.away_win == pytest.approx(1.0, abs=1e-4)

    def test_dc_differs_from_poisson(self) -> None:
        df = _make_team_match_df(n_teams=6, n_rounds=4)
        poisson_model = fit_independent_poisson(df)
        dc_model = fit_dixon_coles(df)
        p_poisson = predict_match(poisson_model, "team_0", "team_1")
        p_dc = predict_match_dc(dc_model, "team_0", "team_1")
        # DC tau correction should make low scores differ
        assert not np.allclose(
            p_poisson.score_matrix.values[:2, :2],
            p_dc.score_matrix.values[:2, :2],
            atol=1e-6,
        )

    def test_unknown_team_uses_zero(self) -> None:
        df = _make_team_match_df(n_teams=6, n_rounds=4)
        model = fit_dixon_coles(df)
        pred = predict_match_dc(model, "unknown", "team_0")
        assert pred.home_lambda > 0


class TestDCTauScalar:
    def test_00_correction(self) -> None:
        # tau(0,0) = 1 - lam_h * lam_a * rho
        rho = -0.13
        lam_h, lam_a = 1.5, 1.2
        tau = _dc_tau_scalar(0, 0, lam_h, lam_a, rho)
        expected = 1.0 - lam_h * lam_a * rho
        assert tau == pytest.approx(expected)

    def test_10_correction(self) -> None:
        rho = -0.13
        lam_h, lam_a = 1.5, 1.2
        tau = _dc_tau_scalar(1, 0, lam_h, lam_a, rho)
        expected = 1.0 + lam_h * rho
        assert tau == pytest.approx(expected)

    def test_01_correction(self) -> None:
        rho = -0.13
        lam_h, lam_a = 1.5, 1.2
        tau = _dc_tau_scalar(0, 1, lam_h, lam_a, rho)
        expected = 1.0 + lam_a * rho
        assert tau == pytest.approx(expected)

    def test_11_correction(self) -> None:
        rho = -0.13
        tau = _dc_tau_scalar(1, 1, 1.5, 1.2, rho)
        expected = 1.0 - rho
        assert tau == pytest.approx(expected)

    def test_high_scores_no_correction(self) -> None:
        assert _dc_tau_scalar(2, 0, 1.5, 1.2, -0.13) == 1.0
        assert _dc_tau_scalar(0, 2, 1.5, 1.2, -0.13) == 1.0
        assert _dc_tau_scalar(2, 2, 1.5, 1.2, -0.13) == 1.0
        assert _dc_tau_scalar(3, 1, 1.5, 1.2, -0.13) == 1.0

    def test_tau_never_zero(self) -> None:
        # Even with extreme rho, tau should be clamped to > 0
        tau = _dc_tau_scalar(0, 0, 5.0, 5.0, -0.99)
        assert tau > 0


class TestCalibratePredictions:
    def _make_predictions_df(self, n: int = 200) -> pd.DataFrame:
        """Create synthetic predictions DataFrame for calibration testing."""
        rng = np.random.default_rng(42)
        home_win_prob = rng.uniform(0.1, 0.8, n)
        draw_prob = rng.uniform(0.1, 0.4, n)
        away_win_prob = 1.0 - home_win_prob - draw_prob
        # Clip to ensure valid probabilities
        away_win_prob = np.clip(away_win_prob, 0.05, 0.9)
        total = home_win_prob + draw_prob + away_win_prob
        home_win_prob /= total
        draw_prob /= total
        away_win_prob /= total

        outcomes = rng.choice(["home_win", "draw", "away_win"], n, p=[0.45, 0.28, 0.27])
        return pd.DataFrame({
            "home_win_probability": home_win_prob,
            "draw_probability": draw_prob,
            "away_win_probability": away_win_prob,
            "actual_outcome": outcomes,
        })

    def test_returns_calibration_report(self) -> None:
        df = self._make_predictions_df()
        report = calibrate_predictions(df)
        assert isinstance(report, CalibrationReport)

    def test_isotonic_method(self) -> None:
        df = self._make_predictions_df()
        report = calibrate_predictions(df, method="isotonic")
        assert report.method == "isotonic"
        assert report.n_matches == len(df)

    def test_platt_method(self) -> None:
        df = self._make_predictions_df()
        report = calibrate_predictions(df, method="platt")
        assert report.method == "platt"
        assert report.n_matches == len(df)

    def test_brier_after_not_worse(self) -> None:
        df = self._make_predictions_df()
        report = calibrate_predictions(df, method="isotonic")
        # Isotonic calibration should not make Brier score significantly worse
        assert report.brier_after <= report.brier_before + 1e-6

    def test_rps_after_not_worse(self) -> None:
        df = self._make_predictions_df()
        report = calibrate_predictions(df, method="isotonic")
        assert report.rps_after <= report.rps_before + 1e-6

    def test_calibrated_predictions_df(self) -> None:
        df = self._make_predictions_df()
        report = calibrate_predictions(df)
        assert report.calibrated_predictions is not None
        cal_df = report.calibrated_predictions
        assert "home_win_probability_calibrated" in cal_df.columns
        assert "draw_probability_calibrated" in cal_df.columns
        assert "away_win_probability_calibrated" in cal_df.columns

    def test_calibrated_probabilities_sum_to_one(self) -> None:
        df = self._make_predictions_df()
        report = calibrate_predictions(df)
        cal_df = report.calibrated_predictions
        total = (
            cal_df["home_win_probability_calibrated"]
            + cal_df["draw_probability_calibrated"]
            + cal_df["away_win_probability_calibrated"]
        )
        np.testing.assert_allclose(total, 1.0, atol=1e-6)

    def test_invalid_method_raises(self) -> None:
        df = self._make_predictions_df()
        with pytest.raises(ValueError, match="Unknown calibration method"):
            calibrate_predictions(df, method="invalid")

"""Tests for bootstrap confidence intervals and form-based match weighting."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scoutfootball.models import (
    PredictionConfidenceInterval,
    bootstrap_prediction_confidence,
    compute_form_weights,
    fit_dixon_coles,
    fit_dixon_coles_with_form,
    predict_match_dc,
)
from scoutfootball.models.match_prediction import _build_bootstrap_fixtures


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


# ---------------------------------------------------------------------------
# Bootstrap confidence intervals
# ---------------------------------------------------------------------------


class TestBootstrapPredictionConfidence:
    def test_returns_result(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_prediction_confidence(
            df, "team_0", "team_1", n_bootstrap=15, confidence_level=0.90,
        )
        assert isinstance(ci, PredictionConfidenceInterval)

    def test_n_bootstrap_recorded(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_prediction_confidence(
            df, "team_0", "team_1", n_bootstrap=15,
        )
        assert ci.n_bootstrap == 15

    def test_intervals_are_valid_ranges(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_prediction_confidence(
            df, "team_0", "team_1", n_bootstrap=15,
        )
        assert ci.home_win_low <= ci.home_win_high
        assert ci.draw_low <= ci.draw_high
        assert ci.away_win_low <= ci.away_win_high
        assert ci.home_lambda_low <= ci.home_lambda_high
        assert ci.away_lambda_low <= ci.away_lambda_high

    def test_probabilities_in_zero_one(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_prediction_confidence(
            df, "team_0", "team_1", n_bootstrap=15,
        )
        assert 0.0 <= ci.home_win_low <= 1.0
        assert 0.0 <= ci.home_win_high <= 1.0
        assert 0.0 <= ci.draw_low <= 1.0
        assert 0.0 <= ci.draw_high <= 1.0
        assert 0.0 <= ci.away_win_low <= 1.0
        assert 0.0 <= ci.away_win_high <= 1.0

    def test_lambdas_positive(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_prediction_confidence(
            df, "team_0", "team_1", n_bootstrap=15,
        )
        assert ci.home_lambda_low > 0
        assert ci.away_lambda_low > 0

    def test_too_few_bootstrap_raises(self) -> None:
        df = _make_team_match_df()
        with pytest.raises(ValueError, match="at least 10"):
            bootstrap_prediction_confidence(df, "team_0", "team_1", n_bootstrap=5)

    def test_invalid_confidence_level_raises(self) -> None:
        df = _make_team_match_df()
        with pytest.raises(ValueError, match="confidence_level"):
            bootstrap_prediction_confidence(
                df, "team_0", "team_1", n_bootstrap=15, confidence_level=1.5,
            )

    def test_too_few_fixtures_raises(self) -> None:
        df = _make_team_match_df(n_teams=2, n_seasons=1)
        # Only 6 fixtures — below the 20 minimum
        with pytest.raises(ValueError, match="at least 20 fixtures"):
            bootstrap_prediction_confidence(
                df, "team_0", "team_1", n_bootstrap=15,
            )

    def test_with_decay(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_prediction_confidence(
            df, "team_0", "team_1", n_bootstrap=15, decay=0.005,
        )
        assert ci.n_bootstrap == 15

    def test_failed_iterations_non_negative(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_prediction_confidence(
            df, "team_0", "team_1", n_bootstrap=15,
        )
        assert ci.failed_iterations >= 0

    def test_reproducible_with_same_seed(self) -> None:
        df = _make_team_match_df()
        ci1 = bootstrap_prediction_confidence(
            df, "team_0", "team_1", n_bootstrap=15, random_seed=123,
        )
        ci2 = bootstrap_prediction_confidence(
            df, "team_0", "team_1", n_bootstrap=15, random_seed=123,
        )
        assert ci1.home_win_low == pytest.approx(ci2.home_win_low)
        assert ci1.away_win_high == pytest.approx(ci2.away_win_high)

    def test_different_seed_gives_different_result(self) -> None:
        df = _make_team_match_df()
        ci1 = bootstrap_prediction_confidence(
            df, "team_0", "team_1", n_bootstrap=15, random_seed=1,
        )
        ci2 = bootstrap_prediction_confidence(
            df, "team_0", "team_1", n_bootstrap=15, random_seed=999,
        )
        # Very unlikely they're exactly the same
        assert ci1.home_win_low != ci2.home_win_low or ci1.home_win_high != ci2.home_win_high


# ---------------------------------------------------------------------------
# _build_bootstrap_fixtures helper
# ---------------------------------------------------------------------------


class TestBuildBootstrapFixtures:
    def test_returns_fixture_level_rows(self) -> None:
        df = _make_team_match_df()
        fixtures = _build_bootstrap_fixtures(df)
        # Should have half as many rows as team_match_df (2 rows per fixture)
        assert len(fixtures) == len(df) // 2

    def test_has_expected_columns(self) -> None:
        df = _make_team_match_df()
        fixtures = _build_bootstrap_fixtures(df)
        assert "home_team" in fixtures.columns
        assert "away_team" in fixtures.columns
        assert "home_goals" in fixtures.columns
        assert "away_goals" in fixtures.columns
        assert "match_id" in fixtures.columns


# ---------------------------------------------------------------------------
# Form-based match weighting
# ---------------------------------------------------------------------------


class TestComputeFormWeights:
    def test_returns_weights_for_all_fixtures(self) -> None:
        df = _make_team_match_df()
        weights = compute_form_weights(df)
        fixtures = _build_bootstrap_fixtures(df)
        assert len(weights) == len(fixtures)

    def test_zero_form_factor_returns_ones(self) -> None:
        df = _make_team_match_df()
        weights = compute_form_weights(df, form_factor=0.0)
        assert np.allclose(weights, 1.0)

    def test_weights_normalized_to_mean_one(self) -> None:
        df = _make_team_match_df()
        weights = compute_form_weights(df, form_factor=0.3)
        assert np.mean(weights) == pytest.approx(1.0, abs=0.01)

    def test_weights_positive(self) -> None:
        df = _make_team_match_df()
        weights = compute_form_weights(df, form_factor=0.5)
        assert np.all(weights > 0)

    def test_different_lookback_changes_weights(self) -> None:
        df = _make_team_match_df()
        w5 = compute_form_weights(df, lookback=5, form_factor=0.5)
        w1 = compute_form_weights(df, lookback=1, form_factor=0.5)
        # Different lookback should produce different weights
        assert not np.allclose(w5, w1)


# ---------------------------------------------------------------------------
# fit_dixon_coles_with_form
# ---------------------------------------------------------------------------


class TestFitDixonColesWithForm:
    def test_returns_model(self) -> None:
        df = _make_team_match_df()
        model = fit_dixon_coles_with_form(df)
        assert model is not None
        assert hasattr(model, "team_attack")
        assert hasattr(model, "team_defense")

    def test_with_decay(self) -> None:
        df = _make_team_match_df()
        model = fit_dixon_coles_with_form(df, decay=0.005)
        assert model.decay == 0.005

    def test_can_predict(self) -> None:
        df = _make_team_match_df()
        model = fit_dixon_coles_with_form(df)
        pred = predict_match_dc(model, "team_0", "team_1")
        assert pred.home_lambda > 0
        assert pred.away_lambda > 0
        assert 0 <= pred.summary.home_win <= 1

    def test_form_factor_zero_matches_plain_dc(self) -> None:
        df = _make_team_match_df()
        model_form0 = fit_dixon_coles_with_form(df, form_factor=0.0)
        model_plain = fit_dixon_coles(df)
        # With form_factor=0, weights are all 1.0, so should match plain DC
        assert model_form0.rho == pytest.approx(model_plain.rho, abs=0.01)

    def test_match_weights_length_mismatch_raises(self) -> None:
        df = _make_team_match_df()
        with pytest.raises(ValueError, match="match_weights length"):
            fit_dixon_coles(df, match_weights=np.array([1.0, 2.0]))

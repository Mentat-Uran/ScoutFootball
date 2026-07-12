"""Tests for prediction explanation features.

Covers:
- Per-league calibration breakdown (compute_calibration_comparison)
- Permutation-based prediction attribution (compute_prediction_attribution)
- Ensemble CI cache key isolation by model_type
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scoutfootball.evaluation.backtests import (
    CalibrationComparison,
    compute_calibration_comparison,
)
from scoutfootball.models import (
    PredictionAttribution,
    compute_prediction_attribution,
    fit_dixon_coles,
    fit_isotonic_calibrator,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


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


def _make_predictions_df(n: int = 200, *, with_league: bool = False) -> pd.DataFrame:
    """Create synthetic predictions DataFrame for calibration testing."""
    rng = np.random.default_rng(42)
    home_win_prob = rng.uniform(0.1, 0.8, n)
    draw_prob = rng.uniform(0.1, 0.4, n)
    away_win_prob = 1.0 - home_win_prob - draw_prob
    away_win_prob = np.clip(away_win_prob, 0.05, 0.9)
    total = home_win_prob + draw_prob + away_win_prob
    home_win_prob /= total
    draw_prob /= total
    away_win_prob /= total

    outcomes = rng.choice(["home_win", "draw", "away_win"], n, p=[0.45, 0.28, 0.27])
    home_goals = rng.poisson(1.5, n)
    away_goals = rng.poisson(1.1, n)
    df = pd.DataFrame({
        "home_win_probability": home_win_prob,
        "draw_probability": draw_prob,
        "away_win_probability": away_win_prob,
        "actual_outcome": outcomes,
        "home_goals": home_goals,
        "away_goals": away_goals,
    })
    if with_league:
        # Two leagues with enough samples each to pass min_per_league=20
        df["league"] = np.where(np.arange(n) < n // 2, "Premier", "La Liga")
    return df


# ---------------------------------------------------------------------------
# Per-league calibration breakdown
# ---------------------------------------------------------------------------


class TestPerLeagueCalibrationBreakdown:
    def test_no_league_column_returns_empty_by_league(self) -> None:
        df = _make_predictions_df(n=200, with_league=False)
        calibrator = fit_isotonic_calibrator(df)
        result = compute_calibration_comparison(df, calibrator)
        assert isinstance(result, CalibrationComparison)
        assert result.by_league == [] or result.by_league == ()

    def test_with_league_returns_by_league_entries(self) -> None:
        df = _make_predictions_df(n=200, with_league=True)
        calibrator = fit_isotonic_calibrator(df)
        result = compute_calibration_comparison(df, calibrator, min_per_league=20)
        assert isinstance(result.by_league, list)
        assert len(result.by_league) == 2
        leagues = {e["league"] for e in result.by_league}
        assert leagues == {"Premier", "La Liga"}

    def test_by_league_entries_have_required_fields(self) -> None:
        df = _make_predictions_df(n=200, with_league=True)
        calibrator = fit_isotonic_calibrator(df)
        result = compute_calibration_comparison(df, calibrator, min_per_league=20)
        for entry in result.by_league:
            assert "league" in entry
            assert "n_matches" in entry
            assert "brier_raw" in entry
            assert "brier_recalibrated" in entry
            assert "rps_raw" in entry
            assert "rps_recalibrated" in entry
            assert "brier_improvement_pct" in entry
            assert "rps_improvement_pct" in entry

    def test_by_league_sorted_by_n_matches_desc(self) -> None:
        df = _make_predictions_df(n=200, with_league=True)
        # Make one league bigger than the other
        df.loc[df.index[:50], "league"] = "Premier"
        df.loc[df.index[50:], "league"] = "La Liga"
        calibrator = fit_isotonic_calibrator(df)
        result = compute_calibration_comparison(df, calibrator, min_per_league=20)
        n_matches = [e["n_matches"] for e in result.by_league]
        assert n_matches == sorted(n_matches, reverse=True)

    def test_min_per_league_filters_small_leagues(self) -> None:
        df = _make_predictions_df(n=200, with_league=True)
        # Add a tiny third league
        small_league_mask = df.index[:10]
        df.loc[small_league_mask, "league"] = "Tiny League"
        calibrator = fit_isotonic_calibrator(df)
        result = compute_calibration_comparison(df, calibrator, min_per_league=20)
        league_names = {e["league"] for e in result.by_league}
        assert "Tiny League" not in league_names
        assert "Premier" in league_names
        assert "La Liga" in league_names

    def test_overall_metrics_unchanged_by_league_presence(self) -> None:
        df = _make_predictions_df(n=200, with_league=True)
        calibrator = fit_isotonic_calibrator(df)
        result_with = compute_calibration_comparison(df, calibrator, min_per_league=20)
        df_no_league = df.drop(columns=["league"])
        result_without = compute_calibration_comparison(df_no_league, calibrator)
        assert result_with.overall == pytest.approx(result_without.overall)
        assert result_with.n_matches == result_without.n_matches


# ---------------------------------------------------------------------------
# Prediction attribution
# ---------------------------------------------------------------------------


class TestPredictionAttribution:
    def test_returns_attribution(self) -> None:
        df = _make_team_match_df()
        model = fit_dixon_coles(df)
        attribution = compute_prediction_attribution(model, "team_0", "team_1")
        assert isinstance(attribution, PredictionAttribution)

    def test_home_and_away_teams(self) -> None:
        df = _make_team_match_df()
        model = fit_dixon_coles(df)
        attribution = compute_prediction_attribution(model, "team_0", "team_1")
        assert attribution.home_team == "team_0"
        assert attribution.away_team == "team_1"

    def test_baseline_probabilities_sum_to_one(self) -> None:
        df = _make_team_match_df()
        model = fit_dixon_coles(df)
        attribution = compute_prediction_attribution(model, "team_0", "team_1")
        total = (
            attribution.baseline_home_win
            + attribution.baseline_draw
            + attribution.baseline_away_win
        )
        assert total == pytest.approx(1.0, abs=1e-4)

    def test_seven_factors(self) -> None:
        df = _make_team_match_df()
        model = fit_dixon_coles(df)
        attribution = compute_prediction_attribution(model, "team_0", "team_1")
        assert len(attribution.factors) == 7
        factor_keys = {f["factor"] for f in attribution.factors}
        expected = {
            "home_attack", "home_defense",
            "away_attack", "away_defense",
            "home_advantage", "league_mean_goals", "rho_correction",
        }
        assert factor_keys == expected

    def test_factors_sorted_by_abs_delta_desc(self) -> None:
        df = _make_team_match_df()
        model = fit_dixon_coles(df)
        attribution = compute_prediction_attribution(model, "team_0", "team_1")
        abs_deltas = [f["abs_delta"] for f in attribution.factors]
        assert abs_deltas == sorted(abs_deltas, reverse=True)

    def test_factor_fields(self) -> None:
        df = _make_team_match_df()
        model = fit_dixon_coles(df)
        attribution = compute_prediction_attribution(model, "team_0", "team_1")
        for f in attribution.factors:
            assert "factor" in f
            assert "label" in f
            assert "baseline_home_win" in f
            assert "neutralized_home_win" in f
            assert "delta" in f
            assert "abs_delta" in f

    def test_delta_equals_baseline_minus_neutralized(self) -> None:
        df = _make_team_match_df()
        model = fit_dixon_coles(df)
        attribution = compute_prediction_attribution(model, "team_0", "team_1")
        for f in attribution.factors:
            expected_delta = f["baseline_home_win"] - f["neutralized_home_win"]
            assert f["delta"] == pytest.approx(expected_delta, abs=1e-6)

    def test_home_advantage_neutral_decreases_home_win(self) -> None:
        """Neutralizing home advantage should not increase home_win
        (typically decreases it, but at minimum the delta should be >= 0
        meaning removing home advantage doesn't help home team)."""
        df = _make_team_match_df()
        model = fit_dixon_coles(df)
        attribution = compute_prediction_attribution(model, "team_0", "team_1")
        ha_factor = next(f for f in attribution.factors if f["factor"] == "home_advantage")
        # delta = baseline - neutralized; if home advantage helps home team,
        # removing it should lower neutralized_home_win, making delta positive
        assert ha_factor["delta"] >= -1e-6

    def test_unknown_teams_do_not_crash(self) -> None:
        df = _make_team_match_df()
        model = fit_dixon_coles(df)
        # Unknown teams default to 0.0 strength; should not raise
        attribution = compute_prediction_attribution(model, "unknown_home", "unknown_away")
        assert len(attribution.factors) == 7


# ---------------------------------------------------------------------------
# Ensemble CI cache key isolation (model_type-aware)
# ---------------------------------------------------------------------------


class TestCICacheKeyIsolation:
    """Verify that _get_prediction_confidence uses model_type in cache key
    so that different models don't overwrite each other's cached CIs."""

    def test_cache_key_includes_model_type(self, monkeypatch) -> None:
        """Directly inspect the cache after populating with different model_types."""
        from scoutfootball import api as api_module

        df = _make_team_match_df()
        monkeypatch.setattr(api_module, "load_team_match", lambda: df)
        monkeypatch.setattr(api_module, "_resolve_tuned_decay", lambda: 0.005)

        api_module._PREDICTION_CI_CACHE.clear()

        # Populate cache for dixon_coles
        api_module._get_prediction_confidence("team_0", "team_1", model_type="dixon_coles")
        # Populate cache for ensemble
        api_module._get_prediction_confidence("team_0", "team_1", model_type="ensemble")

        # Both cache keys should exist
        key_dc = "team_0__team_1__dixon_coles"
        key_ens = "team_0__team_1__ensemble"
        assert key_dc in api_module._PREDICTION_CI_CACHE
        assert key_ens in api_module._PREDICTION_CI_CACHE
        assert key_dc != key_ens

    def test_cached_result_marked_cached(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_team_match_df()
        monkeypatch.setattr(api_module, "load_team_match", lambda: df)
        monkeypatch.setattr(api_module, "_resolve_tuned_decay", lambda: 0.005)

        api_module._PREDICTION_CI_CACHE.clear()

        # First call: not cached
        result1 = api_module._get_prediction_confidence(
            "team_2", "team_3", model_type="dixon_coles",
        )
        assert result1 is not None
        assert result1.get("cached") is False

        # Second call: should be cached
        result2 = api_module._get_prediction_confidence(
            "team_2", "team_3", model_type="dixon_coles",
        )
        assert result2 is not None
        assert result2.get("cached") is True

    def test_different_model_types_independent(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_team_match_df()
        monkeypatch.setattr(api_module, "load_team_match", lambda: df)
        monkeypatch.setattr(api_module, "_resolve_tuned_decay", lambda: 0.005)

        api_module._PREDICTION_CI_CACHE.clear()

        result_dc = api_module._get_prediction_confidence(
            "team_4", "team_5", model_type="dixon_coles",
        )
        result_ens = api_module._get_prediction_confidence(
            "team_4", "team_5", model_type="ensemble",
        )

        # Both should succeed and be independent (not cached)
        assert result_dc is not None
        assert result_ens is not None
        assert result_dc.get("cached") is False
        assert result_ens.get("cached") is False

        # Subsequent calls should each hit their own cache
        result_dc2 = api_module._get_prediction_confidence(
            "team_4", "team_5", model_type="dixon_coles",
        )
        result_ens2 = api_module._get_prediction_confidence(
            "team_4", "team_5", model_type="ensemble",
        )
        assert result_dc2 is not None
        assert result_ens2 is not None
        assert result_dc2.get("cached") is True
        assert result_ens2.get("cached") is True

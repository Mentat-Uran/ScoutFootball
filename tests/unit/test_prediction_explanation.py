"""Tests for prediction explanation features.

Covers:
- Per-league calibration breakdown (compute_calibration_comparison)
- Permutation-based prediction attribution (compute_prediction_attribution)
- Ensemble CI cache key isolation by model_type
- Bootstrap attribution confidence intervals
- Ensemble attribution (per-model + blended)
- Prediction diagnostics aggregation endpoint
- Ensemble attribution bootstrap CI
- Calibration drift timeline endpoint
- Value betting analysis (compute_value_bets)
- Reliability diagram (compute_reliability_diagram)
- Per-team prediction accuracy (compute_team_accuracy)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scoutfootball.evaluation.backtests import (
    CalibrationComparison,
    compute_calibration_comparison,
    compute_confidence_distribution,
    compute_error_analysis,
    compute_h2h_bias_correction,
    compute_model_comparison,
    compute_outcome_distribution,
    compute_prediction_staleness,
    compute_probability_heatmap,
    compute_reliability_diagram,
    compute_scoreline_calibration,
    compute_team_accuracy,
    compute_temporal_validation,
    compute_value_bets,
)
from scoutfootball.models import (
    AttributionConfidenceInterval,
    EnsembleAttribution,
    PredictionAttribution,
    bootstrap_attribution_confidence,
    bootstrap_ensemble_attribution_confidence,
    compute_ensemble_attribution,
    compute_prediction_attribution,
    fit_dixon_coles,
    fit_dixon_coles_with_form,
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


# ---------------------------------------------------------------------------
# Bootstrap attribution confidence intervals
# ---------------------------------------------------------------------------


class TestBootstrapAttributionConfidence:
    """Tests for bootstrap_attribution_confidence producing CIs on factor deltas."""

    def test_returns_attribution_ci(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=5, seed=42,
        )
        assert isinstance(ci, AttributionConfidenceInterval)
        assert ci.home_team == "team_0"
        assert ci.away_team == "team_1"

    def test_n_bootstrap_counts_successful_iterations(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=8, seed=1,
        )
        # n_bootstrap reflects successful iterations; failed_iterations tracks skips
        assert ci.n_bootstrap + ci.failed_iterations == 8
        assert ci.n_bootstrap >= 1

    def test_factor_cis_have_expected_fields(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=5, seed=2,
        )
        assert len(ci.factor_cis) > 0
        for entry in ci.factor_cis:
            assert "factor" in entry
            assert "n_samples" in entry
            assert "delta_mean" in entry
            assert "delta_std" in entry
            assert "delta_low" in entry
            assert "delta_high" in entry

    def test_ci_bounds_ordered(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=6, seed=3,
        )
        for entry in ci.factor_cis:
            assert entry["delta_low"] <= entry["delta_mean"] + 1e-9
            assert entry["delta_mean"] - 1e-9 <= entry["delta_high"]
            assert entry["delta_low"] <= entry["delta_high"]

    def test_seven_factors_present(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=5, seed=4,
        )
        factor_keys = {e["factor"] for e in ci.factor_cis}
        expected = {
            "home_attack", "home_defense",
            "away_attack", "away_defense",
            "home_advantage", "league_mean_goals", "rho_correction",
        }
        assert factor_keys == expected

    def test_invalid_n_bootstrap_raises(self) -> None:
        df = _make_team_match_df()
        with pytest.raises(ValueError):
            bootstrap_attribution_confidence(
                df, "team_0", "team_1", n_bootstrap=1,
            )

    def test_reproducible_with_seed(self) -> None:
        df = _make_team_match_df()
        ci1 = bootstrap_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=5, seed=99,
        )
        ci2 = bootstrap_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=5, seed=99,
        )
        assert ci1.n_bootstrap == ci2.n_bootstrap
        assert ci1.failed_iterations == ci2.failed_iterations
        # Compare mean deltas factor-by-factor
        m1 = {e["factor"]: e["delta_mean"] for e in ci1.factor_cis}
        m2 = {e["factor"]: e["delta_mean"] for e in ci2.factor_cis}
        for k in m1:
            assert m1[k] == pytest.approx(m2[k], abs=1e-12)


# ---------------------------------------------------------------------------
# Ensemble attribution (per-model + blended)
# ---------------------------------------------------------------------------


class TestEnsembleAttribution:
    """Tests for compute_ensemble_attribution blending per-model factor deltas."""

    def test_returns_ensemble_attribution(self) -> None:
        df = _make_team_match_df()
        dc_model = fit_dixon_coles(df)
        form_model = fit_dixon_coles_with_form(df)
        ens = compute_ensemble_attribution(
            {"dixon_coles": dc_model, "dixon_coles_form": form_model},
            "team_0", "team_1",
        )
        assert isinstance(ens, EnsembleAttribution)
        assert ens.home_team == "team_0"
        assert ens.away_team == "team_1"

    def test_per_model_has_each_model(self) -> None:
        df = _make_team_match_df()
        dc_model = fit_dixon_coles(df)
        form_model = fit_dixon_coles_with_form(df)
        ens = compute_ensemble_attribution(
            {"dixon_coles": dc_model, "dixon_coles_form": form_model},
            "team_0", "team_1",
        )
        assert set(ens.per_model.keys()) == {"dixon_coles", "dixon_coles_form"}
        for attr in ens.per_model.values():
            assert isinstance(attr, PredictionAttribution)

    def test_blended_has_seven_factors(self) -> None:
        df = _make_team_match_df()
        dc_model = fit_dixon_coles(df)
        form_model = fit_dixon_coles_with_form(df)
        ens = compute_ensemble_attribution(
            {"dixon_coles": dc_model, "dixon_coles_form": form_model},
            "team_0", "team_1",
        )
        assert len(ens.blended.factors) == 7
        factor_keys = {f["factor"] for f in ens.blended.factors}
        assert "home_advantage" in factor_keys

    def test_equal_weights_default(self) -> None:
        df = _make_team_match_df()
        dc_model = fit_dixon_coles(df)
        form_model = fit_dixon_coles_with_form(df)
        ens = compute_ensemble_attribution(
            {"dixon_coles": dc_model, "dixon_coles_form": form_model},
            "team_0", "team_1",
        )
        # Default weights should be equal (0.5 each)
        for w in ens.weights.values():
            assert w == pytest.approx(0.5, abs=1e-6)

    def test_custom_weights_normalized(self) -> None:
        df = _make_team_match_df()
        dc_model = fit_dixon_coles(df)
        form_model = fit_dixon_coles_with_form(df)
        ens = compute_ensemble_attribution(
            {"dixon_coles": dc_model, "dixon_coles_form": form_model},
            "team_0", "team_1",
            weights={"dixon_coles": 3.0, "dixon_coles_form": 1.0},
        )
        assert ens.weights["dixon_coles"] == pytest.approx(0.75, abs=1e-6)
        assert ens.weights["dixon_coles_form"] == pytest.approx(0.25, abs=1e-6)

    def test_blended_delta_is_weighted_average(self) -> None:
        df = _make_team_match_df()
        dc_model = fit_dixon_coles(df)
        form_model = fit_dixon_coles_with_form(df)
        weights = {"dixon_coles": 0.6, "dixon_coles_form": 0.4}
        ens = compute_ensemble_attribution(
            {"dixon_coles": dc_model, "dixon_coles_form": form_model},
            "team_0", "team_1",
            weights=weights,
        )
        # Pick a factor and verify blended delta = weighted sum of per-model deltas
        factor_key = ens.blended.factors[0]["factor"]
        dc_delta = next(
            f["delta"] for f in ens.per_model["dixon_coles"].factors
            if f["factor"] == factor_key
        )
        form_delta = next(
            f["delta"] for f in ens.per_model["dixon_coles_form"].factors
            if f["factor"] == factor_key
        )
        expected = dc_delta * 0.6 + form_delta * 0.4
        blended_delta = next(
            f["delta"] for f in ens.blended.factors if f["factor"] == factor_key
        )
        assert blended_delta == pytest.approx(expected, abs=1e-6)

    def test_empty_models_raises(self) -> None:
        with pytest.raises(ValueError):
            compute_ensemble_attribution({}, "team_0", "team_1")

    def test_blended_factors_sorted_by_abs_delta(self) -> None:
        df = _make_team_match_df()
        dc_model = fit_dixon_coles(df)
        form_model = fit_dixon_coles_with_form(df)
        ens = compute_ensemble_attribution(
            {"dixon_coles": dc_model, "dixon_coles_form": form_model},
            "team_0", "team_1",
        )
        abs_deltas = [f["abs_delta"] for f in ens.blended.factors]
        assert abs_deltas == sorted(abs_deltas, reverse=True)


# ---------------------------------------------------------------------------
# Prediction diagnostics aggregation endpoint
# ---------------------------------------------------------------------------


class TestPredictionDiagnosticsEndpoint:
    """Tests for get_prediction_diagnostics aggregating calibration, drift,
    attribution, and CI cache status into one response."""

    def test_returns_diagnostics_with_expected_sections(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_team_match_df()
        monkeypatch.setattr(api_module, "load_team_match", lambda: df)
        monkeypatch.setattr(api_module, "_resolve_tuned_decay", lambda: 0.005)
        api_module._PREDICTION_CI_CACHE.clear()

        result = api_module.get_prediction_diagnostics("team_0", "team_1")

        assert result.get("status") == "ok"
        assert result["home_team"] == "team_0"
        assert result["away_team"] == "team_1"
        assert "calibration" in result
        assert "drift" in result
        assert "attribution" in result
        assert "ci_cache" in result

    def test_diagnostics_attribution_has_top_factors(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_team_match_df()
        monkeypatch.setattr(api_module, "load_team_match", lambda: df)
        monkeypatch.setattr(api_module, "_resolve_tuned_decay", lambda: 0.005)
        api_module._PREDICTION_CI_CACHE.clear()

        result = api_module.get_prediction_diagnostics("team_0", "team_1")
        attr = result["attribution"]
        assert attr.get("status") == "ok"
        top = attr.get("top_factors", [])
        assert isinstance(top, list)
        assert len(top) <= 3
        assert attr.get("n_factors") == 7

    def test_diagnostics_ci_cache_reflects_warming(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_team_match_df()
        monkeypatch.setattr(api_module, "load_team_match", lambda: df)
        monkeypatch.setattr(api_module, "_resolve_tuned_decay", lambda: 0.005)
        api_module._PREDICTION_CI_CACHE.clear()

        # Before warming: ci_cache.available should be False
        result1 = api_module.get_prediction_diagnostics("team_0", "team_1")
        assert result1["ci_cache"].get("available") is False

        # Warm the cache for dixon_coles
        api_module._get_prediction_confidence(
            "team_0", "team_1", model_type="dixon_coles",
        )

        # After warming: ci_cache.available should be True
        result2 = api_module.get_prediction_diagnostics("team_0", "team_1")
        assert result2["ci_cache"].get("available") is True
        assert "age_seconds" in result2["ci_cache"]

    def test_diagnostics_does_not_raise_on_unknown_teams(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_team_match_df()
        monkeypatch.setattr(api_module, "load_team_match", lambda: df)
        monkeypatch.setattr(api_module, "_resolve_tuned_decay", lambda: 0.005)
        api_module._PREDICTION_CI_CACHE.clear()

        result = api_module.get_prediction_diagnostics(
            "unknown_home", "unknown_away",
        )
        # Should still return a structured response, not crash
        assert result.get("status") == "ok"
        assert "calibration" in result
        assert "drift" in result


# ---------------------------------------------------------------------------
# Attribution CI and ensemble attribution API endpoints
# ---------------------------------------------------------------------------


class TestAttributionCIAndEnsembleAPI:
    """Smoke tests for the API wrappers get_prediction_attribution_ci and
    get_ensemble_attribution."""

    def test_attribution_ci_returns_ok(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_team_match_df()
        monkeypatch.setattr(api_module, "load_team_match", lambda: df)
        monkeypatch.setattr(api_module, "_resolve_tuned_decay", lambda: 0.005)

        result = api_module.get_prediction_attribution_ci(
            "team_0", "team_1", n_bootstrap=5,
        )
        assert result.get("status") == "ok"
        assert result["home_team"] == "team_0"
        assert result["away_team"] == "team_1"
        assert "factor_cis" in result
        assert isinstance(result["factor_cis"], list)
        assert len(result["factor_cis"]) > 0

    def test_attribution_ci_insufficient_data(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        # Empty dataframe should trigger not_available
        monkeypatch.setattr(api_module, "load_team_match", lambda: pd.DataFrame())
        result = api_module.get_prediction_attribution_ci(
            "team_0", "team_1", n_bootstrap=5,
        )
        assert result.get("status") == "not_available"

    def test_ensemble_attribution_returns_ok(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_team_match_df()
        monkeypatch.setattr(api_module, "load_team_match", lambda: df)
        monkeypatch.setattr(api_module, "_resolve_tuned_decay", lambda: 0.005)

        result = api_module.get_ensemble_attribution("team_0", "team_1")
        assert result.get("status") == "ok"
        assert "blended" in result
        assert "per_model" in result
        assert "weights" in result
        assert set(result["per_model"].keys()) == {"dixon_coles", "dixon_coles_form"}

    def test_ensemble_attribution_blended_has_factors(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_team_match_df()
        monkeypatch.setattr(api_module, "load_team_match", lambda: df)
        monkeypatch.setattr(api_module, "_resolve_tuned_decay", lambda: 0.005)

        result = api_module.get_ensemble_attribution("team_0", "team_1")
        blended = result["blended"]
        assert "factors" in blended
        assert len(blended["factors"]) == 7
        assert "baseline_home_win" in blended


# ---------------------------------------------------------------------------
# Ensemble attribution bootstrap CI
# ---------------------------------------------------------------------------


class TestBootstrapEnsembleAttributionConfidence:
    """Tests for bootstrap_ensemble_attribution_confidence producing CIs on
    blended factor deltas across both DC and form-weighted DC models."""

    def test_returns_attribution_ci(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_ensemble_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=5, seed=42,
        )
        assert isinstance(ci, AttributionConfidenceInterval)
        assert ci.home_team == "team_0"
        assert ci.away_team == "team_1"

    def test_n_bootstrap_counts_successful_iterations(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_ensemble_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=6, seed=1,
        )
        assert ci.n_bootstrap + ci.failed_iterations == 6
        assert ci.n_bootstrap >= 1

    def test_factor_cis_have_expected_fields(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_ensemble_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=5, seed=2,
        )
        assert len(ci.factor_cis) > 0
        for entry in ci.factor_cis:
            assert "factor" in entry
            assert "n_samples" in entry
            assert "delta_mean" in entry
            assert "delta_low" in entry
            assert "delta_high" in entry

    def test_ci_bounds_ordered(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_ensemble_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=5, seed=3,
        )
        for entry in ci.factor_cis:
            assert entry["delta_low"] <= entry["delta_high"]

    def test_seven_factors_present(self) -> None:
        df = _make_team_match_df()
        ci = bootstrap_ensemble_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=5, seed=4,
        )
        factor_keys = {e["factor"] for e in ci.factor_cis}
        assert len(factor_keys) == 7

    def test_invalid_n_bootstrap_raises(self) -> None:
        df = _make_team_match_df()
        with pytest.raises(ValueError):
            bootstrap_ensemble_attribution_confidence(
                df, "team_0", "team_1", n_bootstrap=1,
            )

    def test_reproducible_with_seed(self) -> None:
        df = _make_team_match_df()
        ci1 = bootstrap_ensemble_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=5, seed=77,
        )
        ci2 = bootstrap_ensemble_attribution_confidence(
            df, "team_0", "team_1", n_bootstrap=5, seed=77,
        )
        assert ci1.n_bootstrap == ci2.n_bootstrap
        m1 = {e["factor"]: e["delta_mean"] for e in ci1.factor_cis}
        m2 = {e["factor"]: e["delta_mean"] for e in ci2.factor_cis}
        for k in m1:
            assert m1[k] == pytest.approx(m2[k], abs=1e-12)

    def test_custom_weights_normalized(self) -> None:
        """Custom weights should be accepted and normalized internally
        without changing the CI structure."""
        df = _make_team_match_df()
        ci = bootstrap_ensemble_attribution_confidence(
            df, "team_0", "team_1",
            n_bootstrap=4, seed=5,
            weights={"dixon_coles": 3.0, "dixon_coles_form": 1.0},
        )
        assert isinstance(ci, AttributionConfidenceInterval)
        assert len(ci.factor_cis) > 0


# ---------------------------------------------------------------------------
# Ensemble attribution CI API endpoint
# ---------------------------------------------------------------------------


class TestEnsembleAttributionCIAPI:
    """Smoke tests for the get_ensemble_attribution_ci API wrapper."""

    def test_returns_ok(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_team_match_df()
        monkeypatch.setattr(api_module, "load_team_match", lambda: df)
        monkeypatch.setattr(api_module, "_resolve_tuned_decay", lambda: 0.005)

        result = api_module.get_ensemble_attribution_ci(
            "team_0", "team_1", n_bootstrap=5,
        )
        assert result.get("status") == "ok"
        assert result["home_team"] == "team_0"
        assert result["away_team"] == "team_1"
        assert "factor_cis" in result
        assert isinstance(result["factor_cis"], list)
        assert len(result["factor_cis"]) > 0
        assert "weights_source" in result

    def test_insufficient_data(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(api_module, "load_team_match", lambda: pd.DataFrame())
        result = api_module.get_ensemble_attribution_ci(
            "team_0", "team_1", n_bootstrap=5,
        )
        assert result.get("status") == "not_available"

    def test_weights_source_equal_when_no_cache(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_team_match_df()
        monkeypatch.setattr(api_module, "load_team_match", lambda: df)
        monkeypatch.setattr(api_module, "_resolve_tuned_decay", lambda: 0.005)

        # Ensure load_ensemble_weights returns None (no cached weights)
        from scoutfootball.models import match_prediction as mp

        original = mp.load_ensemble_weights
        monkeypatch.setattr(mp, "load_ensemble_weights", lambda *a, **k: None)

        result = api_module.get_ensemble_attribution_ci(
            "team_0", "team_1", n_bootstrap=4,
        )
        assert result.get("status") == "ok"
        assert result.get("weights_source") == "equal"

        # Restore
        monkeypatch.setattr(mp, "load_ensemble_weights", original)


# ---------------------------------------------------------------------------
# Calibration drift timeline endpoint
# ---------------------------------------------------------------------------


class TestCalibrationDriftTimeline:
    """Tests for get_calibration_drift_timeline projecting windows into
    chart-ready points."""

    def test_returns_timeline_with_points(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        # Build a drift report stub with windows
        fake_report = {
            "status": "ok",
            "drift_detected": False,
            "drift_metric": "rps_1x2",
            "drift_threshold": 0.05,
            "overall_metrics": {"rps_1x2": 0.2},
            "windows": [
                {
                    "start_date": "2024-01-01", "end_date": "2024-04-01",
                    "n_matches": 50, "rps_1x2": 0.18, "brier_1x2": 0.30,
                    "log_loss_exact": 0.65,
                },
                {
                    "start_date": "2024-04-01", "end_date": "2024-07-01",
                    "n_matches": 60, "rps_1x2": 0.22, "brier_1x2": 0.33,
                    "log_loss_exact": 0.70,
                },
            ],
            "latest_window": {
                "start_date": "2024-04-01", "end_date": "2024-07-01",
                "n_matches": 60, "rps_1x2": 0.22,
            },
        }
        monkeypatch.setattr(
            api_module, "get_calibration_drift", lambda: fake_report,
        )

        result = api_module.get_calibration_drift_timeline()

        assert result.get("status") == "ok"
        assert result["metric"] == "rps_1x2"
        assert result["threshold"] == 0.05
        assert result["drift_detected"] is False
        assert result["n_points"] == 2
        points = result["points"]
        assert len(points) == 2
        for p in points:
            assert "date" in p
            assert "start_date" in p
            assert "end_date" in p
            assert "n_matches" in p
            assert "rps_1x2" in p
            assert "brier_1x2" in p
            assert "log_loss_exact" in p

    def test_date_uses_end_date(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        fake_report = {
            "status": "ok",
            "drift_detected": False,
            "drift_metric": "rps_1x2",
            "drift_threshold": 0.05,
            "overall_metrics": {},
            "windows": [
                {
                    "start_date": "2024-01-01", "end_date": "2024-04-01",
                    "n_matches": 10, "rps_1x2": 0.2, "brier_1x2": 0.3,
                    "log_loss_exact": 0.6,
                },
            ],
            "latest_window": None,
        }
        monkeypatch.setattr(
            api_module, "get_calibration_drift", lambda: fake_report,
        )

        result = api_module.get_calibration_drift_timeline()
        assert result["points"][0]["date"] == "2024-04-01"

    def test_propagates_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "get_calibration_drift",
            lambda: {"status": "not_available", "instructions": "run backtest"},
        )
        result = api_module.get_calibration_drift_timeline()
        assert result.get("status") == "not_available"

    def test_empty_windows_returns_zero_points(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        fake_report = {
            "status": "ok",
            "drift_detected": False,
            "drift_metric": "rps_1x2",
            "drift_threshold": 0.05,
            "overall_metrics": {},
            "windows": [],
            "latest_window": None,
        }
        monkeypatch.setattr(
            api_module, "get_calibration_drift", lambda: fake_report,
        )
        result = api_module.get_calibration_drift_timeline()
        assert result.get("status") == "ok"
        assert result["n_points"] == 0
        assert result["points"] == []


# ---------------------------------------------------------------------------
# Value betting analysis (compute_value_bets)
# ---------------------------------------------------------------------------


class TestComputeValueBets:
    """Tests for the value betting computation function."""

    def test_returns_analysis_with_three_outcomes(self) -> None:
        probs = {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}
        odds = {"home_win": 2.0, "draw": 3.5, "away_win": 5.0}
        result = compute_value_bets(probs, odds)
        assert len(result.outcomes) == 3
        outcome_keys = {o.outcome for o in result.outcomes}
        assert outcome_keys == {"home_win", "draw", "away_win"}

    def test_implied_probability_correct(self) -> None:
        probs = {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}
        odds = {"home_win": 2.0, "draw": 4.0, "away_win": 5.0}
        result = compute_value_bets(probs, odds)
        home = next(o for o in result.outcomes if o.outcome == "home_win")
        assert home.implied_probability == pytest.approx(0.5, abs=1e-6)

    def test_expected_value_correct(self) -> None:
        probs = {"home_win": 0.6, "draw": 0.25, "away_win": 0.15}
        odds = {"home_win": 2.0, "draw": 4.0, "away_win": 8.0}
        result = compute_value_bets(probs, odds)
        home = next(o for o in result.outcomes if o.outcome == "home_win")
        # EV = 0.6 * 2.0 - 1 = 0.2
        assert home.expected_value == pytest.approx(0.2, abs=1e-6)

    def test_edge_correct(self) -> None:
        probs = {"home_win": 0.6, "draw": 0.25, "away_win": 0.15}
        odds = {"home_win": 2.0, "draw": 4.0, "away_win": 8.0}
        result = compute_value_bets(probs, odds)
        home = next(o for o in result.outcomes if o.outcome == "home_win")
        # edge = 0.6 - 0.5 = 0.1
        assert home.edge == pytest.approx(0.1, abs=1e-6)

    def test_kelly_fraction_correct(self) -> None:
        probs = {"home_win": 0.6, "draw": 0.25, "away_win": 0.15}
        odds = {"home_win": 2.0, "draw": 4.0, "away_win": 8.0}
        result = compute_value_bets(probs, odds)
        home = next(o for o in result.outcomes if o.outcome == "home_win")
        # Kelly = (0.6 * 2 - 1) / (2 - 1) = 0.2
        assert home.kelly_fraction == pytest.approx(0.2, abs=1e-6)

    def test_value_bet_recommendation_when_ev_positive(self) -> None:
        probs = {"home_win": 0.6, "draw": 0.25, "away_win": 0.15}
        odds = {"home_win": 2.0, "draw": 4.0, "away_win": 8.0}
        result = compute_value_bets(probs, odds)
        home = next(o for o in result.outcomes if o.outcome == "home_win")
        assert home.recommendation == "value_bet"

    def test_no_value_when_ev_negative(self) -> None:
        probs = {"home_win": 0.3, "draw": 0.4, "away_win": 0.3}
        odds = {"home_win": 2.0, "draw": 2.0, "away_win": 2.0}
        result = compute_value_bets(probs, odds)
        for o in result.outcomes:
            assert o.recommendation == "no_value"

    def test_best_bet_is_highest_ev_value(self) -> None:
        probs = {"home_win": 0.6, "draw": 0.25, "away_win": 0.15}
        odds = {"home_win": 2.0, "draw": 4.0, "away_win": 8.0}
        result = compute_value_bets(probs, odds)
        assert result.best_bet is not None
        # Home has EV 0.2, away has EV 0.15*8-1=0.2, draw has EV 0.25*4-1=0.0
        # Home and away tied, best_bet should be one of the value bets
        assert result.best_bet.recommendation == "value_bet"

    def test_best_bet_none_when_no_value(self) -> None:
        probs = {"home_win": 0.3, "draw": 0.4, "away_win": 0.3}
        odds = {"home_win": 2.0, "draw": 2.0, "away_win": 2.0}
        result = compute_value_bets(probs, odds)
        assert result.best_bet is None

    def test_overround_positive_for_fair_book(self) -> None:
        probs = {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}
        # Odds with overround: implied = 0.55 + 0.30 + 0.25 = 1.10
        odds = {"home_win": 1.818, "draw": 3.333, "away_win": 4.0}
        result = compute_value_bets(probs, odds)
        assert result.overround > 0

    def test_missing_prob_keys_raises(self) -> None:
        with pytest.raises(ValueError, match="missing keys"):
            compute_value_bets(
                {"home_win": 0.5, "draw": 0.5},
                {"home_win": 2.0, "draw": 3.0, "away_win": 4.0},
            )

    def test_probs_not_summing_to_one_raises(self) -> None:
        with pytest.raises(ValueError, match="sum to 1.0"):
            compute_value_bets(
                {"home_win": 0.5, "draw": 0.3, "away_win": 0.3},
                {"home_win": 2.0, "draw": 3.0, "away_win": 4.0},
            )

    def test_odds_below_one_raises(self) -> None:
        with pytest.raises(ValueError, match=">= 1.0"):
            compute_value_bets(
                {"home_win": 0.5, "draw": 0.3, "away_win": 0.2},
                {"home_win": 0.5, "draw": 3.0, "away_win": 4.0},
            )

    def test_kelly_clamped_to_zero_when_negative(self) -> None:
        probs = {"home_win": 0.3, "draw": 0.4, "away_win": 0.3}
        odds = {"home_win": 2.0, "draw": 2.5, "away_win": 3.0}
        result = compute_value_bets(probs, odds)
        for o in result.outcomes:
            assert o.kelly_fraction >= 0.0


# ---------------------------------------------------------------------------
# Reliability diagram (compute_reliability_diagram)
# ---------------------------------------------------------------------------


class TestComputeReliabilityDiagram:
    """Tests for the reliability diagram computation."""

    def test_returns_diagram_with_bins(self) -> None:
        df = _make_predictions_df(n=200)
        diagram = compute_reliability_diagram(df, n_bins=10)
        assert diagram.n_predictions == 200
        assert len(diagram.bins) > 0
        assert "home_win" in diagram.per_outcome
        assert "draw" in diagram.per_outcome
        assert "away_win" in diagram.per_outcome

    def test_bin_fields_present(self) -> None:
        df = _make_predictions_df(n=200)
        diagram = compute_reliability_diagram(df, n_bins=10)
        for b in diagram.bins:
            assert 0.0 <= b.bin_lower <= 1.0
            assert 0.0 <= b.bin_upper <= 1.0
            assert 0.0 <= b.mean_predicted <= 1.0
            assert 0.0 <= b.observed_frequency <= 1.0
            assert b.n_samples > 0
            assert b.outcome in ("home_win", "draw", "away_win")

    def test_overall_metrics_present(self) -> None:
        df = _make_predictions_df(n=200)
        diagram = compute_reliability_diagram(df, n_bins=10)
        assert "ece" in diagram.overall
        assert "rms_calibration_error" in diagram.overall
        assert diagram.overall["ece"] >= 0.0
        assert diagram.overall["rms_calibration_error"] >= 0.0

    def test_min_samples_filters_small_bins(self) -> None:
        df = _make_predictions_df(n=50)
        diagram_few = compute_reliability_diagram(df, n_bins=10, min_samples_per_bin=1)
        diagram_many = compute_reliability_diagram(df, n_bins=10, min_samples_per_bin=100)
        assert len(diagram_few.bins) >= len(diagram_many.bins)

    def test_invalid_n_bins_raises(self) -> None:
        df = _make_predictions_df(n=200)
        with pytest.raises(ValueError, match="n_bins must be >= 2"):
            compute_reliability_diagram(df, n_bins=1)

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"foo": [1, 2, 3]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_reliability_diagram(df)

    def test_perfect_calibration_has_low_ece(self) -> None:
        """When predicted == observed, ECE should be near 0."""
        n = 1000
        rng = np.random.default_rng(42)
        # Create perfectly calibrated predictions
        probs = rng.uniform(0.1, 0.9, n)
        outcomes = (rng.uniform(0, 1, n) < probs).astype(int)
        df = pd.DataFrame({
            "home_win_probability": probs,
            "draw_probability": 0.1,
            "away_win_probability": 1.0 - probs - 0.1,
            "actual_outcome": np.where(outcomes == 1, "home_win", "away_win"),
        })
        diagram = compute_reliability_diagram(df, n_bins=10, min_samples_per_bin=5)
        assert diagram.overall["ece"] < 0.1  # Should be reasonably calibrated


# ---------------------------------------------------------------------------
# Per-team prediction accuracy (compute_team_accuracy)
# ---------------------------------------------------------------------------


class TestComputeTeamAccuracy:
    """Tests for per-team prediction accuracy tracking."""

    def test_returns_report_with_entries(self) -> None:
        df = _make_predictions_df(n=200)
        n = len(df)
        df["home_team_id"] = [f"team_{i % 6}" for i in range(n)]
        df["away_team_id"] = [f"team_{(i + 3) % 6}" for i in range(n)]
        report = compute_team_accuracy(df, min_predictions=1)
        assert len(report.entries) > 0
        assert report.n_teams > 0

    def test_entries_sorted_by_n_predictions_desc(self) -> None:
        df = _make_predictions_df(n=200)
        n = len(df)
        df["home_team_id"] = [f"team_{i % 6}" for i in range(n)]
        df["away_team_id"] = [f"team_{(i + 3) % 6}" for i in range(n)]
        report = compute_team_accuracy(df, min_predictions=1)
        n_preds = [e.n_predictions for e in report.entries]
        assert n_preds == sorted(n_preds, reverse=True)

    def test_hit_rate_in_range(self) -> None:
        df = _make_predictions_df(n=200)
        n = len(df)
        df["home_team_id"] = [f"team_{i % 6}" for i in range(n)]
        df["away_team_id"] = [f"team_{(i + 3) % 6}" for i in range(n)]
        report = compute_team_accuracy(df, min_predictions=1)
        for e in report.entries:
            assert 0.0 <= e.hit_rate <= 1.0

    def test_calibration_gap_is_confidence_minus_hit_rate(self) -> None:
        df = _make_predictions_df(n=200)
        n = len(df)
        df["home_team_id"] = [f"team_{i % 6}" for i in range(n)]
        df["away_team_id"] = [f"team_{(i + 3) % 6}" for i in range(n)]
        report = compute_team_accuracy(df, min_predictions=1)
        for e in report.entries:
            expected = round(e.avg_confidence - e.hit_rate, 4)
            assert e.calibration_gap == pytest.approx(expected, abs=1e-4)

    def test_min_predictions_filters_teams(self) -> None:
        df = _make_predictions_df(n=200)
        n = len(df)
        df["home_team_id"] = [f"team_{i % 6}" for i in range(n)]
        df["away_team_id"] = [f"team_{(i + 3) % 6}" for i in range(n)]
        report_low = compute_team_accuracy(df, min_predictions=1)
        report_high = compute_team_accuracy(df, min_predictions=100)
        assert len(report_low.entries) >= len(report_high.entries)

    def test_overall_hit_rate_present(self) -> None:
        df = _make_predictions_df(n=200)
        n = len(df)
        df["home_team_id"] = [f"team_{i % 6}" for i in range(n)]
        df["away_team_id"] = [f"team_{(i + 3) % 6}" for i in range(n)]
        report = compute_team_accuracy(df, min_predictions=1)
        assert 0.0 <= report.overall_hit_rate <= 1.0

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"foo": [1, 2, 3]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_team_accuracy(df)

    def test_last_match_date_tracked(self) -> None:
        df = _make_predictions_df(n=200)
        n = len(df)
        df["home_team_id"] = [f"team_{i % 6}" for i in range(n)]
        df["away_team_id"] = [f"team_{(i + 3) % 6}" for i in range(n)]
        df["match_date"] = [f"2024-{(i % 12) + 1:02d}-15" for i in range(n)]
        report = compute_team_accuracy(df, min_predictions=1)
        for e in report.entries:
            assert e.last_match_date is not None
            assert e.last_match_date.startswith("2024-")


# ---------------------------------------------------------------------------
# Value bet API endpoint
# ---------------------------------------------------------------------------


class TestValueBetAPI:
    """Tests for the get_value_bet_analysis API wrapper."""

    def test_returns_ok(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        # Stub get_match_prediction_dc to return known probabilities
        def fake_pred(home, away):
            return {
                "home_win": 0.5,
                "draw": 0.3,
                "away_win": 0.2,
                "model_type": "dixon_coles",
            }

        monkeypatch.setattr(api_module, "get_match_prediction_dc", fake_pred)

        result = api_module.get_value_bet_analysis(
            "team_a", "team_b",
            home_odds=2.0, draw_odds=4.0, away_odds=8.0,
        )
        assert result["status"] == "ok"
        assert len(result["outcomes"]) == 3
        assert result["best_bet"] is not None
        assert "overround" in result
        assert "disclaimer" in result

    def test_odds_below_one_returns_error(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        result = api_module.get_value_bet_analysis(
            "team_a", "team_b",
            home_odds=0.5, draw_odds=4.0, away_odds=8.0,
        )
        assert result["status"] == "error"

    def test_no_value_when_odds_unfavorable(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        def fake_pred(home, away):
            return {"home_win": 0.3, "draw": 0.4, "away_win": 0.3, "model_type": "dc"}

        monkeypatch.setattr(api_module, "get_match_prediction_dc", fake_pred)

        result = api_module.get_value_bet_analysis(
            "team_a", "team_b",
            home_odds=2.0, draw_odds=2.0, away_odds=2.0,
        )
        assert result["status"] == "ok"
        assert result["best_bet"] is None


# ---------------------------------------------------------------------------
# Reliability diagram API endpoint
# ---------------------------------------------------------------------------


class TestReliabilityDiagramAPI:
    """Tests for the get_reliability_diagram API wrapper."""

    def test_returns_not_available_without_data(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        class FakeSettings:
            class _Inner:
                report_root = Path("/nonexistent")

            def __call__(self):
                return self._Inner()

        # Point to nonexistent path
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent_path_12345")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_reliability_diagram(n_bins=10)
        assert result["status"] == "not_available"

    def test_returns_ok_with_data(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=200)
        # Create a temporary parquet file
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "calibration_backtest"
            tmp_path.mkdir()
            df.to_parquet(tmp_path / "poisson_backtest_predictions.parquet", index=False)

            monkeypatch.setattr(
                api_module, "_settings",
                lambda: type("S", (), {"report_root": Path(tmpdir)})(),
            )
            api_module._BACKTEST_CACHE.clear()
            result = api_module.get_reliability_diagram(n_bins=10)
            assert result["status"] == "ok"
            assert "per_outcome" in result
            assert "overall" in result
            assert result["n_predictions"] == 200


# ---------------------------------------------------------------------------
# Team accuracy API endpoint
# ---------------------------------------------------------------------------


class TestTeamAccuracyAPI:
    """Tests for the get_team_accuracy API wrapper."""

    def test_returns_not_available_without_data(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent_path_12345")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_team_accuracy("team_0")
        assert result["status"] == "not_available"

    def test_returns_ok_with_matching_team(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=200)
        n = len(df)
        df["home_team_id"] = ["arsenal" if i < 100 else "chelsea" for i in range(n)]
        df["away_team_id"] = ["chelsea" if i < 100 else "arsenal" for i in range(n)]

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "calibration_backtest"
            tmp_path.mkdir()
            df.to_parquet(tmp_path / "dixon_coles_decay_backtest_predictions.parquet", index=False)

            monkeypatch.setattr(
                api_module, "_settings",
                lambda: type("S", (), {"report_root": Path(tmpdir)})(),
            )
            api_module._BACKTEST_CACHE.clear()
            result = api_module.get_team_accuracy("arsenal", min_predictions=1)
            assert result["status"] == "ok"
            assert result["team_id"] == "arsenal"
            assert result["n_predictions"] > 0

    def test_returns_not_found_for_unknown_team(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=200)
        n = len(df)
        df["home_team_id"] = ["arsenal"] * n
        df["away_team_id"] = ["chelsea"] * n

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "calibration_backtest"
            tmp_path.mkdir()
            df.to_parquet(tmp_path / "poisson_backtest_predictions.parquet", index=False)

            monkeypatch.setattr(
                api_module, "_settings",
                lambda: type("S", (), {"report_root": Path(tmpdir)})(),
            )
            api_module._BACKTEST_CACHE.clear()
            result = api_module.get_team_accuracy("nonexistent_team", min_predictions=1)
            assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# Model comparison dashboard (compute_model_comparison)
# ---------------------------------------------------------------------------


class TestComputeModelComparison:
    """Tests for the unified model comparison function."""

    def _make_model_df(
        self, n: int = 100, *, model_bias: float = 0.0, seed: int = 42,
    ) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        home_prob = np.clip(rng.uniform(0.2, 0.7, n) + model_bias, 0.05, 0.95)
        draw_prob = rng.uniform(0.15, 0.3, n)
        away_prob = 1.0 - home_prob - draw_prob
        away_prob = np.clip(away_prob, 0.05, 0.9)
        total = home_prob + draw_prob + away_prob
        home_prob /= total
        draw_prob /= total
        away_prob /= total
        outcomes = rng.choice(["home_win", "draw", "away_win"], n, p=[0.45, 0.28, 0.27])
        return pd.DataFrame({
            "match_id": [f"m{i}" for i in range(n)],
            "home_win_probability": home_prob,
            "draw_probability": draw_prob,
            "away_win_probability": away_prob,
            "actual_outcome": outcomes,
        })

    def test_returns_comparison_with_models(self) -> None:
        models = {
            "poisson": self._make_model_df(seed=1),
            "dixon_coles": self._make_model_df(seed=2),
        }
        result = compute_model_comparison(models)
        assert len(result.models) == 2
        assert result.n_models == 2
        assert result.n_aligned > 0

    def test_aligned_on_intersection(self) -> None:
        df1 = self._make_model_df(n=100, seed=1)
        df2 = self._make_model_df(n=100, seed=2)
        df2["match_id"] = [f"m{i+50}" for i in range(100)]
        result = compute_model_comparison({"a": df1, "b": df2})
        assert result.n_aligned == 50

    def test_empty_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            compute_model_comparison({})

    def test_missing_align_column_raises(self) -> None:
        df = self._make_model_df(seed=1)
        df_no_id = df.drop(columns=["match_id"])
        with pytest.raises(ValueError, match="missing align column"):
            compute_model_comparison({"a": df, "b": df_no_id})

    def test_no_intersection_returns_empty_models(self) -> None:
        df1 = self._make_model_df(n=50, seed=1)
        df2 = self._make_model_df(n=50, seed=2)
        df1["match_id"] = [f"a{i}" for i in range(50)]
        df2["match_id"] = [f"b{i}" for i in range(50)]
        result = compute_model_comparison({"a": df1, "b": df2})
        assert result.models == []
        assert result.n_aligned == 0

    def test_metric_winners_present(self) -> None:
        models = {
            "poisson": self._make_model_df(seed=1),
            "dixon_coles": self._make_model_df(seed=2),
        }
        result = compute_model_comparison(models)
        assert "brier" in result.metric_winners
        assert "rps" in result.metric_winners
        assert "accuracy" in result.metric_winners

    def test_model_entry_fields(self) -> None:
        models = {"poisson": self._make_model_df(seed=1)}
        result = compute_model_comparison(models)
        e = result.models[0]
        assert e.model == "poisson"
        assert e.label == "Poisson"
        assert e.n_predictions > 0
        assert e.brier is not None
        assert e.rps is not None
        assert e.accuracy is not None

    def test_lower_brier_wins(self) -> None:
        """The model with lower Brier should win the brier metric."""
        df_good = self._make_model_df(seed=1)
        # Make df_good well-calibrated by aligning probs with outcomes
        df_good["home_win_probability"] = np.where(
            df_good["actual_outcome"] == "home_win", 0.7,
            np.where(df_good["actual_outcome"] == "draw", 0.2, 0.1),
        )
        df_good["draw_probability"] = np.where(
            df_good["actual_outcome"] == "draw", 0.6, 0.2,
        )
        df_good["away_win_probability"] = (
            1.0 - df_good["home_win_probability"] - df_good["draw_probability"]
        )
        df_bad = self._make_model_df(seed=2)
        result = compute_model_comparison({"good": df_good, "bad": df_bad})
        good_brier = next(e.brier for e in result.models if e.model == "good")
        bad_brier = next(e.brier for e in result.models if e.model == "bad")
        assert good_brier < bad_brier
        assert result.metric_winners["brier"] == "good"

    def test_higher_accuracy_wins(self) -> None:
        """The model with higher accuracy should win the accuracy metric."""
        df_good = self._make_model_df(seed=1)
        df_bad = self._make_model_df(seed=2)
        # Force df_good to have higher accuracy by aligning predictions with outcomes
        df_good["home_win_probability"] = np.where(
            df_good["actual_outcome"] == "home_win", 0.8,
            np.where(df_good["actual_outcome"] == "draw", 0.1, 0.1),
        )
        df_good["draw_probability"] = np.where(
            df_good["actual_outcome"] == "draw", 0.8, 0.1,
        )
        df_good["away_win_probability"] = (
            1.0 - df_good["home_win_probability"] - df_good["draw_probability"]
        )
        result = compute_model_comparison({"good": df_good, "bad": df_bad})
        good_acc = next(e.accuracy for e in result.models if e.model == "good")
        bad_acc = next(e.accuracy for e in result.models if e.model == "bad")
        assert good_acc > bad_acc
        assert result.metric_winners["accuracy"] == "good"

    def test_log_loss_none_without_exact_score(self) -> None:
        df = self._make_model_df(seed=1)
        result = compute_model_comparison({"poisson": df})
        assert result.models[0].log_loss is None

    def test_log_loss_computed_with_exact_score(self) -> None:
        df = self._make_model_df(seed=1)
        df["exact_score_probability"] = 0.05
        result = compute_model_comparison({"poisson": df})
        assert result.models[0].log_loss is not None
        assert result.models[0].log_loss > 0


# ---------------------------------------------------------------------------
# Score-line calibration (compute_scoreline_calibration)
# ---------------------------------------------------------------------------


class TestComputeScorelineCalibration:
    """Tests for score-line calibration matrix."""

    def _make_scoreline_df(self, n: int = 200) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        home_goals = rng.poisson(1.5, n)
        away_goals = rng.poisson(1.1, n)
        outcomes = np.where(
            home_goals > away_goals, "home_win",
            np.where(home_goals == away_goals, "draw", "away_win"),
        )
        return pd.DataFrame({
            "home_goals": home_goals,
            "away_goals": away_goals,
            "home_win_probability": rng.uniform(0.2, 0.6, n),
            "draw_probability": rng.uniform(0.2, 0.3, n),
            "away_win_probability": rng.uniform(0.2, 0.5, n),
            "actual_outcome": outcomes,
        })

    def test_returns_entries(self) -> None:
        df = self._make_scoreline_df(n=300)
        result = compute_scoreline_calibration(df)
        assert len(result.entries) > 0
        assert result.n_matches == 300

    def test_entries_sorted_by_n_matches_desc(self) -> None:
        df = self._make_scoreline_df(n=500)
        result = compute_scoreline_calibration(df)
        n_matches = [e.n_matches for e in result.entries]
        assert n_matches == sorted(n_matches, reverse=True)

    def test_entry_fields(self) -> None:
        df = self._make_scoreline_df(n=300)
        result = compute_scoreline_calibration(df)
        e = result.entries[0]
        assert hasattr(e, "scoreline")
        assert hasattr(e, "outcome")
        assert hasattr(e, "n_matches")
        assert hasattr(e, "avg_home_win_prob")
        assert hasattr(e, "avg_draw_prob")
        assert hasattr(e, "avg_away_win_prob")
        assert hasattr(e, "actual_home_win_rate")
        assert hasattr(e, "actual_draw_rate")
        assert hasattr(e, "actual_away_win_rate")

    def test_min_samples_filters(self) -> None:
        df = self._make_scoreline_df(n=100)
        result_few = compute_scoreline_calibration(df, min_samples=1)
        result_many = compute_scoreline_calibration(df, min_samples=50)
        assert len(result_few.entries) >= len(result_many.entries)

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"foo": [1, 2, 3]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_scoreline_calibration(df)

    def test_high_score_bucketed(self) -> None:
        df = self._make_scoreline_df(n=500)
        # Inject some high-score matches
        df.loc[:5, "home_goals"] = 7
        df.loc[:5, "away_goals"] = 0
        result = compute_scoreline_calibration(df, max_scoreline=5, min_samples=1)
        scorelines = [e.scoreline for e in result.entries]
        assert any("5+" in s for s in scorelines)

    def test_outcome_summary(self) -> None:
        df = self._make_scoreline_df(n=300)
        result = compute_scoreline_calibration(df)
        assert len(result.outcome_summary) > 0
        for s in result.outcome_summary:
            assert "outcome" in s
            assert "n_matches" in s
            assert "avg_predicted_prob" in s

    def test_dominant_outcome_correct(self) -> None:
        """Score-line 1-0 should have home_win as dominant outcome."""
        n = 200
        df = pd.DataFrame({
            "home_goals": [1] * n,
            "away_goals": [0] * n,
            "home_win_probability": [0.5] * n,
            "draw_probability": [0.3] * n,
            "away_win_probability": [0.2] * n,
            "actual_outcome": ["home_win"] * n,
        })
        result = compute_scoreline_calibration(df, min_samples=3)
        assert len(result.entries) == 1
        assert result.entries[0].outcome == "home_win"
        assert result.entries[0].actual_home_win_rate == 1.0


# ---------------------------------------------------------------------------
# Confidence distribution (compute_confidence_distribution)
# ---------------------------------------------------------------------------


class TestComputeConfidenceDistribution:
    """Tests for prediction confidence distribution calibration."""

    def test_returns_buckets(self) -> None:
        df = _make_predictions_df(n=500)
        result = compute_confidence_distribution(df, n_bins=10, min_samples_per_bucket=1)
        assert len(result.buckets) > 0
        assert result.n_predictions == 500

    def test_bucket_fields(self) -> None:
        df = _make_predictions_df(n=500)
        result = compute_confidence_distribution(df, n_bins=10, min_samples_per_bucket=1)
        b = result.buckets[0]
        assert hasattr(b, "bucket_label")
        assert hasattr(b, "bucket_lower")
        assert hasattr(b, "bucket_upper")
        assert hasattr(b, "n_predictions")
        assert hasattr(b, "accuracy")
        assert hasattr(b, "avg_confidence")
        assert hasattr(b, "calibration_gap")

    def test_overall_metrics(self) -> None:
        df = _make_predictions_df(n=500)
        result = compute_confidence_distribution(df, n_bins=10, min_samples_per_bucket=1)
        assert 0 <= result.overall_accuracy <= 1
        assert 0 <= result.overall_confidence <= 1

    def test_min_samples_filters(self) -> None:
        df = _make_predictions_df(n=100)
        few = compute_confidence_distribution(df, n_bins=10, min_samples_per_bucket=1)
        many = compute_confidence_distribution(df, n_bins=10, min_samples_per_bucket=50)
        assert len(few.buckets) >= len(many.buckets)

    def test_invalid_n_bins_raises(self) -> None:
        df = _make_predictions_df(n=100)
        with pytest.raises(ValueError, match="n_bins must be in"):
            compute_confidence_distribution(df, n_bins=1)

    def test_invalid_n_bins_too_high_raises(self) -> None:
        df = _make_predictions_df(n=100)
        with pytest.raises(ValueError, match="n_bins must be in"):
            compute_confidence_distribution(df, n_bins=51)

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"foo": [1, 2, 3]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_confidence_distribution(df)

    def test_perfect_calibration_low_gap(self) -> None:
        """When confidence == accuracy, calibration gap should be near 0."""
        n = 1000
        rng = np.random.default_rng(42)
        probs = rng.uniform(0.34, 0.9, n)
        # Make outcomes match the predicted confidence level
        outcomes = (rng.uniform(0, 1, n) < probs).astype(int)
        df = pd.DataFrame({
            "home_win_probability": probs,
            "draw_probability": 0.1,
            "away_win_probability": 1.0 - probs - 0.1,
            "actual_outcome": np.where(outcomes == 1, "home_win", "away_win"),
        })
        result = compute_confidence_distribution(df, n_bins=10, min_samples_per_bucket=5)
        # Overall gap should be small for well-calibrated predictions
        assert abs(result.overall_confidence - result.overall_accuracy) < 0.15

    def test_buckets_sorted_ascending_by_confidence(self) -> None:
        df = _make_predictions_df(n=500)
        result = compute_confidence_distribution(df, n_bins=10, min_samples_per_bucket=1)
        lowers = [b.bucket_lower for b in result.buckets]
        assert lowers == sorted(lowers)


# ---------------------------------------------------------------------------
# Model comparison API endpoint
# ---------------------------------------------------------------------------


class TestModelComparisonAPI:
    """Tests for the get_model_comparison API wrapper."""

    def test_returns_not_available_without_data(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent_path_12345")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_model_comparison()
        assert result["status"] == "not_available"

    def test_returns_ok_with_data(self, monkeypatch) -> None:
        import tempfile

        from scoutfootball import api as api_module

        rng = np.random.default_rng(42)
        n = 100
        df = pd.DataFrame({
            "match_id": [f"m{i}" for i in range(n)],
            "home_win_probability": rng.uniform(0.2, 0.6, n),
            "draw_probability": rng.uniform(0.2, 0.3, n),
            "away_win_probability": rng.uniform(0.2, 0.5, n),
            "actual_outcome": rng.choice(["home_win", "draw", "away_win"], n),
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "calibration_backtest"
            tmp_path.mkdir()
            df.to_parquet(tmp_path / "poisson_backtest_predictions.parquet", index=False)

            monkeypatch.setattr(
                api_module, "_settings",
                lambda: type("S", (), {"report_root": Path(tmpdir)})(),
            )
            api_module._BACKTEST_CACHE.clear()
            result = api_module.get_model_comparison()
            assert result["status"] == "ok"
            assert len(result["models"]) == 1
            assert "brier" in result["metric_winners"]


# ---------------------------------------------------------------------------
# Score-line calibration API endpoint
# ---------------------------------------------------------------------------


class TestScorelineCalibrationAPI:
    """Tests for the get_scoreline_calibration API wrapper."""

    def test_returns_not_available_without_data(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent_path_12345")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_scoreline_calibration()
        assert result["status"] == "not_available"

    def test_returns_ok_with_data(self, monkeypatch) -> None:
        import tempfile

        from scoutfootball import api as api_module

        rng = np.random.default_rng(42)
        n = 100
        home_goals = rng.poisson(1.5, n)
        away_goals = rng.poisson(1.1, n)
        outcomes = np.where(
            home_goals > away_goals, "home_win",
            np.where(home_goals == away_goals, "draw", "away_win"),
        )
        df = pd.DataFrame({
            "home_goals": home_goals,
            "away_goals": away_goals,
            "home_win_probability": rng.uniform(0.2, 0.6, n),
            "draw_probability": rng.uniform(0.2, 0.3, n),
            "away_win_probability": rng.uniform(0.2, 0.5, n),
            "actual_outcome": outcomes,
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "calibration_backtest"
            tmp_path.mkdir()
            df.to_parquet(tmp_path / "dixon_coles_decay_backtest_predictions.parquet", index=False)

            monkeypatch.setattr(
                api_module, "_settings",
                lambda: type("S", (), {"report_root": Path(tmpdir)})(),
            )
            api_module._BACKTEST_CACHE.clear()
            result = api_module.get_scoreline_calibration()
            assert result["status"] == "ok"
            assert result["n_matches"] == 100
            assert len(result["entries"]) > 0


# ---------------------------------------------------------------------------
# Confidence distribution API endpoint
# ---------------------------------------------------------------------------


class TestConfidenceDistributionAPI:
    """Tests for the get_confidence_distribution API wrapper."""

    def test_returns_not_available_without_data(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent_path_12345")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_confidence_distribution()
        assert result["status"] == "not_available"

    def test_returns_ok_with_data(self, monkeypatch) -> None:
        import tempfile

        from scoutfootball import api as api_module

        rng = np.random.default_rng(42)
        n = 200
        df = pd.DataFrame({
            "home_win_probability": rng.uniform(0.2, 0.6, n),
            "draw_probability": rng.uniform(0.2, 0.3, n),
            "away_win_probability": rng.uniform(0.2, 0.5, n),
            "actual_outcome": rng.choice(["home_win", "draw", "away_win"], n),
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "calibration_backtest"
            tmp_path.mkdir()
            df.to_parquet(tmp_path / "poisson_backtest_predictions.parquet", index=False)

            monkeypatch.setattr(
                api_module, "_settings",
                lambda: type("S", (), {"report_root": Path(tmpdir)})(),
            )
            api_module._BACKTEST_CACHE.clear()
            result = api_module.get_confidence_distribution(n_bins=10, min_samples_per_bucket=1)
            assert result["status"] == "ok"
            assert result["n_predictions"] == 200
            assert len(result["buckets"]) > 0
            assert "overall_accuracy" in result
            assert "overall_confidence" in result


# ---------------------------------------------------------------------------
# H2H historical bias correction
# ---------------------------------------------------------------------------


class TestComputeH2HBiasCorrection:
    def test_no_correction_when_insufficient_meetings(self) -> None:
        baseline = {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}
        h2h = {"total_meetings": 2, "home_wins": 1, "draws": 1, "away_wins": 0}
        result = compute_h2h_bias_correction("A", "B", baseline, h2h, min_meetings=3)
        assert result.correction_applied is False
        assert result.corrected_probabilities == pytest.approx(baseline)
        assert result.n_meetings == 2

    def test_correction_applied_with_sufficient_meetings(self) -> None:
        baseline = {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}
        # H2H strongly favors away team
        h2h = {"total_meetings": 10, "home_wins": 1, "draws": 2, "away_wins": 7}
        result = compute_h2h_bias_correction(
            "A", "B", baseline, h2h, min_meetings=3, blend_weight=0.5,
        )
        assert result.correction_applied is True
        # Away win probability should increase
        assert result.corrected_probabilities["away_win"] > baseline["away_win"]
        # Home win probability should decrease
        assert result.corrected_probabilities["home_win"] < baseline["home_win"]

    def test_corrected_probabilities_sum_to_one(self) -> None:
        baseline = {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}
        h2h = {"total_meetings": 10, "home_wins": 5, "draws": 3, "away_wins": 2}
        result = compute_h2h_bias_correction("A", "B", baseline, h2h)
        total = sum(result.corrected_probabilities.values())
        assert total == pytest.approx(1.0, abs=1e-4)

    def test_h2h_rates_computed_correctly(self) -> None:
        baseline = {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}
        h2h = {"total_meetings": 10, "home_wins": 4, "draws": 3, "away_wins": 3}
        result = compute_h2h_bias_correction("A", "B", baseline, h2h)
        assert result.h2h_rates["home_win"] == pytest.approx(0.4, abs=1e-4)
        assert result.h2h_rates["draw"] == pytest.approx(0.3, abs=1e-4)
        assert result.h2h_rates["away_win"] == pytest.approx(0.3, abs=1e-4)

    def test_max_correction_bounds(self) -> None:
        baseline = {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}
        # Extreme H2H — all away wins
        h2h = {"total_meetings": 10, "home_wins": 0, "draws": 0, "away_wins": 10}
        result = compute_h2h_bias_correction(
            "A", "B", baseline, h2h, max_correction=0.05, blend_weight=1.0,
        )
        # Each adjustment should be within ±0.05 (before normalization)
        for adj in result.adjustments.values():
            assert abs(adj) <= 0.07  # allow small normalization drift

    def test_missing_baseline_keys_raises(self) -> None:
        h2h = {"total_meetings": 10, "home_wins": 5, "draws": 3, "away_wins": 2}
        with pytest.raises(ValueError, match="missing keys"):
            compute_h2h_bias_correction("A", "B", {"home_win": 0.5}, h2h)

    def test_baseline_not_summing_to_one_raises(self) -> None:
        h2h = {"total_meetings": 10, "home_wins": 5, "draws": 3, "away_wins": 2}
        with pytest.raises(ValueError, match="sum to ~1.0"):
            compute_h2h_bias_correction(
                "A", "B", {"home_win": 0.5, "draw": 0.3, "away_win": 0.5}, h2h,
            )

    def test_invalid_blend_weight_raises(self) -> None:
        baseline = {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}
        h2h = {"total_meetings": 10, "home_wins": 5, "draws": 3, "away_wins": 2}
        with pytest.raises(ValueError, match="blend_weight"):
            compute_h2h_bias_correction("A", "B", baseline, h2h, blend_weight=1.5)

    def test_zero_meetings_no_correction(self) -> None:
        baseline = {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}
        h2h = {"total_meetings": 0, "home_wins": 0, "draws": 0, "away_wins": 0}
        result = compute_h2h_bias_correction("A", "B", baseline, h2h)
        assert result.correction_applied is False
        assert result.n_meetings == 0

    def test_adjustments_equal_corrected_minus_baseline(self) -> None:
        baseline = {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}
        h2h = {"total_meetings": 10, "home_wins": 6, "draws": 2, "away_wins": 2}
        result = compute_h2h_bias_correction("A", "B", baseline, h2h, blend_weight=0.3)
        for key in ["home_win", "draw", "away_win"]:
            expected = result.corrected_probabilities[key] - result.baseline_probabilities[key]
            assert result.adjustments[key] == pytest.approx(expected, abs=1e-4)

    def test_disclaimer_present(self) -> None:
        baseline = {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}
        h2h = {"total_meetings": 10, "home_wins": 5, "draws": 3, "away_wins": 2}
        result = compute_h2h_bias_correction("A", "B", baseline, h2h)
        assert len(result.disclaimer) > 0


# ---------------------------------------------------------------------------
# Prediction error analysis
# ---------------------------------------------------------------------------


class TestComputeErrorAnalysis:
    def test_returns_buckets(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_error_analysis(df, n_bins=5, min_samples_per_bucket=5)
        assert isinstance(result.buckets, list)
        assert len(result.buckets) > 0

    def test_bucket_fields(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_error_analysis(df, n_bins=5, min_samples_per_bucket=5)
        for b in result.buckets:
            assert b.bucket_label is not None
            assert b.bucket_lower >= 0.0
            assert b.bucket_upper <= 1.0
            assert b.n_predictions > 0
            assert 0.0 <= b.accuracy <= 1.0
            assert b.avg_brier >= 0.0

    def test_overall_metrics(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_error_analysis(df, n_bins=5, min_samples_per_bucket=5)
        assert result.n_predictions == 200
        assert 0.0 <= result.overall_accuracy <= 1.0
        assert result.overall_avg_brier >= 0.0
        assert result.n_buckets > 0

    def test_min_samples_filter(self) -> None:
        df = _make_predictions_df(n=50)
        result = compute_error_analysis(df, n_bins=20, min_samples_per_bucket=100)
        assert len(result.buckets) == 0

    def test_invalid_n_bins_raises(self) -> None:
        df = _make_predictions_df(n=50)
        with pytest.raises(ValueError, match="n_bins"):
            compute_error_analysis(df, n_bins=1)

    def test_invalid_top_n_raises(self) -> None:
        df = _make_predictions_df(n=50)
        with pytest.raises(ValueError, match="top_n"):
            compute_error_analysis(df, top_n=0)

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"foo": [1, 2, 3]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_error_analysis(df)

    def test_worst_matches_present(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_error_analysis(df, n_bins=5, min_samples_per_bucket=5, top_n=3)
        for b in result.buckets:
            assert len(b.worst_matches) <= 3
        assert len(result.worst_matches_overall) <= 3

    def test_worst_match_fields(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_error_analysis(df, n_bins=5, min_samples_per_bucket=5, top_n=2)
        for b in result.buckets:
            for m in b.worst_matches:
                assert m.actual_outcome in ("home_win", "draw", "away_win")
                assert 0.0 <= m.confidence <= 1.0
                assert m.brier >= 0.0
                assert isinstance(m.correct, bool)

    def test_log_loss_none_without_exact_score(self) -> None:
        df = _make_predictions_df(n=100)
        # No exact_score_probability column
        result = compute_error_analysis(df, n_bins=5, min_samples_per_bucket=5)
        assert result.overall_avg_log_loss is None
        for b in result.buckets:
            assert b.avg_log_loss is None

    def test_log_loss_computed_with_exact_score(self) -> None:
        df = _make_predictions_df(n=100)
        rng = np.random.default_rng(42)
        df["exact_score_probability"] = rng.uniform(0.01, 0.1, len(df))
        result = compute_error_analysis(df, n_bins=5, min_samples_per_bucket=5)
        assert result.overall_avg_log_loss is not None
        assert result.overall_avg_log_loss > 0.0

    def test_worst_matches_sorted_by_brier_desc(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_error_analysis(df, n_bins=5, min_samples_per_bucket=5, top_n=5)
        for b in result.buckets:
            briars = [m.brier for m in b.worst_matches]
            assert briars == sorted(briars, reverse=True)


# ---------------------------------------------------------------------------
# Outcome distribution analysis
# ---------------------------------------------------------------------------


class TestComputeOutcomeDistribution:
    def test_returns_entries(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_outcome_distribution(df)
        assert len(result.entries) == 3

    def test_entry_fields(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_outcome_distribution(df)
        for e in result.entries:
            assert e.outcome in ("home_win", "draw", "away_win")
            assert e.predicted_count >= 0
            assert e.actual_count >= 0
            assert 0.0 <= e.predicted_share <= 1.0
            assert 0.0 <= e.actual_share <= 1.0

    def test_predicted_plus_actual_counts_match_total(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_outcome_distribution(df)
        total_pred = sum(e.predicted_count for e in result.entries)
        total_actual = sum(e.actual_count for e in result.entries)
        assert total_pred == 200
        assert total_actual == 200

    def test_shares_sum_to_one(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_outcome_distribution(df)
        pred_share_sum = sum(e.predicted_share for e in result.entries)
        actual_share_sum = sum(e.actual_share for e in result.entries)
        assert pred_share_sum == pytest.approx(1.0, abs=1e-4)
        assert actual_share_sum == pytest.approx(1.0, abs=1e-4)

    def test_distribution_gap_equals_pred_minus_actual(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_outcome_distribution(df)
        for e in result.entries:
            expected = e.predicted_share - e.actual_share
            assert e.distribution_gap == pytest.approx(expected, abs=1e-4)

    def test_dominant_bias_identified(self) -> None:
        # Construct a model that always predicts home_win
        df = pd.DataFrame({
            "home_win_probability": [0.5] * 100,
            "draw_probability": [0.3] * 100,
            "away_win_probability": [0.2] * 100,
            "actual_outcome": ["home_win"] * 30 + ["draw"] * 30 + ["away_win"] * 40,
        })
        result = compute_outcome_distribution(df)
        # Model predicts home_win 100% of the time, but actual home_win is only 30%
        assert (
            "over_predicts_home_win" in result.dominant_bias
            or "under_predicts" in result.dominant_bias
        )

    def test_no_bias_when_perfect(self) -> None:
        df = pd.DataFrame({
            "home_win_probability": [0.6, 0.2, 0.2] * 30,
            "draw_probability": [0.2, 0.6, 0.2] * 30,
            "away_win_probability": [0.2, 0.2, 0.6] * 30,
            "actual_outcome": ["home_win", "draw", "away_win"] * 30,
        })
        result = compute_outcome_distribution(df)
        # Each outcome predicted 30 times, actual 30 times — gap is 0
        assert result.dominant_bias == "none"

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"foo": [1, 2, 3]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_outcome_distribution(df)

    def test_empty_dataframe_returns_zero(self) -> None:
        df = pd.DataFrame({
            "home_win_probability": [],
            "draw_probability": [],
            "away_win_probability": [],
            "actual_outcome": [],
        })
        result = compute_outcome_distribution(df)
        assert result.n_predictions == 0
        assert result.dominant_bias == "none"

    def test_disclaimer_present(self) -> None:
        df = _make_predictions_df(n=50)
        result = compute_outcome_distribution(df)
        assert len(result.disclaimer) > 0


# ---------------------------------------------------------------------------
# API: H2H bias correction, error analysis, outcome distribution
# ---------------------------------------------------------------------------


class TestH2HBiasCorrectionAPI:
    def test_no_data_returns_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        def _fake_dc_prediction(home, away):
            return {"status": "not_available"}

        monkeypatch.setattr(api_module, "get_match_prediction_dc", _fake_dc_prediction)
        result = api_module.get_h2h_bias_correction("UnknownA", "UnknownB")
        assert result["status"] == "not_available"


class TestErrorAnalysisAPI:
    def test_no_data_returns_not_available(self, monkeypatch) -> None:
        import tempfile

        from scoutfootball import api as api_module

        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr(
                api_module, "_settings",
                lambda: type("S", (), {"report_root": Path(tmpdir)})(),
            )
            api_module._BACKTEST_CACHE.clear()
            result = api_module.get_error_analysis()
            assert result["status"] == "not_available"

    def test_with_data_returns_ok(self, monkeypatch) -> None:
        import tempfile

        from scoutfootball import api as api_module

        rng = np.random.default_rng(42)
        n = 200
        df = pd.DataFrame({
            "home_win_probability": rng.uniform(0.2, 0.6, n),
            "draw_probability": rng.uniform(0.2, 0.3, n),
            "away_win_probability": rng.uniform(0.2, 0.5, n),
            "actual_outcome": rng.choice(["home_win", "draw", "away_win"], n),
            "home_goals": rng.poisson(1.5, n),
            "away_goals": rng.poisson(1.1, n),
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "calibration_backtest"
            tmp_path.mkdir()
            df.to_parquet(tmp_path / "poisson_backtest_predictions.parquet", index=False)

            monkeypatch.setattr(
                api_module, "_settings",
                lambda: type("S", (), {"report_root": Path(tmpdir)})(),
            )
            api_module._BACKTEST_CACHE.clear()
            result = api_module.get_error_analysis(n_bins=5, min_samples_per_bucket=5, top_n=3)
            assert result["status"] == "ok"
            assert result["n_predictions"] == 200
            assert len(result["buckets"]) > 0
            assert "overall_accuracy" in result
            assert "worst_matches_overall" in result


class TestOutcomeDistributionAPI:
    def test_no_data_returns_not_available(self, monkeypatch) -> None:
        import tempfile

        from scoutfootball import api as api_module

        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr(
                api_module, "_settings",
                lambda: type("S", (), {"report_root": Path(tmpdir)})(),
            )
            api_module._BACKTEST_CACHE.clear()
            result = api_module.get_outcome_distribution()
            assert result["status"] == "not_available"

    def test_with_data_returns_ok(self, monkeypatch) -> None:
        import tempfile

        from scoutfootball import api as api_module

        rng = np.random.default_rng(42)
        n = 200
        df = pd.DataFrame({
            "home_win_probability": rng.uniform(0.2, 0.6, n),
            "draw_probability": rng.uniform(0.2, 0.3, n),
            "away_win_probability": rng.uniform(0.2, 0.5, n),
            "actual_outcome": rng.choice(["home_win", "draw", "away_win"], n),
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "calibration_backtest"
            tmp_path.mkdir()
            df.to_parquet(tmp_path / "poisson_backtest_predictions.parquet", index=False)

            monkeypatch.setattr(
                api_module, "_settings",
                lambda: type("S", (), {"report_root": Path(tmpdir)})(),
            )
            api_module._BACKTEST_CACHE.clear()
            result = api_module.get_outcome_distribution()
            assert result["status"] == "ok"
            assert result["n_predictions"] == 200
            assert len(result["entries"]) == 3
            assert "dominant_bias" in result


# ---------------------------------------------------------------------------
# Temporal validation backtest
# ---------------------------------------------------------------------------


class TestComputeTemporalValidation:
    def test_returns_windows(self) -> None:
        df = _make_predictions_df(n=200)
        df["match_date"] = pd.date_range("2022-01-01", periods=200, freq="D")
        result = compute_temporal_validation(df, n_windows=4)
        assert len(result.windows) == 4
        assert result.n_windows == 4

    def test_window_fields(self) -> None:
        df = _make_predictions_df(n=200)
        df["match_date"] = pd.date_range("2022-01-01", periods=200, freq="D")
        result = compute_temporal_validation(df, n_windows=4)
        for w in result.windows:
            assert isinstance(w.window_label, str)
            assert isinstance(w.n_matches, int)
            assert isinstance(w.accuracy, float)
            assert isinstance(w.brier, float)
            assert isinstance(w.rps, float)
            assert isinstance(w.avg_confidence, float)

    def test_overall_metrics(self) -> None:
        df = _make_predictions_df(n=200)
        df["match_date"] = pd.date_range("2022-01-01", periods=200, freq="D")
        result = compute_temporal_validation(df, n_windows=4)
        assert result.n_total_matches == 200
        assert 0.0 <= result.overall_accuracy <= 1.0
        assert result.overall_brier >= 0.0
        assert result.overall_rps >= 0.0

    def test_trend_value(self) -> None:
        df = _make_predictions_df(n=200)
        df["match_date"] = pd.date_range("2022-01-01", periods=200, freq="D")
        result = compute_temporal_validation(df, n_windows=4)
        assert result.trend in ("improving", "degrading", "stable", "insufficient_data")

    def test_invalid_n_windows_low_raises(self) -> None:
        df = _make_predictions_df(n=100)
        with pytest.raises(ValueError, match="n_windows must be between"):
            compute_temporal_validation(df, n_windows=1)

    def test_invalid_n_windows_high_raises(self) -> None:
        df = _make_predictions_df(n=100)
        with pytest.raises(ValueError, match="n_windows must be between"):
            compute_temporal_validation(df, n_windows=21)

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"match_date": pd.date_range("2022-01-01", periods=50)})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_temporal_validation(df)

    def test_insufficient_data_returns_empty_windows(self) -> None:
        df = _make_predictions_df(n=10)
        df["match_date"] = pd.date_range("2022-01-01", periods=10, freq="D")
        result = compute_temporal_validation(
            df, n_windows=6, min_samples_per_window=10,
        )
        assert result.trend == "insufficient_data"
        assert result.n_windows == 0

    def test_log_loss_none_without_exact_score(self) -> None:
        df = _make_predictions_df(n=200)
        df["match_date"] = pd.date_range("2022-01-01", periods=200, freq="D")
        df = df.drop(columns=["exact_score_probability"], errors="ignore")
        result = compute_temporal_validation(df, n_windows=4)
        assert result.overall_log_loss is None
        for w in result.windows:
            assert w.log_loss is None

    def test_log_loss_computed_with_exact_score(self) -> None:
        df = _make_predictions_df(n=200)
        df["match_date"] = pd.date_range("2022-01-01", periods=200, freq="D")
        df["exact_score_probability"] = np.random.uniform(0.01, 0.1, 200)
        result = compute_temporal_validation(df, n_windows=4)
        assert result.overall_log_loss is not None
        assert result.overall_log_loss > 0.0

    def test_disclaimer_present(self) -> None:
        df = _make_predictions_df(n=200)
        df["match_date"] = pd.date_range("2022-01-01", periods=200, freq="D")
        result = compute_temporal_validation(df, n_windows=4)
        assert isinstance(result.disclaimer, str)
        assert len(result.disclaimer) > 0

    def test_windows_sorted_chronologically(self) -> None:
        df = _make_predictions_df(n=200)
        df["match_date"] = pd.date_range("2022-01-01", periods=200, freq="D")
        result = compute_temporal_validation(df, n_windows=4)
        starts = [w.window_start for w in result.windows if w.window_start]
        assert starts == sorted(starts)


# ---------------------------------------------------------------------------
# Probability heatmap
# ---------------------------------------------------------------------------


class TestComputeProbabilityHeatmap:
    def test_returns_cells(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_probability_heatmap(df, n_bins=5)
        assert isinstance(result.cells, list)
        assert len(result.cells) > 0

    def test_cell_fields(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_probability_heatmap(df, n_bins=5)
        for c in result.cells:
            assert isinstance(c.home_bin, str)
            assert isinstance(c.away_bin, str)
            assert isinstance(c.count, int)
            assert isinstance(c.density, float)
            assert isinstance(c.accuracy, float)
            assert isinstance(c.avg_confidence, float)

    def test_n_predictions_matches(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_probability_heatmap(df, n_bins=5)
        assert result.n_predictions == 200

    def test_density_sum_leq_one(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_probability_heatmap(df, n_bins=5, min_samples_per_cell=1)
        assert result.total_density <= 1.0 + 1e-6

    def test_min_samples_filter(self) -> None:
        df = _make_predictions_df(n=50)
        result_low = compute_probability_heatmap(df, n_bins=5, min_samples_per_cell=1)
        result_high = compute_probability_heatmap(df, n_bins=5, min_samples_per_cell=10)
        assert len(result_low.cells) >= len(result_high.cells)

    def test_invalid_n_bins_low_raises(self) -> None:
        df = _make_predictions_df(n=100)
        with pytest.raises(ValueError, match="n_bins must be between"):
            compute_probability_heatmap(df, n_bins=1)

    def test_invalid_n_bins_high_raises(self) -> None:
        df = _make_predictions_df(n=100)
        with pytest.raises(ValueError, match="n_bins must be between"):
            compute_probability_heatmap(df, n_bins=16)

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"match_date": pd.date_range("2022-01-01", periods=50)})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_probability_heatmap(df)

    def test_empty_df_returns_empty_cells(self) -> None:
        df = pd.DataFrame({
            "home_win_probability": [],
            "draw_probability": [],
            "away_win_probability": [],
            "actual_outcome": [],
        })
        result = compute_probability_heatmap(df, n_bins=5)
        assert result.cells == []
        assert result.n_predictions == 0

    def test_disclaimer_present(self) -> None:
        df = _make_predictions_df(n=200)
        result = compute_probability_heatmap(df, n_bins=5)
        assert isinstance(result.disclaimer, str)
        assert len(result.disclaimer) > 0


# ---------------------------------------------------------------------------
# Prediction staleness
# ---------------------------------------------------------------------------


class TestComputePredictionStaleness:
    def test_returns_staleness(self) -> None:
        df = _make_predictions_df(n=50)
        df["match_date"] = pd.date_range("2022-01-01", periods=50, freq="D")
        result = compute_prediction_staleness(df)
        assert result.has_backtest is True
        assert result.staleness_level in ("fresh", "aging", "stale")

    def test_backtest_dates(self) -> None:
        df = _make_predictions_df(n=50)
        df["match_date"] = pd.date_range("2022-01-01", periods=50, freq="D")
        result = compute_prediction_staleness(df, reference_date="2022-03-01")
        assert result.backtest_start == "2022-01-01"
        assert result.backtest_end == "2022-02-19"

    def test_days_since(self) -> None:
        df = _make_predictions_df(n=50)
        df["match_date"] = pd.date_range("2022-01-01", periods=50, freq="D")
        result = compute_prediction_staleness(df, reference_date="2022-03-01")
        assert result.days_since_backtest_end is not None
        assert result.days_since_backtest_end >= 0

    def test_fresh_level(self) -> None:
        df = _make_predictions_df(n=50)
        df["match_date"] = pd.date_range("2022-01-01", periods=50, freq="D")
        result = compute_prediction_staleness(df, reference_date="2022-02-25")
        assert result.staleness_level == "fresh"

    def test_aging_level(self) -> None:
        df = _make_predictions_df(n=50)
        df["match_date"] = pd.date_range("2022-01-01", periods=50, freq="D")
        result = compute_prediction_staleness(df, reference_date="2022-05-01")
        assert result.staleness_level == "aging"

    def test_stale_level(self) -> None:
        df = _make_predictions_df(n=50)
        df["match_date"] = pd.date_range("2022-01-01", periods=50, freq="D")
        result = compute_prediction_staleness(df, reference_date="2023-01-01")
        assert result.staleness_level == "stale"

    def test_model_type(self) -> None:
        df = _make_predictions_df(n=50)
        df["match_date"] = pd.date_range("2022-01-01", periods=50, freq="D")
        result = compute_prediction_staleness(df, model_type="poisson")
        assert result.model_type == "poisson"

    def test_missing_match_date_raises(self) -> None:
        df = _make_predictions_df(n=50)
        with pytest.raises(ValueError, match="missing required column"):
            compute_prediction_staleness(df)

    def test_empty_df_returns_empty_level(self) -> None:
        df = pd.DataFrame({"match_date": []})
        result = compute_prediction_staleness(df)
        assert result.has_backtest is False
        assert result.staleness_level == "empty"
        assert result.n_backtest_matches == 0

    def test_disclaimer_present(self) -> None:
        df = _make_predictions_df(n=50)
        df["match_date"] = pd.date_range("2022-01-01", periods=50, freq="D")
        result = compute_prediction_staleness(df)
        assert isinstance(result.disclaimer, str)
        assert len(result.disclaimer) > 0


# ---------------------------------------------------------------------------
# API tests for temporal validation, heatmap, staleness
# ---------------------------------------------------------------------------


class TestTemporalValidationAPI:
    def test_no_data_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_temporal_validation()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=200)
        df["match_date"] = pd.date_range("2022-01-01", periods=200, freq="D")
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet", index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_temporal_validation(n_windows=4)
        assert result["status"] == "ok"
        assert result["n_windows"] == 4
        assert len(result["windows"]) == 4


class TestProbabilityHeatmapAPI:
    def test_no_data_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_probability_heatmap()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=200)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet", index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_probability_heatmap(n_bins=5)
        assert result["status"] == "ok"
        assert result["n_predictions"] == 200
        assert result["n_bins"] == 5
        assert len(result["cells"]) > 0


class TestPredictionStalenessAPI:
    def test_no_data_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_prediction_staleness()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=100)
        df["match_date"] = pd.date_range("2022-01-01", periods=100, freq="D")
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet", index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_prediction_staleness()
        assert result["status"] == "ok"
        assert result["has_backtest"] is True
        assert result["staleness_level"] in ("fresh", "aging", "stale")
        assert result["model_type"] == "dixon_coles_decay"

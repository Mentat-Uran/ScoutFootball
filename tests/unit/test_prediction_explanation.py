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
    compute_calibration_drift_heatmap,
    compute_ci_coverage,
    compute_ci_width_analysis,
    compute_confidence_distribution,
    compute_confidence_interval_plot,
    compute_data_drift,
    compute_error_analysis,
    compute_error_clustering,
    compute_feature_importance,
    compute_fold_comparison,
    compute_h2h_bias_correction,
    compute_league_error_analysis,
    compute_model_comparison,
    compute_outcome_distribution,
    compute_prediction_staleness,
    compute_prediction_uncertainty,
    compute_probability_heatmap,
    compute_reliability_diagram,
    compute_scenario_stress_test,
    compute_scoreline_calibration,
    compute_team_accuracy,
    compute_team_calibration_drift,
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


# ---------------------------------------------------------------------------
# Confidence interval plot (CI width vs confidence scatter)
# ---------------------------------------------------------------------------


def _make_ci_predictions_df(n: int = 200) -> pd.DataFrame:
    """Create synthetic predictions DataFrame with CI columns for CI plot."""
    rng = np.random.default_rng(42)
    home_win_prob = rng.uniform(0.2, 0.7, n)
    draw_prob = rng.uniform(0.2, 0.3, n)
    away_win_prob = 1.0 - home_win_prob - draw_prob
    away_win_prob = np.clip(away_win_prob, 0.05, 0.9)
    total = home_win_prob + draw_prob + away_win_prob
    home_win_prob /= total
    draw_prob /= total
    away_win_prob /= total
    # CI bounds around home_win_probability
    ci_width = rng.uniform(0.05, 0.30, n)
    ci_lower = np.clip(home_win_prob - ci_width / 2, 0.0, 1.0)
    ci_upper = np.clip(home_win_prob + ci_width / 2, 0.0, 1.0)
    outcomes = rng.choice(["home_win", "draw", "away_win"], n, p=[0.45, 0.28, 0.27])
    df = pd.DataFrame({
        "home_win_probability": home_win_prob,
        "draw_probability": draw_prob,
        "away_win_probability": away_win_prob,
        "home_win_ci_lower": ci_lower,
        "home_win_ci_upper": ci_upper,
        "actual_outcome": outcomes,
        "match_id": [f"m{i}" for i in range(n)],
        "home_team": [f"team_{i % 5}" for i in range(n)],
        "away_team": [f"team_{(i + 1) % 5}" for i in range(n)],
    })
    return df


class TestComputeConfidenceIntervalPlot:
    def test_returns_points(self) -> None:
        df = _make_ci_predictions_df(n=200)
        result = compute_confidence_interval_plot(df)
        assert len(result.points) > 0
        assert result.n_predictions > 0

    def test_point_fields(self) -> None:
        df = _make_ci_predictions_df(n=50)
        result = compute_confidence_interval_plot(df)
        for p in result.points:
            assert p.confidence >= 0.0
            assert p.ci_lower <= p.ci_upper
            assert p.ci_width >= 0.0
            assert p.actual_outcome in ("home_win", "draw", "away_win")
            assert isinstance(p.correct, bool)

    def test_n_predictions_matches_points(self) -> None:
        df = _make_ci_predictions_df(n=80)
        result = compute_confidence_interval_plot(df)
        assert result.n_predictions == len(result.points)

    def test_avg_confidence_in_range(self) -> None:
        df = _make_ci_predictions_df(n=100)
        result = compute_confidence_interval_plot(df)
        assert 0.0 <= result.avg_confidence <= 1.0

    def test_avg_ci_width_nonneg(self) -> None:
        df = _make_ci_predictions_df(n=100)
        result = compute_confidence_interval_plot(df)
        assert result.avg_ci_width >= 0.0

    def test_correlation_present(self) -> None:
        df = _make_ci_predictions_df(n=100)
        result = compute_confidence_interval_plot(df)
        assert result.correlation is not None
        assert -1.0 <= result.correlation <= 1.0

    def test_max_points_subsamples(self) -> None:
        df = _make_ci_predictions_df(n=200)
        result = compute_confidence_interval_plot(df, max_points=50)
        assert result.n_predictions == 50
        assert len(result.points) == 50

    def test_missing_ci_columns_raises(self) -> None:
        df = _make_predictions_df(n=50)
        with pytest.raises(ValueError, match="missing required columns"):
            compute_confidence_interval_plot(df)

    def test_missing_prob_columns_raises(self) -> None:
        df = pd.DataFrame({"home_win_ci_lower": [0.1], "home_win_ci_upper": [0.3]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_confidence_interval_plot(df)

    def test_empty_df_returns_empty(self) -> None:
        df = pd.DataFrame({
            "home_win_probability": [],
            "draw_probability": [],
            "away_win_probability": [],
            "home_win_ci_lower": [],
            "home_win_ci_upper": [],
        })
        result = compute_confidence_interval_plot(df)
        assert result.n_predictions == 0
        assert result.points == []
        assert result.correlation is None

    def test_disclaimer_present(self) -> None:
        df = _make_ci_predictions_df(n=50)
        result = compute_confidence_interval_plot(df)
        assert len(result.disclaimer) > 0

    def test_custom_ci_columns(self) -> None:
        df = _make_ci_predictions_df(n=50)
        df = df.rename(columns={
            "home_win_ci_lower": "hw_lo",
            "home_win_ci_upper": "hw_hi",
        })
        result = compute_confidence_interval_plot(
            df, ci_lower_col="hw_lo", ci_upper_col="hw_hi",
        )
        assert result.n_predictions > 0


# ---------------------------------------------------------------------------
# Fold comparison (per-fold metrics + stability)
# ---------------------------------------------------------------------------


def _make_fold_predictions_df(n: int = 200, n_folds: int = 5) -> pd.DataFrame:
    """Create synthetic predictions DataFrame with a fold column."""
    rng = np.random.default_rng(42)
    home_win_prob = rng.uniform(0.2, 0.7, n)
    draw_prob = rng.uniform(0.2, 0.3, n)
    away_win_prob = 1.0 - home_win_prob - draw_prob
    away_win_prob = np.clip(away_win_prob, 0.05, 0.9)
    total = home_win_prob + draw_prob + away_win_prob
    home_win_prob /= total
    draw_prob /= total
    away_win_prob /= total
    outcomes = rng.choice(["home_win", "draw", "away_win"], n, p=[0.45, 0.28, 0.27])
    df = pd.DataFrame({
        "home_win_probability": home_win_prob,
        "draw_probability": draw_prob,
        "away_win_probability": away_win_prob,
        "actual_outcome": outcomes,
        "fold": np.tile(np.arange(n_folds), n // n_folds + 1)[:n],
    })
    return df


class TestComputeFoldComparison:
    def test_returns_folds(self) -> None:
        df = _make_fold_predictions_df(n=200, n_folds=5)
        result = compute_fold_comparison(df)
        assert len(result.folds) > 0
        assert result.n_folds > 0

    def test_fold_fields(self) -> None:
        df = _make_fold_predictions_df(n=100, n_folds=5)
        result = compute_fold_comparison(df)
        for f in result.folds:
            assert f.fold >= 0
            assert f.n_matches > 0
            assert 0.0 <= f.accuracy <= 1.0
            assert f.brier >= 0.0
            assert f.rps >= 0.0
            assert 0.0 <= f.avg_confidence <= 1.0

    def test_n_total_matches(self) -> None:
        df = _make_fold_predictions_df(n=100, n_folds=5)
        result = compute_fold_comparison(df)
        assert result.n_total_matches == sum(f.n_matches for f in result.folds)

    def test_stability_value(self) -> None:
        df = _make_fold_predictions_df(n=200, n_folds=5)
        result = compute_fold_comparison(df)
        assert result.stability in ("stable", "moderate", "unstable")

    def test_std_nonneg(self) -> None:
        df = _make_fold_predictions_df(n=200, n_folds=5)
        result = compute_fold_comparison(df)
        assert result.accuracy_std >= 0.0
        assert result.brier_std >= 0.0
        assert result.rps_std >= 0.0

    def test_min_samples_filter(self) -> None:
        df = _make_fold_predictions_df(n=100, n_folds=5)
        # Each fold has 20 samples; raising min_samples filters all out
        result = compute_fold_comparison(df, min_samples_per_fold=50)
        assert result.n_folds == 0
        assert result.stability == "insufficient_data"

    def test_missing_fold_column_raises(self) -> None:
        df = _make_predictions_df(n=50)
        with pytest.raises(ValueError, match="missing required columns"):
            compute_fold_comparison(df)

    def test_missing_prob_columns_raises(self) -> None:
        df = pd.DataFrame({"fold": [0, 1, 2]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_fold_comparison(df)

    def test_log_loss_none_without_exact_score(self) -> None:
        df = _make_fold_predictions_df(n=100, n_folds=5)
        result = compute_fold_comparison(df)
        for f in result.folds:
            assert f.log_loss is None
        assert result.overall_log_loss is None

    def test_log_loss_computed_with_exact_score(self) -> None:
        df = _make_fold_predictions_df(n=100, n_folds=5)
        df["exact_score_probability"] = np.full(100, 0.05)
        result = compute_fold_comparison(df)
        for f in result.folds:
            assert f.log_loss is not None
            assert f.log_loss > 0.0
        assert result.overall_log_loss is not None

    def test_disclaimer_present(self) -> None:
        df = _make_fold_predictions_df(n=100, n_folds=5)
        result = compute_fold_comparison(df)
        assert len(result.disclaimer) > 0

    def test_overall_metrics_in_range(self) -> None:
        df = _make_fold_predictions_df(n=200, n_folds=5)
        result = compute_fold_comparison(df)
        assert 0.0 <= result.overall_accuracy <= 1.0
        assert result.overall_brier >= 0.0


# ---------------------------------------------------------------------------
# Per-league error analysis
# ---------------------------------------------------------------------------


def _make_league_predictions_df(n: int = 200) -> pd.DataFrame:
    """Create synthetic predictions DataFrame with a league column."""
    df = _make_predictions_df(n=n)
    # Two leagues with enough samples each
    df["league"] = np.where(np.arange(n) < n // 2, "Premier", "La Liga")
    df["match_id"] = [f"m{i}" for i in range(n)]
    return df


class TestComputeLeagueErrorAnalysis:
    def test_returns_leagues(self) -> None:
        df = _make_league_predictions_df(n=200)
        result = compute_league_error_analysis(df)
        assert len(result.leagues) > 0
        assert result.n_leagues > 0

    def test_league_fields(self) -> None:
        df = _make_league_predictions_df(n=200)
        result = compute_league_error_analysis(df)
        for lg in result.leagues:
            assert len(lg.league) > 0
            assert lg.n_matches > 0
            assert 0.0 <= lg.accuracy <= 1.0
            assert lg.brier >= 0.0
            assert lg.rps >= 0.0
            assert 0.0 <= lg.avg_confidence <= 1.0

    def test_n_total_matches(self) -> None:
        df = _make_league_predictions_df(n=200)
        result = compute_league_error_analysis(df)
        assert result.n_total_matches == sum(lg.n_matches for lg in result.leagues)

    def test_min_matches_filter(self) -> None:
        df = _make_league_predictions_df(n=100)
        # Each league has 50; raising min to 100 filters all out
        result = compute_league_error_analysis(df, min_matches_per_league=100)
        assert result.n_leagues == 0
        assert result.n_total_matches == 0

    def test_top_n_limits_worst_matches(self) -> None:
        df = _make_league_predictions_df(n=200)
        result = compute_league_error_analysis(df, top_n=2)
        for lg in result.leagues:
            assert len(lg.worst_matches) <= 2

    def test_worst_matches_sorted_by_brier_desc(self) -> None:
        df = _make_league_predictions_df(n=200)
        result = compute_league_error_analysis(df, top_n=5)
        for lg in result.leagues:
            briars = [m.brier for m in lg.worst_matches]
            assert briars == sorted(briars, reverse=True)

    def test_worst_match_fields(self) -> None:
        df = _make_league_predictions_df(n=200)
        result = compute_league_error_analysis(df, top_n=3)
        for lg in result.leagues:
            for m in lg.worst_matches:
                assert m.actual_outcome in ("home_win", "draw", "away_win")
                assert m.predicted_outcome in ("home_win", "draw", "away_win")
                assert 0.0 <= m.predicted_home_win <= 1.0
                assert 0.0 <= m.predicted_draw <= 1.0
                assert 0.0 <= m.predicted_away_win <= 1.0
                assert 0.0 <= m.confidence <= 1.0
                assert m.brier >= 0.0
                assert isinstance(m.correct, bool)

    def test_missing_league_column_raises(self) -> None:
        df = _make_predictions_df(n=50)
        with pytest.raises(ValueError, match="missing required columns"):
            compute_league_error_analysis(df)

    def test_missing_prob_columns_raises(self) -> None:
        df = pd.DataFrame({"league": ["A", "B"]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_league_error_analysis(df)

    def test_log_loss_none_without_exact_score(self) -> None:
        df = _make_league_predictions_df(n=200)
        result = compute_league_error_analysis(df)
        for lg in result.leagues:
            assert lg.log_loss is None

    def test_log_loss_computed_with_exact_score(self) -> None:
        df = _make_league_predictions_df(n=200)
        df["exact_score_probability"] = np.full(200, 0.05)
        result = compute_league_error_analysis(df)
        for lg in result.leagues:
            assert lg.log_loss is not None
            assert lg.log_loss > 0.0

    def test_leagues_sorted_by_n_matches_desc(self) -> None:
        df = _make_league_predictions_df(n=200)
        # Make one league bigger
        df.loc[df.index[:120], "league"] = "Big"
        df.loc[df.index[120:], "league"] = "Small"
        result = compute_league_error_analysis(df, min_matches_per_league=10)
        n_matches_list = [lg.n_matches for lg in result.leagues]
        assert n_matches_list == sorted(n_matches_list, reverse=True)

    def test_disclaimer_present(self) -> None:
        df = _make_league_predictions_df(n=100)
        result = compute_league_error_analysis(df)
        assert len(result.disclaimer) > 0

    def test_overall_metrics_in_range(self) -> None:
        df = _make_league_predictions_df(n=200)
        result = compute_league_error_analysis(df)
        assert 0.0 <= result.overall_accuracy <= 1.0
        assert result.overall_brier >= 0.0


# ---------------------------------------------------------------------------
# API: CI plot, fold comparison, league error analysis
# ---------------------------------------------------------------------------


class TestConfidenceIntervalPlotAPI:
    def test_no_data_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_confidence_interval_plot()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_ci_predictions_df(n=80)
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
        result = api_module.get_confidence_interval_plot()
        assert result["status"] == "ok"
        assert result["n_predictions"] > 0
        assert "points" in result
        assert "correlation" in result

    def test_with_data_no_ci_columns(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=80)  # No CI columns
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
        result = api_module.get_confidence_interval_plot()
        assert result["status"] == "not_available"


class TestFoldComparisonAPI:
    def test_no_data_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_fold_comparison()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_fold_predictions_df(n=100, n_folds=5)
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
        result = api_module.get_fold_comparison()
        assert result["status"] == "ok"
        assert result["n_folds"] > 0
        assert "folds" in result
        assert "stability" in result

    def test_with_data_no_fold_column(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=80)  # No fold column
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
        result = api_module.get_fold_comparison()
        assert result["status"] == "not_available"


class TestLeagueErrorAnalysisAPI:
    def test_no_data_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_league_error_analysis()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_league_predictions_df(n=100)
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
        result = api_module.get_league_error_analysis()
        assert result["status"] == "ok"
        assert result["n_leagues"] > 0
        assert "leagues" in result
        assert "overall_accuracy" in result

    def test_with_data_no_league_column(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=80)  # No league column
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
        result = api_module.get_league_error_analysis()
        assert result["status"] == "not_available"


# ---------------------------------------------------------------------------
# Feature importance ranking
# ---------------------------------------------------------------------------


def _make_feature_predictions_df(n: int = 200) -> pd.DataFrame:
    """Create predictions DataFrame with synthetic numeric feature columns."""
    rng = np.random.default_rng(42)
    df = _make_predictions_df(n=n)
    # Add two numeric features; feature_a should be more important (correlated
    # with error), feature_b is noise.
    df["feature_a"] = rng.uniform(0.0, 10.0, n)
    df["feature_b"] = rng.normal(50.0, 5.0, n)
    df["match_id"] = [f"m{i}" for i in range(n)]
    return df


class TestComputeFeatureImportance:
    def test_returns_features(self) -> None:
        df = _make_feature_predictions_df(n=200)
        result = compute_feature_importance(df)
        assert result.n_features > 0
        assert len(result.features) > 0

    def test_feature_fields(self) -> None:
        df = _make_feature_predictions_df(n=200)
        result = compute_feature_importance(df)
        for fe in result.features:
            assert len(fe.feature) > 0
            assert fe.importance >= 0.0
            assert fe.n_matches > 0
            assert len(fe.bins) > 0

    def test_bin_fields(self) -> None:
        df = _make_feature_predictions_df(n=200)
        result = compute_feature_importance(df)
        for fe in result.features:
            for b in fe.bins:
                assert len(b.bin_label) > 0
                assert b.bin_lower <= b.bin_upper
                assert b.n_matches > 0
                assert 0.0 <= b.accuracy <= 1.0
                assert b.brier >= 0.0
                assert 0.0 <= b.avg_confidence <= 1.0

    def test_features_sorted_by_importance_desc(self) -> None:
        df = _make_feature_predictions_df(n=200)
        result = compute_feature_importance(df)
        importances = [fe.importance for fe in result.features]
        assert importances == sorted(importances, reverse=True)

    def test_n_total_matches(self) -> None:
        df = _make_feature_predictions_df(n=200)
        result = compute_feature_importance(df)
        assert result.n_total_matches == sum(fe.n_matches for fe in result.features)

    def test_overall_brier_nonneg(self) -> None:
        df = _make_feature_predictions_df(n=200)
        result = compute_feature_importance(df)
        assert result.overall_brier >= 0.0

    def test_min_samples_filter(self) -> None:
        df = _make_feature_predictions_df(n=30)
        # With min_samples_per_bin=20 and only 30 rows, no feature should pass
        result = compute_feature_importance(df, min_samples_per_bin=20, n_bins=2)
        assert result.n_features == 0

    def test_explicit_features_list(self) -> None:
        df = _make_feature_predictions_df(n=200)
        result = compute_feature_importance(df, features=("feature_a",))
        assert result.n_features == 1
        assert result.features[0].feature == "feature_a"

    def test_invalid_n_bins_low_raises(self) -> None:
        df = _make_feature_predictions_df(n=50)
        with pytest.raises(ValueError, match="n_bins"):
            compute_feature_importance(df, n_bins=1)

    def test_invalid_n_bins_high_raises(self) -> None:
        df = _make_feature_predictions_df(n=50)
        with pytest.raises(ValueError, match="n_bins"):
            compute_feature_importance(df, n_bins=21)

    def test_missing_prob_columns_raises(self) -> None:
        df = pd.DataFrame({"feature_a": [1.0, 2.0]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_feature_importance(df)

    def test_explicit_missing_feature_raises(self) -> None:
        df = _make_feature_predictions_df(n=50)
        with pytest.raises(ValueError, match="feature column not found"):
            compute_feature_importance(df, features=("nonexistent_col",))

    def test_disclaimer_present(self) -> None:
        df = _make_feature_predictions_df(n=100)
        result = compute_feature_importance(df)
        assert len(result.disclaimer) > 0


# ---------------------------------------------------------------------------
# Confidence band coverage analysis
# ---------------------------------------------------------------------------


def _make_ci_coverage_df(n: int = 200) -> pd.DataFrame:
    """Create predictions DataFrame with CI columns for coverage testing."""
    rng = np.random.default_rng(42)
    df = _make_predictions_df(n=n)
    # Create CI bounds around home_win_probability
    ci_width = rng.uniform(0.05, 0.25, n)
    df["home_win_ci_lower"] = (df["home_win_probability"] - ci_width / 2).clip(0.0, 1.0)
    df["home_win_ci_upper"] = (df["home_win_probability"] + ci_width / 2).clip(0.0, 1.0)
    df["match_id"] = [f"m{i}" for i in range(n)]
    return df


class TestComputeCICoverage:
    def test_returns_coverage(self) -> None:
        df = _make_ci_coverage_df(n=200)
        result = compute_ci_coverage(df)
        assert 0.0 <= result.overall_coverage <= 1.0
        assert result.avg_ci_width >= 0.0
        assert result.n_matches > 0

    def test_bucket_fields(self) -> None:
        df = _make_ci_coverage_df(n=200)
        result = compute_ci_coverage(df)
        for b in result.buckets:
            assert len(b.bucket_label) > 0
            assert b.confidence_lower <= b.confidence_upper
            assert b.n_matches > 0
            assert 0.0 <= b.empirical_coverage <= 1.0
            assert b.avg_ci_width >= 0.0

    def test_n_matches_matches_df(self) -> None:
        df = _make_ci_coverage_df(n=200)
        result = compute_ci_coverage(df)
        assert result.n_matches == len(df)

    def test_coverage_assessment_values(self) -> None:
        df = _make_ci_coverage_df(n=200)
        result = compute_ci_coverage(df)
        assert result.coverage_assessment in (
            "well_calibrated", "undercoverage", "overcoverage",
            "insufficient_data",
        )

    def test_nominal_level_propagated(self) -> None:
        df = _make_ci_coverage_df(n=200)
        result = compute_ci_coverage(df, nominal_level=0.80)
        assert result.nominal_level == 0.80
        for b in result.buckets:
            assert b.nominal_coverage == 0.80

    def test_min_samples_filter(self) -> None:
        df = _make_ci_coverage_df(n=30)
        result = compute_ci_coverage(df, min_samples_per_bucket=50, n_bins=3)
        assert len(result.buckets) == 0

    def test_missing_ci_columns_raises(self) -> None:
        df = _make_predictions_df(n=50)
        with pytest.raises(ValueError, match="missing required columns"):
            compute_ci_coverage(df)

    def test_missing_actual_outcome_raises(self) -> None:
        df = _make_ci_coverage_df(n=50)
        df = df.drop(columns=["actual_outcome"])
        with pytest.raises(ValueError, match="missing required columns"):
            compute_ci_coverage(df)

    def test_invalid_n_bins_low_raises(self) -> None:
        df = _make_ci_coverage_df(n=50)
        with pytest.raises(ValueError, match="n_bins"):
            compute_ci_coverage(df, n_bins=1)

    def test_invalid_n_bins_high_raises(self) -> None:
        df = _make_ci_coverage_df(n=50)
        with pytest.raises(ValueError, match="n_bins"):
            compute_ci_coverage(df, n_bins=21)

    def test_custom_ci_columns(self) -> None:
        df = _make_ci_coverage_df(n=200)
        df["custom_lo"] = df["home_win_ci_lower"]
        df["custom_hi"] = df["home_win_ci_upper"]
        result = compute_ci_coverage(
            df, ci_lower_col="custom_lo", ci_upper_col="custom_hi",
        )
        assert result.n_matches > 0

    def test_empty_df_returns_insufficient(self) -> None:
        df = _make_ci_coverage_df(n=10)
        df = df.iloc[:0]
        result = compute_ci_coverage(df)
        assert result.coverage_assessment == "insufficient_data"
        assert result.n_matches == 0

    def test_disclaimer_present(self) -> None:
        df = _make_ci_coverage_df(n=100)
        result = compute_ci_coverage(df)
        assert len(result.disclaimer) > 0


# ---------------------------------------------------------------------------
# Calibration drift heatmap
# ---------------------------------------------------------------------------


def _make_drift_heatmap_df(n: int = 200) -> pd.DataFrame:
    """Create predictions DataFrame with match_date for drift heatmap testing."""
    df = _make_predictions_df(n=n)
    # Spread matches across a year so multiple 90D windows form
    start = pd.Timestamp("2023-01-01")
    df["match_date"] = [start + pd.Timedelta(days=int(i * 365 / n)) for i in range(n)]
    df["match_id"] = [f"m{i}" for i in range(n)]
    return df


class TestComputeCalibrationDriftHeatmap:
    def test_returns_cells(self) -> None:
        df = _make_drift_heatmap_df(n=200)
        result = compute_calibration_drift_heatmap(df)
        assert result.n_windows > 0
        assert result.n_confidence_buckets > 0
        assert len(result.cells) > 0

    def test_cell_fields(self) -> None:
        df = _make_drift_heatmap_df(n=200)
        result = compute_calibration_drift_heatmap(df)
        for c in result.cells:
            assert len(c.window_label) > 0
            assert len(c.window_start) > 0
            assert len(c.window_end) > 0
            assert len(c.confidence_bucket) > 0
            assert c.confidence_lower <= c.confidence_upper
            assert c.n_matches > 0
            assert 0.0 <= c.accuracy <= 1.0
            assert c.brier >= 0.0
            assert c.rps >= 0.0

    def test_n_windows_matches_labels(self) -> None:
        df = _make_drift_heatmap_df(n=200)
        result = compute_calibration_drift_heatmap(df)
        assert result.n_windows == len(result.window_labels)

    def test_n_confidence_buckets_matches_labels(self) -> None:
        df = _make_drift_heatmap_df(n=200)
        result = compute_calibration_drift_heatmap(df)
        assert result.n_confidence_buckets == len(result.confidence_bucket_labels)

    def test_drift_detected_bool(self) -> None:
        df = _make_drift_heatmap_df(n=200)
        result = compute_calibration_drift_heatmap(df)
        assert isinstance(result.drift_detected, bool)

    def test_min_samples_filter(self) -> None:
        df = _make_drift_heatmap_df(n=50)
        result = compute_calibration_drift_heatmap(
            df, min_samples_per_cell=200, n_confidence_bins=3,
        )
        assert len(result.cells) == 0

    def test_missing_match_date_raises(self) -> None:
        df = _make_predictions_df(n=50)
        with pytest.raises(ValueError, match="missing required columns"):
            compute_calibration_drift_heatmap(df)

    def test_missing_prob_columns_raises(self) -> None:
        df = pd.DataFrame({"match_date": ["2023-01-01"]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_calibration_drift_heatmap(df)

    def test_invalid_n_confidence_bins_low_raises(self) -> None:
        df = _make_drift_heatmap_df(n=50)
        with pytest.raises(ValueError, match="n_confidence_bins"):
            compute_calibration_drift_heatmap(df, n_confidence_bins=1)

    def test_invalid_n_confidence_bins_high_raises(self) -> None:
        df = _make_drift_heatmap_df(n=50)
        with pytest.raises(ValueError, match="n_confidence_bins"):
            compute_calibration_drift_heatmap(df, n_confidence_bins=16)

    def test_log_loss_none_without_exact_score(self) -> None:
        df = _make_drift_heatmap_df(n=200)
        result = compute_calibration_drift_heatmap(df)
        for c in result.cells:
            assert c.log_loss is None

    def test_log_loss_computed_with_exact_score(self) -> None:
        df = _make_drift_heatmap_df(n=200)
        df["exact_score_probability"] = np.full(200, 0.05)
        result = compute_calibration_drift_heatmap(df)
        for c in result.cells:
            assert c.log_loss is not None
            assert c.log_loss > 0.0

    def test_disclaimer_present(self) -> None:
        df = _make_drift_heatmap_df(n=100)
        result = compute_calibration_drift_heatmap(df)
        assert len(result.disclaimer) > 0

    def test_n_total_matches_nonneg(self) -> None:
        df = _make_drift_heatmap_df(n=200)
        result = compute_calibration_drift_heatmap(df)
        assert result.n_total_matches >= 0


# ---------------------------------------------------------------------------
# API: feature importance, CI coverage, drift heatmap
# ---------------------------------------------------------------------------


class TestFeatureImportanceAPI:
    def test_no_data_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_feature_importance()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_feature_predictions_df(n=100)
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
        result = api_module.get_feature_importance()
        assert result["status"] == "ok"
        assert result["n_features"] > 0
        assert "features" in result
        assert "overall_brier" in result

    def test_with_data_no_features(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=80)  # No numeric feature columns
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
        result = api_module.get_feature_importance()
        # No numeric features found → n_features == 0 but status is still ok
        assert result["status"] == "ok"
        assert result["n_features"] == 0


class TestCICoverageAPI:
    def test_no_data_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_ci_coverage()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_ci_coverage_df(n=100)
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
        result = api_module.get_ci_coverage()
        assert result["status"] == "ok"
        assert result["n_matches"] > 0
        assert "overall_coverage" in result
        assert "coverage_assessment" in result

    def test_with_data_no_ci_columns(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=80)  # No CI columns
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
        result = api_module.get_ci_coverage()
        assert result["status"] == "not_available"


class TestCalibrationDriftHeatmapAPI:
    def test_no_data_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_calibration_drift_heatmap()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_drift_heatmap_df(n=100)
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
        result = api_module.get_calibration_drift_heatmap()
        assert result["status"] == "ok"
        assert result["n_windows"] > 0
        assert "cells" in result
        assert "drift_detected" in result

    def test_with_data_no_match_date(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=80)  # No match_date column
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
        result = api_module.get_calibration_drift_heatmap()
        assert result["status"] == "not_available"


# ---------------------------------------------------------------------------
# Prediction error clustering (k-means on worst-decile feature signatures)
# ---------------------------------------------------------------------------


def _make_error_clustering_df(n: int = 200) -> pd.DataFrame:
    """Create predictions DataFrame with numeric features for clustering."""
    rng = np.random.default_rng(42)
    df = _make_predictions_df(n=n)
    # Add numeric features that vary across rows
    df["attack_strength"] = rng.uniform(0.5, 2.0, n)
    df["defense_strength"] = rng.uniform(0.5, 2.0, n)
    df["form_index"] = rng.uniform(-1.0, 1.0, n)
    df["rest_days"] = rng.integers(2, 10, n)
    return df


class TestComputeErrorClustering:
    def test_returns_clusters(self) -> None:
        df = _make_error_clustering_df(n=200)
        result = compute_error_clustering(df, n_clusters=3)
        assert result.n_clusters >= 1
        assert len(result.clusters) >= 1
        assert result.n_total_matches == 200
        assert result.n_features_used > 0
        assert result.overall_avg_brier >= 0.0

    def test_cluster_fields(self) -> None:
        df = _make_error_clustering_df(n=200)
        result = compute_error_clustering(df, n_clusters=3)
        for c in result.clusters:
            assert c.cluster_id >= 0
            assert c.n_matches > 0
            assert c.avg_brier >= 0.0
            assert 0.0 <= c.avg_confidence <= 1.0
            assert 0.0 <= c.accuracy <= 1.0
            assert isinstance(c.dominant_actual_outcome, str)
            assert isinstance(c.dominant_predicted_outcome, str)
            assert isinstance(c.top_centroid_features, list)
            for f in c.top_centroid_features:
                assert isinstance(f.feature, str)
                assert isinstance(f.centroid_value, float)
                assert isinstance(f.abs_centroid, float)
                assert f.abs_centroid >= 0.0

    def test_clusters_sorted_by_brier_desc(self) -> None:
        df = _make_error_clustering_df(n=200)
        result = compute_error_clustering(df, n_clusters=3)
        briers = [c.avg_brier for c in result.clusters]
        assert briers == sorted(briers, reverse=True)

    def test_n_clusters_param(self) -> None:
        df = _make_error_clustering_df(n=300)
        result = compute_error_clustering(df, n_clusters=4)
        assert result.n_clusters <= 4

    def test_error_percentile_param(self) -> None:
        df = _make_error_clustering_df(n=300)
        result = compute_error_clustering(df, n_clusters=2, error_percentile=0.2)
        assert result.error_percentile == 0.2

    def test_custom_features(self) -> None:
        df = _make_error_clustering_df(n=200)
        result = compute_error_clustering(
            df, n_clusters=2, features=("attack_strength", "form_index"),
        )
        assert result.n_features_used == 2

    def test_invalid_n_clusters_low(self) -> None:
        df = _make_error_clustering_df(n=50)
        with pytest.raises(ValueError, match="n_clusters"):
            compute_error_clustering(df, n_clusters=1)

    def test_invalid_n_clusters_high(self) -> None:
        df = _make_error_clustering_df(n=50)
        with pytest.raises(ValueError, match="n_clusters"):
            compute_error_clustering(df, n_clusters=9)

    def test_invalid_error_percentile_zero(self) -> None:
        df = _make_error_clustering_df(n=50)
        with pytest.raises(ValueError, match="error_percentile"):
            compute_error_clustering(df, error_percentile=0.0)

    def test_invalid_error_percentile_high(self) -> None:
        df = _make_error_clustering_df(n=50)
        with pytest.raises(ValueError, match="error_percentile"):
            compute_error_clustering(df, error_percentile=0.6)

    def test_missing_required_columns_raises(self) -> None:
        df = pd.DataFrame({"foo": [1, 2, 3]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_error_clustering(df)

    def test_custom_feature_not_found_raises(self) -> None:
        df = _make_error_clustering_df(n=50)
        with pytest.raises(ValueError, match="feature column not found"):
            compute_error_clustering(df, features=("nonexistent_col",))

    def test_no_features_returns_empty_clusters(self) -> None:
        df = _make_predictions_df(n=100)  # No extra numeric features
        result = compute_error_clustering(df, n_clusters=3)
        assert result.n_clusters == 0
        assert result.clusters == []
        assert result.n_features_used == 0

    def test_too_few_samples_returns_empty(self) -> None:
        df = _make_error_clustering_df(n=20)
        result = compute_error_clustering(
            df, n_clusters=3, min_samples_per_cluster=50,
        )
        assert result.n_clusters == 0

    def test_disclaimer_present(self) -> None:
        df = _make_error_clustering_df(n=100)
        result = compute_error_clustering(df, n_clusters=2)
        assert len(result.disclaimer) > 0

    def test_random_state_reproducible(self) -> None:
        df = _make_error_clustering_df(n=200)
        r1 = compute_error_clustering(df, n_clusters=3, random_state=42)
        r2 = compute_error_clustering(df, n_clusters=3, random_state=42)
        assert r1.n_clusters == r2.n_clusters
        for c1, c2 in zip(r1.clusters, r2.clusters, strict=False):
            assert c1.avg_brier == c2.avg_brier
            assert c1.n_matches == c2.n_matches


# ---------------------------------------------------------------------------
# Data drift detection (KS test between train/holdout windows)
# ---------------------------------------------------------------------------


def _make_data_drift_df(n: int = 200) -> pd.DataFrame:
    """Create predictions DataFrame with match_date for drift testing."""
    df = _make_error_clustering_df(n=n)
    start = pd.Timestamp("2023-01-01")
    df["match_date"] = [
        start + pd.Timedelta(days=int(i * 365 / n)) for i in range(n)
    ]
    return df


class TestComputeDataDrift:
    def test_returns_drift(self) -> None:
        df = _make_data_drift_df(n=200)
        result = compute_data_drift(df)
        assert result.n_features > 0
        assert result.n_train > 0
        assert result.n_holdout > 0
        assert 0.0 <= result.drift_ratio <= 1.0
        assert len(result.split_date) > 0

    def test_feature_fields(self) -> None:
        df = _make_data_drift_df(n=200)
        result = compute_data_drift(df)
        for e in result.features:
            assert isinstance(e.feature, str)
            assert 0.0 <= e.ks_statistic <= 1.0
            assert 0.0 <= e.p_value <= 1.0
            assert isinstance(e.drifted, bool)
            assert isinstance(e.train_mean, float)
            assert isinstance(e.holdout_mean, float)
            assert isinstance(e.mean_delta, float)
            assert isinstance(e.train_std, float)
            assert isinstance(e.holdout_std, float)

    def test_features_sorted_by_ks_desc(self) -> None:
        df = _make_data_drift_df(n=200)
        result = compute_data_drift(df)
        ks_vals = [e.ks_statistic for e in result.features]
        assert ks_vals == sorted(ks_vals, reverse=True)

    def test_split_ratio_param(self) -> None:
        df = _make_data_drift_df(n=200)
        result = compute_data_drift(df, split_ratio=0.5)
        # With 50/50 split, both windows should have similar size
        assert result.n_train + result.n_holdout == 200

    def test_split_date_param(self) -> None:
        df = _make_data_drift_df(n=200)
        result = compute_data_drift(df, split_date="2023-06-01")
        assert len(result.split_date) > 0

    def test_p_value_threshold_param(self) -> None:
        df = _make_data_drift_df(n=200)
        result = compute_data_drift(df, p_value_threshold=0.01)
        assert result.p_value_threshold == 0.01

    def test_custom_features(self) -> None:
        df = _make_data_drift_df(n=200)
        result = compute_data_drift(
            df, features=("attack_strength", "form_index"),
        )
        assert result.n_features <= 2

    def test_missing_window_col_raises(self) -> None:
        df = _make_error_clustering_df(n=50)  # No match_date
        with pytest.raises(ValueError, match="missing required column"):
            compute_data_drift(df)

    def test_invalid_split_ratio_low(self) -> None:
        df = _make_data_drift_df(n=50)
        with pytest.raises(ValueError, match="split_ratio"):
            compute_data_drift(df, split_ratio=0.05)

    def test_invalid_split_ratio_high(self) -> None:
        df = _make_data_drift_df(n=50)
        with pytest.raises(ValueError, match="split_ratio"):
            compute_data_drift(df, split_ratio=0.95)

    def test_invalid_p_value_threshold_zero(self) -> None:
        df = _make_data_drift_df(n=50)
        with pytest.raises(ValueError, match="p_value_threshold"):
            compute_data_drift(df, p_value_threshold=0.0)

    def test_invalid_p_value_threshold_one(self) -> None:
        df = _make_data_drift_df(n=50)
        with pytest.raises(ValueError, match="p_value_threshold"):
            compute_data_drift(df, p_value_threshold=1.0)

    def test_custom_feature_not_found_raises(self) -> None:
        df = _make_data_drift_df(n=200)
        with pytest.raises(ValueError, match="feature column not found"):
            compute_data_drift(df, features=("nonexistent_col",))

    def test_too_few_samples_returns_empty(self) -> None:
        df = _make_data_drift_df(n=20)
        result = compute_data_drift(df, min_samples=50)
        assert result.n_features == 0
        assert result.n_drifted == 0

    def test_disclaimer_present(self) -> None:
        df = _make_data_drift_df(n=100)
        result = compute_data_drift(df)
        assert len(result.disclaimer) > 0

    def test_drifted_flag_consistent_with_p_value(self) -> None:
        df = _make_data_drift_df(n=200)
        result = compute_data_drift(df, p_value_threshold=0.05)
        for e in result.features:
            if e.p_value < 0.05:
                assert e.drifted is True
            else:
                assert e.drifted is False


# ---------------------------------------------------------------------------
# CI width analysis (per-confidence-bucket CI width tracking)
# ---------------------------------------------------------------------------


def _make_ci_width_df(n: int = 200) -> pd.DataFrame:
    """Create predictions DataFrame with CI columns for width analysis."""
    rng = np.random.default_rng(42)
    df = _make_predictions_df(n=n)
    # Create CI bounds with varying widths
    ci_width = rng.uniform(0.05, 0.30, n)
    df["home_win_ci_lower"] = (df["home_win_probability"] - ci_width / 2).clip(0.0, 1.0)
    df["home_win_ci_upper"] = (df["home_win_probability"] + ci_width / 2).clip(0.0, 1.0)
    return df


class TestComputeCIWidthAnalysis:
    def test_returns_report(self) -> None:
        df = _make_ci_width_df(n=200)
        result = compute_ci_width_analysis(df)
        assert result.n_matches > 0
        assert result.overall_avg_ci_width >= 0.0
        assert 0.0 <= result.overall_avg_confidence <= 1.0
        assert len(result.buckets) > 0

    def test_bucket_fields(self) -> None:
        df = _make_ci_width_df(n=200)
        result = compute_ci_width_analysis(df)
        for b in result.buckets:
            assert len(b.bucket_label) > 0
            assert b.confidence_lower <= b.confidence_upper
            assert b.n_matches > 0
            assert b.avg_ci_width >= 0.0
            assert 0.0 <= b.avg_ci_lower <= 1.0
            assert 0.0 <= b.avg_ci_upper <= 1.0
            assert b.width_std >= 0.0
            assert b.relative_width >= 0.0

    def test_assessment_values(self) -> None:
        df = _make_ci_width_df(n=200)
        result = compute_ci_width_analysis(df)
        assert result.assessment in (
            "anomalous_widening", "expected_narrowing",
            "weak_correlation", "insufficient_data",
        )

    def test_correlation_can_be_none(self) -> None:
        # Constant confidence (all probs identical) → std=0 → correlation None
        df = _make_predictions_df(n=50)
        df["home_win_probability"] = 0.5
        df["draw_probability"] = 0.25
        df["away_win_probability"] = 0.25
        df["home_win_ci_lower"] = 0.4
        df["home_win_ci_upper"] = 0.5
        result = compute_ci_width_analysis(df)
        assert result.width_confidence_correlation is None
        assert result.assessment == "insufficient_data"

    def test_n_bins_param(self) -> None:
        df = _make_ci_width_df(n=300)
        result = compute_ci_width_analysis(df, n_bins=10, min_samples_per_bucket=5)
        assert len(result.buckets) <= 10

    def test_min_samples_filter(self) -> None:
        df = _make_ci_width_df(n=30)
        result = compute_ci_width_analysis(
            df, n_bins=5, min_samples_per_bucket=50,
        )
        assert len(result.buckets) == 0

    def test_missing_ci_columns_raises(self) -> None:
        df = _make_predictions_df(n=50)
        with pytest.raises(ValueError, match="missing required columns"):
            compute_ci_width_analysis(df)

    def test_missing_probability_columns_raises(self) -> None:
        df = pd.DataFrame({
            "home_win_ci_lower": [0.2, 0.3, 0.4],
            "home_win_ci_upper": [0.4, 0.5, 0.6],
        })
        with pytest.raises(ValueError, match="missing required columns"):
            compute_ci_width_analysis(df)

    def test_invalid_n_bins_low(self) -> None:
        df = _make_ci_width_df(n=50)
        with pytest.raises(ValueError, match="n_bins"):
            compute_ci_width_analysis(df, n_bins=1)

    def test_invalid_n_bins_high(self) -> None:
        df = _make_ci_width_df(n=50)
        with pytest.raises(ValueError, match="n_bins"):
            compute_ci_width_analysis(df, n_bins=21)

    def test_custom_ci_columns(self) -> None:
        df = _make_ci_width_df(n=200)
        df["custom_lo"] = df["home_win_ci_lower"]
        df["custom_hi"] = df["home_win_ci_upper"]
        result = compute_ci_width_analysis(
            df, ci_lower_col="custom_lo", ci_upper_col="custom_hi",
        )
        assert result.n_matches > 0

    def test_empty_df_returns_insufficient(self) -> None:
        df = _make_ci_width_df(n=10)
        df = df.iloc[:0]
        result = compute_ci_width_analysis(df)
        assert result.assessment == "insufficient_data"
        assert result.n_matches == 0

    def test_disclaimer_present(self) -> None:
        df = _make_ci_width_df(n=100)
        result = compute_ci_width_analysis(df)
        assert len(result.disclaimer) > 0

    def test_widest_and_narrowest_buckets(self) -> None:
        df = _make_ci_width_df(n=200)
        result = compute_ci_width_analysis(df)
        if result.buckets:
            widths = [b.avg_ci_width for b in result.buckets]
            widest = max(result.buckets, key=lambda b: b.avg_ci_width)
            narrowest = min(result.buckets, key=lambda b: b.avg_ci_width)
            assert result.widest_bucket == widest.bucket_label
            assert result.narrowest_bucket == narrowest.bucket_label
            assert widest.avg_ci_width == max(widths)
            assert narrowest.avg_ci_width == min(widths)


# ---------------------------------------------------------------------------
# Error clustering API
# ---------------------------------------------------------------------------


class TestErrorClusteringAPI:
    def test_no_data_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_error_clustering()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_error_clustering_df(n=200)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_error_clustering()
        assert result["status"] == "ok"
        assert "n_clusters" in result
        assert "clusters" in result
        assert "disclaimer" in result

    def test_with_empty_data_no_data(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_error_clustering_df(n=200).iloc[:0]
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_error_clustering()
        assert result["status"] == "no_data"

    def test_cache_hit(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_error_clustering_df(n=100)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        r1 = api_module.get_error_clustering()
        r2 = api_module.get_error_clustering()
        assert r1 == r2

    def test_fallback_to_poisson(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_error_clustering_df(n=200)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        # Only write Poisson file (no DC decay)
        df.to_parquet(
            tmp_path / "poisson_backtest_predictions.parquet",
            index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_error_clustering()
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Data drift API
# ---------------------------------------------------------------------------


class TestDataDriftAPI:
    def test_no_data_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_data_drift()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_data_drift_df(n=200)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_data_drift()
        assert result["status"] == "ok"
        assert "n_features" in result
        assert "n_drifted" in result
        assert "features" in result
        assert "disclaimer" in result

    def test_no_match_date_not_available(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=80)  # No match_date
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_data_drift()
        assert result["status"] == "not_available"

    def test_with_split_date_param(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_data_drift_df(n=200)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_data_drift(split_date="2023-06-01")
        assert result["status"] == "ok"

    def test_cache_hit(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_data_drift_df(n=100)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        r1 = api_module.get_data_drift()
        r2 = api_module.get_data_drift()
        assert r1 == r2


# ---------------------------------------------------------------------------
# CI width analysis API
# ---------------------------------------------------------------------------


class TestCIWidthAnalysisAPI:
    def test_no_data_not_available(self, monkeypatch) -> None:
        from scoutfootball import api as api_module

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path("/nonexistent")})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_ci_width_analysis()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_ci_width_df(n=200)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_ci_width_analysis()
        assert result["status"] == "ok"
        assert "assessment" in result
        assert "buckets" in result
        assert "overall_avg_ci_width" in result
        assert "disclaimer" in result

    def test_no_ci_columns_not_available(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=80)  # No CI columns
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_ci_width_analysis()
        assert result["status"] == "not_available"

    def test_with_custom_ci_columns(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_ci_width_df(n=200)
        df["custom_lo"] = df["home_win_ci_lower"]
        df["custom_hi"] = df["home_win_ci_upper"]
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_ci_width_analysis(
            ci_lower_col="custom_lo", ci_upper_col="custom_hi",
        )
        assert result["status"] == "ok"

    def test_cache_hit(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_ci_width_df(n=100)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )

        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        r1 = api_module.get_ci_width_analysis()
        r2 = api_module.get_ci_width_analysis()
        assert r1 == r2


# ---------------------------------------------------------------------------
# Round 34: Scenario Stress Test, Per-Team Calibration Drift, Uncertainty
# ---------------------------------------------------------------------------


def _make_stress_test_df(n: int = 200) -> pd.DataFrame:
    """Create predictions DataFrame suitable for stress testing."""
    return _make_predictions_df(n=n)


def _make_team_drift_df(n: int = 200) -> pd.DataFrame:
    """Create predictions DataFrame with team + match_date columns."""
    rng = np.random.default_rng(42)
    df = _make_predictions_df(n=n)
    teams = ["TeamA", "TeamB", "TeamC", "TeamD"]
    df["home_team"] = rng.choice(teams, n)
    df["away_team"] = rng.choice(teams, n)
    start = pd.Timestamp("2023-01-01")
    df["match_date"] = [start + pd.Timedelta(days=int(i * 365 / n)) for i in range(n)]
    return df


def _make_uncertainty_df(n: int = 200) -> pd.DataFrame:
    """Create predictions DataFrame for uncertainty analysis."""
    rng = np.random.default_rng(42)
    df = _make_predictions_df(n=n)
    df["match_id"] = [f"m{i}" for i in range(n)]
    df["home_team"] = rng.choice(["TeamA", "TeamB", "TeamC"], n)
    df["away_team"] = rng.choice(["TeamD", "TeamE", "TeamF"], n)
    return df


class TestComputeScenarioStressTest:
    def test_returns_report(self) -> None:
        df = _make_stress_test_df(n=200)
        result = compute_scenario_stress_test(df)
        assert result.baseline.n_matches == 200
        assert result.stressed.n_matches == 200
        assert result.n_shifted > 0
        assert 0.0 <= result.baseline.accuracy <= 1.0
        assert result.baseline.brier >= 0.0
        assert result.baseline.rps >= 0.0
        assert result.baseline.avg_confidence >= 0.0

    def test_report_fields(self) -> None:
        df = _make_stress_test_df(n=100)
        result = compute_scenario_stress_test(df, shift_ratio=0.3)
        assert result.shift_type == "outcome_swap"
        assert result.shift_ratio == 0.3
        assert isinstance(result.accuracy_delta, float)
        assert isinstance(result.brier_delta, float)
        assert isinstance(result.rps_delta, float)
        assert isinstance(result.confidence_delta, float)
        assert isinstance(result.degradation_score, float)
        assert result.assessment in ("severe", "moderate", "mild", "negligible")
        assert result.n_shifted > 0
        assert len(result.disclaimer) > 0

    def test_shift_ratio_zero_returns_negligible(self) -> None:
        df = _make_stress_test_df(n=100)
        result = compute_scenario_stress_test(df, shift_ratio=0.0)
        assert result.n_shifted == 0
        assert result.degradation_score == 0.0
        assert result.assessment == "negligible"
        assert result.accuracy_delta == 0.0

    def test_shift_type_probability_shift(self) -> None:
        df = _make_stress_test_df(n=100)
        result = compute_scenario_stress_test(
            df, shift_type="probability_shift", shift_ratio=0.5,
        )
        assert result.shift_type == "probability_shift"
        assert result.n_shifted > 0

    def test_shift_type_confidence_inflation(self) -> None:
        df = _make_stress_test_df(n=100)
        result = compute_scenario_stress_test(
            df, shift_type="confidence_inflation", shift_ratio=0.5,
        )
        assert result.shift_type == "confidence_inflation"
        assert result.stressed.avg_confidence >= result.baseline.avg_confidence

    def test_shift_type_confidence_deflation(self) -> None:
        df = _make_stress_test_df(n=100)
        result = compute_scenario_stress_test(
            df, shift_type="confidence_deflation", shift_ratio=0.5,
        )
        assert result.shift_type == "confidence_deflation"
        assert result.stressed.avg_confidence <= result.baseline.avg_confidence

    def test_empty_df_returns_negligible(self) -> None:
        df = pd.DataFrame(columns=[
            "home_win_probability", "draw_probability",
            "away_win_probability", "actual_outcome",
        ])
        result = compute_scenario_stress_test(df)
        assert result.baseline.n_matches == 0
        assert result.degradation_score == 0.0

    def test_missing_prob_columns_raises(self) -> None:
        df = pd.DataFrame({"actual_outcome": ["home_win"] * 10})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_scenario_stress_test(df)

    def test_invalid_shift_type_raises(self) -> None:
        df = _make_stress_test_df(n=50)
        with pytest.raises(ValueError, match="shift_type must be one of"):
            compute_scenario_stress_test(df, shift_type="bogus")

    def test_invalid_shift_ratio_raises(self) -> None:
        df = _make_stress_test_df(n=50)
        with pytest.raises(ValueError, match="shift_ratio must be in"):
            compute_scenario_stress_test(df, shift_ratio=1.5)

    def test_reproducible_with_same_seed(self) -> None:
        df = _make_stress_test_df(n=100)
        r1 = compute_scenario_stress_test(df, random_state=42)
        r2 = compute_scenario_stress_test(df, random_state=42)
        assert r1.stressed.accuracy == r2.stressed.accuracy
        assert r1.stressed.brier == r2.stressed.brier

    def test_different_seed_may_differ(self) -> None:
        df = _make_stress_test_df(n=100)
        r1 = compute_scenario_stress_test(df, random_state=42)
        r2 = compute_scenario_stress_test(df, random_state=123)
        # Different seeds should generally perturb different rows
        # (not a strict requirement, but a sanity check)
        assert isinstance(r1.stressed.accuracy, float)
        assert isinstance(r2.stressed.accuracy, float)

    def test_log_loss_present(self) -> None:
        rng = np.random.default_rng(42)
        df = _make_stress_test_df(n=100)
        df["exact_score_probability"] = rng.uniform(0.01, 0.1, 100)
        result = compute_scenario_stress_test(df)
        assert result.baseline.log_loss is not None
        assert result.baseline.log_loss > 0.0

    def test_log_loss_none_without_exact_score(self) -> None:
        df = _make_stress_test_df(n=100)
        result = compute_scenario_stress_test(df)
        assert result.baseline.log_loss is None
        assert result.log_loss_delta is None

    def test_degradation_score_nonneg(self) -> None:
        df = _make_stress_test_df(n=200)
        result = compute_scenario_stress_test(df, shift_ratio=0.5)
        assert result.degradation_score >= 0.0

    def test_disclaimer_present(self) -> None:
        df = _make_stress_test_df(n=50)
        result = compute_scenario_stress_test(df)
        assert "stress" in result.disclaimer.lower()


class TestComputeTeamCalibrationDrift:
    def test_returns_report(self) -> None:
        df = _make_team_drift_df(n=200)
        result = compute_team_calibration_drift(df, team_name="TeamA")
        assert result.team_name == "TeamA"
        assert result.team_col == "home_team"
        assert result.n_total_matches > 0

    def test_report_fields(self) -> None:
        df = _make_team_drift_df(n=300)
        result = compute_team_calibration_drift(df, team_name="TeamA")
        assert isinstance(result.points, list)
        assert isinstance(result.drift_detected, bool)
        assert isinstance(result.latest_brier, float)
        assert isinstance(result.historical_avg_brier, float)
        assert isinstance(result.relative_change, float)
        assert result.trend in ("improving", "degrading", "stable", "insufficient_data")
        assert len(result.disclaimer) > 0

    def test_team_not_found_returns_empty(self) -> None:
        df = _make_team_drift_df(n=100)
        result = compute_team_calibration_drift(df, team_name="NonexistentTeam")
        assert result.n_total_matches == 0
        assert result.points == []
        assert result.trend == "insufficient_data"

    def test_empty_team_name_raises(self) -> None:
        df = _make_team_drift_df(n=50)
        with pytest.raises(ValueError, match="team_name must be a non-empty string"):
            compute_team_calibration_drift(df, team_name="")

    def test_missing_team_col_raises(self) -> None:
        df = _make_predictions_df(n=50)
        with pytest.raises(ValueError, match="missing required columns"):
            compute_team_calibration_drift(df, team_name="TeamA")

    def test_missing_match_date_raises(self) -> None:
        df = _make_predictions_df(n=50)
        df["home_team"] = "TeamA"
        with pytest.raises(ValueError, match="missing required columns"):
            compute_team_calibration_drift(df, team_name="TeamA")

    def test_missing_prob_columns_raises(self) -> None:
        df = pd.DataFrame({
            "home_team": ["TeamA"] * 10,
            "match_date": pd.date_range("2023-01-01", periods=10),
            "actual_outcome": ["home_win"] * 10,
        })
        with pytest.raises(ValueError, match="missing required columns"):
            compute_team_calibration_drift(df, team_name="TeamA")

    def test_custom_team_col(self) -> None:
        df = _make_team_drift_df(n=200)
        result = compute_team_calibration_drift(
            df, team_col="away_team", team_name="TeamB",
        )
        assert result.team_col == "away_team"
        assert result.team_name == "TeamB"

    def test_n_windows_cap(self) -> None:
        df = _make_team_drift_df(n=500)
        result = compute_team_calibration_drift(
            df, team_name="TeamA", n_windows=2,
        )
        assert result.n_windows <= 2

    def test_point_fields(self) -> None:
        df = _make_team_drift_df(n=300)
        result = compute_team_calibration_drift(df, team_name="TeamA")
        for p in result.points:
            assert len(p.window_label) > 0
            assert p.n_matches > 0
            assert 0.0 <= p.accuracy <= 1.0
            assert p.brier >= 0.0
            assert 0.0 <= p.avg_confidence <= 1.0

    def test_min_samples_filter(self) -> None:
        df = _make_team_drift_df(n=100)
        # Very high min_samples_per_window should filter out most windows
        result = compute_team_calibration_drift(
            df, team_name="TeamA", min_samples_per_window=1000,
        )
        assert result.n_windows == 0

    def test_drift_detection_logic(self) -> None:
        df = _make_team_drift_df(n=400)
        result = compute_team_calibration_drift(df, team_name="TeamA")
        # Drift detection requires >= 2 windows and >5% relative change
        if result.n_windows >= 2:
            expected = abs(result.relative_change) > 0.05
            assert result.drift_detected == expected

    def test_insufficient_windows_trend(self) -> None:
        df = _make_team_drift_df(n=100)
        result = compute_team_calibration_drift(
            df, team_name="TeamA", min_samples_per_window=1000,
        )
        assert result.trend == "insufficient_data"

    def test_disclaimer_present(self) -> None:
        df = _make_team_drift_df(n=100)
        result = compute_team_calibration_drift(df, team_name="TeamA")
        assert "team" in result.disclaimer.lower() or "drift" in result.disclaimer.lower()

    def test_away_team_filter(self) -> None:
        df = _make_team_drift_df(n=200)
        result = compute_team_calibration_drift(
            df, team_col="away_team", team_name="TeamC",
        )
        assert result.team_name == "TeamC"
        assert result.n_total_matches > 0


class TestComputePredictionUncertainty:
    def test_returns_report(self) -> None:
        df = _make_uncertainty_df(n=200)
        result = compute_prediction_uncertainty(df)
        assert result.n_matches == 200
        assert 0.0 <= result.avg_entropy <= 1.0
        assert result.avg_margin >= 0.0
        assert result.avg_dispersion >= 0.0
        assert result.high_uncertainty_count >= 0
        assert len(result.points) > 0

    def test_point_fields(self) -> None:
        df = _make_uncertainty_df(n=100)
        result = compute_prediction_uncertainty(df)
        for p in result.points:
            assert p.match_id is not None or p.home_team is not None
            assert 0.0 <= p.confidence <= 1.0
            assert 0.0 <= p.entropy <= 1.0
            assert p.margin >= 0.0
            assert p.dispersion >= 0.0
            assert p.predicted_outcome in ("home_win", "draw", "away_win")
            assert p.uncertainty_label in ("high", "medium", "low")

    def test_correct_flag_with_actual(self) -> None:
        df = _make_uncertainty_df(n=100)
        result = compute_prediction_uncertainty(df)
        # At least some points should have correct flag set
        correct_flags = [p.correct for p in result.points if p.correct is not None]
        assert len(correct_flags) > 0
        assert all(isinstance(c, bool) for c in correct_flags)

    def test_max_points_caps_points(self) -> None:
        df = _make_uncertainty_df(n=300)
        result = compute_prediction_uncertainty(df, max_points=50)
        assert len(result.points) <= 50
        # Aggregates should still be computed on all rows
        assert result.n_matches == 300

    def test_empty_df_returns_empty(self) -> None:
        df = pd.DataFrame(columns=[
            "home_win_probability", "draw_probability", "away_win_probability",
        ])
        result = compute_prediction_uncertainty(df)
        assert result.n_matches == 0
        assert result.points == []
        assert result.avg_entropy == 0.0

    def test_missing_prob_columns_raises(self) -> None:
        df = pd.DataFrame({"match_id": ["m1"]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_prediction_uncertainty(df)

    def test_entropy_uniform_distribution(self) -> None:
        # Uniform distribution → max entropy (close to 1.0)
        df = pd.DataFrame({
            "home_win_probability": [1.0 / 3.0] * 10,
            "draw_probability": [1.0 / 3.0] * 10,
            "away_win_probability": [1.0 / 3.0] * 10,
        })
        result = compute_prediction_uncertainty(df)
        assert result.avg_entropy > 0.99  # Near max entropy

    def test_entropy_dominant_outcome(self) -> None:
        # Dominant outcome → low entropy
        df = pd.DataFrame({
            "home_win_probability": [0.95] * 10,
            "draw_probability": [0.03] * 10,
            "away_win_probability": [0.02] * 10,
        })
        result = compute_prediction_uncertainty(df)
        assert result.avg_entropy < 0.25  # Low entropy

    def test_uncertainty_label_high(self) -> None:
        df = pd.DataFrame({
            "home_win_probability": [0.34, 0.34, 0.33] * 5,
            "draw_probability": [0.33, 0.33, 0.34] * 5,
            "away_win_probability": [0.33, 0.33, 0.33] * 5,
        })
        result = compute_prediction_uncertainty(df)
        for p in result.points:
            assert p.uncertainty_label == "high"

    def test_uncertainty_label_low(self) -> None:
        df = pd.DataFrame({
            "home_win_probability": [0.95] * 10,
            "draw_probability": [0.03] * 10,
            "away_win_probability": [0.02] * 10,
        })
        result = compute_prediction_uncertainty(df)
        for p in result.points:
            assert p.uncertainty_label == "low"

    def test_high_uncertainty_count(self) -> None:
        df = pd.DataFrame({
            "home_win_probability": [1.0 / 3.0] * 20,
            "draw_probability": [1.0 / 3.0] * 20,
            "away_win_probability": [1.0 / 3.0] * 20,
        })
        result = compute_prediction_uncertainty(df)
        assert result.high_uncertainty_count == 20

    def test_correlation_can_be_none(self) -> None:
        # When all entropies are identical, correlation is None
        df = pd.DataFrame({
            "home_win_probability": [0.5, 0.5] * 10,
            "draw_probability": [0.25, 0.25] * 10,
            "away_win_probability": [0.25, 0.25] * 10,
            "actual_outcome": ["home_win", "draw"] * 10,
        })
        result = compute_prediction_uncertainty(df)
        # All entropies identical → set(entropies) has 1 element → correlation None
        assert result.entropy_accuracy_correlation is None

    def test_correlation_computed_with_variance(self) -> None:
        df = _make_uncertainty_df(n=200)
        result = compute_prediction_uncertainty(df)
        # With varied probabilities and outcomes, correlation should be a float
        assert result.entropy_accuracy_correlation is not None or result.n_matches < 2

    def test_disclaimer_present(self) -> None:
        df = _make_uncertainty_df(n=50)
        result = compute_prediction_uncertainty(df)
        assert "entropy" in result.disclaimer.lower() or "uncertainty" in result.disclaimer.lower()


class TestScenarioStressTestAPI:
    def test_no_data_not_available(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        tmp_path = Path(tmp_path)
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": tmp_path})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_scenario_stress_test()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_stress_test_df(n=200)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_scenario_stress_test()
        assert result["status"] == "ok"
        assert result["baseline"]["n_matches"] == 200
        assert result["stressed"]["n_matches"] == 200

    def test_poisson_fallback(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_stress_test_df(n=100)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "poisson_backtest_predictions.parquet",
            index=False,
        )
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_scenario_stress_test()
        assert result["status"] == "ok"

    def test_cache_hit(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_stress_test_df(n=100)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        r1 = api_module.get_scenario_stress_test()
        r2 = api_module.get_scenario_stress_test()
        assert r1 == r2

    def test_synthesizes_actual_outcome(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=100)
        df = df.drop(columns=["actual_outcome"])
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_scenario_stress_test()
        assert result["status"] == "ok"


class TestTeamCalibrationDriftAPI:
    def test_no_data_not_available(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        tmp_path = Path(tmp_path)
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": tmp_path})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_team_calibration_drift(team_name="TeamA")
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_team_drift_df(n=200)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_team_calibration_drift(team_name="TeamA")
        assert result["status"] == "ok"
        assert result["team_name"] == "TeamA"

    def test_no_team_column_not_available(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=100)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_team_calibration_drift(team_name="TeamA")
        assert result["status"] == "not_available"

    def test_no_match_date_not_available(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_predictions_df(n=100)
        df["home_team"] = "TeamA"
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_team_calibration_drift(team_name="TeamA")
        assert result["status"] == "not_available"

    def test_cache_hit(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_team_drift_df(n=200)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        r1 = api_module.get_team_calibration_drift(team_name="TeamA")
        r2 = api_module.get_team_calibration_drift(team_name="TeamA")
        assert r1 == r2


class TestPredictionUncertaintyAPI:
    def test_no_data_not_available(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        tmp_path = Path(tmp_path)
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": tmp_path})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_prediction_uncertainty()
        assert result["status"] == "not_available"

    def test_with_data_ok(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_uncertainty_df(n=200)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_prediction_uncertainty()
        assert result["status"] == "ok"
        assert result["n_matches"] == 200
        assert len(result["points"]) > 0

    def test_synthesizes_actual_outcome(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_uncertainty_df(n=100)
        df = df.drop(columns=["actual_outcome"])
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        result = api_module.get_prediction_uncertainty()
        assert result["status"] == "ok"

    def test_cache_hit(self, monkeypatch, tmp_path) -> None:
        from scoutfootball import api as api_module

        df = _make_uncertainty_df(n=100)
        tmp_path = Path(tmp_path) / "calibration_backtest"
        tmp_path.mkdir()
        df.to_parquet(
            tmp_path / "dixon_coles_decay_backtest_predictions.parquet",
            index=False,
        )
        monkeypatch.setattr(
            api_module, "_settings",
            lambda: type("S", (), {"report_root": Path(tmp_path.parent)})(),
        )
        api_module._BACKTEST_CACHE.clear()
        r1 = api_module.get_prediction_uncertainty()
        r2 = api_module.get_prediction_uncertainty()
        assert r1 == r2

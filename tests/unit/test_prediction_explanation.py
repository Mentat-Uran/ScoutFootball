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

"""Tests for WC tournament knockout match impact API."""

import pytest


@pytest.fixture
def api_module():
    from scoutfootball import api as api_mod

    return api_mod


class TestKnockoutMatchImpactStatus:
    def test_returns_dict(self, api_module):
        result = api_module.get_wc_tournament_knockout_match_impact(
            num_simulations=200, top_n=5
        )
        assert isinstance(result, dict)

    def test_has_status(self, api_module):
        result = api_module.get_wc_tournament_knockout_match_impact(
            num_simulations=200, top_n=5
        )
        assert "status" in result

    def test_has_source_attribution(self, api_module):
        result = api_module.get_wc_tournament_knockout_match_impact(
            num_simulations=200, top_n=5
        )
        if result.get("status") == "ok":
            assert "source_attribution" in result

    def test_status_is_ok_or_not_generated(self, api_module):
        """Without a generated bracket the endpoint returns not_generated."""
        result = api_module.get_wc_tournament_knockout_match_impact(
            num_simulations=200, top_n=5
        )
        assert result["status"] in {"ok", "not_generated", "no_data"}


class TestKnockoutMatchImpactFields:
    def test_has_num_simulations(self, api_module):
        result = api_module.get_wc_tournament_knockout_match_impact(
            num_simulations=200, top_n=5
        )
        if result.get("status") == "ok":
            assert result["num_simulations"] == 200

    def test_has_mode(self, api_module):
        result = api_module.get_wc_tournament_knockout_match_impact(
            num_simulations=200, top_n=5
        )
        if result.get("status") == "ok":
            assert result["mode"] == "strength"

    def test_matches_is_list(self, api_module):
        result = api_module.get_wc_tournament_knockout_match_impact(
            num_simulations=200, top_n=5
        )
        if result.get("status") == "ok":
            assert isinstance(result["matches"], list)

    def test_top_n_limits_results(self, api_module):
        result = api_module.get_wc_tournament_knockout_match_impact(
            num_simulations=200, top_n=3
        )
        if result.get("status") == "ok":
            assert len(result["matches"]) <= 3

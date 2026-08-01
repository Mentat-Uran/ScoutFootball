"""Tests for WC tournament top matches unified leaderboard API."""

import pytest


@pytest.fixture
def api_module():
    from scoutfootball import api as api_mod

    return api_mod


class TestTopMatchesStatus:
    def test_ok_status(self, api_module):
        result = api_module.get_wc_tournament_top_matches(
            group_top_n=3, knockout_top_n=3, num_simulations=10
        )
        assert result["status"] == "ok"

    def test_has_schema(self, api_module):
        result = api_module.get_wc_tournament_top_matches(
            group_top_n=3, knockout_top_n=3, num_simulations=10
        )
        assert result["schema"] == "scoutfootball.world-cup-top-matches"

    def test_has_source_attribution(self, api_module):
        result = api_module.get_wc_tournament_top_matches(
            group_top_n=3, knockout_top_n=3, num_simulations=10
        )
        assert "source_attribution" in result

    def test_has_disclaimer(self, api_module):
        result = api_module.get_wc_tournament_top_matches(
            group_top_n=3, knockout_top_n=3, num_simulations=10
        )
        assert isinstance(result.get("disclaimer"), str)
        assert len(result["disclaimer"]) > 0


class TestTopMatchesContent:
    def test_has_matches_list(self, api_module):
        result = api_module.get_wc_tournament_top_matches(
            group_top_n=3, knockout_top_n=3, num_simulations=10
        )
        assert isinstance(result["matches"], list)

    def test_has_stage_counts(self, api_module):
        result = api_module.get_wc_tournament_top_matches(
            group_top_n=3, knockout_top_n=3, num_simulations=10
        )
        assert "group_stage_count" in result
        assert "knockout_count" in result
        assert isinstance(result["group_stage_count"], int)
        assert isinstance(result["knockout_count"], int)

    def test_match_has_required_fields(self, api_module):
        result = api_module.get_wc_tournament_top_matches(
            group_top_n=3, knockout_top_n=3, num_simulations=10
        )
        if not result["matches"]:
            pytest.skip("No top matches")
        m = result["matches"][0]
        for field in ("match_id", "stage", "home", "away", "total_impact", "impact_metric"):
            assert field in m, f"Missing field: {field}"

    def test_stage_is_group_or_knockout(self, api_module):
        result = api_module.get_wc_tournament_top_matches(
            group_top_n=3, knockout_top_n=3, num_simulations=10
        )
        for m in result["matches"]:
            assert m["stage"] in {"group", "knockout"}

    def test_total_impact_non_negative(self, api_module):
        result = api_module.get_wc_tournament_top_matches(
            group_top_n=3, knockout_top_n=3, num_simulations=10
        )
        for m in result["matches"]:
            assert m["total_impact"] >= 0.0

    def test_matches_sorted_by_total_impact_desc(self, api_module):
        result = api_module.get_wc_tournament_top_matches(
            group_top_n=5, knockout_top_n=5, num_simulations=10
        )
        impacts = [m["total_impact"] for m in result["matches"]]
        assert impacts == sorted(impacts, reverse=True)

    def test_metric_is_recognized(self, api_module):
        result = api_module.get_wc_tournament_top_matches(
            group_top_n=3, knockout_top_n=3, num_simulations=10
        )
        for m in result["matches"]:
            assert m["impact_metric"] in {"advancement_prob_swing", "championship_prob_swing"}

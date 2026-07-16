"""Tests for WC tournament match impact API."""

import pytest


@pytest.fixture
def api_module():
    from scoutfootball import api as api_mod

    return api_mod


class TestMatchImpactStatus:
    def test_ok_status(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        assert result["status"] == "ok"

    def test_has_matches_list(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        assert isinstance(result["matches"], list)

    def test_has_num_simulations(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        assert result["num_simulations"] == 200

    def test_has_mode_strength(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        assert result["mode"] == "strength"

    def test_has_disclaimer(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        assert isinstance(result["disclaimer"], str)
        assert len(result["disclaimer"]) > 0

    def test_has_source_attribution(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        assert "source_attribution" in result

    def test_has_total_pending(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        assert isinstance(result["total_pending"], int)
        assert result["total_pending"] >= 0


class TestMatchImpactPerMatch:
    def test_match_has_required_fields(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        if not result["matches"]:
            pytest.skip("No pending matches")
        m = result["matches"][0]
        for field in (
            "match_id", "home", "away", "group", "total_impact",
            "max_swing", "max_swing_team", "per_team",
        ):
            assert field in m, f"Missing field: {field}"

    def test_total_impact_non_negative(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        for m in result["matches"]:
            assert m["total_impact"] >= 0

    def test_max_swing_non_negative(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        for m in result["matches"]:
            assert m["max_swing"] >= 0

    def test_per_team_has_fields(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        if not result["matches"]:
            pytest.skip("No pending matches")
        m = result["matches"][0]
        for pt in m["per_team"]:
            for field in (
                "team", "home_win_prob", "draw_prob",
                "away_win_prob", "swing",
            ):
                assert field in pt, f"Missing per_team field: {field}"

    def test_per_team_probs_in_range(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        for m in result["matches"]:
            for pt in m["per_team"]:
                assert 0.0 <= pt["home_win_prob"] <= 1.0
                assert 0.0 <= pt["draw_prob"] <= 1.0
                assert 0.0 <= pt["away_win_prob"] <= 1.0

    def test_per_team_swing_is_max_minus_min(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        for m in result["matches"]:
            for pt in m["per_team"]:
                expected = max(
                    pt["home_win_prob"], pt["draw_prob"], pt["away_win_prob"]
                ) - min(
                    pt["home_win_prob"], pt["draw_prob"], pt["away_win_prob"]
                )
                assert abs(pt["swing"] - expected) < 1e-9

    def test_per_team_sorted_by_swing_desc(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        for m in result["matches"]:
            swings = [pt["swing"] for pt in m["per_team"]]
            assert swings == sorted(swings, reverse=True)

    def test_matches_sorted_by_total_impact_desc(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=10
        )
        impacts = [m["total_impact"] for m in result["matches"]]
        assert impacts == sorted(impacts, reverse=True)


class TestMatchImpactGroupFilter:
    def test_group_filter_returns_only_matching(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            group="A", num_simulations=200, top_n=10
        )
        assert result["status"] == "ok"
        for m in result["matches"]:
            assert m["group"] == "A"

    def test_unknown_group_returns_error(self, api_module):
        result = api_module.get_wc_tournament_match_impact(group="X")
        assert result["status"] == "error"
        assert result["code"] == "unknown_group"

    def test_group_filter_case_insensitive(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            group="a", num_simulations=200, top_n=10
        )
        assert result["status"] == "ok"
        for m in result["matches"]:
            assert m["group"] == "A"


class TestMatchImpactTopN:
    def test_top_n_limits_results(self, api_module):
        result = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=3
        )
        assert len(result["matches"]) <= 3


class TestMatchImpactDeterministic:
    def test_same_result_with_same_state(self, api_module):
        result1 = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        result2 = api_module.get_wc_tournament_match_impact(
            num_simulations=200, top_n=5
        )
        assert len(result1["matches"]) == len(result2["matches"])
        for m1, m2 in zip(result1["matches"], result2["matches"], strict=True):
            assert m1["match_id"] == m2["match_id"]
            assert abs(m1["total_impact"] - m2["total_impact"]) < 1e-9

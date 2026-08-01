"""Tests for WC tournament standings probabilities API."""

import pytest


@pytest.fixture
def api_module():
    from scoutfootball import api as api_mod

    return api_mod


class TestStandingsProbabilitiesStatus:
    def test_ok_status_with_group(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities(group="A")
        assert result["status"] == "ok"
        assert result["group"] == "A"
        assert "A" in result["groups"]

    def test_ok_status_all_groups(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities()
        assert result["status"] == "ok"
        assert result["group"] is None
        assert len(result["groups"]) >= 12

    def test_unknown_group_error(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities(group="ZZ")
        assert result["status"] == "error"
        assert result["code"] == "unknown_group"

    def test_has_num_simulations(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities(group="A")
        assert isinstance(result["num_simulations"], int)
        assert result["num_simulations"] > 0

    def test_has_mode_strength(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities(group="A")
        assert result["mode"] == "strength"

    def test_has_disclaimer(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities(group="A")
        assert isinstance(result["disclaimer"], str)
        assert len(result["disclaimer"]) > 0

    def test_has_source_attribution(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities(group="A")
        assert "source_attribution" in result


class TestStandingsProbabilitiesPerTeam:
    def test_each_team_has_advance_prob(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities(group="A")
        rows = result["groups"]["A"]
        assert len(rows) >= 4
        for row in rows:
            assert "advance_prob" in row
            assert isinstance(row["advance_prob"], float)
            assert 0.0 <= row["advance_prob"] <= 1.0

    def test_each_team_has_win_group_prob(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities(group="A")
        rows = result["groups"]["A"]
        for row in rows:
            assert "win_group_prob" in row
            assert isinstance(row["win_group_prob"], float)
            assert 0.0 <= row["win_group_prob"] <= 1.0

    def test_standings_fields_preserved(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities(group="A")
        rows = result["groups"]["A"]
        for row in rows:
            assert "team" in row
            assert "played" in row
            assert "won" in row
            assert "drawn" in row
            assert "lost" in row
            assert "points" in row

    def test_win_group_prob_le_advance_prob(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities(group="A")
        rows = result["groups"]["A"]
        for row in rows:
            assert row["win_group_prob"] <= row["advance_prob"] + 1e-9

    def test_num_simulations_param_works(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities(
            group="A", num_simulations=100
        )
        assert result["num_simulations"] == 100

    def test_group_filter_case_insensitive(self, api_module):
        result_lower = api_module.get_wc_tournament_standings_probabilities(group="a")
        result_upper = api_module.get_wc_tournament_standings_probabilities(group="A")
        assert result_lower["status"] == "ok"
        assert result_upper["status"] == "ok"
        assert len(result_lower["groups"]["A"]) == len(result_upper["groups"]["A"])


class TestStandingsProbabilitiesDeterministic:
    def test_same_state_same_result(self, api_module):
        r1 = api_module.get_wc_tournament_standings_probabilities(group="A", num_simulations=500)
        r2 = api_module.get_wc_tournament_standings_probabilities(group="A", num_simulations=500)
        teams1 = [row["team"] for row in r1["groups"]["A"]]
        teams2 = [row["team"] for row in r2["groups"]["A"]]
        assert teams1 == teams2


class TestStandingsProbabilitiesRemainingMatches:
    def test_remaining_matches_is_int(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities(group="A")
        assert isinstance(result["remaining_matches"], int)
        assert result["remaining_matches"] >= 0

    def test_all_groups_have_remaining_matches(self, api_module):
        result = api_module.get_wc_tournament_standings_probabilities()
        assert isinstance(result["remaining_matches"], int)

"""Tests for WC tournament overall leaderboard API."""

import pytest


@pytest.fixture
def api_module():
    from scoutfootball import api as api_mod

    return api_mod


class TestOverallLeaderboardStatus:
    def test_ok_status(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        assert result["status"] == "ok"

    def test_has_teams_list(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        assert isinstance(result["teams"], list)
        assert len(result["teams"]) >= 48

    def test_has_num_simulations(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        assert isinstance(result["num_simulations"], int)
        assert result["num_simulations"] > 0

    def test_has_mode_strength(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        assert result["mode"] == "strength"

    def test_has_disclaimer(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        assert isinstance(result["disclaimer"], str)
        assert len(result["disclaimer"]) > 0

    def test_has_source_attribution(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        assert "source_attribution" in result

    def test_default_sort_by_advance_prob(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        assert result["sort_by"] == "advance_prob"

    def test_invalid_sort_by_error(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard(sort_by="invalid")
        assert result["status"] == "error"
        assert result["code"] == "invalid_sort"


class TestOverallLeaderboardPerTeam:
    def test_each_team_has_rank(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        for team in result["teams"]:
            assert "rank" in team
            assert isinstance(team["rank"], int)
            assert 1 <= team["rank"] <= len(result["teams"])

    def test_each_team_has_group(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        for team in result["teams"]:
            assert "group" in team
            assert isinstance(team["group"], str)
            assert len(team["group"]) == 1
            assert team["group"] in "ABCDEFGHIJKL"

    def test_each_team_has_position(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        for team in result["teams"]:
            assert "position" in team
            assert isinstance(team["position"], int)
            assert 1 <= team["position"] <= 4

    def test_each_team_has_advance_prob(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        for team in result["teams"]:
            assert "advance_prob" in team
            assert isinstance(team["advance_prob"], float)
            assert 0.0 <= team["advance_prob"] <= 1.0

    def test_each_team_has_win_group_prob(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        for team in result["teams"]:
            assert "win_group_prob" in team
            assert isinstance(team["win_group_prob"], float)
            assert 0.0 <= team["win_group_prob"] <= 1.0

    def test_each_team_has_standings_fields(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        for team in result["teams"]:
            assert "team" in team
            assert "played" in team
            assert "won" in team
            assert "drawn" in team
            assert "lost" in team
            assert "goals_for" in team
            assert "goals_against" in team
            assert "goal_difference" in team
            assert "points" in team


class TestOverallLeaderboardSorting:
    def test_default_sort_by_advance_prob_desc(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        teams = result["teams"]
        for i in range(len(teams) - 1):
            assert teams[i]["advance_prob"] >= teams[i + 1]["advance_prob"] - 1e-9

    def test_sort_by_win_group_prob(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard(sort_by="win_group_prob")
        assert result["sort_by"] == "win_group_prob"
        teams = result["teams"]
        for i in range(len(teams) - 1):
            assert teams[i]["win_group_prob"] >= teams[i + 1]["win_group_prob"] - 1e-9

    def test_sort_by_points(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard(sort_by="points")
        assert result["sort_by"] == "points"
        teams = result["teams"]
        for i in range(len(teams) - 1):
            assert teams[i]["points"] >= teams[i + 1]["points"]

    def test_sort_by_goal_difference(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard(sort_by="goal_difference")
        assert result["sort_by"] == "goal_difference"
        teams = result["teams"]
        for i in range(len(teams) - 1):
            assert teams[i]["goal_difference"] >= teams[i + 1]["goal_difference"]

    def test_sort_by_goals_for(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard(sort_by="goals_for")
        assert result["sort_by"] == "goals_for"
        teams = result["teams"]
        for i in range(len(teams) - 1):
            assert teams[i]["goals_for"] >= teams[i + 1]["goals_for"]


class TestOverallLeaderboardDeterministic:
    def test_same_result_with_same_state(self, api_module):
        result1 = api_module.get_wc_tournament_overall_leaderboard()
        result2 = api_module.get_wc_tournament_overall_leaderboard()
        assert len(result1["teams"]) == len(result2["teams"])
        for t1, t2 in zip(result1["teams"], result2["teams"], strict=True):
            assert t1["team"] == t2["team"]
            assert abs(t1["advance_prob"] - t2["advance_prob"]) < 1e-9
            assert abs(t1["win_group_prob"] - t2["win_group_prob"]) < 1e-9


class TestOverallLeaderboardRemainingMatches:
    def test_has_remaining_matches_field(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard()
        assert "remaining_matches" in result
        assert isinstance(result["remaining_matches"], int)
        assert result["remaining_matches"] >= 0

    def test_custom_num_simulations(self, api_module):
        result = api_module.get_wc_tournament_overall_leaderboard(num_simulations=500)
        assert result["num_simulations"] == 500

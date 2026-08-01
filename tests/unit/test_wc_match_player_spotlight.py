"""Tests for WC match player spotlight API."""

import pytest


@pytest.fixture
def api_module():
    from scoutfootball import api as api_mod

    return api_mod


class TestPlayerSpotlightStatus:
    def test_ok_status(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Argentina", "France", top_n=3)
        assert result["status"] == "ok"

    def test_has_schema(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Argentina", "France", top_n=3)
        assert result["schema"] == "scoutfootball.world-cup-match-player-spotlight"

    def test_has_fixture(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Argentina", "France", top_n=3)
        assert result["fixture"] == {"home_team": "Argentina", "away_team": "France"}

    def test_has_source_attribution(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Argentina", "France", top_n=3)
        assert "source_attribution" in result

    def test_has_disclaimer(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Argentina", "France", top_n=3)
        # Endpoint exposes limitations list; verify non-empty guidance is present
        limitations = result.get("limitations") or []
        assert isinstance(limitations, list)
        assert len(limitations) > 0


class TestPlayerSpotlightPlayers:
    def test_has_players_list(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Argentina", "France", top_n=3)
        assert isinstance(result["players"], list)

    def test_top_n_limits_results(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Argentina", "France", top_n=3)
        assert len(result["players"]) <= 3

    def test_player_has_required_fields(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Argentina", "France", top_n=3)
        if not result["players"]:
            pytest.skip("No rated players in fixture")
        p = result["players"][0]
        for field in ("name", "team", "position", "rating", "spotlight_score", "reason"):
            assert field in p, f"Missing player field: {field}"

    def test_spotlight_score_non_negative(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Argentina", "France", top_n=3)
        for p in result["players"]:
            assert p["spotlight_score"] >= 0.0

    def test_players_sorted_by_score_desc(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Argentina", "France", top_n=5)
        scores = [p["spotlight_score"] for p in result["players"]]
        assert scores == sorted(scores, reverse=True)

    def test_player_team_is_one_of_fixture_teams(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Argentina", "France", top_n=3)
        for p in result["players"]:
            assert p["team"] in {"Argentina", "France"}


class TestPlayerSpotlightErrors:
    def test_same_team_returns_error(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Argentina", "Argentina")
        assert result["status"] == "error"
        assert result["code"] == "invalid_fixture"

    def test_unknown_home_returns_error(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Unknown XI", "France")
        assert result["status"] == "error"
        assert result["code"] == "unknown_team"
        assert "Unknown XI" in result["message"]

    def test_unknown_away_returns_error(self, api_module):
        result = api_module.get_wc_match_player_spotlight("Argentina", "Unknown XI")
        assert result["status"] == "error"
        assert result["code"] == "unknown_team"

"""Tests for WC team form trend API."""

import pytest


@pytest.fixture
def api_module():
    from scoutfootball import api as api_mod

    return api_mod


class TestFormTrendStatus:
    def test_ok_status(self, api_module):
        result = api_module.get_wc_team_form_trend("France", last_n=4)
        assert result["status"] == "ok"

    def test_has_schema(self, api_module):
        result = api_module.get_wc_team_form_trend("France", last_n=4)
        assert result["schema"] == "scoutfootball.world-cup-team-form-trend"

    def test_has_team(self, api_module):
        result = api_module.get_wc_team_form_trend("France", last_n=4)
        assert result["team"] == "France"

    def test_has_source_attribution(self, api_module):
        result = api_module.get_wc_team_form_trend("France", last_n=4)
        assert "source_attribution" in result

    def test_has_disclaimer(self, api_module):
        result = api_module.get_wc_team_form_trend("France", last_n=4)
        limitations = result.get("limitations") or []
        assert isinstance(limitations, list)
        assert len(limitations) > 0


class TestFormTrendMatches:
    def test_has_matches_list(self, api_module):
        result = api_module.get_wc_team_form_trend("France", last_n=4)
        assert isinstance(result["matches"], list)

    def test_last_n_limits_results(self, api_module):
        result = api_module.get_wc_team_form_trend("France", last_n=4)
        assert len(result["matches"]) <= 4

    def test_match_has_required_fields(self, api_module):
        result = api_module.get_wc_team_form_trend("France", last_n=4)
        if not result["matches"]:
            pytest.skip("No matches in trend")
        m = result["matches"][0]
        for field in ("date", "opponent", "venue", "kind"):
            assert field in m, f"Missing match field: {field}"

    def test_venue_is_home_or_away(self, api_module):
        result = api_module.get_wc_team_form_trend("France", last_n=4)
        for m in result["matches"]:
            assert m["venue"] in {"home", "away"}


class TestFormTrendSummary:
    def test_has_summary(self, api_module):
        result = api_module.get_wc_team_form_trend("France", last_n=4)
        assert isinstance(result["summary"], dict)

    def test_summary_has_required_fields(self, api_module):
        result = api_module.get_wc_team_form_trend("France", last_n=4)
        s = result["summary"]
        for field in ("recorded_count", "projected_count", "wins", "draws", "losses",
                      "form_score", "form_score_normalized"):
            assert field in s, f"Missing summary field: {field}"

    def test_form_score_normalized_in_range(self, api_module):
        result = api_module.get_wc_team_form_trend("France", last_n=4)
        s = result["summary"]
        assert 0.0 <= s["form_score_normalized"] <= 1.0


class TestFormTrendErrors:
    def test_unknown_team_returns_error(self, api_module):
        result = api_module.get_wc_team_form_trend("Unknown XI")
        assert result["status"] == "error"
        assert result["code"] == "unknown_team"
        assert "Unknown XI" in result["message"]

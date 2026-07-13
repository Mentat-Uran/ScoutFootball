"""Contracts for source-bounded World Cup pre-match briefings."""

from __future__ import annotations

from scoutfootball import api
from scoutfootball.api import get_world_cup_match_briefing


def test_world_cup_match_briefing_returns_prediction_and_coverage() -> None:
    briefing = get_world_cup_match_briefing("Argentina", "France")

    assert briefing["status"] == "ok"
    assert briefing["schema"] == "scoutfootball.world-cup-match-briefing"
    assert briefing["fixture"] == {"home_team": "Argentina", "away_team": "France"}
    assert briefing["prediction"]["model_type"] == "world_cup_strength_poisson"
    assert len(briefing["prediction"]["score_matrix"]) == 6
    assert briefing["teams"]["home"]["squad"]["total_players"] > 0
    assert 0 <= briefing["teams"]["away"]["squad"]["rating_coverage"] <= 1
    assert len(briefing["teams"]["home"]["squad"]["top_rated_players"]) <= 5
    snapshot = briefing["input_snapshot"]
    assert snapshot["status"] in {"recorded", "not_recorded"}
    assert snapshot["strength_model"]["version"] == "wc-1.0"
    assert snapshot["strength_model"]["score_matrix_max_goals"] == 5
    assert len(briefing["limitations"]) >= 3
    assert "placeholder" in " ".join(briefing["limitations"]).lower()


def test_world_cup_match_briefing_rejects_unknown_team() -> None:
    briefing = get_world_cup_match_briefing("Unknown XI", "France")

    assert "error" in briefing
    assert "Unknown XI" in briefing["error"]


class _BracketState:
    def __init__(self, match: dict) -> None:
        self.knockout = {"matches": [match], "provisional": True}
        self._match = match

    def knockout_match_by_id(self, match_id: str) -> dict | None:
        return self._match if match_id == self._match["match_id"] else None


def test_knockout_briefing_reuses_populated_fixture_and_keeps_context(monkeypatch) -> None:
    match = {
        "match_id": "R32-01", "round": "r32", "round_label": "Round of 32",
        "position": 1, "status": "ready", "home": "Argentina", "away": "France",
    }
    monkeypatch.setattr(api, "_wc_tournament_state", lambda: _BracketState(match))
    monkeypatch.setattr(api, "get_world_cup_match_briefing", lambda home, away: {
        "schema": "scoutfootball.world-cup-match-briefing", "status": "ok",
        "fixture": {"home_team": home, "away_team": away}, "limitations": [],
    })

    briefing = api.get_wc_knockout_match_briefing("R32-01")

    assert briefing["status"] == "ok"
    assert briefing["fixture"] == {"home_team": "Argentina", "away_team": "France"}
    assert briefing["knockout_context"]["match_id"] == "R32-01"
    assert briefing["knockout_context"]["bracket_provisional"] is True


def test_knockout_briefing_does_not_infer_unresolved_opponent(monkeypatch) -> None:
    match = {
        "match_id": "R16-01", "round": "r16", "round_label": "Round of 16",
        "position": 1, "status": "not_ready", "home": None, "away": None,
    }
    monkeypatch.setattr(api, "_wc_tournament_state", lambda: _BracketState(match))

    briefing = api.get_wc_knockout_match_briefing("R16-01")

    assert briefing["status"] == "not_ready"
    assert briefing["fixture"] == {"home_team": None, "away_team": None}

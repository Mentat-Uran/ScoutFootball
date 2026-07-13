"""Contracts for source-bounded World Cup pre-match briefings."""

from __future__ import annotations

from scoutfootball import api
from scoutfootball.api import get_world_cup_match_briefing
from scoutfootball.worldcup.tournament import generate_knockout_bracket, init_state


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


def test_knockout_result_review_compares_only_a_captured_local_snapshot(monkeypatch) -> None:
    match = {
        "match_id": "R32-01", "round": "r32", "round_label": "Round of 32",
        "position": 1, "status": "completed", "home": "Argentina", "away": "France",
        "home_goals": 0, "away_goals": 1, "winner": "France", "decided_by": "regular",
        "prediction_snapshot": {
            "schema": "scoutfootball.world-cup-knockout-prediction-snapshot",
            "prediction": {"home_win_probability": 0.7, "away_win_probability": 0.3},
        },
    }
    monkeypatch.setattr(api, "_wc_tournament_state", lambda: _BracketState(match))

    review = api.get_wc_knockout_match_review("R32-01")

    assert review["status"] == "ok"
    assert review["recording_scope"] == "local application tournament state"
    assert review["comparison"]["predicted_winner"] == "Argentina"
    assert review["comparison"]["recorded_winner"] == "France"
    assert review["comparison"]["directional_result"] == "recorded_upset"
    assert review["comparison"]["recorded_winner_probability"] == 0.3


def test_knockout_result_review_does_not_backfill_missing_snapshot(monkeypatch) -> None:
    match = {
        "match_id": "R32-01", "round": "r32", "position": 1, "status": "completed",
        "home": "Argentina", "away": "France", "home_goals": 2, "away_goals": 1,
        "winner": "Argentina", "decided_by": "regular",
    }
    monkeypatch.setattr(api, "_wc_tournament_state", lambda: _BracketState(match))

    review = api.get_wc_knockout_match_review("R32-01")

    assert review["status"] == "snapshot_not_recorded"
    assert "no retrospective" in " ".join(review["limitations"]).lower()


def test_knockout_prediction_snapshot_is_captured_before_result_projection(monkeypatch) -> None:
    state = init_state()
    state.knockout = generate_knockout_bracket(state)
    match = state.knockout_match_by_id("r32-01")
    monkeypatch.setattr(api, "_get_wc_enriched_squads", lambda: ({"Argentina": [], "France": []}, {
        match["home"]: 0.8, match["away"]: 0.2,
    }))

    snapshot = api._capture_wc_knockout_prediction_snapshot(state, "r32-01")

    assert snapshot is not None
    assert snapshot["fixture"] == {"home_team": match["home"], "away_team": match["away"]}
    assert (
        snapshot["prediction"]["home_win_probability"]
        > snapshot["prediction"]["away_win_probability"]
    )
    assert snapshot["source"] == "pre-recording local knockout bracket projection"


def test_knockout_review_ledger_keeps_missing_snapshots_explicit(monkeypatch) -> None:
    completed = {
        "match_id": "R32-01", "round": "r32", "position": 1, "status": "completed",
        "home": "Argentina", "away": "France", "home_goals": 1, "away_goals": 0,
        "winner": "Argentina", "decided_by": "regular",
        "prediction_snapshot": {
            "prediction": {"home_win_probability": 0.6, "away_win_probability": 0.4}
        },
    }
    older = {
        "match_id": "R32-02", "round": "r32", "position": 2, "status": "completed",
        "home": "Brazil", "away": "Spain", "home_goals": 0, "away_goals": 1,
        "winner": "Spain", "decided_by": "regular",
    }
    state = _BracketState(completed)
    state.knockout["matches"].append(older)
    state.knockout_match_by_id = lambda match_id: next(
        (match for match in state.knockout["matches"] if match["match_id"] == match_id), None
    )
    monkeypatch.setattr(api, "_wc_tournament_state", lambda: state)

    ledger = api.get_wc_knockout_review_ledger()

    assert ledger["status"] == "ok"
    assert ledger["recording_scope"] == "local application tournament state"
    assert ledger["summary"]["completed_matches"] == 2
    assert ledger["summary"]["reviews_with_snapshot"] == 1
    assert ledger["summary"]["snapshots_missing"] == 1

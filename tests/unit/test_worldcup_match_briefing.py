"""Contracts for source-bounded World Cup pre-match briefings."""

from __future__ import annotations

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
    assert len(briefing["limitations"]) >= 3
    assert "placeholder" in " ".join(briefing["limitations"]).lower()


def test_world_cup_match_briefing_rejects_unknown_team() -> None:
    briefing = get_world_cup_match_briefing("Unknown XI", "France")

    assert "error" in briefing
    assert "Unknown XI" in briefing["error"]

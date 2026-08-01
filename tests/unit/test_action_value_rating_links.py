"""Tests for conservative action-value to rating candidate links."""

from __future__ import annotations

import pandas as pd

from scoutfootball.action_value.rating_links import build_action_value_rating_links


def test_rating_link_requires_name_team_and_season_match() -> None:
    actions = pd.DataFrame([{
        "player_id": "7", "player_name": "José Álvarez", "team_name": "Example FC",
        "season": "2023/2024",
    }])
    ratings = pd.DataFrame(
        [{
            "player": "Jose Alvarez", "team": "Example FC", "season": "2324",
            "league": "Example", "sub_position": "CM", "optimized_score": 81.2,
            "minutes": 2200,
        }]
    )

    result = build_action_value_rating_links("7", actions, ratings)

    assert result["status"] == "candidate_available"
    assert result["rating_candidates"] == [{
        "player": "Jose Alvarez", "team": "Example FC", "league": "Example",
        "season": "2324", "position_group": "CM", "optimized_score": 81.2,
        "minutes": 2200, "match_basis": "normalized_name_team_season",
    }]
    assert result["action_identity"]["contexts"][0]["matchable"] is True


def test_rating_link_does_not_match_name_only_or_missing_context() -> None:
    actions = pd.DataFrame([
        {
            "player_id": "7", "player_name": "Alex Smith", "team_name": "North FC",
            "season": "2023/2024",
        },
        {"player_id": "8", "player_name": "No Context", "team_name": "", "season": ""},
    ])
    ratings = pd.DataFrame([
        {"player": "Alex Smith", "team": "South FC", "season": "2324"},
        {"player": "Alex Smith", "team": "North FC", "season": "2223"},
    ])

    wrong_team_or_season = build_action_value_rating_links("7", actions, ratings)
    missing_context = build_action_value_rating_links("8", actions, ratings)

    assert wrong_team_or_season["status"] == "no_strict_candidate"
    assert missing_context["status"] == "no_strict_candidate"
    assert missing_context["action_identity"]["contexts"][0]["matchable"] is False


def test_rating_link_handles_invalid_id_and_missing_rating_artifact() -> None:
    actions = pd.DataFrame([{
        "player_id": "7", "player_name": "Ada", "team_name": "FC", "season": "2023/2024",
    }])

    invalid = build_action_value_rating_links("", actions, pd.DataFrame())
    unavailable = build_action_value_rating_links("7", actions, pd.DataFrame())

    assert invalid["status"] == "invalid_player_id"
    assert unavailable["status"] == "rating_artifact_unavailable"

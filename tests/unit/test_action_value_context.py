"""Contracts for the non-additive player action-value dossier."""

from __future__ import annotations

import pandas as pd

from scoutfootball.action_value.context import build_player_action_value_context


def test_context_keeps_xt_vaep_and_sample_in_separate_sections() -> None:
    xt = pd.DataFrame(
        [
            {
                "player_id": "7",
                "player_name": "Ada",
                "team_id": "10",
                "season": "2023/2024",
                "competition": "League",
                "xt_per_90": 0.4,
            },
        ]
    )
    vaep = pd.DataFrame(
        [
            {
                "player_id": 7,
                "player_name": "Ada",
                "team_id": "10",
                "season_context": "2022/2023 | 2023/2024",
                "vaep_per_90": 1.2,
                "identity_status": "mapped",
            },
        ]
    )
    sample = pd.DataFrame(
        [
            {
                "player_id": "7",
                "match_id": "42",
                "match_date": "2024-03-01",
                "xt_per_90": 0.2,
                "source_coverage": "sample",
            },
        ]
    )

    result = build_player_action_value_context("7", xt, vaep, sample)

    assert result["status"] == "ok"
    assert result["player_name"] == "Ada"
    assert result["models"]["xt"]["granularity"] == "player_team_season"
    assert result["models"]["vaep"]["granularity"] == "player_team_career"
    assert len(result["models"]["xt"]["rows"]) == 1
    assert len(result["models"]["vaep"]["rows"]) == 1
    assert result["match_sample"]["rows"][0]["match_id"] == "42"
    assert result["comparability"]["direct_numeric_comparison"] is False
    assert result["comparability"]["additive"] is False


def test_context_handles_missing_and_invalid_player_ids_explicitly() -> None:
    frame = pd.DataFrame([{"player_id": "7", "player_name": "Ada"}])

    missing = build_player_action_value_context("8", frame, pd.DataFrame(), pd.DataFrame())
    invalid = build_player_action_value_context("", frame, pd.DataFrame(), pd.DataFrame())

    assert missing["status"] == "not_found"
    assert missing["models"]["xt"]["status"] == "not_available"
    assert invalid["status"] == "invalid_player_id"


def test_context_normalizes_integral_identifier_values() -> None:
    xt = pd.DataFrame([{"player_id": 7.0, "player_name": "Ada", "season": "2023/2024"}])

    result = build_player_action_value_context("7", xt, pd.DataFrame(), pd.DataFrame())

    assert result["status"] == "ok"
    assert result["player_id"] == "7"

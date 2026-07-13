from __future__ import annotations

import pandas as pd
import pytest

from scoutfootball.features.understat_history import build_understat_season_proxy


def _understat_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": "1", "player_name": "Ada Striker", "team_title": "Example FC",
                "league": "EPL", "season": "202021", "time": 1800, "games": 24,
                "position": "F S", "goals": 12, "assists": 4, "shots": 70,
                "npxG": 9.5, "xA": 3.2,
            },
            {
                "id": "2", "player_name": "Bert Mid", "team_title": "Elsewhere",
                "league": "RFPL", "season": "202021", "time": 1800, "games": 24,
                "position": "M S", "goals": 4, "assists": 5, "shots": 30,
                "npxG": 3.0, "xA": 4.0,
            },
            {
                "id": "3", "player_name": "Cara Keeper", "team_title": "Example FC",
                "league": "EPL", "season": "202324", "time": 0, "games": 0,
                "position": "GK", "goals": 0, "assists": 0, "shots": 0,
                "npxG": 0.0, "xA": 0.0,
            },
        ],
    )


def test_build_understat_proxy_keeps_supported_historical_rows() -> None:
    proxy = build_understat_season_proxy(_understat_rows())

    assert len(proxy) == 1
    row = proxy.iloc[0]
    assert row["season_id"] == "2021"
    assert row["competition_id"] == "ENG-Premier League"
    assert row["position_group"] == "FW"
    assert row["source_name"] == "understat"
    assert row["data_granularity"] == "season_proxy"
    assert row["starts"] == 0
    assert row["has_expected_metrics"]


def test_build_understat_proxy_excludes_higher_fidelity_overlap() -> None:
    proxy = build_understat_season_proxy(_understat_rows(), excluded_season_ids={"2021"})

    assert proxy.empty


def test_build_understat_proxy_allows_missing_optional_position() -> None:
    proxy = build_understat_season_proxy(_understat_rows().drop(columns="position"))

    assert proxy.iloc[0]["position_group"] == "UNK"


def test_build_understat_proxy_requires_core_fields() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        build_understat_season_proxy(pd.DataFrame({"id": ["1"]}))

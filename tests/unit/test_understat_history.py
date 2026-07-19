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


def test_multi_team_comma_team_title_resolves_to_first_club() -> None:
    """Comma-separated team_title (mid-season transfer) resolves to first club.

    Understat aggregates season stats across all clubs a player appeared for,
    joining team names with commas.  This pollutes team-level aggregations
    and team-name matching.  The fix keeps the first club as primary team
    and sets multi_team_season=True.
    """
    rows = pd.DataFrame(
        [
            {
                "id": "1", "player_name": "Transfer Striker",
                "team_title": "Club A,Club B",
                "league": "EPL", "season": "202021", "time": 1800, "games": 24,
                "position": "F S", "goals": 12, "assists": 4, "shots": 70,
                "npxG": 9.5, "xA": 3.2,
            },
            {
                "id": "2", "player_name": "Stable Mid",
                "team_title": "Single Club",
                "league": "EPL", "season": "202021", "time": 2000, "games": 28,
                "position": "M S", "goals": 3, "assists": 5, "shots": 40,
                "npxG": 2.0, "xA": 4.0,
            },
        ],
    )
    proxy = build_understat_season_proxy(rows)
    assert len(proxy) == 2

    multi_team_row = proxy[proxy["player_name"] == "Transfer Striker"].iloc[0]
    single_team_row = proxy[proxy["player_name"] == "Stable Mid"].iloc[0]

    assert multi_team_row["team_name"] == "Club A"
    assert bool(multi_team_row["multi_team_season"]) is True
    assert "," not in multi_team_row["team_name"]

    assert single_team_row["team_name"] == "Single Club"
    assert bool(single_team_row["multi_team_season"]) is False


def test_three_team_comma_team_title_resolves_to_first() -> None:
    """Three-club comma-separated team_title also resolves to first club."""
    rows = pd.DataFrame(
        [
            {
                "id": "1", "player_name": "Journeyman",
                "team_title": "Club X,Club Y,Club Z",
                "league": "Serie_A", "season": "202021", "time": 900, "games": 15,
                "position": "M S", "goals": 2, "assists": 1, "shots": 20,
                "npxG": 1.5, "xA": 1.0,
            },
        ],
    )
    proxy = build_understat_season_proxy(rows)
    assert len(proxy) == 1
    assert proxy.iloc[0]["team_name"] == "Club X"
    assert bool(proxy.iloc[0]["multi_team_season"]) is True


def test_no_comma_team_title_has_multi_team_season_false() -> None:
    """Rows without comma in team_title have multi_team_season=False."""
    proxy = build_understat_season_proxy(_understat_rows())
    assert len(proxy) >= 1
    for _, row in proxy.iterrows():
        assert bool(row["multi_team_season"]) is False
        assert "," not in row["team_name"]

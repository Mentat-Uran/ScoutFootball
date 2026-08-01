"""Tests for the World Cup squad scouting-needs overlay.

Covers :func:`scoutfootball.api.get_wc_squad_scouting_needs`, which
annotates each WC squad player with their club team's position-group gap
(shallow / low_quality / missing) at the player's listed position.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scoutfootball import api
from scoutfootball.api import get_wc_squad_scouting_needs
from scoutfootball.worldcup.data import SquadPlayer


def _build_ratings_df() -> pd.DataFrame:
    """Build a synthetic ratings frame matching the depth_df layout.

    - "Gap Team" has a shallow ST gap, low_quality CB gap, deep CM strength
    - "Strong Team" has no gaps at ST/CB/CM
    - "Unknown Club" is absent (no rows) -> team_not_found
    """
    rows: list[dict] = []

    def add(team: str, league: str, pos: str, scores: list[float]) -> None:
        for i, sc in enumerate(scores):
            rows.append({
                "player": f"{team} {pos} P{i}",
                "player_id": f"{team.replace(' ', '_')}_{pos}_{i}",
                "team": team,
                "league": league,
                "season": "2526",
                "position_group": pos,
                "sub_position": pos,
                "optimized_score": sc,
                "minutes": 1500.0 - i * 50,
                "matches": 20,
                "npg_p90": 0.2 + i * 0.01,
                "assists_p90": 0.1 + i * 0.005,
                "defense_composite": 50.0 + i * 0.5,
                "possession_composite": 50.0 + i * 0.3,
                "confidence_level": "HIGH",
                "low_appearance": False,
            })

    # Gap Team — shallow ST (1 player), low_quality CB (3 below p40),
    # deep CM (5 above p60), adequate FB (2 players)
    add("Gap Team", "Premier League", "ST", [70.0])
    add("Gap Team", "Premier League", "CB", [50.0, 52.0, 54.0])
    add("Gap Team", "Premier League", "CM", [75.0, 77.0, 78.0, 80.0, 82.0])
    add("Gap Team", "Premier League", "FB", [60.0, 65.0])
    # Strong Team — no gaps at ST/CB/CM (4 players each, deep)
    add("Strong Team", "Premier League", "ST", [70.0, 75.0, 80.0, 85.0])
    add("Strong Team", "Premier League", "CB", [65.0, 70.0, 75.0, 80.0])
    add("Strong Team", "Premier League", "CM", [65.0, 70.0, 75.0, 80.0])

    return pd.DataFrame(rows)


@pytest.fixture
def _mock_env(monkeypatch):
    """Mock the rating matrix + WC squad for a synthetic team."""
    df = _build_ratings_df()

    def _load(**kwargs):
        result = df.copy()
        season = kwargs.get("season")
        if season and "season" in result.columns:
            result = result[result["season"] == season]
        return result.reset_index(drop=True)

    monkeypatch.setattr(api, "load_player_ratings", _load)

    squad = [
        # Player at Gap Team ST -> shallow gap
        SquadPlayer("Gap Striker", "ST", "Gap Team", "Premier League"),
        # Player at Gap Team CB -> low_quality gap
        SquadPlayer("Gap Defender", "CB", "Gap Team", "Premier League"),
        # Player at Gap Team CM -> no gap (deep strength)
        SquadPlayer("Gap Mid", "CM", "Gap Team", "Premier League"),
        # Player at Strong Team ST -> no gap
        SquadPlayer("Strong Striker", "ST", "Strong Team", "Premier League"),
        # Player at unknown club -> team_not_found
        SquadPlayer("Unknown Player", "ST", "Unknown Club", "Other League"),
    ]
    monkeypatch.setattr(
        api,
        "_get_wc_enriched_squads",
        lambda: ({"Test Nation": squad}, {}),
    )
    monkeypatch.setattr(api, "get_team_group", lambda team: "Group A")
    monkeypatch.setattr(api, "HOSTS", [])
    return df


# ── status / structure ──────────────────────────────────────────────


def test_scouting_needs_ok_status(_mock_env):
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    assert result["status"] == "ok"
    assert result["team"] == "Test Nation"
    assert result["group"] == "Group A"
    assert result["is_host"] is False
    assert result["season"] == "2526"


def test_scouting_needs_no_data_when_ratings_empty(monkeypatch):
    """Empty rating matrix should return no_data."""
    monkeypatch.setattr(
        api, "load_player_ratings", lambda **k: pd.DataFrame()
    )
    monkeypatch.setattr(
        api,
        "_get_wc_enriched_squads",
        lambda: ({"Test Nation": []}, {}),
    )
    monkeypatch.setattr(api, "get_team_group", lambda team: "Group A")
    monkeypatch.setattr(api, "HOSTS", [])

    result = get_wc_squad_scouting_needs("Test Nation")
    assert result["status"] == "no_data"
    assert result["club_gaps"] == {}
    assert result["players"] == []
    assert "disclaimer" in result


def test_scouting_needs_players_list_populated(_mock_env):
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    assert len(result["players"]) == 5
    names = [p["name"] for p in result["players"]]
    assert "Gap Striker" in names
    assert "Unknown Player" in names


def test_scouting_needs_player_fields(_mock_env):
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    for p in result["players"]:
        assert "name" in p
        assert "position" in p
        assert "club" in p
        assert "club_league" in p
        assert "has_rating" in p
        assert "rating" in p
        assert "rating_confidence" in p
        assert "club_gap_status" in p
        assert "scouting_need" in p


def test_scouting_needs_disclaimer_present(_mock_env):
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    assert "disclaimer" in result
    assert "descriptive overlay" in result["disclaimer"]


def test_scouting_needs_source_attribution_present(_mock_env):
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    assert "source_attribution" in result
    assert "rating matrix" in result["source_attribution"]


# ── per-player annotation ───────────────────────────────────────────


def test_scouting_needs_shallow_gap_annotated(_mock_env):
    """Gap Team ST player should have a shallow scouting_need."""
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    p = next(p for p in result["players"] if p["name"] == "Gap Striker")
    assert p["club_gap_status"] == "ok"
    assert p["scouting_need"] is not None
    assert p["scouting_need"]["position_group"] == "ST"
    assert p["scouting_need"]["gap_type"] == "shallow"
    assert p["scouting_need"]["n_players"] == 1


def test_scouting_needs_low_quality_gap_annotated(_mock_env):
    """Gap Team CB player should have a low_quality scouting_need."""
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    p = next(p for p in result["players"] if p["name"] == "Gap Defender")
    assert p["club_gap_status"] == "ok"
    assert p["scouting_need"] is not None
    assert p["scouting_need"]["position_group"] == "CB"
    assert p["scouting_need"]["gap_type"] == "low_quality"
    assert p["scouting_need"]["n_players"] == 3
    assert "league_p40" in p["scouting_need"]


def test_scouting_needs_no_gap_when_position_is_deep(_mock_env):
    """Gap Team CM (deep strength) should have scouting_need == None."""
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    p = next(p for p in result["players"] if p["name"] == "Gap Mid")
    assert p["club_gap_status"] == "ok"
    assert p["scouting_need"] is None


def test_scouting_needs_no_gap_for_strong_team(_mock_env):
    """Strong Team ST (deep) should have scouting_need == None."""
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    p = next(p for p in result["players"] if p["name"] == "Strong Striker")
    assert p["club_gap_status"] == "ok"
    assert p["scouting_need"] is None


def test_scouting_needs_team_not_found_for_unknown_club(_mock_env):
    """Unknown Club (no rows in rating matrix) -> team_not_found + null."""
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    p = next(p for p in result["players"] if p["name"] == "Unknown Player")
    assert p["club_gap_status"] == "team_not_found"
    assert p["scouting_need"] is None


# ── club_gaps aggregation ───────────────────────────────────────────


def test_scouting_needs_club_gaps_keys(_mock_env):
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    assert "Gap Team" in result["club_gaps"]
    assert "Strong Team" in result["club_gaps"]
    assert "Unknown Club" in result["club_gaps"]


def test_scouting_needs_club_gaps_entry_fields(_mock_env):
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    entry = result["club_gaps"]["Gap Team"]
    assert entry["status"] == "ok"
    assert entry["league"] == "Premier League"
    assert entry["n_gaps"] >= 2
    assert isinstance(entry["gaps_by_position"], dict)
    assert "ST" in entry["gaps_by_position"]
    assert "CB" in entry["gaps_by_position"]


def test_scouting_needs_club_gaps_unknown_team_status(_mock_env):
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    assert result["club_gaps"]["Unknown Club"]["status"] == "team_not_found"
    assert result["club_gaps"]["Unknown Club"]["n_gaps"] == 0


def test_scouting_needs_club_gaps_dedupes_per_club(_mock_env):
    """compute_position_gap_report should run once per unique club, not per player."""
    # The fixture has 5 players across 3 clubs. The club_gaps dict should
    # have exactly 3 keys (no duplicates for Gap Team which has 3 players).
    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    assert len(result["club_gaps"]) == 3


# ── defensive / error handling ──────────────────────────────────────


def test_scouting_needs_handles_gap_report_exception(monkeypatch):
    """If compute_position_gap_report raises, the player path should still succeed."""
    df = _build_ratings_df()
    monkeypatch.setattr(api, "load_player_ratings", lambda **k: df)
    squad = [
        SquadPlayer("Boom Player", "ST", "Boom Club", "Premier League"),
    ]
    monkeypatch.setattr(
        api,
        "_get_wc_enriched_squads",
        lambda: ({"Test Nation": squad}, {}),
    )
    monkeypatch.setattr(api, "get_team_group", lambda team: "Group A")
    monkeypatch.setattr(api, "HOSTS", [])

    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "scoutfootball.features.team_style.compute_position_gap_report",
        _boom,
    )

    result = get_wc_squad_scouting_needs("Test Nation", season="2526")
    assert result["status"] == "ok"
    entry = result["club_gaps"]["Boom Club"]
    assert entry["status"] == "error"
    p = result["players"][0]
    assert p["club_gap_status"] == "error"
    assert p["scouting_need"] is None


def test_scouting_needs_no_mutation_of_input_df(_mock_env):
    df = _build_ratings_df()
    df_before = df.copy()
    get_wc_squad_scouting_needs("Test Nation", season="2526")
    pd.testing.assert_frame_equal(df, df_before)


def test_scouting_needs_season_filter_propagated(monkeypatch):
    """The `season` parameter should be passed through to the gap report."""
    df = _build_ratings_df()
    monkeypatch.setattr(api, "load_player_ratings", lambda **k: df)
    squad = [SquadPlayer("P", "ST", "Gap Team", "Premier League")]
    monkeypatch.setattr(
        api,
        "_get_wc_enriched_squads",
        lambda: ({"Test Nation": squad}, {}),
    )
    monkeypatch.setattr(api, "get_team_group", lambda team: "Group A")
    monkeypatch.setattr(api, "HOSTS", [])

    captured: dict = {}

    from scoutfootball.features import team_style

    real = team_style.compute_position_gap_report

    def _spy(df_in, team, **kwargs):
        captured["season"] = kwargs.get("season")
        return real(df_in, team, **kwargs)

    monkeypatch.setattr(
        "scoutfootball.features.team_style.compute_position_gap_report", _spy
    )

    get_wc_squad_scouting_needs("Test Nation", season="2526")
    assert captured["season"] == "2526"


def test_scouting_needs_min_minutes_propagated(monkeypatch):
    df = _build_ratings_df()
    monkeypatch.setattr(api, "load_player_ratings", lambda **k: df)
    squad = [SquadPlayer("P", "ST", "Gap Team", "Premier League")]
    monkeypatch.setattr(
        api,
        "_get_wc_enriched_squads",
        lambda: ({"Test Nation": squad}, {}),
    )
    monkeypatch.setattr(api, "get_team_group", lambda team: "Group A")
    monkeypatch.setattr(api, "HOSTS", [])

    captured: dict = {}

    from scoutfootball.features import team_style

    real = team_style.compute_position_gap_report

    def _spy(df_in, team, **kwargs):
        captured["min_player_minutes"] = kwargs.get("min_player_minutes")
        return real(df_in, team, **kwargs)

    monkeypatch.setattr(
        "scoutfootball.features.team_style.compute_position_gap_report", _spy
    )

    get_wc_squad_scouting_needs("Test Nation", min_player_minutes=750.0)
    assert captured["min_player_minutes"] == 750.0

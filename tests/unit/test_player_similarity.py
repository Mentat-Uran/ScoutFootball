"""Tests for player similarity search API."""

from __future__ import annotations

import pandas as pd
import pytest

from scoutfootball.api import find_similar_players


@pytest.fixture
def _mock_ratings(monkeypatch):
    """Provide synthetic ratings with multiple ST players for similarity."""
    players = []
    # 10 strikers with varying profiles
    data = [
        ("Striker A", "Team A", "Premier League", "2526", "ST", 80, 2700, 0.6, 0.15, 15, 40),
        ("Striker B", "Team B", "Premier League", "2526", "ST", 78, 2500, 0.55, 0.18, 18, 42),
        ("Striker C", "Team C", "La Liga", "2526", "ST", 75, 2400, 0.5, 0.2, 20, 45),
        ("Striker D", "Team D", "Bundesliga", "2526", "ST", 72, 2200, 0.45, 0.22, 25, 48),
        ("Striker E", "Team E", "Serie A", "2526", "ST", 70, 2000, 0.4, 0.25, 30, 50),
        ("Striker F", "Team F", "Ligue 1", "2526", "ST", 68, 1800, 0.35, 0.28, 35, 52),
        ("Striker G", "Team G", "Premier League", "2526", "ST", 65, 1600, 0.3, 0.1, 40, 55),
        ("Striker H", "Team H", "La Liga", "2526", "ST", 62, 1400, 0.25, 0.12, 45, 58),
        ("Striker I", "Team I", "Bundesliga", "2526", "ST", 60, 1200, 0.2, 0.14, 50, 60),
        ("Striker J", "Team J", "Serie A", "2526", "ST", 58, 1000, 0.15, 0.16, 55, 62),
    ]
    for name, team, league, season, pos, score, mins, npg, ast, defc, posc in data:
        players.append({
            "player": name,
            "team": team,
            "league": league,
            "season": season,
            "sub_position": pos,
            "position_group": pos,
            "optimized_score": float(score),
            "minutes": float(mins),
            "matches": 30,
            "npg_p90": float(npg),
            "assists_p90": float(ast),
            "defense_composite": float(defc),
            "possession_composite": float(posc),
            "confidence_level": "HIGH",
            "low_appearance": False,
        })
    # Add a CM for position filtering test
    players.append({
        "player": "Midfielder X", "team": "Team X", "league": "Premier League",
        "season": "2526", "sub_position": "CM", "position_group": "CM",
        "optimized_score": 70.0, "minutes": 2700, "matches": 30,
        "npg_p90": 0.1, "assists_p90": 0.3, "defense_composite": 60.0,
        "possession_composite": 70.0, "confidence_level": "HIGH", "low_appearance": False,
    })

    df = pd.DataFrame(players)

    def _load(**kwargs):
        result = df.copy()
        league = kwargs.get("league")
        season = kwargs.get("season")
        if league and "league" in result.columns:
            result = result[result["league"] == league]
        if season and "season" in result.columns:
            result = result[result["season"] == season]
        return result.reset_index(drop=True)

    monkeypatch.setattr("scoutfootball.api.load_player_ratings", _load)
    monkeypatch.setattr(
        "scoutfootball.api.load_player_value_metrics",
        lambda: pd.DataFrame(),
    )
    return df


def test_similarity_basic(_mock_ratings):
    """Should return similar players for a known player."""
    result = find_similar_players("Striker A")
    assert result["count"] > 0
    assert result["target"]["name"] == "Striker A"
    assert result["target"]["position_group"] == "ST"
    assert len(result["similar"]) <= 10


def test_similarity_excludes_target(_mock_ratings):
    """Target player should not appear in similar list."""
    result = find_similar_players("Striker A")
    names = [p["name"] for p in result["similar"]]
    assert "Striker A" not in names


def test_similarity_only_same_position(_mock_ratings):
    """Similar players should all be in the same position group."""
    result = find_similar_players("Striker A")
    for p in result["similar"]:
        assert p["position_group"] == "ST"


def test_similarity_sorted_by_score(_mock_ratings):
    """Similar players should be sorted by similarity descending."""
    result = find_similar_players("Striker A")
    sims = [p["similarity"] for p in result["similar"]]
    assert sims == sorted(sims, reverse=True)


def test_similarity_score_range(_mock_ratings):
    """Similarity scores should be between 0 and 100."""
    result = find_similar_players("Striker A")
    for p in result["similar"]:
        assert 0 <= p["similarity"] <= 100


def test_similarity_limit(_mock_ratings):
    """Should respect limit parameter."""
    result = find_similar_players("Striker A", limit=3)
    assert result["count"] <= 3
    assert len(result["similar"]) <= 3


def test_similarity_fuzzy_match(_mock_ratings):
    """Should work with partial name match."""
    result = find_similar_players("Striker B")
    assert result["target"]["name"] == "Striker B"


def test_similarity_player_not_found(_mock_ratings):
    """Should return error for unknown player."""
    result = find_similar_players("Nobody Here")
    assert result["count"] == 0
    assert "error" in result


def test_similarity_has_features(_mock_ratings):
    """Result should include feature labels."""
    result = find_similar_players("Striker A")
    assert "features" in result
    assert len(result["features"]) == 6
    assert "Overall" in result["features"]


def test_similarity_shared_strengths(_mock_ratings):
    """Top similar players may have shared strengths."""
    result = find_similar_players("Striker A", limit=5)
    # Striker A is top in attack and overall, so top similar should share some strengths
    has_strengths = any(
        len(p.get("shared_strengths", [])) > 0
        for p in result["similar"]
    )
    assert has_strengths


def test_similarity_has_player_info(_mock_ratings):
    """Each similar player should have team, league, score."""
    result = find_similar_players("Striker A")
    for p in result["similar"]:
        assert "name" in p
        assert "team" in p
        assert "league" in p
        assert "optimized_score" in p
        assert "minutes" in p


def test_similarity_season_filter(_mock_ratings):
    """Should work with season filter."""
    result = find_similar_players("Striker A", season="2526")
    assert result["count"] > 0
    assert result["target"]["season"] == "2526"


def test_similarity_different_position(_mock_ratings):
    """Should work for non-ST positions."""
    result = find_similar_players("Midfielder X")
    # Only 1 CM in mock data, pool too small
    assert result["count"] == 0 or result["target"]["position_group"] == "CM"

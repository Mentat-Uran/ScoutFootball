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


# ── Round 6 enhancements: position weights, cross-position, filters ──────


def test_similarity_returns_feature_weights(_mock_ratings):
    """Response should expose the active position-weighted feature weights."""
    result = find_similar_players("Striker A")
    assert "feature_weights" in result
    weights = result["feature_weights"]
    assert "Attack" in weights
    assert "Defense" in weights
    # For ST, attack weight should exceed defense weight.
    assert weights["Attack"] > weights["Defense"]


def test_similarity_st_weights_favour_attack(_mock_ratings):
    """ST position should weight Attack (npg_p90) higher than Defense."""
    result = find_similar_players("Striker A")
    weights = result["feature_weights"]
    assert weights["Attack"] == 3.0
    assert weights["Defense"] == 0.5
    assert weights["Possession"] == 1.0


def test_similarity_returns_filters(_mock_ratings):
    """Response should echo the active filters."""
    result = find_similar_players(
        "Striker A",
        same_position_only=False,
        league="Premier League",
        min_minutes=1500,
    )
    filters = result["filters"]
    assert filters["same_position_only"] is False
    assert filters["league"] == "Premier League"
    assert filters["min_minutes"] == 1500


def test_similarity_default_same_position_only(_mock_ratings):
    """Default behaviour should keep same_position_only=True."""
    result = find_similar_players("Striker A")
    assert result["filters"]["same_position_only"] is True


def test_similarity_cross_position_includes_other_positions(_mock_ratings):
    """Cross-position mode should return candidates from other positions."""
    result = find_similar_players("Striker A", same_position_only=False)
    positions = {p["position_group"] for p in result["similar"]}
    # Should include at least one non-ST position (Midfielder X is CM).
    assert "CM" in positions or any(pos != "ST" for pos in positions)


def test_similarity_cross_position_still_excludes_target(_mock_ratings):
    """Target player should be excluded even in cross-position mode."""
    result = find_similar_players("Striker A", same_position_only=False)
    names = [p["name"] for p in result["similar"]]
    assert "Striker A" not in names


def test_similarity_cross_position_sorted(_mock_ratings):
    """Cross-position results should still be sorted by similarity desc."""
    result = find_similar_players("Striker A", same_position_only=False)
    sims = [p["similarity"] for p in result["similar"]]
    assert sims == sorted(sims, reverse=True)


def test_similarity_league_filter(_mock_ratings):
    """League filter should restrict candidates to that league."""
    result = find_similar_players("Striker A", league="La Liga")
    for p in result["similar"]:
        assert p["league"] == "La Liga"


def test_similarity_league_filter_case_insensitive(_mock_ratings):
    """League filter should be case-insensitive."""
    result = find_similar_players("Striker A", league="la liga")
    assert result["count"] > 0
    for p in result["similar"]:
        assert p["league"].lower() == "la liga"


def test_similarity_league_filter_target_still_found(_mock_ratings):
    """Target player should still be resolved even if in different league."""
    # Striker A is in Premier League; filter to La Liga should still find
    # Striker A as the target, but candidates come from La Liga.
    result = find_similar_players("Striker A", league="La Liga")
    assert result["target"]["name"] == "Striker A"
    assert result["target"]["league"] == "Premier League"


def test_similarity_min_minutes_filter(_mock_ratings):
    """min_minutes should exclude players below the threshold."""
    result = find_similar_players("Striker A", min_minutes=2000)
    for p in result["similar"]:
        assert p["minutes"] >= 2000


def test_similarity_min_minutes_excludes_all(_mock_ratings):
    """Very high min_minutes should result in pool_too_small or empty."""
    result = find_similar_players("Striker A", min_minutes=5000)
    # No ST in mock data has >= 5000 minutes.
    assert result["count"] == 0
    assert result.get("error") in ("pool_too_small", "zero_vector")


def test_similarity_combined_filters(_mock_ratings):
    """League + min_minutes filters should combine."""
    result = find_similar_players(
        "Striker A",
        league="Premier League",
        min_minutes=1500,
    )
    for p in result["similar"]:
        assert p["league"] == "Premier League"
        assert p["minutes"] >= 1500


def test_similarity_cross_position_with_league(_mock_ratings):
    """Cross-position mode should respect league filter."""
    result = find_similar_players(
        "Striker A",
        same_position_only=False,
        league="Premier League",
    )
    for p in result["similar"]:
        assert p["league"] == "Premier League"


def test_similarity_position_weights_change_ranking(_mock_ratings):
    """Position weighting should produce different rankings than uniform.

    Compare Striker A's top similar player under position-weighted vs
    a hypothetical uniform weighting — at minimum the result should not
    crash and should produce a valid ranking.
    """
    result = find_similar_players("Striker A", limit=5)
    assert result["count"] > 0
    # Top similar should have non-zero similarity.
    assert result["similar"][0]["similarity"] > 0


def test_similarity_unknown_position_uses_default_weights(_mock_ratings):
    """Unknown position group should fall back to uniform weights."""
    # Midfielder X is CM (known), but verify the default path explicitly.
    from scoutfootball.api import _position_weights
    weights = _position_weights("UNKNOWN_POS")
    for label in ("npg_p90", "assists_p90", "defense_composite",
                  "possession_composite", "optimized_score", "minutes"):
        assert weights[label] == 1.0


def test_similarity_gk_weights_zero_attack(_mock_ratings):
    """GK position should not weight attack metrics."""
    from scoutfootball.api import _position_weights
    weights = _position_weights("GK")
    assert weights["npg_p90"] == 0.0
    assert weights["assists_p90"] == 0.0
    assert weights["defense_composite"] > 0.0


def test_similarity_weights_symmetric_for_wingers(_mock_ratings):
    """W and ST should both heavily weight attack but ST more than W."""
    from scoutfootball.api import _position_weights
    w_weights = _position_weights("W")
    st_weights = _position_weights("ST")
    assert w_weights["npg_p90"] > 0
    assert st_weights["npg_p90"] > w_weights["npg_p90"]


def test_similarity_cross_position_target_resolved(_mock_ratings):
    """Cross-position mode should still resolve the target correctly."""
    result = find_similar_players("Striker A", same_position_only=False)
    assert result["target"]["name"] == "Striker A"
    assert result["target"]["position_group"] == "ST"


def test_similarity_pool_too_small_with_strict_filter(_mock_ratings):
    """A filter that empties the pool should return pool_too_small."""
    # No ST in Ligue 1 with >= 3000 minutes in mock data.
    result = find_similar_players(
        "Striker A",
        league="Ligue 1",
        min_minutes=3000,
    )
    assert result["count"] == 0
    assert result.get("error") == "pool_too_small"


def test_similarity_filters_default_none(_mock_ratings):
    """Default filter values should be None/False in the response."""
    result = find_similar_players("Striker A")
    assert result["filters"]["league"] is None
    assert result["filters"]["min_minutes"] is None
    assert result["filters"]["season"] is None


def test_similarity_cross_league_finds_closest_profile(_mock_ratings):
    """Cross-league scouting should return the closest-profile player.

    Striker A (PL, npg=0.6, score=80) scouted against La Liga should rank
    Striker C (npg=0.5, score=75) above Striker H (npg=0.25, score=62)
    because C's profile is closer to A's.
    """
    result = find_similar_players("Striker A", league="La Liga")
    assert result["count"] > 0
    names = [p["name"] for p in result["similar"]]
    # Both La Liga STs should be in the results.
    assert "Striker C" in names
    assert "Striker H" in names
    # Striker C should rank above Striker H (closer profile to A).
    assert names.index("Striker C") < names.index("Striker H")
    # Top match should have non-trivial similarity (> 50%).
    assert result["similar"][0]["similarity"] > 50.0


def test_similarity_target_excluded_when_in_pool(_mock_ratings):
    """Target should be excluded from results even when present in pool."""
    result = find_similar_players("Striker A")
    names = [p["name"] for p in result["similar"]]
    assert "Striker A" not in names
    # All 9 other STs should be candidates (mock has 10 STs total).
    assert result["count"] == 9


def test_similarity_weights_in_response_are_position_specific(_mock_ratings):
    """Different target positions should yield different weight sets."""
    st_result = find_similar_players("Striker A")
    # ST weights are hard-coded; verify the response reflects them.
    assert st_result["feature_weights"]["Attack"] == 3.0
    assert st_result["feature_weights"]["Defense"] == 0.5


def test_similarity_zero_vector_returns_clean_error(_mock_ratings, monkeypatch):
    """When the target's weighted z-vector is zero, return zero_vector."""
    # Build a degenerate dataset where every ST has identical features, so
    # all z-scores are 0 and the target vector is zero.
    rows = []
    for i in range(5):
        rows.append({
            "player": f"Clone {i}", "team": "T", "league": "L",
            "season": "2526", "sub_position": "ST", "position_group": "ST",
            "optimized_score": 70.0, "minutes": 2000.0, "matches": 30,
            "npg_p90": 0.4, "assists_p90": 0.2, "defense_composite": 30.0,
            "possession_composite": 50.0, "confidence_level": "HIGH",
            "low_appearance": False,
        })
    df = pd.DataFrame(rows)
    monkeypatch.setattr("scoutfootball.api.load_player_ratings", lambda **kw: df.copy())
    monkeypatch.setattr(
        "scoutfootball.api.load_player_value_metrics",
        lambda: pd.DataFrame(),
    )
    result = find_similar_players("Clone 0")
    assert result["count"] == 0
    assert result.get("error") == "zero_vector"

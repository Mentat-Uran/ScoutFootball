"""Tests for the team tactical-style clustering module.

Covers ``compute_team_style_profiles`` and
``compute_team_style_clusters`` in ``scoutfootball.features.team_style``.
The fixtures use synthetic pandas frames that mirror the player-ratings
schema so the helpers can be exercised without loading disk artifacts.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scoutfootball.features.team_style import (
    compute_cluster_recruits,
    compute_player_style_fit,
    compute_team_style_clusters,
    compute_team_style_profiles,
)


def _build_team_style_df() -> pd.DataFrame:
    """Build a synthetic frame with 8 teams across 1 season.

    Team A/B: attacking (high npg_p90, low defense)
    Team C/D: defensive (low npg_p90, high defense)
    Team E/F: possession-heavy (high possession_composite)
    Team G/H: balanced (mid-range on all)
    """
    rows: list[dict] = []
    templates = [
        # (team, league, attack, creation, defense, possession)
        ("Team A", "Premier League", 0.6, 0.3, 10.0, 35.0),
        ("Team B", "Premier League", 0.55, 0.28, 12.0, 33.0),
        ("Team C", "La Liga", 0.15, 0.1, 75.0, 55.0),
        ("Team D", "La Liga", 0.18, 0.12, 70.0, 58.0),
        ("Team E", "Bundesliga", 0.3, 0.35, 40.0, 80.0),
        ("Team F", "Bundesliga", 0.28, 0.32, 42.0, 78.0),
        ("Team G", "Serie A", 0.3, 0.2, 45.0, 50.0),
        ("Team H", "Serie A", 0.32, 0.22, 43.0, 52.0),
    ]
    for team, league, npg, ast, defc, poss in templates:
        # 5 players per team with similar style profile
        for i in range(5):
            rows.append({
                "player": f"{team} P{i}",
                "player_id": f"{team}_{i}",
                "team": team,
                "league": league,
                "season": "2526",
                "position_group": "ST" if i == 0 else ("CM" if i < 3 else "CB"),
                "sub_position": "ST",
                "optimized_score": 60.0 + i * 3,
                "minutes": 2000.0 - i * 100,
                "matches": 25,
                "npg_p90": npg + i * 0.02,
                "assists_p90": ast + i * 0.01,
                "defense_composite": defc + i * 1.5,
                "possession_composite": poss + i * 0.8,
                "confidence_level": "HIGH",
                "low_appearance": False,
            })
    return pd.DataFrame(rows)


@pytest.fixture
def style_df() -> pd.DataFrame:
    return _build_team_style_df()


# ── compute_team_style_profiles ──────────────────────────────────────────


def test_profiles_empty():
    """Empty input should return an empty list."""
    assert compute_team_style_profiles(pd.DataFrame()) == []


def test_profiles_basic(style_df):
    """Should return one profile per team-season."""
    profiles = compute_team_style_profiles(style_df)
    assert len(profiles) == 8
    team_names = {p.team for p in profiles}
    assert team_names == {"Team A", "Team B", "Team C", "Team D",
                          "Team E", "Team F", "Team G", "Team H"}


def test_profiles_minutes_weighted(style_df):
    """Minutes-weighting should give more weight to higher-minute players."""
    profiles = compute_team_style_profiles(style_df)
    # Team A's player 0 has highest minutes and npg_p90=0.6
    team_a = next(p for p in profiles if p.team == "Team A")
    # The weighted attack should be close to the mean but slightly lower
    # because the highest-npg player also has the highest minutes.
    assert team_a.attack > 0.5  # should be near 0.6
    assert team_a.n_players == 5
    assert team_a.total_minutes > 0


def test_profiles_season_filter(style_df):
    """Season filter should narrow results."""
    profiles = compute_team_style_profiles(style_df, season="2526")
    assert len(profiles) == 8
    profiles_other = compute_team_style_profiles(style_df, season="9999")
    assert len(profiles_other) == 0


def test_profiles_league_filter(style_df):
    """League filter should narrow results (case-insensitive)."""
    profiles = compute_team_style_profiles(style_df, league="premier league")
    assert len(profiles) == 2
    assert all(p.league == "Premier League" for p in profiles)


def test_profiles_min_minutes(style_df):
    """Teams below min_minutes_total should be excluded."""
    # Set a very high threshold
    profiles = compute_team_style_profiles(
        style_df, min_minutes_total=999999.0
    )
    assert len(profiles) == 0


def test_profiles_fields(style_df):
    """Each profile should have all expected fields."""
    profiles = compute_team_style_profiles(style_df)
    p = profiles[0]
    assert hasattr(p, "team")
    assert hasattr(p, "league")
    assert hasattr(p, "season")
    assert hasattr(p, "n_players")
    assert hasattr(p, "total_minutes")
    assert hasattr(p, "attack")
    assert hasattr(p, "creation")
    assert hasattr(p, "defense")
    assert hasattr(p, "possession")


# ── compute_team_style_clusters ──────────────────────────────────────────


def test_clusters_empty():
    """Empty input should return insufficient_teams status."""
    result = compute_team_style_clusters(pd.DataFrame())
    assert result["status"] == "insufficient_teams"
    assert result["n_teams"] == 0
    assert result["clusters"] == []


def test_clusters_basic(style_df):
    """Should produce clusters with the expected structure."""
    result = compute_team_style_clusters(style_df, n_clusters=4)
    assert result["status"] == "ok"
    assert result["n_teams"] == 8
    assert result["n_clusters"] <= 4
    assert len(result["clusters"]) > 0
    assert len(result["team_profiles"]) == 8


def test_clusters_reproducible(style_df):
    """Same random_state should produce same cluster assignments."""
    r1 = compute_team_style_clusters(style_df, n_clusters=4, random_state=42)
    r2 = compute_team_style_clusters(style_df, n_clusters=4, random_state=42)
    assert r1["n_clusters"] == r2["n_clusters"]
    # Same teams should be in same clusters
    for p1, p2 in zip(r1["team_profiles"], r2["team_profiles"], strict=True):
        assert p1["cluster_id"] == p2["cluster_id"]


def test_clusters_n_clusters(style_df):
    """n_clusters should be respected (within bounds)."""
    result = compute_team_style_clusters(style_df, n_clusters=3)
    assert result["n_clusters"] <= 3


def test_clusters_n_clusters_max(style_df):
    """n_clusters should be capped at 8."""
    result = compute_team_style_clusters(style_df, n_clusters=20)
    assert result["n_clusters"] <= 8


def test_clusters_n_clusters_min(style_df):
    """n_clusters should be at least 2."""
    result = compute_team_style_clusters(style_df, n_clusters=1)
    assert result["n_clusters"] >= 2


def test_clusters_insufficient_teams():
    """Fewer than 4 teams should return insufficient_teams."""
    df = pd.DataFrame([
        {"team": "A", "league": "L", "season": "S", "minutes": 2000.0,
         "npg_p90": 0.3, "assists_p90": 0.1, "defense_composite": 40.0,
         "possession_composite": 50.0},
        {"team": "B", "league": "L", "season": "S", "minutes": 2000.0,
         "npg_p90": 0.2, "assists_p90": 0.15, "defense_composite": 50.0,
         "possession_composite": 55.0},
    ])
    result = compute_team_style_clusters(df)
    assert result["status"] == "insufficient_teams"


def test_clusters_cluster_fields(style_df):
    """Each cluster should have all expected fields."""
    result = compute_team_style_clusters(style_df, n_clusters=4)
    for c in result["clusters"]:
        assert "cluster_id" in c
        assert "label" in c
        assert "n_teams" in c
        assert "centroid" in c
        assert "teams" in c
        assert isinstance(c["teams"], list)


def test_clusters_team_profile_has_cluster_id(style_df):
    """Each team profile should have a cluster_id assignment."""
    result = compute_team_style_clusters(style_df, n_clusters=4)
    for p in result["team_profiles"]:
        assert "cluster_id" in p
        assert isinstance(p["cluster_id"], int)


def test_clusters_disclaimer(style_df):
    """Disclaimer should be present and mention limitations."""
    result = compute_team_style_clusters(style_df, n_clusters=4)
    assert len(result["disclaimer"]) > 50
    assert "statistical" in result["disclaimer"].lower() or \
           "heuristic" in result["disclaimer"].lower()


def test_clusters_feature_means_stds(style_df):
    """Feature means and stds should be returned for reference."""
    result = compute_team_style_clusters(style_df, n_clusters=4)
    assert "feature_means" in result
    assert "feature_stds" in result
    assert "npg_p90" in result["feature_means"]
    assert "npg_p90" in result["feature_stds"]


def test_clusters_sorted_by_size(style_df):
    """Clusters should be sorted by size descending."""
    result = compute_team_style_clusters(style_df, n_clusters=4)
    sizes = [c["n_teams"] for c in result["clusters"]]
    assert sizes == sorted(sizes, reverse=True)


def test_clusters_no_mutation(style_df):
    """Input frame must not be mutated."""
    original = style_df.copy()
    compute_team_style_clusters(style_df, n_clusters=4)
    pd.testing.assert_frame_equal(style_df, original)


def test_clusters_cluster_ids_sequential(style_df):
    """After sorting, cluster IDs should be sequential 0..n-1."""
    result = compute_team_style_clusters(style_df, n_clusters=4)
    ids = [c["cluster_id"] for c in result["clusters"]]
    assert ids == list(range(len(ids)))


def test_clusters_season_filter(style_df):
    """Season filter should narrow the teams clustered."""
    result = compute_team_style_clusters(style_df, season="2526", n_clusters=4)
    assert result["n_teams"] == 8
    result_empty = compute_team_style_clusters(
        style_df, season="9999", n_clusters=4
    )
    assert result_empty["status"] == "insufficient_teams"


# ── compute_player_style_fit ─────────────────────────────────────────────


def test_style_fit_empty():
    """Empty DataFrame should return no_data."""
    result = compute_player_style_fit(pd.DataFrame(), "Test Player")
    assert result["status"] == "no_data"
    assert result["clusters"] == []


def test_style_fit_basic(style_df):
    """Should return per-cluster fit scores for a known player."""
    result = compute_player_style_fit(style_df, "Team A P0", n_clusters=4)
    assert result["status"] == "ok"
    assert result["player"] == "Team A P0"
    assert len(result["clusters"]) > 0
    for c in result["clusters"]:
        assert "cluster_id" in c
        assert "label" in c
        assert "fit_score" in c
        assert 0 <= c["fit_score"] <= 100
        assert "cosine_similarity" in c
        assert -1 <= c["cosine_similarity"] <= 1


def test_style_fit_player_not_found(style_df):
    """Unknown player should return player_not_found."""
    result = compute_player_style_fit(style_df, "Nobody", n_clusters=4)
    assert result["status"] == "player_not_found"
    assert result["clusters"] == []


def test_style_fit_case_insensitive(style_df):
    """Player name match should be case-insensitive."""
    r1 = compute_player_style_fit(style_df, "Team A P0", n_clusters=4)
    r2 = compute_player_style_fit(style_df, "team a p0", n_clusters=4)
    assert r1["status"] == "ok"
    assert r2["status"] == "ok"
    assert r1["player_style"] == r2["player_style"]


def test_style_fit_sorted_descending(style_df):
    """Clusters should be sorted by fit_score descending."""
    result = compute_player_style_fit(style_df, "Team A P0", n_clusters=4)
    scores = [c["fit_score"] for c in result["clusters"]]
    assert scores == sorted(scores, reverse=True)


def test_style_fit_player_style_fields(style_df):
    """player_style dict should contain all 4 style features."""
    result = compute_player_style_fit(style_df, "Team A P0", n_clusters=4)
    ps = result["player_style"]
    assert "npg_p90" in ps
    assert "assists_p90" in ps
    assert "defense_composite" in ps
    assert "possession_composite" in ps


def test_style_fit_best_fit_cluster(style_df):
    """best_fit_cluster should match the top cluster label."""
    result = compute_player_style_fit(style_df, "Team A P0", n_clusters=4)
    assert result["best_fit_cluster"] == result["clusters"][0]["label"]


def test_style_fit_disclaimer_present(style_df):
    """Result should include a disclaimer."""
    result = compute_player_style_fit(style_df, "Team A P0", n_clusters=4)
    assert "disclaimer" in result
    assert len(result["disclaimer"]) > 0


def test_style_fit_insufficient_teams():
    """Should propagate insufficient_teams status."""
    df = pd.DataFrame([
        {"player": "P1", "team": "A", "league": "L", "season": "S",
         "minutes": 2000.0, "position_group": "ST",
         "npg_p90": 0.3, "assists_p90": 0.1,
         "defense_composite": 40.0, "possession_composite": 50.0},
    ])
    result = compute_player_style_fit(df, "P1")
    assert result["status"] == "insufficient_teams"


def test_style_fit_no_mutation(style_df):
    """Original DataFrame should not be mutated."""
    original = style_df.copy()
    compute_player_style_fit(style_df, "Team A P0", n_clusters=4)
    pd.testing.assert_frame_equal(style_df, original)


# ── compute_cluster_recruits ─────────────────────────────────────────────


def test_recruits_empty():
    """Empty DataFrame should return no_data."""
    result = compute_cluster_recruits(pd.DataFrame(), 0)
    assert result["status"] == "no_data"
    assert result["recruits"] == []


def test_recruits_basic(style_df):
    """Should return ranked recruits for a valid cluster."""
    clusters = compute_team_style_clusters(style_df, n_clusters=4)
    if clusters["status"] != "ok":
        pytest.skip("Clustering not available in test env")
    cid = clusters["clusters"][0]["cluster_id"]
    result = compute_cluster_recruits(style_df, cid, n_clusters=4, top_n=5)
    assert result["status"] == "ok"
    assert result["cluster_id"] == cid
    assert isinstance(result["recruits"], list)
    assert len(result["recruits"]) <= 5
    for r in result["recruits"]:
        assert "player" in r
        assert "team" in r
        assert "fit_score" in r
        assert 0 <= r["fit_score"] <= 100
        assert "position_group" in r


def test_recruits_sorted_descending(style_df):
    """Recruits should be sorted by fit_score descending."""
    clusters = compute_team_style_clusters(style_df, n_clusters=4)
    if clusters["status"] != "ok":
        pytest.skip("Clustering not available in test env")
    cid = clusters["clusters"][0]["cluster_id"]
    result = compute_cluster_recruits(style_df, cid, n_clusters=4, top_n=20)
    scores = [r["fit_score"] for r in result["recruits"]]
    assert scores == sorted(scores, reverse=True)


def test_recruits_cluster_not_found(style_df):
    """Invalid cluster_id should return cluster_not_found."""
    result = compute_cluster_recruits(style_df, 999, n_clusters=4)
    assert result["status"] == "cluster_not_found"
    assert "available_clusters" in result


def test_recruits_exclude_cluster_teams(style_df):
    """Players from teams in the cluster should be excluded by default."""
    clusters = compute_team_style_clusters(style_df, n_clusters=4)
    if clusters["status"] != "ok":
        pytest.skip("Clustering not available in test env")
    target = clusters["clusters"][0]
    cluster_teams = set(target["teams"])
    result = compute_cluster_recruits(
        style_df, target["cluster_id"], n_clusters=4, top_n=50
    )
    for r in result["recruits"]:
        assert r["team"] not in cluster_teams


def test_recruits_include_cluster_teams(style_df):
    """When exclude_cluster_teams=False, cluster team players may appear."""
    clusters = compute_team_style_clusters(style_df, n_clusters=4)
    if clusters["status"] != "ok":
        pytest.skip("Clustering not available in test env")
    target = clusters["clusters"][0]
    result = compute_cluster_recruits(
        style_df,
        target["cluster_id"],
        n_clusters=4,
        top_n=50,
        exclude_cluster_teams=False,
    )
    assert result["status"] == "ok"
    # At least some recruits should be returned
    assert len(result["recruits"]) > 0


def test_recruits_top_n_cap(style_df):
    """top_n should limit the number of returned recruits."""
    clusters = compute_team_style_clusters(style_df, n_clusters=4)
    if clusters["status"] != "ok":
        pytest.skip("Clustering not available in test env")
    cid = clusters["clusters"][0]["cluster_id"]
    result = compute_cluster_recruits(style_df, cid, n_clusters=4, top_n=3)
    assert len(result["recruits"]) <= 3


def test_recruits_position_filter(style_df):
    """position_group filter should narrow candidates."""
    clusters = compute_team_style_clusters(style_df, n_clusters=4)
    if clusters["status"] != "ok":
        pytest.skip("Clustering not available in test env")
    cid = clusters["clusters"][0]["cluster_id"]
    result = compute_cluster_recruits(
        style_df, cid, n_clusters=4, top_n=50, position_group="ST"
    )
    for r in result["recruits"]:
        assert r["position_group"] == "ST"


def test_recruits_min_minutes(style_df):
    """min_player_minutes should filter out low-minute players."""
    clusters = compute_team_style_clusters(style_df, n_clusters=4)
    if clusters["status"] != "ok":
        pytest.skip("Clustering not available in test env")
    cid = clusters["clusters"][0]["cluster_id"]
    result = compute_cluster_recruits(
        style_df, cid, n_clusters=4, top_n=50, min_player_minutes=1900.0
    )
    for r in result["recruits"]:
        assert r["minutes"] >= 1900


def test_recruits_n_scanned(style_df):
    """n_candidates_scanned should reflect total qualifying candidates."""
    clusters = compute_team_style_clusters(style_df, n_clusters=4)
    if clusters["status"] != "ok":
        pytest.skip("Clustering not available in test env")
    cid = clusters["clusters"][0]["cluster_id"]
    result = compute_cluster_recruits(
        style_df, cid, n_clusters=4, top_n=100,
        min_player_minutes=0.0, exclude_cluster_teams=False,
    )
    assert result["n_candidates_scanned"] >= len(result["recruits"])


def test_recruits_disclaimer_present(style_df):
    """Result should include a disclaimer."""
    clusters = compute_team_style_clusters(style_df, n_clusters=4)
    if clusters["status"] != "ok":
        pytest.skip("Clustering not available in test env")
    cid = clusters["clusters"][0]["cluster_id"]
    result = compute_cluster_recruits(style_df, cid, n_clusters=4)
    assert "disclaimer" in result
    assert len(result["disclaimer"]) > 0


def test_recruits_no_mutation(style_df):
    """Original DataFrame should not be mutated."""
    clusters = compute_team_style_clusters(style_df, n_clusters=4)
    if clusters["status"] != "ok":
        pytest.skip("Clustering not available in test env")
    original = style_df.copy()
    cid = clusters["clusters"][0]["cluster_id"]
    compute_cluster_recruits(style_df, cid, n_clusters=4, top_n=5)
    pd.testing.assert_frame_equal(style_df, original)

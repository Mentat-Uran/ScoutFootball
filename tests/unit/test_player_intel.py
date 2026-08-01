"""Tests for the player career intelligence module.

Covers ``compute_career_trajectory``, ``compute_role_fit_scores``,
``compute_peer_benchmark`` and ``compute_multi_player_comparison`` in
``scoutfootball.player_intel``. The fixtures use synthetic pandas frames
that mirror the rating-feature-matrix schema so the helpers can be
exercised without loading disk artifacts.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scoutfootball.player_intel import (
    compute_career_trajectory,
    compute_multi_player_comparison,
    compute_pairwise_similarity,
    compute_peer_benchmark,
    compute_role_fit_scores,
)


def _build_synthetic_ratings() -> pd.DataFrame:
    """Build a synthetic ratings frame with enough rows per position."""
    rows: list[dict] = []
    # 8 ST players in Premier League (big5) with starter minutes.
    for i in range(8):
        rows.append({
            "player": f"ST Player {i}",
            "team": f"Team {i}",
            "league": "Premier League",
            "season": "2526",
            "sub_position": "ST",
            "position_group": "ST",
            "optimized_score": 60.0 + i * 2,
            "minutes": 2000.0 + i * 50,
            "matches": 25,
            "npg_p90": 0.3 + i * 0.05,
            "assists_p90": 0.1 + i * 0.02,
            "defense_composite": 10.0 + i,
            "possession_composite": 30.0 + i * 2,
            "confidence_level": "HIGH",
            "low_appearance": False,
        })
    # 8 CM players in La Liga (big5) with starter minutes.
    for i in range(8):
        rows.append({
            "player": f"CM Player {i}",
            "team": f"Spanish {i}",
            "league": "La Liga",
            "season": "2526",
            "sub_position": "CM",
            "position_group": "CM",
            "optimized_score": 55.0 + i * 2,
            "minutes": 1800.0 + i * 50,
            "matches": 22,
            "npg_p90": 0.05 + i * 0.01,
            "assists_p90": 0.2 + i * 0.03,
            "defense_composite": 55.0 + i * 2,
            "possession_composite": 65.0 + i * 2,
            "confidence_level": "HIGH",
            "low_appearance": False,
        })
    # 6 CB players in Other league with rotation minutes.
    for i in range(6):
        rows.append({
            "player": f"CB Player {i}",
            "team": f"Other {i}",
            "league": "Eredivisie",
            "season": "2526",
            "sub_position": "CB",
            "position_group": "CB",
            "optimized_score": 50.0 + i * 2,
            "minutes": 1200.0 + i * 30,
            "matches": 18,
            "npg_p90": 0.02,
            "assists_p90": 0.01,
            "defense_composite": 75.0 + i * 2,
            "possession_composite": 50.0 + i,
            "confidence_level": "MEDIUM",
            "low_appearance": False,
        })
    return pd.DataFrame(rows)


@pytest.fixture
def synthetic_df() -> pd.DataFrame:
    return _build_synthetic_ratings()


@pytest.fixture
def multi_season_player_rows() -> pd.DataFrame:
    """Five seasons for a single ST player, used for trajectory tests."""
    return pd.DataFrame([
        {
            "player": "Veteran Striker", "team": "Team A", "league": "Premier League",
            "season": "2122", "position_group": "ST", "sub_position": "ST",
            "optimized_score": 60.0, "minutes": 1500.0, "matches": 20,
            "npg_p90": 0.3, "assists_p90": 0.1, "defense_composite": 10.0,
            "possession_composite": 30.0, "confidence_level": "HIGH", "low_appearance": False,
        },
        {
            "player": "Veteran Striker", "team": "Team A", "league": "Premier League",
            "season": "2223", "position_group": "ST", "sub_position": "ST",
            "optimized_score": 68.0, "minutes": 2400.0, "matches": 30,
            "npg_p90": 0.5, "assists_p90": 0.2, "defense_composite": 12.0,
            "possession_composite": 35.0, "confidence_level": "HIGH", "low_appearance": False,
        },
        {
            "player": "Veteran Striker", "team": "Team B", "league": "Premier League",
            "season": "2324", "position_group": "ST", "sub_position": "ST",
            "optimized_score": 75.0, "minutes": 2700.0, "matches": 32,
            "npg_p90": 0.6, "assists_p90": 0.25, "defense_composite": 14.0,
            "possession_composite": 38.0, "confidence_level": "HIGH", "low_appearance": False,
        },
        {
            "player": "Veteran Striker", "team": "Team B", "league": "Premier League",
            "season": "2425", "position_group": "ST", "sub_position": "ST",
            "optimized_score": 72.0, "minutes": 2200.0, "matches": 28,
            "npg_p90": 0.45, "assists_p90": 0.18, "defense_composite": 11.0,
            "possession_composite": 33.0, "confidence_level": "HIGH", "low_appearance": False,
        },
        {
            "player": "Veteran Striker", "team": "Team C", "league": "Premier League",
            "season": "2526", "position_group": "ST", "sub_position": "ST",
            "optimized_score": 65.0, "minutes": 1600.0, "matches": 22,
            "npg_p90": 0.35, "assists_p90": 0.15, "defense_composite": 9.0,
            "possession_composite": 28.0, "confidence_level": "MEDIUM", "low_appearance": False,
        },
    ])


# ── compute_career_trajectory ────────────────────────────────────────────


def test_career_trajectory_empty():
    """Empty input should produce a structured 'unavailable' response."""
    result = compute_career_trajectory(pd.DataFrame())
    assert result["metrics"]["n_seasons"] == 0
    assert result["peak"] is None
    assert result["seasons"] == []
    assert "disclaimer" in result


def test_career_trajectory_basic(multi_season_player_rows):
    result = compute_career_trajectory(multi_season_player_rows)
    assert result["metrics"]["n_seasons"] == 5
    assert len(result["seasons"]) == 5
    # Seasons must be in chronological order.
    seasons = [s["season"] for s in result["seasons"]]
    assert seasons == sorted(seasons)
    assert seasons[0] == "2122"
    assert seasons[-1] == "2526"


def test_career_trajectory_peak_detection(multi_season_player_rows):
    """Peak must be the highest-scoring season that meets the minutes floor."""
    result = compute_career_trajectory(multi_season_player_rows)
    peak = result["peak"]
    assert peak is not None
    # Highest score (75.0) is in season 2324 with 2700 minutes — meets the
    # 900-minute floor.
    assert peak["season"] == "2324"
    assert peak["optimized_score"] == 75.0


def test_career_trajectory_peak_minutes_floor():
    """A short-career prospect with all sub-900-minute seasons should
    still get a peak (falls back to highest score)."""
    rows = pd.DataFrame([
        {"season": "2425", "team": "X", "league": "L", "position_group": "ST",
         "optimized_score": 70.0, "minutes": 400.0, "npg_p90": 0.4,
         "assists_p90": 0.1, "defense_composite": 10.0,
         "possession_composite": 30.0},
        {"season": "2526", "team": "X", "league": "L", "position_group": "ST",
         "optimized_score": 65.0, "minutes": 300.0, "npg_p90": 0.3,
         "assists_p90": 0.08, "defense_composite": 8.0,
         "possession_composite": 25.0},
    ])
    result = compute_career_trajectory(rows)
    assert result["peak"]["season"] == "2425"
    assert result["peak"]["optimized_score"] == 70.0


def test_career_trajectory_phases(multi_season_player_rows):
    """Phases should include at least prime, possibly prospect/decline."""
    result = compute_career_trajectory(multi_season_player_rows)
    phases = result["phases"]
    assert len(phases) >= 1
    phase_names = {p["phase"] for p in phases}
    assert "prime" in phase_names
    # Peak is at index 2 (season 2324) in a 5-season career. Prime window
    # covers indices 1-3, so prospect (index 0) and decline (index 4) exist.
    assert "prospect" in phase_names
    assert "decline" in phase_names


def test_career_trajectory_yoy_deltas(multi_season_player_rows):
    result = compute_career_trajectory(multi_season_player_rows)
    yoy = result["yoy_deltas"]
    assert len(yoy) == 4  # 5 seasons → 4 transitions
    # 2122→2223: 60→68 = +8.0
    assert yoy[0]["from_season"] == "2122"
    assert yoy[0]["to_season"] == "2223"
    assert yoy[0]["score_change"] == 8.0


def test_career_trajectory_metrics(multi_season_player_rows):
    result = compute_career_trajectory(multi_season_player_rows)
    m = result["metrics"]
    assert m["n_seasons"] == 5
    assert m["peak_score"] == 75.0
    assert m["min_score"] == 60.0
    assert m["career_minutes_total"] == 10400
    # Trajectory slope should be non-negative (career trended up overall).
    assert m["trajectory_slope"] is not None


def test_career_trajectory_disclaimer(multi_season_player_rows):
    """A disclaimer must always be present."""
    result = compute_career_trajectory(multi_season_player_rows)
    assert isinstance(result["disclaimer"], str)
    assert len(result["disclaimer"]) > 0


def test_career_trajectory_no_mutation(multi_season_player_rows):
    """Function must not mutate the input frame."""
    original = multi_season_player_rows.copy()
    compute_career_trajectory(multi_season_player_rows)
    pd.testing.assert_frame_equal(multi_season_player_rows, original)


# ── compute_role_fit_scores ──────────────────────────────────────────────


def test_role_fit_basic(synthetic_df):
    target = synthetic_df[synthetic_df["player"] == "ST Player 5"].iloc[0]
    result = compute_role_fit_scores(target, synthetic_df)
    assert "scores" in result
    # All 8 positions should be present in the scores dict.
    for pos in ("GK", "CB", "FB", "DM", "CM", "AM", "W", "ST"):
        assert pos in result["scores"]


def test_role_fit_primary_match(synthetic_df):
    """An ST-target should have ST either as primary or as a strong fit."""
    target = synthetic_df[synthetic_df["player"] == "ST Player 7"].iloc[0]
    result = compute_role_fit_scores(target, synthetic_df)
    primary = result["primary_fit"]
    assert primary is not None
    assert primary["position"] in result["scores"]


def test_role_fit_insufficient_samples_returns_none(synthetic_df):
    """Positions with < _MIN_PEER_SAMPLES should withhold fit_score."""
    target = synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0]
    result = compute_role_fit_scores(target, synthetic_df)
    # GK has no rows in synthetic_df → should be marked insufficient.
    gk = result["scores"]["GK"]
    assert gk["fit_score"] is None
    assert gk["confidence"] == "insufficient_samples"


def test_role_fit_score_range(synthetic_df):
    """Fit scores that are computed must be in [0, 100]."""
    target = synthetic_df[synthetic_df["player"] == "CM Player 3"].iloc[0]
    result = compute_role_fit_scores(target, synthetic_df)
    for _pos, info in result["scores"].items():
        if info.get("fit_score") is not None:
            assert 0.0 <= info["fit_score"] <= 100.0


def test_role_fit_disclaimer(synthetic_df):
    target = synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0]
    result = compute_role_fit_scores(target, synthetic_df)
    assert isinstance(result["disclaimer"], str)
    assert len(result["disclaimer"]) > 0


# ── compute_peer_benchmark ───────────────────────────────────────────────


def test_peer_benchmark_basic(synthetic_df):
    target = synthetic_df[synthetic_df["player"] == "ST Player 3"].iloc[0]
    result = compute_peer_benchmark(target, synthetic_df)
    assert "peer_group" in result
    assert "metrics" in result
    assert "summary" in result
    pg = result["peer_group"]
    assert pg["position_group"] == "ST"
    assert pg["league_tier"] == "big5"
    # 2000-2350 minutes — all in starter band (>=1800).
    assert pg["minutes_band"] == "starter"
    assert pg["size"] >= 5


def test_peer_benchmark_metrics_have_percentiles(synthetic_df):
    target = synthetic_df[synthetic_df["player"] == "ST Player 4"].iloc[0]
    result = compute_peer_benchmark(target, synthetic_df)
    metrics = result["metrics"]
    # optimized_score should always be present.
    assert "optimized_score" in metrics
    os_info = metrics["optimized_score"]
    assert os_info["percentile"] is not None
    assert 0.0 <= os_info["percentile"] <= 100.0
    assert os_info["rank"] >= 1


def test_peer_benchmark_top_peers_excludes_target(synthetic_df):
    target = synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0]
    result = compute_peer_benchmark(target, synthetic_df)
    top = result["top_peers"]
    assert isinstance(top, list)
    # Target must not appear in its own top peers list.
    for peer in top:
        assert peer["player"] != "ST Player 0"


def test_peer_benchmark_thin_pool_withheld():
    """When peer group has < 5 members, benchmark is withheld."""
    df = pd.DataFrame([
        {"player": "Lone ST", "team": "T", "league": "Premier League",
         "season": "2526", "position_group": "ST", "optimized_score": 70.0,
         "minutes": 2000.0, "npg_p90": 0.5, "assists_p90": 0.2,
         "defense_composite": 10.0, "possession_composite": 30.0},
        {"player": "Other ST", "team": "T", "league": "Premier League",
         "season": "2526", "position_group": "ST", "optimized_score": 65.0,
         "minutes": 1900.0, "npg_p90": 0.4, "assists_p90": 0.1,
         "defense_composite": 8.0, "possession_composite": 25.0},
    ])
    target = df.iloc[0]
    result = compute_peer_benchmark(target, df)
    assert result["summary"]["overall_rank"] is None
    assert result["summary"]["overall_percentile"] is None
    assert "comparison_note" in result["summary"]


def test_peer_benchmark_overall_percentile(synthetic_df):
    """The overall percentile should be a weighted average, dominated by
    optimized_score."""
    target = synthetic_df[synthetic_df["player"] == "ST Player 7"].iloc[0]
    result = compute_peer_benchmark(target, synthetic_df)
    # ST Player 7 is the highest-rated ST in the big5/starter band.
    assert result["summary"]["overall_percentile"] >= 80.0


def test_peer_benchmark_disclaimer(synthetic_df):
    target = synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0]
    result = compute_peer_benchmark(target, synthetic_df)
    assert isinstance(result["disclaimer"], str)


# ── compute_pairwise_similarity ──────────────────────────────────────────


def test_pairwise_similarity_identical_rows(synthetic_df):
    """Identical rows should yield similarity close to 1.0."""
    row = synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0]
    sim = compute_pairwise_similarity(row, row, synthetic_df)
    assert sim is not None
    assert sim >= 0.99


def test_pairwise_similarity_different_positions(synthetic_df):
    """Players in different positions can still get a similarity score."""
    st = synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0]
    cm = synthetic_df[synthetic_df["player"] == "CM Player 0"].iloc[0]
    sim = compute_pairwise_similarity(st, cm, synthetic_df)
    assert sim is not None
    assert 0.0 <= sim <= 1.0


# ── compute_multi_player_comparison ──────────────────────────────────────


def test_multi_compare_too_few(synthetic_df):
    """One player should return an error."""
    row = synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0]
    result = compute_multi_player_comparison({"ST Player 0": row}, synthetic_df)
    assert result["error"] == "need_at_least_two_players"


def test_multi_compare_too_many(synthetic_df):
    """Seven players should return an error (max is 6 since Round 84)."""
    names = [f"ST Player {i}" for i in range(7)]
    rows = {n: synthetic_df[synthetic_df["player"] == n].iloc[0] for n in names}
    result = compute_multi_player_comparison(rows, synthetic_df)
    assert result["error"] == "too_many_players"


def test_multi_compare_six_players_ok(synthetic_df):
    """Six players should succeed (Round 84 raised the cap from 5 to 6)."""
    names = [f"ST Player {i}" for i in range(6)]
    rows = {n: synthetic_df[synthetic_df["player"] == n].iloc[0] for n in names}
    result = compute_multi_player_comparison(rows, synthetic_df)
    assert "error" not in result
    assert result["n_players"] == 6
    assert len(result["players"]) == 6
    # Pairwise similarity matrix should be 6x6 with diagonal == 1.0
    matrix = result["pairwise_similarity"]["matrix"]
    assert len(matrix) == 6
    assert all(len(row) == 6 for row in matrix)
    for i in range(6):
        assert matrix[i][i] == 1.0


def test_multi_compare_basic(synthetic_df):
    """Two-player comparison should return the full structure."""
    rows = {
        "ST Player 0": synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0],
        "ST Player 5": synthetic_df[synthetic_df["player"] == "ST Player 5"].iloc[0],
    }
    result = compute_multi_player_comparison(rows, synthetic_df)
    assert result["n_players"] == 2
    assert len(result["players"]) == 2
    assert "percentile_matrix" in result
    assert "metric_rankings" in result
    assert "composite_ranking" in result
    assert "pairwise_similarity" in result
    assert result["same_position"] is True


def test_multi_compare_percentile_matrix(synthetic_df):
    """Percentile matrix should have one row per similarity dimension."""
    rows = {
        "ST Player 0": synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0],
        "ST Player 7": synthetic_df[synthetic_df["player"] == "ST Player 7"].iloc[0],
    }
    result = compute_multi_player_comparison(rows, synthetic_df)
    matrix = result["percentile_matrix"]
    assert len(matrix) > 0
    for entry in matrix:
        assert "dimension" in entry
        assert "label" in entry
        assert "values" in entry
        assert len(entry["values"]) == 2


def test_multi_compare_composite_ranking_sorted(synthetic_df):
    """Composite ranking should be sorted by avg_percentile descending."""
    rows = {
        "ST Player 0": synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0],
        "ST Player 7": synthetic_df[synthetic_df["player"] == "ST Player 7"].iloc[0],
    }
    result = compute_multi_player_comparison(rows, synthetic_df)
    ranking = result["composite_ranking"]
    assert len(ranking) == 2
    assert ranking[0]["avg_percentile"] >= ranking[1]["avg_percentile"]
    # Ranks 1 and 2 assigned.
    assert ranking[0]["rank"] == 1
    assert ranking[1]["rank"] == 2


def test_multi_compare_pairwise_matrix(synthetic_df):
    """Pairwise similarity matrix should be square with 1.0 on diagonal."""
    rows = {
        "ST Player 0": synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0],
        "ST Player 3": synthetic_df[synthetic_df["player"] == "ST Player 3"].iloc[0],
        "ST Player 7": synthetic_df[synthetic_df["player"] == "ST Player 7"].iloc[0],
    }
    result = compute_multi_player_comparison(rows, synthetic_df)
    sim = result["pairwise_similarity"]
    assert "players" in sim
    assert "matrix" in sim
    matrix = sim["matrix"]
    n = len(rows)
    assert len(matrix) == n
    for i, row in enumerate(matrix):
        assert len(row) == n
        # Diagonal should be 1.0 (self-similarity).
        assert matrix[i][i] == 1.0


def test_multi_compare_cross_position(synthetic_df):
    """Comparing players across positions should still work and mark
    same_position=False."""
    rows = {
        "ST Player 0": synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0],
        "CM Player 0": synthetic_df[synthetic_df["player"] == "CM Player 0"].iloc[0],
    }
    result = compute_multi_player_comparison(rows, synthetic_df)
    assert result["same_position"] is False


def test_multi_compare_disclaimer(synthetic_df):
    rows = {
        "ST Player 0": synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0],
        "ST Player 1": synthetic_df[synthetic_df["player"] == "ST Player 1"].iloc[0],
    }
    result = compute_multi_player_comparison(rows, synthetic_df)
    assert isinstance(result["disclaimer"], str)
    assert len(result["disclaimer"]) > 0


def test_multi_compare_metric_rankings(synthetic_df):
    """Metric rankings should include optimized_score with proper ranks."""
    rows = {
        "ST Player 0": synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0],
        "ST Player 7": synthetic_df[synthetic_df["player"] == "ST Player 7"].iloc[0],
    }
    result = compute_multi_player_comparison(rows, synthetic_df)
    rankings = result["metric_rankings"]
    os_ranking = next(r for r in rankings if r["metric"] == "optimized_score")
    # ST Player 7 (74.0) should rank #1, ST Player 0 (60.0) #2.
    ranks = {r["player"]: r["rank"] for r in os_ranking["rankings"]}
    assert ranks["ST Player 7"] == 1
    assert ranks["ST Player 0"] == 2


def test_multi_compare_no_input_mutation(synthetic_df):
    """Input frame must not be mutated."""
    original = synthetic_df.copy()
    rows = {
        "ST Player 0": synthetic_df[synthetic_df["player"] == "ST Player 0"].iloc[0],
        "ST Player 1": synthetic_df[synthetic_df["player"] == "ST Player 1"].iloc[0],
    }
    compute_multi_player_comparison(rows, synthetic_df)
    pd.testing.assert_frame_equal(synthetic_df, original)


# ── compute_riser_decliner_watchlist ─────────────────────────────────────


from scoutfootball.player_intel import compute_riser_decliner_watchlist  # noqa: E402


def _build_multi_season_df() -> pd.DataFrame:
    """Build a frame with several players across multiple seasons."""
    rows: list[dict] = []
    # Riser: 50 -> 60 -> 75 (strong upward slope)
    for _i, (season, score, minutes) in enumerate([
        ("2122", 50.0, 1500.0),
        ("2223", 60.0, 2000.0),
        ("2324", 75.0, 2500.0),
    ]):
        rows.append({
            "player": "Rising Star", "player_id": "p1",
            "team": "Team A", "league": "Premier League",
            "season": season, "position_group": "ST", "sub_position": "ST",
            "optimized_score": score, "minutes": minutes, "matches": 25,
            "npg_p90": 0.3, "assists_p90": 0.1,
            "defense_composite": 10.0, "possession_composite": 30.0,
            "confidence_level": "HIGH", "low_appearance": False,
        })
    # Decliner: 80 -> 70 -> 55 (strong downward slope)
    for _i, (season, score, minutes) in enumerate([
        ("2122", 80.0, 2500.0),
        ("2223", 70.0, 2000.0),
        ("2324", 55.0, 1000.0),
    ]):
        rows.append({
            "player": "Fading Veteran", "player_id": "p2",
            "team": "Team B", "league": "La Liga",
            "season": season, "position_group": "CM", "sub_position": "CM",
            "optimized_score": score, "minutes": minutes, "matches": 20,
            "npg_p90": 0.1, "assists_p90": 0.2,
            "defense_composite": 50.0, "possession_composite": 60.0,
            "confidence_level": "HIGH", "low_appearance": False,
        })
    # Flat player: 65 -> 65 -> 65 (slope = 0)
    for season in ("2122", "2223", "2324"):
        rows.append({
            "player": "Steady Hand", "player_id": "p3",
            "team": "Team C", "league": "Bundesliga",
            "season": season, "position_group": "CB", "sub_position": "CB",
            "optimized_score": 65.0, "minutes": 2000.0, "matches": 25,
            "npg_p90": 0.02, "assists_p90": 0.01,
            "defense_composite": 70.0, "possession_composite": 50.0,
            "confidence_level": "HIGH", "low_appearance": False,
        })
    # Single-season player (should be excluded by min_seasons=2)
    rows.append({
        "player": "One Season Wonder", "player_id": "p4",
        "team": "Team D", "league": "Serie A",
        "season": "2324", "position_group": "ST", "sub_position": "ST",
        "optimized_score": 90.0, "minutes": 2500.0, "matches": 30,
        "npg_p90": 0.8, "assists_p90": 0.3,
        "defense_composite": 5.0, "possession_composite": 25.0,
        "confidence_level": "HIGH", "low_appearance": False,
    })
    # Low latest-minutes player (should be excluded by min_minutes_latest)
    rows.append({
        "player": "Injured Star", "player_id": "p5",
        "team": "Team E", "league": "Ligue 1",
        "season": "2122", "position_group": "AM", "sub_position": "AM",
        "optimized_score": 70.0, "minutes": 2000.0, "matches": 25,
        "npg_p90": 0.3, "assists_p90": 0.25,
        "defense_composite": 20.0, "possession_composite": 55.0,
        "confidence_level": "HIGH", "low_appearance": False,
    })
    rows.append({
        "player": "Injured Star", "player_id": "p5",
        "team": "Team E", "league": "Ligue 1",
        "season": "2223", "position_group": "AM", "sub_position": "AM",
        "optimized_score": 80.0, "minutes": 100.0, "matches": 2,
        "npg_p90": 0.0, "assists_p90": 0.0,
        "defense_composite": 15.0, "possession_composite": 40.0,
        "confidence_level": "LOW", "low_appearance": True,
    })
    return pd.DataFrame(rows)


@pytest.fixture
def multi_season_df() -> pd.DataFrame:
    return _build_multi_season_df()


def test_riser_decliner_empty():
    """Empty input should produce a structured 'unavailable' response."""
    result = compute_riser_decliner_watchlist(pd.DataFrame())
    assert result["risers"] == []
    assert result["decliners"] == []
    assert result["n_scanned"] == 0
    assert "unavailable" in result["disclaimer"].lower()


def test_riser_decliner_basic(multi_season_df):
    """Rising Star should be in risers, Fading Veteran in decliners."""
    result = compute_riser_decliner_watchlist(multi_season_df)
    riser_names = [r["player"] for r in result["risers"]]
    decliner_names = [d["player"] for d in result["decliners"]]
    assert "Rising Star" in riser_names
    assert "Fading Veteran" in decliner_names


def test_riser_decliner_slope_direction(multi_season_df):
    """Riser slope should be positive, decliner slope negative."""
    result = compute_riser_decliner_watchlist(multi_season_df)
    for r in result["risers"]:
        assert r["trajectory_slope"] > 0
        assert r["trend_label"] == "rising"
    for d in result["decliners"]:
        assert d["trajectory_slope"] < 0
        assert d["trend_label"] == "declining"


def test_riser_decliner_excludes_single_season(multi_season_df):
    """One Season Wonder has only 1 season and should not appear."""
    result = compute_riser_decliner_watchlist(multi_season_df)
    all_names = [r["player"] for r in result["risers"]] + [
        d["player"] for d in result["decliners"]
    ]
    assert "One Season Wonder" not in all_names


def test_riser_decliner_excludes_low_latest_minutes(multi_season_df):
    """Injured Star's latest season has only 100 min — should be excluded."""
    result = compute_riser_decliner_watchlist(multi_season_df)
    all_names = [r["player"] for r in result["risers"]] + [
        d["player"] for d in result["decliners"]
    ]
    assert "Injured Star" not in all_names


def test_riser_decliner_flat_player_excluded(multi_season_df):
    """Steady Hand has slope=0, should not appear in risers or decliners."""
    result = compute_riser_decliner_watchlist(multi_season_df)
    all_names = [r["player"] for r in result["risers"]] + [
        d["player"] for d in result["decliners"]
    ]
    assert "Steady Hand" not in all_names


def test_riser_decliner_entry_fields(multi_season_df):
    """Each entry should have all expected fields."""
    result = compute_riser_decliner_watchlist(multi_season_df)
    for entry in result["risers"] + result["decliners"]:
        assert "player" in entry
        assert "team" in entry
        assert "league" in entry
        assert "position_group" in entry
        assert "current_score" in entry
        assert "peak_score" in entry
        assert "trajectory_slope" in entry
        assert "n_seasons" in entry
        assert "latest_season" in entry
        assert "trend_label" in entry


def test_riser_decliner_sorted(multi_season_df):
    """Risers should be sorted by slope descending, decliners ascending."""
    result = compute_riser_decliner_watchlist(multi_season_df)
    if len(result["risers"]) > 1:
        slopes = [r["trajectory_slope"] for r in result["risers"]]
        assert slopes == sorted(slopes, reverse=True)
    if len(result["decliners"]) > 1:
        slopes = [d["trajectory_slope"] for d in result["decliners"]]
        assert slopes == sorted(slopes)


def test_riser_decliner_top_n(multi_season_df):
    """top_n should cap the number of risers and decliners."""
    result = compute_riser_decliner_watchlist(multi_season_df, top_n=1)
    assert len(result["risers"]) <= 1
    assert len(result["decliners"]) <= 1


def test_riser_decliner_n_scanned(multi_season_df):
    """n_scanned should count players that passed min_seasons + minutes filters."""
    result = compute_riser_decliner_watchlist(multi_season_df)
    # Rising Star, Fading Veteran, Steady Hand, Injured Star all have >= 2 seasons
    # but Injured Star fails min_minutes_latest=300.
    # So n_scanned should be 3 (Rising Star, Fading Veteran, Steady Hand).
    assert result["n_scanned"] == 3


def test_riser_decliner_thresholds(multi_season_df):
    """Custom thresholds should filter accordingly."""
    # Very high riser threshold — Rising Star slope is ~12.5, so 15 should exclude.
    result = compute_riser_decliner_watchlist(
        multi_season_df, riser_threshold=15.0
    )
    riser_names = [r["player"] for r in result["risers"]]
    assert "Rising Star" not in riser_names


def test_riser_decliner_disclaimer(multi_season_df):
    """Disclaimer should be present and mention limitations."""
    result = compute_riser_decliner_watchlist(multi_season_df)
    assert len(result["disclaimer"]) > 50
    assert "slope" in result["disclaimer"].lower()


def test_riser_decliner_no_mutation(multi_season_df):
    """Input frame must not be mutated."""
    original = multi_season_df.copy()
    compute_riser_decliner_watchlist(multi_season_df)
    pd.testing.assert_frame_equal(multi_season_df, original)


def test_riser_decliner_thresholds_echoed(multi_season_df):
    """Thresholds dict should echo the parameters used."""
    result = compute_riser_decliner_watchlist(
        multi_season_df,
        min_seasons=3,
        min_minutes_latest=500.0,
        riser_threshold=2.0,
        decliner_threshold=-2.0,
    )
    t = result["thresholds"]
    assert t["min_seasons"] == 3
    assert t["min_minutes_latest"] == 500.0
    assert t["riser_threshold"] == 2.0
    assert t["decliner_threshold"] == -2.0

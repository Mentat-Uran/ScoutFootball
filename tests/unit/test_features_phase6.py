import pandas as pd

from scoutfootball.features import (
    build_player_match_features,
    build_player_rolling_features,
    build_team_match_features,
    build_team_rolling_features,
)


def test_build_team_match_features_creates_two_rows_and_pre_match_context() -> None:
    matches = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "match_date": "2026-08-01",
                "home_team_id": "t1",
                "away_team_id": "t2",
                "home_goals": 2,
                "away_goals": 0,
                "home_shots": 10,
                "away_shots": 5,
                "home_shots_on_target": 4,
                "away_shots_on_target": 1,
                "home_xg": 1.8,
                "away_xg": 0.4,
            },
            {
                "match_id": "m2",
                "match_date": "2026-08-08",
                "home_team_id": "t2",
                "away_team_id": "t1",
                "home_goals": 1,
                "away_goals": 1,
                "home_shots": 8,
                "away_shots": 7,
                "home_shots_on_target": 2,
                "away_shots_on_target": 3,
                "home_xg": 0.9,
                "away_xg": 1.0,
            },
            {
                "match_id": "m3",
                "match_date": "2026-08-20",
                "home_team_id": "t1",
                "away_team_id": "t3",
                "home_goals": 3,
                "away_goals": 0,
                "home_shots": 12,
                "away_shots": 4,
                "home_shots_on_target": 5,
                "away_shots_on_target": 1,
                "home_xg": 2.2,
                "away_xg": 0.3,
            },
        ],
    )
    elo = pd.DataFrame(
        [
            {"team_id": "t1", "rating_date": "2026-07-31", "elo": 1500},
            {"team_id": "t1", "rating_date": "2026-08-07", "elo": 1510},
            {"team_id": "t1", "rating_date": "2026-08-19", "elo": 1520},
            {"team_id": "t2", "rating_date": "2026-07-31", "elo": 1450},
            {"team_id": "t2", "rating_date": "2026-08-07", "elo": 1445},
            {"team_id": "t3", "rating_date": "2026-08-19", "elo": 1400},
        ],
    )

    team_match = build_team_match_features(matches, elo_df=elo)

    assert len(team_match) == 6
    t1_first = team_match.loc[
        (team_match["team_id"] == "t1") & (team_match["match_id"] == "m1")
    ].iloc[0]
    t1_third = team_match.loc[
        (team_match["team_id"] == "t1") & (team_match["match_id"] == "m3")
    ].iloc[0]
    assert t1_first["result_points"] == 3
    assert t1_first["elo_pre"] == 1500
    assert t1_first["opponent_elo_pre"] == 1450
    assert pd.isna(t1_first["rest_days"])
    assert t1_third["rest_days"] == 12.0
    assert bool(t1_third["has_xg_data"]) is True


def test_build_player_match_features_preserves_missing_advanced_metrics() -> None:
    appearances = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "match_date": "2026-08-01",
                "player_id": "p1",
                "team_id": "t1",
                "minutes_played": 90,
                "goals": 1,
                "assists": 0,
                "shots": 2,
                "shots_on_target": 1,
                "npxg": 0.8,
                "xa": 0.1,
                "xT_added": 0.25,
                "started": 1,
            },
            {
                "match_id": "m1",
                "match_date": "2026-08-01",
                "player_id": "p2",
                "team_id": "t1",
                "minutes_played": 45,
                "goals": 0,
                "assists": 1,
                "shots": 1,
                "shots_on_target": 1,
                "started": 0,
            },
        ],
    )
    team_match = pd.DataFrame(
        [{"match_id": "m1", "team_id": "t1", "opponent_team_id": "t2", "is_home": True}],
    )

    player_match = build_player_match_features(appearances, team_match_df=team_match)

    p1 = player_match.loc[player_match["player_id"] == "p1"].iloc[0]
    p2 = player_match.loc[player_match["player_id"] == "p2"].iloc[0]
    assert p1["minutes_share"] == 90 / 135
    assert bool(p1["has_expected_metrics"]) is True
    assert bool(p2["has_expected_metrics"]) is False
    assert pd.isna(p2["npxg"])
    assert p2["opponent_team_id"] == "t2"


def test_build_player_rolling_features_avoids_future_leakage_and_applies_shrinkage() -> None:
    player_match = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "match_date": "2026-08-01",
                "player_id": "p1",
                "minutes_played": 90,
                "starts": 1,
                "available_flag": 1,
                "goals": 1,
                "assists": 0,
                "shots": 2,
                "shots_on_target": 1,
                "npxg": 0.8,
                "xa": 0.1,
                "xT_added": 0.2,
            },
            {
                "match_id": "m2",
                "match_date": "2026-08-08",
                "player_id": "p1",
                "minutes_played": 45,
                "starts": 0,
                "available_flag": 1,
                "goals": 0,
                "assists": 1,
                "shots": 1,
                "shots_on_target": 1,
                "npxg": pd.NA,
                "xa": pd.NA,
                "xT_added": pd.NA,
            },
            {
                "match_id": "m3",
                "match_date": "2026-08-20",
                "player_id": "p1",
                "minutes_played": 90,
                "starts": 1,
                "available_flag": 1,
                "goals": 1,
                "assists": 0,
                "shots": 3,
                "shots_on_target": 2,
                "npxg": 1.2,
                "xa": 0.2,
                "xT_added": 0.3,
            },
        ],
    )

    rolling = build_player_rolling_features(player_match, windows=[2])

    first = rolling.loc[rolling["match_id"] == "m1"].iloc[0]
    third = rolling.loc[rolling["match_id"] == "m3"].iloc[0]
    assert pd.isna(first["prior_minutes_2"])
    assert third["prior_minutes_2"] == 135
    assert third["goals_2"] == 1
    assert round(third["goals_p90_raw_2"], 4) == round((1 * 90) / 135, 4)
    assert round(third["shrink_factor_2"], 4) == round(135 / (135 + 270), 4)
    assert round(third["goals_p90_shrunk_2"], 4) == round(((1 * 90) / 135) * (135 / 405), 4)


def test_build_team_rolling_features_uses_only_prior_matches() -> None:
    team_match = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "match_date": "2026-08-01",
                "team_id": "t1",
                "result_points": 3,
                "goals_for": 2,
                "goals_against": 0,
                "goal_diff": 2,
                "shots": 10,
                "shots_on_target": 4,
                "xg": 1.8,
                "xg_against": 0.4,
                "xg_diff": 1.4,
                "elo_pre": 1500,
                "rest_days": pd.NA,
            },
            {
                "match_id": "m2",
                "match_date": "2026-08-08",
                "team_id": "t1",
                "result_points": 1,
                "goals_for": 1,
                "goals_against": 1,
                "goal_diff": 0,
                "shots": 7,
                "shots_on_target": 3,
                "xg": 1.0,
                "xg_against": 0.9,
                "xg_diff": 0.1,
                "elo_pre": 1510,
                "rest_days": 7.0,
            },
            {
                "match_id": "m3",
                "match_date": "2026-08-20",
                "team_id": "t1",
                "result_points": 3,
                "goals_for": 3,
                "goals_against": 0,
                "goal_diff": 3,
                "shots": 12,
                "shots_on_target": 5,
                "xg": 2.2,
                "xg_against": 0.3,
                "xg_diff": 1.9,
                "elo_pre": 1520,
                "rest_days": 12.0,
            },
        ],
    )

    rolling = build_team_rolling_features(team_match, windows=[2])

    third = rolling.loc[rolling["match_id"] == "m3"].iloc[0]
    assert third["prior_matches_2"] == 2
    assert third["result_points_2"] == 4
    assert third["goals_for_2"] == 3
    assert third["points_per_match_2"] == 2
    assert third["elo_pre_mean_2"] == 1505

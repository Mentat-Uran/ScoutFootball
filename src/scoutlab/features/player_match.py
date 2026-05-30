"""Player-match feature builders."""

from __future__ import annotations

import pandas as pd

PLAYER_STAT_DEFAULTS = {
    "goals": pd.NA,
    "assists": pd.NA,
    "shots": pd.NA,
    "shots_on_target": pd.NA,
    "npxg": pd.NA,
    "xa": pd.NA,
    "tackles": pd.NA,
    "passes": pd.NA,
    "xT_added": pd.NA,
}


def build_player_match_features(
    appearances_df: pd.DataFrame,
    *,
    team_match_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build per-player match features without filling unavailable source metrics."""

    required = {"match_id", "player_id", "team_id", "minutes_played"}
    missing = sorted(required.difference(appearances_df.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"appearances_df is missing required columns: {missing_text}")

    player_match = appearances_df.copy()
    player_match["match_date"] = pd.to_datetime(player_match["match_date"], errors="raise")
    for stat_name, default_value in PLAYER_STAT_DEFAULTS.items():
        if stat_name not in player_match.columns:
            player_match[stat_name] = default_value

    if "started" in player_match.columns:
        player_match["starts"] = player_match["started"].fillna(0).astype(int)
    else:
        player_match["starts"] = (player_match["minutes_played"] >= 60).astype(int)

    player_match["available_flag"] = (player_match["minutes_played"] > 0).astype(int)
    team_minutes = player_match.groupby(["match_id", "team_id"])["minutes_played"].transform("sum")
    safe_team_minutes = team_minutes.where(team_minutes > 0)
    player_match["minutes_share"] = player_match["minutes_played"] / safe_team_minutes
    player_match["has_expected_metrics"] = player_match["npxg"].notna() | player_match["xa"].notna()
    player_match["has_ball_value_data"] = player_match["xT_added"].notna()

    if team_match_df is not None:
        merge_columns = [
            column
            for column in [
                "match_id",
                "team_id",
                "competition_id",
                "season_id",
                "opponent_team_id",
                "is_home",
            ]
            if column in team_match_df.columns
        ]
        team_context = team_match_df.loc[:, merge_columns].drop_duplicates()
        player_match = player_match.merge(team_context, on=["match_id", "team_id"], how="left")

    return player_match.sort_values(["player_id", "match_date", "match_id"]).reset_index(drop=True)

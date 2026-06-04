#!/usr/bin/env python3
"""Feature engineering on real data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd

from scoutlab.config import PlatformSettings


def main():
    settings = PlatformSettings.from_root()

    print("=" * 60)
    print("Phase 6: 特征工程 - 真实数据测试")
    print("=" * 60)

    # Load Football-Data (has odds and results)
    fd_path = settings.raw_root / "football_data" / "combined_results.parquet"
    matches = pd.read_parquet(fd_path)
    print(f"\n[1] 加载数据: {len(matches)} 场比赛")

    # Calculate team-level features
    print("\n[2] 计算球队特征...")

    # Home team features
    home_features = (
        matches.groupby(["league", "HomeTeam"])
        .agg(
            matches_played=("FTHG", "count"),
            home_goals_scored=("FTHG", "sum"),
            home_goals_conceded=("FTAG", "sum"),
            home_wins=("FTR", lambda x: (x == "H").sum()),
            home_draws=("FTR", lambda x: (x == "D").sum()),
            home_losses=("FTR", lambda x: (x == "A").sum()),
            home_shots=("HS", "sum"),
            home_shots_target=("HST", "sum"),
        )
        .reset_index()
    )

    # Away team features
    away_features = (
        matches.groupby(["league", "AwayTeam"])
        .agg(
            away_matches_played=("FTAG", "count"),
            away_goals_scored=("FTAG", "sum"),
            away_goals_conceded=("FTHG", "sum"),
            away_wins=("FTR", lambda x: (x == "A").sum()),
            away_draws=("FTR", lambda x: (x == "D").sum()),
            away_losses=("FTR", lambda x: (x == "H").sum()),
            away_shots=("AS", "sum"),
            away_shots_target=("AST", "sum"),
        )
        .reset_index()
    )

    # Merge and calculate derived features
    print("\n[3] 计算衍生特征...")

    # Rename for merge
    home_features = home_features.rename(columns={"HomeTeam": "team"})
    away_features = away_features.rename(columns={"AwayTeam": "team"})

    team_features = pd.merge(home_features, away_features, on=["league", "team"], how="outer")
    team_features = team_features.fillna(0)

    # Calculate per-match averages
    team_features["total_matches"] = (
        team_features["matches_played"] + team_features["away_matches_played"]
    )
    team_features["total_goals_scored"] = (
        team_features["home_goals_scored"] + team_features["away_goals_scored"]
    )
    team_features["total_goals_conceded"] = (
        team_features["home_goals_conceded"] + team_features["away_goals_conceded"]
    )

    team_features["goals_per_match"] = (
        team_features["total_goals_scored"] / team_features["total_matches"]
    )
    team_features["goals_conceded_per_match"] = (
        team_features["total_goals_conceded"] / team_features["total_matches"]
    )
    team_features["goal_difference"] = (
        team_features["total_goals_scored"] - team_features["total_goals_conceded"]
    )

    team_features["win_rate"] = (
        team_features["home_wins"] + team_features["away_wins"]
    ) / team_features["total_matches"]
    team_features["draw_rate"] = (
        team_features["home_draws"] + team_features["away_draws"]
    ) / team_features["total_matches"]
    team_features["loss_rate"] = (
        team_features["home_losses"] + team_features["away_losses"]
    ) / team_features["total_matches"]

    # Shot accuracy
    team_features["shot_accuracy"] = np.where(
        (team_features["home_shots"] + team_features["away_shots"]) > 0,
        (team_features["home_shots_target"] + team_features["away_shots_target"])
        / (team_features["home_shots"] + team_features["away_shots"]),
        0,
    )

    print(f"  ✓ 球队特征表: {len(team_features)} 支球队, {len(team_features.columns)} 个特征")

    # Show top teams by goal difference
    print("\n[4] 进球差 Top 10:")
    top_teams = team_features.nlargest(10, "goal_difference")
    for _, row in top_teams.iterrows():
        print(f"  {row['team']}: GD={row['goal_difference']:.0f}, Win%={row['win_rate']:.1%}")

    # Save features
    output_path = settings.gold_root / "feature_store" / "team_features.parquet"
    team_features.to_parquet(output_path, index=False)
    print(f"\n  ✓ 已保存: {output_path}")

    # Calculate match-level features
    print("\n[5] 计算比赛特征...")
    match_features = matches[
        ["league", "season", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]
    ].copy()
    match_features["total_goals"] = match_features["FTHG"] + match_features["FTAG"]
    match_features["home_win"] = (match_features["FTR"] == "H").astype(int)
    match_features["draw"] = (match_features["FTR"] == "D").astype(int)
    match_features["away_win"] = (match_features["FTR"] == "A").astype(int)

    # Add odds if available
    if "B365H" in matches.columns:
        match_features["odds_home"] = matches["B365H"]
        match_features["odds_draw"] = matches["B365D"]
        match_features["odds_away"] = matches["B365A"]
        match_features["implied_prob_home"] = 1 / match_features["odds_home"]
        match_features["implied_prob_draw"] = 1 / match_features["odds_draw"]
        match_features["implied_prob_away"] = 1 / match_features["odds_away"]

    match_output = settings.gold_root / "feature_store" / "match_features.parquet"
    match_features.to_parquet(match_output, index=False)
    print(f"  ✓ 比赛特征: {len(match_features)} 场, {len(match_features.columns)} 个特征")
    print(f"  ✓ 已保存: {match_output}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

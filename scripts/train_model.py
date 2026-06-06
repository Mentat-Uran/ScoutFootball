#!/usr/bin/env python3
"""Train baseline Poisson model for match prediction."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.model_selection import TimeSeriesSplit

from scoutfootball.config import PlatformSettings


def main():
    settings = PlatformSettings.from_root()

    print("=" * 60)
    print("Phase 7-8: 模型训练 - Poisson 比分预测基线")
    print("=" * 60)

    # Load features
    features_path = settings.gold_root / "feature_store" / "match_features.parquet"
    matches = pd.read_parquet(features_path)
    print(f"\n[1] 加载数据: {len(matches)} 场比赛")

    # Prepare features for Poisson model
    print("\n[2] 准备特征...")

    # Calculate team attack/defense strengths
    team_stats = {}
    for team in set(matches["HomeTeam"].unique()) | set(matches["AwayTeam"].unique()):
        home = matches[matches["HomeTeam"] == team]
        away = matches[matches["AwayTeam"] == team]

        team_stats[team] = {
            "home_goals_scored": home["FTHG"].mean() if len(home) > 0 else 0,
            "home_goals_conceded": home["FTAG"].mean() if len(home) > 0 else 0,
            "away_goals_scored": away["FTAG"].mean() if len(away) > 0 else 0,
            "away_goals_conceded": away["FTHG"].mean() if len(away) > 0 else 0,
        }

    # League averages
    league_avg_home_goals = matches["FTHG"].mean()
    league_avg_away_goals = matches["FTAG"].mean()

    print(f"  ✓ 联赛平均: 主场 {league_avg_home_goals:.2f} 球, 客场 {league_avg_away_goals:.2f} 球")

    # Calculate attack/defense strengths
    for team in team_stats:
        stats = team_stats[team]
        stats["home_attack"] = (
            stats["home_goals_scored"] / league_avg_home_goals if league_avg_home_goals > 0 else 1
        )
        stats["home_defense"] = (
            stats["home_goals_conceded"] / league_avg_away_goals if league_avg_away_goals > 0 else 1
        )
        stats["away_attack"] = (
            stats["away_goals_scored"] / league_avg_away_goals if league_avg_away_goals > 0 else 1
        )
        stats["away_defense"] = (
            stats["away_goals_conceded"] / league_avg_home_goals if league_avg_home_goals > 0 else 1
        )

    # Prepare training data
    print("\n[3] 训练 Poisson 模型...")

    feature_rows = []
    y_home = []
    y_away = []

    for _, row in matches.iterrows():
        home_team = row["HomeTeam"]
        away_team = row["AwayTeam"]

        if home_team in team_stats and away_team in team_stats:
            home_stats = team_stats[home_team]
            away_stats = team_stats[away_team]

            # Expected goals
            home_expected = (
                home_stats["home_attack"] * away_stats["away_defense"] * league_avg_home_goals
            )
            away_expected = (
                away_stats["away_attack"] * home_stats["home_defense"] * league_avg_away_goals
            )

            feature_rows.append([home_expected, away_expected])
            y_home.append(row["FTHG"])
            y_away.append(row["FTAG"])

    features = np.array(feature_rows)
    y_home = np.array(y_home)
    y_away = np.array(y_away)

    print(f"  ✓ 训练样本: {len(features)}")

    # Evaluate with time series split
    print("\n[4] 评估模型...")

    tscv = TimeSeriesSplit(n_splits=3)
    scores = []

    for _, test_idx in tscv.split(features):
        test_features = features[test_idx]
        y_home_test = y_home[test_idx]
        y_away_test = y_away[test_idx]

        # Calculate Poisson probabilities
        for i in range(len(test_features)):
            home_lambda = test_features[i, 0]
            away_lambda = test_features[i, 1]

            # Calculate score probabilities
            max_goals = 5
            home_probs = [poisson.pmf(k, home_lambda) for k in range(max_goals)]
            away_probs = [poisson.pmf(k, away_lambda) for k in range(max_goals)]

            # 1X2 probabilities
            home_win_prob = sum(
                home_probs[h] * away_probs[a]
                for h in range(max_goals)
                for a in range(max_goals)
                if h > a
            )
            draw_prob = sum(
                home_probs[h] * away_probs[a]
                for h in range(max_goals)
                for a in range(max_goals)
                if h == a
            )
            away_win_prob = sum(
                home_probs[h] * away_probs[a]
                for h in range(max_goals)
                for a in range(max_goals)
                if h < a
            )

            # Actual outcome
            if y_home_test[i] > y_away_test[i]:
                actual = 0  # Home win
            elif y_home_test[i] == y_away_test[i]:
                actual = 1  # Draw
            else:
                actual = 2  # Away win

            # Log loss for this prediction
            probs = np.array([home_win_prob, draw_prob, away_win_prob])
            probs = np.clip(probs, 1e-10, 1 - 1e-10)
            probs = probs / probs.sum()

            score = -np.log(probs[actual])
            scores.append(score)

    avg_log_loss = np.mean(scores)
    print(f"  ✓ 平均 Log Loss: {avg_log_loss:.4f}")

    # Show predictions for next matches
    print("\n[5] 预测示例 (最近 5 场比赛):")
    recent = matches.tail(5)

    for _, row in recent.iterrows():
        home_team = row["HomeTeam"]
        away_team = row["AwayTeam"]

        if home_team in team_stats and away_team in team_stats:
            home_stats = team_stats[home_team]
            away_stats = team_stats[away_team]

            home_expected = (
                home_stats["home_attack"] * away_stats["away_defense"] * league_avg_home_goals
            )
            away_expected = (
                away_stats["away_attack"] * home_stats["home_defense"] * league_avg_away_goals
            )

            # 1X2 probabilities
            max_goals = 5
            home_probs = [poisson.pmf(k, home_expected) for k in range(max_goals)]
            away_probs = [poisson.pmf(k, away_expected) for k in range(max_goals)]

            home_win_prob = sum(
                home_probs[h] * away_probs[a]
                for h in range(max_goals)
                for a in range(max_goals)
                if h > a
            )
            draw_prob = sum(
                home_probs[h] * away_probs[a]
                for h in range(max_goals)
                for a in range(max_goals)
                if h == a
            )
            away_win_prob = sum(
                home_probs[h] * away_probs[a]
                for h in range(max_goals)
                for a in range(max_goals)
                if h < a
            )

            print(f"\n  {home_team} vs {away_team}")
            print(f"    期望进球: {home_expected:.2f} - {away_expected:.2f}")
            print(f"    胜平负概率: {home_win_prob:.1%} / {draw_prob:.1%} / {away_win_prob:.1%}")

    # Save model results
    print("\n[6] 保存模型结果...")

    model_results = {
        "model_type": "poisson_baseline",
        "train_samples": len(features),
        "avg_log_loss": avg_log_loss,
        "league_avg_home_goals": league_avg_home_goals,
        "league_avg_away_goals": league_avg_away_goals,
    }

    results_df = pd.DataFrame([model_results])
    results_path = settings.model_root / "artifacts" / "poisson_baseline_results.parquet"
    results_df.to_parquet(results_path, index=False)
    print(f"  ✓ 已保存: {results_path}")

    # Save team strengths
    team_strengths = pd.DataFrame.from_dict(team_stats, orient="index")
    team_strengths.index.name = "team"
    strengths_path = settings.model_root / "artifacts" / "team_strengths.parquet"
    team_strengths.to_parquet(strengths_path)
    print(f"  ✓ 已保存: {strengths_path}")

    print("\n" + "=" * 60)
    print("模型训练完成!")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

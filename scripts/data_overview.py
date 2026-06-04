#!/usr/bin/env python3
"""
五大联赛球员数据概览
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutlab.config import PlatformSettings


def main():
    settings = PlatformSettings.from_root()

    # 加载 FBref 数据
    fbref_path = settings.raw_root / "fbref" / "player_stats_big5_3seasons.parquet"
    df = pd.read_parquet(fbref_path)

    print("=" * 60)
    print("五大联赛球员数据概览")
    print("=" * 60)

    print(f"\n总记录数: {len(df)}")
    print(f"独特球员数: {df.index.get_level_values('player').nunique()}")

    print("\n联赛分布:")
    for league in df.index.get_level_values("league").dropna().unique():
        league_data = df.xs(league, level="league")
        unique_players = league_data.index.get_level_values("player").nunique()
        print(f"  {league}: {len(league_data)} 记录, {unique_players} 球员")

    print("\n赛季分布:")
    for season in df.index.get_level_values("season").unique():
        print(f"  {season}")

    # 显示主要列
    print("\n主要统计列:")
    cols = [c for c in df.columns if isinstance(c, tuple)]
    for col in cols[:15]:
        print(f"  {col[0]} - {col[1]}")

    # 样本数据
    print("\n样本数据 (Top 10 进球手):")
    # 找到进球列
    goals_col = None
    for col in df.columns:
        if isinstance(col, tuple) and col[1] == "Gls":
            goals_col = col
            break

    if goals_col:
        player_goals = pd.Series(
            pd.to_numeric(df[goals_col], errors="coerce").fillna(0.0).to_numpy(),
            index=df.index.get_level_values("player"),
        )
        top_scorers = player_goals.groupby(level=0).sum().nlargest(10)
        for player, goals in top_scorers.items():
            print(f"  {player}: {goals} 球")

    # 数据文件位置
    print("\n数据文件位置:")
    print(f"  {fbref_path}")

    # 其他可用数据
    print("\n其他可用数据:")
    other_files = [
        settings.raw_root / "statsbomb_open" / "big5_matches.parquet",
        settings.raw_root / "football_data" / "combined_results.parquet",
        settings.gold_root / "feature_store" / "team_features.parquet",
        settings.gold_root / "feature_store" / "player_value_metrics.parquet",
    ]

    for f in other_files:
        if f.exists():
            size = f.stat().st_size / 1024
            print(f"  ✓ {f.name} ({size:.1f} KB)")
        else:
            print(f"  ✗ {f.name} (不存在)")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

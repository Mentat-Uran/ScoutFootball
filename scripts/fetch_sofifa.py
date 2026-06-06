#!/usr/bin/env python3
"""
抓取 SoFIFA 球员属性数据 (FIFA 20-25)
覆盖 Big 5 + 扩展联赛
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutfootball.adapters.sofifa import fetch_player_attributes
from scoutfootball.config import PlatformSettings


def main():
    settings = PlatformSettings.from_root()

    # Big 5 + 扩展联赛 (SoFIFA league identifiers)
    leagues = [
        "ENG-Premier League",
        "ESP-La Liga",
        "GER-Bundesliga",
        "ITA-Serie A",
        "FRA-Ligue 1",
        "POR-Primeira Liga",
        "NED-Eredivisie",
        "TUR-Süper Lig",
        "SCO-Scottish Premiership",
        "BEL-First Division A",
    ]

    # FIFA 20-25 (season 20, 21, 22, 23, 24, 25)
    seasons = [20, 21, 22, 23, 24, 25]

    print("=" * 60)
    print("SoFIFA - FIFA 20-25 球员属性数据")
    print("=" * 60)

    all_frames = []
    success_count = 0
    fail_count = 0

    for league in leagues:
        for season in seasons:
            try:
                result = fetch_player_attributes(
                    league,
                    season,
                    settings=settings,
                    force_refresh=False,
                )
                df = result.dataframe
                all_frames.append(df)
                success_count += 1
                print(f"  ✓ {league} FIFA {season}: {len(df)} 球员")
            except Exception as e:
                fail_count += 1
                print(f"  ✗ {league} FIFA {season}: {e}")

    if all_frames:
        combined = pd.concat(all_frames, ignore_index=True)
        output_path = settings.raw_root / "sofifa" / "player_attributes.parquet"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_parquet(output_path, index=False)

        print(f"\n总计: {len(combined)} 条球员记录")
        print(f"已保存: {output_path}")
        print(f"成功获取: {success_count}/{len(leagues) * len(seasons)} 个数据集")
        print(f"失败: {fail_count}")

        # Season distribution
        print("\nFIFA 版本分布:")
        for season in sorted(combined["season"].unique()):
            count = len(combined[combined["season"] == season])
            print(f"  FIFA {season}: {count} 条")

        # League distribution
        print("\n联赛分布:")
        for league in sorted(combined["league"].unique()):
            count = len(combined[combined["league"] == league])
            print(f"  {league}: {count} 条")

        # Position distribution
        if "position" in combined.columns:
            print("\n位置分布:")
            for pos in combined["position"].dropna().value_counts().head(15).index:
                count = len(combined[combined["position"] == pos])
                print(f"  {pos}: {count} 条")

    return success_count > 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

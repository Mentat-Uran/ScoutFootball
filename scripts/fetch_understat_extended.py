#!/usr/bin/env python3
"""
抓取 Understat 10 赛季五大联赛球员数据
包含 xG, xA, npxG, xGChain, xGBuildup
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
from scoutfootball.adapters.common import CachedHttpClient
from scoutfootball.adapters.understat import fetch_league_players
from scoutfootball.config import PlatformSettings


def main():
    settings = PlatformSettings.from_root()
    client = CachedHttpClient(settings=settings)

    # Understat 联赛名 (含 RFPL: Russian Premier League)
    leagues = ["EPL", "La_Liga", "Bundesliga", "Serie_A", "Ligue_1", "RFPL"]
    
    # 10 赛季: 2016/17 to 2025/26
    seasons = [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]

    print("=" * 60)
    print("Understat - 10 赛季五大联赛球员数据")
    print("=" * 60)

    all_frames = []
    success_count = 0
    fail_count = 0

    for league in leagues:
        for season in seasons:
            try:
                result = fetch_league_players(
                    league,
                    season,
                    client=client,
                    settings=settings,
                    force_refresh=False,
                )
                df = result.dataframe
                df["league"] = league
                df["season"] = f"{season}{season+1-2000:02d}"  # e.g. 2016 -> "1617"
                all_frames.append(df)
                success_count += 1
                print(f"  ✓ {league} {season}: {len(df)} 球员")
            except Exception as e:
                fail_count += 1
                print(f"  ✗ {league} {season}: {e}")

    if all_frames:
        combined = pd.concat(all_frames, ignore_index=True)
        output_path = settings.raw_root / "understat" / "players_10seasons.parquet"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_parquet(output_path, index=False)

        print(f"\n总计: {len(combined)} 条球员记录")
        print(f"已保存: {output_path}")
        print(f"成功获取: {success_count}/{len(leagues) * len(seasons)} 个数据集")
        print(f"失败: {fail_count}")

        # Show season distribution
        print("\n赛季分布:")
        for season in sorted(combined["season"].unique()):
            count = len(combined[combined["season"] == season])
            print(f"  {season}: {count} 条")

        # Show league distribution
        print("\n联赛分布:")
        for league in sorted(combined["league"].unique()):
            count = len(combined[combined["league"] == league])
            print(f"  {league}: {count} 条")

    return success_count > 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

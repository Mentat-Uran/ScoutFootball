#!/usr/bin/env python3
"""
获取 FBref 五大联赛近三个赛季球员数据
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutlab.adapters.fbref_soccerdata import read_player_season_stats_with_bundesliga_fallback
from scoutlab.config import PlatformSettings


def main():
    settings = PlatformSettings.from_root()

    print("=" * 60)
    print("获取 FBref 五大联赛近三个赛季球员数据")
    print("=" * 60)

    try:
        # 近三个赛季
        seasons = ["2022-2023", "2023-2024", "2024-2025"]

        all_data = []

        for season in seasons:
            print(f"\n[{len(all_data) + 1}/{len(seasons)}] 获取 {season} 赛季数据...")

            try:
                # Big 5 combined currently omits Bundesliga in soccerdata.
                player_stats = read_player_season_stats_with_bundesliga_fallback(
                    season,
                    stat_type="standard",
                )

                if not player_stats.empty:
                    # 添加赛季列
                    player_stats["season"] = season
                    all_data.append(player_stats)

                    print(f"  ✓ 球员数: {player_stats.index.get_level_values('player').nunique()}")
                    print(f"  ✓ 记录数: {len(player_stats)}")
                else:
                    print("  ✗ 无数据")

            except Exception as e:
                print(f"  ✗ 获取失败: {e}")

        if all_data:
            # 合并所有赛季数据
            combined = pd.concat(all_data)

            # 保存数据
            output_path = settings.raw_root / "fbref" / "player_stats_big5_3seasons.parquet"
            combined.to_parquet(output_path, index=True)

            print("\n[汇总]")
            print("-" * 60)
            print(f"  总记录数: {len(combined)}")
            print(f"  球员数: {combined.index.get_level_values('player').nunique()}")
            print(f"  联赛: {combined.index.get_level_values('league').unique().tolist()}")
            print(f"  赛季: {seasons}")
            print(f"\n  保存位置: {output_path}")

            # 统计每个联赛的球员数
            print("\n  各联赛球员数:")
            for league in combined.index.get_level_values("league").unique():
                league_data = combined.xs(league, level="league")
                players = league_data.index.get_level_values("player").nunique()
                print(f"    {league}: {players} 球员")

            return True

    except ImportError:
        print("soccerdata 未安装")
    except Exception as e:
        print(f"获取失败: {e}")
        import traceback

        traceback.print_exc()

    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

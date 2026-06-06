#!/usr/bin/env python3
"""
使用 soccerdata 获取 FBref 五大联赛球员数据
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scoutfootball.config import PlatformSettings


def main():
    settings = PlatformSettings.from_root()

    print("=" * 60)
    print("使用 soccerdata 获取 FBref 球员数据")
    print("=" * 60)

    try:
        import soccerdata as sd

        # 获取 Big 5 联赛数据
        print("\n[1] 初始化 FBref 客户端...")
        fbref = sd.FBref(leagues=["Big 5 European Leagues Combined"], seasons=["2024-2025"])

        # 获取球员标准统计
        print("\n[2] 获取球员标准统计...")
        player_stats = fbref.read_player_season_stats(stat_type="standard")

        if not player_stats.empty:
            print(f"  ✓ 获取成功: {len(player_stats)} 条记录")
            print(f"  ✓ 球员数: {player_stats.index.get_level_values('player').nunique()}")

            # 显示列
            print(f"  ✓ 列数: {len(player_stats.columns)}")
            print(f"  ✓ 主要列: {list(player_stats.columns[:10])}")

            # 保存数据
            output_path = settings.raw_root / "fbref" / "player_standard_stats_2024_2025.parquet"
            player_stats.to_parquet(output_path, index=True)
            print(f"\n  ✓ 已保存: {output_path}")

            # 显示样本数据
            print("\n[3] 样本数据:")
            print("-" * 60)
            sample = player_stats.head(5)
            print(sample.to_string())

            return True

    except ImportError:
        print("  soccerdata 未安装")
    except Exception as e:
        print(f"  获取失败: {e}")
        import traceback

        traceback.print_exc()

    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
获取五大联赛球员数据
来源: FBref (通过 soccerdata) + Kaggle 数据集
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutfootball.config import PlatformSettings


def main():
    settings = PlatformSettings.from_root()

    print("=" * 60)
    print("五大联赛球员数据获取")
    print("=" * 60)

    # 检查是否有 Kaggle 数据集
    kaggle_path = settings.raw_root / "fbref" / "players_data-2024_2025.csv"

    if kaggle_path.exists():
        print("\n[1] 发现 Kaggle 数据集")
        df = pd.read_csv(kaggle_path)
        print(f"  ✓ 球员数: {len(df)}")
        print(f"  ✓ 列数: {len(df.columns)}")
        print(f"  ✓ 联赛: {df['Comp'].unique() if 'Comp' in df.columns else 'N/A'}")
        return True

    print("\n[1] 未找到本地数据集")
    print("  请从以下地址下载数据:")
    print("  https://www.kaggle.com/datasets/hubertsidorowicz/football-players-stats-2024-2025")
    print(f"\n  下载后保存到: {kaggle_path}")

    # 尝试使用 soccerdata 获取 FBref 数据
    print("\n[2] 尝试使用 soccerdata 获取 FBref 数据...")

    try:
        import soccerdata as sd

        # 初始化 FBref 客户端
        fbref = sd.FBref(leagues=["Big 5 European Leagues Combined"], seasons=["2024-2025"])

        # 获取球员标准统计
        print("  获取球员标准统计...")
        player_stats = fbref.read_player_season_stats(stat_type="standard")

        if not player_stats.empty:
            print(f"  ✓ 获取成功: {len(player_stats)} 条记录")

            # 保存数据
            output_path = settings.raw_root / "fbref" / "player_standard_stats.parquet"
            player_stats.to_parquet(output_path, index=False)
            print(f"  ✓ 已保存: {output_path}")

            return True

    except ImportError:
        print("  soccerdata 未安装，跳过")
    except Exception as e:
        print(f"  获取失败: {e}")

    print("\n[3] 使用 Football-Data.co.uk 作为补充...")

    # Football-Data 数据已获取
    fd_path = settings.raw_root / "football_data" / "combined_results.parquet"
    if fd_path.exists():
        fd = pd.read_parquet(fd_path)
        print(f"  ✓ Football-Data 数据: {len(fd)} 场比赛")

        # 提取独特球队
        teams = pd.concat(
            [
                fd[["HomeTeam"]].rename(columns={"HomeTeam": "team"}),
                fd[["AwayTeam"]].rename(columns={"AwayTeam": "team"}),
            ]
        ).drop_duplicates()
        print(f"  ✓ 球队数: {len(teams)}")

    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

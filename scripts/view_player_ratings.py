#!/usr/bin/env python3
"""
球员评分数据交互式查看工具
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutlab.config import PlatformSettings


def load_data():
    """加载数据"""
    settings = PlatformSettings.from_root()
    path = settings.gold_root / "feature_store" / "player_ratings_v2.parquet"
    return pd.read_parquet(path)


def show_top_n(df, n=20):
    """显示 Top N 球员"""
    print(f"\n{'=' * 90}")
    print(f"Top {n} 球员综合评分")
    print(f"{'=' * 90}")
    print(
        f"{'排名':<4} {'球员':<25} {'联赛':<15} {'位置':<6} "
        f"{'评分':<6} {'出场':<5} {'进球':<5} {'助攻':<5}"
    )
    print(f"{'-' * 90}")

    for i, (_, row) in enumerate(df.head(n).iterrows(), 1):
        league_short = (
            row["league"]
            .replace("ENG-", "")
            .replace("ESP-", "")
            .replace("FRA-", "")
            .replace("ITA-", "")
        )
        print(
            f"{i:<4} {row['player']:<25} {league_short:<15} {row['position']:<6} "
            f"{row['composite_score']:<6.1f} {row['matches']:<5} "
            f"{row['goals']:<5} {row['assists']:<5}"
        )


def search_player(df, name):
    """搜索球员"""
    results = df[df["player"].str.contains(name, case=False, na=False)]

    if results.empty:
        print(f'\n未找到包含 "{name}" 的球员')
        return

    print(f"\n搜索结果: {len(results)} 条记录")
    print(f"{'-' * 90}")
    print(
        f"{'球员':<25} {'联赛':<15} {'赛季':<8} {'位置':<6} "
        f"{'评分':<6} {'出场':<5} {'进球':<5} {'助攻':<5}"
    )
    print(f"{'-' * 90}")

    for _, row in results.iterrows():
        league_short = (
            row["league"]
            .replace("ENG-", "")
            .replace("ESP-", "")
            .replace("FRA-", "")
            .replace("ITA-", "")
        )
        print(
            f"{row['player']:<25} {league_short:<15} {row['season']:<8} {row['position']:<6} "
            f"{row['composite_score']:<6.1f} {row['matches']:<5} "
            f"{row['goals']:<5} {row['assists']:<5}"
        )


def filter_by_league(df, league):
    """按联赛筛选"""
    league_map = {
        "eng": "ENG-Premier League",
        "esp": "ESP-La Liga",
        "fra": "FRA-Ligue 1",
        "ita": "ITA-Serie A",
    }

    league_key = league_map.get(league.lower())
    if not league_key:
        print(f"无效的联赛代码: {league}")
        print("可用代码: eng, esp, fra, ita")
        return

    filtered = df[df["league"] == league_key]
    print(f"\n{league_key} 球员数: {len(filtered)}")
    show_top_n(filtered, 20)


def filter_by_position(df, position):
    """按位置筛选"""
    position_map = {
        "fw": "FW",
        "mf": "MF",
        "df": "DF",
        "gk": "GK",
    }

    pos_key = position_map.get(position.lower())
    if not pos_key:
        print(f"无效的位置代码: {position}")
        print("可用代码: fw, mf, df, gk")
        return

    filtered = df[df["pos_group"] == pos_key]
    print(f"\n{pos_key} 球员数: {len(filtered)}")
    show_top_n(filtered, 20)


def show_stats(df):
    """显示统计信息"""
    print(f"\n{'=' * 90}")
    print("数据统计")
    print(f"{'=' * 90}")

    print(f"\n总记录数: {len(df)}")
    print(f"独特球员数: {df['player'].nunique()}")

    print("\n联赛分布:")
    for league in df["league"].unique():
        count = len(df[df["league"] == league])
        league_short = (
            league.replace("ENG-", "").replace("ESP-", "").replace("FRA-", "").replace("ITA-", "")
        )
        print(f"  {league_short}: {count} 条记录")

    print("\n位置分布:")
    for pos in df["pos_group"].unique():
        count = len(df[df["pos_group"] == pos])
        print(f"  {pos}: {count} 条记录")

    # 评分分布
    qualified = df[df["matches"] >= 10]
    print("\n评分分布 (出场≥10场):")
    print(f"  球员数: {len(qualified)}")
    print(f"  平均评分: {qualified['composite_score'].mean():.1f}")
    print(f"  最高评分: {qualified['composite_score'].max():.1f}")
    print(f"  最低评分: {qualified['composite_score'].min():.1f}")


def show_help():
    """显示帮助信息"""
    print(f"\n{'=' * 90}")
    print("球员评分数据查看工具 - 使用说明")
    print(f"{'=' * 90}")
    print("""
命令:
  top [N]           - 显示 Top N 球员 (默认 20)
  search <名字>     - 搜索球员
  league <代码>     - 按联赛筛选 (eng, esp, fra, ita)
  position <代码>   - 按位置筛选 (fw, mf, df, gk)
  stats             - 显示统计信息
  help              - 显示此帮助
  quit              - 退出

示例:
  top 50
  search Salah
  league eng
  position fw
""")


def main():
    print("=" * 90)
    print("球员评分数据查看工具")
    print("=" * 90)

    # 加载数据
    df = load_data()
    print(f"已加载 {len(df)} 条记录")

    # 显示默认 Top 20
    show_top_n(df, 20)

    # 交互式命令行
    print("\n输入 help 查看可用命令")

    while True:
        try:
            cmd = input("\n> ").strip()

            if not cmd:
                continue

            parts = cmd.split()
            action = parts[0].lower()

            if action == "quit" or action == "exit":
                print("再见!")
                break
            elif action == "top":
                n = int(parts[1]) if len(parts) > 1 else 20
                show_top_n(df, n)
            elif action == "search":
                name = " ".join(parts[1:])
                search_player(df, name)
            elif action == "league":
                league = parts[1] if len(parts) > 1 else ""
                filter_by_league(df, league)
            elif action == "position":
                position = parts[1] if len(parts) > 1 else ""
                filter_by_position(df, position)
            elif action == "stats":
                show_stats(df)
            elif action == "help":
                show_help()
            else:
                print(f"未知命令: {action}")
                print("输入 help 查看可用命令")

        except KeyboardInterrupt:
            print("\n再见!")
            break
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    main()

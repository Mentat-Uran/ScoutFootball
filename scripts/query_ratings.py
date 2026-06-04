#!/usr/bin/env python3
"""
球员评分快速查询
用法:
  python scripts/query_ratings.py top [N]
  python scripts/query_ratings.py search <名字>
  python scripts/query_ratings.py league <eng|esp|fra|ita>
  python scripts/query_ratings.py position <fw|mf|df|gk>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutlab.config import PlatformSettings


def load_data():
    settings = PlatformSettings.from_root()
    path = settings.gold_root / "feature_store" / "player_ratings_v2.parquet"
    return pd.read_parquet(path)


def format_table(df, n=None):
    """格式化输出表格"""
    if n:
        df = df.head(n)

    print(
        f"{'排名':<4} {'球员':<25} {'联赛':<12} {'位置':<6} "
        f"{'评分':<6} {'出场':<5} {'进球':<5} {'助攻':<5}"
    )
    print("-" * 80)

    for i, (_, row) in enumerate(df.iterrows(), 1):
        league_short = (
            row["league"]
            .replace("ENG-", "")
            .replace("ESP-", "")
            .replace("FRA-", "")
            .replace("ITA-", "")
        )
        print(
            f"{i:<4} {row['player']:<25} {league_short:<12} {row['position']:<6} "
            f"{row['composite_score']:<6.1f} {row['matches']:<5} "
            f"{row['goals']:<5} {row['assists']:<5}"
        )


def main():
    df = load_data()

    if len(sys.argv) < 2:
        # 默认显示 Top 20
        print("\n球员综合评分 Top 20")
        print("=" * 80)
        format_table(df, 20)
        return

    cmd = sys.argv[1].lower()

    if cmd == "top":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        print(f"\n球员综合评分 Top {n}")
        print("=" * 80)
        format_table(df, n)

    elif cmd == "search":
        name = " ".join(sys.argv[2:])
        results = df[df["player"].str.contains(name, case=False, na=False)]

        if results.empty:
            print(f'未找到包含 "{name}" 的球员')
            return

        print(f"\n搜索结果: {len(results)} 条记录")
        print("=" * 80)
        format_table(results)

    elif cmd == "league":
        league_map = {
            "eng": "ENG-Premier League",
            "esp": "ESP-La Liga",
            "fra": "FRA-Ligue 1",
            "ita": "ITA-Serie A",
        }

        league_code = sys.argv[2].lower() if len(sys.argv) > 2 else ""
        league_key = league_map.get(league_code)

        if not league_key:
            print("可用联赛代码: eng, esp, fra, ita")
            return

        filtered = df[df["league"] == league_key]
        print(f"\n{league_key} Top 20")
        print("=" * 80)
        format_table(filtered, 20)

    elif cmd == "position":
        pos_map = {
            "fw": "FW",
            "mf": "MF",
            "df": "DF",
            "gk": "GK",
        }

        pos_code = sys.argv[2].lower() if len(sys.argv) > 2 else ""
        pos_key = pos_map.get(pos_code)

        if not pos_key:
            print("可用位置代码: fw, mf, df, gk")
            return

        filtered = df[df["pos_group"] == pos_key]
        print(f"\n{pos_key} 球员 Top 20")
        print("=" * 80)
        format_table(filtered, 20)

    elif cmd == "stats":
        print("\n数据统计")
        print("=" * 80)
        print(f"总记录数: {len(df)}")
        print(f"独特球员数: {df['player'].nunique()}")

        print("\n联赛分布:")
        for league in df["league"].unique():
            count = len(df[df["league"] == league])
            league_short = (
                league.replace("ENG-", "")
                .replace("ESP-", "")
                .replace("FRA-", "")
                .replace("ITA-", "")
            )
            print(f"  {league_short}: {count}")

        qualified = df[df["matches"] >= 10]
        print(f"\n出场≥10场的球员: {len(qualified)}")
        print(f"平均评分: {qualified['composite_score'].mean():.1f}")
        print(f"最高评分: {qualified['composite_score'].max():.1f}")

    else:
        print("""
用法:
  python scripts/query_ratings.py top [N]           - 显示 Top N 球员
  python scripts/query_ratings.py search <名字>     - 搜索球员
  python scripts/query_ratings.py league <代码>     - 按联赛筛选 (eng, esp, fra, ita)
  python scripts/query_ratings.py position <代码>   - 按位置筛选 (fw, mf, df, gk)
  python scripts/query_ratings.py stats             - 显示统计信息
""")


if __name__ == "__main__":
    main()

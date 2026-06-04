#!/usr/bin/env python3
"""
五大联赛球员价值排名
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

    print("=" * 70)
    print("五大联赛球员数据统计 (2022-2025)")
    print("=" * 70)

    # 使用列表形式访问多级列
    goals_col = [("Performance", "Gls")]
    assists_col = [("Performance", "Ast")]
    minutes_col = [("Playing Time", "Min")]

    # Top 10 进球手
    print("\n[1] Top 10 进球手 (三个赛季总和):")
    print("-" * 70)
    goals_by_player = df.groupby(level="player")[goals_col].sum()
    goals_by_player.columns = ["goals"]
    top_scorers = goals_by_player.nlargest(10, "goals")
    for i, (player, row) in enumerate(top_scorers.iterrows(), 1):
        print(f"  {i:2}. {player:<35} {row['goals']:>5.0f} 球")

    # Top 10 助攻手
    print("\n[2] Top 10 助攻手 (三个赛季总和):")
    print("-" * 70)
    assists_by_player = df.groupby(level="player")[assists_col].sum()
    assists_by_player.columns = ["assists"]
    top_assisters = assists_by_player.nlargest(10, "assists")
    for i, (player, row) in enumerate(top_assisters.iterrows(), 1):
        print(f"  {i:2}. {player:<35} {row['assists']:>5.0f} 助攻")

    # Top 10 进球+助攻
    print("\n[3] Top 10 进球+助攻 (三个赛季总和):")
    print("-" * 70)
    ga_by_player = pd.DataFrame(
        {
            "goals": goals_by_player["goals"],
            "assists": assists_by_player["assists"],
        }
    )
    ga_by_player["g_a"] = ga_by_player["goals"] + ga_by_player["assists"]
    top_ga = ga_by_player.nlargest(10, "g_a")
    for i, (player, row) in enumerate(top_ga.iterrows(), 1):
        print(f"  {i:2}. {player:<35} {row['g_a']:>5.0f} (G+A)")

    # 按联赛统计
    print("\n[4] 各联赛进球王:")
    print("-" * 70)
    for league in ["ENG-Premier League", "ESP-La Liga", "FRA-Ligue 1", "ITA-Serie A"]:
        try:
            league_data = df.xs(league, level="league")
            league_goals = league_data.groupby(level="player")[goals_col].sum()
            league_goals.columns = ["goals"]
            top = league_goals.nlargest(1, "goals")
            if not top.empty:
                player = top.index[0]
                goals = top.iloc[0, 0]
                print(f"  {league:<25} {player:<30} {goals:.0f} 球")
        except Exception:
            pass

    # 每90分钟效率
    print("\n[5] Top 10 每90分钟进球效率 (至少1000分钟):")
    print("-" * 70)
    # 计算总分钟数
    total_minutes = df.groupby(level="player")[minutes_col].sum()
    total_minutes.columns = ["minutes"]
    eligible = total_minutes[total_minutes["minutes"] >= 1000].index

    if len(eligible) > 0:
        eligible_data = df.loc[df.index.get_level_values("player").isin(eligible)]
        total_goals = eligible_data.groupby(level="player")[goals_col].sum()
        total_goals.columns = ["goals"]

        efficiency = pd.DataFrame(
            {
                "goals": total_goals["goals"],
                "minutes": total_minutes.loc[eligible, "minutes"],
            }
        )
        efficiency["goals_per_90"] = efficiency["goals"] / efficiency["minutes"] * 90
        top_eff = efficiency.nlargest(10, "goals_per_90")
        for i, (player, row) in enumerate(top_eff.iterrows(), 1):
            print(f"  {i:2}. {player:<35} {row['goals_per_90']:.2f} 球/90分钟")

    # 各联赛最佳阵容 (按位置)
    print("\n[6] 各联赛最佳阵容 (按进球+助攻):")
    print("-" * 70)

    # 找到位置列
    pos_col = [("pos", "")]

    for league in ["ENG-Premier League", "ESP-La Liga", "FRA-Ligue 1", "ITA-Serie A"]:
        try:
            league_data = df.xs(league, level="league")

            # 计算每个球员的进球+助攻
            league_ga = league_data.groupby(level="player").apply(
                lambda x: x[goals_col].sum().iloc[0] + x[assists_col].sum().iloc[0]
            )

            # 获取位置信息
            league_pos = league_data.groupby(level="player")[pos_col].first()
            league_pos.columns = ["position"]

            # 合并数据
            best_players = pd.DataFrame(
                {
                    "g_a": league_ga,
                    "position": league_pos["position"],
                }
            )

            # 按位置分组取最佳
            print(f"\n  {league}:")
            for pos in ["FW", "MF", "DF", "GK"]:
                pos_players = best_players[best_players["position"].str.contains(pos, na=False)]
                if not pos_players.empty:
                    best = pos_players.nlargest(1, "g_a")
                    if not best.empty:
                        player = best.index[0]
                        g_a = best.iloc[0]["g_a"]
                        print(f"    {pos}: {player:<30} {g_a:.0f} (G+A)")
        except Exception:
            pass

    print("\n" + "=" * 70)
    print("数据来源: FBref via soccerdata")
    print("数据范围: 2022-2023, 2023-2024, 2024-2025 赛季")
    print("覆盖联赛: 英超、西甲、法甲、意甲")
    print("=" * 70)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

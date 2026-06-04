#!/usr/bin/env python3
"""
球员综合评分系统
考虑出场时间、首发次数、各项统计数据
适用于前中后场球员
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutlab.config import PlatformSettings


class PlayerRatingSystem:
    """
    球员综合评分系统

    评分维度:
    1. 出场权重 (出场次数、首发率、总分钟数)
    2. 进攻贡献 (进球、助攻、xG)
    3. 防守贡献 (铲球、拦截、对抗)
    4. 控球贡献 (传球、带球、触球)
    5. 效率指标 (每90分钟数据)
    """

    def __init__(self):
        # 各位置权重配置
        self.position_weights = {
            "FW": {  # 前锋
                "appearance": 0.15,
                "offensive": 0.45,
                "defensive": 0.05,
                "possession": 0.15,
                "efficiency": 0.20,
            },
            "MF": {  # 中场
                "appearance": 0.15,
                "offensive": 0.25,
                "defensive": 0.20,
                "possession": 0.25,
                "efficiency": 0.15,
            },
            "DF": {  # 后卫
                "appearance": 0.15,
                "offensive": 0.10,
                "defensive": 0.40,
                "possession": 0.20,
                "efficiency": 0.15,
            },
            "GK": {  # 门将
                "appearance": 0.20,
                "offensive": 0.05,
                "defensive": 0.35,
                "possession": 0.25,
                "efficiency": 0.15,
            },
        }

    def calculate_appearance_score(self, row):
        """
        出场评分
        - 比赛场次 (MP)
        - 首发次数 (Starts)
        - 总分钟数 (Min)
        - 首发率 (Starts/MP)
        """
        mp = row.get(("Playing Time", "MP"), 0)
        starts = row.get(("Playing Time", "Starts"), 0)
        minutes = row.get(("Playing Time", "Min"), 0)

        # 首发率
        start_rate = starts / mp if mp > 0 else 0

        # 评分计算
        # 比赛场次评分 (0-100, 满分38场)
        mp_score = min(mp / 38 * 100, 100)

        # 首发率评分 (0-100)
        start_rate_score = start_rate * 100

        # 分钟数评分 (0-100, 满分3420分钟 = 38场*90分钟)
        minutes_score = min(minutes / 3420 * 100, 100)

        # 综合出场评分
        appearance_score = mp_score * 0.3 + start_rate_score * 0.3 + minutes_score * 0.4

        return appearance_score, mp, starts, minutes, start_rate

    def calculate_offensive_score(self, row, position):
        """
        进攻评分
        - 进球 (Gls)
        - 助攻 (Ast)
        - 进球+助攻 (G+A)
        - 点球 (PK)
        - 每90分钟进球
        """
        goals = row.get(("Performance", "Gls"), 0)
        assists = row.get(("Performance", "Ast"), 0)
        g_a = row.get(("Performance", "G+A"), 0)
        pk = row.get(("Performance", "PK"), 0)
        # 非点球进球
        npg = goals - pk

        # 根据位置调整权重
        if position == "FW":
            goal_weight = 0.50
            assist_weight = 0.25
            g_a_weight = 0.25
        elif position == "MF":
            goal_weight = 0.30
            assist_weight = 0.40
            g_a_weight = 0.30
        else:  # DF, GK
            goal_weight = 0.20
            assist_weight = 0.40
            g_a_weight = 0.40

        # 标准化分数 (基于历史数据分布)
        # 前锋: 满分约25球/赛季
        # 中场: 满分约15球+15助攻/赛季
        # 后卫: 满分约5球+10助攻/赛季

        if position == "FW":
            goal_score = min(npg / 25 * 100, 100)
            assist_score = min(assists / 15 * 100, 100)
        elif position == "MF":
            goal_score = min(npg / 15 * 100, 100)
            assist_score = min(assists / 15 * 100, 100)
        else:
            goal_score = min(npg / 5 * 100, 100)
            assist_score = min(assists / 10 * 100, 100)

        g_a_score = min(g_a / 30 * 100, 100)

        # 综合进攻评分
        offensive_score = (
            goal_score * goal_weight + assist_score * assist_weight + g_a_score * g_a_weight
        )

        return offensive_score, goals, assists, g_a

    def calculate_defensive_score(self, row, position):
        """
        防守评分
        - 黄牌 (CrdY)
        - 红牌 (CrdR)
        - 每90分钟防守数据
        """
        yellow = row.get(("Performance", "CrdY"), 0)
        red = row.get(("Performance", "CrdR"), 0)

        # 纪律评分 (越少越好)
        # 黄牌扣分: 每张-2分
        # 红牌扣分: 每张-10分
        discipline_score = max(0, 100 - yellow * 2 - red * 10)

        # 对于后卫，纪律更重要
        if position == "DF":
            discipline_weight = 0.6
        else:
            discipline_weight = 0.4

        defensive_score = discipline_score * discipline_weight + 50 * (1 - discipline_weight)

        return defensive_score, yellow, red

    def calculate_possession_score(self, row, position):
        """
        控球评分
        - 使用每90分钟数据作为代理
        - 进球+助攻的每90分钟效率
        """
        g90 = row.get(("Per 90 Minutes", "Gls"), 0)
        a90 = row.get(("Per 90 Minutes", "Ast"), 0)
        # 控球贡献评分 (基于进攻效率)
        if position == "FW":
            # 前锋: 更看重进球效率
            possession_score = min(g90 / 0.8 * 100, 100) * 0.6 + min(a90 / 0.4 * 100, 100) * 0.4
        elif position == "MF":
            # 中场: 平衡进球和助攻
            possession_score = min(g90 / 0.4 * 100, 100) * 0.4 + min(a90 / 0.5 * 100, 100) * 0.6
        else:
            # 后卫: 更看重助攻
            possession_score = min(a90 / 0.3 * 100, 100) * 0.7 + min(g90 / 0.2 * 100, 100) * 0.3

        return possession_score

    def calculate_efficiency_score(self, row, position):
        """
        效率评分
        - 每90分钟进球
        - 每90分钟助攻
        - 每90分钟G+A
        """
        g90 = row.get(("Per 90 Minutes", "Gls"), 0)
        a90 = row.get(("Per 90 Minutes", "Ast"), 0)
        ga90 = row.get(("Per 90 Minutes", "G+A"), 0)

        # 效率评分
        if position == "FW":
            # 前锋: 满分约0.8球/90分钟
            efficiency_score = min(g90 / 0.8 * 100, 100) * 0.6 + min(ga90 / 1.2 * 100, 100) * 0.4
        elif position == "MF":
            # 中场: 满分约0.5球+0.5助攻/90分钟
            efficiency_score = min(ga90 / 1.0 * 100, 100) * 0.5 + min(a90 / 0.5 * 100, 100) * 0.5
        else:
            # 后卫: 满分约0.3球+0.3助攻/90分钟
            efficiency_score = min(ga90 / 0.6 * 100, 100) * 0.6 + min(a90 / 0.3 * 100, 100) * 0.4

        return efficiency_score

    def calculate_composite_rating(self, row):
        """
        计算综合评分
        """
        # 获取位置
        position = row.get(("pos", ""), "MF")

        # 简化位置分类
        if isinstance(position, str):
            if "FW" in position or "FW,MF" in position:
                pos_group = "FW"
            elif "DF" in position or "DF,MF" in position:
                pos_group = "DF"
            elif "GK" in position:
                pos_group = "GK"
            else:
                pos_group = "MF"
        else:
            pos_group = "MF"

        # 计算各维度评分
        appearance_score, mp, starts, minutes, start_rate = self.calculate_appearance_score(row)
        offensive_score, goals, assists, g_a = self.calculate_offensive_score(row, pos_group)
        defensive_score, yellow, red = self.calculate_defensive_score(row, pos_group)
        possession_score = self.calculate_possession_score(row, pos_group)
        efficiency_score = self.calculate_efficiency_score(row, pos_group)

        # 获取权重
        weights = self.position_weights.get(pos_group, self.position_weights["MF"])

        # 计算加权总分
        composite_score = (
            appearance_score * weights["appearance"]
            + offensive_score * weights["offensive"]
            + defensive_score * weights["defensive"]
            + possession_score * weights["possession"]
            + efficiency_score * weights["efficiency"]
        )

        # 出场惩罚: 低出场球员减分
        # 少于10场比赛: 严重惩罚
        # 10-20场比赛: 中等惩罚
        # 20+场比赛: 轻微惩罚或无惩罚
        if mp < 10:
            appearance_penalty = 0.5  # 减半
        elif mp < 20:
            appearance_penalty = 0.7  # 减30%
        elif mp < 30:
            appearance_penalty = 0.9  # 减10%
        else:
            appearance_penalty = 1.0  # 无惩罚

        # 首发率惩罚
        if start_rate < 0.3:
            start_penalty = 0.8  # 减20%
        elif start_rate < 0.5:
            start_penalty = 0.9  # 减10%
        else:
            start_penalty = 1.0  # 无惩罚

        # 应用惩罚
        final_score = composite_score * appearance_penalty * start_penalty

        return {
            "player": row.name[3] if len(row.name) > 3 else "Unknown",
            "team": row.name[2] if len(row.name) > 2 else "Unknown",
            "league": row.name[0] if len(row.name) > 0 else "Unknown",
            "season": row.name[1] if len(row.name) > 1 else "Unknown",
            "position": position,
            "pos_group": pos_group,
            "composite_score": round(final_score, 1),
            "appearance_score": round(appearance_score, 1),
            "offensive_score": round(offensive_score, 1),
            "defensive_score": round(defensive_score, 1),
            "possession_score": round(possession_score, 1),
            "efficiency_score": round(efficiency_score, 1),
            "matches": mp,
            "starts": starts,
            "minutes": minutes,
            "start_rate": round(start_rate * 100, 1),
            "goals": goals,
            "assists": assists,
            "g_a": g_a,
            "yellow": yellow,
            "red": red,
            "appearance_penalty": appearance_penalty,
            "start_penalty": start_penalty,
        }


def main():
    settings = PlatformSettings.from_root()

    # 加载 FBref 数据
    fbref_path = settings.raw_root / "fbref" / "player_stats_big5_3seasons.parquet"
    df = pd.read_parquet(fbref_path)

    print("=" * 80)
    print("球员综合评分系统")
    print("=" * 80)
    print("\n数据范围: 2022-2023, 2023-2024, 2024-2025 赛季")
    print("覆盖联赛: 英超、西甲、法甲、意甲")
    print(f"总记录数: {len(df)}")

    # 初始化评分系统
    rating_system = PlayerRatingSystem()

    # 计算所有球员评分
    print("\n[1] 计算球员评分...")
    ratings = []

    for _, row in df.iterrows():
        try:
            rating = rating_system.calculate_composite_rating(row)
            ratings.append(rating)
        except Exception:
            continue

    ratings_df = pd.DataFrame(ratings)

    # 按评分排序
    ratings_df = ratings_df.sort_values("composite_score", ascending=False)

    # 保存结果
    output_path = settings.gold_root / "feature_store" / "player_ratings.parquet"
    ratings_df.to_parquet(output_path, index=False)
    print(f"  ✓ 已保存: {output_path}")

    # 显示 Top 50 球员
    print("\n[2] Top 50 球员综合评分:")
    print("-" * 80)
    print(
        f"{'排名':<4} {'球员':<25} {'位置':<5} {'评分':<6} "
        f"{'出场':<5} {'首发':<5} {'进球':<5} {'助攻':<5} {'G+A':<5}"
    )
    print("-" * 80)

    for i, (_, row) in enumerate(ratings_df.head(50).iterrows(), 1):
        print(
            f"{i:<4} {row['player']:<25} {row['position']:<5} {row['composite_score']:<6.1f} "
            f"{row['matches']:<5} {row['starts']:<5} {row['goals']:<5} "
            f"{row['assists']:<5} {row['g_a']:<5}"
        )

    # 按位置分组显示 Top 10
    print("\n[3] 各位置 Top 10:")
    print("-" * 80)

    for pos in ["FW", "MF", "DF", "GK"]:
        pos_players = ratings_df[ratings_df["pos_group"] == pos].head(10)

        if not pos_players.empty:
            print(
                f"\n  {pos} (前锋):"
                if pos == "FW"
                else f"\n  {pos} (中场):"
                if pos == "MF"
                else f"\n  {pos} (后卫):"
                if pos == "DF"
                else f"\n  {pos} (门将):"
            )

            for i, (_, row) in enumerate(pos_players.iterrows(), 1):
                print(
                    f"    {i}. {row['player']:<25} {row['composite_score']:<6.1f} "
                    f"({row['matches']}场, {row['goals']}球, {row['assists']}助攻)"
                )

    # 按联赛分组显示 Top 5
    print("\n[4] 各联赛 Top 5:")
    print("-" * 80)

    for league in ["ENG-Premier League", "ESP-La Liga", "FRA-Ligue 1", "ITA-Serie A"]:
        league_players = ratings_df[ratings_df["league"] == league].head(5)

        if not league_players.empty:
            print(f"\n  {league}:")
            for i, (_, row) in enumerate(league_players.iterrows(), 1):
                print(
                    f"    {i}. {row['player']:<25} {row['composite_score']:<6.1f} "
                    f"({row['position']}, {row['goals']}球, {row['assists']}助攻)"
                )

    # 评分分布统计
    print("\n[5] 评分分布统计:")
    print("-" * 80)

    # 过滤出场至少10场的球员
    qualified = ratings_df[ratings_df["matches"] >= 10]

    print(f"  出场至少10场的球员数: {len(qualified)}")
    print(f"  平均评分: {qualified['composite_score'].mean():.1f}")
    print(f"  评分中位数: {qualified['composite_score'].median():.1f}")
    print(f"  最高评分: {qualified['composite_score'].max():.1f}")
    print(f"  最低评分: {qualified['composite_score'].min():.1f}")

    # 评分等级分布
    print("\n  评分等级分布:")
    score_90_plus = len(qualified[qualified["composite_score"] >= 90])
    score_80_89 = len(
        qualified[(qualified["composite_score"] >= 80) & (qualified["composite_score"] < 90)]
    )
    score_70_79 = len(
        qualified[(qualified["composite_score"] >= 70) & (qualified["composite_score"] < 80)]
    )
    score_60_69 = len(
        qualified[(qualified["composite_score"] >= 60) & (qualified["composite_score"] < 70)]
    )
    score_below_60 = len(qualified[qualified["composite_score"] < 60])
    print(f"    90+ (世界级): {score_90_plus} 名")
    print(f"    80-89 (优秀): {score_80_89} 名")
    print(f"    70-79 (良好): {score_70_79} 名")
    print(f"    60-69 (平均): {score_60_69} 名")
    print(f"    <60 (低于平均): {score_below_60} 名")

    print("\n" + "=" * 80)
    print("评分说明:")
    print("- 综合评分考虑出场次数、首发率、进球、助攻、纪律等因素")
    print("- 低出场球员会相应减分 (出场<10场减50%, <20场减30%, <30场减10%)")
    print("- 低首发率球员会减分 (首发率<30%减20%, <50%减10%)")
    print("- 各位置权重不同: 前锋偏重进攻, 后卫偏重防守, 中场均衡")
    print("=" * 80)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
球员综合评分系统 v2
添加联赛系数调整
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd

from scoutlab.config import PlatformSettings


class PlayerRatingSystem:
    """
    球员综合评分系统 v2

    新增:
    - 联赛系数: 基于 UEFA 国家系数排名
    """

    def __init__(self):
        # UEFA 国家系数 (2024-2025)
        # 来源: football-coefficient.eu / UEFA.com
        self.uefa_coefficients = {
            "ENG-Premier League": 119.52,
            "ESP-La Liga": 92.998,
            "GER-Bundesliga": 92.904,
            "ITA-Serie A": 81.926,
            "FRA-Ligue 1": 83.5,
        }

        # 计算联赛系数 (英超=1.0)
        england_coeff = self.uefa_coefficients["ENG-Premier League"]
        self.league_coefficients = {}

        for league, coeff in self.uefa_coefficients.items():
            # 使用 ln(联赛积分) / ln(英超积分)
            self.league_coefficients[league] = np.log(coeff) / np.log(england_coeff)

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

    def get_league_coefficient(self, league):
        """获取联赛系数"""
        # 标准化联赛名称
        for key in self.league_coefficients:
            if key in league or league in key:
                return self.league_coefficients[key]

        # 默认返回 1.0
        return 1.0

    def calculate_appearance_score(self, row):
        """
        出场评分
        """
        mp = row.get(("Playing Time", "MP"), 0)
        starts = row.get(("Playing Time", "Starts"), 0)
        minutes = row.get(("Playing Time", "Min"), 0)

        start_rate = starts / mp if mp > 0 else 0

        mp_score = min(mp / 38 * 100, 100)
        start_rate_score = start_rate * 100
        minutes_score = min(minutes / 3420 * 100, 100)

        appearance_score = mp_score * 0.3 + start_rate_score * 0.3 + minutes_score * 0.4

        return appearance_score, mp, starts, minutes, start_rate

    def calculate_offensive_score(self, row, position):
        """
        进攻评分
        """
        goals = row.get(("Performance", "Gls"), 0)
        assists = row.get(("Performance", "Ast"), 0)
        g_a = row.get(("Performance", "G+A"), 0)
        pk = row.get(("Performance", "PK"), 0)

        npg = goals - pk

        if position == "FW":
            goal_weight = 0.50
            assist_weight = 0.25
            g_a_weight = 0.25
        elif position == "MF":
            goal_weight = 0.30
            assist_weight = 0.40
            g_a_weight = 0.30
        else:
            goal_weight = 0.20
            assist_weight = 0.40
            g_a_weight = 0.40

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

        offensive_score = (
            goal_score * goal_weight + assist_score * assist_weight + g_a_score * g_a_weight
        )

        return offensive_score, goals, assists, g_a

    def calculate_defensive_score(self, row, position):
        """
        防守评分
        """
        yellow = row.get(("Performance", "CrdY"), 0)
        red = row.get(("Performance", "CrdR"), 0)

        discipline_score = max(0, 100 - yellow * 2 - red * 10)

        if position == "DF":
            discipline_weight = 0.6
        else:
            discipline_weight = 0.4

        defensive_score = discipline_score * discipline_weight + 50 * (1 - discipline_weight)

        return defensive_score, yellow, red

    def calculate_possession_score(self, row, position):
        """
        控球评分
        """
        g90 = row.get(("Per 90 Minutes", "Gls"), 0)
        a90 = row.get(("Per 90 Minutes", "Ast"), 0)

        if position == "FW":
            possession_score = min(g90 / 0.8 * 100, 100) * 0.6 + min(a90 / 0.4 * 100, 100) * 0.4
        elif position == "MF":
            possession_score = min(g90 / 0.4 * 100, 100) * 0.4 + min(a90 / 0.5 * 100, 100) * 0.6
        else:
            possession_score = min(a90 / 0.3 * 100, 100) * 0.7 + min(g90 / 0.2 * 100, 100) * 0.3

        return possession_score

    def calculate_efficiency_score(self, row, position):
        """
        效率评分
        """
        g90 = row.get(("Per 90 Minutes", "Gls"), 0)
        a90 = row.get(("Per 90 Minutes", "Ast"), 0)
        ga90 = row.get(("Per 90 Minutes", "G+A"), 0)

        if position == "FW":
            efficiency_score = min(g90 / 0.8 * 100, 100) * 0.6 + min(ga90 / 1.2 * 100, 100) * 0.4
        elif position == "MF":
            efficiency_score = min(ga90 / 1.0 * 100, 100) * 0.5 + min(a90 / 0.5 * 100, 100) * 0.5
        else:
            efficiency_score = min(ga90 / 0.6 * 100, 100) * 0.6 + min(a90 / 0.3 * 100, 100) * 0.4

        return efficiency_score

    def calculate_composite_rating(self, row):
        """
        计算综合评分 (含联赛系数)
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

        # 获取联赛信息
        league = row.name[0] if len(row.name) > 0 else "Unknown"
        league_coeff = self.get_league_coefficient(league)

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

        # 出场惩罚
        if mp < 10:
            appearance_penalty = 0.5
        elif mp < 20:
            appearance_penalty = 0.7
        elif mp < 30:
            appearance_penalty = 0.9
        else:
            appearance_penalty = 1.0

        # 首发率惩罚
        if start_rate < 0.3:
            start_penalty = 0.8
        elif start_rate < 0.5:
            start_penalty = 0.9
        else:
            start_penalty = 1.0

        # 应用惩罚和联赛系数
        final_score = composite_score * appearance_penalty * start_penalty * league_coeff

        return {
            "player": row.name[3] if len(row.name) > 3 else "Unknown",
            "team": row.name[2] if len(row.name) > 2 else "Unknown",
            "league": league,
            "season": row.name[1] if len(row.name) > 1 else "Unknown",
            "position": position,
            "pos_group": pos_group,
            "composite_score": round(final_score, 1),
            "base_score": round(composite_score, 1),
            "league_coefficient": round(league_coeff, 3),
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

    print("=" * 90)
    print("球员综合评分系统 v2 (含联赛系数)")
    print("=" * 90)
    print("\n数据范围: 2022-2023, 2023-2024, 2024-2025 赛季")
    print("覆盖联赛: 英超、西甲、法甲、意甲")
    print(f"总记录数: {len(df)}")

    # 初始化评分系统
    rating_system = PlayerRatingSystem()

    # 显示联赛系数
    print("\n[0] 联赛系数 (基于 UEFA 国家系数):")
    print("-" * 90)
    print(f"  {'联赛':<25} {'UEFA系数':<15} {'联赛系数':<15}")
    print("-" * 90)
    for league, coeff in sorted(
        rating_system.league_coefficients.items(),
        key=lambda x: rating_system.uefa_coefficients.get(x[0], 0),
        reverse=True,
    ):
        uefa = rating_system.uefa_coefficients.get(league, 0)
        print(f"  {league:<25} {uefa:<15.2f} {coeff:<15.3f}")

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
    output_path = settings.gold_root / "feature_store" / "player_ratings_v2.parquet"
    ratings_df.to_parquet(output_path, index=False)
    print(f"  ✓ 已保存: {output_path}")

    # 显示 Top 50 球员
    print("\n[2] Top 50 球员综合评分 (含联赛系数):")
    print("-" * 90)
    print(
        f"{'排名':<4} {'球员':<25} {'联赛':<15} {'位置':<5} {'评分':<6} "
        f"{'基础分':<7} {'系数':<6} {'出场':<5} {'进球':<5} {'助攻':<5}"
    )
    print("-" * 90)

    for i, (_, row) in enumerate(ratings_df.head(50).iterrows(), 1):
        # 简化联赛名称
        league_short = (
            row["league"]
            .replace("ENG-", "")
            .replace("ESP-", "")
            .replace("FRA-", "")
            .replace("ITA-", "")
            .replace("GER-", "")
        )
        print(
            f"{i:<4} {row['player']:<25} {league_short:<15} {row['position']:<5} "
            f"{row['composite_score']:<6.1f} {row['base_score']:<7.1f} "
            f"{row['league_coefficient']:<6.3f} "
            f"{row['matches']:<5} {row['goals']:<5} {row['assists']:<5}"
        )

    # 按位置分组显示 Top 10
    print("\n[3] 各位置 Top 10 (含联赛系数):")
    print("-" * 90)

    for pos in ["FW", "MF", "DF", "GK"]:
        pos_players = ratings_df[ratings_df["pos_group"] == pos].head(10)

        if not pos_players.empty:
            pos_name = {"FW": "前锋", "MF": "中场", "DF": "后卫", "GK": "门将"}
            print(f"\n  {pos} ({pos_name[pos]}):")

            for i, (_, row) in enumerate(pos_players.iterrows(), 1):
                league_short = (
                    row["league"]
                    .replace("ENG-", "")
                    .replace("ESP-", "")
                    .replace("FRA-", "")
                    .replace("ITA-", "")
                    .replace("GER-", "")
                )
                print(
                    f"    {i}. {row['player']:<25} {league_short:<12} "
                    f"{row['composite_score']:<6.1f} ({row['matches']}场, "
                    f"{row['goals']}球, {row['assists']}助攻, "
                    f"系数{row['league_coefficient']:.3f})"
                )

    # 按联赛分组显示 Top 5
    print("\n[4] 各联赛 Top 5 (含联赛系数):")
    print("-" * 90)

    for league in ["ENG-Premier League", "ESP-La Liga", "FRA-Ligue 1", "ITA-Serie A"]:
        league_players = ratings_df[ratings_df["league"] == league].head(5)

        if not league_players.empty:
            league_short = (
                league.replace("ENG-", "")
                .replace("ESP-", "")
                .replace("FRA-", "")
                .replace("ITA-", "")
            )
            coeff = rating_system.get_league_coefficient(league)
            print(f"\n  {league_short} (系数: {coeff:.3f}):")
            for i, (_, row) in enumerate(league_players.iterrows(), 1):
                print(
                    f"    {i}. {row['player']:<25} {row['composite_score']:<6.1f} "
                    f"({row['position']}, {row['goals']}球, {row['assists']}助攻)"
                )

    # 评分分布统计
    print("\n[5] 评分分布统计:")
    print("-" * 90)

    qualified = ratings_df[ratings_df["matches"] >= 10]

    print(f"  出场至少10场的球员数: {len(qualified)}")
    print(f"  平均评分: {qualified['composite_score'].mean():.1f}")
    print(f"  评分中位数: {qualified['composite_score'].median():.1f}")
    print(f"  最高评分: {qualified['composite_score'].max():.1f}")
    print(f"  最低评分: {qualified['composite_score'].min():.1f}")

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

    # 联赛系数影响分析
    print("\n[6] 联赛系数影响分析:")
    print("-" * 90)

    for league in ["ENG-Premier League", "ESP-La Liga", "FRA-Ligue 1", "ITA-Serie A"]:
        league_players = ratings_df[ratings_df["league"] == league]
        qualified_league = league_players[league_players["matches"] >= 10]

        if not qualified_league.empty:
            avg_score = qualified_league["composite_score"].mean()
            avg_base = qualified_league["base_score"].mean()
            coeff = rating_system.get_league_coefficient(league)

            league_short = (
                league.replace("ENG-", "")
                .replace("ESP-", "")
                .replace("FRA-", "")
                .replace("ITA-", "")
            )
            print(
                f"  {league_short:<20} 系数: {coeff:.3f}  平均分: {avg_score:.1f}  "
                f"基础分: {avg_base:.1f}  球员数: {len(qualified_league)}"
            )

    print("\n" + "=" * 90)
    print("评分说明:")
    print("- 综合评分 = 基础分 × 出场惩罚 × 首发率惩罚 × 联赛系数")
    print("- 联赛系数基于 UEFA 国家系数，英超=1.0，其他联赛 ln(积分)/ln(英超积分)")
    print("- 低出场球员会相应减分 (出场<10场减50%, <20场减30%, <30场减10%)")
    print("- 低首发率球员会减分 (首发率<30%减20%, <50%减10%)")
    print("=" * 90)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
球员综合评分系统 v3
基于 ALGORITHM.md 新算法
- 百分位评分
- 细分位置
- 连续样本可靠性
- 去重处理
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd

from scoutfootball.config import PlatformSettings


class PlayerRatingSystemV3:
    """
    球员综合评分系统 v3
    基于 ALGORITHM.md 新算法
    """

    def __init__(self):
        # UEFA 国家系数 (2024-2025)
        self.uefa_coefficients = {
            "ENG-Premier League": 119.52,
            "ESP-La Liga": 93.00,
            "GER-Bundesliga": 92.90,
            "ITA-Serie A": 81.93,
            "FRA-Ligue 1": 83.50,
        }

        # 计算联赛系数
        england_coeff = self.uefa_coefficients["ENG-Premier League"]
        self.league_coefficients = {}
        for league, coeff in self.uefa_coefficients.items():
            self.league_coefficients[league] = np.log(coeff) / np.log(england_coeff)

        # 细分位置权重
        self.position_weights = {
            "ST": {
                "availability": 0.15,
                "attack": 0.38,
                "defense": 0.08,
                "possession": 0.14,
                "quality": 0.25,
            },
            "W": {
                "availability": 0.12,
                "attack": 0.30,
                "defense": 0.10,
                "possession": 0.25,
                "quality": 0.23,
            },
            "AM": {
                "availability": 0.12,
                "attack": 0.28,
                "defense": 0.10,
                "possession": 0.28,
                "quality": 0.22,
            },
            "CM": {
                "availability": 0.14,
                "attack": 0.16,
                "defense": 0.18,
                "possession": 0.32,
                "quality": 0.20,
            },
            "DM": {
                "availability": 0.14,
                "attack": 0.08,
                "defense": 0.30,
                "possession": 0.28,
                "quality": 0.20,
            },
            "FB": {
                "availability": 0.15,
                "attack": 0.10,
                "defense": 0.28,
                "possession": 0.27,
                "quality": 0.20,
            },
            "CB": {
                "availability": 0.16,
                "attack": 0.05,
                "defense": 0.42,
                "possession": 0.20,
                "quality": 0.17,
            },
            "GK": {
                "availability": 0.20,
                "attack": 0.05,
                "defense": 0.35,
                "possession": 0.20,
                "quality": 0.20,
            },
        }

        # 进攻权重
        self.attack_weights = {
            "ST": {"npxg_p90": 0.45, "assists_p90": 0.15, "g_a_volume": 0.40},
            "W": {"npxg_p90": 0.30, "assists_p90": 0.30, "g_a_volume": 0.40},
            "AM": {"npxg_p90": 0.20, "assists_p90": 0.40, "g_a_volume": 0.40},
            "CM": {"npxg_p90": 0.15, "assists_p90": 0.35, "g_a_volume": 0.50},
            "DM": {"npxg_p90": 0.10, "assists_p90": 0.25, "g_a_volume": 0.65},
            "FB": {"npxg_p90": 0.10, "assists_p90": 0.45, "g_a_volume": 0.45},
            "CB": {"npxg_p90": 0.20, "assists_p90": 0.20, "g_a_volume": 0.60},
            "GK": {"npxg_p90": 0.05, "assists_p90": 0.05, "g_a_volume": 0.90},
        }

    def map_position(self, pos_str):
        """映射细分位置"""
        if not isinstance(pos_str, str):
            return "CM"

        pos_str = pos_str.upper()

        if "GK" in pos_str:
            return "GK"
        elif "FW" in pos_str and "MF" in pos_str:
            return "W"
        elif "MF" in pos_str and "FW" in pos_str:
            return "AM"
        elif "DF" in pos_str and "MF" in pos_str:
            return "FB"
        elif "MF" in pos_str and "DF" in pos_str:
            return "DM"
        elif "FW" in pos_str:
            return "ST"
        elif "DF" in pos_str:
            return "CB"
        elif "MF" in pos_str:
            return "CM"
        else:
            return "CM"

    def calculate_percentile(self, values, value):
        """计算百分位数"""
        if len(values) == 0:
            return 50
        return (values < value).sum() / len(values) * 100

    def calculate_sample_reliability(self, minutes, starts, matches):
        """计算样本可靠性系数"""
        minutes_reliability = 0.5 + 0.5 * min(minutes / 1800, 1)
        start_rate = starts / max(matches, 1) if matches > 0 else 0
        starts_reliability = 0.85 + 0.15 * min(start_rate / 0.60, 1)
        return minutes_reliability * starts_reliability

    def calculate_availability_score(self, minutes, starts, matches, league_median_minutes):
        """计算出勤角色分"""
        minutes_share_score = (
            min(minutes / league_median_minutes, 1) * 100 if league_median_minutes > 0 else 50
        )
        start_rate_score = starts / max(matches, 1) * 100
        availability_score = min(matches / 38, 1) * 100
        role_stability_score = 50

        return (
            minutes_share_score * 0.45
            + start_rate_score * 0.25
            + availability_score * 0.20
            + role_stability_score * 0.10
        )

    def calculate_attack_score(self, npg_p90, assists_p90, g_a_volume, position, pos_data):
        """计算进攻贡献分 (百分位)"""
        npg_percentile = (
            self.calculate_percentile(pos_data["npg_p90"].values, npg_p90)
            if len(pos_data) > 0
            else 50
        )
        assists_percentile = (
            self.calculate_percentile(pos_data["assists_p90"].values, assists_p90)
            if len(pos_data) > 0
            else 50
        )
        volume_percentile = (
            self.calculate_percentile(pos_data["g_a_volume"].values, g_a_volume)
            if len(pos_data) > 0
            else 50
        )

        weights = self.attack_weights.get(position, self.attack_weights["CM"])

        return (
            npg_percentile * weights["npxg_p90"]
            + assists_percentile * weights["assists_p90"]
            + volume_percentile * weights["g_a_volume"]
        )

    def calculate_quality_score(self, npg_p90, assists_p90, position, pos_data):
        """计算效率质量分 (百分位)"""
        npg_percentile = (
            self.calculate_percentile(pos_data["npg_p90"].values, npg_p90)
            if len(pos_data) > 0
            else 50
        )
        assists_percentile = (
            self.calculate_percentile(pos_data["assists_p90"].values, assists_p90)
            if len(pos_data) > 0
            else 50
        )

        return npg_percentile * 0.35 + assists_percentile * 0.25 + 50 * 0.25 + 50 * 0.15


def main():
    settings = PlatformSettings.from_root()

    # 加载 FBref 数据
    fbref_path = settings.raw_root / "fbref" / "player_stats_big5_3seasons.parquet"
    df = pd.read_parquet(fbref_path)

    print("=" * 100)
    print("球员综合评分系统 v3 (基于 ALGORITHM.md)")
    print("=" * 100)
    print("\n数据范围: 2022-2023, 2023-2024, 2024-2025 赛季")
    print("覆盖联赛: 英超、西甲、法甲、意甲")
    print(f"总记录数: {len(df)}")

    # 初始化评分系统
    rating_system = PlayerRatingSystemV3()

    # 预处理: 计算每90分钟数据
    print("\n[1] 预处理数据...")

    # 提取列
    goals = df[("Performance", "Gls")].values.astype(float)
    assists = df[("Performance", "Ast")].values.astype(float)
    pk = df[("Performance", "PK")].values.astype(float)
    minutes = df[("Playing Time", "Min")].values.astype(float)
    starts = df[("Playing Time", "Starts")].values.astype(float)
    matches = df[("Playing Time", "MP")].values.astype(float)
    positions = df[("pos", "")].values
    leagues = df.index.get_level_values("league").astype(str).values
    seasons = df.index.get_level_values("season").values
    teams = df.index.get_level_values("team").values
    players = df.index.get_level_values("player").values

    # 计算衍生指标
    non_penalty_goals = goals - pk
    npg_p90 = non_penalty_goals / np.maximum(minutes, 1) * 90
    assists_p90 = assists / np.maximum(minutes, 1) * 90
    g_a_volume = non_penalty_goals + assists

    # 映射细分位置
    sub_positions = np.array([rating_system.map_position(p) for p in positions])

    # 创建结果DataFrame
    results = pd.DataFrame(
        {
            "player": players,
            "team": teams,
            "league": leagues,
            "season": seasons,
            "position": positions,
            "sub_position": sub_positions,
            "matches": matches,
            "starts": starts,
            "minutes": minutes,
            "goals": goals,
            "assists": assists,
            "pk": pk,
            "npg_p90": npg_p90,
            "assists_p90": assists_p90,
            "g_a_volume": g_a_volume,
        }
    )

    print("  ✓ 预处理完成")

    # 计算联赛中位数分钟数
    print("\n[2] 计算联赛系数...")
    league_median_minutes = {}
    for league in np.unique(leagues):
        league_mask = results["league"] == league
        league_median_minutes[league] = np.median(results.loc[league_mask, "minutes"].values)

    # 计算各维度分数
    print("\n[3] 计算球员评分...")

    availability_scores = []
    attack_scores = []
    quality_scores = []
    sample_reliabilities = []
    league_strength_factors = []
    base_scores = []
    overall_scores = []

    for i in range(len(results)):
        row = results.iloc[i]

        # 出勤角色分
        avail_score = rating_system.calculate_availability_score(
            row["minutes"],
            row["starts"],
            row["matches"],
            league_median_minutes.get(row["league"], 1800),
        )
        availability_scores.append(avail_score)

        # 进攻贡献分
        pos_mask = results["sub_position"] == row["sub_position"]
        pos_data = results[pos_mask]
        attack_score = rating_system.calculate_attack_score(
            row["npg_p90"], row["assists_p90"], row["g_a_volume"], row["sub_position"], pos_data
        )
        attack_scores.append(attack_score)

        # 效率质量分
        quality_score = rating_system.calculate_quality_score(
            row["npg_p90"], row["assists_p90"], row["sub_position"], pos_data
        )
        quality_scores.append(quality_score)

        # 样本可靠性
        reliability = rating_system.calculate_sample_reliability(
            row["minutes"], row["starts"], row["matches"]
        )
        sample_reliabilities.append(reliability)

        # 联赛系数
        league_coeff = rating_system.league_coefficients.get(row["league"], 1.0)
        league_strength_factors.append(league_coeff)

        # 计算基础分
        weights = rating_system.position_weights.get(
            row["sub_position"], rating_system.position_weights["CM"]
        )
        base_score = (
            avail_score * weights["availability"]
            + attack_score * weights["attack"]
            + 50 * weights["defense"]  # 缺失数据回退到50
            + 50 * weights["possession"]  # 缺失数据回退到50
            + quality_score * weights["quality"]
        )
        base_scores.append(base_score)

        # 最终评分
        overall_score = base_score * reliability * league_coeff
        overall_scores.append(overall_score)

    results["availability_score"] = availability_scores
    results["attack_score"] = attack_scores
    results["quality_score"] = quality_scores
    results["sample_reliability"] = sample_reliabilities
    results["league_strength_factor"] = league_strength_factors
    results["base_score"] = base_scores
    results["overall_score"] = overall_scores

    # 置信度
    results["score_confidence"] = "medium"
    results.loc[results["minutes"] < 900, "score_confidence"] = "low"
    results.loc[(results["minutes"] >= 1800) & (results["matches"] >= 20), "score_confidence"] = (
        "high"
    )

    # 去重
    print("\n[4] 去重处理...")
    print(f"  去重前: {len(results)} 条记录")

    results = results.sort_values("minutes", ascending=False)
    results = results.drop_duplicates(subset=["player", "season", "league"], keep="first")

    print(f"  去重后: {len(results)} 条记录")

    # 按评分排序
    results = results.sort_values("overall_score", ascending=False)

    # 保存结果
    output_path = settings.gold_root / "feature_store" / "player_ratings_v3.parquet"
    results.to_parquet(output_path, index=False)
    print(f"  ✓ 已保存: {output_path}")

    # 显示 Top 30 球员
    print("\n[5] Top 30 球员综合评分:")
    print("-" * 100)
    print(
        f"{'排名':<4} {'球员':<25} {'联赛':<12} {'位置':<4} {'评分':<6} "
        f"{'基础分':<7} {'可靠性':<7} {'系数':<6} {'出场':<5} {'进球':<5} {'助攻':<5}"
    )
    print("-" * 100)

    for i, (_, row) in enumerate(results.head(30).iterrows(), 1):
        league_short = (
            row["league"]
            .replace("ENG-", "")
            .replace("ESP-", "")
            .replace("FRA-", "")
            .replace("ITA-", "")
            .replace("GER-", "")
        )
        print(
            f"{i:<4} {row['player']:<25} {league_short:<12} {row['sub_position']:<4} "
            f"{row['overall_score']:<6.1f} {row['base_score']:<7.1f} "
            f"{row['sample_reliability']:<7.3f} {row['league_strength_factor']:<6.3f} "
            f"{row['matches']:<5} {row['goals']:<5} {row['assists']:<5}"
        )

    # 按细分位置显示 Top 10
    print("\n[6] 各位置 Top 10:")
    print("-" * 100)

    for pos in ["ST", "W", "AM", "CM", "DM", "FB", "CB", "GK"]:
        pos_players = results[results["sub_position"] == pos].head(10)

        if not pos_players.empty:
            pos_names = {
                "ST": "中锋",
                "W": "边锋",
                "AM": "前腰",
                "CM": "中前卫",
                "DM": "后腰",
                "FB": "边后卫",
                "CB": "中卫",
                "GK": "门将",
            }
            print(f"\n  {pos} ({pos_names[pos]}):")

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
                    f"{row['overall_score']:<6.1f} ({row['matches']}场, {row['goals']}球, "
                    f"{row['assists']}助攻, 置信度:{row['score_confidence']})"
                )

    # 按联赛显示 Top 5
    print("\n[7] 各联赛 Top 5:")
    print("-" * 100)

    for league in ["ENG-Premier League", "ESP-La Liga", "FRA-Ligue 1", "ITA-Serie A"]:
        league_players = results[results["league"] == league].head(5)

        if not league_players.empty:
            league_short = (
                league.replace("ENG-", "")
                .replace("ESP-", "")
                .replace("FRA-", "")
                .replace("ITA-", "")
            )
            coeff = rating_system.league_coefficients.get(league, 1.0)
            print(f"\n  {league_short} (系数: {coeff:.3f}):")
            for i, (_, row) in enumerate(league_players.iterrows(), 1):
                print(
                    f"    {i}. {row['player']:<25} {row['overall_score']:<6.1f} "
                    f"({row['sub_position']}, {row['goals']}球, {row['assists']}助攻)"
                )

    # 统计信息
    print("\n[8] 评分统计:")
    print("-" * 100)

    qualified = results[results["minutes"] >= 900]

    print(f"  总球员数: {len(results)}")
    print(f"  出场≥900分钟: {len(qualified)}")
    print(f"  平均评分: {qualified['overall_score'].mean():.1f}")
    print(f"  最高评分: {qualified['overall_score'].max():.1f}")
    print(f"  最低评分: {qualified['overall_score'].min():.1f}")

    print("\n  评分等级分布 (出场≥900分钟):")
    score_90_plus = len(qualified[qualified["overall_score"] >= 90])
    score_80_89 = len(
        qualified[(qualified["overall_score"] >= 80) & (qualified["overall_score"] < 90)]
    )
    score_70_79 = len(
        qualified[(qualified["overall_score"] >= 70) & (qualified["overall_score"] < 80)]
    )
    score_60_69 = len(
        qualified[(qualified["overall_score"] >= 60) & (qualified["overall_score"] < 70)]
    )
    score_50_59 = len(
        qualified[(qualified["overall_score"] >= 50) & (qualified["overall_score"] < 60)]
    )
    score_below_50 = len(qualified[qualified["overall_score"] < 50])
    print(f"    90+ (顶级): {score_90_plus} 名")
    print(f"    80-89 (优秀): {score_80_89} 名")
    print(f"    70-79 (良好): {score_70_79} 名")
    print(f"    60-69 (可用): {score_60_69} 名")
    print(f"    50-59 (平均): {score_50_59} 名")
    print(f"    <50 (低于平均): {score_below_50} 名")

    print("\n  置信度分布:")
    for conf in ["high", "medium", "low"]:
        count = len(results[results["score_confidence"] == conf])
        print(f"    {conf}: {count} 名")

    print("\n" + "=" * 100)
    print("算法说明:")
    print("- 使用百分位评分，同位置球员相对排名")
    print("- 样本可靠性系数: 分钟数和首发率的连续函数")
    print("- 联赛系数: 基于 UEFA 国家系数取对数比值")
    print("- 防守和控球分: 当前数据缺失，回退到50 (低置信度)")
    print("- 去重: 每个球员每个赛季只保留出场最多的记录")
    print("=" * 100)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

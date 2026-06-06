#!/usr/bin/env python3
"""
综合球员价值评估系统
实现多种高阶数据指标计算
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd

from scoutfootball.config import PlatformSettings


# ============================================================
# 1. Expected Threat (xT) 模型
# ============================================================
class ExpectedThreat:
    """
    Expected Threat (xT) 模型
    基于 Karun Singh 2018 年的实现

    xT 将球场划分为 16x12 的网格，每个格子有一个威胁值
    """

    def __init__(self):
        # xT 值矩阵 (16x12)
        # 来源: 基于历史数据的平均进球概率
        self.xT_values = np.array(
            [
                [
                    0.006383,
                    0.008089,
                    0.009944,
                    0.012216,
                    0.015594,
                    0.018385,
                    0.024089,
                    0.029327,
                    0.040973,
                    0.054177,
                    0.070223,
                    0.094417,
                ],
                [
                    0.007136,
                    0.009189,
                    0.011493,
                    0.014045,
                    0.017406,
                    0.020789,
                    0.027179,
                    0.033058,
                    0.045827,
                    0.060739,
                    0.076783,
                    0.101685,
                ],
                [
                    0.008007,
                    0.010324,
                    0.012989,
                    0.015988,
                    0.019618,
                    0.023320,
                    0.030286,
                    0.036731,
                    0.050459,
                    0.066732,
                    0.083681,
                    0.108654,
                ],
                [
                    0.009025,
                    0.011601,
                    0.014588,
                    0.017900,
                    0.021787,
                    0.025579,
                    0.032801,
                    0.039645,
                    0.054022,
                    0.071059,
                    0.088552,
                    0.112073,
                ],
                [
                    0.010216,
                    0.013026,
                    0.016252,
                    0.019771,
                    0.023756,
                    0.027605,
                    0.034860,
                    0.041619,
                    0.056051,
                    0.072869,
                    0.090042,
                    0.112829,
                ],
                [
                    0.011581,
                    0.014534,
                    0.017824,
                    0.021397,
                    0.025313,
                    0.029016,
                    0.035948,
                    0.042416,
                    0.056268,
                    0.072389,
                    0.088587,
                    0.110179,
                ],
                [
                    0.012836,
                    0.015816,
                    0.019043,
                    0.022590,
                    0.026351,
                    0.029778,
                    0.036193,
                    0.042020,
                    0.054807,
                    0.069861,
                    0.085211,
                    0.105484,
                ],
                [
                    0.013567,
                    0.016403,
                    0.019428,
                    0.022772,
                    0.026277,
                    0.029391,
                    0.035118,
                    0.040425,
                    0.051807,
                    0.065631,
                    0.079747,
                    0.098681,
                ],
                [
                    0.013290,
                    0.015839,
                    0.018498,
                    0.021467,
                    0.024586,
                    0.027333,
                    0.032342,
                    0.037091,
                    0.047052,
                    0.059056,
                    0.071094,
                    0.087837,
                ],
                [
                    0.011881,
                    0.014039,
                    0.016228,
                    0.018671,
                    0.021309,
                    0.023575,
                    0.027765,
                    0.031689,
                    0.039647,
                    0.049087,
                    0.058743,
                    0.072296,
                ],
                [
                    0.009543,
                    0.011263,
                    0.013027,
                    0.014983,
                    0.017061,
                    0.018856,
                    0.022074,
                    0.025146,
                    0.031192,
                    0.038289,
                    0.045567,
                    0.056032,
                ],
                [
                    0.006670,
                    0.007900,
                    0.009202,
                    0.010629,
                    0.012181,
                    0.013504,
                    0.015867,
                    0.018032,
                    0.022319,
                    0.027288,
                    0.032593,
                    0.039847,
                ],
                [
                    0.003826,
                    0.004579,
                    0.005374,
                    0.006273,
                    0.007243,
                    0.008103,
                    0.009555,
                    0.010919,
                    0.013539,
                    0.016576,
                    0.019828,
                    0.024145,
                ],
                [
                    0.001760,
                    0.002140,
                    0.002538,
                    0.002999,
                    0.003500,
                    0.003944,
                    0.004683,
                    0.005395,
                    0.006744,
                    0.008329,
                    0.010080,
                    0.012290,
                ],
                [
                    0.000638,
                    0.000797,
                    0.000966,
                    0.001162,
                    0.001379,
                    0.001571,
                    0.001879,
                    0.002187,
                    0.002740,
                    0.003395,
                    0.004160,
                    0.005112,
                ],
                [
                    0.000182,
                    0.000234,
                    0.000292,
                    0.000359,
                    0.000433,
                    0.000500,
                    0.000604,
                    0.000712,
                    0.000905,
                    0.001142,
                    0.001426,
                    0.001787,
                ],
            ]
        )

    def get_zone(self, x, y):
        """获取球场坐标对应的网格区域"""
        # 标准化坐标到 0-100
        x = max(0, min(100, x))
        y = max(0, min(100, y))

        # 映射到网格索引
        x_idx = min(int(x / 100 * 16), 15)
        y_idx = min(int(y / 100 * 12), 11)

        return x_idx, y_idx

    def get_xt_value(self, x, y):
        """获取某位置的 xT 值"""
        x_idx, y_idx = self.get_zone(x, y)
        return self.xT_values[x_idx][y_idx]

    def calculate_xt_added(self, start_x, start_y, end_x, end_y):
        """计算动作的 xT 增量"""
        start_xt = self.get_xt_value(start_x, start_y)
        end_xt = self.get_xt_value(end_x, end_y)
        return end_xt - start_xt


# ============================================================
# 2. 球员综合价值评估指标
# ============================================================
class PlayerValueMetrics:
    """
    综合球员价值评估
    包含多个维度的指标计算
    """

    def __init__(self):
        self.xt_model = ExpectedThreat()

    def calculate_offensive_metrics(self, player_events):
        """
        计算进攻指标

        输入: 球员的事件数据 (DataFrame)
        输出: 进攻指标字典
        """
        metrics = {}

        # 计算比赛分钟数 (假设每场比赛 90 分钟)
        unique_matches = (
            player_events["match_id"].nunique() if "match_id" in player_events.columns else 1
        )
        total_minutes = unique_matches * 90

        if total_minutes == 0:
            return metrics

        # 射门相关
        shots = player_events[player_events["event_type"] == "Shot"]
        if len(shots) > 0:
            metrics["shots_per_90"] = len(shots) * 90 / total_minutes

            # xG 相关 (如果有 shot_statsbomb_xg 列)
            if "shot_statsbomb_xg" in shots.columns:
                metrics["xG_total"] = shots["shot_statsbomb_xg"].sum()
                metrics["xG_per_90"] = metrics["xG_total"] * 90 / total_minutes

                # 实际进球
                goals = shots[shots["shot_outcome_name"] == "Goal"]
                metrics["goals"] = len(goals)
                metrics["goals_per_90"] = metrics["goals"] * 90 / total_minutes

                # 进球超额 (G - xG)
                metrics["finishing_delta"] = metrics["goals"] - metrics["xG_total"]

        # 传球相关
        passes = player_events[player_events["event_type"] == "Pass"]
        if len(passes) > 0:
            metrics["passes_per_90"] = len(passes) * 90 / total_minutes

            # 完成率
            completed = passes[passes["pass_outcome_name"].isna()]
            metrics["pass_completion_rate"] = len(completed) / len(passes)

            # 前向传球
            if "pass_end_location_x" in passes.columns:
                forward_passes = passes[passes["pass_end_location_x"] > passes["location_x"]]
                metrics["forward_pass_rate"] = len(forward_passes) / len(passes)

        # xT 相关
        if "location_x" in player_events.columns and "pass_end_location_x" in player_events.columns:
            xt_values = []
            for _, event in passes.iterrows():
                if pd.notna(event.get("location_x")) and pd.notna(event.get("pass_end_location_x")):
                    xt = self.xt_model.calculate_xt_added(
                        event["location_x"],
                        event["location_y"],
                        event["pass_end_location_x"],
                        event.get("pass_end_location_y", 50),
                    )
                    xt_values.append(xt)

            if xt_values:
                metrics["xT_total"] = sum(xt_values)
                metrics["xT_per_90"] = metrics["xT_total"] * 90 / total_minutes

        return metrics

    def calculate_defensive_metrics(self, player_events):
        """
        计算防守指标
        """
        metrics = {}

        # 计算比赛分钟数
        unique_matches = (
            player_events["match_id"].nunique() if "match_id" in player_events.columns else 1
        )
        total_minutes = unique_matches * 90

        if total_minutes == 0:
            return metrics

        # 铲球
        tackles = player_events[player_events["event_type"] == "Tackle"]
        metrics["tackles_per_90"] = len(tackles) * 90 / total_minutes

        # 拦截
        interceptions = player_events[player_events["event_type"] == "Interception"]
        metrics["interceptions_per_90"] = len(interceptions) * 90 / total_minutes

        # 封堵
        blocks = player_events[player_events["event_type"] == "Block"]
        metrics["blocks_per_90"] = len(blocks) * 90 / total_minutes

        # 对抗
        duels = player_events[player_events["event_type"] == "Duel"]
        if len(duels) > 0:
            won_duels = duels[duels["duel_outcome_name"].isin(["Won", "Success In Play"])]
            metrics["duel_win_rate"] = len(won_duels) / len(duels)
            metrics["duels_per_90"] = len(duels) * 90 / total_minutes

        return metrics

    def calculate_possession_metrics(self, player_events):
        """
        计算控球指标
        """
        metrics = {}

        # 计算比赛分钟数
        unique_matches = (
            player_events["match_id"].nunique() if "match_id" in player_events.columns else 1
        )
        total_minutes = unique_matches * 90

        if total_minutes == 0:
            return metrics

        # 触球
        touches = player_events[
            player_events["event_type"].isin(["Ball Receipt", "Carry", "Pass", "Shot", "Dribble"])
        ]
        metrics["touches_per_90"] = len(touches) * 90 / total_minutes

        # 带球推进
        carries = player_events[player_events["event_type"] == "Carry"]
        if len(carries) > 0 and "carry_end_location_x" in carries.columns:
            progressive_carries = carries[
                carries["carry_end_location_x"] - carries["location_x"] > 10
            ]
            metrics["progressive_carries_per_90"] = len(progressive_carries) * 90 / total_minutes

        # 进入危险区域
        if "location_x" in player_events.columns:
            final_third_entries = player_events[player_events["location_x"] > 66.7]
            metrics["final_third_touches_per_90"] = len(final_third_entries) * 90 / total_minutes

            penalty_area_entries = player_events[
                (player_events["location_x"] > 83.5)
                & (player_events["location_y"].between(21.1, 78.9))
            ]
            metrics["penalty_area_touches_per_90"] = len(penalty_area_entries) * 90 / total_minutes

        return metrics

    def calculate_composite_score(self, metrics, position_group):
        """
        计算综合评分 (0-100)

        根据位置不同，权重不同
        """
        # 位置权重
        weights = {
            "fwd": {
                "goals_per_90": 0.25,
                "xG_per_90": 0.15,
                "finishing_delta": 0.10,
                "shots_per_90": 0.10,
                "xT_per_90": 0.15,
                "touches_per_90": 0.05,
                "passes_per_90": 0.05,
                "pass_completion_rate": 0.05,
                "duel_win_rate": 0.05,
                "tackles_per_90": 0.05,
            },
            "mid": {
                "xT_per_90": 0.20,
                "passes_per_90": 0.15,
                "pass_completion_rate": 0.15,
                "forward_pass_rate": 0.10,
                "touches_per_90": 0.10,
                "progressive_carries_per_90": 0.10,
                "tackles_per_90": 0.05,
                "interceptions_per_90": 0.05,
                "duel_win_rate": 0.05,
                "goals_per_90": 0.05,
            },
            "def": {
                "tackles_per_90": 0.20,
                "interceptions_per_90": 0.20,
                "blocks_per_90": 0.10,
                "duel_win_rate": 0.15,
                "duels_per_90": 0.10,
                "pass_completion_rate": 0.10,
                "passes_per_90": 0.05,
                "xT_per_90": 0.05,
                "progressive_carries_per_90": 0.05,
            },
            "gk": {
                # 门将指标需要特殊处理
                "pass_completion_rate": 0.30,
                "passes_per_90": 0.20,
                "tackles_per_90": 0.20,
                "interceptions_per_90": 0.15,
                "duel_win_rate": 0.15,
            },
        }

        position_weights = weights.get(position_group, weights["mid"])

        # 计算加权分数
        total_score = 0
        total_weight = 0

        for metric, weight in position_weights.items():
            if metric in metrics and metrics[metric] is not None:
                # 简单归一化 (实际应该用百分位数)
                normalized = self._normalize_metric(metrics[metric], metric)
                total_score += normalized * weight
                total_weight += weight

        if total_weight > 0:
            return total_score / total_weight * 100
        return 50  # 默认中位数

    def _normalize_metric(self, value, metric_name):
        """
        简单的指标归一化
        实际应该使用百分位数或 z-score
        """
        # 这里用简单的 sigmoid 函数
        # 实际应该用真实数据的分布
        if value is None or pd.isna(value):
            return 0.5

        # 对于比率类指标
        if "rate" in metric_name or "completion" in metric_name:
            return min(1, max(0, value))

        # 对于计数类指标 (per 90)
        if "per_90" in metric_name:
            # 用 sigmoid 函数
            return 1 / (1 + np.exp(-value + 2))

        return 0.5


# ============================================================
# 3. 比赛价值评估
# ============================================================
class MatchValueAnalyzer:
    """
    比赛价值分析
    评估球员在特定比赛中的表现
    """

    def __init__(self):
        self.xt_model = ExpectedThreat()

    def analyze_match_performance(self, player_events, match_context):
        """
        分析球员在单场比赛中的表现

        参数:
        - player_events: 球员在该场比赛的事件数据
        - match_context: 比赛背景 (对手强度、比赛重要性等)
        """
        analysis = {}

        # 基础统计
        analysis["minutes_played"] = player_events["minutes"].sum()
        analysis["total_events"] = len(player_events)

        # 进攻贡献
        shots = player_events[player_events["event_type"] == "Shot"]
        analysis["shots"] = len(shots)

        if "shot_statsbomb_xg" in shots.columns:
            analysis["xG"] = shots["shot_statsbomb_xg"].sum()

        # 传球贡献
        passes = player_events[player_events["event_type"] == "Pass"]
        analysis["passes"] = len(passes)
        analysis["completed_passes"] = len(passes[passes["pass_outcome_name"].isna()])

        # xT 贡献
        if "location_x" in player_events.columns:
            xt_total = 0
            for _, event in passes.iterrows():
                if pd.notna(event.get("location_x")) and pd.notna(event.get("pass_end_location_x")):
                    xt = self.xt_model.calculate_xt_added(
                        event["location_x"],
                        event["location_y"],
                        event["pass_end_location_x"],
                        event.get("pass_end_location_y", 50),
                    )
                    xt_total += xt
            analysis["xT_added"] = xt_total

        # 防守贡献
        analysis["tackles"] = len(player_events[player_events["event_type"] == "Tackle"])
        analysis["interceptions"] = len(
            player_events[player_events["event_type"] == "Interception"]
        )

        # 根据比赛背景调整评分
        context_multiplier = self._calculate_context_multiplier(match_context)
        analysis["context_multiplier"] = context_multiplier

        return analysis

    def _calculate_context_multiplier(self, context):
        """
        根据比赛背景计算调整系数

        考虑因素:
        - 对手强度 (Elo 差)
        - 比赛重要性
        - 主客场
        """
        multiplier = 1.0

        # 对手强度
        if "opponent_elo" in context:
            elo_diff = context.get("elo_diff", 0)
            # 对阵强队表现好 -> 更高价值
            if elo_diff < -100:
                multiplier *= 1.2
            elif elo_diff > 100:
                multiplier *= 0.8

        # 比赛重要性
        match_importance = context.get("importance", "normal")
        if match_importance == "high":
            multiplier *= 1.15
        elif match_importance == "critical":
            multiplier *= 1.3

        return multiplier


# ============================================================
# 4. 测试和演示
# ============================================================
def main():
    settings = PlatformSettings.from_root()

    print("=" * 60)
    print("球员价值评估系统 - 高阶指标计算")
    print("=" * 60)

    # 加载 StatsBomb 事件数据
    events_path = settings.raw_root / "statsbomb_open" / "events_sample.parquet"
    events = pd.read_parquet(events_path)
    print(f"\n[1] 加载事件数据: {len(events)} 条记录")

    # 初始化指标计算器
    metrics_calc = PlayerValueMetrics()

    # 按球员分组计算指标
    print("\n[2] 计算球员指标...")

    player_metrics = []
    for player_id in events["player_id"].dropna().unique()[:10]:  # 先测试前10个球员
        player_events = events[events["player_id"] == player_id]

        # 计算各项指标
        offensive = metrics_calc.calculate_offensive_metrics(player_events)
        defensive = metrics_calc.calculate_defensive_metrics(player_events)
        possession = metrics_calc.calculate_possession_metrics(player_events)

        # 合并指标
        all_metrics = {**offensive, **defensive, **possession}
        all_metrics["player_id"] = player_id

        # 获取球员名称
        if "player_name" in player_events.columns:
            all_metrics["player_name"] = player_events["player_name"].iloc[0]

        # 计算综合评分 (假设为中场)
        all_metrics["composite_score"] = metrics_calc.calculate_composite_score(all_metrics, "mid")

        player_metrics.append(all_metrics)

    # 展示结果
    metrics_df = pd.DataFrame(player_metrics)

    print("\n[3] 球员价值评估结果:")
    print("-" * 60)

    for _, player in metrics_df.iterrows():
        print(f"\n球员: {player.get('player_name', player['player_id'])}")
        print(f"  综合评分: {player.get('composite_score', 0):.1f}/100")

        if "xG_total" in player and player["xG_total"] is not None:
            print(f"  xG: {player.get('xG_total', 0):.2f}")
        if "xT_total" in player and player["xT_total"] is not None:
            print(f"  xT: {player.get('xT_total', 0):.3f}")
        if "pass_completion_rate" in player and player["pass_completion_rate"] is not None:
            print(f"  传球完成率: {player.get('pass_completion_rate', 0):.1%}")
        if "duel_win_rate" in player and player["duel_win_rate"] is not None:
            print(f"  对抗胜率: {player.get('duel_win_rate', 0):.1%}")

    # xT 模型演示
    print("\n[4] Expected Threat (xT) 模型演示:")
    print("-" * 60)

    xt_model = ExpectedThreat()

    # 示例: 从后场传球到前场
    scenarios = [
        ("后场传球", 20, 50, 40, 50),
        ("中场推进", 40, 50, 60, 50),
        ("前场直塞", 60, 50, 80, 50),
        ("禁区前沿", 80, 50, 90, 50),
        ("横传转移", 50, 20, 50, 80),
    ]

    for name, start_x, start_y, end_x, end_y in scenarios:
        xt_added = xt_model.calculate_xt_added(start_x, start_y, end_x, end_y)
        print(f"  {name}: ({start_x},{start_y}) → ({end_x},{end_y}), xT = {xt_added:+.4f}")

    # 保存结果
    output_path = settings.gold_root / "feature_store" / "player_value_metrics.parquet"
    metrics_df.to_parquet(output_path, index=False)
    print(f"\n[5] 已保存: {output_path}")

    print("\n" + "=" * 60)
    print("高阶指标计算完成!")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

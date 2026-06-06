#!/usr/bin/env python3
"""
球员评分权重优化器 - 带实时绘图版本
用球队实际战绩作为 ground truth，优化评分参数使球队平均分与积分相关性最大化。
支持实时显示训练进度和图表。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution
from scipy.stats import spearmanr, pearsonr

from scoutfootball.viz.training_monitor import (
    TrainingMonitor,
    create_objective_wrapper,
)


def load_fbref_data(settings):
    """加载 FBref 球员数据并预处理。"""
    fbref_path = settings.raw_root / "fbref" / "player_stats_big5_3seasons.parquet"
    df = pd.read_parquet(fbref_path)

    goals = df[("Performance", "Gls")].values.astype(float)
    assists_col = df[("Performance", "Ast")].values.astype(float)
    pk = df[("Performance", "PK")].values.astype(float)
    minutes = df[("Playing Time", "Min")].values.astype(float)
    starts = df[("Playing Time", "Starts")].values.astype(float)
    matches = df[("Playing Time", "MP")].values.astype(float)
    positions = df[("pos", "")].values
    leagues = df.index.get_level_values("league").astype(str).values
    seasons = df.index.get_level_values("season").values
    teams = df.index.get_level_values("team").astype(str).values
    players = df.index.get_level_values("player").astype(str).values

    non_penalty_goals = goals - pk
    npg_p90 = non_penalty_goals / np.maximum(minutes, 1) * 90
    assists_p90 = assists_col / np.maximum(minutes, 1) * 90
    g_a_volume = non_penalty_goals + assists_col

    pos_map_fn = _make_pos_mapper()
    sub_positions = np.array([pos_map_fn(p) for p in positions])

    result = pd.DataFrame({
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
        "assists": assists_col,
        "pk": pk,
        "npg_p90": npg_p90,
        "assists_p90": assists_p90,
        "g_a_volume": g_a_volume,
    })

    # Deduplicate
    result = result.sort_values("minutes", ascending=False)
    result = result.drop_duplicates(subset=["player", "season", "league"], keep="first")
    return result


def load_team_standings(settings):
    """从 Football-Data 计算球队赛季积分。"""
    fd_path = settings.raw_root / "football_data" / "combined_results.parquet"
    matches = pd.read_parquet(fd_path)

    standings = []
    for _, row in matches.iterrows():
        season = str(row.get("season", ""))
        league = str(row.get("league", ""))
        home = str(row["HomeTeam"])
        away = str(row["AwayTeam"])
        hg = float(row["FTHG"])
        ag = float(row["FTAG"])

        # Home result
        if hg > ag:
            h_pts, a_pts = 3, 0
        elif hg == ag:
            h_pts, a_pts = 1, 1
        else:
            h_pts, a_pts = 0, 3

        standings.append({"team": home, "league": league, "season": season,
                          "goals_for": hg, "goals_against": ag, "points": h_pts})
        standings.append({"team": away, "league": league, "season": season,
                          "goals_for": ag, "goals_against": hg, "points": a_pts})

    df = pd.DataFrame(standings)
    team_season = df.groupby(["team", "league", "season"]).agg(
        total_points=("points", "sum"),
        goals_for=("goals_for", "sum"),
        goals_against=("goals_against", "sum"),
        matches=("points", "count"),
    ).reset_index()
    team_season["goal_diff"] = team_season["goals_for"] - team_season["goals_against"]
    return team_season


def _make_pos_mapper():
    """Position string -> sub_position group."""
    def mapper(pos_str):
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
    return mapper


# ── Parameterized rating function ──────────────────────────────────────────

POSITIONS = ["ST", "W", "AM", "CM", "DM", "FB", "CB", "GK"]
DIMENSIONS = ["availability", "attack", "defense", "possession", "quality"]
ATTACK_METRICS = ["npxg_p90", "assists_p90", "g_a_volume"]


def params_to_weights(params):
    """Convert flat parameter vector to structured weight dicts."""
    idx = 0

    # Position weights (8×5)
    pw = {}
    for pos in POSITIONS:
        raw = params[idx:idx + 5]
        norm = _softmax(raw)
        pw[pos] = dict(zip(DIMENSIONS, norm))
        idx += 5

    # Attack weights (8×3)
    aw = {}
    for pos in POSITIONS:
        raw = params[idx:idx + 3]
        norm = _softmax(raw)
        aw[pos] = dict(zip(ATTACK_METRICS, norm))
        idx += 3

    # Availability sub-weights (4)
    avail_raw = params[idx:idx + 4]
    avail_sw = _softmax(avail_raw)
    idx += 4

    # Quality sub-weights (4)
    qual_raw = params[idx:idx + 4]
    qual_sw = _softmax(qual_raw)
    idx += 4

    # League log scale
    league_log_scale = params[idx]
    idx += 1

    # Reliability params
    rel_minutes_ref = 900 + params[idx] * 1800
    idx += 1
    rel_starts_ref = 0.3 + params[idx] * 0.4
    idx += 1

    return {
        "position_weights": pw,
        "attack_weights": aw,
        "avail_sub_weights": avail_sw,
        "qual_sub_weights": qual_sw,
        "league_log_scale": league_log_scale,
        "rel_minutes_ref": rel_minutes_ref,
        "rel_starts_ref": rel_starts_ref,
    }


def _softmax(x):
    """Softmax normalization to sum to 1."""
    e = np.exp(x - np.max(x))
    return e / e.sum()


def compute_ratings(player_df, weights):
    """Compute player ratings with given weights."""
    pw = weights["position_weights"]
    aw = weights["attack_weights"]
    avail_sw = weights["avail_sub_weights"]
    qual_sw = weights["qual_sub_weights"]
    league_log_scale = weights["league_log_scale"]
    rel_min_ref = weights["rel_minutes_ref"]
    rel_starts_ref = weights["rel_starts_ref"]

    # UEFA coefficients
    uefa = {
        "ENG-Premier League": 119.52,
        "ESP-La Liga": 93.00,
        "GER-Bundesliga": 92.90,
        "ITA-Serie A": 81.93,
        "FRA-Ligue 1": 83.50,
    }
    eng_coeff = uefa["ENG-Premier League"]
    league_coeff = {k: (np.log(v) / np.log(eng_coeff)) ** league_log_scale for k, v in uefa.items()}

    league_med_min = player_df.groupby("league")["minutes"].median().to_dict()
    pos_groups = player_df.groupby("sub_position")

    ratings = []
    for _, row in player_df.iterrows():
        pos = row["sub_position"]
        pos_data = pos_groups.get_group(pos) if pos in pos_groups.groups else player_df

        # Availability
        med_min = league_med_min.get(row["league"], 1800)
        min_share = min(row["minutes"] / max(med_min, 1), 1) * 100
        start_rate_score = row["starts"] / max(row["matches"], 1) * 100
        avail_pct = min(row["matches"] / 38, 1) * 100
        role_stab = 50.0
        availability = (min_share * avail_sw[0] + start_rate_score * avail_sw[1]
                        + avail_pct * avail_sw[2] + role_stab * avail_sw[3])

        # Attack (percentile-based)
        npg_pct = _percentile(pos_data["npg_p90"].values, row["npg_p90"])
        ast_pct = _percentile(pos_data["assists_p90"].values, row["assists_p90"])
        vol_pct = _percentile(pos_data["g_a_volume"].values, row["g_a_volume"])

        pos_aw = aw.get(pos, aw.get("CM"))
        attack = npg_pct * pos_aw["npxg_p90"] + ast_pct * pos_aw["assists_p90"] + vol_pct * pos_aw["g_a_volume"]

        # Defense & possession — placeholder at 50 (no data)
        defense = 50.0
        possession = 50.0

        # Quality (percentile-based)
        q_npg = _percentile(pos_data["npg_p90"].values, row["npg_p90"])
        q_ast = _percentile(pos_data["assists_p90"].values, row["assists_p90"])
        quality = q_npg * qual_sw[0] + q_ast * qual_sw[1] + 50 * qual_sw[2] + 50 * qual_sw[3]

        # Position weights
        pos_pw = pw.get(pos, pw.get("CM"))
        base = (availability * pos_pw["availability"] + attack * pos_pw["attack"]
                + defense * pos_pw["defense"] + possession * pos_pw["possession"]
                + quality * pos_pw["quality"])

        # Reliability
        min_rel = 0.5 + 0.5 * min(row["minutes"] / rel_min_ref, 1)
        sr = row["starts"] / max(row["matches"], 1) if row["matches"] > 0 else 0
        start_rel = 0.85 + 0.15 * min(sr / rel_starts_ref, 1)
        reliability = min_rel * start_rel

        # League coefficient
        lcoeff = league_coeff.get(row["league"], 1.0)

        overall = base * reliability * lcoeff
        ratings.append(overall)

    return np.array(ratings)


def _percentile(values, value):
    if len(values) == 0:
        return 50.0
    return (values < value).sum() / len(values) * 100


def compute_team_ratings(player_df, ratings):
    """Compute per-team average rating for each season."""
    df = player_df[["team", "league", "season", "minutes"]].copy()
    df["rating"] = ratings

    # Weighted average by minutes (starters matter more)
    def weighted_avg(group):
        w = group["minutes"].clip(lower=1)
        return np.average(group["rating"], weights=w)

    team_ratings = df.groupby(["team", "league", "season"]).apply(
        weighted_avg, include_groups=False
    ).reset_index(name="avg_rating")
    return team_ratings


def objective(params, player_df, team_standings, verbose=False, monitor=None):
    """
    Negative Spearman correlation between team avg rating and actual points.
    (We minimize, so negative correlation = maximize positive correlation.)
    """
    weights = params_to_weights(params)
    ratings = compute_ratings(player_df, weights)
    team_ratings = compute_team_ratings(player_df, ratings)

    # Merge with actual standings
    merged = team_ratings.merge(
        team_standings,
        on=["team", "league", "season"],
        how="inner",
    )

    if len(merged) < 10:
        return 1.0  # bad

    spearman_corr, _ = spearmanr(merged["avg_rating"], merged["total_points"])
    pearson_corr, _ = pearsonr(merged["avg_rating"], merged["total_points"])

    if verbose:
        print(f"  Spearman: {spearman_corr:.4f}, Pearson: {pearson_corr:.4f}, N={len(merged)}")

    # Record to monitor if provided
    if monitor is not None:
        iteration = len(monitor.get_history()) + 1
        monitor.record(
            iteration=iteration,
            spearman=spearman_corr,
            pearson=pearson_corr,
            n_teams=len(merged),
            loss=-spearman_corr,
        )
        # Print progress every 10 iterations
        if iteration % 10 == 0:
            monitor.print_progress(iteration, spearman_corr, pearson_corr)
            if monitor.fig is not None:
                monitor.update_matplotlib()

    # Minimize negative correlation
    return -spearman_corr


def main():
    parser = argparse.ArgumentParser(description="球员评分权重优化器（带实时绘图）")
    parser.add_argument("--maxiter", type=int, default=50, help="最大迭代次数")
    parser.add_argument("--popsize", type=int, default=15, help="种群大小")
    parser.add_argument("--no-plot", action="store_true", help="禁用实时绘图")
    parser.add_argument("--save-history", type=str, help="保存训练历史到 CSV 文件")
    args = parser.parse_args()

    from scoutfootball.config import PlatformSettings
    settings = PlatformSettings.from_root()

    print("=" * 80)
    print("球员评分权重优化器 - 实时绘图版")
    print("目标: 最大化球队平均评分与实际积分的 Spearman 相关性")
    print("=" * 80)

    # Load data
    print("\n[1] 加载数据...")
    player_df = load_fbref_data(settings)
    team_standings = load_team_standings(settings)
    print(f"  球员记录: {len(player_df)}")
    print(f"  球队赛季: {len(team_standings)}")

    # Baseline with default weights
    print("\n[2] 计算基线相关性 (当前 v3 权重)...")
    default_params = _get_default_params()
    baseline_loss = objective(default_params, player_df, team_standings, verbose=True)
    baseline_spearman = -baseline_loss
    print(f"  基线 Spearman: {baseline_spearman:.4f}")

    # Create training monitor
    print("\n[3] 初始化训练监控...")
    monitor = TrainingMonitor(baseline_spearman=baseline_spearman, baseline_pearson=0.0)

    # Initialize matplotlib if not disabled
    if not args.no_plot:
        try:
            monitor.init_matplotlib_figure()
            print("  实时图表已开启 (关闭 matplotlib 窗口可继续训练)")
        except Exception as e:
            print(f"  警告: 无法启动实时图表 ({e})，将使用文本模式")
            print("  提示: 使用 --no-plot 参数可禁用图表功能")

    # Optimize with monitoring
    print("\n[4] 开始优化 (differential evolution)...")
    print("  提示: 每 10 次迭代显示一次进度")
    print("-" * 80)

    bounds = [(-3, 3)] * 75  # 75 parameters

    result = differential_evolution(
        objective,
        bounds=bounds,
        args=(player_df, team_standings, False, monitor),  # verbose=False, monitor=monitor
        maxiter=args.maxiter,
        popsize=args.popsize,
        tol=1e-4,
        seed=42,
        disp=True,
        workers=1,
    )

    print("-" * 80)
    print(f"\n优化完成!")

    # Close matplotlib
    if monitor.fig is not None:
        monitor.close_matplotlib()

    # Print final report
    print("\n" + monitor.generate_text_report())

    # Extract optimized weights
    opt_weights = params_to_weights(result.x)

    # Show optimized position weights
    print("\n[5] 优化后的权重:")
    print("-" * 80)
    print(f"{'位置':<5} {'出勤':>6} {'进攻':>6} {'防守':>6} {'控球':>6} {'质量':>6}")
    print("-" * 80)
    for pos in POSITIONS:
        w = opt_weights["position_weights"][pos]
        print(f"{pos:<5} {w['availability']:>6.3f} {w['attack']:>6.3f} "
              f"{w['defense']:>6.3f} {w['possession']:>6.3f} {w['quality']:>6.3f}")

    print(f"\n联赛系数缩放: {opt_weights['league_log_scale']:.3f}")
    print(f"可靠性-出场参考: {opt_weights['rel_minutes_ref']:.0f} 分钟")
    print(f"可靠性-首发参考: {opt_weights['rel_starts_ref']:.2f}")

    # Show team correlation
    print("\n[6] 优化后球队相关性:")
    opt_ratings = compute_ratings(player_df, opt_weights)
    team_ratings = compute_team_ratings(player_df, opt_ratings)
    merged = team_ratings.merge(team_standings, on=["team", "league", "season"], how="inner")

    sp, _ = spearmanr(merged["avg_rating"], merged["total_points"])
    pr, _ = pearsonr(merged["avg_rating"], merged["total_points"])
    print(f"  Spearman: {sp:.4f}")
    print(f"  Pearson: {pr:.4f}")

    # Show per-league correlation
    print("\n  各联赛相关性:")
    for league in sorted(merged["league"].unique()):
        lm = merged[merged["league"] == league]
        if len(lm) >= 5:
            s, _ = spearmanr(lm["avg_rating"], lm["total_points"])
            p, _ = pearsonr(lm["avg_rating"], lm["total_points"])
            print(f"    {league:<22} Spearman={s:.3f}  Pearson={p:.3f}  (N={len(lm)})")

    # Save optimized weights
    output_path = settings.gold_root / "feature_store" / "optimized_weights.npz"
    np.savez(output_path, params=result.x)
    print(f"\n[7] 优化参数已保存: {output_path}")

    # Save training history
    if args.save_history:
        monitor.save_history(Path(args.save_history))
        print(f"    训练历史已保存: {args.save_history}")

    # Re-rate all players with optimized weights
    print("\n[8] 用优化权重重新评分...")
    player_df["optimized_score"] = opt_ratings
    player_df = player_df.sort_values("optimized_score", ascending=False)

    ratings_path = settings.gold_root / "feature_store" / "player_ratings_optimized.parquet"
    player_df.to_parquet(ratings_path, index=False)
    print(f"  已保存: {ratings_path}")

    print("\n  Top 20 (优化后):")
    print("-" * 80)
    for i, (_, row) in enumerate(player_df.head(20).iterrows(), 1):
        print(f"  {i:>3}  {row['player']:<28} {row['team']:<22} "
              f"{row['sub_position']:<3} {row['optimized_score']:>6.1f}")

    # Generate final plot
    print("\n[9] 生成训练曲线图...")
    try:
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend for saving
        import matplotlib.pyplot as plt

        history = monitor.get_history()
        if history:
            iterations = [h.iteration for h in history]
            spearman_vals = [h.spearman for h in history]
            pearson_vals = [h.pearson for h in history]

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

            # Correlation plot
            ax1.plot(iterations, spearman_vals, "g-", linewidth=2, label="Spearman")
            ax1.plot(iterations, pearson_vals, "r--", linewidth=2, label="Pearson")
            ax1.axhline(baseline_spearman, color="gray", linestyle="--", alpha=0.5, label="Baseline")
            ax1.set_xlabel("Iteration")
            ax1.set_ylabel("Correlation")
            ax1.set_title("Optimization Progress: Correlation")
            ax1.set_ylim(-0.1, 1.0)
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Scatter plot: team rating vs points
            ax2.scatter(merged["avg_rating"], merged["total_points"], alpha=0.5, s=20)
            ax2.set_xlabel("Team Average Rating")
            ax2.set_ylabel("Total Points")
            ax2.set_title(f"Team Rating vs Points (Spearman={sp:.3f})")
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            plot_path = settings.model_root / "training_progress.png"
            plt.savefig(plot_path, dpi=150)
            print(f"  训练曲线图已保存: {plot_path}")
            plt.close()
    except Exception as e:
        print(f"  警告: 无法生成图表 ({e})")


def _get_default_params():
    """Convert default v3 weights to parameter vector (inverse of params_to_weights)."""
    default_pw = {
        "ST": {"availability": 0.15, "attack": 0.38, "defense": 0.08, "possession": 0.14, "quality": 0.25},
        "W":  {"availability": 0.12, "attack": 0.30, "defense": 0.10, "possession": 0.25, "quality": 0.23},
        "AM": {"availability": 0.12, "attack": 0.28, "defense": 0.10, "possession": 0.28, "quality": 0.22},
        "CM": {"availability": 0.14, "attack": 0.16, "defense": 0.18, "possession": 0.32, "quality": 0.20},
        "DM": {"availability": 0.14, "attack": 0.08, "defense": 0.30, "possession": 0.28, "quality": 0.20},
        "FB": {"availability": 0.15, "attack": 0.10, "defense": 0.28, "possession": 0.27, "quality": 0.20},
        "CB": {"availability": 0.16, "attack": 0.05, "defense": 0.42, "possession": 0.20, "quality": 0.17},
        "GK": {"availability": 0.20, "attack": 0.05, "defense": 0.35, "possession": 0.20, "quality": 0.20},
    }
    default_aw = {
        "ST": {"npxg_p90": 0.45, "assists_p90": 0.15, "g_a_volume": 0.40},
        "W":  {"npxg_p90": 0.30, "assists_p90": 0.30, "g_a_volume": 0.40},
        "AM": {"npxg_p90": 0.20, "assists_p90": 0.40, "g_a_volume": 0.40},
        "CM": {"npxg_p90": 0.15, "assists_p90": 0.35, "g_a_volume": 0.50},
        "DM": {"npxg_p90": 0.10, "assists_p90": 0.25, "g_a_volume": 0.65},
        "FB": {"npxg_p90": 0.10, "assists_p90": 0.45, "g_a_volume": 0.45},
        "CB": {"npxg_p90": 0.20, "assists_p90": 0.20, "g_a_volume": 0.60},
        "GK": {"npxg_p90": 0.05, "assists_p90": 0.05, "g_a_volume": 0.90},
    }

    params = []
    for pos in POSITIONS:
        w = default_pw[pos]
        params.extend(_inv_softmax([w[d] for d in DIMENSIONS]))
    for pos in POSITIONS:
        w = default_aw[pos]
        params.extend(_inv_softmax([w[m] for m in ATTACK_METRICS]))
    params.extend(_inv_softmax([0.45, 0.25, 0.20, 0.10]))  # avail sub
    params.extend(_inv_softmax([0.35, 0.25, 0.25, 0.15]))  # quality sub
    params.append(1.0)  # league_log_scale
    params.append(0.0)  # rel_minutes_ref centered at 1800
    params.append(0.0)  # rel_starts_ref centered at 0.5
    return np.array(params)


def _inv_softmax(probs):
    """Approximate inverse softmax (log-probabilities)."""
    p = np.array(probs)
    p = np.clip(p, 1e-10, 1.0)
    return np.log(p) - np.log(p).mean()


if __name__ == "__main__":
    main()

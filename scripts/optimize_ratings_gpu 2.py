#!/usr/bin/env python3
"""
球员评分权重优化器 — PyTorch GPU 版本
在 Windows + RTX 5070 Ti 上运行，几秒完成一次优化循环。

使用方法 (Windows):
  1. pip install torch pandas numpy scipy pyarrow
  2. 把 data/ 目录复制到 Windows 机器上
  3. python optimize_ratings_gpu.py --data_dir ./data

或在 Mac 上用 CPU 也能跑 (会慢一些但比 scipy 快很多)。
"""

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from scipy.stats import spearmanr, pearsonr

# ── 位置映射 ──────────────────────────────────────────────────────────────

POSITIONS = ["ST", "W", "AM", "CM", "DM", "FB", "CB", "GK"]
DIMENSIONS = ["availability", "attack", "defense", "possession", "quality"]
ATTACK_METRICS = ["npxg_p90", "assists_p90", "g_a_volume"]
POS_TO_IDX = {p: i for i, p in enumerate(POSITIONS)}
N_POS = len(POSITIONS)
N_DIM = len(DIMENSIONS)
N_ATK = len(ATTACK_METRICS)
N_PARAMS = N_POS * N_DIM + N_POS * N_ATK + 4 + 4 + 3  # = 75


def map_position(pos_str):
    if not isinstance(pos_str, str):
        return "CM"
    s = pos_str.upper()
    if "GK" in s: return "GK"
    if "FW" in s and "MF" in s: return "W"
    if "MF" in s and "FW" in s: return "AM"
    if "DF" in s and "MF" in s: return "FB"
    if "MF" in s and "DF" in s: return "DM"
    if "FW" in s: return "ST"
    if "DF" in s: return "CB"
    if "MF" in s: return "CM"
    return "CM"


# ── 数据加载 ──────────────────────────────────────────────────────────────

def load_data(data_dir: Path):
    """加载 FBref 球员数据 + Football-Data 球队积分。"""
    fbref = pd.read_parquet(data_dir / "raw" / "fbref" / "player_stats_big5_3seasons.parquet")

    goals = fbref[("Performance", "Gls")].values.astype(np.float32)
    assists_col = fbref[("Performance", "Ast")].values.astype(np.float32)
    pk = fbref[("Performance", "PK")].values.astype(np.float32)
    minutes = fbref[("Playing Time", "Min")].values.astype(np.float32)
    starts = fbref[("Playing Time", "Starts")].values.astype(np.float32)
    matches = fbref[("Playing Time", "MP")].values.astype(np.float32)
    positions = fbref[("pos", "")].values
    leagues = fbref.index.get_level_values("league").astype(str).values
    seasons = fbref.index.get_level_values("season").values
    teams = fbref.index.get_level_values("team").values
    players = fbref.index.get_level_values("player").values

    npg = goals - pk
    safe_min = np.maximum(minutes, 1.0)
    npg_p90 = npg / safe_min * 90
    assists_p90 = assists_col / safe_min * 90
    g_a_volume = npg + assists_col

    sub_pos = np.array([map_position(p) for p in positions])
    pos_idx = np.array([POS_TO_IDX.get(p, 4) for p in sub_pos])  # default CM

    # Deduplicate
    df = pd.DataFrame({
        "player": players, "team": teams, "league": leagues, "season": seasons,
        "sub_position": sub_pos, "pos_idx": pos_idx,
        "matches": matches, "starts": starts, "minutes": minutes,
        "npg_p90": npg_p90, "assists_p90": assists_p90, "g_a_volume": g_a_volume,
    })
    df = df.sort_values("minutes", ascending=False)
    df = df.drop_duplicates(subset=["player", "season", "league"], keep="first")
    df = df.reset_index(drop=True)

    # Team standings
    fd = pd.read_parquet(data_dir / "raw" / "football_data" / "combined_results.parquet")
    standings_rows = []
    for _, row in fd.iterrows():
        season = str(row.get("season", ""))
        league = str(row.get("league", ""))
        home, away = str(row["HomeTeam"]), str(row["AwayTeam"])
        hg, ag = float(row["FTHG"]), float(row["FTAG"])
        hp = 3 if hg > ag else (1 if hg == ag else 0)
        ap = 3 - hp if hg != ag else 1
        standings_rows.append({"team": home, "league": league, "season": season,
                               "points": hp, "gf": hg, "ga": ag})
        standings_rows.append({"team": away, "league": league, "season": season,
                               "points": ap, "gf": ag, "ga": hg})
    standings = pd.DataFrame(standings_rows)
    team_pts = standings.groupby(["team", "league", "season"]).agg(
        total_points=("points", "sum"),
    ).reset_index()

    return df, team_pts


# ── 向量化评分 (PyTorch) ──────────────────────────────────────────────────

def build_feature_tensors(df):
    """预计算所有特征张量，避免循环。"""
    N = len(df)

    # Per-position percentile ranks (预计算，不在每次迭代中重算)
    pos_groups = {}
    for pos_name, pos_i in POS_TO_IDX.items():
        mask = df["pos_idx"].values == pos_i
        if mask.sum() == 0:
            continue
        pos_groups[pos_i] = {
            "mask": mask,
            "npg_p90": df["npg_p90"].values[mask],
            "assists_p90": df["assists_p90"].values[mask],
            "g_a_volume": df["g_a_volume"].values[mask],
        }

    # Compute percentile for each player within its position group
    npg_pct = np.full(N, 50.0, dtype=np.float32)
    ast_pct = np.full(N, 50.0, dtype=np.float32)
    vol_pct = np.full(N, 50.0, dtype=np.float32)

    for pos_i, pg in pos_groups.items():
        mask = pg["mask"]
        vals_npg = pg["npg_p90"]
        vals_ast = pg["assists_p90"]
        vals_vol = pg["g_a_volume"]
        n = len(vals_npg)
        if n == 0:
            continue
        for j, idx in enumerate(np.where(mask)[0]):
            npg_pct[idx] = (vals_npg < vals_npg[j]).sum() / n * 100
            ast_pct[idx] = (vals_ast < vals_ast[j]).sum() / n * 100
            vol_pct[idx] = (vals_vol < vals_vol[j]).sum() / n * 100

    # League encoding
    league_names = sorted(df["league"].unique())
    league_to_idx = {l: i for i, l in enumerate(league_names)}
    league_idx = np.array([league_to_idx.get(l, 0) for l in df["league"].values])

    # League median minutes
    league_med = df.groupby("league")["minutes"].median()
    league_med_arr = np.array([league_med.get(l, 1800) for l in df["league"].values], dtype=np.float32)

    # Team-season grouping
    team_season_keys = df.groupby(["team", "league", "season"]).groups
    ts_indices = []
    ts_team_names = []
    ts_leagues = []
    ts_seasons = []
    for (team, league, season), indices in team_season_keys.items():
        ts_indices.append(indices.values if hasattr(indices, 'values') else list(indices))
        ts_team_names.append(team)
        ts_leagues.append(league)
        ts_seasons.append(season)

    return {
        "N": N,
        "pos_idx": torch.tensor(df["pos_idx"].values, dtype=torch.long),
        "npg_pct": torch.tensor(npg_pct, dtype=torch.float32),
        "ast_pct": torch.tensor(ast_pct, dtype=torch.float32),
        "vol_pct": torch.tensor(vol_pct, dtype=torch.float32),
        "minutes": torch.tensor(df["minutes"].values, dtype=torch.float32),
        "starts": torch.tensor(df["starts"].values, dtype=torch.float32),
        "matches": torch.tensor(df["matches"].values, dtype=torch.float32),
        "league_med": torch.tensor(league_med_arr, dtype=torch.float32),
        "league_idx": torch.tensor(league_idx, dtype=torch.long),
        "n_leagues": len(league_names),
        "league_names": league_names,
        "ts_indices": ts_indices,
        "ts_team_names": ts_team_names,
        "ts_leagues": ts_leagues,
        "ts_seasons": ts_seasons,
        "df": df,
    }


def compute_ratings_torch(feat, params, device):
    """向量化评分，无循环。"""
    # Unpack parameters
    idx = 0
    # Position weights: 8×5
    pw_raw = params[idx:idx + N_POS * N_DIM].reshape(N_POS, N_DIM)
    pw = torch.softmax(pw_raw, dim=1)  # [8, 5]
    idx += N_POS * N_DIM

    # Attack weights: 8×3
    aw_raw = params[idx:idx + N_POS * N_ATK].reshape(N_POS, N_ATK)
    aw = torch.softmax(aw_raw, dim=1)  # [8, 3]
    idx += N_POS * N_ATK

    # Availability sub-weights: 4
    avail_sw = torch.softmax(params[idx:idx + 4], dim=0)
    idx += 4

    # Quality sub-weights: 4
    qual_sw = torch.softmax(params[idx:idx + 4], dim=0)
    idx += 4

    # Scalar params
    league_log_scale = params[idx]  # raw, will be used as exponent
    idx += 1
    rel_min_scale = torch.sigmoid(params[idx])  # [0, 1] -> maps to [900, 2700]
    rel_starts_scale = torch.sigmoid(params[idx + 1])  # [0, 1] -> maps to [0.3, 0.7]

    # Gather position weights for each player
    pos_idx = feat["pos_idx"].to(device)
    player_pw = pw[pos_idx]  # [N, 5]
    player_aw = aw[pos_idx]  # [N, 3]

    minutes = feat["minutes"].to(device)
    starts_t = feat["starts"].to(device)
    matches_t = feat["matches"].to(device)
    league_med = feat["league_med"].to(device)

    # ── Availability ──
    min_share = torch.clamp(minutes / league_med, max=1.0) * 100
    start_rate_score = starts_t / torch.clamp(matches_t, min=1) * 100
    avail_pct = torch.clamp(matches_t / 38, max=1.0) * 100
    role_stab = torch.full_like(minutes, 50.0)

    availability = (min_share * avail_sw[0] + start_rate_score * avail_sw[1]
                    + avail_pct * avail_sw[2] + role_stab * avail_sw[3])

    # ── Attack (percentile-based, pre-computed) ──
    npg_pct = feat["npg_pct"].to(device)
    ast_pct = feat["ast_pct"].to(device)
    vol_pct = feat["vol_pct"].to(device)

    attack = (npg_pct * player_aw[:, 0] + ast_pct * player_aw[:, 1]
              + vol_pct * player_aw[:, 2])

    # ── Defense & Possession (no data → 50) ──
    defense = torch.full_like(minutes, 50.0)
    possession = torch.full_like(minutes, 50.0)

    # ── Quality ──
    quality = (npg_pct * qual_sw[0] + ast_pct * qual_sw[1]
               + 50.0 * qual_sw[2] + 50.0 * qual_sw[3])

    # ── Base score ──
    base = (availability * player_pw[:, 0] + attack * player_pw[:, 1]
            + defense * player_pw[:, 2] + possession * player_pw[:, 3]
            + quality * player_pw[:, 4])

    # ── Reliability ──
    rel_min_ref = 900 + rel_min_scale * 1800
    rel_starts_ref = 0.3 + rel_starts_scale * 0.4

    min_rel = 0.5 + 0.5 * torch.clamp(minutes / rel_min_ref, max=1.0)
    sr = starts_t / torch.clamp(matches_t, min=1)
    start_rel = 0.85 + 0.15 * torch.clamp(sr / rel_starts_ref, max=1.0)
    reliability = min_rel * start_rel

    # ── League coefficient ──
    # Log-ratio scaling: (ln(league_coeff) / ln(england_coeff))^scale
    league_coeffs = torch.tensor(
        [119.52, 93.00, 92.90, 81.93, 83.50],  # UEFA coefficients
        dtype=torch.float32, device=device,
    )
    eng_log = torch.log(league_coeffs[0])
    league_strength = (torch.log(league_coeffs) / eng_log) ** torch.clamp(league_log_scale, 0.1, 3.0)

    league_idx = feat["league_idx"].to(device)
    player_league_coeff = league_strength[league_idx]

    # ── Final score ──
    overall = base * reliability * player_league_coeff
    return overall


def compute_team_avg_ratings(feat, ratings, device):
    """计算每队每赛季平均评分 (按出场分钟加权)。"""
    ts_indices = feat["ts_indices"]
    minutes = feat["minutes"].to(device)

    team_avgs = []
    for indices in ts_indices:
        idx_t = torch.tensor(indices, dtype=torch.long, device=device)
        r = ratings[idx_t]
        m = torch.clamp(minutes[idx_t], min=1)
        avg = (r * m).sum() / m.sum()
        team_avgs.append(avg.item())
    return np.array(team_avgs)


def objective_torch(feat, team_pts_df, params, device, verbose=False):
    """负 Spearman 相关性 (最小化)。"""
    ratings = compute_ratings_torch(feat, params, device)
    team_avgs = compute_team_avg_ratings(feat, ratings, device)

    # Match with actual standings
    ts_team = feat["ts_team_names"]
    ts_league = feat["ts_leagues"]
    ts_season = feat["ts_seasons"]

    pred_pts = []
    actual_pts = []
    for i in range(len(ts_team)):
        mask = ((team_pts_df["team"] == ts_team[i])
                & (team_pts_df["league"] == ts_league[i])
                & (team_pts_df["season"] == ts_season[i]))
        matched = team_pts_df.loc[mask, "total_points"]
        if len(matched) > 0:
            pred_pts.append(team_avgs[i])
            actual_pts.append(matched.values[0])

    pred_pts = np.array(pred_pts)
    actual_pts = np.array(actual_pts)

    if len(pred_pts) < 10:
        return torch.tensor(1.0, device=device, requires_grad=True)

    sp, _ = spearmanr(pred_pts, actual_pts)
    pr, _ = pearsonr(pred_pts, actual_pts)

    if verbose:
        print(f"  Spearman={sp:.4f}  Pearson={pr:.4f}  N={len(pred_pts)}")

    # Use negative Spearman as loss (minimize)
    return torch.tensor(-sp, device=device, requires_grad=True)


# ── 优化循环 ──────────────────────────────────────────────────────────────

def optimize(feat, team_pts, device, n_steps=500, lr=0.05, pop_size=32):
    """
    多起点并行优化。
    对 pop_size 组随机初始化的参数同时优化，取最优。
    """
    print(f"  设备: {device}")
    print(f"  种群: {pop_size}, 步数: {n_steps}, 学习率: {lr}")

    # 初始化参数种群
    all_params = []
    all_losses = []
    all_final_corrs = []

    for pop_i in range(pop_size):
        # Random init with bias toward reasonable values
        params = torch.randn(N_PARAMS, device=device) * 0.5

        # Adam optimizer
        params_t = params.clone().detach().requires_grad_(True)
        optimizer = torch.optim.Adam([params_t], lr=lr)

        best_loss = float("inf")
        best_params = params_t.clone().detach()
        patience_counter = 0

        for step in range(n_steps):
            optimizer.zero_grad()

            # Forward: compute ratings
            ratings = compute_ratings_torch(feat, params_t, device)
            team_avgs = compute_team_avg_ratings(feat, ratings, device)

            # Match standings
            pred_list = []
            actual_list = []
            for i in range(len(feat["ts_team_names"])):
                mask = ((team_pts["team"] == feat["ts_team_names"][i])
                        & (team_pts["league"] == feat["ts_leagues"][i])
                        & (team_pts["season"] == feat["ts_seasons"][i]))
                matched = team_pts.loc[mask, "total_points"]
                if len(matched) > 0:
                    pred_list.append(team_avgs[i])
                    actual_list.append(matched.values[0])

            if len(pred_list) < 10:
                continue

            pred_t = torch.tensor(pred_list, device=device, dtype=torch.float32)
            actual_t = torch.tensor(actual_list, device=device, dtype=torch.float32)

            # Differentiable loss: negative Pearson + small Spearman-like penalty
            # Pearson is differentiable; we use it as the main gradient signal
            pred_mean = pred_t.mean()
            actual_mean = actual_t.mean()
            pred_centered = pred_t - pred_mean
            actual_centered = actual_t - actual_mean
            pearson_corr = (pred_centered * actual_centered).sum() / (
                torch.sqrt((pred_centered ** 2).sum() * (actual_centered ** 2).sum()) + 1e-8
            )
            loss = -pearson_corr  # maximize correlation

            # Regularization: penalize extreme weights
            reg = 0.001 * (params_t ** 2).mean()
            total_loss = loss + reg

            total_loss.backward()
            optimizer.step()

            current_loss = loss.item()
            if current_loss < best_loss:
                best_loss = current_loss
                best_params = params_t.clone().detach()
                patience_counter = 0
            else:
                patience_counter += 1

            if patience_counter > 50:
                break

        # Final evaluation with Spearman (non-differentiable but correct metric)
        final_ratings = compute_ratings_torch(feat, best_params, device)
        final_team_avgs = compute_team_avg_ratings(feat, final_ratings, device)

        pred_arr = []
        actual_arr = []
        for i in range(len(feat["ts_team_names"])):
            mask = ((team_pts["team"] == feat["ts_team_names"][i])
                    & (team_pts["league"] == feat["ts_leagues"][i])
                    & (team_pts["season"] == feat["ts_seasons"][i]))
            matched = team_pts.loc[mask, "total_points"]
            if len(matched) > 0:
                pred_arr.append(final_team_avgs[i])
                actual_arr.append(matched.values[0])

        if len(pred_arr) >= 10:
            sp, _ = spearmanr(pred_arr, actual_arr)
            pr, _ = pearsonr(pred_arr, actual_arr)
        else:
            sp, pr = -1.0, -1.0

        all_params.append(best_params.cpu())
        all_losses.append(-sp)
        all_final_corrs.append((sp, pr))

        if (pop_i + 1) % 5 == 0 or pop_i == 0:
            print(f"  [{pop_i+1}/{pop_size}] best Spearman={sp:.4f}  Pearson={pr:.4f}")

    # Pick best
    best_idx = int(np.argmin(all_losses))
    best_sp, best_pr = all_final_corrs[best_idx]
    print(f"\n  最优: Spearman={best_sp:.4f}  Pearson={best_pr:.4f}  (第 {best_idx+1} 组)")

    return all_params[best_idx].to(device)


def _inv_softmax(probs):
    """Approximate inverse softmax."""
    p = np.array(probs, dtype=np.float32)
    p = np.clip(p, 1e-10, 1.0)
    return np.log(p) - np.log(p).mean()


def _get_default_params_tensor(device):
    """Default v3 weights converted to parameter tensor."""
    default_pw = [
        [0.15, 0.38, 0.08, 0.14, 0.25],  # ST
        [0.12, 0.30, 0.10, 0.25, 0.23],  # W
        [0.12, 0.28, 0.10, 0.28, 0.22],  # AM
        [0.14, 0.16, 0.18, 0.32, 0.20],  # CM
        [0.14, 0.08, 0.30, 0.28, 0.20],  # DM
        [0.15, 0.10, 0.28, 0.27, 0.20],  # FB
        [0.16, 0.05, 0.42, 0.20, 0.17],  # CB
        [0.20, 0.05, 0.35, 0.20, 0.20],  # GK
    ]
    default_aw = [
        [0.45, 0.15, 0.40],  # ST
        [0.30, 0.30, 0.40],  # W
        [0.20, 0.40, 0.40],  # AM
        [0.15, 0.35, 0.50],  # CM
        [0.10, 0.25, 0.65],  # DM
        [0.10, 0.45, 0.45],  # FB
        [0.20, 0.20, 0.60],  # CB
        [0.05, 0.05, 0.90],  # GK
    ]
    params = []
    for row in default_pw:
        params.extend(_inv_softmax(row))
    for row in default_aw:
        params.extend(_inv_softmax(row))
    params.extend(_inv_softmax([0.45, 0.25, 0.20, 0.10]))
    params.extend(_inv_softmax([0.35, 0.25, 0.25, 0.15]))
    params.extend([1.0, 0.0, 0.0])
    return torch.tensor(params, dtype=torch.float32, device=device)


# ── 主流程 ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="球员评分权重优化器 (GPU)")
    parser.add_argument("--data_dir", type=str, default="./data",
                        help="数据目录路径 (包含 raw/ 和 gold/)")
    parser.add_argument("--steps", type=int, default=500, help="每组优化步数")
    parser.add_argument("--lr", type=float, default=0.05, help="学习率")
    parser.add_argument("--pop", type=int, default=32, help="种群大小 (并行起点数)")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    print("=" * 80)
    print("球员评分权重优化器 (PyTorch GPU)")
    print("=" * 80)

    # Device
    # Force CPU on RTX 50-series until PyTorch cu128 stable is available
    device = torch.device("cpu")
    print("\nCPU (RTX 50-series: PyTorch cu126 does not support sm_120, using CPU)")

    # Load data
    print("\n[1] 加载数据...")
    t0 = time.time()
    df, team_pts = load_data(data_dir)
    print(f"  球员: {len(df)}, 球队赛季: {len(team_pts)}")
    print(f"  耗时: {time.time()-t0:.1f}s")

    # Build feature tensors
    print("\n[2] 预计算特征...")
    t0 = time.time()
    feat = build_feature_tensors(df)
    print(f"  耗时: {time.time()-t0:.1f}s")

    # Baseline
    print("\n[3] 基线 (v3 默认权重)...")
    default_params = _get_default_params_tensor(device)
    baseline_ratings = compute_ratings_torch(feat, default_params, device)
    baseline_team_avgs = compute_team_avg_ratings(feat, baseline_ratings, device)

    pred_b, actual_b = [], []
    for i in range(len(feat["ts_team_names"])):
        mask = ((team_pts["team"] == feat["ts_team_names"][i])
                & (team_pts["league"] == feat["ts_leagues"][i])
                & (team_pts["season"] == feat["ts_seasons"][i]))
        matched = team_pts.loc[mask, "total_points"]
        if len(matched) > 0:
            pred_b.append(baseline_team_avgs[i])
            actual_b.append(matched.values[0])
    sp_b, pr_b = spearmanr(pred_b, actual_b)
    print(f"  基线 Spearman: {sp_b:.4f}  Pearson: {pr_b:.4f}")

    # Optimize
    print(f"\n[4] 优化 (pop={args.pop}, steps={args.steps}, lr={args.lr})...")
    t0 = time.time()
    best_params = optimize(feat, team_pts, device, n_steps=args.steps, lr=args.lr, pop_size=args.pop)
    print(f"  总耗时: {time.time()-t0:.1f}s")

    # Results
    print("\n[5] 优化后权重:")
    print("-" * 80)
    pw_raw = best_params[:N_POS * N_DIM].reshape(N_POS, N_DIM)
    pw = torch.softmax(pw_raw, dim=1).cpu().numpy()
    print(f"{'位置':<5} {'出勤':>7} {'进攻':>7} {'防守':>7} {'控球':>7} {'质量':>7}")
    print("-" * 80)
    for i, pos in enumerate(POSITIONS):
        print(f"{pos:<5} {pw[i,0]:>7.4f} {pw[i,1]:>7.4f} {pw[i,2]:>7.4f} {pw[i,3]:>7.4f} {pw[i,4]:>7.4f}")

    # Attack weights
    aw_raw = best_params[N_POS * N_DIM:N_POS * N_DIM + N_POS * N_ATK].reshape(N_POS, N_ATK)
    aw = torch.softmax(aw_raw, dim=1).cpu().numpy()
    print(f"\n{'位置':<5} {'npxG_p90':>9} {'ast_p90':>9} {'G+A_vol':>9}")
    print("-" * 40)
    for i, pos in enumerate(POSITIONS):
        print(f"{pos:<5} {aw[i,0]:>9.4f} {aw[i,1]:>9.4f} {aw[i,2]:>9.4f}")

    # Per-league correlation
    print("\n[6] 各联赛相关性 (优化后):")
    opt_ratings = compute_ratings_torch(feat, best_params, device)
    opt_team_avgs = compute_team_avg_ratings(feat, opt_ratings, device)

    pred_opt, actual_opt = [], []
    for i in range(len(feat["ts_team_names"])):
        mask = ((team_pts["team"] == feat["ts_team_names"][i])
                & (team_pts["league"] == feat["ts_leagues"][i])
                & (team_pts["season"] == feat["ts_seasons"][i]))
        matched = team_pts.loc[mask, "total_points"]
        if len(matched) > 0:
            pred_opt.append(opt_team_avgs[i])
            actual_opt.append(matched.values[0])

    sp_opt, pr_opt = spearmanr(pred_opt, actual_opt)
    print(f"\n  总体: Spearman={sp_opt:.4f}  Pearson={pr_opt:.4f}")
    print(f"  提升: Spearman {sp_opt - sp_b:+.4f}  Pearson {pr_opt - pr_b:+.4f}")

    # Per league
    for league in sorted(set(feat["ts_leagues"])):
        indices = [i for i, l in enumerate(feat["ts_leagues"]) if l == league]
        p = [pred_opt[i] for i in indices]
        a = [actual_opt[i] for i in indices]
        if len(p) >= 5:
            s, _ = spearmanr(p, a)
            pr_l, _ = pearsonr(p, a)
            print(f"    {league:<22} Spearman={s:.3f}  Pearson={pr_l:.3f}  N={len(p)}")

    # Save
    output = data_dir / "gold" / "feature_store"
    output.mkdir(parents=True, exist_ok=True)
    np.save(output / "optimized_params.npy", best_params.cpu().numpy())
    print(f"\n[7] 参数已保存: {output / 'optimized_params.npy'}")

    # Save re-rated players
    df["optimized_score"] = opt_ratings.cpu().numpy()
    df = df.sort_values("optimized_score", ascending=False)
    df.to_parquet(output / "player_ratings_optimized.parquet", index=False)
    print(f"  球员评分已保存: {output / 'player_ratings_optimized.parquet'}")

    print("\n  Top 20 (优化后):")
    print("-" * 80)
    for i, (_, row) in enumerate(df.head(20).iterrows(), 1):
        print(f"  {i:>3}  {row['player']:<28} {row['team']:<22} "
              f"{row['sub_position']:<3} {row['optimized_score']:>6.1f}")


if __name__ == "__main__":
    main()

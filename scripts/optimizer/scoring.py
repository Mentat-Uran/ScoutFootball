"""Scoring functions for player/team rating computation (PyTorch)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from .constants import (
    ATTACK_SCALE,
    INJURY_MIN_CEILING,
    INJURY_MIN_FLOOR,
    INJURY_START_RATE_THRESHOLD,
    N_ATK,
    N_DIM,
    N_POS,
    POSITION_SLOT_CAPS,
    POSITION_SLOT_GROUPS,
    POSITIONS,
    QUALITY_SCALE,
    RELIABILITY_MIN_CEILING,
    RELIABILITY_MIN_FLOOR,
    RELIABILITY_MIN_THRESHOLD,
    STANDARD_SEASON_MATCHES,
    TEAM_AGG_CAPPED_MINUTES_BLEND,
    TEAM_AGG_CORE_MINUTES,
    TEAM_AGG_CORE_SCALE,
    TEAM_AGG_MINUTES_CAP,
    apply_position_weight_caps,
)

# _percentile_against_reference is imported from .data (lazy to avoid circular imports)
# from .data import _percentile_against_reference


# ---------------------------------------------------------------------------
# Feature tensor construction
# ---------------------------------------------------------------------------

def build_feature_tensors(
    df: pd.DataFrame,
    rank_reference_df: pd.DataFrame | None = None,
) -> dict:
    """预计算所有特征张量，包括防守和控球维度。

    rank_reference_df 用于把验证/测试集映射到训练集分布，避免用测试集整体分布
    计算百分位或联赛分钟中位数。
    """
    # Late import to avoid circular dependency with data.py
    from .data import _percentile_against_reference

    n_rows = len(df)
    reference_df = df if rank_reference_df is None else rank_reference_df

    # Per-position percentile ranks for all dimensions. For validation/test
    # slices, percentile thresholds come only from the train reference frame.
    rank_cols = {
        "npg_p90": "npg_pct",
        "assists_p90": "ast_pct",
        "g_a_volume": "vol_pct",
        "defense_composite": "def_pct",
        "possession_composite": "pos_pct",
    }
    if "npg_trend" in df.columns:
        rank_cols["npg_trend"] = "trend_pct"

    pct_df = pd.DataFrame(index=df.index)
    for src_col, out_col in rank_cols.items():
        pct_df[out_col] = _percentile_against_reference(
            df,
            reference_df,
            src_col,
        )

    npg_pct = pct_df["npg_pct"].to_numpy(dtype=np.float32)
    ast_pct = pct_df["ast_pct"].to_numpy(dtype=np.float32)
    vol_pct = pct_df["vol_pct"].to_numpy(dtype=np.float32)
    def_pct = pct_df["def_pct"].to_numpy(dtype=np.float32)
    pos_pct = pct_df["pos_pct"].to_numpy(dtype=np.float32)
    trend_pct = pct_df.get(
        "trend_pct",
        pd.Series(np.full(n_rows, 50.0, dtype=np.float32), index=df.index),
    ).to_numpy(dtype=np.float32)

    # League encoding
    league_names = sorted(df["league"].unique())
    league_to_idx = {league: i for i, league in enumerate(league_names)}
    league_idx = np.array([league_to_idx.get(league, 0) for league in df["league"].values])

    # League median minutes
    league_med = reference_df.groupby("league")["minutes"].median()
    global_minutes_median = float(pd.to_numeric(reference_df["minutes"], errors="coerce").median())
    if not np.isfinite(global_minutes_median):
        global_minutes_median = 1800.0
    league_med_arr = np.array(
        [league_med.get(league, global_minutes_median) for league in df["league"].values],
        dtype=np.float32,
    )

    # Team-season grouping (use reset index positions)
    df_reset = df.reset_index(drop=True)
    team_agg_weight = _build_team_aggregation_weights(df_reset)
    team_season_groups = df_reset.groupby(["team", "league", "season"]).groups
    ts_indices = []
    ts_team_names = []
    ts_leagues = []
    ts_seasons = []
    team_group_idx = np.empty(n_rows, dtype=np.int64)
    for (team, league, season), indices in team_season_groups.items():
        group_i = len(ts_indices)
        idx_arr = np.array(
            indices.values if hasattr(indices, "values") else list(indices),
            dtype=np.int64,
        )
        team_group_idx[idx_arr] = group_i
        ts_indices.append(idx_arr)
        ts_team_names.append(team)
        ts_leagues.append(league)
        ts_seasons.append(season)

    return {
        "N": n_rows,
        "n_team_groups": len(ts_indices),
        "team_group_idx": torch.tensor(team_group_idx, dtype=torch.long),
        "team_agg_weight": torch.tensor(team_agg_weight, dtype=torch.float32),
        "pos_idx": torch.tensor(df["pos_idx"].values, dtype=torch.long),
        "npg_pct": torch.tensor(npg_pct, dtype=torch.float32),
        "ast_pct": torch.tensor(ast_pct, dtype=torch.float32),
        "vol_pct": torch.tensor(vol_pct, dtype=torch.float32),
        "def_pct": torch.tensor(def_pct, dtype=torch.float32),
        "pos_pct": torch.tensor(pos_pct, dtype=torch.float32),
        "trend_pct": torch.tensor(trend_pct, dtype=torch.float32),
        # Missing-data flags: 1.0 = has data, 0.0 = missing (NaN source)
        "has_defense": torch.tensor(
            np.isfinite(df["defense_composite"].to_numpy(dtype=np.float32)).astype(np.float32)
            if "defense_composite" in df.columns
            else np.zeros(n_rows, dtype=np.float32),
            dtype=torch.float32,
        ),
        "has_possession": torch.tensor(
            np.isfinite(df["possession_composite"].to_numpy(dtype=np.float32)).astype(np.float32)
            if "possession_composite" in df.columns
            else np.zeros(n_rows, dtype=np.float32),
            dtype=torch.float32,
        ),
        "experience": torch.tensor(
            np.clip(
                df["experience_factor"].values
                if "experience_factor" in df.columns
                else np.ones(n_rows),
                0.5,
                1.0,
            ),
            dtype=torch.float32,
        ),
        "minutes": torch.tensor(df["minutes"].values, dtype=torch.float32),
        "starts": torch.tensor(df["starts"].values, dtype=torch.float32),
        "matches": torch.tensor(df["matches"].values, dtype=torch.float32),
        "league_med": torch.tensor(league_med_arr, dtype=torch.float32),
        "league_idx": torch.tensor(league_idx, dtype=torch.long),
        "n_leagues": len(league_names),
        "league_names": league_names,
        "ts_indices": ts_indices,
        "ts_team_names": ts_team_names,
        "ts_leagues": ["Bundesliga" if str(league) == "nan" else league for league in ts_leagues],
        "ts_seasons": ts_seasons,
        "df": df,
    }


def _build_team_aggregation_weights(df_reset: pd.DataFrame) -> np.ndarray:
    """Build robust team-season weights that do not reward raw minutes twice.

    Player ratings already include availability/reliability. For team strength,
    pure minutes weighting lets high-minute average CM/CB/GK profiles drag a
    squad above stronger but more rotated sides. This uses a capped-minutes share
    blended with a core-rotation share, approximating a squad median without
    dropping the first-team signal.
    """
    if df_reset.empty:
        return np.array([], dtype=np.float32)

    minutes = pd.to_numeric(df_reset["minutes"], errors="coerce").fillna(0.0).clip(lower=0.0)
    capped = np.sqrt(np.minimum(minutes.to_numpy(dtype=np.float64), TEAM_AGG_MINUTES_CAP))
    z = np.clip(
        (minutes.to_numpy(dtype=np.float64) - TEAM_AGG_CORE_MINUTES) / TEAM_AGG_CORE_SCALE,
        -50.0,
        50.0,
    )
    core = 1.0 / (1.0 + np.exp(-z))

    work = df_reset.loc[:, ["team", "league", "season"]].copy()
    work["capped"] = capped
    work["core"] = core
    group = work.groupby(["team", "league", "season"], sort=False)
    group_size = group["capped"].transform("size").to_numpy(dtype=np.float64)

    capped_sum = group["capped"].transform("sum").to_numpy(dtype=np.float64)
    core_sum = group["core"].transform("sum").to_numpy(dtype=np.float64)
    capped_share = np.divide(
        capped,
        capped_sum,
        out=np.divide(1.0, group_size, out=np.zeros_like(group_size), where=group_size > 0),
        where=capped_sum > 0,
    )
    core_share = np.divide(
        core,
        core_sum,
        out=np.divide(1.0, group_size, out=np.zeros_like(group_size), where=group_size > 0),
        where=core_sum > 0,
    )

    weights = (
        TEAM_AGG_CAPPED_MINUTES_BLEND * capped_share
        + (1.0 - TEAM_AGG_CAPPED_MINUTES_BLEND) * core_share
    )

    # Apply position slot caps
    if "sub_position" in df_reset.columns:
        slot_group = df_reset["sub_position"].map(POSITION_SLOT_GROUPS).fillna("MF")
        work["slot_group"] = slot_group.values
        work["team_season"] = (
            work["team"] + "|" + work["league"] + "|" + work["season"]
        )
        work["weight"] = weights

        # Compute slot totals per team-season
        slot_totals = work.groupby(
            ["team_season", "slot_group"], sort=False
        )["weight"].transform("sum")
        slot_caps = slot_group.map(POSITION_SLOT_CAPS).fillna(2.5)

        # Scale down weights where slot total exceeds cap
        overcap = slot_totals > slot_caps.values
        if overcap.any():
            scale_factor = np.where(overcap, slot_caps.values / slot_totals, 1.0)
            weights = weights * scale_factor

    # Normalize within team-season
    work["weight"] = weights
    weight_sum = work.groupby(["team", "league", "season"], sort=False)["weight"].transform(
        "sum",
    ).to_numpy(dtype=np.float64)
    normalized = np.divide(
        weights,
        weight_sum,
        out=np.divide(1.0, group_size, out=np.zeros_like(group_size), where=group_size > 0),
        where=weight_sum > 0,
    )
    return normalized.astype(np.float32)


# ---------------------------------------------------------------------------
# Rating computation (PyTorch)
# ---------------------------------------------------------------------------


def _unpack_params(
    params: torch.Tensor,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, dict]:
    """Unpack the 77-parameter vector into named tensors.

    Returns:
        pw: position weights [N_POS, N_DIM] (softmax + capped)
        aw: attack weights [N_POS, N_ATK] (softmax)
        avail_sw: availability sub-weights [4] (softmax)
        qual_sw: quality sub-weights [4] (softmax)
        scalar: dict with league_log_scale, rel_starts_scale,
                trend_weight, exp_weight
    """
    idx = 0
    pw_raw = params[idx:idx + N_POS * N_DIM].reshape(N_POS, N_DIM)
    pw = torch.softmax(pw_raw, dim=1)
    pw = apply_position_weight_caps(pw)
    idx += N_POS * N_DIM

    aw_raw = params[idx:idx + N_POS * N_ATK].reshape(N_POS, N_ATK)
    aw = torch.softmax(aw_raw, dim=1)
    idx += N_POS * N_ATK

    avail_sw = torch.softmax(params[idx:idx + 4], dim=0)
    idx += 4

    qual_sw = torch.softmax(params[idx:idx + 4], dim=0)
    idx += 4

    league_log_scale = params[idx]
    idx += 1
    _rel_min_scale = torch.sigmoid(params[idx])
    rel_starts_scale = torch.sigmoid(params[idx + 1])
    idx += 2
    trend_weight = torch.sigmoid(params[idx]) * 10
    idx += 1
    exp_weight = torch.sigmoid(params[idx]) * 5

    scalar = {
        "league_log_scale": league_log_scale,
        "rel_starts_scale": rel_starts_scale,
        "trend_weight": trend_weight,
        "exp_weight": exp_weight,
    }
    return pw, aw, avail_sw, qual_sw, scalar


def compute_ratings_torch(
    feat: dict,
    params: torch.Tensor,
    device: torch.device,
) -> torch.Tensor:
    """向量化评分，无循环。"""
    # Unpack parameters into named tensors
    pw, aw, avail_sw, qual_sw, scalar = _unpack_params(params, device)

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
    avail_pct = torch.clamp(matches_t / STANDARD_SEASON_MATCHES, max=1.0) * 100
    role_stab = torch.full_like(minutes, 50.0)

    availability = (min_share * avail_sw[0] + start_rate_score * avail_sw[1]
                    + avail_pct * avail_sw[2] + role_stab * avail_sw[3])

    # ── Attack (percentile-based, pre-computed) ──
    npg_pct = feat["npg_pct"].to(device)
    ast_pct = feat["ast_pct"].to(device)
    vol_pct = feat["vol_pct"].to(device)

    # 前场球员的进攻百分位已经在位置内排序，优化器又可能给 ST/W 很高的 attack
    # 维度权重。如果最后再按位置整体打折，会同时惩罚出勤、防守和控球，解释性较差；
    # 这里只压缩进攻维度本身，让高产前锋仍然靠真实进攻输出拿分，但避免进球/助攻
    # 单一维度把 Top 排名挤满。AM 只做轻微压缩，供未来位置映射修正后使用。
    attack_scale = torch.ones(N_POS, device=device)
    for i, pos in enumerate(POSITIONS):
        attack_scale[i] = ATTACK_SCALE.get(pos, 1.0)

    attack = (
        npg_pct * player_aw[:, 0]
        + ast_pct * player_aw[:, 1]
        + vol_pct * player_aw[:, 2]
    ) * attack_scale[pos_idx]

    # ── Defense (percentile-based, real data) ──
    def_pct = feat["def_pct"].to(device)
    has_def = feat.get("has_defense", torch.ones_like(def_pct)).to(device)
    # For rows missing defense data (Understat), blend toward position median
    # instead of treating 50th percentile as real performance
    defense = def_pct * has_def + 50.0 * (1.0 - has_def)

    # ── Possession (percentile-based, real data) ──
    pos_pct = feat["pos_pct"].to(device)
    has_pos = feat.get("has_possession", torch.ones_like(pos_pct)).to(device)
    possession = pos_pct * has_pos + 50.0 * (1.0 - has_pos)

    # ── Quality ──
    # Reduce quality weight for rows missing defense/possession data
    quality_has_data = torch.min(has_def, has_pos)  # 1.0 only if both present
    quality_def = (
        def_pct * qual_sw[2] * quality_has_data
        + 50.0 * qual_sw[2] * (1.0 - quality_has_data)
    )
    quality_pos = (
        pos_pct * qual_sw[3] * quality_has_data
        + 50.0 * qual_sw[3] * (1.0 - quality_has_data)
    )
    quality = (npg_pct * qual_sw[0] + ast_pct * qual_sw[1]
               + quality_def + quality_pos)
    # quality 是跨维度效率项，不应让中场通过"进攻百分位 + 出勤"获得前锋级
    # 影响力。ST 的 quality 已被 cap 限制在 0.30，不需要额外下调；
    # CM/DM 下调，避免优化器把中场 quality 当作低风险的统一捷径。
    quality_scale = torch.ones(N_POS, dtype=quality.dtype, device=device)
    for i, pos in enumerate(POSITIONS):
        quality_scale[i] = QUALITY_SCALE.get(pos, 1.0)
    quality = quality * quality_scale[pos_idx]

    # ── Base score ──
    base = (availability * player_pw[:, 0] + attack * player_pw[:, 1]
            + defense * player_pw[:, 2] + possession * player_pw[:, 3]
            + quality * player_pw[:, 4])

    # ── Reliability (出场时间惩罚) ──
    # 低分钟数样本仍然不可靠，但旧曲线把 500 分钟球员压到 0.3，容易把
    # 半季主力、冬窗转会和伤愈回归球员惩罚过重。这里改成更温和的线性爬坡：
    # <400 分钟保留 0.42 底分，400-1200 分钟快速恢复，>=1200 分钟视为满可信。
    min_threshold = RELIABILITY_MIN_THRESHOLD
    min_ceiling = RELIABILITY_MIN_CEILING
    min_floor = RELIABILITY_MIN_FLOOR
    min_progress = torch.clamp(
        (minutes - min_threshold) / (min_ceiling - min_threshold),
        min=0.0,
        max=1.0,
    )
    min_rel = min_floor + (1.0 - min_floor) * min_progress

    # 首发率惩罚 (保持原有逻辑)
    sr = starts_t / torch.clamp(matches_t, min=1)
    rel_starts_ref = 0.3 + scalar["rel_starts_scale"] * 0.4
    start_rel = 0.85 + 0.15 * torch.clamp(sr / rel_starts_ref, max=1.0)

    # ── 高首发率伤病保护 ──
    # 首发率 >= 70% 的球员，低分钟数大概率是伤病/转会导致，不是替补刷分。
    # 对这类球员，分钟惩罚的底分从 0.42 提升到 0.72，爬坡终点从 1200 降到 900。
    # 这样一个首发率 90%、500 分钟的球员 reliability ≈ 0.85 而非 0.49。
    high_start_mask = sr >= INJURY_START_RATE_THRESHOLD
    injury_min_floor = INJURY_MIN_FLOOR
    injury_min_ceiling = INJURY_MIN_CEILING
    injury_min_progress = torch.clamp(
        (minutes - min_threshold) / (injury_min_ceiling - min_threshold),
        min=0.0,
        max=1.0,
    )
    injury_min_rel = injury_min_floor + (1.0 - injury_min_floor) * injury_min_progress
    # 只对高首发率且低分钟的球员应用保护（分钟>=1200时两者相同，无需切换）
    min_rel = torch.where(high_start_mask & (minutes < min_ceiling), injury_min_rel, min_rel)

    reliability = min_rel * start_rel

    # ── League coefficient ──
    # 外部联赛强度只能作为温和校准，而不是硬排名：当前特征已经是跨联赛球员
    # 原始表现百分位，英超球员本身会因数据分布拿到较高基础分。如果再用线性
    # UEFA 比值，会把 Top 30 推成英超名单；如果完全不用强度先验，又会低估
    # 联赛竞争环境。这里保留 Big 5 强度先验，但用 0.14-0.20 的窄幂曲线压缩
    # 差距。上一版 0.14-0.20 的指数过窄，Ligue 1/Serie A 的高百分位球员
    # 容易被推到接近英超同档。这里改成 0.28-0.42 的中等幂曲线：弱一档
    # 联赛会被明确折扣，但不会把 La Liga/Bundesliga 顶级球员整体压扁。
    league_name_to_coeff = {
        "Premier League": 119.52,
        "La Liga": 93.00,
        "Bundesliga": 92.90,
        "Ligue 1": 83.50,
        "Serie A": 81.93,
    }
    league_names_sorted = feat["league_names"]
    coeff_values = [league_name_to_coeff.get(league, 80.0) for league in league_names_sorted]
    league_coeffs = torch.tensor(coeff_values, dtype=torch.float32, device=device)
    league_ratio = league_coeffs / torch.max(league_coeffs)
    league_curve_exponent = 0.28 + 0.14 * torch.sigmoid(scalar["league_log_scale"])
    league_strength = torch.pow(league_ratio, league_curve_exponent)

    league_idx = feat["league_idx"].to(device)
    player_league_coeff = league_strength[league_idx]

    # ── Trend bonus ──
    trend_pct = feat["trend_pct"].to(device)
    trend_bonus = (trend_pct - 50) / 50 * scalar["trend_weight"]  # centered at 0, range [-tw, +tw]

    # ── Experience bonus ──
    experience = feat["experience"].to(device)
    exp_bonus = (experience - 0.5) / 0.5 * scalar["exp_weight"]  # centered at 0, range [0, ew]

    # ── Final score ──
    overall = base * reliability * player_league_coeff + trend_bonus + exp_bonus

    return overall


# ---------------------------------------------------------------------------
# Team-level aggregation
# ---------------------------------------------------------------------------

def compute_team_avg_ratings_torch(feat, ratings, device):
    """计算每队每赛季稳健平均评分，保持 Torch 计算图用于反向传播。"""
    group_idx = feat["team_group_idx"].to(device)
    if "team_agg_weight" in feat:
        weights = feat["team_agg_weight"].to(device)
    else:
        minutes = feat["minutes"].to(device)
        weights = torch.clamp(minutes, min=1)
    n_groups = int(feat["n_team_groups"])

    weighted_sum = torch.zeros(n_groups, dtype=ratings.dtype, device=device)
    weight_sum = torch.zeros(n_groups, dtype=ratings.dtype, device=device)
    weighted_sum = weighted_sum.index_add(0, group_idx, ratings * weights)
    weight_sum = weight_sum.index_add(0, group_idx, weights)
    return weighted_sum / torch.clamp(weight_sum, min=1e-8)


def compute_team_avg_ratings(feat, ratings, device):
    """计算每队每赛季稳健平均评分，返回 NumPy 供报告使用。"""
    return compute_team_avg_ratings_torch(feat, ratings, device).detach().cpu().numpy()


# ---------------------------------------------------------------------------
# Team target tensors
# ---------------------------------------------------------------------------

def build_team_target_tensors(feat, team_pts_df, device):
    """把可匹配的球队赛季积分预编译成张量索引，避免训练步内 pandas 查询。

    Teams with NaN or non-finite total_points are excluded.
    """
    # Filter out teams with NaN or non-finite total_points
    valid_pts = team_pts_df.copy()
    valid_pts["total_points"] = pd.to_numeric(valid_pts["total_points"], errors="coerce")
    valid_pts = valid_pts[
        valid_pts["total_points"].notna() & np.isfinite(valid_pts["total_points"])
    ]

    points_lookup = {
        (str(row["team"]), str(row["league"]), str(row["season"])): float(row["total_points"])
        for _, row in valid_pts.iterrows()
    }
    matched_group_idx = []
    actual_points = []
    for i, (team, league, season) in enumerate(
        zip(feat["ts_team_names"], feat["ts_leagues"], feat["ts_seasons"], strict=False)
    ):
        # Defensive: replace "nan" league with "Bundesliga" (FBref NaN league issue)
        league_str = str(league)
        if league_str == "nan":
            league_str = "Bundesliga"
        key = (str(team), league_str, str(season))
        if key in points_lookup:
            matched_group_idx.append(i)
            actual_points.append(points_lookup[key])

    return (
        torch.tensor(matched_group_idx, dtype=torch.long, device=device),
        torch.tensor(actual_points, dtype=torch.float32, device=device),
    )

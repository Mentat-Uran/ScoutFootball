"""
损失函数模块 — 排名损失、校准损失、分布匹配、NDCG、Dixon-Coles 等。

从 optimize_ratings_gpu.py (2361-2955 行) 提取。
"""

import numpy as np
import pandas as pd
import torch

# 来自 constants.py 的依赖
from .constants import POSITION_CORE_METRICS, POS_TO_IDX, normalize_team_name

# 来自 scoring.py 的依赖
from .scoring import (
    build_team_target_tensors,
    compute_ratings_torch,
    compute_team_avg_ratings_torch,
)


# ── 基础排名/相关性工具 ─────────────────────────────────────────────────


def _corrcoef_torch(x, y, eps=1e-8):
    """Pearson correlation with numerical guards."""
    x = x - x.mean()
    y = y - y.mean()
    denom = torch.sqrt(torch.sum(x * x) * torch.sum(y * y)).clamp_min(eps)
    return torch.sum(x * y) / denom


def soft_rank_torch(values, temperature=4.0):
    """Dependency-free smooth ascending ranks for Spearman-style optimization."""
    temp = max(float(temperature), 1e-6)
    x = values.reshape(-1)
    pairwise = (x[:, None] - x[None, :]) / temp
    return torch.sigmoid(pairwise).sum(dim=1)


# ── 排名/相关性损失 ─────────────────────────────────────────────────────


def differentiable_rank_loss(pred, actual, spearman_weight=0.7, temperature=4.0):
    """Blend soft Spearman and Pearson into a single differentiable objective."""
    pred_rank = soft_rank_torch(pred, temperature=temperature)
    actual_rank = soft_rank_torch(actual.detach(), temperature=temperature)
    soft_spearman = _corrcoef_torch(pred_rank, actual_rank)
    pearson_corr = _corrcoef_torch(pred, actual)
    w = float(np.clip(spearman_weight, 0.0, 1.0))
    objective = w * soft_spearman + (1.0 - w) * pearson_corr
    return -objective, soft_spearman, pearson_corr


# ── 积分校准损失 ────────────────────────────────────────────────────────


def calibrate_points_torch(pred_strength, actual_points, eps=1e-6):
    """Differentiable quadratic calibration from strength to point scale.

    Uses y = a*x^2 + b*x + c fitted on training data, which can capture
    the nonlinear relationship between player rating aggregates and team points.
    Falls back to linear if quadratic fit is unstable.
    """
    pred_detached = pred_strength.detach()
    actual_detached = actual_points.detach()

    # Normalize pred to [0, 1] range for numerical stability
    pred_min = pred_detached.min()
    pred_max = pred_detached.max()
    pred_range = (pred_max - pred_min).clamp(min=eps)
    pred_norm = (pred_strength - pred_min) / pred_range  # [0, 1]

    # Fit quadratic: actual = a*pred_norm^2 + b*pred_norm + c
    # Using least squares with pred_norm, pred_norm^2 as features
    x1 = pred_norm.detach()
    x2 = pred_norm.detach() ** 2
    ones = torch.ones_like(x1)

    # Design matrix [1, x, x^2]
    X = torch.stack([ones, x1, x2], dim=1)  # (n, 3)
    y = actual_detached.unsqueeze(1)  # (n, 1)

    # Normal equations: (X^T X) beta = X^T y
    XtX = X.T @ X + eps * torch.eye(3, device=X.device)  # regularization
    Xty = X.T @ y
    try:
        beta = torch.linalg.solve(XtX, Xty).squeeze(1)  # (3,)
    except Exception:
        # Fallback to linear
        beta = torch.stack([
            actual_detached.mean(),
            actual_detached.std(),
            torch.tensor(0.0, device=X.device),
        ])

    c, b, a = beta[0], beta[1], beta[2]

    # Apply: calibrated = a*pred_norm^2 + b*pred_norm + c
    calibrated = a * pred_norm ** 2 + b * pred_norm + c

    # Ensure the output has the right spread (rescale if needed)
    cal_std = calibrated.detach().std(unbiased=False).clamp(min=eps)
    actual_std = actual_detached.std(unbiased=False).clamp(min=eps)
    # Soft rescale to match actual spread
    calibrated = (
        (calibrated - calibrated.detach().mean())
        / cal_std * actual_std
        + actual_detached.mean()
    )

    return calibrated


def points_regression_loss(pred_strength, actual_points):
    """Optimize calibrated point distance, not just ordering."""
    pred_points = calibrate_points_torch(pred_strength, actual_points)
    scale = actual_points.detach().std(unbiased=False).clamp_min(1.0)
    residual = (pred_points - actual_points.detach()) / scale
    return torch.mean(residual ** 2), pred_points


def distribution_matching_loss(pred_points, actual_points):
    """1D Wasserstein-style loss between calibrated predicted and actual points."""
    if len(pred_points) < 2:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=pred_points.device)
    scale = actual_points.detach().std(unbiased=False).clamp_min(1.0)
    pred_sorted = torch.sort(pred_points).values
    actual_sorted = torch.sort(actual_points.detach()).values
    return torch.mean(((pred_sorted - actual_sorted) / scale) ** 2)


def tail_calibration_loss(pred_points, actual_points, tail_quantile=0.20):
    """Upweight title-race and relegation-zone teams in calibrated point loss."""
    n = int(actual_points.numel())
    if n < 5:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=pred_points.device)
    actual_detached = actual_points.detach()
    low_cut = torch.quantile(actual_detached, float(tail_quantile))
    high_cut = torch.quantile(actual_detached, float(1.0 - tail_quantile))
    tail_mask = (actual_detached <= low_cut) | (actual_detached >= high_cut)
    if int(tail_mask.sum().item()) == 0:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=pred_points.device)
    scale = actual_detached.std(unbiased=False).clamp_min(1.0)
    residual = (pred_points[tail_mask] - actual_detached[tail_mask]) / scale
    return torch.mean(residual ** 2)


def quantile_matching_loss(pred_points, actual_points, quantiles=(0.1, 0.25, 0.5, 0.75, 0.9)):
    """Force predicted distribution quantiles to match actual distribution quantiles.

    Unlike distribution_matching_loss (Wasserstein on sorted values), this explicitly
    targets specific quantile levels, which helps stretch the predicted range.
    """
    if len(pred_points) < 5:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=pred_points.device)
    actual_detached = actual_points.detach()
    scale = actual_detached.std(unbiased=False).clamp_min(1.0)
    losses = []
    for q in quantiles:
        pred_q = torch.quantile(pred_points, q)
        actual_q = torch.quantile(actual_detached, q)
        losses.append(((pred_q - actual_q) / scale) ** 2)
    return torch.stack(losses).mean()


def range_penalty_loss(pred_points, actual_points):
    """Directly penalize the gap between predicted and actual value ranges.

    This is the key loss to fix distribution compression: pred_range=24 vs actual_range=77.
    """
    pred_range = pred_points.max() - pred_points.min()
    actual_range = actual_points.detach().max() - actual_points.detach().min()
    actual_range = actual_range.clamp(min=1.0)
    # Penalize relative range gap: (1 - pred_range/actual_range)^2
    return (1.0 - pred_range / actual_range) ** 2


def league_bias_loss(
    feat,
    matched_group_idx,
    pred_points,
    actual_points,
    device,
    min_teams=5,
):
    """Penalize systematic calibrated point bias by league-season source league."""
    if int(actual_points.numel()) < min_teams:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=device)
    group_indices = matched_group_idx.detach().cpu().tolist()
    leagues = [str(feat["ts_leagues"][int(group_i)]) for group_i in group_indices]
    if not leagues:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=device)

    residual = pred_points - actual_points.detach()
    scale = actual_points.detach().std(unbiased=False).clamp_min(1.0)
    losses = []
    for league in sorted(set(leagues)):
        mask_values = [item == league for item in leagues]
        if sum(mask_values) < min_teams:
            continue
        mask = torch.tensor(mask_values, dtype=torch.bool, device=device)
        league_bias = residual[mask].mean() / scale
        losses.append(league_bias ** 2)
    if not losses:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=device)
    return torch.stack(losses).mean()


# ── Dixon-Coles 比分预测似然 ────────────────────────────────────────────


def build_dc_match_tensors(matches_df, feat, device):
    """Build match-level tensors for Dixon-Coles likelihood computation.

    Matches team-season groups from feat with match results from Football-Data.
    Only includes matches where both teams have a team-season group in feat.
    """
    # Build lookup: (normalized_team, league, season) -> group index
    team_season_to_group = {}
    for i, (team, league, season) in enumerate(
        zip(feat["ts_team_names"], feat["ts_leagues"], feat["ts_seasons"]),
    ):
        key = (normalize_team_name(team), str(league), str(season))
        team_season_to_group[key] = i

    home_group_idx = []
    away_group_idx = []
    home_goals = []
    away_goals = []

    for _, row in matches_df.iterrows():
        home_key = (
            normalize_team_name(str(row["home_team"])),
            str(row["league"]),
            str(row["season"]),
        )
        away_key = (
            normalize_team_name(str(row["away_team"])),
            str(row["league"]),
            str(row["season"]),
        )
        if home_key in team_season_to_group and away_key in team_season_to_group:
            home_group_idx.append(team_season_to_group[home_key])
            away_group_idx.append(team_season_to_group[away_key])
            home_goals.append(float(row["home_goals"]))
            away_goals.append(float(row["away_goals"]))

    if not home_group_idx:
        return None

    return {
        "home_group_idx": torch.tensor(home_group_idx, dtype=torch.long, device=device),
        "away_group_idx": torch.tensor(away_group_idx, dtype=torch.long, device=device),
        "home_goals": torch.tensor(home_goals, dtype=torch.float32, device=device),
        "away_goals": torch.tensor(away_goals, dtype=torch.float32, device=device),
        "n_matches": len(home_group_idx),
    }


def _poisson_log_pmf(k, lam, eps=1e-8):
    """Log PMF of Poisson: log(P(X=k|λ)) = k*log(λ) - λ - log(k!)"""
    lam_safe = lam.clamp(min=eps)
    return k * torch.log(lam_safe) - lam_safe - torch.lgamma(k + 1.0)


def _dixon_coles_log_tau(x, y, lam_home, lam_away, rho, eps=1e-8):
    """Dixon-Coles low-score correction factor in log space.

    τ corrects Poisson independence for outcomes (0,0), (1,0), (0,1), (1,1).
    Returns log(τ(x, y, λ, μ, ρ)); for scores > 1 returns 0 (log(1)).
    """
    log_tau = torch.zeros_like(lam_home)

    # (0, 0): τ = 1 - λ*μ*ρ
    mask_00 = (x == 0) & (y == 0)
    if mask_00.any():
        val = 1.0 - lam_home[mask_00] * lam_away[mask_00] * rho
        log_tau = log_tau.masked_scatter(mask_00, torch.log(val.clamp(min=eps)))

    # (1, 0): τ = 1 + λ*ρ
    mask_10 = (x == 1) & (y == 0)
    if mask_10.any():
        val = 1.0 + lam_home[mask_10] * rho
        log_tau = log_tau.masked_scatter(mask_10, torch.log(val.clamp(min=eps)))

    # (0, 1): τ = 1 + μ*ρ
    mask_01 = (x == 0) & (y == 1)
    if mask_01.any():
        val = 1.0 + lam_away[mask_01] * rho
        log_tau = log_tau.masked_scatter(mask_01, torch.log(val.clamp(min=eps)))

    # (1, 1): τ = 1 - ρ
    mask_11 = (x == 1) & (y == 1)
    if mask_11.any():
        n11 = int(mask_11.sum())
        val = torch.full((n11,), 1.0 - rho, device=log_tau.device, dtype=log_tau.dtype)
        log_tau = log_tau.masked_scatter(mask_11, torch.log(val.clamp(min=eps)))

    return log_tau


def dixon_coles_log_likelihood(
    team_avgs,
    dc_tensors,
    rho=-0.13,
    base_rate=0.25,
    rating_scale=0.05,
    home_advantage=0.25,
    eps=1e-8,
):
    """Compute Dixon-Coles mean negative log-likelihood from team ratings.

    Expected goals model:
        λ_home = exp(base + scale*(R_home - R_away) + home_adv)
        λ_away = exp(base + scale*(R_away - R_home))

    The ρ parameter corrects Poisson independence for low-score outcomes
    (Dixon & Coles 1997). Returns mean NLL (lower = better fit).

    Gradients flow back through team_avgs → player ratings → params.
    """
    if dc_tensors is None or dc_tensors["n_matches"] == 0:
        return torch.tensor(0.0, device=team_avgs.device, requires_grad=True)

    home_idx = dc_tensors["home_group_idx"]
    away_idx = dc_tensors["away_group_idx"]
    hg = dc_tensors["home_goals"]
    ag = dc_tensors["away_goals"]

    rating_home = team_avgs.index_select(0, home_idx)
    rating_away = team_avgs.index_select(0, away_idx)

    # Expected goals (log-space for stability, then exp)
    diff = rating_scale * (rating_home - rating_away)
    log_lam_home = base_rate + diff + home_advantage
    log_lam_away = base_rate - diff
    lam_home = torch.exp(log_lam_home).clamp(min=eps, max=12.0)
    lam_away = torch.exp(log_lam_away).clamp(min=eps, max=12.0)

    # Poisson log-likelihood for each team
    ll_home = _poisson_log_pmf(hg, lam_home)
    ll_away = _poisson_log_pmf(ag, lam_away)

    # Dixon-Coles low-score correction
    log_tau = _dixon_coles_log_tau(hg, ag, lam_home, lam_away, rho)

    # Negative mean log-likelihood (loss to minimize)
    return -(ll_home + ll_away + log_tau).mean()


# ── 复合目标组件 (v2: quantile + range_penalty + quadratic calibration) ─────


def ndcg_loss(feat, ratings, team_pts_df, device, k=20, temperature=4.0):
    """Differentiable NDCG@K loss across league-season groups.

    Returns 1 - mean(NDCG@K), so lower is better.
    Uses soft-rank discounts for differentiable predicted ranking.
    """
    # Build team average ratings per team-season group
    team_avgs = compute_team_avg_ratings_torch(feat, ratings, device)

    # Build actual points lookup (same logic as build_team_target_tensors)
    valid_pts = team_pts_df.copy()
    valid_pts["total_points"] = pd.to_numeric(valid_pts["total_points"], errors="coerce")
    valid_pts = valid_pts[
        valid_pts["total_points"].notna() & np.isfinite(valid_pts["total_points"])
    ]

    points_lookup = {
        (str(row["team"]), str(row["league"]), str(row["season"])): float(row["total_points"])
        for _, row in valid_pts.iterrows()
    }

    # Group team-season indices by league-season
    league_season_groups: dict[tuple[str, str], list[int]] = {}
    for i, (team, league, season) in enumerate(
        zip(feat["ts_team_names"], feat["ts_leagues"], feat["ts_seasons"], strict=False)
    ):
        key = (str(team), str(league), str(season))
        if key in points_lookup:
            ls_key = (str(league), str(season))
            league_season_groups.setdefault(ls_key, []).append(i)

    if not league_season_groups:
        return torch.tensor(0.0, device=device, requires_grad=True)

    ndcg_values = []
    for _ls_key, group_indices in league_season_groups.items():
        if len(group_indices) < 3:
            continue

        idx_t = torch.tensor(group_indices, dtype=torch.long, device=device)
        pred_ratings = team_avgs.index_select(0, idx_t)
        actual_points = torch.tensor(
            [points_lookup[(str(feat["ts_team_names"][i]),
                            str(feat["ts_leagues"][i]),
                            str(feat["ts_seasons"][i]))]
             for i in group_indices],
            dtype=torch.float32,
            device=device,
        )

        # soft_rank_torch gives ascending ranks; negate ratings so stronger
        # predictions receive lower rank values. Avoid argsort here because it
        # would detach NDCG from the prediction graph.
        pred_soft_rank = soft_rank_torch(-pred_ratings, temperature=temperature)

        # Normalize actual points to [0, 1] for relevance
        pts_min = actual_points.min()
        pts_max = actual_points.max()
        pts_range = pts_max - pts_min
        if pts_range < 1e-8:
            continue
        rel = (actual_points - pts_min) / pts_range

        top_k = min(k, len(group_indices))
        gains = torch.pow(2.0, rel) - 1.0
        soft_discounts = 1.0 / torch.log2(pred_soft_rank + 2.0)
        gate_temperature = max(float(temperature) / 4.0, 0.5)
        top_gate = torch.sigmoid((top_k - pred_soft_rank) / gate_temperature)
        dcg = torch.sum(gains * soft_discounts * top_gate)

        # Ideal DCG: sort by actual relevance descending
        ideal_sorted_rel = torch.sort(rel, descending=True).values[:top_k]
        positions = torch.arange(1, top_k + 1, dtype=torch.float32, device=device)
        discounts = 1.0 / torch.log2(positions + 1.0)
        idcg = torch.sum((torch.pow(2.0, ideal_sorted_rel) - 1.0) * discounts)
        if idcg < 1e-8:
            continue

        ndcg_values.append(dcg / idcg)

    if not ndcg_values:
        return torch.tensor(0.0, device=device, requires_grad=True)

    mean_ndcg = torch.stack(ndcg_values).mean()
    return 1.0 - mean_ndcg


def position_consistency_loss(feat, ratings, device, temperature=4.0):
    """Penalize inconsistency between rating rank and core-stat rank within each position.

    Returns mean(1 - soft_spearman) across positions.
    """
    pos_idx = feat["pos_idx"].to(device)
    df = feat["df"]

    losses = []
    for pos_name, core_metric in POSITION_CORE_METRICS.items():
        pos_i = POS_TO_IDX[pos_name]
        mask = (pos_idx == pos_i)
        n_pos = int(mask.sum().item())
        if n_pos < 5:
            continue

        # Get core metric values from the DataFrame
        if core_metric not in df.columns:
            continue
        metric_series = pd.to_numeric(df[core_metric], errors="coerce")
        # Exclude NaN rows from position consistency loss — Understat rows
        # without defense/possession data should not distort the metric.
        valid_mask = mask & torch.tensor(
            metric_series.notna().values, dtype=torch.bool, device=device,
        )
        n_valid = int(valid_mask.sum().item())
        if n_valid < 5:
            continue
        metric_values = metric_series.fillna(0.0).values
        metric_t = torch.tensor(metric_values, dtype=torch.float32, device=device)
        pos_ratings = ratings[valid_mask]
        pos_metrics = metric_t[valid_mask]

        # Skip if all values are identical (no ranking signal)
        if pos_metrics.std() < 1e-8 or pos_ratings.std() < 1e-8:
            continue

        # Soft Spearman between ratings and core metric
        rating_rank = soft_rank_torch(pos_ratings, temperature=temperature)
        metric_rank = soft_rank_torch(pos_metrics.detach(), temperature=temperature)
        soft_sp = _corrcoef_torch(rating_rank, metric_rank)
        losses.append(1.0 - soft_sp)

    if not losses:
        return torch.tensor(0.0, device=device, requires_grad=True)

    return torch.stack(losses).mean()


def extreme_penalty(ratings, sigma=3.0):
    """L2 penalty on ratings beyond sigma standard deviations from mean.

    Penalizes extreme ratings that may result from attendance shortcuts.
    """
    mean = ratings.mean()
    std = ratings.std()
    z = (ratings - mean) / (std + 1e-8)
    extreme_mask = (z.abs() > z.new_full([], sigma)).float()
    penalty = (extreme_mask * (z - sigma * z.sign()) ** 2).mean()
    return penalty


# ── 主目标函数 ──────────────────────────────────────────────────────────


def objective_torch(
    feat,
    team_pts_df,
    params,
    device,
    spearman_weight=0.30,
    soft_rank_temperature=4.0,
    ndcg_weight=0.12,
    position_consistency_weight=0.10,
    points_regression_weight=0.20,
    distribution_weight=0.05,
    quantile_weight=0.08,
    range_penalty_weight=0.10,
    tail_calibration_weight=0.08,
    league_bias_weight=0.05,
    extreme_penalty_weight=0.02,
    prior_weight=0.01,
    dc_likelihood_weight=0.08,
    dc_tensors=None,
    prior_params=None,
    verbose=False,
    return_components=False,
):
    """Composite objective with ranking, calibrated points, distribution and guardrails."""
    ratings = compute_ratings_torch(feat, params, device)
    team_avgs = compute_team_avg_ratings_torch(feat, ratings, device)
    matched_group_idx, actual_t = build_team_target_tensors(feat, team_pts_df, device)

    if len(matched_group_idx) < 10:
        dummy = torch.tensor(1.0, device=device, requires_grad=True)
        if return_components:
            return dummy, {}
        return dummy

    pred_t = team_avgs.index_select(0, matched_group_idx)

    # 1. Spearman/Pearson loss
    rank_loss, soft_sp, pr = differentiable_rank_loss(
        pred_t,
        actual_t,
        temperature=soft_rank_temperature,
    )

    # 2. NDCG loss
    ndcg = ndcg_loss(feat, ratings, team_pts_df, device, k=20, temperature=soft_rank_temperature)

    # 3. Position consistency loss
    pos_loss = position_consistency_loss(feat, ratings, device, temperature=soft_rank_temperature)

    # 4. Calibrated team-points losses
    points_loss, pred_points = points_regression_loss(pred_t, actual_t)
    dist_loss = distribution_matching_loss(pred_points, actual_t)
    quant_loss = quantile_matching_loss(pred_points, actual_t)
    range_pen = range_penalty_loss(pred_points, actual_t)
    tail_loss = tail_calibration_loss(pred_points, actual_t)
    lg_bias_loss = league_bias_loss(feat, matched_group_idx, pred_points, actual_t, device)

    # 5b. Dixon-Coles match-level likelihood
    dc_loss = torch.tensor(0.0, device=device)
    if dc_tensors is not None and dc_likelihood_weight > 0:
        dc_loss = dixon_coles_log_likelihood(team_avgs, dc_tensors)

    # 6. Player-score guardrail. This is not the team-points tail loss.
    ext_pen = extreme_penalty(ratings)

    # 6. Prior regularization
    if prior_params is not None:
        prior_reg = ((params - prior_params) ** 2).mean()
    else:
        prior_reg = torch.tensor(0.0, device=device)

    total = (
        spearman_weight * rank_loss
        + ndcg_weight * ndcg
        + position_consistency_weight * pos_loss
        + points_regression_weight * points_loss
        + distribution_weight * dist_loss
        + quantile_weight * quant_loss
        + range_penalty_weight * range_pen
        + tail_calibration_weight * tail_loss
        + league_bias_weight * lg_bias_loss
        + dc_likelihood_weight * dc_loss
        + extreme_penalty_weight * ext_pen
        + prior_weight * prior_reg
    )

    if verbose:
        print(
            f"  rank={rank_loss.item():.4f} ndcg={ndcg.item():.4f} "
            f"pos={pos_loss.item():.4f} points={points_loss.item():.4f} "
            f"dist={dist_loss.item():.4f} quant={quant_loss.item():.4f} "
            f"range={range_pen.item():.4f} tail={tail_loss.item():.4f} "
            f"league_bias={lg_bias_loss.item():.4f} "
            f"dc={dc_loss.item():.4f} "
            f"ext={ext_pen.item():.4f} "
            f"prior={prior_reg.item():.4f} total={total.item():.4f}"
        )

    if return_components:
        components = {
            "rank_loss": float(rank_loss.detach().cpu()),
            "ndcg": float(ndcg.detach().cpu()),
            "pos_loss": float(pos_loss.detach().cpu()),
            "points_loss": float(points_loss.detach().cpu()),
            "distribution": float(dist_loss.detach().cpu()),
            "quantile": float(quant_loss.detach().cpu()),
            "range_penalty": float(range_pen.detach().cpu()),
            "tail": float(tail_loss.detach().cpu()),
            "league_bias": float(lg_bias_loss.detach().cpu()),
            "dc_likelihood": float(dc_loss.detach().cpu()),
            "extreme": float(ext_pen.detach().cpu()),
            "prior": float(prior_reg.detach().cpu()),
            "soft_spearman": float(soft_sp.detach().cpu()),
            "soft_pearson": float(pr.detach().cpu()),
            "pred_points_std": float(pred_points.detach().std(unbiased=False).cpu()),
            "actual_points_std": float(actual_t.detach().std(unbiased=False).cpu()),
        }
        return total, components

    return total

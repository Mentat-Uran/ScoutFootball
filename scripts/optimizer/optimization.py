"""
优化循环模块 — cosine 学习率调度、多起点并行优化、参数初始化。

从 optimize_ratings_gpu.py (2957-3189 行) 提取。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from scipy.stats import pearsonr, spearmanr

from .constants import (
    ATTACK_WEIGHT_PRIOR,
    DIMENSIONS,
    N_DIM,
    N_PARAMS,
    N_POS,
    POSITION_DIMENSION_PRIOR,
    POSITIONS,
    QUALITY_SUBWEIGHT_PRIOR,
)
from .losses import objective_torch
from .scoring import (
    build_team_target_tensors,
    compute_ratings_torch,
    compute_team_avg_ratings,
)
from .viz import create_visualizer

# ── 学习率调度 ───────────────────────────────────────────────────────────


def cosine_lr_scale(
    step: int,
    total_steps: int,
    warmup_steps: int = 20,
    min_lr_ratio: float = 0.08,
) -> float:
    """Warm up linearly, then decay with a cosine floor."""
    total_steps = max(int(total_steps), 1)
    warmup_steps = max(0, min(int(warmup_steps), total_steps))
    min_lr_ratio = float(np.clip(min_lr_ratio, 0.0, 1.0))
    if warmup_steps > 0 and step < warmup_steps:
        return max((step + 1) / warmup_steps, min_lr_ratio)
    decay_steps = max(total_steps - warmup_steps, 1)
    progress = (step - warmup_steps) / decay_steps
    progress = float(np.clip(progress, 0.0, 1.0))
    cosine = 0.5 * (1.0 + np.cos(np.pi * progress))
    return min_lr_ratio + (1.0 - min_lr_ratio) * cosine


# ── 多起点并行优化 ─────────────────────────────────────────────────────


def optimize(
    feat,
    team_pts,
    device,
    n_steps=500,
    lr=0.035,
    pop_size=32,
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
    prior_strength=0.01,
    dc_likelihood_weight=0.08,
    dc_tensors=None,
    dc_rho=-0.13,
    init_scale=0.35,
    patience=80,
    warmup_steps=20,
    min_lr_ratio=0.08,
    grad_clip=5.0,
    seed=None,
    enable_viz=True,
    output_dir=None,
):
    """
    多起点并行优化。
    对 pop_size 组随机初始化的参数同时优化，取最优。
    """
    print(f"  设备: {device}")
    print(f"  种群: {pop_size}, 步数: {n_steps}, 学习率: {lr}")
    print(
        "  目标: "
        f"spearman={spearman_weight:.2f} ndcg={ndcg_weight:.2f} "
        f"pos_consistency={position_consistency_weight:.2f} "
        f"points={points_regression_weight:.2f} dist={distribution_weight:.2f} "
        f"tail={tail_calibration_weight:.2f} league_bias={league_bias_weight:.2f} "
        f"dc_likelihood={dc_likelihood_weight:.2f} "
        f"player_extreme={extreme_penalty_weight:.2f} prior={prior_strength:.2f}"
    )
    print(
        "  调度: "
        f"warmup={warmup_steps}, min_lr_ratio={min_lr_ratio:.2f}, grad_clip={grad_clip:.2f}"
    )

    if seed is not None:
        np.random.seed(int(seed))
        torch.manual_seed(int(seed))
        if device.type == "cuda":
            torch.cuda.manual_seed_all(int(seed))

    matched_group_idx, actual_t = build_team_target_tensors(feat, team_pts, device)
    if len(matched_group_idx) < 10:
        raise ValueError("可匹配的球队赛季少于 10 个，无法稳定优化")

    prior_params = _get_default_params_tensor(device)

    # 初始化可视化器 (使用新版 Plotly)
    viz = create_visualizer(n_steps=n_steps, pop_size=pop_size, enable=enable_viz)
    viz.start()

    # 初始化参数种群
    all_params = []
    all_losses = []
    all_final_corrs = []

    for pop_i in range(pop_size):
        # Warm-start from the explainable v3 prior, then explore around it.
        if pop_i == 0:
            params = prior_params.clone()
        else:
            params = prior_params + torch.randn(N_PARAMS, device=device) * init_scale

        # Adam optimizer
        params_t = params.clone().detach().requires_grad_(True)
        optimizer = torch.optim.AdamW([params_t], lr=lr)

        best_loss = float("inf")
        best_params = params_t.clone().detach()
        patience_counter = 0

        for step in range(n_steps):
            lr_scale = cosine_lr_scale(
                step,
                n_steps,
                warmup_steps=warmup_steps,
                min_lr_ratio=min_lr_ratio,
            )
            for group in optimizer.param_groups:
                group["lr"] = lr * lr_scale

            optimizer.zero_grad()

            total_loss, components = objective_torch(
                feat,
                team_pts,
                params_t,
                device,
                spearman_weight=spearman_weight,
                soft_rank_temperature=soft_rank_temperature,
                ndcg_weight=ndcg_weight,
                position_consistency_weight=position_consistency_weight,
                points_regression_weight=points_regression_weight,
                distribution_weight=distribution_weight,
                quantile_weight=quantile_weight,
                range_penalty_weight=range_penalty_weight,
                tail_calibration_weight=tail_calibration_weight,
                league_bias_weight=league_bias_weight,
                extreme_penalty_weight=extreme_penalty_weight,
                prior_weight=prior_strength,
                dc_likelihood_weight=dc_likelihood_weight,
                dc_tensors=dc_tensors,
                dc_rho=dc_rho,
                prior_params=prior_params,
                return_components=True,
            )

            total_loss.backward()
            if grad_clip and grad_clip > 0:
                torch.nn.utils.clip_grad_norm_([params_t], max_norm=float(grad_clip))
            optimizer.step()

            current_loss = float(total_loss.detach().cpu())

            # 更新可视化 (每 5 步更新一次)
            if step % 5 == 0:
                # 提取位置权重用于热力图
                params_cpu = params_t.detach().cpu()
                pw_raw = params_cpu[:N_POS * N_DIM].reshape(N_POS, N_DIM)
                pw_np = torch.softmax(pw_raw, dim=1).numpy()
                position_weights = {
                    pos: {dim: pw_np[i, j] for j, dim in enumerate(DIMENSIONS)}
                    for i, pos in enumerate(POSITIONS)
                }

                viz.update(
                    step=step,
                    pop_idx=pop_i,
                    loss=current_loss,
                    spearman=components.get("soft_spearman", 0.0),
                    pearson=components.get("soft_pearson", 0.0),
                    components=components,
                    position_weights=position_weights,
                )

            if current_loss < best_loss:
                best_loss = current_loss
                best_params = params_t.clone().detach()
                patience_counter = 0
            else:
                patience_counter += 1

            if patience_counter > patience:
                break

        # Final evaluation with Spearman (non-differentiable but correct metric)
        final_ratings = compute_ratings_torch(feat, best_params, device)
        final_team_avgs = compute_team_avg_ratings(feat, final_ratings, device)

        idx_np = matched_group_idx.detach().cpu().numpy()
        pred_arr = final_team_avgs[idx_np]
        actual_arr = actual_t.detach().cpu().numpy()
        sp, _ = spearmanr(pred_arr, actual_arr)
        pr, _ = pearsonr(pred_arr, actual_arr)

        all_params.append(best_params.cpu())
        all_losses.append(-sp)
        all_final_corrs.append((sp, pr))

        if (pop_i + 1) % 5 == 0 or pop_i == 0:
            print(f"  [{pop_i+1}/{pop_size}] best Spearman={sp:.4f}  Pearson={pr:.4f}")

    # Pick best
    best_idx = int(np.argmin(all_losses))
    best_sp, best_pr = all_final_corrs[best_idx]
    print(f"\n  最优: Spearman={best_sp:.4f}  Pearson={best_pr:.4f}  (第 {best_idx+1} 组)")

    # 训练结束，保存可视化报告
    viz.finalize(best_params=all_params[best_idx], best_spearman=best_sp, best_pearson=best_pr)
    if output_dir is not None:
        viz.save(Path(output_dir) / "training_report.html")
        viz.save_json(Path(output_dir) / "training_history.json")
    viz.close()

    return all_params[best_idx].to(device)


# ── 辅助函数 ──────────────────────────────────────────────────────────


def _inv_softmax(probs):
    """Approximate inverse softmax."""
    p = np.array(probs, dtype=np.float32)
    p = np.clip(p, 1e-10, 1.0)
    return np.log(p) - np.log(p).mean()


def _get_default_params_tensor(device):
    """Default v3 weights converted to parameter tensor."""
    params = []
    for row in POSITION_DIMENSION_PRIOR:
        params.extend(_inv_softmax(row))
    for row in ATTACK_WEIGHT_PRIOR:
        params.extend(_inv_softmax(row))
    params.extend(_inv_softmax([0.45, 0.25, 0.20, 0.10]))
    params.extend(_inv_softmax(QUALITY_SUBWEIGHT_PRIOR))
    params.extend([1.0, 0.0, 0.0])  # league_log_scale, rel_min, rel_starts
    # trend_weight (sigmoid=0.5 -> 5), experience_weight (sigmoid=0.5 -> 2.5)
    params.extend([0.0, 0.0])
    return torch.tensor(params, dtype=torch.float32, device=device)

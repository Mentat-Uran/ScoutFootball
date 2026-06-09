"""
交叉验证与参数稳定性模块 — expanding-window CV、多 seed 稳定性测试、指标输出。

从 optimize_ratings_gpu.py (3191-3472 行) 提取。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import evaluate_params, _filter_by_seasons, make_season_splits
from .optimization import optimize, _get_default_params_tensor
from .scoring import build_feature_tensors
from .data import fit_team_points_calibrator


# ── 交叉验证 ───────────────────────────────────────────────────────────


def run_cross_validation(
    df,
    team_pts,
    device,
    *,
    n_splits=3,
    test_seasons=1,
    min_train_seasons=2,
    gap_seasons=0,
    n_steps=150,
    lr=0.035,
    pop_size=8,
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
    dc_likelihood_weight=0.00,
    dc_tensors=None,
    init_scale=0.35,
    patience=40,
    warmup_steps=20,
    min_lr_ratio=0.08,
    grad_clip=5.0,
    seed=42,
    calibration_bins=5,
    league_calibration_prior_n=60.0,
    league_calibration_cap=8.0,
    disable_league_calibration=False,
):
    """Run expanding-window CV; each fold optimizes only on its train seasons."""
    splits = make_season_splits(
        df,
        n_splits=n_splits,
        test_seasons=test_seasons,
        min_train_seasons=min_train_seasons,
        gap_seasons=gap_seasons,
    )
    default_params = _get_default_params_tensor(device)
    rows = []
    for fold_idx, split in enumerate(splits, start=1):
        print(
            f"\n  CV {split.name}: train={list(split.train_seasons)} "
            f"test={list(split.test_seasons)}"
        )
        train_df = _filter_by_seasons(df, split.train_seasons)
        test_df = _filter_by_seasons(df, split.test_seasons)
        train_team_pts = _filter_by_seasons(team_pts, split.train_seasons)
        test_team_pts = _filter_by_seasons(team_pts, split.test_seasons)
        train_feat = build_feature_tensors(train_df)
        fold_params = optimize(
            train_feat,
            train_team_pts,
            device,
            n_steps=n_steps,
            lr=lr,
            pop_size=pop_size,
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
            prior_strength=prior_strength,
            dc_likelihood_weight=dc_likelihood_weight,
            dc_tensors=dc_tensors,
            init_scale=init_scale,
            patience=patience,
            warmup_steps=warmup_steps,
            min_lr_ratio=min_lr_ratio,
            grad_clip=grad_clip,
            seed=seed + fold_idx,
        )
        for model_name, params in [("baseline_v3", default_params), ("optimized", fold_params)]:
            train_raw = evaluate_params(
                params,
                train_df,
                train_team_pts,
                train_df,
                device,
                split_name="train",
                calibration_bins=calibration_bins,
            )
            points_calibrator = fit_team_points_calibrator(
                train_raw["matched"],
                use_league_offsets=not disable_league_calibration,
                league_prior_n=league_calibration_prior_n,
                league_offset_cap=league_calibration_cap,
            )
            for split_name, eval_df, eval_team_pts in [
                ("train", train_df, train_team_pts),
                ("test", test_df, test_team_pts),
            ]:
                evaluation = evaluate_params(
                    params,
                    eval_df,
                    eval_team_pts,
                    train_df,
                    device,
                    split_name=split_name,
                    calibration_bins=calibration_bins,
                    points_calibrator=points_calibrator,
                )
                row = {
                    "fold": fold_idx,
                    "fold_name": split.name,
                    "model": model_name,
                    "split": split_name,
                    "train_seasons": ",".join(split.train_seasons),
                    "test_seasons": ",".join(split.test_seasons),
                }
                row.update(evaluation["metrics"])
                rows.append(row)
    return pd.DataFrame(rows)


# ── 参数稳定性测试 ─────────────────────────────────────────────────────


def run_parameter_stability(
    train_df,
    test_df,
    train_team_pts,
    test_team_pts,
    device,
    *,
    n_runs=3,
    n_steps=150,
    lr=0.035,
    pop_size=8,
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
    dc_likelihood_weight=0.00,
    dc_tensors=None,
    init_scale=0.35,
    patience=40,
    warmup_steps=20,
    min_lr_ratio=0.08,
    grad_clip=5.0,
    seed=42,
    calibration_bins=5,
    league_calibration_prior_n=60.0,
    league_calibration_cap=8.0,
    disable_league_calibration=False,
):
    """Repeat optimization across seeds and summarize metric/parameter variance."""
    if n_runs <= 1:
        return pd.DataFrame(), {}

    train_feat = build_feature_tensors(train_df)
    rows = []
    params_rows = []
    for run_idx in range(n_runs):
        run_seed = seed + run_idx * 101
        print(f"\n  稳定性 run {run_idx + 1}/{n_runs}: seed={run_seed}")
        params = optimize(
            train_feat,
            train_team_pts,
            device,
            n_steps=n_steps,
            lr=lr,
            pop_size=pop_size,
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
            prior_strength=prior_strength,
            dc_likelihood_weight=dc_likelihood_weight,
            dc_tensors=dc_tensors,
            init_scale=init_scale,
            patience=patience,
            warmup_steps=warmup_steps,
            min_lr_ratio=min_lr_ratio,
            grad_clip=grad_clip,
            seed=run_seed,
        )
        train_raw = evaluate_params(
            params,
            train_df,
            train_team_pts,
            train_df,
            device,
            split_name="train",
            calibration_bins=calibration_bins,
        )
        points_calibrator = fit_team_points_calibrator(
            train_raw["matched"],
            use_league_offsets=not disable_league_calibration,
            league_prior_n=league_calibration_prior_n,
            league_offset_cap=league_calibration_cap,
        )
        train_eval = evaluate_params(
            params,
            train_df,
            train_team_pts,
            train_df,
            device,
            split_name="train",
            calibration_bins=calibration_bins,
            points_calibrator=points_calibrator,
        )
        test_eval = evaluate_params(
            params,
            test_df,
            test_team_pts,
            train_df,
            device,
            split_name="test",
            calibration_bins=calibration_bins,
            points_calibrator=points_calibrator,
        )
        rows.append(
            {
                "run": run_idx + 1,
                "seed": run_seed,
                "train_spearman": train_eval["metrics"]["spearman"],
                "test_spearman": test_eval["metrics"]["spearman"],
                "train_rank_loss": train_eval["metrics"]["rank_loss"],
                "test_rank_loss": test_eval["metrics"]["rank_loss"],
                "overfit_rank_loss_gap": (
                    test_eval["metrics"]["rank_loss"] - train_eval["metrics"]["rank_loss"]
                ),
            },
        )
        params_rows.append(params.detach().cpu().numpy())

    stability_df = pd.DataFrame(rows)
    params_matrix = np.vstack(params_rows)
    param_std = np.std(params_matrix, axis=0)
    summary = {
        "runs": int(n_runs),
        "test_spearman_mean": float(stability_df["test_spearman"].mean()),
        "test_spearman_std": float(stability_df["test_spearman"].std(ddof=0)),
        "test_spearman_min": float(stability_df["test_spearman"].min()),
        "test_spearman_max": float(stability_df["test_spearman"].max()),
        "param_std_mean": float(np.mean(param_std)),
        "param_std_max": float(np.max(param_std)),
    }
    return stability_df, summary


# ── 指标输出 ──────────────────────────────────────────────────────────


def _print_metric_block(title, baseline_eval, optimized_eval):
    base = baseline_eval["metrics"]
    opt = optimized_eval["metrics"]
    print(f"\n{title}")
    print("-" * 80)
    print(
        "  baseline_v3: "
        f"Spearman={base['spearman']:.4f}  Pearson={base['pearson']:.4f}  "
        f"rank_loss={base['rank_loss']:.4f}  calib_MAE={base['calibration_mae']:.2f}  "
        f"points_MAE={base['points_mae']:.2f}  "
        f"raw_spread={base['raw_spread_ratio']:.2f}  "
        f"N={base['n_team_seasons']}"
    )
    print(
        "  optimized:   "
        f"Spearman={opt['spearman']:.4f}  Pearson={opt['pearson']:.4f}  "
        f"rank_loss={opt['rank_loss']:.4f}  calib_MAE={opt['calibration_mae']:.2f}  "
        f"points_MAE={opt['points_mae']:.2f}  "
        f"raw_spread={opt['raw_spread_ratio']:.2f}  "
        f"N={opt['n_team_seasons']}"
    )
    print(
        "  improvement: "
        f"Spearman {opt['spearman'] - base['spearman']:+.4f}  "
        f"rank_loss {opt['rank_loss'] - base['rank_loss']:+.4f}"
    )

#!/usr/bin/env python3
"""
球员评分权重优化器 — PyTorch GPU 版本
在 Windows + RTX 5070 Ti 上运行，几秒完成一次优化循环。

使用方法 (Windows):
  1. pip install torch pandas numpy scipy pyarrow matplotlib
  2. 把 data/ 目录复制到 Windows 机器上
  3. python optimize_ratings_gpu.py --data_dir ./data

Mac 快速模式 (几分钟完成):
  python optimize_ratings_gpu.py --data_dir ./data --quick

  --quick 自动降低: steps=80, pop=6, patience=15, 跳过 CV/稳定性/重要性。
  如需进一步加速: --quick --steps 40 --pop 3

Mac 完整模式 (较慢但更准):
  python optimize_ratings_gpu.py --data_dir ./data --steps 150 --pop 8 --patience 25

模块结构 (scripts/optimizer/):
  optimizer/__init__.py   - 包入口，导出 viz 和核心类
  optimizer/constants.py  - 队名别名、位置映射、配置常量
  optimizer/data.py       - 数据加载、评估指标、校准、dc_tensors 构建
  optimizer/scoring.py    - 评分计算、张量构建、球队聚合、缺失标记
  optimizer/losses.py     - 损失函数、Dixon-Coles、复合目标
  optimizer/optimization.py - 优化循环、学习率调度
  optimizer/cv.py         - 交叉验证、参数稳定性
  optimizer/viz.py        - 训练可视化 (Plotly/Console)
"""

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

# ── 从 optimizer 包导入所有辅助函数 ──────────────────────────────────────
from optimizer.constants import (
    N_ATK,
    N_DIM,
    N_POS,
    POSITIONS,
    apply_position_weight_caps,
)
from optimizer.cv import _print_metric_block, run_cross_validation, run_parameter_stability
from optimizer.data import (
    _filter_by_seasons,
    build_dc_tensors,
    compute_error_cases,
    compute_input_hash,
    evaluate_params,
    fit_team_points_calibrator,
    league_metrics,
    load_data,
    make_holdout_split,
    permutation_feature_importance,
    save_model_run,
    summarize_optimizer_data_coverage,
)
from optimizer.optimization import _get_default_params_tensor, optimize
from optimizer.scoring import build_feature_tensors
from optimizer.truth import build_truth_label_anchor


def main():
    parser = argparse.ArgumentParser(description="球员评分权重优化器 (GPU)")
    parser.add_argument("--data_dir", type=str, default="./data",
                        help="数据目录路径 (包含 raw/ 和 gold/)")
    parser.add_argument("--steps", type=int, default=500, help="每组优化步数")
    parser.add_argument("--lr", type=float, default=0.035, help="初始学习率")
    parser.add_argument("--pop", type=int, default=32, help="种群大小 (并行起点数)")
    parser.add_argument("--spearman-weight", type=float, default=0.30,
                        help="Spearman/Pearson 排名损失在复合目标中的权重")
    parser.add_argument("--soft-rank-temperature", type=float, default=4.0,
                        help="soft-rank 温度；越小越接近硬排名但梯度更容易饱和")
    parser.add_argument("--ndcg-weight", type=float, default=0.12,
                        help="NDCG@20 损失在复合目标中的权重")
    parser.add_argument("--position-consistency-weight", type=float, default=0.10,
                        help="位置核心指标一致性损失在复合目标中的权重")
    parser.add_argument("--points-regression-weight", type=float, default=0.20,
                        help="训练集校准后球队积分回归损失在复合目标中的权重")
    parser.add_argument("--distribution-weight", type=float, default=0.05,
                        help="校准后积分分布匹配损失在复合目标中的权重")
    parser.add_argument("--quantile-weight", type=float, default=0.08,
                        help="预测分布分位数匹配损失权重")
    parser.add_argument("--range-penalty-weight", type=float, default=0.10,
                        help="预测范围压缩惩罚权重")
    parser.add_argument("--tail-calibration-weight", type=float, default=0.08,
                        help="争冠/降级尾部球队校准损失在复合目标中的权重")
    parser.add_argument("--league-bias-weight", type=float, default=0.05,
                        help="训练集联赛平均积分残差惩罚在复合目标中的权重")
    parser.add_argument("--extreme-penalty-weight", type=float, default=0.02,
                        help="球员评分离群 guardrail 在复合目标中的权重")
    parser.add_argument("--truth-label-weight", type=float, default=0.08,
                        help="球员真值标签锚定损失权重；标签不足时自动禁用")
    parser.add_argument("--min-truth-labels", type=int, default=50,
                        help="启用球员真值标签锚定所需的最少训练集匹配标签数")
    parser.add_argument("--disable-truth-label-anchor", action="store_true",
                        help="禁用 player_truth_labels.parquet 的球员级监督锚定")
    parser.add_argument("--prior-weight", type=float, default=0.01,
                        help="锚定 v3 默认权重的正则强度")
    parser.add_argument("--dc-likelihood-weight", type=float, default=0.00,
                        help="Dixon-Coles 对数似然损失权重 (需要 Football-Data 比赛数据)")
    parser.add_argument("--dc-rho", type=float, default=-0.13,
                        help="Dixon-Coles 低比分相关性修正参数 (典型范围 -0.1 ~ -0.2)")
    parser.add_argument("--prior-strength", type=float, default=None,
                        help="锚定 v3 默认权重的正则强度 (deprecated, use --prior-weight)")
    parser.add_argument("--init-scale", type=float, default=0.35,
                        help="多起点围绕 v3 默认参数的随机扰动标准差")
    parser.add_argument("--patience", type=int, default=80, help="单个起点的 early-stop 耐心步数")
    parser.add_argument("--warmup-steps", type=int, default=20, help="学习率线性 warmup 步数")
    parser.add_argument("--min-lr-ratio", type=float, default=0.08,
                        help="余弦衰减后的最小学习率比例")
    parser.add_argument("--grad-clip", type=float, default=5.0,
                        help="梯度裁剪阈值；<=0 表示禁用")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--test-seasons", type=int, default=1, help="最终 holdout 使用最近几个赛季")
    parser.add_argument("--min-train-seasons", type=int, default=2,
                        help="每个时间切分最少训练赛季数")
    parser.add_argument("--gap-seasons", type=int, default=0, help="训练和测试之间跳过的赛季数")
    parser.add_argument("--cv-folds", type=int, default=3,
                        help="时间序列交叉验证 fold 数；0 表示跳过")
    parser.add_argument("--cv-steps", type=int, default=None, help="CV 每 fold 优化步数")
    parser.add_argument("--cv-pop", type=int, default=None, help="CV 每 fold 起点数")
    parser.add_argument("--stability-runs", type=int, default=3, help="不同 seed 稳定性运行次数")
    parser.add_argument("--stability-steps", type=int, default=None, help="稳定性运行每次优化步数")
    parser.add_argument("--stability-pop", type=int, default=None, help="稳定性运行每次起点数")
    parser.add_argument("--importance-repeats", type=int, default=1, help="特征置换重要性重复次数")
    parser.add_argument("--calibration-bins", type=int, default=5, help="校准检查分箱数")
    parser.add_argument("--league-calibration-prior-n", type=float, default=60.0,
                        help="训练集联赛残差 offset 的收缩强度；越大越保守")
    parser.add_argument("--league-calibration-cap", type=float, default=8.0,
                        help="训练集联赛残差 offset 的绝对值上限")
    parser.add_argument("--disable-league-calibration", action="store_true",
                        help="禁用 train-fitted 联赛残差 offset，仅使用全局积分校准")
    parser.add_argument("--quick", action="store_true",
                        help="快速模式：大幅降低种群/步数/耐心，适合 Mac CPU/MPS 本地快速迭代")
    parser.add_argument("--no-viz", action="store_true",
                        help="禁用实时可视化（适用于无 GUI 环境或远程服务器）")
    args = parser.parse_args()

    # Quick mode: Mac-friendly defaults
    if args.quick:
        if args.steps == 500:
            args.steps = 80
        if args.pop == 32:
            args.pop = 6
        if args.patience == 80:
            args.patience = 15
        if args.warmup_steps == 20:
            args.warmup_steps = 8
        if args.cv_folds == 3:
            args.cv_folds = 0
        if args.stability_runs == 3:
            args.stability_runs = 0
        if args.importance_repeats == 1:
            args.importance_repeats = 0

    # Backward compatibility: --prior-strength overrides --prior-weight if set
    if args.prior_strength is not None:
        args.prior_weight = args.prior_strength

    data_dir = Path(args.data_dir).resolve()
    print("=" * 80)
    print("球员评分权重优化器 (PyTorch GPU)")
    print("=" * 80)

    # Device
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"\nGPU: {torch.cuda.get_device_name(0)}")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
        print("\nApple MPS (Metal)")
    else:
        device = torch.device("cpu")
        print("\nCPU (没有 GPU 加速)")

    # Load data
    print("\n[1] 加载数据...")
    t0 = time.time()
    data_load_result = load_data(data_dir)
    if len(data_load_result) == 3:
        df, team_pts, matches_df = data_load_result
    else:
        df, team_pts = data_load_result
        matches_df = None
    data_coverage = summarize_optimizer_data_coverage(df)
    print(
        "  data coverage: "
        + ", ".join(
            f"{item['source_name']}={item['rows']} rows "
            f"(starts observed={item['starts_observed_rows']})"
            for item in data_coverage["sources"]
        )
    )
    for status in data_coverage["artifact_statuses"]:
        if status["status"] != "loaded":
            print(
                f"  optional source {status['source']}: {status['status']} "
                f"({status.get('error_type', 'not found')})"
            )

    # 出场标记：不足 20 场的球员仍参与评分，但不参与优化训练
    min_matches_opt = 20
    if "matches" in df.columns:
        df["low_appearance"] = df["matches"] < min_matches_opt
        n_low = df["low_appearance"].sum()
        print(f"  出场标记 (<{min_matches_opt}场): {n_low} 人标记为 low_appearance")

    print(f"  球员: {len(df)}, 球队赛季: {len(team_pts)}")
    print(f"  耗时: {time.time()-t0:.1f}s")

    # Build Dixon-Coles tensors (optional, for dc_likelihood loss)
    # NOTE: built after time split so only train-season matches are included,
    # ensuring dc_tensors indices align with train_feat team_avgs.
    dc_tensors = None

    # Compute input hash for reproducibility
    feat_hash = compute_input_hash(data_dir)
    print(f"  输入哈希: {feat_hash}")

    print("\n[2] 时间切分...")
    holdout = make_holdout_split(
        df,
        test_seasons=args.test_seasons,
        min_train_seasons=args.min_train_seasons,
        gap_seasons=args.gap_seasons,
    )
    train_df = _filter_by_seasons(df, holdout.train_seasons)
    test_df = _filter_by_seasons(df, holdout.test_seasons)
    train_team_pts = _filter_by_seasons(team_pts, holdout.train_seasons)
    test_team_pts = _filter_by_seasons(team_pts, holdout.test_seasons)

    # 优化训练排除 low_appearance 球员（仍参与最终评分）
    if "low_appearance" in train_df.columns:
        n_low_train = train_df["low_appearance"].sum()
        train_df = train_df[~train_df["low_appearance"]].copy()
        print(f"  训练集排除 low_appearance: {n_low_train} 人")

    print(f"  train seasons: {list(holdout.train_seasons)}")
    print(f"  test seasons:  {list(holdout.test_seasons)}")
    print(f"  train players={len(train_df)}, test players={len(test_df)}")

    print("\n[3] 基线 (v3 默认权重, 不训练)...")
    default_params = _get_default_params_tensor(device)
    baseline_train_raw_eval = evaluate_params(
        default_params, train_df, train_team_pts, train_df, device,
        split_name="train", calibration_bins=args.calibration_bins,
    )
    baseline_points_calibrator = fit_team_points_calibrator(
        baseline_train_raw_eval["matched"],
        use_league_offsets=not args.disable_league_calibration,
        league_prior_n=args.league_calibration_prior_n,
        league_offset_cap=args.league_calibration_cap,
    )
    baseline_train_eval = evaluate_params(
        default_params, train_df, train_team_pts, train_df, device,
        split_name="train", calibration_bins=args.calibration_bins,
        points_calibrator=baseline_points_calibrator,
    )
    baseline_test_eval = evaluate_params(
        default_params, test_df, test_team_pts, train_df, device,
        split_name="test", calibration_bins=args.calibration_bins,
        points_calibrator=baseline_points_calibrator,
    )
    print(
        f"  train Spearman={baseline_train_eval['metrics']['spearman']:.4f}  "
        f"test Spearman={baseline_test_eval['metrics']['spearman']:.4f}"
    )

    print(f"\n[4] 只在训练赛季优化 (pop={args.pop}, steps={args.steps}, lr={args.lr})...")
    t0 = time.time()
    train_feat = build_feature_tensors(train_df)

    # Build DC tensors from train_feat (not full df) so indices align with team_avgs
    if args.dc_likelihood_weight > 0 and matches_df is not None:
        train_matches = matches_df[
            matches_df["season"].astype(str).isin(holdout.train_seasons)
        ].copy() if "season" in matches_df.columns else matches_df
        dc_tensors = build_dc_tensors(train_feat, train_matches, device)
        if dc_tensors:
            print(f"  Dixon-Coles (train only): {dc_tensors['n_matches']} 场比赛已映射")
        else:
            print("  Dixon-Coles: 无训练赛季比赛可映射，dc_likelihood 已禁用")

    truth_anchor = None
    if args.truth_label_weight > 0 and not args.disable_truth_label_anchor:
        truth_anchor = build_truth_label_anchor(
            data_dir,
            train_df,
            device,
            min_labels=args.min_truth_labels,
        )
        if truth_anchor.get("enabled"):
            print(
                "  球员真值标签锚定: "
                f"matched={truth_anchor.get('n_matched')} "
                f"resolved={truth_anchor.get('n_labels')}"
            )
        else:
            print(f"  球员真值标签锚定跳过: {truth_anchor.get('reason')}")
    best_params = optimize(
        train_feat, train_team_pts, device,
        n_steps=args.steps, lr=args.lr, pop_size=args.pop,
        spearman_weight=args.spearman_weight,
        soft_rank_temperature=args.soft_rank_temperature,
        ndcg_weight=args.ndcg_weight,
        position_consistency_weight=args.position_consistency_weight,
        points_regression_weight=args.points_regression_weight,
        distribution_weight=args.distribution_weight,
        quantile_weight=args.quantile_weight,
        range_penalty_weight=args.range_penalty_weight,
        tail_calibration_weight=args.tail_calibration_weight,
        league_bias_weight=args.league_bias_weight,
        extreme_penalty_weight=args.extreme_penalty_weight,
        truth_label_weight=args.truth_label_weight if truth_anchor else 0.0,
        prior_strength=args.prior_weight,
        dc_likelihood_weight=args.dc_likelihood_weight,
        dc_tensors=dc_tensors,
        dc_rho=args.dc_rho,
        truth_anchor=truth_anchor,
        init_scale=args.init_scale, patience=args.patience,
        warmup_steps=args.warmup_steps, min_lr_ratio=args.min_lr_ratio,
        grad_clip=args.grad_clip, seed=args.seed,
        enable_viz=not args.no_viz,
        output_dir=data_dir / "gold" / "feature_store",
    )
    print(f"  总耗时: {time.time()-t0:.1f}s")

    optimized_train_raw_eval = evaluate_params(
        best_params, train_df, train_team_pts, train_df, device,
        split_name="train", calibration_bins=args.calibration_bins,
    )
    optimized_points_calibrator = fit_team_points_calibrator(
        optimized_train_raw_eval["matched"],
        use_league_offsets=not args.disable_league_calibration,
        league_prior_n=args.league_calibration_prior_n,
        league_offset_cap=args.league_calibration_cap,
    )
    optimized_train_eval = evaluate_params(
        best_params, train_df, train_team_pts, train_df, device,
        split_name="train", calibration_bins=args.calibration_bins,
        points_calibrator=optimized_points_calibrator,
    )
    optimized_test_eval = evaluate_params(
        best_params, test_df, test_team_pts, train_df, device,
        split_name="test", calibration_bins=args.calibration_bins,
        points_calibrator=optimized_points_calibrator,
    )

    print("\n[5] Train/Test 对比:")
    _print_metric_block("  训练集", baseline_train_eval, optimized_train_eval)
    _print_metric_block("  Holdout 测试集", baseline_test_eval, optimized_test_eval)
    overfit_gap = (
        optimized_test_eval["metrics"]["rank_loss"] - optimized_train_eval["metrics"]["rank_loss"]
    )
    print(f"\n  过拟合检查: test_rank_loss - train_rank_loss = {overfit_gap:+.4f}")

    print("\n[6] 优化后权重:")
    print("-" * 80)
    best_params_cpu = best_params.detach().cpu()
    pw_raw = best_params_cpu[:N_POS * N_DIM].reshape(N_POS, N_DIM)
    pw = apply_position_weight_caps(torch.softmax(pw_raw, dim=1)).cpu().numpy()
    print(f"{'位置':<5} {'出勤':>7} {'进攻':>7} {'防守':>7} {'控球':>7} {'质量':>7}")
    print("-" * 80)
    for i, pos in enumerate(POSITIONS):
        row = f"{pos:<5}"
        for j in range(N_DIM):
            row += f" {pw[i,j]:>7.4f}"
        print(row)

    aw_raw = best_params_cpu[N_POS * N_DIM:N_POS * N_DIM + N_POS * N_ATK].reshape(N_POS, N_ATK)
    aw = torch.softmax(aw_raw, dim=1).cpu().numpy()
    print(f"\n{'位置':<5} {'npxG_p90':>9} {'ast_p90':>9} {'G+A_vol':>9}")
    print("-" * 40)
    for i, pos in enumerate(POSITIONS):
        print(f"{pos:<5} {aw[i,0]:>9.4f} {aw[i,1]:>9.4f} {aw[i,2]:>9.4f}")

    print("\n[7] Holdout 球队覆盖率:")
    holdout_coverage = optimized_test_eval["coverage"]
    if holdout_coverage.empty:
        print("  没有可报告的球队覆盖率")
    else:
        for _, row in holdout_coverage.iterrows():
            print(
                f"  {row['league']:<22} {row['season']:<8} "
                f"matched={int(row['matched_teams']):>2}/{int(row['target_teams']):<2} "
                f"rated={int(row['rated_teams']):>2} coverage={row['coverage']:.2f}"
            )

    print("\n[8] Holdout 联赛分层评估:")
    holdout_league_metrics = league_metrics(
        optimized_test_eval["matched"], min_n=5, calibration_bins=args.calibration_bins,
    )
    if holdout_league_metrics.empty:
        print("  样本不足，未生成联赛分层指标")
    else:
        for _, row in holdout_league_metrics.iterrows():
            print(
                f"  {row['league']:<22} Spearman={row['spearman']:.3f}  "
                f"Pearson={row['pearson']:.3f}  calib_MAE={row['calibration_mae']:.2f}  "
                f"N={int(row['n_team_seasons'])}"
            )

    print("\n[9] Holdout 校准检查:")
    calibration_test = optimized_test_eval["calibration"]
    for _, row in calibration_test.iterrows():
        print(
            f"  bin={int(row['bin']) if pd.notna(row['bin']) else -1} "
            f"N={int(row['n'])} pred_pct={row['pred_percentile_mean']:.1f} "
            f"actual_pct={row['actual_percentile_mean']:.1f} gap={row['calibration_gap']:+.1f}"
        )

    cv_metrics = pd.DataFrame()
    cv_error = None
    if args.cv_folds > 0:
        print("\n[10] 时间序列交叉验证:")
        try:
            cv_metrics = run_cross_validation(
                df, team_pts, device,
                n_splits=args.cv_folds, test_seasons=args.test_seasons,
                min_train_seasons=args.min_train_seasons, gap_seasons=args.gap_seasons,
                n_steps=args.cv_steps or max(50, args.steps // 3),
                lr=args.lr, pop_size=args.cv_pop or max(2, args.pop // 4),
                spearman_weight=args.spearman_weight,
                soft_rank_temperature=args.soft_rank_temperature,
                ndcg_weight=args.ndcg_weight,
                position_consistency_weight=args.position_consistency_weight,
                points_regression_weight=args.points_regression_weight,
                distribution_weight=args.distribution_weight,
                quantile_weight=args.quantile_weight,
                range_penalty_weight=args.range_penalty_weight,
                tail_calibration_weight=args.tail_calibration_weight,
                league_bias_weight=args.league_bias_weight,
                extreme_penalty_weight=args.extreme_penalty_weight,
                prior_strength=args.prior_weight,
                dc_likelihood_weight=args.dc_likelihood_weight,
                dc_tensors=dc_tensors,
                init_scale=args.init_scale,
                patience=min(args.patience, 40),
                warmup_steps=min(
                    args.warmup_steps,
                    max(1, (args.cv_steps or max(50, args.steps // 3)) // 5),
                ),
                min_lr_ratio=args.min_lr_ratio, grad_clip=args.grad_clip,
                seed=args.seed, calibration_bins=args.calibration_bins,
                league_calibration_prior_n=args.league_calibration_prior_n,
                league_calibration_cap=args.league_calibration_cap,
                disable_league_calibration=args.disable_league_calibration,
            )
            cv_test = cv_metrics.loc[
                (cv_metrics["model"] == "optimized") & (cv_metrics["split"] == "test")
            ]
            base_test = cv_metrics.loc[
                (cv_metrics["model"] == "baseline_v3") & (cv_metrics["split"] == "test")
            ]
            print(
                f"  optimized test Spearman: mean={cv_test['spearman'].mean():.4f}, "
                f"std={cv_test['spearman'].std(ddof=0):.4f}"
            )
            print(
                f"  baseline_v3 test Spearman: mean={base_test['spearman'].mean():.4f}, "
                f"std={base_test['spearman'].std(ddof=0):.4f}"
            )
        except ValueError as error:
            cv_error = str(error)
            print(f"  跳过 CV: {cv_error}")

    stability_df = pd.DataFrame()
    stability_summary = {}
    if args.stability_runs > 1:
        print("\n[11] 参数稳定性:")
        stability_df, stability_summary = run_parameter_stability(
            train_df, test_df, train_team_pts, test_team_pts, device,
            n_runs=args.stability_runs,
            n_steps=args.stability_steps or max(50, args.steps // 3),
            lr=args.lr, pop_size=args.stability_pop or max(2, args.pop // 4),
            spearman_weight=args.spearman_weight,
            soft_rank_temperature=args.soft_rank_temperature,
            ndcg_weight=args.ndcg_weight,
            position_consistency_weight=args.position_consistency_weight,
            points_regression_weight=args.points_regression_weight,
            distribution_weight=args.distribution_weight,
            quantile_weight=args.quantile_weight,
            range_penalty_weight=args.range_penalty_weight,
            tail_calibration_weight=args.tail_calibration_weight,
            league_bias_weight=args.league_bias_weight,
            extreme_penalty_weight=args.extreme_penalty_weight,
            prior_strength=args.prior_weight,
            dc_likelihood_weight=args.dc_likelihood_weight,
            dc_tensors=dc_tensors,
            init_scale=args.init_scale,
            patience=min(args.patience, 40),
            warmup_steps=min(
                args.warmup_steps,
                max(1, (args.stability_steps or max(50, args.steps // 3)) // 5),
            ),
            min_lr_ratio=args.min_lr_ratio, grad_clip=args.grad_clip, seed=args.seed,
        )
        if stability_summary:
            print(f"  runs: {stability_summary.get('runs', '?')}")
            print(f"  test Spearman: mean={stability_summary.get('test_spearman_mean', 0):.4f}, "
                  f"std={stability_summary.get('test_spearman_std', 0):.4f}")

    # Feature importance
    if args.importance_repeats > 0:
        print("\n[12] 特征置换重要性:")
        importance = permutation_feature_importance(
            best_params, test_df, test_team_pts, train_df, device,
            n_repeats=args.importance_repeats, calibration_bins=args.calibration_bins,
        )
        for _, row in importance.iterrows():
            print(f"  {row['feature']:<20s} drop={row['spearman_drop_mean']:+.4f}")

    # Save outputs
    print("\n[13] 保存输出...")
    output_dir = data_dir / "gold" / "feature_store"
    output_dir.mkdir(parents=True, exist_ok=True)

    np.save(output_dir / "optimized_params.npy", best_params_cpu.numpy())

    # Build metrics dict for save_model_run
    metrics = {
        "baseline_train": baseline_train_eval["metrics"],
        "baseline_test": baseline_test_eval["metrics"],
        "optimized_train": optimized_train_eval["metrics"],
        "optimized_test": optimized_test_eval["metrics"],
        "overfit_rank_loss_gap": overfit_gap,
    }

    save_model_run(
        params=best_params_cpu.numpy(),
        metrics=metrics,
        args=args,
        feat_hash=feat_hash,
        data_dir=data_dir,
        data_coverage=data_coverage,
        error_cases=compute_error_cases(optimized_test_eval["matched"]),
    )

    print(f"\n{'='*80}")
    print("完成!")
    print(f"  optimized_params.npy: {output_dir / 'optimized_params.npy'}")
    print(f"  optimized_params_meta.json: {output_dir / 'optimized_params_meta.json'}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()

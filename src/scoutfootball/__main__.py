"""CLI entrypoint for ScoutFootball pipeline operations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from scoutfootball.architecture import build_default_architecture


def _cmd_info(_args: argparse.Namespace) -> None:
    architecture = build_default_architecture()
    lines = [
        f"package: {architecture.package_name}",
        f"status: {architecture.status}",
        "modules:",
    ]
    lines.extend(
        f"  - {module.name}: {module.purpose}" for module in architecture.module_boundaries
    )
    lines.append("commands:")
    lines.extend(f"  - {command}" for command in architecture.supported_commands)
    print("\n".join(lines))


def _cmd_ingest(args: argparse.Namespace) -> None:
    from scoutfootball.pipeline import run_daily_ingest

    results = run_daily_ingest(sources=tuple(args.sources))
    for source, status in results.items():
        print(f"  {source}: {status}")


def _cmd_build_features(_args: argparse.Namespace) -> None:
    from scoutfootball.pipeline import run_build_features

    results = run_build_features()
    for feature_set, status in results.items():
        print(f"  {feature_set}: {status}")


def _cmd_train(_args: argparse.Namespace) -> None:
    from scoutfootball.pipeline import run_weekly_train

    results = run_weekly_train(skip_if_validation_fails=False)
    for model, status in results.items():
        print(f"  {model}: {status}")


def _cmd_train_rating_nn(args: argparse.Namespace) -> None:
    from scoutfootball.models.player_rating_nn import (
        PlayerRatingNNConfig,
        train_player_rating_nn_from_files,
    )

    result = train_player_rating_nn_from_files(
        config=PlayerRatingNNConfig(
            min_labels=args.min_labels,
            max_iter=args.max_iter,
            random_state=args.seed,
        ),
        output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
    )
    print(result.status)
    if result.metrics:
        print(json.dumps(result.metrics, indent=2, ensure_ascii=False))


def _cmd_validate(_args: argparse.Namespace) -> None:
    from scoutfootball.evaluation.validation import run_pre_training_validation

    report = run_pre_training_validation()
    print(report.summary())


def _cmd_import_truth_labels(args: argparse.Namespace) -> None:
    """Import scouting workspace review decisions as truth labels."""
    import json as _json
    from pathlib import Path as _Path

    from scoutfootball.evaluation.truth_labels import (
        validate_truth_labels,
        workspace_to_truth_labels,
    )

    workspace_path = _Path(args.workspace).resolve()
    if not workspace_path.exists():
        print(f"Error: workspace file not found: {workspace_path}")
        sys.exit(1)

    with open(workspace_path, encoding="utf-8") as f:
        workspace = _json.load(f)

    new_labels = workspace_to_truth_labels(
        workspace,
        default_season=args.season or "",
        default_position_scope=args.position_scope or "all",
    )

    if new_labels.empty:
        print("No approved/rejected decisions found in workspace. Nothing to import.")
        return

    # Merge with existing truth labels if present
    output_path = _Path(args.output).resolve()
    if output_path.exists():
        existing = pd.read_parquet(output_path)
        # Remove old scouting_review labels for the same player_ids to avoid duplicates
        if not existing.empty:
            new_ids = set(new_labels["player_id"].unique())
            mask = ~(
                (existing["label_source"] == "scouting_review")
                & (existing["player_id"].isin(new_ids))
            )
            existing = existing[mask]
            combined = pd.concat([existing, new_labels], ignore_index=True)
        else:
            combined = new_labels
    else:
        combined = new_labels
        output_path.parent.mkdir(parents=True, exist_ok=True)

    errors = validate_truth_labels(combined)
    if errors:
        print("Validation errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    combined.to_parquet(output_path, index=False)
    print(f"Imported {len(new_labels)} scouting review labels to {output_path}")
    print(f"  Approved: {(new_labels['label_value'] == 1.0).sum()}")
    print(f"  Rejected: {(new_labels['label_value'] == 0.0).sum()}")
    print(f"  Total labels in file: {len(combined)}")


def _cmd_serve(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. Run: uv add uvicorn")
        sys.exit(1)

    from scoutfootball.api_server import create_app

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)


def _cmd_action_value(args: argparse.Namespace) -> None:
    from scoutfootball.action_value.aggregate import (
        build_player_action_value,
        save_player_action_value,
    )
    from scoutfootball.action_value.spadl_adapter import convert_all_events_to_actions

    project_root = Path(__file__).resolve().parents[2]
    events_path = Path(args.events_path) if args.events_path else (
        project_root / "data" / "raw" / "statsbomb_open" / "events_all.parquet"
    )
    output_path = Path(args.output_path) if args.output_path else (
        project_root / "data" / "gold" / "feature_store" / "player_value_metrics.parquet"
    )

    if not events_path.exists():
        print(f"Error: Events file not found: {events_path}")
        sys.exit(1)

    # Load events for both conversion and shot/xG stats
    events_df = pd.read_parquet(events_path)
    print(f"  Loaded {len(events_df)} events from {events_path}")

    # Convert to InternalActions
    actions = convert_all_events_to_actions(events_path)
    print(f"  Converted to {len(actions)} internal actions")

    if not actions:
        print("Error: No actions converted from events.")
        sys.exit(1)

    # Build player name mapping
    player_names = {}
    if "player_id" in events_df.columns and "player_name" in events_df.columns:
        name_map = (
            events_df.dropna(subset=["player_id", "player_name"])
            .drop_duplicates("player_id")
        )
        for _, row in name_map.iterrows():
            pid = str(int(float(row["player_id"])))
            player_names[pid] = row["player_name"]

    # Compute xT and aggregate
    result = build_player_action_value(
        actions=actions,
        events_df=events_df,
        player_names=player_names,
    )

    if result.empty:
        print("Error: No player action values computed.")
        sys.exit(1)

    # Save
    save_player_action_value(result, output_path)
    print(f"  Saved {len(result)} players to {output_path}")
    print("  Top players by composite score:")
    for _, row in result.head(5).iterrows():
        name = row.get("player_name", row.get("player_id", "?"))
        score = row.get("composite_score", 0)
        xt = row.get("total_xt", 0)
        print(f"    {name}: composite={score:.1f}, total_xT={xt:.4f}")


def _cmd_action_value_matches(args: argparse.Namespace) -> None:
    """Create the explicitly sample-bounded player-team-match xT artifact."""
    from scoutfootball.action_value.match_artifact import (
        build_player_match_action_values,
        save_player_match_action_values,
    )
    from scoutfootball.action_value.spadl_adapter import convert_all_events
    from scoutfootball.action_value.xt import compute_xt_values

    project_root = Path(__file__).resolve().parents[2]
    events_path = Path(args.events_path) if args.events_path else (
        project_root / "data" / "raw" / "statsbomb_open" / "events_sample.parquet"
    )
    matches_path = Path(args.matches_path) if args.matches_path else (
        project_root / "data" / "raw" / "statsbomb_open" / "big5_matches.parquet"
    )
    output_path = Path(args.output_path) if args.output_path else (
        project_root
        / "data"
        / "gold"
        / "feature_store"
        / "player_match_action_value_sample.parquet"
    )
    if not events_path.exists():
        print(f"Error: Events file not found: {events_path}")
        sys.exit(1)
    if not matches_path.exists():
        print(f"Error: Match metadata file not found: {matches_path}")
        sys.exit(1)

    events = pd.read_parquet(events_path)
    names = (
        events.dropna(subset=["player_id", "player_name"])
        .drop_duplicates("player_id")
        if {"player_id", "player_name"}.issubset(events.columns)
        else pd.DataFrame(columns=["player_id", "player_name"])
    )
    player_names = {
        str(int(float(row.player_id))): str(row.player_name)
        for row in names.itertuples(index=False)
    }
    actions = convert_all_events(events_path)
    if actions.empty:
        print("Error: No convertible actions in events file.")
        sys.exit(1)
    _, valued_actions = compute_xt_values(actions)
    artifact, manifest = build_player_match_action_values(
        valued_actions,
        pd.read_parquet(matches_path),
        coverage_scope=args.coverage_scope,
        player_names=player_names,
    )
    if artifact.empty:
        print("Error: No player-match xT rows computed.")
        sys.exit(1)
    save_player_match_action_values(artifact, manifest, output_path)
    print(f"Saved {len(artifact)} player-team-match rows to {output_path}")
    print(
        f"  coverage={manifest['coverage_scope']}; matches={manifest['match_count']}; "
        f"valued_actions={manifest['input_action_rows']}"
    )


def _cmd_export_ratings(_args: argparse.Namespace) -> None:
    from scoutfootball.storage.duckdb_io import create_ratings_database

    project_root = Path(__file__).resolve().parents[2]
    feature_store = project_root / "data" / "gold" / "feature_store"
    output_path = project_root / "data" / "gold" / "scoutlab.duckdb"

    # --- player_ratings ---
    ratings_path = feature_store / "player_ratings_optimized.parquet"
    if not ratings_path.exists():
        print("Error: player_ratings_optimized.parquet not found. Run 'scoutfootball train' first.")
        sys.exit(1)

    ratings_df = pd.read_parquet(ratings_path)
    available_cols = set(ratings_df.columns)

    # Rename sub_position -> position_group for consistent schema
    if "sub_position" in available_cols and "position_group" not in available_cols:
        ratings_df = ratings_df.rename(columns={"sub_position": "position_group"})
        available_cols.add("position_group")

    select_cols = [
        "player", "team", "league", "season", "position_group",
        "optimized_score", "minutes", "npg_p90", "assists_p90",
        "defense_composite", "possession_composite", "finishing_shrunk",
    ]
    present_cols = [c for c in select_cols if c in available_cols]
    player_ratings = ratings_df[present_cols].copy()

    minutes_col = "minutes" if "minutes" in player_ratings.columns else None
    if minutes_col:
        player_ratings["confidence_level"] = player_ratings[minutes_col].apply(
            lambda m: "high" if m >= 900 else ("medium" if m >= 450 else "low")
        )
    else:
        player_ratings["confidence_level"] = "low"

    # --- model_meta ---
    meta_path = feature_store / "optimized_params_meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        holdout = meta.get("holdout", {})
        opt_test = holdout.get("optimized_test", {})
        model_meta = pd.DataFrame([{
            "run_id": meta.get("timestamp", "unknown"),
            "timestamp": meta.get("timestamp", ""),
            "n_params": meta.get("n_params", 0),
            "spearman": opt_test.get("spearman", float("nan")),
            "pearson": opt_test.get("pearson", float("nan")),
            "overfit_gap": holdout.get("overfit_rank_loss_gap", float("nan")),
            "composite_weights": json.dumps({
                "spearman": meta.get("spearman_weight", 0.5),
                "ndcg": meta.get("ndcg_weight", 0.2),
                "position_consistency": meta.get("position_consistency_weight", 0.15),
                "extreme_penalty": meta.get("extreme_penalty_weight", 0.1),
                "prior": meta.get("prior_weight", 0.05),
            }),
        }])
    else:
        model_meta = pd.DataFrame(columns=[
            "run_id", "timestamp", "n_params", "spearman", "pearson",
            "overfit_gap", "composite_weights",
        ])

    # --- league_metrics ---
    league_path = feature_store / "rating_league_metrics.parquet"
    if league_path.exists():
        league_metrics = pd.read_parquet(league_path)
    else:
        league_metrics = pd.DataFrame(
            columns=["league", "spearman", "pearson", "n_teams", "coverage"]
        )

    # --- team_coverage ---
    coverage_path = feature_store / "rating_team_coverage.parquet"
    if coverage_path.exists():
        team_coverage = pd.read_parquet(coverage_path)
    else:
        team_coverage = pd.DataFrame(columns=[
            "league", "season", "n_target", "n_scored", "n_matched", "coverage", "confidence",
        ])

    create_ratings_database(output_path, player_ratings, model_meta, league_metrics, team_coverage)
    print(f"Ratings database written to {output_path}")
    print(f"  player_ratings: {len(player_ratings)} rows")
    print(f"  model_meta: {len(model_meta)} rows")
    print(f"  league_metrics: {len(league_metrics)} rows")
    print(f"  team_coverage: {len(team_coverage)} rows")


def _cmd_backtest(args: argparse.Namespace) -> None:
    from scoutfootball.evaluation.backtests import (
        run_dc_backtest_with_calibration,
        run_dixon_coles_backtest,
        run_poisson_backtest,
    )
    from scoutfootball.models import TimeSplitConfig

    project_root = Path(__file__).resolve().parents[2]
    raw_path = project_root / "data" / "raw" / "football_data" / "combined_results.parquet"
    out_dir = Path(args.output_dir).resolve() if args.output_dir else (
        project_root / "data" / "reports" / "calibration_backtest"
    )

    if not raw_path.exists():
        print(f"Error: Football-Data file not found: {raw_path}")
        sys.exit(1)

    raw = pd.read_parquet(raw_path)
    print(f"  Loaded {len(raw)} matches from {raw_path.name}")

    # Convert to team_match format
    from scoutfootball.entities.normalize import normalize_team_name

    df = raw[["HomeTeam", "AwayTeam", "FTHG", "FTAG", "Date", "season", "league"]].copy()
    df["match_date"] = pd.to_datetime(df["Date"], format="mixed", dayfirst=True, errors="coerce")
    df = df.dropna(subset=["match_date"])
    df["home_team"] = df["HomeTeam"].apply(normalize_team_name)
    df["away_team"] = df["AwayTeam"].apply(normalize_team_name)
    df = df.dropna(subset=["FTHG", "FTAG"])
    df["FTHG"] = df["FTHG"].astype(int)
    df["FTAG"] = df["FTAG"].astype(int)
    df["match_id"] = (
        df["home_team"] + "_v_" + df["away_team"] + "_" + df["match_date"].dt.strftime("%Y%m%d")
    )

    home_rows = pd.DataFrame({
        "match_id": df["match_id"], "match_date": df["match_date"],
        "team_id": df["home_team"], "is_home": True,
        "goals_for": df["FTHG"], "goals_against": df["FTAG"],
    })
    away_rows = pd.DataFrame({
        "match_id": df["match_id"], "match_date": df["match_date"],
        "team_id": df["away_team"], "is_home": False,
        "goals_for": df["FTAG"], "goals_against": df["FTHG"],
    })
    team_match = pd.concat([home_rows, away_rows], ignore_index=True)
    team_match = team_match.sort_values(["match_date", "match_id"]).reset_index(drop=True)
    print(f"  team_match: {len(team_match)} rows, {team_match['match_id'].nunique()} matches")

    n_splits = args.n_splits
    decay = args.decay
    split_cfg = TimeSplitConfig(n_splits=n_splits, gap=0)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Poisson
    print("\n=== Independent Poisson Backtest ===")
    p_result = run_poisson_backtest(team_match, split_cfg)
    p_result.predictions.to_parquet(out_dir / "poisson_backtest_predictions.parquet", index=False)
    p_metrics = {
        "model": "independent_poisson", "n_splits": n_splits,
        "total_predictions": len(p_result.predictions),
        "overall": p_result.metrics,
        "folds": p_result.fold_metrics.to_dict(orient="records"),
    }
    with open(out_dir / "poisson_backtest_metrics.json", "w", encoding="utf-8") as f:
        json.dump(p_metrics, f, indent=2, default=str, ensure_ascii=False)
    print(f"  Log Loss: {p_result.metrics['log_loss_exact']:.4f}")
    print(f"  Brier:    {p_result.metrics['brier_1x2']:.4f}")
    print(f"  RPS:      {p_result.metrics['rps_1x2']:.4f}")

    # Dixon-Coles (no decay)
    print("\n=== Dixon-Coles Backtest (no decay) ===")
    dc_result = run_dixon_coles_backtest(team_match, split_cfg)
    dc_result.predictions.to_parquet(
        out_dir / "dixon_coles_backtest_predictions.parquet",
        index=False,
    )
    dc_metrics = {
        "model": "dixon_coles", "decay": None, "n_splits": n_splits,
        "total_predictions": len(dc_result.predictions),
        "overall": dc_result.metrics,
        "folds": dc_result.fold_metrics.to_dict(orient="records"),
    }
    with open(out_dir / "dixon_coles_backtest_metrics.json", "w", encoding="utf-8") as f:
        json.dump(dc_metrics, f, indent=2, default=str, ensure_ascii=False)
    print(f"  Log Loss: {dc_result.metrics['log_loss_exact']:.4f}")
    print(f"  Brier:    {dc_result.metrics['brier_1x2']:.4f}")
    print(f"  RPS:      {dc_result.metrics['rps_1x2']:.4f}")

    # Dixon-Coles (with decay)
    print(f"\n=== Dixon-Coles Backtest (decay={decay}) ===")
    dc_decay_result = run_dixon_coles_backtest(team_match, split_cfg, decay=decay)
    dc_decay_result.predictions.to_parquet(
        out_dir / "dixon_coles_decay_backtest_predictions.parquet",
        index=False,
    )
    dc_decay_metrics = {
        "model": "dixon_coles", "decay": decay, "n_splits": n_splits,
        "total_predictions": len(dc_decay_result.predictions),
        "overall": dc_decay_result.metrics,
        "folds": dc_decay_result.fold_metrics.to_dict(orient="records"),
    }
    with open(out_dir / "dixon_coles_decay_backtest_metrics.json", "w", encoding="utf-8") as f:
        json.dump(dc_decay_metrics, f, indent=2, default=str, ensure_ascii=False)
    print(f"  Log Loss: {dc_decay_result.metrics['log_loss_exact']:.4f}")
    print(f"  Brier:    {dc_decay_result.metrics['brier_1x2']:.4f}")
    print(f"  RPS:      {dc_decay_result.metrics['rps_1x2']:.4f}")

    # Comparison: Poisson vs DC (no decay) vs DC (with decay)
    print(f"\n{'Metric':<25} {'Poisson':>12} {'DC(no decay)':>12} {'DC(decay)':>12}")
    print("-" * 65)
    for m in ["log_loss_exact", "brier_1x2", "rps_1x2"]:
        pv = p_result.metrics[m]
        dv = dc_result.metrics[m]
        ddv = dc_decay_result.metrics[m]
        print(f"  {m:<23} {pv:>12.4f} {dv:>12.4f} {ddv:>12.4f}")

    # Probability calibration (isotonic)
    print(f"\n=== Dixon-Coles Calibration (decay={decay}, isotonic) ===")
    try:
        cal_bt = run_dc_backtest_with_calibration(
            team_match, split_cfg, decay=decay, calibration_method="isotonic",
        )
        cal_metrics = cal_bt.metrics
        print(f"  Brier before: {cal_metrics['brier_1x2_before']:.4f}")
        print(f"  Brier after:  {cal_metrics['brier_1x2_after']:.4f}")
        print(f"  RPS before:   {cal_metrics['rps_before']:.4f}")
        print(f"  RPS after:    {cal_metrics['rps_after']:.4f}")
        print(f"  N matches:    {cal_metrics['n_matches']}")

        # Save calibration report
        if cal_bt.calibration.calibrated_predictions is not None:
            cal_bt.calibration.calibrated_predictions.to_parquet(
                out_dir / "dc_calibrated_predictions.parquet", index=False,
            )
        cal_report_data = {
            "method": "isotonic", "decay": decay,
            "brier_before": cal_metrics["brier_1x2_before"],
            "brier_after": cal_metrics["brier_1x2_after"],
            "rps_before": cal_metrics["rps_before"],
            "rps_after": cal_metrics["rps_after"],
            "n_matches": cal_metrics["n_matches"],
        }
        with open(out_dir / "dc_calibration_report.json", "w", encoding="utf-8") as f:
            json.dump(cal_report_data, f, indent=2, default=str, ensure_ascii=False)
    except Exception as exc:
        print(f"  Calibration failed: {exc}")

    print(f"\nResults saved to {out_dir}")


def _load_team_match_from_raw() -> pd.DataFrame:
    """Load and prepare team_match frame from combined_results.parquet.

    Shared by ``backtest`` and ``tune-predictions`` commands.
    """
    project_root = Path(__file__).resolve().parents[2]
    raw_path = project_root / "data" / "raw" / "football_data" / "combined_results.parquet"
    if not raw_path.exists():
        print(f"Error: Football-Data file not found: {raw_path}")
        sys.exit(1)

    raw = pd.read_parquet(raw_path)
    from scoutfootball.entities.normalize import normalize_team_name

    df = raw[["HomeTeam", "AwayTeam", "FTHG", "FTAG", "Date", "season", "league"]].copy()
    df["match_date"] = pd.to_datetime(df["Date"], format="mixed", dayfirst=True, errors="coerce")
    df = df.dropna(subset=["match_date"])
    df["home_team"] = df["HomeTeam"].apply(normalize_team_name)
    df["away_team"] = df["AwayTeam"].apply(normalize_team_name)
    df = df.dropna(subset=["FTHG", "FTAG"])
    df["FTHG"] = df["FTHG"].astype(int)
    df["FTAG"] = df["FTAG"].astype(int)
    df["match_id"] = (
        df["home_team"] + "_v_" + df["away_team"] + "_" + df["match_date"].dt.strftime("%Y%m%d")
    )

    home_rows = pd.DataFrame({
        "match_id": df["match_id"], "match_date": df["match_date"],
        "team_id": df["home_team"], "is_home": True,
        "goals_for": df["FTHG"], "goals_against": df["FTAG"],
    })
    away_rows = pd.DataFrame({
        "match_id": df["match_id"], "match_date": df["match_date"],
        "team_id": df["away_team"], "is_home": False,
        "goals_for": df["FTAG"], "goals_against": df["FTHG"],
    })
    team_match = pd.concat([home_rows, away_rows], ignore_index=True)
    team_match = team_match.sort_values(["match_date", "match_id"]).reset_index(drop=True)
    return team_match


def _cmd_tune_predictions(args: argparse.Namespace) -> None:
    """Grid-search Dixon-Coles decay parameter and optionally run backtest."""
    from scoutfootball.evaluation.backtests import tune_dixon_coles_decay
    from scoutfootball.models import TimeSplitConfig

    project_root = Path(__file__).resolve().parents[2]
    out_dir = Path(args.output_dir).resolve() if args.output_dir else (
        project_root / "data" / "reports" / "calibration_backtest"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    team_match = _load_team_match_from_raw()
    print(f"  Loaded {len(team_match)} rows, {team_match['match_id'].nunique()} matches")

    split_cfg = TimeSplitConfig(n_splits=args.n_splits, gap=0)
    selection_metric = args.metric

    print(f"\n=== Dixon-Coles Decay Tuning (metric: {selection_metric}) ===")
    tuning = tune_dixon_coles_decay(
        team_match,
        split_cfg=split_cfg,
        selection_metric=selection_metric,
    )

    print(f"\n{'Decay':>8} {'HalfLife':>10} {'LogLoss':>10} {'Brier':>10} {'RPS':>10}")
    print("-" * 52)
    for _, row in tuning.comparison_table.iterrows():
        hl = f"{row['half_life_days']:.0f}" if row["half_life_days"] != float("inf") else "inf"
        print(
            f"  {row['decay']:>6.4f} {hl:>10} {row['log_loss_exact']:>10.4f} "
            f"{row['brier_1x2']:>10.4f} {row['rps_1x2']:>10.4f}"
        )

    print(f"\n  Best decay: {tuning.best_decay} (by {selection_metric})")

    # Save tuning results
    tuning_data = {
        "best_decay": tuning.best_decay,
        "selection_metric": tuning.selection_metric,
        "n_folds": tuning.n_folds,
        "n_matches": tuning.n_matches,
        "candidates": tuning.comparison_table.to_dict(orient="records"),
        "candidate_metrics": {
            str(k): v for k, v in tuning.candidate_metrics.items()
        },
    }
    tuning_path = out_dir / "decay_tuning_results.json"
    with open(tuning_path, "w", encoding="utf-8") as f:
        json.dump(tuning_data, f, indent=2, default=str, ensure_ascii=False)
    print(f"  Saved to {tuning_path}")

    # Optionally run full backtest with the best decay
    if args.run_backtest:
        print(f"\n=== Running full backtest with best decay={tuning.best_decay} ===")
        from scoutfootball.evaluation.backtests import (
            run_dc_backtest_with_calibration,
            run_dixon_coles_backtest,
            run_poisson_backtest,
        )

        # Poisson
        print("\n--- Independent Poisson ---")
        p_result = run_poisson_backtest(team_match, split_cfg)
        p_result.predictions.to_parquet(
            out_dir / "poisson_backtest_predictions.parquet", index=False,
        )
        p_metrics = {
            "model": "independent_poisson", "n_splits": args.n_splits,
            "total_predictions": len(p_result.predictions),
            "overall": p_result.metrics,
            "folds": p_result.fold_metrics.to_dict(orient="records"),
        }
        with open(out_dir / "poisson_backtest_metrics.json", "w", encoding="utf-8") as f:
            json.dump(p_metrics, f, indent=2, default=str, ensure_ascii=False)
        print(f"  RPS: {p_result.metrics['rps_1x2']:.4f}")

        # DC no-decay
        print("\n--- Dixon-Coles (no decay) ---")
        dc_result = run_dixon_coles_backtest(team_match, split_cfg)
        dc_result.predictions.to_parquet(
            out_dir / "dixon_coles_backtest_predictions.parquet", index=False,
        )
        dc_metrics = {
            "model": "dixon_coles", "decay": None, "n_splits": args.n_splits,
            "total_predictions": len(dc_result.predictions),
            "overall": dc_result.metrics,
            "folds": dc_result.fold_metrics.to_dict(orient="records"),
        }
        with open(out_dir / "dixon_coles_backtest_metrics.json", "w", encoding="utf-8") as f:
            json.dump(dc_metrics, f, indent=2, default=str, ensure_ascii=False)
        print(f"  RPS: {dc_result.metrics['rps_1x2']:.4f}")

        # DC with best decay
        best_decay = tuning.best_decay
        print(f"\n--- Dixon-Coles (decay={best_decay}) ---")
        dc_decay_result = run_dixon_coles_backtest(
            team_match, split_cfg,
            decay=best_decay if best_decay > 0 else None,
        )
        dc_decay_result.predictions.to_parquet(
            out_dir / "dixon_coles_decay_backtest_predictions.parquet", index=False,
        )
        dc_decay_metrics = {
            "model": "dixon_coles", "decay": best_decay, "n_splits": args.n_splits,
            "total_predictions": len(dc_decay_result.predictions),
            "overall": dc_decay_result.metrics,
            "folds": dc_decay_result.fold_metrics.to_dict(orient="records"),
        }
        with open(out_dir / "dixon_coles_decay_backtest_metrics.json", "w", encoding="utf-8") as f:
            json.dump(dc_decay_metrics, f, indent=2, default=str, ensure_ascii=False)
        print(f"  RPS: {dc_decay_result.metrics['rps_1x2']:.4f}")

        # Calibration
        print(f"\n--- Calibration (decay={best_decay}, isotonic) ---")
        try:
            cal_bt = run_dc_backtest_with_calibration(
                team_match, split_cfg,
                decay=best_decay if best_decay > 0 else None,
                calibration_method="isotonic",
            )
            cal_report_data = {
                "method": "isotonic", "decay": best_decay,
                "brier_before": cal_bt.metrics["brier_1x2_before"],
                "brier_after": cal_bt.metrics["brier_1x2_after"],
                "rps_before": cal_bt.metrics["rps_before"],
                "rps_after": cal_bt.metrics["rps_after"],
                "n_matches": cal_bt.metrics["n_matches"],
            }
            with open(out_dir / "dc_calibration_report.json", "w", encoding="utf-8") as f:
                json.dump(cal_report_data, f, indent=2, default=str, ensure_ascii=False)
            if cal_bt.calibration.calibrated_predictions is not None:
                cal_bt.calibration.calibrated_predictions.to_parquet(
                    out_dir / "dc_calibrated_predictions.parquet", index=False,
                )
            print(
                f"  Brier: {cal_bt.metrics['brier_1x2_before']:.4f}"
                f" -> {cal_bt.metrics['brier_1x2_after']:.4f}"
            )
            print(
                f"  RPS:   {cal_bt.metrics['rps_before']:.4f}"
                f" -> {cal_bt.metrics['rps_after']:.4f}"
            )
        except Exception as exc:
            print(f"  Calibration failed: {exc}")

    print(f"\nResults saved to {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scoutfootball",
        description="ScoutFootball — local-first football data research platform",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("info", help="Show project info and module status")

    ingest_p = sub.add_parser("ingest", help="Run daily data ingestion")
    ingest_p.add_argument(
        "--sources",
        nargs="+",
        default=["statsbomb_open", "football_data", "clubelo"],
        help="Data sources to ingest",
    )

    sub.add_parser("build-features", help="Build feature store from raw data")
    sub.add_parser("train", help="Run weekly model training")
    nn_p = sub.add_parser(
        "train-rating-nn",
        help="Train supervised player-rating neural-network candidate",
    )
    nn_p.add_argument("--min-labels", type=int, default=200)
    nn_p.add_argument("--max-iter", type=int, default=300)
    nn_p.add_argument("--seed", type=int, default=42)
    nn_p.add_argument("--output-dir", type=str, default=None)
    sub.add_parser("validate", help="Run pre-training data validation")

    av_p = sub.add_parser(
        "action-value",
        help="Run action value pipeline (StatsBomb -> xT -> player metrics)",
    )
    av_p.add_argument(
        "--events-path", type=str, default=None,
        help="Path to StatsBomb events Parquet",
    )
    av_p.add_argument(
        "--output-path", type=str, default=None,
        help="Path to output player_value_metrics Parquet",
    )
    avm_p = sub.add_parser(
        "action-value-matches",
        help="Build sample-bounded player-team-match xT rows with match context",
    )
    avm_p.add_argument("--events-path", type=str, default=None)
    avm_p.add_argument("--matches-path", type=str, default=None)
    avm_p.add_argument("--output-path", type=str, default=None)
    avm_p.add_argument(
        "--coverage-scope",
        choices=["sample"],
        default="sample",
        help="Coverage declaration for the bundled three-match event sample",
    )

    sub.add_parser("export-ratings", help="Export ratings to DuckDB database")

    truth_p = sub.add_parser(
        "import-truth-labels",
        help="Import scouting workspace review decisions as truth labels",
    )
    truth_p.add_argument(
        "--workspace", type=str, required=True,
        help="Path to scouting workspace JSON file",
    )
    truth_p.add_argument(
        "--output", type=str,
        default="data/gold/feature_store/player_truth_labels.parquet",
        help="Output truth labels parquet path",
    )
    truth_p.add_argument(
        "--season", type=str, default="",
        help="Season override (auto-detected from workspace if omitted)",
    )
    truth_p.add_argument(
        "--position-scope", type=str, default="all",
        help="Position scope for labels (default: all)",
    )

    bt_p = sub.add_parser(
        "backtest",
        help="Run probability calibration backtest (Poisson vs Dixon-Coles)",
    )
    bt_p.add_argument(
        "--n-splits", type=int, default=3,
        help="Number of time-series folds (default: 3)",
    )
    bt_p.add_argument(
        "--decay", type=float, default=0.005,
        help="Exponential decay parameter for Dixon-Coles (default: 0.005)",
    )
    bt_p.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory for backtest results",
    )

    tune_p = sub.add_parser(
        "tune-predictions",
        help="Grid-search Dixon-Coles time-decay parameter via backtest",
    )
    tune_p.add_argument(
        "--n-splits", type=int, default=3,
        help="Number of time-series folds (default: 3)",
    )
    tune_p.add_argument(
        "--metric", type=str, default="rps_1x2",
        choices=["log_loss_exact", "brier_1x2", "rps_1x2"],
        help="Selection metric to minimise (default: rps_1x2)",
    )
    tune_p.add_argument(
        "--run-backtest", action="store_true",
        help="Also run full backtest with the best decay to generate all artifacts",
    )
    tune_p.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory for tuning results",
    )

    serve_p = sub.add_parser("serve", help="Start FastAPI server")
    serve_p.add_argument("--host", default="0.0.0.0")
    serve_p.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    handlers = {
        "info": _cmd_info,
        "ingest": _cmd_ingest,
        "build-features": _cmd_build_features,
        "train": _cmd_train,
        "train-rating-nn": _cmd_train_rating_nn,
        "validate": _cmd_validate,
        "action-value": _cmd_action_value,
        "action-value-matches": _cmd_action_value_matches,
        "export-ratings": _cmd_export_ratings,
        "import-truth-labels": _cmd_import_truth_labels,
        "backtest": _cmd_backtest,
        "tune-predictions": _cmd_tune_predictions,
        "serve": _cmd_serve,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)
    handler(args)


if __name__ == "__main__":
    main()

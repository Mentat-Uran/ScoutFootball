"""CLI entrypoint for ScoutLab pipeline operations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from scoutlab.architecture import build_default_architecture


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
    from scoutlab.pipeline import run_daily_ingest

    results = run_daily_ingest(sources=tuple(args.sources))
    for source, status in results.items():
        print(f"  {source}: {status}")


def _cmd_build_features(_args: argparse.Namespace) -> None:
    from scoutlab.pipeline import run_build_features

    results = run_build_features()
    for feature_set, status in results.items():
        print(f"  {feature_set}: {status}")


def _cmd_train(_args: argparse.Namespace) -> None:
    from scoutlab.pipeline import run_weekly_train

    results = run_weekly_train(skip_if_validation_fails=False)
    for model, status in results.items():
        print(f"  {model}: {status}")


def _cmd_validate(_args: argparse.Namespace) -> None:
    from scoutlab.evaluation.validation import run_pre_training_validation

    report = run_pre_training_validation()
    print(report.summary())


def _cmd_serve(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. Run: uv add uvicorn")
        sys.exit(1)

    from scoutlab.api_server import create_app

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)


def _cmd_export_ratings(_args: argparse.Namespace) -> None:
    from scoutlab.storage.duckdb_io import create_ratings_database

    project_root = Path(__file__).resolve().parents[2]
    feature_store = project_root / "data" / "gold" / "feature_store"
    output_path = project_root / "data" / "gold" / "scoutlab.duckdb"

    # --- player_ratings ---
    ratings_path = feature_store / "player_ratings_optimized.parquet"
    if not ratings_path.exists():
        print("Error: player_ratings_optimized.parquet not found. Run 'scoutlab train' first.")
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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scoutlab",
        description="ScoutLab — local-first football data research platform",
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
    sub.add_parser("validate", help="Run pre-training data validation")

    sub.add_parser("export-ratings", help="Export ratings to DuckDB database")

    serve_p = sub.add_parser("serve", help="Start FastAPI server")
    serve_p.add_argument("--host", default="0.0.0.0")
    serve_p.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    handlers = {
        "info": _cmd_info,
        "ingest": _cmd_ingest,
        "build-features": _cmd_build_features,
        "train": _cmd_train,
        "validate": _cmd_validate,
        "export-ratings": _cmd_export_ratings,
        "serve": _cmd_serve,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)
    handler(args)


if __name__ == "__main__":
    main()

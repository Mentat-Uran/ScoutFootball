"""Run probability calibration backtest for Poisson and Dixon-Coles models.

Loads Football-Data match results, converts to team_match format,
runs 3-fold time-series backtests, and saves predictions + metrics.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def normalize_team_name(name: str) -> str:
    """Normalize team name using the project's canonical alias map."""
    from scoutfootball.entities.normalize import (
        TEAM_NAME_ALIASES,
        normalize_team_name as _normalize,
    )

    return _normalize(name)


def load_football_data(parquet_path: Path | None = None) -> pd.DataFrame:
    """Load Football-Data combined results and return raw DataFrame."""
    path = parquet_path or (
        PROJECT_ROOT / "data" / "raw" / "football_data" / "combined_results.parquet"
    )
    if not path.exists():
        print(f"Error: Football-Data file not found: {path}")
        sys.exit(1)
    df = pd.read_parquet(path)
    print(f"  Loaded {len(df)} matches from {path.name}")
    return df


def convert_to_team_match(raw: pd.DataFrame) -> pd.DataFrame:
    """Convert Football-Data results to team_match format for backtest.

    Required columns: match_id, match_date, team_id, is_home, goals_for, goals_against
    """
    df = raw[["HomeTeam", "AwayTeam", "FTHG", "FTAG", "Date", "season", "league"]].copy()

    # Parse dates (Football-Data uses DD/MM/YYYY format)
    df["match_date"] = pd.to_datetime(df["Date"], format="mixed", dayfirst=True, errors="coerce")
    bad_dates = df["match_date"].isna().sum()
    if bad_dates > 0:
        print(f"  Warning: {bad_dates} rows with unparseable dates dropped")
        df = df.dropna(subset=["match_date"])

    # Normalize team names
    df["home_team"] = df["HomeTeam"].apply(normalize_team_name)
    df["away_team"] = df["AwayTeam"].apply(normalize_team_name)

    # Drop rows with missing goals
    df = df.dropna(subset=["FTHG", "FTAG"])
    df["FTHG"] = df["FTHG"].astype(int)
    df["FTAG"] = df["FTAG"].astype(int)

    # Build match_id from home+away+date
    df["match_id"] = (
        df["home_team"] + "_v_" + df["away_team"] + "_" + df["match_date"].dt.strftime("%Y%m%d")
    )

    # Create home rows
    home_rows = pd.DataFrame(
        {
            "match_id": df["match_id"],
            "match_date": df["match_date"],
            "team_id": df["home_team"],
            "is_home": True,
            "goals_for": df["FTHG"],
            "goals_against": df["FTAG"],
            "league": df["league"],
            "season": df["season"],
        }
    )

    # Create away rows
    away_rows = pd.DataFrame(
        {
            "match_id": df["match_id"],
            "match_date": df["match_date"],
            "team_id": df["away_team"],
            "is_home": False,
            "goals_for": df["FTAG"],
            "goals_against": df["FTHG"],
            "league": df["league"],
            "season": df["season"],
        }
    )

    team_match = pd.concat([home_rows, away_rows], ignore_index=True)
    team_match = team_match.sort_values(["match_date", "match_id"]).reset_index(drop=True)

    n_teams = team_match["team_id"].nunique()
    n_matches = team_match["match_id"].nunique()
    print(f"  Converted to team_match: {len(team_match)} rows, {n_matches} matches, {n_teams} teams")
    return team_match


def run_backtests(
    team_match_df: pd.DataFrame,
    output_dir: Path | None = None,
    n_splits: int = 3,
) -> dict:
    """Run Poisson and Dixon-Coles backtests and save results."""
    from scoutfootball.evaluation.backtests import (
        run_dixon_coles_backtest,
        run_poisson_backtest,
    )
    from scoutfootball.models import TimeSplitConfig

    out_dir = output_dir or (PROJECT_ROOT / "data" / "reports" / "calibration_backtest")
    out_dir.mkdir(parents=True, exist_ok=True)

    split_cfg = TimeSplitConfig(n_splits=n_splits, gap=0)

    # --- Poisson backtest ---
    print("\n=== Independent Poisson Backtest ===")
    poisson_result = run_poisson_backtest(team_match_df, split_cfg)
    print(f"  Total predictions: {len(poisson_result.predictions)}")
    print(f"  Folds: {len(poisson_result.fold_metrics)}")

    # Save predictions
    poisson_pred_path = out_dir / "poisson_backtest_predictions.parquet"
    poisson_result.predictions.to_parquet(poisson_pred_path, index=False)
    print(f"  Saved predictions to {poisson_pred_path}")

    # Save metrics
    poisson_metrics = {
        "model": "independent_poisson",
        "n_splits": n_splits,
        "total_predictions": len(poisson_result.predictions),
        "overall": poisson_result.metrics,
        "folds": poisson_result.fold_metrics.to_dict(orient="records"),
    }
    poisson_metrics_path = out_dir / "poisson_backtest_metrics.json"
    with open(poisson_metrics_path, "w", encoding="utf-8") as f:
        json.dump(poisson_metrics, f, indent=2, default=str, ensure_ascii=False)
    print(f"  Saved metrics to {poisson_metrics_path}")

    # --- Dixon-Coles backtest ---
    print("\n=== Dixon-Coles Backtest ===")
    dc_result = run_dixon_coles_backtest(team_match_df, split_cfg)
    print(f"  Total predictions: {len(dc_result.predictions)}")
    print(f"  Folds: {len(dc_result.fold_metrics)}")

    # Save predictions
    dc_pred_path = out_dir / "dixon_coles_backtest_predictions.parquet"
    dc_result.predictions.to_parquet(dc_pred_path, index=False)
    print(f"  Saved predictions to {dc_pred_path}")

    # Save metrics
    dc_metrics = {
        "model": "dixon_coles",
        "n_splits": n_splits,
        "total_predictions": len(dc_result.predictions),
        "overall": dc_result.metrics,
        "folds": dc_result.fold_metrics.to_dict(orient="records"),
    }
    dc_metrics_path = out_dir / "dixon_coles_backtest_metrics.json"
    with open(dc_metrics_path, "w", encoding="utf-8") as f:
        json.dump(dc_metrics, f, indent=2, default=str, ensure_ascii=False)
    print(f"  Saved metrics to {dc_metrics_path}")

    return {
        "poisson": poisson_result,
        "dixon_coles": dc_result,
    }


def print_comparison_table(results: dict) -> None:
    """Print a summary comparison table of both models."""
    p_metrics = results["poisson"].metrics
    dc_metrics = results["dixon_coles"].metrics

    print("\n" + "=" * 65)
    print("CALIBRATION BACKTEST COMPARISON")
    print("=" * 65)
    print(f"{'Metric':<25} {'Poisson':>15} {'Dixon-Coles':>15} {'Delta':>10}")
    print("-" * 65)

    for metric_name in ["log_loss_exact", "brier_1x2", "rps_1x2"]:
        p_val = p_metrics[metric_name]
        dc_val = dc_metrics[metric_name]
        delta = dc_val - p_val
        sign = "+" if delta > 0 else ""
        print(f"  {metric_name:<23} {p_val:>15.4f} {dc_val:>15.4f} {sign}{delta:>9.4f}")

    print("-" * 65)

    # Per-fold breakdown
    print("\nPer-fold breakdown:")
    p_folds = results["poisson"].fold_metrics
    dc_folds = results["dixon_coles"].fold_metrics

    for fold_col in ["log_loss_exact", "brier_1x2", "rps_1x2"]:
        print(f"\n  {fold_col}:")
        print(f"    {'Fold':<8} {'Poisson':>12} {'Dixon-Coles':>12}")
        for i in range(len(p_folds)):
            p_val = p_folds.iloc[i][fold_col]
            dc_val = dc_folds.iloc[i][fold_col] if i < len(dc_folds) else float("nan")
            print(f"    {i+1:<8} {p_val:>12.4f} {dc_val:>12.4f}")

    # Interpretation
    print("\nInterpretation:")
    if dc_metrics["rps_1x2"] < p_metrics["rps_1x2"]:
        print("  Dixon-Coles outperforms Poisson on RPS (lower is better).")
    else:
        print("  Poisson outperforms Dixon-Coles on RPS (lower is better).")

    if dc_metrics["brier_1x2"] < p_metrics["brier_1x2"]:
        print("  Dixon-Coles outperforms Poisson on Brier score (lower is better).")
    else:
        print("  Poisson outperforms Dixon-Coles on Brier score (lower is better).")

    print("=" * 65)


def main() -> None:
    print("ScoutFootball — Probability Calibration Backtest")
    print("=" * 50)

    # Step 1: Load raw data
    print("\n[1/3] Loading Football-Data match results...")
    raw = load_football_data()

    # Step 2: Convert to team_match format
    print("\n[2/3] Converting to team_match format...")
    team_match = convert_to_team_match(raw)

    # Step 3: Run backtests
    print("\n[3/3] Running backtests (3-fold time-series split)...")
    results = run_backtests(team_match, n_splits=3)

    # Print comparison
    print_comparison_table(results)

    print("\nDone.")


if __name__ == "__main__":
    main()

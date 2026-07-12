"""Backtests for probability models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scoutfootball.models import TimeSplitConfig
from scoutfootball.models.match_prediction import (
    CalibrationReport,
    DixonColesModel,
    calibrate_predictions,
    fit_dixon_coles,
    fit_independent_poisson,
    predict_match,
    predict_match_dc,
)


@dataclass(frozen=True)
class PoissonBacktestResult:
    """Fold-level metrics plus per-match predictions from the Poisson backtest."""

    predictions: pd.DataFrame
    fold_metrics: pd.DataFrame
    metrics: dict[str, float]


@dataclass(frozen=True)
class DixonColesBacktestResult:
    """Fold-level metrics plus per-match predictions from the Dixon-Coles backtest."""

    predictions: pd.DataFrame
    fold_metrics: pd.DataFrame
    metrics: dict[str, float]


def run_poisson_backtest(
    team_match_df: pd.DataFrame,
    split_cfg: TimeSplitConfig | None = None,
    *,
    max_goals: int = 10,
) -> PoissonBacktestResult:
    """Run a past-only rolling backtest for the independent Poisson baseline."""

    config = split_cfg or TimeSplitConfig()
    fixtures = _build_fixture_frame(team_match_df)
    if len(fixtures) <= config.n_splits:
        raise ValueError("team_match_df must contain more matches than the requested splits")

    splitter = _time_series_split(len(fixtures), config.n_splits, config.gap)
    prediction_rows: list[pd.DataFrame] = []
    fold_rows: list[dict] = []

    for fold_index, (train_idx, test_idx) in enumerate(splitter, start=1):
        train_fixtures = fixtures.iloc[train_idx].copy()
        test_fixtures = fixtures.iloc[test_idx].copy()
        if train_fixtures["match_date"].max() > test_fixtures["match_date"].min():
            raise ValueError("time split leakage detected in Poisson backtest")

        train_match_ids = set(train_fixtures["match_id"])
        train_team_match = team_match_df.loc[team_match_df["match_id"].isin(train_match_ids)].copy()
        model = fit_independent_poisson(train_team_match)

        fold_predictions = []
        for _, fixture in test_fixtures.iterrows():
            prediction = predict_match(
                model,
                fixture["home_team_id"],
                fixture["away_team_id"],
                max_goals=max_goals,
            )
            hg = int(fixture["home_goals"])
            ag = int(fixture["away_goals"])
            if hg > max_goals or ag > max_goals:
                continue
            exact_probability = float(
                prediction.score_matrix.loc[hg, ag]
            )
            outcome_label = _outcome_label(fixture["home_goals"], fixture["away_goals"])
            fold_predictions.append(
                {
                    "match_id": fixture["match_id"],
                    "match_date": fixture["match_date"],
                    "home_team_id": fixture["home_team_id"],
                    "away_team_id": fixture["away_team_id"],
                    "home_goals": fixture["home_goals"],
                    "away_goals": fixture["away_goals"],
                    "home_lambda": prediction.home_lambda,
                    "away_lambda": prediction.away_lambda,
                    "exact_score_probability": exact_probability,
                    "home_win_probability": prediction.summary.home_win,
                    "draw_probability": prediction.summary.draw,
                    "away_win_probability": prediction.summary.away_win,
                    "over_2_5_probability": prediction.summary.over_2_5,
                    "under_2_5_probability": prediction.summary.under_2_5,
                    "btts_yes_probability": prediction.summary.btts_yes,
                    "btts_no_probability": prediction.summary.btts_no,
                    "actual_outcome": outcome_label,
                    "fold": fold_index,
                },
            )

        fold_frame = pd.DataFrame.from_records(fold_predictions)
        prediction_rows.append(fold_frame)
        fold_rows.append(
            {
                "fold": fold_index,
                "train_start": train_fixtures["match_date"].min(),
                "train_end": train_fixtures["match_date"].max(),
                "test_start": test_fixtures["match_date"].min(),
                "test_end": test_fixtures["match_date"].max(),
                "train_matches": len(train_fixtures),
                "test_matches": len(test_fixtures),
                "log_loss_exact": _exact_score_log_loss(fold_frame),
                "brier_1x2": _brier_1x2(fold_frame),
                "rps_1x2": _ranked_probability_score(fold_frame),
            },
        )

    predictions = pd.concat(prediction_rows, ignore_index=True, sort=False)
    fold_metrics = pd.DataFrame.from_records(fold_rows)
    metrics = {
        "log_loss_exact": float(_exact_score_log_loss(predictions)),
        "brier_1x2": float(_brier_1x2(predictions)),
        "rps_1x2": float(_ranked_probability_score(predictions)),
    }
    return PoissonBacktestResult(
        predictions=predictions,
        fold_metrics=fold_metrics,
        metrics=metrics,
    )


def _build_fixture_frame(team_match_df: pd.DataFrame) -> pd.DataFrame:
    required = {"match_id", "match_date", "team_id", "is_home", "goals_for", "goals_against"}
    missing = sorted(required.difference(team_match_df.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"team_match_df is missing required columns: {missing_text}")

    prepared = team_match_df.copy()
    prepared["match_date"] = pd.to_datetime(prepared["match_date"], errors="raise")
    home = prepared.loc[prepared["is_home"].astype(bool)].copy()
    away = prepared.loc[~prepared["is_home"].astype(bool)].copy()

    fixtures = home.merge(
        away,
        on="match_id",
        suffixes=("_home", "_away"),
        how="inner",
    )
    fixtures = fixtures.rename(
        columns={
            "match_date_home": "match_date",
            "team_id_home": "home_team_id",
            "team_id_away": "away_team_id",
            "goals_for_home": "home_goals",
            "goals_for_away": "away_goals",
        },
    )
    fixtures["home_goals"] = pd.to_numeric(fixtures["home_goals"], errors="coerce")
    fixtures["away_goals"] = pd.to_numeric(fixtures["away_goals"], errors="coerce")
    fixtures = fixtures.dropna(subset=["home_goals", "away_goals"])
    fixtures = fixtures.loc[
        (fixtures["home_goals"] >= 0) & (fixtures["away_goals"] >= 0),
    ]
    return (
        fixtures.loc[
            :,
            ["match_id", "match_date", "home_team_id", "away_team_id", "home_goals", "away_goals"],
        ]
        .sort_values(["match_date", "match_id"])
        .reset_index(drop=True)
    )


def _time_series_split(
    n_rows: int,
    n_splits: int,
    gap: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    fold_size = n_rows // (n_splits + 1)
    splits: list[tuple[np.ndarray, np.ndarray]] = []
    for split_index in range(1, n_splits + 1):
        test_start = split_index * fold_size
        test_end = n_rows if split_index == n_splits else (split_index + 1) * fold_size
        train_end = max(test_start - gap, 0)
        train_idx = np.arange(0, train_end)
        test_idx = np.arange(test_start, test_end)
        splits.append((train_idx, test_idx))
    return splits


def _exact_score_log_loss(predictions: pd.DataFrame) -> float:
    probabilities = predictions["exact_score_probability"].clip(lower=1e-12)
    return float(-(np.log(probabilities)).mean())


def _brier_1x2(predictions: pd.DataFrame) -> float:
    probs = predictions.loc[
        :,
        ["home_win_probability", "draw_probability", "away_win_probability"],
    ].to_numpy()
    actual = np.vstack(
        predictions["actual_outcome"].map(
            {
                "home_win": [1.0, 0.0, 0.0],
                "draw": [0.0, 1.0, 0.0],
                "away_win": [0.0, 0.0, 1.0],
            },
        ),
    )
    return float(np.mean(np.sum((probs - actual) ** 2, axis=1)))


def _ranked_probability_score(predictions: pd.DataFrame) -> float:
    probs = predictions.loc[
        :,
        ["away_win_probability", "draw_probability", "home_win_probability"],
    ].to_numpy()
    actual = np.vstack(
        predictions["actual_outcome"].map(
            {
                "away_win": [1.0, 0.0, 0.0],
                "draw": [0.0, 1.0, 0.0],
                "home_win": [0.0, 0.0, 1.0],
            },
        ),
    )
    cumulative_probs = np.cumsum(probs, axis=1)
    cumulative_actual = np.cumsum(actual, axis=1)
    return float(np.mean(np.sum((cumulative_probs - cumulative_actual) ** 2, axis=1) / 2.0))


def _outcome_label(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home_win"
    if home_goals < away_goals:
        return "away_win"
    return "draw"


@dataclass(frozen=True)
class DCCalibrationResult:
    """Calibration metrics for the Dixon-Coles model by score bucket."""

    predictions: pd.DataFrame
    calibration: pd.DataFrame
    metrics: dict[str, float]


def run_dc_calibration_backtest(
    team_match_df: pd.DataFrame,
    model_root: Path,
    *,
    max_goals: int = 10,
    save_detail: bool = False,
) -> DCCalibrationResult:
    """Evaluate DC calibration against held-out or full data.

    Loads the saved Dixon-Coles artifacts, predicts every match in
    *team_match_df*, and returns predicted-vs-actual frequency per
    score bucket together with overall log-loss and Brier metrics.

    Parameters
    ----------
    team_match_df : DataFrame with columns: team_id, is_home, goals_for,
        goals_against, match_id, match_date.
    model_root : Path to the model root directory (e.g. data/models).
        Must contain artifacts/dixon_coles_results.parquet and
        artifacts/dc_team_strengths.parquet.
    max_goals : Maximum goal count for the score matrix.
    save_detail : If True, save detailed calibration artifacts to
        data/models/artifacts/dc_calibration_detail.parquet.

    Returns
    -------
    DCCalibrationResult with predictions, calibration DataFrame, and metrics.
    """
    model = _load_dc_artifacts(model_root)
    fixtures = _build_fixture_frame(team_match_df)

    # Merge competition info if available. The canonical team-match contract
    # uses ``competition_id`` while a few legacy fixtures still expose
    # ``league``.
    league_column = (
        "league" if "league" in team_match_df.columns
        else ("competition_id" if "competition_id" in team_match_df.columns else None)
    )
    has_league = league_column is not None
    league_lookup: dict[str, str] = {}
    if has_league:
        for _, row in team_match_df.iterrows():
            league_lookup[str(row["match_id"])] = str(row.get(league_column, ""))

    prediction_rows: list[dict] = []
    for _, fixture in fixtures.iterrows():
        home_id = str(fixture["home_team_id"])
        away_id = str(fixture["away_team_id"])
        try:
            prediction = predict_match_dc(model, home_id, away_id, max_goals=max_goals)
        except Exception:
            continue

        hg = int(fixture["home_goals"])
        ag = int(fixture["away_goals"])

        if hg >= prediction.score_matrix.shape[0] or ag >= prediction.score_matrix.shape[1]:
            continue

        exact_prob = float(prediction.score_matrix.loc[hg, ag])
        outcome_label = _outcome_label(hg, ag)
        score_bucket = f"{hg}-{ag}"
        mid = str(fixture["match_id"])

        row_data: dict[str, Any] = {
            "match_id": mid,
            "match_date": fixture["match_date"],
            "home_team_id": home_id,
            "away_team_id": away_id,
            "home_goals": hg,
            "away_goals": ag,
            "score_bucket": score_bucket,
            "exact_score_probability": exact_prob,
            "home_win_probability": prediction.summary.home_win,
            "draw_probability": prediction.summary.draw,
            "away_win_probability": prediction.summary.away_win,
            "actual_outcome": outcome_label,
            "home_lambda": prediction.home_lambda,
            "away_lambda": prediction.away_lambda,
        }
        if has_league and mid in league_lookup:
            row_data["league"] = league_lookup[mid]
        prediction_rows.append(row_data)

    if not prediction_rows:
        raise ValueError("DC calibration backtest produced no predictions")

    predictions = pd.DataFrame.from_records(prediction_rows)

    # --- Overall metrics ---
    metrics: dict[str, float] = {
        "log_loss_exact": float(_exact_score_log_loss(predictions)),
        "brier_1x2": float(_brier_1x2(predictions)),
        "rps_1x2": float(_ranked_probability_score(predictions)),
        "n_matches": float(len(predictions)),
    }

    # --- Per-score-bucket calibration ---
    calibration = _compute_score_bucket_calibration(predictions)

    # --- Low-score calibration detail (saved in detail parquet) ---
    _low_score_detail = _compute_low_score_calibration(predictions)

    # --- Brier score decomposition ---
    brier_decomposition = _compute_brier_decomposition(predictions)

    # --- Calibration plot data (saved in detail parquet) ---
    _calibration_plot = _compute_calibration_plot_data(predictions)

    # --- Coverage by league (saved in detail parquet) ---
    _league_coverage = _compute_league_coverage(predictions)

    # --- Save detailed artifacts ---
    if save_detail:
        artifact_dir = model_root / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        detail_path = artifact_dir / "dc_calibration_detail.parquet"
        detail_records: list[dict[str, Any]] = []
        for _, row in predictions.iterrows():
            detail_records.append({
                "match_id": row["match_id"],
                "score_bucket": row["score_bucket"],
                "exact_score_probability": row["exact_score_probability"],
                "home_win_probability": row["home_win_probability"],
                "draw_probability": row["draw_probability"],
                "away_win_probability": row["away_win_probability"],
                "actual_outcome": row["actual_outcome"],
                "home_lambda": row["home_lambda"],
                "away_lambda": row["away_lambda"],
                "league": row.get("league", ""),
            })
        detail_df = pd.DataFrame(detail_records)
        detail_df.to_parquet(detail_path, index=False)

    # Enrich metrics with decomposition
    all_metrics: dict[str, float] = {
        **metrics,
        "brier_reliability": brier_decomposition["reliability"],
        "brier_resolution": brier_decomposition["resolution"],
        "brier_uncertainty": brier_decomposition["uncertainty"],
    }

    return DCCalibrationResult(
        predictions=predictions,
        calibration=calibration,
        metrics=all_metrics,
    )


def _load_dc_artifacts(model_root: Path) -> DixonColesModel:
    """Reconstruct a DixonColesModel from saved parquet artifacts."""
    artifact_dir = Path(model_root) / "artifacts"
    results_path = artifact_dir / "dixon_coles_results.parquet"
    strengths_path = artifact_dir / "dc_team_strengths.parquet"

    if not results_path.exists():
        raise FileNotFoundError(f"Missing DC results artifact: {results_path}")
    if not strengths_path.exists():
        raise FileNotFoundError(f"Missing DC strengths artifact: {strengths_path}")

    results_df = pd.read_parquet(results_path)
    strengths_df = pd.read_parquet(strengths_path)

    row = results_df.iloc[0]
    team_attack = dict(
        zip(strengths_df["team_id"].astype(str), strengths_df["attack_strength"], strict=False),
    )
    team_defense = dict(
        zip(strengths_df["team_id"].astype(str), strengths_df["defense_strength"], strict=False),
    )

    hld = row.get("half_life_days")
    decay_val = row.get("decay")
    return DixonColesModel(
        team_attack=team_attack,
        team_defense=team_defense,
        home_advantage=float(row["home_advantage"]),
        rho=float(row["rho"]),
        league_mean_goals=float(row["league_mean_goals"]),
        num_matches=int(row["num_matches"]),
        half_life_days=float(hld) if pd.notna(hld) else None,
        decay=float(decay_val) if pd.notna(decay_val) else None,
    )


def _compute_score_bucket_calibration(predictions: pd.DataFrame) -> pd.DataFrame:
    """Compute predicted vs actual frequency for each score bucket.

    Returns a DataFrame with columns:
      score_bucket, n_matches, actual_pct, mean_predicted_pct,
      calibration_error, log_loss_bucket
    """
    # Cap buckets: individual scores 0-0 through 3-3, everything else is "other"
    common_buckets = [
        "0-0", "1-0", "0-1", "1-1",
        "2-0", "0-2", "2-1", "1-2",
        "3-0", "0-3", "3-1", "1-3", "2-2", "3-2", "2-3", "3-3",
    ]

    preds = predictions.copy()
    preds["bucket"] = preds["score_bucket"].where(
        preds["score_bucket"].isin(common_buckets), other="other",
    )

    bucket_rows: list[dict] = []
    total = len(preds)

    for bucket, group in preds.groupby("bucket", sort=False):
        n = len(group)
        actual_pct = n / total * 100.0
        mean_predicted_pct = float(group["exact_score_probability"].mean()) * 100.0
        calibration_error = abs(actual_pct - mean_predicted_pct)
        clipped_probs = group["exact_score_probability"].clip(lower=1e-12)
        log_loss_bucket = float(-(np.log(clipped_probs)).mean())

        bucket_rows.append(
            {
                "score_bucket": bucket,
                "n_matches": n,
                "actual_pct": round(actual_pct, 2),
                "mean_predicted_pct": round(mean_predicted_pct, 2),
                "calibration_error": round(calibration_error, 2),
                "log_loss_bucket": round(log_loss_bucket, 4),
            },
        )

    cal_df = pd.DataFrame(bucket_rows)
    # Sort: common buckets first in order, then "other"
    bucket_order = {b: i for i, b in enumerate(common_buckets)}
    bucket_order["other"] = len(common_buckets)
    cal_df["_sort"] = cal_df["score_bucket"].map(bucket_order).fillna(len(common_buckets))
    cal_df = cal_df.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)

    return cal_df


def run_dixon_coles_backtest(
    team_match_df: pd.DataFrame,
    split_cfg: TimeSplitConfig | None = None,
    *,
    max_goals: int = 10,
    half_life_days: float | None = None,
    decay: float | None = None,
) -> DixonColesBacktestResult:
    """Run a past-only rolling backtest for the Dixon-Coles model."""

    config = split_cfg or TimeSplitConfig()
    fixtures = _build_fixture_frame(team_match_df)
    if len(fixtures) <= config.n_splits:
        raise ValueError("team_match_df must contain more matches than the requested splits")

    splitter = _time_series_split(len(fixtures), config.n_splits, config.gap)
    prediction_rows: list[pd.DataFrame] = []
    fold_rows: list[dict] = []

    for fold_index, (train_idx, test_idx) in enumerate(splitter, start=1):
        train_fixtures = fixtures.iloc[train_idx].copy()
        test_fixtures = fixtures.iloc[test_idx].copy()
        if train_fixtures["match_date"].max() > test_fixtures["match_date"].min():
            raise ValueError("time split leakage detected in Dixon-Coles backtest")

        train_match_ids = set(train_fixtures["match_id"])
        train_team_match = team_match_df.loc[
            team_match_df["match_id"].isin(train_match_ids)
        ].copy()

        try:
            model = fit_dixon_coles(
                train_team_match, half_life_days=half_life_days, decay=decay,
            )
        except (ValueError, RuntimeError, OverflowError, ArithmeticError, FloatingPointError):
            # Skip fold if DC fitting fails (e.g., too few matches)
            continue

        fold_predictions = []
        for _, fixture in test_fixtures.iterrows():
            prediction = predict_match_dc(
                model,
                fixture["home_team_id"],
                fixture["away_team_id"],
                max_goals=max_goals,
            )
            hg = int(fixture["home_goals"])
            ag = int(fixture["away_goals"])
            if hg > max_goals or ag > max_goals:
                continue
            exact_probability = float(
                prediction.score_matrix.loc[hg, ag]
            )
            outcome_label = _outcome_label(fixture["home_goals"], fixture["away_goals"])
            fold_predictions.append(
                {
                    "match_id": fixture["match_id"],
                    "match_date": fixture["match_date"],
                    "home_team_id": fixture["home_team_id"],
                    "away_team_id": fixture["away_team_id"],
                    "home_goals": fixture["home_goals"],
                    "away_goals": fixture["away_goals"],
                    "home_lambda": prediction.home_lambda,
                    "away_lambda": prediction.away_lambda,
                    "exact_score_probability": exact_probability,
                    "home_win_probability": prediction.summary.home_win,
                    "draw_probability": prediction.summary.draw,
                    "away_win_probability": prediction.summary.away_win,
                    "over_2_5_probability": prediction.summary.over_2_5,
                    "under_2_5_probability": prediction.summary.under_2_5,
                    "btts_yes_probability": prediction.summary.btts_yes,
                    "btts_no_probability": prediction.summary.btts_no,
                    "actual_outcome": outcome_label,
                    "fold": fold_index,
                },
            )

        fold_frame = pd.DataFrame.from_records(fold_predictions)
        prediction_rows.append(fold_frame)
        fold_rows.append(
            {
                "fold": fold_index,
                "train_start": train_fixtures["match_date"].min(),
                "train_end": train_fixtures["match_date"].max(),
                "test_start": test_fixtures["match_date"].min(),
                "test_end": test_fixtures["match_date"].max(),
                "train_matches": len(train_fixtures),
                "test_matches": len(test_fixtures),
                "log_loss_exact": _exact_score_log_loss(fold_frame),
                "brier_1x2": _brier_1x2(fold_frame),
                "rps_1x2": _ranked_probability_score(fold_frame),
            },
        )

    if not prediction_rows:
        raise ValueError("Dixon-Coles backtest failed on all folds")

    predictions = pd.concat(prediction_rows, ignore_index=True, sort=False)
    fold_metrics = pd.DataFrame.from_records(fold_rows)
    metrics = {
        "log_loss_exact": float(_exact_score_log_loss(predictions)),
        "brier_1x2": float(_brier_1x2(predictions)),
        "rps_1x2": float(_ranked_probability_score(predictions)),
    }
    return DixonColesBacktestResult(
        predictions=predictions,
        fold_metrics=fold_metrics,
        metrics=metrics,
    )


def _compute_low_score_calibration(predictions: pd.DataFrame) -> pd.DataFrame:
    """Compute per-score-bucket log-loss for low-scoring outcomes.

    Focuses on the four Dixon-Coles tau-corrected buckets: 0-0, 1-0, 0-1, 1-1.
    Returns a DataFrame with columns:
      score_bucket, n_matches, actual_pct, mean_predicted_pct,
      calibration_error, log_loss_bucket
    """
    low_scores = ["0-0", "1-0", "0-1", "1-1"]
    total = len(predictions)
    rows: list[dict[str, Any]] = []

    for bucket in low_scores:
        group = predictions[predictions["score_bucket"] == bucket]
        n = len(group)
        if n == 0:
            rows.append({
                "score_bucket": bucket,
                "n_matches": 0,
                "actual_pct": 0.0,
                "mean_predicted_pct": 0.0,
                "calibration_error": 0.0,
                "log_loss_bucket": float("nan"),
            })
            continue
        actual_pct = n / total * 100.0
        mean_pred_pct = float(group["exact_score_probability"].mean()) * 100.0
        cal_error = abs(actual_pct - mean_pred_pct)
        clipped = group["exact_score_probability"].clip(lower=1e-12)
        log_loss_b = float(-(np.log(clipped)).mean())
        rows.append({
            "score_bucket": bucket,
            "n_matches": n,
            "actual_pct": round(actual_pct, 2),
            "mean_predicted_pct": round(mean_pred_pct, 2),
            "calibration_error": round(cal_error, 2),
            "log_loss_bucket": round(log_loss_b, 4),
        })

    return pd.DataFrame(rows)


def _compute_brier_decomposition(predictions: pd.DataFrame) -> dict[str, float]:
    """Brier score decomposition into reliability, resolution, and uncertainty.

    For the 1x2 (home/draw/away) outcome using predicted probabilities.
    Brier = reliability - resolution + uncertainty
    """
    probs = predictions.loc[
        :,
        ["home_win_probability", "draw_probability", "away_win_probability"],
    ].to_numpy()
    actual = np.vstack(
        predictions["actual_outcome"].map(
            {
                "home_win": [1.0, 0.0, 0.0],
                "draw": [0.0, 1.0, 0.0],
                "away_win": [0.0, 0.0, 1.0],
            },
        ),
    )

    n = len(predictions)
    overall_mean = actual.mean(axis=0)
    uncertainty = float(np.sum(overall_mean * (1 - overall_mean)))

    # Bin by rounded predicted home-win probability (10 bins)
    bin_edges = np.linspace(0, 1, 11)
    bin_indices = np.digitize(probs[:, 0], bin_edges) - 1
    bin_indices = np.clip(bin_indices, 0, 9)

    reliability = 0.0
    resolution = 0.0
    for b in range(10):
        mask = bin_indices == b
        if mask.sum() == 0:
            continue
        bin_size = int(mask.sum())
        mean_pred = probs[mask].mean(axis=0)
        mean_actual = actual[mask].mean(axis=0)
        reliability += bin_size * float(np.sum((mean_pred - mean_actual) ** 2))
        resolution += bin_size * float(np.sum((mean_actual - overall_mean) ** 2))

    reliability /= n
    resolution /= n

    return {
        "reliability": round(float(reliability), 6),
        "resolution": round(float(resolution), 6),
        "uncertainty": round(float(uncertainty), 6),
    }


def _compute_calibration_plot_data(predictions: pd.DataFrame) -> pd.DataFrame:
    """Compute calibration plot data: predicted vs actual probability bins.

    For 1x2 outcome, bins predicted home-win probability into deciles.
    Returns DataFrame with columns: bin_center, n_matches, mean_predicted, mean_actual.
    """
    probs = predictions["home_win_probability"].to_numpy()
    actual_hw = (predictions["actual_outcome"] == "home_win").to_numpy().astype(float)

    bin_edges = np.linspace(0, 1, 11)
    bin_indices = np.digitize(probs, bin_edges) - 1
    bin_indices = np.clip(bin_indices, 0, 9)

    rows: list[dict[str, Any]] = []
    for b in range(10):
        mask = bin_indices == b
        if mask.sum() == 0:
            continue
        bin_center = round(float((bin_edges[b] + bin_edges[b + 1]) / 2), 2)
        rows.append({
            "bin_center": bin_center,
            "n_matches": int(mask.sum()),
            "mean_predicted": round(float(probs[mask].mean()), 4),
            "mean_actual": round(float(actual_hw[mask].mean()), 4),
        })

    return pd.DataFrame(rows)


def _compute_league_coverage(predictions: pd.DataFrame) -> pd.DataFrame:
    """Compute prediction coverage by league.

    Returns DataFrame with columns: league, n_matches, mean_log_loss, mean_brier.
    """
    if "league" not in predictions.columns:
        return pd.DataFrame(columns=["league", "n_matches", "mean_log_loss", "mean_brier"])

    rows: list[dict[str, Any]] = []
    for league, group in predictions.groupby("league", sort=True):
        n = len(group)
        if n == 0:
            continue
        clipped = group["exact_score_probability"].clip(lower=1e-12)
        ll = float(-(np.log(clipped)).mean())

        probs = group.loc[
            :,
            ["home_win_probability", "draw_probability", "away_win_probability"],
        ].to_numpy()
        actual = np.vstack(
            group["actual_outcome"].map(
                {
                    "home_win": [1.0, 0.0, 0.0],
                    "draw": [0.0, 1.0, 0.0],
                    "away_win": [0.0, 0.0, 1.0],
                },
            ),
        )
        brier = float(np.mean(np.sum((probs - actual) ** 2, axis=1)))

        rows.append({
            "league": str(league),
            "n_matches": n,
            "mean_log_loss": round(ll, 4),
            "mean_brier": round(brier, 4),
        })

    return pd.DataFrame(rows)


@dataclass(frozen=True)
class DCDecayComparisonResult:
    """Comparison of Dixon-Coles backtest with and without time decay."""

    no_decay: DixonColesBacktestResult
    with_decay: DixonColesBacktestResult
    decay_value: float
    comparison: pd.DataFrame


def run_dc_decay_comparison(
    team_match_df: pd.DataFrame,
    split_cfg: TimeSplitConfig | None = None,
    *,
    decay: float = 0.005,
    max_goals: int = 10,
) -> DCDecayComparisonResult:
    """Run Dixon-Coles backtest with and without time decay, then compare.

    Parameters
    ----------
    team_match_df : DataFrame with match data.
    split_cfg : Time split configuration.
    decay : Exponential decay parameter (default 0.005, Dixon-Coles paper).
    max_goals : Maximum goals for score matrix.

    Returns
    -------
    DCDecayComparisonResult with both backtest results and a comparison table.
    """
    no_decay_result = run_dixon_coles_backtest(
        team_match_df, split_cfg, max_goals=max_goals,
    )
    with_decay_result = run_dixon_coles_backtest(
        team_match_df, split_cfg, max_goals=max_goals, decay=decay,
    )

    comparison_rows = []
    for metric_name in ["log_loss_exact", "brier_1x2", "rps_1x2"]:
        nd_val = no_decay_result.metrics[metric_name]
        wd_val = with_decay_result.metrics[metric_name]
        delta = wd_val - nd_val
        comparison_rows.append({
            "metric": metric_name,
            "no_decay": round(nd_val, 6),
            f"decay={decay}": round(wd_val, 6),
            "delta": round(delta, 6),
            "improved": delta < 0,
        })

    comparison = pd.DataFrame(comparison_rows)

    return DCDecayComparisonResult(
        no_decay=no_decay_result,
        with_decay=with_decay_result,
        decay_value=decay,
        comparison=comparison,
    )


@dataclass(frozen=True)
class DCCalibrationBacktestResult:
    """Dixon-Coles backtest with calibration applied."""

    backtest: DixonColesBacktestResult
    calibration: CalibrationReport
    metrics: dict[str, float]


def run_dc_backtest_with_calibration(
    team_match_df: pd.DataFrame,
    split_cfg: TimeSplitConfig | None = None,
    *,
    decay: float | None = None,
    half_life_days: float | None = None,
    calibration_method: str = "isotonic",
    max_goals: int = 10,
) -> DCCalibrationBacktestResult:
    """Run Dixon-Coles backtest and apply probability calibration.

    Parameters
    ----------
    team_match_df : DataFrame with match data.
    split_cfg : Time split configuration.
    decay : Exponential decay parameter.
    half_life_days : Half-life for time decay (ignored if decay is set).
    calibration_method : "isotonic" or "platt".
    max_goals : Maximum goals for score matrix.

    Returns
    -------
    DCCalibrationBacktestResult with backtest, calibration report, and combined metrics.
    """
    bt_result = run_dixon_coles_backtest(
        team_match_df, split_cfg,
        max_goals=max_goals, decay=decay, half_life_days=half_life_days,
    )

    cal_report = calibrate_predictions(
        bt_result.predictions, method=calibration_method,
    )

    metrics = {
        "log_loss_exact": bt_result.metrics["log_loss_exact"],
        "brier_1x2_before": cal_report.brier_before,
        "brier_1x2_after": cal_report.brier_after,
        "rps_before": cal_report.rps_before,
        "rps_after": cal_report.rps_after,
        "brier_improvement": cal_report.brier_before - cal_report.brier_after,
        "rps_improvement": cal_report.rps_before - cal_report.rps_after,
        "n_matches": cal_report.n_matches,
    }

    return DCCalibrationBacktestResult(
        backtest=bt_result,
        calibration=cal_report,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Calibration drift monitoring
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationDriftReport:
    """Report on calibration drift across time windows.

    Tracks how prediction metrics (RPS, Brier, LogLoss) change over time
    windows, helping identify when a model's calibration degrades.
    """

    windows: list[dict[str, Any]]
    overall_metrics: dict[str, float]
    drift_detected: bool
    drift_metric: str
    drift_threshold: float
    latest_window: dict[str, Any] | None


def compute_calibration_drift(
    predictions: pd.DataFrame,
    *,
    window_col: str = "match_date",
    window_size: str = "90D",
    metrics: tuple[str, ...] = ("rps_1x2", "brier_1x2", "log_loss_exact"),
    drift_metric: str = "rps_1x2",
    drift_threshold: float = 0.05,
) -> CalibrationDriftReport:
    """Compute calibration drift across time windows.

    Parameters
    ----------
    predictions : DataFrame with columns home_win_probability, draw_probability,
        away_win_probability, actual_outcome, and ``window_col``.
    window_col : column to use for time-based windowing (default match_date).
    window_size : pandas frequency string for window size (default "90D" = 90 days).
    metrics : metrics to compute per window.
    drift_metric : metric to check for drift.
    drift_threshold : relative change threshold for drift detection.
        If the latest window's drift_metric exceeds the historical average
        by more than this fraction, drift is detected.

    Returns
    -------
    CalibrationDriftReport with per-window metrics and drift status.
    """
    required = {
        "home_win_probability",
        "draw_probability",
        "away_win_probability",
        "actual_outcome",
        window_col,
    }
    missing = required.difference(predictions.columns)
    if missing:
        raise ValueError(f"predictions missing columns: {', '.join(sorted(missing))}")

    df = predictions.copy()
    df[window_col] = pd.to_datetime(df[window_col], errors="coerce")
    df = df.dropna(subset=[window_col]).sort_values(window_col)

    if df.empty:
        return CalibrationDriftReport(
            windows=[],
            overall_metrics={},
            drift_detected=False,
            drift_metric=drift_metric,
            drift_threshold=drift_threshold,
            latest_window=None,
        )

    # Compute overall metrics
    overall = _compute_window_metrics(df, metrics)

    # Compute per-window metrics
    windows: list[dict[str, Any]] = []
    min_date = df[window_col].min()
    max_date = df[window_col].max()

    current_start = min_date
    while current_start <= max_date:
        current_end = current_start + pd.Timedelta(window_size)
        window_df = df[
            (df[window_col] >= current_start) & (df[window_col] < current_end)
        ]
        if not window_df.empty:
            window_metrics = _compute_window_metrics(window_df, metrics)
            window_entry: dict[str, Any] = {
                "start_date": current_start.strftime("%Y-%m-%d"),
                "end_date": current_end.strftime("%Y-%m-%d"),
                "n_matches": len(window_df),
                **window_metrics,
            }
            windows.append(window_entry)
        current_start = current_end

    # Detect drift
    drift_detected = False
    latest_window = windows[-1] if windows else None
    if len(windows) >= 2 and latest_window is not None:
        historical = windows[:-1]
        avg_metric = float(np.mean([w.get(drift_metric, 0.0) for w in historical]))
        latest_metric = float(latest_window.get(drift_metric, 0.0))
        if avg_metric > 0:
            relative_change = (latest_metric - avg_metric) / avg_metric
            drift_detected = relative_change > drift_threshold

    return CalibrationDriftReport(
        windows=windows,
        overall_metrics=overall,
        drift_detected=drift_detected,
        drift_metric=drift_metric,
        drift_threshold=drift_threshold,
        latest_window=latest_window,
    )


def _compute_window_metrics(
    df: pd.DataFrame,
    metrics: tuple[str, ...] = ("rps_1x2", "brier_1x2", "log_loss_exact"),
) -> dict[str, float]:
    """Compute prediction metrics for a window of predictions."""
    probs = df[
        ["home_win_probability", "draw_probability", "away_win_probability"]
    ].to_numpy()
    actual = df["actual_outcome"].to_numpy()

    outcome_map = {"home_win": 0, "draw": 1, "away_win": 2}
    actual_idx = np.array([outcome_map.get(o, 1) for o in actual])
    actual_onehot = np.zeros_like(probs)
    valid = actual_idx < probs.shape[1]
    actual_onehot[np.arange(len(actual_idx))[valid], actual_idx[valid]] = 1.0

    result: dict[str, float] = {}
    result["n_matches"] = len(df)

    if "rps_1x2" in metrics:
        cum_probs = np.cumsum(probs, axis=1)
        cum_actual = np.cumsum(actual_onehot, axis=1)
        rps = float(np.mean(np.sum((cum_probs - cum_actual) ** 2, axis=1) / 2.0))
        result["rps_1x2"] = rps

    if "brier_1x2" in metrics:
        brier = float(np.mean(np.sum((probs - actual_onehot) ** 2, axis=1)))
        result["brier_1x2"] = brier

    if "log_loss_exact" in metrics:
        # Clip probabilities to avoid log(0)
        eps = 1e-15
        clipped = np.clip(probs, eps, 1.0 - eps)
        ll = -float(np.mean(np.sum(actual_onehot * np.log(clipped), axis=1)))
        result["log_loss_exact"] = ll

    return result


# ---------------------------------------------------------------------------
# Calibration comparison (raw vs recalibrated)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationComparison:
    """Per-score-line comparison of raw vs recalibrated predictions.

    ``overall`` holds aggregate Brier/RPS for raw and recalibrated
    probabilities. ``by_score_line`` breaks the comparison down by
    common low-score outcomes (0-0, 1-0, 0-1, 1-1, 2-1, 1-2, 2-0, 0-2)
    so users can see where isotonic recalibration helps most.
    ``improvement`` expresses the relative change as a percentage
    (negative = improvement, since lower Brier/RPS is better).
    """

    overall: dict[str, float]
    by_score_line: list[dict[str, Any]]
    n_matches: int
    improvement: dict[str, float]


def compute_calibration_comparison(
    predictions: pd.DataFrame,
    calibrator: object,
) -> CalibrationComparison:
    """Compare raw vs isotonic-recalibrated predictions per score line.

    Parameters
    ----------
    predictions : DataFrame with ``home_win_probability``,
        ``draw_probability``, ``away_win_probability``, ``actual_outcome``
        and optionally ``home_goals``/``away_goals``.
    calibrator : IsotonicCalibrator with fitted isotonic regressors.

    Returns
    -------
    CalibrationComparison with overall and per-score-line metrics.
    """
    from scoutfootball.models.match_prediction import (
        _compute_rps,
        apply_recalibration,
    )

    required = {
        "home_win_probability", "draw_probability",
        "away_win_probability", "actual_outcome",
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    probs = predictions.loc[
        :, ["home_win_probability", "draw_probability", "away_win_probability"]
    ].to_numpy()
    outcome_map = {"home_win": 0, "draw": 1, "away_win": 2}
    actual_idx = np.array([outcome_map[o] for o in predictions["actual_outcome"]])
    actual_onehot = np.zeros_like(probs)
    actual_onehot[np.arange(len(actual_idx)), actual_idx] = 1.0

    # Recalibrated probabilities
    recalibrated = np.array([
        list(apply_recalibration(
            calibrator,
            float(probs[i, 0]),
            float(probs[i, 1]),
            float(probs[i, 2]),
        ))
        for i in range(len(predictions))
    ])

    brier_raw = float(np.mean(np.sum((probs - actual_onehot) ** 2, axis=1)))
    brier_recal = float(np.mean(np.sum((recalibrated - actual_onehot) ** 2, axis=1)))
    rps_raw = _compute_rps(probs, actual_onehot)
    rps_recal = _compute_rps(recalibrated, actual_onehot)

    overall = {
        "brier_raw": brier_raw,
        "brier_recalibrated": brier_recal,
        "rps_raw": rps_raw,
        "rps_recalibrated": rps_recal,
    }

    improvement: dict[str, float] = {}
    for metric, raw_val, recal_val in [
        ("brier", brier_raw, brier_recal),
        ("rps", rps_raw, rps_recal),
    ]:
        if raw_val > 0:
            improvement[f"{metric}_improvement_pct"] = float(
                (recal_val - raw_val) / raw_val * 100
            )
        else:
            improvement[f"{metric}_improvement_pct"] = 0.0

    # Per-score-line breakdown
    by_score_line: list[dict[str, Any]] = []
    has_goals = "home_goals" in predictions.columns and "away_goals" in predictions.columns
    if has_goals:
        score_lines = [(0, 0), (1, 0), (0, 1), (1, 1), (2, 1), (1, 2), (2, 0), (0, 2)]
        for hg, ag in score_lines:
            mask = (predictions["home_goals"] == hg) & (predictions["away_goals"] == ag)
            n = int(mask.sum())
            if n < 5:
                continue
            raw_subset = probs[mask]
            recal_subset = recalibrated[mask]
            actual_subset = actual_onehot[mask]
            sl_brier_raw = float(np.mean(np.sum((raw_subset - actual_subset) ** 2, axis=1)))
            sl_brier_recal = float(np.mean(np.sum((recal_subset - actual_subset) ** 2, axis=1)))
            sl_rps_raw = _compute_rps(raw_subset, actual_subset)
            sl_rps_recal = _compute_rps(recal_subset, actual_subset)
            entry: dict[str, Any] = {
                "score_line": f"{hg}-{ag}",
                "n_matches": n,
                "brier_raw": sl_brier_raw,
                "brier_recalibrated": sl_brier_recal,
                "rps_raw": sl_rps_raw,
                "rps_recalibrated": sl_rps_recal,
            }
            if sl_brier_raw > 0:
                entry["brier_improvement_pct"] = float(
                    (sl_brier_recal - sl_brier_raw) / sl_brier_raw * 100
                )
            else:
                entry["brier_improvement_pct"] = 0.0
            if sl_rps_raw > 0:
                entry["rps_improvement_pct"] = float(
                    (sl_rps_recal - sl_rps_raw) / sl_rps_raw * 100
                )
            else:
                entry["rps_improvement_pct"] = 0.0
            by_score_line.append(entry)

    return CalibrationComparison(
        overall=overall,
        by_score_line=by_score_line,
        n_matches=len(predictions),
        improvement=improvement,
    )


# ---------------------------------------------------------------------------
# Decay parameter tuning
# ---------------------------------------------------------------------------

DEFAULT_DECAY_CANDIDATES: tuple[float, ...] = (
    0.0,    # no decay
    0.001,  # very slow decay (~693-day half-life)
    0.002,  # slow decay (~347-day half-life)
    0.003,  # moderate-slow (~231-day half-life)
    0.005,  # Dixon-Coles paper recommended (~139-day half-life)
    0.008,  # moderate-fast (~87-day half-life)
    0.010,  # fast (~69-day half-life)
    0.015,  # very fast (~46-day half-life)
    0.020,  # aggressive (~35-day half-life)
)


@dataclass(frozen=True)
class DecayTuningResult:
    """Result of Dixon-Coles time-decay parameter grid search.

    ``candidate_metrics`` maps each decay value to its backtest metrics
    (log_loss_exact, brier_1x2, rps_1x2). ``best_decay`` is the candidate
    that minimises ``selection_metric``. ``selection_metric`` is one of
    ``log_loss_exact``, ``brier_1x2``, ``rps_1x2`` (default: ``rps_1x2``).
    """

    best_decay: float
    selection_metric: str
    candidate_metrics: dict[float, dict[str, float]]
    comparison_table: pd.DataFrame
    n_folds: int
    n_matches: int


def tune_dixon_coles_decay(
    team_match_df: pd.DataFrame,
    *,
    decay_candidates: tuple[float, ...] | list[float] | None = None,
    split_cfg: TimeSplitConfig | None = None,
    selection_metric: str = "rps_1x2",
    max_goals: int = 10,
) -> DecayTuningResult:
    """Grid-search the Dixon-Coles time-decay parameter via past-only backtest.

    For each candidate decay value, runs a full time-series cross-validation
    backtest and collects ``log_loss_exact``, ``brier_1x2``, and ``rps_1x2``.
    The candidate with the lowest ``selection_metric`` is returned as best.

    Parameters
    ----------
    team_match_df : DataFrame with match data (must include ``match_date``).
    decay_candidates : Sequence of decay values to evaluate. Defaults to
        :data:`DEFAULT_DECAY_CANDIDATES`.
    split_cfg : Time split configuration (default: 3 folds, no gap).
    selection_metric : Metric to minimise — one of ``log_loss_exact``,
        ``brier_1x2``, ``rps_1x2`` (default: ``rps_1x2``).
    max_goals : Maximum goals for score matrix.

    Returns
    -------
    DecayTuningResult with best decay, per-candidate metrics, and comparison.
    """
    valid_metrics = {"log_loss_exact", "brier_1x2", "rps_1x2"}
    if selection_metric not in valid_metrics:
        raise ValueError(
            f"selection_metric must be one of {valid_metrics}, got {selection_metric!r}"
        )

    candidates = (
        list(decay_candidates)
        if decay_candidates is not None
        else list(DEFAULT_DECAY_CANDIDATES)
    )
    if not candidates:
        raise ValueError("decay_candidates must not be empty")

    config = split_cfg or TimeSplitConfig()
    candidate_metrics: dict[float, dict[str, float]] = {}
    n_folds = config.n_splits
    n_matches = 0

    for decay_val in candidates:
        try:
            result = run_dixon_coles_backtest(
                team_match_df, config,
                max_goals=max_goals, decay=decay_val if decay_val > 0 else None,
            )
            candidate_metrics[decay_val] = result.metrics
            n_matches = len(result.predictions)
        except (ValueError, RuntimeError, OverflowError, ArithmeticError, FloatingPointError):
            # If a particular decay fails, record NaN metrics
            candidate_metrics[decay_val] = {
                "log_loss_exact": float("inf"),
                "brier_1x2": float("inf"),
                "rps_1x2": float("inf"),
            }

    # Build comparison table
    rows = []
    for decay_val in candidates:
        m = candidate_metrics[decay_val]
        rows.append({
            "decay": decay_val,
            "half_life_days": round(np.log(2) / decay_val, 1) if decay_val > 0 else float("inf"),
            "log_loss_exact": round(m["log_loss_exact"], 6),
            "brier_1x2": round(m["brier_1x2"], 6),
            "rps_1x2": round(m["rps_1x2"], 6),
        })
    comparison = pd.DataFrame(rows)

    # Select best decay by the chosen metric
    best_decay = min(candidates, key=lambda d: candidate_metrics[d][selection_metric])

    return DecayTuningResult(
        best_decay=best_decay,
        selection_metric=selection_metric,
        candidate_metrics=candidate_metrics,
        comparison_table=comparison,
        n_folds=n_folds,
        n_matches=n_matches,
    )

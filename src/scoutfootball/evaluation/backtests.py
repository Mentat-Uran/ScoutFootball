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
    ``by_league`` breaks the comparison down by competition (when the
    ``league`` column is present), requiring at least ``min_per_league``
    matches per league for a stable estimate.
    """

    overall: dict[str, float]
    by_score_line: list[dict[str, Any]]
    n_matches: int
    improvement: dict[str, float]
    by_league: list[dict[str, Any]] = ()  # default empty tuple for backward compat


def compute_calibration_comparison(
    predictions: pd.DataFrame,
    calibrator: object,
    *,
    min_per_league: int = 20,
) -> CalibrationComparison:
    """Compare raw vs isotonic-recalibrated predictions per score line.

    Parameters
    ----------
    predictions : DataFrame with ``home_win_probability``,
        ``draw_probability``, ``away_win_probability``, ``actual_outcome``
        and optionally ``home_goals``/``away_goals``. When a ``league``
        column is present, per-league breakdown is also computed.
    calibrator : IsotonicCalibrator with fitted isotonic regressors.
    min_per_league : minimum matches required for a league to appear in
        the ``by_league`` breakdown (default 20).

    Returns
    -------
    CalibrationComparison with overall, per-score-line and per-league metrics.
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

    # Per-league breakdown (only when league column is present)
    by_league: list[dict[str, Any]] = []
    if "league" in predictions.columns:
        for league_name, group in predictions.groupby("league"):
            n_lg = len(group)
            if n_lg < min_per_league:
                continue
            lg_probs = group.loc[
                :, ["home_win_probability", "draw_probability", "away_win_probability"]
            ].to_numpy()
            lg_outcome_map = {"home_win": 0, "draw": 1, "away_win": 2}
            lg_actual_idx = np.array(
                [lg_outcome_map[o] for o in group["actual_outcome"]]
            )
            lg_actual_onehot = np.zeros_like(lg_probs)
            lg_actual_onehot[np.arange(len(lg_actual_idx)), lg_actual_idx] = 1.0
            lg_recalibrated = np.array([
                list(apply_recalibration(
                    calibrator,
                    float(lg_probs[i, 0]),
                    float(lg_probs[i, 1]),
                    float(lg_probs[i, 2]),
                ))
                for i in range(len(group))
            ])
            lg_brier_raw = float(
                np.mean(np.sum((lg_probs - lg_actual_onehot) ** 2, axis=1))
            )
            lg_brier_recal = float(
                np.mean(np.sum((lg_recalibrated - lg_actual_onehot) ** 2, axis=1))
            )
            lg_rps_raw = _compute_rps(lg_probs, lg_actual_onehot)
            lg_rps_recal = _compute_rps(lg_recalibrated, lg_actual_onehot)
            lg_entry: dict[str, Any] = {
                "league": str(league_name),
                "n_matches": n_lg,
                "brier_raw": lg_brier_raw,
                "brier_recalibrated": lg_brier_recal,
                "rps_raw": lg_rps_raw,
                "rps_recalibrated": lg_rps_recal,
            }
            if lg_brier_raw > 0:
                lg_entry["brier_improvement_pct"] = float(
                    (lg_brier_recal - lg_brier_raw) / lg_brier_raw * 100
                )
            else:
                lg_entry["brier_improvement_pct"] = 0.0
            if lg_rps_raw > 0:
                lg_entry["rps_improvement_pct"] = float(
                    (lg_rps_recal - lg_rps_raw) / lg_rps_raw * 100
                )
            else:
                lg_entry["rps_improvement_pct"] = 0.0
            by_league.append(lg_entry)
        # Sort by n_matches descending for a stable, useful order
        by_league.sort(key=lambda e: e["n_matches"], reverse=True)

    return CalibrationComparison(
        overall=overall,
        by_score_line=by_score_line,
        n_matches=len(predictions),
        improvement=improvement,
        by_league=by_league,
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


# ---------------------------------------------------------------------------
# Value betting analysis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValueBetOutcome:
    """Value betting analysis for a single outcome (home/draw/away)."""

    outcome: str
    model_probability: float
    decimal_odds: float
    implied_probability: float
    expected_value: float
    edge: float
    kelly_fraction: float
    recommendation: str


@dataclass(frozen=True)
class ValueBetAnalysis:
    """Value betting analysis for a match with three-way 1X2 market.

    ``outcomes`` is a list of :class:`ValueBetOutcome` for home/draw/away.
    ``best_bet`` is the outcome with the highest positive expected value,
    or ``None`` when no value bet exists. ``overround`` is the bookmaker
    margin (sum of implied probabilities minus 1).
    """

    outcomes: list[ValueBetOutcome]
    best_bet: ValueBetOutcome | None
    overround: float
    total_implied: float


def compute_value_bets(
    model_probabilities: dict[str, float],
    decimal_odds: dict[str, float],
    *,
    min_ev: float = 0.0,
) -> ValueBetAnalysis:
    """Compute value betting analysis from model probabilities and market odds.

    Parameters
    ----------
    model_probabilities : ``{"home_win": p, "draw": p, "away_win": p}``.
    decimal_odds : ``{"home_win": d, "draw": d, "away_win": d}`` (European
        decimal odds, >= 1.0).
    min_ev : Minimum expected value to flag as a value bet (default 0.0,
        meaning any positive EV).

    Returns
    -------
    :class:`ValueBetAnalysis` with per-outcome analysis and best bet.

    Raises
    ------
    ValueError
        If probabilities don't sum to ~1.0, odds are < 1.0, or keys are
        missing.
    """
    required = {"home_win", "draw", "away_win"}
    missing = sorted(required.difference(model_probabilities))
    if missing:
        raise ValueError(f"model_probabilities missing keys: {missing}")
    missing_odds = sorted(required.difference(decimal_odds))
    if missing_odds:
        raise ValueError(f"decimal_odds missing keys: {missing_odds}")

    probs = {k: float(model_probabilities[k]) for k in required}
    odds = {k: float(decimal_odds[k]) for k in required}

    total_prob = sum(probs.values())
    if not np.isclose(total_prob, 1.0, atol=1e-4):
        raise ValueError(
            f"model_probabilities must sum to 1.0, got {total_prob:.6f}"
        )

    for k in required:
        if odds[k] < 1.0:
            raise ValueError(f"decimal_odds[{k!r}] must be >= 1.0, got {odds[k]}")
        if probs[k] < 0.0 or probs[k] > 1.0:
            raise ValueError(f"model_probabilities[{k!r}] must be in [0, 1], got {probs[k]}")

    outcomes: list[ValueBetOutcome] = []
    for outcome_key in required:
        p = probs[outcome_key]
        d = odds[outcome_key]
        implied = 1.0 / d
        ev = p * d - 1.0
        edge = p - implied
        # Kelly fraction: (p * d - 1) / (d - 1), clamped to [0, 1]
        kelly = (p * d - 1.0) / (d - 1.0) if d > 1.0 else 0.0
        kelly = max(0.0, min(1.0, kelly))
        recommendation = "value_bet" if ev > min_ev and kelly > 0 else "no_value"
        outcomes.append(ValueBetOutcome(
            outcome=outcome_key,
            model_probability=p,
            decimal_odds=d,
            implied_probability=implied,
            expected_value=ev,
            edge=edge,
            kelly_fraction=kelly,
            recommendation=recommendation,
        ))

    # Sort outcomes by EV descending for best_bet selection
    sorted_by_ev = sorted(outcomes, key=lambda o: o.expected_value, reverse=True)
    best_bet = next(
        (o for o in sorted_by_ev if o.recommendation == "value_bet"),
        None,
    )
    total_implied = sum(1.0 / odds[k] for k in required)
    overround = total_implied - 1.0

    return ValueBetAnalysis(
        outcomes=outcomes,
        best_bet=best_bet,
        overround=overround,
        total_implied=total_implied,
    )


# ---------------------------------------------------------------------------
# Reliability diagram
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReliabilityBin:
    """One bin in a reliability diagram."""

    bin_lower: float
    bin_upper: float
    bin_center: float
    mean_predicted: float
    observed_frequency: float
    n_samples: int
    outcome: str


@dataclass(frozen=True)
class ReliabilityDiagram:
    """Reliability diagram data for 1X2 calibration visualization.

    ``bins`` is a flat list of :class:`ReliabilityBin` across all outcomes
    and probability bins. ``per_outcome`` maps outcome name to a list of
    bins for that outcome only. ``overall`` contains aggregate metrics.
    """

    bins: list[ReliabilityBin]
    per_outcome: dict[str, list[ReliabilityBin]]
    n_bins: int
    n_predictions: int
    overall: dict[str, float]


def compute_reliability_diagram(
    predictions: pd.DataFrame,
    *,
    n_bins: int = 10,
    min_samples_per_bin: int = 5,
) -> ReliabilityDiagram:
    """Compute a reliability diagram for 1X2 prediction calibration.

    Bins predictions by predicted probability and compares to observed
    frequency for each outcome (home_win, draw, away_win).

    Parameters
    ----------
    predictions : DataFrame with columns ``home_win_probability``,
        ``draw_probability``, ``away_win_probability``, ``actual_outcome``.
    n_bins : Number of probability bins from 0 to 1 (default 10).
    min_samples_per_bin : Bins with fewer samples are excluded (default 5).

    Returns
    -------
    :class:`ReliabilityDiagram` with per-bin and aggregate data.
    """
    required = {
        "home_win_probability", "draw_probability",
        "away_win_probability", "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        raise ValueError(f"predictions missing required columns: {missing}")

    if n_bins < 2:
        raise ValueError("n_bins must be >= 2")

    df = predictions.copy()
    outcomes = ["home_win", "draw", "away_win"]
    prob_cols = {
        "home_win": "home_win_probability",
        "draw": "draw_probability",
        "away_win": "away_win_probability",
    }

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    all_bins: list[ReliabilityBin] = []
    per_outcome: dict[str, list[ReliabilityBin]] = {o: [] for o in outcomes}

    total_samples = 0
    total_abs_error = 0.0
    total_squared_error = 0.0

    for outcome in outcomes:
        prob_col = prob_cols[outcome]
        observed = (df["actual_outcome"] == outcome).astype(float).to_numpy()
        probs = df[prob_col].to_numpy(dtype=float)

        for i in range(n_bins):
            lo = edges[i]
            hi = edges[i + 1]
            if i == n_bins - 1:
                mask = (probs >= lo) & (probs <= hi)
            else:
                mask = (probs >= lo) & (probs < hi)

            count = int(mask.sum())
            if count < min_samples_per_bin:
                continue

            mean_pred = float(probs[mask].mean())
            obs_freq = float(observed[mask].mean())
            center = (lo + hi) / 2.0

            bin_entry = ReliabilityBin(
                bin_lower=float(lo),
                bin_upper=float(hi),
                bin_center=float(center),
                mean_predicted=mean_pred,
                observed_frequency=obs_freq,
                n_samples=count,
                outcome=outcome,
            )
            all_bins.append(bin_entry)
            per_outcome[outcome].append(bin_entry)
            total_samples += count
            total_abs_error += abs(mean_pred - obs_freq) * count
            total_squared_error += (mean_pred - obs_freq) ** 2 * count

    # Aggregate metrics
    if total_samples > 0:
        calibration_error = total_abs_error / total_samples
        rms_calibration_error = float(np.sqrt(total_squared_error / total_samples))
    else:
        calibration_error = 0.0
        rms_calibration_error = 0.0

    # ECE (Expected Calibration Error) — same as calibration_error
    overall = {
        "ece": float(calibration_error),
        "rms_calibration_error": rms_calibration_error,
        "n_bins_used": len(all_bins),
        "n_predictions": len(df),
    }

    return ReliabilityDiagram(
        bins=all_bins,
        per_outcome=per_outcome,
        n_bins=n_bins,
        n_predictions=len(df),
        overall=overall,
    )


# ---------------------------------------------------------------------------
# Per-team prediction accuracy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TeamAccuracyEntry:
    """Prediction accuracy statistics for a single team."""

    team_id: str
    n_predictions: int
    n_correct: int
    hit_rate: float
    avg_confidence: float
    calibration_gap: float
    last_match_date: str | None


@dataclass(frozen=True)
class TeamAccuracyReport:
    """Per-team prediction accuracy report.

    ``entries`` is sorted by ``n_predictions`` descending. ``overall``
    contains aggregate hit rate across all teams.
    """

    entries: list[TeamAccuracyEntry]
    overall_hit_rate: float
    total_predictions: int
    n_teams: int


def compute_team_accuracy(
    predictions: pd.DataFrame,
    *,
    min_predictions: int = 3,
) -> TeamAccuracyReport:
    """Compute per-team prediction accuracy from backtest predictions.

    For each team (appearing as either home or away), computes:
    - ``n_predictions``: number of predictions involving the team
    - ``n_correct``: predictions where the model's top pick matched actual
    - ``hit_rate``: n_correct / n_predictions
    - ``avg_confidence``: mean of the model's top-pick probability
    - ``calibration_gap``: avg_confidence - hit_rate (positive = overconfident)
    - ``last_match_date``: most recent match date for the team

    Parameters
    ----------
    predictions : DataFrame with ``home_team_id``, ``away_team_id``,
        ``home_win_probability``, ``draw_probability``,
        ``away_win_probability``, ``actual_outcome``, and optionally
        ``match_date``.
    min_predictions : Teams with fewer predictions are excluded (default 3).

    Returns
    -------
    :class:`TeamAccuracyReport` sorted by n_predictions descending.
    """
    required = {
        "home_team_id", "away_team_id",
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        raise ValueError(f"predictions missing required columns: {missing}")

    df = predictions.copy()
    has_date = "match_date" in df.columns

    prob_cols = ["home_win_probability", "draw_probability", "away_win_probability"]
    outcome_map = {
        "home_win_probability": "home_win",
        "draw_probability": "draw",
        "away_win_probability": "away_win",
    }

    def _predicted_outcome(row: pd.Series) -> str:
        probs = {col: row[col] for col in prob_cols}
        best = max(probs, key=probs.get)
        return outcome_map[best]

    df["_predicted_outcome"] = df.apply(_predicted_outcome, axis=1)
    df["_correct"] = (df["_predicted_outcome"] == df["actual_outcome"]).astype(int)
    df["_top_prob"] = df[prob_cols].max(axis=1)

    # Collect per-team stats
    team_stats: dict[str, dict] = {}

    for _, row in df.iterrows():
        for team_col in ("home_team_id", "away_team_id"):
            team_id = str(row[team_col])
            if team_id not in team_stats:
                team_stats[team_id] = {
                    "n_predictions": 0,
                    "n_correct": 0,
                    "confidence_sum": 0.0,
                    "last_date": None,
                }
            stats = team_stats[team_id]
            stats["n_predictions"] += 1
            stats["n_correct"] += int(row["_correct"])
            stats["confidence_sum"] += float(row["_top_prob"])
            if has_date:
                d = row.get("match_date")
                if d is not None and str(d) != "NaT":
                    d_str = str(d)[:10]
                    if stats["last_date"] is None or d_str > stats["last_date"]:
                        stats["last_date"] = d_str

    entries: list[TeamAccuracyEntry] = []
    total_correct = 0
    total_predictions = 0

    for team_id, stats in team_stats.items():
        n = stats["n_predictions"]
        if n < min_predictions:
            continue
        correct = stats["n_correct"]
        hit_rate = correct / n if n > 0 else 0.0
        avg_conf = stats["confidence_sum"] / n if n > 0 else 0.0
        entries.append(TeamAccuracyEntry(
            team_id=team_id,
            n_predictions=n,
            n_correct=correct,
            hit_rate=round(hit_rate, 4),
            avg_confidence=round(avg_conf, 4),
            calibration_gap=round(avg_conf - hit_rate, 4),
            last_match_date=stats["last_date"],
        ))
        total_correct += correct
        total_predictions += n

    entries.sort(key=lambda e: e.n_predictions, reverse=True)
    overall_hit_rate = total_correct / total_predictions if total_predictions > 0 else 0.0

    return TeamAccuracyReport(
        entries=entries,
        overall_hit_rate=round(overall_hit_rate, 4),
        total_predictions=total_predictions,
        n_teams=len(entries),
    )


# ---------------------------------------------------------------------------
# Model comparison dashboard
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelComparisonEntry:
    """Per-model metrics for the unified comparison dashboard."""

    model: str
    label: str
    n_predictions: int
    log_loss: float | None
    brier: float | None
    rps: float | None
    accuracy: float | None
    avg_confidence: float | None
    calibration_gap: float | None


@dataclass(frozen=True)
class ModelComparison:
    """Unified comparison of multiple models on aligned predictions.

    ``models`` is a list of :class:`ModelComparisonEntry`, one per model.
    ``metric_winners`` maps metric name to the winning model key.
    ``n_aligned`` is the number of matches shared across all models.
    """

    models: list[ModelComparisonEntry]
    metric_winners: dict[str, str]
    n_aligned: int
    n_models: int


def _compute_prediction_metrics(df: pd.DataFrame) -> dict[str, float | None]:
    """Compute log_loss/brier/rps/accuracy/confidence/calibration_gap.

    Returns a dict with ``None`` values for metrics that cannot be computed
    because the required columns are missing.
    """
    result: dict[str, float | None] = {
        "log_loss": None,
        "brier": None,
        "rps": None,
        "accuracy": None,
        "avg_confidence": None,
        "calibration_gap": None,
    }
    prob_cols = ["home_win_probability", "draw_probability", "away_win_probability"]
    if "actual_outcome" not in df.columns:
        return result
    has_probs = all(c in df.columns for c in prob_cols)
    if not has_probs:
        return result

    n = len(df)
    if n == 0:
        return result

    # Brier and RPS
    probs = df.loc[:, prob_cols].to_numpy(dtype=float)
    actual_vec = np.vstack(
        df["actual_outcome"].map(
            {
                "home_win": [1.0, 0.0, 0.0],
                "draw": [0.0, 1.0, 0.0],
                "away_win": [0.0, 0.0, 1.0],
            },
        ),
    )
    result["brier"] = float(np.mean(np.sum((probs - actual_vec) ** 2, axis=1)))

    # RPS: cumulative over [away, draw, home] ordering
    rps_probs = df.loc[
        :,
        ["away_win_probability", "draw_probability", "home_win_probability"],
    ].to_numpy(dtype=float)
    rps_actual = np.vstack(
        df["actual_outcome"].map(
            {
                "away_win": [1.0, 0.0, 0.0],
                "draw": [0.0, 1.0, 0.0],
                "home_win": [0.0, 0.0, 1.0],
            },
        ),
    )
    cum_probs = np.cumsum(rps_probs, axis=1)
    cum_actual = np.cumsum(rps_actual, axis=1)
    result["rps"] = float(np.mean(np.sum((cum_probs - cum_actual) ** 2, axis=1) / 2.0))

    # Accuracy (hit rate of most-likely outcome)
    outcome_map = {
        "home_win_probability": "home_win",
        "draw_probability": "draw",
        "away_win_probability": "away_win",
    }
    predicted = df[prob_cols].idxmax(axis=1).map(outcome_map)
    correct = (predicted == df["actual_outcome"]).astype(int)
    result["accuracy"] = float(correct.mean())

    # Confidence and calibration gap
    top_probs = df[prob_cols].max(axis=1).to_numpy(dtype=float)
    avg_conf = float(top_probs.mean())
    result["avg_confidence"] = avg_conf
    result["calibration_gap"] = round(avg_conf - result["accuracy"], 4)

    # Log loss (exact score) — only if exact_score_probability column exists
    if "exact_score_probability" in df.columns:
        probabilities = df["exact_score_probability"].clip(lower=1e-12)
        result["log_loss"] = float(-(np.log(probabilities)).mean())

    return result


def compute_model_comparison(
    model_predictions: dict[str, pd.DataFrame],
    *,
    align_on: str = "match_id",
) -> ModelComparison:
    """Compare multiple models on a unified set of aligned predictions.

    Parameters
    ----------
    model_predictions:
        Mapping of model key (e.g. ``"poisson"``, ``"dixon_coles"``) to the
        backtest predictions DataFrame. Each DataFrame must contain at least
        ``home_win_probability``, ``draw_probability``,
        ``away_win_probability``, ``actual_outcome``, and the ``align_on``
        column.
    align_on:
        Column used to align predictions across models (default
        ``"match_id"``). Only matches present in **all** models are scored.

    Returns
    -------
    ModelComparison
        Per-model metrics computed on the aligned intersection, plus the
        winning model per metric (lowest value wins for all metrics except
        ``accuracy``, where highest wins).

    Raises
    ------
    ValueError
        If ``model_predictions`` is empty or a DataFrame is missing the
        ``align_on`` column.
    """
    if not model_predictions:
        raise ValueError("model_predictions must not be empty")

    # Determine the aligned match set (intersection across all models)
    aligned_ids: set | None = None
    for model_key, df in model_predictions.items():
        if align_on not in df.columns:
            raise ValueError(
                f"model_predictions[{model_key!r}] missing align column {align_on!r}"
            )
        ids = set(df[align_on].dropna().tolist())
        if aligned_ids is None:
            aligned_ids = ids
        else:
            aligned_ids &= ids

    if not aligned_ids:
        return ModelComparison(
            models=[],
            metric_winners={},
            n_aligned=0,
            n_models=len(model_predictions),
        )

    metric_keys = ["log_loss", "brier", "rps", "accuracy", "avg_confidence", "calibration_gap"]
    entries: list[ModelComparisonEntry] = []

    for model_key, df in model_predictions.items():
        aligned_df = df[df[align_on].isin(aligned_ids)].copy()
        metrics = _compute_prediction_metrics(aligned_df)
        entries.append(ModelComparisonEntry(
            model=model_key,
            label=model_key.replace("_", " ").title(),
            n_predictions=len(aligned_df),
            log_loss=metrics["log_loss"],
            brier=metrics["brier"],
            rps=metrics["rps"],
            accuracy=metrics["accuracy"],
            avg_confidence=metrics["avg_confidence"],
            calibration_gap=metrics["calibration_gap"],
        ))

    # Determine winners: lower is better for log_loss/brier/rps/calibration_gap;
    # higher is better for accuracy/avg_confidence.
    higher_is_better = {"accuracy", "avg_confidence"}
    metric_winners: dict[str, str] = {}
    for mk in metric_keys:
        candidates: list[tuple[str, float]] = []
        for e in entries:
            v = getattr(e, mk)
            if v is not None:
                candidates.append((e.model, float(v)))
        if not candidates:
            continue
        if mk in higher_is_better:
            winner = max(candidates, key=lambda x: x[1])[0]
        else:
            winner = min(candidates, key=lambda x: x[1])[0]
        metric_winners[mk] = winner

    return ModelComparison(
        models=entries,
        metric_winners=metric_winners,
        n_aligned=len(aligned_ids),
        n_models=len(entries),
    )


# ---------------------------------------------------------------------------
# Score-line calibration matrix
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScorelineCalibrationEntry:
    """Calibration data for a single actual score-line bucket."""

    scoreline: str
    outcome: str
    n_matches: int
    avg_home_win_prob: float
    avg_draw_prob: float
    avg_away_win_prob: float
    actual_home_win_rate: float
    actual_draw_rate: float
    actual_away_win_rate: float


@dataclass(frozen=True)
class ScorelineCalibration:
    """Score-line calibration matrix data.

    ``entries`` is a list of :class:`ScorelineCalibrationEntry`, one per
    actual score-line bucket, sorted by frequency descending.
    ``outcome_summary`` aggregates by 1x2 outcome.
    """

    entries: list[ScorelineCalibrationEntry]
    outcome_summary: list[dict[str, Any]]
    n_matches: int
    n_scorelines: int


def compute_scoreline_calibration(
    predictions: pd.DataFrame,
    *,
    max_scoreline: int = 5,
    min_samples: int = 3,
) -> ScorelineCalibration:
    """Compute score-line calibration: predicted vs actual by score-line bucket.

    Groups predictions by actual score-line (e.g. ``"1-0"``, ``"0-0"``).
    Score-lines where either team's goals exceed ``max_scoreline`` are
    bucketed as ``"{max}+"`` (e.g. ``"5+"``). For each bucket, computes the
    average predicted 1x2 probabilities and the actual 1x2 outcome rates,
    revealing whether the model is well-calibrated for specific score-line
    types.

    Parameters
    ----------
    predictions:
        DataFrame with ``home_goals``, ``away_goals``,
        ``home_win_probability``, ``draw_probability``,
        ``away_win_probability``, and ``actual_outcome`` columns.
    max_scoreline:
        Goals above this value are bucketed as ``"{max}+"`` (default 5).
    min_samples:
        Minimum matches required for a score-line bucket to be included
        (default 3).

    Returns
    -------
    ScorelineCalibration

    Raises
    ------
    ValueError
        If required columns are missing.
    """
    required = {
        "home_goals", "away_goals",
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        raise ValueError(f"predictions missing required columns: {missing}")

    df = predictions.copy()
    df["home_goals"] = pd.to_numeric(df["home_goals"], errors="coerce")
    df["away_goals"] = pd.to_numeric(df["away_goals"], errors="coerce")
    df = df.dropna(subset=["home_goals", "away_goals"])
    df["home_goals"] = df["home_goals"].astype(int)
    df["away_goals"] = df["away_goals"].astype(int)

    def _scoreline_label(h: int, a: int) -> str:
        hl = f"{h}" if h <= max_scoreline else f"{max_scoreline}+"
        al = f"{a}" if a <= max_scoreline else f"{max_scoreline}+"
        return f"{hl}-{al}"

    df["_scoreline"] = df.apply(
        lambda r: _scoreline_label(int(r["home_goals"]), int(r["away_goals"])),
        axis=1,
    )

    entries: list[ScorelineCalibrationEntry] = []
    outcome_acc: dict[str, dict[str, Any]] = {}

    for scoreline, group in df.groupby("_scoreline"):
        n = len(group)
        if n < min_samples:
            continue
        avg_hw = float(group["home_win_probability"].mean())
        avg_d = float(group["draw_probability"].mean())
        avg_aw = float(group["away_win_probability"].mean())
        actual_hw = float((group["actual_outcome"] == "home_win").mean())
        actual_d = float((group["actual_outcome"] == "draw").mean())
        actual_aw = float((group["actual_outcome"] == "away_win").mean())
        # Determine the dominant outcome for this score-line
        if actual_hw >= actual_d and actual_hw >= actual_aw:
            outcome = "home_win"
        elif actual_d >= actual_aw:
            outcome = "draw"
        else:
            outcome = "away_win"
        entries.append(ScorelineCalibrationEntry(
            scoreline=scoreline,
            outcome=outcome,
            n_matches=n,
            avg_home_win_prob=round(avg_hw, 4),
            avg_draw_prob=round(avg_d, 4),
            avg_away_win_prob=round(avg_aw, 4),
            actual_home_win_rate=round(actual_hw, 4),
            actual_draw_rate=round(actual_d, 4),
            actual_away_win_rate=round(actual_aw, 4),
        ))

    entries.sort(key=lambda e: e.n_matches, reverse=True)

    # Outcome summary
    prob_col_map = {
        "home_win": "home_win_probability",
        "draw": "draw_probability",
        "away_win": "away_win_probability",
    }
    for outcome in ("home_win", "draw", "away_win"):
        mask = df["actual_outcome"] == outcome
        n_outcome = int(mask.sum())
        if n_outcome == 0:
            continue
        sub = df[mask]
        prob_col = prob_col_map[outcome]
        outcome_acc[outcome] = {
            "outcome": outcome,
            "n_matches": n_outcome,
            "avg_predicted_prob": round(float(sub[prob_col].mean()), 4),
            "scoreline_distribution": (
                sub["_scoreline"].value_counts().head(5).to_dict()
            ),
        }

    return ScorelineCalibration(
        entries=entries,
        outcome_summary=list(outcome_acc.values()),
        n_matches=len(df),
        n_scorelines=len(entries),
    )


# ---------------------------------------------------------------------------
# Prediction confidence distribution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfidenceBucket:
    """One confidence bucket in the prediction confidence distribution."""

    bucket_label: str
    bucket_lower: float
    bucket_upper: float
    n_predictions: int
    accuracy: float
    avg_confidence: float
    calibration_gap: float


@dataclass(frozen=True)
class ConfidenceDistribution:
    """Distribution of prediction confidence and accuracy per bucket.

    ``buckets`` is a list of :class:`ConfidenceBucket` sorted by confidence
    ascending. ``overall_accuracy`` and ``overall_confidence`` are the
    full-sample aggregates.
    """

    buckets: list[ConfidenceBucket]
    overall_accuracy: float
    overall_confidence: float
    n_predictions: int
    n_buckets: int


def compute_confidence_distribution(
    predictions: pd.DataFrame,
    *,
    n_bins: int = 10,
    min_samples_per_bucket: int = 5,
) -> ConfidenceDistribution:
    """Bucket predictions by max probability and compute accuracy per bucket.

    This reveals whether the model's confidence (max predicted probability)
    is well-calibrated: in a well-calibrated model, a 70% confidence bucket
    should have ~70% accuracy.

    Parameters
    ----------
    predictions:
        DataFrame with ``home_win_probability``, ``draw_probability``,
        ``away_win_probability``, and ``actual_outcome`` columns.
    n_bins:
        Number of equal-width confidence buckets between 0 and 1 (default 10).
    min_samples_per_bucket:
        Buckets with fewer samples are excluded (default 5).

    Returns
    -------
    ConfidenceDistribution

    Raises
    ------
    ValueError
        If ``n_bins`` is not in [2, 50] or required columns are missing.
    """
    if not 2 <= n_bins <= 50:
        raise ValueError(f"n_bins must be in [2, 50], got {n_bins}")

    required = {
        "home_win_probability", "draw_probability",
        "away_win_probability", "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        raise ValueError(f"predictions missing required columns: {missing}")

    prob_cols = ["home_win_probability", "draw_probability", "away_win_probability"]
    outcome_map = {
        "home_win_probability": "home_win",
        "draw_probability": "draw",
        "away_win_probability": "away_win",
    }

    df = predictions.copy()
    df["_top_prob"] = df[prob_cols].max(axis=1).astype(float)
    df["_predicted_outcome"] = df[prob_cols].idxmax(axis=1).map(outcome_map)
    df["_correct"] = (df["_predicted_outcome"] == df["actual_outcome"]).astype(int)

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    buckets: list[ConfidenceBucket] = []
    for i in range(n_bins):
        lo = edges[i]
        hi = edges[i + 1]
        if i == n_bins - 1:
            mask = (df["_top_prob"] >= lo) & (df["_top_prob"] <= hi)
        else:
            mask = (df["_top_prob"] >= lo) & (df["_top_prob"] < hi)
        count = int(mask.sum())
        if count < min_samples_per_bucket:
            continue
        sub = df[mask]
        acc = float(sub["_correct"].mean())
        conf = float(sub["_top_prob"].mean())
        buckets.append(ConfidenceBucket(
            bucket_label=f"{lo:.1f}-{hi:.1f}",
            bucket_lower=round(float(lo), 4),
            bucket_upper=round(float(hi), 4),
            n_predictions=count,
            accuracy=round(acc, 4),
            avg_confidence=round(conf, 4),
            calibration_gap=round(conf - acc, 4),
        ))

    n_total = len(df)
    overall_acc = float(df["_correct"].mean()) if n_total > 0 else 0.0
    overall_conf = float(df["_top_prob"].mean()) if n_total > 0 else 0.0

    return ConfidenceDistribution(
        buckets=buckets,
        overall_accuracy=round(overall_acc, 4),
        overall_confidence=round(overall_conf, 4),
        n_predictions=n_total,
        n_buckets=len(buckets),
    )


# ---------------------------------------------------------------------------
# H2H historical bias correction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class H2HBiasCorrection:
    """Result of adjusting baseline 1x2 probabilities with historical H2H rates.

    Attributes
    ----------
    home_team, away_team:
        Team identifiers echoed back for traceability.
    baseline_probabilities:
        Original 1x2 probabilities (home_win/draw/away_win).
    corrected_probabilities:
        Bias-corrected 1x2 probabilities (sum to 1.0).
    h2h_rates:
        Historical H2H outcome rates from the queried home team's perspective.
    adjustments:
        Per-outcome delta applied (corrected - baseline), after clipping to
        ``max_correction``. Signed.
    n_meetings:
        Number of historical H2H matches used.
    correction_applied:
        True when a non-zero adjustment was applied; False when the H2H sample
        was too small or the correction was clipped to zero.
    disclaimer:
        Plain-text caveat about the correction's limitations.
    """

    home_team: str
    away_team: str
    baseline_probabilities: dict[str, float]
    corrected_probabilities: dict[str, float]
    h2h_rates: dict[str, float]
    adjustments: dict[str, float]
    n_meetings: int
    correction_applied: bool
    disclaimer: str


def compute_h2h_bias_correction(
    home_team: str,
    away_team: str,
    baseline_probabilities: dict[str, float],
    h2h_summary: dict[str, Any],
    *,
    max_correction: float = 0.10,
    min_meetings: int = 3,
    blend_weight: float = 0.25,
) -> H2HBiasCorrection:
    """Adjust baseline 1x2 probabilities using historical H2H outcome rates.

    Computes historical outcome rates from ``h2h_summary`` (home_wins / draws
    / away_wins / total_meetings), then nudges the baseline probabilities
    toward the historical rates by ``blend_weight`` (default 25% blend), with
    per-outcome adjustments clipped to ``±max_correction`` (default 0.10).
    The corrected probabilities are re-normalized to sum to 1.0.

    Parameters
    ----------
    home_team, away_team:
        Team identifiers (echoed back, not used for computation).
    baseline_probabilities:
        Dict with ``home_win``, ``draw``, ``away_win`` keys summing to ~1.0.
    h2h_summary:
        Dict from :func:`scoutfootball.head_to_head.compute_h2h_summary` with
        ``total_meetings``, ``home_wins``, ``draws``, ``away_wins`` keys.
    max_correction:
        Maximum absolute adjustment per outcome (default 0.10).
    min_meetings:
        Minimum H2H sample size required to apply any correction (default 3).
    blend_weight:
        Fraction of the historical rate to blend into the baseline
        (0.0 = no correction, 1.0 = fully replace baseline). Default 0.25.

    Returns
    -------
    H2HBiasCorrection

    Raises
    ------
    ValueError
        If baseline probabilities are missing keys, don't sum to ~1.0, or
        ``blend_weight`` is outside [0, 1].
    """
    if not 0.0 <= blend_weight <= 1.0:
        raise ValueError(f"blend_weight must be in [0, 1], got {blend_weight}")

    required_keys = {"home_win", "draw", "away_win"}
    missing = sorted(required_keys.difference(baseline_probabilities.keys()))
    if missing:
        raise ValueError(f"baseline_probabilities missing keys: {missing}")

    base_home = float(baseline_probabilities["home_win"])
    base_draw = float(baseline_probabilities["draw"])
    base_away = float(baseline_probabilities["away_win"])
    base_sum = base_home + base_draw + base_away
    if not 0.95 <= base_sum <= 1.05:
        raise ValueError(
            f"baseline_probabilities must sum to ~1.0, got {base_sum:.4f}"
        )

    total_meetings = int(h2h_summary.get("total_meetings", 0))
    home_wins = int(h2h_summary.get("home_wins", 0))
    draws = int(h2h_summary.get("draws", 0))
    away_wins = int(h2h_summary.get("away_wins", 0))

    disclaimer = (
        "H2H bias correction is a heuristic nudge based on a small historical "
        "sample and should not replace domain judgment. Corrections are "
        "bounded and blended to avoid overfitting to rare matchup patterns."
    )

    if total_meetings < min_meetings or total_meetings == 0:
        # No correction possible — echo baseline back unchanged.
        rates = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}
        adjustments = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}
        corrected = {"home_win": base_home, "draw": base_draw, "away_win": base_away}
        return H2HBiasCorrection(
            home_team=home_team,
            away_team=away_team,
            baseline_probabilities=corrected,
            corrected_probabilities=corrected,
            h2h_rates=rates,
            adjustments=adjustments,
            n_meetings=total_meetings,
            correction_applied=False,
            disclaimer=disclaimer,
        )

    hist_home = home_wins / total_meetings
    hist_draw = draws / total_meetings
    hist_away = away_wins / total_meetings
    rates = {
        "home_win": round(hist_home, 4),
        "draw": round(hist_draw, 4),
        "away_win": round(hist_away, 4),
    }

    # Raw blend: baseline * (1 - w) + historical * w
    raw_home = base_home * (1.0 - blend_weight) + hist_home * blend_weight
    raw_draw = base_draw * (1.0 - blend_weight) + hist_draw * blend_weight
    raw_away = base_away * (1.0 - blend_weight) + hist_away * blend_weight

    # Clip per-outcome adjustment to ±max_correction relative to baseline.
    adj_home = max(-max_correction, min(max_correction, raw_home - base_home))
    adj_draw = max(-max_correction, min(max_correction, raw_draw - base_draw))
    adj_away = max(-max_correction, min(max_correction, raw_away - base_away))

    corrected_home = base_home + adj_home
    corrected_draw = base_draw + adj_draw
    corrected_away = base_away + adj_away

    # Re-normalize to sum to 1.0 (guard against zero sum).
    total = corrected_home + corrected_draw + corrected_away
    if total <= 0.0:
        corrected_home = base_home
        corrected_draw = base_draw
        corrected_away = base_away
        adj_home = 0.0
        adj_draw = 0.0
        adj_away = 0.0
    else:
        corrected_home /= total
        corrected_draw /= total
        corrected_away /= total

    adjustments = {
        "home_win": round(corrected_home - base_home, 4),
        "draw": round(corrected_draw - base_draw, 4),
        "away_win": round(corrected_away - base_away, 4),
    }
    corrected = {
        "home_win": round(corrected_home, 4),
        "draw": round(corrected_draw, 4),
        "away_win": round(corrected_away, 4),
    }
    correction_applied = any(abs(v) > 1e-6 for v in adjustments.values())

    return H2HBiasCorrection(
        home_team=home_team,
        away_team=away_team,
        baseline_probabilities={
            "home_win": round(base_home, 4),
            "draw": round(base_draw, 4),
            "away_win": round(base_away, 4),
        },
        corrected_probabilities=corrected,
        h2h_rates=rates,
        adjustments=adjustments,
        n_meetings=total_meetings,
        correction_applied=correction_applied,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Prediction error analysis (worst-match identification)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ErrorMatchEntry:
    """A single match with its prediction error contribution."""

    match_id: str | int | None
    home_goals: int | None
    away_goals: int | None
    actual_outcome: str
    predicted_home_win: float
    predicted_draw: float
    predicted_away_win: float
    predicted_outcome: str
    confidence: float
    brier: float
    log_loss: float | None
    correct: bool


@dataclass(frozen=True)
class ErrorAnalysisBucket:
    """Per-confidence-band error summary."""

    bucket_label: str
    bucket_lower: float
    bucket_upper: float
    n_predictions: int
    avg_confidence: float
    accuracy: float
    avg_brier: float
    avg_log_loss: float | None
    worst_matches: list[ErrorMatchEntry]


@dataclass(frozen=True)
class ErrorAnalysisReport:
    """Full error analysis: per-band buckets plus overall worst matches."""

    buckets: list[ErrorAnalysisBucket]
    overall_accuracy: float
    overall_avg_brier: float
    overall_avg_log_loss: float | None
    n_predictions: int
    n_buckets: int
    worst_matches_overall: list[ErrorMatchEntry]


def _brier_per_match(
    home_prob: float, draw_prob: float, away_prob: float, actual: str
) -> float:
    """Per-match Brier score for 1x2 outcomes (lower is better)."""
    actual_vec = {
        "home_win": [1.0, 0.0, 0.0],
        "draw": [0.0, 1.0, 0.0],
        "away_win": [0.0, 0.0, 1.0],
    }.get(actual, [0.0, 0.0, 0.0])
    probs = [home_prob, draw_prob, away_prob]
    return float(
        sum((p - a) ** 2 for p, a in zip(probs, actual_vec, strict=True)) / 2.0
    )


def _log_loss_per_match(
    exact_score_prob: float | None, actual_home: int, actual_away: int
) -> float | None:
    """Per-match log loss contribution (requires exact_score_probability)."""
    if exact_score_prob is None or exact_score_prob <= 0.0:
        return None
    return -float(np.log(exact_score_prob))


def _row_to_error_entry(
    row: pd.Series, has_home_goals: bool, has_away_goals: bool
) -> ErrorMatchEntry:
    """Convert a DataFrame row to an ErrorMatchEntry."""
    ll = row.get("_log_loss")
    home_goals = (
        int(row["home_goals"])
        if has_home_goals and pd.notna(row.get("home_goals"))
        else None
    )
    away_goals = (
        int(row["away_goals"])
        if has_away_goals and pd.notna(row.get("away_goals"))
        else None
    )
    log_loss_val = (
        round(float(ll), 4)
        if ll is not None and pd.notna(ll)
        else None
    )
    return ErrorMatchEntry(
        match_id=row.get("match_id"),
        home_goals=home_goals,
        away_goals=away_goals,
        actual_outcome=str(row["actual_outcome"]),
        predicted_home_win=round(float(row["home_win_probability"]), 4),
        predicted_draw=round(float(row["draw_probability"]), 4),
        predicted_away_win=round(float(row["away_win_probability"]), 4),
        predicted_outcome=str(row["_predicted_outcome"]),
        confidence=round(float(row["_top_prob"]), 4),
        brier=round(float(row["_brier"]), 4),
        log_loss=log_loss_val,
        correct=bool(row["_correct"]),
    )


def _safe_log_loss_avg(series: pd.Series, has_exact: bool) -> float | None:
    """Compute mean log loss, returning None when not applicable."""
    if not has_exact:
        return None
    dropped = series.dropna()
    if dropped.empty:
        return None
    val = float(dropped.mean())
    if np.isnan(val):
        return None
    return round(val, 4)


def compute_error_analysis(
    predictions: pd.DataFrame,
    *,
    n_bins: int = 5,
    min_samples_per_bucket: int = 5,
    top_n: int = 5,
) -> ErrorAnalysisReport:
    """Analyze prediction errors grouped by confidence band.

    Buckets predictions by max predicted probability (confidence) into
    ``n_bins`` equal-width buckets, and per bucket computes accuracy,
    average Brier, average log-loss (when ``exact_score_probability`` is
    present), and the ``top_n`` worst matches (highest Brier).

    Parameters
    ----------
    predictions:
        DataFrame with ``home_win_probability``, ``draw_probability``,
        ``away_win_probability``, ``actual_outcome`` columns. Optional:
        ``match_id``, ``home_goals``, ``away_goals``,
        ``exact_score_probability``.
    n_bins:
        Number of equal-width confidence buckets between 1/3 and 1.0
        (default 5, range [2, 20]). Predictions with confidence below 1/3
        are grouped into the first bucket.
    min_samples_per_bucket:
        Buckets with fewer samples are excluded (default 5).
    top_n:
        Number of worst matches to surface per bucket (default 5, range
        [1, 50]).

    Returns
    -------
    ErrorAnalysisReport

    Raises
    ------
    ValueError
        If ``n_bins`` is not in [2, 20], ``top_n`` is not in [1, 50], or
        required columns are missing.
    """
    if not 2 <= n_bins <= 20:
        raise ValueError(f"n_bins must be in [2, 20], got {n_bins}")
    if not 1 <= top_n <= 50:
        raise ValueError(f"top_n must be in [1, 50], got {top_n}")

    required = {
        "home_win_probability", "draw_probability",
        "away_win_probability", "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        raise ValueError(f"predictions missing required columns: {missing}")

    prob_cols = ["home_win_probability", "draw_probability", "away_win_probability"]
    outcome_map = {
        "home_win_probability": "home_win",
        "draw_probability": "draw",
        "away_win_probability": "away_win",
    }

    df = predictions.copy()
    df["_top_prob"] = df[prob_cols].max(axis=1).astype(float)
    df["_predicted_outcome"] = df[prob_cols].idxmax(axis=1).map(outcome_map)
    df["_correct"] = (df["_predicted_outcome"] == df["actual_outcome"]).astype(int)
    df["_brier"] = df.apply(
        lambda r: _brier_per_match(
            float(r["home_win_probability"]),
            float(r["draw_probability"]),
            float(r["away_win_probability"]),
            r["actual_outcome"],
        ),
        axis=1,
    )

    has_exact = "exact_score_probability" in df.columns
    has_home_goals = "home_goals" in df.columns
    has_away_goals = "away_goals" in df.columns
    if has_exact:
        df["_log_loss"] = df.apply(
            lambda r: _log_loss_per_match(
                float(r["exact_score_probability"])
                if pd.notna(r["exact_score_probability"])
                else None,
                int(r["home_goals"]) if has_home_goals and pd.notna(r.get("home_goals")) else 0,
                int(r["away_goals"]) if has_away_goals and pd.notna(r.get("away_goals")) else 0,
            ),
            axis=1,
        )
    else:
        df["_log_loss"] = None

    # Confidence buckets: 1/n_outcomes (1/3) to 1.0
    lo_floor = 1.0 / 3.0
    edges = np.linspace(lo_floor, 1.0, n_bins + 1)
    buckets: list[ErrorAnalysisBucket] = []
    for i in range(n_bins):
        lo = edges[i]
        hi = edges[i + 1]
        if i == n_bins - 1:
            mask = (df["_top_prob"] >= lo) & (df["_top_prob"] <= hi)
        elif i == 0:
            # First bucket also catches sub-1/3 confidence predictions.
            mask = df["_top_prob"] < hi
        else:
            mask = (df["_top_prob"] >= lo) & (df["_top_prob"] < hi)
        count = int(mask.sum())
        if count < min_samples_per_bucket:
            continue
        sub = df[mask].copy()
        sub_sorted = sub.sort_values("_brier", ascending=False).head(top_n)
        worst: list[ErrorMatchEntry] = [
            _row_to_error_entry(row, has_home_goals, has_away_goals)
            for _, row in sub_sorted.iterrows()
        ]
        avg_log = _safe_log_loss_avg(sub["_log_loss"], has_exact)
        buckets.append(ErrorAnalysisBucket(
            bucket_label=f"{lo:.2f}-{hi:.2f}",
            bucket_lower=round(float(lo), 4),
            bucket_upper=round(float(hi), 4),
            n_predictions=count,
            avg_confidence=round(float(sub["_top_prob"].mean()), 4),
            accuracy=round(float(sub["_correct"].mean()), 4),
            avg_brier=round(float(sub["_brier"].mean()), 4),
            avg_log_loss=avg_log,
            worst_matches=worst,
        ))

    n_total = len(df)
    overall_acc = float(df["_correct"].mean()) if n_total > 0 else 0.0
    overall_brier = float(df["_brier"].mean()) if n_total > 0 else 0.0
    overall_log = _safe_log_loss_avg(df["_log_loss"], has_exact)
    overall_log_raw = (
        float(overall_log) if overall_log is not None else None
    )

    # Overall worst matches
    df_sorted = df.sort_values("_brier", ascending=False).head(top_n)
    worst_overall: list[ErrorMatchEntry] = [
        _row_to_error_entry(row, has_home_goals, has_away_goals)
        for _, row in df_sorted.iterrows()
    ]

    return ErrorAnalysisReport(
        buckets=buckets,
        overall_accuracy=round(overall_acc, 4),
        overall_avg_brier=round(overall_brier, 4),
        overall_avg_log_loss=overall_log_raw,
        n_predictions=n_total,
        n_buckets=len(buckets),
        worst_matches_overall=worst_overall,
    )


# ---------------------------------------------------------------------------
# Outcome distribution analysis (predicted vs actual 1x2 distribution)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutcomeDistributionEntry:
    """Per-outcome predicted vs actual distribution row."""

    outcome: str
    predicted_count: int
    predicted_share: float
    actual_count: int
    actual_share: float
    distribution_gap: float


@dataclass(frozen=True)
class OutcomeDistributionReport:
    """Compares the model's predicted 1x2 distribution to the actual one.

    Reveals whether the model systematically over-predicts one outcome
    (e.g. too many home wins) or under-predicts another (e.g. too few
    draws).
    """

    entries: list[OutcomeDistributionEntry]
    n_predictions: int
    predicted_most_likely: dict[str, int]
    actual_counts: dict[str, int]
    dominant_bias: str
    disclaimer: str


def compute_outcome_distribution(
    predictions: pd.DataFrame,
) -> OutcomeDistributionReport:
    """Compare predicted 1x2 outcome distribution to actual outcomes.

    For each match, the model's "predicted outcome" is the argmax of
    ``home_win_probability`` / ``draw_probability`` / ``away_probability``.
    The function tallies how often each outcome is predicted vs how often
    it actually occurred, and reports the per-outcome distribution gap.

    Parameters
    ----------
    predictions:
        DataFrame with ``home_win_probability``, ``draw_probability``,
        ``away_win_probability``, and ``actual_outcome`` columns.

    Returns
    -------
    OutcomeDistributionReport

    Raises
    ------
    ValueError
        If required columns are missing.
    """
    required = {
        "home_win_probability", "draw_probability",
        "away_win_probability", "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        raise ValueError(f"predictions missing required columns: {missing}")

    prob_cols = ["home_win_probability", "draw_probability", "away_win_probability"]
    outcome_map = {
        "home_win_probability": "home_win",
        "draw_probability": "draw",
        "away_win_probability": "away_win",
    }

    df = predictions.copy()
    df["_predicted_outcome"] = df[prob_cols].idxmax(axis=1).map(outcome_map)

    n_total = len(df)
    disclaimer = (
        "Distribution gaps reflect the model's argmax predictions, not the "
        "mean predicted probability. A non-zero gap indicates systematic "
        "over- or under-prediction of an outcome class."
    )

    if n_total == 0:
        empty_entries = [
            OutcomeDistributionEntry(
                outcome=o,
                predicted_count=0,
                predicted_share=0.0,
                actual_count=0,
                actual_share=0.0,
                distribution_gap=0.0,
            )
            for o in ["home_win", "draw", "away_win"]
        ]
        return OutcomeDistributionReport(
            entries=empty_entries,
            n_predictions=0,
            predicted_most_likely={"home_win": 0, "draw": 0, "away_win": 0},
            actual_counts={"home_win": 0, "draw": 0, "away_win": 0},
            dominant_bias="none",
            disclaimer=disclaimer,
        )

    predicted_counts = {"home_win": 0, "draw": 0, "away_win": 0}
    actual_counts = {"home_win": 0, "draw": 0, "away_win": 0}
    for po in df["_predicted_outcome"]:
        if po in predicted_counts:
            predicted_counts[po] += 1
    for ao in df["actual_outcome"]:
        if ao in actual_counts:
            actual_counts[ao] += 1

    entries: list[OutcomeDistributionEntry] = []
    for outcome in ["home_win", "draw", "away_win"]:
        p_count = predicted_counts[outcome]
        a_count = actual_counts[outcome]
        p_share = p_count / n_total
        a_share = a_count / n_total
        entries.append(OutcomeDistributionEntry(
            outcome=outcome,
            predicted_count=p_count,
            predicted_share=round(p_share, 4),
            actual_count=a_count,
            actual_share=round(a_share, 4),
            distribution_gap=round(p_share - a_share, 4),
        ))

    # Dominant bias = outcome with largest absolute distribution gap.
    max_gap_outcome = max(entries, key=lambda e: abs(e.distribution_gap))
    if abs(max_gap_outcome.distribution_gap) < 1e-4:
        dominant_bias = "none"
    elif max_gap_outcome.distribution_gap > 0:
        dominant_bias = f"over_predicts_{max_gap_outcome.outcome}"
    else:
        dominant_bias = f"under_predicts_{max_gap_outcome.outcome}"

    return OutcomeDistributionReport(
        entries=entries,
        n_predictions=n_total,
        predicted_most_likely=predicted_counts,
        actual_counts=actual_counts,
        dominant_bias=dominant_bias,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Temporal validation backtest (per-window metric trend)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TemporalWindow:
    """Metrics for one time window in a temporal validation backtest."""

    window_label: str
    window_start: str
    window_end: str
    n_matches: int
    accuracy: float
    brier: float
    rps: float
    log_loss: float | None
    avg_confidence: float


@dataclass(frozen=True)
class TemporalValidationReport:
    """Rolling-origin temporal validation report with per-window trends."""

    windows: list[TemporalWindow]
    n_total_matches: int
    n_windows: int
    overall_accuracy: float
    overall_brier: float
    overall_rps: float
    overall_log_loss: float | None
    trend: str
    disclaimer: str


def _accuracy_for_df(df: pd.DataFrame) -> float:
    """Compute accuracy (argmax hit rate) for a predictions DataFrame."""
    if df.empty:
        return 0.0
    probs = df.loc[
        :,
        ["home_win_probability", "draw_probability", "away_win_probability"],
    ].to_numpy()
    predicted_idx = np.argmax(probs, axis=1)
    outcome_map = {"home_win": 0, "draw": 1, "away_win": 2}
    actual_idx = df["actual_outcome"].map(outcome_map).to_numpy()
    return float(np.mean(predicted_idx == actual_idx))


def _avg_confidence_for_df(df: pd.DataFrame) -> float:
    """Compute average confidence (mean of max predicted probability)."""
    if df.empty:
        return 0.0
    probs = df.loc[
        :,
        ["home_win_probability", "draw_probability", "away_win_probability"],
    ].to_numpy()
    return float(np.mean(np.max(probs, axis=1)))


def compute_temporal_validation(
    predictions: pd.DataFrame,
    *,
    n_windows: int = 6,
    min_samples_per_window: int = 10,
) -> TemporalValidationReport:
    """Compute per-window metric trends for temporal validation.

    Groups backtest predictions into equal-count time windows (sorted by
    ``match_date``) and computes accuracy, Brier, RPS, LogLoss, and
    avg_confidence per window. Useful for detecting model drift over time.

    Args:
        predictions: DataFrame with backtest prediction columns.
        n_windows: Number of time windows to create (2–20).
        min_samples_per_window: Minimum samples per window; windows below
            this threshold are merged into the previous window.

    Returns:
        TemporalValidationReport with per-window metrics and trend detection.

    Raises:
        ValueError: If ``n_windows`` is outside [2, 20] or required columns
            are missing.
    """
    required = {
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")
    if not (2 <= n_windows <= 20):
        raise ValueError(f"n_windows must be between 2 and 20, got {n_windows}")

    disclaimer = (
        "Temporal validation shows per-window metric trends; small windows "
        "may have high variance."
    )

    df = predictions.copy()
    df["match_date"] = pd.to_datetime(df.get("match_date"), errors="coerce")
    has_dates = df["match_date"].notna().any()
    if not has_dates:
        df["match_date"] = pd.date_range(
            start="2020-01-01", periods=len(df), freq="D",
        )
    df = df.sort_values("match_date").reset_index(drop=True)

    has_exact = "exact_score_probability" in df.columns

    n_total = len(df)
    if n_total < n_windows * min_samples_per_window:
        n_windows = max(2, n_total // min_samples_per_window)
    if n_total < 2 * min_samples_per_window:
        return TemporalValidationReport(
            windows=[],
            n_total_matches=n_total,
            n_windows=0,
            overall_accuracy=0.0,
            overall_brier=0.0,
            overall_rps=0.0,
            overall_log_loss=None,
            trend="insufficient_data",
            disclaimer=disclaimer,
        )

    window_size = n_total // n_windows
    windows: list[TemporalWindow] = []

    for i in range(n_windows):
        start_idx = i * window_size
        if i == n_windows - 1:
            end_idx = n_total
        else:
            end_idx = (i + 1) * window_size
        chunk = df.iloc[start_idx:end_idx]
        if len(chunk) < min_samples_per_window:
            continue

        w_start = chunk["match_date"].min()
        w_end = chunk["match_date"].max()
        w_label = (
            f"{w_start.strftime('%Y-%m')}"
            if pd.notna(w_start)
            else f"window_{i + 1}"
        )
        if pd.notna(w_start) and pd.notna(w_end) and w_start != w_end:
            w_label = (
                f"{w_start.strftime('%Y-%m')}–{w_end.strftime('%Y-%m')}"
            )

        acc = round(_accuracy_for_df(chunk), 4)
        brier = round(_brier_1x2(chunk), 4)
        rps = round(_ranked_probability_score(chunk), 4)
        ll = None
        if has_exact and "exact_score_probability" in chunk.columns:
            ll_val = _exact_score_log_loss(chunk)
            ll = round(float(ll_val), 4)
        conf = round(_avg_confidence_for_df(chunk), 4)

        windows.append(TemporalWindow(
            window_label=w_label,
            window_start=str(w_start.date()) if pd.notna(w_start) else "",
            window_end=str(w_end.date()) if pd.notna(w_end) else "",
            n_matches=len(chunk),
            accuracy=acc,
            brier=brier,
            rps=rps,
            log_loss=ll,
            avg_confidence=conf,
        ))

    overall_acc = round(_accuracy_for_df(df), 4)
    overall_brier = round(_brier_1x2(df), 4)
    overall_rps = round(_ranked_probability_score(df), 4)
    overall_ll = None
    if has_exact:
        overall_ll = round(float(_exact_score_log_loss(df)), 4)

    # Trend detection: compare first-half vs second-half Brier.
    mid = n_total // 2
    first_half_brier = _brier_1x2(df.iloc[:mid]) if mid > 0 else 0.0
    second_half_brier = _brier_1x2(df.iloc[mid:]) if mid < n_total else 0.0
    delta = second_half_brier - first_half_brier
    if abs(delta) < 0.005:
        trend = "stable"
    elif delta < 0:
        trend = "improving"
    else:
        trend = "degrading"

    return TemporalValidationReport(
        windows=windows,
        n_total_matches=n_total,
        n_windows=len(windows),
        overall_accuracy=overall_acc,
        overall_brier=overall_brier,
        overall_rps=overall_rps,
        overall_log_loss=overall_ll,
        trend=trend,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Probability heatmap (2D density + accuracy grid)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HeatmapCell:
    """One cell in the probability heatmap grid."""

    home_bin: str
    away_bin: str
    home_lo: float
    home_hi: float
    away_lo: float
    away_hi: float
    count: int
    density: float
    accuracy: float
    avg_confidence: float


@dataclass(frozen=True)
class ProbabilityHeatmap:
    """2D grid of home_win vs away_win probability density and accuracy."""

    cells: list[HeatmapCell]
    n_predictions: int
    n_bins: int
    total_density: float
    disclaimer: str


def compute_probability_heatmap(
    predictions: pd.DataFrame,
    *,
    n_bins: int = 5,
    min_samples_per_cell: int = 3,
) -> ProbabilityHeatmap:
    """Compute a 2D heatmap of home_win vs away_win probability density.

    Buckets predictions into an ``n_bins`` × ``n_bins`` grid based on
    ``home_win_probability`` and ``away_win_probability``. Each cell reports
    count, density (fraction of total), accuracy (argmax hit rate), and
    avg_confidence. Cells below ``min_samples_per_cell`` are excluded.

    Args:
        predictions: DataFrame with backtest prediction columns.
        n_bins: Number of bins per axis (2–15).
        min_samples_per_cell: Minimum samples per cell; sparser cells are
            excluded.

    Returns:
        ProbabilityHeatmap with per-cell stats.

    Raises:
        ValueError: If ``n_bins`` is outside [2, 15] or required columns
            are missing.
    """
    required = {
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")
    if not (2 <= n_bins <= 15):
        raise ValueError(f"n_bins must be between 2 and 15, got {n_bins}")

    disclaimer = (
        "Heatmap shows prediction density and accuracy across the "
        "home_win vs away_win probability space."
    )

    df = predictions.copy()
    n_total = len(df)
    if n_total == 0:
        return ProbabilityHeatmap(
            cells=[],
            n_predictions=0,
            n_bins=n_bins,
            total_density=0.0,
            disclaimer=disclaimer,
        )

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    cells: list[HeatmapCell] = []

    for i in range(n_bins):
        h_lo = float(edges[i])
        h_hi = float(edges[i + 1])
        if i == n_bins - 1:
            h_mask = (df["home_win_probability"] >= h_lo) & (
                df["home_win_probability"] <= h_hi
            )
        else:
            h_mask = (df["home_win_probability"] >= h_lo) & (
                df["home_win_probability"] < h_hi
            )
        for j in range(n_bins):
            a_lo = float(edges[j])
            a_hi = float(edges[j + 1])
            if j == n_bins - 1:
                a_mask = (df["away_win_probability"] >= a_lo) & (
                    df["away_win_probability"] <= a_hi
                )
            else:
                a_mask = (df["away_win_probability"] >= a_lo) & (
                    df["away_win_probability"] < a_hi
                )
            chunk = df.loc[h_mask & a_mask]
            count = len(chunk)
            if count < min_samples_per_cell:
                continue
            density = round(count / n_total, 4)
            acc = round(_accuracy_for_df(chunk), 4)
            conf = round(_avg_confidence_for_df(chunk), 4)
            h_label = f"{h_lo:.1f}-{h_hi:.1f}"
            a_label = f"{a_lo:.1f}-{a_hi:.1f}"
            cells.append(HeatmapCell(
                home_bin=h_label,
                away_bin=a_label,
                home_lo=round(h_lo, 2),
                home_hi=round(h_hi, 2),
                away_lo=round(a_lo, 2),
                away_hi=round(a_hi, 2),
                count=count,
                density=density,
                accuracy=acc,
                avg_confidence=conf,
            ))

    total_density = round(sum(c.density for c in cells), 4)
    return ProbabilityHeatmap(
        cells=cells,
        n_predictions=n_total,
        n_bins=n_bins,
        total_density=total_density,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Prediction staleness indicator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PredictionStaleness:
    """Model training date and data freshness indicator."""

    has_backtest: bool
    backtest_start: str
    backtest_end: str
    n_backtest_matches: int
    model_type: str
    days_since_backtest_end: int | None
    staleness_level: str
    disclaimer: str


def compute_prediction_staleness(
    predictions: pd.DataFrame,
    *,
    reference_date: str | None = None,
    model_type: str = "dixon_coles_decay",
) -> PredictionStaleness:
    """Compute model staleness from backtest prediction date range.

    Args:
        predictions: DataFrame with backtest prediction columns (must have
            ``match_date``).
        reference_date: Reference date for staleness calculation (ISO format).
            Defaults to today.
        model_type: Model identifier for the staleness report.

    Returns:
        PredictionStaleness with date range, days since last match, and
        staleness level (fresh/aging/stale/empty).

    Raises:
        ValueError: If required columns are missing.
    """
    if "match_date" not in predictions.columns:
        raise ValueError("predictions is missing required column: match_date")

    disclaimer = (
        "Staleness is based on the backtest data coverage window, not "
        "real-time model retraining status."
    )

    df = predictions.copy()
    df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce")
    df = df.dropna(subset=["match_date"])

    if df.empty:
        return PredictionStaleness(
            has_backtest=False,
            backtest_start="",
            backtest_end="",
            n_backtest_matches=0,
            model_type=model_type,
            days_since_backtest_end=None,
            staleness_level="empty",
            disclaimer=disclaimer,
        )

    b_start = df["match_date"].min()
    b_end = df["match_date"].max()
    n_matches = len(df)

    if reference_date is not None:
        ref = pd.to_datetime(reference_date)
    else:
        ref = pd.Timestamp.now()

    days_since = int((ref - b_end).days)
    if days_since < 0:
        days_since = 0

    if days_since <= 30:
        level = "fresh"
    elif days_since <= 90:
        level = "aging"
    else:
        level = "stale"

    return PredictionStaleness(
        has_backtest=True,
        backtest_start=str(b_start.date()),
        backtest_end=str(b_end.date()),
        n_backtest_matches=n_matches,
        model_type=model_type,
        days_since_backtest_end=days_since,
        staleness_level=level,
        disclaimer=disclaimer,
    )

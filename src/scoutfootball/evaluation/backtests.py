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

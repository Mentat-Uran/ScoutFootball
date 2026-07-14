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

    # MCE (Maximum Calibration Error) — worst-case per-bin gap across
    # all retained bins. Empty bin list yields 0.0.
    if all_bins:
        mce = float(max(
            abs(b.mean_predicted - b.observed_frequency) for b in all_bins
        ))
    else:
        mce = 0.0

    # Overall calibration intercept/slope via OLS regression of
    # observed_frequency on mean_predicted across all retained bins.
    # Ideal values: slope=1.0, intercept=0.0. Slope<1 signals
    # over-confidence (predictions move faster than observed frequencies).
    if len(all_bins) >= 2:
        x = np.array([b.mean_predicted for b in all_bins], dtype=float)
        y = np.array([b.observed_frequency for b in all_bins], dtype=float)
        x_mean = float(x.mean())
        y_mean = float(y.mean())
        denom = float(((x - x_mean) ** 2).sum())
        if denom > 0:
            slope = float(((x - x_mean) * (y - y_mean)).sum() / denom)
            intercept = float(y_mean - slope * x_mean)
        else:
            slope = 0.0
            intercept = y_mean
    else:
        slope = 0.0
        intercept = 0.0

    # Per-outcome intercept/slope (only when ≥2 bins survived for the
    # outcome). Useful for diagnosing which outcome is miscalibrated.
    per_outcome_calibration: dict[str, dict[str, float]] = {}
    for outcome in outcomes:
        outcome_bins = per_outcome[outcome]
        if len(outcome_bins) >= 2:
            xo = np.array([b.mean_predicted for b in outcome_bins], dtype=float)
            yo = np.array([b.observed_frequency for b in outcome_bins], dtype=float)
            xo_mean = float(xo.mean())
            yo_mean = float(yo.mean())
            denom_o = float(((xo - xo_mean) ** 2).sum())
            if denom_o > 0:
                slope_o = float(((xo - xo_mean) * (yo - yo_mean)).sum() / denom_o)
                intercept_o = float(yo_mean - slope_o * xo_mean)
            else:
                slope_o = 0.0
                intercept_o = yo_mean
            per_outcome_calibration[outcome] = {
                "slope": round(slope_o, 4),
                "intercept": round(intercept_o, 4),
                "n_bins": len(outcome_bins),
            }
        else:
            per_outcome_calibration[outcome] = {
                "slope": 0.0,
                "intercept": 0.0,
                "n_bins": len(outcome_bins),
            }

    # ECE (Expected Calibration Error) — same as calibration_error
    overall = {
        "ece": float(calibration_error),
        "rms_calibration_error": rms_calibration_error,
        "mce": mce,
        "calibration_slope": round(slope, 4),
        "calibration_intercept": round(intercept, 4),
        "per_outcome_calibration": per_outcome_calibration,
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


# ---------------------------------------------------------------------------
# Confidence interval plot data (CI width vs match confidence)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CIPlotPoint:
    """One point in the confidence interval plot."""

    match_id: str | int | None
    home_team: str | None
    away_team: str | None
    confidence: float
    ci_lower: float
    ci_upper: float
    ci_width: float
    actual_outcome: str | None
    correct: bool | None


@dataclass(frozen=True)
class CIPlotReport:
    """CI width vs match confidence scatter plot data."""

    points: list[CIPlotPoint]
    n_predictions: int
    avg_confidence: float
    avg_ci_width: float
    correlation: float | None
    disclaimer: str


def compute_confidence_interval_plot(
    predictions: pd.DataFrame,
    *,
    ci_lower_col: str = "home_win_ci_lower",
    ci_upper_col: str = "home_win_ci_upper",
    max_points: int = 500,
) -> CIPlotReport:
    """Compute CI width vs match confidence scatter plot data.

    Each prediction becomes a point with confidence (max predicted
    probability), CI lower/upper bounds, CI width, and correctness flag.
    Useful for visualizing whether high-confidence predictions have
    narrower CIs.

    Args:
        predictions: DataFrame with backtest prediction columns plus
            CI bound columns.
        ci_lower_col: Column name for CI lower bound (default
            ``home_win_ci_lower``).
        ci_upper_col: Column name for CI upper bound (default
            ``home_win_ci_upper``).
        max_points: Maximum number of points to return (subsamples if
            exceeded, keeping first N).

    Returns:
        CIPlotReport with scatter points and summary statistics.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {
        "home_win_probability", "draw_probability", "away_win_probability",
        ci_lower_col, ci_upper_col,
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    disclaimer = (
        "CI plot shows the relationship between prediction confidence and "
        "uncertainty interval width; wider CIs at high confidence may "
        "indicate miscalibration."
    )

    df = predictions.copy()
    n_total = len(df)
    if n_total == 0:
        return CIPlotReport(
            points=[],
            n_predictions=0,
            avg_confidence=0.0,
            avg_ci_width=0.0,
            correlation=None,
            disclaimer=disclaimer,
        )

    probs = df.loc[
        :,
        ["home_win_probability", "draw_probability", "away_win_probability"],
    ].to_numpy()
    df["_confidence"] = np.max(probs, axis=1)
    df["_ci_width"] = df[ci_upper_col] - df[ci_lower_col]

    has_actual = "actual_outcome" in df.columns
    if has_actual:
        outcome_map = {"home_win": 0, "draw": 1, "away_win": 2}
        predicted_idx = np.argmax(probs, axis=1)
        actual_idx = df["actual_outcome"].map(outcome_map).to_numpy()
        df["_correct"] = predicted_idx == actual_idx
    else:
        df["_correct"] = None

    has_match_id = "match_id" in df.columns
    has_home = "home_team_id" in df.columns or "home_team" in df.columns
    has_away = "away_team_id" in df.columns or "away_team" in df.columns
    home_col = "home_team" if "home_team" in df.columns else "home_team_id"
    away_col = "away_team" if "away_team" in df.columns else "away_team_id"

    if len(df) > max_points:
        df = df.iloc[:max_points]

    points: list[CIPlotPoint] = []
    for _, row in df.iterrows():
        mid = row.get("match_id") if has_match_id else None
        ht = row.get(home_col) if has_home else None
        at = row.get(away_col) if has_away else None
        correct_val = bool(row["_correct"]) if has_actual else None
        actual_val = str(row["actual_outcome"]) if has_actual else None
        points.append(CIPlotPoint(
            match_id=mid,
            home_team=str(ht) if ht is not None else None,
            away_team=str(at) if at is not None else None,
            confidence=round(float(row["_confidence"]), 4),
            ci_lower=round(float(row[ci_lower_col]), 4),
            ci_upper=round(float(row[ci_upper_col]), 4),
            ci_width=round(float(row["_ci_width"]), 4),
            actual_outcome=actual_val,
            correct=correct_val,
        ))

    avg_conf = round(float(df["_confidence"].mean()), 4)
    avg_width = round(float(df["_ci_width"].mean()), 4)
    if len(df) >= 2 and df["_confidence"].std() > 0 and df["_ci_width"].std() > 0:
        corr = round(
            float(df["_confidence"].corr(df["_ci_width"])), 4,
        )
    else:
        corr = None

    return CIPlotReport(
        points=points,
        n_predictions=len(points),
        avg_confidence=avg_conf,
        avg_ci_width=avg_width,
        correlation=corr,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Backtest fold comparison (per-fold metrics + stability)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FoldMetrics:
    """Metrics for one cross-validation fold."""

    fold: int
    n_matches: int
    accuracy: float
    brier: float
    rps: float
    log_loss: float | None
    avg_confidence: float


@dataclass(frozen=True)
class FoldComparisonReport:
    """Per-fold metrics comparison with stability indicator."""

    folds: list[FoldMetrics]
    n_folds: int
    n_total_matches: int
    overall_accuracy: float
    overall_brier: float
    overall_rps: float
    overall_log_loss: float | None
    accuracy_std: float
    brier_std: float
    rps_std: float
    stability: str
    disclaimer: str


def compute_fold_comparison(
    predictions: pd.DataFrame,
    *,
    min_samples_per_fold: int = 5,
) -> FoldComparisonReport:
    """Compute per-fold metrics comparison with stability indicator.

    Groups backtest predictions by the ``fold`` column and computes
    accuracy, Brier, RPS, LogLoss, and avg_confidence per fold. Reports
    standard deviation of accuracy/Brier/RPS across folds and a stability
    label (stable/moderate/unstable) based on accuracy std.

    Args:
        predictions: DataFrame with backtest prediction columns plus a
            ``fold`` column.
        min_samples_per_fold: Minimum samples per fold; folds below this
            threshold are excluded.

    Returns:
        FoldComparisonReport with per-fold metrics and stability.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome", "fold",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    disclaimer = (
        "Fold stability is based on the standard deviation of per-fold "
        "accuracy; high variance suggests the model is sensitive to "
        "temporal splits."
    )

    df = predictions.copy()
    has_exact = "exact_score_probability" in df.columns

    fold_ids = sorted(df["fold"].unique())
    folds: list[FoldMetrics] = []
    for fid in fold_ids:
        chunk = df.loc[df["fold"] == fid]
        if len(chunk) < min_samples_per_fold:
            continue
        ll = None
        if has_exact and "exact_score_probability" in chunk.columns:
            ll = round(float(_exact_score_log_loss(chunk)), 4)
        folds.append(FoldMetrics(
            fold=int(fid),
            n_matches=len(chunk),
            accuracy=round(_accuracy_for_df(chunk), 4),
            brier=round(_brier_1x2(chunk), 4),
            rps=round(_ranked_probability_score(chunk), 4),
            log_loss=ll,
            avg_confidence=round(_avg_confidence_for_df(chunk), 4),
        ))

    if not folds:
        return FoldComparisonReport(
            folds=[],
            n_folds=0,
            n_total_matches=0,
            overall_accuracy=0.0,
            overall_brier=0.0,
            overall_rps=0.0,
            overall_log_loss=None,
            accuracy_std=0.0,
            brier_std=0.0,
            rps_std=0.0,
            stability="insufficient_data",
            disclaimer=disclaimer,
        )

    accs = [f.accuracy for f in folds]
    briers = [f.brier for f in folds]
    rpss = [f.rps for f in folds]
    acc_std = round(float(np.std(accs, ddof=0)), 4)
    brier_std = round(float(np.std(briers, ddof=0)), 4)
    rps_std = round(float(np.std(rpss, ddof=0)), 4)

    if acc_std < 0.03:
        stability = "stable"
    elif acc_std < 0.08:
        stability = "moderate"
    else:
        stability = "unstable"

    n_total = sum(f.n_matches for f in folds)
    overall_acc = round(_accuracy_for_df(df), 4)
    overall_brier = round(_brier_1x2(df), 4)
    overall_rps = round(_ranked_probability_score(df), 4)
    overall_ll = None
    if has_exact:
        overall_ll = round(float(_exact_score_log_loss(df)), 4)

    return FoldComparisonReport(
        folds=folds,
        n_folds=len(folds),
        n_total_matches=n_total,
        overall_accuracy=overall_acc,
        overall_brier=overall_brier,
        overall_rps=overall_rps,
        overall_log_loss=overall_ll,
        accuracy_std=acc_std,
        brier_std=brier_std,
        rps_std=rps_std,
        stability=stability,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Per-league error analysis (league-grouped worst predictions)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LeagueErrorSummary:
    """Per-league error summary."""

    league: str
    n_matches: int
    accuracy: float
    brier: float
    rps: float
    log_loss: float | None
    avg_confidence: float
    worst_matches: list[ErrorMatchEntry]


@dataclass(frozen=True)
class LeagueErrorReport:
    """Per-league error analysis report."""

    leagues: list[LeagueErrorSummary]
    n_leagues: int
    n_total_matches: int
    overall_accuracy: float
    overall_brier: float
    disclaimer: str


def compute_league_error_analysis(
    predictions: pd.DataFrame,
    *,
    min_matches_per_league: int = 10,
    top_n: int = 3,
) -> LeagueErrorReport:
    """Compute per-league error analysis with worst predictions.

    Groups backtest predictions by the ``league`` column and computes
    accuracy, Brier, RPS, LogLoss, and avg_confidence per league. Also
    extracts the top-N worst predictions (highest Brier) per league.

    Args:
        predictions: DataFrame with backtest prediction columns plus a
            ``league`` column.
        min_matches_per_league: Minimum matches per league; leagues below
            this threshold are excluded.
        top_n: Number of worst predictions to extract per league.

    Returns:
        LeagueErrorReport with per-league summaries.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome", "league",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    disclaimer = (
        "Per-league error analysis reveals whether the model performs "
        "better or worse on specific competitions; small leagues may "
        "have high variance."
    )

    df = predictions.copy()
    has_exact = "exact_score_probability" in df.columns
    has_home_goals = "home_goals" in df.columns
    has_away_goals = "away_goals" in df.columns

    probs_cols = [
        "home_win_probability", "draw_probability", "away_win_probability",
    ]
    df["_top_prob"] = df[probs_cols].max(axis=1)
    outcome_map = {"home_win": 0, "draw": 1, "away_win": 2}
    df["_predicted_outcome"] = df[probs_cols].idxmax(axis=1).str.replace(
        "_probability", "", regex=False,
    )
    actual_idx = df["actual_outcome"].map(outcome_map)
    predicted_idx = np.argmax(df[probs_cols].to_numpy(), axis=1)
    df["_correct"] = predicted_idx == actual_idx.to_numpy()

    def _brier_row(row: pd.Series) -> float:
        return _brier_per_match(
            row["home_win_probability"],
            row["draw_probability"],
            row["away_win_probability"],
            str(row["actual_outcome"]),
        )

    df["_brier"] = df.apply(_brier_row, axis=1)
    if has_exact:
        df["_log_loss"] = df["exact_score_probability"].apply(
            lambda p: _log_loss_per_match(
                float(p) if pd.notna(p) else None, 0, 0,
            )
        )
    else:
        df["_log_loss"] = None

    leagues: list[LeagueErrorSummary] = []
    league_names = sorted(df["league"].dropna().unique())
    for lg in league_names:
        chunk = df.loc[df["league"] == lg]
        if len(chunk) < min_matches_per_league:
            continue
        ll = _safe_log_loss_avg(chunk["_log_loss"], has_exact) if has_exact else None
        worst = chunk.nlargest(top_n, "_brier")
        worst_entries = [
            _row_to_error_entry(row, has_home_goals, has_away_goals)
            for _, row in worst.iterrows()
        ]
        leagues.append(LeagueErrorSummary(
            league=str(lg),
            n_matches=len(chunk),
            accuracy=round(_accuracy_for_df(chunk), 4),
            brier=round(_brier_1x2(chunk), 4),
            rps=round(_ranked_probability_score(chunk), 4),
            log_loss=ll,
            avg_confidence=round(_avg_confidence_for_df(chunk), 4),
            worst_matches=worst_entries,
        ))

    leagues.sort(key=lambda x: x.n_matches, reverse=True)

    n_total = sum(lg.n_matches for lg in leagues)
    overall_acc = round(_accuracy_for_df(df), 4) if n_total > 0 else 0.0
    overall_brier = round(_brier_1x2(df), 4) if n_total > 0 else 0.0

    return LeagueErrorReport(
        leagues=leagues,
        n_leagues=len(leagues),
        n_total_matches=n_total,
        overall_accuracy=overall_acc,
        overall_brier=overall_brier,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Feature importance ranking (bin-based Brier separation)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureImportanceBin:
    """Per-bin statistics for a feature column."""

    bin_label: str
    bin_lower: float
    bin_upper: float
    n_matches: int
    accuracy: float
    brier: float
    avg_confidence: float


@dataclass(frozen=True)
class FeatureImportanceEntry:
    """Importance summary for a single feature column."""

    feature: str
    importance: float
    mean_value: float
    std_value: float
    n_matches: int
    bins: list[FeatureImportanceBin]


@dataclass(frozen=True)
class FeatureImportanceReport:
    """Aggregated feature importance ranking report."""

    features: list[FeatureImportanceEntry]
    n_features: int
    n_total_matches: int
    overall_brier: float
    disclaimer: str


# Columns that must never be treated as model input features.
_FEATURE_EXCLUDE_COLUMNS = {
    "home_win_probability",
    "draw_probability",
    "away_win_probability",
    "actual_outcome",
    "home_goals",
    "away_goals",
    "match_id",
    "match_date",
    "league",
    "fold",
    "exact_score_probability",
    "home_win_ci_lower",
    "home_win_ci_upper",
    "draw_win_ci_lower",
    "draw_win_ci_upper",
    "away_win_ci_lower",
    "away_win_ci_upper",
    "predicted_outcome",
    "correct",
}


def compute_feature_importance(
    predictions: pd.DataFrame,
    *,
    features: tuple[str, ...] | None = None,
    n_bins: int = 5,
    min_samples_per_bin: int = 10,
) -> FeatureImportanceReport:
    """Rank input features by how strongly they separate prediction error.

    For each numeric feature column, predictions are bucketed into
    ``n_bins`` quantile bins and the per-bin Brier score is computed.
    The importance score is the standard deviation of bin-level Brier
    values (weighted by bin size); higher values indicate the feature
    more strongly separates good vs bad predictions.

    Args:
        predictions: DataFrame with backtest prediction columns plus
            numeric feature columns. When ``features`` is None, numeric
            columns excluding probabilities/outcomes/goals/date/league
            are auto-detected.
        features: Optional explicit list of feature column names.
        n_bins: Number of quantile bins per feature (2-20).
        min_samples_per_bin: Minimum samples per bin; bins below this
            threshold are excluded from importance calculation.

    Returns:
        FeatureImportanceReport with features sorted by importance desc.

    Raises:
        ValueError: If required probability columns are missing or
            ``n_bins`` is outside [2, 20].
    """
    required = {
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    if n_bins < 2 or n_bins > 20:
        raise ValueError(f"n_bins must be in [2, 20], got {n_bins}")

    disclaimer = (
        "Feature importance is computed via bin-wise Brier separation "
        "and reflects association, not causal effect. Features with "
        "small sample sizes per bin may show inflated importance."
    )

    df = predictions.copy()

    def _brier_row(row: pd.Series) -> float:
        return _brier_per_match(
            row["home_win_probability"],
            row["draw_probability"],
            row["away_win_probability"],
            str(row["actual_outcome"]),
        )

    df["_brier"] = df.apply(_brier_row, axis=1)
    overall_brier = round(float(df["_brier"].mean()), 4)

    # Auto-detect feature columns when not provided.
    if features is None:
        feature_cols: list[str] = []
        for col in df.columns:
            if col in _FEATURE_EXCLUDE_COLUMNS or col.startswith("_"):
                continue
            if col == "home_team" or col == "away_team":
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                if df[col].dropna().nunique() > 1:
                    feature_cols.append(col)
    else:
        feature_cols = list(features)
        for fc in feature_cols:
            if fc not in df.columns:
                raise ValueError(f"feature column not found: {fc}")

    entries: list[FeatureImportanceEntry] = []
    probs_cols = [
        "home_win_probability", "draw_probability", "away_win_probability",
    ]
    for col in feature_cols:
        keep_cols = [col, "_brier", "actual_outcome"] + probs_cols
        col_data = df[keep_cols].dropna(subset=[col, "_brier"])
        if len(col_data) < min_samples_per_bin:
            continue
        if col_data[col].nunique() < 2:
            continue
        try:
            col_data = col_data.assign(_bin=pd.qcut(
                col_data[col],
                q=n_bins,
                duplicates="drop",
                labels=False,
            ))
        except ValueError:
            # Sufficient unique values but qcut failed; fall back to equal-width.
            col_data = col_data.assign(_bin=pd.cut(
                col_data[col],
                bins=min(n_bins, col_data[col].nunique()),
                labels=False,
                include_lowest=True,
            ))
        col_data = col_data.dropna(subset=["_bin"])
        if col_data.empty:
            continue

        bins: list[FeatureImportanceBin] = []
        bin_briers: list[float] = []
        bin_weights: list[int] = []
        for bid in sorted(col_data["_bin"].unique()):
            chunk = col_data.loc[col_data["_bin"] == bid]
            if len(chunk) < min_samples_per_bin:
                continue
            bin_brier = float(chunk["_brier"].mean())
            bin_briers.append(bin_brier)
            bin_weights.append(len(chunk))
            bin_lower = float(chunk[col].min())
            bin_upper = float(chunk[col].max())
            bins.append(FeatureImportanceBin(
                bin_label=f"bin_{int(bid)}",
                bin_lower=round(bin_lower, 4),
                bin_upper=round(bin_upper, 4),
                n_matches=len(chunk),
                accuracy=round(_accuracy_for_df(chunk), 4),
                brier=round(bin_brier, 4),
                avg_confidence=round(_avg_confidence_for_df(chunk), 4),
            ))

        if len(bin_briers) < 2:
            continue

        # Weighted std of bin Brier scores.
        weights = np.array(bin_weights, dtype=float)
        values = np.array(bin_briers, dtype=float)
        weighted_mean = float(np.average(values, weights=weights))
        if len(values) > 1:
            variance = float(
                np.average((values - weighted_mean) ** 2, weights=weights)
            )
            importance = float(np.sqrt(variance))
        else:
            importance = 0.0

        entries.append(FeatureImportanceEntry(
            feature=col,
            importance=round(importance, 6),
            mean_value=round(float(col_data[col].mean()), 4),
            std_value=round(float(col_data[col].std()), 4),
            n_matches=len(col_data),
            bins=bins,
        ))

    entries.sort(key=lambda x: x.importance, reverse=True)

    n_total = sum(e.n_matches for e in entries) if entries else 0
    return FeatureImportanceReport(
        features=entries,
        n_features=len(entries),
        n_total_matches=n_total,
        overall_brier=overall_brier,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Confidence band coverage analysis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoverageBucket:
    """Per-confidence-bucket coverage statistics."""

    bucket_label: str
    confidence_lower: float
    confidence_upper: float
    n_matches: int
    empirical_coverage: float
    avg_ci_width: float
    nominal_coverage: float | None


@dataclass(frozen=True)
class CICoverageReport:
    """Confidence band coverage analysis report."""

    overall_coverage: float
    avg_ci_width: float
    n_matches: int
    nominal_level: float | None
    coverage_assessment: str
    buckets: list[CoverageBucket]
    disclaimer: str


def compute_ci_coverage(
    predictions: pd.DataFrame,
    *,
    ci_lower_col: str = "home_win_ci_lower",
    ci_upper_col: str = "home_win_ci_upper",
    nominal_level: float | None = None,
    n_bins: int = 5,
    min_samples_per_bucket: int = 10,
) -> CICoverageReport:
    """Validate whether bootstrap confidence bands achieve nominal coverage.

    For each prediction, checks whether the actual home-win indicator
    (1 if ``actual_outcome`` == "home_win", else 0) falls within the
    interval ``[ci_lower, ci_upper]``. Computes the empirical coverage
    and compares it to the nominal level when provided.

    Args:
        predictions: DataFrame with CI columns plus ``actual_outcome``.
        ci_lower_col: Column name for CI lower bound (default
            ``home_win_ci_lower``).
        ci_upper_col: Column name for CI upper bound (default
            ``home_win_ci_upper``).
        nominal_level: Optional nominal coverage level (e.g., 0.80 for
            80% CIs). When provided, coverage assessment is computed.
        n_bins: Number of confidence buckets (2-20).
        min_samples_per_bucket: Minimum samples per bucket.

    Returns:
        CICoverageReport with overall and per-bucket coverage stats.

    Raises:
        ValueError: If CI columns or ``actual_outcome`` are missing, or
            ``n_bins`` is outside [2, 20].
    """
    required = {ci_lower_col, ci_upper_col, "actual_outcome"}
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    if n_bins < 2 or n_bins > 20:
        raise ValueError(f"n_bins must be in [2, 20], got {n_bins}")

    disclaimer = (
        "Coverage analysis validates whether bootstrap confidence "
        "intervals achieve their nominal coverage. Undercoverage (<80%) "
        "indicates CIs are too narrow; overcoverage (>95%) indicates "
        "CIs are too wide. Small buckets may have high variance."
    )

    df = predictions.copy()
    df["_ci_lower"] = pd.to_numeric(df[ci_lower_col], errors="coerce")
    df["_ci_upper"] = pd.to_numeric(df[ci_upper_col], errors="coerce")
    df = df.dropna(subset=["_ci_lower", "_ci_upper", "actual_outcome"])

    if df.empty:
        return CICoverageReport(
            overall_coverage=0.0,
            avg_ci_width=0.0,
            n_matches=0,
            nominal_level=nominal_level,
            coverage_assessment="insufficient_data",
            buckets=[],
            disclaimer=disclaimer,
        )

    df["_actual_home_win"] = (
        df["actual_outcome"].astype(str) == "home_win"
    ).astype(float)
    df["_ci_width"] = (df["_ci_upper"] - df["_ci_lower"]).clip(lower=0.0)
    df["_covered"] = (
        (df["_actual_home_win"] >= df["_ci_lower"])
        & (df["_actual_home_win"] <= df["_ci_upper"])
    )

    overall_coverage = float(df["_covered"].mean())
    avg_ci_width = float(df["_ci_width"].mean())

    # Coverage assessment against nominal level.
    if nominal_level is not None:
        diff = overall_coverage - float(nominal_level)
        if diff < -0.05:
            assessment = "undercoverage"
        elif diff > 0.05:
            assessment = "overcoverage"
        else:
            assessment = "well_calibrated"
    else:
        # Without a nominal level, use absolute thresholds.
        if overall_coverage < 0.80:
            assessment = "undercoverage"
        elif overall_coverage > 0.95:
            assessment = "overcoverage"
        else:
            assessment = "well_calibrated"

    # Per-confidence-bucket coverage.
    probs_cols = [
        "home_win_probability", "draw_probability", "away_win_probability",
    ]
    if all(c in df.columns for c in probs_cols):
        df["_confidence"] = df[probs_cols].max(axis=1)
    elif "home_win_probability" in df.columns:
        df["_confidence"] = df["home_win_probability"]
    else:
        df["_confidence"] = df["_ci_lower"]

    try:
        df["_bucket"] = pd.qcut(
            df["_confidence"],
            q=n_bins,
            duplicates="drop",
            labels=False,
        )
    except ValueError:
        df["_bucket"] = pd.cut(
            df["_confidence"],
            bins=min(n_bins, df["_confidence"].nunique()),
            labels=False,
            include_lowest=True,
        )

    buckets: list[CoverageBucket] = []
    for bid in sorted(df["_bucket"].dropna().unique()):
        chunk = df.loc[df["_bucket"] == bid]
        if len(chunk) < min_samples_per_bucket:
            continue
        conf_lower = float(chunk["_confidence"].min())
        conf_upper = float(chunk["_confidence"].max())
        buckets.append(CoverageBucket(
            bucket_label=f"conf_bin_{int(bid)}",
            confidence_lower=round(conf_lower, 4),
            confidence_upper=round(conf_upper, 4),
            n_matches=len(chunk),
            empirical_coverage=round(float(chunk["_covered"].mean()), 4),
            avg_ci_width=round(float(chunk["_ci_width"].mean()), 4),
            nominal_coverage=round(float(nominal_level), 4) if nominal_level else None,
        ))

    return CICoverageReport(
        overall_coverage=round(overall_coverage, 4),
        avg_ci_width=round(avg_ci_width, 4),
        n_matches=len(df),
        nominal_level=round(float(nominal_level), 4) if nominal_level else None,
        coverage_assessment=assessment,
        buckets=buckets,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Calibration drift heatmap (window × confidence bucket grid)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DriftHeatmapCell:
    """A single cell in the calibration drift heatmap grid."""

    window_label: str
    window_start: str
    window_end: str
    confidence_bucket: str
    confidence_lower: float
    confidence_upper: float
    n_matches: int
    accuracy: float
    brier: float
    rps: float
    log_loss: float | None


@dataclass(frozen=True)
class DriftHeatmapReport:
    """Calibration drift heatmap report.

    Combines time-window segmentation with confidence-bucket segmentation
    to produce a 2D grid of per-cell metrics. Useful for spotting
    degradation that only affects high-confidence or low-confidence
    predictions over time.
    """

    cells: list[DriftHeatmapCell]
    n_windows: int
    n_confidence_buckets: int
    n_total_matches: int
    window_labels: list[str]
    confidence_bucket_labels: list[str]
    drift_detected: bool
    disclaimer: str


def compute_calibration_drift_heatmap(
    predictions: pd.DataFrame,
    *,
    window_col: str = "match_date",
    window_size: str = "90D",
    n_confidence_bins: int = 4,
    min_samples_per_cell: int = 5,
) -> DriftHeatmapReport:
    """Compute a 2D heatmap of calibration metrics over time × confidence.

    Segments predictions into time windows (via ``window_size``) and
    confidence buckets (via ``n_confidence_bins`` quantiles on the max
    predicted probability), then computes accuracy/Brier/RPS/LogLoss
    per cell.

    Args:
        predictions: DataFrame with prediction columns, ``actual_outcome``,
            and ``window_col``.
        window_col: Column to use for time windowing (default match_date).
        window_size: Pandas frequency string for window size.
        n_confidence_bins: Number of confidence buckets (2-15).
        min_samples_per_cell: Minimum samples per cell; cells below this
            threshold are excluded.

    Returns:
        DriftHeatmapReport with the 2D grid and drift detection flag.

    Raises:
        ValueError: If required columns are missing or ``n_confidence_bins``
            is outside [2, 15].
    """
    required = {
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome", window_col,
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    if n_confidence_bins < 2 or n_confidence_bins > 15:
        raise ValueError(
            f"n_confidence_bins must be in [2, 15], got {n_confidence_bins}"
        )

    disclaimer = (
        "The drift heatmap reveals temporal calibration patterns across "
        "confidence levels. Cells with high Brier indicate regions where "
        "the model is over-confident or mis-calibrated. Empty cells "
        "indicate insufficient samples."
    )

    df = predictions.copy()
    df[window_col] = pd.to_datetime(df[window_col], errors="coerce")
    df = df.dropna(subset=[window_col]).sort_values(window_col).reset_index(drop=True)

    has_exact = "exact_score_probability" in df.columns

    probs_cols = [
        "home_win_probability", "draw_probability", "away_win_probability",
    ]
    df["_confidence"] = df[probs_cols].max(axis=1)

    if df.empty:
        return DriftHeatmapReport(
            cells=[],
            n_windows=0,
            n_confidence_buckets=0,
            n_total_matches=0,
            window_labels=[],
            confidence_bucket_labels=[],
            drift_detected=False,
            disclaimer=disclaimer,
        )

    # Build confidence buckets on the full DataFrame BEFORE windowing so
    # that bucket boundaries are consistent across windows.
    try:
        df = df.assign(_conf_bin=pd.qcut(
            df["_confidence"],
            q=n_confidence_bins,
            duplicates="drop",
            labels=False,
        ))
    except ValueError:
        df = df.assign(_conf_bin=pd.cut(
            df["_confidence"],
            bins=min(n_confidence_bins, df["_confidence"].nunique()),
            labels=False,
            include_lowest=True,
        ))

    # Determine global confidence bucket boundaries for labeling.
    bucket_bounds: dict[int, tuple[float, float]] = {}
    for bid in sorted(df["_conf_bin"].dropna().unique()):
        chunk = df.loc[df["_conf_bin"] == bid]
        bucket_bounds[int(bid)] = (
            float(chunk["_confidence"].min()),
            float(chunk["_confidence"].max()),
        )

    confidence_labels = [
        f"conf_{bid}_[{lo:.3f},{hi:.3f}]"
        for bid, (lo, hi) in sorted(bucket_bounds.items())
    ]

    # Build time windows (after _conf_bin is assigned so windows inherit it).
    min_date = df[window_col].min()
    max_date = df[window_col].max()
    windows: list[tuple[str, str, pd.DataFrame]] = []
    current_start = min_date
    while current_start <= max_date:
        current_end = current_start + pd.Timedelta(window_size)
        window_df = df[
            (df[window_col] >= current_start) & (df[window_col] < current_end)
        ].copy()
        if not window_df.empty:
            windows.append((
                current_start.strftime("%Y-%m-%d"),
                current_end.strftime("%Y-%m-%d"),
                window_df,
            ))
        current_start = current_end

    if not windows:
        return DriftHeatmapReport(
            cells=[],
            n_windows=0,
            n_confidence_buckets=0,
            n_total_matches=0,
            window_labels=[],
            confidence_bucket_labels=[],
            drift_detected=False,
            disclaimer=disclaimer,
        )

    cells: list[DriftHeatmapCell] = []
    # Track per-window overall Brier for drift detection.
    window_briers: list[float] = []
    for start_str, end_str, window_df in windows:
        window_label = f"{start_str}_{end_str}"
        window_brier = float(
            window_df.apply(
                lambda r: _brier_per_match(
                    r["home_win_probability"],
                    r["draw_probability"],
                    r["away_win_probability"],
                    str(r["actual_outcome"]),
                ),
                axis=1,
            ).mean()
        ) if not window_df.empty else 0.0
        window_briers.append(window_brier)

        for bid in sorted(bucket_bounds.keys()):
            chunk = window_df.loc[window_df["_conf_bin"] == bid]
            if len(chunk) < min_samples_per_cell:
                continue
            conf_lo, conf_hi = bucket_bounds[bid]
            ll = None
            if has_exact:
                ll = _safe_log_loss_avg(
                    chunk["exact_score_probability"].apply(
                        lambda p: _log_loss_per_match(
                            float(p) if pd.notna(p) else None, 0, 0,
                        )
                    ),
                    has_exact,
                )
            cells.append(DriftHeatmapCell(
                window_label=window_label,
                window_start=start_str,
                window_end=end_str,
                confidence_bucket=f"conf_{bid}",
                confidence_lower=round(conf_lo, 4),
                confidence_upper=round(conf_hi, 4),
                n_matches=len(chunk),
                accuracy=round(_accuracy_for_df(chunk), 4),
                brier=round(_brier_1x2(chunk), 4),
                rps=round(_ranked_probability_score(chunk), 4),
                log_loss=ll,
            ))

    # Drift detection: compare latest window Brier to historical mean.
    drift_detected = False
    if len(window_briers) >= 2:
        historical_avg = float(np.mean(window_briers[:-1]))
        latest = window_briers[-1]
        if historical_avg > 0:
            relative_change = (latest - historical_avg) / historical_avg
            drift_detected = relative_change > 0.05

    window_labels_list = [
        f"{s}_{e}" for s, e, _ in windows
    ]
    n_total = sum(c.n_matches for c in cells)

    return DriftHeatmapReport(
        cells=cells,
        n_windows=len(windows),
        n_confidence_buckets=len(bucket_bounds),
        n_total_matches=n_total,
        window_labels=window_labels_list,
        confidence_bucket_labels=confidence_labels,
        drift_detected=drift_detected,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Prediction error clustering (k-means on worst-decile feature signatures)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ErrorClusterCentroid:
    """Per-feature centroid value for an error cluster."""

    feature: str
    centroid_value: float
    abs_centroid: float


@dataclass(frozen=True)
class ErrorCluster:
    """Statistics for a single cluster of prediction errors."""

    cluster_id: int
    n_matches: int
    avg_brier: float
    avg_confidence: float
    accuracy: float
    dominant_actual_outcome: str
    dominant_predicted_outcome: str
    top_centroid_features: list[ErrorClusterCentroid]


@dataclass(frozen=True)
class ErrorClusteringReport:
    """Report grouping worst predictions into clusters by feature signature."""

    clusters: list[ErrorCluster]
    n_clusters: int
    n_total_matches: int
    n_features_used: int
    error_percentile: float
    n_worst_matches: int
    overall_avg_brier: float
    disclaimer: str


def compute_error_clustering(
    predictions: pd.DataFrame,
    *,
    n_clusters: int = 3,
    error_percentile: float = 0.1,
    features: tuple[str, ...] | None = None,
    min_samples_per_cluster: int = 5,
    random_state: int = 42,
) -> ErrorClusteringReport:
    """Cluster the worst predictions by feature signature using k-means.

    Selects the bottom ``error_percentile`` (worst) predictions by Brier
    score, standardizes the feature columns, and runs k-means clustering
    to surface common error patterns.

    Args:
        predictions: DataFrame with prediction columns, ``actual_outcome``,
            and numeric feature columns.
        n_clusters: Number of k-means clusters (2-8).
        error_percentile: Fraction of worst predictions to select (0.01-0.5).
        features: Optional explicit list of feature column names.
        min_samples_per_cluster: Minimum samples per cluster; clusters below
            this threshold are excluded.
        random_state: Random seed for reproducibility.

    Returns:
        ErrorClusteringReport with per-cluster stats and centroids.

    Raises:
        ValueError: If required columns are missing, ``n_clusters`` is
            outside [2, 8], or ``error_percentile`` is outside (0, 0.5].
    """
    required = {
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    if n_clusters < 2 or n_clusters > 8:
        raise ValueError(f"n_clusters must be in [2, 8], got {n_clusters}")

    if error_percentile <= 0.0 or error_percentile > 0.5:
        raise ValueError(
            f"error_percentile must be in (0, 0.5], got {error_percentile}"
        )

    disclaimer = (
        "Error clustering groups worst predictions by feature signature "
        "via k-means. Clusters reveal common error patterns but do not "
        "imply causation. Small clusters may be unreliable."
    )

    df = predictions.copy()

    def _brier_row(row: pd.Series) -> float:
        return _brier_per_match(
            row["home_win_probability"],
            row["draw_probability"],
            row["away_win_probability"],
            str(row["actual_outcome"]),
        )

    df["_brier"] = df.apply(_brier_row, axis=1)
    overall_avg_brier = round(float(df["_brier"].mean()), 4)

    # Auto-detect feature columns when not provided.
    if features is None:
        feature_cols: list[str] = []
        for col in df.columns:
            if col in _FEATURE_EXCLUDE_COLUMNS or col.startswith("_"):
                continue
            if col in ("home_team", "away_team"):
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                if df[col].dropna().nunique() > 1:
                    feature_cols.append(col)
    else:
        feature_cols = list(features)
        for fc in feature_cols:
            if fc not in df.columns:
                raise ValueError(f"feature column not found: {fc}")

    if not feature_cols:
        return ErrorClusteringReport(
            clusters=[],
            n_clusters=0,
            n_total_matches=len(df),
            n_features_used=0,
            error_percentile=error_percentile,
            n_worst_matches=0,
            overall_avg_brier=overall_avg_brier,
            disclaimer=disclaimer,
        )

    # Select worst predictions by Brier.
    n_worst = max(n_clusters * min_samples_per_cluster, int(len(df) * error_percentile))
    worst_df = df.nlargest(n_worst, "_brier").copy()

    if len(worst_df) < n_clusters * min_samples_per_cluster:
        return ErrorClusteringReport(
            clusters=[],
            n_clusters=0,
            n_total_matches=len(df),
            n_features_used=len(feature_cols),
            error_percentile=error_percentile,
            n_worst_matches=len(worst_df),
            overall_avg_brier=overall_avg_brier,
            disclaimer=disclaimer,
        )

    # Prepare feature matrix (drop rows with NaN in feature columns).
    feature_data = worst_df[feature_cols].dropna()
    if len(feature_data) < n_clusters * min_samples_per_cluster:
        return ErrorClusteringReport(
            clusters=[],
            n_clusters=0,
            n_total_matches=len(df),
            n_features_used=len(feature_cols),
            error_percentile=error_percentile,
            n_worst_matches=len(feature_data),
            overall_avg_brier=overall_avg_brier,
            disclaimer=disclaimer,
        )

    # Standardize features.
    means = feature_data.mean(axis=0)
    stds = feature_data.std(axis=0).replace(0.0, 1.0)
    standardized = (feature_data - means) / stds

    # Run k-means clustering.
    from sklearn.cluster import KMeans

    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = km.fit_predict(standardized.values)

    worst_df = worst_df.loc[feature_data.index].copy()
    worst_df["_cluster"] = labels

    probs_cols = [
        "home_win_probability", "draw_probability", "away_win_probability",
    ]

    def _predicted_outcome(row: pd.Series) -> str:
        probs = {
            "home_win": row["home_win_probability"],
            "draw": row["draw_probability"],
            "away_win": row["away_win_probability"],
        }
        return max(probs, key=probs.get)

    clusters: list[ErrorCluster] = []
    for cid in sorted(worst_df["_cluster"].unique()):
        chunk = worst_df.loc[worst_df["_cluster"] == cid]
        if len(chunk) < min_samples_per_cluster:
            continue

        # Centroid: mean standardized value per feature in this cluster.
        chunk_std = standardized.loc[chunk.index]
        centroid_values = chunk_std.mean(axis=0)
        top_features = sorted(
            [
                ErrorClusterCentroid(
                    feature=feat,
                    centroid_value=round(float(centroid_values[feat]), 4),
                    abs_centroid=round(abs(float(centroid_values[feat])), 4),
                )
                for feat in feature_cols
            ],
            key=lambda x: x.abs_centroid,
            reverse=True,
        )[:10]

        actual_counts = chunk["actual_outcome"].value_counts()
        dominant_actual = str(actual_counts.index[0]) if not actual_counts.empty else "unknown"
        predicted_outcomes = chunk.apply(_predicted_outcome, axis=1)
        pred_counts = predicted_outcomes.value_counts()
        dominant_predicted = str(pred_counts.index[0]) if not pred_counts.empty else "unknown"

        chunk_with_probs = chunk[probs_cols + ["actual_outcome"]].copy()
        clusters.append(ErrorCluster(
            cluster_id=int(cid),
            n_matches=len(chunk),
            avg_brier=round(float(chunk["_brier"].mean()), 4),
            avg_confidence=round(_avg_confidence_for_df(chunk_with_probs), 4),
            accuracy=round(_accuracy_for_df(chunk_with_probs), 4),
            dominant_actual_outcome=dominant_actual,
            dominant_predicted_outcome=dominant_predicted,
            top_centroid_features=top_features,
        ))

    clusters.sort(key=lambda x: x.avg_brier, reverse=True)

    n_total = sum(c.n_matches for c in clusters)

    return ErrorClusteringReport(
        clusters=clusters,
        n_clusters=len(clusters),
        n_total_matches=len(df),
        n_features_used=len(feature_cols),
        error_percentile=error_percentile,
        n_worst_matches=n_total,
        overall_avg_brier=overall_avg_brier,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Backtest data drift detection (KS test between train/holdout windows)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureDriftEntry:
    """Per-feature drift statistics between train and holdout windows."""

    feature: str
    ks_statistic: float
    p_value: float
    drifted: bool
    train_mean: float
    holdout_mean: float
    mean_delta: float
    train_std: float
    holdout_std: float


@dataclass(frozen=True)
class DataDriftReport:
    """Report on feature distribution drift between train and holdout."""

    features: list[FeatureDriftEntry]
    n_features: int
    n_drifted: int
    drift_ratio: float
    n_train: int
    n_holdout: int
    split_date: str
    p_value_threshold: float
    disclaimer: str


def compute_data_drift(
    predictions: pd.DataFrame,
    *,
    window_col: str = "match_date",
    split_ratio: float = 0.7,
    split_date: str | None = None,
    p_value_threshold: float = 0.05,
    features: tuple[str, ...] | None = None,
    min_samples: int = 20,
) -> DataDriftReport:
    """Detect feature distribution drift between train and holdout windows.

    Splits predictions chronologically into training and holdout windows,
    then runs a two-sample Kolmogorov-Smirnov test per numeric feature
    to detect distribution shifts.

    Args:
        predictions: DataFrame with prediction columns, ``window_col``,
            and numeric feature columns.
        window_col: Column to use for chronological split (default match_date).
        split_ratio: Fraction of data to use as training window (0.1-0.9).
            Ignored when ``split_date`` is provided.
        split_date: Explicit split date (ISO format string). When provided,
            overrides ``split_ratio``.
        p_value_threshold: P-value below which a feature is flagged as drifted.
        features: Optional explicit list of feature column names.
        min_samples: Minimum samples in both train and holdout for the test
            to be meaningful.

    Returns:
        DataDriftReport with per-feature drift stats.

    Raises:
        ValueError: If required columns are missing, ``split_ratio`` is
            outside [0.1, 0.9], or ``window_col`` is absent.
    """
    if window_col not in predictions.columns:
        raise ValueError(f"predictions is missing required column: {window_col}")

    if split_ratio < 0.1 or split_ratio > 0.9:
        raise ValueError(f"split_ratio must be in [0.1, 0.9], got {split_ratio}")

    if p_value_threshold <= 0.0 or p_value_threshold >= 1.0:
        raise ValueError(
            f"p_value_threshold must be in (0, 1), got {p_value_threshold}"
        )

    disclaimer = (
        "Data drift detection uses the two-sample Kolmogorov-Smirnov test "
        "per feature. A drifted feature (p < threshold) indicates its "
        "distribution changed between train and holdout windows, which "
        "may degrade model performance. Multiple testing is not corrected; "
        "some features may be flagged by chance."
    )

    from scipy.stats import ks_2samp

    df = predictions.copy()
    df[window_col] = pd.to_datetime(df[window_col], errors="coerce")
    df = df.dropna(subset=[window_col]).sort_values(window_col).reset_index(drop=True)

    if len(df) < min_samples * 2:
        return DataDriftReport(
            features=[],
            n_features=0,
            n_drifted=0,
            drift_ratio=0.0,
            n_train=0,
            n_holdout=0,
            split_date="",
            p_value_threshold=p_value_threshold,
            disclaimer=disclaimer,
        )

    # Split into train and holdout.
    if split_date is not None:
        split_ts = pd.Timestamp(split_date)
        train_df = df.loc[df[window_col] < split_ts]
        holdout_df = df.loc[df[window_col] >= split_ts]
        split_date_str = split_ts.strftime("%Y-%m-%d")
    else:
        split_idx = int(len(df) * split_ratio)
        train_df = df.iloc[:split_idx]
        holdout_df = df.iloc[split_idx:]
        split_ts = train_df[window_col].max()
        split_date_str = split_ts.strftime("%Y-%m-%d") if pd.notna(split_ts) else ""

    if len(train_df) < min_samples or len(holdout_df) < min_samples:
        return DataDriftReport(
            features=[],
            n_features=0,
            n_drifted=0,
            drift_ratio=0.0,
            n_train=len(train_df),
            n_holdout=len(holdout_df),
            split_date=split_date_str,
            p_value_threshold=p_value_threshold,
            disclaimer=disclaimer,
        )

    # Auto-detect feature columns.
    if features is None:
        feature_cols: list[str] = []
        for col in df.columns:
            if col in _FEATURE_EXCLUDE_COLUMNS or col.startswith("_"):
                continue
            if col in ("home_team", "away_team"):
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                if df[col].dropna().nunique() > 1:
                    feature_cols.append(col)
    else:
        feature_cols = list(features)
        for fc in feature_cols:
            if fc not in df.columns:
                raise ValueError(f"feature column not found: {fc}")

    entries: list[FeatureDriftEntry] = []
    for col in feature_cols:
        train_values = train_df[col].dropna()
        holdout_values = holdout_df[col].dropna()
        if len(train_values) < min_samples or len(holdout_values) < min_samples:
            continue
        if train_values.nunique() < 2 and holdout_values.nunique() < 2:
            continue
        ks_result = ks_2samp(train_values.values, holdout_values.values)
        ks_stat = float(ks_result.statistic)
        p_val = float(ks_result.pvalue)
        drifted = p_val < p_value_threshold
        entries.append(FeatureDriftEntry(
            feature=col,
            ks_statistic=round(ks_stat, 6),
            p_value=round(p_val, 6),
            drifted=drifted,
            train_mean=round(float(train_values.mean()), 4),
            holdout_mean=round(float(holdout_values.mean()), 4),
            mean_delta=round(
                float(holdout_values.mean() - train_values.mean()), 4,
            ),
            train_std=round(float(train_values.std()), 4),
            holdout_std=round(float(holdout_values.std()), 4),
        ))

    entries.sort(key=lambda x: x.ks_statistic, reverse=True)

    n_drifted = sum(1 for e in entries if e.drifted)
    drift_ratio = round(n_drifted / len(entries), 4) if entries else 0.0

    return DataDriftReport(
        features=entries,
        n_features=len(entries),
        n_drifted=n_drifted,
        drift_ratio=drift_ratio,
        n_train=len(train_df),
        n_holdout=len(holdout_df),
        split_date=split_date_str,
        p_value_threshold=p_value_threshold,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# CI width analysis (per-confidence-bucket CI width tracking)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CIWidthBucket:
    """Per-confidence-bucket CI width statistics."""

    bucket_label: str
    confidence_lower: float
    confidence_upper: float
    n_matches: int
    avg_ci_width: float
    avg_ci_lower: float
    avg_ci_upper: float
    width_std: float
    relative_width: float


@dataclass(frozen=True)
class CIWidthReport:
    """Report on CI width distribution across confidence levels."""

    buckets: list[CIWidthBucket]
    n_matches: int
    overall_avg_ci_width: float
    overall_avg_confidence: float
    width_confidence_correlation: float | None
    widest_bucket: str
    narrowest_bucket: str
    assessment: str
    disclaimer: str


def compute_ci_width_analysis(
    predictions: pd.DataFrame,
    *,
    ci_lower_col: str = "home_win_ci_lower",
    ci_upper_col: str = "home_win_ci_upper",
    n_bins: int = 5,
    min_samples_per_bucket: int = 10,
) -> CIWidthReport:
    """Analyze CI width distribution across confidence levels.

    Buckets predictions by max predicted probability and per bucket
    computes average CI width, CI bounds, width std, and relative width
    (avg_ci_width / avg_confidence). Surfaces over/under-confident CI
    widths via the width-confidence correlation.

    Args:
        predictions: DataFrame with CI columns plus probability columns.
        ci_lower_col: Column name for CI lower bound.
        ci_upper_col: Column name for CI upper bound.
        n_bins: Number of confidence buckets (2-20).
        min_samples_per_bucket: Minimum samples per bucket.

    Returns:
        CIWidthReport with per-bucket CI width stats.

    Raises:
        ValueError: If CI or probability columns are missing, or
            ``n_bins`` is outside [2, 20].
    """
    required = {
        ci_lower_col, ci_upper_col,
        "home_win_probability", "draw_probability", "away_win_probability",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    if n_bins < 2 or n_bins > 20:
        raise ValueError(f"n_bins must be in [2, 20], got {n_bins}")

    disclaimer = (
        "CI width analysis tracks how confidence interval width varies "
        "with prediction confidence. A negative correlation is expected "
        "(higher confidence → narrower CI). Anomalous widening or "
        "consistently narrow CIs may indicate miscalibration."
    )

    df = predictions.copy()
    df["_ci_lower"] = pd.to_numeric(df[ci_lower_col], errors="coerce")
    df["_ci_upper"] = pd.to_numeric(df[ci_upper_col], errors="coerce")
    df = df.dropna(subset=["_ci_lower", "_ci_upper"])

    if df.empty:
        return CIWidthReport(
            buckets=[],
            n_matches=0,
            overall_avg_ci_width=0.0,
            overall_avg_confidence=0.0,
            width_confidence_correlation=None,
            widest_bucket="",
            narrowest_bucket="",
            assessment="insufficient_data",
            disclaimer=disclaimer,
        )

    probs_cols = [
        "home_win_probability", "draw_probability", "away_win_probability",
    ]
    df["_confidence"] = df[probs_cols].max(axis=1)
    df["_ci_width"] = (df["_ci_upper"] - df["_ci_lower"]).clip(lower=0.0)

    overall_avg_ci_width = round(float(df["_ci_width"].mean()), 4)
    overall_avg_confidence = round(float(df["_confidence"].mean()), 4)

    # Pearson correlation between confidence and CI width.
    if len(df) >= 2 and df["_confidence"].std() > 0 and df["_ci_width"].std() > 0:
        correlation = round(
            float(df["_confidence"].corr(df["_ci_width"])), 4,
        )
    else:
        correlation = None

    # Bucket by confidence.
    try:
        df["_bucket"] = pd.qcut(
            df["_confidence"],
            q=n_bins,
            duplicates="drop",
            labels=False,
        )
    except ValueError:
        df["_bucket"] = pd.cut(
            df["_confidence"],
            bins=min(n_bins, df["_confidence"].nunique()),
            labels=False,
            include_lowest=True,
        )

    buckets: list[CIWidthBucket] = []
    for bid in sorted(df["_bucket"].dropna().unique()):
        chunk = df.loc[df["_bucket"] == bid]
        if len(chunk) < min_samples_per_bucket:
            continue
        conf_lower = float(chunk["_confidence"].min())
        conf_upper = float(chunk["_confidence"].max())
        avg_width = float(chunk["_ci_width"].mean())
        avg_conf = float(chunk["_confidence"].mean())
        buckets.append(CIWidthBucket(
            bucket_label=f"conf_bin_{int(bid)}",
            confidence_lower=round(conf_lower, 4),
            confidence_upper=round(conf_upper, 4),
            n_matches=len(chunk),
            avg_ci_width=round(avg_width, 4),
            avg_ci_lower=round(float(chunk["_ci_lower"].mean()), 4),
            avg_ci_upper=round(float(chunk["_ci_upper"].mean()), 4),
            width_std=round(float(chunk["_ci_width"].std()), 4),
            relative_width=round(avg_width / avg_conf, 4) if avg_conf > 0 else 0.0,
        ))

    # Identify widest and narrowest buckets.
    if buckets:
        widest = max(buckets, key=lambda b: b.avg_ci_width)
        narrowest = min(buckets, key=lambda b: b.avg_ci_width)
        widest_label = widest.bucket_label
        narrowest_label = narrowest.bucket_label
    else:
        widest_label = ""
        narrowest_label = ""

    # Assessment based on correlation.
    if correlation is None:
        assessment = "insufficient_data"
    elif correlation > 0.3:
        assessment = "anomalous_widening"
    elif correlation < -0.3:
        assessment = "expected_narrowing"
    else:
        assessment = "weak_correlation"

    return CIWidthReport(
        buckets=buckets,
        n_matches=len(df),
        overall_avg_ci_width=overall_avg_ci_width,
        overall_avg_confidence=overall_avg_confidence,
        width_confidence_correlation=correlation,
        widest_bucket=widest_label,
        narrowest_bucket=narrowest_label,
        assessment=assessment,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Round 34: Scenario Stress Test, Per-Team Calibration Drift, Uncertainty
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StressTestMetricSet:
    """Metric snapshot for either baseline or stressed predictions."""

    n_matches: int
    accuracy: float
    brier: float
    rps: float
    log_loss: float | None
    avg_confidence: float


@dataclass(frozen=True)
class StressTestReport:
    """Report comparing baseline vs stressed distribution metrics."""

    shift_type: str
    shift_ratio: float
    baseline: StressTestMetricSet
    stressed: StressTestMetricSet
    accuracy_delta: float
    brier_delta: float
    rps_delta: float
    log_loss_delta: float | None
    confidence_delta: float
    degradation_score: float
    assessment: str
    n_shifted: int
    disclaimer: str


def _metrics_set(df: pd.DataFrame) -> StressTestMetricSet:
    """Build a StressTestMetricSet from a predictions DataFrame."""
    if df.empty:
        return StressTestMetricSet(
            n_matches=0,
            accuracy=0.0,
            brier=0.0,
            rps=0.0,
            log_loss=None,
            avg_confidence=0.0,
        )
    accuracy = _accuracy_for_df(df)
    brier = _brier_1x2(df)
    rps = _ranked_probability_score(df)
    if "exact_score_probability" in df.columns:
        sub = df.dropna(subset=["exact_score_probability"])
        log_loss = _exact_score_log_loss(sub) if not sub.empty else None
    else:
        log_loss = None
    avg_conf = _avg_confidence_for_df(df)
    return StressTestMetricSet(
        n_matches=int(len(df)),
        accuracy=round(accuracy, 4),
        brier=round(brier, 4),
        rps=round(rps, 4),
        log_loss=round(log_loss, 4) if log_loss is not None else None,
        avg_confidence=round(avg_conf, 4),
    )


_VALID_SHIFT_TYPES = {
    "outcome_swap", "probability_shift",
    "confidence_inflation", "confidence_deflation",
}


def compute_scenario_stress_test(
    predictions: pd.DataFrame,
    *,
    shift_type: str = "outcome_swap",
    shift_ratio: float = 0.2,
    random_state: int = 42,
) -> StressTestReport:
    """Simulate distribution shift and measure model degradation.

    Args:
        predictions: Backtest predictions DataFrame. Must include
            ``home_win_probability``, ``draw_probability``,
            ``away_win_probability`` and ``actual_outcome`` columns.
        shift_type: Type of distribution shift to simulate. One of:

            * ``outcome_swap`` — swap ``shift_ratio`` fraction of
              ``home_win`` actual outcomes to ``away_win``.
            * ``probability_shift`` — shift probability mass from
              home to away for ``shift_ratio`` fraction of rows.
            * ``confidence_inflation`` — inflate the max probability
              toward 1.0 for ``shift_ratio`` fraction of rows.
            * ``confidence_deflation`` — compress probabilities
              toward uniform for ``shift_ratio`` fraction of rows.
        shift_ratio: Fraction of rows to perturb (0.0–1.0).
        random_state: Seed for reproducible row selection.

    Returns:
        StressTestReport with baseline and stressed metric sets plus
        deltas and a composite degradation score.

    Raises:
        ValueError: If required columns are missing, ``shift_type`` is
            invalid, or ``shift_ratio`` is outside [0.0, 1.0].
    """
    required = {
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    if shift_type not in _VALID_SHIFT_TYPES:
        valid = ", ".join(sorted(_VALID_SHIFT_TYPES))
        raise ValueError(f"shift_type must be one of {valid}, got '{shift_type}'")

    if shift_ratio < 0.0 or shift_ratio > 1.0:
        raise ValueError(f"shift_ratio must be in [0.0, 1.0], got {shift_ratio}")

    disclaimer = (
        "Scenario stress testing simulates distribution shifts on the "
        "backtest predictions to quantify model robustness. The "
        "degradation score summarizes accuracy loss, Brier increase, "
        "and RPS increase. Positive scores indicate degradation."
    )

    df = predictions.copy()
    baseline = _metrics_set(df)

    if df.empty or shift_ratio == 0.0:
        return StressTestReport(
            shift_type=shift_type,
            shift_ratio=shift_ratio,
            baseline=baseline,
            stressed=baseline,
            accuracy_delta=0.0,
            brier_delta=0.0,
            rps_delta=0.0,
            log_loss_delta=None,
            confidence_delta=0.0,
            degradation_score=0.0,
            assessment="negligible",
            n_shifted=0,
            disclaimer=disclaimer,
        )

    rng = np.random.default_rng(random_state)
    n_rows = len(df)
    n_shift = int(round(n_rows * shift_ratio))
    if n_shift < 1:
        n_shift = 1 if n_rows >= 1 else 0
    if n_shift > n_rows:
        n_shift = n_rows

    shift_idx = rng.choice(n_rows, size=n_shift, replace=False)

    stressed = df.copy()
    probs_cols = ["home_win_probability", "draw_probability", "away_win_probability"]

    if shift_type == "outcome_swap":
        # Swap home_win -> away_win for the selected rows.
        mask = stressed.index.isin(stressed.iloc[shift_idx].index)
        swap_mask = mask & (stressed["actual_outcome"] == "home_win")
        stressed.loc[swap_mask, "actual_outcome"] = "away_win"
    elif shift_type == "probability_shift":
        # Shift probability mass from home to away.
        shift_amount = 0.2  # move 20% of home prob to away
        for i in shift_idx:
            row_label = stressed.index[i]
            home_p = float(stressed.at[row_label, "home_win_probability"])
            move = home_p * shift_amount
            stressed.at[row_label, "home_win_probability"] = max(0.0, home_p - move)
            stressed.at[row_label, "away_win_probability"] = (
                float(stressed.at[row_label, "away_win_probability"]) + move
            )
    elif shift_type == "confidence_inflation":
        # Inflate max probability toward 1.0.
        for i in shift_idx:
            row_label = stressed.index[i]
            probs = [
                float(stressed.at[row_label, "home_win_probability"]),
                float(stressed.at[row_label, "draw_probability"]),
                float(stressed.at[row_label, "away_win_probability"]),
            ]
            max_idx = int(np.argmax(probs))
            inflation = 0.2  # inflate by 20% of gap to 1.0
            new_max = probs[max_idx] + (1.0 - probs[max_idx]) * inflation
            residual = max(0.0, 1.0 - new_max)
            others = [j for j in range(3) if j != max_idx]
            other_sum = sum(probs[j] for j in others)
            if other_sum > 0:
                for j in others:
                    probs[j] = residual * (probs[j] / other_sum)
            else:
                for j in others:
                    probs[j] = residual / 2.0
            probs[max_idx] = new_max
            for j, col in enumerate(probs_cols):
                stressed.at[row_label, col] = probs[j]
    else:  # confidence_deflation
        # Compress probabilities toward uniform (1/3 each).
        compress = 0.2  # move 20% toward uniform
        uniform = 1.0 / 3.0
        for i in shift_idx:
            row_label = stressed.index[i]
            for col in probs_cols:
                cur = float(stressed.at[row_label, col])
                stressed.at[row_label, col] = cur + (uniform - cur) * compress

    stressed_metrics = _metrics_set(stressed)

    accuracy_delta = round(stressed_metrics.accuracy - baseline.accuracy, 4)
    brier_delta = round(stressed_metrics.brier - baseline.brier, 4)
    rps_delta = round(stressed_metrics.rps - baseline.rps, 4)
    confidence_delta = round(
        stressed_metrics.avg_confidence - baseline.avg_confidence, 4
    )
    if (
        baseline.log_loss is not None
        and stressed_metrics.log_loss is not None
    ):
        log_loss_delta = round(stressed_metrics.log_loss - baseline.log_loss, 4)
    else:
        log_loss_delta = None

    # Composite degradation score: weighted sum of normalized deltas.
    # Positive = degradation. Accuracy delta is negated (loss is bad).
    degradation_score = round(
        max(0.0, -accuracy_delta) * 2.0
        + max(0.0, brier_delta) * 5.0
        + max(0.0, rps_delta) * 3.0,
        4,
    )

    if degradation_score >= 0.5:
        assessment = "severe"
    elif degradation_score >= 0.2:
        assessment = "moderate"
    elif degradation_score >= 0.05:
        assessment = "mild"
    else:
        assessment = "negligible"

    return StressTestReport(
        shift_type=shift_type,
        shift_ratio=shift_ratio,
        baseline=baseline,
        stressed=stressed_metrics,
        accuracy_delta=accuracy_delta,
        brier_delta=brier_delta,
        rps_delta=rps_delta,
        log_loss_delta=log_loss_delta,
        confidence_delta=confidence_delta,
        degradation_score=degradation_score,
        assessment=assessment,
        n_shifted=n_shift,
        disclaimer=disclaimer,
    )


@dataclass(frozen=True)
class TeamDriftPoint:
    """Per-team metrics within a single time window."""

    window_label: str
    n_matches: int
    accuracy: float
    brier: float
    avg_confidence: float


@dataclass(frozen=True)
class TeamCalibrationDriftReport:
    """Calibration drift analysis restricted to a single team."""

    team_col: str
    team_name: str
    points: list[TeamDriftPoint]
    n_total_matches: int
    n_windows: int
    drift_detected: bool
    latest_brier: float
    historical_avg_brier: float
    relative_change: float
    trend: str
    disclaimer: str


def compute_team_calibration_drift(
    predictions: pd.DataFrame,
    *,
    team_col: str = "home_team",
    team_name: str,
    window_size: str = "180D",
    min_samples_per_window: int = 5,
    n_windows: int | None = None,
) -> TeamCalibrationDriftReport:
    """Compute calibration drift restricted to a single team.

    Filters predictions to rows where ``team_col == team_name``, then
    builds rolling time windows of ``window_size`` over ``match_date``
    and computes per-window accuracy, Brier, and avg confidence.

    Drift detection compares the latest window's mean Brier to the
    historical mean Brier (all earlier windows). ``drift_detected`` is
    flagged when the relative change exceeds 5%.

    Args:
        predictions: Backtest predictions DataFrame.
        team_col: Column to filter on (e.g. ``home_team`` or
            ``away_team``).
        team_name: Team name to filter for.
        window_size: Pandas offset alias for window size.
        min_samples_per_window: Minimum matches per window.
        n_windows: Optional cap on the number of windows returned.

    Returns:
        TeamCalibrationDriftReport with per-window points and drift
        summary.

    Raises:
        ValueError: If required columns are missing or ``team_name``
            is empty.
    """
    required = {
        team_col,
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome", "match_date",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    if not team_name:
        raise ValueError("team_name must be a non-empty string")

    disclaimer = (
        "Per-team calibration drift tracks how a single team's "
        "prediction quality evolves over time. A degrading trend may "
        "indicate roster turnover, tactical shifts, or model staleness "
        "specific to that team. Small samples per window can produce "
        "noisy trends."
    )

    df = predictions.copy()
    df = df.loc[df[team_col].astype(str) == str(team_name)].copy()
    if df.empty:
        return TeamCalibrationDriftReport(
            team_col=team_col,
            team_name=team_name,
            points=[],
            n_total_matches=0,
            n_windows=0,
            drift_detected=False,
            latest_brier=0.0,
            historical_avg_brier=0.0,
            relative_change=0.0,
            trend="insufficient_data",
            disclaimer=disclaimer,
        )

    df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce")
    df = df.dropna(subset=["match_date"]).sort_values("match_date").reset_index(drop=True)
    if df.empty:
        return TeamCalibrationDriftReport(
            team_col=team_col,
            team_name=team_name,
            points=[],
            n_total_matches=0,
            n_windows=0,
            drift_detected=False,
            latest_brier=0.0,
            historical_avg_brier=0.0,
            relative_change=0.0,
            trend="insufficient_data",
            disclaimer=disclaimer,
        )

    min_date = df["match_date"].min()
    max_date = df["match_date"].max()

    points: list[TeamDriftPoint] = []
    current_start = min_date
    while current_start <= max_date:
        current_end = current_start + pd.Timedelta(window_size)
        window_df = df[
            (df["match_date"] >= current_start)
            & (df["match_date"] < current_end)
        ]
        if len(window_df) >= min_samples_per_window:
            label = f"{current_start.strftime('%Y-%m-%d')}_{current_end.strftime('%Y-%m-%d')}"
            points.append(TeamDriftPoint(
                window_label=label,
                n_matches=int(len(window_df)),
                accuracy=round(_accuracy_for_df(window_df), 4),
                brier=round(_brier_1x2(window_df), 4),
                avg_confidence=round(_avg_confidence_for_df(window_df), 4),
            ))
        current_start = current_end

    if n_windows is not None and len(points) > n_windows:
        points = points[:n_windows]

    if not points:
        return TeamCalibrationDriftReport(
            team_col=team_col,
            team_name=team_name,
            points=[],
            n_total_matches=int(len(df)),
            n_windows=0,
            drift_detected=False,
            latest_brier=0.0,
            historical_avg_brier=0.0,
            relative_change=0.0,
            trend="insufficient_data",
            disclaimer=disclaimer,
        )

    latest_brier = points[-1].brier
    if len(points) >= 2:
        historical_briers = [p.brier for p in points[:-1]]
        historical_avg = float(np.mean(historical_briers))
    else:
        historical_avg = latest_brier

    if historical_avg > 0:
        relative_change = round((latest_brier - historical_avg) / historical_avg, 4)
    else:
        relative_change = 0.0

    drift_detected = abs(relative_change) > 0.05 and len(points) >= 2

    if len(points) < 2:
        trend = "insufficient_data"
    elif relative_change < -0.005:
        trend = "improving"
    elif relative_change > 0.005:
        trend = "degrading"
    else:
        trend = "stable"

    return TeamCalibrationDriftReport(
        team_col=team_col,
        team_name=team_name,
        points=points,
        n_total_matches=int(len(df)),
        n_windows=len(points),
        drift_detected=drift_detected,
        latest_brier=latest_brier,
        historical_avg_brier=round(historical_avg, 4),
        relative_change=relative_change,
        trend=trend,
        disclaimer=disclaimer,
    )


@dataclass(frozen=True)
class UncertaintyPoint:
    """Per-match uncertainty metrics."""

    match_id: str | None
    home_team: str | None
    away_team: str | None
    confidence: float
    entropy: float
    margin: float
    dispersion: float
    predicted_outcome: str
    actual_outcome: str | None
    correct: bool | None
    uncertainty_label: str


@dataclass(frozen=True)
class UncertaintyReport:
    """Aggregated prediction uncertainty analysis."""

    points: list[UncertaintyPoint]
    n_matches: int
    avg_entropy: float
    avg_margin: float
    avg_dispersion: float
    high_uncertainty_count: int
    high_uncertainty_accuracy: float
    low_uncertainty_accuracy: float
    entropy_accuracy_correlation: float | None
    disclaimer: str


def _shannon_entropy(probs: list[float]) -> float:
    """Normalized Shannon entropy in [0, 1] for a 3-outcome distribution."""
    raw = 0.0
    for p in probs:
        if p > 0:
            raw -= p * float(np.log(p))
    # Normalize by log(3) so the result is in [0, 1].
    return float(raw / float(np.log(3)))


def _uncertainty_label(entropy: float) -> str:
    """Categorize entropy into high/medium/low."""
    if entropy >= 0.85:
        return "high"
    if entropy >= 0.5:
        return "medium"
    return "low"


def compute_prediction_uncertainty(
    predictions: pd.DataFrame,
    *,
    max_points: int = 500,
) -> UncertaintyReport:
    """Quantify per-match prediction uncertainty.

    For each match computes:
        * Shannon entropy of the 1x2 probability vector (normalized
          to [0, 1] via division by ``log(3)``).
        * Confidence margin (max probability − second-highest).
        * Probability dispersion (standard deviation of the 1x2
          probabilities).
        * Uncertainty label (``high`` / ``medium`` / ``low``).

    Also reports the average metrics, accuracy for high vs low
    uncertainty buckets, and the Pearson correlation between entropy
    and binary correctness (1 = correct, 0 = incorrect).

    Args:
        predictions: Backtest predictions DataFrame.
        max_points: Maximum number of points to return (keeps first N).

    Returns:
        UncertaintyReport with per-match points and aggregates.

    Raises:
        ValueError: If required probability columns are missing.
    """
    required = {"home_win_probability", "draw_probability", "away_win_probability"}
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    disclaimer = (
        "Prediction uncertainty quantification supplements confidence "
        "with Shannon entropy, margin, and dispersion. High-uncertainty "
        "matches should be treated cautiously. Entropy near 1.0 "
        "indicates near-uniform probabilities; entropy near 0.0 "
        "indicates a dominant outcome."
    )

    df = predictions.copy()
    if df.empty:
        return UncertaintyReport(
            points=[],
            n_matches=0,
            avg_entropy=0.0,
            avg_margin=0.0,
            avg_dispersion=0.0,
            high_uncertainty_count=0,
            high_uncertainty_accuracy=0.0,
            low_uncertainty_accuracy=0.0,
            entropy_accuracy_correlation=None,
            disclaimer=disclaimer,
        )

    probs_cols = ["home_win_probability", "draw_probability", "away_win_probability"]
    probs = df[probs_cols].to_numpy(dtype=float)
    outcome_map = {"home_win": 0, "draw": 1, "away_win": 2}
    label_map = {0: "home_win", 1: "draw", 2: "away_win"}

    has_actual = "actual_outcome" in df.columns
    has_match_id = "match_id" in df.columns
    has_home = "home_team" in df.columns
    has_away = "away_team" in df.columns

    points: list[UncertaintyPoint] = []
    entropies: list[float] = []
    margins: list[float] = []
    dispersions: list[float] = []
    correct_flags: list[int] = []

    n_rows = len(df)
    cap = min(max_points, n_rows) if max_points > 0 else n_rows

    for i in range(n_rows):
        row_probs = [float(probs[i, 0]), float(probs[i, 1]), float(probs[i, 2])]
        confidence = max(row_probs)
        entropy = _shannon_entropy(row_probs)
        sorted_desc = sorted(row_probs, reverse=True)
        margin = sorted_desc[0] - sorted_desc[1] if len(sorted_desc) >= 2 else 0.0
        dispersion = float(np.std(row_probs))
        predicted_idx = int(np.argmax(row_probs))
        predicted_outcome = label_map[predicted_idx]

        actual = None
        correct = None
        if has_actual:
            actual_val = df.iloc[i]["actual_outcome"]
            if isinstance(actual_val, str) and actual_val in outcome_map:
                actual = actual_val
                correct = predicted_idx == outcome_map[actual_val]
                correct_flags.append(1 if correct else 0)

        entropies.append(entropy)
        margins.append(margin)
        dispersions.append(dispersion)

        if i < cap:
            match_id = None
            if has_match_id:
                mid_val = df.iloc[i]["match_id"]
                match_id = str(mid_val) if mid_val is not None and str(mid_val) != "nan" else None
            home_team = None
            if has_home:
                ht_val = df.iloc[i]["home_team"]
                home_team = str(ht_val) if ht_val is not None and str(ht_val) != "nan" else None
            away_team = None
            if has_away:
                at_val = df.iloc[i]["away_team"]
                away_team = str(at_val) if at_val is not None and str(at_val) != "nan" else None

            points.append(UncertaintyPoint(
                match_id=match_id,
                home_team=home_team,
                away_team=away_team,
                confidence=round(confidence, 4),
                entropy=round(entropy, 4),
                margin=round(margin, 4),
                dispersion=round(dispersion, 4),
                predicted_outcome=predicted_outcome,
                actual_outcome=actual,
                correct=correct,
                uncertainty_label=_uncertainty_label(entropy),
            ))

    avg_entropy = float(np.mean(entropies)) if entropies else 0.0
    avg_margin = float(np.mean(margins)) if margins else 0.0
    avg_dispersion = float(np.mean(dispersions)) if dispersions else 0.0

    high_uncertainty_count = sum(1 for e in entropies if e >= 0.85)
    low_entropy_mask = [e < 0.5 for e in entropies]
    high_entropy_mask = [e >= 0.85 for e in entropies]

    high_acc = 0.0
    low_acc = 0.0
    if correct_flags:
        high_correct = sum(
            c for c, h in zip(correct_flags, high_entropy_mask, strict=False) if h
        )
        high_total = sum(1 for h in high_entropy_mask if h)
        if high_total > 0:
            high_acc = high_correct / high_total
        low_correct = sum(
            c for c, lo in zip(correct_flags, low_entropy_mask, strict=False) if lo
        )
        low_total = sum(1 for lo in low_entropy_mask if lo)
        if low_total > 0:
            low_acc = low_correct / low_total

    correlation: float | None = None
    if len(correct_flags) >= 2 and len(set(entropies)) > 1:
        try:
            from scipy.stats import pearsonr

            r, _ = pearsonr(entropies, correct_flags)
            if not np.isnan(r):
                correlation = round(float(r), 4)
        except Exception:
            correlation = None

    return UncertaintyReport(
        points=points,
        n_matches=int(len(df)),
        avg_entropy=round(avg_entropy, 4),
        avg_margin=round(avg_margin, 4),
        avg_dispersion=round(avg_dispersion, 4),
        high_uncertainty_count=high_uncertainty_count,
        high_uncertainty_accuracy=round(high_acc, 4),
        low_uncertainty_accuracy=round(low_acc, 4),
        entropy_accuracy_correlation=correlation,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Profit/Loss Simulation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProfitLossPoint:
    """Per-match profit/loss record for betting simulation."""

    match_index: int
    predicted_outcome: str
    actual_outcome: str
    correct: bool
    model_probability: float
    implied_odds: float
    flat_stake: float
    flat_profit: float
    cumulative_flat_profit: float
    kelly_fraction: float
    kelly_stake: float
    kelly_profit: float
    cumulative_kelly_profit: float


@dataclass(frozen=True)
class ProfitLossSimulationReport:
    """Profit/loss simulation report for a flat-stake and Kelly betting strategy.

    Simulates betting 1 unit (flat) or Kelly-fraction stake on the model's
    predicted outcome (argmax of 1x2 probabilities) for each match, using
    implied odds from the model's own probabilities (1/prob). This is a
    self-referential simulation — it measures whether the model's confidence
    is well-calibrated, not whether it beats real bookmaker odds.
    """

    points: list[ProfitLossPoint]
    n_matches: int
    n_correct: int
    win_rate: float
    total_flat_stake: float
    total_flat_profit: float
    flat_roi: float
    max_flat_drawdown: float
    total_kelly_stake: float
    total_kelly_profit: float
    kelly_roi: float
    max_kelly_drawdown: float
    avg_confidence: float
    assessment: str
    disclaimer: str


def compute_profit_loss_simulation(
    predictions: pd.DataFrame,
    *,
    max_points: int = 500,
) -> ProfitLossSimulationReport:
    """Simulate flat-stake and Kelly betting on backtest predictions.

    For each match, bets on the argmax outcome using implied odds (1/prob).
    Flat-stake bets 1 unit per match; Kelly sizes stake by edge.

    Args:
        predictions: DataFrame with ``home_win_probability``,
            ``draw_probability``, ``away_win_probability``, and
            ``actual_outcome`` columns. Optional: ``match_date``.
        max_points: Maximum number of per-match points to return
            (keeps first N after sorting by match_date if available).

    Returns:
        :class:`ProfitLossSimulationReport` with per-match points and
        aggregate P/L metrics.

    Raises:
        ValueError: If required probability or outcome columns are missing.
    """
    required = {
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    disclaimer = (
        "Self-referential P/L simulation using implied odds from model "
        "probabilities. Positive ROI indicates well-calibrated confidence, "
        "not real-world betting profitability."
    )

    df = predictions.copy().reset_index(drop=True)
    if "match_date" in df.columns:
        df = df.sort_values("match_date").reset_index(drop=True)

    probs_cols = [
        "home_win_probability", "draw_probability", "away_win_probability",
    ]
    probs = df[probs_cols].to_numpy()
    predicted_idx = np.argmax(probs, axis=1)
    max_probs = probs[np.arange(len(df)), predicted_idx]
    outcome_labels = ["home_win", "draw", "away_win"]
    predicted_outcomes = [outcome_labels[i] for i in predicted_idx]
    actual_outcomes = df["actual_outcome"].astype(str).tolist()

    points: list[ProfitLossPoint] = []
    cum_flat = 0.0
    cum_kelly = 0.0
    peak_flat = 0.0
    peak_kelly = 0.0
    max_flat_dd = 0.0
    max_kelly_dd = 0.0
    n_correct = 0

    for i in range(len(df)):
        p = float(max_probs[i])
        p_safe = max(p, 1e-12)
        odds = 1.0 / p_safe
        correct = predicted_outcomes[i] == actual_outcomes[i]
        if correct:
            n_correct += 1

        flat_stake = 1.0
        flat_profit = (odds - 1.0) if correct else -1.0
        cum_flat += flat_profit
        peak_flat = max(peak_flat, cum_flat)
        flat_dd = peak_flat - cum_flat
        max_flat_dd = max(max_flat_dd, flat_dd)

        kelly_frac = (p * odds - 1.0) / (odds - 1.0) if odds > 1.0 else 0.0
        kelly_frac = max(0.0, min(1.0, kelly_frac))
        kelly_stake = kelly_frac
        kelly_profit = kelly_stake * (odds - 1.0) if correct else -kelly_stake
        cum_kelly += kelly_profit
        peak_kelly = max(peak_kelly, cum_kelly)
        kelly_dd = peak_kelly - cum_kelly
        max_kelly_dd = max(max_kelly_dd, kelly_dd)

        if i < max_points:
            points.append(ProfitLossPoint(
                match_index=int(i),
                predicted_outcome=predicted_outcomes[i],
                actual_outcome=actual_outcomes[i],
                correct=correct,
                model_probability=round(p, 4),
                implied_odds=round(odds, 4),
                flat_stake=round(flat_stake, 4),
                flat_profit=round(flat_profit, 4),
                cumulative_flat_profit=round(cum_flat, 4),
                kelly_fraction=round(kelly_frac, 4),
                kelly_stake=round(kelly_stake, 4),
                kelly_profit=round(kelly_profit, 4),
                cumulative_kelly_profit=round(cum_kelly, 4),
            ))

    n = len(df)
    win_rate = n_correct / n if n > 0 else 0.0
    total_flat_stake = float(n)
    total_flat_profit = cum_flat
    flat_roi = cum_flat / total_flat_stake if total_flat_stake > 0 else 0.0
    total_kelly_profit = cum_kelly
    # Compute total Kelly stake over ALL matches (not just max_points)
    total_kelly_stake_full = 0.0
    for i in range(n):
        p = float(max_probs[i])
        p_safe = max(p, 1e-12)
        odds = 1.0 / p_safe
        kf = (p * odds - 1.0) / (odds - 1.0) if odds > 1.0 else 0.0
        kf = max(0.0, min(1.0, kf))
        total_kelly_stake_full += kf
    kelly_roi = total_kelly_profit / total_kelly_stake_full if total_kelly_stake_full > 0 else 0.0

    if flat_roi > 0.05:
        assessment = "profitable"
    elif flat_roi < -0.02:
        assessment = "unprofitable"
    else:
        assessment = "breakeven"

    avg_conf = float(np.mean(max_probs)) if n > 0 else 0.0

    return ProfitLossSimulationReport(
        points=points,
        n_matches=int(n),
        n_correct=int(n_correct),
        win_rate=round(win_rate, 4),
        total_flat_stake=round(total_flat_stake, 4),
        total_flat_profit=round(total_flat_profit, 4),
        flat_roi=round(flat_roi, 4),
        max_flat_drawdown=round(max_flat_dd, 4),
        total_kelly_stake=round(total_kelly_stake_full, 4),
        total_kelly_profit=round(total_kelly_profit, 4),
        kelly_roi=round(kelly_roi, 4),
        max_kelly_drawdown=round(max_kelly_dd, 4),
        avg_confidence=round(avg_conf, 4),
        assessment=assessment,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Cumulative Performance Trajectory
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrajectoryPoint:
    """A single point in the cumulative performance trajectory."""

    match_index: int
    cumulative_accuracy: float
    cumulative_brier: float
    cumulative_profit: float
    rolling_accuracy: float | None
    rolling_brier: float | None
    match_date: str | None


@dataclass(frozen=True)
class CumulativeTrajectoryReport:
    """Cumulative performance trajectory over the backtest timeline.

    Tracks running accuracy, Brier, and flat-stake profit as each match
    is added. Optionally computes a rolling-window comparison to detect
    local trend changes.
    """

    points: list[TrajectoryPoint]
    n_matches: int
    final_accuracy: float
    final_brier: float
    final_profit: float
    trend: str
    best_window_accuracy: float
    worst_window_accuracy: float
    n_change_points: int
    disclaimer: str


def compute_cumulative_trajectory(
    predictions: pd.DataFrame,
    *,
    rolling_window: int = 50,
    max_points: int = 500,
    change_threshold: float = 0.05,
) -> CumulativeTrajectoryReport:
    """Compute cumulative performance trajectory over the backtest timeline.

    Sorts by ``match_date`` (if present) and computes running accuracy,
    Brier, and flat-stake profit. Optionally computes rolling-window
    metrics for trend change detection.

    Args:
        predictions: DataFrame with probability and outcome columns.
        rolling_window: Window size for rolling metrics (default 50).
        max_points: Maximum trajectory points to return (subsampled evenly).
        change_threshold: Accuracy change threshold for change-point detection.

    Returns:
        :class:`CumulativeTrajectoryReport` with trajectory points and summary.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    disclaimer = (
        "Cumulative trajectory tracks running metrics over the backtest "
        "timeline. Change points indicate significant accuracy shifts."
    )

    df = predictions.copy().reset_index(drop=True)
    if "match_date" in df.columns:
        df = df.sort_values("match_date").reset_index(drop=True)

    probs_cols = [
        "home_win_probability", "draw_probability", "away_win_probability",
    ]
    n = len(df)
    if n == 0:
        return CumulativeTrajectoryReport(
            points=[],
            n_matches=0,
            final_accuracy=0.0,
            final_brier=0.0,
            final_profit=0.0,
            trend="insufficient_data",
            best_window_accuracy=0.0,
            worst_window_accuracy=0.0,
            n_change_points=0,
            disclaimer=disclaimer,
        )

    probs = df[probs_cols].to_numpy()
    predicted_idx = np.argmax(probs, axis=1)
    max_probs = probs[np.arange(n), predicted_idx]
    outcome_map = {"home_win": 0, "draw": 1, "away_win": 2}
    actual_idx = df["actual_outcome"].map(outcome_map).to_numpy()
    correct_arr = (predicted_idx == actual_idx).astype(float)

    # Brier per match
    actuals_1x2 = np.vstack(
        df["actual_outcome"].map({
            "home_win": [1.0, 0.0, 0.0],
            "draw": [0.0, 1.0, 0.0],
            "away_win": [0.0, 0.0, 1.0],
        }).tolist()
    )
    brier_arr = np.sum((probs - actuals_1x2) ** 2, axis=1)

    # Flat-stake profit per match
    odds_arr = 1.0 / np.maximum(max_probs, 1e-12)
    profit_arr = np.where(correct_arr > 0, odds_arr - 1.0, -1.0)

    n = len(df)
    cum_correct = np.cumsum(correct_arr)
    cum_brier = np.cumsum(brier_arr)
    cum_profit = np.cumsum(profit_arr)
    indices = np.arange(1, n + 1)
    cum_accuracy = cum_correct / indices
    cum_brier_mean = cum_brier / indices

    # Rolling metrics
    if n >= rolling_window:
        s_correct = pd.Series(correct_arr)
        s_brier = pd.Series(brier_arr)
        rolling_acc = s_correct.rolling(rolling_window, min_periods=1).mean().to_numpy()
        rolling_brier = s_brier.rolling(rolling_window, min_periods=1).mean().to_numpy()
    else:
        rolling_acc = cum_accuracy.copy()
        rolling_brier = cum_brier_mean.copy()

    # Change-point detection: where rolling accuracy changes by > threshold
    n_change = 0
    if n >= rolling_window * 2:
        rolling_changes = np.abs(np.diff(rolling_acc[rolling_window - 1:]))
        n_change = int(np.sum(rolling_changes > change_threshold))

    # Best/worst rolling window accuracy
    if n >= rolling_window:
        best_win = float(np.max(rolling_acc[rolling_window - 1:]))
        worst_win = float(np.min(rolling_acc[rolling_window - 1:]))
    else:
        best_win = float(np.max(rolling_acc)) if n > 0 else 0.0
        worst_win = float(np.min(rolling_acc)) if n > 0 else 0.0

    # Trend: compare first half vs second half rolling accuracy
    if n >= rolling_window * 2:
        mid = n // 2
        first_half = float(np.mean(rolling_acc[rolling_window - 1:mid]))
        second_half = float(np.mean(rolling_acc[mid:]))
        if second_half > first_half + change_threshold:
            trend = "improving"
        elif second_half < first_half - change_threshold:
            trend = "degrading"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"

    # Subsample points if needed
    if n <= max_points:
        sample_indices = list(range(n))
    else:
        sample_indices = np.linspace(0, n - 1, max_points, dtype=int).tolist()

    if "match_date" in df.columns:
        match_dates = df["match_date"].astype(str).tolist()
    else:
        match_dates = [None] * n

    points: list[TrajectoryPoint] = []
    for i in sample_indices:
        points.append(TrajectoryPoint(
            match_index=int(i),
            cumulative_accuracy=round(float(cum_accuracy[i]), 4),
            cumulative_brier=round(float(cum_brier_mean[i]), 4),
            cumulative_profit=round(float(cum_profit[i]), 4),
            rolling_accuracy=round(float(rolling_acc[i]), 4),
            rolling_brier=round(float(rolling_brier[i]), 4),
            match_date=match_dates[i],
        ))

    final_acc = float(cum_accuracy[-1]) if n > 0 else 0.0
    final_brier = float(cum_brier_mean[-1]) if n > 0 else 0.0
    final_profit = float(cum_profit[-1]) if n > 0 else 0.0

    return CumulativeTrajectoryReport(
        points=points,
        n_matches=int(n),
        final_accuracy=round(final_acc, 4),
        final_brier=round(final_brier, 4),
        final_profit=round(final_profit, 4),
        trend=trend,
        best_window_accuracy=round(best_win, 4),
        worst_window_accuracy=round(worst_win, 4),
        n_change_points=n_change,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Match Difficulty Stratification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DifficultyTier:
    """Per-tier metrics for a difficulty stratification bucket."""

    tier: str
    n_matches: int
    accuracy: float
    brier: float
    rps: float
    log_loss: float | None
    avg_confidence: float
    calibration_gap: float
    assessment: str


@dataclass(frozen=True)
class DifficultyStratificationReport:
    """Match difficulty stratification report.

    Buckets backtest predictions by difficulty (max predicted probability)
    and closeness (margin between top-1 and top-2 probabilities), then
    computes per-tier metrics to reveal where the model excels or struggles.
    """

    tiers: list[DifficultyTier]
    n_matches: int
    overall_accuracy: float
    overall_brier: float
    best_tier: str | None
    worst_tier: str | None
    disclaimer: str


def compute_difficulty_stratification(
    predictions: pd.DataFrame,
    *,
    easy_threshold: float = 0.6,
    hard_threshold: float = 0.4,
    n_bins: int = 5,
) -> DifficultyStratificationReport:
    """Compute per-difficulty-tier metrics for backtest predictions.

    Classifies each match into difficulty tiers by max predicted
    probability: ``easy`` (≥ easy_threshold), ``medium`` (between
    thresholds), ``hard`` (< hard_threshold). Also computes a fine-grained
    ``n_bins`` quantile bucketing for the difficulty dimension.

    Args:
        predictions: DataFrame with probability and outcome columns.
        easy_threshold: Max prob ≥ this → ``easy`` tier (default 0.6).
        hard_threshold: Max prob < this → ``hard`` tier (default 0.4).
        n_bins: Number of quantile bins for fine-grained difficulty analysis.

    Returns:
        :class:`DifficultyStratificationReport` with per-tier metrics.

    Raises:
        ValueError: If required columns are missing or thresholds are invalid.
    """
    if not (0.0 < hard_threshold < easy_threshold < 1.0):
        raise ValueError(
            "Require 0.0 < hard_threshold < easy_threshold < 1.0"
        )
    if n_bins < 2 or n_bins > 20:
        raise ValueError("n_bins must be in [2, 20]")

    required = {
        "home_win_probability", "draw_probability", "away_win_probability",
        "actual_outcome",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    disclaimer = (
        "Difficulty stratification reveals model performance across "
        "prediction difficulty tiers; small tiers may have high variance."
    )

    df = predictions.copy().reset_index(drop=True)
    probs_cols = [
        "home_win_probability", "draw_probability", "away_win_probability",
    ]
    df["_max_prob"] = df[probs_cols].max(axis=1)
    sorted_probs = df[probs_cols].to_numpy()
    sorted_desc = np.sort(sorted_probs, axis=1)[:, ::-1]
    df["_margin"] = sorted_desc[:, 0] - sorted_desc[:, 1]

    # Ensure actual_outcome
    if "actual_outcome" not in df.columns:
        if "home_goals" in df.columns and "away_goals" in df.columns:
            df["actual_outcome"] = np.where(
                df["home_goals"] > df["away_goals"], "home_win",
                np.where(
                    df["home_goals"] == df["away_goals"], "draw", "away_win",
                ),
            )

    has_exact = "exact_score_probability" in df.columns

    # Assign coarse tiers
    def _coarse_tier(mp: float) -> str:
        if mp >= easy_threshold:
            return "easy"
        if mp < hard_threshold:
            return "hard"
        return "medium"

    df["_tier"] = df["_max_prob"].apply(_coarse_tier)

    # Fine-grained quantile bins
    try:
        df["_bin"] = pd.qcut(df["_max_prob"], n_bins, labels=False, duplicates="drop")
    except Exception:
        df["_bin"] = pd.cut(df["_max_prob"], n_bins, labels=False)

    actual_n_bins = int(df["_bin"].nunique()) if "_bin" in df.columns else 0

    tiers: list[DifficultyTier] = []

    def _compute_tier_metrics(tier_df: pd.DataFrame, tier_label: str) -> DifficultyTier:
        if tier_df.empty:
            return DifficultyTier(
                tier=tier_label, n_matches=0, accuracy=0.0, brier=0.0,
                rps=0.0, log_loss=None, avg_confidence=0.0,
                calibration_gap=0.0, assessment="no_data",
            )
        acc = _accuracy_for_df(tier_df)
        brier = _brier_1x2(tier_df)
        rps = _ranked_probability_score(tier_df)
        log_loss = None
        if has_exact and "exact_score_probability" in tier_df.columns:
            log_loss = _exact_score_log_loss(tier_df)
        conf = _avg_confidence_for_df(tier_df)
        # Calibration gap: avg_confidence - accuracy (positive = overconfident)
        cal_gap = conf - acc
        if acc >= 0.60:
            assessment = "strong"
        elif acc >= 0.45:
            assessment = "average"
        else:
            assessment = "weak"
        return DifficultyTier(
            tier=tier_label,
            n_matches=int(len(tier_df)),
            accuracy=round(acc, 4),
            brier=round(brier, 4),
            rps=round(rps, 4),
            log_loss=round(log_loss, 4) if log_loss is not None else None,
            avg_confidence=round(conf, 4),
            calibration_gap=round(cal_gap, 4),
            assessment=assessment,
        )

    # Coarse tiers
    for tier_label in ["easy", "medium", "hard"]:
        tier_df = df[df["_tier"] == tier_label]
        tiers.append(_compute_tier_metrics(tier_df, tier_label))

    # Fine-grained bin tiers (only if different from coarse)
    if actual_n_bins > 0:
        for bin_idx in range(actual_n_bins):
            bin_df = df[df["_bin"] == bin_idx]
            if not bin_df.empty:
                lo = float(bin_df["_max_prob"].min())
                hi = float(bin_df["_max_prob"].max())
                tier_label = f"bin_{bin_idx}_[{lo:.2f},{hi:.2f}]"
                tiers.append(_compute_tier_metrics(bin_df, tier_label))

    overall_acc = _accuracy_for_df(df) if not df.empty else 0.0
    overall_brier = _brier_1x2(df) if not df.empty else 0.0

    # Best/worst tier by accuracy (among non-empty coarse tiers)
    coarse_tiers = [t for t in tiers if t.tier in ("easy", "medium", "hard") and t.n_matches > 0]
    best_tier = max(coarse_tiers, key=lambda t: t.accuracy).tier if coarse_tiers else None
    worst_tier = min(coarse_tiers, key=lambda t: t.accuracy).tier if coarse_tiers else None

    return DifficultyStratificationReport(
        tiers=tiers,
        n_matches=int(len(df)),
        overall_accuracy=round(overall_acc, 4),
        overall_brier=round(overall_brier, 4),
        best_tier=best_tier,
        worst_tier=worst_tier,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Prediction streak analysis (consecutive correct/wrong runs + break patterns)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StreakPoint:
    """Per-match streak snapshot, ordered by ``match_date`` when available."""

    match_index: int
    streak_sign: str  # "correct" | "wrong" | "none"
    streak_length: int
    confidence: float
    predicted_outcome: str | None
    actual_outcome: str | None
    correct: bool | None
    streak_break_type: str | None  # "upset" | "recovery" | "neutral" | None on first row
    match_id: str | None = None
    home_team: str | None = None
    away_team: str | None = None
    match_date: str | None = None


@dataclass(frozen=True)
class StreakAnalysisReport:
    """Aggregate summary of consecutive correct/wrong prediction runs.

    ``upset_breaks`` counts high-confidence wrong predictions that ended a
    correct streak; ``recovery_breaks`` counts low-confidence correct
    predictions that ended a wrong streak. ``neutral_breaks`` counts all
    other streak transitions.
    """

    n_matches: int
    current_streak: int
    current_streak_type: str  # "correct" | "wrong" | "none"
    longest_correct_streak: int
    longest_wrong_streak: int
    total_streak_breaks: int
    upset_breaks: int
    recovery_breaks: int
    neutral_breaks: int
    upset_rate: float
    recovery_rate: float
    avg_correct_streak_length: float
    avg_wrong_streak_length: float
    points: list[StreakPoint]
    disclaimer: str


def _streak_outcome_label(actual_outcome: str | None) -> str | None:
    """Normalize an actual outcome label for streak reporting."""
    if actual_outcome is None:
        return None
    text = str(actual_outcome).strip().lower()
    aliases = {
        "h": "home_win",
        "home": "home_win",
        "home_win": "home_win",
        "1": "home_win",
        "d": "draw",
        "draw": "draw",
        "0": "draw",
        "a": "away_win",
        "away": "away_win",
        "away_win": "away_win",
        "2": "away_win",
    }
    return aliases.get(text, text)


def compute_prediction_streaks(
    predictions: pd.DataFrame,
    *,
    high_confidence_threshold: float = 0.60,
    low_confidence_threshold: float = 0.40,
    max_points: int = 1000,
) -> StreakAnalysisReport:
    """Track consecutive correct/wrong prediction runs and streak breaks.

    Sorts predictions by ``match_date`` when available (falling back to
    original order) and walks the per-match correctness flag to identify
    streak transitions. A streak ends when the correctness sign flips.

    - ``upset_break``: a high-confidence (>= ``high_confidence_threshold``)
      wrong prediction that ends a correct streak.
    - ``recovery_break``: a low-confidence (< ``low_confidence_threshold``)
      correct prediction that ends a wrong streak.
    - ``neutral_break``: any other streak transition.

    Args:
        predictions: DataFrame with probability columns. When
            ``actual_outcome`` is present it is used directly; otherwise
            it is synthesized from ``home_goals``/``away_goals``.
        high_confidence_threshold: Confidence at or above which a wrong
            prediction is considered an "upset" break. Must be in (0, 1].
        low_confidence_threshold: Confidence below which a correct
            prediction is considered a "recovery" break. Must be in
            [0, 1) and strictly below ``high_confidence_threshold``.
        max_points: Maximum number of per-match points to return (keeps
            the first N after sorting; aggregates always use the full
            DataFrame).

    Returns:
        StreakAnalysisReport with aggregate streak stats and a per-match
        timeline.

    Raises:
        ValueError: If probability columns are missing, the thresholds
            are out of range, or ``max_points`` is below 1.
    """
    required = {"home_win_probability", "draw_probability", "away_win_probability"}
    missing = sorted(required.difference(predictions.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"predictions is missing required columns: {missing_text}")

    if not (0.0 < high_confidence_threshold <= 1.0):
        raise ValueError(
            "high_confidence_threshold must be in (0, 1], got "
            f"{high_confidence_threshold}",
        )
    if not (0.0 <= low_confidence_threshold < 1.0):
        raise ValueError(
            "low_confidence_threshold must be in [0, 1), got "
            f"{low_confidence_threshold}",
        )
    if low_confidence_threshold >= high_confidence_threshold:
        raise ValueError(
            "low_confidence_threshold ("
            f"{low_confidence_threshold}) must be strictly below "
            f"high_confidence_threshold ({high_confidence_threshold})"
        )
    if max_points < 1:
        raise ValueError(f"max_points must be >= 1, got {max_points}")

    disclaimer = (
        "Streak analysis tracks consecutive correct/wrong predictions on "
        "the backtest sample. Streak lengths are sensitive to ordering "
        "and sample size; they are descriptive only and do not imply a "
        "predictive pattern for future matches."
    )

    df = predictions.copy()
    probs_cols = [
        "home_win_probability",
        "draw_probability",
        "away_win_probability",
    ]
    for col in probs_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=probs_cols)
    if df.empty:
        return StreakAnalysisReport(
            n_matches=0,
            current_streak=0,
            current_streak_type="none",
            longest_correct_streak=0,
            longest_wrong_streak=0,
            total_streak_breaks=0,
            upset_breaks=0,
            recovery_breaks=0,
            neutral_breaks=0,
            upset_rate=0.0,
            recovery_rate=0.0,
            avg_correct_streak_length=0.0,
            avg_wrong_streak_length=0.0,
            points=[],
            disclaimer=disclaimer,
        )

    if "actual_outcome" not in df.columns:
        if {"home_goals", "away_goals"}.issubset(df.columns):
            df["actual_outcome"] = np.where(
                df["home_goals"] > df["away_goals"],
                "home_win",
                np.where(
                    df["home_goals"] < df["away_goals"], "away_win", "draw",
                ),
            )
        else:
            df["actual_outcome"] = None

    if "match_date" in df.columns:
        df["_sort_key"] = pd.to_datetime(df["match_date"], errors="coerce")
        df = df.sort_values(by="_sort_key", kind="stable", na_position="last")
    else:
        df["_sort_key"] = range(len(df))

    df = df.reset_index(drop=True)

    probs = df[probs_cols].to_numpy()
    pred_idx = probs.argmax(axis=1)
    outcome_labels = ["home_win", "draw", "away_win"]
    predicted_outcomes = [outcome_labels[i] for i in pred_idx]
    actual_outcomes_raw = df["actual_outcome"].tolist()
    actual_outcomes = [_streak_outcome_label(a) for a in actual_outcomes_raw]
    confidence = probs.max(axis=1)

    correct_flags: list[bool | None] = []
    for pred, act in zip(predicted_outcomes, actual_outcomes, strict=True):
        if act is None:
            correct_flags.append(None)
        else:
            correct_flags.append(pred == act)

    optional_cols = {
        "match_id": "match_id",
        "home_team": "home_team",
        "away_team": "away_team",
        "match_date": "match_date",
    }
    available_optional = {
        field: (col if col in df.columns else None)
        for field, col in optional_cols.items()
    }

    points: list[StreakPoint] = []
    current_sign = "none"
    current_len = 0
    longest_correct = 0
    longest_wrong = 0
    correct_streak_lengths: list[int] = []
    wrong_streak_lengths: list[int] = []
    total_breaks = 0
    upset_breaks = 0
    recovery_breaks = 0
    neutral_breaks = 0

    for i, correct in enumerate(correct_flags):
        if correct is None:
            # Unknown outcome — preserve current streak sign but do not
            # extend it; emit a "none" point without breaking the run.
            points.append(StreakPoint(
                match_index=i,
                streak_sign="none",
                streak_length=current_len,
                confidence=round(float(confidence[i]), 4),
                predicted_outcome=predicted_outcomes[i],
                actual_outcome=actual_outcomes[i],
                correct=None,
                streak_break_type=None,
                match_id=(
                    str(df.at[i, available_optional["match_id"]])
                    if available_optional["match_id"] else None
                ),
                home_team=(
                    str(df.at[i, available_optional["home_team"]])
                    if available_optional["home_team"] else None
                ),
                away_team=(
                    str(df.at[i, available_optional["away_team"]])
                    if available_optional["away_team"] else None
                ),
                match_date=(
                    str(df.at[i, available_optional["match_date"]])
                    if available_optional["match_date"] else None
                ),
            ))
            continue

        sign = "correct" if correct else "wrong"
        break_type: str | None = None
        if current_sign == "none":
            # First known outcome — start of first streak.
            current_sign = sign
            current_len = 1
            break_type = None
        elif sign == current_sign:
            current_len += 1
            break_type = None
        else:
            # Streak transition: classify the break using the new match.
            total_breaks += 1
            if (
                sign == "wrong"
                and confidence[i] >= high_confidence_threshold
            ):
                break_type = "upset"
                upset_breaks += 1
            elif (
                sign == "correct"
                and confidence[i] < low_confidence_threshold
            ):
                break_type = "recovery"
                recovery_breaks += 1
            else:
                break_type = "neutral"
                neutral_breaks += 1
            # Close out the previous streak.
            if current_sign == "correct":
                correct_streak_lengths.append(current_len)
                longest_correct = max(longest_correct, current_len)
            else:
                wrong_streak_lengths.append(current_len)
                longest_wrong = max(longest_wrong, current_len)
            current_sign = sign
            current_len = 1

        if sign == "correct":
            longest_correct = max(longest_correct, current_len)
        else:
            longest_wrong = max(longest_wrong, current_len)

        points.append(StreakPoint(
            match_index=i,
            streak_sign=sign,
            streak_length=current_len,
            confidence=round(float(confidence[i]), 4),
            predicted_outcome=predicted_outcomes[i],
            actual_outcome=actual_outcomes[i],
            correct=correct,
            streak_break_type=break_type,
            match_id=(
                str(df.at[i, available_optional["match_id"]])
                if available_optional["match_id"] else None
            ),
            home_team=(
                str(df.at[i, available_optional["home_team"]])
                if available_optional["home_team"] else None
            ),
            away_team=(
                str(df.at[i, available_optional["away_team"]])
                if available_optional["away_team"] else None
            ),
            match_date=(
                str(df.at[i, available_optional["match_date"]])
                if available_optional["match_date"] else None
            ),
        ))

    # Close the final streak.
    if current_sign == "correct":
        correct_streak_lengths.append(current_len)
        longest_correct = max(longest_correct, current_len)
    elif current_sign == "wrong":
        wrong_streak_lengths.append(current_len)
        longest_wrong = max(longest_wrong, current_len)

    avg_correct = (
        round(sum(correct_streak_lengths) / len(correct_streak_lengths), 4)
        if correct_streak_lengths else 0.0
    )
    avg_wrong = (
        round(sum(wrong_streak_lengths) / len(wrong_streak_lengths), 4)
        if wrong_streak_lengths else 0.0
    )

    upset_rate = round(upset_breaks / total_breaks, 4) if total_breaks else 0.0
    recovery_rate = round(recovery_breaks / total_breaks, 4) if total_breaks else 0.0

    return StreakAnalysisReport(
        n_matches=int(len(df)),
        current_streak=current_len if current_sign != "none" else 0,
        current_streak_type=current_sign,
        longest_correct_streak=longest_correct,
        longest_wrong_streak=longest_wrong,
        total_streak_breaks=total_breaks,
        upset_breaks=upset_breaks,
        recovery_breaks=recovery_breaks,
        neutral_breaks=neutral_breaks,
        upset_rate=upset_rate,
        recovery_rate=recovery_rate,
        avg_correct_streak_length=avg_correct,
        avg_wrong_streak_length=avg_wrong,
        points=points[:max_points],
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Backtest Report Card (letter-graded model quality summary)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportCardDimension:
    """Single dimension grade in the backtest report card."""

    name: str
    grade: str  # A / B / C / D / F
    score: float  # 0–100
    metric_value: float
    metric_name: str
    assessment: str  # excellent / good / average / poor / failing
    threshold: str  # human-readable threshold description


@dataclass(frozen=True)
class BacktestReportCard:
    """Aggregated letter-graded report card across model quality dimensions."""

    overall_grade: str
    overall_score: float
    dimensions: list[ReportCardDimension]
    n_matches: int
    model_type: str | None
    summary: str
    disclaimer: str


def _grade_from_score(score: float) -> str:
    """Convert a 0–100 score to a letter grade."""
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 65:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def _assessment_from_grade(grade: str) -> str:
    """Convert a letter grade to an assessment label."""
    return {
        "A": "excellent",
        "B": "good",
        "C": "average",
        "D": "poor",
        "F": "failing",
    }.get(grade, "unknown")


def compute_backtest_report_card(
    predictions: pd.DataFrame,
    *,
    model_type: str | None = None,
) -> BacktestReportCard:
    """Compute a letter-graded report card aggregating model quality dimensions.

    Grades six dimensions on a 0–100 scale, each mapped to A/B/C/D/F:

    - **Accuracy**: argmax hit rate.
    - **Calibration**: Expected Calibration Error (ECE) — lower is better.
    - **Discrimination**: Brier score — lower is better.
    - **Sharpness**: Ranked Probability Score (RPS) — lower is better.
    - **Confidence Alignment**: |avg_confidence − accuracy| — lower is better.
    - **Stability**: 1 − std(accuracy) across temporal halves — higher is better.

    The overall score is a weighted average (accuracy 25%, calibration 20%,
    discrimination 20%, sharpness 15%, confidence 10%, stability 10%).

    Args:
        predictions: DataFrame with backtest prediction columns.
        model_type: Optional model label (e.g. "dixon_coles_decay").

    Returns:
        BacktestReportCard with per-dimension grades and overall grade.

    Raises:
        ValueError: If required probability or outcome columns are missing.
    """
    prob_cols = ["home_win_probability", "draw_probability", "away_win_probability"]
    missing = [c for c in prob_cols if c not in predictions.columns]
    if missing:
        raise ValueError(f"Missing required probability columns: {missing}")
    if "actual_outcome" not in predictions.columns:
        raise ValueError("Missing required column: actual_outcome")

    df = predictions.copy()
    n = int(len(df))
    disclaimer = (
        "Backtest report card is a retrospective summary on historical data; "
        "it does not guarantee future performance."
    )

    if n == 0:
        return BacktestReportCard(
            overall_grade="F",
            overall_score=0.0,
            dimensions=[],
            n_matches=0,
            model_type=model_type,
            summary="No predictions available for grading.",
            disclaimer=disclaimer,
        )

    # --- Accuracy ---
    accuracy = _accuracy_for_df(df)
    acc_score = min(100.0, accuracy * 100.0 / 0.55)  # 55% → 100
    acc_score = max(0.0, acc_score)

    # --- Calibration (ECE) ---
    ece = 0.0
    n_bins = 10
    bin_edges = np.linspace(1.0 / 3.0, 1.0, n_bins + 1)
    probs = df[prob_cols].to_numpy()
    max_probs = np.max(probs, axis=1)
    predicted_idx = np.argmax(probs, axis=1)
    outcome_map = {"home_win": 0, "draw": 1, "away_win": 2}
    actual_idx = df["actual_outcome"].map(outcome_map).to_numpy()
    correct_flags = (predicted_idx == actual_idx).astype(float)
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        if i == n_bins - 1:
            mask = (max_probs >= lo) & (max_probs <= hi)
        else:
            mask = (max_probs >= lo) & (max_probs < hi)
        count = int(mask.sum())
        if count == 0:
            continue
        avg_conf = float(max_probs[mask].mean())
        avg_acc = float(correct_flags[mask].mean())
        ece += count * abs(avg_conf - avg_acc)
    ece /= n
    # ECE: 0 → 100, 0.20 → 0
    cal_score = max(0.0, min(100.0, (1.0 - ece / 0.20) * 100.0))

    # --- Discrimination (Brier) ---
    brier = _brier_1x2(df)
    # Brier: 0 → 100, 0.33 → 0
    disc_score = max(0.0, min(100.0, (1.0 - brier / 0.33) * 100.0))

    # --- Sharpness (RPS) ---
    rps = _ranked_probability_score(df)
    # RPS: 0 → 100, 0.25 → 0
    sharp_score = max(0.0, min(100.0, (1.0 - rps / 0.25) * 100.0))

    # --- Confidence Alignment ---
    avg_conf = _avg_confidence_for_df(df)
    alignment_gap = abs(avg_conf - accuracy)
    # gap: 0 → 100, 0.20 → 0
    conf_score = max(0.0, min(100.0, (1.0 - alignment_gap / 0.20) * 100.0))

    # --- Stability (temporal halves) ---
    stab_score = 50.0  # default when insufficient data
    if "match_date" in df.columns and n >= 20:
        try:
            df_sorted = df.sort_values("match_date").reset_index(drop=True)
            half = n // 2
            first_acc = _accuracy_for_df(df_sorted.iloc[:half])
            second_acc = _accuracy_for_df(df_sorted.iloc[half:])
            stab_diff = abs(second_acc - first_acc)
            # diff: 0 → 100, 0.15 → 0
            stab_score = max(0.0, min(100.0, (1.0 - stab_diff / 0.15) * 100.0))
        except Exception:
            stab_score = 50.0

    dimensions = [
        ReportCardDimension(
            name="accuracy",
            grade=_grade_from_score(acc_score),
            score=round(acc_score, 1),
            metric_value=round(accuracy, 4),
            metric_name="accuracy",
            assessment=_assessment_from_grade(_grade_from_score(acc_score)),
            threshold="55%+ → A, 44%+ → B, 33%+ → C, 25%+ → D",
        ),
        ReportCardDimension(
            name="calibration",
            grade=_grade_from_score(cal_score),
            score=round(cal_score, 1),
            metric_value=round(ece, 4),
            metric_name="ECE",
            assessment=_assessment_from_grade(_grade_from_score(cal_score)),
            threshold="ECE<0.04 → A, <0.08 → B, <0.12 → C, <0.16 → D",
        ),
        ReportCardDimension(
            name="discrimination",
            grade=_grade_from_score(disc_score),
            score=round(disc_score, 1),
            metric_value=round(brier, 4),
            metric_name="Brier",
            assessment=_assessment_from_grade(_grade_from_score(disc_score)),
            threshold="Brier<0.17 → A, <0.21 → B, <0.25 → C, <0.29 → D",
        ),
        ReportCardDimension(
            name="sharpness",
            grade=_grade_from_score(sharp_score),
            score=round(sharp_score, 1),
            metric_value=round(rps, 4),
            metric_name="RPS",
            assessment=_assessment_from_grade(_grade_from_score(sharp_score)),
            threshold="RPS<0.13 → A, <0.16 → B, <0.19 → C, <0.22 → D",
        ),
        ReportCardDimension(
            name="confidence_alignment",
            grade=_grade_from_score(conf_score),
            score=round(conf_score, 1),
            metric_value=round(alignment_gap, 4),
            metric_name="|conf−acc|",
            assessment=_assessment_from_grade(_grade_from_score(conf_score)),
            threshold="gap<0.03 → A, <0.06 → B, <0.10 → C, <0.14 → D",
        ),
        ReportCardDimension(
            name="stability",
            grade=_grade_from_score(stab_score),
            score=round(stab_score, 1),
            metric_value=round(stab_score / 100.0, 4),
            metric_name="stability_score",
            assessment=_assessment_from_grade(_grade_from_score(stab_score)),
            threshold="diff<0.03 → A, <0.06 → B, <0.09 → C, <0.12 → D",
        ),
    ]

    weights = {
        "accuracy": 0.25,
        "calibration": 0.20,
        "discrimination": 0.20,
        "sharpness": 0.15,
        "confidence_alignment": 0.10,
        "stability": 0.10,
    }
    overall_score = sum(
        dim.score * weights.get(dim.name, 0.0) for dim in dimensions
    )
    overall_grade = _grade_from_score(overall_score)

    grade_counts: dict[str, int] = {}
    for dim in dimensions:
        grade_counts[dim.grade] = grade_counts.get(dim.grade, 0) + 1

    summary = (
        f"Overall grade {overall_grade} ({overall_score:.1f}/100) "
        f"across {n} predictions. "
        f"Accuracy={accuracy:.1%}, Brier={brier:.4f}, RPS={rps:.4f}, "
        f"ECE={ece:.4f}. "
        f"Grade distribution: "
        + ", ".join(f"{g}×{c}" for g, c in sorted(grade_counts.items()))
        + "."
    )

    return BacktestReportCard(
        overall_grade=overall_grade,
        overall_score=round(overall_score, 1),
        dimensions=dimensions,
        n_matches=n,
        model_type=model_type,
        summary=summary,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Prediction Anomaly Detection (flag unreliable or noteworthy predictions)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnomalyEntry:
    """A single flagged prediction anomaly."""

    match_index: int
    anomaly_type: str
    severity: str  # low / medium / high / critical
    confidence: float
    predicted_outcome: str
    actual_outcome: str | None
    correct: bool | None
    explanation: str
    match_id: str | None
    home_team: str | None
    away_team: str | None


@dataclass(frozen=True)
class AnomalyReport:
    """Summary of detected prediction anomalies."""

    n_matches: int
    n_anomalies: int
    anomaly_counts: dict[str, int]
    severity_counts: dict[str, int]
    anomalies: list[AnomalyEntry]
    high_entropy_count: int
    overconfident_wrong_count: int
    underconfident_correct_count: int
    outlier_confidence_count: int
    disclaimer: str


def compute_prediction_anomalies(
    predictions: pd.DataFrame,
    *,
    high_entropy_threshold: float = 0.85,
    overconfident_threshold: float = 0.60,
    underconfident_threshold: float = 0.40,
    outlier_high_threshold: float = 0.90,
    outlier_low_threshold: float = 0.35,
    max_anomalies: int = 500,
) -> AnomalyReport:
    """Flag predictions that are potentially unreliable or noteworthy.

    Detects five anomaly types:

    - ``high_entropy``: Shannon entropy ≥ *high_entropy_threshold* — the model
      is very uncertain about the outcome.
    - ``overconfident_wrong``: confidence ≥ *overconfident_threshold* but the
      prediction was wrong — potential calibration issue.
    - ``underconfident_correct``: confidence < *underconfident_threshold* but
      the prediction was correct — the model undervalued the true outcome.
    - ``outlier_confidence_high``: confidence ≥ *outlier_high_threshold* —
      extreme confidence that may indicate overfitting.
    - ``outlier_confidence_low``: confidence < *outlier_low_threshold* —
      very low confidence that may indicate data sparsity.

    Each anomaly is assigned a severity: ``low``, ``medium``, ``high``, or
    ``critical``.

    Args:
        predictions: DataFrame with backtest prediction columns.
        high_entropy_threshold: Entropy threshold for ``high_entropy``.
        overconfident_threshold: Confidence threshold for ``overconfident_wrong``.
        underconfident_threshold: Confidence threshold for ``underconfident_correct``.
        outlier_high_threshold: Upper confidence bound for outlier detection.
        outlier_low_threshold: Lower confidence bound for outlier detection.
        max_anomalies: Maximum number of anomaly entries to return.

    Returns:
        AnomalyReport with flagged predictions and summary counts.

    Raises:
        ValueError: If required probability columns are missing or thresholds
            are invalid.
    """
    if not 0.0 < high_entropy_threshold <= 1.0:
        raise ValueError("high_entropy_threshold must be in (0, 1]")
    if not 0.0 < overconfident_threshold < 1.0:
        raise ValueError("overconfident_threshold must be in (0, 1)")
    if not 0.0 < underconfident_threshold < 1.0:
        raise ValueError("underconfident_threshold must be in (0, 1)")
    if not 0.0 < outlier_low_threshold < outlier_high_threshold < 1.0:
        raise ValueError(
            "outlier_low_threshold must be < outlier_high_threshold, both in (0, 1)"
        )
    if max_anomalies < 1:
        raise ValueError("max_anomalies must be >= 1")

    prob_cols = ["home_win_probability", "draw_probability", "away_win_probability"]
    missing = [c for c in prob_cols if c not in predictions.columns]
    if missing:
        raise ValueError(f"Missing required probability columns: {missing}")

    df = predictions.copy()
    n = int(len(df))
    disclaimer = (
        "Anomaly detection flags predictions for review; flagged matches "
        "are not guaranteed to be wrong, and unflagged matches are not "
        "guaranteed to be correct."
    )

    if n == 0:
        return AnomalyReport(
            n_matches=0,
            n_anomalies=0,
            anomaly_counts={},
            severity_counts={},
            anomalies=[],
            high_entropy_count=0,
            overconfident_wrong_count=0,
            underconfident_correct_count=0,
            outlier_confidence_count=0,
            disclaimer=disclaimer,
        )

    has_actual = "actual_outcome" in df.columns
    optional_cols = {
        "match_id": "match_id" in df.columns,
        "home_team": "home_team" in df.columns,
        "away_team": "away_team" in df.columns,
    }

    probs = df[prob_cols].to_numpy()
    max_probs = np.max(probs, axis=1)
    predicted_idx = np.argmax(probs, axis=1)
    outcome_labels = ["home_win", "draw", "away_win"]
    predicted_outcomes = [outcome_labels[i] for i in predicted_idx]

    actual_outcomes: list[str | None] = [None] * n
    correct_flags: list[bool | None] = [None] * n
    if has_actual:
        outcome_map = {"home_win": 0, "draw": 1, "away_win": 2}
        actual_idx = df["actual_outcome"].map(outcome_map).to_numpy()
        for i in range(n):
            ai = actual_idx[i]
            if pd.isna(ai):
                actual_outcomes[i] = None
                correct_flags[i] = None
            else:
                actual_outcomes[i] = outcome_labels[int(ai)]
                correct_flags[i] = bool(predicted_idx[i] == int(ai))

    anomalies: list[AnomalyEntry] = []
    counts: dict[str, int] = {
        "high_entropy": 0,
        "overconfident_wrong": 0,
        "underconfident_correct": 0,
        "outlier_confidence_high": 0,
        "outlier_confidence_low": 0,
    }
    sev_counts: dict[str, int] = {
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
    }

    for i in range(n):
        conf = float(max_probs[i])
        probs_vec = [float(probs[i, j]) for j in range(3)]
        entropy = _shannon_entropy(probs_vec)
        predicted = predicted_outcomes[i]
        actual = actual_outcomes[i]
        correct = correct_flags[i]

        match_id = (
            str(df.at[df.index[i], "match_id"])
            if optional_cols["match_id"] and pd.notna(df.at[df.index[i], "match_id"])
            else None
        )
        home_team = (
            str(df.at[df.index[i], "home_team"])
            if optional_cols["home_team"] and pd.notna(df.at[df.index[i], "home_team"])
            else None
        )
        away_team = (
            str(df.at[df.index[i], "away_team"])
            if optional_cols["away_team"] and pd.notna(df.at[df.index[i], "away_team"])
            else None
        )

        # high_entropy
        if entropy >= high_entropy_threshold:
            severity = "high" if entropy >= 0.95 else "medium"
            anomalies.append(AnomalyEntry(
                match_index=i,
                anomaly_type="high_entropy",
                severity=severity,
                confidence=round(conf, 4),
                predicted_outcome=predicted,
                actual_outcome=actual,
                correct=correct,
                explanation=(
                    f"Entropy {entropy:.3f} ≥ {high_entropy_threshold} — "
                    "model is very uncertain."
                ),
                match_id=match_id,
                home_team=home_team,
                away_team=away_team,
            ))
            counts["high_entropy"] += 1
            sev_counts[severity] += 1

        # overconfident_wrong
        if correct is False and conf >= overconfident_threshold:
            severity = "critical" if conf >= 0.80 else "high"
            anomalies.append(AnomalyEntry(
                match_index=i,
                anomaly_type="overconfident_wrong",
                severity=severity,
                confidence=round(conf, 4),
                predicted_outcome=predicted,
                actual_outcome=actual,
                correct=correct,
                explanation=(
                    f"Confidence {conf:.1%} ≥ {overconfident_threshold:.0%} but "
                    f"prediction was wrong (actual: {actual})."
                ),
                match_id=match_id,
                home_team=home_team,
                away_team=away_team,
            ))
            counts["overconfident_wrong"] += 1
            sev_counts[severity] += 1

        # underconfident_correct
        if correct is True and conf < underconfident_threshold:
            severity = "low"
            anomalies.append(AnomalyEntry(
                match_index=i,
                anomaly_type="underconfident_correct",
                severity=severity,
                confidence=round(conf, 4),
                predicted_outcome=predicted,
                actual_outcome=actual,
                correct=correct,
                explanation=(
                    f"Confidence {conf:.1%} < {underconfident_threshold:.0%} but "
                    f"prediction was correct — model undervalued the outcome."
                ),
                match_id=match_id,
                home_team=home_team,
                away_team=away_team,
            ))
            counts["underconfident_correct"] += 1
            sev_counts[severity] += 1

        # outlier_confidence_high
        if conf >= outlier_high_threshold:
            severity = "medium" if conf < 0.95 else "high"
            anomalies.append(AnomalyEntry(
                match_index=i,
                anomaly_type="outlier_confidence_high",
                severity=severity,
                confidence=round(conf, 4),
                predicted_outcome=predicted,
                actual_outcome=actual,
                correct=correct,
                explanation=(
                    f"Confidence {conf:.1%} ≥ {outlier_high_threshold:.0%} — "
                    f"extreme confidence, verify data coverage."
                ),
                match_id=match_id,
                home_team=home_team,
                away_team=away_team,
            ))
            counts["outlier_confidence_high"] += 1
            sev_counts[severity] += 1

        # outlier_confidence_low
        if conf < outlier_low_threshold:
            severity = "medium"
            anomalies.append(AnomalyEntry(
                match_index=i,
                anomaly_type="outlier_confidence_low",
                severity=severity,
                confidence=round(conf, 4),
                predicted_outcome=predicted,
                actual_outcome=actual,
                correct=correct,
                explanation=(
                    f"Confidence {conf:.1%} < {outlier_low_threshold:.0%} — "
                    f"very low confidence, potential data sparsity."
                ),
                match_id=match_id,
                home_team=home_team,
                away_team=away_team,
            ))
            counts["outlier_confidence_low"] += 1
            sev_counts[severity] += 1

    # Sort by severity (critical first), then by confidence descending
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    anomalies.sort(key=lambda a: (sev_order.get(a.severity, 4), -a.confidence))

    return AnomalyReport(
        n_matches=n,
        n_anomalies=len(anomalies),
        anomaly_counts=counts,
        severity_counts=sev_counts,
        anomalies=anomalies[:max_anomalies],
        high_entropy_count=counts["high_entropy"],
        overconfident_wrong_count=counts["overconfident_wrong"],
        underconfident_correct_count=counts["underconfident_correct"],
        outlier_confidence_count=(
            counts["outlier_confidence_high"] + counts["outlier_confidence_low"]
        ),
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Team Performance Profile (backtest-derived team-level analysis)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TeamPerformanceProfile:
    """Backtest-derived performance profile for a single team."""

    team: str
    n_matches: int
    n_home: int
    n_away: int
    overall_accuracy: float
    home_accuracy: float
    away_accuracy: float
    avg_confidence: float
    calibration_gap: float
    overperformance: float  # actual win rate − predicted win rate
    n_wins: int
    n_draws: int
    n_losses: int
    avg_goals_scored: float
    avg_goals_conceded: float
    clean_sheet_rate: float
    btts_rate: float  # both teams to score
    common_scorelines: list[tuple[str, int]]  # (scoreline, count)
    worst_predictions: list[dict[str, Any]]  # top-N highest-Brier matches
    best_predictions: list[dict[str, Any]]  # top-N lowest-Brier correct matches
    assessment: str  # overperformer / underperformer / aligned
    disclaimer: str


def compute_team_performance_profile(
    predictions: pd.DataFrame,
    team: str,
    *,
    top_n: int = 5,
    min_matches: int = 3,
) -> TeamPerformanceProfile | None:
    """Compute a backtest-derived performance profile for a single team.

    Filters backtest predictions to matches involving *team* (as either home
    or away) and computes:

    - Overall / home / away prediction accuracy.
    - Average confidence and calibration gap.
    - Over/underperformance (actual win rate vs predicted win rate).
    - Win/draw/loss record, average goals scored/conceded.
    - Clean sheet rate and BTTS (both teams to score) rate.
    - Most common score lines.
    - Worst predictions (highest Brier) and best predictions (lowest Brier
      among correct).

    Args:
        predictions: DataFrame with backtest prediction columns.
        team: Team name to profile.
        top_n: Number of worst/best predictions to return.
        min_matches: Minimum matches for a meaningful profile; returns ``None``
            if fewer matches involve the team.

    Returns:
        TeamPerformanceProfile or ``None`` if the team has fewer than
        *min_matches* matches.

    Raises:
        ValueError: If required probability columns are missing or *team*
            is empty.
    """
    if not team or not team.strip():
        raise ValueError("team must be a non-empty string")
    if top_n < 1:
        raise ValueError("top_n must be >= 1")

    prob_cols = ["home_win_probability", "draw_probability", "away_win_probability"]
    missing = [c for c in prob_cols if c not in predictions.columns]
    if missing:
        raise ValueError(f"Missing required probability columns: {missing}")

    if "home_team" not in predictions.columns or "away_team" not in predictions.columns:
        raise ValueError("home_team and away_team columns are required")

    disclaimer = (
        "Team performance profile is derived from backtest predictions on "
        "historical data; it reflects model behavior, not definitive team ability."
    )

    df = predictions.copy()
    home_mask = df["home_team"] == team
    away_mask = df["away_team"] == team
    team_mask = home_mask | away_mask
    team_df = df[team_mask].copy()

    n = int(len(team_df))
    if n < min_matches:
        return None

    n_home = int(home_mask.sum())
    n_away = int(away_mask.sum())

    # Accuracy
    overall_acc = _accuracy_for_df(team_df) if n > 0 else 0.0
    home_df = df[home_mask].copy()
    away_df = df[away_mask].copy()
    home_acc = _accuracy_for_df(home_df) if n_home > 0 else 0.0
    away_acc = _accuracy_for_df(away_df) if n_away > 0 else 0.0
    avg_conf = _avg_confidence_for_df(team_df) if n > 0 else 0.0
    cal_gap = round(avg_conf - overall_acc, 4)

    # Win/draw/loss and goals
    n_wins = 0
    n_draws = 0
    n_losses = 0
    goals_scored: list[float] = []
    goals_conceded: list[float] = []
    clean_sheets = 0
    btts = 0
    scoreline_counts: dict[str, int] = {}

    has_goals = "home_goals" in df.columns and "away_goals" in df.columns
    has_actual = "actual_outcome" in df.columns

    for idx in team_df.index:
        row = team_df.loc[idx]
        is_home = row["home_team"] == team

        if has_actual:
            actual = row.get("actual_outcome")
            if is_home:
                if actual == "home_win":
                    n_wins += 1
                elif actual == "draw":
                    n_draws += 1
                elif actual == "away_win":
                    n_losses += 1
            else:
                if actual == "away_win":
                    n_wins += 1
                elif actual == "draw":
                    n_draws += 1
                elif actual == "home_win":
                    n_losses += 1

        if has_goals:
            hg = float(row["home_goals"]) if pd.notna(row.get("home_goals")) else 0.0
            ag = float(row["away_goals"]) if pd.notna(row.get("away_goals")) else 0.0
            if is_home:
                goals_scored.append(hg)
                goals_conceded.append(ag)
                if ag == 0:
                    clean_sheets += 1
                if hg > 0 and ag > 0:
                    btts += 1
                sl = f"{int(hg)}-{int(ag)}"
            else:
                goals_scored.append(ag)
                goals_conceded.append(hg)
                if hg == 0:
                    clean_sheets += 1
                if hg > 0 and ag > 0:
                    btts += 1
                sl = f"{int(ag)}-{int(hg)}"
            scoreline_counts[sl] = scoreline_counts.get(sl, 0) + 1

    avg_gs = round(float(np.mean(goals_scored)), 2) if goals_scored else 0.0
    avg_gc = round(float(np.mean(goals_conceded)), 2) if goals_conceded else 0.0
    cs_rate = round(clean_sheets / n, 4) if n > 0 else 0.0
    btts_rate = round(btts / n, 4) if n > 0 else 0.0

    common_scorelines = sorted(
        scoreline_counts.items(), key=lambda x: x[1], reverse=True
    )[:5]

    # Over/underperformance
    overperformance = 0.0
    if has_actual and n > 0:
        actual_wins = n_wins
        predicted_wins = 0.0
        for idx in team_df.index:
            row = team_df.loc[idx]
            is_home = row["home_team"] == team
            if is_home:
                predicted_wins += float(row["home_win_probability"])
            else:
                predicted_wins += float(row["away_win_probability"])
        actual_win_rate = actual_wins / n
        predicted_win_rate = predicted_wins / n
        overperformance = round(actual_win_rate - predicted_win_rate, 4)

    if overperformance > 0.05:
        assessment = "overperformer"
    elif overperformance < -0.05:
        assessment = "underperformer"
    else:
        assessment = "aligned"

    # Worst/best predictions
    worst: list[dict[str, Any]] = []
    best: list[dict[str, Any]] = []
    if has_actual and n > 0:
        brier_values: list[tuple[int, float]] = []
        for idx in team_df.index:
            row = team_df.loc[idx]
            b = _brier_per_match(
                float(row["home_win_probability"]),
                float(row["draw_probability"]),
                float(row["away_win_probability"]),
                str(row["actual_outcome"]),
            )
            brier_values.append((idx, b))

        brier_values.sort(key=lambda x: x[1], reverse=True)
        for idx, b in brier_values[:top_n]:
            row = team_df.loc[idx]
            worst.append({
                "home_team": str(row.get("home_team", "")),
                "away_team": str(row.get("away_team", "")),
                "predicted_outcome": str(
                    ["home_win", "draw", "away_win"][int(np.argmax([
                        float(row["home_win_probability"]),
                        float(row["draw_probability"]),
                        float(row["away_win_probability"]),
                    ]))]
                ),
                "actual_outcome": str(row.get("actual_outcome", "")),
                "confidence": round(float(max(
                    row["home_win_probability"],
                    row["draw_probability"],
                    row["away_win_probability"],
                )), 4),
                "brier": round(b, 4),
            })

        correct_briers = [
            (idx, b) for idx, b in brier_values
            if str(team_df.loc[idx, "actual_outcome"])
            == ["home_win", "draw", "away_win"][int(np.argmax([
                float(team_df.loc[idx, "home_win_probability"]),
                float(team_df.loc[idx, "draw_probability"]),
                float(team_df.loc[idx, "away_win_probability"]),
            ]))]
        ]
        correct_briers.sort(key=lambda x: x[1])
        for idx, b in correct_briers[:top_n]:
            row = team_df.loc[idx]
            best.append({
                "home_team": str(row.get("home_team", "")),
                "away_team": str(row.get("away_team", "")),
                "predicted_outcome": str(
                    ["home_win", "draw", "away_win"][int(np.argmax([
                        float(row["home_win_probability"]),
                        float(row["draw_probability"]),
                        float(row["away_win_probability"]),
                    ]))]
                ),
                "actual_outcome": str(row.get("actual_outcome", "")),
                "confidence": round(float(max(
                    row["home_win_probability"],
                    row["draw_probability"],
                    row["away_win_probability"],
                )), 4),
                "brier": round(b, 4),
            })

    return TeamPerformanceProfile(
        team=team,
        n_matches=n,
        n_home=n_home,
        n_away=n_away,
        overall_accuracy=round(overall_acc, 4),
        home_accuracy=round(home_acc, 4),
        away_accuracy=round(away_acc, 4),
        avg_confidence=round(avg_conf, 4),
        calibration_gap=cal_gap,
        overperformance=overperformance,
        n_wins=n_wins,
        n_draws=n_draws,
        n_losses=n_losses,
        avg_goals_scored=avg_gs,
        avg_goals_conceded=avg_gc,
        clean_sheet_rate=cs_rate,
        btts_rate=btts_rate,
        common_scorelines=common_scorelines,
        worst_predictions=worst,
        best_predictions=best,
        assessment=assessment,
        disclaimer=disclaimer,
    )

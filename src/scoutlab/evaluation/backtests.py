"""Backtests for probability models."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from scoutlab.models import TimeSplitConfig
from scoutlab.models.match_prediction import (
    fit_independent_poisson,
    predict_match,
)


@dataclass(frozen=True)
class PoissonBacktestResult:
    """Fold-level metrics plus per-match predictions from the Poisson backtest."""

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
            exact_probability = float(
                prediction.score_matrix.loc[fixture["home_goals"], fixture["away_goals"]]
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
    return fixtures.loc[
        :,
        ["match_id", "match_date", "home_team_id", "away_team_id", "home_goals", "away_goals"],
    ].sort_values(["match_date", "match_id"]).reset_index(drop=True)


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

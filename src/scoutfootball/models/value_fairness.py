"""Baseline market-value fairness modeling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DEFAULT_RESIDUAL_THRESHOLD = 0.25
ID_COLUMNS = {
    "player_id",
    "player_name",
    "team_id",
    "team_name",
    "match_id",
    "source_name",
    "data_source",
}
NON_FEATURE_COLUMNS = {
    "market_value",
    "market_value_log",
    "snapshot_date",
    "residual_log",
    "fairness_label",
}
DEFAULT_CATEGORICAL_COLUMNS = ("position_group", "league", "team_id")


@dataclass(frozen=True)
class TimeSplitConfig:
    """Time-series split configuration for fairness training."""

    n_splits: int = 3
    gap: int = 0


@dataclass(frozen=True)
class ValueFairnessResult:
    """OOF predictions, metrics, and training metadata for the fairness model."""

    oof_predictions: pd.DataFrame
    fold_metrics: pd.DataFrame
    metrics: dict[str, float]
    feature_columns: tuple[str, ...]
    feature_version: str
    data_version: str
    estimator_name: str
    model: Any


def fit_regressor(
    feature_df: pd.DataFrame,
    split_cfg: TimeSplitConfig | None = None,
    *,
    target_col: str = "market_value",
    date_col: str = "snapshot_date",
    residual_threshold: float = DEFAULT_RESIDUAL_THRESHOLD,
    feature_version: str = "unknown",
    data_version: str = "unknown",
) -> ValueFairnessResult:
    """Fit the baseline market-value fairness regressor with OOF outputs."""

    config = split_cfg or TimeSplitConfig()
    required_columns = {target_col, date_col}
    missing = sorted(required_columns.difference(feature_df.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"feature_df is missing required columns: {missing_text}")

    prepared = feature_df.copy()
    prepared[date_col] = pd.to_datetime(prepared[date_col], errors="raise")
    prepared = prepared.sort_values([date_col]).reset_index(drop=True)
    if len(prepared) <= config.n_splits:
        raise ValueError("feature_df must contain more rows than the requested number of splits")

    prepared["age_band"] = _build_age_band(prepared)
    prepared["league"] = _resolve_league_column(prepared)
    prepared["market_value_log"] = np.log1p(pd.to_numeric(prepared[target_col], errors="raise"))

    feature_columns = _select_feature_columns(prepared)
    oof_rows: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    splitter = TimeSeriesSplit(n_splits=config.n_splits, gap=config.gap)

    for fold_index, (train_idx, test_idx) in enumerate(splitter.split(prepared), start=1):
        train_frame = prepared.iloc[train_idx].copy()
        test_frame = prepared.iloc[test_idx].copy()
        if train_frame[date_col].max() > test_frame[date_col].min():
            raise ValueError("time split leakage detected: train dates extend beyond test start")

        baseline_pred = _predict_baseline(train_frame, test_frame)
        train_matrix, test_matrix = _vectorize_features(train_frame, test_frame, feature_columns)

        model = _build_regressor()
        model.fit(train_matrix, train_frame["market_value_log"])
        test_pred_log = model.predict(test_matrix)

        fold_oof = test_frame.loc[:, _id_output_columns(test_frame.columns, date_col)].copy()
        fold_oof["actual_market_value"] = test_frame[target_col].astype(float)
        fold_oof["actual_market_value_log"] = test_frame["market_value_log"]
        fold_oof["predicted_market_value_log"] = test_pred_log
        fold_oof["predicted_market_value"] = np.expm1(test_pred_log)
        fold_oof["baseline_market_value_log"] = baseline_pred
        fold_oof["baseline_market_value"] = np.expm1(baseline_pred)
        fold_oof["residual_log"] = (
            fold_oof["actual_market_value_log"] - fold_oof["predicted_market_value_log"]
        )
        fold_oof["fairness_label"] = classify_fairness(
            fold_oof["predicted_market_value_log"],
            fold_oof["actual_market_value_log"],
            threshold=residual_threshold,
        )
        fold_oof["feature_version"] = feature_version
        fold_oof["data_version"] = data_version
        fold_oof["fold"] = fold_index
        oof_rows.append(fold_oof)

        fold_rows.append(
            {
                "fold": fold_index,
                "train_start": train_frame[date_col].min(),
                "train_end": train_frame[date_col].max(),
                "test_start": test_frame[date_col].min(),
                "test_end": test_frame[date_col].max(),
                "train_rows": len(train_frame),
                "test_rows": len(test_frame),
                "mae_model": mean_absolute_error(
                    fold_oof["actual_market_value"],
                    fold_oof["predicted_market_value"],
                ),
                "mae_baseline": mean_absolute_error(
                    fold_oof["actual_market_value"],
                    fold_oof["baseline_market_value"],
                ),
            },
        )

    oof_predictions = pd.concat(oof_rows, ignore_index=True, sort=False)
    fold_metrics = pd.DataFrame.from_records(fold_rows)
    metrics = {
        "mae_model": float(
            mean_absolute_error(
                oof_predictions["actual_market_value"],
                oof_predictions["predicted_market_value"],
            ),
        ),
        "mae_baseline": float(
            mean_absolute_error(
                oof_predictions["actual_market_value"],
                oof_predictions["baseline_market_value"],
            ),
        ),
        "log_mae_model": float(
            mean_absolute_error(
                oof_predictions["actual_market_value_log"],
                oof_predictions["predicted_market_value_log"],
            ),
        ),
        "log_mae_baseline": float(
            mean_absolute_error(
                oof_predictions["actual_market_value_log"],
                oof_predictions["baseline_market_value_log"],
            ),
        ),
    }
    metrics["mae_improvement_vs_baseline"] = metrics["mae_baseline"] - metrics["mae_model"]

    full_matrix, _ = _vectorize_features(prepared, prepared, feature_columns)
    final_model = _build_regressor()
    final_model.fit(full_matrix, prepared["market_value_log"])

    return ValueFairnessResult(
        oof_predictions=oof_predictions,
        fold_metrics=fold_metrics,
        metrics=metrics,
        feature_columns=tuple(feature_columns),
        feature_version=feature_version,
        data_version=data_version,
        estimator_name="ElasticNet",
        model=final_model,
    )


def classify_fairness(
    predicted_log: pd.Series | np.ndarray,
    actual_log: pd.Series | np.ndarray,
    *,
    threshold: float = DEFAULT_RESIDUAL_THRESHOLD,
) -> pd.Series:
    """Classify market value fairness from residual bands."""

    residual = pd.Series(actual_log) - pd.Series(predicted_log)
    labels = np.where(
        residual > threshold,
        "expensive",
        np.where(residual < -threshold, "cheap", "fair"),
    )
    return pd.Series(labels, index=residual.index, dtype="string")


def _build_age_band(frame: pd.DataFrame, *, band_size: int = 4) -> pd.Series:
    if "age" in frame.columns:
        age_series = pd.to_numeric(frame["age"], errors="coerce")
    elif "date_of_birth" in frame.columns:
        dob = pd.to_datetime(frame["date_of_birth"], errors="coerce")
        age_series = (frame["snapshot_date"] - dob).dt.days / 365.25
    else:
        age_series = pd.Series(np.nan, index=frame.index)
    bins = np.floor(age_series / band_size) * band_size
    lower = bins.fillna(-1).astype(int)
    upper = (bins + band_size - 1).fillna(-1).astype(int)
    return pd.Series(
        np.where(
            age_series.notna(),
            lower.astype(str) + "-" + upper.astype(str),
            "unknown",
        ),
        index=frame.index,
        dtype="string",
    )


def _resolve_league_column(frame: pd.DataFrame) -> pd.Series:
    for column in ["league", "competition_name", "competition_id", "domestic_league"]:
        if column in frame.columns:
            return frame[column].astype("string")
    return pd.Series("unknown", index=frame.index, dtype="string")


def _select_feature_columns(frame: pd.DataFrame) -> list[str]:
    selected: list[str] = []
    for column in frame.columns:
        if column in NON_FEATURE_COLUMNS or column in ID_COLUMNS:
            continue
        if column.endswith("_version"):
            continue
        if column == "age_band":
            selected.append(column)
            continue
        if pd.api.types.is_bool_dtype(frame[column]) or pd.api.types.is_numeric_dtype(
            frame[column]
        ):
            selected.append(column)
            continue
        if column in DEFAULT_CATEGORICAL_COLUMNS:
            selected.append(column)
    return selected


def _vectorize_features(
    train_frame: pd.DataFrame,
    test_frame: pd.DataFrame,
    feature_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_features = train_frame.loc[:, feature_columns].copy()
    test_features = test_frame.loc[:, feature_columns].copy()
    categorical_columns = [
        column
        for column in feature_columns
        if train_features[column].dtype == "string" or train_features[column].dtype == object
    ]
    train_matrix = pd.get_dummies(train_features, columns=categorical_columns, dummy_na=True)
    test_matrix = pd.get_dummies(test_features, columns=categorical_columns, dummy_na=True)
    train_matrix, test_matrix = train_matrix.align(test_matrix, join="left", axis=1, fill_value=0.0)
    train_matrix = train_matrix.fillna(0.0).astype(float)
    test_matrix = test_matrix.fillna(0.0).astype(float)
    return train_matrix, test_matrix


def _predict_baseline(train_frame: pd.DataFrame, test_frame: pd.DataFrame) -> pd.Series:
    global_median = train_frame["market_value_log"].median()
    exact_lookup = train_frame.groupby(
        ["position_group", "age_band", "league"],
        dropna=False,
    )["market_value_log"].median()
    position_age_lookup = train_frame.groupby(
        ["position_group", "age_band"],
        dropna=False,
    )["market_value_log"].median()
    position_lookup = train_frame.groupby(
        "position_group",
        dropna=False,
    )["market_value_log"].median()

    predictions = []
    for _, row in test_frame.iterrows():
        key_exact = (row.get("position_group"), row.get("age_band"), row.get("league"))
        key_position_age = (row.get("position_group"), row.get("age_band"))
        position = row.get("position_group")
        if key_exact in exact_lookup.index:
            predictions.append(exact_lookup.loc[key_exact])
        elif key_position_age in position_age_lookup.index:
            predictions.append(position_age_lookup.loc[key_position_age])
        elif position in position_lookup.index:
            predictions.append(position_lookup.loc[position])
        else:
            predictions.append(global_median)
    return pd.Series(predictions, index=test_frame.index, dtype="float64")


def _build_regressor() -> Pipeline:
    return Pipeline(
        steps=[
            ("scale", StandardScaler()),
            (
                "regressor",
                ElasticNet(
                    alpha=0.001,
                    l1_ratio=0.1,
                    max_iter=20_000,
                    random_state=0,
                ),
            ),
        ],
    )


def _id_output_columns(columns: pd.Index, date_col: str) -> list[str]:
    preferred = [
        column
        for column in ["player_id", "player_name", "team_id", "team_name", date_col]
        if column in columns
    ]
    return preferred

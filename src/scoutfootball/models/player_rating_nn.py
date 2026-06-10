"""Supervised neural-network candidate for player rating calibration."""

from __future__ import annotations

import json
import pickle
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from scoutfootball.config import PlatformSettings


@dataclass(frozen=True)
class PlayerRatingNNConfig:
    """Configuration for the supervised player-rating MLP candidate."""

    min_labels: int = 200
    test_seasons: int = 1
    hidden_layer_sizes: tuple[int, ...] = (64, 24)
    alpha: float = 0.001
    learning_rate_init: float = 0.001
    max_iter: int = 300
    random_state: int = 42
    early_stopping: bool = True


@dataclass
class PlayerRatingNNResult:
    """Training result and artifacts for the player-rating MLP candidate."""

    trained: bool
    status: str
    metrics: dict[str, Any]
    predictions: pd.DataFrame
    feature_columns: list[str]
    category_columns: list[str]
    model: Pipeline | None = None


ID_COLUMNS = {
    "player_id",
    "player_name",
    "team_id",
    "team_name",
    "season",
    "season_id",
    "label_source",
    "label_confidence",
    "label_value",
    "as_of_date",
    "position_scope",
    "manual_review_flag",
    "baseline_optimized_score",
    "baseline_same_position_score",
}

CATEGORY_COLUMNS = ["position_group", "competition_id"]


def _season_sort_key(value: object) -> tuple[int, str]:
    text = str(value)
    match = re.search(r"\d{4}", text)
    if match:
        return int(match.group()), text
    match = re.search(r"\d{2}", text)
    if match:
        return int(match.group()), text
    return 0, text


def _normalize_player_key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().replace(".", " ").replace("-", " ").split())


def _spearman_like(pred: pd.Series | np.ndarray, actual: pd.Series | np.ndarray) -> float:
    frame = pd.DataFrame({"pred": pred, "actual": actual}).dropna()
    if len(frame) < 2:
        return float("nan")
    if frame["pred"].nunique() < 2 or frame["actual"].nunique() < 2:
        return float("nan")
    return float(frame["pred"].rank(method="average").corr(frame["actual"].rank(method="average")))


def _attach_optimizer_baseline(
    dataset: pd.DataFrame,
    baseline_ratings: pd.DataFrame | None,
) -> pd.DataFrame:
    if baseline_ratings is None or baseline_ratings.empty:
        result = dataset.copy()
        result["baseline_optimized_score"] = np.nan
        result["baseline_same_position_score"] = np.nan
        return result
    required = {"player", "season", "optimized_score"}
    if required - set(baseline_ratings.columns):
        result = dataset.copy()
        result["baseline_optimized_score"] = np.nan
        result["baseline_same_position_score"] = np.nan
        return result

    baseline = baseline_ratings.copy()
    baseline["player_key"] = baseline["player"].map(_normalize_player_key)
    baseline["season"] = baseline["season"].astype(str)
    agg = {"optimized_score": "mean"}
    if "same_position_score" in baseline.columns:
        agg["same_position_score"] = "mean"
    baseline = baseline.groupby(["player_key", "season"], as_index=False).agg(agg)
    baseline = baseline.rename(
        columns={
            "optimized_score": "baseline_optimized_score",
            "same_position_score": "baseline_same_position_score",
        },
    )

    result = dataset.copy()
    result["player_key"] = result["player_name"].map(_normalize_player_key)
    result = result.merge(baseline, on=["player_key", "season"], how="left")
    result = result.drop(columns=["player_key"])
    for col in ["baseline_optimized_score", "baseline_same_position_score"]:
        if col not in result.columns:
            result[col] = np.nan
    return result


def build_player_rating_nn_dataset(
    feature_matrix: pd.DataFrame,
    truth_labels: pd.DataFrame,
    *,
    baseline_ratings: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Join rating features to supervised truth labels and optional baseline scores."""
    if feature_matrix.empty or truth_labels.empty:
        return pd.DataFrame()

    from scoutfootball.evaluation.truth_labels import validate_truth_labels

    errors = validate_truth_labels(truth_labels)
    if errors:
        raise ValueError("; ".join(errors))

    features = feature_matrix.copy()
    if "season_id" not in features.columns:
        raise ValueError("rating feature matrix must contain season_id")
    if "player_id" not in features.columns:
        raise ValueError("rating feature matrix must contain player_id")
    if "player_name" not in features.columns:
        raise ValueError("rating feature matrix must contain player_name")
    features["season"] = features["season_id"].astype(str)

    labels = truth_labels.copy()
    labels["season"] = labels["season"].astype(str)
    labels["label_value"] = pd.to_numeric(labels["label_value"], errors="coerce")
    labels = labels[labels["label_value"].notna() & np.isfinite(labels["label_value"])]
    if labels.empty:
        return pd.DataFrame()

    labels["confidence_weight"] = (
        labels["label_confidence"].astype(str).str.lower().map(
            {"high": 1.0, "medium": 0.65, "low": 0.35},
        ).fillna(0.35)
    )

    def _weighted_label(group: pd.DataFrame) -> float:
        weights = group["confidence_weight"].to_numpy(dtype=float)
        values = group["label_value"].to_numpy(dtype=float)
        if weights.sum() <= 0:
            return float(values.mean())
        return float(np.average(values, weights=weights))

    labels = (
        labels.groupby(["player_id", "season"], as_index=False)
        .apply(
            lambda g: pd.Series(
                {
                    "label_value": _weighted_label(g),
                    "label_confidence": g["label_confidence"].iloc[0],
                    "label_sources": ",".join(sorted(set(g["label_source"].astype(str)))),
                },
            ),
            include_groups=False,
        )
        .reset_index(drop=True)
    )

    # Normalize player_id for matching: feature matrix uses "name|birth_year|nationality",
    # truth labels use just "name". Extract name part for join.
    def _extract_name(pid: str) -> str:
        return str(pid).split("|")[0].strip().lower()

    features["_join_name"] = features["player_id"].apply(lambda x: _extract_name(str(x)))
    labels["_join_name"] = labels["player_id"].apply(lambda x: _extract_name(str(x)))

    dataset = features.merge(
        labels,
        on=["_join_name", "season"],
        how="inner",
        suffixes=("", "_label"),
    )
    dataset = dataset.drop(columns=["_join_name"])
    # Clean up duplicate columns from merge
    for col in list(dataset.columns):
        if col.endswith("_label") and col.replace("_label", "") in dataset.columns:
            dataset = dataset.drop(columns=[col])
    dataset = _attach_optimizer_baseline(dataset, baseline_ratings)
    return dataset


def _select_feature_columns(dataset: pd.DataFrame) -> tuple[list[str], list[str]]:
    category_columns = [col for col in CATEGORY_COLUMNS if col in dataset.columns]
    numeric_columns: list[str] = []
    for col in dataset.columns:
        if col in ID_COLUMNS or col in category_columns:
            continue
        if pd.api.types.is_bool_dtype(dataset[col]):
            numeric_columns.append(col)
            continue
        if pd.api.types.is_numeric_dtype(dataset[col]):
            numeric_columns.append(col)
            continue
        converted = pd.to_numeric(dataset[col], errors="coerce")
        if converted.notna().mean() >= 0.7:
            dataset[col] = converted
            numeric_columns.append(col)
    return numeric_columns, category_columns


def _split_by_season(
    dataset: pd.DataFrame,
    *,
    test_seasons: int,
) -> tuple[pd.DataFrame, pd.DataFrame, tuple[str, ...], tuple[str, ...]]:
    seasons = tuple(sorted({str(s) for s in dataset["season"].dropna()}, key=_season_sort_key))
    if len(seasons) <= int(test_seasons):
        return pd.DataFrame(), pd.DataFrame(), tuple(), seasons
    test = seasons[-int(test_seasons):]
    train = seasons[: -int(test_seasons)]
    return (
        dataset[dataset["season"].isin(train)].copy(),
        dataset[dataset["season"].isin(test)].copy(),
        train,
        test,
    )


def _build_model(
    numeric_columns: list[str],
    category_columns: list[str],
    config: PlayerRatingNNConfig,
) -> Pipeline:
    numeric_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ],
    )
    category_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ],
    )
    transformers: list[tuple[str, Pipeline, list[str]]] = []
    if numeric_columns:
        transformers.append(("num", numeric_pipe, numeric_columns))
    if category_columns:
        transformers.append(("cat", category_pipe, category_columns))
    preprocessor = ColumnTransformer(transformers=transformers)
    model = MLPRegressor(
        hidden_layer_sizes=config.hidden_layer_sizes,
        alpha=config.alpha,
        learning_rate_init=config.learning_rate_init,
        max_iter=config.max_iter,
        random_state=config.random_state,
        early_stopping=config.early_stopping,
    )
    return Pipeline(steps=[("preprocess", preprocessor), ("model", model)])


def _regression_metrics(actual: pd.Series, pred: np.ndarray) -> dict[str, float]:
    return {
        "n": int(len(actual)),
        "mae": float(mean_absolute_error(actual, pred)) if len(actual) else float("nan"),
        "rmse": float(np.sqrt(mean_squared_error(actual, pred))) if len(actual) else float("nan"),
        "r2": float(r2_score(actual, pred)) if len(actual) >= 2 else float("nan"),
        "spearman": _spearman_like(pred, actual),
    }


def train_player_rating_nn(
    feature_matrix: pd.DataFrame,
    truth_labels: pd.DataFrame,
    *,
    baseline_ratings: pd.DataFrame | None = None,
    config: PlayerRatingNNConfig | None = None,
) -> PlayerRatingNNResult:
    """Train a supervised MLP candidate against player truth labels."""
    cfg = config or PlayerRatingNNConfig()
    dataset = build_player_rating_nn_dataset(
        feature_matrix,
        truth_labels,
        baseline_ratings=baseline_ratings,
    )
    if len(dataset) < cfg.min_labels:
        return PlayerRatingNNResult(
            trained=False,
            status=f"skipped: {len(dataset)} resolved labels, need at least {cfg.min_labels}",
            metrics={"n_labels": int(len(dataset)), "min_labels": int(cfg.min_labels)},
            predictions=pd.DataFrame(),
            feature_columns=[],
            category_columns=[],
        )

    numeric_columns, category_columns = _select_feature_columns(dataset)
    if not numeric_columns and not category_columns:
        return PlayerRatingNNResult(
            trained=False,
            status="skipped: no usable feature columns",
            metrics={"n_labels": int(len(dataset))},
            predictions=pd.DataFrame(),
            feature_columns=[],
            category_columns=[],
        )

    train_df, test_df, train_seasons, test_seasons = _split_by_season(
        dataset,
        test_seasons=cfg.test_seasons,
    )
    if train_df.empty or test_df.empty:
        return PlayerRatingNNResult(
            trained=False,
            status="skipped: need at least two chronological seasons for holdout",
            metrics={"n_labels": int(len(dataset))},
            predictions=pd.DataFrame(),
            feature_columns=[],
            category_columns=[],
        )

    model = _build_model(numeric_columns, category_columns, cfg)
    x_train = train_df[numeric_columns + category_columns]
    y_train = train_df["label_value"].astype(float)
    x_test = test_df[numeric_columns + category_columns]
    y_test = test_df["label_value"].astype(float)
    model.fit(x_train, y_train)

    train_pred = model.predict(x_train)
    test_pred = model.predict(x_test)

    median_baseline = DummyRegressor(strategy="median")
    median_baseline.fit(x_train, y_train)
    median_test_pred = median_baseline.predict(x_test)

    metrics = {
        "n_labels": int(len(dataset)),
        "train_seasons": list(train_seasons),
        "test_seasons": list(test_seasons),
        "train": _regression_metrics(y_train, train_pred),
        "test": _regression_metrics(y_test, test_pred),
        "median_baseline_test": _regression_metrics(y_test, median_test_pred),
    }
    baseline_test = test_df["baseline_optimized_score"]
    if baseline_test.notna().sum() >= 2:
        mask = baseline_test.notna()
        metrics["optimizer_baseline_test"] = _regression_metrics(
            y_test[mask],
            baseline_test[mask].to_numpy(dtype=float),
        )
    else:
        metrics["optimizer_baseline_test"] = {
            "n": int(baseline_test.notna().sum()),
            "mae": float("nan"),
            "rmse": float("nan"),
            "r2": float("nan"),
            "spearman": float("nan"),
        }

    predictions = pd.concat(
        [
            train_df.assign(split="train", nn_prediction=train_pred),
            test_df.assign(split="test", nn_prediction=test_pred),
        ],
        ignore_index=True,
        sort=False,
    )
    keep_cols = [
        "split",
        "player_id",
        "player_name",
        "team_name",
        "season",
        "position_group",
        "competition_id",
        "label_value",
        "nn_prediction",
        "baseline_optimized_score",
        "baseline_same_position_score",
        "label_sources",
    ]
    predictions = predictions[[col for col in keep_cols if col in predictions.columns]].copy()
    predictions["nn_residual"] = predictions["nn_prediction"] - predictions["label_value"]
    if "baseline_optimized_score" in predictions.columns:
        predictions["baseline_residual"] = (
            predictions["baseline_optimized_score"] - predictions["label_value"]
        )

    return PlayerRatingNNResult(
        trained=True,
        status=(
            "ok: trained supervised player_rating_nn "
            f"({len(train_df)} train labels, {len(test_df)} holdout labels)"
        ),
        metrics=metrics,
        predictions=predictions,
        feature_columns=numeric_columns,
        category_columns=category_columns,
        model=model,
    )


def write_player_rating_nn_artifacts(
    result: PlayerRatingNNResult,
    output_dir: Path,
    *,
    config: PlayerRatingNNConfig,
) -> None:
    """Persist player-rating NN artifacts and provenance."""
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_payload = {
        "trained": result.trained,
        "status": result.status,
        "metrics": result.metrics,
        "feature_columns": result.feature_columns,
        "category_columns": result.category_columns,
        "config": asdict(config),
    }
    with open(output_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2, ensure_ascii=False)
    if not result.predictions.empty:
        result.predictions.to_parquet(output_dir / "predictions.parquet", index=False)
    if result.model is not None:
        with open(output_dir / "model.pkl", "wb") as f:
            pickle.dump(result.model, f)


def train_player_rating_nn_from_files(
    *,
    settings: PlatformSettings | None = None,
    config: PlayerRatingNNConfig | None = None,
    output_dir: Path | None = None,
) -> PlayerRatingNNResult:
    """Train the supervised player-rating NN from local feature-store artifacts."""
    resolved = settings or PlatformSettings.from_root()
    cfg = config or PlayerRatingNNConfig()
    feature_path = resolved.gold_root / "feature_store" / "rating_feature_matrix.parquet"
    labels_path = resolved.gold_root / "feature_store" / "player_truth_labels.parquet"
    baseline_path = resolved.gold_root / "feature_store" / "player_ratings_optimized.parquet"

    if not feature_path.exists():
        result = PlayerRatingNNResult(
            trained=False,
            status=f"skipped: missing {feature_path.name}",
            metrics={},
            predictions=pd.DataFrame(),
            feature_columns=[],
            category_columns=[],
        )
    elif not labels_path.exists():
        result = PlayerRatingNNResult(
            trained=False,
            status=f"skipped: missing {labels_path.name}",
            metrics={},
            predictions=pd.DataFrame(),
            feature_columns=[],
            category_columns=[],
        )
    else:
        feature_matrix = pd.read_parquet(feature_path)
        truth_labels = pd.read_parquet(labels_path)
        baseline = pd.read_parquet(baseline_path) if baseline_path.exists() else None
        result = train_player_rating_nn(
            feature_matrix,
            truth_labels,
            baseline_ratings=baseline,
            config=cfg,
        )

    write_player_rating_nn_artifacts(
        result,
        output_dir or resolved.model_root / "player_rating_nn",
        config=cfg,
    )
    return result

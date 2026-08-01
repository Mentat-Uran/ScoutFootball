"""Weakly supervised neural candidate for team-points-calibrated ratings.

This module deliberately keeps the existing rating artifact untouched.  It
trains a player-level MLP against a team-season points proxy: player outputs
are aggregated with minutes weights, then calibrated to observed team points.
The target is therefore a team-performance proxy, not an independent label of
individual ability.  Results must remain candidate-only until the research
admission gates and independent labels are satisfied.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as torch_functional
from torch import nn


@dataclass(frozen=True)
class TeamPointsMLPConfig:
    """Configuration for the weakly supervised team-points candidate."""

    hidden_layer_sizes: tuple[int, ...] = (96, 48)
    epochs: int = 300
    learning_rate: float = 0.001
    weight_decay: float = 0.0001
    patience: int = 30
    validation_seasons: int = 1
    test_seasons: int = 1
    min_team_players: int = 5
    seed: int = 42
    grad_clip: float = 5.0


@dataclass
class TeamPointsMLPResult:
    """Candidate metrics and group/player predictions."""

    trained: bool
    status: str
    metrics: dict[str, Any]
    team_predictions: pd.DataFrame
    player_predictions: pd.DataFrame
    feature_columns: list[str]
    category_columns: list[str]
    model_state: dict[str, Any] | None = None


_EXCLUDED_COLUMNS = {
    "player",
    "player_id",
    "player_name",
    "team",
    "team_id",
    "team_name",
    "league",
    "season",
    "season_id",
    "source_name",
    "data_granularity",
    "position_source",
    "position_confidence",
    "optimized_score",
    "same_position_score",
    "actual_points",
    "total_points",
    "target_points",
}
_CATEGORY_COLUMNS = ("sub_position", "source_position", "position_group")


def _season_sort_key(value: object) -> tuple[int, str]:
    text = str(value)
    match = re.search(r"\d{4}", text)
    if match:
        return int(match.group()), text
    match = re.search(r"\d{2}", text)
    return (int(match.group()), text) if match else (0, text)


def _normalize_team_name(value: object) -> str:
    """Normalize the common accent/case variation used by local sources."""

    text = str(value or "").strip().casefold()
    replacements = {
        "paris saint-germain": "paris saint-germain",
        "psg": "paris saint-germain",
        "man utd": "manchester united",
        "manchester utd": "manchester united",
        "man city": "manchester city",
    }
    return replacements.get(text, text)


def _spearman(pred: np.ndarray, actual: np.ndarray) -> float:
    frame = pd.DataFrame({"pred": pred, "actual": actual}).dropna()
    if len(frame) < 2 or frame.nunique().min() < 2:
        return float("nan")
    return float(frame["pred"].rank().corr(frame["actual"].rank()))


def _metrics(actual: np.ndarray, pred: np.ndarray) -> dict[str, float | int]:
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    if len(actual) == 0:
        return {
            "n": 0,
            "mae": float("nan"),
            "rmse": float("nan"),
            "r2": float("nan"),
            "spearman": float("nan"),
            "bias": float("nan"),
        }
    residual = pred - actual
    ss_tot = float(np.sum((actual - actual.mean()) ** 2))
    ss_res = float(np.sum(residual**2))
    return {
        "n": int(len(actual)),
        "mae": float(np.mean(np.abs(residual))),
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "r2": float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan"),
        "spearman": _spearman(pred, actual),
        "bias": float(np.mean(residual)),
    }


class _FeatureEncoder:
    """Fit numeric imputation/scaling and categorical levels on train only."""

    def __init__(self, numeric_columns: list[str], category_columns: list[str]) -> None:
        self.numeric_columns = numeric_columns
        self.category_columns = category_columns
        self.medians: dict[str, float] = {}
        self.means: dict[str, float] = {}
        self.stds: dict[str, float] = {}
        self.category_levels: dict[str, list[str]] = {}

    def fit(self, frame: pd.DataFrame) -> _FeatureEncoder:
        for column in self.numeric_columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            median = float(values.median()) if values.notna().any() else 0.0
            filled = values.fillna(median).to_numpy(dtype=float)
            mean = float(np.mean(filled))
            std = float(np.std(filled))
            self.medians[column] = median
            self.means[column] = mean
            self.stds[column] = std if std > 1e-8 else 1.0
        for column in self.category_columns:
            values = frame[column].fillna("__missing__").astype(str)
            self.category_levels[column] = sorted(set(values))
        return self

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        blocks: list[np.ndarray] = []
        for column in self.numeric_columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            missing = values.isna().to_numpy(dtype=np.float32).reshape(-1, 1)
            filled = values.fillna(self.medians[column]).to_numpy(dtype=np.float32)
            scaled = ((filled - self.means[column]) / self.stds[column]).reshape(-1, 1)
            blocks.extend([scaled, missing])
        for column in self.category_columns:
            values = frame[column].fillna("__missing__").astype(str)
            levels = self.category_levels[column]
            lookup = {value: index for index, value in enumerate(levels)}
            encoded = np.zeros((len(frame), len(levels)), dtype=np.float32)
            for row, value in enumerate(values):
                if value in lookup:
                    encoded[row, lookup[value]] = 1.0
            blocks.append(encoded)
        if not blocks:
            return np.empty((len(frame), 0), dtype=np.float32)
        return np.concatenate(blocks, axis=1).astype(np.float32, copy=False)


def _select_columns(frame: pd.DataFrame) -> tuple[list[str], list[str]]:
    numeric: list[str] = []
    for column in frame.columns:
        if column in _EXCLUDED_COLUMNS or column in _CATEGORY_COLUMNS:
            continue
        converted = pd.to_numeric(frame[column], errors="coerce")
        if converted.notna().mean() >= 0.6:
            numeric.append(column)
    categories = [column for column in _CATEGORY_COLUMNS if column in frame.columns]
    return numeric, categories


def _build_groups(
    frame: pd.DataFrame,
    team_points: pd.DataFrame,
    *,
    seasons: set[str],
    min_team_players: int,
) -> pd.DataFrame:
    work = frame.loc[frame["season"].astype(str).isin(seasons)].copy()
    work["_team_key"] = work["team"].map(_normalize_team_name)
    work["season"] = work["season"].astype(str)
    work["league"] = work["league"].astype(str)
    counts = work.groupby(["_team_key", "league", "season"], observed=True).size()
    counts = counts[counts >= int(min_team_players)].rename("n_players").reset_index()

    points = team_points.copy()
    points["_team_key"] = points["team"].map(_normalize_team_name)
    points["season"] = points["season"].astype(str)
    points["league"] = points["league"].astype(str)
    points = points.rename(columns={"total_points": "actual_points"})
    points = points[["_team_key", "league", "season", "actual_points"]]
    return counts.merge(points, on=["_team_key", "league", "season"], how="inner")


class _TeamPointsMLP(nn.Module):
    def __init__(
        self,
        input_dim: int,
        hidden: tuple[int, ...],
        n_leagues: int,
        target_mean: float,
    ) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        current = input_dim
        for width in hidden:
            layers.extend([nn.Linear(current, width), nn.ReLU(), nn.Dropout(p=0.05)])
            current = width
        layers.append(nn.Linear(current, 1))
        self.network = nn.Sequential(*layers)
        self.raw_scale = nn.Parameter(torch.tensor(0.0))
        self.bias = nn.Parameter(torch.tensor(float(target_mean - 50.0)))
        self.league_bias = nn.Embedding(n_leagues + 1, 1)
        nn.init.zeros_(self.league_bias.weight)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return 100.0 * torch.sigmoid(self.network(features).squeeze(-1))

    def predict_points(
        self,
        features: torch.Tensor,
        group_index: torch.Tensor,
        group_league: torch.Tensor,
        weights: torch.Tensor,
        n_groups: int,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        player_rating = self(features)
        aggregate = torch.zeros(n_groups, dtype=player_rating.dtype, device=player_rating.device)
        aggregate.index_add_(0, group_index, player_rating * weights)
        scale = torch_functional.softplus(self.raw_scale) + 0.05
        predicted_points = (
            self.bias + scale * aggregate + self.league_bias(group_league).squeeze(-1)
        )
        return player_rating, predicted_points


def _group_tensors(
    frame: pd.DataFrame,
    groups: pd.DataFrame,
    encoder: _FeatureEncoder,
    league_levels: dict[str, int],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, pd.DataFrame]:
    work = frame.copy()
    work["_team_key"] = work["team"].map(_normalize_team_name)
    work["season"] = work["season"].astype(str)
    work["league"] = work["league"].astype(str)
    group_keys = groups["_team_key"].astype(str) + "|" + groups["league"] + "|" + groups["season"]
    group_lookup = {key: index for index, key in enumerate(group_keys)}
    row_keys = work["_team_key"] + "|" + work["league"] + "|" + work["season"]
    work["_group_index"] = row_keys.map(group_lookup)
    work = work[work["_group_index"].notna()].copy()
    work["_group_index"] = work["_group_index"].astype(int)
    minutes_source = (
        work["minutes"] if "minutes" in work.columns else pd.Series(1.0, index=work.index)
    )
    minutes = pd.to_numeric(minutes_source, errors="coerce").fillna(0.0).clip(lower=1.0)
    raw_weights = np.sqrt(minutes.to_numpy(dtype=np.float32))
    weight_sum = pd.Series(raw_weights).groupby(work["_group_index"].to_numpy()).transform("sum")
    weights = raw_weights / np.maximum(weight_sum.to_numpy(dtype=np.float32), 1e-6)
    league_index = np.array(
        [league_levels.get(str(value), len(league_levels)) for value in groups["league"]],
        dtype=np.int64,
    )
    return (
        torch.from_numpy(encoder.transform(work)),
        torch.from_numpy(work["_group_index"].to_numpy(dtype=np.int64)),
        torch.from_numpy(league_index),
        torch.from_numpy(weights.astype(np.float32)),
        work,
    )


def _evaluate_split(
    model: _TeamPointsMLP,
    frame: pd.DataFrame,
    groups: pd.DataFrame,
    encoder: _FeatureEncoder,
    league_levels: dict[str, int],
    split: str,
) -> tuple[dict[str, float | int], pd.DataFrame, pd.DataFrame]:
    features, group_index, group_league, weights, rows = _group_tensors(
        frame, groups, encoder, league_levels
    )
    model.eval()
    with torch.no_grad():
        player_rating, predicted = model.predict_points(
            features, group_index, group_league, weights, len(groups)
        )
    group_result = groups[["_team_key", "league", "season", "n_players", "actual_points"]].copy()
    group_result["predicted_points"] = predicted.numpy()
    group_result["split"] = split
    player_result = rows[["player", "team", "league", "season", "_group_index"]].copy()
    player_result["player_rating"] = player_rating.numpy()
    player_result["split"] = split
    metrics = _metrics(
        group_result["actual_points"].to_numpy(dtype=float),
        group_result["predicted_points"].to_numpy(dtype=float),
    )
    return metrics, group_result, player_result


def train_team_points_mlp(
    feature_frame: pd.DataFrame,
    team_points: pd.DataFrame,
    *,
    config: TeamPointsMLPConfig | None = None,
) -> TeamPointsMLPResult:
    """Train a chronological team-points proxy MLP and return candidate outputs."""

    cfg = config or TeamPointsMLPConfig()
    required = {"team", "league", "season"}
    if feature_frame.empty or team_points.empty:
        return TeamPointsMLPResult(
            False, "skipped: empty input", {}, pd.DataFrame(), pd.DataFrame(), [], []
        )
    if required - set(feature_frame.columns) or {"team", "league", "season", "total_points"} - set(
        team_points.columns
    ):
        return TeamPointsMLPResult(
            False,
            "skipped: missing team-points input columns",
            {},
            pd.DataFrame(),
            pd.DataFrame(),
            [],
            [],
        )

    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    frame = feature_frame.copy()
    frame["season"] = frame["season"].astype(str)
    seasons = tuple(sorted(frame["season"].dropna().unique(), key=_season_sort_key))
    if len(seasons) <= cfg.test_seasons + cfg.validation_seasons:
        return TeamPointsMLPResult(
            False,
            "skipped: need train, validation, and holdout seasons",
            {},
            pd.DataFrame(),
            pd.DataFrame(),
            [],
            [],
        )
    test_seasons = set(seasons[-cfg.test_seasons :])
    train_seasons = seasons[: -cfg.test_seasons]
    validation_seasons = set(train_seasons[-cfg.validation_seasons :])
    fit_seasons = set(train_seasons) - validation_seasons
    if not fit_seasons:
        return TeamPointsMLPResult(
            False,
            "skipped: no fit seasons after validation split",
            {},
            pd.DataFrame(),
            pd.DataFrame(),
            [],
            [],
        )

    fit_groups = _build_groups(
        frame, team_points, seasons=fit_seasons, min_team_players=cfg.min_team_players
    )
    validation_groups = _build_groups(
        frame, team_points, seasons=validation_seasons, min_team_players=cfg.min_team_players
    )
    train_groups = _build_groups(
        frame, team_points, seasons=set(train_seasons), min_team_players=cfg.min_team_players
    )
    test_groups = _build_groups(
        frame, team_points, seasons=test_seasons, min_team_players=cfg.min_team_players
    )
    if fit_groups.empty or validation_groups.empty or test_groups.empty:
        return TeamPointsMLPResult(
            False,
            "skipped: insufficient matched team-season groups",
            {
                "groups": {
                    "fit": len(fit_groups),
                    "validation": len(validation_groups),
                    "train": len(train_groups),
                    "test": len(test_groups),
                }
            },
            pd.DataFrame(),
            pd.DataFrame(),
            [],
            [],
        )

    numeric_columns, category_columns = _select_columns(frame)
    encoder = _FeatureEncoder(numeric_columns, category_columns).fit(
        frame[frame["season"].isin(fit_seasons)]
    )
    league_levels = {
        str(value): index
        for index, value in enumerate(sorted(fit_groups["league"].astype(str).unique()))
    }
    fit_features, fit_index, fit_leagues, fit_weights, _ = _group_tensors(
        frame, fit_groups, encoder, league_levels
    )
    fit_target = torch.from_numpy(fit_groups["actual_points"].to_numpy(dtype=np.float32))
    input_dim = int(fit_features.shape[1])
    if input_dim == 0:
        return TeamPointsMLPResult(
            False, "skipped: no usable features", {}, pd.DataFrame(), pd.DataFrame(), [], []
        )

    model = _TeamPointsMLP(
        input_dim, cfg.hidden_layer_sizes, len(league_levels), float(fit_target.mean())
    )
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay
    )
    best_state: dict[str, Any] | None = None
    best_validation = float("inf")
    stale_epochs = 0
    history: list[dict[str, float | int]] = []
    validation_features, validation_index, validation_leagues, validation_weights, _ = (
        _group_tensors(frame, validation_groups, encoder, league_levels)
    )
    validation_target = torch.from_numpy(
        validation_groups["actual_points"].to_numpy(dtype=np.float32)
    )

    for epoch in range(cfg.epochs):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        _, predicted = model.predict_points(
            fit_features, fit_index, fit_leagues, fit_weights, len(fit_groups)
        )
        loss = 0.75 * torch_functional.mse_loss(
            predicted, fit_target
        ) + 0.25 * torch_functional.smooth_l1_loss(
            predicted,
            fit_target,
            beta=8.0,
        )
        loss.backward()
        if cfg.grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
        optimizer.step()
        model.eval()
        with torch.no_grad():
            _, validation_pred = model.predict_points(
                validation_features,
                validation_index,
                validation_leagues,
                validation_weights,
                len(validation_groups),
            )
            validation_loss = float(
                torch_functional.mse_loss(validation_pred, validation_target).item()
            )
        history.append(
            {
                "epoch": epoch + 1,
                "train_loss": float(loss.item()),
                "validation_loss": validation_loss,
            }
        )
        if validation_loss + 1e-6 < best_validation:
            best_validation = validation_loss
            best_state = copy.deepcopy(model.state_dict())
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= cfg.patience:
                break
    if best_state is None:
        return TeamPointsMLPResult(
            False,
            "failed: no validation checkpoint",
            {},
            pd.DataFrame(),
            pd.DataFrame(),
            numeric_columns,
            category_columns,
        )
    model.load_state_dict(best_state)

    fit_metrics, fit_predictions, fit_players = _evaluate_split(
        model, frame, fit_groups, encoder, league_levels, "fit"
    )
    validation_metrics, validation_predictions, validation_players = _evaluate_split(
        model, frame, validation_groups, encoder, league_levels, "validation"
    )
    train_metrics, train_predictions, train_players = _evaluate_split(
        model, frame, train_groups, encoder, league_levels, "train"
    )
    test_metrics, test_predictions, test_players = _evaluate_split(
        model, frame, test_groups, encoder, league_levels, "test"
    )
    all_groups = pd.concat([train_predictions, test_predictions], ignore_index=True)
    all_players = pd.concat([train_players, test_players], ignore_index=True)
    metrics: dict[str, Any] = {
        "train_seasons": list(train_seasons),
        "fit_seasons": sorted(fit_seasons, key=_season_sort_key),
        "validation_seasons": sorted(validation_seasons, key=_season_sort_key),
        "test_seasons": sorted(test_seasons, key=_season_sort_key),
        "groups": {
            "fit": len(fit_groups),
            "validation": len(validation_groups),
            "train": len(train_groups),
            "test": len(test_groups),
        },
        "fit": fit_metrics,
        "validation": validation_metrics,
        "train": train_metrics,
        "test": test_metrics,
        "epochs_completed": len(history),
        "best_validation_mse": best_validation,
        "target_semantics": "team-season points proxy; not independent player-ability truth",
        "history": history,
    }
    return TeamPointsMLPResult(
        True,
        (
            "ok: trained team-points MLP candidate "
            f"({len(train_groups)} train groups, {len(test_groups)} holdout groups)"
        ),
        metrics,
        all_groups,
        all_players,
        numeric_columns,
        category_columns,
        {
            key: value.detach().cpu() if isinstance(value, torch.Tensor) else value
            for key, value in model.state_dict().items()
        },
    )


def write_team_points_mlp_artifacts(
    result: TeamPointsMLPResult,
    output_dir: Path,
    *,
    config: TeamPointsMLPConfig,
    input_frame: pd.DataFrame | None = None,
) -> None:
    """Write candidate-only artifacts with explicit proxy-target semantics."""

    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = {
        "trained": result.trained,
        "status": result.status,
        "metrics": result.metrics,
        "config": asdict(config),
        "feature_columns": result.feature_columns,
        "category_columns": result.category_columns,
        "activation": {"status": "not_activated", "reason": "candidate experiment only"},
        "target_semantics": "team-season points proxy; not independent player-ability truth",
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if not result.team_predictions.empty:
        result.team_predictions.to_parquet(output_dir / "team_predictions.parquet", index=False)
    if not result.player_predictions.empty:
        result.player_predictions.to_parquet(output_dir / "player_predictions.parquet", index=False)
    if result.model_state is not None:
        torch.save(result.model_state, output_dir / "model_state.pt")
    payload = input_frame.to_csv(index=False).encode("utf-8") if input_frame is not None else b""
    manifest = {
        "input_sha256": hashlib.sha256(payload).hexdigest() if payload else None,
        "feature_columns": result.feature_columns,
        "category_columns": result.category_columns,
        "config": asdict(config),
        "target_semantics": "team-season points proxy; not independent player-ability truth",
    }
    (output_dir / "feature_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Keep the candidate visible to the existing read-only model registry.
    # This is deliberately not an optimizer-admission record: it has no
    # independent player label or candidate rating parquet, so admission must
    # remain not_reviewable until those contracts exist.
    feature_store_manifest = output_dir.parents[2] / "gold" / "feature_store" / (
        "rating_feature_matrix_manifest.json"
    )
    recorded_feature_manifest: dict[str, Any] = {
        "path": "gold/feature_store/rating_feature_matrix_manifest.json",
        "hash": None,
        "schema_version": None,
    }
    if feature_store_manifest.is_file():
        try:
            current = json.loads(feature_store_manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
        if isinstance(current, dict):
            recorded_feature_manifest.update(
                {
                    "hash": current.get("hash"),
                    "schema_version": current.get("schema_version"),
                    "generated_at": current.get("generated_at"),
                    "input_hash": current.get("input_hash"),
                }
            )
    run_id = output_dir.name
    run_meta = {
        "timestamp": run_id,
        "run_id": run_id,
        "model_type": "team_points_mlp",
        "input_hash": manifest["input_sha256"],
        "metrics": result.metrics,
        "lineage": {
            "schema": "scoutfootball.model-run-lineage",
            "version": "1.0.0",
            "status": "recorded",
            "dataset_snapshot": {"input_hash": manifest["input_sha256"]},
            "feature_manifest": recorded_feature_manifest,
        },
        "activation": metrics["activation"],
        "candidate_artifacts": {
            "model": {"path": "model_state.pt", "scope": "unactivated_local_candidate"},
            "team_predictions": {
                "path": "team_predictions.parquet",
                "scope": "proxy_target_evaluation",
            },
            "player_predictions": {
                "path": "player_predictions.parquet",
                "scope": "proxy_target_evaluation",
            },
        },
        "args": asdict(config),
        "target_semantics": metrics["target_semantics"],
    }
    (output_dir / "meta.json").write_text(
        json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

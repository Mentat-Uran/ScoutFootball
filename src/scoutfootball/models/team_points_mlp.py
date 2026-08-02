"""Weakly supervised neural candidates for team-points-calibrated ratings.

This module deliberately keeps the existing rating artifact untouched.  It
trains either a player-level MLP or a Set Transformer against a team-season
points proxy: player outputs are aggregated with minutes weights, then
calibrated to observed team points.  The Set Transformer processes each
team-season as a permutation-invariant player set and uses self-attention plus
pooling attention to model player interactions.
The target is therefore a team-performance proxy, not an independent label of
individual ability.  Results must remain candidate-only until the research
admission gates and independent labels are satisfied.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as torch_functional
from torch import nn

from scoutfootball.entities.normalize import normalize_team_name


@dataclass(frozen=True)
class TeamPointsMLPConfig:
    """Configuration for the weakly supervised team-points candidate."""

    architecture: str = "set_transformer"
    hidden_layer_sizes: tuple[int, ...] = (96, 48)
    attention_dim: int = 48
    attention_heads: int = 4
    attention_layers: int = 1
    attention_dropout: float = 0.05
    epochs: int = 400
    learning_rate: float = 0.001
    weight_decay: float = 0.0001
    patience: int = 50
    validation_seasons: int = 1
    test_seasons: int = 1
    min_team_players: int = 5
    seed: int = 42
    grad_clip: float = 5.0
    soft_rank_temperature: float = 4.0
    spearman_loss_weight: float = 0.30
    points_regression_weight: float = 0.20
    distribution_loss_weight: float = 0.05
    quantile_loss_weight: float = 0.08
    tail_loss_weight: float = 0.08
    position_consistency_weight: float = 0.10
    truth_label_weight: float = 0.08
    prior_weight: float = 0.01


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
    "optimizer_prior_score",
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
    """Use the shared cross-source team identity vocabulary."""

    return normalize_team_name(value if value is not None else "")


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


def _corrcoef_torch(left: torch.Tensor, right: torch.Tensor) -> torch.Tensor:
    left = left - left.mean()
    right = right - right.mean()
    denominator = torch.sqrt(torch.sum(left * left) * torch.sum(right * right)).clamp_min(1e-8)
    return torch.sum(left * right) / denominator


def _soft_rank(values: torch.Tensor, temperature: float) -> torch.Tensor:
    pairwise = (values[:, None] - values[None, :]) / max(float(temperature), 1e-6)
    return torch.sigmoid(pairwise).sum(dim=1)


def _composite_team_loss(
    predicted: torch.Tensor,
    actual: torch.Tensor,
    leagues: pd.Series,
    config: TeamPointsMLPConfig,
) -> tuple[torch.Tensor, dict[str, float]]:
    """Port the optimizer's ranking, calibration, distribution and bias guards."""
    actual_detached = actual.detach()
    pred_rank = _soft_rank(predicted, config.soft_rank_temperature)
    actual_rank = _soft_rank(actual_detached, config.soft_rank_temperature)
    soft_spearman = _corrcoef_torch(pred_rank, actual_rank)
    pearson = _corrcoef_torch(predicted, actual_detached)
    rank_loss = 1.0 - (0.7 * soft_spearman + 0.3 * pearson)

    pred_std = predicted.detach().std(unbiased=False).clamp_min(1.0)
    actual_std = actual_detached.std(unbiased=False).clamp_min(1.0)
    calibrated = (
        predicted - predicted.detach().mean()
    ) / pred_std * actual_std + actual_detached.mean()
    residual = (calibrated - actual_detached) / actual_std
    calibrated_points_loss = torch.mean(residual.square())
    raw_residual = (predicted - actual_detached) / actual_std
    raw_points_loss = torch.mean(raw_residual.square())
    points_loss = 0.5 * raw_points_loss + 0.5 * calibrated_points_loss
    sorted_loss = torch.mean(
        ((torch.sort(calibrated).values - torch.sort(actual_detached).values) / actual_std).square()
    )
    quantile_loss = (
        torch.stack(
            [
                (
                    (torch.quantile(calibrated, q) - torch.quantile(actual_detached, q))
                    / actual_std
                ).square()
                for q in (0.1, 0.25, 0.5, 0.75, 0.9)
            ]
        ).mean()
        if len(actual) >= 5
        else torch.zeros((), device=predicted.device)
    )
    predicted_range = calibrated.max() - calibrated.min()
    actual_range = (actual_detached.max() - actual_detached.min()).clamp_min(1.0)
    range_loss = (1.0 - predicted_range / actual_range).square()
    if len(actual) >= 5:
        low = torch.quantile(actual_detached, 0.2)
        high = torch.quantile(actual_detached, 0.8)
        tail = (actual_detached <= low) | (actual_detached >= high)
        tail_loss = torch.mean(((calibrated[tail] - actual_detached[tail]) / actual_std).square())
    else:
        tail_loss = torch.zeros((), device=predicted.device)
    league_losses: list[torch.Tensor] = []
    league_values = leagues.astype(str).to_numpy()
    for league in sorted(set(league_values)):
        mask = torch.tensor(league_values == league, dtype=torch.bool, device=predicted.device)
        if int(mask.sum()) >= 5:
            league_losses.append(
                torch.mean((calibrated[mask] - actual_detached[mask]) / actual_std) ** 2
            )
    league_bias = (
        torch.stack(league_losses).mean()
        if league_losses
        else torch.zeros((), device=predicted.device)
    )
    total = (
        config.spearman_loss_weight * rank_loss
        + config.points_regression_weight * points_loss
        + config.distribution_loss_weight * sorted_loss
        + config.quantile_loss_weight * quantile_loss
        + config.tail_loss_weight * (tail_loss + range_loss + league_bias) / 3.0
    )
    components = {
        "rank_loss": float(rank_loss.detach().cpu()),
        "points_loss": float(points_loss.detach().cpu()),
        "raw_points_loss": float(raw_points_loss.detach().cpu()),
        "distribution_loss": float(sorted_loss.detach().cpu()),
        "quantile_loss": float(quantile_loss.detach().cpu()),
        "tail_loss": float(tail_loss.detach().cpu()),
        "range_loss": float(range_loss.detach().cpu()),
        "league_bias": float(league_bias.detach().cpu()),
        "soft_spearman": float(soft_spearman.detach().cpu()),
        "soft_pearson": float(pearson.detach().cpu()),
    }
    return total, components


def _position_consistency_loss(ratings: torch.Tensor, rows: pd.DataFrame) -> torch.Tensor:
    """Keep each position's rating ordering aligned with its core metric."""
    losses: list[torch.Tensor] = []
    for position, metric in _POSITION_CORE_METRICS.items():
        if metric not in rows.columns:
            continue
        mask = rows["sub_position"].astype(str).eq(position).to_numpy()
        values = pd.to_numeric(rows[metric], errors="coerce").to_numpy(dtype=float)
        valid = mask & np.isfinite(values)
        if int(valid.sum()) < 5:
            continue
        metric_tensor = torch.from_numpy(values[valid].astype(np.float32)).to(ratings.device)
        rating_tensor = ratings[torch.from_numpy(valid).to(ratings.device)]
        if float(metric_tensor.std(unbiased=False)) < 1e-8:
            continue
        rank_corr = _corrcoef_torch(_soft_rank(rating_tensor, 4.0), _soft_rank(metric_tensor, 4.0))
        losses.append(1.0 - rank_corr)
    return torch.stack(losses).mean() if losses else torch.zeros((), device=ratings.device)


def _normalize_player_name(value: object) -> str:
    text = str(value).split("|", 1)[0]
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text).strip().casefold()


def _truth_label_lookup(truth_labels: pd.DataFrame | None) -> dict[tuple[str, str], float]:
    if truth_labels is None or truth_labels.empty:
        return {}
    from scoutfootball.evaluation.truth_labels import filter_supervision_eligible_truth_labels

    labels = filter_supervision_eligible_truth_labels(truth_labels).copy()
    if labels.empty or not {"player_id", "season", "label_value"}.issubset(labels.columns):
        return {}
    labels["player_id"] = labels["player_id"].map(_normalize_player_name)
    labels["season"] = labels["season"].astype(str)
    labels["label_value"] = pd.to_numeric(labels["label_value"], errors="coerce")
    labels = labels.dropna(subset=["label_value"])
    labels = labels.groupby(["player_id", "season"], as_index=False)["label_value"].mean()
    return {
        (_normalize_player_name(row.player_id), str(row.season)): float(row.label_value)
        for row in labels.itertuples(index=False)
    }


def _truth_targets(rows: pd.DataFrame, lookup: dict[tuple[str, str], float]) -> np.ndarray:
    if not lookup:
        return np.full(len(rows), np.nan, dtype=np.float32)
    return np.asarray(
        [
            lookup.get((_normalize_player_name(player), str(season)), np.nan)
            for player, season in zip(rows["player"], rows["season"], strict=False)
        ],
        dtype=np.float32,
    )


_POSITION_LEVELS = ("ST", "W", "AM", "CM", "DM", "FB", "CB", "GK", "UNK")
_POSITION_INDEX = {value: index for index, value in enumerate(_POSITION_LEVELS)}
_POSITION_SLOT_GROUPS = {
    "GK": "GK",
    "CB": "CB",
    "FB": "FB",
    "DM": "MF",
    "CM": "MF",
    "AM": "ATT",
    "W": "ATT",
    "ST": "ATT",
}
_POSITION_SLOT_CAPS = {"GK": 1.0, "CB": 2.5, "FB": 1.5, "MF": 2.5, "ATT": 2.5}
_POSITION_CORE_METRICS = {
    "ST": "npg_p90",
    "W": "g_a_volume",
    "AM": "assists_p90",
    "CM": "possession_composite",
    "DM": "defense_composite",
    "FB": "crosses_p90",
    "CB": "defense_composite",
    "GK": "defense_composite",
}


def _build_position_capped_weights(work: pd.DataFrame) -> np.ndarray:
    """Mirror optimizer team aggregation: minutes/core blend plus slot caps."""
    minutes = pd.to_numeric(work["minutes"], errors="coerce").fillna(0.0).clip(lower=0.0)
    capped = np.sqrt(np.minimum(minutes.to_numpy(dtype=float), 1500.0))
    core = 1.0 / (
        1.0 + np.exp(-np.clip((minutes.to_numpy(dtype=float) - 450.0) / 180.0, -50.0, 50.0))
    )
    work["_capped"] = capped
    work["_core"] = core
    groups = work.groupby(["_team_key", "league", "season"], sort=False)
    size = groups["_team_key"].transform("size").to_numpy(dtype=float)
    capped_sum = groups["_capped"].transform("sum").to_numpy(dtype=float)
    core_sum = groups["_core"].transform("sum").to_numpy(dtype=float)
    fallback = np.divide(1.0, size, out=np.zeros_like(size), where=size > 0)
    weights = 0.55 * np.divide(capped, capped_sum, out=fallback, where=capped_sum > 0)
    weights += 0.45 * np.divide(core, core_sum, out=fallback, where=core_sum > 0)
    work["_slot_group"] = work["sub_position"].map(_POSITION_SLOT_GROUPS).fillna("MF")
    work["_weight"] = weights
    work["_team_season"] = work["_team_key"] + "|" + work["league"] + "|" + work["season"]
    slot_totals = work.groupby(["_team_season", "_slot_group"], sort=False)["_weight"].transform(
        "sum"
    )
    caps = work["_slot_group"].map(_POSITION_SLOT_CAPS).fillna(2.5).to_numpy(dtype=float)
    weights = weights * np.where(slot_totals.to_numpy(dtype=float) > caps, caps / slot_totals, 1.0)
    total = work.groupby(["_team_key", "league", "season"], sort=False)["_weight"].transform("sum")
    return np.divide(
        weights, total.to_numpy(dtype=float), out=fallback, where=total.to_numpy(dtype=float) > 0
    ).astype(np.float32)


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


def _team_coverage_summary(
    frame: pd.DataFrame,
    team_points: pd.DataFrame,
    *,
    seasons: set[str],
    min_team_players: int,
) -> dict[str, Any]:
    """Report coverage against only leagues with player features.

    The old ``154/538`` diagnostic compared raw team strings across all
    football-data leagues.  That denominator mixed unsupported leagues and
    multi-club season strings with valid player/team-season groups.  This
    summary uses the actual training unit: one canonical team, league, and
    season with at least ``min_team_players`` feature rows.
    """

    work = frame.loc[frame["season"].astype(str).isin(seasons)].copy()
    work["_team_key"] = work["team"].map(_normalize_team_name)
    work["league"] = work["league"].astype(str)
    work["season"] = work["season"].astype(str)
    counts = (
        work.groupby(["_team_key", "league", "season"], observed=True)
        .size()
        .rename("n_players")
        .reset_index()
    )
    eligible_feature_groups = counts.loc[counts["n_players"] >= min_team_players]

    points = team_points.copy()
    points["_team_key"] = points["team"].map(_normalize_team_name)
    points["league"] = points["league"].astype(str)
    points["season"] = points["season"].astype(str)
    # Do not count leagues for which this feature matrix has no player source.
    points = points.loc[points["league"].isin(work["league"].unique())]
    target_groups = points[["_team_key", "league", "season"]].drop_duplicates()
    target_groups = target_groups.loc[target_groups["season"].isin(seasons)]
    matched = target_groups.merge(
        eligible_feature_groups[["_team_key", "league", "season"]],
        on=["_team_key", "league", "season"],
        how="inner",
    )
    return {
        "scope": "leagues_with_player_features",
        "source_leagues": sorted(work["league"].unique()),
        "target_team_seasons": int(len(target_groups)),
        "eligible_feature_team_seasons": int(len(eligible_feature_groups)),
        "matched_team_seasons": int(len(matched)),
        "coverage_rate": (float(len(matched) / len(target_groups)) if len(target_groups) else 0.0),
        "unsupported_target_leagues": sorted(
            set(team_points["league"].astype(str).unique()) - set(work["league"].unique())
        ),
    }


class _TeamPointsMLP(nn.Module):
    def __init__(
        self,
        input_dim: int,
        hidden: tuple[int, ...],
        n_leagues: int,
        n_positions: int,
        target_mean: float,
    ) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        current = input_dim
        for width in hidden:
            layers.extend([nn.Linear(current, width), nn.ReLU(), nn.Dropout(p=0.05)])
            current = width
        self.network = nn.Sequential(*layers)
        position_width = max(8, min(24, current // 2))
        self.position_embedding = nn.Embedding(n_positions, position_width)
        self.rating_head = nn.Sequential(
            nn.Linear(current + position_width, max(8, current // 2)),
            nn.ReLU(),
            nn.Linear(max(8, current // 2), 1),
        )
        self.position_offset = nn.Embedding(n_positions, 1)
        nn.init.zeros_(self.position_offset.weight)
        self.raw_scale = nn.Parameter(torch.tensor(0.0))
        self.bias = nn.Parameter(torch.tensor(float(target_mean - 50.0)))
        self.league_bias = nn.Embedding(n_leagues + 1, 1)
        nn.init.zeros_(self.league_bias.weight)

    def forward(
        self,
        features: torch.Tensor,
        position_index: torch.Tensor,
        prior_score: torch.Tensor | None = None,
    ) -> torch.Tensor:
        hidden = self.network(features)
        position = self.position_embedding(position_index)
        logits = self.rating_head(torch.cat([hidden, position], dim=1)).squeeze(-1)
        logits = logits + self.position_offset(position_index).squeeze(-1)
        residual = 20.0 * torch.tanh(logits)
        baseline = torch.full_like(residual, 50.0) if prior_score is None else prior_score
        return torch.clamp(baseline + residual, min=0.0, max=100.0)

    def predict_points(
        self,
        features: torch.Tensor,
        group_index: torch.Tensor,
        group_league: torch.Tensor,
        weights: torch.Tensor,
        n_groups: int,
        position_index: torch.Tensor,
        prior_score: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        player_rating = self(features, position_index, prior_score)
        aggregate = torch.zeros(n_groups, dtype=player_rating.dtype, device=player_rating.device)
        aggregate.index_add_(0, group_index, player_rating * weights)
        scale = torch_functional.softplus(self.raw_scale) + 0.05
        predicted_points = (
            self.bias + scale * aggregate + self.league_bias(group_league).squeeze(-1)
        )
        return player_rating, predicted_points


class _TeamPointsSetTransformer(nn.Module):
    """Permutation-invariant team model with self-attention and PMA pooling.

    Every group is a ``team|league|season`` player set.  A shared encoder
    embeds each player, a self-attention block models player interactions, and
    a learned pooling query summarizes the set for the team-points head.  The
    player rating head still emits one score per player so the existing rating
    artifact contract can be reused.
    """

    def __init__(
        self,
        input_dim: int,
        hidden: tuple[int, ...],
        n_leagues: int,
        n_positions: int,
        target_mean: float,
        *,
        attention_dim: int = 48,
        attention_heads: int = 4,
        attention_layers: int = 1,
        attention_dropout: float = 0.05,
    ) -> None:
        super().__init__()
        del hidden  # The attention dimension controls the set representation.
        if attention_dim < 8 or attention_dim % attention_heads != 0:
            raise ValueError("attention_dim must be >= 8 and divisible by attention_heads")
        if attention_layers < 1:
            raise ValueError("attention_layers must be positive")
        position_width = max(8, min(24, attention_dim // 2))
        self.position_embedding = nn.Embedding(n_positions, position_width)
        self.player_encoder = nn.Sequential(
            nn.Linear(input_dim + position_width, attention_dim),
            nn.ReLU(),
            nn.LayerNorm(attention_dim),
            nn.Dropout(p=attention_dropout),
        )
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=attention_dim,
            nhead=attention_heads,
            dim_feedforward=max(attention_dim * 2, 32),
            dropout=attention_dropout,
            activation="gelu",
            batch_first=True,
            norm_first=False,
        )
        self.set_attention = nn.TransformerEncoder(encoder_layer, num_layers=attention_layers)
        self.pool_query = nn.Parameter(torch.randn(1, 1, attention_dim) * 0.02)
        self.pool_attention = nn.MultiheadAttention(
            attention_dim,
            attention_heads,
            dropout=attention_dropout,
            batch_first=True,
        )
        head_width = max(8, attention_dim // 2)
        self.rating_head = nn.Sequential(
            nn.Linear(attention_dim * 2, head_width),
            nn.ReLU(),
            nn.Linear(head_width, 1),
        )
        self.context_points_head = nn.Linear(attention_dim, 1)
        nn.init.zeros_(self.context_points_head.weight)
        nn.init.zeros_(self.context_points_head.bias)
        self.position_offset = nn.Embedding(n_positions, 1)
        nn.init.zeros_(self.position_offset.weight)
        self.raw_scale = nn.Parameter(torch.tensor(0.0))
        self.bias = nn.Parameter(torch.tensor(float(target_mean - 50.0)))
        self.league_bias = nn.Embedding(n_leagues + 1, 1)
        nn.init.zeros_(self.league_bias.weight)

    def _encode_set(
        self, features: torch.Tensor, position_index: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        position = self.position_embedding(position_index)
        encoded = self.player_encoder(torch.cat([features, position], dim=1)).unsqueeze(0)
        contextual = self.set_attention(encoded)
        query = self.pool_query.expand(1, -1, -1)
        pooled, _ = self.pool_attention(query, contextual, contextual)
        return contextual.squeeze(0), pooled.squeeze(0).squeeze(0)

    def forward(
        self,
        features: torch.Tensor,
        position_index: torch.Tensor,
        prior_score: torch.Tensor | None = None,
    ) -> torch.Tensor:
        contextual, pooled = self._encode_set(features, position_index)
        rating_context = torch.cat(
            [contextual, pooled.expand(contextual.shape[0], -1)], dim=1
        )
        logits = self.rating_head(rating_context).squeeze(-1)
        logits = logits + self.position_offset(position_index).squeeze(-1)
        residual = 20.0 * torch.tanh(logits)
        baseline = torch.full_like(residual, 50.0) if prior_score is None else prior_score
        return torch.clamp(baseline + residual, min=0.0, max=100.0)

    def predict_points(
        self,
        features: torch.Tensor,
        group_index: torch.Tensor,
        group_league: torch.Tensor,
        weights: torch.Tensor,
        n_groups: int,
        position_index: torch.Tensor,
        prior_score: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        rating_chunks: list[torch.Tensor] = []
        index_chunks: list[torch.Tensor] = []
        point_values: list[torch.Tensor] = []
        scale = torch_functional.softplus(self.raw_scale) + 0.05
        for group_id in range(n_groups):
            indices = torch.where(group_index == group_id)[0]
            if indices.numel() == 0:
                point_values.append(
                    self.bias + self.league_bias(group_league[group_id]).squeeze(-1)
                )
                continue
            contextual, pooled = self._encode_set(
                features.index_select(0, indices), position_index.index_select(0, indices)
            )
            group_positions = position_index.index_select(0, indices)
            rating_context = torch.cat(
                [contextual, pooled.expand(contextual.shape[0], -1)], dim=1
            )
            logits = self.rating_head(rating_context).squeeze(-1)
            logits = logits + self.position_offset(group_positions).squeeze(-1)
            residual = 20.0 * torch.tanh(logits)
            if prior_score is None:
                baseline = torch.full_like(residual, 50.0)
            else:
                baseline = prior_score.index_select(0, indices)
            group_rating = torch.clamp(baseline + residual, min=0.0, max=100.0)
            rating_chunks.append(group_rating)
            index_chunks.append(indices)
            aggregate = torch.sum(weights.index_select(0, indices) * group_rating)
            context_adjustment = self.context_points_head(pooled).squeeze(-1)
            point_values.append(
                self.bias
                + scale * aggregate
                + self.league_bias(group_league[group_id]).squeeze(-1)
                + context_adjustment
            )
        if not rating_chunks:
            player_rating = features.new_empty((0,))
        else:
            all_indices = torch.cat(index_chunks)
            order = torch.argsort(all_indices)
            player_rating = torch.cat(rating_chunks).index_select(0, order)
        return player_rating, torch.stack(point_values)


def _build_team_points_model(
    config: TeamPointsMLPConfig,
    *,
    input_dim: int,
    n_leagues: int,
    n_positions: int,
    target_mean: float,
) -> nn.Module:
    if config.architecture == "mlp":
        return _TeamPointsMLP(
            input_dim,
            config.hidden_layer_sizes,
            n_leagues,
            n_positions,
            target_mean,
        )
    if config.architecture == "set_transformer":
        return _TeamPointsSetTransformer(
            input_dim,
            config.hidden_layer_sizes,
            n_leagues,
            n_positions,
            target_mean,
            attention_dim=config.attention_dim,
            attention_heads=config.attention_heads,
            attention_layers=config.attention_layers,
            attention_dropout=config.attention_dropout,
        )
    raise ValueError("architecture must be 'mlp' or 'set_transformer'")


def _group_tensors(
    frame: pd.DataFrame,
    groups: pd.DataFrame,
    encoder: _FeatureEncoder,
    league_levels: dict[str, int],
) -> tuple[
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
    pd.DataFrame,
]:
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
    work["minutes"] = minutes.to_numpy(dtype=float)
    weights = _build_position_capped_weights(work)
    league_index = np.array(
        [league_levels.get(str(value), len(league_levels)) for value in groups["league"]],
        dtype=np.int64,
    )
    position_index = work["sub_position"].map(_POSITION_INDEX).fillna(_POSITION_INDEX["UNK"])
    prior_score = (
        pd.to_numeric(
            work.get("optimizer_prior_score", pd.Series(50.0, index=work.index)), errors="coerce"
        )
        .fillna(50.0)
        .clip(lower=0.0, upper=100.0)
    )
    return (
        torch.from_numpy(encoder.transform(work)),
        torch.from_numpy(work["_group_index"].to_numpy(dtype=np.int64)),
        torch.from_numpy(league_index),
        torch.from_numpy(weights.astype(np.float32)),
        torch.from_numpy(position_index.to_numpy(dtype=np.int64)),
        torch.from_numpy(prior_score.to_numpy(dtype=np.float32)),
        work,
    )


def _evaluate_split(
    model: Any,
    frame: pd.DataFrame,
    groups: pd.DataFrame,
    encoder: _FeatureEncoder,
    league_levels: dict[str, int],
    split: str,
) -> tuple[dict[str, float | int], pd.DataFrame, pd.DataFrame]:
    features, group_index, group_league, weights, position_index, prior_score, rows = (
        _group_tensors(frame, groups, encoder, league_levels)
    )
    device = next(model.parameters()).device
    features = features.to(device)
    group_index = group_index.to(device)
    group_league = group_league.to(device)
    weights = weights.to(device)
    position_index = position_index.to(device)
    prior_score = prior_score.to(device)
    model.eval()
    with torch.no_grad():
        player_rating, predicted = model.predict_points(
            features,
            group_index,
            group_league,
            weights,
            len(groups),
            position_index,
            prior_score,
        )
    group_result = groups[["_team_key", "league", "season", "n_players", "actual_points"]].copy()
    group_result["predicted_points"] = predicted.detach().cpu().numpy()
    group_result["split"] = split
    player_result = rows[["player", "team", "league", "season", "_group_index"]].copy()
    player_result["player_rating"] = player_rating.detach().cpu().numpy()
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
    truth_labels: pd.DataFrame | None = None,
) -> TeamPointsMLPResult:
    """Train a chronological MLP or Set Transformer proxy candidate.

    ``train_team_points_mlp`` remains the compatibility entry point; the
    architecture is selected by ``TeamPointsMLPConfig.architecture``.
    """

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
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(cfg.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
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
    fit_features, fit_index, fit_leagues, fit_weights, fit_positions, fit_prior, fit_rows = (
        _group_tensors(frame, fit_groups, encoder, league_levels)
    )
    fit_features = fit_features.to(device)
    fit_index = fit_index.to(device)
    fit_leagues = fit_leagues.to(device)
    fit_weights = fit_weights.to(device)
    fit_positions = fit_positions.to(device)
    fit_prior = fit_prior.to(device)
    fit_target = torch.from_numpy(fit_groups["actual_points"].to_numpy(dtype=np.float32)).to(device)
    input_dim = int(fit_features.shape[1])
    if input_dim == 0:
        return TeamPointsMLPResult(
            False, "skipped: no usable features", {}, pd.DataFrame(), pd.DataFrame(), [], []
        )

    model = _build_team_points_model(
        cfg,
        input_dim=input_dim,
        n_leagues=len(league_levels),
        n_positions=len(_POSITION_LEVELS),
        target_mean=float(fit_target.mean().cpu()),
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay
    )
    best_state: dict[str, Any] | None = None
    best_validation = float("inf")
    stale_epochs = 0
    history: list[dict[str, float | int]] = []
    (
        validation_features,
        validation_index,
        validation_leagues,
        validation_weights,
        validation_positions,
        validation_prior,
        _validation_rows,
    ) = _group_tensors(frame, validation_groups, encoder, league_levels)
    validation_features = validation_features.to(device)
    validation_index = validation_index.to(device)
    validation_leagues = validation_leagues.to(device)
    validation_weights = validation_weights.to(device)
    validation_positions = validation_positions.to(device)
    validation_prior = validation_prior.to(device)
    validation_target = torch.from_numpy(
        validation_groups["actual_points"].to_numpy(dtype=np.float32)
    ).to(device)
    truth_lookup = _truth_label_lookup(truth_labels)
    fit_truth = _truth_targets(fit_rows, truth_lookup)
    test_truth = _truth_targets(
        frame[frame["season"].astype(str).isin({str(value) for value in test_seasons})],
        truth_lookup,
    )
    truth_supervision_report: dict[str, Any] = {
        "total_rows": 0,
        "eligible_rows": 0,
        "proxy_rows": 0,
        "independent_rows": 0,
        "matched_fit_rows": int(np.isfinite(fit_truth).sum()),
        "matched_test_rows": int(np.isfinite(test_truth).sum()),
        "status": "no_truth_labels",
    }
    if truth_labels is not None:
        from scoutfootball.evaluation.truth_labels import truth_label_supervision_report

        truth_supervision_report = truth_label_supervision_report(truth_labels)
        truth_supervision_report["matched_fit_rows"] = int(np.isfinite(fit_truth).sum())
        truth_supervision_report["matched_test_rows"] = int(np.isfinite(test_truth).sum())
    fit_truth_mask = torch.from_numpy(np.isfinite(fit_truth)).to(device)
    fit_truth_values = torch.from_numpy(np.nan_to_num(fit_truth, nan=0.0)).to(device)

    for epoch in range(cfg.epochs):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        player_rating, predicted = model.predict_points(
            fit_features,
            fit_index,
            fit_leagues,
            fit_weights,
            len(fit_groups),
            fit_positions,
            fit_prior,
        )
        loss, loss_components = _composite_team_loss(
            predicted, fit_target, fit_groups["league"], cfg
        )
        position_loss = _position_consistency_loss(player_rating, fit_rows)
        truth_loss = torch.zeros((), dtype=loss.dtype)
        if int(fit_truth_mask.sum()) >= 5:
            truth_values = fit_truth_values[fit_truth_mask]
            truth_pred = player_rating[fit_truth_mask]
            pred_z = (truth_pred - truth_pred.mean()) / truth_pred.std(unbiased=False).clamp_min(
                1e-6
            )
            label_z = (truth_values - truth_values.mean()) / truth_values.std(
                unbiased=False
            ).clamp_min(1e-6)
            truth_loss = 0.55 * torch_functional.smooth_l1_loss(truth_pred, truth_values, beta=8.0)
            truth_loss = truth_loss + 0.45 * (1.0 - _corrcoef_torch(pred_z, label_z))
        prior_loss = model.position_offset.weight.square().mean()
        loss = (
            loss
            + cfg.position_consistency_weight * position_loss
            + cfg.truth_label_weight * truth_loss
            + cfg.prior_weight * prior_loss
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
                validation_positions,
                validation_prior,
            )
            validation_loss = float(
                _composite_team_loss(
                    validation_pred, validation_target, validation_groups["league"], cfg
                )[0].item()
            )
        history.append(
            {
                "epoch": epoch + 1,
                "train_loss": float(loss.item()),
                "validation_loss": validation_loss,
                **{f"train_{key}": value for key, value in loss_components.items()},
                "position_consistency": float(position_loss.detach().cpu()),
                "truth_anchor": float(truth_loss.detach().cpu()),
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
        "team_coverage": {
            "train": _team_coverage_summary(
                frame,
                team_points,
                seasons=set(train_seasons),
                min_team_players=cfg.min_team_players,
            ),
            "test": _team_coverage_summary(
                frame,
                team_points,
                seasons=test_seasons,
                min_team_players=cfg.min_team_players,
            ),
        },
        "fit": fit_metrics,
        "validation": validation_metrics,
        "train": train_metrics,
        "test": test_metrics,
        "epochs_completed": len(history),
        "best_validation_mse": best_validation,
        "architecture": cfg.architecture,
        "training_device": str(device),
        "cuda_device": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "target_semantics": "team-season points proxy; not independent player-ability truth",
        "truth_label_supervision": truth_supervision_report,
        "history": history,
    }
    return TeamPointsMLPResult(
        True,
        (
            f"ok: trained team-points {cfg.architecture} candidate "
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


def _write_training_curve_svg(path: Path, training_history: dict[str, Any]) -> None:
    """Write a small static diagnostic chart beside the model artifact.

    The chart is deliberately a training diagnostic, not an evaluation claim:
    holdout metrics remain in ``meta.json`` and the API response.
    """

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        history = training_history.get("history", [])
        epochs = [row.get("epoch") for row in history if isinstance(row, dict)]
        train_loss = [row.get("train_loss") for row in history if isinstance(row, dict)]
        validation_loss = [
            row.get("validation_loss") for row in history if isinstance(row, dict)
        ]
        soft_spearman = [
            row.get("train_soft_spearman") for row in history if isinstance(row, dict)
        ]
        if not epochs:
            path.write_text(
                "<svg xmlns='http://www.w3.org/2000/svg' width='640' height='320'></svg>",
                encoding="utf-8",
            )
            return

        fig, axes = plt.subplots(2, 1, figsize=(8.4, 5.4), constrained_layout=True)
        fig.suptitle(
            f"{training_history.get('architecture', 'neural')} training diagnostics",
            fontsize=11,
        )
        axes[0].plot(epochs, train_loss, label="train loss", color="#2563eb", linewidth=1.8)
        axes[0].plot(
            epochs,
            validation_loss,
            label="validation loss",
            color="#dc2626",
            linewidth=1.8,
        )
        axes[0].set_ylabel("composite loss")
        axes[0].legend(loc="best", frameon=False)
        axes[0].grid(alpha=0.22)
        axes[1].plot(
            epochs,
            soft_spearman,
            label="train soft Spearman",
            color="#059669",
            linewidth=1.8,
        )
        axes[1].set_xlabel("epoch")
        axes[1].set_ylabel("rank correlation")
        axes[1].set_ylim(-1.0, 1.0)
        axes[1].legend(loc="best", frameon=False)
        axes[1].grid(alpha=0.22)
        for axis in axes:
            axis.spines["top"].set_visible(False)
            axis.spines["right"].set_visible(False)
        fig.savefig(path, format="svg")
        plt.close(fig)
    except Exception:
        # The JSON history remains the authoritative artifact if plotting is
        # unavailable in a minimal environment.
        path.write_text(
            "<svg xmlns='http://www.w3.org/2000/svg' width='640' height='320'></svg>",
            encoding="utf-8",
        )


def _resolve_candidate_identity(
    candidate_ratings: pd.DataFrame,
    output_dir: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Attach the canonical identity contract to a candidate rating frame.

    Candidate training frames often carry a human-readable ``player`` name
    but not the source key used by the identity registry. Resolve through the
    same ``player_match`` view used by the API and keep explicit unresolved
    markers when the local registry has no confirmed mapping. A candidate
    without this block must not pass neural model admission.
    """

    from scoutfootball.evaluation.canonical_resolver import (
        load_resolved_player_ratings,
        resolution_summary,
        unresolved_canonical_id,
    )

    identity_input = candidate_ratings.drop(
        columns=[
            "player_id",
            "source_name",
            "canonical_player_id",
            "canonical_match_ambiguous",
        ],
        errors="ignore",
    )
    settings = None
    roots: list[Path] = []
    try:
        roots.append(output_dir.parents[3])
    except IndexError:
        pass
    roots.append(Path.cwd())
    for root in roots:
        try:
            from scoutfootball.config import PlatformSettings

            possible = PlatformSettings.from_root(root)
            if (possible.gold_root / "feature_store" / "player_match.parquet").is_file():
                settings = possible
                break
        except (OSError, IndexError, TypeError, ValueError):
            continue

    try:
        if settings is None:
            raise ValueError("player_match.parquet unavailable for candidate identity")
        resolved = load_resolved_player_ratings(settings=settings, ratings_df=identity_input)
        if len(resolved) != len(candidate_ratings):
            raise ValueError(
                "candidate identity resolver changed row count "
                f"({len(candidate_ratings)} -> {len(resolved)})"
            )
        identity_columns = [
            "player_id",
            "source_name",
            "canonical_player_id",
            "canonical_match_ambiguous",
        ]
        missing = [column for column in identity_columns if column not in resolved.columns]
        if missing:
            raise ValueError(f"candidate identity columns missing after resolution: {missing}")
        output = candidate_ratings.copy()
        for column in identity_columns:
            output[column] = resolved[column].to_numpy()
        summary = resolution_summary(output)
        return output, {
            "schema": "scoutfootball.canonical-resolver",
            "version": "1.0.0",
            "status": "ok",
            "canonical_column": "canonical_player_id",
            "unresolved_prefix": "unresolved:",
            "summary": summary,
        }
    except Exception as exc:  # candidate generation must remain honest, not crash silently
        output = candidate_ratings.copy()
        output["player_id"] = pd.Series(pd.NA, index=output.index, dtype="string")
        output["source_name"] = pd.Series(pd.NA, index=output.index, dtype="string")
        output["canonical_player_id"] = unresolved_canonical_id("unknown", "missing")
        output["canonical_match_ambiguous"] = False
        return output, {
            "schema": "scoutfootball.canonical-resolver",
            "version": "1.0.0",
            "status": "unavailable",
            "canonical_column": "canonical_player_id",
            "unresolved_prefix": "unresolved:",
            "summary": resolution_summary(output),
            "error": f"{type(exc).__name__}: {exc}",
        }


def write_team_points_mlp_artifacts(
    result: TeamPointsMLPResult,
    output_dir: Path,
    *,
    config: TeamPointsMLPConfig,
    input_frame: pd.DataFrame | None = None,
) -> None:
    """Write candidate-only artifacts with explicit proxy-target semantics."""

    output_dir.mkdir(parents=True, exist_ok=True)
    history = result.metrics.get("history", []) if isinstance(result.metrics, dict) else []
    if not isinstance(history, list):
        history = []
    training_history = {
        "run_id": output_dir.name,
        "model_type": (
            "team_points_set_transformer"
            if config.architecture == "set_transformer"
            else "team_points_mlp"
        ),
        "architecture": config.architecture,
        "training_device": result.metrics.get("training_device"),
        "cuda_device": result.metrics.get("cuda_device"),
        "train_seasons": result.metrics.get("train_seasons", []),
        "validation_seasons": result.metrics.get("validation_seasons", []),
        "test_seasons": result.metrics.get("test_seasons", []),
        "epochs_requested": config.epochs,
        "epochs_completed": result.metrics.get("epochs_completed", len(history)),
        "best_validation_loss": result.metrics.get("best_validation_mse"),
        "test": result.metrics.get("test", {}),
        "target_semantics": result.metrics.get(
            "target_semantics",
            "team-season points proxy; not independent player-ability truth",
        ),
        "truth_label_supervision": result.metrics.get("truth_label_supervision", {}),
        "history": history,
    }
    (output_dir / "training_history.json").write_text(
        json.dumps(training_history, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _write_training_curve_svg(output_dir / "training_curves.svg", training_history)
    candidate_ratings: pd.DataFrame | None = None
    identity_resolution: dict[str, Any] = {
        "schema": "scoutfootball.canonical-resolver",
        "version": "1.0.0",
        "status": "unavailable",
        "canonical_column": "canonical_player_id",
        "unresolved_prefix": "unresolved:",
        "summary": {"status": "unavailable", "evidence": {"reason": "no candidate ratings"}},
    }
    if input_frame is not None and not result.player_predictions.empty:
        keys = ["player", "team", "league", "season"]
        missing = sorted(set(keys) - set(input_frame.columns))
        if missing:
            raise ValueError(f"input frame is missing candidate identity columns: {missing}")
        predictions = result.player_predictions.copy()
        if predictions.duplicated(keys).any():
            raise ValueError("neural player predictions contain duplicate rating identities")
        source = input_frame.copy()
        source["season"] = source["season"].astype(str)
        predictions["season"] = predictions["season"].astype(str)
        candidate_ratings = predictions.merge(
            source,
            on=keys,
            how="left",
            validate="one_to_one",
            suffixes=("", "_input"),
            sort=False,
        )
        if len(candidate_ratings) != len(predictions):
            raise ValueError("some neural predictions could not be mapped to input identities")
        candidate_ratings["sub_position"] = (
            candidate_ratings.get("sub_position", pd.Series(index=candidate_ratings.index))
            .fillna("UNK")
            .astype(str)
        )
        candidate_ratings["minutes"] = pd.to_numeric(
            candidate_ratings.get("minutes", 0.0), errors="coerce"
        ).fillna(0.0)
        candidate_ratings["optimized_score"] = pd.to_numeric(
            candidate_ratings["player_rating"], errors="coerce"
        )
        if not np.isfinite(candidate_ratings["optimized_score"].to_numpy(dtype=float)).all():
            raise ValueError("neural predictions contain non-finite candidate scores")
        candidate_ratings["same_position_score"] = (
            candidate_ratings.groupby(["sub_position", "season"], observed=True)[
                "optimized_score"
            ].rank(pct=True)
            * 100.0
        )
        candidate_ratings = candidate_ratings.drop(columns=["_group_index"], errors="ignore")
        candidate_ratings, identity_resolution = _resolve_candidate_identity(
            candidate_ratings, output_dir
        )
        candidate_ratings.to_parquet(output_dir / "player_ratings_candidate.parquet", index=False)
    metrics = {
        "trained": result.trained,
        "status": result.status,
        "metrics": result.metrics,
        "config": asdict(config),
        "feature_columns": result.feature_columns,
        "category_columns": result.category_columns,
        "activation": {
            "status": "not_activated",
            "reason": "candidate requires explicit scoped review and local promotion",
        },
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
        "optimizer_prior_artifact": (
            input_frame.attrs.get("optimizer_prior_artifact") if input_frame is not None else None
        ),
        "input_sources": (
            {
                "fbref_standard": input_frame.attrs.get("fbref_standard_path"),
                "optimizer_artifact_statuses": input_frame.attrs.get(
                    "optimizer_artifact_statuses", []
                ),
            }
            if input_frame is not None
            else {}
        ),
        "target_semantics": "team-season points proxy; not independent player-ability truth",
    }
    (output_dir / "feature_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Keep the candidate visible to the existing read-only model registry.
    # This is a candidate model-run record, not an automatic activation record.
    # Admission can verify the proxy holdout and rating artifact, but it must
    # not turn proxy supervision into independent player-ability truth.
    feature_store_manifest: Path | None = None
    for parent in output_dir.parents:
        possible_manifest = (
            parent / "gold" / "feature_store" / "rating_feature_matrix_manifest.json"
        )
        if possible_manifest.is_file():
            feature_store_manifest = possible_manifest
            break
    recorded_feature_manifest: dict[str, Any] = {
        "path": "gold/feature_store/rating_feature_matrix_manifest.json",
        "hash": None,
        "schema_version": None,
    }
    if feature_store_manifest is not None:
        try:
            current = json.loads(feature_store_manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
        if isinstance(current, dict):
            # Admission compares the training snapshot with the exact
            # on-disk manifest bytes. The manifest's internal ``hash`` is the
            # feature-data hash, not the manifest-file hash, so store both and
            # use the file hash for the chain-of-custody field.
            manifest_hash = hashlib.sha256(feature_store_manifest.read_bytes()).hexdigest()[:16]
            recorded_feature_manifest.update(
                {
                    "hash": manifest_hash,
                    "content_hash": current.get("hash"),
                    "schema_version": current.get("schema_version"),
                    "generated_at": current.get("generated_at"),
                    "input_hash": current.get("input_hash"),
                }
            )
    run_id = output_dir.name
    candidate_artifacts: dict[str, Any] = {
        "model": {
            "path": "model_state.pt",
            "scope": "unactivated_local_candidate",
            "sha256": (
                hashlib.sha256((output_dir / "model_state.pt").read_bytes()).hexdigest()
                if (output_dir / "model_state.pt").is_file()
                else None
            ),
        },
        "team_predictions": {
            "path": "team_predictions.parquet",
            "scope": "proxy_target_evaluation",
        },
        "player_predictions": {
            "path": "player_predictions.parquet",
            "scope": "proxy_target_evaluation",
        },
        "training_history": {
            "path": "training_history.json",
            "rows": len(history),
            "scope": "training_diagnostics",
        },
        "training_chart": {
            "path": "training_curves.svg",
            "scope": "training_diagnostics",
        },
        "identity": identity_resolution,
    }
    if candidate_ratings is not None:
        ratings_path = output_dir / "player_ratings_candidate.parquet"
        candidate_artifacts["ratings"] = {
            "path": ratings_path.name,
            "sha256": hashlib.sha256(ratings_path.read_bytes()).hexdigest(),
            "rows": len(candidate_ratings),
            "columns": list(candidate_ratings.columns),
            "scope": "unactivated_local_candidate",
        }
    run_meta = {
        "timestamp": run_id,
        "run_id": run_id,
        "model_type": (
            "team_points_set_transformer"
            if config.architecture == "set_transformer"
            else "team_points_mlp"
        ),
        "architecture": config.architecture,
        "input_hash": manifest["input_sha256"],
        "metrics": result.metrics,
        "train_seasons": result.metrics.get("train_seasons", []),
        "test_seasons": result.metrics.get("test_seasons", []),
        "lineage": {
            "schema": "scoutfootball.model-run-lineage",
            "version": "1.0.0",
            "status": "recorded",
            "dataset_snapshot": {"input_hash": manifest["input_sha256"]},
            "feature_manifest": recorded_feature_manifest,
        },
        "activation": metrics["activation"],
        "candidate_artifacts": candidate_artifacts,
        "args": asdict(config),
        "target_semantics": metrics["target_semantics"],
        "optimizer_prior_artifact": manifest["optimizer_prior_artifact"],
        "identity_resolution": identity_resolution,
    }
    (output_dir / "meta.json").write_text(
        json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# Public compatibility names: older callers can keep importing the MLP entry
# point, while new callers can make the architecture explicit.
train_team_points_set_transformer = train_team_points_mlp
write_team_points_set_transformer_artifacts = write_team_points_mlp_artifacts

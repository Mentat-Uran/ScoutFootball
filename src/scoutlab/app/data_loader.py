"""Unified data loader: reads local Parquet when available, falls back to demo data."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from scoutlab.config import PlatformSettings


def _settings() -> PlatformSettings:
    return PlatformSettings.from_root()


def _parquet_path(relative_path: str):
    return _settings().data_root / relative_path


def _parquet_exists(relative_path: str) -> bool:
    path = _parquet_path(relative_path)
    return path.exists() and path.suffix == ".parquet"


def load_player_match() -> pd.DataFrame:
    rel = "gold/feature_store/player_match.parquet"
    if _parquet_exists(rel):
        return pd.read_parquet(_parquet_path(rel))
    from scoutlab.app.demo_data import generate_player_match

    return generate_player_match()


def load_team_match() -> pd.DataFrame:
    rel = "gold/feature_store/team_match.parquet"
    if _parquet_exists(rel):
        return pd.read_parquet(_parquet_path(rel))
    from scoutlab.app.demo_data import generate_team_match

    return generate_team_match()


@lru_cache(maxsize=2)
def load_player_rolling() -> pd.DataFrame:
    rel = "gold/feature_store/player_rolling.parquet"
    if _parquet_exists(rel):
        return pd.read_parquet(_parquet_path(rel))
    from scoutlab.app.demo_data import generate_player_match, generate_player_rolling

    return generate_player_rolling(generate_player_match())


@lru_cache(maxsize=2)
def load_team_rolling() -> pd.DataFrame:
    rel = "gold/feature_store/team_rolling.parquet"
    if _parquet_exists(rel):
        return pd.read_parquet(_parquet_path(rel))
    from scoutlab.app.demo_data import generate_team_match, generate_team_rolling

    return generate_team_rolling(generate_team_match())


def load_oof_predictions() -> pd.DataFrame:
    rel = "models/oof_predictions/value_fairness_oof.parquet"
    if _parquet_exists(rel):
        return pd.read_parquet(_parquet_path(rel))
    from scoutlab.app.demo_data import generate_oof_predictions

    return generate_oof_predictions()


def load_score_prediction():
    if _parquet_exists("models/artifacts/poisson_model.parquet"):
        from scoutlab.models.match_prediction import (
            fit_independent_poisson,
            predict_match,
        )

        team_match = load_team_match()
        model = fit_independent_poisson(team_match)
        return predict_match(model, "t_1", "t_2")
    from scoutlab.app.demo_data import generate_score_matrix

    return generate_score_matrix()


def data_source_label() -> str:
    if _parquet_exists("gold/feature_store/player_match.parquet"):
        return "Local Parquet data"
    return "Demo data (synthetic)"

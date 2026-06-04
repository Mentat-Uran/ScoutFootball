"""Synthetic demo data generator for Streamlit pages without real Parquet data."""

from __future__ import annotations

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

POSITION_GROUPS = ("GK", "DEF", "MID", "FWD")
LEAGUES = ("Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1")
TEAM_NAMES = (
    "Arsenal",
    "Chelsea",
    "Liverpool",
    "Man City",
    "Man United",
    "Barcelona",
    "Real Madrid",
    "Atletico Madrid",
    "Bayern Munich",
    "Dortmund",
    "Juventus",
    "Inter Milan",
    "AC Milan",
    "Napoli",
    "PSG",
    "Lyon",
    "Marseille",
)
PLAYER_NAMES = (
    "Player A",
    "Player B",
    "Player C",
    "Player D",
    "Player E",
    "Player F",
    "Player G",
    "Player H",
    "Player I",
    "Player J",
    "Player K",
    "Player L",
    "Player M",
    "Player N",
    "Player O",
    "Player P",
    "Player Q",
    "Player R",
    "Player S",
    "Player T",
)


def generate_player_match(n_rows: int = 500) -> pd.DataFrame:
    dates = pd.date_range("2024-08-01", "2025-05-31", freq="3D")
    rows = []
    for _ in range(n_rows):
        pos = rng.choice(POSITION_GROUPS)
        minutes = int(rng.exponential(50))
        rows.append(
            {
                "match_id": f"m_{rng.integers(1, 200)}",
                "match_date": rng.choice(dates),
                "player_id": f"p_{rng.integers(1, 21)}",
                "player_name": rng.choice(PLAYER_NAMES),
                "team_id": f"t_{rng.integers(1, 18)}",
                "team_name": rng.choice(TEAM_NAMES),
                "opponent_team_id": f"t_{rng.integers(1, 18)}",
                "is_home": bool(rng.integers(0, 2)),
                "minutes_played": min(minutes, 120),
                "position_group": pos,
                "league": rng.choice(LEAGUES),
                "goals": int(rng.poisson(0.12)),
                "assists": int(rng.poisson(0.1)),
                "shots": int(rng.poisson(1.5)),
                "shots_on_target": int(rng.poisson(0.6)),
                "npxg": float(rng.exponential(0.15)),
                "xa": float(rng.exponential(0.1)),
                "tackles": int(rng.poisson(1.2)),
                "passes": int(rng.poisson(30)),
                "xT_added": float(rng.exponential(0.05)),
            }
        )
    return pd.DataFrame(rows)


def generate_team_match(n_rows: int = 300) -> pd.DataFrame:
    dates = pd.date_range("2024-08-01", "2025-05-31", freq="3D")
    rows = []
    for _ in range(n_rows):
        rows.append(
            {
                "match_id": f"m_{rng.integers(1, 200)}",
                "match_date": rng.choice(dates),
                "team_id": f"t_{rng.integers(1, 18)}",
                "team_name": rng.choice(TEAM_NAMES),
                "opponent_team_id": f"t_{rng.integers(1, 18)}",
                "is_home": bool(rng.integers(0, 2)),
                "goals_for": int(rng.poisson(1.3)),
                "goals_against": int(rng.poisson(1.1)),
                "result_points": int(rng.choice([0, 1, 3], p=[0.3, 0.25, 0.45])),
                "shots": int(rng.poisson(12)),
                "shots_on_target": int(rng.poisson(5)),
                "xg": float(rng.exponential(1.2)),
                "xg_against": float(rng.exponential(1.0)),
                "elo_pre": float(rng.normal(1500, 200)),
            }
        )
    return pd.DataFrame(rows)


def generate_player_rolling(player_match_df: pd.DataFrame) -> pd.DataFrame:
    from scoutlab.features.player_rolling import build_player_rolling_features

    return build_player_rolling_features(player_match_df, windows=[5, 10, 20])


def generate_team_rolling(team_match_df: pd.DataFrame) -> pd.DataFrame:
    from scoutlab.features.team_rolling import build_team_rolling_features

    return build_team_rolling_features(team_match_df, windows=[5, 10, 20])


def generate_oof_predictions(n_rows: int = 300) -> pd.DataFrame:
    rows = []
    for _ in range(n_rows):
        actual_log = float(rng.normal(15, 1.5))
        residual = float(rng.normal(0, 0.3))
        predicted_log = actual_log - residual
        rows.append(
            {
                "player_id": f"p_{rng.integers(1, 21)}",
                "player_name": rng.choice(PLAYER_NAMES),
                "snapshot_date": pd.Timestamp("2025-01-15"),
                "actual_market_value": float(np.expm1(actual_log)),
                "actual_market_value_log": actual_log,
                "predicted_market_value_log": predicted_log,
                "predicted_market_value": float(np.expm1(predicted_log)),
                "residual_log": residual,
                "fairness_label": rng.choice(["cheap", "fair", "expensive"], p=[0.2, 0.6, 0.2]),
            }
        )
    return pd.DataFrame(rows)


def generate_score_matrix() -> pd.DataFrame:
    from scoutlab.models.match_prediction import fit_independent_poisson, predict_match

    team_match = generate_team_match(300)
    model = fit_independent_poisson(team_match)
    return predict_match(model, "t_1", "t_2")

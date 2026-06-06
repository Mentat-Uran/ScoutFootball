"""Independent Poisson baseline for match prediction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import poisson


@dataclass(frozen=True)
class IndependentPoissonModel:
    """Independent Poisson parameters estimated from historical team-match data."""

    league_home_rate: float
    league_away_rate: float
    home_attack_strength: dict[str, float]
    away_attack_strength: dict[str, float]
    home_defense_strength: dict[str, float]
    away_defense_strength: dict[str, float]
    smoothing: float


@dataclass(frozen=True)
class MatchProbabilitySummary:
    """Aggregated market-style probabilities from one exact-score matrix."""

    home_win: float
    draw: float
    away_win: float
    over_2_5: float
    under_2_5: float
    btts_yes: float
    btts_no: float


@dataclass(frozen=True)
class PoissonPrediction:
    """Exact-score matrix plus expected goals and derived market summaries."""

    home_lambda: float
    away_lambda: float
    score_matrix: pd.DataFrame
    summary: MatchProbabilitySummary


def fit_independent_poisson(
    team_match_df: pd.DataFrame,
    *,
    smoothing: float = 1.0,
) -> IndependentPoissonModel:
    """Fit a simple attack-defense Poisson baseline from team-match rows."""

    required = {"team_id", "is_home", "goals_for", "goals_against"}
    missing = sorted(required.difference(team_match_df.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"team_match_df is missing required columns: {missing_text}")

    prepared = team_match_df.copy()
    prepared["is_home"] = prepared["is_home"].astype(bool)
    home_rows = prepared.loc[prepared["is_home"]].copy()
    away_rows = prepared.loc[~prepared["is_home"]].copy()
    if home_rows.empty or away_rows.empty:
        raise ValueError("team_match_df must include both home and away rows")

    league_home_rate = float(pd.to_numeric(home_rows["goals_for"], errors="raise").mean())
    league_away_rate = float(pd.to_numeric(away_rows["goals_for"], errors="raise").mean())

    home_attack = _fit_strength_lookup(
        home_rows,
        team_column="team_id",
        value_column="goals_for",
        baseline_rate=league_home_rate,
        smoothing=smoothing,
    )
    away_attack = _fit_strength_lookup(
        away_rows,
        team_column="team_id",
        value_column="goals_for",
        baseline_rate=league_away_rate,
        smoothing=smoothing,
    )
    home_defense = _fit_strength_lookup(
        home_rows,
        team_column="team_id",
        value_column="goals_against",
        baseline_rate=league_away_rate,
        smoothing=smoothing,
    )
    away_defense = _fit_strength_lookup(
        away_rows,
        team_column="team_id",
        value_column="goals_against",
        baseline_rate=league_home_rate,
        smoothing=smoothing,
    )

    return IndependentPoissonModel(
        league_home_rate=league_home_rate,
        league_away_rate=league_away_rate,
        home_attack_strength=home_attack,
        away_attack_strength=away_attack,
        home_defense_strength=home_defense,
        away_defense_strength=away_defense,
        smoothing=smoothing,
    )


def predict_match(
    model: IndependentPoissonModel,
    home_team_id: str,
    away_team_id: str,
    *,
    max_goals: int = 10,
) -> PoissonPrediction:
    """Predict an exact-score matrix for one fixture."""

    if max_goals <= 0:
        raise ValueError("max_goals must be positive")

    home_lambda = _expected_goals(
        league_rate=model.league_home_rate,
        attack_lookup=model.home_attack_strength,
        defense_lookup=model.away_defense_strength,
        attack_team_id=home_team_id,
        defense_team_id=away_team_id,
    )
    away_lambda = _expected_goals(
        league_rate=model.league_away_rate,
        attack_lookup=model.away_attack_strength,
        defense_lookup=model.home_defense_strength,
        attack_team_id=away_team_id,
        defense_team_id=home_team_id,
    )

    home_probs = poisson.pmf(np.arange(max_goals + 1), home_lambda)
    away_probs = poisson.pmf(np.arange(max_goals + 1), away_lambda)
    matrix = np.outer(home_probs, away_probs)
    matrix = matrix / matrix.sum()
    score_matrix = pd.DataFrame(
        matrix,
        index=pd.Index(range(max_goals + 1), name="home_goals"),
        columns=pd.Index(range(max_goals + 1), name="away_goals"),
    )
    summary = _summarize_score_matrix(score_matrix)
    return PoissonPrediction(
        home_lambda=home_lambda,
        away_lambda=away_lambda,
        score_matrix=score_matrix,
        summary=summary,
    )


def fit_dixon_coles_placeholder(*args: object, **kwargs: object) -> None:
    """Explicit placeholder for the later Dixon-Coles extension."""

    del args, kwargs
    raise NotImplementedError(
        "Dixon-Coles is intentionally not implemented in this first Phase 8 slice.",
    )


def _fit_strength_lookup(
    frame: pd.DataFrame,
    *,
    team_column: str,
    value_column: str,
    baseline_rate: float,
    smoothing: float,
) -> dict[str, float]:
    grouped = frame.groupby(team_column, dropna=False)[value_column].agg(["sum", "count"])
    strengths: dict[str, float] = {}
    for team_id, row in grouped.iterrows():
        smoothed_mean = (row["sum"] + smoothing * baseline_rate) / (row["count"] + smoothing)
        strengths[str(team_id)] = float(smoothed_mean / baseline_rate) if baseline_rate > 0 else 1.0
    return strengths


def _expected_goals(
    *,
    league_rate: float,
    attack_lookup: dict[str, float],
    defense_lookup: dict[str, float],
    attack_team_id: str,
    defense_team_id: str,
) -> float:
    attack_strength = attack_lookup.get(str(attack_team_id), 1.0)
    defense_strength = defense_lookup.get(str(defense_team_id), 1.0)
    return float(league_rate * attack_strength * defense_strength)


def _summarize_score_matrix(score_matrix: pd.DataFrame) -> MatchProbabilitySummary:
    matrix = score_matrix.to_numpy()
    home_win = float(np.tril(matrix, k=-1).sum())
    draw = float(np.trace(matrix))
    away_win = float(np.triu(matrix, k=1).sum())

    home_goals = np.arange(score_matrix.shape[0])[:, None]
    away_goals = np.arange(score_matrix.shape[1])[None, :]
    total_goals = home_goals + away_goals
    over_2_5 = float(matrix[total_goals > 2].sum())
    under_2_5 = float(matrix[total_goals <= 2].sum())
    btts_yes = float(matrix[(home_goals > 0) & (away_goals > 0)].sum())
    btts_no = 1.0 - btts_yes

    return MatchProbabilitySummary(
        home_win=home_win,
        draw=draw,
        away_win=away_win,
        over_2_5=over_2_5,
        under_2_5=under_2_5,
        btts_yes=btts_yes,
        btts_no=btts_no,
    )

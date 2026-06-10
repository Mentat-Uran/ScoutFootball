"""Match prediction models: Independent Poisson baseline and Dixon-Coles extension."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

logger = logging.getLogger(__name__)


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
class DixonColesModel:
    """Dixon-Coles (1997) bivariate Poisson model with low-score correction.

    Extends Independent Poisson by estimating a rho parameter that corrects
    for the correlation between home and away goals in low-scoring matches.
    """

    team_attack: dict[str, float]
    team_defense: dict[str, float]
    home_advantage: float
    rho: float
    league_mean_goals: float
    num_matches: int
    half_life_days: float | None = None


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


def fit_dixon_coles(
    team_match_df: pd.DataFrame,
    *,
    maxiter: int = 500,
    half_life_days: float | None = None,
) -> DixonColesModel:
    """Fit a Dixon-Coles (1997) model via maximum likelihood estimation.

    Parameters
    ----------
    team_match_df : DataFrame with columns: team_id, is_home, goals_for, goals_against
    maxiter : Maximum optimizer iterations.
    half_life_days : If set, apply exponential time decay weighting. Each match
        is weighted by 0.5 ** (days_since_most_recent / half_life_days).

    Returns
    -------
    DixonColesModel with fitted attack/defense parameters, home advantage, and rho.
    """
    required = {"team_id", "is_home", "goals_for", "goals_against"}
    missing = sorted(required.difference(team_match_df.columns))
    if missing:
        raise ValueError(f"team_match_df is missing required columns: {', '.join(missing)}")

    df = team_match_df.copy()
    df["is_home"] = df["is_home"].astype(bool)
    df["goals_for"] = pd.to_numeric(df["goals_for"], errors="raise")
    df["goals_against"] = pd.to_numeric(df["goals_against"], errors="raise")

    home_df = df[df["is_home"]].copy()
    away_df = df[~df["is_home"]].copy()
    if home_df.empty or away_df.empty:
        raise ValueError("team_match_df must include both home and away rows")

    # Build match pairs: home_goals, away_goals per match
    matches_merged = home_df.merge(
        away_df,
        on="match_id",
        suffixes=("_home", "_away"),
    )
    if matches_merged.empty:
        raise ValueError("No complete home-away match pairs found")

    # Compute time decay weights if requested
    decay_weights = np.ones(len(matches_merged))
    if half_life_days is not None and "match_date_home" in matches_merged.columns:
        dates = pd.to_datetime(matches_merged["match_date_home"], errors="coerce")
        most_recent = dates.max()
        days_since = (most_recent - dates).dt.days.to_numpy(dtype=float)
        decay_weights = 0.5 ** (days_since / half_life_days)

    teams = sorted(df["team_id"].dropna().astype(str).unique())
    n_teams = len(teams)
    team_idx = {t: i for i, t in enumerate(teams)}

    hg = matches_merged["goals_for_home"].to_numpy(dtype=float)
    ag = matches_merged["goals_for_away"].to_numpy(dtype=float)
    home_team_ids = matches_merged["team_id_home"].astype(str).values
    away_team_ids = matches_merged["team_id_away"].astype(str).values

    home_indices = np.array([team_idx[t] for t in home_team_ids])
    away_indices = np.array([team_idx[t] for t in away_team_ids])

    league_mean = float(df["goals_for"].mean())
    if league_mean <= 0:
        league_mean = 1.3  # reasonable default

    # Parameter vector: [attack_0..n-1, defense_0..n-1, home_adv, rho]
    # Skip one attack parameter for identifiability (set attack[0] = 0)
    n_params = 2 * n_teams - 1 + 2  # -1 for identifiability + home_adv + rho

    def _unpack(params: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
        attack = np.zeros(n_teams)
        attack[1:] = params[: n_teams - 1]
        defense = params[n_teams - 1 : 2 * n_teams - 1]
        home_adv = params[2 * n_teams - 1]
        rho = params[2 * n_teams]
        return attack, defense, home_adv, rho

    def _neg_log_likelihood(params: np.ndarray) -> float:
        attack, defense, home_adv, rho = _unpack(params)

        log_lam_home = np.log(league_mean) + attack[home_indices] + defense[away_indices] + home_adv
        log_lam_away = np.log(league_mean) + attack[away_indices] + defense[home_indices]
        lam_home = np.exp(np.clip(log_lam_home, -10, 3))
        lam_away = np.exp(np.clip(log_lam_away, -10, 3))

        # Poisson log-likelihood
        ll = poisson.logpmf(hg.astype(int), lam_home) + poisson.logpmf(ag.astype(int), lam_away)

        # Dixon-Coles tau correction for low scores
        ll += _dc_log_tau(hg, ag, lam_home, lam_away, rho)

        return -float(np.sum(ll * decay_weights))

    # Initial guess: small random perturbation around zero
    rng = np.random.default_rng(42)
    x0 = rng.normal(0, 0.01, n_params)
    # home_adv around 0.25, rho around -0.13
    x0[2 * n_teams - 1] = 0.25
    x0[2 * n_teams] = -0.13

    # Bounds: rho in [-1, 0], others unbounded
    bounds = [(None, None)] * (2 * n_teams - 1) + [(None, None), (-1.0, 0.0)]

    result = minimize(
        _neg_log_likelihood,
        x0,
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": maxiter, "ftol": 1e-10},
    )

    attack, defense, home_adv, rho = _unpack(result.x)

    # Normalize: mean attack = 0, mean defense = 0
    attack = attack - attack.mean()
    defense = defense - defense.mean()

    team_attack = {teams[i]: float(attack[i]) for i in range(n_teams)}
    team_defense = {teams[i]: float(defense[i]) for i in range(n_teams)}

    logger.info(
        "Dixon-Coles fit: %d teams, %d matches, NLL=%.2f, rho=%.4f, home_adv=%.4f",
        n_teams,
        len(hg),
        result.fun,
        rho,
        home_adv,
    )

    return DixonColesModel(
        team_attack=team_attack,
        team_defense=team_defense,
        home_advantage=float(home_adv),
        rho=float(rho),
        league_mean_goals=league_mean,
        num_matches=len(hg),
        half_life_days=half_life_days,
    )


def predict_match_dc(
    model: DixonColesModel,
    home_team_id: str,
    away_team_id: str,
    *,
    max_goals: int = 10,
) -> PoissonPrediction:
    """Predict an exact-score matrix using Dixon-Coles tau correction."""
    if max_goals <= 0:
        raise ValueError("max_goals must be positive")

    home_attack = model.team_attack.get(str(home_team_id), 0.0)
    home_defense = model.team_defense.get(str(home_team_id), 0.0)
    away_attack = model.team_attack.get(str(away_team_id), 0.0)
    away_defense = model.team_defense.get(str(away_team_id), 0.0)

    log_lam_home = (
        np.log(model.league_mean_goals) + home_attack + away_defense + model.home_advantage
    )
    log_lam_away = np.log(model.league_mean_goals) + away_attack + home_defense
    home_lambda = float(np.exp(np.clip(log_lam_home, -10, 3)))
    away_lambda = float(np.exp(np.clip(log_lam_away, -10, 3)))

    goals = np.arange(max_goals + 1)
    home_probs = poisson.pmf(goals, home_lambda)
    away_probs = poisson.pmf(goals, away_lambda)

    # Independent Poisson base matrix
    matrix = np.outer(home_probs, away_probs)

    # Apply Dixon-Coles tau correction for low scores
    rho = model.rho
    for i in range(min(2, max_goals + 1)):
        for j in range(min(2, max_goals + 1)):
            tau = _dc_tau_scalar(i, j, home_lambda, away_lambda, rho)
            matrix[i, j] *= tau

    total = matrix.sum()
    if total > 0:
        matrix /= total
    else:
        logger.warning(
            "Score matrix sum is zero after tau correction; returning unnormalized matrix"
        )

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


def _dc_tau_scalar(x: float, y: float, lam_h: float, lam_a: float, rho: float) -> float:
    """Dixon-Coles tau correction factor for a single (x, y) score pair."""
    x, y = int(x), int(y)
    if x == 0 and y == 0:
        return max(1.0 - lam_h * lam_a * rho, 1e-12)
    if x == 1 and y == 0:
        return max(1.0 + lam_h * rho, 1e-12)
    if x == 0 and y == 1:
        return max(1.0 + lam_a * rho, 1e-12)
    if x == 1 and y == 1:
        return max(1.0 - rho, 1e-12)
    return 1.0


def _dc_log_tau(
    hg: np.ndarray,
    ag: np.ndarray,
    lam_home: np.ndarray,
    lam_away: np.ndarray,
    rho: float,
) -> np.ndarray:
    """Dixon-Coles log-tau correction vectorized over matches."""
    log_tau = np.zeros_like(lam_home)

    mask_00 = (hg == 0) & (ag == 0)
    if mask_00.any():
        val = 1.0 - lam_home[mask_00] * lam_away[mask_00] * rho
        log_tau[mask_00] = np.log(np.clip(val, 1e-12, None))

    mask_10 = (hg == 1) & (ag == 0)
    if mask_10.any():
        val = 1.0 + lam_home[mask_10] * rho
        log_tau[mask_10] = np.log(np.clip(val, 1e-12, None))

    mask_01 = (hg == 0) & (ag == 1)
    if mask_01.any():
        val = 1.0 + lam_away[mask_01] * rho
        log_tau[mask_01] = np.log(np.clip(val, 1e-12, None))

    mask_11 = (hg == 1) & (ag == 1)
    if mask_11.any():
        val = 1.0 - rho
        log_tau[mask_11] = np.log(max(val, 1e-12))

    return log_tau


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

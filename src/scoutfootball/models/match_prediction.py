"""Match prediction models: Independent Poisson baseline and Dixon-Coles extension."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

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
    decay: float | None = None


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
    decay: float | None = None,
    match_weights: np.ndarray | None = None,
) -> DixonColesModel:
    """Fit a Dixon-Coles (1997) model via maximum likelihood estimation.

    Parameters
    ----------
    team_match_df : DataFrame with columns: team_id, is_home, goals_for, goals_against
    maxiter : Maximum optimizer iterations.
    half_life_days : If set, apply exponential time decay weighting. Each match
        is weighted by 0.5 ** (days_since_most_recent / half_life_days).
        Ignored if ``decay`` is also provided.
    decay : If set, apply exponential time decay weighting. Each match is
        weighted by exp(-decay * days_since_match_i). The Dixon-Coles (1997)
        paper recommends decay ≈ 0.005. Takes precedence over ``half_life_days``.
    match_weights : Optional per-match weights (aligned to the merged
        home-away match pairs). When provided, these multiply the time-decay
        weights. Useful for form-based or confidence-based weighting.

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
    effective_decay: float | None = None
    if "match_date_home" in matches_merged.columns:
        dates = pd.to_datetime(matches_merged["match_date_home"], errors="coerce")
        most_recent = dates.max()
        days_since = (most_recent - dates).dt.days.to_numpy(dtype=float)
        if decay is not None:
            # Dixon-Coles paper: w_i = exp(-decay * days_since)
            decay_weights = np.exp(-decay * days_since)
            effective_decay = decay
        elif half_life_days is not None:
            # Alternative: half-life formulation
            decay_weights = 0.5 ** (days_since / half_life_days)
            effective_decay = float(np.log(2) / half_life_days)

    # Apply optional per-match weights (e.g. form-based) on top of decay
    if match_weights is not None:
        if len(match_weights) != len(decay_weights):
            raise ValueError(
                f"match_weights length {len(match_weights)} does not match "
                f"number of fixtures {len(decay_weights)}"
            )
        decay_weights = decay_weights * np.asarray(match_weights, dtype=float)

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
        half_life_days=half_life_days if decay is None else None,
        decay=effective_decay,
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


@dataclass(frozen=True)
class CalibrationReport:
    """Calibration report for Dixon-Coles 1x2 probability predictions."""

    method: str
    brier_before: float
    brier_after: float
    rps_before: float
    rps_after: float
    n_matches: int
    calibrated_predictions: pd.DataFrame | None = None


def calibrate_predictions(
    predictions: pd.DataFrame,
    *,
    method: str = "isotonic",
) -> CalibrationReport:
    """Calibrate 1x2 (home/draw/away) probabilities using isotonic regression or Platt scaling.

    Parameters
    ----------
    predictions : DataFrame with columns: home_win_probability, draw_probability,
        away_win_probability, actual_outcome.
    method : "isotonic" or "platt".

    Returns
    -------
    CalibrationReport with before/after Brier and RPS metrics.
    """
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression

    probs = predictions.loc[
        :, ["home_win_probability", "draw_probability", "away_win_probability"]
    ].to_numpy()
    actual = predictions["actual_outcome"].to_numpy()

    # Build one-hot actual matrix
    outcome_map = {"home_win": 0, "draw": 1, "away_win": 2}
    actual_idx = np.array([outcome_map[o] for o in actual])
    actual_onehot = np.zeros_like(probs)
    actual_onehot[np.arange(len(actual_idx)), actual_idx] = 1.0

    # Pre-calibration metrics
    brier_before = float(np.mean(np.sum((probs - actual_onehot) ** 2, axis=1)))
    rps_before = _compute_rps(probs, actual_onehot)

    # Calibrate each outcome independently
    calibrated_probs = probs.copy()
    for col_idx in range(3):
        y_true = actual_onehot[:, col_idx]
        y_prob = probs[:, col_idx]

        if method == "isotonic":
            iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            iso.fit(y_prob, y_true)
            calibrated_probs[:, col_idx] = iso.transform(y_prob)
        elif method == "platt":
            lr = LogisticRegression(C=1e10, solver="lbfgs", max_iter=5000)
            x_feat = y_prob.reshape(-1, 1)
            lr.fit(x_feat, y_true)
            calibrated_probs[:, col_idx] = lr.predict_proba(x_feat)[:, 1]
        else:
            raise ValueError(f"Unknown calibration method: {method}")

    # Normalize so probabilities sum to 1
    row_sums = calibrated_probs.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums == 0, 1.0, row_sums)
    calibrated_probs = calibrated_probs / row_sums

    # Post-calibration metrics
    brier_after = float(np.mean(np.sum((calibrated_probs - actual_onehot) ** 2, axis=1)))
    rps_after = _compute_rps(calibrated_probs, actual_onehot)

    # Build calibrated predictions DataFrame
    cal_df = predictions.copy()
    cal_df["home_win_probability_calibrated"] = calibrated_probs[:, 0]
    cal_df["draw_probability_calibrated"] = calibrated_probs[:, 1]
    cal_df["away_win_probability_calibrated"] = calibrated_probs[:, 2]

    return CalibrationReport(
        method=method,
        brier_before=brier_before,
        brier_after=brier_after,
        rps_before=rps_before,
        rps_after=rps_after,
        n_matches=len(predictions),
        calibrated_predictions=cal_df,
    )


def _compute_rps(probs: np.ndarray, actual_onehot: np.ndarray) -> float:
    """Compute Ranked Probability Score."""
    cumulative_probs = np.cumsum(probs, axis=1)
    cumulative_actual = np.cumsum(actual_onehot, axis=1)
    return float(np.mean(np.sum((cumulative_probs - cumulative_actual) ** 2, axis=1) / 2.0))


# ---------------------------------------------------------------------------
# Bootstrap confidence intervals for match predictions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PredictionConfidenceInterval:
    """Bootstrap confidence intervals for match prediction quantities.

    Each interval is a (low, high) tuple representing the percentile bounds
    of the bootstrap distribution.
    """

    n_bootstrap: int
    home_win_low: float
    home_win_high: float
    draw_low: float
    draw_high: float
    away_win_low: float
    away_win_high: float
    home_lambda_low: float
    home_lambda_high: float
    away_lambda_low: float
    away_lambda_high: float
    failed_iterations: int = 0


def bootstrap_prediction_confidence(
    team_match_df: pd.DataFrame,
    home_team_id: str,
    away_team_id: str,
    *,
    n_bootstrap: int = 200,
    confidence_level: float = 0.95,
    max_goals: int = 10,
    decay: float | None = None,
    half_life_days: float | None = None,
    random_seed: int = 42,
) -> PredictionConfidenceInterval:
    """Estimate confidence intervals for match predictions via bootstrap.

    Resamples the team-match data with replacement, refits a Dixon-Coles model
    on each bootstrap sample, and predicts the match. The distribution of
    home_win / draw / away_win / lambdas across bootstrap iterations yields
    percentile-based confidence intervals.

    Parameters
    ----------
    team_match_df : DataFrame with columns match_id, match_date, team_id,
        is_home, goals_for, goals_against.
    home_team_id, away_team_id : team identifiers present in team_match_df.
    n_bootstrap : number of bootstrap iterations (default 200).
    confidence_level : confidence level for the interval (default 0.95).
    max_goals : max goals for score matrix (default 10).
    decay, half_life_days : forwarded to fit_dixon_coles.
    random_seed : reproducibility seed.

    Returns
    -------
    PredictionConfidenceInterval with percentile-based bounds.
    """
    if n_bootstrap < 10:
        raise ValueError("n_bootstrap must be at least 10")
    if not (0.0 < confidence_level < 1.0):
        raise ValueError("confidence_level must be between 0 and 1")

    rng = np.random.default_rng(random_seed)
    alpha = (1.0 - confidence_level) / 2.0 * 100.0
    beta = (1.0 - alpha / 100.0) * 100.0

    # Build fixture-level data (one row per match) for resampling
    fixtures = _build_bootstrap_fixtures(team_match_df)
    n_fixtures = len(fixtures)
    if n_fixtures < 20:
        raise ValueError(
            f"Need at least 20 fixtures for bootstrap, got {n_fixtures}"
        )

    home_wins: list[float] = []
    draws: list[float] = []
    away_wins: list[float] = []
    home_lambdas: list[float] = []
    away_lambdas: list[float] = []
    failed = 0

    for _ in range(n_bootstrap):
        # Resample fixture indices with replacement
        sample_indices = rng.integers(0, n_fixtures, size=n_fixtures)
        sampled = fixtures.iloc[sample_indices]

        # Reconstruct team-match format (two rows per fixture)
        rows = []
        for _, fixture in sampled.iterrows():
            rows.append({
                "match_id": str(fixture["match_id"]),
                "match_date": str(fixture["match_date"]),
                "team_id": str(fixture["home_team"]),
                "is_home": True,
                "goals_for": int(fixture["home_goals"]),
                "goals_against": int(fixture["away_goals"]),
            })
            rows.append({
                "match_id": str(fixture["match_id"]),
                "match_date": str(fixture["match_date"]),
                "team_id": str(fixture["away_team"]),
                "is_home": False,
                "goals_for": int(fixture["away_goals"]),
                "goals_against": int(fixture["home_goals"]),
            })
        boot_df = pd.DataFrame(rows)

        try:
            model = fit_dixon_coles(
                boot_df,
                decay=decay,
                half_life_days=half_life_days,
                maxiter=300,
            )
            pred = predict_match_dc(
                model, home_team_id, away_team_id, max_goals=max_goals
            )
            home_wins.append(pred.summary.home_win)
            draws.append(pred.summary.draw)
            away_wins.append(pred.summary.away_win)
            home_lambdas.append(pred.home_lambda)
            away_lambdas.append(pred.away_lambda)
        except Exception:
            failed += 1
            continue

    if len(home_wins) < 5:
        raise RuntimeError(
            f"Bootstrap failed: only {len(home_wins)}/{n_bootstrap} iterations succeeded"
        )

    def _pct(arr: list[float]) -> tuple[float, float]:
        a = np.array(arr)
        return float(np.percentile(a, alpha)), float(np.percentile(a, beta))

    hw_lo, hw_hi = _pct(home_wins)
    d_lo, d_hi = _pct(draws)
    aw_lo, aw_hi = _pct(away_wins)
    hl_lo, hl_hi = _pct(home_lambdas)
    al_lo, al_hi = _pct(away_lambdas)

    return PredictionConfidenceInterval(
        n_bootstrap=n_bootstrap,
        home_win_low=hw_lo,
        home_win_high=hw_hi,
        draw_low=d_lo,
        draw_high=d_hi,
        away_win_low=aw_lo,
        away_win_high=aw_hi,
        home_lambda_low=hl_lo,
        home_lambda_high=hl_hi,
        away_lambda_low=al_lo,
        away_lambda_high=al_hi,
        failed_iterations=failed,
    )


def _build_bootstrap_fixtures(team_match_df: pd.DataFrame) -> pd.DataFrame:
    """Convert team-match rows (two per match) into fixture-level rows (one per match).

    Returns a DataFrame with columns: match_id, match_date, home_team,
    away_team, home_goals, away_goals.
    """
    df = team_match_df.copy()
    df["team_id"] = df["team_id"].astype(str)
    df["match_id"] = df["match_id"].astype(str)

    home_rows = df[df["is_home"]].rename(columns={
        "team_id": "home_team",
        "goals_for": "home_goals",
        "goals_against": "away_goals",
    })
    away_rows = df[~df["is_home"]].rename(columns={
        "team_id": "away_team",
        "goals_for": "away_goals",
        "goals_against": "home_goals",
    })

    merge_cols = ["match_id"]
    if "match_date" in df.columns:
        merge_cols.append("match_date")

    fixtures = home_rows[merge_cols + ["home_team", "home_goals", "away_goals"]].merge(
        away_rows[merge_cols + ["away_team", "away_goals", "home_goals"]],
        on=merge_cols,
        suffixes=("_h", "_a"),
    )
    # Resolve duplicate columns from merge
    for col in ["home_goals", "away_goals"]:
        h_col = f"{col}_h"
        a_col = f"{col}_a"
        if h_col in fixtures.columns and a_col in fixtures.columns:
            fixtures[col] = fixtures[h_col].where(fixtures[h_col].notna(), fixtures[a_col])
            fixtures = fixtures.drop(columns=[h_col, a_col])

    return fixtures.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Form-based match weighting
# ---------------------------------------------------------------------------


def compute_form_weights(
    team_match_df: pd.DataFrame,
    *,
    lookback: int = 5,
    form_factor: float = 0.3,
) -> np.ndarray:
    """Compute per-match form-based weights for Dixon-Coles fitting.

    For each match, the weight is based on the rolling form (points per game)
    of both teams in the preceding ``lookback`` matches. Teams in good recent
    form receive higher weight, reflecting that their recent performances are
    more predictive of current strength.

    Parameters
    ----------
    team_match_df : DataFrame with columns match_id, match_date, team_id,
        is_home, goals_for, goals_against.
    lookback : number of recent matches to compute rolling form (default 5).
    form_factor : controls the strength of form weighting (default 0.3).
        0.0 means no form weighting (all weights = 1.0).
        1.0 means strong form weighting.

    Returns
    -------
    np.ndarray of per-match weights aligned to the fixture-level ordering
    produced by _build_bootstrap_fixtures.
    """
    if form_factor <= 0.0:
        fixtures = _build_bootstrap_fixtures(team_match_df)
        return np.ones(len(fixtures))

    df = team_match_df.copy()
    df["team_id"] = df["team_id"].astype(str)
    df["match_id"] = df["match_id"].astype(str)
    if "match_date" in df.columns:
        df = df.sort_values("match_date").reset_index(drop=True)

    # Compute rolling form (points per game) for each team
    form_records: dict[str, list[float]] = {}
    for _, row in df.iterrows():
        tid = str(row["team_id"])
        gf = float(row["goals_for"])
        ga = float(row["goals_against"])
        pts = 3.0 if gf > ga else (1.0 if gf == ga else 0.0)
        if tid not in form_records:
            form_records[tid] = []
        form_records[tid].append(pts)

    # Compute rolling average form for each team at each match index
    rolling_form: dict[str, list[float]] = {}
    for tid, pts_list in form_records.items():
        arr = np.array(pts_list, dtype=float)
        rolling = np.full(len(arr), 1.0)  # default form = 1.0 (average)
        for i in range(1, len(arr)):
            start = max(0, i - lookback)
            rolling[i] = arr[start:i].mean() if i > 0 else 1.0
        rolling_form[tid] = rolling.tolist()

    # Build fixtures and compute per-fixture form weight
    fixtures = _build_bootstrap_fixtures(team_match_df)
    if "match_date" in fixtures.columns:
        fixtures = fixtures.sort_values("match_date").reset_index(drop=True)

    # Track per-team match index for rolling form lookup
    team_match_counter: dict[str, int] = {}
    weights = np.ones(len(fixtures))

    for idx, row in fixtures.iterrows():
        home_team = str(row["home_team"])
        away_team = str(row["away_team"])

        # Get current form index for each team
        h_idx = team_match_counter.get(home_team, 0)
        a_idx = team_match_counter.get(away_team, 0)

        # Get rolling form (0-3 scale, normalize to 0-1)
        h_form = 1.0
        a_form = 1.0
        if home_team in rolling_form and h_idx < len(rolling_form[home_team]):
            h_form = rolling_form[home_team][h_idx] / 3.0  # normalize 0-3 → 0-1
        if away_team in rolling_form and a_idx < len(rolling_form[away_team]):
            a_form = rolling_form[away_team][a_idx] / 3.0

        # Form weight: blend base weight (1.0) with form-adjusted weight
        # Good form (1.0) → weight > 1, bad form (0.0) → weight < 1
        h_weight = 1.0 + form_factor * (h_form - 0.5)
        a_weight = 1.0 + form_factor * (a_form - 0.5)
        weights[idx] = (h_weight + a_weight) / 2.0

        # Increment match counters
        team_match_counter[home_team] = h_idx + 1
        team_match_counter[away_team] = a_idx + 1

    # Normalize weights to mean 1.0 to preserve overall likelihood scale
    mean_w = float(np.mean(weights))
    if mean_w > 0:
        weights = weights / mean_w

    return weights


def fit_dixon_coles_with_form(
    team_match_df: pd.DataFrame,
    *,
    maxiter: int = 500,
    half_life_days: float | None = None,
    decay: float | None = None,
    form_lookback: int = 5,
    form_factor: float = 0.3,
) -> DixonColesModel:
    """Fit Dixon-Coles with form-based match weighting.

    Convenience wrapper that computes form weights via :func:`compute_form_weights`
    and passes them to :func:`fit_dixon_coles`.
    """
    form_weights = compute_form_weights(
        team_match_df,
        lookback=form_lookback,
        form_factor=form_factor,
    )
    return fit_dixon_coles(
        team_match_df,
        maxiter=maxiter,
        half_life_days=half_life_days,
        decay=decay,
        match_weights=form_weights,
    )


# ---------------------------------------------------------------------------
# Ensemble prediction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnsemblePrediction:
    """Blended prediction from multiple models with optimal weighting."""

    home_lambda: float
    away_lambda: float
    home_win: float
    draw: float
    away_win: float
    over_2_5: float
    btts_yes: float
    score_matrix: pd.DataFrame
    weights: dict[str, float]
    model_predictions: dict[str, dict[str, float]]


def ensemble_prediction(
    predictions: dict[str, PoissonPrediction],
    *,
    weights: dict[str, float] | None = None,
) -> EnsemblePrediction:
    """Blend multiple PoissonPrediction results into an ensemble.

    Parameters
    ----------
    predictions : dict mapping model name to PoissonPrediction.
    weights : optional dict mapping model name to weight. If None, equal
        weighting is used. Weights are normalized to sum to 1.

    Returns
    -------
    EnsemblePrediction with blended probabilities and score matrix.
    """
    if not predictions:
        raise ValueError("At least one prediction is required")

    model_names = list(predictions.keys())
    if weights is None:
        weights = {name: 1.0 / len(model_names) for name in model_names}
    else:
        # Validate and normalize
        total = sum(weights.get(name, 0.0) for name in model_names)
        if total <= 0:
            raise ValueError("Weights must sum to a positive value")
        weights = {name: weights.get(name, 0.0) / total for name in model_names}

    # Blend lambdas
    home_lambda = sum(
        weights[name] * predictions[name].home_lambda for name in model_names
    )
    away_lambda = sum(
        weights[name] * predictions[name].away_lambda for name in model_names
    )

    # Blend score matrices
    blended_matrix = None
    for name in model_names:
        mat = predictions[name].score_matrix
        if blended_matrix is None:
            blended_matrix = weights[name] * mat.to_numpy()
        else:
            blended_matrix += weights[name] * mat.to_numpy()

    # Normalize blended matrix
    total_prob = blended_matrix.sum()
    if total_prob > 0:
        blended_matrix /= total_prob

    score_matrix = pd.DataFrame(
        blended_matrix,
        index=predictions[model_names[0]].score_matrix.index,
        columns=predictions[model_names[0]].score_matrix.columns,
    )

    # Derive summary from blended matrix
    summary = _summarize_score_matrix(score_matrix)

    # Store per-model predictions for transparency
    model_preds: dict[str, dict[str, float]] = {}
    for name in model_names:
        pred = predictions[name]
        model_preds[name] = {
            "home_lambda": pred.home_lambda,
            "away_lambda": pred.away_lambda,
            "home_win": pred.summary.home_win,
            "draw": pred.summary.draw,
            "away_win": pred.summary.away_win,
        }

    return EnsemblePrediction(
        home_lambda=home_lambda,
        away_lambda=away_lambda,
        home_win=summary.home_win,
        draw=summary.draw,
        away_win=summary.away_win,
        over_2_5=summary.over_2_5,
        btts_yes=summary.btts_yes,
        score_matrix=score_matrix,
        weights=weights,
        model_predictions=model_preds,
    )


def optimize_ensemble_weights(
    team_match_df: pd.DataFrame,
    *,
    decay: float | None = None,
    split_cfg: object | None = None,
    max_goals: int = 10,
) -> dict[str, float]:
    """Find optimal ensemble weights by minimizing RPS on holdout.

    Fits all three models (Poisson, DC, DC+Form) on training data and
    evaluates on holdout, then searches over weight combinations to
    minimize the Ranked Probability Score.

    Returns a dict of normalized weights keyed by model name.
    """
    from scoutfootball.evaluation.backtests import (
        TimeSplitConfig,
        run_dixon_coles_backtest,
        run_poisson_backtest,
    )

    if split_cfg is None:
        split_cfg = TimeSplitConfig(n_splits=3, gap=0)

    # Run backtests to get per-model predictions
    poisson_bt = run_poisson_backtest(team_match_df, split_cfg)
    dc_bt = run_dixon_coles_backtest(team_match_df, split_cfg, decay=decay)

    # Get actual outcomes from predictions
    poisson_preds = poisson_bt.predictions
    dc_preds = dc_bt.predictions

    if poisson_preds.empty or dc_preds.empty:
        return {"poisson": 0.33, "dixon_coles": 0.34, "dixon_coles_form": 0.33}

    # Align on match_id
    merged = poisson_preds.merge(
        dc_preds[["match_id", "home_win_probability", "draw_probability", "away_win_probability"]],
        on="match_id",
        suffixes=("_poisson", "_dc"),
    )

    # Determine actual outcomes
    if "actual_outcome" in merged.columns:
        actual = merged["actual_outcome"].map(
            {"home_win": 0, "draw": 1, "away_win": 2}
        ).to_numpy()
    elif "home_goals" in merged.columns and "away_goals" in merged.columns:
        actual = np.where(
            merged["home_goals"] > merged["away_goals"], 0,
            np.where(merged["home_goals"] == merged["away_goals"], 1, 2),
        )
    else:
        return {"poisson": 0.33, "dixon_coles": 0.34, "dixon_coles_form": 0.33}

    poisson_probs = merged[
        ["home_win_probability_poisson", "draw_probability_poisson", "away_win_probability_poisson"]
    ].to_numpy()
    dc_probs = merged[
        ["home_win_probability_dc", "draw_probability_dc", "away_win_probability_dc"]
    ].to_numpy()

    # For form-weighted, use DC as proxy (form weighting is a refinement of DC)
    form_probs = dc_probs  # proxy

    # Grid search over weights
    best_rps = float("inf")
    best_weights = {"poisson": 0.33, "dixon_coles": 0.34, "dixon_coles_form": 0.33}

    # Actual one-hot
    actual_onehot = np.zeros_like(poisson_probs)
    actual_onehot[np.arange(len(actual)), actual] = 1.0

    for w_p in np.arange(0.0, 1.01, 0.1):
        for w_d in np.arange(0.0, 1.01 - w_p, 0.1):
            w_f = 1.0 - w_p - w_d
            if w_f < 0:
                continue
            blended = w_p * poisson_probs + w_d * dc_probs + w_f * form_probs
            rps = _compute_rps(blended, actual_onehot)
            if rps < best_rps:
                best_rps = rps
                best_weights = {
                    "poisson": float(w_p),
                    "dixon_coles": float(w_d),
                    "dixon_coles_form": float(w_f),
                }

    return best_weights


def save_ensemble_weights(
    weights: dict[str, float],
    path: Path,
    *,
    rps: float | None = None,
    n_matches: int | None = None,
) -> None:
    """Save ensemble weights to a JSON artifact for later reuse.

    Parameters
    ----------
    weights : normalized weights dict keyed by model name.
    path : destination JSON file path.
    rps : optional RPS achieved by these weights on the holdout.
    n_matches : optional number of matches used for optimization.
    """
    import json
    from datetime import UTC, datetime

    payload = {
        "weights": {k: float(v) for k, v in weights.items()},
        "rps": float(rps) if rps is not None else None,
        "n_matches": int(n_matches) if n_matches is not None else None,
        "saved_at": datetime.now(UTC).isoformat(),
        "format": "ensemble-weights-v1",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def load_ensemble_weights(path: Path) -> dict[str, float] | None:
    """Load cached ensemble weights from a JSON artifact.

    Returns ``None`` if the file does not exist or is invalid.
    """
    import json

    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        weights = data.get("weights")
        if not isinstance(weights, dict) or not weights:
            return None
        return {k: float(v) for k, v in weights.items()}
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Isotonic recalibration
# ---------------------------------------------------------------------------


@dataclass
class IsotonicCalibrator:
    """Fitted isotonic regression calibrators for 1x2 match probabilities.

    Stores three independent IsotonicRegression objects (one per outcome)
    along with before/after metrics so the recalibration effect is
    transparent and auditable.
    """

    home_win_iso: object  # sklearn.isotonic.IsotonicRegression
    draw_iso: object
    away_win_iso: object
    n_samples: int
    brier_before: float
    brier_after: float
    rps_before: float
    rps_after: float


def fit_isotonic_calibrator(predictions: pd.DataFrame) -> IsotonicCalibrator:
    """Fit isotonic regression calibrators on backtest predictions.

    Parameters
    ----------
    predictions : DataFrame with columns ``home_win_probability``,
        ``draw_probability``, ``away_win_probability`` and
        ``actual_outcome`` (values: ``home_win``/``draw``/``away_win``).

    Returns
    -------
    IsotonicCalibrator holding the fitted regressors and before/after metrics.
    """
    from sklearn.isotonic import IsotonicRegression

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

    brier_before = float(np.mean(np.sum((probs - actual_onehot) ** 2, axis=1)))
    rps_before = _compute_rps(probs, actual_onehot)

    calibrators: list[IsotonicRegression] = []
    for col_idx in range(3):
        iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        iso.fit(probs[:, col_idx], actual_onehot[:, col_idx])
        calibrators.append(iso)

    calibrated = np.column_stack([
        calibrators[0].transform(probs[:, 0]),
        calibrators[1].transform(probs[:, 1]),
        calibrators[2].transform(probs[:, 2]),
    ])
    row_sums = calibrated.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums == 0, 1.0, row_sums)
    calibrated = calibrated / row_sums

    brier_after = float(np.mean(np.sum((calibrated - actual_onehot) ** 2, axis=1)))
    rps_after = _compute_rps(calibrated, actual_onehot)

    return IsotonicCalibrator(
        home_win_iso=calibrators[0],
        draw_iso=calibrators[1],
        away_win_iso=calibrators[2],
        n_samples=len(predictions),
        brier_before=brier_before,
        brier_after=brier_after,
        rps_before=rps_before,
        rps_after=rps_after,
    )


def apply_recalibration(
    calibrator: IsotonicCalibrator,
    home_win: float,
    draw: float,
    away_win: float,
) -> tuple[float, float, float]:
    """Apply isotonic recalibration to a single prediction's 1x2 probabilities.

    Returns a normalized ``(home_win, draw, away_win)`` tuple.
    """
    raw = np.array([home_win, draw, away_win], dtype=float)
    calibrated = np.array([
        float(calibrator.home_win_iso.transform([raw[0]])[0]),
        float(calibrator.draw_iso.transform([raw[1]])[0]),
        float(calibrator.away_win_iso.transform([raw[2]])[0]),
    ])
    total = calibrated.sum()
    if total > 0:
        calibrated = calibrated / total
    return float(calibrated[0]), float(calibrated[1]), float(calibrated[2])


# ---------------------------------------------------------------------------
# Match momentum prediction (in-play win probability)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MomentumPoint:
    """In-play win probability at a specific minute and scoreline."""

    minute: int
    home_win: float
    draw: float
    away_win: float
    remaining_home_lambda: float
    remaining_away_lambda: float


@dataclass(frozen=True)
class MatchMomentum:
    """In-play momentum timeline for a match.

    Given pre-match expected goals (lambdas) and a current scoreline,
    computes the updated win/draw/loss probability at each minute.
    """

    home_team: str
    away_team: str
    home_lambda: float
    away_lambda: float
    current_minute: int
    current_home_goals: int
    current_away_goals: int
    timeline: list[MomentumPoint]


def compute_momentum(
    home_team: str,
    away_team: str,
    home_lambda: float,
    away_lambda: float,
    *,
    current_home_goals: int = 0,
    current_away_goals: int = 0,
    current_minute: int = 0,
    max_goals: int = 10,
    minute_step: int = 5,
    match_duration: int = 90,
) -> MatchMomentum:
    """Compute in-play win probability timeline.

    Uses independent Poisson for remaining goals: at each minute, the
    remaining expected goals are proportional to remaining time. The
    final outcome is determined by current scoreline + remaining goals.

    Parameters
    ----------
    home_team, away_team : team names.
    home_lambda, away_lambda : pre-match expected goals (full match).
    current_home_goals, current_away_goals : scoreline at ``current_minute``.
    current_minute : minute at which the scoreline applies (0-90+).
    max_goals : maximum goals to consider per team in remaining-time Poisson.
    minute_step : interval between timeline points (default 5 minutes).
    match_duration : total match duration in minutes (default 90).

    Returns
    -------
    MatchMomentum with timeline from current_minute to match_duration.
    """
    if home_lambda < 0 or away_lambda < 0:
        raise ValueError("Lambdas must be non-negative")
    if current_minute < 0 or current_minute > match_duration + 10:
        raise ValueError(f"current_minute must be in [0, {match_duration + 10}]")
    if current_home_goals < 0 or current_away_goals < 0:
        raise ValueError("Goals must be non-negative")
    if minute_step < 1:
        raise ValueError("minute_step must be at least 1")

    timeline: list[MomentumPoint] = []
    for minute in range(current_minute, match_duration + 1, minute_step):
        remaining_minutes = max(0, match_duration - minute)
        if remaining_minutes == 0:
            # Match is over — outcome is determined by current scoreline
            if current_home_goals > current_away_goals:
                hw, dw, aw = 1.0, 0.0, 0.0
            elif current_home_goals == current_away_goals:
                hw, dw, aw = 0.0, 1.0, 0.0
            else:
                hw, dw, aw = 0.0, 0.0, 1.0
            timeline.append(MomentumPoint(
                minute=minute,
                home_win=hw,
                draw=dw,
                away_win=aw,
                remaining_home_lambda=0.0,
                remaining_away_lambda=0.0,
            ))
            break

        remaining_home_lambda = home_lambda * (remaining_minutes / match_duration)
        remaining_away_lambda = away_lambda * (remaining_minutes / match_duration)

        hw, dw, aw = _compute_inplay_probabilities(
            current_home_goals,
            current_away_goals,
            remaining_home_lambda,
            remaining_away_lambda,
            max_goals=max_goals,
        )

        timeline.append(MomentumPoint(
            minute=minute,
            home_win=hw,
            draw=dw,
            away_win=aw,
            remaining_home_lambda=remaining_home_lambda,
            remaining_away_lambda=remaining_away_lambda,
        ))

    return MatchMomentum(
        home_team=home_team,
        away_team=away_team,
        home_lambda=home_lambda,
        away_lambda=away_lambda,
        current_minute=current_minute,
        current_home_goals=current_home_goals,
        current_away_goals=current_away_goals,
        timeline=timeline,
    )


def _compute_inplay_probabilities(
    current_home_goals: int,
    current_away_goals: int,
    remaining_home_lambda: float,
    remaining_away_lambda: float,
    *,
    max_goals: int = 10,
) -> tuple[float, float, float]:
    """Compute win/draw/loss probabilities from current scoreline and remaining lambdas.

    Uses independent Poisson for remaining goals. Returns (home_win, draw, away_win).
    """
    if remaining_home_lambda <= 0 and remaining_away_lambda <= 0:
        # No time remaining — outcome is determined
        if current_home_goals > current_away_goals:
            return 1.0, 0.0, 0.0
        if current_home_goals == current_away_goals:
            return 0.0, 1.0, 0.0
        return 0.0, 0.0, 1.0

    home_probs = poisson.pmf(np.arange(max_goals + 1), remaining_home_lambda)
    away_probs = poisson.pmf(np.arange(max_goals + 1), remaining_away_lambda)

    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    for rh in range(max_goals + 1):
        for ra in range(max_goals + 1):
            prob = float(home_probs[rh] * away_probs[ra])
            final_home = current_home_goals + rh
            final_away = current_away_goals + ra
            if final_home > final_away:
                home_win += prob
            elif final_home == final_away:
                draw += prob
            else:
                away_win += prob

    total = home_win + draw + away_win
    if total > 0:
        home_win /= total
        draw /= total
        away_win /= total

    return home_win, draw, away_win


def update_probability_at_scoreline(
    home_lambda: float,
    away_lambda: float,
    current_home_goals: int,
    current_away_goals: int,
    current_minute: int,
    *,
    max_goals: int = 10,
    match_duration: int = 90,
) -> tuple[float, float, float]:
    """Compute updated win/draw/loss probabilities at a given minute and scoreline.

    Convenience wrapper around :func:`_compute_inplay_probabilities` that
    scales lambdas by remaining time.

    Returns
    -------
    (home_win, draw, away_win) tuple of probabilities.
    """
    remaining_minutes = max(0, match_duration - current_minute)
    remaining_home_lambda = home_lambda * (remaining_minutes / match_duration)
    remaining_away_lambda = away_lambda * (remaining_minutes / match_duration)
    return _compute_inplay_probabilities(
        current_home_goals,
        current_away_goals,
        remaining_home_lambda,
        remaining_away_lambda,
        max_goals=max_goals,
    )

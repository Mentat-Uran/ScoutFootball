"""League season projection and form analysis.

Three interconnected descriptive/predictive features operating on the
Football-Data ``combined_results`` Parquet:

1. :func:`compute_league_form_table` — last-N form table for every team
   in a league-season, with form rating, trend label and home/away split.
2. :func:`compute_fixture_difficulty` — retrospective fixture difficulty
   rating for each team's most recent N matches using a Bradley-Terry
   expected-points model derived from season win percentages.
3. :func:`compute_season_projection` — Monte Carlo simulation of the
   remaining league season, producing per-team final-position
   distributions and title / top-N / relegation probabilities.

The module is side-effect free and accepts an already-loaded pandas
DataFrame so it can be unit-tested with synthetic frames and reused by
both the API and CLI layers. All three functions are explicitly
non-additive interpretive overlays relative to the Dixon-Coles match
prediction model — they use a simple Bradley-Terry strength estimate
derived from in-season results and do not modify any persisted model
artifact.

Design notes
------------
* ``results_df`` mirrors the schema of ``combined_results.parquet``:
  required columns are ``HomeTeam``, ``AwayTeam``, ``FTHG``, ``FTAG``,
  ``league`` and ``season``. ``Date`` is used when present for ordering.
* Bradley-Terry strength is derived from in-season points per game so
  the simulation is self-contained and does not depend on the rating
  matrix or DC model being fitted.
* The Monte Carlo simulation assumes a standard double round-robin
  fixture list (each pair meets twice, home and away). Remaining
  fixtures are inferred as the complement of already-played pairs.
* A reproducible ``random_seed`` makes simulation outputs deterministic
  across runs and processes.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

_DISCLAIMER = (
    "Descriptive season overlay based on in-season results only; does "
    "not use the Dixon-Coles prediction model, rating matrix, or any "
    "external odds feed. Projections assume a standard double "
    "round-robin fixture list and a Bradley-Terry strength estimate."
)

_REQUIRED_COLUMNS = {"HomeTeam", "AwayTeam", "FTHG", "FTAG", "league", "season"}
_DEFAULT_LAST_N = 6
_DEFAULT_UPCOMING_N = 10
_DEFAULT_NUM_SIMULATIONS = 1000
_DEFAULT_TOP_N = 4
_DEFAULT_RELEGATION_SLOTS = 3
_HOME_ADVANTAGE_LOGIT = 0.25  # modest home-edge logit for Bradley-Terry
_MAX_LAST_N = 30
_MAX_UPCOMING_N = 30
_MAX_SIMULATIONS = 10000
_MIN_SIMULATIONS = 100


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _filter_results(
    results_df: pd.DataFrame,
    *,
    league: str | None,
    season: str,
) -> pd.DataFrame:
    """Return a copy filtered to the requested league-season with valid scores."""
    if results_df is None or results_df.empty:
        return pd.DataFrame()
    missing = _REQUIRED_COLUMNS.difference(results_df.columns)
    if missing:
        return pd.DataFrame()
    df = results_df.copy()
    mask = df["season"].astype(str) == str(season)
    if league is not None and league != "":
        mask &= df["league"].astype(str) == str(league)
    df = df.loc[mask].copy()
    # Keep only rows with valid integer scores.
    df = df.loc[df["FTHG"].notna() & df["FTAG"].notna()].copy()
    if "Date" in df.columns:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.sort_values("Date", ascending=True, na_position="last").reset_index(drop=True)
    else:
        df = df.reset_index(drop=True)
    return df


def _safe_int(value: Any) -> int:
    """Convert a numpy/pandas scalar to int (0 on failure)."""
    try:
        if pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _result_from_scores(home_goals: int, away_goals: int) -> str:
    """Return 'H' / 'D' / 'A' from full-time scores."""
    if home_goals > away_goals:
        return "H"
    if home_goals < away_goals:
        return "A"
    return "D"


def _points_for(result: str, is_home: bool) -> int:
    """Points earned by the focal team given result and venue."""
    if result == "D":
        return 1
    if result == "H":
        return 3 if is_home else 0
    # Away win.
    return 0 if is_home else 3


def _build_season_standings(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Build per-team standings from a filtered DataFrame of completed matches."""
    standings: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        home = str(row.get("HomeTeam", "")).strip()
        away = str(row.get("AwayTeam", "")).strip()
        if not home or not away:
            continue
        hg = _safe_int(row.get("FTHG"))
        ag = _safe_int(row.get("FTAG"))
        result = _result_from_scores(hg, ag)
        for team, is_home, gf, ga in (
            (home, True, hg, ag),
            (away, False, ag, hg),
        ):
            if team not in standings:
                standings[team] = {
                    "played": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "points": 0,
                    "home_played": 0,
                    "home_points": 0,
                    "away_played": 0,
                    "away_points": 0,
                }
            entry = standings[team]
            entry["played"] += 1
            entry["goals_for"] += gf
            entry["goals_against"] += ga
            pts = _points_for(result, is_home)
            entry["points"] += pts
            if is_home:
                entry["home_played"] += 1
                entry["home_points"] += pts
            else:
                entry["away_played"] += 1
                entry["away_points"] += pts
            if pts == 3:
                entry["wins"] += 1
            elif pts == 1:
                entry["draws"] += 1
            else:
                entry["losses"] += 1
    return standings


def _standings_list(standings: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert standings dict to a sorted list (points desc, GD desc, GF desc)."""
    rows = []
    for team, entry in standings.items():
        gd = entry["goals_for"] - entry["goals_against"]
        rows.append({
            "team": team,
            "played": entry["played"],
            "wins": entry["wins"],
            "draws": entry["draws"],
            "losses": entry["losses"],
            "goals_for": entry["goals_for"],
            "goals_against": entry["goals_against"],
            "goal_difference": gd,
            "points": entry["points"],
        })
    rows.sort(
        key=lambda r: (r["points"], r["goal_difference"], r["goals_for"], r["team"]),
        reverse=True,
    )
    for idx, row in enumerate(rows, start=1):
        row["position"] = idx
    return rows


def _team_ppg(standings: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Points-per-game for each team (0 for unplayed)."""
    ppg: dict[str, float] = {}
    for team, entry in standings.items():
        played = entry["played"]
        ppg[team] = entry["points"] / played if played > 0 else 0.0
    return ppg


def _bradley_terry_prob(
    home_strength: float,
    away_strength: float,
    *,
    home_advantage: float = _HOME_ADVANTAGE_LOGIT,
) -> tuple[float, float, float]:
    """Bradley-Terry win/draw/loss probabilities with a small home edge.

    Draw probability uses the standard 1/(1+exp(|delta|)) heuristic scaled
    by a constant so the three outcomes sum to 1.
    """
    logit_home = math.log1p(max(home_strength, 1e-6)) + home_advantage
    logit_away = math.log1p(max(away_strength, 1e-6))
    delta = logit_home - logit_away
    # Win probabilities before draw adjustment.
    p_home_raw = 1.0 / (1.0 + math.exp(-delta))
    p_away_raw = 1.0 - p_home_raw
    # Draw probability is highest when teams are evenly matched.
    draw_intensity = math.exp(-abs(delta)) * 0.28  # cap draw share
    p_draw = draw_intensity
    p_home = p_home_raw * (1.0 - p_draw)
    p_away = p_away_raw * (1.0 - p_draw)
    total = p_home + p_draw + p_away
    if total <= 0:
        return 1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0
    return p_home / total, p_draw / total, p_away / total


def _form_rating(ppg: float, max_ppg: float = 3.0) -> float:
    """Map points-per-game to a 0-100 rating."""
    if max_ppg <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * ppg / max_ppg))


def _trend_label(recent_ppg: float, older_ppg: float) -> str:
    """Rising/declining/stable label from recent vs older PPG."""
    delta = recent_ppg - older_ppg
    if delta > 0.3:
        return "rising"
    if delta < -0.3:
        return "declining"
    return "stable"


def _linear_slope(values: list[float]) -> float:
    """Least-squares slope of a 1-D series (0 when n < 2)."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = np.arange(n, dtype=float)
    ys = np.asarray(values, dtype=float)
    x_mean = xs.mean()
    y_mean = ys.mean()
    denom = float(np.sum((xs - x_mean) ** 2))
    if denom == 0:
        return 0.0
    return float(np.sum((xs - x_mean) * (ys - y_mean)) / denom)


# ---------------------------------------------------------------------------
# 1. League form table
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FormTableEntry:
    """One team's recent-form summary within a league-season."""

    team: str
    played: int
    wins: int
    draws: int
    losses: int
    points: int
    ppg: float
    form_rating: float
    form_string: str
    trend_label: str
    recent_ppg: float
    older_ppg: float
    home_ppg: float
    away_ppg: float
    goals_for: int
    goals_against: int


def compute_league_form_table(
    results_df: pd.DataFrame,
    *,
    league: str | None = None,
    season: str,
    last_n: int = _DEFAULT_LAST_N,
) -> dict[str, Any]:
    """Build a last-N form table for every team in a league-season.

    Returns a dict with ``status`` (``ok`` / ``no_data`` / ``insufficient_matches``),
    ``league``, ``season``, ``last_n``, ``teams`` (sorted by ``ppg`` descending),
    and ``disclaimer``.
    """
    last_n = max(1, min(int(last_n), _MAX_LAST_N))
    df = _filter_results(results_df, league=league, season=season)
    if df.empty:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "last_n": last_n,
            "teams": [],
            "disclaimer": _DISCLAIMER,
        }

    # Per-team match list (chronological).
    team_matches: dict[str, list[dict[str, Any]]] = {}
    for _, row in df.iterrows():
        home = str(row.get("HomeTeam", "")).strip()
        away = str(row.get("AwayTeam", "")).strip()
        if not home or not away:
            continue
        hg = _safe_int(row.get("FTHG"))
        ag = _safe_int(row.get("FTAG"))
        result = _result_from_scores(hg, ag)
        date_value = row.get("Date")
        date_iso = None
        if date_value is not None and not pd.isna(date_value):
            try:
                date_iso = pd.Timestamp(date_value).isoformat()
            except (TypeError, ValueError):
                date_iso = None
        for team, is_home, gf, ga in (
            (home, True, hg, ag),
            (away, False, ag, hg),
        ):
            team_matches.setdefault(team, []).append({
                "date": date_iso,
                "opponent": away if is_home else home,
                "venue": "H" if is_home else "A",
                "goals_for": gf,
                "goals_against": ga,
                "result": _result_label(result, is_home),
                "points": _points_for(result, is_home),
            })

    teams: list[dict[str, Any]] = []
    for team, matches in team_matches.items():
        # Last N matches (most recent first).
        recent = list(reversed(matches[-last_n:]))
        played = len(recent)
        if played == 0:
            continue
        wins = sum(1 for m in recent if m["result"] == "W")
        draws = sum(1 for m in recent if m["result"] == "D")
        losses = sum(1 for m in recent if m["result"] == "L")
        points = sum(m["points"] for m in recent)
        ppg = points / played if played > 0 else 0.0
        form_string = "".join(m["result"] for m in recent)
        # Split recent window into recent half and older half for trend.
        half = max(1, played // 2)
        recent_half = recent[:half]
        older_half = recent[half:]
        recent_ppg = (
            sum(m["points"] for m in recent_half) / len(recent_half) if recent_half else 0.0
        )
        older_ppg = (
            sum(m["points"] for m in older_half) / len(older_half) if older_half else 0.0
        )
        trend_label = _trend_label(recent_ppg, older_ppg)
        # Home/away split within the window.
        home_matches = [m for m in recent if m["venue"] == "H"]
        away_matches = [m for m in recent if m["venue"] == "A"]
        home_ppg = (
            sum(m["points"] for m in home_matches) / len(home_matches) if home_matches else 0.0
        )
        away_ppg = (
            sum(m["points"] for m in away_matches) / len(away_matches) if away_matches else 0.0
        )
        goals_for = sum(m["goals_for"] for m in recent)
        goals_against = sum(m["goals_against"] for m in recent)
        teams.append({
            "team": team,
            "played": played,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "points": points,
            "ppg": round(ppg, 4),
            "form_rating": round(_form_rating(ppg), 2),
            "form_string": form_string,
            "trend_label": trend_label,
            "recent_ppg": round(recent_ppg, 4),
            "older_ppg": round(older_ppg, 4),
            "home_ppg": round(home_ppg, 4),
            "away_ppg": round(away_ppg, 4),
            "goals_for": goals_for,
            "goals_against": goals_against,
        })

    teams.sort(
        key=lambda r: (
            r["ppg"],
            r["points"],
            r["goal_difference"] if "goal_difference" in r
            else r["goals_for"] - r["goals_against"],
            r["team"],
        ),
        reverse=True,
    )

    status = "ok" if teams else "insufficient_matches"
    return {
        "status": status,
        "league": league,
        "season": season,
        "last_n": last_n,
        "n_teams": len(teams),
        "teams": teams,
        "disclaimer": _DISCLAIMER,
    }


def _result_label(result: str, is_home: bool) -> str:
    """Convert 'H'/'D'/'A' to the focal team's 'W'/'D'/'L'."""
    if result == "D":
        return "D"
    if result == "H":
        return "W" if is_home else "L"
    return "L" if is_home else "W"


# ---------------------------------------------------------------------------
# 2. Fixture difficulty
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FixtureDifficultyEntry:
    """One fixture's difficulty rating for the focal team."""

    date: str | None
    opponent: str
    venue: str
    opponent_ppg: float
    expected_points: float
    difficulty_score: float
    difficulty_label: str
    actual_result: str | None
    actual_points: int


def _difficulty_label(score: float) -> str:
    """Map 0-100 difficulty score to a label."""
    if score >= 75:
        return "very_hard"
    if score >= 55:
        return "hard"
    if score >= 35:
        return "moderate"
    if score >= 20:
        return "easy"
    return "very_easy"


def compute_fixture_difficulty(
    results_df: pd.DataFrame,
    *,
    league: str | None = None,
    season: str,
    team: str | None = None,
    upcoming_n: int = _DEFAULT_UPCOMING_N,
    team_strengths: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Rate fixture difficulty for each team's most recent N matches.

    When ``team`` is provided, only that team's fixture list is returned.
    Otherwise, every team in the league-season gets a fixture list.
    ``expected_points`` uses a Bradley-Terry model on the season's
    points-per-game (or the supplied ``team_strengths`` mapping).
    ``difficulty_score`` is ``100 * (1 - expected_points / 3)``.
    """
    upcoming_n = max(1, min(int(upcoming_n), _MAX_UPCOMING_N))
    df = _filter_results(results_df, league=league, season=season)
    if df.empty:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "team": team,
            "upcoming_n": upcoming_n,
            "teams": [],
            "disclaimer": _DISCLAIMER,
        }

    standings = _build_season_standings(df)
    if not standings:
        return {
            "status": "insufficient_matches",
            "league": league,
            "season": season,
            "team": team,
            "upcoming_n": upcoming_n,
            "teams": [],
            "disclaimer": _DISCLAIMER,
        }

    # Strength = PPG (or supplied strengths).
    if team_strengths:
        strengths = {t: float(team_strengths.get(t, 0.0)) for t in standings}
    else:
        strengths = _team_ppg(standings)

    # Per-team chronological match list (oldest first).
    team_matches: dict[str, list[dict[str, Any]]] = {}
    for _, row in df.iterrows():
        home = str(row.get("HomeTeam", "")).strip()
        away = str(row.get("AwayTeam", "")).strip()
        if not home or not away:
            continue
        hg = _safe_int(row.get("FTHG"))
        ag = _safe_int(row.get("FTAG"))
        result = _result_from_scores(hg, ag)
        date_value = row.get("Date")
        date_iso = None
        if date_value is not None and not pd.isna(date_value):
            try:
                date_iso = pd.Timestamp(date_value).isoformat()
            except (TypeError, ValueError):
                date_iso = None
        for focal, opp, is_home, gf, ga in (
            (home, away, True, hg, ag),
            (away, home, False, ag, hg),
        ):
            team_matches.setdefault(focal, []).append({
                "date": date_iso,
                "opponent": opp,
                "venue": "H" if is_home else "A",
                "goals_for": gf,
                "goals_against": ga,
                "result": _result_label(result, is_home),
                "actual_points": _points_for(result, is_home),
            })

    target_teams = [team] if team else list(team_matches.keys())
    if team and team not in team_matches:
        return {
            "status": "team_not_found",
            "league": league,
            "season": season,
            "team": team,
            "upcoming_n": upcoming_n,
            "teams": [],
            "disclaimer": _DISCLAIMER,
        }

    teams_output: list[dict[str, Any]] = []
    for focal in target_teams:
        matches = team_matches.get(focal, [])
        # Most recent N (chronological, then reverse for display).
        recent = matches[-upcoming_n:]
        fixtures: list[dict[str, Any]] = []
        for m in recent:
            opp = m["opponent"]
            venue = m["venue"]
            focal_strength = strengths.get(focal, 0.0)
            opp_strength = strengths.get(opp, 0.0)
            if venue == "H":
                p_home, p_draw, p_away = _bradley_terry_prob(focal_strength, opp_strength)
            else:
                p_home, p_draw, p_away = _bradley_terry_prob(opp_strength, focal_strength)
                p_home, p_away = p_away, p_home  # swap to focal perspective
            expected_points = 3.0 * p_home + 1.0 * p_draw
            difficulty_score = max(0.0, min(100.0, 100.0 * (1.0 - expected_points / 3.0)))
            fixtures.append({
                "date": m["date"],
                "opponent": opp,
                "venue": venue,
                "opponent_ppg": round(float(opp_strength), 4),
                "expected_points": round(float(expected_points), 4),
                "difficulty_score": round(float(difficulty_score), 2),
                "difficulty_label": _difficulty_label(difficulty_score),
                "actual_result": m["result"],
                "actual_points": int(m["actual_points"]),
            })
        avg_difficulty = (
            sum(f["difficulty_score"] for f in fixtures) / len(fixtures) if fixtures else 0.0
        )
        avg_expected = (
            sum(f["expected_points"] for f in fixtures) / len(fixtures) if fixtures else 0.0
        )
        teams_output.append({
            "team": focal,
            "n_fixtures": len(fixtures),
            "avg_difficulty": round(float(avg_difficulty), 2),
            "avg_expected_points": round(float(avg_expected), 4),
            "fixtures": fixtures,
        })

    teams_output.sort(key=lambda r: (r["avg_difficulty"], r["team"]), reverse=True)
    return {
        "status": "ok",
        "league": league,
        "season": season,
        "team": team,
        "upcoming_n": upcoming_n,
        "n_teams": len(teams_output),
        "teams": teams_output,
        "disclaimer": _DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# 3. Season projection (Monte Carlo)
# ---------------------------------------------------------------------------


def _remaining_fixtures(
    df: pd.DataFrame,
    teams: list[str],
) -> list[tuple[str, str]]:
    """Infer remaining fixtures as the complement of a double round-robin.

    Each pair of distinct teams should meet twice (home and away). For
    every ordered pair (home, away) we count how many times they have
    already met in that arrangement; remaining fixtures fill the gap up
    to one home leg each way.
    """
    played_counts: dict[tuple[str, str], int] = {}
    for _, row in df.iterrows():
        home = str(row.get("HomeTeam", "")).strip()
        away = str(row.get("AwayTeam", "")).strip()
        if not home or not away or home not in teams or away not in teams:
            continue
        key = (home, away)
        played_counts[key] = played_counts.get(key, 0) + 1

    remaining: list[tuple[str, str]] = []
    for home in teams:
        for away in teams:
            if home == away:
                continue
            count = played_counts.get((home, away), 0)
            if count < 1:
                remaining.append((home, away))
    return remaining


def _simulate_season(
    standings: dict[str, dict[str, Any]],
    remaining: list[tuple[str, str]],
    strengths: dict[str, float],
    *,
    rng: np.random.Generator,
) -> dict[str, int]:
    """Simulate one season completion and return final points per team."""
    final_points: dict[str, int] = {team: int(entry["points"]) for team, entry in standings.items()}
    for home, away in remaining:
        home_strength = strengths.get(home, 0.0)
        away_strength = strengths.get(away, 0.0)
        p_home, p_draw, p_away = _bradley_terry_prob(home_strength, away_strength)
        roll = rng.random()
        if roll < p_home:
            final_points[home] += 3
        elif roll < p_home + p_draw:
            final_points[home] += 1
            final_points[away] += 1
        else:
            final_points[away] += 3
    return final_points


def _rank_teams(final_points: dict[str, int]) -> list[str]:
    """Return team names sorted by points descending (ties broken alphabetically)."""
    return sorted(final_points.keys(), key=lambda t: (-final_points[t], t))


def compute_season_projection(
    results_df: pd.DataFrame,
    *,
    league: str | None = None,
    season: str,
    num_simulations: int = _DEFAULT_NUM_SIMULATIONS,
    random_seed: int = 42,
    top_n: int = _DEFAULT_TOP_N,
    relegation_slots: int = _DEFAULT_RELEGATION_SLOTS,
    team_strengths: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Monte Carlo projection of final league standings.

    Runs ``num_simulations`` completions of the remaining double
    round-robin fixtures using a Bradley-Terry model on in-season PPG
    (or supplied ``team_strengths``). Returns per-team average final
    points, average position, position distribution, and probabilities
    for title (1st), top-N, and relegation (bottom ``relegation_slots``).

    The projection is a self-contained descriptive overlay — it does not
    use the Dixon-Coles model, rating matrix, or any external odds feed.
    """
    num_simulations = max(_MIN_SIMULATIONS, min(int(num_simulations), _MAX_SIMULATIONS))
    top_n = max(1, int(top_n))
    relegation_slots = max(0, int(relegation_slots))
    df = _filter_results(results_df, league=league, season=season)
    if df.empty:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "num_simulations": num_simulations,
            "teams": [],
            "disclaimer": _DISCLAIMER,
        }

    standings = _build_season_standings(df)
    if not standings:
        return {
            "status": "insufficient_matches",
            "league": league,
            "season": season,
            "num_simulations": num_simulations,
            "teams": [],
            "disclaimer": _DISCLAIMER,
        }

    teams = sorted(standings.keys())
    if len(teams) < 2:
        return {
            "status": "insufficient_teams",
            "league": league,
            "season": season,
            "num_simulations": num_simulations,
            "teams": [],
            "disclaimer": _DISCLAIMER,
        }

    if team_strengths:
        strengths = {t: float(team_strengths.get(t, 0.0)) for t in teams}
    else:
        strengths = _team_ppg(standings)

    remaining = _remaining_fixtures(df, teams)

    current_table = _standings_list(standings)
    current_positions = {row["team"]: row["position"] for row in current_table}

    rng = np.random.default_rng(random_seed)

    # Accumulators.
    points_sum: dict[str, int] = {t: 0 for t in teams}
    position_sum: dict[str, int] = {t: 0 for t in teams}
    position_counts: dict[str, dict[int, int]] = {t: {} for t in teams}
    title_counts: dict[str, int] = {t: 0 for t in teams}
    top_n_counts: dict[str, int] = {t: 0 for t in teams}
    relegation_counts: dict[str, int] = {t: 0 for t in teams}
    n_teams = len(teams)
    if relegation_slots > 0:
        relegation_zone = set(
            range(max(1, n_teams - relegation_slots + 1), n_teams + 1)
        )
    else:
        relegation_zone = set()

    completed_simulations = 0
    for _ in range(num_simulations):
        final_points = _simulate_season(standings, remaining, strengths, rng=rng)
        ranked = _rank_teams(final_points)
        for pos, team in enumerate(ranked, start=1):
            points_sum[team] += final_points[team]
            position_sum[team] += pos
            position_counts[team][pos] = position_counts[team].get(pos, 0) + 1
            if pos == 1:
                title_counts[team] += 1
            if pos <= top_n:
                top_n_counts[team] += 1
            if pos in relegation_zone:
                relegation_counts[team] += 1
        completed_simulations += 1

    if completed_simulations == 0:
        return {
            "status": "simulation_failed",
            "league": league,
            "season": season,
            "num_simulations": 0,
            "teams": [],
            "disclaimer": _DISCLAIMER,
        }

    teams_output: list[dict[str, Any]] = []
    for team in teams:
        avg_points = points_sum[team] / completed_simulations
        avg_position = position_sum[team] / completed_simulations
        pos_dist = position_counts[team]
        # Compact position distribution: top-1, top-3, top-half, bottom-half, bottom-3.
        sorted_positions = sorted(pos_dist.keys())
        compact_dist = []
        for pos in sorted_positions:
            compact_dist.append({
                "position": pos,
                "count": pos_dist[pos],
                "probability": round(pos_dist[pos] / completed_simulations, 4),
            })
        teams_output.append({
            "team": team,
            "current_position": current_positions.get(team, n_teams),
            "current_points": int(standings[team]["points"]),
            "current_played": int(standings[team]["played"]),
            "avg_final_points": round(float(avg_points), 2),
            "avg_position": round(float(avg_position), 2),
            "title_probability": round(title_counts[team] / completed_simulations, 4),
            "top_n_probability": round(top_n_counts[team] / completed_simulations, 4),
            "relegation_probability": round(relegation_counts[team] / completed_simulations, 4),
            "position_distribution": compact_dist,
            "strength_ppg": round(float(strengths.get(team, 0.0)), 4),
        })

    # Sort by avg_position ascending (best teams first).
    teams_output.sort(key=lambda r: (r["avg_position"], r["avg_final_points"], r["team"]))

    n_remaining = len(remaining)
    return {
        "status": "ok",
        "league": league,
        "season": season,
        "num_simulations": completed_simulations,
        "random_seed": int(random_seed),
        "n_teams": n_teams,
        "n_remaining_fixtures": n_remaining,
        "top_n": top_n,
        "relegation_slots": relegation_slots,
        "current_standings": current_table,
        "teams": teams_output,
        "disclaimer": _DISCLAIMER,
    }

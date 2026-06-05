"""Coverage-based confidence level classification for league-season ratings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd


class ConfidenceLevel(StrEnum):
    HIGH = "high"       # coverage >= 0.90
    MEDIUM = "medium"   # 0.70 <= coverage < 0.90
    LOW = "low"         # coverage < 0.70


@dataclass(frozen=True)
class CoverageAssessment:
    league: str
    season: str
    target_teams: int
    rated_teams: int
    matched_teams: int
    coverage: float
    confidence_level: ConfidenceLevel
    allowed_output: str  # "full", "reference_only", "diagnostic_only"


def classify_confidence(coverage: float) -> ConfidenceLevel:
    """Classify confidence level based on coverage ratio."""
    if coverage >= 0.90:
        return ConfidenceLevel.HIGH
    if coverage >= 0.70:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def assess_league_season(
    league: str,
    season: str,
    target_teams: int,
    rated_teams: int,
    matched_teams: int,
) -> CoverageAssessment:
    """Assess coverage and confidence for a single league-season."""
    coverage = matched_teams / target_teams if target_teams > 0 else 0.0
    confidence = classify_confidence(coverage)
    if confidence == ConfidenceLevel.HIGH:
        allowed = "full"
    elif confidence == ConfidenceLevel.MEDIUM:
        allowed = "reference_only"
    else:
        allowed = "diagnostic_only"
    return CoverageAssessment(
        league=league,
        season=season,
        target_teams=target_teams,
        rated_teams=rated_teams,
        matched_teams=matched_teams,
        coverage=coverage,
        confidence_level=confidence,
        allowed_output=allowed,
    )


def assess_coverage_batch(
    ratings_df: pd.DataFrame,
    *,
    league_col: str = "league",
    season_col: str = "season",
    team_col: str = "team_name",
    target_teams_per_league: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Assess coverage for all league-seasons in a ratings DataFrame.

    Returns a DataFrame with columns: league, season, target_teams, rated_teams,
    matched_teams, coverage, confidence_level, allowed_output.

    If *target_teams_per_league* is provided, its values are used as the target
    team count for each league; otherwise rated_teams == target_teams (coverage
    defaults to 1.0).
    """
    if ratings_df.empty:
        return pd.DataFrame(
            columns=[
                "league",
                "season",
                "target_teams",
                "rated_teams",
                "matched_teams",
                "coverage",
                "confidence_level",
                "allowed_output",
            ],
        )

    required = {league_col, season_col, team_col}
    missing = sorted(required.difference(ratings_df.columns))
    if missing:
        raise ValueError(f"ratings_df is missing required columns: {', '.join(missing)}")

    grouped = ratings_df.groupby([league_col, season_col], sort=False)
    rated_counts = grouped[team_col].nunique()

    rows: list[dict] = []
    for (league, season), rated_teams in rated_counts.items():
        target = (
            target_teams_per_league.get(league, rated_teams)
            if target_teams_per_league is not None
            else rated_teams
        )
        matched = min(rated_teams, target)
        assessment = assess_league_season(
            league=league,
            season=season,
            target_teams=target,
            rated_teams=int(rated_teams),
            matched_teams=int(matched),
        )
        rows.append(
            {
                "league": assessment.league,
                "season": assessment.season,
                "target_teams": assessment.target_teams,
                "rated_teams": assessment.rated_teams,
                "matched_teams": assessment.matched_teams,
                "coverage": assessment.coverage,
                "confidence_level": assessment.confidence_level.value,
                "allowed_output": assessment.allowed_output,
            },
        )

    return pd.DataFrame(rows)


def add_confidence_to_ratings(
    ratings_df: pd.DataFrame,
    assessments: pd.DataFrame,
    *,
    league_col: str = "league",
    season_col: str = "season",
) -> pd.DataFrame:
    """Merge confidence assessment columns back onto the ratings DataFrame.

    Adds ``coverage``, ``confidence_level``, and ``allowed_output`` columns.
    Returns a new DataFrame; the original is not mutated.
    """
    if assessments.empty:
        result = ratings_df.copy()
        result["coverage"] = pd.NA
        result["confidence_level"] = pd.NA
        result["allowed_output"] = pd.NA
        return result

    merge_cols = [league_col, season_col]
    right = assessments[merge_cols + ["coverage", "confidence_level", "allowed_output"]].copy()
    result = ratings_df.merge(right, on=merge_cols, how="left")
    return result


def display_confidence_badge(confidence_level: str | ConfidenceLevel) -> None:
    """Display a confidence level badge in Streamlit.

    - HIGH: no special indicator (normal display)
    - MEDIUM: yellow warning badge
    - LOW: red warning badge with tooltip explaining limitations

    Streamlit is imported inside the function to avoid import errors in
    non-Streamlit contexts.
    """
    import streamlit as st

    is_enum = isinstance(confidence_level, ConfidenceLevel)
    level = confidence_level.value if is_enum else confidence_level

    if level == ConfidenceLevel.HIGH.value:
        return
    if level == ConfidenceLevel.MEDIUM.value:
        st.markdown(
            '<span style="background-color:#f0ad4e;color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:0.85em;">中置信度</span>',
            unsafe_allow_html=True,
        )
    elif level == ConfidenceLevel.LOW.value:
        st.markdown(
            '<span title="覆盖不足，仅输出低置信度诊断，不能作为完整联赛排名或前四预测结论"'
            ' style="background-color:#d9534f;color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:0.85em;cursor:help;">低置信度</span>',
            unsafe_allow_html=True,
        )

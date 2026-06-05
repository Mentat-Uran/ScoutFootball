"""Unified low-confidence detection and display for player ratings.

Aggregates multiple confidence signals:
- Minutes played (< 450 = low confidence)
- Missing data dimensions (defense_missing, possession_missing, etc.)
- Position mapping uncertainty (coarse position group)
- Event sample insufficiency (StatsBomb coverage)
- League coverage (< 0.90)
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ConfidenceAssessment:
    """Assessment of a player's rating confidence level."""

    player_name: str
    is_low_confidence: bool
    reasons: tuple[str, ...]
    minutes_played: float | None
    missing_dimensions: tuple[str, ...]
    league_coverage: float | None
    position_confidence: str  # "high", "medium", "low"


MIN_MINUTES_THRESHOLD = 450.0
COARSE_POSITION_GROUPS = {"DF", "MF", "FW"}  # These are coarse; GK/CB/FB/DM/CM/AM/W/ST are fine


def assess_player_confidence(
    player_row: pd.Series,
    *,
    min_minutes: float = MIN_MINUTES_THRESHOLD,
    missing_suffix: str = "_missing",
    coverage_col: str = "coverage",
    position_col: str = "position_group",
) -> ConfidenceAssessment:
    """Assess confidence for a single player based on multiple signals.

    Checks:
    1. Minutes played < min_minutes → low confidence
    2. Any {dimension}_missing == True → low confidence
    3. Position group is coarse (DF/MF/FW) → medium confidence
    4. League coverage < 0.90 → low confidence

    Args:
        player_row: Single row from a DataFrame with player data
        min_minutes: Minimum minutes for high confidence (default 450)
        missing_suffix: Suffix for missing dimension columns
        coverage_col: Column name for league coverage
        position_col: Column name for position group

    Returns:
        ConfidenceAssessment with reasons for low confidence
    """
    reasons: list[str] = []
    missing_dims: list[str] = []

    # 1. Minutes played check
    minutes_val = pd.to_numeric(player_row.get("minutes_played"), errors="coerce")
    minutes_played: float | None = None
    if pd.notna(minutes_val):
        minutes_played = float(minutes_val)
        if minutes_played < min_minutes:
            reasons.append(f"出场时间不足 ({minutes_played:.0f} < {min_minutes:.0f})")

    # 2. Missing dimensions check
    for col in player_row.index:
        if col.endswith(missing_suffix):
            val = player_row[col]
            if val is True or (isinstance(val, (int, float)) and val == 1):
                dim_name = col[: -len(missing_suffix)]
                missing_dims.append(dim_name)
                reasons.append(f"缺失{dim_name}数据")

    # 3. Position confidence
    raw_position = str(player_row.get(position_col, ""))
    if raw_position in COARSE_POSITION_GROUPS:
        position_confidence = "low"
        reasons.append(f"位置分组粗略 ({raw_position})")
    else:
        position_confidence = "high"

    # 4. League coverage check
    coverage_val = pd.to_numeric(player_row.get(coverage_col), errors="coerce")
    league_coverage: float | None = None
    if pd.notna(coverage_val):
        league_coverage = float(coverage_val)
        if league_coverage < 0.90:
            reasons.append(f"联赛覆盖不足 ({league_coverage:.0%})")

    # If position is coarse but no other reasons, it's medium confidence
    is_low = len(reasons) > 0
    only_coarse_position = (
        position_confidence == "low"
        and len(reasons) == 1
        and not missing_dims
        and minutes_played is not None
        and minutes_played >= min_minutes
        and (league_coverage is None or league_coverage >= 0.90)
    )
    if only_coarse_position:
        # Only coarse position → medium, not low
        is_low = False

    return ConfidenceAssessment(
        player_name=str(player_row.get("player_name", "Unknown")),
        is_low_confidence=is_low,
        reasons=tuple(reasons),
        minutes_played=minutes_played,
        missing_dimensions=tuple(missing_dims),
        league_coverage=league_coverage,
        position_confidence=position_confidence,
    )


def assess_batch_confidence(
    df: pd.DataFrame,
    *,
    min_minutes: float = MIN_MINUTES_THRESHOLD,
    missing_suffix: str = "_missing",
    coverage_col: str = "coverage",
    position_col: str = "position_group",
) -> pd.DataFrame:
    """Assess confidence for all players in a DataFrame.

    Adds columns: is_low_confidence, confidence_reasons, missing_dimensions

    Args:
        df: DataFrame with player data
        min_minutes: Minimum minutes for high confidence
        missing_suffix: Suffix for missing dimension columns
        coverage_col: Column name for league coverage
        position_col: Column name for position group

    Returns:
        DataFrame with added confidence columns
    """
    if df.empty:
        result = df.copy()
        result["is_low_confidence"] = pd.Series(dtype=bool)
        result["confidence_reasons"] = pd.Series(dtype=object)
        result["missing_dimensions"] = pd.Series(dtype=object)
        return result

    assessments = df.apply(
        lambda row: assess_player_confidence(
            row,
            min_minutes=min_minutes,
            missing_suffix=missing_suffix,
            coverage_col=coverage_col,
            position_col=position_col,
        ),
        axis=1,
    )

    result = df.copy()
    result["is_low_confidence"] = [a.is_low_confidence for a in assessments]
    result["confidence_reasons"] = [a.reasons for a in assessments]
    result["missing_dimensions"] = [a.missing_dimensions for a in assessments]
    return result


def display_confidence_warnings(assessment: ConfidenceAssessment) -> None:
    """Display confidence warnings in Streamlit.

    Shows appropriate warning messages based on the assessment.
    Uses st.warning for low confidence, st.info for medium.

    Args:
        assessment: Confidence assessment for a player
    """
    import streamlit as st

    if assessment.is_low_confidence:
        reasons_text = "；".join(assessment.reasons)
        st.warning(f"⚠️ 低置信度：{reasons_text}")
    elif assessment.position_confidence == "low":
        st.info("位置分组粗略，评分精度可能受限")

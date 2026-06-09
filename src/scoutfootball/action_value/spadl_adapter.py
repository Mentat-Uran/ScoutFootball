"""SPADL adapter: convert StatsBomb events to internal actions.

This module reads StatsBomb Open Data events from Parquet and converts
them to the InternalAction schema defined in schema.py.

StatsBomb Open Data uses a flat column format:
- event_type: action type name (e.g., "Pass", "Shot")
- player_id, player_name, team_id, team_name: identifiers
- location: [x, y] start coordinates (0-120, 0-80)
- pass_end_location, carry_end_location, shot_end_location: end coords

Current status: P2. Reads events_all.parquet from data/raw/statsbomb_open/.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from scoutfootball.action_value.schema import (
    ActionResult,
    ActionType,
    InternalAction,
    normalize_coordinates,
)

logger = logging.getLogger(__name__)

# StatsBomb action type mapping (flat format)
STATSBOMB_ACTION_MAP: dict[str, ActionType] = {
    "Pass": ActionType.PASS,
    "Ball Receipt*": ActionType.RECEIPT,
    "Carry": ActionType.CARRY,
    "Shot": ActionType.SHOT,
    "Dribble": ActionType.DRIBBLE,
    "Dribbled Past": ActionType.DRIBBLE,
    "Tackle": ActionType.TACKLE,
    "Interception": ActionType.INTERCEPTION,
    "Clearance": ActionType.CLEARANCE,
    "Block": ActionType.BLOCK,
    "Goal Keeper": ActionType.GOALKEEPER,
    "Foul Committed": ActionType.TACKLE,
    "Foul Won": ActionType.RECEIPT,
    "Ball Recovery": ActionType.INTERCEPTION,
    "Dispossessed": ActionType.CARRY,
    "Miscontrol": ActionType.CARRY,
    "50/50": ActionType.TACKLE,
    "Half Start": ActionType.FREEZE,
    "Half End": ActionType.FREEZE,
    "Starting XI": ActionType.FREEZE,
    "Substitution": ActionType.FREEZE,
    "Injury Stoppage": ActionType.FREEZE,
    "Referee Ball-Drop": ActionType.FREEZE,
    "Bad Behaviour": ActionType.FREEZE,
    "Offside": ActionType.FREEZE,
    "Error": ActionType.CARRY,
    "Shield": ActionType.CARRY,
    "Pressure": ActionType.TACKLE,
    "Duel": ActionType.TACKLE,
    "Tactical Shift": ActionType.FREEZE,
}


def load_statsbomb_events(events_path: Path) -> pd.DataFrame:
    """Load StatsBomb events from Parquet."""
    if not events_path.exists():
        logger.warning("StatsBomb events not found at %s", events_path)
        return pd.DataFrame()
    try:
        return pd.read_parquet(events_path)
    except Exception:
        logger.warning("Failed to read StatsBomb events", exc_info=True)
        return pd.DataFrame()


def _parse_location(loc) -> tuple[float, float] | None:
    """Parse a location field (list, tuple, or numpy array) to (x, y)."""
    if loc is None:
        return None
    try:
        import numpy as np
        if isinstance(loc, np.ndarray):
            if len(loc) >= 2:
                return (float(loc[0]), float(loc[1]))
            return None
    except ImportError:
        pass
    if isinstance(loc, (list, tuple)):
        if len(loc) >= 2:
            return (float(loc[0]), float(loc[1]))
        return None
    if isinstance(loc, str):
        try:
            cleaned = loc.strip("[]")
            parts = cleaned.split(",")
            return (float(parts[0].strip()), float(parts[1].strip()))
        except (ValueError, IndexError):
            return None
    return None


def _get_end_location(row: pd.Series, action_type: ActionType) -> tuple[float, float] | None:
    """Get end location based on action type."""
    if action_type == ActionType.PASS:
        return _parse_location(row.get("pass_end_location"))
    elif action_type == ActionType.CARRY:
        return _parse_location(row.get("carry_end_location"))
    elif action_type == ActionType.SHOT:
        return _parse_location(row.get("shot_end_location"))
    elif action_type == ActionType.GOALKEEPER:
        return _parse_location(row.get("goalkeeper_end_location"))
    return None


def _get_result(row: pd.Series, action_type: ActionType) -> ActionResult:
    """Determine action result from the row."""
    # Check pass outcome
    if action_type == ActionType.PASS:
        pass_outcome = row.get("pass_outcome")
        if pd.isna(pass_outcome) or pass_outcome is None:
            return ActionResult.SUCCESS
        return ActionResult.FAILURE

    # Check shot outcome
    if action_type == ActionType.SHOT:
        shot_outcome = row.get("shot_outcome")
        if pd.isna(shot_outcome) or shot_outcome is None:
            return ActionResult.UNKNOWN
        if "Goal" in str(shot_outcome):
            return ActionResult.SUCCESS
        return ActionResult.FAILURE

    return ActionResult.UNKNOWN


def convert_event_to_action(row: pd.Series, match_id: str) -> InternalAction | None:
    """Convert a single StatsBomb event row to an InternalAction.

    Returns None for events that don't map to actionable types (e.g., Half Start).
    """
    event_type = str(row.get("event_type", "Unknown"))
    action_type = STATSBOMB_ACTION_MAP.get(event_type, ActionType.UNKNOWN)

    if action_type in (ActionType.FREEZE, ActionType.UNKNOWN):
        return None

    # Get start location
    start_loc = _parse_location(row.get("location"))
    if start_loc:
        start_x, start_y = normalize_coordinates(start_loc[0], start_loc[1])
    else:
        start_x, start_y = 50.0, 50.0

    # Get end location
    end_loc = _get_end_location(row, action_type)
    if end_loc:
        end_x, end_y = normalize_coordinates(end_loc[0], end_loc[1])
    else:
        end_x, end_y = start_x, start_y

    # Get result
    result = _get_result(row, action_type)

    # Get identifiers
    player_id = str(row.get("player_id", "")) if not pd.isna(row.get("player_id")) else ""
    team_id = str(row.get("team_id", "")) if not pd.isna(row.get("team_id")) else ""

    # Get timing
    period = int(row.get("period", 1)) if not pd.isna(row.get("period")) else 1
    minute = int(row.get("minute", 0)) if not pd.isna(row.get("minute")) else 0
    second = int(row.get("second", 0)) if not pd.isna(row.get("second")) else 0

    # Get action_id
    index = int(row.get("index", 0)) if not pd.isna(row.get("index")) else 0
    event_id = str(row.get("event_id", ""))

    return InternalAction(
        action_id=index,
        provider_action_id=event_id,
        match_id=str(match_id),
        team_id=team_id,
        player_id=player_id,
        period=period,
        minute=minute,
        second=second,
        action_type=action_type,
        result=result,
        start_x=start_x,
        start_y=start_y,
        end_x=end_x,
        end_y=end_y,
        source="statsbomb",
        source_coverage="sample",
    )


def convert_match_events(events_df: pd.DataFrame, match_id: str) -> list[InternalAction]:
    """Convert all events for a single match to internal actions."""
    actions = []
    for _, row in events_df.iterrows():
        action = convert_event_to_action(row, match_id)
        if action is not None:
            actions.append(action)
    return actions


def convert_all_events(events_path: Path) -> list[InternalAction]:
    """Convert all StatsBomb events to internal actions."""
    df = load_statsbomb_events(events_path)
    if df.empty:
        return []

    all_actions = []
    if "match_id" in df.columns:
        for mid, group in df.groupby("match_id"):
            actions = convert_match_events(group, str(mid))
            all_actions.extend(actions)
    else:
        all_actions = convert_match_events(df, "unknown")

    logger.info("Converted %d events to %d internal actions", len(df), len(all_actions))
    return all_actions

"""SPADL adapter: convert StatsBomb events to internal actions.

This module reads StatsBomb Open Data events from Parquet and converts
them to the InternalAction schema defined in schema.py.

Current status: P2 skeleton. Reads events_all.parquet from data/raw/statsbomb_open/.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from scoutfootball.action_value.schema import (
    STATSBOMB_ACTION_MAP,
    ActionResult,
    ActionType,
    InternalAction,
    normalize_coordinates,
    statsbomb_result,
)

logger = logging.getLogger(__name__)


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


def convert_event_to_action(row: pd.Series, match_id: str) -> InternalAction | None:
    """Convert a single StatsBomb event row to an InternalAction.

    Returns None for events that don't map to actionable types (e.g., Half Start).
    """
    event_type = row.get("type", {})
    if isinstance(event_type, dict):
        type_name = event_type.get("name", "Unknown")
    else:
        type_name = str(event_type)

    action_type = STATSBOMB_ACTION_MAP.get(type_name, ActionType.UNKNOWN)
    if action_type in (ActionType.FREEZE, ActionType.UNKNOWN):
        return None

    # Get location
    location = row.get("location", [None, None])
    if isinstance(location, list) and len(location) >= 2:
        start_x, start_y = location[0], location[1]
    else:
        start_x, start_y = 50.0, 50.0

    # Get end location (for passes, shots, carries)
    end_location = row.get("end_location", [start_x, start_y])
    if isinstance(end_location, list) and len(end_location) >= 2:
        end_x, end_y = end_location[0], end_location[1]
    else:
        end_x, end_y = start_x, start_y

    # Normalize coordinates
    if start_x is not None and start_y is not None:
        start_x, start_y = normalize_coordinates(float(start_x), float(start_y))
    else:
        start_x, start_y = 50.0, 50.0
    if end_x is not None and end_y is not None:
        end_x, end_y = normalize_coordinates(float(end_x), float(end_y))
    else:
        end_x, end_y = start_x, start_y

    # Get result
    outcome = row.get("pass", {}).get("outcome") or row.get("shot", {}).get("outcome")
    if isinstance(outcome, dict):
        result = statsbomb_result(outcome)
    else:
        result = ActionResult.UNKNOWN

    # Get player/team
    player = row.get("player", {})
    player_id = (str(player.get("id", ""))
                 if isinstance(player, dict)
                 else str(row.get("player_id", "")))
    team = row.get("team", {})
    team_id = str(team.get("id", "")) if isinstance(team, dict) else str(row.get("team_id", ""))

    # Get timing
    period = int(row.get("period", 1))
    minute = int(row.get("minute", 0))
    second = int(row.get("second", 0))

    # Get action_id
    event_id = str(row.get("id", ""))
    index = int(row.get("index", 0))

    return InternalAction(
        action_id=index,
        provider_action_id=event_id,
        match_id=match_id,
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

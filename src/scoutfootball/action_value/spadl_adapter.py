"""StatsBomb event adapter: convert flat events to internal actions.

This module reads StatsBomb Open Data events from Parquet and converts
them to the InternalAction schema defined in schema.py.

StatsBomb Open Data uses a flat column format:
- event_type: action type name (e.g., "Pass", "Shot")
- player_id, player_name, team_id, team_name: identifiers
- location_x, location_y: start coordinates (0-120, 0-80)
- pass_end_location_x/y, shot_end_location_x/y: end coords

This is a SPADL-informed internal representation, not a claim that the
result is a complete canonical SPADL or atomic-SPADL export.  In particular,
the converter does not infer an attacking direction or reconstruct provider
fields that were not retained in the flat source artifact.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scoutfootball.action_value.schema import (
    STATSBOMB_ACTION_MAP,
    ActionResult,
    ActionType,
    InternalAction,
)

logger = logging.getLogger(__name__)

# Event types that map to FREEZE or UNKNOWN — skip these entirely
_SKIP_TYPES: set[ActionType] = {ActionType.FREEZE, ActionType.UNKNOWN}

# These fields are required to preserve event identity, match scope, ordering,
# and the source coordinate frame.  Optional event-specific end locations may
# be absent (for example some goalkeeper events); those retain the existing
# same-as-start fallback and must not be interpreted as an observed endpoint.
_REQUIRED_EVENT_COLUMNS = frozenset({
    "event_id",
    "match_id",
    "event_type",
    "period",
    "minute",
    "second",
    "location_x",
    "location_y",
})


class EventConversionError(ValueError):
    """Raised when a flat event artifact cannot safely become actions."""


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


def _validate_events(events: pd.DataFrame) -> None:
    """Fail closed on missing event identity, timing, or retained coordinates."""
    missing = sorted(_REQUIRED_EVENT_COLUMNS.difference(events.columns))
    if missing:
        raise EventConversionError(
            "StatsBomb event artifact is missing required columns: "
            + ", ".join(missing)
        )

    for column in ("event_id", "match_id", "event_type"):
        values = events[column]
        if values.isna().any() or values.astype(str).str.strip().eq("").any():
            raise EventConversionError(
                f"StatsBomb event artifact has blank {column} values."
            )

    if events["event_id"].duplicated().any():
        raise EventConversionError(
            "StatsBomb event artifact has duplicate event_id values; "
            "provider action identity would not be preserved."
        )

    bounds = {"period": (1, None), "minute": (0, None), "second": (0, 59)}
    for column, (minimum, maximum) in bounds.items():
        values = pd.to_numeric(events[column], errors="coerce")
        invalid = (
            values.isna()
            | ~np.isfinite(values)
            | (values < minimum)
            | (values % 1 != 0)
        )
        if maximum is not None:
            invalid |= values > maximum
        if invalid.any():
            raise EventConversionError(
                f"StatsBomb event artifact has invalid {column} values."
            )


def _validate_action_coordinates(events: pd.DataFrame) -> None:
    """Ensure converted actions have finite coordinates in the StatsBomb frame."""
    for column, upper_bound in (("location_x", 120.0), ("location_y", 80.0)):
        values = pd.to_numeric(events[column], errors="coerce")
        invalid = values.isna() | ~np.isfinite(values) | (values < 0) | (values > upper_bound)
        if invalid.any():
            raise EventConversionError(
                f"Convertible StatsBomb events contain invalid {column} values."
            )


def _determine_result_vectorized(df: pd.DataFrame) -> pd.Series:
    """Determine action result for each row using vectorized logic.

    Rules:
    - pass: no pass_outcome_name → success; otherwise → failure
    - shot: shot_outcome_name contains "Goal" → success; otherwise → failure
    - dribble: check dribble_outcome_name for "Complete" → success; else → failure
    - tackle: check dribble_outcome_name or tackle_outcome_name for "Won" → success; else → failure
    - interception: default success
    - clearance: default success
    - block: default success
    - own goal: success
    - others: unknown
    """
    result = pd.Series("unknown", index=df.index, dtype="object")

    action_type = df["_action_type"]

    # Pass
    is_pass = action_type == ActionType.PASS
    pass_outcome = df.get("pass_outcome_name")
    if pass_outcome is not None:
        result[is_pass & pass_outcome.isna()] = ActionResult.SUCCESS
        result[is_pass & pass_outcome.notna()] = ActionResult.FAILURE
    else:
        result[is_pass] = ActionResult.SUCCESS

    # Shot
    is_shot = action_type == ActionType.SHOT
    shot_outcome = df.get("shot_outcome_name")
    if shot_outcome is not None:
        goal_mask = shot_outcome.fillna("").str.contains("Goal", na=False)
        result[is_shot & goal_mask] = ActionResult.SUCCESS
        result[is_shot & ~goal_mask] = ActionResult.FAILURE
    else:
        result[is_shot] = ActionResult.FAILURE

    # Dribble: check dribble_outcome_name if available
    is_dribble = action_type == ActionType.DRIBBLE
    dribble_outcome = df.get("dribble_outcome_name")
    if dribble_outcome is not None:
        complete_mask = dribble_outcome.fillna("").str.contains("Complete", na=False)
        result[is_dribble & complete_mask] = ActionResult.SUCCESS
        result[is_dribble & ~complete_mask] = ActionResult.FAILURE
    else:
        # No outcome column available — default to failure (most dribbles in open data
        # are incomplete without explicit outcome)
        result[is_dribble] = ActionResult.FAILURE

    # Tackle: check tackle_outcome_name if available
    is_tackle = action_type == ActionType.TACKLE
    tackle_outcome = df.get("tackle_outcome_name")
    if tackle_outcome is not None:
        won_mask = tackle_outcome.fillna("").str.contains("Won", na=False)
        result[is_tackle & won_mask] = ActionResult.SUCCESS
        result[is_tackle & ~won_mask] = ActionResult.FAILURE
    else:
        result[is_tackle] = ActionResult.FAILURE

    # Interception: default success
    result[action_type == ActionType.INTERCEPTION] = ActionResult.SUCCESS

    # Clearance: default success
    result[action_type == ActionType.CLEARANCE] = ActionResult.SUCCESS

    # Block: default success
    result[action_type == ActionType.BLOCK] = ActionResult.SUCCESS

    return result


def _get_end_location_vectorized(df: pd.DataFrame) -> pd.DataFrame:
    """Compute end_x, end_y for each row using vectorized logic.

    Priority:
    - pass: pass_end_location_x/y
    - shot: shot_end_location_x/y
    - carry: carry_end_location_x/y (if missing, fallback to start location)
    - goalkeeper: goalkeeper_end_location_x/y (if missing, fallback to start)
    - others: same as start location
    """
    start_x = df["_start_x"].values
    start_y = df["_start_y"].values
    action_type = df["_action_type"]

    end_x = start_x.copy()
    end_y = start_y.copy()

    # Pass end location
    is_pass = action_type == ActionType.PASS
    pass_end_x = df.get("pass_end_location_x")
    pass_end_y = df.get("pass_end_location_y")
    if pass_end_x is not None and pass_end_y is not None:
        valid = is_pass & pass_end_x.notna() & pass_end_y.notna()
        end_x[valid] = pass_end_x[valid].values / 120.0 * 100.0
        end_y[valid] = pass_end_y[valid].values / 80.0 * 100.0

    # Shot end location
    is_shot = action_type == ActionType.SHOT
    shot_end_x = df.get("shot_end_location_x")
    shot_end_y = df.get("shot_end_location_y")
    if shot_end_x is not None and shot_end_y is not None:
        valid = is_shot & shot_end_x.notna() & shot_end_y.notna()
        end_x[valid] = shot_end_x[valid].values / 120.0 * 100.0
        end_y[valid] = shot_end_y[valid].values / 80.0 * 100.0

    # Carry end location — fallback to start location if missing
    is_carry = action_type == ActionType.CARRY
    carry_end_x = df.get("carry_end_location_x")
    carry_end_y = df.get("carry_end_location_y")
    if carry_end_x is not None and carry_end_y is not None:
        valid = is_carry & carry_end_x.notna() & carry_end_y.notna()
        end_x[valid] = carry_end_x[valid].values / 120.0 * 100.0
        end_y[valid] = carry_end_y[valid].values / 80.0 * 100.0
    # If carry_end_location columns don't exist, end_x/y already = start_x/y

    # Goalkeeper end location — fallback to start if missing
    is_gk = action_type == ActionType.GOALKEEPER
    gk_end_x = df.get("goalkeeper_end_location_x")
    gk_end_y = df.get("goalkeeper_end_location_y")
    if gk_end_x is not None and gk_end_y is not None:
        valid = is_gk & gk_end_x.notna() & gk_end_y.notna()
        end_x[valid] = gk_end_x[valid].values / 120.0 * 100.0
        end_y[valid] = gk_end_y[valid].values / 80.0 * 100.0

    return pd.DataFrame({"_end_x": end_x, "_end_y": end_y}, index=df.index)


def convert_events(events: pd.DataFrame) -> pd.DataFrame:
    """Convert a flat StatsBomb event frame to internal actions.

    The conversion keeps the provider event ID, generates a deterministic
    zero-based ``action_id`` within each match in input order, and fails closed
    when identity, timing, or coordinates for a convertible event are invalid.
    It does not orient actions to a single attacking direction.
    """
    if events.empty:
        return pd.DataFrame()

    _validate_events(events)
    df = events.copy()

    # Map event_type → ActionType
    df["_action_type"] = df["event_type"].map(STATSBOMB_ACTION_MAP).fillna(ActionType.UNKNOWN)

    # Filter out FREEZE and UNKNOWN types
    mask = ~df["_action_type"].isin(_SKIP_TYPES)
    df = df.loc[mask].copy()

    if df.empty:
        logger.info("No actionable events after filtering")
        return pd.DataFrame()

    _validate_action_coordinates(df)

    # Normalize start coordinates
    loc_x = df.get("location_x", pd.Series(np.nan, index=df.index))
    loc_y = df.get("location_y", pd.Series(np.nan, index=df.index))
    df["_start_x"] = loc_x.fillna(60.0) / 120.0 * 100.0
    df["_start_y"] = loc_y.fillna(40.0) / 80.0 * 100.0

    # Compute end locations
    end_locs = _get_end_location_vectorized(df)
    df["_end_x"] = end_locs["_end_x"]
    df["_end_y"] = end_locs["_end_y"]

    # Determine results
    df["_result"] = _determine_result_vectorized(df)

    # Build output DataFrame
    player_id = df.get("player_id", pd.Series("", index=df.index))
    team_id = df.get("team_id", pd.Series("", index=df.index))
    match_id = df.get("match_id", pd.Series("", index=df.index))

    out = pd.DataFrame({
        "action_id": df.groupby("match_id", sort=False).cumcount().astype(int),
        "provider_action_id": df["event_id"].astype(str),
        "match_id": match_id.fillna("").astype(str),
        "team_id": team_id.fillna("").apply(
            lambda x: str(int(float(x))) if pd.notna(x) and x != "" else ""
        ),
        "player_id": player_id.fillna("").apply(
            lambda x: str(int(float(x))) if pd.notna(x) and x != "" else ""
        ),
        "period": df.get("period", pd.Series(1, index=df.index)).fillna(1).astype(int),
        "minute": df.get("minute", pd.Series(0, index=df.index)).fillna(0).astype(int),
        "second": df.get("second", pd.Series(0, index=df.index)).fillna(0).astype(int),
        "action_type": df["_action_type"].astype(str),
        "result": df["_result"].astype(str),
        "start_x": df["_start_x"].round(2),
        "start_y": df["_start_y"].round(2),
        "end_x": df["_end_x"].round(2),
        "end_y": df["_end_y"].round(2),
        "body_part": "foot",
        "source": "statsbomb",
        "source_coverage": "sample",
    })

    # Drop temp columns
    out.reset_index(drop=True, inplace=True)

    logger.info("Converted %d events to %d internal actions", len(df), len(out))
    return out


def convert_all_events(events_path: Path) -> pd.DataFrame:
    """Load a StatsBomb Parquet artifact and convert it to internal actions."""
    return convert_events(load_statsbomb_events(events_path))


def convert_all_events_to_actions(events_path: Path) -> list[InternalAction]:
    """Convert all StatsBomb events to InternalAction objects.

    Convenience wrapper that returns a list of InternalAction dataclass instances.
    For large datasets, prefer convert_all_events() which returns a DataFrame.
    """
    df = convert_all_events(events_path)
    if df.empty:
        return []

    actions = []
    for _, row in df.iterrows():
        actions.append(InternalAction(
            action_id=int(row["action_id"]),
            provider_action_id=str(row["provider_action_id"]),
            match_id=str(row["match_id"]),
            team_id=str(row["team_id"]),
            player_id=str(row["player_id"]),
            period=int(row["period"]),
            minute=int(row["minute"]),
            second=int(row["second"]),
            action_type=ActionType(row["action_type"]),
            result=ActionResult(row["result"]),
            start_x=float(row["start_x"]),
            start_y=float(row["start_y"]),
            end_x=float(row["end_x"]),
            end_y=float(row["end_y"]),
            source="statsbomb",
            source_coverage="sample",
        ))
    return actions


def save_spadl_actions(events_path: Path, output_path: Path) -> pd.DataFrame:
    """Convert StatsBomb events to internal actions and save as Parquet.

    Returns the DataFrame for inspection.
    """
    df = convert_all_events(events_path)
    if df.empty:
        logger.warning("No SPADL actions to save")
        return df

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info("Saved %d SPADL actions to %s", len(df), output_path)
    return df

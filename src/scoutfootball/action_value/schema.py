"""Internal actions schema for ScoutFootball.

Defines the standardized action representation that all data sources
(StatsBomb, etc.) are converted into before computing xT/VAEP.

Coordinate system: 0-100 normalized (x: left-to-right, y: bottom-to-top).
Direction: always attack-to-defense (left-to-right after normalization).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ActionType(StrEnum):
    """Standardized action types (SPADL-compatible)."""
    PASS = "pass"
    DRIBBLE = "dribble"
    SHOT = "shot"
    FREEZE = "freeze"  # stoppage / no action
    TAKE_ON = "take_on"
    CLEARANCE = "clearance"
    INTERCEPTION = "interception"
    TACKLE = "tackle"
    BLOCK = "block"
    GOALKEEPER = "goalkeeper"
    RECEIPT = "receipt"
    CARRY = "carry"
    UNKNOWN = "unknown"


class ActionResult(StrEnum):
    """Standardized action outcomes."""
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class InternalAction:
    """A single standardized action.

    Fields:
        action_id: unique identifier within the match
        provider_action_id: original action ID from the data source
        match_id: match identifier
        team_id: team identifier
        player_id: player identifier
        period: 1=first half, 2=second half, etc.
        minute: minute of the action
        second: second within the minute
        action_type: standardized action type
        result: action outcome
        start_x: starting x coordinate (0-100)
        start_y: starting y coordinate (0-100)
        end_x: ending x coordinate (0-100)
        end_y: ending y coordinate (0-100)
        body_part: body part used (foot, head, other)
        qualifier: additional metadata from the source
        source: data provider name (e.g., "statsbomb")
        source_coverage: coverage flag for this action type
    """
    action_id: int
    provider_action_id: str
    match_id: str
    team_id: str
    player_id: str
    period: int
    minute: int
    second: int
    action_type: ActionType
    result: ActionResult
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    body_part: str = "foot"
    qualifier: dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    source_coverage: str = "full"  # "full", "partial", "sample"


@dataclass
class ActionSequence:
    """A sequence of actions representing a possession or phase."""
    match_id: str
    team_id: str
    actions: list[InternalAction]
    start_minute: int = 0
    end_minute: int = 0
    outcome: str = "unknown"  # "goal", "shot", "turnover", "other"


# StatsBomb action type mapping
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
    "Pressure": ActionType.TACKLE,
    "Duel": ActionType.TACKLE,
    "Half Start": ActionType.FREEZE,
    "Half End": ActionType.FREEZE,
    "Starting XI": ActionType.FREEZE,
    "Substitution": ActionType.FREEZE,
    "Injury Stoppage": ActionType.FREEZE,
    "Referee Ball-Drop": ActionType.FREEZE,
    "Bad Behaviour": ActionType.FREEZE,
    "Offside": ActionType.FREEZE,
    "Tactical Shift": ActionType.FREEZE,
    "Player On": ActionType.FREEZE,
    "Player Off": ActionType.FREEZE,
    "Camera On": ActionType.FREEZE,
    "Camera off": ActionType.FREEZE,
    "Own Goal For": ActionType.SHOT,
    "Own Goal Against": ActionType.SHOT,
    "Error": ActionType.CARRY,
    "Shield": ActionType.CARRY,
}


def statsbomb_result(outcome: dict | None) -> ActionResult:
    """Convert StatsBomb outcome dict to ActionResult."""
    if outcome is None:
        return ActionResult.UNKNOWN
    name = outcome.get("name", "")
    if name in ("Complete", "Won", "Success", "Complete To Team"):
        return ActionResult.SUCCESS
    if name in ("Incomplete", "Lost", "Out"):
        return ActionResult.FAILURE
    return ActionResult.UNKNOWN


def normalize_coordinates(x: float, y: float) -> tuple[float, float]:
    """Convert StatsBomb coordinates (0-120, 0-80) to normalized (0-100, 0-100)."""
    return (x / 120.0 * 100.0, y / 80.0 * 100.0)

"""Internal match and tracking schema for ScoutFootball.

Defines the standardized match, event and tracking representations
that all data sources (StatsBomb, Metrica, etc.) are converted into.

Coordinate system: 0-100 normalized (x: left-to-right, y: bottom-to-top).
Direction: always attack-to-defense (left-to-right after normalization).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MatchStatus(StrEnum):
    """Match status."""
    SCHEDULED = "scheduled"
    LIVE = "live"
    COMPLETED = "completed"
    POSTPONED = "postponed"
    ABANDONED = "abandoned"


class PeriodType(StrEnum):
    """Period within a match."""
    FIRST_HALF = "1H"
    SECOND_HALF = "2H"
    EXTRA_TIME_1 = "ET1"
    EXTRA_TIME_2 = "ET2"
    PENALTY_SHOOTOUT = "PS"


@dataclass(frozen=True)
class InternalMatch:
    """A single standardized match.

    Fields:
        match_id: unique match identifier
        provider_match_id: original match ID from the data source
        competition: competition name
        season: season identifier (e.g., "2526")
        match_date: match date in ISO format
        home_team_id: home team identifier
        away_team_id: away team identifier
        home_score: goals scored by home team
        away_score: goals scored by away team
        status: match status
        venue: stadium/venue name
        referee: referee name
        source: data provider name
        source_coverage: coverage confidence level
    """
    match_id: str
    provider_match_id: str
    competition: str
    season: str
    match_date: str
    home_team_id: str
    away_team_id: str
    home_score: int = 0
    away_score: int = 0
    status: MatchStatus = MatchStatus.SCHEDULED
    venue: str = ""
    referee: str = ""
    source: str = "unknown"
    source_coverage: str = "full"


@dataclass(frozen=True)
class InternalEvent:
    """A single standardized event (higher-level than action).

    Events represent on-the-ball actions plus off-the-ball events
    (substitutions, cards, tactical shifts). This is the match-level
    event schema; action-level detail is in action_value.schema.

    Fields:
        event_id: unique event identifier within the match
        provider_event_id: original event ID from the data source
        match_id: match identifier
        team_id: team identifier
        player_id: player identifier (empty for team-level events)
        period: match period
        minute: minute of the event
        second: second within the minute
        event_type: standardized event type name
        outcome: event outcome (success/failure/unknown)
        start_x: starting x coordinate (0-100)
        start_y: starting y coordinate (0-100)
        end_x: ending x coordinate (0-100)
        end_y: ending y coordinate (0-100)
        body_part: body part used
        qualifier: additional metadata from the source
        source: data provider name
        source_coverage: coverage flag for this event type
    """
    event_id: str
    provider_event_id: str
    match_id: str
    team_id: str
    player_id: str
    period: PeriodType = PeriodType.FIRST_HALF
    minute: int = 0
    second: int = 0
    event_type: str = "unknown"
    outcome: str = "unknown"
    start_x: float = 50.0
    start_y: float = 50.0
    end_x: float = 50.0
    end_y: float = 50.0
    body_part: str = ""
    qualifier: dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    source_coverage: str = "full"


@dataclass(frozen=True)
class TrackingFrame:
    """A single tracking frame (freeze-frame or full tracking).

    Fields:
        frame_id: unique frame identifier
        match_id: match identifier
        period: match period
        minute: minute of the frame
        second: second within the minute
        players: list of player positions in this frame
        ball_x: ball x coordinate (0-100)
        ball_y: ball y coordinate (0-100)
        ball_z: ball z coordinate (height, 0 = ground)
        home_possession: whether home team has possession
        source: data provider name
        source_coverage: coverage flag
    """
    frame_id: int
    match_id: str
    period: PeriodType = PeriodType.FIRST_HALF
    minute: int = 0
    second: int = 0
    players: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    ball_x: float = 50.0
    ball_y: float = 50.0
    ball_z: float = 0.0
    home_possession: bool = True
    source: str = "unknown"
    source_coverage: str = "sample"


@dataclass
class InternalLineup:
    """Starting lineup and substitutes for a team in a match.

    Fields:
        match_id: match identifier
        team_id: team identifier
        formation: formation string (e.g., "4-3-3")
        starting_players: list of starting player identifiers
        substitutes: list of substitute player identifiers
        source: data provider name
    """
    match_id: str
    team_id: str
    formation: str = ""
    starting_players: list[str] = field(default_factory=list)
    substitutes: list[str] = field(default_factory=list)
    source: str = "unknown"

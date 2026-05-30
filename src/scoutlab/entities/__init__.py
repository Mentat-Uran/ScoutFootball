"""Entities package for canonical IDs and bridge-table logic."""

from .bridge_builders import BridgeBuildResult, match_players, match_teams
from .normalize import (
    normalize_country_name,
    normalize_person_name,
    normalize_position_group,
    normalize_team_name,
)

__all__ = [
    "BridgeBuildResult",
    "match_players",
    "match_teams",
    "normalize_country_name",
    "normalize_person_name",
    "normalize_position_group",
    "normalize_team_name",
]

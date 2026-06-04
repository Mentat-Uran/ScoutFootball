"""Entities package for canonical IDs and bridge-table logic."""

from .bridge_builders import BridgeBuildResult, match_players, match_teams
from .normalize import (
    build_player_composite_key,
    fuzzy_match_player_key,
    normalize_country_name,
    normalize_person_name,
    normalize_position_group,
    normalize_team_name,
)

__all__ = [
    "BridgeBuildResult",
    "build_player_composite_key",
    "fuzzy_match_player_key",
    "match_players",
    "match_teams",
    "normalize_country_name",
    "normalize_person_name",
    "normalize_position_group",
    "normalize_team_name",
]

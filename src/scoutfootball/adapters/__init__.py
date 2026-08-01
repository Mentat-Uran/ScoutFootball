"""Adapters package for external sources and manual imports."""

from .api_football import ApiKeyMissingError, fetch_coaches, fetch_injuries, fetch_transfers
from .base import AdapterResult, SourceMetadata
from .capology import fetch_player_salaries
from .clubelo import fetch_elo_by_date
from .fbref import fetch_player_standard
from .football_data import download_csv
from .manifest import AdapterCapability, AdapterManifest, AdapterRegistry, SchemaMapping
from .registry import build_adapter_registry
from .sofascore import fetch_player_match_stats, fetch_team_match_stats
from .sofifa import fetch_player_attributes
from .statsbomb_open import load_events, load_lineups, load_matches
from .transfermarkt_datasets import (
    download_duckdb,
    export_priority_tables,
    export_table,
    load_csv_table,
)
from .transfermarkt_manual import load_snapshot
from .understat import fetch_league_players
from .whoscored import fetch_match_events, fetch_missing_players, fetch_player_match_ratings

__all__ = [
    "AdapterCapability",
    "AdapterManifest",
    "AdapterRegistry",
    "AdapterResult",
    "ApiKeyMissingError",
    "SchemaMapping",
    "SourceMetadata",
    "build_adapter_registry",
    "download_csv",
    "download_duckdb",
    "export_priority_tables",
    "export_table",
    "fetch_coaches",
    "fetch_elo_by_date",
    "fetch_injuries",
    "fetch_league_players",
    "fetch_player_attributes",
    "fetch_player_match_ratings",
    "fetch_player_match_stats",
    "fetch_player_salaries",
    "fetch_team_match_stats",
    "fetch_match_events",
    "fetch_missing_players",
    "fetch_player_standard",
    "fetch_transfers",
    "load_csv_table",
    "load_snapshot",
    "load_events",
    "load_lineups",
    "load_matches",
]

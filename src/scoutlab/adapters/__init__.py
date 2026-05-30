"""Adapters package for external sources and manual imports."""

from .base import AdapterResult, SourceMetadata
from .clubelo import fetch_elo_by_date
from .fbref import fetch_player_standard
from .football_data import download_csv
from .statsbomb_open import load_events, load_lineups, load_matches
from .transfermarkt_manual import load_snapshot
from .understat import fetch_league_players

__all__ = [
    "AdapterResult",
    "SourceMetadata",
    "download_csv",
    "fetch_elo_by_date",
    "fetch_league_players",
    "fetch_player_standard",
    "load_snapshot",
    "load_events",
    "load_lineups",
    "load_matches",
]

"""Understat adapter."""

from __future__ import annotations

import json

import pandas as pd

from scoutfootball.adapters.base import AdapterResult
from scoutfootball.adapters.common import (
    CachedHttpClient,
    SourceSchemaError,
    with_record_count,
)
from scoutfootball.config import PlatformSettings

SOURCE_NAME = "understat"
PARSER_VERSION = "understat/v0.1.0"
BASE_URL = "https://understat.com"
LEAGUE_HEADERS = {
    "User-Agent": "football-data-platform/0.1.0",
    "X-Requested-With": "XMLHttpRequest",
}
REQUIRED_PLAYER_FIELDS = (
    "id",
    "player_name",
    "team_title",
    "games",
    "time",
    "xG",
    "xA",
    "npxG",
    "xGChain",
    "xGBuildup",
)


def fetch_league_players(
    league: str,
    season: int,
    *,
    client: CachedHttpClient | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Fetch league-level Understat player stats."""

    resolved_settings = settings or PlatformSettings.from_root()
    resolved_client = client or CachedHttpClient(settings=resolved_settings)
    normalized_league = _normalize_league(league)
    source_uri = f"{BASE_URL}/getLeagueData/{normalized_league}/{season}"
    cache_path = resolved_settings.raw_root / SOURCE_NAME / normalized_league / f"{season}.json"
    artifact = resolved_client.fetch(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        cache_path=cache_path,
        parser_version=PARSER_VERSION,
        force_refresh=force_refresh,
        request_headers=LEAGUE_HEADERS,
    )
    payload = _decode_league_payload(artifact.payload)
    players = payload.get("players")
    if not isinstance(players, list):
        raise SourceSchemaError("Understat league payload must contain a players list")
    if not players:
        raise SourceSchemaError("Understat league payload contains no players")
    missing = tuple(field for field in REQUIRED_PLAYER_FIELDS if field not in players[0])
    if missing:
        missing_text = ", ".join(missing)
        raise SourceSchemaError(f"Understat players payload is missing fields: {missing_text}")
    frame = pd.DataFrame.from_records(players)
    metadata = with_record_count(artifact.metadata, len(frame))
    return AdapterResult(dataframe=frame, metadata=metadata)


def _normalize_league(league: str) -> str:
    normalized = league.strip().replace(" ", "_")
    if not normalized:
        raise ValueError("league must be a non-empty Understat league name such as 'EPL'")
    return normalized


def _decode_league_payload(payload: bytes) -> dict:
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceSchemaError("Understat league payload is not valid UTF-8 JSON") from error
    if not isinstance(decoded, dict):
        raise SourceSchemaError("Understat league payload must decode to a JSON object")
    return decoded

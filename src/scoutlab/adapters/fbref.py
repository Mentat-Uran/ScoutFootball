"""FBref adapter for low-frequency standard player tables."""

from __future__ import annotations

import re
from io import StringIO

import pandas as pd

from scoutlab.adapters.base import AdapterResult
from scoutlab.adapters.common import (
    CachedHttpClient,
    SourceSchemaError,
    with_record_count,
)
from scoutlab.config import PlatformSettings

SOURCE_NAME = "fbref"
PARSER_VERSION = "fbref/v0.1.0"
FBREF_RATE_LIMIT_SECONDS = 6.5
TABLE_ID = "stats_standard"
FBREF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
LEAGUE_MAPPINGS = {
    "ENG-Premier League": {"comp_id": 9, "slug": "Premier-League"},
    "Premier League": {"comp_id": 9, "slug": "Premier-League"},
    "ENG-Championship": {"comp_id": 10, "slug": "Championship"},
    "Championship": {"comp_id": 10, "slug": "Championship"},
    "ESP-La Liga": {"comp_id": 12, "slug": "La-Liga"},
    "La Liga": {"comp_id": 12, "slug": "La-Liga"},
    "GER-Bundesliga": {"comp_id": 20, "slug": "Bundesliga"},
    "Bundesliga": {"comp_id": 20, "slug": "Bundesliga"},
    "ITA-Serie A": {"comp_id": 11, "slug": "Serie-A"},
    "Serie A": {"comp_id": 11, "slug": "Serie-A"},
    "FRA-Ligue 1": {"comp_id": 13, "slug": "Ligue-1"},
    "Ligue 1": {"comp_id": 13, "slug": "Ligue-1"},
    "POR-Primeira Liga": {"comp_id": 32, "slug": "Primeira-Liga"},
    "Primeira Liga": {"comp_id": 32, "slug": "Primeira-Liga"},
    "NED-Eredivisie": {"comp_id": 23, "slug": "Eredivisie"},
    "Eredivisie": {"comp_id": 23, "slug": "Eredivisie"},
    "TUR-Süper Lig": {"comp_id": 26, "slug": "Super-Lig"},
    "Süper Lig": {"comp_id": 26, "slug": "Super-Lig"},
    "SCO-Scottish Premiership": {"comp_id": 24, "slug": "Scottish-Premiership"},
    "Scottish Premiership": {"comp_id": 24, "slug": "Scottish-Premiership"},
    "BEL-First Division A": {"comp_id": 22, "slug": "First-Division-A"},
    "First Division A": {"comp_id": 22, "slug": "First-Division-A"},
}


def fetch_player_standard(
    leagues: list[str],
    seasons: list[int],
    *,
    client: CachedHttpClient | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Fetch low-frequency FBref player standard tables for league-season pairs."""

    if not leagues:
        raise ValueError("leagues must contain at least one league identifier")
    if not seasons:
        raise ValueError("seasons must contain at least one season start year")

    resolved_settings = settings or PlatformSettings.from_root()
    resolved_client = client or CachedHttpClient(
        settings=resolved_settings,
        rate_limit_seconds=FBREF_RATE_LIMIT_SECONDS,
    )
    frames: list[pd.DataFrame] = []
    source_uris: list[str] = []
    source_hashes: list[str] = []
    request_logs = []
    cache_paths: list[str] = []

    for league in leagues:
        mapping = _resolve_league_mapping(league)
        for season in seasons:
            season_slug = _season_slug(season)
            source_uri = (
                f"https://fbref.com/en/comps/{mapping['comp_id']}/{season_slug}/stats/"
                f"{season_slug}-{mapping['slug']}-Stats"
            )
            cache_path = (
                resolved_settings.raw_root
                / SOURCE_NAME
                / mapping["slug"]
                / season_slug
                / "stats_standard.html"
            )
            artifact = resolved_client.fetch(
                source_name=SOURCE_NAME,
                source_uri=source_uri,
                cache_path=cache_path,
                parser_version=PARSER_VERSION,
                force_refresh=force_refresh,
                request_headers=FBREF_HEADERS,
            )
            frame = _parse_standard_table(artifact.payload)
            frame["league"] = league
            frame["season"] = season
            frames.append(frame)
            source_uris.append(source_uri)
            source_hashes.append(artifact.metadata.source_file_sha256)
            request_logs.append(artifact.metadata.request_log)
            cache_paths.append(str(cache_path))

    combined = pd.concat(frames, ignore_index=True, sort=False)
    metadata = with_record_count(artifact.metadata, len(combined))
    metadata = type(metadata)(
        source_name=metadata.source_name,
        source_uri="|".join(source_uris),
        cache_path=artifact.metadata.cache_path,
        parser_version=metadata.parser_version,
        source_file_sha256="|".join(source_hashes),
        request_log=request_logs[-1],
        record_count=metadata.record_count,
    )
    return AdapterResult(dataframe=combined, metadata=metadata)


def _resolve_league_mapping(league: str) -> dict[str, str | int]:
    mapping = LEAGUE_MAPPINGS.get(league)
    if mapping is None:
        raise ValueError(f"Unsupported FBref league identifier: {league}")
    return mapping


def _season_slug(season: int) -> str:
    if season < 1900:
        raise ValueError("season must be a four-digit start year such as 2025")
    return f"{season}-{season + 1}"


def _parse_standard_table(payload: bytes) -> pd.DataFrame:
    html = payload.decode("utf-8", errors="replace")
    tables = _read_tables(html)
    if not tables:
        uncommented = re.sub(r"<!--|-->", "", html)
        tables = _read_tables(uncommented)
    if not tables:
        raise SourceSchemaError("FBref standard stats table was not found in the HTML payload")
    frame = tables[0]
    frame.columns = _flatten_columns(frame.columns)
    frame = frame.loc[~frame.iloc[:, 0].astype(str).eq("Rk")].reset_index(drop=True)
    if "Player" not in frame.columns:
        raise SourceSchemaError("FBref standard stats table is missing the Player column")
    return frame


def _read_tables(html: str) -> list[pd.DataFrame]:
    try:
        return pd.read_html(StringIO(html), attrs={"id": TABLE_ID}, flavor="lxml")
    except ValueError:
        return []


def _flatten_columns(columns: pd.Index) -> list[str]:
    flattened: list[str] = []
    for column in columns.tolist():
        if isinstance(column, tuple):
            parts = [
                str(part) for part in column if str(part) and not str(part).startswith("Unnamed")
            ]
            flattened.append("_".join(parts) if parts else str(column[-1]))
        else:
            flattened.append(str(column))
    return flattened

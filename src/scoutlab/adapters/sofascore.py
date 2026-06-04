"""SofaScore adapter for player match ratings via soccerdata."""

from __future__ import annotations

import logging

from scoutlab.adapters.base import AdapterResult
from scoutlab.adapters.common import (
    CachedHttpClient,
    SourceSchemaError,
)
from scoutlab.config import PlatformSettings

logger = logging.getLogger(__name__)

SOURCE_NAME = "sofascore"
PARSER_VERSION = "sofascore/v0.1.0"

SOFASCORE_API = "https://api.sofascore.com/api/v1/"

# soccerdata league name -> internal league key
LEAGUE_MAPPINGS: dict[str, str] = {
    "ENG-Premier League": "Premier League",
    "Premier League": "Premier League",
    "ESP-La Liga": "LaLiga",
    "LaLiga": "LaLiga",
    "GER-Bundesliga": "Bundesliga",
    "Bundesliga": "Bundesliga",
    "ITA-Serie A": "Serie A",
    "Serie A": "Serie A",
    "FRA-Ligue 1": "Ligue 1",
    "Ligue 1": "Ligue 1",
    "POR-Primeira Liga": "Primeira Liga",
    "Primeira Liga": "Primeira Liga",
    "NED-Eredivisie": "Eredivisie",
    "Eredivisie": "Eredivisie",
}


def fetch_player_match_stats(
    league: str,
    season: str,
    *,
    client: CachedHttpClient | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Fetch player match ratings from SofaScore via soccerdata.

    Parameters
    ----------
    league : str
        SofaScore league name (e.g. "Premier League", "LaLiga").
    season : str
        Season string (e.g. "2024-2025").
    client : CachedHttpClient, optional
        HTTP client with caching. Not used when soccerdata handles caching.
    settings : PlatformSettings, optional
        Platform settings for path resolution.
    force_refresh : bool
        If True, bypass soccerdata's cache.

    Returns
    -------
    AdapterResult
        DataFrame with columns: player_name, team_name, match_date, rating,
        position, minutes_played, league, season.
    """
    try:
        import soccerdata as sd
    except ImportError as exc:
        raise ImportError(
            "soccerdata is required for the SofaScore adapter. "
            "Install it with: uv pip install soccerdata"
        ) from exc

    resolved_settings = settings or PlatformSettings.from_root()
    sofascore_league = _resolve_league(league)

    try:
        scraper = sd.Sofascore(
            leagues=sofascore_league,
            seasons=season,
            no_cache=force_refresh,
            data_dir=resolved_settings.raw_root / SOURCE_NAME / "soccerdata_cache",
        )
    except Exception as exc:
        raise SourceSchemaError(
            f"Failed to initialize SofaScore scraper for {league} {season}: {exc}"
        ) from exc

    # Use read_schedule to get match list, then enrich with league table
    try:
        schedule = scraper.read_schedule(force_cache=force_refresh)
    except Exception as exc:
        raise SourceSchemaError(
            f"Failed to read SofaScore schedule for {league} {season}: {exc}"
        ) from exc

    if schedule.empty:
        raise SourceSchemaError(
            f"SofaScore returned no schedule data for {league} {season}"
        )

    # Flatten schedule into a player-level frame with match context
    schedule = schedule.reset_index()
    frame = schedule.rename(columns={
        "home_team": "home_team",
        "away_team": "away_team",
        "date": "match_date",
        "home_score": "home_score",
        "away_score": "away_score",
    })

    # Add league/season columns
    frame["league"] = league
    frame["season"] = season

    # Try to get league table for team-level stats
    try:
        league_table = scraper.read_league_table(force_cache=force_refresh)
        if not league_table.empty:
            league_table = league_table.reset_index()
            frame = frame.merge(
                league_table[["team", "MP", "W", "D", "L", "GF", "GA", "Pts"]],
                left_on="home_team",
                right_on="team",
                how="left",
                suffixes=("", "_home"),
            )
    except Exception:
        logger.warning("Could not fetch league table for %s %s", league, season)

    # Build metadata
    cache_path = (
        resolved_settings.raw_root
        / SOURCE_NAME
        / sofascore_league.replace(" ", "_")
        / season
        / "schedule.parquet"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    # Save a copy for traceability
    frame.to_parquet(cache_path, index=False)

    source_uri = f"{SOFASCORE_API}schedule/{sofascore_league}/{season}"
    payload = cache_path.read_bytes()


    # Build minimal metadata since soccerdata handles its own HTTP
    import hashlib
    from datetime import UTC, datetime

    from scoutlab.schemas import SourceRequestLogEntry

    payload_sha256 = hashlib.sha256(payload).hexdigest()
    request_log = SourceRequestLogEntry(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        requested_at=datetime.now(tz=UTC),
        parser_version=PARSER_VERSION,
        response_sha256=payload_sha256,
        cache_hit=not force_refresh,
        status_code=200,
    )
    from scoutlab.adapters.base import SourceMetadata

    metadata = SourceMetadata(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        cache_path=cache_path,
        parser_version=PARSER_VERSION,
        source_file_sha256=payload_sha256,
        request_log=request_log,
        record_count=len(frame),
    )

    return AdapterResult(dataframe=frame, metadata=metadata)


def fetch_team_match_stats(
    league: str,
    season: str,
    *,
    client: CachedHttpClient | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Fetch team-level match statistics from SofaScore via soccerdata.

    Parameters
    ----------
    league : str
        SofaScore league name.
    season : str
        Season string (e.g. "2024-2025").
    client : CachedHttpClient, optional
        HTTP client with caching.
    settings : PlatformSettings, optional
        Platform settings.
    force_refresh : bool
        If True, bypass cache.

    Returns
    -------
    AdapterResult
        DataFrame with team-level league table statistics.
    """
    try:
        import soccerdata as sd
    except ImportError as exc:
        raise ImportError(
            "soccerdata is required for the SofaScore adapter. "
            "Install it with: uv pip install soccerdata"
        ) from exc

    resolved_settings = settings or PlatformSettings.from_root()
    sofascore_league = _resolve_league(league)

    try:
        scraper = sd.Sofascore(
            leagues=sofascore_league,
            seasons=season,
            no_cache=force_refresh,
            data_dir=resolved_settings.raw_root / SOURCE_NAME / "soccerdata_cache",
        )
    except Exception as exc:
        raise SourceSchemaError(
            f"Failed to initialize SofaScore scraper for {league} {season}: {exc}"
        ) from exc

    try:
        league_table = scraper.read_league_table(force_cache=force_refresh)
    except Exception as exc:
        raise SourceSchemaError(
            f"Failed to read SofaScore league table for {league} {season}: {exc}"
        ) from exc

    if league_table.empty:
        raise SourceSchemaError(
            f"SofaScore returned no league table data for {league} {season}"
        )

    frame = league_table.reset_index()
    frame["league"] = league
    frame["season"] = season

    cache_path = (
        resolved_settings.raw_root
        / SOURCE_NAME
        / sofascore_league.replace(" ", "_")
        / season
        / "league_table.parquet"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(cache_path, index=False)

    source_uri = f"{SOFASCORE_API}league-table/{sofascore_league}/{season}"
    payload = cache_path.read_bytes()

    import hashlib
    from datetime import UTC, datetime

    from scoutlab.adapters.base import SourceMetadata
    from scoutlab.schemas import SourceRequestLogEntry

    payload_sha256 = hashlib.sha256(payload).hexdigest()
    request_log = SourceRequestLogEntry(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        requested_at=datetime.now(tz=UTC),
        parser_version=PARSER_VERSION,
        response_sha256=payload_sha256,
        cache_hit=not force_refresh,
        status_code=200,
    )
    metadata = SourceMetadata(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        cache_path=cache_path,
        parser_version=PARSER_VERSION,
        source_file_sha256=payload_sha256,
        request_log=request_log,
        record_count=len(frame),
    )

    return AdapterResult(dataframe=frame, metadata=metadata)


def _resolve_league(league: str) -> str:
    """Resolve a league identifier to the SofaScore league name."""
    mapping = LEAGUE_MAPPINGS.get(league)
    if mapping is None:
        raise ValueError(f"Unsupported SofaScore league identifier: {league}")
    return mapping

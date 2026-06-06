"""WhoScored adapter for player match ratings and event data via soccerdata."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from scoutfootball.adapters.base import AdapterResult, SourceMetadata
from scoutfootball.adapters.common import SourceSchemaError
from scoutfootball.config import PlatformSettings
from scoutfootball.schemas import SourceRequestLogEntry

logger = logging.getLogger(__name__)

SOURCE_NAME = "whoscored"
PARSER_VERSION = "whoscored/v0.1.0"

WHOSCORED_URL = "https://www.whoscored.com"

# soccerdata league name -> internal league key
LEAGUE_MAPPINGS: dict[str, str] = {
    "ENG-Premier League": "Premier League",
    "ESP-La Liga": "LaLiga",
    "GER-Bundesliga": "Bundesliga",
    "ITA-Serie A": "Serie A",
    "FRA-Ligue 1": "Ligue 1",
    "POR-Primeira Liga": "Primeira Liga",
    "NED-Eredivisie": "Eredivisie",
}

# Reverse mapping: internal key -> soccerdata league name
LEAGUE_REVERSE: dict[str, str] = {v: k for k, v in LEAGUE_MAPPINGS.items()}


def _resolve_league(league: str) -> str:
    """Resolve a league identifier to the soccerdata WhoScored league name."""
    if league in LEAGUE_MAPPINGS:
        return league
    mapping = LEAGUE_REVERSE.get(league)
    if mapping is not None:
        return mapping
    raise ValueError(f"Unsupported WhoScored league identifier: {league}")


def _build_metadata(
    *,
    source_uri: str,
    cache_path: Path,
    payload: bytes,
    force_refresh: bool,
    record_count: int,
) -> SourceMetadata:
    """Build SourceMetadata from saved parquet payload."""
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
    return SourceMetadata(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        cache_path=cache_path,
        parser_version=PARSER_VERSION,
        source_file_sha256=payload_sha256,
        request_log=request_log,
        record_count=record_count,
    )


def _init_scraper(
    league: str,
    season: str,
    settings: PlatformSettings,
    force_refresh: bool = False,
):
    """Initialize soccerdata.WhoScored scraper with consistent settings."""
    try:
        import soccerdata as sd
    except ImportError as exc:
        raise ImportError(
            "soccerdata is required for the WhoScored adapter. "
            "Install it with: uv pip install soccerdata\n"
            "WhoScored also requires Selenium and a Chrome/Chromium browser. "
            "Install with: uv pip install selenium && ensure Chrome is installed."
        ) from exc

    resolved_league = _resolve_league(league)

    # NOTE: WhoScored uses Selenium (headless Chrome) for scraping.
    # In some regions, a proxy may be required to access whoscored.com.
    # Set proxy via soccerdata's proxy config or environment variables.
    try:
        scraper = sd.WhoScored(
            leagues=resolved_league,
            seasons=season,
            no_cache=force_refresh,
            data_dir=settings.raw_root / SOURCE_NAME / "soccerdata_cache",
        )
    except Exception as exc:
        raise SourceSchemaError(
            f"Failed to initialize WhoScored scraper for {league} {season}: {exc}"
        ) from exc

    return scraper, resolved_league


def fetch_player_match_ratings(
    league: str,
    season: str,
    *,
    client=None,  # noqa: ARG001 - CachedHttpClient, unused (soccerdata handles HTTP)
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Fetch player match ratings from WhoScored via Selenium scraping.

    WhoScored provides player ratings (1-10 scale) based on Opta event data.
    These are scraped from match pages using Selenium since soccerdata does not
    expose a dedicated ratings endpoint.

    Parameters
    ----------
    league : str
        League name (e.g. "Premier League", "ENG-Premier League").
    season : str
        Season string (e.g. "2024-2025").
    client : CachedHttpClient, optional
        Not used; soccerdata handles its own HTTP/Selenium.
    settings : PlatformSettings, optional
        Platform settings for path resolution.
    force_refresh : bool
        If True, bypass soccerdata's cache.

    Returns
    -------
    AdapterResult
        DataFrame with columns: player_name, team_name, match_date, rating,
        position, league, season.
    """
    resolved_settings = settings or PlatformSettings.from_root()
    scraper, resolved_league = _init_scraper(league, season, resolved_settings, force_refresh)

    # Get schedule first to iterate over matches
    try:
        schedule = scraper.read_schedule(force_cache=force_refresh)
    except Exception as exc:
        raise SourceSchemaError(
            f"Failed to read WhoScored schedule for {league} {season}: {exc}"
        ) from exc

    if schedule.empty:
        raise SourceSchemaError(
            f"WhoScored returned no schedule data for {league} {season}"
        )

    schedule = schedule.reset_index()

    # Scrape player ratings from each match page
    # WhoScored match pages contain a ratings table accessible via Selenium
    from selenium.webdriver.common.by import By

    all_ratings: list[dict] = []
    for _, game in schedule.iterrows():
        game_id = game.get("game_id")
        match_date = game.get("date")
        home_team = game.get("home_team", "")
        away_team = game.get("away_team", "")

        try:
            url = f"{WHOSCORED_URL}/Matches/{game_id}"
            scraper._driver.get(url)

            # Wait for player ratings to load
            import time
            time.sleep(2)

            # Extract ratings from both home and away tables
            for side, team_name in [("home", home_team), ("away", away_team)]:
                try:
                    table = scraper._driver.find_element(
                        By.XPATH,
                        f"//div[@id='{side}-team-summary']//table"
                    )
                    rows = table.find_elements(By.XPATH, ".//tbody/tr")
                    for row in rows:
                        try:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            if len(cells) >= 3:
                                player_name = cells[0].text.strip()
                                position = cells[1].text.strip() if len(cells) > 1 else ""
                                rating_str = cells[-1].text.strip()
                                try:
                                    rating = float(rating_str)
                                except ValueError:
                                    continue
                                all_ratings.append({
                                    "player_name": player_name,
                                    "team_name": team_name,
                                    "match_date": match_date,
                                    "rating": rating,
                                    "position": position,
                                    "league": league,
                                    "season": season,
                                })
                        except Exception:
                            continue
                except Exception:
                    logger.debug(
                        "No ratings table for %s in match %s", side, game_id
                    )
        except Exception as exc:
            logger.warning("Failed to scrape ratings for match %s: %s", game_id, exc)
            continue

    if not all_ratings:
        # Fallback: return schedule with placeholder columns
        logger.warning(
            "Could not scrape player ratings for %s %s; returning schedule only",
            league, season,
        )
        frame = schedule.copy()
        frame["league"] = league
        frame["season"] = season
        frame["rating"] = float("nan")
        frame["position"] = ""
        frame = frame.rename(columns={
            "home_team": "team_name",
            "date": "match_date",
        })
        frame["player_name"] = ""
    else:
        frame = pd.DataFrame(all_ratings)

    # Save to parquet
    cache_path = (
        resolved_settings.raw_root
        / SOURCE_NAME
        / resolved_league.replace(" ", "_")
        / season
        / "player_ratings.parquet"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(cache_path, index=False)

    source_uri = f"{WHOSCORED_URL}/ratings/{resolved_league}/{season}"
    payload = cache_path.read_bytes()
    metadata = _build_metadata(
        source_uri=source_uri,
        cache_path=cache_path,
        payload=payload,
        force_refresh=force_refresh,
        record_count=len(frame),
    )

    return AdapterResult(dataframe=frame, metadata=metadata)


def fetch_match_events(
    league: str,
    season: str,
    *,
    client=None,  # noqa: ARG001
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Fetch match event stream data from WhoScored via soccerdata.

    Parameters
    ----------
    league : str
        League name (e.g. "Premier League", "ENG-Premier League").
    season : str
        Season string (e.g. "2024-2025").
    client : CachedHttpClient, optional
        Not used; soccerdata handles its own HTTP/Selenium.
    settings : PlatformSettings, optional
        Platform settings for path resolution.
    force_refresh : bool
        If True, bypass cache.

    Returns
    -------
    AdapterResult
        DataFrame with columns: match_id, event_type, minute, second,
        player_name, team_name, x, y, end_x, end_y, is_shot, is_goal,
        card_type, outcome_type, league, season.
    """
    resolved_settings = settings or PlatformSettings.from_root()
    scraper, resolved_league = _init_scraper(league, season, resolved_settings, force_refresh)

    try:
        events = scraper.read_events(
            force_cache=force_refresh,
            output_fmt="events",
            on_error="skip",
        )
    except Exception as exc:
        raise SourceSchemaError(
            f"Failed to read WhoScored events for {league} {season}: {exc}"
        ) from exc

    if events is None or (isinstance(events, pd.DataFrame) and events.empty):
        raise SourceSchemaError(
            f"WhoScored returned no event data for {league} {season}"
        )

    frame = events.reset_index()

    # Standardize column names for downstream consumption
    rename_map = {
        "game_id": "match_id",
        "type": "event_type",
        "player": "player_name",
        "team": "team_name",
    }
    frame = frame.rename(columns={k: v for k, v in rename_map.items() if k in frame.columns})

    # Add league/season
    frame["league"] = league
    frame["season"] = season

    # Ensure key columns exist
    for col in ("match_id", "event_type", "minute", "player_name", "team_name",
                "x", "y", "end_x", "end_y", "is_shot", "is_goal", "card_type",
                "outcome_type", "league", "season"):
        if col not in frame.columns:
            frame[col] = float("nan") if col not in ("is_shot", "is_goal") else False

    # Select output columns that exist
    output_cols = [c for c in (
        "match_id", "event_type", "minute", "second", "player_name", "team_name",
        "x", "y", "end_x", "end_y", "is_shot", "is_goal", "card_type",
        "outcome_type", "league", "season",
    ) if c in frame.columns]
    frame = frame[output_cols]

    # Save to parquet
    cache_path = (
        resolved_settings.raw_root
        / SOURCE_NAME
        / resolved_league.replace(" ", "_")
        / season
        / "match_events.parquet"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(cache_path, index=False)

    source_uri = f"{WHOSCORED_URL}/events/{resolved_league}/{season}"
    payload = cache_path.read_bytes()
    metadata = _build_metadata(
        source_uri=source_uri,
        cache_path=cache_path,
        payload=payload,
        force_refresh=force_refresh,
        record_count=len(frame),
    )

    return AdapterResult(dataframe=frame, metadata=metadata)


def fetch_missing_players(
    league: str,
    season: str,
    *,
    client=None,  # noqa: ARG001
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Fetch missing players (injured/suspended) from WhoScored via soccerdata.

    Parameters
    ----------
    league : str
        League name (e.g. "Premier League", "ENG-Premier League").
    season : str
        Season string (e.g. "2024-2025").
    client : CachedHttpClient, optional
        Not used; soccerdata handles its own HTTP/Selenium.
    settings : PlatformSettings, optional
        Platform settings for path resolution.
    force_refresh : bool
        If True, bypass cache.

    Returns
    -------
    AdapterResult
        DataFrame with columns: player_name, team_name, reason, status,
        match_date, league, season.
    """
    resolved_settings = settings or PlatformSettings.from_root()
    scraper, resolved_league = _init_scraper(league, season, resolved_settings, force_refresh)

    try:
        missing = scraper.read_missing_players(force_cache=force_refresh)
    except Exception as exc:
        raise SourceSchemaError(
            f"Failed to read WhoScored missing players for {league} {season}: {exc}"
        ) from exc

    if missing.empty:
        raise SourceSchemaError(
            f"WhoScored returned no missing player data for {league} {season}"
        )

    frame = missing.reset_index()

    # Standardize column names
    rename_map = {
        "player": "player_name",
        "team": "team_name",
    }
    frame = frame.rename(columns={k: v for k, v in rename_map.items() if k in frame.columns})

    # Add league/season
    frame["league"] = league
    frame["season"] = season

    # Derive match_date from game info if available
    if "game" in frame.columns:
        frame["match_date"] = frame["game"]
    else:
        frame["match_date"] = pd.NaT

    # Ensure key columns exist
    for col in ("player_name", "team_name", "reason", "status", "match_date",
                "league", "season"):
        if col not in frame.columns:
            frame[col] = ""

    # Save to parquet
    cache_path = (
        resolved_settings.raw_root
        / SOURCE_NAME
        / resolved_league.replace(" ", "_")
        / season
        / "missing_players.parquet"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(cache_path, index=False)

    source_uri = f"{WHOSCORED_URL}/missing-players/{resolved_league}/{season}"
    payload = cache_path.read_bytes()
    metadata = _build_metadata(
        source_uri=source_uri,
        cache_path=cache_path,
        payload=payload,
        force_refresh=force_refresh,
        record_count=len(frame),
    )

    return AdapterResult(dataframe=frame, metadata=metadata)

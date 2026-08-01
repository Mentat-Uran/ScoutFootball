"""Capology adapter for player salary data via ScraperFC."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from scoutfootball.adapters.base import AdapterResult, SourceMetadata
from scoutfootball.adapters.common import (
    CachedHttpClient,
    SourceSchemaError,
)
from scoutfootball.config import PlatformSettings
from scoutfootball.schemas import SourceRequestLogEntry

logger = logging.getLogger(__name__)

SOURCE_NAME = "capology"
PARSER_VERSION = "capology/v0.1.0"

# Internal league name -> ScraperFC Capology league name
LEAGUE_MAPPINGS: dict[str, str] = {
    "Premier League": "England Premier League",
    "La Liga": "Spain La Liga",
    "Bundesliga": "Germany Bundesliga",
    "Serie A": "Italy Serie A",
    "Ligue 1": "France Ligue 1",
}

# Canonical output columns
OUTPUT_COLUMNS = [
    "player_name",
    "team_name",
    "position",
    "weekly_gross_salary",
    "annual_gross_salary",
    "weekly_net_salary",
    "annual_net_salary",
    "expiry_date",
    "league",
    "season",
]


def fetch_player_salaries(
    league: str,
    season: str,
    *,
    client: CachedHttpClient | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Fetch player salary data from Capology via ScraperFC.

    Parameters
    ----------
    league : str
        League name (e.g. "Premier League", "La Liga").
    season : str
        Season string in Capology format (e.g. "2024-25").
    client : CachedHttpClient, optional
        HTTP client with caching. Not used directly; ScraperFC handles HTTP.
    settings : PlatformSettings, optional
        Platform settings for path resolution.
    force_refresh : bool
        If True, bypass cached parquet and re-scrape.

    Returns
    -------
    AdapterResult
        DataFrame with columns: player_name, team_name, position,
        weekly_gross_salary, annual_gross_salary, weekly_net_salary,
        annual_net_salary, expiry_date, league, season.
    """
    try:
        from ScraperFC import Capology
    except ImportError as exc:
        raise ImportError(
            "ScraperFC is required for the Capology adapter. "
            "Install it with: uv pip install ScraperFC"
        ) from exc

    resolved_settings = settings or PlatformSettings.from_root()
    capology_league = _resolve_league(league)

    # Check cache first
    cache_path = (
        resolved_settings.raw_root
        / SOURCE_NAME
        / capology_league.replace(" ", "_")
        / season
        / "player_salaries.parquet"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists() and not force_refresh:
        frame = pd.read_parquet(cache_path)
        payload = cache_path.read_bytes()
        metadata = _build_metadata(
            payload=payload,
            cache_path=cache_path,
            season=season,
            capology_league=capology_league,
            cache_hit=True,
            record_count=len(frame),
        )
        return AdapterResult(dataframe=frame, metadata=metadata)

    # Scrape from Capology
    try:
        scraper = Capology()
        raw_df = scraper.scrape_salaries(season, capology_league, "gbp")
    except Exception as exc:
        raise SourceSchemaError(
            f"Failed to scrape Capology salaries for {league} {season}: {exc}"
        ) from exc

    if raw_df.empty:
        raise SourceSchemaError(
            f"Capology returned no salary data for {league} {season}"
        )

    frame = _normalize_dataframe(raw_df, league, season)

    # Save for traceability
    frame.to_parquet(cache_path, index=False)

    payload = cache_path.read_bytes()
    metadata = _build_metadata(
        payload=payload,
        cache_path=cache_path,
        season=season,
        capology_league=capology_league,
        cache_hit=False,
        record_count=len(frame),
    )

    return AdapterResult(dataframe=frame, metadata=metadata)


def _resolve_league(league: str) -> str:
    """Resolve a league identifier to the ScraperFC Capology league name."""
    mapping = LEAGUE_MAPPINGS.get(league)
    if mapping is None:
        valid = list(LEAGUE_MAPPINGS.keys())
        raise ValueError(
            f"Unsupported Capology league: {league}. Valid options: {valid}"
        )
    return mapping


def _normalize_dataframe(raw_df: pd.DataFrame, league: str, season: str) -> pd.DataFrame:
    """Normalize the raw ScraperFC Capology DataFrame to canonical schema.

    ScraperFC returns a MultiIndex column DataFrame with structure like:
    Level 0: '', 'Gross', 'Net', 'Gross', 'Net'
    Level 1: 'Player', 'Club', 'Pos', 'Weekly', 'Annual', 'Weekly', 'Annual', 'Expires'

    We flatten and rename to our canonical columns.
    """
    # Flatten MultiIndex columns
    if isinstance(raw_df.columns, pd.MultiIndex):
        flat_cols = []
        for level0, level1 in raw_df.columns.values:
            if level0 and level0.strip():
                flat_cols.append(f"{level0}_{level1}".strip())
            else:
                flat_cols.append(level1.strip())
        raw_df.columns = flat_cols

    # Build normalized frame
    frame = pd.DataFrame()

    # Map columns - exact names depend on Capology's HTML structure
    # Player name is typically in a column like 'Player' or the first column
    col_map = _detect_column_mapping(raw_df.columns.tolist())

    frame["player_name"] = raw_df[col_map["player"]].astype(str).str.strip()
    frame["team_name"] = raw_df[col_map["team"]].astype(str).str.strip()
    frame["position"] = raw_df[col_map["position"]].astype(str).str.strip()

    for salary_col in ["weekly_gross", "annual_gross", "weekly_net", "annual_net"]:
        if col_map[salary_col] in raw_df.columns:
            frame[salary_col.replace("_", "_") + "_salary"] = (
                raw_df[col_map[salary_col]]
                .astype(str)
                .str.replace(r"[^\d.-]", "", regex=True)
                .replace("", "0")
                .astype(float)
            )
        else:
            frame[salary_col.replace("_", "_") + "_salary"] = 0.0

    if col_map["expiry"] in raw_df.columns:
        frame["expiry_date"] = raw_df[col_map["expiry"]].astype(str).str.strip()
    else:
        frame["expiry_date"] = None

    frame["league"] = league
    frame["season"] = season

    # Ensure all output columns exist
    for col in OUTPUT_COLUMNS:
        if col not in frame.columns:
            frame[col] = None

    return frame[OUTPUT_COLUMNS]


def _detect_column_mapping(columns: list[str]) -> dict[str, str]:
    """Detect column name mapping from raw DataFrame columns.

    ScraperFC Capology returns columns that vary by page structure.
    We use heuristic matching to find the right columns.
    """
    mapping: dict[str, str] = {}
    cols_lower = {c.lower().strip(): c for c in columns}

    # Player name
    for candidate in ["player", "name"]:
        if candidate in cols_lower:
            mapping["player"] = cols_lower[candidate]
            break
    if "player" not in mapping:
        mapping["player"] = columns[0]  # fallback to first column

    # Team/Club
    for candidate in ["club", "team", "team_name"]:
        if candidate in cols_lower:
            mapping["team"] = cols_lower[candidate]
            break
    if "team" not in mapping:
        mapping["team"] = columns[1] if len(columns) > 1 else columns[0]

    # Position
    for candidate in ["pos", "position"]:
        if candidate in cols_lower:
            mapping["position"] = cols_lower[candidate]
            break
    if "position" not in mapping:
        mapping["position"] = columns[2] if len(columns) > 2 else columns[0]

    # Salary columns - look for Gross/Net Weekly/Annual patterns
    for col in columns:
        col_lower = col.lower()
        if "gross" in col_lower and "week" in col_lower:
            mapping["weekly_gross"] = col
        elif "gross" in col_lower and "annual" in col_lower:
            mapping["annual_gross"] = col
        elif "net" in col_lower and "week" in col_lower:
            mapping["weekly_net"] = col
        elif "net" in col_lower and "annual" in col_lower:
            mapping["annual_net"] = col
        elif "expir" in col_lower:
            mapping["expiry"] = col

    # Defaults for missing salary columns
    for key in ["weekly_gross", "annual_gross", "weekly_net", "annual_net"]:
        if key not in mapping:
            mapping[key] = ""
    if "expiry" not in mapping:
        mapping["expiry"] = ""

    return mapping


def _build_metadata(
    *,
    payload: bytes,
    cache_path: Path,
    season: str,
    capology_league: str,
    cache_hit: bool,
    record_count: int,
) -> SourceMetadata:
    """Build SourceMetadata for a Capology fetch result."""
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    source_uri = f"https://www.capology.com/{capology_league}/salaries/{season}"
    request_log = SourceRequestLogEntry(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        requested_at=datetime.now(tz=UTC),
        parser_version=PARSER_VERSION,
        response_sha256=payload_sha256,
        cache_hit=cache_hit,
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

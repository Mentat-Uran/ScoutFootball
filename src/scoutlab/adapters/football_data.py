"""Football-Data.co.uk adapter."""

from __future__ import annotations

import re
from io import BytesIO

import pandas as pd

from scoutlab.adapters.base import AdapterResult
from scoutlab.adapters.common import (
    CachedHttpClient,
    SourceSchemaError,
    with_record_count,
)
from scoutlab.config import PlatformSettings

SOURCE_NAME = "football_data"
PARSER_VERSION = "football_data/v0.1.0"
SEASON_PATTERN = re.compile(r"^\d{4}$")
BASE_URL = "https://www.football-data.co.uk/mmz4281"
REQUIRED_COLUMNS = ("Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG")


def download_csv(
    league_code: str,
    season: str,
    *,
    client: CachedHttpClient | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Download one Football-Data CSV with local caching."""

    if not SEASON_PATTERN.fullmatch(season):
        raise ValueError("season must use Football-Data's 4-digit code format such as '2425'")

    resolved_settings = settings or PlatformSettings.from_root()
    resolved_client = client or CachedHttpClient(settings=resolved_settings)
    source_uri = f"{BASE_URL}/{season}/{league_code}.csv"
    cache_path = resolved_settings.raw_root / SOURCE_NAME / season / f"{league_code}.csv"
    artifact = resolved_client.fetch(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        cache_path=cache_path,
        parser_version=PARSER_VERSION,
        force_refresh=force_refresh,
    )
    frame = _parse_csv_payload(artifact.payload)
    missing = tuple(column for column in REQUIRED_COLUMNS if column not in frame.columns)
    if missing:
        missing_text = ", ".join(missing)
        raise SourceSchemaError(f"Football-Data payload is missing columns: {missing_text}")
    metadata = with_record_count(artifact.metadata, len(frame))
    return AdapterResult(dataframe=frame, metadata=metadata)


def _parse_csv_payload(payload: bytes) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "latin1"):
        try:
            return pd.read_csv(BytesIO(payload), encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise SourceSchemaError("Football-Data payload is not decodable as utf-8-sig or latin1")

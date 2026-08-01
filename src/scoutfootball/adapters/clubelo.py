"""Club Elo adapter."""

from __future__ import annotations

from datetime import date
from io import BytesIO

import pandas as pd

from scoutfootball.adapters.base import AdapterResult
from scoutfootball.adapters.common import (
    CachedHttpClient,
    SourceSchemaError,
    with_record_count,
)
from scoutfootball.config import PlatformSettings

SOURCE_NAME = "clubelo"
PARSER_VERSION = "clubelo/v0.1.0"
BASE_URL = "http://api.clubelo.com"
REQUIRED_COLUMNS = ("Club", "Elo")


def fetch_elo_by_date(
    as_of_date: str | date,
    *,
    client: CachedHttpClient | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Fetch Club Elo ratings for a specific date."""

    normalized_date = _normalize_date(as_of_date)
    resolved_settings = settings or PlatformSettings.from_root()
    resolved_client = client or CachedHttpClient(settings=resolved_settings)
    source_uri = f"{BASE_URL}/{normalized_date.isoformat()}"
    cache_path = resolved_settings.raw_root / SOURCE_NAME / f"{normalized_date.isoformat()}.csv"
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
        raise SourceSchemaError(f"Club Elo payload is missing columns: {missing_text}")
    frame = _fill_missing_club_names(frame)
    metadata = with_record_count(artifact.metadata, len(frame))
    return AdapterResult(dataframe=frame, metadata=metadata)


def _normalize_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("as_of_date must be an ISO date string such as '2026-05-01'") from error


def _parse_csv_payload(payload: bytes) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "latin1"):
        try:
            return pd.read_csv(BytesIO(payload), encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise SourceSchemaError("Club Elo payload is not decodable as utf-8-sig or latin1")


def _fill_missing_club_names(frame: pd.DataFrame) -> pd.DataFrame:
    club_series = frame["Club"].astype("string")
    missing_mask = club_series.isna() | club_series.str.strip().eq("")
    filled = frame.copy()
    filled["missing_club_name"] = missing_mask
    if missing_mask.any():
        replacements = [f"__missing_club_{index}__" for index in filled.index[missing_mask]]
        filled.loc[missing_mask, "Club"] = replacements
    return filled

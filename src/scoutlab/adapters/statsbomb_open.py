"""StatsBomb Open Data adapter."""

from __future__ import annotations

import json

import pandas as pd

from scoutlab.adapters.base import AdapterResult
from scoutlab.adapters.common import (
    CachedHttpClient,
    SourceSchemaError,
    with_record_count,
)
from scoutlab.config import PlatformSettings

SOURCE_NAME = "statsbomb_open"
PARSER_VERSION = "statsbomb_open/v0.1.0"
RAW_BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
COORDINATE_COLUMNS = (
    "location",
    "pass_end_location",
    "carry_end_location",
    "shot_end_location",
    "goalkeeper_end_location",
)


def load_matches(
    competition_id: int,
    season_id: int,
    *,
    client: CachedHttpClient | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Load matches for one StatsBomb competition and season."""

    resolved_settings = settings or PlatformSettings.from_root()
    resolved_client = client or CachedHttpClient(settings=resolved_settings)
    source_uri = f"{RAW_BASE_URL}/matches/{competition_id}/{season_id}.json"
    cache_path = resolved_settings.raw_root / SOURCE_NAME / "matches" / str(competition_id) / (
        f"{season_id}.json"
    )
    artifact = resolved_client.fetch(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        cache_path=cache_path,
        parser_version=PARSER_VERSION,
        force_refresh=force_refresh,
    )
    records = _decode_json_records(artifact.payload, context="matches")
    _ensure_record_fields(
        records,
        required_fields=("match_id", "match_date", "home_team", "away_team"),
        context="matches",
    )
    frame = pd.json_normalize(records, sep="_").rename(
        columns={
            "home_team_home_team_id": "home_team_id",
            "home_team_home_team_name": "home_team_name",
            "away_team_away_team_id": "away_team_id",
            "away_team_away_team_name": "away_team_name",
            "competition_competition_id": "competition_id",
            "competition_competition_name": "competition_name",
            "season_season_id": "season_id",
            "season_season_name": "season_name",
        },
    )
    metadata = with_record_count(artifact.metadata, len(frame))
    return AdapterResult(dataframe=frame, metadata=metadata)


def load_lineups(
    match_id: int,
    *,
    client: CachedHttpClient | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Load flattened lineups for one StatsBomb match."""

    resolved_settings = settings or PlatformSettings.from_root()
    resolved_client = client or CachedHttpClient(settings=resolved_settings)
    source_uri = f"{RAW_BASE_URL}/lineups/{match_id}.json"
    cache_path = resolved_settings.raw_root / SOURCE_NAME / "lineups" / f"{match_id}.json"
    artifact = resolved_client.fetch(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        cache_path=cache_path,
        parser_version=PARSER_VERSION,
        force_refresh=force_refresh,
    )
    records = _decode_json_records(artifact.payload, context="lineups")
    _ensure_record_fields(
        records,
        required_fields=("team_id", "team_name", "lineup"),
        context="lineups",
    )
    frame = pd.json_normalize(
        records,
        record_path="lineup",
        meta=["team_id", "team_name"],
        sep="_",
    )
    frame.insert(0, "match_id", match_id)
    metadata = with_record_count(artifact.metadata, len(frame))
    return AdapterResult(dataframe=frame, metadata=metadata)


def load_events(
    match_id: int,
    *,
    client: CachedHttpClient | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Load flattened events for one StatsBomb match."""

    resolved_settings = settings or PlatformSettings.from_root()
    resolved_client = client or CachedHttpClient(settings=resolved_settings)
    source_uri = f"{RAW_BASE_URL}/events/{match_id}.json"
    cache_path = resolved_settings.raw_root / SOURCE_NAME / "events" / f"{match_id}.json"
    artifact = resolved_client.fetch(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        cache_path=cache_path,
        parser_version=PARSER_VERSION,
        force_refresh=force_refresh,
    )
    records = _decode_json_records(artifact.payload, context="events")
    _ensure_record_fields(
        records,
        required_fields=("id", "period", "minute", "second", "type"),
        context="events",
    )
    frame = pd.json_normalize(records, sep="_").rename(
        columns={
            "id": "event_id",
            "type_name": "event_type",
        },
    )
    frame.insert(0, "match_id", match_id)
    frame = _expand_coordinate_columns(frame)
    metadata = with_record_count(artifact.metadata, len(frame))
    return AdapterResult(dataframe=frame, metadata=metadata)


def _decode_json_records(payload: bytes, *, context: str) -> list[dict]:
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceSchemaError(f"StatsBomb {context} payload is not valid UTF-8 JSON") from error
    if not isinstance(decoded, list):
        raise SourceSchemaError(f"StatsBomb {context} payload must be a JSON list")
    if not all(isinstance(item, dict) for item in decoded):
        raise SourceSchemaError(f"StatsBomb {context} payload must contain JSON objects")
    return decoded


def _ensure_record_fields(
    records: list[dict],
    *,
    required_fields: tuple[str, ...],
    context: str,
) -> None:
    if not records:
        raise SourceSchemaError(f"StatsBomb {context} payload is empty")
    first_record = records[0]
    missing = tuple(field for field in required_fields if field not in first_record)
    if missing:
        missing_text = ", ".join(missing)
        raise SourceSchemaError(f"StatsBomb {context} payload is missing fields: {missing_text}")


def _expand_coordinate_columns(frame: pd.DataFrame) -> pd.DataFrame:
    expanded = frame.copy()
    for column in COORDINATE_COLUMNS:
        if column not in expanded.columns:
            continue
        values = expanded[column].apply(_normalize_coordinate_list)
        width = values.map(len).max()
        if width == 0:
            continue
        coordinate_frame = pd.DataFrame(
            values.tolist(),
            columns=[f"{column}_{i}" for i in range(width)],
        )
        rename_map = {
            f"{column}_0": f"{column}_x",
            f"{column}_1": f"{column}_y",
            f"{column}_2": f"{column}_z",
        }
        coordinate_frame = coordinate_frame.rename(columns=rename_map)
        expanded = pd.concat((expanded, coordinate_frame), axis=1)
    return expanded


def _normalize_coordinate_list(value: object) -> list[float | None]:
    if isinstance(value, list):
        return value
    return []

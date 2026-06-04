"""API-Football adapter for injuries, transfers, and coaches data.

# Pipeline integration note (Task 9):
# The pipeline should catch ApiKeyMissingError and skip this source with a warning,
# so that the platform works without an API-Football key.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from scoutlab.adapters.base import AdapterResult, SourceMetadata
from scoutlab.adapters.common import (
    CachedHttpClient,
    SourceAdapterError,
    SourceSchemaError,
)
from scoutlab.config import PlatformSettings

SOURCE_NAME = "api_football"
PARSER_VERSION = "api_football/v0.1.0"
BASE_URL = "https://v3.football.api-sports.io"
REQUEST_HEADERS_TEMPLATE = {"x-apisports-key": "{API_KEY}"}

# Free-tier daily limit
DEFAULT_DAILY_REQUEST_LIMIT = 100

# API-Football league IDs for Big 5
LEAGUE_IDS = {
    "EPL": 39,
    "La_Liga": 140,
    "Bundesliga": 78,
    "Serie_A": 135,
    "Ligue_1": 61,
}


class ApiKeyMissingError(SourceAdapterError):
    """Raised when API-Football key is not configured."""


class DailyLimitExceededError(SourceAdapterError):
    """Raised when the daily API request limit has been reached."""


class _DailyRequestCounter:
    """Track daily API request count using a simple file on disk."""

    def __init__(self, counter_dir: Path, daily_limit: int = DEFAULT_DAILY_REQUEST_LIMIT) -> None:
        self._counter_dir = counter_dir
        self._daily_limit = daily_limit

    def _counter_path(self, today: date | None = None) -> Path:
        today = today or date.today()
        self._counter_dir.mkdir(parents=True, exist_ok=True)
        return self._counter_dir / f"{today.isoformat()}.json"

    def count(self) -> int:
        path = self._counter_path()
        if not path.exists():
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("count", 0)
        except (json.JSONDecodeError, OSError):
            return 0

    def increment(self) -> int:
        path = self._counter_path()
        current = self.count() + 1
        path.write_text(
            json.dumps({"count": current, "updated": datetime.now(tz=UTC).isoformat()}),
            encoding="utf-8",
        )
        return current

    def remaining(self) -> int:
        return max(0, self._daily_limit - self.count())

    def check_and_increment(self) -> None:
        if self.count() >= self._daily_limit:
            raise DailyLimitExceededError(
                f"API-Football daily limit of {self._daily_limit} requests reached. "
                f"Remaining: 0"
            )
        self.increment()


def _resolve_api_key(api_key: str | None = None) -> str:
    """Resolve API key from parameter or environment variable."""
    key = api_key or os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise ApiKeyMissingError(
            "API-Football key is required. "
            "Set API_FOOTBALL_KEY environment variable or pass api_key parameter."
        )
    return key


def _build_headers(api_key: str) -> dict[str, str]:
    return {"x-apisports-key": api_key}


def _parse_response(payload: bytes) -> dict:
    """Parse and validate an API-Football JSON response."""
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceSchemaError("API-Football payload is not valid UTF-8 JSON") from error
    if not isinstance(decoded, dict):
        raise SourceSchemaError("API-Football payload must decode to a JSON object")
    errors = decoded.get("errors")
    if errors:
        error_text = errors if isinstance(errors, str) else json.dumps(errors)
        raise SourceSchemaError(f"API-Football returned errors: {error_text}")
    return decoded


def _paginate_fetch(
    *,
    endpoint: str,
    api_key: str,
    client: CachedHttpClient,
    settings: PlatformSettings,
    counter: _DailyRequestCounter,
    force_refresh: bool = False,
) -> list[dict]:
    """Fetch all pages from a paginated API-Football endpoint.

    On the first request, if force_refresh is False and a cached merged file
    exists, we return that directly. Otherwise we fetch page by page.
    """
    all_responses: list[dict] = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        separator = "&" if "?" in endpoint else "?"
        page_uri = f"{BASE_URL}{endpoint}{separator}page={page}"

        cache_path = (
            settings.raw_root
            / SOURCE_NAME
            / endpoint.strip("/").replace("?", "_").replace("&", "_").replace("=", "_")
            / f"page_{page}.json"
        )

        # Check rate limit before each request (only for non-cache-hit requests)
        if force_refresh or not cache_path.exists():
            counter.check_and_increment()

        headers = _build_headers(api_key)
        artifact = client.fetch(
            source_name=SOURCE_NAME,
            source_uri=page_uri,
            cache_path=cache_path,
            parser_version=PARSER_VERSION,
            force_refresh=force_refresh,
            request_headers=headers,
        )

        parsed = _parse_response(artifact.payload)
        paging = parsed.get("paging", {})
        total_pages = paging.get("total", 1)

        response_data = parsed.get("response", [])
        if not isinstance(response_data, list):
            raise SourceSchemaError(
                f"API-Football response field must be a list, got {type(response_data).__name__}"
            )
        all_responses.extend(response_data)
        page += 1

    return all_responses


# ---------------------------------------------------------------------------
# Public adapter functions
# ---------------------------------------------------------------------------


def fetch_injuries(
    league_id: int,
    season: int,
    *,
    api_key: str | None = None,
    client: CachedHttpClient | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Fetch injury data for a league+season.

    Returns DataFrame with columns:
        player_name, team_name, injury_type, reason, date_start, date_end
    """
    resolved_key = _resolve_api_key(api_key)
    resolved_settings = settings or PlatformSettings.from_root()
    resolved_client = client or CachedHttpClient(settings=resolved_settings)
    counter = _DailyRequestCounter(
        resolved_settings.log_root / SOURCE_NAME / "daily_counter"
    )

    endpoint = f"/injuries?league={league_id}&season={season}"
    records = _paginate_fetch(
        endpoint=endpoint,
        api_key=resolved_key,
        client=resolved_client,
        settings=resolved_settings,
        counter=counter,
        force_refresh=force_refresh,
    )

    rows = []
    for rec in records:
        player = rec.get("player", {})
        team = rec.get("team", {})
        injury = rec.get("injury", {})
        rows.append(
            {
                "player_name": player.get("name", ""),
                "team_name": team.get("name", ""),
                "injury_type": injury.get("type", ""),
                "reason": injury.get("reason", ""),
                "date_start": injury.get("date_start", ""),
                "date_end": injury.get("date_end", ""),
            }
        )

    frame = pd.DataFrame.from_records(rows)
    # Build metadata from the first page artifact
    cache_path = (
        resolved_settings.raw_root
        / SOURCE_NAME
        / "injuries"
        / str(league_id)
        / f"{season}.json"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    # Save merged result for faster re-reads
    if not frame.empty:
        frame.to_json(cache_path, orient="records", force_ascii=False)

    # Build a minimal metadata via a synthetic artifact
    merged_payload = cache_path.read_bytes() if cache_path.exists() else b"[]"
    metadata = _build_result_metadata(
        source_uri=f"{BASE_URL}{endpoint}",
        cache_path=cache_path,
        payload=merged_payload,
        record_count=len(frame),
        client=resolved_client,
    )
    return AdapterResult(dataframe=frame, metadata=metadata)


def fetch_transfers(
    team_id: int,
    *,
    api_key: str | None = None,
    client: CachedHttpClient | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Fetch transfer data for a team.

    Returns DataFrame with columns:
        player_name, from_team, to_team, transfer_type, date, fee
    """
    resolved_key = _resolve_api_key(api_key)
    resolved_settings = settings or PlatformSettings.from_root()
    resolved_client = client or CachedHttpClient(settings=resolved_settings)
    counter = _DailyRequestCounter(
        resolved_settings.log_root / SOURCE_NAME / "daily_counter"
    )

    endpoint = f"/transfers?team={team_id}"
    records = _paginate_fetch(
        endpoint=endpoint,
        api_key=resolved_key,
        client=resolved_client,
        settings=resolved_settings,
        counter=counter,
        force_refresh=force_refresh,
    )

    rows = []
    for rec in records:
        player = rec.get("player", {})
        transfers = rec.get("transfers", [])
        for transfer in transfers:
            transfer_from = transfer.get("from", {})
            transfer_to = transfer.get("to", {})
            transfer_date = transfer.get("date", {})
            rows.append(
                {
                    "player_name": player.get("name", ""),
                    "from_team": transfer_from.get("name", ""),
                    "to_team": transfer_to.get("name", ""),
                    "transfer_type": transfer.get("type", ""),
                    "date": (
                        transfer_date.get("from", "")
                        if isinstance(transfer_date, dict)
                        else str(transfer_date)
                    ),
                    "fee": transfer.get("fee", ""),
                }
            )

    frame = pd.DataFrame.from_records(rows)
    cache_path = (
        resolved_settings.raw_root
        / SOURCE_NAME
        / "transfers"
        / f"{team_id}.json"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if not frame.empty:
        frame.to_json(cache_path, orient="records", force_ascii=False)

    merged_payload = cache_path.read_bytes() if cache_path.exists() else b"[]"
    metadata = _build_result_metadata(
        source_uri=f"{BASE_URL}{endpoint}",
        cache_path=cache_path,
        payload=merged_payload,
        record_count=len(frame),
        client=resolved_client,
    )
    return AdapterResult(dataframe=frame, metadata=metadata)


def fetch_coaches(
    league_id: int,
    season: int,
    *,
    api_key: str | None = None,
    client: CachedHttpClient | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Fetch coach data for a league+season.

    Returns DataFrame with columns:
        coach_name, nationality, team_name, appointment_date
    """
    resolved_key = _resolve_api_key(api_key)
    resolved_settings = settings or PlatformSettings.from_root()
    resolved_client = client or CachedHttpClient(settings=resolved_settings)
    counter = _DailyRequestCounter(
        resolved_settings.log_root / SOURCE_NAME / "daily_counter"
    )

    endpoint = f"/coachs?league={league_id}&season={season}"
    records = _paginate_fetch(
        endpoint=endpoint,
        api_key=resolved_key,
        client=resolved_client,
        settings=resolved_settings,
        counter=counter,
        force_refresh=force_refresh,
    )

    rows = []
    for rec in records:
        coach = rec.get("coach", {}) if "coach" in rec else rec
        # The coaches endpoint returns career info; extract current team
        career = rec.get("career", [])
        # Find the team matching the requested league+season
        team_name = ""
        appointment_date = ""
        for job in career:
            team_info = job.get("team", {})
            if team_info.get("id"):
                team_name = team_info.get("name", "")
                appointment_date = job.get("start", "")
                break  # Use most recent career entry

        rows.append(
            {
                "coach_name": coach.get("name", ""),
                "nationality": coach.get("nationality", ""),
                "team_name": team_name,
                "appointment_date": appointment_date,
            }
        )

    frame = pd.DataFrame.from_records(rows)
    cache_path = (
        resolved_settings.raw_root
        / SOURCE_NAME
        / "coaches"
        / str(league_id)
        / f"{season}.json"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if not frame.empty:
        frame.to_json(cache_path, orient="records", force_ascii=False)

    merged_payload = cache_path.read_bytes() if cache_path.exists() else b"[]"
    metadata = _build_result_metadata(
        source_uri=f"{BASE_URL}{endpoint}",
        cache_path=cache_path,
        payload=merged_payload,
        record_count=len(frame),
        client=resolved_client,
    )
    return AdapterResult(dataframe=frame, metadata=metadata)


def _build_result_metadata(
    *,
    source_uri: str,
    cache_path: Path,
    payload: bytes,
    record_count: int,
    client: CachedHttpClient,
) -> SourceMetadata:
    """Build SourceMetadata for a merged result using the client's internal helper."""
    import hashlib

    from scoutlab.schemas import SourceRequestLogEntry

    payload_sha256 = hashlib.sha256(payload).hexdigest()
    request_log = SourceRequestLogEntry(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        requested_at=datetime.now(tz=UTC),
        parser_version=PARSER_VERSION,
        response_sha256=payload_sha256,
        cache_hit=True,
        status_code=None,
    )
    from scoutlab.storage import append_source_request_log

    append_source_request_log(
        client.settings.log_root / "ingestion" / "source_request_log.jsonl",
        request_log,
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

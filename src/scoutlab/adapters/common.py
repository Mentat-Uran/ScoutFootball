"""Shared HTTP/cache helpers for source adapters."""

from __future__ import annotations

import gzip
import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scoutlab.adapters.base import SourceMetadata
from scoutlab.config import PlatformSettings
from scoutlab.schemas import SourceRequestLogEntry
from scoutlab.storage import append_source_request_log

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_RATE_LIMIT_SECONDS = 0.25
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY_SECONDS = 0.5
DEFAULT_USER_AGENT = "football-data-platform/0.1.0"


class SourceAdapterError(RuntimeError):
    """Base class for structured adapter failures."""


class SourceFetchError(SourceAdapterError):
    """Raised when a remote fetch fails after retries."""


class SourceSchemaError(SourceAdapterError):
    """Raised when a fetched payload does not satisfy the expected schema."""


@dataclass(frozen=True)
class HttpResponse:
    """Minimal transport response for adapter fetches."""

    body: bytes
    status_code: int


@dataclass(frozen=True)
class FetchArtifact:
    """Raw payload plus request metadata returned by the cache client."""

    payload: bytes
    metadata: SourceMetadata


class HttpTransport(Protocol):
    """Callable transport contract for tests and production fetches."""

    def __call__(
        self,
        url: str,
        timeout_seconds: float,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        """Fetch one URL and return bytes plus status."""


class CachedHttpClient:
    """Filesystem-cached HTTP client with simple rate limiting and retries."""

    def __init__(
        self,
        *,
        settings: PlatformSettings | None = None,
        transport: HttpTransport | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
    ) -> None:
        self.settings = settings or PlatformSettings.from_root()
        self.transport = transport or default_http_transport
        self.sleep_fn = sleep_fn
        self.rate_limit_seconds = rate_limit_seconds
        self.retry_attempts = retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self._last_request_monotonic: float | None = None

    def fetch(
        self,
        *,
        source_name: str,
        source_uri: str,
        cache_path: Path,
        parser_version: str,
        force_refresh: bool = False,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        request_headers: dict[str, str] | None = None,
    ) -> FetchArtifact:
        """Fetch one payload, preferring cache when available."""

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if cache_path.exists() and not force_refresh:
            payload = cache_path.read_bytes()
            return FetchArtifact(
                payload=payload,
                metadata=self._build_metadata(
                    source_name=source_name,
                    source_uri=source_uri,
                    cache_path=cache_path,
                    parser_version=parser_version,
                    payload=payload,
                    cache_hit=True,
                    status_code=None,
                ),
            )

        last_error: Exception | None = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                self._respect_rate_limit()
                response = self.transport(source_uri, timeout_seconds, request_headers)
                self._last_request_monotonic = time.monotonic()
                if response.status_code >= 400:
                    raise SourceFetchError(
                        f"{source_name} returned HTTP {response.status_code} for {source_uri}",
                    )
                cache_path.write_bytes(response.body)
                return FetchArtifact(
                    payload=response.body,
                    metadata=self._build_metadata(
                        source_name=source_name,
                        source_uri=source_uri,
                        cache_path=cache_path,
                        parser_version=parser_version,
                        payload=response.body,
                        cache_hit=False,
                        status_code=response.status_code,
                    ),
                )
            except (HTTPError, URLError, TimeoutError, SourceFetchError, OSError) as error:
                last_error = error
                if attempt == self.retry_attempts:
                    break
                self.sleep_fn(self.retry_delay_seconds)

        raise SourceFetchError(
            f"Failed to fetch {source_name} from {source_uri} after {self.retry_attempts} attempts",
        ) from last_error

    def _build_metadata(
        self,
        *,
        source_name: str,
        source_uri: str,
        cache_path: Path,
        parser_version: str,
        payload: bytes,
        cache_hit: bool,
        status_code: int | None,
    ) -> SourceMetadata:
        payload_sha256 = hashlib.sha256(payload).hexdigest()
        request_log = SourceRequestLogEntry(
            source_name=source_name,
            source_uri=source_uri,
            requested_at=datetime.now(tz=UTC),
            parser_version=parser_version,
            response_sha256=payload_sha256,
            cache_hit=cache_hit,
            status_code=status_code,
        )
        append_source_request_log(
            self.settings.log_root / "ingestion" / "source_request_log.jsonl",
            request_log,
        )
        return SourceMetadata(
            source_name=source_name,
            source_uri=source_uri,
            cache_path=cache_path,
            parser_version=parser_version,
            source_file_sha256=payload_sha256,
            request_log=request_log,
            record_count=0,
        )

    def _respect_rate_limit(self) -> None:
        if self._last_request_monotonic is None:
            return
        elapsed = time.monotonic() - self._last_request_monotonic
        remaining = self.rate_limit_seconds - elapsed
        if remaining > 0:
            self.sleep_fn(remaining)


def default_http_transport(
    url: str,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
) -> HttpResponse:
    """Default urllib-based transport."""

    request_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers is not None:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=timeout_seconds) as response:
        body = response.read()
        status_code = getattr(response, "status", 200)
        content_encoding = response.headers.get("Content-Encoding", "")
    if content_encoding.lower() == "gzip" or body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return HttpResponse(body=body, status_code=status_code)


def with_record_count(metadata: SourceMetadata, record_count: int) -> SourceMetadata:
    """Return metadata with an updated row count."""

    return SourceMetadata(
        source_name=metadata.source_name,
        source_uri=metadata.source_uri,
        cache_path=metadata.cache_path,
        parser_version=metadata.parser_version,
        source_file_sha256=metadata.source_file_sha256,
        request_log=metadata.request_log,
        record_count=record_count,
    )

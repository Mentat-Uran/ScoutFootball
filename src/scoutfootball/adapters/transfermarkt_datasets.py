"""Transfermarkt-datasets adapter for bulk data import from pre-built DuckDB.

Downloads the dcaribou/transfermarkt-datasets DuckDB file (~500MB) and
exports individual tables to Parquet for downstream ingestion.
"""

from __future__ import annotations

import hashlib
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scoutfootball.adapters.base import AdapterResult, SourceMetadata
from scoutfootball.adapters.common import SourceSchemaError
from scoutfootball.config import PlatformSettings
from scoutfootball.schemas import SourceRequestLogEntry
from scoutfootball.storage.duckdb_io import connect_duckdb

logger = logging.getLogger(__name__)

SOURCE_NAME = "transfermarkt_datasets"
PARSER_VERSION = "transfermarkt_datasets/v0.1.0"
DUCKDB_URL = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/transfermarkt-datasets.duckdb"
DUCKDB_FILENAME = "transfermarkt-datasets.duckdb"
DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB

EXPECTED_TABLES = frozenset(
    [
        "players",
        "clubs",
        "competitions",
        "games",
        "appearances",
        "player_valuations",
        "club_games",
        "game_events",
        "game_lineups",
        "transfers",
        "countries",
        "national_teams",
    ]
)

PRIORITY_TABLES = [
    "player_valuations",
    "game_lineups",
    "game_events",
    "transfers",
    "appearances",
    "players",
]


def download_duckdb(
    *,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> Path:
    """Download the pre-built transfermarkt-datasets DuckDB file.

    Returns the path to the downloaded (or cached) file.
    """
    resolved_settings = settings or PlatformSettings.from_root()
    dest_dir = resolved_settings.raw_root / SOURCE_NAME
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / DUCKDB_FILENAME

    if dest_path.exists() and not force_refresh:
        size_mb = dest_path.stat().st_size / (1024 * 1024)
        logger.info("Cached DuckDB found (%.1f MB): %s", size_mb, dest_path)
        return dest_path

    logger.info("Downloading transfermarkt-datasets DuckDB from %s", DUCKDB_URL)
    tmp_path = dest_path.with_suffix(".duckdb.tmp")

    try:
        request = Request(DUCKDB_URL, headers={"User-Agent": "football-data-platform/0.1.0"})
        with urlopen(request, timeout=120) as response:
            total_size = response.headers.get("Content-Length")
            total_mb = int(total_size) / (1024 * 1024) if total_size else None
            downloaded = 0
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    _report_progress(downloaded, total_mb)
        print()  # newline after progress
        tmp_path.replace(dest_path)
        size_mb = dest_path.stat().st_size / (1024 * 1024)
        logger.info("Download complete (%.1f MB): %s", size_mb, dest_path)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Failed to download transfermarkt-datasets DuckDB: {exc}"
        ) from exc

    return dest_path


def export_table(
    table_name: str,
    *,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Export one table from the pre-built DuckDB to Parquet.

    Returns an AdapterResult with the DataFrame and source metadata.
    """
    if table_name not in EXPECTED_TABLES:
        raise ValueError(
            f"Unknown table '{table_name}'. Expected one of: {sorted(EXPECTED_TABLES)}"
        )

    resolved_settings = settings or PlatformSettings.from_root()
    dest_dir = resolved_settings.raw_root / SOURCE_NAME
    dest_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = dest_dir / f"{table_name}.parquet"

    if parquet_path.exists() and not force_refresh:
        con = connect_duckdb()
        try:
            frame = con.execute("SELECT * FROM read_parquet(?)", [str(parquet_path)]).fetchdf()
        finally:
            con.close()
        metadata = _build_metadata(
            settings=resolved_settings,
            source_uri=f"duckdb:{table_name}",
            cache_path=parquet_path,
            payload_hash=_sha256_file(parquet_path),
            record_count=len(frame),
            cache_hit=True,
        )
        return AdapterResult(dataframe=frame, metadata=metadata)

    duckdb_path = download_duckdb(settings=resolved_settings, force_refresh=False)
    _validate_duckdb_tables(duckdb_path)

    con = connect_duckdb(database_path=duckdb_path, read_only=True)
    try:
        available = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
        if table_name not in available:
            raise SourceSchemaError(
                f"Table '{table_name}' not found in DuckDB. Available: {available}"
            )
        frame = con.execute(f'SELECT * FROM "{table_name}"').fetchdf()
    finally:
        con.close()

    frame.to_parquet(parquet_path, index=False)
    logger.info("Exported %s: %d rows -> %s", table_name, len(frame), parquet_path)

    metadata = _build_metadata(
        settings=resolved_settings,
        source_uri=f"duckdb:{table_name}",
        cache_path=parquet_path,
        payload_hash=_sha256_file(parquet_path),
        record_count=len(frame),
        cache_hit=False,
    )
    return AdapterResult(dataframe=frame, metadata=metadata)


def export_priority_tables(
    *,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> dict[str, str]:
    """Export the 6 priority tables to Parquet.

    Returns a dict mapping table_name -> status string ("ok" or error message).
    """
    results: dict[str, str] = {}
    for table_name in PRIORITY_TABLES:
        try:
            result = export_table(table_name, settings=settings, force_refresh=force_refresh)
            results[table_name] = f"ok ({result.metadata.record_count} rows)"
        except Exception as exc:
            results[table_name] = f"error: {exc}"
            logger.error("Failed to export %s: %s", table_name, exc)
    return results


def _validate_duckdb_tables(duckdb_path: Path) -> None:
    """Verify the DuckDB file contains the expected tables."""
    con = connect_duckdb(database_path=duckdb_path, read_only=True)
    try:
        available = frozenset(row[0] for row in con.execute("SHOW TABLES").fetchall())
    finally:
        con.close()

    missing = EXPECTED_TABLES - available
    if missing:
        raise SourceSchemaError(
            f"DuckDB file is missing expected tables: {sorted(missing)}. "
            f"Available: {sorted(available)}"
        )


def _report_progress(downloaded: int, total_mb: float | None) -> None:
    """Print download progress to stderr."""
    downloaded_mb = downloaded / (1024 * 1024)
    if total_mb is not None:
        pct = downloaded_mb / total_mb * 100
        sys.stderr.write(f"\r  Downloading: {downloaded_mb:.1f}/{total_mb:.1f} MB ({pct:.0f}%)")
    else:
        sys.stderr.write(f"\r  Downloading: {downloaded_mb:.1f} MB")
    sys.stderr.flush()


def _build_metadata(
    *,
    settings: PlatformSettings,
    source_uri: str,
    cache_path: Path,
    payload_hash: str,
    record_count: int,
    cache_hit: bool,
) -> SourceMetadata:
    """Build SourceMetadata for an exported table."""
    request_log = SourceRequestLogEntry(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        requested_at=datetime.now(tz=UTC),
        parser_version=PARSER_VERSION,
        response_sha256=payload_hash,
        cache_hit=cache_hit,
        status_code=None,
    )
    return SourceMetadata(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        cache_path=cache_path,
        parser_version=PARSER_VERSION,
        source_file_sha256=payload_hash,
        request_log=request_log,
        record_count=record_count,
    )


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 of a file, reading in chunks to handle large files."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

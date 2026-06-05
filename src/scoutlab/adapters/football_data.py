"""Football-Data.co.uk adapter."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pandas as pd

from scoutlab.adapters.base import AdapterResult
from scoutlab.adapters.common import (
    CachedHttpClient,
    SourceSchemaError,
    with_record_count,
)
from scoutlab.config import PlatformSettings

logger = logging.getLogger(__name__)

SOURCE_NAME = "football_data"
PARSER_VERSION = "football_data/v0.1.0"
SEASON_PATTERN = re.compile(r"^\d{4}$")
BASE_URL = "https://www.football-data.co.uk/mmz4281"
REQUIRED_COLUMNS = ("Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG")

LEAGUE_CODE_NAMES: dict[str, str] = {
    "E0": "Premier League",
    "E1": "Championship",
    "E2": "League One",
    "E3": "League Two",
    "EC": "National League",
    "SC0": "Scottish Premiership",
    "SC1": "Scottish Championship",
    "SC2": "Scottish League One",
    "SC3": "Scottish League Two",
    "D1": "Bundesliga",
    "D2": "2. Bundesliga",
    "I1": "Serie A",
    "I2": "Serie B",
    "SP1": "La Liga",
    "SP2": "Segunda División",
    "F1": "Ligue 1",
    "F2": "Ligue 2",
    "N1": "Eredivisie",
    "B1": "First Division A",
    "P1": "Primeira Liga",
    "T1": "Süper Lig",
    "G1": "Super League",
}


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


def rebuild_combined_results(
    data_dir: Path,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Rebuild combined_results.parquet from all cached CSVs.

    Scans all season directories under *data_dir*, reads every CSV file,
    adds league name and season columns, and saves the combined DataFrame
    to *output_path* (default: data_dir / "combined_results.parquet").

    Returns a metadata dict with:
      total_rows     – sum of rows across all CSVs
      parquet_rows   – rows in the saved Parquet
      league_seasons – sorted list of "{league_code}/{season}" strings
      input_hash     – SHA-256 of concatenated file hashes
      rebuild_time   – ISO-8601 timestamp of the rebuild
    """
    data_dir = Path(data_dir)
    resolved_output = output_path or data_dir / "combined_results.parquet"

    season_dirs = sorted(
        d for d in data_dir.iterdir()
        if d.is_dir() and SEASON_PATTERN.fullmatch(d.name)
    )

    frames: list[pd.DataFrame] = []
    league_seasons: list[str] = []
    total_rows = 0
    file_hashes: list[str] = []

    for season_dir in season_dirs:
        season = season_dir.name
        csv_files = sorted(season_dir.glob("*.csv"))
        for csv_path in csv_files:
            league_code = csv_path.stem
            league_name = LEAGUE_CODE_NAMES.get(league_code, league_code)
            try:
                frame = pd.read_csv(csv_path, encoding="utf-8-sig")
            except UnicodeDecodeError:
                try:
                    frame = pd.read_csv(csv_path, encoding="latin1")
                except Exception as exc:
                    logger.warning("Skipping %s: %s", csv_path, exc)
                    continue
            except Exception as exc:
                logger.warning("Skipping %s: %s", csv_path, exc)
                continue

            if frame.empty:
                continue

            frame["league"] = league_name
            frame["season"] = season
            frames.append(frame)
            total_rows += len(frame)
            league_seasons.append(f"{league_code}/{season}")

            file_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()
            file_hashes.append(file_hash)

    if not frames:
        combined = pd.DataFrame()
    else:
        combined = pd.concat(frames, ignore_index=True, sort=False)

    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(resolved_output, index=False)

    input_hash = hashlib.sha256("".join(file_hashes).encode()).hexdigest() if file_hashes else ""
    rebuild_time = datetime.now(tz=UTC).isoformat()

    metadata: dict[str, object] = {
        "total_rows": total_rows,
        "parquet_rows": len(combined),
        "league_seasons": sorted(league_seasons),
        "input_hash": input_hash,
        "rebuild_time": rebuild_time,
    }

    logger.info(
        "Rebuilt combined_results.parquet: %d raw rows -> %d parquet rows, "
        "%d league-seasons, hash=%s",
        total_rows,
        len(combined),
        len(league_seasons),
        input_hash[:12],
    )

    return metadata

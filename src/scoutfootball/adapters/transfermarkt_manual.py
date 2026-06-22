"""Manual Transfermarkt snapshot importer without network capabilities."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from scoutfootball.adapters.base import AdapterResult, SourceMetadata
from scoutfootball.adapters.common import SourceSchemaError
from scoutfootball.schemas import SourceRequestLogEntry
from scoutfootball.storage.duckdb_io import connect_duckdb

SOURCE_NAME = "transfermarkt_manual"
PARSER_VERSION = "transfermarkt_manual/v0.1.0"
REQUIRED_OUTPUT_COLUMNS = (
    "player_name",
    "team_name",
    "snapshot_date",
    "market_value",
    "contract_end",
    "data_source",
    "import_method",
)
FIELD_ALIASES = {
    "player_name": ("player_name", "player", "name", "Player", "Name"),
    "team_name": ("team_name", "club", "team", "Club", "Squad"),
    "snapshot_date": ("snapshot_date", "date", "Date", "snapshot"),
    "market_value_raw": (
        "market_value",
        "market_value_raw",
        "market value",
        "Market Value",
        "Market value",
    ),
    "contract_end": (
        "contract_end",
        "contract expires",
        "Contract expires",
        "Contract Expires",
    ),
    "transfer_fee_raw": (
        "transfer_fee",
        "transfer fee",
        "Transfer Fee",
        "fee",
    ),
}
MONEY_PATTERN = re.compile(r"(?P<value>[\d.,]+)\s*(?P<suffix>[mk]|bn)?", re.IGNORECASE)


def load_snapshot(path: str | Path) -> AdapterResult:
    """Load a local Transfermarkt CSV or Parquet snapshot."""

    snapshot_path = Path(path).expanduser().resolve()
    frame = _read_local_snapshot(snapshot_path)
    normalized = _normalize_snapshot_frame(frame)
    request_log = SourceRequestLogEntry(
        source_name=SOURCE_NAME,
        source_uri=snapshot_path.as_uri(),
        requested_at=datetime.now(tz=UTC),
        parser_version=PARSER_VERSION,
        response_sha256=_sha256_file(snapshot_path),
        cache_hit=True,
        status_code=None,
    )
    metadata = SourceMetadata(
        source_name=SOURCE_NAME,
        source_uri=snapshot_path.as_uri(),
        cache_path=snapshot_path,
        parser_version=PARSER_VERSION,
        source_file_sha256=request_log.response_sha256,
        request_log=request_log,
        record_count=len(normalized),
    )
    return AdapterResult(dataframe=normalized, metadata=metadata)


def _read_local_snapshot(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Snapshot file does not exist: {path}")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".parquet":
        connection = connect_duckdb()
        try:
            return connection.execute("SELECT * FROM read_parquet(?)", [str(path)]).fetchdf()
        finally:
            connection.close()
    raise ValueError("Snapshot file must use .csv or .parquet")


def _normalize_snapshot_frame(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = frame.copy()
    column_map = {column: _canonical_column_name(column) for column in renamed.columns}
    renamed = renamed.rename(columns=column_map)

    missing = tuple(
        column
        for column in ("player_name", "team_name", "snapshot_date", "market_value_raw")
        if column not in renamed.columns
    )
    if missing:
        missing_text = ", ".join(missing)
        raise SourceSchemaError(f"Transfermarkt manual snapshot is missing columns: {missing_text}")

    normalized = pd.DataFrame(
        {
            "player_name": renamed["player_name"].astype("string").str.strip(),
            "team_name": renamed["team_name"].astype("string").str.strip(),
            "snapshot_date": pd.to_datetime(renamed["snapshot_date"], errors="coerce").dt.date,
            "market_value": renamed["market_value_raw"].map(_parse_money),
            "contract_end": pd.to_datetime(
                renamed.get("contract_end"),
                errors="coerce",
            ).dt.date,
            "transfer_fee": renamed.get(
                "transfer_fee_raw",
                pd.Series(dtype="object"),
            ).map(_parse_money),
            "data_source": SOURCE_NAME,
            "import_method": "local_file",
        }
    )
    if normalized["snapshot_date"].isna().any():
        raise SourceSchemaError(
            "Transfermarkt manual snapshot contains invalid snapshot_date values",
        )
    if normalized["market_value"].isna().any():
        raise SourceSchemaError(
            "Transfermarkt manual snapshot contains invalid market_value values",
        )
    return normalized


def _canonical_column_name(column: str) -> str:
    for canonical, aliases in FIELD_ALIASES.items():
        if column in aliases:
            return canonical
    return column


def _parse_money(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("€", "").replace("$", "").replace("£", "")
    text = text.replace(" ", "").replace(",", ".")
    if text in {"", "-", "nan", "None"}:
        return None
    match = MONEY_PATTERN.fullmatch(text)
    if match is None:
        return None
    amount = float(match.group("value"))
    suffix = (match.group("suffix") or "").lower()
    multiplier = {"": 1.0, "k": 1_000.0, "m": 1_000_000.0, "bn": 1_000_000_000.0}[suffix]
    return amount * multiplier


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_to_truth_labels(
    path: str | Path,
    season: str,
    confidence: str = "medium",
) -> pd.DataFrame:
    """Import a Transfermarkt snapshot and convert to truth labels format.

    This is the bridge between the manual Transfermarkt importer and the
    player_truth_labels.parquet schema used by the rating optimizer.

    Args:
        path: Path to the local CSV or Parquet snapshot.
        season: Season identifier (e.g., "2526").
        confidence: Confidence level ("high", "medium", "low").
            Transfermarkt market values are proxy labels, so "medium" is default.

    Returns:
        DataFrame matching the player_truth_labels schema.
    """
    result = load_snapshot(path)
    df = result.dataframe

    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    labels = pd.DataFrame({
        "player_id": df["player_name"].astype("string"),
        "season": season,
        "label_source": "transfermarkt_value",
        "label_confidence": confidence,
        "label_value": df["market_value"].astype("float64"),
        "as_of_date": today,
        "position_scope": "all",
        "manual_review_flag": False,
    })

    # Validate using truth_labels module
    from scoutfootball.evaluation.truth_labels import validate_truth_labels
    errors = validate_truth_labels(labels)
    if errors:
        raise ValueError(f"Truth labels validation failed: {'; '.join(errors)}")

    return labels

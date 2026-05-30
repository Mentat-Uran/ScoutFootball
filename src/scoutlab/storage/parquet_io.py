"""Parquet writers that preserve idempotency and ingest metadata."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict

from scoutlab.schemas import IngestMetadata, TableDefinition
from scoutlab.storage.duckdb_io import connect_duckdb
from scoutlab.storage.metadata_logging import write_ingest_metadata


class DatasetWriteResult(BaseModel):
    """Summary of one parquet write operation."""

    model_config = ConfigDict(frozen=True)

    dataset_path: Path
    metadata_path: Path
    input_row_count: int
    output_row_count: int
    deduplicated_rows: int


def write_parquet_dataset(
    frame: pd.DataFrame,
    dataset_path: Path | str,
    *,
    metadata: IngestMetadata,
    table_definition: TableDefinition | None = None,
) -> DatasetWriteResult:
    """Write a dataset idempotently by primary key and persist ingest metadata."""

    target_path = Path(dataset_path)
    primary_keys = metadata.primary_keys

    if table_definition is not None:
        table_definition.validate_columns(frame.columns)

    _validate_primary_keys(frame, primary_keys)
    existing = _read_existing_dataset(target_path)
    combined = pd.concat((existing, frame.copy()), ignore_index=True, sort=False)
    deduplicated = combined.drop_duplicates(subset=list(primary_keys), keep="last")
    if primary_keys:
        deduplicated = deduplicated.sort_values(list(primary_keys), kind="stable")
    deduplicated = deduplicated.reset_index(drop=True)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    _write_frame_to_parquet(deduplicated, target_path)

    deduplicated_rows = len(combined) - len(deduplicated)
    metadata_path = write_ingest_metadata(
        target_path,
        metadata,
        output_row_count=len(deduplicated),
        deduplicated_rows=deduplicated_rows,
    )
    return DatasetWriteResult(
        dataset_path=target_path,
        metadata_path=metadata_path,
        input_row_count=len(frame),
        output_row_count=len(deduplicated),
        deduplicated_rows=deduplicated_rows,
    )


def _read_existing_dataset(dataset_path: Path) -> pd.DataFrame:
    if not dataset_path.exists():
        return pd.DataFrame()
    connection = connect_duckdb()
    try:
        return connection.execute(
            "SELECT * FROM read_parquet(?)",
            [str(dataset_path)],
        ).fetchdf()
    finally:
        connection.close()


def _write_frame_to_parquet(frame: pd.DataFrame, dataset_path: Path) -> None:
    connection = connect_duckdb()
    try:
        connection.register("deduplicated_frame", frame)
        escaped_path = str(dataset_path).replace("'", "''")
        connection.execute(
            f"COPY deduplicated_frame TO '{escaped_path}' (FORMAT PARQUET)",
        )
    finally:
        connection.close()


def _validate_primary_keys(frame: pd.DataFrame, primary_keys: tuple[str, ...]) -> None:
    missing_keys = tuple(key for key in primary_keys if key not in frame.columns)
    if missing_keys:
        missing_text = ", ".join(missing_keys)
        raise ValueError(f"Frame is missing primary key columns: {missing_text}")
    if primary_keys and frame.loc[:, list(primary_keys)].isnull().any().any():
        keys_text = ", ".join(primary_keys)
        raise ValueError(f"Primary key columns cannot contain null values: {keys_text}")

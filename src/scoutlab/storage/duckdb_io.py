"""DuckDB helpers for local analytical storage."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


def connect_duckdb(
    database_path: Path | str | None = None,
    *,
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection for local queries."""

    location = ":memory:" if database_path is None else str(database_path)
    return duckdb.connect(location, read_only=read_only)


def query_parquet(
    connection: duckdb.DuckDBPyConnection,
    dataset_path: Path | str,
    *,
    sql: str | None = None,
) -> pd.DataFrame:
    """Query a parquet dataset, optionally wrapping it with custom SQL."""

    dataset_location = str(dataset_path)
    if sql is None:
        query = "SELECT * FROM read_parquet(?)"
    else:
        query = sql
    return connection.execute(query, [dataset_location]).fetchdf()

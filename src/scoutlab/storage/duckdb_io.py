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


def create_ratings_database(
    database_path: Path | str,
    player_ratings: pd.DataFrame,
    model_meta: pd.DataFrame,
    league_metrics: pd.DataFrame,
    team_coverage: pd.DataFrame,
) -> None:
    """Create or overwrite the ratings DuckDB database with 4 tables.

    Idempotent: drops existing tables before writing.
    """
    con = connect_duckdb(database_path)
    try:
        for table_name in ["player_ratings", "model_meta", "league_metrics", "team_coverage"]:
            con.execute(f"DROP TABLE IF EXISTS {table_name}")

        con.register("player_ratings_view", player_ratings)
        con.execute("CREATE TABLE player_ratings AS SELECT * FROM player_ratings_view")

        con.register("model_meta_view", model_meta)
        con.execute("CREATE TABLE model_meta AS SELECT * FROM model_meta_view")

        con.register("league_metrics_view", league_metrics)
        con.execute("CREATE TABLE league_metrics AS SELECT * FROM league_metrics_view")

        con.register("team_coverage_view", team_coverage)
        con.execute("CREATE TABLE team_coverage AS SELECT * FROM team_coverage_view")
    finally:
        con.close()


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

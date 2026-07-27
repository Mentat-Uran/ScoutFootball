"""Tests for storage/duckdb_io.py — DuckDB helpers for local analytical storage.

Covers the three public functions:
    - connect_duckdb (in-memory, file, read-only)
    - create_ratings_database (4-table creation, idempotency, data integrity)
    - query_parquet (default SELECT *, custom SQL with parameterized path)

These are critical storage-path functions used by the CLI
(``export-duckdb``), ``storage/parquet_io.py``, and two transfermarkt
adapters. A silent bug here would corrupt the ratings DB or break
parquet queries across the pipeline.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from scoutfootball.storage.duckdb_io import (
    connect_duckdb,
    create_ratings_database,
    query_parquet,
)


# ---------------------------------------------------------------------------
# connect_duckdb
# ---------------------------------------------------------------------------


class TestConnectDuckDB:
    def test_in_memory_connection_is_usable(self) -> None:
        con = connect_duckdb(None)
        try:
            result = con.execute("SELECT 1 AS value").fetchdf()
            assert len(result) == 1
            assert result.iloc[0]["value"] == 1
        finally:
            con.close()

    def test_file_connection_persists_across_connections(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.duckdb"
        con1 = connect_duckdb(db_path)
        try:
            con1.execute("CREATE TABLE persistent (x INTEGER)")
            con1.execute("INSERT INTO persistent VALUES (42)")
        finally:
            con1.close()

        # Reopen the same file — data must persist.
        con2 = connect_duckdb(db_path)
        try:
            result = con2.execute("SELECT x FROM persistent").fetchdf()
            assert len(result) == 1
            assert result.iloc[0]["x"] == 42
        finally:
            con2.close()

    def test_read_only_flag_rejects_writes(self, tmp_path: Path) -> None:
        db_path = tmp_path / "readonly.duckdb"
        # Create and write via a read-write connection first.
        con_rw = connect_duckdb(db_path)
        try:
            con_rw.execute("CREATE TABLE t (v INTEGER)")
            con_rw.execute("INSERT INTO t VALUES (1)")
        finally:
            con_rw.close()

        # Reopen read-only — writes must fail.
        con_ro = connect_duckdb(db_path, read_only=True)
        try:
            with pytest.raises(duckdb.Error):
                con_ro.execute("INSERT INTO t VALUES (2)")
        finally:
            con_ro.close()


# ---------------------------------------------------------------------------
# create_ratings_database
# ---------------------------------------------------------------------------


def _make_ratings_inputs() -> dict[str, pd.DataFrame]:
    """Build minimal valid inputs for create_ratings_database."""
    return {
        "player_ratings": pd.DataFrame({
            "player_id": ["p1", "p2", "p3"],
            "player_name": ["Alice", "Bob", "Carol"],
            "rating": [7.5, 6.8, 8.1],
            "position_group": ["FW", "MF", "DF"],
        }),
        "model_meta": pd.DataFrame({
            "model_type": ["dixon_coles"],
            "num_matches": [100],
            "rho": [-0.05],
        }),
        "league_metrics": pd.DataFrame({
            "league_id": ["PL"],
            "mean_goals": [1.35],
            "num_teams": [20],
        }),
        "team_coverage": pd.DataFrame({
            "team_id": ["t1", "t2"],
            "team_name": ["Team Alpha", "Team Beta"],
            "matches_played": [10, 8],
        }),
    }


class TestCreateRatingsDatabase:
    def test_creates_all_four_tables(self, tmp_path: Path) -> None:
        db_path = tmp_path / "ratings.duckdb"
        inputs = _make_ratings_inputs()
        create_ratings_database(db_path, **inputs)

        con = connect_duckdb(db_path, read_only=True)
        try:
            tables = {
                row[0]
                for row in con.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'main'"
                ).fetchall()
            }
            assert tables == {
                "player_ratings", "model_meta", "league_metrics", "team_coverage",
            }
        finally:
            con.close()

    def test_table_row_counts_match_input(self, tmp_path: Path) -> None:
        db_path = tmp_path / "ratings.duckdb"
        inputs = _make_ratings_inputs()
        create_ratings_database(db_path, **inputs)

        con = connect_duckdb(db_path, read_only=True)
        try:
            assert len(con.execute("SELECT * FROM player_ratings").fetchdf()) == 3
            assert len(con.execute("SELECT * FROM model_meta").fetchdf()) == 1
            assert len(con.execute("SELECT * FROM league_metrics").fetchdf()) == 1
            assert len(con.execute("SELECT * FROM team_coverage").fetchdf()) == 2
        finally:
            con.close()

    def test_data_integrity_player_ratings(self, tmp_path: Path) -> None:
        db_path = tmp_path / "ratings.duckdb"
        inputs = _make_ratings_inputs()
        create_ratings_database(db_path, **inputs)

        con = connect_duckdb(db_path, read_only=True)
        try:
            df = con.execute(
                "SELECT player_id, player_name, rating "
                "FROM player_ratings ORDER BY rating DESC"
            ).fetchdf()
            assert df.iloc[0]["player_id"] == "p3"
            assert df.iloc[0]["player_name"] == "Carol"
            assert df.iloc[0]["rating"] == pytest.approx(8.1)
        finally:
            con.close()

    def test_idempotent_drop_and_recreate(self, tmp_path: Path) -> None:
        """Running create_ratings_database twice must not duplicate rows."""
        db_path = tmp_path / "ratings.duckdb"
        inputs = _make_ratings_inputs()
        create_ratings_database(db_path, **inputs)

        # Second call with different data — must replace, not append.
        inputs["player_ratings"] = pd.DataFrame({
            "player_id": ["p9"],
            "player_name": ["Dave"],
            "rating": [9.0],
            "position_group": ["GK"],
        })
        create_ratings_database(db_path, **inputs)

        con = connect_duckdb(db_path, read_only=True)
        try:
            df = con.execute("SELECT * FROM player_ratings").fetchdf()
            assert len(df) == 1
            assert df.iloc[0]["player_id"] == "p9"
        finally:
            con.close()

    def test_overwrites_existing_tables_from_prior_schema(self, tmp_path: Path) -> None:
        """Even if a table with a different schema pre-exists, the drop+
        recreate must succeed (not fail on schema mismatch)."""
        db_path = tmp_path / "ratings.duckdb"
        # Pre-create a player_ratings table with an incompatible schema.
        con_pre = connect_duckdb(db_path)
        try:
            con_pre.execute(
                "CREATE TABLE player_ratings (old_col TEXT, another INTEGER)"
            )
        finally:
            con_pre.close()

        inputs = _make_ratings_inputs()
        # Must not raise — drop+recreate handles the schema change.
        create_ratings_database(db_path, **inputs)

        con = connect_duckdb(db_path, read_only=True)
        try:
            df = con.execute("SELECT * FROM player_ratings").fetchdf()
            assert "old_col" not in df.columns
            assert "player_id" in df.columns
            assert len(df) == 3
        finally:
            con.close()


# ---------------------------------------------------------------------------
# query_parquet
# ---------------------------------------------------------------------------


class TestQueryParquet:
    def test_default_select_star_returns_all_rows(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        pq_path = tmp_path / "data.parquet"
        df.to_parquet(pq_path, index=False)

        con = connect_duckdb(None)
        try:
            result = query_parquet(con, pq_path)
            assert len(result) == 3
            assert list(result.columns) == ["a", "b"]
            assert result.iloc[0]["a"] == 1
        finally:
            con.close()

    def test_custom_sql_with_parameterized_path(self, tmp_path: Path) -> None:
        df = pd.DataFrame({
            "team": ["A", "B", "C"],
            "goals": [0, 3, 1],
        })
        pq_path = tmp_path / "matches.parquet"
        df.to_parquet(pq_path, index=False)

        con = connect_duckdb(None)
        try:
            custom_sql = (
                "SELECT team, goals FROM read_parquet(?) "
                "WHERE goals > 1 ORDER BY goals DESC"
            )
            result = query_parquet(con, pq_path, sql=custom_sql)
            assert len(result) == 1
            assert result.iloc[0]["team"] == "B"
            assert result.iloc[0]["goals"] == 3
        finally:
            con.close()

    def test_empty_parquet_returns_empty_dataframe(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"a": [], "b": []})
        pq_path = tmp_path / "empty.parquet"
        df.to_parquet(pq_path, index=False)

        con = connect_duckdb(None)
        try:
            result = query_parquet(con, pq_path)
            assert len(result) == 0
        finally:
            con.close()

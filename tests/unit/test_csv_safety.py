"""Tests for CSV export formula-injection protection.

The frontend ``csvCell()`` is tested in ``test_frontend_security.py``;
these tests cover the Python-side ``csv_safety`` module and the
``_player_list_to_csv`` API helper that were added to satisfy the
AGENTS.md requirement that CSV exports must guard against spreadsheet
formula injection.
"""

from __future__ import annotations

import csv
import io

import pandas as pd
import pytest

from scoutfootball.api import _player_list_to_csv
from scoutfootball.storage.csv_safety import (
    dataframe_to_csv,
    sanitize_csv_cell,
    sanitize_csv_row,
    write_csv,
)


class TestSanitizeCsvCell:
    """Unit tests for the core cell sanitizer."""

    @pytest.mark.parametrize("payload", [
        "=SUM(A1:A2)",
        "+1+2",
        "-2+3",
        "@SUM",
        "\tSUM",
        "\rCMD",
    ])
    def test_dangerous_prefix_gets_quote(self, payload: str):
        result = sanitize_csv_cell(payload)
        assert result.startswith("'")
        assert payload in result

    @pytest.mark.parametrize("payload", [
        "Mohamed Salah",
        "Liverpool",
        "90",
        "",
        "0",
        " normal text",
    ])
    def test_safe_values_unchanged(self, payload: str):
        assert sanitize_csv_cell(payload) == payload

    def test_none_becomes_empty(self):
        assert sanitize_csv_cell(None) == ""

    def test_numeric_values_converted(self):
        assert sanitize_csv_cell(42) == "42"
        assert sanitize_csv_cell(3.14) == "3.14"


class TestSanitizeCsvRow:
    def test_sanitizes_each_cell(self):
        row = ["=evil", "safe", "+also_evil", "123"]
        result = sanitize_csv_row(row)
        assert result[0].startswith("'")
        assert result[1] == "safe"
        assert result[2].startswith("'")
        assert result[3] == "123"

    def test_preserves_length(self):
        row = ["a", "b", "c"]
        assert len(sanitize_csv_row(row)) == len(row)


class TestWriteCsv:
    def test_header_and_rows_sanitized(self):
        rows = [["=evil", "safe"], ["+bad", "42"]]
        result = write_csv(rows, header=["=name", "score"])
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        row1 = next(reader)
        row2 = next(reader)
        assert header[0].startswith("'")
        assert header[1] == "score"
        assert row1[0].startswith("'")
        assert row1[1] == "safe"
        assert row2[0].startswith("'")
        assert row2[1] == "42"

    def test_no_header(self):
        rows = [["=evil", "safe"]]
        result = write_csv(rows)
        reader = csv.reader(io.StringIO(result))
        row1 = next(reader)
        assert row1[0].startswith("'")
        assert row1[1] == "safe"


class TestDataframeToCsv:
    def test_formula_cells_sanitized(self):
        df = pd.DataFrame({
            "player": ["=evil", "Mohamed Salah", "+bad"],
            "team": ["Liverpool", "Arsenal", "Chelsea"],
        })
        result = dataframe_to_csv(df)
        reader = csv.reader(io.StringIO(result))
        next(reader)  # skip header
        row1 = next(reader)
        row2 = next(reader)
        row3 = next(reader)
        assert row1[0].startswith("'")
        assert row2[0] == "Mohamed Salah"
        assert row3[0].startswith("'")

    def test_matches_to_csv_for_safe_data(self):
        df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        safe = dataframe_to_csv(df)
        original = df.to_csv(index=False)
        assert safe == original

    def test_rejects_non_dataframe(self):
        with pytest.raises(TypeError):
            dataframe_to_csv([1, 2, 3])


class TestPlayerListToCsv:
    """Verify the API CSV export path applies sanitization."""

    def test_formula_injection_blocked(self):
        players = [
            {"player": "=CMD|calc", "team": "Liverpool", "score": 90},
            {"player": "Mohamed Salah", "team": "Arsenal", "score": 85},
        ]
        result = _player_list_to_csv(players)
        reader = csv.reader(io.StringIO(result))
        next(reader)  # skip header
        row1 = next(reader)
        row2 = next(reader)
        # The formula-injecting cell must be prefixed with a single quote
        assert row1[0].startswith("'")
        assert "CMD" in row1[0]
        # Safe rows are unchanged
        assert row2[0] == "Mohamed Salah"

    def test_empty_list_returns_empty(self):
        assert _player_list_to_csv([]) == ""

    def test_normal_data_unchanged(self):
        players = [
            {"player": "Mohamed Salah", "team": "Liverpool", "score": 90},
        ]
        result = _player_list_to_csv(players)
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        row1 = next(reader)
        assert header == ["player", "team", "score"]
        assert row1 == ["Mohamed Salah", "Liverpool", "90"]

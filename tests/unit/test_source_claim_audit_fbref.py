"""Tests for the fbref source_claim audit helper functions."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "dry_run_source_claim_audit_fbref.py"
)


def _load_audit_module():
    """Load the audit script as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "dry_run_source_claim_audit_fbref", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["dry_run_source_claim_audit_fbref"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit_mod():
    return _load_audit_module()


# ---------------------------------------------------------------------------
# _to_float
# ---------------------------------------------------------------------------


class TestToFloat:
    def test_int(self, audit_mod):
        assert audit_mod._to_float(5) == 5.0

    def test_float(self, audit_mod):
        assert audit_mod._to_float(3.14) == pytest.approx(3.14)

    def test_string_numeric(self, audit_mod):
        assert audit_mod._to_float("42") == 42.0

    def test_string_non_numeric(self, audit_mod):
        assert audit_mod._to_float("abc") is None

    def test_none(self, audit_mod):
        assert audit_mod._to_float(None) is None

    def test_nan(self, audit_mod):
        assert audit_mod._to_float(float("nan")) is None

    def test_empty_string(self, audit_mod):
        assert audit_mod._to_float("") is None


# ---------------------------------------------------------------------------
# _flatten_raw
# ---------------------------------------------------------------------------


class TestFlattenRaw:
    def test_returns_flat_dataframe_with_expected_columns(self, audit_mod):
        # Build a small raw-like frame with MultiIndex columns and index.
        cols = pd.MultiIndex.from_tuples(
            [
                ("nation", ""),
                ("pos", ""),
                ("age", ""),
                ("born", ""),
                ("Playing Time", "MP"),
                ("Playing Time", "Starts"),
                ("Playing Time", "Min"),
                ("Performance", "Gls"),
                ("Performance", "Ast"),
            ]
        )
        index = pd.MultiIndex.from_tuples(
            [
                ("ENG-Premier League", "2324", "Arsenal", "Aaron Ramsdale"),
                ("ESP-La Liga", "2324", "Barcelona", "Robert Lewandowski"),
            ],
            names=["league", "season", "team", "player"],
        )
        raw = pd.DataFrame(
            [
                ["ENG", "GK", "25", "1998", 10, 10, 900, 0, 0],
                ["POL", "FW", "35", "1988", 20, 20, 1800, 15, 5],
            ],
            columns=cols,
            index=index,
        )

        flat = audit_mod._flatten_raw(raw)

        assert list(flat.columns) == [
            "player",
            "season",
            "team",
            "born_raw",
            ("Performance", "Gls"),
            ("Performance", "Ast"),
            ("Playing Time", "Min"),
            ("Playing Time", "MP"),
            ("Playing Time", "Starts"),
        ]
        assert flat.iloc[0]["player"] == "Aaron Ramsdale"
        assert flat.iloc[0]["season"] == "2324"
        assert flat.iloc[0]["team"] == "Arsenal"
        assert flat.iloc[0]["born_raw"] == 1998
        assert flat.iloc[0][("Performance", "Gls")] == 0
        assert flat.iloc[1][("Performance", "Gls")] == 15

    def test_handles_nan_born(self, audit_mod):
        cols = pd.MultiIndex.from_tuples(
            [("born", ""), ("Playing Time", "MP"), ("Playing Time", "Starts"),
             ("Playing Time", "Min"), ("Performance", "Gls"), ("Performance", "Ast")]
        )
        index = pd.MultiIndex.from_tuples(
            [("L1", "2324", "T1", "Player A")],
            names=["league", "season", "team", "player"],
        )
        raw = pd.DataFrame([[None, 5, 5, 450, 2, 1]], columns=cols, index=index)

        flat = audit_mod._flatten_raw(raw)
        assert pd.isna(flat.iloc[0]["born_raw"])
        assert flat.iloc[0][("Playing Time", "MP")] == 5


# ---------------------------------------------------------------------------
# _find_raw_row
# ---------------------------------------------------------------------------


class TestFindRawRow:
    def _make_flat_raw(self, audit_mod):
        return pd.DataFrame(
            [
                {
                    "player": "Aaron Ramsdale",
                    "season": "2324",
                    "team": "Arsenal",
                    "born_raw": 1998,
                    ("Performance", "Gls"): 0,
                    ("Performance", "Ast"): 0,
                    ("Playing Time", "Min"): 900,
                    ("Playing Time", "MP"): 10,
                    ("Playing Time", "Starts"): 10,
                },
                {
                    "player": "Aaron Ramsdale",
                    "season": "2324",
                    "team": "Southampton",
                    "born_raw": 1998,
                    ("Performance", "Gls"): 0,
                    ("Performance", "Ast"): 0,
                    ("Playing Time", "Min"): 450,
                    ("Playing Time", "MP"): 5,
                    ("Playing Time", "Starts"): 5,
                },
                {
                    "player": "Robert Lewandowski",
                    "season": "2324",
                    "team": "Barcelona",
                    "born_raw": 1988,
                    ("Performance", "Gls"): 15,
                    ("Performance", "Ast"): 5,
                    ("Playing Time", "Min"): 1800,
                    ("Playing Time", "MP"): 20,
                    ("Playing Time", "Starts"): 20,
                },
            ]
        )

    def test_unique_match(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = audit_mod._find_raw_row(flat, "Robert Lewandowski", "2324", "Barcelona")
        assert row is not None
        assert row[("Performance", "Gls")] == 15

    def test_no_match(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        assert audit_mod._find_raw_row(flat, "Nobody", "2324", "X") is None

    def test_multi_team_disambiguated_by_team(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = audit_mod._find_raw_row(
            flat, "Aaron Ramsdale", "2324", "Southampton"
        )
        assert row is not None
        assert row[("Playing Time", "MP")] == 5

    def test_multi_team_fallback_first_when_team_unknown(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = audit_mod._find_raw_row(
            flat, "Aaron Ramsdale", "2324", "Unknown Team"
        )
        assert row is not None
        # Should return the first match.
        assert row[("Playing Time", "MP")] == 10

    def test_multi_team_fallback_first_when_team_empty(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = audit_mod._find_raw_row(flat, "Aaron Ramsdale", "2324", "")
        assert row is not None
        assert row[("Playing Time", "MP")] == 10


# ---------------------------------------------------------------------------
# audit_sample
# ---------------------------------------------------------------------------


class TestAuditSample:
    def _make_flat_raw(self, audit_mod):
        return pd.DataFrame(
            [
                {
                    "player": "Test Player",
                    "season": "2324",
                    "team": "Test Team",
                    "born_raw": 1995,
                    ("Performance", "Gls"): 10,
                    ("Performance", "Ast"): 5,
                    ("Playing Time", "Min"): 1500,
                    ("Playing Time", "MP"): 18,
                    ("Playing Time", "Starts"): 15,
                },
            ]
        )

    def test_confirmed_correct_all_fields_match(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = pd.Series(
            {
                "player_name": "Test Player",
                "season_id": "2324",
                "team_name": "Test Team",
                "goals": 10,
                "assists": 5,
                "minutes_played": 1500,
                "matches_played": 18,
                "starts": 15,
                "born": 1995,
                "player_id": "test player|1995|testland",
                "multi_team_season": False,
            }
        )
        result = audit_mod.audit_sample(row, flat)
        assert result["outcome"] == "confirmed_correct"
        assert "goals" in result["fields_verified"]
        assert result["born_verified"] is True

    def test_goals_mismatch_is_error(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = pd.Series(
            {
                "player_name": "Test Player",
                "season_id": "2324",
                "team_name": "Test Team",
                "goals": 99,
                "assists": 5,
                "minutes_played": 1500,
                "matches_played": 18,
                "starts": 15,
                "born": 1995,
                "player_id": "test player|1995|testland",
                "multi_team_season": False,
            }
        )
        result = audit_mod.audit_sample(row, flat)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "goals_mismatch"

    def test_minutes_float_tolerance(self, audit_mod):
        """Minutes values may differ by ULP after to_numeric coercion."""
        flat = self._make_flat_raw(audit_mod)
        row = pd.Series(
            {
                "player_name": "Test Player",
                "season_id": "2324",
                "team_name": "Test Team",
                "goals": 10,
                "assists": 5,
                "minutes_played": 1500.0000000000002,  # ULP-level diff
                "matches_played": 18,
                "starts": 15,
                "born": 1995,
                "player_id": "test player|1995|testland",
                "multi_team_season": False,
            }
        )
        result = audit_mod.audit_sample(row, flat)
        assert result["outcome"] == "confirmed_correct"

    def test_born_mismatch_is_error(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = pd.Series(
            {
                "player_name": "Test Player",
                "season_id": "2324",
                "team_name": "Test Team",
                "goals": 10,
                "assists": 5,
                "minutes_played": 1500,
                "matches_played": 18,
                "starts": 15,
                "born": 1990,  # Different from raw 1995
                "player_id": "test player|1990|testland",
                "multi_team_season": False,
            }
        )
        result = audit_mod.audit_sample(row, flat)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "born_mismatch"

    def test_empty_player_name_is_no_match(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = pd.Series({"player_name": "", "season_id": "2324", "team_name": "T"})
        result = audit_mod.audit_sample(row, flat)
        assert result["outcome"] == "no_match"
        assert result["reason"] == "player_name_empty"

    def test_empty_season_id_is_no_match(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = pd.Series(
            {"player_name": "Test Player", "season_id": "", "team_name": "T"}
        )
        result = audit_mod.audit_sample(row, flat)
        assert result["outcome"] == "no_match"
        assert result["reason"] == "season_id_empty"

    def test_raw_row_not_found_is_no_match(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = pd.Series(
            {
                "player_name": "Nonexistent Player",
                "season_id": "2324",
                "team_name": "T",
                "goals": 0,
                "assists": 0,
                "minutes_played": 0,
                "matches_played": 0,
                "starts": 0,
                "born": 1995,
                "player_id": "x",
                "multi_team_season": False,
            }
        )
        result = audit_mod.audit_sample(row, flat)
        assert result["outcome"] == "no_match"
        assert result["reason"] == "raw_row_not_found"

    def test_missing_gold_numeric_skipped_not_error(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = pd.Series(
            {
                "player_name": "Test Player",
                "season_id": "2324",
                "team_name": "Test Team",
                "goals": None,  # Missing in gold
                "assists": 5,
                "minutes_played": 1500,
                "matches_played": 18,
                "starts": 15,
                "born": 1995,
                "player_id": "test player|1995|testland",
                "multi_team_season": False,
            }
        )
        result = audit_mod.audit_sample(row, flat)
        # goals is skipped (gold None), other fields match → confirmed_correct
        assert result["outcome"] == "confirmed_correct"

    def test_missing_raw_numeric_skipped_not_error(self, audit_mod):
        flat = self._make_flat_raw(audit_mod).copy()
        # Set raw goals to NaN
        flat.loc[0, ("Performance", "Gls")] = float("nan")
        row = pd.Series(
            {
                "player_name": "Test Player",
                "season_id": "2324",
                "team_name": "Test Team",
                "goals": 10,
                "assists": 5,
                "minutes_played": 1500,
                "matches_played": 18,
                "starts": 15,
                "born": 1995,
                "player_id": "test player|1995|testland",
                "multi_team_season": False,
            }
        )
        result = audit_mod.audit_sample(row, flat)
        # goals is skipped (raw NaN), other fields match → confirmed_correct
        assert result["outcome"] == "confirmed_correct"

    def test_multi_team_season_flag_preserved(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = pd.Series(
            {
                "player_name": "Test Player",
                "season_id": "2324",
                "team_name": "Test Team",
                "goals": 10,
                "assists": 5,
                "minutes_played": 1500,
                "matches_played": 18,
                "starts": 15,
                "born": 1995,
                "player_id": "test player|1995|testland",
                "multi_team_season": True,
            }
        )
        result = audit_mod.audit_sample(row, flat)
        assert result["outcome"] == "confirmed_correct"
        assert result["multi_team_season"] is True

    def test_na_multi_team_season_treated_as_false(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = pd.Series(
            {
                "player_name": "Test Player",
                "season_id": "2324",
                "team_name": "Test Team",
                "goals": 10,
                "assists": 5,
                "minutes_played": 1500,
                "matches_played": 18,
                "starts": 15,
                "born": 1995,
                "player_id": "test player|1995|testland",
                "multi_team_season": pd.NA,
            }
        )
        result = audit_mod.audit_sample(row, flat)
        assert result["outcome"] == "confirmed_correct"
        assert result["multi_team_season"] is False

    def test_assists_mismatch_is_error(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = pd.Series(
            {
                "player_name": "Test Player",
                "season_id": "2324",
                "team_name": "Test Team",
                "goals": 10,
                "assists": 99,
                "minutes_played": 1500,
                "matches_played": 18,
                "starts": 15,
                "born": 1995,
                "player_id": "test player|1995|testland",
                "multi_team_season": False,
            }
        )
        result = audit_mod.audit_sample(row, flat)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "assists_mismatch"

    def test_starts_mismatch_is_error(self, audit_mod):
        flat = self._make_flat_raw(audit_mod)
        row = pd.Series(
            {
                "player_name": "Test Player",
                "season_id": "2324",
                "team_name": "Test Team",
                "goals": 10,
                "assists": 5,
                "minutes_played": 1500,
                "matches_played": 18,
                "starts": 99,
                "born": 1995,
                "player_id": "test player|1995|testland",
                "multi_team_season": False,
            }
        )
        result = audit_mod.audit_sample(row, flat)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "starts_mismatch"

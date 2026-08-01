"""Unit tests for the understat source_claim audit helper functions."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "dry_run_source_claim_audit_understat.py"
)


def _load_audit_module():
    """Load the scripts module by file path (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "dry_run_source_claim_audit_understat", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["dry_run_source_claim_audit_understat"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit():
    return _load_audit_module()


# --- _season_id_to_raw ---


class TestSeasonIdToRaw:
    def test_standard_four_digit(self, audit):
        assert audit._season_id_to_raw("1617") == "201617"

    def test_recent_season(self, audit):
        assert audit._season_id_to_raw("2526") == "202526"

    def test_three_digit_returns_empty(self, audit):
        assert audit._season_id_to_raw("617") == ""

    def test_non_digit_returns_empty(self, audit):
        assert audit._season_id_to_raw("abcd") == ""

    def test_empty_returns_empty(self, audit):
        assert audit._season_id_to_raw("") == ""

    def test_none_returns_empty(self, audit):
        assert audit._season_id_to_raw(None) == ""

    def test_strips_whitespace(self, audit):
        assert audit._season_id_to_raw("  1617  ") == "201617"


# --- _extract_understat_id ---


class TestExtractUnderstatId:
    def test_standard(self, audit):
        assert audit._extract_understat_id("understat|1") == "1"

    def test_large_id(self, audit):
        assert audit._extract_understat_id("understat|13748") == "13748"

    def test_non_understat_prefix(self, audit):
        assert audit._extract_understat_id("fbref|1") == ""

    def test_no_pipe(self, audit):
        assert audit._extract_understat_id("understat") == ""

    def test_empty(self, audit):
        assert audit._extract_understat_id("") == ""

    def test_none(self, audit):
        assert audit._extract_understat_id(None) == ""

    def test_strips_whitespace(self, audit):
        assert audit._extract_understat_id("  understat|42  ") == "42"


# --- _to_float ---


class TestToFloat:
    def test_integer(self, audit):
        assert audit._to_float(5) == 5.0

    def test_float(self, audit):
        assert audit._to_float(3.14) == 3.14

    def test_string_numeric(self, audit):
        assert audit._to_float("2.5") == 2.5

    def test_none(self, audit):
        assert audit._to_float(None) is None

    def test_nan(self, audit):
        assert audit._to_float(float("nan")) is None

    def test_non_numeric_string(self, audit):
        assert audit._to_float("abc") is None

    def test_pandas_nan(self, audit):
        assert audit._to_float(pd.NA) is None


# --- _team_consistent ---


class TestTeamConsistent:
    def test_exact_match(self, audit):
        assert audit._team_consistent("Arsenal", "Arsenal") is True

    def test_multi_team_raw_starts_with_gold(self, audit):
        assert audit._team_consistent("Hull", "Hull,West Ham") is True

    def test_mismatch(self, audit):
        assert audit._team_consistent("Arsenal", "Chelsea") is False

    def test_gold_is_suffix_not_consistent(self, audit):
        assert audit._team_consistent("West Ham", "Hull,West Ham") is False

    def test_empty_gold(self, audit):
        assert audit._team_consistent("", "Arsenal") is False

    def test_empty_raw(self, audit):
        assert audit._team_consistent("Arsenal", "") is False


# --- audit_sample ---


def _make_gold_row(**kwargs):
    """Build a gold player_match row as a pandas Series."""
    defaults = {
        "player_id": "understat|1",
        "season_id": "1617",
        "player_name": "Test Player",
        "team_name": "Arsenal",
        "goals": 10,
        "assists": 5,
        "shots": 50,
        "npxg": 8.3,
        "xa": 4.2,
        "minutes_played": 1800,
        "matches_played": 20,
        "multi_team_season": False,
    }
    defaults.update(kwargs)
    return pd.Series(defaults)


def _make_raw_df(**kwargs):
    """Build a raw understat DataFrame with one row."""
    defaults = {
        "id": ["1"],
        "season": ["201617"],
        "player_name": ["Test Player"],
        "team_title": ["Arsenal"],
        "goals": [10],
        "assists": [5],
        "shots": [50],
        "npxG": [8.3],
        "xA": [4.2],
        "time": [1800],
        "games": [20],
    }
    defaults.update(kwargs)
    return pd.DataFrame(defaults)


class TestAuditSample:
    def test_confirmed_correct_all_fields_match(self, audit):
        row = _make_gold_row()
        raw = _make_raw_df()
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "confirmed_correct"
        assert result["player_id"] == "understat|1"
        assert result["understat_id"] == "1"
        assert result["raw_season"] == "201617"
        expected_fields = [
            "goals", "assists", "shots", "npxg",
            "xa", "minutes_played", "matches_played",
        ]
        assert result["fields_verified"] == expected_fields
        assert result["player_name_verified"] is True
        assert result["team_name_verified"] is True
        assert result["multi_team_season"] is False

    def test_no_match_player_id_not_understat(self, audit):
        row = _make_gold_row(player_id="fbref|1")
        raw = _make_raw_df()
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "no_match"
        assert result["reason"] == "player_id_not_understat_prefixed"

    def test_no_match_season_unparseable(self, audit):
        row = _make_gold_row(season_id="abc")
        raw = _make_raw_df()
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "no_match"
        assert result["reason"] == "season_id_unparseable"

    def test_no_match_raw_row_not_found(self, audit):
        row = _make_gold_row(player_id="understat|999")
        raw = _make_raw_df()
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "no_match"
        assert result["reason"] == "raw_row_not_found"

    def test_confirmed_error_goals_mismatch(self, audit):
        row = _make_gold_row(goals=10)
        raw = _make_raw_df(goals=[11])
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "goals_mismatch"
        assert result["gold_value"] == 10.0
        assert result["raw_value"] == 11.0

    def test_confirmed_error_assists_mismatch(self, audit):
        row = _make_gold_row(assists=5)
        raw = _make_raw_df(assists=[6])
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "assists_mismatch"

    def test_float_precision_tolerance(self, audit):
        """ULP-level float differences from JSON round-trip should not be errors."""
        row = _make_gold_row(npxg=0.1069720014929771)
        raw = _make_raw_df(npxG=[0.10697200149297714])
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "confirmed_correct"

    def test_real_npxg_mismatch_is_error(self, audit):
        row = _make_gold_row(npxg=8.3)
        raw = _make_raw_df(npxG=[9.5])
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "npxg_mismatch"

    def test_confirmed_error_player_name_mismatch(self, audit):
        row = _make_gold_row(player_name="Player A")
        raw = _make_raw_df(player_name=["Player B"])
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "player_name_mismatch"

    def test_confirmed_error_team_name_mismatch(self, audit):
        row = _make_gold_row(team_name="Arsenal")
        raw = _make_raw_df(team_title=["Chelsea"])
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "team_name_mismatch"

    def test_multi_team_season_consistent(self, audit):
        """Gold keeps first club; raw has comma-joined teams."""
        row = _make_gold_row(team_name="Hull", multi_team_season=True)
        raw = _make_raw_df(team_title=["Hull,West Ham"])
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "confirmed_correct"
        assert result["multi_team_season"] is True

    def test_multi_team_season_wrong_first_club_is_error(self, audit):
        """If gold's first club doesn't match raw's first club, it's an error."""
        row = _make_gold_row(team_name="West Ham", multi_team_season=True)
        raw = _make_raw_df(team_title=["Hull,West Ham"])
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "team_name_mismatch"

    def test_missing_gold_numeric_skipped(self, audit):
        """Missing numeric values on gold side are a coverage gap, not an error."""
        row = _make_gold_row(npxg=float("nan"))
        raw = _make_raw_df()
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "confirmed_correct"

    def test_missing_raw_numeric_skipped(self, audit):
        """Missing numeric values on raw side are a coverage gap, not an error."""
        row = _make_gold_row()
        raw = _make_raw_df(npxG=[None])
        result = audit.audit_sample(row, raw)
        assert result["outcome"] == "confirmed_correct"

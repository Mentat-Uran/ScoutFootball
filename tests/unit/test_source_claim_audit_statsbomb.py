"""Tests for the statsbomb_open source_claim audit helper functions."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "dry_run_source_claim_audit_statsbomb.py"
)


def _load_audit_module():
    """Load the audit script as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "dry_run_source_claim_audit_statsbomb", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["dry_run_source_claim_audit_statsbomb"] = module
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


# ---------------------------------------------------------------------------
# _normalise_player_id
# ---------------------------------------------------------------------------


class TestNormalisePlayerId:
    def test_float_value(self, audit_mod):
        assert audit_mod._normalise_player_id(10605.0) == "10605.0"

    def test_float_string(self, audit_mod):
        assert audit_mod._normalise_player_id("10605.0") == "10605.0"

    def test_int_string_normalised_to_float_form(self, audit_mod):
        assert audit_mod._normalise_player_id("10605") == "10605.0"

    def test_int_value(self, audit_mod):
        assert audit_mod._normalise_player_id(10605) == "10605.0"

    def test_none_returns_empty(self, audit_mod):
        assert audit_mod._normalise_player_id(None) == ""

    def test_non_numeric_string_passthrough(self, audit_mod):
        assert audit_mod._normalise_player_id("abc") == "abc"


# ---------------------------------------------------------------------------
# aggregate_raw_group
# ---------------------------------------------------------------------------


def _make_events_frame(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal raw events DataFrame with the columns the audit reads."""
    defaults = {
        "match_id": 3773386,
        "player_id": 10605.0,
        "player_name": "Test Player",
        "team_name": "Test Team",
        "minute": 0,
        "event_type": "Pass",
        "shot_outcome_name": None,
        "shot_statsbomb_xg": None,
        "pass_goal_assist": False,
    }
    records = []
    for row in rows:
        merged = {**defaults, **row}
        records.append(merged)
    return pd.DataFrame(records)


class TestAggregateRawGroup:
    def test_empty_group_returns_zeros(self, audit_mod):
        empty = pd.DataFrame(
            columns=[
                "minute", "event_type", "shot_outcome_name", "shot_statsbomb_xg",
                "pass_goal_assist", "player_name", "team_name",
            ]
        )
        result = audit_mod.aggregate_raw_group(empty)
        assert result["minutes_played"] == 0
        assert result["goals"] == 0
        assert result["assists"] == 0
        assert result["shots"] == 0
        assert result["shots_on_target"] == 0
        assert result["passes"] == 0
        assert result["tackles"] == 0
        assert result["npxg_raw"] == 0.0
        assert result["player_name_raw"] == ""
        assert result["team_name_raw"] == ""

    def test_mixed_event_types_aggregate_correctly(self, audit_mod):
        shot_goal = {
            "minute": 15, "event_type": "Shot",
            "shot_outcome_name": "Goal", "shot_statsbomb_xg": 0.4,
        }
        shot_saved = {
            "minute": 20, "event_type": "Shot",
            "shot_outcome_name": "Saved", "shot_statsbomb_xg": 0.1,
        }
        shot_off = {
            "minute": 25, "event_type": "Shot",
            "shot_outcome_name": "Off T", "shot_statsbomb_xg": 0.05,
        }
        events = _make_events_frame([
            {"minute": 5, "event_type": "Pass"},
            {"minute": 10, "event_type": "Pass", "pass_goal_assist": True},
            shot_goal, shot_saved, shot_off,
            {"minute": 30, "event_type": "Duel"},
            {"minute": 35, "event_type": "Duel"},
            {"minute": 90, "event_type": "Carry"},
        ])
        result = audit_mod.aggregate_raw_group(events)
        assert result["minutes_played"] == 91  # max minute 90 + 1
        assert result["goals"] == 1
        assert result["assists"] == 1
        assert result["shots"] == 3
        assert result["shots_on_target"] == 2  # Goal + Saved
        assert result["passes"] == 2
        assert result["tackles"] == 2  # All Duels (matches pipeline behaviour)
        assert result["npxg_raw"] == pytest.approx(0.55)
        assert result["player_name_raw"] == "Test Player"
        assert result["team_name_raw"] == "Test Team"

    def test_no_shots_yields_zero_npxg(self, audit_mod):
        events = _make_events_frame([
            {"minute": 10, "event_type": "Pass"},
            {"minute": 20, "event_type": "Duel"},
        ])
        result = audit_mod.aggregate_raw_group(events)
        assert result["goals"] == 0
        assert result["shots"] == 0
        assert result["shots_on_target"] == 0
        assert result["npxg_raw"] == 0.0

    def test_shots_on_target_excludes_off_target_and_post(self, audit_mod):
        events = _make_events_frame([
            {
                "minute": 10, "event_type": "Shot",
                "shot_outcome_name": "Goal", "shot_statsbomb_xg": 0.3,
            },
            {
                "minute": 20, "event_type": "Shot",
                "shot_outcome_name": "Saved", "shot_statsbomb_xg": 0.1,
            },
            {
                "minute": 30, "event_type": "Shot",
                "shot_outcome_name": "Saved To Post", "shot_statsbomb_xg": 0.05,
            },
            {
                "minute": 40, "event_type": "Shot",
                "shot_outcome_name": "Off T", "shot_statsbomb_xg": 0.05,
            },
            {
                "minute": 50, "event_type": "Shot",
                "shot_outcome_name": "Post", "shot_statsbomb_xg": 0.05,
            },
            {
                "minute": 60, "event_type": "Shot",
                "shot_outcome_name": "Blocked", "shot_statsbomb_xg": 0.05,
            },
        ])
        result = audit_mod.aggregate_raw_group(events)
        assert result["shots"] == 6
        assert result["shots_on_target"] == 3  # Goal + Saved + Saved To Post


# ---------------------------------------------------------------------------
# build_raw_aggregates
# ---------------------------------------------------------------------------


class TestBuildRawAggregates:
    def test_groups_by_match_and_player(self, audit_mod):
        events = _make_events_frame([
            {"match_id": 1, "player_id": 100.0, "minute": 10, "event_type": "Pass"},
            {"match_id": 1, "player_id": 100.0, "minute": 20, "event_type": "Pass"},
            {"match_id": 1, "player_id": 200.0, "minute": 30, "event_type": "Duel"},
            {
                "match_id": 2, "player_id": 100.0, "minute": 40,
                "event_type": "Shot", "shot_outcome_name": "Goal",
                "shot_statsbomb_xg": 0.5,
            },
        ])
        aggregates = audit_mod.build_raw_aggregates(events)
        assert len(aggregates) == 3
        # Keys are (str(match_id), str(player_id)).  Raw stores match_id as
        # int and player_id as float, so str() gives '1' and '100.0'.
        assert ("1", "100.0") in aggregates
        assert ("1", "200.0") in aggregates
        assert ("2", "100.0") in aggregates
        assert aggregates[("1", "100.0")]["passes"] == 2
        assert aggregates[("1", "200.0")]["tackles"] == 1
        assert aggregates[("2", "100.0")]["goals"] == 1

    def test_drops_rows_with_missing_player_id(self, audit_mod):
        events = _make_events_frame([
            {"match_id": 1, "player_id": 100.0, "minute": 10, "event_type": "Pass"},
            {"match_id": 1, "player_id": None, "minute": 20, "event_type": "Pass"},
        ])
        # Force the None row to actually be NaN (the helper default kicks in otherwise).
        events.loc[1, "player_id"] = np.nan
        aggregates = audit_mod.build_raw_aggregates(events)
        assert len(aggregates) == 1
        assert ("1", "100.0") in aggregates


# ---------------------------------------------------------------------------
# audit_sample
# ---------------------------------------------------------------------------


class TestAuditSample:
    def _make_aggregates(self, audit_mod, *, npxg_raw=0.0):
        return {
            ("3773386", "10605.0"): {
                "minutes_played": 91,
                "goals": 1,
                "assists": 1,
                "shots": 3,
                "shots_on_target": 2,
                "passes": 50,
                "tackles": 4,
                "npxg_raw": npxg_raw,
                "player_name_raw": "Test Player",
                "team_name_raw": "Test Team",
            }
        }

    def _make_gold_row(self, **overrides):
        defaults = {
            "match_id": "3773386",
            "player_id": "10605.0",
            "player_name": "Test Player",
            "team_name": "Test Team",
            "minutes_played": 91,
            "goals": 1,
            "assists": 1,
            "shots": 3,
            "shots_on_target": 2,
            "passes": 50,
            "tackles": 4,
            "npxg": pd.NA,  # gold stores NA when raw xG sums to 0
        }
        defaults.update(overrides)
        return pd.Series(defaults)

    def test_confirmed_correct_all_fields_match(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row()
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_correct"
        assert "minutes_played" in result["fields_verified"]
        assert "tackles" in result["fields_verified"]
        assert result["npxg_verified"] is True
        assert result["player_name_verified"] is True
        assert result["team_name_verified"] is True

    def test_confirmed_correct_with_nonzero_npxg(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod, npxg_raw=0.55)
        row = self._make_gold_row(npxg=0.55)
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_correct"
        assert result["npxg_verified"] is True

    def test_npxg_float_precision_within_tolerance(self, audit_mod):
        """xG values may differ by ULP after JSON round-trip and to_numeric coercion."""
        aggregates = self._make_aggregates(audit_mod, npxg_raw=0.55)
        row = self._make_gold_row(npxg=0.5500000000000001)  # ULP-level diff
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_correct"

    def test_npxg_mismatch_outside_tolerance_is_error(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod, npxg_raw=0.55)
        row = self._make_gold_row(npxg=0.6)
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "npxg_mismatch"
        assert result["gold_value"] == pytest.approx(0.6)
        assert result["raw_value"] == pytest.approx(0.55)

    def test_npxg_missing_in_gold_but_present_in_raw_is_error(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod, npxg_raw=0.55)
        row = self._make_gold_row(npxg=pd.NA)
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "npxg_missing_in_gold"

    def test_npxg_na_in_gold_and_zero_in_raw_is_correct(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod, npxg_raw=0.0)
        row = self._make_gold_row(npxg=pd.NA)
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_correct"

    def test_goals_mismatch_is_error(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(goals=99)
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "goals_mismatch"

    def test_assists_mismatch_is_error(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(assists=99)
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "assists_mismatch"

    def test_shots_mismatch_is_error(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(shots=99)
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "shots_mismatch"

    def test_shots_on_target_mismatch_is_error(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(shots_on_target=99)
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "shots_on_target_mismatch"

    def test_passes_mismatch_is_error(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(passes=99)
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "passes_mismatch"

    def test_tackles_mismatch_is_error(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(tackles=99)
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "tackles_mismatch"

    def test_minutes_played_mismatch_is_error(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(minutes_played=99)
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "minutes_played_mismatch"

    def test_player_name_mismatch_is_error(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(player_name="Wrong Name")
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "player_name_mismatch"
        assert result["gold_name"] == "Wrong Name"
        assert result["raw_name"] == "Test Player"

    def test_team_name_mismatch_is_error(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(team_name="Wrong Team")
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "team_name_mismatch"

    def test_missing_identifier_is_no_match(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = pd.Series({"player_name": "Test Player", "team_name": "Test Team"})
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "no_match"
        assert result["reason"] == "missing_identifier"

    def test_unparseable_player_id_is_no_match(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(player_id="abc")
        result = audit_mod.audit_sample(row, aggregates)
        # 'abc' normalises to 'abc'; key ('3773386', 'abc') is not in aggregates.
        assert result["outcome"] == "no_match"
        assert result["reason"] == "raw_events_not_found"

    def test_raw_events_not_found_is_no_match(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(player_id="99999.0")
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "no_match"
        assert result["reason"] == "raw_events_not_found"

    def test_player_id_int_string_matches_float_string_in_aggregates(self, audit_mod):
        """Gold may store '10605' (int string); aggregates key is '10605.0'."""
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(player_id="10605")  # int string
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_correct"

    def test_player_id_float_value_matches_string_key(self, audit_mod):
        """When gold row is built from raw events (not parquet), player_id may be float."""
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(player_id=10605.0)
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_correct"

    def test_empty_player_name_not_flagged_as_mismatch(self, audit_mod):
        """Gold player_name empty is skipped, not an error (other fields still checked)."""
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(player_name="")
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_correct"
        assert result["player_name_verified"] is False

    def test_empty_team_name_not_flagged_as_mismatch(self, audit_mod):
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(team_name="")
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_correct"
        assert result["team_name_verified"] is False

    def test_na_integer_field_with_zero_raw_skipped(self, audit_mod):
        """Gold integer field NA + raw value 0 is treated as consistent."""
        aggregates = self._make_aggregates(audit_mod, npxg_raw=0.0)
        aggregates[("3773386", "10605.0")]["goals"] = 0
        row = self._make_gold_row(goals=pd.NA)
        result = audit_mod.audit_sample(row, aggregates)
        assert result["outcome"] == "confirmed_correct"

    def test_na_integer_field_with_nonzero_raw_is_error(self, audit_mod):
        """Gold integer field NA + raw value >0 falls back to int(NA) which raises."""
        aggregates = self._make_aggregates(audit_mod)
        row = self._make_gold_row(goals=pd.NA)
        result = audit_mod.audit_sample(row, aggregates)
        # raw goals=1, gold NA → int(NA) raises → unparseable path triggered.
        assert result["outcome"] == "confirmed_error"
        assert result["reason"] == "goals_unparseable"


# ---------------------------------------------------------------------------
# write_audit_ledger + write_threshold_ledger (smoke)
# ---------------------------------------------------------------------------


class TestLedgerWrite:
    def test_write_audit_ledger_dedupes_existing_ids(self, audit_mod, tmp_path, monkeypatch):
        """Pre-existing audit_ids are skipped; new ones are appended."""
        # Stub the ledger API to avoid importing the full package during unit
        # tests.  We patch the functions inside the audit module's namespace.
        appended: list[dict] = []

        def fake_build(*, audit_kind, source_id, sample_id, outcome, reviewer,
                       evidence_reference, decision, supersedes_audit_id=None,
                       recorded_at=None):
            return {
                "audit_id": f"{source_id}:{sample_id}:{outcome}",
                "audit_kind": audit_kind,
                "source_id": source_id,
                "sample_id": sample_id,
                "outcome": outcome,
                "reviewer": reviewer,
                "evidence_reference": evidence_reference,
                "decision": decision,
                "supersedes_audit_id": supersedes_audit_id,
            }

        def fake_read(path):
            # Pretend the first record already exists.
            return [{"audit_id": "statsbomb_open:player_match:10605.0:3773386:confirmed_correct"}]

        def fake_append(record, path):
            appended.append(record)
            return path

        # Inject a fake module with the expected functions.
        fake_module = type("M", (), {})()
        fake_module.build_quality_audit_record = fake_build
        fake_module.read_quality_audit_ledger = fake_read
        fake_module.append_quality_audit_record = fake_append

        import sys as _sys
        _sys.modules["scoutfootball.evaluation.quality_audit_ledger"] = fake_module

        records = [
            {
                "outcome": "confirmed_correct",
                "player_id": "10605.0",
                "match_id": "3773386",
                "player_name": "Test Player",
                "team_name": "Test Team",
                "fields_verified": ["goals"],
            },
            {
                "outcome": "confirmed_error",
                "reason": "tackles_mismatch",
                "player_id": "11388.0",
                "match_id": "3773457",
                "gold_value": 5,
                "raw_value": 3,
            },
        ]
        ledger_path = tmp_path / "audit.jsonl"
        # write_audit_ledger only reads the existing ledger when the path
        # exists, so pre-create an empty file to trigger the dedupe path.
        ledger_path.write_text("", encoding="utf-8")
        written = audit_mod.write_audit_ledger(records, ledger_path)
        # First record deduped (matches pre-existing id), second is new.
        assert written == 1
        assert len(appended) == 1
        assert appended[0]["outcome"] == "confirmed_error"

    def test_write_threshold_ledger_dedupes_existing_ids(self, audit_mod, tmp_path):
        appended: list[dict] = []

        def fake_build(*, audit_kind, maximum_error_rate, minimum_sample_count, decision):
            return {
                "threshold_id": f"{audit_kind}:{maximum_error_rate}:{minimum_sample_count}",
                "audit_kind": audit_kind,
                "maximum_error_rate": maximum_error_rate,
                "minimum_sample_count": minimum_sample_count,
                "decision": decision,
            }

        def fake_read(path):
            return [{"threshold_id": "source_claim:0.05:50"}]

        def fake_append(record, path):
            appended.append(record)
            return path

        fake_module = type("M", (), {})()
        fake_module.build_quality_threshold_record = fake_build
        fake_module.read_quality_threshold_ledger = fake_read
        fake_module.append_quality_threshold_record = fake_append

        import sys as _sys
        _sys.modules["scoutfootball.evaluation.quality_audit_ledger"] = fake_module

        threshold_path = tmp_path / "threshold.jsonl"
        # write_threshold_ledger only reads existing thresholds when the path
        # exists, so pre-create an empty file to trigger the dedupe path.
        threshold_path.write_text("", encoding="utf-8")
        result = audit_mod.write_threshold_ledger(threshold_path, 50)
        assert result == 0  # Deduped.
        assert appended == []

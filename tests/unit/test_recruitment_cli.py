"""Unit tests for recruitment CLI commands.

Covers:
- ``create-brief`` from CLI flags (generates brief_id, saves record)
- ``create-brief --json`` emits JSON record
- ``list-briefs`` on empty and non-empty stores
- ``list-briefs --json`` emits JSON list
- ``show-brief`` loads and displays one brief
- ``show-brief --json`` emits JSON record
- ``validate-brief`` on a valid file and an invalid file
- Error paths: show-brief on nonexistent id exits non-zero
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

import pytest

from scoutfootball.__main__ import main
from scoutfootball.recruitment.brief import BRIEF_SCHEMA, BRIEF_VERSION


def _valid_brief_json(brief_id: str = "brief-cli-001") -> dict:
    now = datetime.now(tz=UTC).isoformat()
    return {
        "schema": BRIEF_SCHEMA,
        "version": BRIEF_VERSION,
        "brief_id": brief_id,
        "revision": 1,
        "created_at": now,
        "updated_at": now,
        "author": "maintainer",
        "title": "CLI test brief",
        "team": "Test FC",
        "position_group": "MF",
        "position_detail": "CM",
        "role": "deep_playmaker",
        "budget_eur": 20_000_000,
        "age_min": 22,
        "age_max": 28,
        "contract_years_min": 4,
        "league_preferences": ["Premier League"],
        "language_preferences": ["English"],
        "risk_tolerance": "low",
        "minimum_minutes": 2000,
        "notes": "CLI test.",
        "limitations": ["Brief is a personal local object; not an external fact."],
    }


@pytest.fixture
def isolated_data_root(tmp_path, monkeypatch):
    """Point SCOUTFOOTBALL_DATA_ROOT at a temp dir so CLI writes are isolated."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("SCOUTFOOTBALL_DATA_ROOT", str(data_root))
    return data_root


def _run_cli(argv: list[str], capsys):
    """Run the CLI with the given argv and return (exit_code, out, err)."""
    old_argv = sys.argv
    sys.argv = ["scoutfootball"] + argv
    try:
        main()
        captured = capsys.readouterr()
        return 0, captured.out, captured.err
    except SystemExit as exc:
        captured = capsys.readouterr()
        return exc.code, captured.out, captured.err
    finally:
        sys.argv = old_argv


# ── create-brief ──────────────────────────────────────────────────────


class TestCreateBrief:
    def test_create_brief_from_flags(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-brief",
                "--title", "Flag-based brief",
                "--team", "Arsenal",
                "--position-group", "DF",
                "--position-detail", "LB",
                "--role", "attacking_fullback",
                "--budget-eur", "30000000",
                "--age-min", "21",
                "--age-max", "27",
                "--league-preferences", "Premier League", "La Liga",
            ],
            capsys,
        )
        assert code == 0
        assert "Created brief:" in out
        assert "Flag-based brief" in out
        assert "Arsenal" in out

    def test_create_brief_json_output(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-brief",
                "--title", "JSON brief",
                "--position-group", "FW",
                "--position-detail", "ST",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        assert record["schema"] == "scoutfootball.recruitment-brief-record"
        assert record["brief"]["title"] == "JSON brief"
        assert record["brief"]["position_group"] == "FW"

    def test_create_brief_from_json_file(self, isolated_data_root, tmp_path, capsys):
        brief_file = tmp_path / "brief.json"
        brief_file.write_text(
            json.dumps(_valid_brief_json("brief-from-file")), encoding="utf-8"
        )
        code, out, _ = _run_cli(
            ["create-brief", "--from-json", str(brief_file)],
            capsys,
        )
        assert code == 0
        assert "brief-from-file" in out

    def test_create_brief_invalid_position_group_exits(self, isolated_data_root, capsys):
        code, _, err = _run_cli(
            [
                "create-brief",
                "--title", "Bad brief",
                "--position-group", "XX",
            ],
            capsys,
        )
        assert code != 0
        assert "error" in err.lower() or "invalid choice" in err.lower()

    def test_create_brief_missing_title_exits(self, isolated_data_root, capsys):
        code, _, err = _run_cli(
            ["create-brief", "--position-group", "DF"],
            capsys,
        )
        assert code != 0
        assert "--title is required" in err


# ── list-briefs ───────────────────────────────────────────────────────


class TestListBriefs:
    def test_list_empty_store(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(["list-briefs"], capsys)
        assert code == 0
        assert "No briefs" in out or "0 brief" in out

    def test_list_empty_store_json(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(["list-briefs", "--json"], capsys)
        assert code == 0
        result = json.loads(out)
        assert result["count"] == 0
        assert result["briefs"] == []

    def test_list_after_create(self, isolated_data_root, capsys):
        _run_cli(
            ["create-brief", "--title", "First", "--position-group", "DF", "--json"],
            capsys,
        )
        code, out, _ = _run_cli(["list-briefs", "--json"], capsys)
        assert code == 0
        result = json.loads(out)
        assert result["count"] == 1
        assert result["briefs"][0]["title"] == "First"

    def test_list_text_output(self, isolated_data_root, capsys):
        _run_cli(
            ["create-brief", "--title", "Text brief", "--position-group", "MF", "--json"],
            capsys,
        )
        code, out, _ = _run_cli(["list-briefs"], capsys)
        assert code == 0
        assert "Text brief" in out
        assert "MF" in out


# ── show-brief ────────────────────────────────────────────────────────


class TestShowBrief:
    def test_show_brief_text(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            ["create-brief", "--title", "Show me", "--team", "Chelsea",
             "--position-group", "GK", "--json"],
            capsys,
        )
        assert code == 0
        create_result = json.loads(out)
        brief_id = create_result["brief"]["brief_id"]

        code, out, _ = _run_cli(["show-brief", brief_id], capsys)
        assert code == 0
        assert "Show me" in out
        assert "Chelsea" in out
        assert "GK" in out

    def test_show_brief_json(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            ["create-brief", "--title", "JSON show", "--position-group", "FW", "--json"],
            capsys,
        )
        assert code == 0
        create_result = json.loads(out)
        brief_id = create_result["brief"]["brief_id"]

        code, out, _ = _run_cli(["show-brief", brief_id, "--json"], capsys)
        assert code == 0
        record = json.loads(out)
        assert record["brief"]["brief_id"] == brief_id
        assert record["brief"]["title"] == "JSON show"

    def test_show_brief_nonexistent_exits(self, isolated_data_root, capsys):
        code, _, err = _run_cli(["show-brief", "nonexistent-id"], capsys)
        assert code != 0
        assert "brief_not_found" in err


# ── validate-brief ────────────────────────────────────────────────────


class TestValidateBrief:
    def test_validate_valid_brief(self, isolated_data_root, tmp_path, capsys):
        brief_file = tmp_path / "valid.json"
        brief_file.write_text(
            json.dumps(_valid_brief_json("brief-valid")), encoding="utf-8"
        )
        code, out, _ = _run_cli(["validate-brief", str(brief_file)], capsys)
        assert code == 0
        assert "VALID" in out
        assert "brief-valid" in out

    def test_validate_valid_brief_json(self, isolated_data_root, tmp_path, capsys):
        brief_file = tmp_path / "valid.json"
        brief_file.write_text(
            json.dumps(_valid_brief_json("brief-valid")), encoding="utf-8"
        )
        code, out, _ = _run_cli(["validate-brief", str(brief_file), "--json"], capsys)
        assert code == 0
        result = json.loads(out)
        assert result["status"] == "valid"
        assert result["brief_id"] == "brief-valid"

    def test_validate_invalid_brief_exits(self, isolated_data_root, tmp_path, capsys):
        bad_payload = _valid_brief_json("brief-invalid")
        bad_payload["position_group"] = "XX"
        brief_file = tmp_path / "invalid.json"
        brief_file.write_text(json.dumps(bad_payload), encoding="utf-8")
        code, _, err = _run_cli(["validate-brief", str(brief_file)], capsys)
        assert code != 0
        assert "INVALID" in err

    def test_validate_missing_file_exits(self, isolated_data_root, tmp_path, capsys):
        code, _, err = _run_cli(
            ["validate-brief", str(tmp_path / "nonexistent.json")], capsys
        )
        assert code != 0
        assert "error" in err.lower()

    def test_validate_does_not_save(self, isolated_data_root, tmp_path, capsys):
        """validate-brief must not write anything to the store."""
        brief_file = tmp_path / "valid.json"
        brief_file.write_text(
            json.dumps(_valid_brief_json("brief-nosave")), encoding="utf-8"
        )
        _run_cli(["validate-brief", str(brief_file)], capsys)
        # list-briefs should still be empty.
        code, out, _ = _run_cli(["list-briefs", "--json"], capsys)
        result = json.loads(out)
        assert result["count"] == 0

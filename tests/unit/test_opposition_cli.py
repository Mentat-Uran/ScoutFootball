"""Unit tests for opposition briefing CLI commands.

Covers:
- ``create-briefing`` from CLI flags (auto-generates briefing_id, saves record)
- ``create-briefing --json`` emits JSON record
- ``create-briefing --from-json`` loads payload from a local JSON file
- ``create-briefing --section "<sid>:<tier>:<summary>"`` builds sections from flags
- ``create-briefing --section-evidence "<sid>:<ref>"`` attaches evidence refs
- ``list-briefings`` on empty and non-empty stores
- ``list-briefings --json`` emits JSON list
- ``show-briefing`` loads and displays one briefing
- ``show-briefing --json`` emits JSON record
- ``validate-briefing`` on a valid file and an invalid file
- Error paths: missing --title, nonexistent id, invalid payload, missing file
- ``validate-briefing`` must not persist anything to the store
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

import pytest

from scoutfootball.__main__ import main
from scoutfootball.opposition.briefing import BRIEFING_SCHEMA, BRIEFING_VERSION


def _valid_briefing_json(briefing_id: str = "briefing-cli-001") -> dict:
    now = datetime.now(tz=UTC).isoformat()
    return {
        "schema": BRIEFING_SCHEMA,
        "version": BRIEFING_VERSION,
        "briefing_id": briefing_id,
        "revision": 1,
        "created_at": now,
        "updated_at": now,
        "author": "maintainer",
        "title": "CLI test briefing",
        "match_id": "fd-match-1",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "kickoff_at": "2026-08-15T15:00:00+00:00",
        "competition": "Premier League",
        "season": "2026-27",
        "sections": [
            {
                "section_id": "opponent_strength",
                "fact_tier": "recorded",
                "summary": "Chelsea are 4th.",
                "evidence_refs": ["fbref/2026-27/Chelsea"],
            },
        ],
        "linked_pattern_card_ids": [],
        "linked_scenario_tree_id": None,
        "linked_post_match_review_id": None,
        "notes": "CLI test.",
        "limitations": [
            "Briefing is a personal local object; not an external fact.",
        ],
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


# ── create-briefing ────────────────────────────────────────────────────


class TestCreateBriefing:
    def test_create_briefing_from_flags(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-briefing",
                "--title", "Flag-based briefing",
                "--home-team", "Arsenal",
                "--away-team", "Chelsea",
                "--competition", "Premier League",
                "--season", "2026-27",
            ],
            capsys,
        )
        assert code == 0
        assert "Created briefing:" in out
        assert "Flag-based briefing" in out
        assert "Arsenal" in out
        assert "Chelsea" in out

    def test_create_briefing_json_output(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-briefing",
                "--title", "JSON briefing",
                "--home-team", "Arsenal",
                "--away-team", "Chelsea",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        assert record["schema"] == "scoutfootball.opposition-briefing-record"
        assert record["briefing"]["title"] == "JSON briefing"
        assert record["briefing"]["home_team"] == "Arsenal"
        assert record["briefing"]["away_team"] == "Chelsea"
        assert record["server_revision"] == 1

    def test_create_briefing_from_json_file(self, isolated_data_root, tmp_path, capsys):
        briefing_file = tmp_path / "briefing.json"
        briefing_file.write_text(
            json.dumps(_valid_briefing_json("briefing-from-file")), encoding="utf-8"
        )
        code, out, _ = _run_cli(
            ["create-briefing", "--from-json", str(briefing_file)],
            capsys,
        )
        assert code == 0
        assert "briefing-from-file" in out

    def test_create_briefing_from_json_with_auto_id(
        self, isolated_data_root, tmp_path, capsys
    ):
        """A --from-json payload without briefing_id should be auto-generated."""
        payload = _valid_briefing_json()
        del payload["briefing_id"]
        briefing_file = tmp_path / "briefing.json"
        briefing_file.write_text(json.dumps(payload), encoding="utf-8")
        code, out, _ = _run_cli(
            ["create-briefing", "--from-json", str(briefing_file), "--json"],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        assert record["briefing"]["briefing_id"].startswith("briefing-")

    def test_create_briefing_with_section_flags(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-briefing",
                "--title", "Sections briefing",
                "--section", "opponent_strength:recorded:Chelsea are 4th.",
                "--section", "key_players:official:Palmer expected to start.",
                "--section-evidence", "opponent_strength:fbref/2026-27/Chelsea",
                "--section-evidence", "opponent_strength:team_match.parquet#row=1",
                "--section-evidence", "key_players:official-squad-list",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        sections = record["briefing"]["sections"]
        assert len(sections) == 2
        # First section carries two evidence refs.
        opp = next(s for s in sections if s["section_id"] == "opponent_strength")
        assert opp["fact_tier"] == "recorded"
        assert len(opp["evidence_refs"]) == 2
        # Second section carries one evidence ref.
        kp = next(s for s in sections if s["section_id"] == "key_players")
        assert kp["fact_tier"] == "official"
        assert len(kp["evidence_refs"]) == 1

    def test_create_briefing_with_custom_section(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-briefing",
                "--title", "Custom section briefing",
                "--section", "custom:set_pieces_zone14:estimated:Set piece plan",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        sections = record["briefing"]["sections"]
        assert sections[0]["section_id"] == "custom:set_pieces_zone14"
        assert sections[0]["fact_tier"] == "estimated"

    def test_create_briefing_missing_title_exits(self, isolated_data_root, capsys):
        code, _, err = _run_cli(["create-briefing"], capsys)
        assert code != 0
        assert "--title is required" in err

    def test_create_briefing_invalid_section_format_exits(
        self, isolated_data_root, capsys
    ):
        code, _, err = _run_cli(
            [
                "create-briefing",
                "--title", "Bad section",
                "--section", "opponent_strength:recorded",  # missing summary
            ],
            capsys,
        )
        assert code != 0
        assert "--section must be" in err

    def test_create_briefing_invalid_section_evidence_format_exits(
        self, isolated_data_root, capsys
    ):
        code, _, err = _run_cli(
            [
                "create-briefing",
                "--title", "Bad evidence",
                "--section-evidence", "no_colon_here",
            ],
            capsys,
        )
        assert code != 0
        assert "--section-evidence must be" in err

    def test_create_briefing_invalid_fact_tier_exits(
        self, isolated_data_root, capsys
    ):
        """Invalid fact_tier is caught by the store validator, not argparse."""
        code, _, err = _run_cli(
            [
                "create-briefing",
                "--title", "Bad tier",
                "--section", "opponent_strength:rumour:Bad tier",
            ],
            capsys,
        )
        assert code != 0
        assert "briefing validation failed" in err.lower()


# ── list-briefings ─────────────────────────────────────────────────────


class TestListBriefings:
    def test_list_empty_store(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(["list-briefings"], capsys)
        assert code == 0
        assert "No briefings" in out

    def test_list_empty_store_json(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(["list-briefings", "--json"], capsys)
        assert code == 0
        result = json.loads(out)
        assert result["count"] == 0
        assert result["briefings"] == []

    def test_list_after_create(self, isolated_data_root, capsys):
        _run_cli(
            ["create-briefing", "--title", "First", "--json"],
            capsys,
        )
        code, out, _ = _run_cli(["list-briefings", "--json"], capsys)
        assert code == 0
        result = json.loads(out)
        assert result["count"] == 1
        assert result["briefings"][0]["title"] == "First"

    def test_list_text_output(self, isolated_data_root, capsys):
        _run_cli(
            [
                "create-briefing",
                "--title", "Text briefing",
                "--home-team", "Arsenal",
                "--away-team", "Chelsea",
                "--competition", "Premier League",
                "--json",
            ],
            capsys,
        )
        code, out, _ = _run_cli(["list-briefings"], capsys)
        assert code == 0
        assert "Text briefing" in out
        assert "Arsenal" in out
        assert "Chelsea" in out
        assert "Premier League" in out


# ── show-briefing ──────────────────────────────────────────────────────


class TestShowBriefing:
    def test_show_briefing_text(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-briefing",
                "--title", "Show me",
                "--home-team", "Arsenal",
                "--away-team", "Chelsea",
                "--competition", "Premier League",
                "--section", "opponent_strength:recorded:Chelsea are 4th.",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        create_result = json.loads(out)
        briefing_id = create_result["briefing"]["briefing_id"]

        code, out, _ = _run_cli(["show-briefing", briefing_id], capsys)
        assert code == 0
        assert "Briefing:" in out
        assert "Show me" in out
        assert "Arsenal" in out
        assert "Chelsea" in out
        assert "Premier League" in out
        assert "opponent_strength" in out

    def test_show_briefing_json(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            ["create-briefing", "--title", "JSON show", "--json"],
            capsys,
        )
        assert code == 0
        create_result = json.loads(out)
        briefing_id = create_result["briefing"]["briefing_id"]

        code, out, _ = _run_cli(["show-briefing", briefing_id, "--json"], capsys)
        assert code == 0
        record = json.loads(out)
        assert record["briefing"]["briefing_id"] == briefing_id
        assert record["briefing"]["title"] == "JSON show"

    def test_show_briefing_nonexistent_exits(self, isolated_data_root, capsys):
        code, _, err = _run_cli(["show-briefing", "nonexistent-id"], capsys)
        assert code != 0
        assert "briefing_not_found" in err


# ── validate-briefing ──────────────────────────────────────────────────


class TestValidateBriefing:
    def test_validate_valid_briefing(self, isolated_data_root, tmp_path, capsys):
        briefing_file = tmp_path / "valid.json"
        briefing_file.write_text(
            json.dumps(_valid_briefing_json("briefing-valid")), encoding="utf-8"
        )
        code, out, _ = _run_cli(["validate-briefing", str(briefing_file)], capsys)
        assert code == 0
        assert "VALID" in out
        assert "briefing-valid" in out

    def test_validate_valid_briefing_json(self, isolated_data_root, tmp_path, capsys):
        briefing_file = tmp_path / "valid.json"
        briefing_file.write_text(
            json.dumps(_valid_briefing_json("briefing-valid")), encoding="utf-8"
        )
        code, out, _ = _run_cli(
            ["validate-briefing", str(briefing_file), "--json"], capsys
        )
        assert code == 0
        result = json.loads(out)
        assert result["status"] == "valid"
        assert result["briefing_id"] == "briefing-valid"

    def test_validate_invalid_briefing_exits(
        self, isolated_data_root, tmp_path, capsys
    ):
        bad_payload = _valid_briefing_json("briefing-invalid")
        # Inject an invalid fact_tier to trigger validation failure.
        bad_payload["sections"][0]["fact_tier"] = "rumour"
        briefing_file = tmp_path / "invalid.json"
        briefing_file.write_text(json.dumps(bad_payload), encoding="utf-8")
        code, _, err = _run_cli(["validate-briefing", str(briefing_file)], capsys)
        assert code != 0
        assert "INVALID" in err

    def test_validate_missing_file_exits(self, isolated_data_root, tmp_path, capsys):
        code, _, err = _run_cli(
            ["validate-briefing", str(tmp_path / "nonexistent.json")], capsys
        )
        assert code != 0
        assert "error" in err.lower()

    def test_validate_does_not_save(self, isolated_data_root, tmp_path, capsys):
        """validate-briefing must not write anything to the store."""
        briefing_file = tmp_path / "valid.json"
        briefing_file.write_text(
            json.dumps(_valid_briefing_json("briefing-nosave")), encoding="utf-8"
        )
        _run_cli(["validate-briefing", str(briefing_file)], capsys)
        # list-briefings should still be empty.
        code, out, _ = _run_cli(["list-briefings", "--json"], capsys)
        result = json.loads(out)
        assert result["count"] == 0

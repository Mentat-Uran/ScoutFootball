"""Unit tests for decision dossier CLI commands.

Covers:
- ``create-dossier`` from CLI flags (auto-generates dossier_id, saves record)
- ``create-dossier --json`` emits JSON record
- ``create-dossier --from-json`` loads payload from a local file
- ``create-dossier --decision`` forces status='decided'
- ``create-dossier --dossier-id`` uses an explicit id
- ``create-dossier`` error paths: missing --title, invalid --dossier-id
- ``list-dossiers`` on empty and non-empty stores (text + JSON)
- ``show-dossier`` text and JSON output
- ``show-dossier`` on nonexistent id exits non-zero
- ``validate-dossier`` on a valid file and an invalid file
- ``validate-dossier`` does not write to the store
- ``validate-dossier`` on missing file exits non-zero
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

import pytest

from scoutfootball.__main__ import main
from scoutfootball.recruitment.dossier import DOSSIER_SCHEMA, DOSSIER_VERSION


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _valid_dossier_json(dossier_id: str = "dossier-cli-001") -> dict:
    return {
        "schema": DOSSIER_SCHEMA,
        "version": DOSSIER_VERSION,
        "dossier_id": dossier_id,
        "revision": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "author": "maintainer",
        "title": "CLI test dossier",
        "brief_id": "brief-cli-001",
        "candidate_player_id": "understat|1234",
        "candidate_player_name": "Player X",
        "candidate_team_name": "Club Y",
        "candidate_season_id": "2425",
        "status": "draft",
        "decision": None,
        "decision_note": "",
        "supporting_evidence": [
            {
                "evidence_id": "ev-001",
                "fact_tier": "recorded",
                "summary": "Top 5% crosses p90.",
                "evidence_refs": ["fbref/2425/PlayerX"],
            }
        ],
        "counter_evidence": [],
        "comparisons": [],
        "risks": [
            {
                "risk_id": "r-001",
                "summary": "Injury history in 2324 season.",
                "severity": "medium",
                "fact_tier": "recorded",
                "evidence_refs": ["transfermarkt/PlayerX/injuries"],
            }
        ],
        "human_opinion": "Fits the brief.",
        "recommendation": "Proceed with bid.",
        "linked_artifacts": ["brief-cli-001"],
        "notes": "CLI test.",
        "limitations": [
            "Dossier is a personal local object; not an external fact.",
            "Decision is the maintainer's honest judgment, not an automated recommendation.",
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


# ── create-dossier ────────────────────────────────────────────────────


class TestCreateDossier:
    def test_create_dossier_from_flags(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-dossier",
                "--title", "Flag-based dossier",
                "--brief-id", "brief-001",
                "--candidate-player-id", "understat|1234",
                "--candidate-player-name", "Player A",
                "--candidate-team-name", "Arsenal",
                "--candidate-season-id", "2425",
            ],
            capsys,
        )
        assert code == 0
        assert "Created dossier:" in out
        assert "Flag-based dossier" in out
        assert "Player A" in out
        assert "understat|1234" in out

    def test_create_dossier_json_output(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-dossier",
                "--title", "JSON dossier",
                "--candidate-player-name", "Player J",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        assert record["schema"] == "scoutfootball.recruitment-decision-dossier-record"
        assert record["dossier"]["title"] == "JSON dossier"
        assert record["dossier"]["status"] == "draft"
        assert record["dossier"]["decision"] is None
        assert record["server_revision"] == 1

    def test_create_dossier_from_json_file(self, isolated_data_root, tmp_path, capsys):
        dossier_file = tmp_path / "dossier.json"
        dossier_file.write_text(
            json.dumps(_valid_dossier_json("dossier-from-file")), encoding="utf-8"
        )
        code, out, _ = _run_cli(
            ["create-dossier", "--from-json", str(dossier_file)],
            capsys,
        )
        assert code == 0
        assert "dossier-from-file" in out

    def test_create_dossier_from_json_file_json_output(
        self, isolated_data_root, tmp_path, capsys
    ):
        dossier_file = tmp_path / "dossier.json"
        dossier_file.write_text(
            json.dumps(_valid_dossier_json("dossier-from-file-json")), encoding="utf-8"
        )
        code, out, _ = _run_cli(
            ["create-dossier", "--from-json", str(dossier_file), "--json"],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        assert record["dossier"]["dossier_id"] == "dossier-from-file-json"
        assert record["dossier"]["title"] == "CLI test dossier"

    def test_create_dossier_decision_forces_decided_status(
        self, isolated_data_root, capsys
    ):
        code, out, _ = _run_cli(
            [
                "create-dossier",
                "--title", "Decided dossier",
                "--decision", "proceed",
                "--decision-note", "Bid accepted.",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        assert record["dossier"]["status"] == "decided"
        assert record["dossier"]["decision"] == "proceed"
        assert record["dossier"]["decision_note"] == "Bid accepted."

    def test_create_dossier_explicit_dossier_id(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-dossier",
                "--title", "Explicit id",
                "--dossier-id", "dossier-explicit-001",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        assert record["dossier"]["dossier_id"] == "dossier-explicit-001"

    def test_create_dossier_missing_title_exits(self, isolated_data_root, capsys):
        code, _, err = _run_cli(
            ["create-dossier", "--candidate-player-name", "No title"],
            capsys,
        )
        assert code != 0
        assert "--title is required" in err

    def test_create_dossier_invalid_dossier_id_exits(
        self, isolated_data_root, capsys
    ):
        code, _, err = _run_cli(
            [
                "create-dossier",
                "--title", "Bad id",
                "--dossier-id", "bad/id/with/slashes",
            ],
            capsys,
        )
        assert code != 0
        assert "error" in err.lower()

    def test_create_dossier_linked_artifacts(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-dossier",
                "--title", "Linked artifacts",
                "--linked-artifacts", "brief-001", "shortlist-002",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        assert record["dossier"]["linked_artifacts"] == ["brief-001", "shortlist-002"]


# ── list-dossiers ─────────────────────────────────────────────────────


class TestListDossiers:
    def test_list_empty_store(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(["list-dossiers"], capsys)
        assert code == 0
        assert "No dossiers" in out

    def test_list_empty_store_json(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(["list-dossiers", "--json"], capsys)
        assert code == 0
        result = json.loads(out)
        assert result["count"] == 0
        assert result["dossiers"] == []

    def test_list_after_create(self, isolated_data_root, capsys):
        _run_cli(
            ["create-dossier", "--title", "First", "--json"],
            capsys,
        )
        _run_cli(
            ["create-dossier", "--title", "Second", "--json"],
            capsys,
        )
        code, out, _ = _run_cli(["list-dossiers", "--json"], capsys)
        assert code == 0
        result = json.loads(out)
        assert result["count"] == 2
        titles = {item["title"] for item in result["dossiers"]}
        assert titles == {"First", "Second"}

    def test_list_text_output(self, isolated_data_root, capsys):
        _run_cli(
            ["create-dossier", "--title", "Text dossier", "--json"],
            capsys,
        )
        code, out, _ = _run_cli(["list-dossiers"], capsys)
        assert code == 0
        assert "Text dossier" in out
        assert "Found 1 dossier" in out

    def test_list_includes_status_and_decision(self, isolated_data_root, capsys):
        _run_cli(
            [
                "create-dossier",
                "--title", "Decided one",
                "--decision", "proceed",
                "--json",
            ],
            capsys,
        )
        code, out, _ = _run_cli(["list-dossiers"], capsys)
        assert code == 0
        assert "status=decided" in out
        assert "decision=proceed" in out


# ── show-dossier ──────────────────────────────────────────────────────


class TestShowDossier:
    def test_show_dossier_text(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-dossier",
                "--title", "Show me",
                "--candidate-player-name", "Player S",
                "--candidate-team-name", "Chelsea",
                "--brief-id", "brief-show-001",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        create_result = json.loads(out)
        dossier_id = create_result["dossier"]["dossier_id"]

        code, out, _ = _run_cli(["show-dossier", dossier_id], capsys)
        assert code == 0
        assert "Show me" in out
        assert "Player S" in out
        assert "Chelsea" in out
        assert "brief-show-001" in out

    def test_show_dossier_json(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            ["create-dossier", "--title", "JSON show", "--json"],
            capsys,
        )
        assert code == 0
        create_result = json.loads(out)
        dossier_id = create_result["dossier"]["dossier_id"]

        code, out, _ = _run_cli(["show-dossier", dossier_id, "--json"], capsys)
        assert code == 0
        record = json.loads(out)
        assert record["dossier"]["dossier_id"] == dossier_id
        assert record["dossier"]["title"] == "JSON show"
        assert record["server_revision"] == 1

    def test_show_dossier_displays_evidence_and_risks(
        self, isolated_data_root, tmp_path, capsys
    ):
        """show-dossier text output must surface evidence, comparisons and risks."""
        payload = _valid_dossier_json("dossier-rich-001")
        dossier_file = tmp_path / "rich.json"
        dossier_file.write_text(json.dumps(payload), encoding="utf-8")
        _run_cli(["create-dossier", "--from-json", str(dossier_file)], capsys)

        code, out, _ = _run_cli(["show-dossier", "dossier-rich-001"], capsys)
        assert code == 0
        assert "supporting evidence" in out
        assert "ev-001" in out
        assert "Top 5% crosses p90" in out
        assert "risks" in out
        assert "r-001" in out

    def test_show_dossier_nonexistent_exits(self, isolated_data_root, capsys):
        code, _, err = _run_cli(["show-dossier", "nonexistent-id"], capsys)
        assert code != 0
        assert "dossier_not_found" in err


# ── validate-dossier ──────────────────────────────────────────────────


class TestValidateDossier:
    def test_validate_valid_dossier(self, isolated_data_root, tmp_path, capsys):
        dossier_file = tmp_path / "valid.json"
        dossier_file.write_text(
            json.dumps(_valid_dossier_json("dossier-valid")), encoding="utf-8"
        )
        code, out, _ = _run_cli(["validate-dossier", str(dossier_file)], capsys)
        assert code == 0
        assert "VALID" in out
        assert "dossier-valid" in out

    def test_validate_valid_dossier_json(self, isolated_data_root, tmp_path, capsys):
        dossier_file = tmp_path / "valid.json"
        dossier_file.write_text(
            json.dumps(_valid_dossier_json("dossier-valid")), encoding="utf-8"
        )
        code, out, _ = _run_cli(
            ["validate-dossier", str(dossier_file), "--json"], capsys
        )
        assert code == 0
        result = json.loads(out)
        assert result["status"] == "valid"
        assert result["dossier_id"] == "dossier-valid"

    def test_validate_invalid_dossier_exits(self, isolated_data_root, tmp_path, capsys):
        bad_payload = _valid_dossier_json("dossier-invalid")
        bad_payload["status"] = "bogus_status"
        dossier_file = tmp_path / "invalid.json"
        dossier_file.write_text(json.dumps(bad_payload), encoding="utf-8")
        code, _, err = _run_cli(["validate-dossier", str(dossier_file)], capsys)
        assert code != 0
        assert "INVALID" in err

    def test_validate_decided_without_decision_exits(
        self, isolated_data_root, tmp_path, capsys
    ):
        """validate-dossier must catch semantic errors, not just schema ones."""
        bad_payload = _valid_dossier_json("dossier-semantics")
        bad_payload["status"] = "decided"
        bad_payload["decision"] = None
        dossier_file = tmp_path / "semantics.json"
        dossier_file.write_text(json.dumps(bad_payload), encoding="utf-8")
        code, _, err = _run_cli(["validate-dossier", str(dossier_file)], capsys)
        assert code != 0
        assert "INVALID" in err

    def test_validate_missing_file_exits(self, isolated_data_root, tmp_path, capsys):
        code, _, err = _run_cli(
            ["validate-dossier", str(tmp_path / "nonexistent.json")], capsys
        )
        assert code != 0
        assert "error" in err.lower()

    def test_validate_does_not_save(self, isolated_data_root, tmp_path, capsys):
        """validate-dossier must not write anything to the store."""
        dossier_file = tmp_path / "valid.json"
        dossier_file.write_text(
            json.dumps(_valid_dossier_json("dossier-nosave")), encoding="utf-8"
        )
        _run_cli(["validate-dossier", str(dossier_file)], capsys)
        # list-dossiers should still be empty.
        code, out, _ = _run_cli(["list-dossiers", "--json"], capsys)
        assert code == 0
        result = json.loads(out)
        assert result["count"] == 0


# ── End-to-end round-trip ─────────────────────────────────────────────


class TestDossierCliRoundTrip:
    """Create → list → show → validate round-trip via the CLI only."""

    def test_create_list_show_round_trip(self, isolated_data_root, capsys):
        # 1. Create from a JSON file with rich content.
        payload = _valid_dossier_json("dossier-e2e-001")
        payload["title"] = "End to end"
        payload["status"] = "decided"
        payload["decision"] = "proceed"
        payload["decision_note"] = "All checks passed."
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            json.dump(payload, handle)
            tmp_json = Path(handle.name)

        try:
            code, out, _ = _run_cli(
                ["create-dossier", "--from-json", str(tmp_json), "--json"], capsys
            )
            assert code == 0
            created = json.loads(out)
            assert created["dossier"]["dossier_id"] == "dossier-e2e-001"
            assert created["dossier"]["status"] == "decided"
            assert created["dossier"]["decision"] == "proceed"
        finally:
            tmp_json.unlink(missing_ok=True)

        # 2. List and confirm it appears.
        code, out, _ = _run_cli(["list-dossiers", "--json"], capsys)
        assert code == 0
        listed = json.loads(out)
        assert listed["count"] == 1
        assert listed["dossiers"][0]["dossier_id"] == "dossier-e2e-001"
        assert listed["dossiers"][0]["status"] == "decided"
        assert listed["dossiers"][0]["decision"] == "proceed"

        # 3. Show by id and confirm full payload round-trips.
        code, out, _ = _run_cli(["show-dossier", "dossier-e2e-001", "--json"], capsys)
        assert code == 0
        shown = json.loads(out)
        assert shown["dossier"]["title"] == "End to end"
        assert shown["dossier"]["decision_note"] == "All checks passed."
        assert shown["dossier"]["supporting_evidence"][0]["evidence_id"] == "ev-001"

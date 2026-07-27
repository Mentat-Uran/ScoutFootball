"""Unit tests for the ``export-local-pack`` and ``import-local-pack`` CLI
commands.

These commands mirror the ``POST /local-pack/export`` and
``POST /local-pack/import`` API endpoints but work without a running
API server, so the maintainer can migrate or back up local artifacts
from a terminal session.  They are the L1.5 extension improvement
called out in WORKFLOW_LOG.md reference workflow 9.

Coverage:

- ``export-local-pack``: stdout vs ``--output PATH``, parent dir
  creation, empty store, argparse parsing.
- ``import-local-pack``: dry-run preview (default), ``--confirm``
  writes, ``--overwrite`` replaces, conflict reporting, stdin input,
  missing-file / invalid-schema error paths, argparse parsing.
- CLI round-trip: ``export-local-pack --output`` →
  ``import-local-pack --from --confirm`` produces equivalent records.

The store-level correctness (atomic writes, revision backups, hash
verification) is covered by ``test_portable_pack.py`` and is not
duplicated here; these tests focus on the CLI surface (argparse, file
I/O, stdout/stderr, exit codes, dry-run vs confirmed behavior).
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scoutfootball.__main__ import (
    _cmd_export_local_pack,
    _cmd_import_local_pack,
    build_parser,
)
from scoutfootball.opposition.briefing import (
    BRIEFING_SCHEMA,
    BRIEFING_VERSION,
)
from scoutfootball.recruitment.brief import (
    BRIEF_SCHEMA,
    BRIEF_VERSION,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _valid_brief_payload(
    brief_id: str = "brief-cli-001",
    *,
    title: str = "CLI test brief",
    **overrides,
) -> dict:
    payload = {
        "schema": BRIEF_SCHEMA,
        "version": BRIEF_VERSION,
        "brief_id": brief_id,
        "revision": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "author": "maintainer",
        "title": title,
        "team": "Arsenal",
        "position_group": "DF",
        "position_detail": "LB",
        "role": "attacking_fullback",
        "budget_eur": 30_000_000,
        "age_min": 21,
        "age_max": 27,
        "contract_years_min": 3,
        "league_preferences": ["Premier League"],
        "language_preferences": ["English"],
        "risk_tolerance": "medium",
        "minimum_minutes": 1500,
        "notes": "",
        "limitations": [],
    }
    payload.update(overrides)
    return payload


def _valid_briefing_payload(
    briefing_id: str = "briefing-cli-001",
    *,
    home_team: str = "Arsenal",
    **overrides,
) -> dict:
    payload = {
        "schema": BRIEFING_SCHEMA,
        "version": BRIEFING_VERSION,
        "briefing_id": briefing_id,
        "revision": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "author": "maintainer",
        "title": "CLI test briefing",
        "match_id": "fd-match-cli-001",
        "home_team": home_team,
        "away_team": "Chelsea",
        "kickoff_at": "2026-08-15T15:00:00+00:00",
        "competition": "Premier League",
        "season": "2026-27",
        "sections": [
            {
                "section_id": "opponent_strength",
                "fact_tier": "recorded",
                "summary": "Chelsea are 4th in the table.",
                "evidence_refs": ["fbref/2026-27/Chelsea"],
            },
        ],
        "linked_pattern_card_ids": [],
        "linked_scenario_tree_id": None,
        "linked_post_match_review_id": None,
        "notes": "",
        "limitations": [],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def patched_stores(tmp_path: Path, monkeypatch):
    """Patch ``_brief_store()`` and ``_briefing_store()`` at isolated
    tmp_path roots so CLI tests never touch the real report_root.

    Mirrors the fixture in ``test_portable_pack.py`` but kept local so
    CLI tests can run independently.
    """
    from scoutfootball.opposition.store import BriefingStore
    from scoutfootball.recruitment.store import BriefStore

    brief_root = tmp_path / "recruitment" / "briefs"
    briefing_root = tmp_path / "opposition" / "briefings"
    brief_root.mkdir(parents=True, exist_ok=True)
    briefing_root.mkdir(parents=True, exist_ok=True)

    brief_store = BriefStore(brief_root)
    briefing_store = BriefingStore(briefing_root)

    monkeypatch.setattr("scoutfootball.api._brief_store", lambda: brief_store)
    monkeypatch.setattr("scoutfootball.api._briefing_store", lambda: briefing_store)
    return brief_store, briefing_store


def _save_brief(store, brief_id: str, **overrides) -> dict:
    return store.save(
        brief_id, _valid_brief_payload(brief_id=brief_id, **overrides)
    )


def _save_briefing(store, briefing_id: str, **overrides) -> dict:
    return store.save(
        briefing_id, _valid_briefing_payload(briefing_id=briefing_id, **overrides)
    )


def _export_args(**overrides) -> argparse.Namespace:
    base = {"output": None}
    base.update(overrides)
    return argparse.Namespace(**base)


def _import_args(**overrides) -> argparse.Namespace:
    base = {
        "from_path": None,
        "overwrite": False,
        "confirm": False,
        "json": False,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


# ── export-local-pack ────────────────────────────────────────────────


class TestExportLocalPackCli:
    def test_stdout_emits_valid_pack_json(self, patched_stores, capsys):
        brief_store, briefing_store = patched_stores
        _save_brief(brief_store, "brief-cli-001")
        _save_briefing(briefing_store, "briefing-cli-001")

        _cmd_export_local_pack(_export_args(output=None))
        out = capsys.readouterr().out
        pack = json.loads(out)

        assert pack["schema"] == "scoutfootball.portable-pack"
        assert pack["version"] == "1.0.0"
        assert pack["sections"]["recruitment_briefs"]["count"] == 1
        assert pack["sections"]["opposition_briefings"]["count"] == 1
        assert "section_hashes" in pack
        assert "exported_at" in pack

    def test_output_flag_writes_pack_to_file_and_prints_summary(
        self, patched_stores, tmp_path, capsys
    ):
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-cli-001", title="File output test")
        _save_brief(brief_store, "brief-cli-002", title="Second brief")

        out_path = tmp_path / "out" / "pack.json"
        _cmd_export_local_pack(_export_args(output=str(out_path)))

        assert out_path.exists()
        pack = json.loads(out_path.read_text(encoding="utf-8"))
        assert pack["sections"]["recruitment_briefs"]["count"] == 2

        stdout = capsys.readouterr().out
        assert str(out_path) in stdout
        assert "recruitment_briefs: 2 record(s)" in stdout
        assert "opposition_briefings: 0 record(s)" in stdout
        assert "scoutfootball.portable-pack" in stdout

    def test_output_flag_creates_parent_dirs(self, patched_stores, tmp_path):
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-cli-001")

        nested = tmp_path / "a" / "b" / "c" / "pack.json"
        assert not nested.parent.exists()

        _cmd_export_local_pack(_export_args(output=str(nested)))

        assert nested.exists()
        pack = json.loads(nested.read_text(encoding="utf-8"))
        assert pack["schema"] == "scoutfootball.portable-pack"

    def test_empty_store_produces_empty_pack(self, patched_stores, capsys):
        _cmd_export_local_pack(_export_args(output=None))
        out = capsys.readouterr().out
        pack = json.loads(out)

        assert pack["schema"] == "scoutfootball.portable-pack"
        assert pack["sections"]["recruitment_briefs"]["count"] == 0
        assert pack["sections"]["opposition_briefings"]["count"] == 0


# ── import-local-pack ────────────────────────────────────────────────


class TestImportLocalPackCli:
    def test_dry_run_prints_preview_without_writing(
        self, patched_stores, tmp_path, capsys
    ):
        brief_store, briefing_store = patched_stores
        _save_brief(brief_store, "brief-cli-001")
        _save_briefing(briefing_store, "briefing-cli-001")

        # Export to a file, then switch to a fresh store via env var
        # by re-patching the stores to a new tmp_path.
        pack_path = tmp_path / "source" / "pack.json"
        pack_path.parent.mkdir(parents=True)
        _cmd_export_local_pack(_export_args(output=str(pack_path)))

        # Reset captured stdout so it doesn't pollute the next assertion.
        capsys.readouterr()

        # Re-patch stores to a fresh empty root to simulate target env.
        target_brief_root = tmp_path / "target" / "recruitment" / "briefs"
        target_briefing_root = tmp_path / "target" / "opposition" / "briefings"
        target_brief_root.mkdir(parents=True)
        target_briefing_root.mkdir(parents=True)
        from scoutfootball.opposition.store import BriefingStore
        from scoutfootball.recruitment.store import BriefStore

        target_brief_store = BriefStore(target_brief_root)
        target_briefing_store = BriefingStore(target_briefing_root)
        # The patched_stores fixture already monkeypatched; re-monkeypatch
        # by using the same attribute name.
        import scoutfootball.api as api_mod

        api_mod._brief_store = lambda: target_brief_store
        api_mod._briefing_store = lambda: target_briefing_store

        # Dry-run: --from PATH, no --confirm.
        _cmd_import_local_pack(_import_args(from_path=str(pack_path)))
        out = capsys.readouterr().out

        assert "Portable pack import preview (dry-run)" in out
        assert "recruitment_briefs: 1 record(s)" in out
        assert "opposition_briefings: 1 record(s)" in out
        assert "Pass --confirm" in out

        # Confirm nothing was written to the target store.
        assert target_brief_store.list_records() == []
        assert target_briefing_store.list_records() == []

    def test_dry_run_json_emits_preview_json(self, patched_stores, tmp_path, capsys):
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-cli-001")

        pack_path = tmp_path / "pack.json"
        _cmd_export_local_pack(_export_args(output=str(pack_path)))
        capsys.readouterr()

        _cmd_import_local_pack(
            _import_args(from_path=str(pack_path), json=True)
        )
        out = capsys.readouterr().out
        result = json.loads(out)

        assert result["status"] == "preview"
        assert result["schema"] == "scoutfootball.portable-pack"
        assert result["version"] == "1.0.0"
        assert result["sections"][0]["section"] == "recruitment_briefs"
        assert result["sections"][0]["count"] == 1
        assert "Pass --confirm" in result["note"]

    def test_confirm_writes_records_to_store(
        self, patched_stores, tmp_path, capsys
    ):
        brief_store, briefing_store = patched_stores
        _save_brief(brief_store, "brief-cli-001")
        _save_briefing(briefing_store, "briefing-cli-001")

        pack_path = tmp_path / "pack.json"
        _cmd_export_local_pack(_export_args(output=str(pack_path)))
        capsys.readouterr()

        # Switch to a fresh target store.
        target_brief_root = tmp_path / "target" / "recruitment" / "briefs"
        target_briefing_root = tmp_path / "target" / "opposition" / "briefings"
        target_brief_root.mkdir(parents=True)
        target_briefing_root.mkdir(parents=True)
        from scoutfootball.opposition.store import BriefingStore
        from scoutfootball.recruitment.store import BriefStore

        target_brief_store = BriefStore(target_brief_root)
        target_briefing_store = BriefingStore(target_briefing_root)
        import scoutfootball.api as api_mod

        api_mod._brief_store = lambda: target_brief_store
        api_mod._briefing_store = lambda: target_briefing_store

        _cmd_import_local_pack(
            _import_args(from_path=str(pack_path), confirm=True)
        )
        out = capsys.readouterr().out

        assert "Import status: ok" in out
        assert "recruitment_briefs: imported=1" in out
        assert "opposition_briefings: imported=1" in out

        # Verify records actually landed in the target store.
        assert len(target_brief_store.list_records()) == 1
        assert len(target_briefing_store.list_records()) == 1

    def test_confirm_without_overwrite_reports_conflicts(
        self, patched_stores, tmp_path, capsys
    ):
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-cli-001")

        pack_path = tmp_path / "pack.json"
        _cmd_export_local_pack(_export_args(output=str(pack_path)))
        capsys.readouterr()

        # Target store already has the same brief_id.
        _cmd_import_local_pack(
            _import_args(from_path=str(pack_path), confirm=True)
        )
        out = capsys.readouterr().out

        # Source store == target store (we didn't switch), so the import
        # hits a conflict on brief-cli-001.
        assert "Import status: ok" in out
        assert "recruitment_briefs: imported=0 conflicts=1" in out

    def test_confirm_with_overwrite_replaces_records(
        self, patched_stores, tmp_path, capsys
    ):
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-cli-001", title="Original title")

        pack_path = tmp_path / "pack.json"
        _cmd_export_local_pack(_export_args(output=str(pack_path)))
        capsys.readouterr()

        # Delete the local record and re-save a different payload under
        # the same ID, so the local store has revision 1 with new content
        # while the pack contains revision 1 with the original content.
        # This mirrors the conflict scenario in test_portable_pack.py.
        for path in brief_store.root.glob("*.json"):
            path.unlink()
        _save_brief(
            brief_store, "brief-cli-001", title="Updated locally"
        )

        _cmd_import_local_pack(
            _import_args(
                from_path=str(pack_path), confirm=True, overwrite=True
            )
        )
        out = capsys.readouterr().out

        assert "Import status: ok" in out
        assert "recruitment_briefs: imported=1" in out
        # The overwritten record should now have a bumped revision.
        record = brief_store.load("brief-cli-001")
        assert record["server_revision"] >= 2
        assert record["brief"]["title"] == "Original title"

    def test_from_stdin_reads_pack_from_stdin(
        self, patched_stores, tmp_path, monkeypatch, capsys
    ):
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-cli-001")

        pack_path = tmp_path / "pack.json"
        _cmd_export_local_pack(_export_args(output=str(pack_path)))
        capsys.readouterr()

        pack_text = pack_path.read_text(encoding="utf-8")
        monkeypatch.setattr("sys.stdin", _FakeStdin(pack_text))

        _cmd_import_local_pack(
            _import_args(from_path=None, json=True)
        )
        out = capsys.readouterr().out
        result = json.loads(out)

        assert result["status"] == "preview"
        assert result["sections"][0]["count"] == 1

    def test_missing_file_exits_nonzero(self, patched_stores, tmp_path, capsys):
        missing = tmp_path / "does-not-exist.json"
        with pytest.raises(SystemExit) as exc_info:
            _cmd_import_local_pack(_import_args(from_path=str(missing)))

        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "pack file not found" in err

    def test_invalid_schema_exits_nonzero(
        self, patched_stores, tmp_path, capsys
    ):
        bad_pack_path = tmp_path / "bad-pack.json"
        bad_pack_path.write_text(
            json.dumps({"schema": "wrong.schema", "version": "1.0.0"}),
            encoding="utf-8",
        )

        with pytest.raises(SystemExit) as exc_info:
            _cmd_import_local_pack(_import_args(from_path=str(bad_pack_path)))

        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "pack schema" in err
        assert "is not 'scoutfootball.portable-pack'" in err

    def test_invalid_version_exits_nonzero(
        self, patched_stores, tmp_path, capsys
    ):
        bad_pack_path = tmp_path / "bad-version.json"
        bad_pack_path.write_text(
            json.dumps(
                {"schema": "scoutfootball.portable-pack", "version": "9.9.9"}
            ),
            encoding="utf-8",
        )

        with pytest.raises(SystemExit) as exc_info:
            _cmd_import_local_pack(_import_args(from_path=str(bad_pack_path)))

        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "pack version" in err
        assert "is not '1.0.0'" in err


# ── CLI round-trip ──────────────────────────────────────────────────


class TestCliRoundTrip:
    def test_export_then_import_round_trip(
        self, patched_stores, tmp_path, capsys
    ):
        """End-to-end: ``export-local-pack --output`` →
        ``import-local-pack --from --confirm`` yields equivalent records
        in the target store.
        """
        brief_store, briefing_store = patched_stores
        _save_brief(brief_store, "brief-rt-001", title="Round trip brief")
        _save_brief(brief_store, "brief-rt-002", title="Second brief")
        _save_briefing(briefing_store, "briefing-rt-001")

        pack_path = tmp_path / "round-trip.json"
        _cmd_export_local_pack(_export_args(output=str(pack_path)))
        capsys.readouterr()

        # Switch to a fresh target store.
        target_brief_root = tmp_path / "target" / "recruitment" / "briefs"
        target_briefing_root = tmp_path / "target" / "opposition" / "briefings"
        target_brief_root.mkdir(parents=True)
        target_briefing_root.mkdir(parents=True)
        from scoutfootball.opposition.store import BriefingStore
        from scoutfootball.recruitment.store import BriefStore

        target_brief_store = BriefStore(target_brief_root)
        target_briefing_store = BriefingStore(target_briefing_root)
        import scoutfootball.api as api_mod

        api_mod._brief_store = lambda: target_brief_store
        api_mod._briefing_store = lambda: target_briefing_store

        _cmd_import_local_pack(
            _import_args(from_path=str(pack_path), confirm=True)
        )
        capsys.readouterr()

        # Verify both briefs and the briefing landed in the target.
        target_briefs = target_brief_store.list_records()
        target_briefings = target_briefing_store.list_records()
        assert {b["brief_id"] for b in target_briefs} == {
            "brief-rt-001",
            "brief-rt-002",
        }
        assert {b["briefing_id"] for b in target_briefings} == {
            "briefing-rt-001"
        }

        # Verify content equivalence (not envelope — envelope is target-managed).
        source_brief_1 = brief_store.load("brief-rt-001")["brief"]
        target_brief_1 = target_brief_store.load("brief-rt-001")["brief"]
        # Strip envelope-managed fields before comparing.
        for key in ("server_revision", "stored_at"):
            target_brief_1.pop(key, None)
        assert source_brief_1["title"] == target_brief_1["title"]
        assert source_brief_1["brief_id"] == target_brief_1["brief_id"]


# ── argparse parsing ────────────────────────────────────────────────


class TestArgparseParsing:
    def test_export_local_pack_parses_output_flag(self):
        parser = build_parser()
        args = parser.parse_args(
            ["export-local-pack", "--output", "/tmp/pack.json"]
        )
        assert args.output == "/tmp/pack.json"

    def test_export_local_pack_output_defaults_to_none(self):
        parser = build_parser()
        args = parser.parse_args(["export-local-pack"])
        assert args.output is None

    def test_import_local_pack_parses_all_flags(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "import-local-pack",
                "--from",
                "/tmp/pack.json",
                "--overwrite",
                "--confirm",
                "--json",
            ]
        )
        assert args.from_path == "/tmp/pack.json"
        assert args.overwrite is True
        assert args.confirm is True
        assert args.json is True

    def test_import_local_pack_flags_default_false(self):
        parser = build_parser()
        args = parser.parse_args(["import-local-pack"])
        assert args.from_path is None
        assert args.overwrite is False
        assert args.confirm is False
        assert args.json is False


# ── Helpers ──────────────────────────────────────────────────────────


class _FakeStdin:
    """Minimal stdin replacement for tests that monkeypatch sys.stdin."""

    def __init__(self, text: str) -> None:
        self._text = text

    def read(self) -> str:
        return self._text

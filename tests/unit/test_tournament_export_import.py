"""Unit tests for export_wc_tournament_state and import_wc_tournament_state.

Covers:
- Export returns valid base64url-encoded JSON with required fields
- Import round-trips correctly (export → import → re-export yields same state)
- Import persists state to disk
- Error handling: invalid base64, invalid JSON, incompatible schema
- Export with knockout bracket present
- State size and format metadata
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from scoutfootball.api import (
    export_wc_tournament_state,
    import_wc_tournament_state,
    preview_wc_tournament_import,
)
from scoutfootball.worldcup.tournament import (
    apply_result,
    generate_knockout_bracket,
    init_state,
    load_state,
    save_state,
    state_to_dict,
)


@pytest.fixture
def patched_state_path(tmp_path: Path, monkeypatch):
    """Patch DEFAULT_STATE_PATH to a temp file so tests don't touch real data."""
    tmp_file = tmp_path / "tournament_state.json"
    import scoutfootball.worldcup.tournament as tour_module

    monkeypatch.setattr(tour_module, "DEFAULT_STATE_PATH", str(tmp_file))
    return tmp_file


# ── Export tests ──────────────────────────────────────────────────────


class TestExportWcTournamentState:
    def test_export_returns_ok_status(self, patched_state_path):
        result = export_wc_tournament_state()
        assert result["status"] == "ok"

    def test_export_has_required_fields(self, patched_state_path):
        result = export_wc_tournament_state()
        assert "format" in result
        assert "schema_version" in result
        assert "state_size" in result
        assert "encoded" in result
        assert "exported_at" in result

    def test_export_format_is_base64url(self, patched_state_path):
        result = export_wc_tournament_state()
        assert result["format"] == "base64url-json-v1"

    def test_export_encoded_is_valid_base64url(self, patched_state_path):
        result = export_wc_tournament_state()
        encoded = result["encoded"]
        # Should be decodable as URL-safe base64
        padded = encoded + "=" * (4 - len(encoded) % 4) if len(encoded) % 4 else encoded
        decoded = base64.urlsafe_b64decode(padded)
        data = json.loads(decoded.decode("utf-8"))
        assert isinstance(data, dict)
        assert "matches" in data
        assert "results" in data

    def test_export_schema_version_matches_state(self, patched_state_path):
        result = export_wc_tournament_state()
        state = load_state()
        assert result["schema_version"] == state.schema_version

    def test_export_state_size_matches_json(self, patched_state_path):
        result = export_wc_tournament_state()
        encoded = result["encoded"]
        padded = encoded + "=" * (4 - len(encoded) % 4) if len(encoded) % 4 else encoded
        decoded_bytes = base64.urlsafe_b64decode(padded)
        assert result["state_size"] == len(decoded_bytes)

    def test_export_contains_matches(self, patched_state_path):
        result = export_wc_tournament_state()
        encoded = result["encoded"]
        padded = encoded + "=" * (4 - len(encoded) % 4) if len(encoded) % 4 else encoded
        data = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        # Fresh state has 72 group matches
        assert len(data["matches"]) == 72

    def test_export_with_results(self, patched_state_path):
        """Export should capture applied results."""
        state = load_state()
        first_match_id = state.matches[0]["match_id"]
        apply_result(state, first_match_id, 2, 1)
        save_state(state, patched_state_path)

        result = export_wc_tournament_state()
        encoded = result["encoded"]
        padded = encoded + "=" * (4 - len(encoded) % 4) if len(encoded) % 4 else encoded
        data = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        assert first_match_id in data["results"]

    def test_export_with_knockout(self, patched_state_path):
        """Export should capture knockout bracket."""
        state = load_state()
        # Complete all group matches to allow bracket generation
        for m in state.matches:
            g = m.get("group", "")
            if g and g not in ("r32", "r16", "qf", "sf", "final"):
                apply_result(state, m["match_id"], 1, 0)
        state.knockout = generate_knockout_bracket(state)
        save_state(state, patched_state_path)

        result = export_wc_tournament_state()
        encoded = result["encoded"]
        padded = encoded + "=" * (4 - len(encoded) % 4) if len(encoded) % 4 else encoded
        data = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        assert "knockout" in data
        assert data["knockout"]


# ── Import tests ──────────────────────────────────────────────────────


class TestImportWcTournamentState:
    def test_preview_reports_differences_without_writing_local_state(self, patched_state_path):
        current = load_state()
        current_match_id = current.matches[0]["match_id"]
        apply_result(current, current_match_id, 1, 0)
        save_state(current, patched_state_path)

        incoming = init_state()
        incoming_match_id = incoming.matches[1]["match_id"]
        apply_result(incoming, incoming_match_id, 2, 0)
        encoded = base64.urlsafe_b64encode(
            json.dumps(state_to_dict(incoming)).encode("utf-8")
        ).decode("ascii")

        preview = preview_wc_tournament_import(encoded)

        assert preview["status"] == "ok"
        assert preview["requires_confirmation"] is True
        assert preview["differences"]["group_results_added"] == 1
        assert preview["differences"]["group_results_removed"] == 1
        assert current_match_id in load_state().results

    def test_preview_reports_all_integrity_issues_without_writing_local_state(
        self, patched_state_path
    ):
        current = load_state()
        current_match_id = current.matches[0]["match_id"]
        apply_result(current, current_match_id, 1, 0)
        save_state(current, patched_state_path)

        incoming = state_to_dict(init_state())
        incoming["matches"][0]["home"] = "Altered Team"
        incoming["results"] = {
            "unknown-match": {"home_goals": 1, "away_goals": 0},
            incoming["matches"][1]["match_id"]: {"home_goals": True, "away_goals": -1},
        }
        incoming["knockout"] = {"matches": [{
            "match_id": "r32-01", "home": "Argentina", "away": "France",
            "winner": "Unknown XI", "status": "completed", "home_goals": 1,
            "away_goals": 0,
        }]}
        encoded = base64.urlsafe_b64encode(json.dumps(incoming).encode("utf-8")).decode("ascii")

        preview = preview_wc_tournament_import(encoded)
        import_result = import_wc_tournament_state(encoded)

        assert preview["status"] == "error"
        assert preview["code"] == "integrity_failed"
        assert preview["integrity_errors"]
        assert any("altered home" in issue for issue in preview["integrity_errors"])
        assert any("unknown match" in issue for issue in preview["integrity_errors"])
        assert any("invalid home_goals" in issue for issue in preview["integrity_errors"])
        assert any("not a fixture participant" in issue for issue in preview["integrity_errors"])
        assert import_result["code"] == "integrity_failed"
        assert load_state().results == {
            current_match_id: {
                "home_goals": 1,
                "away_goals": 0,
                "status": "completed",
            }
        }
    def test_import_round_trip(self, patched_state_path):
        """Export → import should reproduce the same state."""
        # Apply some results to make the state non-trivial
        state = load_state()
        first_match_id = state.matches[0]["match_id"]
        apply_result(state, first_match_id, 3, 0)
        save_state(state, patched_state_path)

        # Export
        export_result = export_wc_tournament_state()
        encoded = export_result["encoded"]

        # Clear the state file
        patched_state_path.unlink()

        # Import
        import_result = import_wc_tournament_state(encoded)
        assert import_result["status"] == "ok"
        assert import_result["imported"] is True

        # Verify the state was restored
        loaded = load_state()
        assert first_match_id in loaded.results

    def test_import_persists_to_disk(self, patched_state_path):
        """Import should save state to the default path."""
        export_result = export_wc_tournament_state()
        encoded = export_result["encoded"]

        # Ensure file doesn't exist
        if patched_state_path.exists():
            patched_state_path.unlink()

        import_result = import_wc_tournament_state(encoded)
        assert import_result["status"] == "ok"
        assert patched_state_path.exists()

    def test_import_returns_match_count(self, patched_state_path):
        export_result = export_wc_tournament_state()
        import_result = import_wc_tournament_state(export_result["encoded"])
        assert import_result["status"] == "ok"
        assert import_result["matches"] == 72

    def test_import_returns_schema_version(self, patched_state_path):
        export_result = export_wc_tournament_state()
        import_result = import_wc_tournament_state(export_result["encoded"])
        assert import_result["schema_version"].startswith("1.")

    def test_import_invalid_base64_returns_error(self, patched_state_path):
        result = import_wc_tournament_state("!!!not-valid-base64!!!")
        assert result["status"] == "error"
        assert result["code"] == "decode_failed"

    def test_import_invalid_json_returns_error(self, patched_state_path):
        # Valid base64 but not valid JSON
        bad_json = base64.urlsafe_b64encode(b"not json").decode("ascii")
        result = import_wc_tournament_state(bad_json)
        assert result["status"] == "error"
        assert result["code"] == "decode_failed"

    def test_import_incompatible_schema_returns_error(self, patched_state_path):
        """Import should reject states with unsupported schema versions."""
        state = init_state()
        state_dict = state_to_dict(state)
        state_dict["schema_version"] = "2.0.0"
        encoded = base64.urlsafe_b64encode(
            json.dumps(state_dict).encode("utf-8")
        ).decode("ascii")

        result = import_wc_tournament_state(encoded)
        assert result["status"] == "error"
        assert result["code"] == "invalid_state"

    def test_import_empty_string_returns_error(self, patched_state_path):
        result = import_wc_tournament_state("")
        assert result["status"] == "error"
        assert result["code"] == "decode_failed"

    def test_import_with_knockout_round_trip(self, patched_state_path):
        """Export → import should preserve knockout bracket."""
        state = load_state()
        # Complete all group matches
        for m in state.matches:
            g = m.get("group", "")
            if g and g not in ("r32", "r16", "qf", "sf", "final"):
                apply_result(state, m["match_id"], 1, 0)
        state.knockout = generate_knockout_bracket(state)
        save_state(state, patched_state_path)

        export_result = export_wc_tournament_state()
        encoded = export_result["encoded"]

        # Clear and re-import
        patched_state_path.unlink()
        import_result = import_wc_tournament_state(encoded)
        assert import_result["status"] == "ok"
        assert import_result["has_knockout"] is True

        loaded = load_state()
        assert loaded.knockout

    def test_import_without_padding(self, patched_state_path):
        """Import should handle base64 strings without padding."""
        export_result = export_wc_tournament_state()
        encoded = export_result["encoded"]
        # Strip any padding
        encoded_no_pad = encoded.rstrip("=")

        if patched_state_path.exists():
            patched_state_path.unlink()

        result = import_wc_tournament_state(encoded_no_pad)
        assert result["status"] == "ok"

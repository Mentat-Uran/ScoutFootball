"""Tests for the I1 adapter admission matrix.

The matrix must not turn a merely importable adapter into an admitted workflow
input.  Its source-license fields are derived from the raw-data contract
registry rather than copied into adapter manifests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scoutfootball.adapters.compatibility import (
    AdapterAdmissionStatus,
    build_adapter_compatibility_matrix,
)
from scoutfootball.adapters.registry import build_adapter_registry
from scoutfootball.api import get_adapter_compatibility_matrix

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CLI_MAIN = _PROJECT_ROOT / "src" / "scoutfootball" / "__main__.py"
_ARCHITECTURE_PY = _PROJECT_ROOT / "src" / "scoutfootball" / "architecture.py"
_API_SERVER_PY = _PROJECT_ROOT / "src" / "scoutfootball" / "api_server.py"


class TestAdapterCompatibilityMatrix:
    def test_has_exactly_one_entry_for_each_registered_adapter(self) -> None:
        matrix = build_adapter_compatibility_matrix()
        assert {entry.source_id for entry in matrix.entries} == {
            manifest.source_id for manifest in build_adapter_registry().manifests
        }
        assert len(matrix.entries) == len({entry.source_id for entry in matrix.entries})

    def test_maintained_adapters_require_and_receive_contract_admission(self) -> None:
        matrix = build_adapter_compatibility_matrix()
        maintained = [entry for entry in matrix.entries if entry.maintained]

        assert maintained
        for entry in maintained:
            assert entry.admission_status == AdapterAdmissionStatus.ADMITTED_LOCAL
            assert entry.admitted_for_current_local_workflow is True
            assert entry.contract_registered is True
            assert entry.license_name
            assert entry.attribution_required is not None
            assert entry.redistribution_allowed is not None

    def test_experimental_adapters_are_blocked_even_when_they_have_a_cli_hint(self) -> None:
        matrix = build_adapter_compatibility_matrix()
        experimental = [entry for entry in matrix.entries if not entry.maintained]

        assert experimental
        for entry in experimental:
            assert entry.admission_status == AdapterAdmissionStatus.BLOCKED_EXPERIMENTAL
            assert entry.admitted_for_current_local_workflow is False
            assert entry.contract_registered is False
            assert entry.license_name == ""
            assert entry.redistribution_allowed is None
            assert any("not admit" in reason.lower() for reason in entry.reasons)

    def test_missing_contract_fails_closed_for_a_maintained_adapter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import scoutfootball.adapters.compatibility as compatibility

        monkeypatch.setattr(compatibility, "_raw_source_licenses", lambda: {})
        matrix = compatibility.build_adapter_compatibility_matrix()

        for entry in matrix.entries:
            if entry.maintained:
                assert entry.admission_status == AdapterAdmissionStatus.BLOCKED_MISSING_CONTRACT
                assert entry.admitted_for_current_local_workflow is False

    def test_json_dump_contains_only_json_safe_values(self) -> None:
        payload = build_adapter_compatibility_matrix().model_dump(mode="json")
        json.dumps(payload)


class TestAdapterCompatibilityApi:
    def test_api_matches_matrix_source_ids_and_statuses(self) -> None:
        expected = build_adapter_compatibility_matrix()
        actual = get_adapter_compatibility_matrix()

        assert actual["package_version"] == expected.package_version
        assert {
            (entry["source_id"], entry["admission_status"])
            for entry in actual["entries"]
        } == {
            (entry.source_id, entry.admission_status.value)
            for entry in expected.entries
        }

    def test_fastapi_route_returns_the_matrix(self) -> None:
        from fastapi.testclient import TestClient

        from scoutfootball.api_server import app

        response = TestClient(app).get("/adapters/compatibility")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["entries"]) == len(build_adapter_registry().manifests)
        assert {entry["admission_status"] for entry in payload["entries"]} == {
            "admitted_local",
            "blocked_experimental",
        }


class TestAdapterCompatibilityCli:
    def _run(self, *argv: str, capsys: pytest.CaptureFixture[str]) -> str:
        from scoutfootball.__main__ import main

        old_argv = sys.argv
        sys.argv = ["scoutfootball", "adapter-compatibility", *argv]
        try:
            main()
        finally:
            sys.argv = old_argv
        return capsys.readouterr().out

    def test_default_output_states_project_local_boundary(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        output = self._run(capsys=capsys)

        assert "project-local" in output
        assert "[statsbomb_open] admitted_local" in output
        assert "[whoscored] blocked_experimental" in output

    def test_source_filter_and_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = self._run("--source", "reep", "--json", capsys=capsys)
        payload = json.loads(output)

        assert [entry["source_id"] for entry in payload["entries"]] == ["reep"]
        assert payload["entries"][0]["admission_status"] == "admitted_local"

    def test_unknown_source_exits_nonzero(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            self._run("--source", "unknown", capsys=capsys)
        assert exc_info.value.code == 1
        assert "No adapter compatibility entry" in capsys.readouterr().out


class TestAdapterCompatibilitySurfaceRegistration:
    def test_command_and_api_route_are_registered_in_architecture(self) -> None:
        architecture = _ARCHITECTURE_PY.read_text(encoding="utf-8")
        assert "adapter-compatibility" in architecture
        assert '"/adapters/compatibility"' in architecture

    def test_cli_and_api_server_register_the_surface(self) -> None:
        assert '"adapter-compatibility"' in _CLI_MAIN.read_text(encoding="utf-8")
        assert '"/adapters/compatibility"' in _API_SERVER_PY.read_text(encoding="utf-8")

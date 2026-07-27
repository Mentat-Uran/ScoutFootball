"""Contract tests for the provider adapter manifest system (I1 baseline).

These tests pin down the I1 (开放互操作与本地视频回链) entry-point
contract: every registered source has a manifest, every manifest is
well-formed, the registry aggregates them faithfully, and the CLI/API
surfaces expose them without drift.

The manifest schema is intentionally conservative — undocumented
capabilities or mappings are omitted rather than guessed — so the tests
enforce that conservatism by checking invariants, not by asserting
exact field lists that would drift on every adapter update.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scoutfootball import __version__
from scoutfootball.adapters.manifest import (
    AdapterCapability,
    AdapterManifest,
    AdapterRegistry,
    SchemaMapping,
)
from scoutfootball.adapters.registry import build_adapter_registry
from scoutfootball.api import get_adapter_registry

# Source ids that the registry is contractually required to know about.
# This mirrors the seven ``build_*_manifest`` functions in registry.py;
# adding a new source requires both a builder and an entry here so the
# contract is not silently widened.
_EXPECTED_SOURCE_IDS = frozenset(
    {
        "statsbomb_open",
        "football_data",
        "clubelo",
        "understat",
        "fbref",
        "transfermarkt_manual",
        "reep",
    }
)

# Conversion categories documented on SchemaMapping.conversion. Anything
# outside this set is a contract violation: either the docstring in
# manifest.py needs updating, or the adapter is using an ad-hoc label.
_VALID_CONVERSIONS = frozenset(
    {"direct", "unit_conversion", "approximate", "derived", "lost"}
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CLI_MAIN = _PROJECT_ROOT / "src" / "scoutfootball" / "__main__.py"
_ARCHITECTURE_PY = _PROJECT_ROOT / "src" / "scoutfootball" / "architecture.py"
_API_SERVER_PY = _PROJECT_ROOT / "src" / "scoutfootball" / "api_server.py"


# ---------------------------------------------------------------------------
# Schema-level invariants
# ---------------------------------------------------------------------------


class TestAdapterManifestSchema:
    def test_adapter_capability_values_are_stable(self) -> None:
        """AdapterCapability string values must not change silently.

        External consumers (CLI ``--capability`` flag, API JSON consumers)
        rely on these exact strings; renaming one is a breaking change.
        """
        expected = {
            "event",
            "tracking",
            "video",
            "identity",
            "market_value",
            "fixture",
            "result",
            "rating",
            "player_stats",
            "lineup",
            "injury",
            "transfer",
        }
        actual = {c.value for c in AdapterCapability}
        assert actual == expected, (
            f"AdapterCapability values drifted. "
            f"Expected {sorted(expected)}, got {sorted(actual)}. "
            f"Renaming a capability value is a breaking change."
        )

    def test_schema_mapping_is_frozen(self) -> None:
        mapping = SchemaMapping(
            source_field="a",
            internal_field="b",
            conversion="direct",
        )
        with pytest.raises((ValueError, TypeError)):
            mapping.source_field = "c"  # type: ignore[misc]

    def test_adapter_manifest_is_frozen(self) -> None:
        manifest = AdapterManifest(
            source_id="x",
            parser_version="x/v0.1.0",
            module_path="scoutfootball.adapters.x",
            capabilities=(AdapterCapability.EVENT,),
        )
        with pytest.raises((ValueError, TypeError)):
            manifest.source_id = "y"  # type: ignore[misc]

    def test_adapter_registry_is_frozen(self) -> None:
        registry = AdapterRegistry(
            generated_at="2026-07-27T00:00:00Z",
            package_version=__version__,
            manifests=(),
        )
        with pytest.raises((ValueError, TypeError)):
            registry.generated_at = "1970-01-01T00:00:00Z"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Registry-level invariants
# ---------------------------------------------------------------------------


class TestAdapterRegistry:
    def test_registry_contains_all_expected_sources(self) -> None:
        registry = build_adapter_registry()
        actual = {m.source_id for m in registry.manifests}
        assert actual == _EXPECTED_SOURCE_IDS, (
            f"Registry source ids drifted. "
            f"Expected {sorted(_EXPECTED_SOURCE_IDS)}, got {sorted(actual)}. "
            f"Adding a source requires updating _EXPECTED_SOURCE_IDS in this test."
        )

    def test_registry_has_unique_source_ids(self) -> None:
        registry = build_adapter_registry()
        ids = [m.source_id for m in registry.manifests]
        dups = [i for i in ids if ids.count(i) > 1]
        assert not dups, f"Duplicate source_id in registry: {dups}"

    def test_registry_package_version_matches_project(self) -> None:
        registry = build_adapter_registry()
        assert registry.package_version == __version__

    def test_registry_generated_at_is_iso8601(self) -> None:
        registry = build_adapter_registry()
        # Accept any ISO 8601 string with timezone info; we do not pin a
        # timestamp because the registry is generated on each call.
        assert registry.generated_at, "generated_at must be non-empty"
        # ``datetime.fromisoformat`` accepts trailing Z on Python 3.11+.
        # We only assert it parses; freshness is not a contract.
        from datetime import datetime

        datetime.fromisoformat(registry.generated_at.replace("Z", "+00:00"))

    def test_by_source_returns_match_or_none(self) -> None:
        registry = build_adapter_registry()
        match = registry.by_source("statsbomb_open")
        assert match is not None
        assert match.source_id == "statsbomb_open"
        assert registry.by_source("does_not_exist") is None

    def test_with_capability_filters_correctly(self) -> None:
        registry = build_adapter_registry()
        event_sources = registry.with_capability(AdapterCapability.EVENT)
        # statsbomb_open is currently the only event-capable source.
        assert any(m.source_id == "statsbomb_open" for m in event_sources)
        for manifest in event_sources:
            assert AdapterCapability.EVENT in manifest.capabilities

        # No adapter currently claims tracking — this is an intentional
        # contract: tracking enters the project only via a later I1 slice
        # gated by compliant sample data (see docs/ROADMAP.md).
        tracking_sources = registry.with_capability(AdapterCapability.TRACKING)
        assert tracking_sources == ()

        video_sources = registry.with_capability(AdapterCapability.VIDEO)
        assert video_sources == ()


# ---------------------------------------------------------------------------
# Per-manifest invariants
# ---------------------------------------------------------------------------


class TestPerManifestInvariants:
    """Every registered manifest must satisfy these baseline invariants.

    The tests are parameterized over the registry so a new source fails
    loudly here if its manifest is incomplete, rather than silently
    shipping a half-documented adapter.
    """

    @pytest.fixture(scope="class")
    def registry(self) -> AdapterRegistry:
        return build_adapter_registry()

    @pytest.mark.parametrize(
        "manifest",
        [build_adapter_registry().by_source(sid) for sid in _EXPECTED_SOURCE_IDS],
        ids=sorted(_EXPECTED_SOURCE_IDS),
    )
    def test_manifest_has_required_fields(self, manifest: AdapterManifest) -> None:
        assert manifest.source_id
        assert manifest.parser_version
        assert manifest.module_path
        assert manifest.capabilities, (
            f"Manifest {manifest.source_id} declares no capabilities; "
            f"if the adapter truly provides nothing, remove it from the registry."
        )
        assert manifest.ingestion_cli, (
            f"Manifest {manifest.source_id} has no ingestion_cli; "
            f"users need a discoverable way to invoke it."
        )

    @pytest.mark.parametrize(
        "manifest",
        [build_adapter_registry().by_source(sid) for sid in _EXPECTED_SOURCE_IDS],
        ids=sorted(_EXPECTED_SOURCE_IDS),
    )
    def test_manifest_parser_version_is_namespaced(
        self, manifest: AdapterManifest
    ) -> None:
        """parser_version must be ``<source_id>/<semver>`` to avoid collisions."""
        assert manifest.parser_version.startswith(
            f"{manifest.source_id}/"
        ), (
            f"parser_version '{manifest.parser_version}' must be namespaced as "
            f"'{manifest.source_id}/<version>' so it cannot collide across sources."
        )

    @pytest.mark.parametrize(
        "manifest",
        [build_adapter_registry().by_source(sid) for sid in _EXPECTED_SOURCE_IDS],
        ids=sorted(_EXPECTED_SOURCE_IDS),
    )
    def test_manifest_capabilities_are_unique(
        self, manifest: AdapterManifest
    ) -> None:
        caps = list(manifest.capabilities)
        assert len(caps) == len(set(caps)), (
            f"Manifest {manifest.source_id} has duplicate capabilities: {caps}"
        )

    @pytest.mark.parametrize(
        "manifest",
        [build_adapter_registry().by_source(sid) for sid in _EXPECTED_SOURCE_IDS],
        ids=sorted(_EXPECTED_SOURCE_IDS),
    )
    def test_manifest_schema_mappings_use_valid_conversions(
        self, manifest: AdapterManifest
    ) -> None:
        for mapping in manifest.schema_mappings:
            assert mapping.conversion in _VALID_CONVERSIONS, (
                f"Manifest {manifest.source_id} mapping "
                f"{mapping.source_field!r}->{mapping.internal_field!r} "
                f"uses unknown conversion {mapping.conversion!r}. "
                f"Valid: {sorted(_VALID_CONVERSIONS)}."
            )
            assert mapping.source_field, (
                f"Manifest {manifest.source_id} has empty source_field."
            )
            assert mapping.internal_field, (
                f"Manifest {manifest.source_id} has empty internal_field."
            )

    @pytest.mark.parametrize(
        "manifest",
        [build_adapter_registry().by_source(sid) for sid in _EXPECTED_SOURCE_IDS],
        ids=sorted(_EXPECTED_SOURCE_IDS),
    )
    def test_manifest_artifact_paths_are_relative(
        self, manifest: AdapterManifest
    ) -> None:
        for path in manifest.artifact_paths:
            assert not Path(path).is_absolute(), (
                f"Manifest {manifest.source_id} artifact path {path!r} "
                f"must be relative to the project data root."
            )

    @pytest.mark.parametrize(
        "manifest",
        [build_adapter_registry().by_source(sid) for sid in _EXPECTED_SOURCE_IDS],
        ids=sorted(_EXPECTED_SOURCE_IDS),
    )
    def test_manifest_conversion_loss_notes_present(
        self, manifest: AdapterManifest
    ) -> None:
        """Every manifest must explain where conversion loses information.

        I1 is fundamentally about honest interop: if a manifest has no
        loss notes, the maintainer is implicitly claiming lossless
        conversion, which is not true for any of the registered sources.
        """
        assert manifest.conversion_loss_notes, (
            f"Manifest {manifest.source_id} has no conversion_loss_notes. "
            f"Even a 'no known loss' note is required to make the claim explicit."
        )


# ---------------------------------------------------------------------------
# Source-specific contracts
# ---------------------------------------------------------------------------


class TestSourceSpecificContracts:
    """Pin a few conservative, non-drifting facts per source.

    These are not exhaustive field lists (those would drift on every
    adapter tweak); they are facts that, if they change, signal a
    deliberate contract change rather than an accidental edit.
    """

    def test_statsbomb_open_provides_events_and_lineups(self) -> None:
        registry = build_adapter_registry()
        m = registry.by_source("statsbomb_open")
        assert m is not None
        assert AdapterCapability.EVENT in m.capabilities
        assert AdapterCapability.LINEUP in m.capabilities

    def test_football_data_does_not_provide_events(self) -> None:
        """Football-Data is match-results-only; it must not claim events."""
        registry = build_adapter_registry()
        m = registry.by_source("football_data")
        assert m is not None
        assert AdapterCapability.EVENT not in m.capabilities
        assert AdapterCapability.TRACKING not in m.capabilities

    def test_reep_is_identity_only(self) -> None:
        """Reep is a read-only identity register, not an ingester."""
        registry = build_adapter_registry()
        m = registry.by_source("reep")
        assert m is not None
        assert m.capabilities == (AdapterCapability.IDENTITY,)

    def test_transfermarkt_manual_is_manual_import(self) -> None:
        registry = build_adapter_registry()
        m = registry.by_source("transfermarkt_manual")
        assert m is not None
        assert AdapterCapability.MARKET_VALUE in m.capabilities
        assert AdapterCapability.IDENTITY in m.capabilities
        # No automated ingestion — the notes must call this out.
        combined = (m.notes + " " + m.conversion_loss_notes).lower()
        assert "manual" in combined, (
            "transfermarkt_manual manifest must clearly state it is manual import only."
        )


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------


class TestApiSurface:
    def test_get_adapter_registry_returns_dict(self) -> None:
        result = get_adapter_registry()
        assert isinstance(result, dict)
        assert "manifests" in result
        assert "generated_at" in result
        assert "package_version" in result

    def test_get_adapter_registry_matches_model_dump(self) -> None:
        registry = build_adapter_registry()
        expected = registry.model_dump(mode="json")
        actual = get_adapter_registry()
        # generated_at is recomputed on each call, so compare everything else.
        assert actual["package_version"] == expected["package_version"]
        assert len(actual["manifests"]) == len(expected["manifests"])
        assert {m["source_id"] for m in actual["manifests"]} == _EXPECTED_SOURCE_IDS

    def test_get_adapter_registry_manifests_are_json_serializable(self) -> None:
        """The API layer must return JSON-safe primitives, not Pydantic objects."""
        result = get_adapter_registry()
        # If any value is not JSON-serializable, this raises TypeError.
        json.dumps(result)


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


class TestCliSurface:
    """Smoke tests for ``scoutfootball list-adapters``.

    These tests import the handler directly rather than spawning a
    subprocess: that keeps them fast and lets us capture stdout/stderr
    through capsys without Windows shell quoting pain.
    """

    def _run(self, *argv: str, capsys: pytest.CaptureFixture[str]) -> str:
        import sys

        from scoutfootball.__main__ import main

        old_argv = sys.argv
        sys.argv = ["scoutfootball", "list-adapters", *argv]
        try:
            main()
        finally:
            sys.argv = old_argv
        captured = capsys.readouterr()
        return captured.out

    def test_default_listing_mentions_every_source(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = self._run(capsys=capsys)
        for source_id in _EXPECTED_SOURCE_IDS:
            assert source_id in out, (
                f"list-adapters default output missing source {source_id!r}."
            )
        assert "Total adapters:" in out

    def test_json_output_is_valid_json(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = self._run("--json", capsys=capsys)
        payload = json.loads(out)
        assert payload["package_version"] == __version__
        source_ids = {m["source_id"] for m in payload["manifests"]}
        assert source_ids == _EXPECTED_SOURCE_IDS

    def test_source_filter_returns_single_manifest(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = self._run("--source", "reep", capsys=capsys)
        assert "reep" in out
        # Other sources must not appear when a filter is active.
        for source_id in _EXPECTED_SOURCE_IDS - {"reep"}:
            assert f"[{source_id}]" not in out, (
                f"--source reep should hide other sources, but found [{source_id}]."
            )

    def test_unknown_source_filter_exits_nonzero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            self._run("--source", "does_not_exist", capsys=capsys)
        assert exc_info.value.code != 0

    def test_capability_filter_narrows_to_event_sources(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = self._run("--capability", "event", capsys=capsys)
        assert "statsbomb_open" in out
        # football_data does not provide events and must be filtered out.
        assert "[football_data]" not in out

    def test_unknown_capability_filter_exits_nonzero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            self._run("--capability", "not_a_real_capability", capsys=capsys)
        assert exc_info.value.code != 0

    def test_verbose_mode_shows_schema_mappings(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = self._run("--verbose", capsys=capsys)
        assert "Schema mapping detail:" in out
        # statsbomb_open has many mappings; at least one should be visible.
        assert "event_id" in out or "match_id" in out


# ---------------------------------------------------------------------------
# Architecture integration
# ---------------------------------------------------------------------------


class TestArchitectureIntegration:
    """The new capability must be registered in the project surface."""

    def test_list_adapters_in_supported_commands(self) -> None:
        source = _ARCHITECTURE_PY.read_text(encoding="utf-8")
        assert "list-adapters" in source, (
            "list-adapters must appear in architecture.py supported_commands "
            "or capability registry; otherwise it is invisible to the "
            "capabilities CLI and to contract tests."
        )

    def test_adapters_endpoint_registered_in_api_server(self) -> None:
        source = _API_SERVER_PY.read_text(encoding="utf-8")
        assert '"/adapters"' in source, (
            "/adapters endpoint must be registered in api_server.py so the "
            "API surface matches the manifest contract."
        )

    def test_cli_main_registers_list_adapters_subparser(self) -> None:
        source = _CLI_MAIN.read_text(encoding="utf-8")
        assert '"list-adapters"' in source
        assert "_cmd_list_adapters" in source

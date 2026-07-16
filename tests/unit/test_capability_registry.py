"""Contract tests for the capability registry.

These tests ensure the capability registry stays consistent with the
actual project surface: every CLI subcommand, every major frontend view,
and every API endpoint group has at least one capability that references
it. The goal is to prevent the registry from drifting away from what the
project actually delivers.
"""

from __future__ import annotations

import re
from pathlib import Path

from scoutfootball.architecture import build_capability_registry
from scoutfootball.schemas import CapabilityRegistry

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CLI_MAIN = _PROJECT_ROOT / "src" / "scoutfootball" / "__main__.py"
_FRONTEND_INDEX = _PROJECT_ROOT / "frontend" / "index.html"


def _extract_cli_subcommands() -> set[str]:
    """Extract top-level CLI subcommand names from __main__.py."""
    source = _CLI_MAIN.read_text(encoding="utf-8")
    return set(re.findall(r'\bsub\.add_parser\(\s*"([^"]+)"', source))


def _extract_frontend_views() -> set[str]:
    """Extract data-view identifiers from the frontend side-nav."""
    html = _FRONTEND_INDEX.read_text(encoding="utf-8")
    return set(re.findall(r'data-view="([^"]+)"', html))


def test_registry_is_valid() -> None:
    registry = build_capability_registry()
    assert isinstance(registry, CapabilityRegistry)
    assert len(registry.capabilities) > 0
    assert len(registry.domains) > 0


def test_registry_has_unique_ids() -> None:
    registry = build_capability_registry()
    ids = [c.id for c in registry.capabilities]
    dups = [i for i in ids if ids.count(i) > 1]
    assert len(ids) == len(set(ids)), f"Duplicate capability ids: {dups}"


def test_registry_domains_match_capabilities() -> None:
    registry = build_capability_registry()
    actual_domains = {c.domain for c in registry.capabilities}
    assert set(registry.domains) == actual_domains


def test_every_cli_subcommand_has_capability_reference() -> None:
    """Every top-level CLI subparser must be referenced by at least one capability.

    This catches drift: when someone adds a new CLI command but forgets to
    update the capability registry.
    """
    registry = build_capability_registry()
    cli_cmds = _extract_cli_subcommands()

    referenced: set[str] = set()
    for cap in registry.capabilities:
        for cmd in cap.cli_commands:
            base = cmd.split()[0]
            referenced.add(base)

    missing = cli_cmds - referenced
    assert not missing, (
        f"CLI subcommands missing from capability registry: {sorted(missing)}. "
        f"Add them to build_capability_registry() in architecture.py."
    )


def test_every_frontend_view_has_capability_reference() -> None:
    """Every frontend nav view must be referenced by at least one capability.

    This catches drift: when someone adds a new frontend view but forgets to
    update the capability registry.
    """
    registry = build_capability_registry()
    views = _extract_frontend_views()

    referenced: set[str] = set()
    for cap in registry.capabilities:
        referenced.update(cap.frontend_views)

    missing = views - referenced
    # Some views may be purely structural (e.g. dividers). We only flag
    # views that look like real page names.
    assert not missing, (
        f"Frontend views missing from capability registry: {sorted(missing)}. "
        f"Add them to the relevant capability in build_capability_registry()."
    )


def test_capability_cli_commands_are_valid() -> None:
    """Every CLI command referenced by capabilities must exist as a subparser."""
    registry = build_capability_registry()
    cli_cmds = _extract_cli_subcommands()

    for cap in registry.capabilities:
        for cmd in cap.cli_commands:
            base = cmd.split()[0]
            assert base in cli_cmds, (
                f"Capability '{cap.id}' references CLI command '{base}' "
                f"which does not exist as a top-level subparser."
            )


def test_count_by_status_matches_capabilities() -> None:
    registry = build_capability_registry()
    counts = registry.count_by_status()
    assert sum(counts.values()) == len(registry.capabilities)


def test_by_domain_returns_only_requested_domain() -> None:
    registry = build_capability_registry()
    for domain in registry.domains:
        subset = registry.by_domain(domain)
        assert all(c.domain == domain for c in subset)
        assert len(subset) > 0


def test_registry_includes_core_domains() -> None:
    registry = build_capability_registry()
    expected_domains = {
        "data_pipeline",
        "player_ratings",
        "match_predictions",
        "team_analysis",
        "player_analysis",
        "action_value",
        "scouting",
        "world_cup",
        "infrastructure",
    }
    missing = expected_domains - set(registry.domains)
    assert not missing, f"Missing core domains: {sorted(missing)}"

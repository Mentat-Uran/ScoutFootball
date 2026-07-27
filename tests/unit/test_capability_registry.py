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


# ── API route drift gate ──────────────────────────────────────────────

# Route prefixes that are owned by the capability registry.  Routes under
# these prefixes must be declared in some capability's ``api_paths``.
# Expanding this set is a deliberate act: any new route under a covered
# prefix MUST be added to a capability, which is exactly the drift we want
# to catch.  Bare-path entries (e.g. ``/search``, ``/artifacts``) cover the
# exact path and any sub-paths, since FastAPI route paths are finite and
# known.  ``api_paths`` entries may carry a ``(METHOD)`` suffix (e.g.
# ``/path (POST)``) which is stripped before comparison.
_CAPABILITY_ROUTE_PREFIXES = (
    "/recruitment/",
    "/opposition/",
    "/world-cup/",
    "/worldcup/",
    "/predictions/",
    "/teams/",
    "/players",
    "/player/",
    "/positions/",
    "/action-values/",
    "/value-summary",
    "/scouting-workspaces",
    "/scouting/",
    "/watchlist",
    "/shortlist",
    "/review-queue",
    "/search",
    "/local-pack/",
    "/tactical-board/",
    "/health",
    "/license",
    "/artifacts",
    "/model-runs",
    "/reports/",
    "/league/",
    "/ratings",
)

# Suffix pattern for non-GET method annotations in api_paths, e.g.
# "/path (POST)" or "/path (POST/DELETE)".  These are normalized away before
# comparing against FastAPI route paths, which carry method info on the
# route object rather than in the path string.
_METHOD_SUFFIX_RE = re.compile(r"\s*\([A-Z/]+\)\s*$")


def _normalize_api_path(path: str) -> str:
    """Strip the ``(METHOD)`` suffix from an api_path for route comparison."""
    return _METHOD_SUFFIX_RE.sub("", path)


def _extract_fastapi_paths() -> set[str]:
    """Return the set of route paths declared on the FastAPI app."""
    from scoutfootball.api_server import create_app

    app = create_app()
    paths: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if isinstance(path, str) and path:
            paths.add(path)
    return paths


def _capability_api_paths() -> set[str]:
    """Return every api_path declared across all capabilities."""
    registry = build_capability_registry()
    paths: set[str] = set()
    for cap in registry.capabilities:
        paths.update(cap.api_paths)
    return paths


def _normalized_capability_api_paths() -> set[str]:
    """Return every api_path with ``(METHOD)`` suffixes stripped."""
    return {_normalize_api_path(p) for p in _capability_api_paths()}


def test_capability_api_paths_exist_as_routes() -> None:
    """Every capability api_path must be a real FastAPI route.

    Catches drift where someone declares a path in the capability registry
    but never wires it in ``api_server.py`` (or renames the route and forgets
    to update the registry).  Covers all capability-managed prefixes.
    ``api_paths`` entries may carry a ``(METHOD)`` suffix (e.g.
    ``/path (POST)``) which is stripped before comparison.
    """
    registered = {
        p for p in _normalized_capability_api_paths()
        if any(p.startswith(prefix) for prefix in _CAPABILITY_ROUTE_PREFIXES)
    }
    actual = _extract_fastapi_paths()
    missing = registered - actual
    assert not missing, (
        f"Capability api_paths not found as FastAPI routes: {sorted(missing)}. "
        f"Either wire the route in api_server.py or remove the stale path "
        f"from architecture.py."
    )


def test_capability_managed_routes_are_registered() -> None:
    """Every route under capability-managed prefixes must be in the registry.

    Catches drift where someone adds a new API endpoint in ``api_server.py``
    but forgets to declare it in the capability registry's ``api_paths``.
    Covers all prefixes listed in ``_CAPABILITY_ROUTE_PREFIXES``.
    """
    actual = {
        p for p in _extract_fastapi_paths()
        if any(p.startswith(prefix) for prefix in _CAPABILITY_ROUTE_PREFIXES)
    }
    registered = {
        p for p in _normalized_capability_api_paths()
        if any(p.startswith(prefix) for prefix in _CAPABILITY_ROUTE_PREFIXES)
    }
    missing = actual - registered
    assert not missing, (
        f"FastAPI routes under capability-managed prefixes missing from "
        f"capability registry api_paths: {sorted(missing)}. "
        f"Add them to the relevant capability in build_capability_registry()."
    )

"""Tests for architecture.py supported_commands consistency with CLI subparsers.

The supported_commands tuple in architecture.py is printed by `scoutfootball info`
and serves as the user-facing command manifest. It must stay in sync with the
actual subparsers registered in __main__.py. This test prevents drift where new
CLI commands are added to __main__.py but not to architecture.py (or vice versa).
"""

from __future__ import annotations

from scoutfootball.architecture import build_default_architecture


def _extract_cli_subcommands() -> set[str]:
    """Extract the set of scoutfootball subcommand names from __main__.py.

    We parse the argparse subparser registrations by inspecting the source,
    since importing __main__ and constructing the parser has side effects
    (e.g. importing heavy modules at collection time).
    """
    import re
    from pathlib import Path

    main_path = Path(__file__).resolve().parents[2] / "src" / "scoutfootball" / "__main__.py"
    source = main_path.read_text(encoding="utf-8")
    # Match only top-level subparsers: `sub.add_parser("info", ...)`.
    # Nested subparsers use different variable names (tour_sub, tour_ko_sub, etc.)
    # and should not be in supported_commands as standalone commands.
    pattern = r'\bsub\.add_parser\(\s*"([^"]+)"'
    return set(re.findall(pattern, source))


def _extract_supported_scoutfootball_commands() -> set[str]:
    """Extract scoutfootball subcommand names from supported_commands.

    supported_commands contains both `scoutfootball` subcommands and external
    tool commands (uv sync, pytest, ruff, streamlit). We only extract the
    scoutfootball ones.
    """
    arch = build_default_architecture()
    result: set[str] = set()
    for cmd in arch.supported_commands:
        # Match "uv run python -m scoutfootball <subcommand>"
        prefix = "uv run python -m scoutfootball "
        if cmd.startswith(prefix):
            subcommand = cmd[len(prefix):].strip()
            # Skip subcommands with arguments (e.g. "tournament show")
            parts = subcommand.split()
            if parts:
                result.add(parts[0])
    return result


def test_supported_commands_covers_all_cli_subparsers():
    """Every subparser in __main__.py must appear in supported_commands."""
    cli_subcommands = _extract_cli_subcommands()
    supported = _extract_supported_scoutfootball_commands()
    missing = cli_subcommands - supported
    assert not missing, (
        f"CLI subparsers missing from architecture.supported_commands: {sorted(missing)}.\n"
        f"Add them to build_default_architecture() in architecture.py."
    )


def test_supported_commands_has_no_phantom_subcommands():
    """Every scoutfootball command in supported_commands must have a real subparser."""
    cli_subcommands = _extract_cli_subcommands()
    supported = _extract_supported_scoutfootball_commands()
    phantom = supported - cli_subcommands
    assert not phantom, (
        f"supported_commands references non-existent CLI subcommands: {sorted(phantom)}.\n"
        f"Remove them from build_default_architecture() in architecture.py."
    )


def test_supported_commands_includes_core_commands():
    """Core pipeline commands must always be present."""
    supported = _extract_supported_scoutfootball_commands()
    core = {"info", "ingest", "build-features", "train", "validate", "preflight", "serve"}
    missing = core - supported
    assert not missing, f"Core commands missing from supported_commands: {sorted(missing)}"

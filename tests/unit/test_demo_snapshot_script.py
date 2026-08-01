"""Static analysis tests for scripts/demo_snapshot/export_worldcup_demo_snapshot.py.

Verifies that the demo snapshot script:
- Exists and is valid Python
- Exposes the expected CLI interface (--check, --output)
- Strips volatile timestamp keys for reproducible checksums
- References the Core DataContract registry endpoint
- Writes a manifest with per-file SHA-256 hashes
"""

from __future__ import annotations

import ast
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "demo_snapshot"
    / "export_worldcup_demo_snapshot.py"
)


def _read_source() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def _parse_ast() -> ast.Module:
    return ast.parse(_read_source(), filename=str(SCRIPT_PATH))


def test_script_exists():
    assert SCRIPT_PATH.exists(), f"Script not found at {SCRIPT_PATH}"


def test_script_is_valid_python():
    """The script must parse without syntax errors."""
    _parse_ast()  # raises SyntaxError if invalid


def test_has_check_flag():
    """The script must support --check for reproducibility verification."""
    content = _read_source()
    assert '"--check"' in content or "'--check'" in content
    assert "check_snapshot" in content


def test_has_output_flag():
    """The script must support --output for custom output directories."""
    content = _read_source()
    assert '"--output"' in content or "'--output'" in content


def test_strips_volatile_timestamps():
    """The script must strip volatile timestamp keys before hashing."""
    content = _read_source()
    assert "_VOLATILE_KEYS" in content
    assert "generated_at" in content
    assert "recorded_at" in content
    assert "_strip_volatile" in content


def test_references_core_contract_registry():
    """The script must call get_wc_contracts to export the registry."""
    content = _read_source()
    assert "get_wc_contracts" in content


def test_writes_manifest_with_sha256():
    """The script must write a manifest with per-file SHA-256 hashes."""
    content = _read_source()
    assert "manifest" in content.lower()
    assert "sha256" in content.lower()
    assert "hashlib" in content


def test_writes_readme():
    """The script must write a human-readable README."""
    content = _read_source()
    assert "README.md" in content
    assert "_write_readme" in content


def test_collect_artifacts_calls_multiple_endpoints():
    """The script must export multiple World Cup artifacts, not just one."""
    content = _read_source()
    # At minimum: contracts, schedule, teams, groups, predictions, tournament_summary
    for endpoint in (
        "get_wc_contracts",
        "get_wc_schedule",
        "get_wc_teams",
        "get_wc_groups",
        "get_wc_predictions",
        "get_wc_tournament_summary",
    ):
        assert endpoint in content, f"Missing endpoint: {endpoint}"


def test_main_returns_exit_code():
    """main() must return an int exit code for shell integration."""
    tree = _parse_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            # Must have a return statement (exit code).
            has_return = any(
                isinstance(child, ast.Return)
                for child in ast.walk(node)
            )
            assert has_return, "main() must return an exit code"
            return
    raise AssertionError("main() function not found")


def test_check_mode_returns_nonzero_on_drift():
    """check_snapshot() must return 1 on drift, 0 on match."""
    content = _read_source()
    assert "return 1" in content
    assert "return 0" in content
    assert "DRIFT DETECTED" in content

"""Integration tests for ScoutFootball CLI pipeline commands."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _PROJECT_ROOT / "src"
_RUN_MUTATING_PIPELINE_TESTS = os.environ.get("SCOUTFOOTBALL_RUN_MUTATING_PIPELINE_TESTS") == "1"


def _run_cli(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a scoutfootball CLI command via subprocess with PYTHONPATH set."""
    env = os.environ.copy()
    # Prepend src/ to PYTHONPATH so the package is importable
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{_SRC_DIR}{os.pathsep}{existing}" if existing else str(_SRC_DIR)
    cmd = [sys.executable, "-m", "scoutfootball", *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def test_info_command():
    """scoutfootball info should exit 0 and print package info."""
    result = _run_cli("info")
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "package:" in result.stdout


def test_validate_command():
    """scoutfootball validate should exit 0 and print a summary."""
    result = _run_cli("validate", timeout=180)
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


@pytest.mark.skipif(
    not _RUN_MUTATING_PIPELINE_TESTS,
    reason=(
        "requires SCOUTFOOTBALL_RUN_MUTATING_PIPELINE_TESTS=1 because it writes "
        "feature artifacts to the configured local data root"
    ),
)
def test_build_features_produces_output():
    """scoutfootball build-features should exit 0 and mention feature sets."""
    result = _run_cli("build-features", timeout=300)
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


@pytest.mark.slow
@pytest.mark.skipif(
    not _RUN_MUTATING_PIPELINE_TESTS,
    reason=(
        "requires SCOUTFOOTBALL_RUN_MUTATING_PIPELINE_TESTS=1 because it runs the "
        "real training pipeline against the configured local data root"
    ),
)
def test_train_command():
    """Explicitly run the real training pipeline against configured local data.

    This remains a slow integration check, but it is intentionally excluded
    from normal test runs because training can take minutes and write model or
    feature artifacts. Run only after choosing the intended data root:
    ``$env:SCOUTFOOTBALL_RUN_MUTATING_PIPELINE_TESTS='1'; uv run pytest -m slow``.
    """
    result = _run_cli("train", timeout=600)
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

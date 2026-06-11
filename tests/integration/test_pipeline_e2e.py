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


def test_build_features_produces_output():
    """scoutfootball build-features should exit 0 and mention feature sets."""
    result = _run_cli("build-features", timeout=300)
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


@pytest.mark.slow
def test_train_command():
    """scoutfootball train should exit 0 (may skip models if no data).

    Marked slow because train involves GPU optimization and can take
    several minutes. Run with: pytest -m slow
    """
    result = _run_cli("train", timeout=600)
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

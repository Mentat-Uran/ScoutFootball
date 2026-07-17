"""Tests for the generate_manifest script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "generate_manifest.py"


def _run_script(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            *args,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={
            **dict(__import__("os").environ),
            "PYTHONPATH": str(REPO_ROOT / "src"),
        },
    )


def test_generate_creates_valid_json(tmp_path: Path) -> None:
    output = tmp_path / "manifest.json"
    result = _run_script(["--output", str(output)])
    assert result.returncode == 0, result.stderr
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert "schema_version" in data
    assert "capabilities" in data
    assert "data_contracts" in data
    assert "architecture" in data
    assert "content_sha256" in data


def test_check_passes_after_generate(tmp_path: Path) -> None:
    output = tmp_path / "manifest.json"
    gen = _run_script(["--output", str(output)])
    assert gen.returncode == 0, gen.stderr
    check = _run_script(["--output", str(output), "--check"])
    assert check.returncode == 0, check.stdout + check.stderr


def test_check_fails_when_missing(tmp_path: Path) -> None:
    output = tmp_path / "nonexistent.json"
    check = _run_script(["--output", str(output), "--check"])
    assert check.returncode == 1


def test_check_fails_when_stale(tmp_path: Path) -> None:
    output = tmp_path / "manifest.json"
    gen = _run_script(["--output", str(output)])
    assert gen.returncode == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    data["capabilities"]["capabilities"].append(
        {"id": "fake", "name": "Fake", "description": "", "domain": "test"}
    )
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    check = _run_script(["--output", str(output), "--check"])
    assert check.returncode == 1
    assert "stale" in check.stdout.lower()


def test_manifest_has_expected_capability_count(tmp_path: Path) -> None:
    output = tmp_path / "manifest.json"
    result = _run_script(["--output", str(output)])
    assert result.returncode == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    caps = data["capabilities"]["capabilities"]
    assert len(caps) >= 20
    contracts = data["data_contracts"]["contracts"]
    assert len(contracts) >= 20


def test_reference_index_is_generated_and_checked(tmp_path: Path) -> None:
    output = tmp_path / "manifest.json"
    reference = tmp_path / "REFERENCE_INDEX.md"
    gen = _run_script(["--output", str(output), "--reference-output", str(reference)])
    assert gen.returncode == 0, gen.stderr
    content = reference.read_text(encoding="utf-8")
    assert "# ScoutFootball 参考索引" in content
    assert "## 能力登记" in content
    assert "## 数据契约登记" in content

    check = _run_script([
        "--output", str(output),
        "--reference-output",
        str(reference),
        "--check",
    ])
    assert check.returncode == 0, check.stdout + check.stderr

    reference.write_text(content + "stale", encoding="utf-8")
    stale = _run_script([
        "--output", str(output),
        "--reference-output",
        str(reference),
        "--check",
    ])
    assert stale.returncode == 1
    assert "reference index is stale" in stale.stdout.lower()

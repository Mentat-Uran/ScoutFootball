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


def test_committed_manifest_matches_current_architecture() -> None:
    """真实仓库的 committed manifest 与 reference index 必须与当前 architecture.py 一致。

    之前所有测试在 tmp_path 上验证 generate_manifest.py 的逻辑正确性，但没有
    测试验证"当前提交的 manifest 与当前 architecture.py 一致"。这导致
    e3a34d7 修改 architecture.py 添加 /health/detailed 到 api.server capability
    的 api_paths 后，data/project_manifest.json 与 docs/REFERENCE_INDEX.md stale
    未被 pytest 捕获——直到维护者手动运行 generate_manifest.py --check 才发现。

    本测试关闭该缺口：直接调用 --check（使用默认路径）验证真实仓库的 manifest
    和 reference index 与当前 architecture.py 一致。未来任何修改 architecture.py
    但忘记刷新 manifest 的 commit 会立即被 uv run pytest 捕获。
    """
    # 使用默认路径（data/project_manifest.json + docs/REFERENCE_INDEX.md）
    check = _run_script(["--check"])
    assert check.returncode == 0, (
        "Committed manifest or reference index is stale. "
        "Run `PYTHONPATH=src uv run python scripts/generate_manifest.py` to regenerate.\n"
        f"stdout: {check.stdout}\nstderr: {check.stderr}"
    )

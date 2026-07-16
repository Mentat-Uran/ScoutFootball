"""Tests for scripts/check_frontend_manifest.py staleness gate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_frontend_manifest.py"


def _load_module():
    """Import the script as a module so we can call check_manifest() directly."""
    spec = importlib.util.spec_from_file_location("check_frontend_manifest", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_manifest(files: dict[str, float]) -> dict:
    return {
        "generated_at": "2026-06-23T00:00:00+00:00",
        "file_count": len(files),
        "total_kb": round(sum(files.values()), 1),
        "files": [{"path": p, "kb": v} for p, v in sorted(files.items())],
    }


def test_fresh_manifest_returns_zero(tmp_path: Path) -> None:
    mod = _load_module()
    data_dir = tmp_path / "frontend" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "a.json").write_text('{"x": 1}', encoding="utf-8")
    (data_dir / "sub").mkdir()
    (data_dir / "sub" / "b.json").write_text('{"y": 2}', encoding="utf-8")

    manifest_path = tmp_path / "frontend" / "data_manifest.json"
    # Sizes must match within SIZE_TOLERANCE_KB (0.2).
    _write_json(manifest_path, _make_manifest({
        "/data/a.json": round(len('{"x": 1}') / 1024, 1),
        "/data/sub/b.json": round(len('{"y": 2}') / 1024, 1),
    }))

    assert mod.check_manifest(manifest_path, data_dir, quiet=True) == 0


def test_missing_manifest_returns_one(tmp_path: Path) -> None:
    mod = _load_module()
    manifest_path = tmp_path / "missing.json"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    assert mod.check_manifest(manifest_path, data_dir, quiet=True) == 1


def test_unreadable_manifest_returns_one(tmp_path: Path) -> None:
    mod = _load_module()
    manifest_path = tmp_path / "data_manifest.json"
    manifest_path.write_text("not valid json {", encoding="utf-8")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    assert mod.check_manifest(manifest_path, data_dir, quiet=True) == 1


def test_extra_file_on_disk_returns_one(tmp_path: Path) -> None:
    mod = _load_module()
    data_dir = tmp_path / "frontend" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "a.json").write_text('{"x": 1}', encoding="utf-8")
    (data_dir / "b.json").write_text('{"y": 2}', encoding="utf-8")  # not in manifest

    manifest_path = tmp_path / "frontend" / "data_manifest.json"
    _write_json(manifest_path, _make_manifest({
        "/data/a.json": round(len('{"x": 1}') / 1024, 1),
    }))

    assert mod.check_manifest(manifest_path, data_dir, quiet=True) == 1


def test_missing_file_on_disk_returns_one(tmp_path: Path) -> None:
    mod = _load_module()
    data_dir = tmp_path / "frontend" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "a.json").write_text('{"x": 1}', encoding="utf-8")
    # manifest references b.json which does not exist on disk

    manifest_path = tmp_path / "frontend" / "data_manifest.json"
    _write_json(manifest_path, _make_manifest({
        "/data/a.json": round(len('{"x": 1}') / 1024, 1),
        "/data/b.json": 1.0,
    }))

    assert mod.check_manifest(manifest_path, data_dir, quiet=True) == 1


def test_size_drift_returns_one(tmp_path: Path) -> None:
    mod = _load_module()
    data_dir = tmp_path / "frontend" / "data"
    data_dir.mkdir(parents=True)
    # Actual size ~0.001 KB, manifest says 5.0 KB — well beyond 0.2 tolerance.
    (data_dir / "a.json").write_text('{"x": 1}', encoding="utf-8")

    manifest_path = tmp_path / "frontend" / "data_manifest.json"
    _write_json(manifest_path, _make_manifest({"/data/a.json": 5.0}))

    assert mod.check_manifest(manifest_path, data_dir, quiet=True) == 1


def test_size_drift_within_tolerance_returns_zero(tmp_path: Path) -> None:
    mod = _load_module()
    data_dir = tmp_path / "frontend" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "a.json").write_text('{"x": 1}', encoding="utf-8")
    actual_kb = round(len('{"x": 1}') / 1024, 1)
    # Drift of 0.1 KB is within the 0.2 tolerance.
    manifest_path = tmp_path / "frontend" / "data_manifest.json"
    _write_json(manifest_path, _make_manifest({"/data/a.json": actual_kb + 0.1}))

    assert mod.check_manifest(manifest_path, data_dir, quiet=True) == 0


def test_empty_data_dir_with_empty_manifest_returns_zero(tmp_path: Path) -> None:
    mod = _load_module()
    data_dir = tmp_path / "frontend" / "data"
    data_dir.mkdir(parents=True)
    manifest_path = tmp_path / "frontend" / "data_manifest.json"
    _write_json(manifest_path, _make_manifest({}))

    assert mod.check_manifest(manifest_path, data_dir, quiet=True) == 0

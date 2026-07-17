"""Tests for the task-history archive utility."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "archive_tasks_history.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("archive_tasks_history", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_archive_moves_history_and_leaves_stable_link(tmp_path: Path) -> None:
    mod = _load_module()
    tasks = tmp_path / "docs" / "TASKS.md"
    archive = tmp_path / "docs" / "history" / "TASKS-2026-07-17.md"
    tasks.parent.mkdir(parents=True)
    tasks.write_text(
        "# Tasks\n\n## Active\n\nCurrent item.\n\n"
        "## 历史顶层架构（待归档）\n\nOld record.\n",
        encoding="utf-8",
    )

    active_lines, archive_lines = mod.archive_tasks_history(tasks, archive)

    active = tasks.read_text(encoding="utf-8")
    archived = archive.read_text(encoding="utf-8")
    assert active_lines > 0
    assert archive_lines > 0
    assert mod.HISTORY_MARKER not in active
    assert "](history/TASKS-2026-07-17.md)" in active
    assert "# ScoutFootball 任务路线图历史归档" in archived
    assert "Old record." in archived
    assert mod.check_archive(tasks, archive) == 0


def test_archive_refuses_to_overwrite_different_history(tmp_path: Path) -> None:
    mod = _load_module()
    tasks = tmp_path / "docs" / "TASKS.md"
    archive = tmp_path / "docs" / "history" / "TASKS-2026-07-17.md"
    tasks.parent.mkdir(parents=True)
    archive.parent.mkdir(parents=True)
    tasks.write_text(
        "# Tasks\n\n## 历史顶层架构（待归档）\n\nOld record.\n",
        encoding="utf-8",
    )
    archive.write_text("different", encoding="utf-8")

    try:
        mod.archive_tasks_history(tasks, archive)
    except FileExistsError:
        pass
    else:
        raise AssertionError("different archive content must not be overwritten")


def test_check_rejects_missing_link_or_authority_boundary(tmp_path: Path) -> None:
    mod = _load_module()
    tasks = tmp_path / "docs" / "TASKS.md"
    archive = tmp_path / "docs" / "history" / "TASKS-2026-07-17.md"
    tasks.parent.mkdir(parents=True)
    archive.parent.mkdir(parents=True)
    tasks.write_text("# Tasks\n", encoding="utf-8")
    archive.write_text("# Archive\n", encoding="utf-8")

    assert mod.check_archive(tasks, archive) == 1

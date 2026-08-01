"""Archive the historical section of ``docs/TASKS.md`` without losing it.

The active task queue is deliberately kept at the top of ``TASKS.md``. This
tool moves the first marked historical section into a dated, versioned document
and replaces it with a stable link. It never deletes an existing archive or
overwrites one with different content.

Usage::

    uv run python scripts/archive_tasks_history.py
    uv run python scripts/archive_tasks_history.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKS_PATH = REPO_ROOT / "docs" / "TASKS.md"
DEFAULT_ARCHIVE_PATH = REPO_ROOT / "docs" / "history" / "TASKS-2026-07-17.md"
HISTORY_MARKER = "## 历史顶层架构（待归档）"


def _archive_text(history: str, source_name: str) -> str:
    """Wrap the moved history with an explicit non-authoritative header."""
    body = history.replace(HISTORY_MARKER, "## 历史顶层架构", 1)
    return (
        "# ScoutFootball 任务路线图历史归档\n\n"
        f"> 来源：`{source_name}`，归档日期：2026-07-17。"
        "本文保留历史交付、旧阶段和研究记录，不是当前任务真源。"
        "当前可执行节点只看 `docs/TASKS.md` 顶部。\n\n"
        f"<!-- archive-sha256: {hashlib.sha256(history.encode('utf-8')).hexdigest()} -->\n\n"
        f"{body}"
    )


def _active_text(active: str, archive_path: Path, tasks_path: Path) -> str:
    relative_archive = archive_path.relative_to(tasks_path.parent).as_posix()
    return (
        f"{active.rstrip()}\n\n"
        "## 历史归档\n\n"
        "旧阶段、历史交付和调研记录已移动到"
        f" [`{relative_archive}`]({relative_archive})。"
        "它们用于追溯，不改变当前节点状态或依赖判断。\n"
    )


def archive_tasks_history(tasks_path: Path, archive_path: Path) -> tuple[int, int]:
    """Archive a marked history section and return active/archive line counts."""
    source = tasks_path.read_text(encoding="utf-8")
    if HISTORY_MARKER not in source:
        raise ValueError(f"history marker not found in {tasks_path}")
    active, history = source.split(HISTORY_MARKER, maxsplit=1)
    history = HISTORY_MARKER + history
    archive_content = _archive_text(history, tasks_path.name)

    if archive_path.exists():
        existing = archive_path.read_text(encoding="utf-8")
        if existing != archive_content:
            raise FileExistsError(
                f"archive already exists with different content: {archive_path}"
            )
    else:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_text(archive_content, encoding="utf-8")

    active_content = _active_text(active, archive_path, tasks_path)
    tasks_path.write_text(active_content, encoding="utf-8")
    return active_content.count("\n"), archive_content.count("\n")


def check_archive(tasks_path: Path, archive_path: Path) -> int:
    """Return zero only when active and archived task documents are consistent."""
    if not archive_path.exists():
        print(f"FAIL: task history archive not found at {archive_path}")
        return 1
    active = tasks_path.read_text(encoding="utf-8")
    if HISTORY_MARKER in active:
        print("FAIL: TASKS.md still contains the unarchived history marker")
        return 1
    try:
        relative_archive = archive_path.relative_to(tasks_path.parent).as_posix()
    except ValueError:
        relative_archive = str(archive_path)
    if f"]({relative_archive})" not in active:
        print("FAIL: TASKS.md does not link to the history archive")
        return 1
    archive = archive_path.read_text(encoding="utf-8")
    if "本文保留历史交付" not in archive:
        print("FAIL: task history archive is missing its authority boundary")
        return 1
    print(f"OK: task history archive is linked ({archive_path.name})")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS_PATH)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    tasks_path = args.tasks.resolve()
    archive_path = args.archive.resolve()
    if args.check:
        sys.exit(check_archive(tasks_path, archive_path))

    active_lines, archive_lines = archive_tasks_history(tasks_path, archive_path)
    print(
        f"Archived task history: {active_lines} active lines, "
        f"{archive_lines} archived lines -> {archive_path}"
    )


if __name__ == "__main__":
    main()

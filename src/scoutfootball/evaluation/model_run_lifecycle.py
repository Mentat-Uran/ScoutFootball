"""Fail-closed local lifecycle actions for optimizer candidate directories."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from scoutfootball.config import PlatformSettings


class ModelRunLifecycleError(ValueError):
    """Raised when a requested model-run lifecycle action is unsafe."""


def _runs_root(settings: PlatformSettings) -> Path:
    return (settings.model_root / "runs").resolve()


def _run_directory(settings: PlatformSettings, run_id: str) -> Path:
    if not run_id or Path(run_id).name != run_id:
        raise ModelRunLifecycleError("run_id must be a single candidate directory name")
    root = _runs_root(settings)
    requested = root / run_id
    if requested.is_symlink():
        raise ModelRunLifecycleError("candidate directory must not be a symlink")
    directory = requested.resolve()
    if directory.parent != root:
        raise ModelRunLifecycleError("candidate directory resolves outside data/models/runs")
    if not directory.is_dir():
        raise ModelRunLifecycleError(f"candidate run does not exist: {run_id}")
    return directory


def _directory_size(directory: Path) -> int:
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())


def inspect_optimizer_run_discard(
    settings: PlatformSettings, run_id: str, *, allow_incomplete: bool = False
) -> dict[str, Any]:
    """Describe whether a local candidate can be discarded without touching gold outputs."""
    directory = _run_directory(settings, run_id)
    meta_path = directory / "meta.json"
    meta: dict[str, Any] | None = None
    if meta_path.exists():
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            incomplete_reason = f"metadata unreadable: {type(exc).__name__}"
        else:
            if isinstance(loaded, dict):
                meta = loaded
                incomplete_reason = None
            else:
                incomplete_reason = "metadata is not an object"
    else:
        incomplete_reason = "metadata is missing"

    activation = meta.get("activation") if meta else None
    activation_status = activation.get("status") if isinstance(activation, dict) else None
    if activation_status == "not_activated":
        discardable = True
        reason = "candidate is explicitly not activated"
    elif incomplete_reason and allow_incomplete:
        discardable = True
        reason = f"incomplete candidate explicitly allowed: {incomplete_reason}"
    elif incomplete_reason:
        discardable = False
        reason = f"incomplete candidate requires --allow-incomplete: {incomplete_reason}"
    else:
        discardable = False
        reason = "run lacks explicit not_activated status and is retained"

    return {
        "run_id": run_id,
        "path": str(directory),
        "activation_status": activation_status,
        "incomplete_reason": incomplete_reason,
        "discardable": discardable,
        "reason": reason,
        "file_count": sum(1 for path in directory.rglob("*") if path.is_file()),
        "size_bytes": _directory_size(directory),
    }


def discard_optimizer_run(
    settings: PlatformSettings,
    run_id: str,
    *,
    confirm: bool = False,
    allow_incomplete: bool = False,
) -> dict[str, Any]:
    """Discard one explicit local candidate after a safety check and confirmation."""
    report = inspect_optimizer_run_discard(
        settings, run_id, allow_incomplete=allow_incomplete
    )
    report["confirmed"] = bool(confirm)
    report["deleted"] = False
    if not report["discardable"]:
        raise ModelRunLifecycleError(report["reason"])
    if not confirm:
        return report

    directory = _run_directory(settings, run_id)
    shutil.rmtree(directory)
    report["deleted"] = True
    return report


def format_optimizer_run_discard(report: dict[str, Any]) -> str:
    """Render a concise local-only discard result."""
    action = "Deleted" if report["deleted"] else "Dry run"
    return "\n".join(
        [
            f"{action}: {report['run_id']}",
            f"  Candidate path: {report['path']}",
            f"  Reason: {report['reason']}",
            f"  Files: {report['file_count']} ({report['size_bytes']} bytes)",
        ]
    )

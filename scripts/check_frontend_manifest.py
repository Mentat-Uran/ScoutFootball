"""Check frontend/data_manifest.json freshness against actual frontend/data/ files.

The frontend ``data_manifest.json`` records the file list and sizes of the
static release snapshot under ``frontend/data/``. When files are added,
removed, or resized without re-running ``export_static_frontend_data.py``,
the manifest becomes stale and the static snapshot's freshness claims can
no longer be trusted.

This script compares the recorded manifest against the actual files on
disk and reports any drift. It is the minimal staleness gate referenced by
G1 post-maintenance ("建立最小文档生成和陈旧度报告"); a full build-time
gate that regenerates the manifest automatically is deferred to C1.

Usage::

    uv run python scripts/check_frontend_manifest.py

Exit codes:
- 0: manifest is fresh (file list and sizes match within tolerance)
- 1: manifest is stale, missing, or unreadable
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = REPO_ROOT / "frontend"
DATA_DIR = FRONTEND_DIR / "data"
MANIFEST_PATH = FRONTEND_DIR / "data_manifest.json"

# Allow tiny size differences from rounding (manifest rounds to 1 decimal KB).
SIZE_TOLERANCE_KB = 0.2


def _scan_actual_files(data_dir: Path) -> dict[str, float]:
    """Return ``{posix_relative_path: size_kb}`` for every *.json under data_dir.

    Paths use the ``/data/...`` prefix to match the manifest convention
    written by ``export_static_frontend_data.py``.
    """
    actual: dict[str, float] = {}
    if not data_dir.exists():
        return actual
    base = data_dir.parent  # e.g. .../frontend; relative_to gives "data/..."
    for p in sorted(data_dir.rglob("*.json")):
        rel = "/" + p.relative_to(base).as_posix()
        actual[rel] = round(p.stat().st_size / 1024, 1)
    return actual


def _validate_recorded_files(manifest: object) -> tuple[dict[str, float] | None, str | None]:
    """Validate the file inventory before comparing it with the snapshot.

    A malformed or internally inconsistent manifest is just as unsafe as a
    stale one: the static UI could otherwise advertise a freshness claim that
    the gate never actually checked.  Keep this validation dependency-free so
    it can run before a static build.
    """
    if not isinstance(manifest, dict):
        return None, "top level must be a JSON object"

    files = manifest.get("files")
    if not isinstance(files, list):
        return None, "files must be a list"

    recorded: dict[str, float] = {}
    for index, entry in enumerate(files):
        if not isinstance(entry, dict):
            return None, f"files[{index}] must be an object"
        path = entry.get("path")
        kb = entry.get("kb")
        if not isinstance(path, str) or not path.startswith("/data/"):
            return None, f"files[{index}].path must start with /data/"
        if (
            isinstance(kb, bool)
            or not isinstance(kb, (int, float))
            or not math.isfinite(kb)
            or kb < 0
        ):
            return None, f"files[{index}].kb must be a finite non-negative number"
        if path in recorded:
            return None, f"duplicate file entry: {path}"
        recorded[path] = float(kb)

    file_count = manifest.get("file_count")
    if (
        isinstance(file_count, bool)
        or not isinstance(file_count, int)
        or file_count != len(recorded)
    ):
        return None, "file_count must match the unique file inventory"

    total_kb = manifest.get("total_kb")
    if (
        isinstance(total_kb, bool)
        or not isinstance(total_kb, (int, float))
        or not math.isfinite(total_kb)
        or abs(float(total_kb) - round(sum(recorded.values()), 1)) > SIZE_TOLERANCE_KB
    ):
        return None, "total_kb must match the file inventory"

    return recorded, None


def check_manifest(
    manifest_path: Path = MANIFEST_PATH,
    data_dir: Path = DATA_DIR,
    *,
    quiet: bool = False,
) -> int:
    """Return 0 if manifest is fresh, 1 if stale/missing/unreadable.

    Parameters
    ----------
    manifest_path, data_dir
        Override paths (used by tests).
    quiet
        If True, suppress stdout (errors still return exit code 1).
    """

    def _print(msg: str) -> None:
        if not quiet:
            print(msg)

    if not manifest_path.exists():
        _print(f"FAIL: manifest not found at {manifest_path}")
        return 1

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _print(f"FAIL: manifest unreadable at {manifest_path}: {exc}")
        return 1

    recorded_files, validation_error = _validate_recorded_files(manifest)
    if validation_error:
        _print(f"FAIL: {manifest_path.name} has invalid metadata: {validation_error}")
        return 1

    assert recorded_files is not None
    actual_files = _scan_actual_files(data_dir)

    missing_on_disk = sorted(set(recorded_files) - set(actual_files))
    missing_in_manifest = sorted(set(actual_files) - set(recorded_files))
    size_drift = sorted(
        path
        for path in set(recorded_files) & set(actual_files)
        if abs(recorded_files[path] - actual_files[path]) > SIZE_TOLERANCE_KB
    )

    if not missing_on_disk and not missing_in_manifest and not size_drift:
        _print(
            f"OK: {manifest_path.name} is fresh "
            f"({len(actual_files)} files, {manifest.get('total_kb', 0):.0f} KB)"
        )
        return 0

    _print(f"FAIL: {manifest_path.name} is stale.")
    if missing_on_disk:
        _print(f"  {len(missing_on_disk)} files in manifest but missing on disk:")
        for path in missing_on_disk[:10]:
            _print(f"    {path}")
        if len(missing_on_disk) > 10:
            _print(f"    ... and {len(missing_on_disk) - 10} more")
    if missing_in_manifest:
        _print(f"  {len(missing_in_manifest)} files on disk but missing from manifest:")
        for path in missing_in_manifest[:10]:
            _print(f"    {path}")
        if len(missing_in_manifest) > 10:
            _print(f"    ... and {len(missing_in_manifest) - 10} more")
    if size_drift:
        _print(f"  {len(size_drift)} files with size drift (>{SIZE_TOLERANCE_KB} KB):")
        for path in size_drift[:10]:
            _print(
                f"    {path}: manifest={recorded_files[path]} KB, "
                f"actual={actual_files[path]} KB"
            )
        if len(size_drift) > 10:
            _print(f"    ... and {len(size_drift) - 10} more")
    _print(
        "  Regenerate with: "
        "PYTHONPATH=src python scripts/export_static_frontend_data.py --profile release"
    )
    return 1


def main() -> None:
    sys.exit(check_manifest())


if __name__ == "__main__":
    main()

"""Content-level, local-only inspection evidence for registered raw CSV files."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scoutfootball.architecture import build_data_contract_registry
from scoutfootball.config import PlatformSettings

RAW_SOURCE_INSPECTION_TYPE = "scoutfootball.raw_source_file_inspection"
RAW_SOURCE_INSPECTION_VERSION = "1.0"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _raw_source_roots() -> dict[str, str]:
    return {
        contract.license.source_name: contract.artifact_id.replace("\\", "/")
        for contract in build_data_contract_registry().contracts
        if contract.layer == "raw" and contract.license is not None
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _schema_hash(headers: list[str]) -> str:
    encoded = json.dumps(headers, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def inspect_raw_csv(
    *,
    source_id: str,
    path: Path | str,
    settings: PlatformSettings | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Read a registered UTF-8 CSV completely and return portable evidence.

    The evidence contains only structural facts and hashes. It deliberately
    excludes cell values, filesystem timestamps, and any assertion about the
    upstream source date or rights.
    """
    settings = settings or PlatformSettings.from_root()
    root = _raw_source_roots().get(source_id)
    if root is None:
        raise ValueError("source_not_registered")
    source_root = (settings.data_root / root).resolve()
    candidate = Path(path)
    resolved = (
        (settings.data_root / candidate).resolve()
        if not candidate.is_absolute()
        else candidate.resolve()
    )
    try:
        relative = resolved.relative_to(source_root)
    except ValueError as exc:
        raise ValueError("path_outside_registered_source") from exc
    if resolved.suffix.lower() != ".csv":
        raise ValueError("csv_required")
    if not resolved.is_file():
        raise ValueError("source_file_missing")

    try:
        with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            headers = next(reader, None)
            if not headers or any(not header.strip() for header in headers):
                raise ValueError("csv_header_invalid")
            if len(set(headers)) != len(headers):
                raise ValueError("csv_header_duplicate")
            row_count = 0
            for line_number, row in enumerate(reader, start=2):
                # Tolerate completely empty lines (csv.reader returns [] for
                # blank lines, including trailing newlines emitted by some
                # upstream tools such as clubelo.com). A partial-width row
                # (e.g. "a,,") still raises csv_row_width_mismatch; only
                # truly empty rows are skipped so real data corruption
                # remains detectable.
                if not row:
                    continue
                if len(row) != len(headers):
                    raise ValueError(f"csv_row_width_mismatch:{line_number}")
                row_count += 1
    except UnicodeDecodeError as exc:
        raise ValueError("csv_utf8_required") from exc
    except csv.Error as exc:
        raise ValueError(f"csv_unreadable:{exc}") from exc

    artifact_path = f"{root.rstrip('/')}/{relative.as_posix()}"
    return {
        "report_type": RAW_SOURCE_INSPECTION_TYPE,
        "report_version": RAW_SOURCE_INSPECTION_VERSION,
        "generated_at": generated_at or _now_iso(),
        "source_id": source_id,
        "artifacts": [
            {
                "artifact_path": artifact_path,
                "inspection": {
                    "status": "ok",
                    "format": "csv",
                    "content_hash": _sha256(resolved),
                    "schema_hash": _schema_hash(headers),
                    "row_count": row_count,
                    "column_count": len(headers),
                    "size_bytes": resolved.stat().st_size,
                    "reader": "python_csv_utf8",
                },
            }
        ],
        "limitations": [
            "The report contains no source cell values and does not upload data.",
            (
                "The content hash identifies only this local file; it is not an upstream "
                "snapshot date."
            ),
            (
                "Successful CSV parsing does not establish source rights, completeness, or "
                "fitness for a downstream claim."
            ),
        ],
    }


def write_raw_source_inspection_report(
    report: dict[str, Any], path: Path | str, *, overwrite: bool = False
) -> Path:
    """Write portable inspection evidence without silently replacing an existing file."""
    output = Path(path).resolve()
    if output.exists() and not overwrite:
        raise FileExistsError("evidence_exists_use_overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    return output

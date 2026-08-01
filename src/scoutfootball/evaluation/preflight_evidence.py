"""Portable evidence reports for local Parquet preflight runs.

The preflight command proves that an artifact decoded in the current local
runtime.  This module preserves that observation alongside the provenance
that is actually recorded in the data-contract registry.  It deliberately
keeps absent snapshot and lineage fields as ``not_recorded`` rather than
trying to reconstruct them from filenames or timestamps.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scoutfootball.architecture import build_data_contract_registry
from scoutfootball.schemas import DataContractRegistry

from .parquet_preflight import ParquetPreflightReport

PREFLIGHT_EVIDENCE_VERSION = "1.0"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _contract_for_path(
    relative_path: str, registry: DataContractRegistry
) -> tuple[Any, ...]:
    """Return the most specific directory contract for a report path."""
    normalized = relative_path.replace("\\", "/").strip("/")
    matches = []
    for contract in registry.contracts:
        artifact_id = contract.artifact_id.replace("\\", "/").strip("/")
        if "/" not in artifact_id:
            continue
        if normalized == artifact_id or normalized.startswith(f"{artifact_id}/"):
            matches.append(contract)
    return tuple(sorted(matches, key=lambda contract: len(contract.artifact_id), reverse=True))


def _not_recorded(note: str) -> dict[str, str]:
    return {"status": "not_recorded", "note": note}


def _contract_evidence(
    report: ParquetPreflightReport, registry: DataContractRegistry
) -> dict[str, Any]:
    matches = _contract_for_path(report.relative_path, registry)
    if not matches:
        return {
            "contract": _not_recorded("No matching directory contract is registered."),
            "source_license": _not_recorded("No matching source license is registered."),
            "snapshot": _not_recorded("No matching contract snapshot is recorded."),
            "lineage": _not_recorded("No matching contract lineage is recorded."),
        }

    contract = matches[0]
    contract_payload = {
        "status": "recorded" if contract.recorded else "not_recorded",
        "artifact_id": contract.artifact_id,
        "layer": contract.layer,
        "purpose": contract.purpose,
        "recorded_note": contract.recorded_note,
    }
    license_payload: dict[str, Any]
    if contract.license is None:
        license_payload = _not_recorded("The matching contract has no source license.")
    else:
        license_payload = {
            "status": "recorded",
            "details": contract.license.model_dump(mode="json"),
        }

    snapshot_payload: dict[str, Any]
    if contract.snapshot is None:
        snapshot_payload = _not_recorded("The matching contract has no snapshot metadata.")
    else:
        snapshot_payload = {
            "status": "recorded",
            "details": contract.snapshot.model_dump(mode="json"),
        }

    if not contract.lineage:
        lineage_payload: dict[str, Any] = _not_recorded(
            "The matching contract has no recorded lineage entries."
        )
    else:
        lineage_payload = {
            "status": "recorded",
            "entries": [entry.model_dump(mode="json") for entry in contract.lineage],
        }

    return {
        "contract": contract_payload,
        "source_license": license_payload,
        "snapshot": snapshot_payload,
        "lineage": lineage_payload,
    }


def build_preflight_evidence_report(
    reports: list[ParquetPreflightReport],
    *,
    target: str,
    registry: DataContractRegistry | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a self-contained, JSON-serialisable local evidence report."""
    registry = registry or build_data_contract_registry()
    artifacts = []
    for report in reports:
        provenance = _contract_evidence(report, registry)
        artifacts.append(
            {
                "artifact_path": report.relative_path,
                "inspection": report.to_dict(),
                "provenance": provenance,
            }
        )

    return {
        "report_type": "scoutfootball.parquet_preflight_evidence",
        "report_version": PREFLIGHT_EVIDENCE_VERSION,
        "generated_at": generated_at or _now_iso(),
        "generator": {
            "package_version": registry.package_version,
            "contract_registry_generated_at": registry.generated_at,
        },
        "scope": {"target": target, "artifact_count": len(artifacts)},
        "summary": {
            "ok": sum(1 for report in reports if report.ok),
            "unreadable": sum(1 for report in reports if not report.readable),
            "footer_content_mismatch": sum(
                1 for report in reports if report.footer_content_mismatch
            ),
            "contracts_recorded": sum(
                1
                for artifact in artifacts
                if artifact["provenance"]["contract"]["status"] == "recorded"
            ),
            "licenses_recorded": sum(
                1
                for artifact in artifacts
                if artifact["provenance"]["source_license"]["status"] == "recorded"
            ),
            "snapshots_recorded": sum(
                1
                for artifact in artifacts
                if artifact["provenance"]["snapshot"]["status"] == "recorded"
            ),
            "lineage_recorded": sum(
                1
                for artifact in artifacts
                if artifact["provenance"]["lineage"]["status"] == "recorded"
            ),
        },
        "artifacts": artifacts,
    }


def write_preflight_evidence_report(
    report: dict[str, Any], output_path: Path | str, *, overwrite: bool = False
) -> Path:
    """Write a report atomically, refusing accidental overwrites by default."""
    output = Path(output_path).expanduser().resolve()
    if output.exists() and not overwrite:
        raise FileExistsError(
            f"Evidence report already exists: {output}. Use --overwrite-evidence to replace it."
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output

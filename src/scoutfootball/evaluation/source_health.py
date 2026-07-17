"""Read-only health observations for registered local raw sources."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from scoutfootball.architecture import build_data_contract_registry
from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.source_snapshot_ledger import (
    latest_snapshot_by_source,
    read_source_snapshot_ledger,
)


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_source_health_report(
    settings: PlatformSettings | None = None,
    preflight_evidence: dict[str, Any] | None = None,
    snapshot_ledger_path: str | None = None,
) -> dict[str, Any]:
    """Inspect local raw directories without treating mtime as source snapshot time."""
    settings = settings or PlatformSettings.from_root()
    registry = build_data_contract_registry()
    registered = [contract for contract in registry.contracts if contract.layer == "raw"]
    inspections = _inspections_by_path(preflight_evidence)
    snapshots = (
        latest_snapshot_by_source(read_source_snapshot_ledger(snapshot_ledger_path))
        if snapshot_ledger_path
        else {}
    )
    entries = []
    registered_dirs = set()
    for contract in registered:
        relative = contract.artifact_id.replace("\\", "/")
        registered_dirs.add(relative.removeprefix("raw/").split("/", 1)[0])
        directory = settings.data_root / relative
        files = (
            sorted(
                path
                for path in directory.rglob("*")
                if path.is_file() and path.name != ".gitkeep"
            )
            if directory.exists()
            else []
        )
        status = "missing" if not directory.exists() else ("present" if files else "empty")
        entries.append(
            {
                "source_id": contract.license.source_name if contract.license else relative,
                "contract": {"status": "recorded", "artifact_id": contract.artifact_id},
                "license": (
                    {"status": "recorded", "details": contract.license.model_dump(mode="json")}
                    if contract.license
                    else {"status": "not_recorded"}
                ),
                "local_observation": {
                    "status": status,
                    "file_count": len(files),
                    "total_bytes": sum(path.stat().st_size for path in files),
                    "newest_local_mtime": (
                        _iso(max(path.stat().st_mtime for path in files)) if files else None
                    ),
                },
                "snapshot": _snapshot_status(snapshots.get(contract.license.source_name)),
                "inspection_capture": [
                    inspections[path]
                    for path in sorted(inspections)
                    if path == relative or path.startswith(f"{relative}/")
                ],
            }
        )

    raw_root = settings.data_root / "raw"
    observed_dirs = (
        {path.name for path in raw_root.iterdir() if path.is_dir()}
        if raw_root.exists()
        else set()
    )
    return {
        "report_type": "scoutfootball.source_health",
        "report_version": "1.0",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "registered_source_count": len(entries),
        "registered_sources": entries,
        "unregistered_raw_directories": sorted(observed_dirs - registered_dirs),
        "limitations": [
            "This is a local filesystem observation, not proof of upstream freshness or rights.",
            "Source snapshot and lineage remain not_recorded unless explicitly "
            "captured by an import workflow.",
        ],
    }


def _snapshot_status(record: dict[str, Any] | None) -> dict[str, Any]:
    if record is None:
        return {
            "status": "not_recorded",
            "note": "Local modification time is not asserted as source snapshot time.",
        }
    return {
        "status": "recorded",
        "snapshot_id": record["snapshot_id"],
        "as_of": record["snapshot_date"],
        "recorded_at": record["recorded_at"],
        "evidence": record["evidence"],
        "note": (
            "Explicit local ledger record; no upstream freshness is inferred "
            "beyond its declared date."
        ),
    }


def _inspections_by_path(evidence: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if evidence is None:
        return {}
    if not isinstance(evidence, dict) or evidence.get(
        "report_type"
    ) != "scoutfootball.parquet_preflight_evidence":
        raise ValueError("evidence_report_type_invalid")
    artifacts = evidence.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("evidence_artifacts_invalid")
    observations: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        path = artifact.get("artifact_path") if isinstance(artifact, dict) else None
        inspection = artifact.get("inspection") if isinstance(artifact, dict) else None
        if not isinstance(path, str) or not isinstance(inspection, dict):
            raise ValueError("evidence_artifact_invalid")
        normalized = path.replace("\\", "/")
        is_windows_absolute = len(normalized) >= 3 and normalized[1:3] == ":/"
        if (
            normalized.startswith("/")
            or is_windows_absolute
            or ".." in normalized.split("/")
        ):
            raise ValueError("evidence_artifact_path_invalid")
        observations[normalized] = {
            "artifact_path": normalized,
            "content_hash": inspection.get("content_hash"),
            "schema_hash": inspection.get("schema_hash"),
            "row_count": inspection.get("row_count"),
            "reader": inspection.get("reader"),
            "inspected_at": evidence.get("generated_at"),
        }
    return observations


def format_source_health_report(report: dict[str, Any]) -> str:
    """Render a concise human-readable local source-health summary."""
    lines = [f"Source health: {report['registered_source_count']} registered sources"]
    for source in report["registered_sources"]:
        observation = source["local_observation"]
        lines.append(
            f"  - {source['source_id']}: {observation['status']}, "
            f"{observation['file_count']} files, snapshot={source['snapshot']['status']}"
        )
    if report["unregistered_raw_directories"]:
        unregistered = ", ".join(report["unregistered_raw_directories"])
        lines.append("  UNREGISTERED RAW DIRECTORIES: " + unregistered)
    return "\n".join(lines)

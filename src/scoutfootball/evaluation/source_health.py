"""Read-only health observations for registered local raw sources."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from scoutfootball.architecture import build_data_contract_registry
from scoutfootball.config import PlatformSettings


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_source_health_report(
    settings: PlatformSettings | None = None,
) -> dict[str, Any]:
    """Inspect local raw directories without treating mtime as source snapshot time."""
    settings = settings or PlatformSettings.from_root()
    registry = build_data_contract_registry()
    registered = [contract for contract in registry.contracts if contract.layer == "raw"]
    entries = []
    registered_dirs = set()
    for contract in registered:
        relative = contract.artifact_id.replace("\\", "/")
        registered_dirs.add(relative.removeprefix("raw/").split("/", 1)[0])
        directory = settings.data_root / relative
        files = (
            sorted(path for path in directory.rglob("*") if path.is_file())
            if directory.exists()
            else []
        )
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
                    "status": "present" if directory.exists() else "missing",
                    "file_count": len(files),
                    "total_bytes": sum(path.stat().st_size for path in files),
                    "newest_local_mtime": (
                        _iso(max(path.stat().st_mtime for path in files)) if files else None
                    ),
                },
                "snapshot": {
                    "status": "not_recorded",
                    "note": "Local modification time is not asserted as source snapshot time.",
                },
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

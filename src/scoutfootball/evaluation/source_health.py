"""Read-only health observations for registered local raw sources."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from scoutfootball.architecture import build_data_contract_registry
from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.source_policy_ledger import (
    latest_policy_by_source,
    read_source_policy_ledger,
)
from scoutfootball.evaluation.source_snapshot_ledger import (
    latest_snapshot_by_source,
    read_source_snapshot_ledger,
)
from scoutfootball.schemas.storage import SourceLicense

# Canonical local ledger filenames. The recording commands
# (`record-source-policy`, `record-source-snapshot`, `record-quality-audit`,
# `record-quality-threshold`) default to these paths under
# ``<data_root>/reports/data_health/``. Reporting commands use the same
# defaults via :func:`resolve_local_ledger_path` so that maintainer-recorded
# evidence is surfaced without forcing the user to repeat ``--*-ledger`` on
# every read. Explicit CLI arguments always override the default.
DEFAULT_DATA_HEALTH_DIR = "data_health"
DEFAULT_SOURCE_POLICY_LEDGER_FILENAME = "source_policy_ledger.jsonl"
DEFAULT_SOURCE_SNAPSHOT_LEDGER_FILENAME = "source_snapshot_ledger.jsonl"
DEFAULT_QUALITY_AUDIT_LEDGER_FILENAME = "quality_audit_ledger.jsonl"
DEFAULT_QUALITY_THRESHOLD_LEDGER_FILENAME = "quality_threshold_ledger.jsonl"
DEFAULT_PREFLIGHT_EVIDENCE_FILENAME = "preflight_evidence.json"


def resolve_local_ledger_path(
    settings: PlatformSettings,
    explicit_path: str | None,
    filename: str,
) -> str | None:
    """Resolve a local ledger path, auto-discovering the canonical default.

    The canonical default location is ``<report_root>/data_health/<filename>``.
    Returns ``explicit_path`` unchanged when supplied (even if the file does
    not exist, preserving the existing reader contract of treating a missing
    file as an empty ledger). When ``explicit_path`` is ``None``, returns the
    default path only if that file actually exists on disk, otherwise
    ``None`` — so the ``*_ledger_supplied`` report flag stays truthful and
    empty-default workspaces (e.g. tests under ``tmp_path``) are unaffected.
    """
    if explicit_path:
        return explicit_path
    default_path = settings.report_root / DEFAULT_DATA_HEALTH_DIR / filename
    return str(default_path) if default_path.exists() else None


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def source_license_policy_status(
    license_info: SourceLicense | None,
    policy_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe recorded retention/deletion policy without supplying missing terms.

    A registered license is not, by itself, evidence that local retention and
    deletion handling have been decided.  This helper deliberately keeps that
    distinction machine-readable for both source-health and contract-quality.
    """
    if license_info is None:
        return {
            "status": "not_recorded",
            "missing_fields": ["source_license"],
            "note": (
                "No source license is registered, so retention and deletion policy are unknown."
            ),
        }

    if policy_record is not None:
        retention = policy_record["retention"]
        deletion = policy_record["deletion"]
        return {
            "status": "recorded",
            "policy_source": "local_policy_ledger",
            "policy_id": policy_record["policy_id"],
            "retention_mode": retention["mode"],
            "retention_policy_days": retention["days"],
            "deletion_strategy": deletion["strategy"],
            "deletion_trigger": deletion["trigger"],
            "derived_artifact_action": deletion["derived_artifact_action"],
            "decision": policy_record["decision"],
            "recorded_at": policy_record["recorded_at"],
            "missing_fields": [],
            "note": (
                "Explicit maintainer policy from the supplied local ledger; "
                "this does not interpret third-party license terms."
            ),
        }

    missing_fields: list[str] = []
    if license_info.retention_policy_days is None:
        missing_fields.append("retention_policy_days")
    if not license_info.deletion_strategy.strip():
        missing_fields.append("deletion_strategy")
    return {
        "status": "recorded" if not missing_fields else "baseline_required",
        "policy_source": "contract" if not missing_fields else "not_recorded",
        "retention_mode": "days" if license_info.retention_policy_days is not None else None,
        "retention_policy_days": license_info.retention_policy_days,
        "deletion_strategy": license_info.deletion_strategy or None,
        "missing_fields": missing_fields,
        "note": (
            "Recorded local policy fields; this does not interpret third-party license terms."
            if not missing_fields
            else (
                "A maintainer-recorded retention period and deletion strategy are required; "
                "missing values are not inferred from a license name or local files."
            )
        ),
    }


def build_source_health_report(
    settings: PlatformSettings | None = None,
    preflight_evidence: dict[str, Any] | None = None,
    snapshot_ledger_path: str | None = None,
    policy_ledger_path: str | None = None,
) -> dict[str, Any]:
    """Inspect local raw directories without treating mtime as source snapshot time."""
    settings = settings or PlatformSettings.from_root()
    registry = build_data_contract_registry()
    registered = [contract for contract in registry.contracts if contract.layer == "raw"]
    inspections = _inspections_by_path(preflight_evidence)
    resolved_snapshot_ledger = resolve_local_ledger_path(
        settings, snapshot_ledger_path, DEFAULT_SOURCE_SNAPSHOT_LEDGER_FILENAME
    )
    resolved_policy_ledger = resolve_local_ledger_path(
        settings, policy_ledger_path, DEFAULT_SOURCE_POLICY_LEDGER_FILENAME
    )
    snapshots = (
        latest_snapshot_by_source(read_source_snapshot_ledger(resolved_snapshot_ledger))
        if resolved_snapshot_ledger
        else {}
    )
    policies = (
        latest_policy_by_source(read_source_policy_ledger(resolved_policy_ledger))
        if resolved_policy_ledger
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
                path for path in directory.rglob("*") if path.is_file() and path.name != ".gitkeep"
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
                    {
                        "status": "recorded",
                        "details": contract.license.model_dump(mode="json"),
                        "policy": source_license_policy_status(
                            contract.license,
                            policies.get(contract.license.source_name),
                        ),
                    }
                    if contract.license
                    else {
                        "status": "not_recorded",
                        "policy": source_license_policy_status(None),
                    }
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
        {path.name for path in raw_root.iterdir() if path.is_dir()} if raw_root.exists() else set()
    )
    unregistered_raw_directories = sorted(observed_dirs - registered_dirs)
    return {
        "report_type": "scoutfootball.source_health",
        "report_version": "1.4",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "registered_source_count": len(entries),
        "policy_ledger_supplied": bool(resolved_policy_ledger),
        "snapshot_ledger_supplied": bool(resolved_snapshot_ledger),
        "registered_sources": entries,
        "unregistered_raw_directories": unregistered_raw_directories,
        "unregistered_raw_directory_details": _unregistered_directory_details(
            raw_root, unregistered_raw_directories
        ),
        "limitations": [
            "This is a local filesystem observation, not proof of upstream freshness or rights.",
            "Source snapshot and lineage remain not_recorded unless explicitly "
            "captured by a local evidence workflow.",
            "Unregistered directory modification times are local observations, not source dates.",
            (
                "When no ledger path is supplied, policy and snapshot ledgers are auto-"
                "discovered at <data_root>/reports/data_health/; explicit --*-ledger "
                "arguments always override the default."
            ),
        ],
    }


def _unregistered_directory_details(raw_root, directory_names: list[str]) -> list[dict[str, Any]]:
    """Summarize unregistered inputs without reading their content or inferring provenance."""
    details: list[dict[str, Any]] = []
    for directory_name in directory_names:
        directory = raw_root / directory_name
        files = sorted(
            path for path in directory.rglob("*") if path.is_file() and path.name != ".gitkeep"
        )
        details.append(
            {
                "directory": directory_name,
                "file_count": len(files),
                "total_bytes": sum(path.stat().st_size for path in files),
                "newest_local_mtime": (
                    _iso(max(path.stat().st_mtime for path in files)) if files else None
                ),
                "files": [
                    {
                        "relative_path": path.relative_to(raw_root).as_posix(),
                        "bytes": path.stat().st_size,
                        "local_mtime": _iso(path.stat().st_mtime),
                    }
                    for path in files
                ],
                "note": (
                    "Local metadata only; file names and mtimes do not establish source, "
                    "license, snapshot date, or permission to import."
                ),
            }
        )
    return details


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
    if (
        not isinstance(evidence, dict)
        or evidence.get("report_type")
        not in {
            "scoutfootball.parquet_preflight_evidence",
            "scoutfootball.raw_source_file_inspection",
        }
    ):
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
        if normalized.startswith("/") or is_windows_absolute or ".." in normalized.split("/"):
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
        policy_status = source.get("license", {}).get("policy", {}).get("status", "not_recorded")
        lines.append(
            f"  - {source['source_id']}: {observation['status']}, "
            f"{observation['file_count']} files, snapshot={source['snapshot']['status']}, "
            f"policy={policy_status}"
        )
    if report["unregistered_raw_directories"]:
        unregistered = ", ".join(report["unregistered_raw_directories"])
        lines.append("  UNREGISTERED RAW DIRECTORIES: " + unregistered)
        for item in report.get("unregistered_raw_directory_details", []):
            lines.append(
                f"    - {item['directory']}: {item['file_count']} files, "
                f"{item['total_bytes']} bytes (local metadata only)"
            )
    return "\n".join(lines)

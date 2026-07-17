"""Truthful, local-only contract-quality baseline reporting.

The report deliberately distinguishes a machine-checkable failure from an
unrecorded quality dimension. It is not a percentage score and it does not
infer an upstream snapshot date from local file timestamps.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from scoutfootball.architecture import build_data_contract_registry
from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.quality_audit_ledger import (
    latest_threshold_by_kind,
    read_quality_audit_ledger,
    read_quality_threshold_ledger,
    summarize_quality_audits,
)
from scoutfootball.evaluation.source_health import (
    _inspections_by_path,
    build_source_health_report,
    source_license_policy_status,
)
from scoutfootball.evaluation.source_policy_ledger import (
    latest_policy_by_source,
    read_source_policy_ledger,
)
from scoutfootball.evaluation.source_snapshot_ledger import (
    latest_snapshot_by_source,
    read_source_snapshot_ledger,
)

CONTRACT_QUALITY_VERSION = "1.4.0"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _status(name: str, status: str, **details: Any) -> dict[str, Any]:
    return {"name": name, "status": status, **details}


def _inspection_is_ok(inspection: dict[str, Any]) -> bool:
    """Apply the preflight's documented content-readiness rule to saved JSON."""
    return bool(
        inspection.get("exists")
        and inspection.get("readable")
        and inspection.get("row_count") is not None
        and not inspection.get("footer_content_mismatch")
        and inspection.get("sample_ok") is not False
    )


def _preflight_check(evidence: dict[str, Any] | None) -> dict[str, Any]:
    if evidence is None:
        return _status(
            "preflight_content_readability",
            "not_recorded",
            inspected_artifact_count=0,
            note="Pass --evidence from `scoutfootball preflight --evidence-out`.",
        )

    # Shared validation keeps evidence-path rules identical to source-health.
    _inspections_by_path(evidence)
    artifacts = evidence.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("evidence_artifacts_invalid")
    inspections = [
        item.get("inspection")
        for item in artifacts
        if isinstance(item, dict) and isinstance(item.get("inspection"), dict)
    ]
    failures = [
        item.get("artifact_path")
        for item in artifacts
        if isinstance(item, dict)
        and isinstance(item.get("inspection"), dict)
        and not _inspection_is_ok(item["inspection"])
    ]
    return _status(
        "preflight_content_readability",
        "pass" if not failures else "fail",
        inspected_artifact_count=len(inspections),
        passing_artifact_count=len(inspections) - len(failures),
        failing_artifacts=failures,
        evidence_generated_at=evidence.get("generated_at"),
        note=(
            "This applies only to artifacts captured by the supplied local evidence; "
            "it does not assert repository-wide coverage or freshness."
        ),
    )


def _audit_rate_check(
    *,
    name: str,
    audit_kind: str,
    audit_summary: dict[str, dict[str, Any]],
    threshold: dict[str, Any] | None,
    note: str,
) -> dict[str, Any]:
    """Evaluate reviewed samples only against an explicit maintainer threshold."""
    observed = audit_summary[audit_kind]
    if threshold is None:
        status = "baseline_required"
        threshold_status = "not_recorded"
    elif observed["record_count"] < threshold["minimum_sample_count"]:
        status = "baseline_required"
        threshold_status = "insufficient_sample"
    elif observed["error_rate"] <= threshold["maximum_error_rate"]:
        status = "pass"
        threshold_status = "met"
    else:
        status = "fail"
        threshold_status = "not_met"
    return _status(
        name,
        status,
        audit_status="observed" if observed["record_count"] else "not_recorded",
        audited_sample_count=observed["record_count"],
        confirmed_correct_count=observed["confirmed_correct_count"],
        confirmed_error_count=observed["confirmed_error_count"],
        observed_error_rate=observed["error_rate"],
        audited_sources=observed["audited_sources"],
        correction_count=observed["correction_count"],
        threshold_status=threshold_status,
        threshold=(
            {
                "threshold_id": threshold["threshold_id"],
                "maximum_error_rate": threshold["maximum_error_rate"],
                "minimum_sample_count": threshold["minimum_sample_count"],
                "decision": threshold["decision"],
                "recorded_at": threshold["recorded_at"],
            }
            if threshold is not None
            else None
        ),
        note=note,
    )


def build_contract_quality_report(
    settings: PlatformSettings | None = None,
    *,
    preflight_evidence: dict[str, Any] | None = None,
    snapshot_ledger_path: str | None = None,
    policy_ledger_path: str | None = None,
    audit_ledger_path: str | None = None,
    threshold_ledger_path: str | None = None,
) -> dict[str, Any]:
    """Build a baseline for C1 quality SLOs without inventing thresholds."""
    settings = settings or PlatformSettings.from_root()
    registry = build_data_contract_registry()
    raw_contracts = [contract for contract in registry.contracts if contract.layer == "raw"]
    raw_without_license = [
        contract.artifact_id for contract in raw_contracts if contract.license is None
    ]
    policies = (
        latest_policy_by_source(read_source_policy_ledger(policy_ledger_path))
        if policy_ledger_path
        else {}
    )
    source_policy_gaps = [
        {
            "source_id": contract.license.source_name if contract.license else contract.artifact_id,
            "missing_fields": source_license_policy_status(
                contract.license,
                policies.get(contract.license.source_name) if contract.license else None,
            )["missing_fields"],
        }
        for contract in raw_contracts
        if source_license_policy_status(
            contract.license,
            policies.get(contract.license.source_name) if contract.license else None,
        )["status"]
        != "recorded"
    ]
    unrecorded_contracts = [
        contract.artifact_id for contract in registry.contracts if not contract.recorded
    ]
    snapshots = (
        latest_snapshot_by_source(read_source_snapshot_ledger(snapshot_ledger_path))
        if snapshot_ledger_path
        else {}
    )
    raw_source_ids = {
        contract.license.source_name for contract in raw_contracts if contract.license
    }
    recorded_snapshot_ids = sorted(raw_source_ids & set(snapshots))
    source_health = build_source_health_report(settings)
    unregistered_raw_directories = source_health["unregistered_raw_directories"]
    audit_summary = (
        summarize_quality_audits(read_quality_audit_ledger(audit_ledger_path))
        if audit_ledger_path
        else summarize_quality_audits([])
    )
    thresholds = (
        latest_threshold_by_kind(read_quality_threshold_ledger(threshold_ledger_path))
        if threshold_ledger_path
        else {}
    )

    checks = [
        _status(
            "registered_contracts",
            "pass" if not unrecorded_contracts else "fail",
            registered_contract_count=len(registry.contracts),
            unrecorded_contracts=unrecorded_contracts,
        ),
        _status(
            "raw_source_licenses",
            "pass" if not raw_without_license else "fail",
            registered_raw_source_count=len(raw_contracts),
            sources_with_license=len(raw_contracts) - len(raw_without_license),
            missing_license_contracts=raw_without_license,
        ),
        _status(
            "unregistered_raw_directories",
            "fail" if unregistered_raw_directories else "pass",
            unregistered_raw_directories=unregistered_raw_directories,
            unregistered_raw_directory_details=source_health[
                "unregistered_raw_directory_details"
            ],
            note=(
                "Observed raw directories must be registered with a source contract or "
                "kept outside the active data root; this check does not infer their rights."
            ),
        ),
        _status(
            "source_retention_and_deletion_policies",
            "pass" if not source_policy_gaps else "baseline_required",
            registered_raw_source_count=len(raw_contracts),
            sources_with_complete_policy=len(raw_contracts) - len(source_policy_gaps),
            sources_missing_policy=source_policy_gaps,
            note=(
                "A source license does not fill retention or deletion policy fields. "
                "This check does not invent terms from external license names."
            ),
        ),
        _preflight_check(preflight_evidence),
        _status(
            "explicit_source_snapshots",
            "baseline_required" if not recorded_snapshot_ids else "observed",
            registered_raw_source_count=len(raw_source_ids),
            explicit_snapshot_source_count=len(recorded_snapshot_ids),
            explicit_snapshot_sources=recorded_snapshot_ids,
            missing_snapshot_sources=sorted(raw_source_ids - set(recorded_snapshot_ids)),
            note=(
                "No universal freshness threshold is assumed. Local mtime is not a "
                "source snapshot date; add a dated ledger entry only when known."
            ),
        ),
        _audit_rate_check(
            name="identity_conflict_error_rate",
            audit_kind="identity_resolution",
            audit_summary=audit_summary,
            threshold=thresholds.get("identity_resolution"),
            note=(
                "Requires reviewed identity-resolution samples and a maintainer-selected "
                "threshold; unresolved or ambiguous identities are never treated as correct."
            ),
        ),
        _audit_rate_check(
            name="source_claim_error_rate",
            audit_kind="source_claim",
            audit_summary=audit_summary,
            threshold=thresholds.get("source_claim"),
            note=(
                "Requires reviewed external factual claims and a maintainer-selected "
                "threshold; contract presence alone is not proof that each claim is correct."
            ),
        ),
    ]
    failures = [check["name"] for check in checks if check["status"] == "fail"]
    pending = [
        check["name"]
        for check in checks
        if check["status"] in {"not_recorded", "baseline_required"}
    ]
    return {
        "report_type": "scoutfootball.contract_quality",
        "report_version": CONTRACT_QUALITY_VERSION,
        "generated_at": _now_iso(),
        "scope": {
            "recording_scope": "local contract registry and explicitly supplied local evidence",
            "snapshot_ledger_supplied": bool(snapshot_ledger_path),
            "policy_ledger_supplied": bool(policy_ledger_path),
            "audit_ledger_supplied": bool(audit_ledger_path),
            "threshold_ledger_supplied": bool(threshold_ledger_path),
            "preflight_evidence_supplied": preflight_evidence is not None,
        },
        "overall_status": "fail" if failures else ("incomplete" if pending else "pass"),
        "failed_checks": failures,
        "incomplete_checks": pending,
        "checks": checks,
        "limitations": [
            "This report does not upload data or contact remote sources.",
            (
                "It does not infer freshness, source truth, identity correctness, or a "
                "quality threshold from local file metadata."
            ),
            (
                "A non-empty unregistered raw directory blocks this report so legacy or "
                "unclassified files cannot be mistaken for contract-governed inputs."
            ),
            (
                "Observed snapshot coverage is an audit baseline, not a claim that "
                "unrecorded sources are invalid or stale."
            ),
            (
                "Reviewed audit samples are evaluated only after the maintainer records "
                "an applicable threshold and enough samples are present."
            ),
        ],
    }


def format_contract_quality_report(report: dict[str, Any]) -> str:
    """Render a compact human-readable summary for a local terminal."""
    lines = [f"Contract quality: {report['overall_status']}"]
    for check in report["checks"]:
        lines.append(f"  - {check['name']}: {check['status']}")
    if report["failed_checks"]:
        lines.append("  FAILED: " + ", ".join(report["failed_checks"]))
    if report["incomplete_checks"]:
        lines.append("  INCOMPLETE: " + ", ".join(report["incomplete_checks"]))
    return "\n".join(lines)

"""CLI entrypoint for ScoutFootball pipeline operations."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

from scoutfootball.architecture import (
    build_capability_registry,
    build_data_contract_registry,
    build_default_architecture,
)


def _local_file_provenance(path: Path) -> dict[str, object]:
    """Return reproducible metadata for an explicitly supplied local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "sha256": digest.hexdigest(),
        "size_bytes": path.stat().st_size,
    }


def _cmd_info(_args: argparse.Namespace) -> None:
    architecture = build_default_architecture()
    lines = [
        f"package: {architecture.package_name}",
        f"status: {architecture.status}",
        "modules:",
    ]
    lines.extend(
        f"  - {module.name}: {module.purpose}" for module in architecture.module_boundaries
    )
    lines.append("commands:")
    lines.extend(f"  - {command}" for command in architecture.supported_commands)
    print("\n".join(lines))


def _cmd_capabilities(args: argparse.Namespace) -> None:
    registry = build_capability_registry()

    if args.json:
        print(json.dumps(registry.model_dump(mode="json"), indent=2, ensure_ascii=False))
        return

    lines = [
        f"ScoutFootball capability registry (v{registry.package_version})",
        f"Generated: {registry.generated_at}",
        f"Total capabilities: {len(registry.capabilities)}",
        f"Domains ({len(registry.domains)}): {', '.join(registry.domains)}",
        "",
    ]

    if args.domain:
        caps = registry.by_domain(args.domain)
        if not caps:
            print(f"No capabilities found for domain: {args.domain}")
            sys.exit(1)
        lines.append(f"Domain: {args.domain} ({len(caps)} capabilities)")
    else:
        caps = registry.capabilities

    for cap in caps:
        lines.append(f"  [{cap.domain}] {cap.id} — {cap.name}")
        lines.append(f"      {cap.description}")
        lines.append(f"      status: {cap.status}")
        if cap.cli_commands:
            lines.append(f"      cli: {', '.join(cap.cli_commands)}")
        if cap.api_paths:
            lines.append(f"      api: {len(cap.api_paths)} paths")
        if cap.frontend_views:
            lines.append(f"      frontend: {', '.join(cap.frontend_views)}")
        if cap.data_artifacts:
            lines.append(f"      data: {len(cap.data_artifacts)} artifacts")
        lines.append("")

    if args.counts:
        status_counts = registry.count_by_status()
        lines.append("Status summary:")
        for status, count in sorted(status_counts.items()):
            lines.append(f"  {status}: {count}")

    print("\n".join(lines))


def _cmd_data_contracts(args: argparse.Namespace) -> None:
    registry = build_data_contract_registry()

    if args.json:
        print(json.dumps(registry.model_dump(mode="json"), indent=2, ensure_ascii=False))
        return

    lines = [
        f"ScoutFootball data contract registry (v{registry.package_version})",
        f"Generated: {registry.generated_at}",
        f"Total contracts: {len(registry.contracts)}",
        f"Layers ({len(registry.layers)}): {', '.join(registry.layers)}",
        "",
    ]

    if args.layer:
        contracts = registry.by_layer(args.layer)
        if not contracts:
            print(f"No contracts found for layer: {args.layer}")
            sys.exit(1)
        lines.append(f"Layer: {args.layer} ({len(contracts)} contracts)")
    else:
        contracts = registry.contracts

    for contract in contracts:
        lines.append(f"  [{contract.layer}] {contract.artifact_id}")
        lines.append(f"      {contract.purpose}")
        lines.append(f"      status: {contract.status}")
        if contract.license:
            lines.append(f"      license: {contract.license.license_name}")
        if contract.primary_keys:
            lines.append(f"      primary_keys: {', '.join(contract.primary_keys)}")
        if contract.columns:
            lines.append(f"      columns: {len(contract.columns)}")
        if not contract.recorded:
            lines.append(f"      recorded: false ({contract.recorded_note})")
        lines.append("")

    if args.counts:
        layer_counts = registry.count_by_layer()
        lines.append("Layer summary:")
        for layer, count in sorted(layer_counts.items()):
            lines.append(f"  {layer}: {count}")
        status_counts = registry.count_by_status()
        lines.append("Status summary:")
        for status, count in sorted(status_counts.items()):
            lines.append(f"  {status}: {count}")

    print("\n".join(lines))


def _cmd_list_adapters(args: argparse.Namespace) -> None:
    """List provider adapter manifests (I1: open interop baseline)."""
    from scoutfootball.adapters.registry import build_adapter_registry

    registry = build_adapter_registry()

    if args.json:
        print(json.dumps(registry.model_dump(mode="json"), indent=2, ensure_ascii=False))
        return

    manifests = registry.manifests
    if args.source:
        manifests = tuple(m for m in manifests if m.source_id == args.source)
        if not manifests:
            print(f"No adapter manifest found for source: {args.source}")
            sys.exit(1)
    if args.capability:
        from scoutfootball.adapters.manifest import AdapterCapability

        try:
            cap = AdapterCapability(args.capability)
        except ValueError:
            valid = ", ".join(c.value for c in AdapterCapability)
            print(
                f"Error: unknown capability '{args.capability}'. Valid: {valid}",
                file=sys.stderr,
            )
            sys.exit(1)
        manifests = tuple(m for m in manifests if cap in m.capabilities)

    lines = [
        f"ScoutFootball adapter registry (v{registry.package_version})",
        f"Generated: {registry.generated_at}",
        f"Total adapters: {len(registry.manifests)}",
        f"Maintained: {sum(1 for m in registry.manifests if m.maintained)}",
        "",
    ]
    for manifest in manifests:
        lines.append(f"  [{manifest.source_id}] {manifest.parser_version}")
        lines.append(f"      module: {manifest.module_path}")
        lines.append(f"      maintained: {manifest.maintained}")
        caps = ", ".join(c.value for c in manifest.capabilities)
        lines.append(f"      capabilities: {caps}")
        if manifest.ingestion_cli:
            lines.append(f"      cli: {manifest.ingestion_cli}")
        if manifest.artifact_paths:
            lines.append(f"      artifacts: {len(manifest.artifact_paths)} paths")
        if manifest.schema_mappings:
            direct = sum(1 for s in manifest.schema_mappings if s.conversion == "direct")
            lossy = len(manifest.schema_mappings) - direct
            lines.append(
                f"      schema_mappings: {len(manifest.schema_mappings)} "
                f"({direct} direct, {lossy} lossy)"
            )
        if manifest.conversion_loss_notes:
            note = manifest.conversion_loss_notes
            if len(note) > 120:
                note = note[:117] + "..."
            lines.append(f"      loss_notes: {note}")
        lines.append("")

    if args.verbose:
        lines.append("Schema mapping detail:")
        for manifest in manifests:
            if not manifest.schema_mappings:
                continue
            lines.append(f"  [{manifest.source_id}]")
            for mapping in manifest.schema_mappings:
                note = f" — {mapping.note}" if mapping.note else ""
                lines.append(
                    f"      {mapping.source_field} -> {mapping.internal_field} "
                    f"({mapping.conversion}){note}"
                )
            lines.append("")

    print("\n".join(lines))


def _cmd_adapter_compatibility(args: argparse.Namespace) -> None:
    """Show project-local adapter admission without running an ingester."""
    from scoutfootball.adapters.compatibility import build_adapter_compatibility_matrix

    matrix = build_adapter_compatibility_matrix()
    entries = matrix.entries
    if args.source:
        entries = tuple(entry for entry in entries if entry.source_id == args.source)
        if not entries:
            print(f"No adapter compatibility entry found for source: {args.source}")
            sys.exit(1)

    if args.json:
        payload = matrix.model_dump(mode="json")
        payload["entries"] = [entry.model_dump(mode="json") for entry in entries]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    lines = [
        f"ScoutFootball adapter compatibility (v{matrix.package_version})",
        "Admission is project-local; it is not an upstream license or publication decision.",
        "",
    ]
    for entry in entries:
        lines.append(f"  [{entry.source_id}] {entry.admission_status}")
        lines.append(f"      maintained: {entry.maintained}")
        lines.append(f"      contract_registered: {entry.contract_registered}")
        if entry.license_name:
            lines.append(f"      input_license: {entry.license_name}")
            lines.append(
                "      input_redistribution_allowed: "
                f"{entry.redistribution_allowed}"
            )
        if entry.ingestion_cli:
            lines.append(f"      cli: {entry.ingestion_cli}")
        for reason in entry.reasons:
            lines.append(f"      reason: {reason}")
        lines.append("")

    print("\n".join(lines))


def _cmd_ingest(args: argparse.Namespace) -> None:
    from scoutfootball.pipeline import run_daily_ingest

    results = run_daily_ingest(sources=tuple(args.sources))
    for source, status in results.items():
        print(f"  {source}: {status}")


def _cmd_build_features(_args: argparse.Namespace) -> None:
    from scoutfootball.pipeline import run_build_features

    results = run_build_features()
    for feature_set, status in results.items():
        print(f"  {feature_set}: {status}")


def _cmd_train(args: argparse.Namespace) -> None:
    from scoutfootball.pipeline import run_weekly_train

    # Default: skip training when pre-training validation fails (G0-B fail-closed).
    # --force overrides for debugging/explicit override at the maintainer's risk.
    results = run_weekly_train(skip_if_validation_fails=not args.force)
    for model, status in results.items():
        print(f"  {model}: {status}")


def _cmd_train_rating_nn(args: argparse.Namespace) -> None:
    from scoutfootball.evaluation.validation import run_pre_training_validation
    from scoutfootball.models.player_rating_nn import (
        PlayerRatingNNConfig,
        train_player_rating_nn_from_files,
    )

    # Default: skip training when pre-training validation fails (G0-B fail-closed).
    # --force overrides for debugging/explicit override at the maintainer's risk.
    # Mirrors the `train` command gate (Round 17 fix). Without this gate,
    # `train-rating-nn` would be a parallel ungated path to the same model
    # artifacts that `train` produces under gate — letting a maintainer
    # silently train an NN candidate on inconsistent data.
    report = run_pre_training_validation()
    if not args.force and not report.passed:
        print("Skipping training: pre-training validation failed.")
        print(report.summary())
        print("Run `scoutfootball validate` for details.")
        print("To train anyway, pass --force (at your own risk).")
        return

    result = train_player_rating_nn_from_files(
        config=PlayerRatingNNConfig(
            min_labels=args.min_labels,
            max_iter=args.max_iter,
            random_state=args.seed,
        ),
        output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
    )
    print(result.status)
    if result.metrics:
        print(json.dumps(result.metrics, indent=2, ensure_ascii=False))


def _cmd_validate(_args: argparse.Namespace) -> None:
    from scoutfootball.evaluation.validation import run_pre_training_validation

    report = run_pre_training_validation()
    print(report.summary())


def _cmd_source_health(args: argparse.Namespace) -> None:
    evidence = None
    if args.evidence:
        try:
            evidence = json.loads(Path(args.evidence).resolve().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Error: unable to read preflight evidence: {exc}", file=sys.stderr)
            sys.exit(1)
    from scoutfootball.evaluation.source_health import (
        build_source_health_report,
        format_source_health_report,
    )

    try:
        report = build_source_health_report(
            preflight_evidence=evidence,
            snapshot_ledger_path=args.snapshot_ledger,
            policy_ledger_path=args.policy_ledger,
        )
    except ValueError as exc:
        print(f"Error: invalid source-health input: {exc}", file=sys.stderr)
        sys.exit(1)
    output = (
        json.dumps(report, indent=2, ensure_ascii=False)
        if args.json
        else format_source_health_report(report)
    )
    print(output)


def _cmd_contract_quality(args: argparse.Namespace) -> None:
    """Report local contract-quality gates without inventing missing evidence."""
    evidence = None
    if args.evidence:
        try:
            evidence = json.loads(Path(args.evidence).resolve().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Error: unable to read preflight evidence: {exc}", file=sys.stderr)
            sys.exit(1)
    from scoutfootball.evaluation.contract_quality import (
        build_contract_quality_report,
        format_contract_quality_report,
    )

    try:
        report = build_contract_quality_report(
            preflight_evidence=evidence,
            snapshot_ledger_path=args.snapshot_ledger,
            policy_ledger_path=args.policy_ledger,
            audit_ledger_path=args.audit_ledger,
            threshold_ledger_path=args.threshold_ledger,
        )
    except ValueError as exc:
        print(f"Error: invalid contract-quality input: {exc}", file=sys.stderr)
        sys.exit(1)
    output = (
        json.dumps(report, indent=2, ensure_ascii=False)
        if args.json
        else format_contract_quality_report(report)
    )
    print(output)


def _cmd_model_admission(args: argparse.Namespace) -> None:
    """Show whether local optimizer runs contain evidence for human review."""
    from scoutfootball.evaluation.model_admission import (
        build_model_admission_report,
        format_model_admission_report,
    )
    report = build_model_admission_report(run_id=args.run_id)
    print(
        json.dumps(report, indent=2, ensure_ascii=False)
        if args.json
        else format_model_admission_report(report)
    )


def _cmd_research_health(_args: argparse.Namespace) -> None:
    """Report the five-layer research health of the rating system.

    PRS-0 R-003/R-004: a stale, unreviewable, synthetic or non-independent-label
    rating system must be reported as not ready, never hidden behind a top-level
    ``ok``. The verdict is fail-closed; see ``research_health.py``.
    """
    from scoutfootball.evaluation.research_health import build_research_health_report

    report = build_research_health_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))


def _cmd_discard_model_run(args: argparse.Namespace) -> None:
    """Discard one explicitly selected local optimizer candidate after confirmation."""
    from scoutfootball.config import PlatformSettings
    from scoutfootball.evaluation.model_run_lifecycle import (
        ModelRunLifecycleError,
        discard_optimizer_run,
        format_optimizer_run_discard,
    )

    try:
        report = discard_optimizer_run(
            PlatformSettings.from_root(),
            args.run_id,
            confirm=args.confirm,
            allow_incomplete=args.allow_incomplete,
        )
    except ModelRunLifecycleError as exc:
        print(f"Error: cannot discard model run: {exc}", file=sys.stderr)
        sys.exit(2)
    print(
        json.dumps(report, indent=2, ensure_ascii=False)
        if args.json
        else format_optimizer_run_discard(report)
    )


def _cmd_reject_model_run(args: argparse.Namespace) -> None:
    """Record an explicit local rejection without deleting a candidate."""
    from scoutfootball.config import PlatformSettings
    from scoutfootball.evaluation.model_run_lifecycle import (
        ModelRunLifecycleError,
        format_optimizer_run_action,
        reject_optimizer_run,
    )

    try:
        report = reject_optimizer_run(
            PlatformSettings.from_root(),
            args.run_id,
            decision=args.decision,
            confirm=args.confirm,
        )
    except ModelRunLifecycleError as exc:
        print(f"Error: cannot reject model run: {exc}", file=sys.stderr)
        sys.exit(2)
    print(
        json.dumps(report, indent=2, ensure_ascii=False)
        if args.json
        else format_optimizer_run_action(report)
    )


def _cmd_promote_model_run(args: argparse.Namespace) -> None:
    """Promote a reviewable candidate only after explicit confirmation."""
    from scoutfootball.config import PlatformSettings
    from scoutfootball.evaluation.model_run_lifecycle import (
        ModelRunLifecycleError,
        format_optimizer_run_action,
        promote_optimizer_run,
    )

    try:
        report = promote_optimizer_run(
            PlatformSettings.from_root(),
            args.run_id,
            decision=args.decision,
            confirm=args.confirm,
        )
    except ModelRunLifecycleError as exc:
        print(f"Error: cannot promote model run: {exc}", file=sys.stderr)
        sys.exit(2)
    print(
        json.dumps(report, indent=2, ensure_ascii=False)
        if args.json
        else format_optimizer_run_action(report)
    )


def _cmd_rollback_model_run(args: argparse.Namespace) -> None:
    """Restore a verified local active-artifact backup after confirmation."""
    from scoutfootball.config import PlatformSettings
    from scoutfootball.evaluation.model_run_lifecycle import (
        ModelRunLifecycleError,
        format_optimizer_run_action,
        rollback_optimizer_run,
    )

    try:
        report = rollback_optimizer_run(
            PlatformSettings.from_root(),
            args.backup_id,
            decision=args.decision,
            confirm=args.confirm,
        )
    except ModelRunLifecycleError as exc:
        print(f"Error: cannot roll back model run: {exc}", file=sys.stderr)
        sys.exit(2)
    print(
        json.dumps(report, indent=2, ensure_ascii=False)
        if args.json
        else format_optimizer_run_action(report)
    )


def _cmd_validate_decision_package(args: argparse.Namespace) -> None:
    """Validate one user-selected local decision-package JSON export."""
    from scoutfootball.evaluation.decision_package import (
        DecisionPackageValidationError,
        format_decision_package_report,
        validate_decision_package_file,
    )

    try:
        report = validate_decision_package_file(args.path)
    except DecisionPackageValidationError as exc:
        print(f"Error: cannot validate decision package: {exc}", file=sys.stderr)
        sys.exit(2)
    print(
        json.dumps(report, indent=2, ensure_ascii=False)
        if args.json
        else format_decision_package_report(report)
    )
    if report["status"] != "valid":
        sys.exit(2)


def _cmd_record_source_snapshot(args: argparse.Namespace) -> None:
    from scoutfootball.evaluation.source_snapshot_ledger import (
        append_source_snapshot_record,
        build_source_snapshot_record,
    )

    try:
        record = build_source_snapshot_record(
            source_id=args.source,
            snapshot_date=args.snapshot_date,
            evidence_path=args.evidence,
        )
        ledger = append_source_snapshot_record(record, args.ledger)
    except (ValueError, FileExistsError) as exc:
        print(f"Error: unable to record source snapshot: {exc}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps({"ledger": str(ledger), "record": record}, indent=2, ensure_ascii=False))
    else:
        print(f"Recorded local source snapshot: {record['snapshot_id']}")
        print(f"  Ledger: {ledger}")
        print(f"  Source: {record['source_id']}")
        print(f"  Declared snapshot date: {record['snapshot_date']}")


def _cmd_inspect_raw_source(args: argparse.Namespace) -> None:
    """Create local structural evidence for one registered raw CSV input."""
    from scoutfootball.evaluation.raw_source_inspection import (
        inspect_raw_csv,
        write_raw_source_inspection_report,
    )

    try:
        report = inspect_raw_csv(source_id=args.source, path=args.path)
        output = write_raw_source_inspection_report(
            report, args.evidence_out, overwrite=args.overwrite
        )
    except (ValueError, FileExistsError, OSError) as exc:
        print(f"Error: unable to inspect raw source file: {exc}", file=sys.stderr)
        sys.exit(1)
    result = {"evidence": str(output), "report": report}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Wrote local raw-source inspection: {output}")


def _cmd_reep_identity_lookup(args: argparse.Namespace) -> None:
    """Look up an exact provider ID in a local Reep identity snapshot."""
    from scoutfootball.evaluation.reep_identity import lookup_reep_provider_identity

    try:
        report = lookup_reep_provider_identity(
            provider=args.provider,
            provider_id=args.provider_id,
            path=args.path,
            limit=args.limit,
            snapshot_ledger_path=args.snapshot_ledger,
        )
    except (OSError, ValueError) as exc:
        print(f"Error: unable to look up Reep identity: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    print(f"Reep exact {report['lookup']['provider']} identity lookup: {report['status']}")
    print(f"  Matches: {report['match_count']} (returned {report['returned_count']})")
    print(f"  Snapshot: {report['source_snapshot']['status']}")
    for match in report["matches"]:
        print(
            "  - "
            f"{match['entity_type'] or 'unknown'}: "
            f"{match['full_name'] or match['name'] or match['reep_id'] or 'unnamed'}"
        )


def _cmd_record_source_policy(args: argparse.Namespace) -> None:
    """Preview or append an explicit local retention/deletion policy."""
    from scoutfootball.evaluation.source_policy_ledger import (
        append_source_policy_record,
        build_source_policy_record,
    )

    try:
        record = build_source_policy_record(
            source_id=args.source,
            retention_mode=args.retention_mode,
            retention_days=args.retention_days,
            deletion_trigger=args.deletion_trigger,
            deletion_strategy=args.deletion_strategy,
            derived_artifact_action=args.derived_artifact_action,
            decision=args.decision,
        )
        ledger = Path(args.ledger).resolve()
        if args.confirm:
            ledger = append_source_policy_record(record, ledger)
    except (ValueError, FileExistsError) as exc:
        print(f"Error: unable to record source policy: {exc}", file=sys.stderr)
        sys.exit(1)

    status = "recorded" if args.confirm else "preview"
    result = {"status": status, "ledger": str(ledger), "record": record}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.confirm:
        print(f"Recorded local source policy: {record['policy_id']}")
        print(f"  Ledger: {ledger}")
        print(f"  Source: {record['source_id']}")
        print(f"  Retention mode: {record['retention']['mode']}")
    else:
        print(f"Preview local source policy: {record['policy_id']}")
        print("  No files or ledger records were changed; rerun with --confirm to append.")


def _cmd_record_quality_audit(args: argparse.Namespace) -> None:
    """Preview or append one explicit maintainer-reviewed C1 audit sample."""
    from scoutfootball.evaluation.quality_audit_ledger import (
        append_quality_audit_record,
        build_quality_audit_record,
    )

    try:
        record = build_quality_audit_record(
            audit_kind=args.audit_kind,
            source_id=args.source,
            sample_id=args.sample_id,
            outcome=args.outcome,
            reviewer=args.reviewer,
            evidence_reference=args.evidence_reference,
            decision=args.decision,
            supersedes_audit_id=args.supersedes,
        )
        ledger = Path(args.ledger).resolve()
        if args.confirm:
            ledger = append_quality_audit_record(record, ledger)
    except (ValueError, FileExistsError) as exc:
        print(f"Error: unable to record quality audit: {exc}", file=sys.stderr)
        sys.exit(1)

    status = "recorded" if args.confirm else "preview"
    result = {"status": status, "ledger": str(ledger), "record": record}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.confirm:
        print(f"Recorded local quality audit: {record['audit_id']}")
        print(f"  Ledger: {ledger}")
        print(f"  Kind: {record['audit_kind']}")
        print(f"  Outcome: {record['outcome']}")
    else:
        print(f"Preview local quality audit: {record['audit_id']}")
        print("  No files or ledger records were changed; rerun with --confirm to append.")


def _cmd_record_quality_threshold(args: argparse.Namespace) -> None:
    """Preview or append a maintainer-selected quality threshold."""
    from scoutfootball.evaluation.quality_audit_ledger import (
        append_quality_threshold_record,
        build_quality_threshold_record,
    )

    try:
        record = build_quality_threshold_record(
            audit_kind=args.audit_kind,
            maximum_error_rate=args.maximum_error_rate,
            minimum_sample_count=args.minimum_sample_count,
            decision=args.decision,
        )
        ledger = Path(args.ledger).resolve()
        if args.confirm:
            ledger = append_quality_threshold_record(record, ledger)
    except (ValueError, FileExistsError) as exc:
        print(f"Error: unable to record quality threshold: {exc}", file=sys.stderr)
        sys.exit(1)

    status = "recorded" if args.confirm else "preview"
    result = {"status": status, "ledger": str(ledger), "record": record}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.confirm:
        print(f"Recorded local quality threshold: {record['threshold_id']}")
        print(f"  Ledger: {ledger}")
        print(f"  Kind: {record['audit_kind']}")
        print(f"  Maximum error rate: {record['maximum_error_rate']}")
    else:
        print(f"Preview local quality threshold: {record['threshold_id']}")
        print("  No files or ledger records were changed; rerun with --confirm to append.")


def _cmd_optimizer_preflight(args: argparse.Namespace) -> None:
    from scoutfootball.evaluation.optimizer_preflight import optimizer_preflight

    report = optimizer_preflight(Path(args.data_dir).resolve())
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["ready"]:
        sys.exit(2)


def _cmd_preflight(args: argparse.Namespace) -> None:
    """Content-level Parquet preflight across key data artifacts.

    Resolves footer-vs-content truth conflicts documented in AGENTS.md by
    fully decoding each file (DuckDB primary, pandas fallback) and comparing
    against footer metadata. Reports schema, row counts, null counts and a
    content fingerprint. Quarantine is opt-in and reversible.
    """
    from scoutfootball.config import PlatformSettings
    from scoutfootball.evaluation.parquet_preflight import (
        preflight_key_artifacts,
        preflight_parquet,
        quarantine_unreadable,
        summarize_reports,
    )

    settings = PlatformSettings.from_root()
    paths = list(args.paths) if args.paths else []

    if paths:
        # Explicit paths resolve against cwd (standard CLI behaviour), not
        # data_root. ``preflight_parquet`` keeps data_root-relative resolution
        # for the key-artifact path used by ``--target``.
        abs_paths = [Path(p).resolve() for p in paths]
        reports = [preflight_parquet(p, settings) for p in abs_paths]
    else:
        reports = preflight_key_artifacts(target=args.target, settings=settings)

    fmt = "json" if args.json else "text"
    print(summarize_reports(reports, fmt=fmt))

    if args.evidence_out:
        from scoutfootball.evaluation.preflight_evidence import (
            build_preflight_evidence_report,
            write_preflight_evidence_report,
        )

        try:
            evidence = build_preflight_evidence_report(
                reports,
                target=args.target if not paths else "explicit_paths",
            )
            output = write_preflight_evidence_report(
                evidence,
                Path(args.evidence_out),
                overwrite=args.overwrite_evidence,
            )
        except OSError as exc:
            print(f"Unable to write evidence report: {exc}", file=sys.stderr)
            sys.exit(2)
        print(f"Evidence report: {output}", file=sys.stderr)

    if args.quarantine:
        result = quarantine_unreadable(reports, settings, dry_run=False)
        if result.moved:
            print(f"\nQuarantined {len(result.moved)} unreadable file(s):")
            for p in result.moved:
                print(f"  - {p}")
            if result.manifest_path:
                print(f"Manifest: {result.manifest_path}")
        else:
            print("\nNo unreadable files to quarantine.")

    # Exit non-zero when any file failed to decode, so CI can gate on it.
    if any(not r.ok for r in reports):
        sys.exit(2)


def _cmd_import_truth_labels(args: argparse.Namespace) -> None:
    """Import scouting workspace review decisions as truth labels."""
    import json as _json
    from pathlib import Path as _Path

    from scoutfootball.evaluation.truth_labels import (
        create_empty_truth_labels,
        merge_truth_label_rows,
        validate_truth_labels,
        workspace_to_truth_labels,
    )

    workspace_path = _Path(args.workspace).resolve()
    if not workspace_path.exists():
        print(f"Error: workspace file not found: {workspace_path}")
        sys.exit(1)

    with open(workspace_path, encoding="utf-8") as f:
        workspace = _json.load(f)

    new_labels = workspace_to_truth_labels(
        workspace,
        default_season=args.season or "",
        default_position_scope=args.position_scope or "all",
    )

    if new_labels.empty:
        print("No approved/rejected decisions found in workspace. Nothing to import.")
        return

    # Merge with existing truth labels if present
    output_path = _Path(args.output).resolve()
    existing = pd.read_parquet(output_path) if output_path.exists() else create_empty_truth_labels()
    combined, _replaced = merge_truth_label_rows(existing, new_labels)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    errors = validate_truth_labels(combined)
    if errors:
        print("Validation errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    combined.to_parquet(output_path, index=False)
    print(f"Imported {len(new_labels)} scouting review labels to {output_path}")
    print(f"  Approved: {(new_labels['label_value'] == 1.0).sum()}")
    print(f"  Rejected: {(new_labels['label_value'] == 0.0).sum()}")
    print(f"  Total labels in file: {len(combined)}")


def _transfermarkt_feature_coverage(
    labels: pd.DataFrame,
    feature_matrix_path: Path,
) -> dict[str, object]:
    """Report whether a local snapshot can resolve to the current rating matrix."""
    if not feature_matrix_path.exists():
        return {"status": "not_checked", "reason": "rating_feature_matrix_not_found"}
    try:
        features = pd.read_parquet(feature_matrix_path, columns=["player_id", "season_id"])
    except Exception as exc:
        return {
            "status": "not_checked",
            "reason": f"feature_matrix_unreadable:{type(exc).__name__}",
        }
    if not {"player_id", "season_id"}.issubset(features.columns):
        return {"status": "not_checked", "reason": "feature_matrix_missing_join_columns"}

    def _name(value: object) -> str:
        return str(value).split("|", maxsplit=1)[0].strip().casefold()

    label_keys = {
        (_name(row.player_id), str(row.season))
        for row in labels[["player_id", "season"]].itertuples(index=False)
    }
    feature_keys = {
        (_name(row.player_id), str(row.season_id))
        for row in features[["player_id", "season_id"]].itertuples(index=False)
    }
    matched = label_keys & feature_keys
    return {
        "status": "checked",
        "unique_player_seasons": len(label_keys),
        "matched_player_seasons": len(matched),
        "unmatched_player_seasons": len(label_keys - matched),
    }


def _cmd_import_transfermarkt_truth_labels(args: argparse.Namespace) -> None:
    """Import a dated, local Transfermarkt snapshot as independent proxy labels."""
    from scoutfootball.adapters.transfermarkt_manual import load_snapshot, snapshot_to_truth_labels
    from scoutfootball.evaluation.transfermarkt_identity import (
        apply_resolved_transfermarkt_identities,
        apply_transfermarkt_identity_review_decisions,
        resolve_transfermarkt_snapshot_identities,
        transfermarkt_identity_report,
    )
    from scoutfootball.evaluation.truth_labels import (
        create_empty_truth_labels,
        merge_truth_label_rows,
        truth_label_supervision_report,
        validate_truth_labels,
    )

    snapshot_path = Path(args.snapshot).resolve()
    if not snapshot_path.exists():
        print(f"Error: snapshot file not found: {snapshot_path}")
        sys.exit(1)
    feature_matrix_path = Path(args.feature_matrix).resolve()
    if not feature_matrix_path.exists():
        print(f"Error: feature matrix file not found: {feature_matrix_path}")
        sys.exit(1)
    try:
        input_provenance = {
            "snapshot": _local_file_provenance(snapshot_path),
            "feature_matrix": _local_file_provenance(feature_matrix_path),
        }
    except OSError as exc:
        print(f"Error: unable to fingerprint local import inputs: {exc}")
        sys.exit(1)
    try:
        source_labels = snapshot_to_truth_labels(
            snapshot_path,
            args.season,
            confidence=args.confidence,
            as_of_date=args.as_of_date,
        )
    except Exception as exc:
        print(f"Error: unable to prepare Transfermarkt labels: {exc}")
        sys.exit(1)

    try:
        snapshot = load_snapshot(snapshot_path).dataframe
        feature_matrix = pd.read_parquet(feature_matrix_path)
        initial_identities = resolve_transfermarkt_snapshot_identities(
            snapshot,
            feature_matrix,
            season=args.season,
        )
        identities, identity_review = apply_transfermarkt_identity_review_decisions(
            initial_identities,
            snapshot_sha256=str(input_provenance["snapshot"]["sha256"]),
            feature_matrix_sha256=str(input_provenance["feature_matrix"]["sha256"]),
            season=args.season,
            ledger_path=args.identity_ledger,
        )
    except Exception as exc:
        print(f"Error: unable to resolve Transfermarkt identities: {exc}")
        sys.exit(1)
    identity = transfermarkt_identity_report(identities)
    identity["review_decisions"] = identity_review
    new_labels = apply_resolved_transfermarkt_identities(source_labels, identities)

    output_path = Path(args.output).resolve()
    try:
        existing = (
            pd.read_parquet(output_path)
            if output_path.exists()
            else create_empty_truth_labels()
        )
        combined, replaced_rows = merge_truth_label_rows(existing, new_labels)
    except (OSError, ValueError) as exc:
        print(f"Error: unable to load or merge existing truth labels: {exc}")
        sys.exit(1)

    errors = validate_truth_labels(combined)
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    report = truth_label_supervision_report(combined)
    summary = {
        "source": "transfermarkt_value",
        "input_provenance": input_provenance,
        "season": str(args.season),
        "incoming_rows": int(len(new_labels)),
        "replaced_rows": replaced_rows,
        "total_rows": int(len(combined)),
        "as_of_date_min": str(new_labels["as_of_date"].min()),
        "as_of_date_max": str(new_labels["as_of_date"].max()),
        "identity": identity,
        "temporal": report["temporal"],
        "dry_run": bool(args.dry_run),
    }
    if args.dry_run:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    identity_path = (
        Path(args.identity_report).resolve()
        if args.identity_report
        else output_path.with_name("transfermarkt_identity_report.json")
    )
    identity_payload = {
        "schema": "scoutfootball.transfermarkt-identity-report",
        "version": "1.1.0",
        **identity,
        "season": str(args.season),
        "input_provenance": input_provenance,
        "mappings": identities.mappings.to_dict(orient="records"),
        "review_queue": identities.review_queue.to_dict(orient="records"),
        "review_context": initial_identities.review_queue.to_dict(orient="records"),
        "unresolved": identities.unresolved.to_dict(orient="records"),
    }
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    identity_path.write_text(
        json.dumps(identity_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if new_labels.empty:
        print("No deterministic Transfermarkt identities resolved; no truth labels were written.")
        print(f"  Identity review report: {identity_path}")
        print(
            f"  Review rows: {identity['review_rows']}; "
            f"unresolved rows: {identity['unresolved_rows']}",
        )
        return

    from scoutfootball.evaluation.transfermarkt_label_reconciliation import (
        append_transfermarkt_label_import_records,
        build_transfermarkt_label_import_records,
        write_truth_labels_atomically,
    )

    label_ledger = (
        Path(args.label_ledger).resolve()
        if args.label_ledger
        else output_path.with_name("transfermarkt_truth_label_import_ledger.jsonl")
    )
    try:
        import_records = build_transfermarkt_label_import_records(
            source_labels,
            identities.mappings,
            input_provenance=input_provenance,
            season=str(args.season),
            labels_path=output_path,
        )
        write_truth_labels_atomically(combined, output_path)
        append_transfermarkt_label_import_records(import_records, label_ledger)
    except (OSError, ValueError) as exc:
        print(
            "Error: labels may have been written but their reconciliation ledger was not "
            f"updated: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Imported {len(new_labels)} dated Transfermarkt labels to {output_path}")
    print(f"  Replaced matching player-season-source rows: {replaced_rows}")
    print(f"  Source snapshot dates: {summary['as_of_date_min']} to {summary['as_of_date_max']}")
    print(f"  Deterministic identity matches: {identity['mapped_rows']} / {identity['total_rows']}")
    print(f"  Identity review report: {identity_path}")
    print(f"  Reconciliation label ledger: {label_ledger}")
    print(f"  Total labels in file: {len(combined)}")


def _cmd_transfermarkt_identity_review(args: argparse.Namespace) -> None:
    """Append one explicit local decision for a Transfermarkt review row."""
    from scoutfootball.evaluation.transfermarkt_identity_review import (
        append_review_decision_from_report,
    )

    try:
        record = append_review_decision_from_report(
            args.report,
            args.ledger,
            source_row=args.source_row,
            action=args.action,
            canonical_player_id=args.canonical_player_id,
            reason=args.reason,
        )
    except (OSError, ValueError) as exc:
        print(f"Error: unable to record identity review decision: {exc}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"ledger": str(Path(args.ledger).resolve()), "decision": record}, indent=2))


def _cmd_reconcile_transfermarkt_truth_labels(args: argparse.Namespace) -> None:
    """Preview or apply narrowly proven removals after identity revocation."""
    from scoutfootball.evaluation.transfermarkt_label_reconciliation import (
        reconcile_revoked_transfermarkt_labels,
        write_truth_labels_atomically,
    )

    labels_path = Path(args.labels).resolve()
    if not labels_path.exists():
        print(f"Error: truth labels file not found: {labels_path}", file=sys.stderr)
        sys.exit(1)
    try:
        labels = pd.read_parquet(labels_path)
        reconciled, report = reconcile_revoked_transfermarkt_labels(
            labels,
            identity_ledger_path=args.identity_ledger,
            label_ledger_path=args.label_ledger,
        )
    except (OSError, ValueError) as exc:
        print(f"Error: unable to reconcile Transfermarkt labels: {exc}", file=sys.stderr)
        sys.exit(1)
    report["dry_run"] = not args.apply
    report["labels_path"] = str(labels_path)
    if args.apply:
        try:
            write_truth_labels_atomically(reconciled, labels_path)
        except OSError as exc:
            print(f"Error: unable to write reconciled truth labels: {exc}", file=sys.stderr)
            sys.exit(1)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def _cmd_audit_truth_labels(args: argparse.Namespace) -> None:
    """Audit source-policy eligibility before rating supervision is enabled."""
    from scoutfootball.evaluation.truth_labels import truth_label_supervision_report

    path = Path(args.input).resolve()
    if not path.exists():
        print(f"Error: truth labels file not found: {path}")
        sys.exit(1)
    report = truth_label_supervision_report(pd.read_parquet(path))
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    print("Truth-label supervision audit (source-policy-v1)")
    print(f"  Total rows: {report['total_rows']}")
    print(f"  Eligible rows: {report['eligible_rows']}")
    print(f"  Excluded rows: {report['excluded_rows']}")
    for source, count in report["excluded_source_counts"].items():
        print(f"  Excluded {source}: {count}")
    print(f"  Status: {report['status']}")
    temporal = report["temporal"]
    print(f"  Temporally eligible: {temporal['temporally_eligible_rows']}")
    print(f"  Post-season snapshots: {temporal['post_season_rows']}")
    print(f"  Note: {report['caveat']}")


def _cmd_serve(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. Run: uv add uvicorn")
        sys.exit(1)

    from scoutfootball.api_server import create_app

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)


# ── Tournament subcommands ───────────────────────────────────────────────


def _tournament_load_state(args: argparse.Namespace):
    """Load tournament state from path or default location."""
    from scoutfootball.worldcup.tournament import DEFAULT_STATE_PATH, init_state, load_state

    path = args.state_path or DEFAULT_STATE_PATH
    try:
        return load_state(path)
    except FileNotFoundError:
        if args.state_path:
            print(f"Error: state file not found: {path}")
            sys.exit(1)
        # No default state file yet — return a fresh one
        return init_state()


def _cmd_tournament_show(args: argparse.Namespace) -> None:

    from scoutfootball.worldcup.tournament import tournament_summary

    state = _tournament_load_state(args)
    summary = tournament_summary(state)

    print(
        f"Tournament state: {summary['completed_matches']}/{summary['total_matches']} "
        f"matches played ({summary['completion_rate']:.1%})"
    )
    print(
        f"  Groups complete: {summary['groups_complete']}/{summary['total_groups']}  "
        f"Schema: {summary['schema_version']}"
    )
    adv = summary["advancing"]
    print(
        f"  Advancing: {len(adv['winners'])} winners, "
        f"{len(adv['runners_up'])} runners-up, "
        f"{len(adv['best_thirds'])} best thirds"
    )
    if adv.get("provisional"):
        print("  (Provisional — group stage not yet complete)")

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    print("\nStandings:")
    for letter in sorted(summary["standings"]):
        rows = summary["standings"][letter]
        print(f"\n  Group {letter}:")
        header = (
            f"    {'#':<3}{'Team':<24}{'P':>3}{'W':>3}{'D':>3}{'L':>3}"
            f"{'GF':>4}{'GA':>4}{'GD':>4}{'Pts':>4}"
        )
        print(header)
        for i, s in enumerate(rows, 1):
            print(
                f"    {i:<3}{s['team']:<24}{s['played']:>3}{s['won']:>3}"
                f"{s['drawn']:>3}{s['lost']:>3}{s['goals_for']:>4}"
                f"{s['goals_against']:>4}{s['goal_difference']:>4}{s['points']:>4}"
            )

    thirds = summary["best_thirds"]
    if thirds:
        print("\nBest third-placed teams:")
        for i, t in enumerate(thirds, 1):
            tag = " (qualified)" if i <= 8 else ""
            prov = " [provisional]" if t.get("provisional") else ""
            print(
                f"  {i}. {t['team']:<24} pts={t['points']} gd={t['goal_difference']} "
                f"gf={t['goals_for']}{tag}{prov}"
            )
        if summary["advancing"].get("provisional"):
            print("  (Provisional — group stage not yet complete)")


def _cmd_tournament_standings(args: argparse.Namespace) -> None:
    from dataclasses import asdict

    from scoutfootball.worldcup.tournament import compute_all_standings, compute_group_standings

    state = _tournament_load_state(args)
    if args.group:
        letter = args.group.upper()
        try:
            standings = compute_group_standings(state, letter)
        except KeyError:
            print(f"Error: unknown group '{letter}'. Valid: A-L")
            sys.exit(1)
        groups = {letter: standings}
    else:
        groups = compute_all_standings(state)

    if args.json:
        out = {k: [asdict(s) for s in v] for k, v in groups.items()}
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    for letter in sorted(groups):
        print(f"\nGroup {letter}:")
        print(
            f"  {'#':<3}{'Team':<24}{'P':>3}{'W':>3}{'D':>3}{'L':>3}"
            f"{'GF':>4}{'GA':>4}{'GD':>4}{'Pts':>4}"
        )
        for i, s in enumerate(groups[letter], 1):
            print(
                f"  {i:<3}{s.team:<24}{s.played:>3}{s.won:>3}{s.drawn:>3}"
                f"{s.lost:>3}{s.goals_for:>4}{s.goals_against:>4}"
                f"{s.goal_difference:>4}{s.points:>4}"
            )


def _cmd_tournament_apply(args: argparse.Namespace) -> None:

    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        apply_result,
        compute_group_standings,
        save_state,
    )

    state = _tournament_load_state(args)
    match_id = args.match_id
    match = state.match_by_id(match_id)
    if not match:
        print(f"Error: match id '{match_id}' not found")
        sys.exit(1)

    ok = apply_result(state, match_id, args.home_goals, args.away_goals)
    if not ok:
        print(
            f"Error: failed to apply result {args.home_goals}-{args.away_goals} "
            f"to {match_id}"
        )
        sys.exit(1)

    out_path = args.state_path or DEFAULT_STATE_PATH
    save_state(state, out_path)
    print(
        f"Recorded {match['home']} {args.home_goals}-{args.away_goals} "
        f"{match['away']}  ({match_id})"
    )
    print(f"State saved to {out_path}")

    if not args.quiet:
        group = match.get("group")
        if group:
            standings = compute_group_standings(state, group)
            print(f"\nGroup {group} standings:")
            for i, s in enumerate(standings, 1):
                marker = " *" if s.team in (match["home"], match["away"]) else "  "
                print(
                    f"{marker}{i}. {s.team:<22} P{s.played} W{s.won} D{s.drawn} "
                    f"L{s.lost} GD{s.goal_difference:+d} Pts{s.points}"
                )


def _cmd_tournament_clear(args: argparse.Namespace) -> None:
    from scoutfootball.worldcup.tournament import DEFAULT_STATE_PATH, clear_result, save_state

    state = _tournament_load_state(args)
    if not clear_result(state, args.match_id):
        print(f"No result recorded for {args.match_id}")
        return
    out_path = args.state_path or DEFAULT_STATE_PATH
    save_state(state, out_path)
    print(f"Cleared result for {args.match_id}")
    print(f"State saved to {out_path}")


def _cmd_tournament_reset(args: argparse.Namespace) -> None:
    from scoutfootball.worldcup.tournament import DEFAULT_STATE_PATH, init_state, save_state

    if not args.force:
        confirm = input("Reset all tournament results? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return
    state = init_state()
    out_path = args.state_path or DEFAULT_STATE_PATH
    save_state(state, out_path)
    print(f"Tournament state reset. Saved to {out_path}")


def _cmd_tournament_scenarios(args: argparse.Namespace) -> None:
    from dataclasses import asdict

    from scoutfootball.worldcup.tournament import compute_team_scenarios

    state = _tournament_load_state(args)
    team = args.team
    try:
        result = compute_team_scenarios(state, team, max_scenarios=args.max_scenarios)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    if args.json:
        out = {
            "team": result.team,
            "group": result.group,
            "current_standing": result.current_standing,
            "remaining_matches": result.remaining_matches,
            "advance_probability": result.advance_probability,
            "scenarios": [asdict(s) for s in result.scenarios],
            "summary": result.summary,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    print(f"Scenarios for {result.team} (Group {result.group})")
    cs = result.current_standing
    print(
        f"  Current: P{cs.get('played', 0)} W{cs.get('won', 0)} D{cs.get('drawn', 0)} "
        f"L{cs.get('lost', 0)} GD{cs.get('goal_difference', 0):+d} Pts{cs.get('points', 0)}"
    )
    print(f"  Remaining matches: {len(result.remaining_matches)}")
    for m in result.remaining_matches:
        print(f"    - {m['home']} vs {m['away']} (md{m['matchday']})")
    print(f"\n  Advance probability: {result.advance_probability:.1%}")
    print(f"  {result.summary}")

    if result.scenarios:
        print(f"\n  Sample scenarios (up to {len(result.scenarios)}):")
        for i, sc in enumerate(result.scenarios, 1):
            tag = "ADVANCES" if sc.advances else "eliminated"
            print(f"    {i}. [{sc.advance_path}] {tag}")
            print(f"       {sc.description}")
            for r in sc.results[:3]:
                print(
                    f"         {r['home']} {r.get('home_outcome', '?')} vs "
                    f"{r.get('away_outcome', '?')} {r['away']}"
                )
            if len(sc.results) > 3:
                print(f"         ... and {len(sc.results) - 3} more")


def _cmd_tournament_matches(args: argparse.Namespace) -> None:
    from scoutfootball.worldcup.tournament import _match_completed

    state = _tournament_load_state(args)
    group = args.group.upper() if args.group else None
    only_pending = args.pending

    rows = []
    for m in state.matches:
        if group and m.get("group") != group:
            continue
        result = state.results.get(m["match_id"])
        is_done = _match_completed(result)
        if only_pending and is_done:
            continue
        rows.append((m, result, is_done))

    if args.json:
        out = []
        for m, result, _ in rows:
            entry = {"match_id": m["match_id"], **m}
            if result:
                entry["result"] = result
            out.append(entry)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    print(f"{'Match ID':<42}{'Group':<6}{'MD':<4}{'Home':<22}{'Away':<22}{'Score':<8}")
    print("-" * 104)
    for m, result, is_done in rows:
        score = (
            f"{result['home_goals']}-{result['away_goals']}" if is_done else "  -  "
        )
        print(
            f"{m['match_id']:<42}{m.get('group', '-'):<6}{m.get('matchday', '-'):<4}"
            f"{m['home']:<22}{m['away']:<22}{score:<8}"
        )
    print(f"\n{len(rows)} matches shown.")


def _cmd_tournament_qualification(args: argparse.Namespace) -> None:
    """Show local best-third cutoff impact for one group."""
    from scoutfootball.worldcup.tournament import qualification_impact

    try:
        impact = qualification_impact(_tournament_load_state(args), args.group)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(impact, indent=2, ensure_ascii=False))
        return
    third = impact["third_place"]
    print(f"Group {impact['group']} local qualification impact")
    print(f"Recorded: {impact['matches_recorded']}/6; remaining: {impact['matches_remaining']}")
    print(
        f"Third: {third['team']} | rank {third['rank']}/{third['cutoff_rank']} | "
        f"{'inside' if third['currently_within_cutoff'] else 'outside'} current cutoff"
    )
    print("Status: provisional" if impact["provisional"] else "Status: group complete")


def _cmd_tournament_tiebreaks(args: argparse.Namespace) -> None:
    """Show local tied-cluster and head-to-head availability diagnostics."""
    from scoutfootball.worldcup.tournament import group_tiebreak_diagnostics

    try:
        diagnostics = group_tiebreak_diagnostics(_tournament_load_state(args), args.group)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(diagnostics, indent=2, ensure_ascii=False))
        return
    print(f"Group {diagnostics['group']} local tiebreak diagnostics")
    clusters = diagnostics["tied_clusters"]
    if not clusters:
        print("No current ties on points, goal difference, and goals scored.")
        return
    for cluster in clusters:
        teams = ", ".join(cluster["teams"])
        status = "available" if cluster["head_to_head_available"] else "incomplete; provisional"
        print(
            f"Positions {cluster['positions']}: {teams} | H2H "
            f"{cluster['head_to_head_matches_recorded']}/"
            f"{cluster['head_to_head_matches_required']} ({status})"
        )


def _cmd_tournament_knockout_generate(args: argparse.Namespace) -> None:
    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        generate_knockout_bracket,
        save_state,
    )

    state = _tournament_load_state(args)
    try:
        ko = generate_knockout_bracket(state)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    state.knockout = ko
    out_path = args.state_path or DEFAULT_STATE_PATH
    save_state(state, out_path)
    provisional = "(provisional — group stage incomplete)" if ko["provisional"] else ""
    print(f"Knockout bracket generated. {provisional}")
    print(f"  {len(ko['matches'])} matches (R32 → Final)")
    print(f"  Saved to {out_path}")


def _cmd_tournament_knockout_show(args: argparse.Namespace) -> None:
    state = _tournament_load_state(args)
    ko = state.knockout
    if not ko or not ko.get("matches"):
        print("No knockout bracket generated. Run `tournament knockout generate` first.")
        return

    overview = _get_knockout_overview(state)
    if args.json:
        print(json.dumps(overview, indent=2, ensure_ascii=False, default=str))
        return

    champ = ko.get("champion")
    if champ:
        print(f"🏆 Champion: {champ}\n")
    else:
        prov = "(provisional)" if ko.get("provisional") else ""
        print(f"Knockout bracket {prov}\n")

    round_labels = {
        "r32": "Round of 32",
        "r16": "Round of 16",
        "qf": "Quarter-Finals",
        "sf": "Semi-Finals",
        "final": "Final",
    }
    for code in ["r32", "r16", "qf", "sf", "final"]:
        matches = [m for m in ko["matches"] if m.get("round") == code]
        if not matches:
            continue
        print(f"  {round_labels.get(code, code)}:")
        for m in matches:
            home = m.get("home") or "TBD"
            away = m.get("away") or "TBD"
            hg = m.get("home_goals")
            ag = m.get("away_goals")
            if hg is not None:
                score = f"{hg}-{ag}"
                winner = m.get("winner", "")
                pen = " (pen)" if m.get("decided_by") == "penalties" else ""
                print(f"    {m['match_id']}: {home} {score} {away}{pen} → {winner}")
            else:
                print(f"    {m['match_id']}: {home} vs {away}")


def _get_knockout_overview(state):
    from scoutfootball.worldcup.tournament import get_knockout_overview

    return get_knockout_overview(state)


def _cmd_tournament_knockout_apply(args: argparse.Namespace) -> None:
    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        apply_knockout_result,
        save_state,
    )

    state = _tournament_load_state(args)
    try:
        apply_knockout_result(
            state,
            args.match_id,
            args.home_goals,
            args.away_goals,
            penalties_winner=args.penalties_winner,
        )
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    out_path = args.state_path or DEFAULT_STATE_PATH
    save_state(state, out_path)

    match = state.knockout_match_by_id(args.match_id)
    print(f"Recorded {match['home']} {args.home_goals}-{args.away_goals} {match['away']}")
    if args.home_goals == args.away_goals and args.penalties_winner:
        print(f"  (Penalties: {args.penalties_winner})")
    print(f"  Winner: {match['winner']}")
    print(f"  Saved to {out_path}")


def _cmd_tournament_knockout_clear(args: argparse.Namespace) -> None:
    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        clear_knockout_result,
        save_state,
    )

    state = _tournament_load_state(args)
    try:
        clear_knockout_result(state, args.match_id)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    out_path = args.state_path or DEFAULT_STATE_PATH
    save_state(state, out_path)
    print(f"Cleared knockout result for {args.match_id}")
    print("  (Downstream matches also cleared)")
    print(f"  Saved to {out_path}")


def _cmd_tournament_knockout(args: argparse.Namespace) -> None:
    """Dispatch to knockout sub-actions."""
    action = args.knockout_action
    handler = {
        "generate": _cmd_tournament_knockout_generate,
        "show": _cmd_tournament_knockout_show,
        "apply": _cmd_tournament_knockout_apply,
        "clear": _cmd_tournament_knockout_clear,
    }.get(action)
    if handler is None:
        print(f"Unknown knockout action: {action}")
        sys.exit(1)
    handler(args)


def _cmd_tournament(args: argparse.Namespace) -> None:
    """Dispatch to tournament sub-actions."""
    action = args.tournament_action
    if action == "knockout":
        _cmd_tournament_knockout(args)
        return
    handler = {
        "show": _cmd_tournament_show,
        "standings": _cmd_tournament_standings,
        "apply": _cmd_tournament_apply,
        "clear": _cmd_tournament_clear,
        "reset": _cmd_tournament_reset,
        "scenarios": _cmd_tournament_scenarios,
        "matches": _cmd_tournament_matches,
        "qualification": _cmd_tournament_qualification,
        "tiebreaks": _cmd_tournament_tiebreaks,
    }.get(action)
    if handler is None:
        print(f"Unknown tournament action: {action}")
        sys.exit(1)
    handler(args)


def _cmd_action_value(args: argparse.Namespace) -> None:
    from scoutfootball.action_value.aggregate import (
        build_player_action_value,
        save_player_action_value,
    )
    from scoutfootball.action_value.spadl_adapter import convert_all_events_to_actions

    project_root = Path(__file__).resolve().parents[2]
    events_path = Path(args.events_path) if args.events_path else (
        project_root / "data" / "raw" / "statsbomb_open" / "events_all.parquet"
    )
    output_path = Path(args.output_path) if args.output_path else (
        project_root / "data" / "gold" / "feature_store" / "player_value_metrics.parquet"
    )

    if not events_path.exists():
        print(f"Error: Events file not found: {events_path}")
        sys.exit(1)

    # Load events for both conversion and shot/xG stats
    events_df = pd.read_parquet(events_path)
    print(f"  Loaded {len(events_df)} events from {events_path}")

    # Convert to InternalActions
    actions = convert_all_events_to_actions(events_path)
    print(f"  Converted to {len(actions)} internal actions")

    if not actions:
        print("Error: No actions converted from events.")
        sys.exit(1)

    # Build player name mapping
    player_names = {}
    if "player_id" in events_df.columns and "player_name" in events_df.columns:
        name_map = (
            events_df.dropna(subset=["player_id", "player_name"])
            .drop_duplicates("player_id")
        )
        for _, row in name_map.iterrows():
            pid = str(int(float(row["player_id"])))
            player_names[pid] = row["player_name"]

    # Compute xT and aggregate
    result = build_player_action_value(
        actions=actions,
        events_df=events_df,
        player_names=player_names,
    )

    if result.empty:
        print("Error: No player action values computed.")
        sys.exit(1)

    # Save
    save_player_action_value(result, output_path)
    print(f"  Saved {len(result)} players to {output_path}")
    print("  Top players by composite score:")
    for _, row in result.head(5).iterrows():
        name = row.get("player_name", row.get("player_id", "?"))
        score = row.get("composite_score", 0)
        xt = row.get("total_xt", 0)
        print(f"    {name}: composite={score:.1f}, total_xT={xt:.4f}")


def _cmd_action_value_matches(args: argparse.Namespace) -> None:
    """Create the explicitly sample-bounded player-team-match xT artifact."""
    from scoutfootball.action_value.match_artifact import (
        build_player_match_action_values,
        save_player_match_action_values,
    )
    from scoutfootball.action_value.spadl_adapter import convert_all_events
    from scoutfootball.action_value.xt import compute_xt_values

    project_root = Path(__file__).resolve().parents[2]
    events_path = Path(args.events_path) if args.events_path else (
        project_root / "data" / "raw" / "statsbomb_open" / "events_sample.parquet"
    )
    matches_path = Path(args.matches_path) if args.matches_path else (
        project_root / "data" / "raw" / "statsbomb_open" / "big5_matches.parquet"
    )
    output_path = Path(args.output_path) if args.output_path else (
        project_root
        / "data"
        / "gold"
        / "feature_store"
        / "player_match_action_value_sample.parquet"
    )
    if not events_path.exists():
        print(f"Error: Events file not found: {events_path}")
        sys.exit(1)
    if not matches_path.exists():
        print(f"Error: Match metadata file not found: {matches_path}")
        sys.exit(1)

    events = pd.read_parquet(events_path)
    names = (
        events.dropna(subset=["player_id", "player_name"])
        .drop_duplicates("player_id")
        if {"player_id", "player_name"}.issubset(events.columns)
        else pd.DataFrame(columns=["player_id", "player_name"])
    )
    player_names = {
        str(int(float(row.player_id))): str(row.player_name)
        for row in names.itertuples(index=False)
    }
    actions = convert_all_events(events_path)
    if actions.empty:
        print("Error: No convertible actions in events file.")
        sys.exit(1)
    _, valued_actions = compute_xt_values(actions)
    artifact, manifest = build_player_match_action_values(
        valued_actions,
        pd.read_parquet(matches_path),
        coverage_scope=args.coverage_scope,
        player_names=player_names,
    )
    if artifact.empty:
        print("Error: No player-match xT rows computed.")
        sys.exit(1)
    save_player_match_action_values(artifact, manifest, output_path)
    print(f"Saved {len(artifact)} player-team-match rows to {output_path}")
    print(
        f"  coverage={manifest['coverage_scope']}; matches={manifest['match_count']}; "
        f"valued_actions={manifest['input_action_rows']}"
    )


def _cmd_export_ratings(_args: argparse.Namespace) -> None:
    from scoutfootball.storage.duckdb_io import create_ratings_database

    project_root = Path(__file__).resolve().parents[2]
    feature_store = project_root / "data" / "gold" / "feature_store"
    output_path = project_root / "data" / "gold" / "scoutlab.duckdb"

    # --- player_ratings ---
    ratings_path = feature_store / "player_ratings_optimized.parquet"
    if not ratings_path.exists():
        print("Error: player_ratings_optimized.parquet not found. Run 'scoutfootball train' first.")
        sys.exit(1)

    ratings_df = pd.read_parquet(ratings_path)
    available_cols = set(ratings_df.columns)

    # Rename sub_position -> position_group for consistent schema
    if "sub_position" in available_cols and "position_group" not in available_cols:
        ratings_df = ratings_df.rename(columns={"sub_position": "position_group"})
        available_cols.add("position_group")

    select_cols = [
        "player", "team", "league", "season", "position_group",
        "optimized_score", "minutes", "npg_p90", "assists_p90",
        "defense_composite", "possession_composite", "finishing_shrunk",
    ]
    present_cols = [c for c in select_cols if c in available_cols]
    player_ratings = ratings_df[present_cols].copy()

    minutes_col = "minutes" if "minutes" in player_ratings.columns else None
    if minutes_col:
        player_ratings["confidence_level"] = player_ratings[minutes_col].apply(
            lambda m: "high" if m >= 900 else ("medium" if m >= 450 else "low")
        )
    else:
        player_ratings["confidence_level"] = "low"

    # --- model_meta ---
    meta_path = feature_store / "optimized_params_meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        holdout = meta.get("holdout", {})
        opt_test = holdout.get("optimized_test", {})
        model_meta = pd.DataFrame([{
            "run_id": meta.get("timestamp", "unknown"),
            "timestamp": meta.get("timestamp", ""),
            "n_params": meta.get("n_params", 0),
            "spearman": opt_test.get("spearman", float("nan")),
            "pearson": opt_test.get("pearson", float("nan")),
            "overfit_gap": holdout.get("overfit_rank_loss_gap", float("nan")),
            "composite_weights": json.dumps({
                "spearman": meta.get("spearman_weight", 0.5),
                "ndcg": meta.get("ndcg_weight", 0.2),
                "position_consistency": meta.get("position_consistency_weight", 0.15),
                "extreme_penalty": meta.get("extreme_penalty_weight", 0.1),
                "prior": meta.get("prior_weight", 0.05),
            }),
        }])
    else:
        model_meta = pd.DataFrame(columns=[
            "run_id", "timestamp", "n_params", "spearman", "pearson",
            "overfit_gap", "composite_weights",
        ])

    # --- league_metrics ---
    league_path = feature_store / "rating_league_metrics.parquet"
    if league_path.exists():
        league_metrics = pd.read_parquet(league_path)
    else:
        league_metrics = pd.DataFrame(
            columns=["league", "spearman", "pearson", "n_teams", "coverage"]
        )

    # --- team_coverage ---
    coverage_path = feature_store / "rating_team_coverage.parquet"
    if coverage_path.exists():
        team_coverage = pd.read_parquet(coverage_path)
    else:
        team_coverage = pd.DataFrame(columns=[
            "league", "season", "n_target", "n_scored", "n_matched", "coverage", "confidence",
        ])

    create_ratings_database(output_path, player_ratings, model_meta, league_metrics, team_coverage)
    print(f"Ratings database written to {output_path}")
    print(f"  player_ratings: {len(player_ratings)} rows")
    print(f"  model_meta: {len(model_meta)} rows")
    print(f"  league_metrics: {len(league_metrics)} rows")
    print(f"  team_coverage: {len(team_coverage)} rows")


def _cmd_export_local_pack(args: argparse.Namespace) -> None:
    """Export all local personal artifacts (recruitment briefs and
    opposition briefings) into a portable offline JSON pack.

    Mirrors ``POST /local-pack/export`` but works without a running API
    server, so the maintainer can migrate or back up local artifacts
    from a terminal session, a cron job, or a recovery shell.  No cloud,
    no account, no telemetry — the pack is a single JSON document
    intended for file transfer or local backup.
    """
    import json as _json

    from scoutfootball.api import export_local_pack

    try:
        response = export_local_pack()
    except Exception as exc:  # noqa: BLE001 — surface any failure to the user
        print(f"Error: unable to export local pack: {exc}", file=sys.stderr)
        sys.exit(1)

    if response.get("status") != "ok":
        print(f"Error: export returned non-ok status: {response}", file=sys.stderr)
        sys.exit(1)

    pack = response["pack"]
    payload = _json.dumps(pack, ensure_ascii=False, indent=2)

    output_path = Path(args.output).resolve() if args.output else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
        briefs = pack.get("sections", {}).get("recruitment_briefs", {}).get("count", 0)
        briefings = pack.get("sections", {}).get("opposition_briefings", {}).get("count", 0)
        skipped = pack.get("skipped", {})
        skipped_briefs = len(skipped.get("recruitment_briefs", []))
        skipped_briefings = len(skipped.get("opposition_briefings", []))
        print(f"Portable pack written to {output_path}")
        print(f"  schema: {pack.get('schema')} v{pack.get('version')}")
        print(f"  recruitment_briefs: {briefs} record(s)")
        print(f"  opposition_briefings: {briefings} record(s)")
        if skipped_briefs or skipped_briefings:
            print(f"  skipped: {skipped_briefs} brief(s), {skipped_briefings} briefing(s)")
        print(f"  exported_at: {pack.get('exported_at')}")
    else:
        # stdout: emit the pack JSON so it can be piped into a file or
        # another command.  Do not print any extra human-readable lines
        # because they would corrupt the piped output.
        print(payload)


def _cmd_import_local_pack(args: argparse.Namespace) -> None:
    """Import a portable pack into the local stores.

    Mirrors ``POST /local-pack/import`` but works without a running API
    server.  By default this is a **dry-run preview**: the pack is
    parsed and a summary is printed without writing anything to disk.
    Pass ``--confirm`` to actually import records; pass ``--overwrite``
    to replace records whose ID already exists locally (otherwise they
    are reported as conflicts and left untouched).
    """
    import json as _json

    from scoutfootball.api import (
        _PORTABLE_PACK_SCHEMA,
        _PORTABLE_PACK_VERSION,
        import_local_pack,
    )

    # ── Read the pack from --from PATH or stdin ────────────────────
    if args.from_path:
        pack_path = Path(args.from_path).resolve()
        if not pack_path.exists():
            print(f"Error: pack file not found: {pack_path}", file=sys.stderr)
            sys.exit(1)
        try:
            pack = _json.loads(pack_path.read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError) as exc:
            print(f"Error: unable to parse pack file: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            pack = _json.loads(sys.stdin.read())
        except _json.JSONDecodeError as exc:
            print(f"Error: unable to parse pack from stdin: {exc}", file=sys.stderr)
            sys.exit(1)

    if not isinstance(pack, dict):
        print("Error: pack must be a JSON object", file=sys.stderr)
        sys.exit(1)

    # ── Pack-level validation (mirrors import_local_pack's checks) ──
    schema = pack.get("schema")
    version = pack.get("version")
    if schema != _PORTABLE_PACK_SCHEMA:
        print(
            f"Error: pack schema '{schema}' is not '{_PORTABLE_PACK_SCHEMA}'",
            file=sys.stderr,
        )
        sys.exit(1)
    if version != _PORTABLE_PACK_VERSION:
        print(
            f"Error: pack version '{version}' is not '{_PORTABLE_PACK_VERSION}'",
            file=sys.stderr,
        )
        sys.exit(1)

    sections = pack.get("sections")
    if not isinstance(sections, dict):
        print("Error: pack.sections must be an object", file=sys.stderr)
        sys.exit(1)

    # ── Build a preview summary ────────────────────────────────────
    # In dry-run mode we report what would happen, without calling
    # import_local_pack (which writes to disk).  This mirrors the
    # "preview or append" pattern used by record-source-policy etc.
    section_summaries = []
    for name in ("recruitment_briefs", "opposition_briefings"):
        section = sections.get(name)
        if isinstance(section, dict):
            count = section.get("count")
            if not isinstance(count, int):
                records = section.get("records")
                count = len(records) if isinstance(records, list) else 0
            section_summaries.append({"section": name, "count": count})
        else:
            section_summaries.append({"section": name, "count": 0, "missing": True})

    # ── Dry-run: print preview and exit ────────────────────────────
    if not args.confirm:
        result = {
            "status": "preview",
            "schema": schema,
            "version": version,
            "exported_at": pack.get("exported_at"),
            "sections": section_summaries,
            "overwrite": args.overwrite,
            "note": (
                "Dry-run only. Pass --confirm to write records to the local stores. "
                "Pass --overwrite to replace records whose ID already exists locally."
            ),
        }
        if args.json:
            print(_json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("Portable pack import preview (dry-run)")
            print(f"  schema: {schema} v{version}")
            print(f"  exported_at: {pack.get('exported_at')}")
            for s in section_summaries:
                marker = " (missing)" if s.get("missing") else ""
                print(f"  {s['section']}: {s['count']} record(s){marker}")
            print(f"  overwrite: {args.overwrite}")
            print(
                "  Pass --confirm to write records to the local stores."
            )
        return

    # ── Confirmed import: call import_local_pack ───────────────────
    try:
        result = import_local_pack(pack, overwrite=args.overwrite)
    except Exception as exc:  # noqa: BLE001 — surface any failure
        print(f"Error: unable to import local pack: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(_json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = result.get("status", "unknown")
        section_results = result.get("section_results", [])
        section_errors = result.get("section_errors", [])
        summary = result.get("summary", {})
        print(f"Import status: {status}")
        for section_result in section_results:
            section_name = section_result.get("section", "?")
            section_imported = section_result.get("imported", 0)
            section_conflicts = len(section_result.get("conflicts", []))
            section_skipped = len(section_result.get("skipped", []))
            print(
                f"  {section_name}: imported={section_imported} "
                f"conflicts={section_conflicts} skipped={section_skipped}"
            )
        if summary:
            print(
                f"  total: imported={summary.get('total_imported', 0)} "
                f"conflicts={summary.get('total_conflicts', 0)} "
                f"skipped={summary.get('total_skipped', 0)}"
            )
        if section_errors:
            print(f"  section_errors: {len(section_errors)}")
            for err in section_errors:
                print(f"    - {err.get('section')}: {err.get('code')}")
        if status == "error":
            sys.exit(1)


def _cmd_backtest(args: argparse.Namespace) -> None:
    from scoutfootball.evaluation.backtests import (
        run_dc_backtest_with_calibration,
        run_dixon_coles_backtest,
        run_poisson_backtest,
    )
    from scoutfootball.models import TimeSplitConfig

    project_root = Path(__file__).resolve().parents[2]
    out_dir = Path(args.output_dir).resolve() if args.output_dir else (
        project_root / "data" / "reports" / "calibration_backtest"
    )

    team_match = _load_team_match_from_gold()
    print(f"  team_match: {len(team_match)} rows, {team_match['match_id'].nunique()} matches")

    n_splits = args.n_splits
    decay = args.decay
    split_cfg = TimeSplitConfig(n_splits=n_splits, gap=0)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Poisson
    print("\n=== Independent Poisson Backtest ===")
    p_result = run_poisson_backtest(team_match, split_cfg)
    p_result.predictions.to_parquet(out_dir / "poisson_backtest_predictions.parquet", index=False)
    p_metrics = {
        "model": "independent_poisson", "n_splits": n_splits,
        "total_predictions": len(p_result.predictions),
        "overall": p_result.metrics,
        "folds": p_result.fold_metrics.to_dict(orient="records"),
    }
    with open(out_dir / "poisson_backtest_metrics.json", "w", encoding="utf-8") as f:
        json.dump(p_metrics, f, indent=2, default=str, ensure_ascii=False)
    print(f"  Log Loss: {p_result.metrics['log_loss_exact']:.4f}")
    print(f"  Brier:    {p_result.metrics['brier_1x2']:.4f}")
    print(f"  RPS:      {p_result.metrics['rps_1x2']:.4f}")

    # Dixon-Coles (no decay)
    print("\n=== Dixon-Coles Backtest (no decay) ===")
    dc_result = run_dixon_coles_backtest(team_match, split_cfg)
    dc_result.predictions.to_parquet(
        out_dir / "dixon_coles_backtest_predictions.parquet",
        index=False,
    )
    dc_metrics = {
        "model": "dixon_coles", "decay": None, "n_splits": n_splits,
        "total_predictions": len(dc_result.predictions),
        "overall": dc_result.metrics,
        "folds": dc_result.fold_metrics.to_dict(orient="records"),
    }
    with open(out_dir / "dixon_coles_backtest_metrics.json", "w", encoding="utf-8") as f:
        json.dump(dc_metrics, f, indent=2, default=str, ensure_ascii=False)
    print(f"  Log Loss: {dc_result.metrics['log_loss_exact']:.4f}")
    print(f"  Brier:    {dc_result.metrics['brier_1x2']:.4f}")
    print(f"  RPS:      {dc_result.metrics['rps_1x2']:.4f}")

    # Dixon-Coles (with decay)
    print(f"\n=== Dixon-Coles Backtest (decay={decay}) ===")
    dc_decay_result = run_dixon_coles_backtest(team_match, split_cfg, decay=decay)
    dc_decay_result.predictions.to_parquet(
        out_dir / "dixon_coles_decay_backtest_predictions.parquet",
        index=False,
    )
    dc_decay_metrics = {
        "model": "dixon_coles", "decay": decay, "n_splits": n_splits,
        "total_predictions": len(dc_decay_result.predictions),
        "overall": dc_decay_result.metrics,
        "folds": dc_decay_result.fold_metrics.to_dict(orient="records"),
    }
    with open(out_dir / "dixon_coles_decay_backtest_metrics.json", "w", encoding="utf-8") as f:
        json.dump(dc_decay_metrics, f, indent=2, default=str, ensure_ascii=False)
    print(f"  Log Loss: {dc_decay_result.metrics['log_loss_exact']:.4f}")
    print(f"  Brier:    {dc_decay_result.metrics['brier_1x2']:.4f}")
    print(f"  RPS:      {dc_decay_result.metrics['rps_1x2']:.4f}")

    # Comparison: Poisson vs DC (no decay) vs DC (with decay)
    print(f"\n{'Metric':<25} {'Poisson':>12} {'DC(no decay)':>12} {'DC(decay)':>12}")
    print("-" * 65)
    for m in ["log_loss_exact", "brier_1x2", "rps_1x2"]:
        pv = p_result.metrics[m]
        dv = dc_result.metrics[m]
        ddv = dc_decay_result.metrics[m]
        print(f"  {m:<23} {pv:>12.4f} {dv:>12.4f} {ddv:>12.4f}")

    # Probability calibration (isotonic)
    print(f"\n=== Dixon-Coles Calibration (decay={decay}, isotonic) ===")
    try:
        cal_bt = run_dc_backtest_with_calibration(
            team_match, split_cfg, decay=decay, calibration_method="isotonic",
        )
        cal_metrics = cal_bt.metrics
        print(f"  Brier before: {cal_metrics['brier_1x2_before']:.4f}")
        print(f"  Brier after:  {cal_metrics['brier_1x2_after']:.4f}")
        print(f"  RPS before:   {cal_metrics['rps_before']:.4f}")
        print(f"  RPS after:    {cal_metrics['rps_after']:.4f}")
        print(f"  N matches:    {cal_metrics['n_matches']}")

        # Save calibration report
        if cal_bt.calibration.calibrated_predictions is not None:
            cal_bt.calibration.calibrated_predictions.to_parquet(
                out_dir / "dc_calibrated_predictions.parquet", index=False,
            )
        cal_report_data = {
            "method": "isotonic", "decay": decay,
            "brier_before": cal_metrics["brier_1x2_before"],
            "brier_after": cal_metrics["brier_1x2_after"],
            "rps_before": cal_metrics["rps_before"],
            "rps_after": cal_metrics["rps_after"],
            "n_matches": cal_metrics["n_matches"],
        }
        with open(out_dir / "dc_calibration_report.json", "w", encoding="utf-8") as f:
            json.dump(cal_report_data, f, indent=2, default=str, ensure_ascii=False)
    except Exception as exc:
        print(f"  Calibration failed: {exc}")

    print(f"\nResults saved to {out_dir}")


def _load_team_match_from_gold() -> pd.DataFrame:
    """Load team_match frame from gold feature_store.

    Reads ``data/gold/feature_store/team_match.parquet`` (the same artifact
    that ``scoutfootball train`` uses via ``run_weekly_train``) and selects
    the columns required by the backtest/tune/optimize commands. This
    closes a dual-source-of-truth gap where ``_load_team_match_from_raw``
    previously built a SEPARATE team_match frame from
    ``data/raw/football_data/combined_results.parquet`` with different
    ``match_id`` format (``{home}_{away}_{date}`` vs gold's
    ``fd-match-{idx+1}``) and different ``team_id`` values
    (``normalize_team_name(HomeTeam)`` vs raw ``HomeTeam``). That divergence
    meant decay values tuned by ``tune-predictions`` and ensemble weights
    computed by ``optimize-ensemble`` were optimized on a different frame
    than ``train`` actually uses.

    Shared by ``backtest``, ``tune-predictions`` and ``optimize-ensemble``
    commands. Errors with exit code 1 if gold parquet is missing — run
    ``scoutfootball build-features`` first.
    """
    project_root = Path(__file__).resolve().parents[2]
    gold_path = project_root / "data" / "gold" / "feature_store" / "team_match.parquet"
    if not gold_path.exists():
        print(
            f"Error: gold team_match.parquet not found at {gold_path}. "
            "Run `scoutfootball build-features` first."
        )
        sys.exit(1)

    team_match = pd.read_parquet(gold_path)
    required = ["match_id", "match_date", "team_id", "is_home", "goals_for", "goals_against"]
    missing = [c for c in required if c not in team_match.columns]
    if missing:
        print(
            f"Error: gold team_match.parquet is missing required columns: {missing}. "
            "Run `scoutfootball build-features` to rebuild."
        )
        sys.exit(1)
    return team_match[required].copy()


def _cmd_tune_predictions(args: argparse.Namespace) -> None:
    """Grid-search Dixon-Coles decay parameter and optionally run backtest."""
    from scoutfootball.evaluation.backtests import tune_dixon_coles_decay
    from scoutfootball.models import TimeSplitConfig

    project_root = Path(__file__).resolve().parents[2]
    out_dir = Path(args.output_dir).resolve() if args.output_dir else (
        project_root / "data" / "reports" / "calibration_backtest"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    team_match = _load_team_match_from_gold()
    print(f"  Loaded {len(team_match)} rows, {team_match['match_id'].nunique()} matches")

    split_cfg = TimeSplitConfig(n_splits=args.n_splits, gap=0)
    selection_metric = args.metric

    print(f"\n=== Dixon-Coles Decay Tuning (metric: {selection_metric}) ===")
    tuning = tune_dixon_coles_decay(
        team_match,
        split_cfg=split_cfg,
        selection_metric=selection_metric,
    )

    print(f"\n{'Decay':>8} {'HalfLife':>10} {'LogLoss':>10} {'Brier':>10} {'RPS':>10}")
    print("-" * 52)
    for _, row in tuning.comparison_table.iterrows():
        hl = f"{row['half_life_days']:.0f}" if row["half_life_days"] != float("inf") else "inf"
        print(
            f"  {row['decay']:>6.4f} {hl:>10} {row['log_loss_exact']:>10.4f} "
            f"{row['brier_1x2']:>10.4f} {row['rps_1x2']:>10.4f}"
        )

    print(f"\n  Best decay: {tuning.best_decay} (by {selection_metric})")

    # Save tuning results
    tuning_data = {
        "best_decay": tuning.best_decay,
        "selection_metric": tuning.selection_metric,
        "n_folds": tuning.n_folds,
        "n_matches": tuning.n_matches,
        "candidates": tuning.comparison_table.to_dict(orient="records"),
        "candidate_metrics": {
            str(k): v for k, v in tuning.candidate_metrics.items()
        },
    }
    tuning_path = out_dir / "decay_tuning_results.json"
    with open(tuning_path, "w", encoding="utf-8") as f:
        json.dump(tuning_data, f, indent=2, default=str, ensure_ascii=False)
    print(f"  Saved to {tuning_path}")

    # Optionally run full backtest with the best decay
    if args.run_backtest:
        print(f"\n=== Running full backtest with best decay={tuning.best_decay} ===")
        from scoutfootball.evaluation.backtests import (
            run_dc_backtest_with_calibration,
            run_dixon_coles_backtest,
            run_poisson_backtest,
        )

        # Poisson
        print("\n--- Independent Poisson ---")
        p_result = run_poisson_backtest(team_match, split_cfg)
        p_result.predictions.to_parquet(
            out_dir / "poisson_backtest_predictions.parquet", index=False,
        )
        p_metrics = {
            "model": "independent_poisson", "n_splits": args.n_splits,
            "total_predictions": len(p_result.predictions),
            "overall": p_result.metrics,
            "folds": p_result.fold_metrics.to_dict(orient="records"),
        }
        with open(out_dir / "poisson_backtest_metrics.json", "w", encoding="utf-8") as f:
            json.dump(p_metrics, f, indent=2, default=str, ensure_ascii=False)
        print(f"  RPS: {p_result.metrics['rps_1x2']:.4f}")

        # DC no-decay
        print("\n--- Dixon-Coles (no decay) ---")
        dc_result = run_dixon_coles_backtest(team_match, split_cfg)
        dc_result.predictions.to_parquet(
            out_dir / "dixon_coles_backtest_predictions.parquet", index=False,
        )
        dc_metrics = {
            "model": "dixon_coles", "decay": None, "n_splits": args.n_splits,
            "total_predictions": len(dc_result.predictions),
            "overall": dc_result.metrics,
            "folds": dc_result.fold_metrics.to_dict(orient="records"),
        }
        with open(out_dir / "dixon_coles_backtest_metrics.json", "w", encoding="utf-8") as f:
            json.dump(dc_metrics, f, indent=2, default=str, ensure_ascii=False)
        print(f"  RPS: {dc_result.metrics['rps_1x2']:.4f}")

        # DC with best decay
        best_decay = tuning.best_decay
        print(f"\n--- Dixon-Coles (decay={best_decay}) ---")
        dc_decay_result = run_dixon_coles_backtest(
            team_match, split_cfg,
            decay=best_decay if best_decay > 0 else None,
        )
        dc_decay_result.predictions.to_parquet(
            out_dir / "dixon_coles_decay_backtest_predictions.parquet", index=False,
        )
        dc_decay_metrics = {
            "model": "dixon_coles", "decay": best_decay, "n_splits": args.n_splits,
            "total_predictions": len(dc_decay_result.predictions),
            "overall": dc_decay_result.metrics,
            "folds": dc_decay_result.fold_metrics.to_dict(orient="records"),
        }
        with open(out_dir / "dixon_coles_decay_backtest_metrics.json", "w", encoding="utf-8") as f:
            json.dump(dc_decay_metrics, f, indent=2, default=str, ensure_ascii=False)
        print(f"  RPS: {dc_decay_result.metrics['rps_1x2']:.4f}")

        # Calibration
        print(f"\n--- Calibration (decay={best_decay}, isotonic) ---")
        try:
            cal_bt = run_dc_backtest_with_calibration(
                team_match, split_cfg,
                decay=best_decay if best_decay > 0 else None,
                calibration_method="isotonic",
            )
            cal_report_data = {
                "method": "isotonic", "decay": best_decay,
                "brier_before": cal_bt.metrics["brier_1x2_before"],
                "brier_after": cal_bt.metrics["brier_1x2_after"],
                "rps_before": cal_bt.metrics["rps_before"],
                "rps_after": cal_bt.metrics["rps_after"],
                "n_matches": cal_bt.metrics["n_matches"],
            }
            with open(out_dir / "dc_calibration_report.json", "w", encoding="utf-8") as f:
                json.dump(cal_report_data, f, indent=2, default=str, ensure_ascii=False)
            if cal_bt.calibration.calibrated_predictions is not None:
                cal_bt.calibration.calibrated_predictions.to_parquet(
                    out_dir / "dc_calibrated_predictions.parquet", index=False,
                )
            print(
                f"  Brier: {cal_bt.metrics['brier_1x2_before']:.4f}"
                f" -> {cal_bt.metrics['brier_1x2_after']:.4f}"
            )
            print(
                f"  RPS:   {cal_bt.metrics['rps_before']:.4f}"
                f" -> {cal_bt.metrics['rps_after']:.4f}"
            )
        except Exception as exc:
            print(f"  Calibration failed: {exc}")

    print(f"\nResults saved to {out_dir}")


def _cmd_optimize_ensemble(args: argparse.Namespace) -> None:
    """Optimize ensemble weights via backtest grid-search and cache them."""
    from scoutfootball.models import (
        TimeSplitConfig,
        optimize_ensemble_weights,
        save_ensemble_weights,
    )

    project_root = Path(__file__).resolve().parents[2]
    out_dir = Path(args.output_dir).resolve() if args.output_dir else (
        project_root / "data" / "reports" / "calibration_backtest"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    team_match = _load_team_match_from_gold()
    print(f"  Loaded {len(team_match)} rows, {team_match['match_id'].nunique()} matches")

    split_cfg = TimeSplitConfig(n_splits=args.n_splits, gap=0)

    # Resolve decay from tuning results if not explicitly provided
    decay = args.decay
    if decay is None:
        tuning_path = out_dir / "decay_tuning_results.json"
        if tuning_path.exists():
            try:
                with open(tuning_path, encoding="utf-8") as f:
                    tuning_data = json.load(f)
                best = tuning_data.get("best_decay")
                if isinstance(best, (int, float)) and best >= 0:
                    decay = float(best)
                    print(f"  Using tuned decay={decay} from {tuning_path.name}")
            except (json.JSONDecodeError, OSError):
                pass
        if decay is None:
            print("  No tuned decay found; fitting without time decay")

    print(f"\n=== Ensemble Weight Optimization (n_splits={args.n_splits}) ===")
    weights = optimize_ensemble_weights(
        team_match,
        decay=decay,
        split_cfg=split_cfg,
    )

    # Compute the RPS achieved by these weights on the full backtest
    import numpy as np

    from scoutfootball.evaluation.backtests import (
        run_dixon_coles_backtest,
        run_poisson_backtest,
    )
    from scoutfootball.models.match_prediction import _compute_rps

    p_bt = run_poisson_backtest(team_match, split_cfg)
    dc_bt = run_dixon_coles_backtest(team_match, split_cfg, decay=decay)
    merged = p_bt.predictions.merge(
        dc_bt.predictions[
            ["match_id", "home_win_probability", "draw_probability", "away_win_probability"]
        ],
        on="match_id",
        suffixes=("_poisson", "_dc"),
    )
    if "actual_outcome" in merged.columns and not merged.empty:
        actual = merged["actual_outcome"].map(
            {"home_win": 0, "draw": 1, "away_win": 2}
        ).to_numpy()
        p_probs = merged[
            [
                "home_win_probability_poisson",
                "draw_probability_poisson",
                "away_win_probability_poisson",
            ]
        ].to_numpy()
        dc_probs = merged[
            ["home_win_probability_dc", "draw_probability_dc", "away_win_probability_dc"]
        ].to_numpy()
        actual_onehot = np.zeros_like(p_probs)
        actual_onehot[np.arange(len(actual)), actual] = 1.0
        blended = (
            weights["poisson"] * p_probs
            + weights["dixon_coles"] * dc_probs
            + weights["dixon_coles_form"] * dc_probs
        )
        achieved_rps = _compute_rps(blended, actual_onehot)
        n_matches = len(merged)
    else:
        achieved_rps = None
        n_matches = 0

    weights_path = out_dir / "ensemble_optimal_weights.json"
    save_ensemble_weights(
        weights,
        weights_path,
        rps=achieved_rps,
        n_matches=n_matches,
    )

    print("\n  Optimal weights (minimizing RPS):")
    for name, w in weights.items():
        print(f"    {name:>20s}: {w:.2f}")
    if achieved_rps is not None:
        print(f"\n  Achieved RPS: {achieved_rps:.4f} ({n_matches} matches)")
    print(f"  Saved to {weights_path}")


# ── Recruitment brief CLI ────────────────────────────────────────────────


def _brief_store():
    """Build a BriefStore rooted at the platform report_root/recruitment/briefs."""
    from scoutfootball.config import PlatformSettings
    from scoutfootball.recruitment.store import BriefStore

    settings = PlatformSettings.from_root()
    return BriefStore(settings.report_root / "recruitment" / "briefs")


def _briefing_store():
    """Build a BriefingStore rooted at report_root/opposition/briefings."""
    from scoutfootball.config import PlatformSettings
    from scoutfootball.opposition.store import BriefingStore

    settings = PlatformSettings.from_root()
    return BriefingStore(settings.report_root / "opposition" / "briefings")


def _review_store():
    """Build a ReviewStore rooted at report_root/opposition/reviews."""
    from scoutfootball.config import PlatformSettings
    from scoutfootball.opposition.post_match_review_store import ReviewStore

    settings = PlatformSettings.from_root()
    return ReviewStore(settings.report_root / "opposition" / "reviews")


def _cmd_create_brief(args: argparse.Namespace) -> None:
    """Create a new recruitment brief from CLI flags or a JSON file."""
    import json
    import uuid as _uuid
    from datetime import UTC, datetime

    from scoutfootball.recruitment.brief import (
        BriefValidationError,
        validate_brief_id,
    )
    from scoutfootball.recruitment.store import BriefStoreError

    if args.from_json:
        path = Path(args.from_json)
        if path.is_symlink() or not path.is_file():
            print(f"error: brief JSON must be a regular local file: {path}", file=sys.stderr)
            sys.exit(1)
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"error: cannot read brief JSON: {type(exc).__name__}: {exc}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(payload, dict):
            print("error: brief JSON must be an object", file=sys.stderr)
            sys.exit(1)
        # If brief_id is missing, generate one.
        if not payload.get("brief_id"):
            date_part = datetime.now(tz=UTC).strftime("%Y%m%d")
            uuid_part = _uuid.uuid4().hex[:8]
            payload["brief_id"] = f"brief-{date_part}-{uuid_part}"
    else:
        # Build from CLI flags.
        if not args.title:
            print("error: --title is required when not using --from-json", file=sys.stderr)
            sys.exit(2)
        if not args.position_group:
            print(
                "error: --position-group is required when not using --from-json",
                file=sys.stderr,
            )
            sys.exit(2)
        date_part = datetime.now(tz=UTC).strftime("%Y%m%d")
        uuid_part = _uuid.uuid4().hex[:8]
        brief_id = args.brief_id or f"brief-{date_part}-{uuid_part}"
        validate_brief_id(brief_id)
        now = datetime.now(tz=UTC).isoformat()
        payload = {
            "schema": "scoutfootball.recruitment-brief",
            "version": "1.0.0",
            "brief_id": brief_id,
            "revision": 1,
            "created_at": now,
            "updated_at": now,
            "author": args.author or "maintainer",
            "title": args.title,
            "team": args.team or "",
            "position_group": args.position_group,
            "position_detail": args.position_detail or "",
            "role": args.role or "",
            "budget_eur": args.budget_eur,
            "age_min": args.age_min,
            "age_max": args.age_max,
            "contract_years_min": args.contract_years_min,
            "league_preferences": args.league_preferences or [],
            "language_preferences": args.language_preferences or [],
            "risk_tolerance": args.risk_tolerance or "medium",
            "minimum_minutes": args.minimum_minutes,
            "notes": args.notes or "",
            "limitations": [
                "Brief is a personal local object; not an external fact.",
                (
                    "Candidate coverage depends on the rating snapshot; "
                    "low-coverage leagues may be under-represented."
                ),
            ],
        }

    try:
        store = _brief_store()
        record = store.save(payload["brief_id"], payload, expected_revision=0)
    except BriefValidationError as exc:
        print(f"error: brief validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except BriefStoreError as exc:
        print(f"error: brief store failed: {exc.code} (HTTP {exc.http_status})", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        brief = record["brief"]
        print(f"Created brief: {brief['brief_id']} (revision {brief['revision']})")
        print(f"  title: {brief['title']}")
        print(f"  team: {brief.get('team', '') or '(none)'}")
        print(f"  position: {brief['position_group']}/{brief.get('position_detail', '') or '-'}")
        print(f"  role: {brief.get('role', '') or '(unspecified)'}")
        print(f"  stored at: {store.root / (brief['brief_id'] + '.json')}")


def _cmd_list_briefs(args: argparse.Namespace) -> None:
    """List stored recruitment briefs."""
    import json

    store = _brief_store()
    records = store.list_records(limit=args.limit)
    if args.json:
        print(json.dumps({"count": len(records), "briefs": records}, ensure_ascii=False, indent=2))
    else:
        if not records:
            print("No briefs found.")
            return
        print(f"Found {len(records)} brief(s):")
        for rec in records:
            print(
                f"  {rec['brief_id']}  rev={rec['server_revision']}  "
                f"{rec.get('title', '')}  "
                f"team={rec.get('team', '') or '-'}  "
                f"pos={rec.get('position_group', '') or '-'}"
            )


def _cmd_show_brief(args: argparse.Namespace) -> None:
    """Show one stored recruitment brief."""
    import json

    from scoutfootball.recruitment.store import BriefStoreError

    try:
        store = _brief_store()
        record = store.load(args.brief_id)
    except BriefStoreError as exc:
        print(f"error: {exc.code} (HTTP {exc.http_status})", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        brief = record["brief"]
        print(f"Brief: {brief['brief_id']}")
        print(f"  schema: {brief['schema']} v{brief['version']}")
        print(f"  revision: {brief['revision']} (server_revision: {record['server_revision']})")
        print(f"  title: {brief['title']}")
        print(f"  team: {brief.get('team', '') or '(none)'}")
        print(f"  position: {brief['position_group']}/{brief.get('position_detail', '') or '-'}")
        print(f"  role: {brief.get('role', '') or '(unspecified)'}")
        if brief.get("budget_eur") is not None:
            print(f"  budget: €{brief['budget_eur']:,}")
        if brief.get("age_min") is not None or brief.get("age_max") is not None:
            print(f"  age: {brief.get('age_min', '-')}–{brief.get('age_max', '-')}")
        if brief.get("contract_years_min") is not None:
            print(f"  contract min years: {brief['contract_years_min']}")
        if brief.get("league_preferences"):
            print(f"  leagues: {', '.join(brief['league_preferences'])}")
        if brief.get("language_preferences"):
            print(f"  languages: {', '.join(brief['language_preferences'])}")
        print(f"  risk tolerance: {brief.get('risk_tolerance', 'medium')}")
        if brief.get("minimum_minutes") is not None:
            print(f"  minimum minutes: {brief['minimum_minutes']}")
        if brief.get("notes"):
            print(f"  notes: {brief['notes']}")
        print(f"  created: {brief.get('created_at', '?')}")
        print(f"  updated: {brief.get('updated_at', '?')}")
        print(f"  stored: {record.get('stored_at', '?')}")


def _cmd_validate_brief(args: argparse.Namespace) -> None:
    """Validate a local brief JSON file without saving it."""
    import json

    from scoutfootball.recruitment.brief import (
        BriefValidationError,
        validate_brief_payload,
    )

    path = Path(args.path)
    if path.is_symlink() or not path.is_file():
        print(f"error: brief file must be a regular local file: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: cannot read brief JSON: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        brief = validate_brief_payload(payload)
    except BriefValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        result = {"status": "valid", "brief_id": brief.brief_id}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"VALID: {brief.brief_id} (schema={brief.schema_name} v{brief.version})")


# ── Recruitment decision dossier CLI ─────────────────────────────────────


def _dossier_store():
    """Build a DossierStore rooted at the platform report_root/recruitment/dossiers."""
    from scoutfootball.config import PlatformSettings
    from scoutfootball.recruitment.dossier_store import DossierStore

    settings = PlatformSettings.from_root()
    return DossierStore(settings.report_root / "recruitment" / "dossiers")


def _cmd_create_dossier(args: argparse.Namespace) -> None:
    """Create a new decision dossier from CLI flags or a JSON file."""
    import json
    import uuid as _uuid
    from datetime import UTC, datetime

    from scoutfootball.recruitment.dossier import (
        DossierValidationError,
        validate_dossier_id,
    )
    from scoutfootball.recruitment.dossier_store import DossierStoreError

    if args.from_json:
        path = Path(args.from_json)
        if path.is_symlink() or not path.is_file():
            print(f"error: dossier JSON must be a regular local file: {path}", file=sys.stderr)
            sys.exit(1)
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"error: cannot read dossier JSON: {type(exc).__name__}: {exc}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(payload, dict):
            print("error: dossier JSON must be an object", file=sys.stderr)
            sys.exit(1)
        if not payload.get("dossier_id"):
            date_part = datetime.now(tz=UTC).strftime("%Y%m%d")
            uuid_part = _uuid.uuid4().hex[:8]
            payload["dossier_id"] = f"dossier-{date_part}-{uuid_part}"
    else:
        if not args.title:
            print("error: --title is required when not using --from-json", file=sys.stderr)
            sys.exit(2)
        date_part = datetime.now(tz=UTC).strftime("%Y%m%d")
        uuid_part = _uuid.uuid4().hex[:8]
        dossier_id = args.dossier_id or f"dossier-{date_part}-{uuid_part}"
        try:
            validate_dossier_id(dossier_id)
        except DossierValidationError as exc:
            print(f"error: invalid dossier id: {exc}", file=sys.stderr)
            sys.exit(1)
        now = datetime.now(tz=UTC).isoformat()
        # Status/decision consistency: when --decision is given we force
        # status="decided"; otherwise default to "draft" with decision=null.
        decision_value = args.decision or None
        status_value = "decided" if decision_value else (args.status or "draft")
        if decision_value and status_value != "decided":
            print(
                f"error: --decision requires --status decided (got {status_value!r})",
                file=sys.stderr,
            )
            sys.exit(2)
        payload = {
            "schema": "scoutfootball.recruitment-decision-dossier",
            "version": "1.0.0",
            "dossier_id": dossier_id,
            "revision": 1,
            "created_at": now,
            "updated_at": now,
            "author": args.author or "maintainer",
            "title": args.title,
            "brief_id": args.brief_id or "",
            "candidate_player_id": args.candidate_player_id or "",
            "candidate_player_name": args.candidate_player_name or "",
            "candidate_team_name": args.candidate_team_name or "",
            "candidate_season_id": args.candidate_season_id or "",
            "status": status_value,
            "decision": decision_value,
            "decision_note": args.decision_note or "",
            "supporting_evidence": [],
            "counter_evidence": [],
            "comparisons": [],
            "risks": [],
            "human_opinion": args.human_opinion or "",
            "recommendation": args.recommendation or "",
            "linked_artifacts": args.linked_artifacts or [],
            "notes": args.notes or "",
            "limitations": [
                "Dossier is a personal local object; not an external fact.",
                "Decision is the maintainer's honest judgment, not an automated recommendation.",
            ],
        }

    try:
        store = _dossier_store()
        record = store.save(payload["dossier_id"], payload, expected_revision=0)
    except DossierValidationError as exc:
        print(f"error: dossier validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except DossierStoreError as exc:
        print(f"error: dossier store failed: {exc.code} (HTTP {exc.http_status})", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        dossier = record["dossier"]
        print(f"Created dossier: {dossier['dossier_id']} (revision {dossier['revision']})")
        print(f"  title: {dossier['title']}")
        print(f"  brief: {dossier.get('brief_id', '') or '(none)'}")
        print(
            f"  candidate: {dossier.get('candidate_player_name', '') or '-'} "
            f"({dossier.get('candidate_player_id', '') or '-'})"
        )
        print(f"  status: {dossier.get('status', 'draft')}")
        if dossier.get("decision"):
            print(f"  decision: {dossier['decision']}")
        print(f"  stored at: {store.root / (dossier['dossier_id'] + '.json')}")


def _cmd_list_dossiers(args: argparse.Namespace) -> None:
    """List stored decision dossiers."""
    import json

    store = _dossier_store()
    records = store.list_records(limit=args.limit)
    if args.json:
        print(json.dumps(
            {"count": len(records), "dossiers": records},
            ensure_ascii=False, indent=2,
        ))
    else:
        if not records:
            print("No dossiers found.")
            return
        print(f"Found {len(records)} dossier(s):")
        for rec in records:
            decision_str = f" decision={rec['decision']}" if rec.get("decision") else ""
            print(
                f"  {rec['dossier_id']}  rev={rec['server_revision']}  "
                f"{rec.get('title', '')}  "
                f"candidate={rec.get('candidate_player_name', '') or '-'}  "
                f"status={rec.get('status', '')}{decision_str}"
            )


def _cmd_show_dossier(args: argparse.Namespace) -> None:
    """Show one stored decision dossier."""
    import json

    from scoutfootball.recruitment.dossier_store import DossierStoreError

    try:
        store = _dossier_store()
        record = store.load(args.dossier_id)
    except DossierStoreError as exc:
        print(f"error: {exc.code} (HTTP {exc.http_status})", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        dossier = record["dossier"]
        print(f"Dossier: {dossier['dossier_id']}")
        print(f"  schema: {dossier['schema']} v{dossier['version']}")
        print(f"  revision: {dossier['revision']} (server_revision: {record['server_revision']})")
        print(f"  title: {dossier['title']}")
        print(f"  brief: {dossier.get('brief_id', '') or '(none)'}")
        print(
            f"  candidate: {dossier.get('candidate_player_name', '') or '-'} "
            f"({dossier.get('candidate_player_id', '') or '-'})"
        )
        if dossier.get("candidate_team_name"):
            print(f"  candidate team: {dossier['candidate_team_name']}")
        if dossier.get("candidate_season_id"):
            print(f"  candidate season: {dossier['candidate_season_id']}")
        print(f"  status: {dossier.get('status', 'draft')}")
        if dossier.get("decision"):
            print(f"  decision: {dossier['decision']}")
        if dossier.get("decision_note"):
            print(f"  decision note: {dossier['decision_note']}")
        if dossier.get("supporting_evidence"):
            print(f"  supporting evidence ({len(dossier['supporting_evidence'])}):")
            for ev in dossier["supporting_evidence"]:
                print(
                    f"    [{ev.get('evidence_id')}] "
                    f"{ev.get('fact_tier')}: {ev.get('summary', '')}"
                )
        if dossier.get("counter_evidence"):
            print(f"  counter evidence ({len(dossier['counter_evidence'])}):")
            for ev in dossier["counter_evidence"]:
                print(
                    f"    [{ev.get('evidence_id')}] "
                    f"{ev.get('fact_tier')}: {ev.get('summary', '')}"
                )
        if dossier.get("comparisons"):
            print(f"  comparisons ({len(dossier['comparisons'])}):")
            for cmp in dossier["comparisons"]:
                print(
                    f"    [{cmp.get('comparison_id')}] {cmp.get('comparison_player_name', '')} "
                    f"({cmp.get('comparison_player_id', '')})"
                )
        if dossier.get("risks"):
            print(f"  risks ({len(dossier['risks'])}):")
            for risk in dossier["risks"]:
                print(
                    f"    [{risk.get('risk_id')}] "
                    f"severity={risk.get('severity')}: {risk.get('summary', '')}"
                )
        if dossier.get("human_opinion"):
            print(f"  human opinion: {dossier['human_opinion']}")
        if dossier.get("recommendation"):
            print(f"  recommendation: {dossier['recommendation']}")
        if dossier.get("linked_artifacts"):
            print(f"  linked artifacts: {', '.join(dossier['linked_artifacts'])}")
        if dossier.get("notes"):
            print(f"  notes: {dossier['notes']}")
        print(f"  created: {dossier.get('created_at', '?')}")
        print(f"  updated: {dossier.get('updated_at', '?')}")
        print(f"  stored: {record.get('stored_at', '?')}")


def _cmd_validate_dossier(args: argparse.Namespace) -> None:
    """Validate a local dossier JSON file without saving it."""
    import json

    from scoutfootball.recruitment.dossier import (
        DossierValidationError,
        validate_dossier_payload,
    )

    path = Path(args.path)
    if path.is_symlink() or not path.is_file():
        print(f"error: dossier file must be a regular local file: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: cannot read dossier JSON: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        dossier = validate_dossier_payload(payload)
    except DossierValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        result = {"status": "valid", "dossier_id": dossier.dossier_id}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"VALID: {dossier.dossier_id} (schema={dossier.schema_name} v={dossier.version})")


# ── Opposition briefing CLI ──────────────────────────────────────────────


def _cmd_create_briefing(args: argparse.Namespace) -> None:
    """Create a new source-limited match briefing from CLI flags or JSON."""
    import json
    import uuid as _uuid
    from datetime import UTC, datetime

    from scoutfootball.opposition.briefing import (
        BriefingValidationError,
        validate_briefing_id,
    )
    from scoutfootball.opposition.store import BriefingStoreError

    if args.from_json:
        path = Path(args.from_json)
        if path.is_symlink() or not path.is_file():
            print(
                f"error: briefing JSON must be a regular local file: {path}",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(
                f"error: cannot read briefing JSON: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)
        if not isinstance(payload, dict):
            print("error: briefing JSON must be an object", file=sys.stderr)
            sys.exit(1)
        if not payload.get("briefing_id"):
            date_part = datetime.now(tz=UTC).strftime("%Y%m%d")
            uuid_part = _uuid.uuid4().hex[:8]
            payload["briefing_id"] = f"briefing-{date_part}-{uuid_part}"
    else:
        if not args.title:
            print(
                "error: --title is required when not using --from-json",
                file=sys.stderr,
            )
            sys.exit(2)
        date_part = datetime.now(tz=UTC).strftime("%Y%m%d")
        uuid_part = _uuid.uuid4().hex[:8]
        briefing_id = args.briefing_id or f"briefing-{date_part}-{uuid_part}"
        validate_briefing_id(briefing_id)
        now = datetime.now(tz=UTC).isoformat()
        sections = []
        # Build sections from CLI flags.  Each section flag has the form
        # "<section_id>:<fact_tier>:<summary>"; evidence_refs are appended
        # via repeated --section-evidence "<section_id>:<ref>" flags.
        # Custom section IDs of the form "custom:<tail>" themselves contain
        # a colon, so the parser must treat "custom:" as a prefix when
        # locating the field separator.
        def _split_section_field(entry: str) -> tuple[str, str, str]:
            if entry.startswith("custom:"):
                rest = entry[len("custom:"):]
                colon = rest.find(":")
                if colon == -1:
                    raise ValueError(
                        "--section must be '<section_id>:<fact_tier>:<summary>'"
                    )
                sid = f"custom:{rest[:colon]}"
                remainder = rest[colon + 1:]
                tier_colon = remainder.find(":")
                if tier_colon == -1:
                    raise ValueError(
                        "--section must be '<section_id>:<fact_tier>:<summary>'"
                    )
                return sid, remainder[:tier_colon], remainder[tier_colon + 1:]
            parts = entry.split(":", 2)
            if len(parts) != 3:
                raise ValueError(
                    "--section must be '<section_id>:<fact_tier>:<summary>'"
                )
            return parts[0], parts[1], parts[2]

        def _split_evidence_field(entry: str) -> tuple[str, str]:
            if entry.startswith("custom:"):
                rest = entry[len("custom:"):]
                colon = rest.find(":")
                if colon == -1:
                    raise ValueError("--section-evidence must be '<section_id>:<ref>'")
                return f"custom:{rest[:colon]}", rest[colon + 1:]
            if ":" not in entry:
                raise ValueError("--section-evidence must be '<section_id>:<ref>'")
            sid, ref = entry.split(":", 1)
            return sid, ref

        section_evidence: dict[str, list[str]] = {}
        for entry in args.section_evidence or []:
            try:
                sid, ref = _split_evidence_field(entry)
            except ValueError:
                print(
                    f"error: --section-evidence must be '<section_id>:<ref>', got: {entry}",
                    file=sys.stderr,
                )
                sys.exit(2)
            section_evidence.setdefault(sid, []).append(ref)
        for entry in args.section or []:
            try:
                sid, tier, summary = _split_section_field(entry)
            except ValueError:
                print(
                    f"error: --section must be '<section_id>:<fact_tier>:<summary>', got: {entry}",
                    file=sys.stderr,
                )
                sys.exit(2)
            sections.append({
                "section_id": sid,
                "fact_tier": tier,
                "summary": summary,
                "evidence_refs": section_evidence.get(sid, []),
            })
        kickoff = args.kickoff_at if args.kickoff_at else None
        payload = {
            "schema": "scoutfootball.opposition-briefing",
            "version": "1.0.0",
            "briefing_id": briefing_id,
            "revision": 1,
            "created_at": now,
            "updated_at": now,
            "author": args.author or "maintainer",
            "title": args.title,
            "match_id": args.match_id or "",
            "home_team": args.home_team or "",
            "away_team": args.away_team or "",
            "kickoff_at": kickoff,
            "competition": args.competition or "",
            "season": args.season or "",
            "sections": sections,
            "linked_pattern_card_ids": args.linked_pattern_card_ids or [],
            "linked_scenario_tree_id": args.linked_scenario_tree_id,
            "linked_post_match_review_id": args.linked_post_match_review_id,
            "notes": args.notes or "",
            "limitations": [
                "Briefing is a personal local object; not an external fact.",
                "fact_tier is the maintainer's honest classification, not automated.",
            ],
        }

    try:
        store = _briefing_store()
        record = store.save(payload["briefing_id"], payload, expected_revision=0)
    except BriefingValidationError as exc:
        print(f"error: briefing validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except BriefingStoreError as exc:
        print(
            f"error: briefing store failed: {exc.code} (HTTP {exc.http_status})",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        briefing = record["briefing"]
        print(
            f"Created briefing: {briefing['briefing_id']} (revision {briefing['revision']})"
        )
        print(f"  title: {briefing['title']}")
        print(
            f"  match: {briefing.get('home_team', '')} vs "
            f"{briefing.get('away_team', '') or '(unknown)'}"
        )
        if briefing.get("kickoff_at"):
            print(f"  kickoff: {briefing['kickoff_at']}")
        if briefing.get("competition"):
            print(f"  competition: {briefing['competition']}")
        print(f"  sections: {len(briefing.get('sections', []))}")
        for sec in briefing.get("sections", []):
            print(
                f"    - {sec['section_id']} [{sec.get('fact_tier', 'unknown')}] "
                f"({len(sec.get('evidence_refs', []))} refs)"
            )
        print(f"  stored at: {store.root / (briefing['briefing_id'] + '.json')}")


def _cmd_list_briefings(args: argparse.Namespace) -> None:
    """List stored source-limited match briefings."""
    import json

    store = _briefing_store()
    records = store.list_records(limit=args.limit)
    if args.json:
        print(
            json.dumps(
                {"count": len(records), "briefings": records},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        if not records:
            print("No briefings found.")
            return
        print(f"Found {len(records)} briefing(s):")
        for rec in records:
            print(
                f"  {rec['briefing_id']}  rev={rec['server_revision']}  "
                f"{rec.get('title', '')}  "
                f"{rec.get('home_team', '') or '-'} vs "
                f"{rec.get('away_team', '') or '-'}  "
                f"comp={rec.get('competition', '') or '-'}"
            )


def _cmd_show_briefing(args: argparse.Namespace) -> None:
    """Show one stored source-limited match briefing."""
    import json

    from scoutfootball.opposition.store import BriefingStoreError

    try:
        store = _briefing_store()
        record = store.load(args.briefing_id)
    except BriefingStoreError as exc:
        print(f"error: {exc.code} (HTTP {exc.http_status})", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        briefing = record["briefing"]
        print(f"Briefing: {briefing['briefing_id']}")
        print(f"  schema: {briefing['schema']} v{briefing['version']}")
        print(
            f"  revision: {briefing['revision']} "
            f"(server_revision: {record['server_revision']})"
        )
        print(f"  title: {briefing['title']}")
        print(
            f"  match: {briefing.get('home_team', '') or '(none)'} vs "
            f"{briefing.get('away_team', '') or '(unknown)'}"
        )
        if briefing.get("kickoff_at"):
            print(f"  kickoff: {briefing['kickoff_at']}")
        if briefing.get("competition"):
            print(f"  competition: {briefing['competition']}")
        if briefing.get("season"):
            print(f"  season: {briefing['season']}")
        if briefing.get("match_id"):
            print(f"  match_id: {briefing['match_id']}")
        if briefing.get("sections"):
            print(f"  sections ({len(briefing['sections'])}):")
            for sec in briefing["sections"]:
                print(
                    f"    - {sec['section_id']} [{sec.get('fact_tier', 'unknown')}]"
                )
                if sec.get("summary"):
                    summary = sec["summary"]
                    if len(summary) > 100:
                        summary = summary[:97] + "..."
                    print(f"        {summary}")
                if sec.get("evidence_refs"):
                    print(f"        evidence: {len(sec['evidence_refs'])} ref(s)")
        if briefing.get("linked_pattern_card_ids"):
            print(
                f"  linked pattern cards: {', '.join(briefing['linked_pattern_card_ids'])}"
            )
        if briefing.get("linked_scenario_tree_id"):
            print(f"  linked scenario tree: {briefing['linked_scenario_tree_id']}")
        if briefing.get("linked_post_match_review_id"):
            print(
                f"  linked post-match review: {briefing['linked_post_match_review_id']}"
            )
        if briefing.get("notes"):
            print(f"  notes: {briefing['notes']}")
        print(f"  created: {briefing.get('created_at', '?')}")
        print(f"  updated: {briefing.get('updated_at', '?')}")
        print(f"  stored: {record.get('stored_at', '?')}")


def _cmd_validate_briefing(args: argparse.Namespace) -> None:
    """Validate a local briefing JSON file without saving it."""
    import json

    from scoutfootball.opposition.briefing import (
        BriefingValidationError,
        validate_briefing_payload,
    )

    path = Path(args.path)
    if path.is_symlink() or not path.is_file():
        print(
            f"error: briefing file must be a regular local file: {path}",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(
            f"error: cannot read briefing JSON: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        briefing = validate_briefing_payload(payload)
    except BriefingValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        result = {"status": "valid", "briefing_id": briefing.briefing_id}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"VALID: {briefing.briefing_id} (schema={briefing.schema_name} v={briefing.version})"
        )


# ── Opposition post-match review CLI ─────────────────────────────────────


def _cmd_create_review(args: argparse.Namespace) -> None:
    """Create a new post-match review from CLI flags or a JSON file."""
    import json
    import uuid as _uuid
    from datetime import UTC, datetime

    from scoutfootball.opposition.post_match_review import (
        ReviewValidationError,
        validate_review_id,
    )
    from scoutfootball.opposition.post_match_review_store import ReviewStoreError

    if args.from_json:
        path = Path(args.from_json)
        if path.is_symlink() or not path.is_file():
            print(
                f"error: review JSON must be a regular local file: {path}",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(
                f"error: cannot read review JSON: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)
        if not isinstance(payload, dict):
            print("error: review JSON must be an object", file=sys.stderr)
            sys.exit(1)
        if not payload.get("review_id"):
            date_part = datetime.now(tz=UTC).strftime("%Y%m%d")
            uuid_part = _uuid.uuid4().hex[:8]
            payload["review_id"] = f"review-{date_part}-{uuid_part}"
    else:
        if not args.title:
            print(
                "error: --title is required when not using --from-json",
                file=sys.stderr,
            )
            sys.exit(2)
        date_part = datetime.now(tz=UTC).strftime("%Y%m%d")
        uuid_part = _uuid.uuid4().hex[:8]
        review_id = args.review_id or f"review-{date_part}-{uuid_part}"
        try:
            validate_review_id(review_id)
        except ReviewValidationError as exc:
            print(f"error: invalid review id: {exc}", file=sys.stderr)
            sys.exit(1)
        now = datetime.now(tz=UTC).isoformat()
        # Status/decision consistency: when --decision is given we force
        # status="finalized"; otherwise default to "draft" with decision=null.
        decision_value = args.decision or None
        status_value = (
            "finalized" if decision_value else (args.status or "draft")
        )
        if decision_value and status_value != "finalized":
            print(
                f"error: --decision requires --status finalized (got {status_value!r})",
                file=sys.stderr,
            )
            sys.exit(2)
        kickoff = args.kickoff_at if args.kickoff_at else None
        final_score_home = args.final_score_home
        if final_score_home is not None and final_score_home < 0:
            print("error: --final-score-home must be >= 0", file=sys.stderr)
            sys.exit(2)
        final_score_away = args.final_score_away
        if final_score_away is not None and final_score_away < 0:
            print("error: --final-score-away must be >= 0", file=sys.stderr)
            sys.exit(2)
        payload = {
            "schema": "scoutfootball.opposition-post-match-review",
            "version": "1.0.0",
            "review_id": review_id,
            "revision": 1,
            "created_at": now,
            "updated_at": now,
            "author": args.author or "maintainer",
            "title": args.title,
            "briefing_id": args.briefing_id or "",
            "match_id": args.match_id or "",
            "home_team": args.home_team or "",
            "away_team": args.away_team or "",
            "kickoff_at": kickoff,
            "competition": args.competition or "",
            "season": args.season or "",
            "final_score_home": final_score_home,
            "final_score_away": final_score_away,
            "status": status_value,
            "decision": decision_value,
            "decision_note": args.decision_note or "",
            "hypothesis_results": [],
            "falsified_patterns": [],
            "new_questions": [],
            "supporting_evidence": [],
            "counter_evidence": [],
            "human_opinion": args.human_opinion or "",
            "recommendation": args.recommendation or "",
            "linked_artifacts": args.linked_artifacts or [],
            "notes": args.notes or "",
            "limitations": [
                "PostMatchReview is a personal local object; not an external fact.",
                "Decision is the maintainer's honest judgment, not an automated recommendation.",
            ],
        }

    try:
        store = _review_store()
        record = store.save(payload["review_id"], payload, expected_revision=0)
    except ReviewValidationError as exc:
        print(f"error: review validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except ReviewStoreError as exc:
        print(
            f"error: review store failed: {exc.code} (HTTP {exc.http_status})",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        review = record["review"]
        print(
            f"Created review: {review['review_id']} (revision {review['revision']})"
        )
        print(f"  title: {review['title']}")
        print(
            f"  match: {review.get('home_team', '')} vs "
            f"{review.get('away_team', '') or '(unknown)'}"
        )
        if review.get("kickoff_at"):
            print(f"  kickoff: {review['kickoff_at']}")
        if review.get("competition"):
            print(f"  competition: {review['competition']}")
        if review.get("final_score_home") is not None:
            print(
                f"  final score: {review['final_score_home']} - "
                f"{review.get('final_score_away')}"
            )
        print(f"  status: {review.get('status', 'draft')}")
        if review.get("decision"):
            print(f"  decision: {review['decision']}")
        print(f"  stored at: {store.root / (review['review_id'] + '.json')}")


def _cmd_list_reviews(args: argparse.Namespace) -> None:
    """List stored post-match reviews."""
    import json

    store = _review_store()
    records = store.list_records(limit=args.limit)
    if args.json:
        print(
            json.dumps(
                {"count": len(records), "reviews": records},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        if not records:
            print("No reviews found.")
            return
        print(f"Found {len(records)} review(s):")
        for rec in records:
            decision_str = (
                f" decision={rec['decision']}" if rec.get("decision") else ""
            )
            print(
                f"  {rec['review_id']}  rev={rec['server_revision']}  "
                f"{rec.get('title', '')}  "
                f"{rec.get('home_team', '') or '-'} vs "
                f"{rec.get('away_team', '') or '-'}  "
                f"status={rec.get('status', '')}{decision_str}"
            )


def _cmd_show_review(args: argparse.Namespace) -> None:
    """Show one stored post-match review."""
    import json

    from scoutfootball.opposition.post_match_review_store import ReviewStoreError

    try:
        store = _review_store()
        record = store.load(args.review_id)
    except ReviewStoreError as exc:
        print(f"error: {exc.code} (HTTP {exc.http_status})", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        review = record["review"]
        print(f"Review: {review['review_id']}")
        print(f"  schema: {review['schema']} v{review['version']}")
        print(
            f"  revision: {review['revision']} "
            f"(server_revision: {record['server_revision']})"
        )
        print(f"  title: {review['title']}")
        if review.get("briefing_id"):
            print(f"  briefing: {review['briefing_id']}")
        if review.get("match_id"):
            print(f"  match_id: {review['match_id']}")
        print(
            f"  match: {review.get('home_team', '') or '(none)'} vs "
            f"{review.get('away_team', '') or '(unknown)'}"
        )
        if review.get("kickoff_at"):
            print(f"  kickoff: {review['kickoff_at']}")
        if review.get("competition"):
            print(f"  competition: {review['competition']}")
        if review.get("season"):
            print(f"  season: {review['season']}")
        if review.get("final_score_home") is not None:
            print(
                f"  final score: {review['final_score_home']} - "
                f"{review.get('final_score_away')}"
            )
        print(f"  status: {review.get('status', 'draft')}")
        if review.get("decision"):
            print(f"  decision: {review['decision']}")
        if review.get("decision_note"):
            print(f"  decision note: {review['decision_note']}")
        if review.get("hypothesis_results"):
            print(
                f"  hypothesis results ({len(review['hypothesis_results'])}):"
            )
            for h in review["hypothesis_results"]:
                print(
                    f"    [{h.get('hypothesis_id')}] outcome={h.get('outcome')} "
                    f"tier={h.get('fact_tier')}"
                )
                if h.get("planned"):
                    planned = h["planned"]
                    if len(planned) > 100:
                        planned = planned[:97] + "..."
                    print(f"        planned: {planned}")
                if h.get("observed"):
                    observed = h["observed"]
                    if len(observed) > 100:
                        observed = observed[:97] + "..."
                    print(f"        observed: {observed}")
        if review.get("falsified_patterns"):
            print(
                f"  falsified patterns ({len(review['falsified_patterns'])}):"
            )
            for p in review["falsified_patterns"]:
                print(
                    f"    [{p.get('pattern_id')}] severity={p.get('severity')} "
                    f"tier={p.get('fact_tier')}"
                )
        if review.get("new_questions"):
            print(f"  new questions ({len(review['new_questions'])}):")
            for q in review["new_questions"]:
                print(
                    f"    [{q.get('question_id')}] scope={q.get('scope', '') or '-'} "
                    f"tier={q.get('fact_tier')}"
                )
        if review.get("supporting_evidence"):
            print(
                f"  supporting evidence ({len(review['supporting_evidence'])}):"
            )
            for ev in review["supporting_evidence"]:
                print(
                    f"    [{ev.get('evidence_id')}] "
                    f"{ev.get('fact_tier')}: {ev.get('summary', '')}"
                )
        if review.get("counter_evidence"):
            print(
                f"  counter evidence ({len(review['counter_evidence'])}):"
            )
            for ev in review["counter_evidence"]:
                print(
                    f"    [{ev.get('evidence_id')}] "
                    f"{ev.get('fact_tier')}: {ev.get('summary', '')}"
                )
        if review.get("human_opinion"):
            print(f"  human opinion: {review['human_opinion']}")
        if review.get("recommendation"):
            print(f"  recommendation: {review['recommendation']}")
        if review.get("linked_artifacts"):
            print(
                f"  linked artifacts: {', '.join(review['linked_artifacts'])}"
            )
        if review.get("notes"):
            print(f"  notes: {review['notes']}")
        if review.get("limitations"):
            print(f"  limitations: {len(review['limitations'])} item(s)")
        print(f"  created: {review.get('created_at', '?')}")
        print(f"  updated: {review.get('updated_at', '?')}")
        print(f"  stored: {record.get('stored_at', '?')}")


def _cmd_validate_review(args: argparse.Namespace) -> None:
    """Validate a local review JSON file without saving it."""
    import json

    from scoutfootball.opposition.post_match_review import (
        ReviewValidationError,
        validate_review_payload,
    )

    path = Path(args.path)
    if path.is_symlink() or not path.is_file():
        print(
            f"error: review file must be a regular local file: {path}",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(
            f"error: cannot read review JSON: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        review = validate_review_payload(payload)
    except ReviewValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        result = {"status": "valid", "review_id": review.review_id}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"VALID: {review.review_id} (schema={review.schema_name} v={review.version})"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scoutfootball",
        description="ScoutFootball — local-first football data research platform",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("info", help="Show project info and module status")

    caps_p = sub.add_parser(
        "capabilities",
        help="List all project capabilities with CLI/API/frontend entry points",
    )
    caps_p.add_argument("--domain", type=str, default=None, help="Filter by domain")
    caps_p.add_argument(
        "--json", action="store_true", help="Emit JSON instead of human-readable text"
    )
    caps_p.add_argument("--counts", action="store_true", help="Show status counts summary")

    dc_p = sub.add_parser(
        "data-contracts",
        help="List all data contracts with license, schema, lineage and coverage",
    )
    dc_p.add_argument("--layer", type=str, default=None, help="Filter by layer")
    dc_p.add_argument(
        "--json", action="store_true", help="Emit JSON instead of human-readable text"
    )
    dc_p.add_argument("--counts", action="store_true", help="Show layer counts summary")

    adapters_p = sub.add_parser(
        "list-adapters",
        help="List provider adapter manifests with capabilities, schema mappings and loss notes",
    )
    adapters_p.add_argument(
        "--source", type=str, default=None, help="Filter by source_id (e.g. statsbomb_open)"
    )
    adapters_p.add_argument(
        "--capability",
        type=str,
        default=None,
        help="Filter by AdapterCapability (e.g. event, player_stats, identity)",
    )
    adapters_p.add_argument(
        "--verbose",
        action="store_true",
        help="Show full schema mapping detail per adapter",
    )
    adapters_p.add_argument(
        "--json", action="store_true", help="Emit JSON instead of human-readable text"
    )

    adapter_compatibility_p = sub.add_parser(
        "adapter-compatibility",
        help="Show project-local adapter admission and input-contract coverage",
    )
    adapter_compatibility_p.add_argument(
        "--source", type=str, default=None, help="Filter by source_id"
    )
    adapter_compatibility_p.add_argument(
        "--json", action="store_true", help="Emit JSON instead of human-readable text"
    )

    ingest_p = sub.add_parser("ingest", help="Run daily data ingestion")
    ingest_p.add_argument(
        "--sources",
        nargs="+",
        default=["statsbomb_open", "football_data", "clubelo"],
        help="Data sources to ingest",
    )

    sub.add_parser("build-features", help="Build feature store from raw data")
    train_p = sub.add_parser("train", help="Run weekly model training")
    train_p.add_argument(
        "--force",
        action="store_true",
        help="Train even if pre-training validation fails (default: skip on failure)",
    )
    nn_p = sub.add_parser(
        "train-rating-nn",
        help="Train supervised player-rating neural-network candidate",
    )
    nn_p.add_argument("--min-labels", type=int, default=200)
    nn_p.add_argument("--max-iter", type=int, default=300)
    nn_p.add_argument("--seed", type=int, default=42)
    nn_p.add_argument("--output-dir", type=str, default=None)
    nn_p.add_argument(
        "--force",
        action="store_true",
        help="Train even if pre-training validation fails (default: skip on failure)",
    )
    sub.add_parser("validate", help="Run pre-training data validation")
    source_health_p = sub.add_parser(
        "source-health", help="Inspect registered local raw-source health without network access"
    )
    source_health_p.add_argument("--json", action="store_true", help="Emit JSON")
    source_health_p.add_argument(
        "--evidence", help="Optional local preflight evidence JSON to attach by registered source"
    )
    source_health_p.add_argument(
        "--snapshot-ledger",
        help=(
            "Optional append-only local source snapshot ledger; when omitted, the "
            "canonical default at data/reports/data_health/source_snapshot_ledger.jsonl "
            "is auto-discovered."
        ),
    )
    source_health_p.add_argument(
        "--policy-ledger",
        help=(
            "Optional append-only local source policy ledger; when omitted, the "
            "canonical default at data/reports/data_health/source_policy_ledger.jsonl "
            "is auto-discovered."
        ),
    )
    contract_quality_p = sub.add_parser(
        "contract-quality",
        help="Report contract-quality gates and honest baseline gaps from local evidence",
    )
    contract_quality_p.add_argument("--json", action="store_true", help="Emit JSON")
    contract_quality_p.add_argument(
        "--evidence",
        help=(
            "Optional local preflight evidence JSON; auto-discovered at "
            "data/reports/data_health/preflight_evidence.json when omitted."
        ),
    )
    contract_quality_p.add_argument(
        "--snapshot-ledger",
        help=(
            "Optional append-only local source snapshot ledger; auto-discovered at "
            "data/reports/data_health/source_snapshot_ledger.jsonl when omitted."
        ),
    )
    contract_quality_p.add_argument(
        "--policy-ledger",
        help=(
            "Optional append-only local source policy ledger; auto-discovered at "
            "data/reports/data_health/source_policy_ledger.jsonl when omitted."
        ),
    )
    contract_quality_p.add_argument(
        "--audit-ledger",
        help=(
            "Optional append-only local identity/source claim audit ledger; auto-discovered "
            "at data/reports/data_health/quality_audit_ledger.jsonl when omitted."
        ),
    )
    contract_quality_p.add_argument(
        "--threshold-ledger",
        help=(
            "Optional append-only local quality-threshold ledger; auto-discovered at "
            "data/reports/data_health/quality_threshold_ledger.jsonl when omitted."
        ),
    )
    model_admission_p = sub.add_parser(
        "model-admission",
        help="Check whether local optimizer runs have evidence for human promotion review",
    )
    model_admission_p.add_argument("--run-id", default=None)
    model_admission_p.add_argument("--json", action="store_true", help="Emit JSON")
    sub.add_parser(
        "research-health",
        help=(
            "Report five-layer research health of the rating system "
            "(PRS-0 R-003/R-004); fail-closed verdict, never hides stale/"
            "unreviewable/synthetic/non-independent-label states behind ok"
        ),
    )
    discard_model_run_p = sub.add_parser(
        "discard-model-run",
        help="Preview or discard one unactivated local optimizer candidate",
    )
    discard_model_run_p.add_argument("run_id", help="Candidate run directory name")
    discard_model_run_p.add_argument(
        "--confirm", action="store_true", help="Actually delete the selected candidate directory"
    )
    discard_model_run_p.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Allow a confirmed discard when the run lacks readable metadata",
    )
    discard_model_run_p.add_argument("--json", action="store_true", help="Emit JSON")
    reject_model_run_p = sub.add_parser(
        "reject-model-run",
        help="Preview or record an explicit local rejection of one unactivated optimizer candidate",
    )
    reject_model_run_p.add_argument("run_id", help="Candidate run directory name")
    reject_model_run_p.add_argument(
        "--decision", required=True, help="Maintainer decision text retained in candidate metadata"
    )
    reject_model_run_p.add_argument(
        "--confirm", action="store_true", help="Actually record the rejection in candidate metadata"
    )
    reject_model_run_p.add_argument("--json", action="store_true", help="Emit JSON")
    promote_model_run_p = sub.add_parser(
        "promote-model-run",
        help="Preview or promote one reviewable local optimizer candidate with a reversible backup",
    )
    promote_model_run_p.add_argument("run_id", help="Candidate run directory name")
    promote_model_run_p.add_argument(
        "--decision", required=True, help="Maintainer decision text retained with the activation"
    )
    promote_model_run_p.add_argument(
        "--confirm", action="store_true", help="Back up and replace active local rating artifacts"
    )
    promote_model_run_p.add_argument("--json", action="store_true", help="Emit JSON")
    rollback_model_run_p = sub.add_parser(
        "rollback-model-run",
        help="Preview or restore one verified active-artifact backup",
    )
    rollback_model_run_p.add_argument(
        "backup_id", help="Backup directory name created during promotion"
    )
    rollback_model_run_p.add_argument(
        "--decision", required=True, help="Maintainer reason retained in the rollback record"
    )
    rollback_model_run_p.add_argument(
        "--confirm", action="store_true", help="Actually restore the selected backup"
    )
    rollback_model_run_p.add_argument("--json", action="store_true", help="Emit JSON")
    decision_package_p = sub.add_parser(
        "validate-decision-package",
        help="Validate one local decision-package JSON export without importing or changing it",
    )
    decision_package_p.add_argument("path", help="Path to a browser-local JSON export")
    decision_package_p.add_argument("--json", action="store_true", help="Emit JSON")
    snapshot_p = sub.add_parser(
        "record-source-snapshot",
        help="Append an explicitly dated local source snapshot backed by preflight evidence",
    )
    snapshot_p.add_argument("--source", required=True, help="Registered raw source identifier")
    snapshot_p.add_argument(
        "--snapshot-date", required=True, help="Explicit upstream snapshot date (YYYY-MM-DD)"
    )
    snapshot_p.add_argument("--evidence", required=True, help="Local preflight evidence JSON")
    snapshot_p.add_argument(
        "--ledger",
        default="data/reports/data_health/source_snapshot_ledger.jsonl",
        help="Local append-only JSONL ledger path",
    )
    snapshot_p.add_argument("--json", action="store_true", help="Emit the appended record as JSON")
    raw_inspection_p = sub.add_parser(
        "inspect-raw-source",
        help="Inspect one registered local UTF-8 CSV source file and write local evidence",
    )
    raw_inspection_p.add_argument(
        "--source", required=True, help="Registered raw source identifier"
    )
    raw_inspection_p.add_argument(
        "--path", required=True, help="CSV path under the registered source directory"
    )
    raw_inspection_p.add_argument(
        "--evidence-out", required=True, help="Output path for local inspection JSON"
    )
    raw_inspection_p.add_argument(
        "--overwrite", action="store_true", help="Allow replacement of an existing evidence JSON"
    )
    raw_inspection_p.add_argument("--json", action="store_true", help="Emit the evidence payload")
    reep_identity_p = sub.add_parser(
        "reep-identity-lookup",
        help="Look up an exact provider ID in a local Reep identity snapshot for manual review",
    )
    reep_identity_p.add_argument(
        "--provider",
        required=True,
        choices=("transfermarkt", "fbref", "wikidata"),
        help="Provider identifier namespace to query exactly",
    )
    reep_identity_p.add_argument(
        "--id", dest="provider_id", required=True, help="Exact provider identifier"
    )
    reep_identity_p.add_argument(
        "--path",
        default="raw/reep/people.csv",
        help="Local CSV path below data/raw/reep",
    )
    reep_identity_p.add_argument(
        "--limit", type=int, default=20, help="Maximum matches returned (1-100)"
    )
    reep_identity_p.add_argument(
        "--snapshot-ledger",
        default="data/reports/data_health/source_snapshot_ledger.jsonl",
        help="Optional local source-snapshot ledger for provenance display",
    )
    reep_identity_p.add_argument("--json", action="store_true", help="Emit JSON")
    policy_p = sub.add_parser(
        "record-source-policy",
        help="Preview or append an explicit local source retention/deletion policy",
    )
    policy_p.add_argument("--source", required=True, help="Registered raw source identifier")
    policy_p.add_argument(
        "--retention-mode",
        required=True,
        choices=("days", "until_manual_deletion", "until_rights_change"),
        help="Explicit local retention policy mode",
    )
    policy_p.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help="Required only when --retention-mode days",
    )
    policy_p.add_argument(
        "--deletion-trigger",
        required=True,
        help="Maintainer-recorded condition that starts deletion handling",
    )
    policy_p.add_argument(
        "--deletion-strategy",
        required=True,
        help="Maintainer-recorded local raw-content deletion procedure",
    )
    policy_p.add_argument(
        "--derived-artifact-action",
        required=True,
        help="Maintainer-recorded handling for dependent local artifacts",
    )
    policy_p.add_argument(
        "--decision", required=True, help="Maintainer decision text retained in the ledger")
    policy_p.add_argument(
        "--ledger",
        default="data/reports/data_health/source_policy_ledger.jsonl",
        help="Local append-only JSONL policy ledger path",
    )
    policy_p.add_argument(
        "--confirm", action="store_true", help="Actually append the policy declaration"
    )
    policy_p.add_argument("--json", action="store_true", help="Emit JSON")
    quality_audit_p = sub.add_parser(
        "record-quality-audit",
        help="Preview or append one explicit local identity or source-claim audit sample",
    )
    quality_audit_p.add_argument(
        "--audit-kind",
        required=True,
        choices=("identity_resolution", "source_claim"),
        help="The reviewed C1 quality dimension",
    )
    quality_audit_p.add_argument("--source", required=True, help="Registered raw source identifier")
    quality_audit_p.add_argument(
        "--sample-id", required=True, help="Opaque local identifier for the reviewed sample"
    )
    quality_audit_p.add_argument(
        "--outcome",
        required=True,
        choices=("confirmed_correct", "confirmed_error"),
        help="Maintainer-confirmed outcome; never inferred by the command",
    )
    quality_audit_p.add_argument(
        "--reviewer", required=True, help="Local reviewer identifier retained with the audit"
    )
    quality_audit_p.add_argument(
        "--evidence-reference",
        required=True,
        help="Opaque local reference locating the reviewed evidence",
    )
    quality_audit_p.add_argument(
        "--decision", required=True, help="Maintainer decision text retained in the ledger"
    )
    quality_audit_p.add_argument(
        "--supersedes",
        default=None,
        help="Optional prior audit ID for an append-only correction of the same sample",
    )
    quality_audit_p.add_argument(
        "--ledger",
        default="data/reports/data_health/quality_audit_ledger.jsonl",
        help="Local append-only JSONL audit ledger path",
    )
    quality_audit_p.add_argument(
        "--confirm", action="store_true", help="Actually append the reviewed sample"
    )
    quality_audit_p.add_argument("--json", action="store_true", help="Emit JSON")
    quality_threshold_p = sub.add_parser(
        "record-quality-threshold",
        help="Preview or append a maintainer-selected local quality threshold",
    )
    quality_threshold_p.add_argument(
        "--audit-kind",
        required=True,
        choices=("identity_resolution", "source_claim"),
        help="The C1 quality dimension governed by the threshold",
    )
    quality_threshold_p.add_argument(
        "--maximum-error-rate",
        required=True,
        type=float,
        help="Maintainer-selected maximum observed error rate from 0 to 1",
    )
    quality_threshold_p.add_argument(
        "--minimum-sample-count",
        required=True,
        type=int,
        help="Minimum effective reviewed samples before this threshold can apply",
    )
    quality_threshold_p.add_argument(
        "--decision", required=True, help="Maintainer rationale retained in the ledger"
    )
    quality_threshold_p.add_argument(
        "--ledger",
        default="data/reports/data_health/quality_threshold_ledger.jsonl",
        help="Local append-only JSONL threshold ledger path",
    )
    quality_threshold_p.add_argument(
        "--confirm", action="store_true", help="Actually append the threshold declaration"
    )
    quality_threshold_p.add_argument("--json", action="store_true", help="Emit JSON")
    preflight_p = sub.add_parser(
        "optimizer-preflight",
        help="Check rating optimizer runtime and raw inputs",
    )
    preflight_p.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing raw optimizer inputs",
    )

    pf_p = sub.add_parser(
        "preflight",
        help="Content-level Parquet preflight (footer vs decode, schema, hash)",
    )
    pf_p.add_argument(
        "paths",
        nargs="*",
        help="Optional explicit parquet paths (absolute or relative to data root). "
        "Defaults to the project's key artifacts.",
    )
    pf_p.add_argument(
        "--target",
        choices=["raw", "gold", "sample", "key", "all"],
        default="key",
        help="Which artifact set to scan when no explicit paths are given",
    )
    pf_p.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON manifest instead of human-readable text",
    )
    pf_p.add_argument(
        "--evidence-out",
        default=None,
        help=(
            "Write a portable evidence JSON report that links the inspected files to "
            "recorded contract, source-license, snapshot, and lineage metadata. "
            "Refuses to overwrite an existing file by default."
        ),
    )
    pf_p.add_argument(
        "--overwrite-evidence",
        action="store_true",
        help="Allow --evidence-out to replace an existing local report.",
    )
    pf_p.add_argument(
        "--quarantine",
        action="store_true",
        help="Move unreadable files into data/quarantine/ (reversible; manifest written). "
        "Default is report-only.",
    )

    av_p = sub.add_parser(
        "action-value",
        help="Run action value pipeline (StatsBomb -> xT -> player metrics)",
    )
    av_p.add_argument(
        "--events-path", type=str, default=None,
        help="Path to StatsBomb events Parquet",
    )
    av_p.add_argument(
        "--output-path", type=str, default=None,
        help="Path to output player_value_metrics Parquet",
    )
    avm_p = sub.add_parser(
        "action-value-matches",
        help="Build sample-bounded player-team-match xT rows with match context",
    )
    avm_p.add_argument("--events-path", type=str, default=None)
    avm_p.add_argument("--matches-path", type=str, default=None)
    avm_p.add_argument("--output-path", type=str, default=None)
    avm_p.add_argument(
        "--coverage-scope",
        choices=["sample"],
        default="sample",
        help="Coverage declaration for the bundled three-match event sample",
    )

    sub.add_parser("export-ratings", help="Export ratings to DuckDB database")

    export_local_pack_p = sub.add_parser(
        "export-local-pack",
        help="Bundle local recruitment briefs and opposition briefings into a portable JSON pack",
    )
    export_local_pack_p.add_argument(
        "--output",
        default=None,
        help="Write the pack to this path. If omitted, the pack JSON is written to stdout.",
    )

    import_local_pack_p = sub.add_parser(
        "import-local-pack",
        help="Import a portable JSON pack into the local stores (dry-run by default)",
    )
    import_local_pack_p.add_argument(
        "--from",
        dest="from_path",
        default=None,
        help="Read the pack from this path. If omitted, the pack is read from stdin.",
    )
    import_local_pack_p.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace records whose ID already exists locally (default: report as conflicts)",
    )
    import_local_pack_p.add_argument(
        "--confirm",
        action="store_true",
        help="Actually write records to the local stores. Without this flag, a preview is printed.",
    )
    import_local_pack_p.add_argument("--json", action="store_true", help="Emit JSON")

    truth_p = sub.add_parser(
        "import-truth-labels",
        help="Import scouting workspace review decisions as truth labels",
    )
    truth_p.add_argument(
        "--workspace", type=str, required=True,
        help="Path to scouting workspace JSON file",
    )
    truth_p.add_argument(
        "--output", type=str,
        default="data/gold/feature_store/player_truth_labels.parquet",
        help="Output truth labels parquet path",
    )
    truth_p.add_argument(
        "--season", type=str, default="",
        help="Season override (auto-detected from workspace if omitted)",
    )
    truth_p.add_argument(
        "--position-scope", type=str, default="all",
        help="Position scope for labels (default: all)",
    )

    transfermarkt_truth_p = sub.add_parser(
        "import-transfermarkt-truth-labels",
        help="Import a dated local Transfermarkt snapshot as proxy truth labels",
    )
    transfermarkt_truth_p.add_argument(
        "--snapshot", type=str, required=True,
        help="Local Transfermarkt CSV or Parquet snapshot; network import is not supported",
    )
    transfermarkt_truth_p.add_argument(
        "--season", type=str, required=True,
        help="Compact season code for the labels (for example: 2526)",
    )
    transfermarkt_truth_p.add_argument(
        "--output", type=str,
        default="data/gold/feature_store/player_truth_labels.parquet",
        help="Output truth labels parquet path",
    )
    transfermarkt_truth_p.add_argument(
        "--confidence", choices=["high", "medium", "low"], default="medium",
        help="Proxy-label confidence (default: medium)",
    )
    transfermarkt_truth_p.add_argument(
        "--as-of-date", type=str, default=None,
        help="Optional ISO date override; defaults to each source snapshot_date",
    )
    transfermarkt_truth_p.add_argument(
        "--feature-matrix", type=str,
        default="data/gold/feature_store/rating_feature_matrix.parquet",
        help="Rating feature matrix used for deterministic identity resolution",
    )
    transfermarkt_truth_p.add_argument(
        "--identity-report", type=str, default=None,
        help="JSON audit output for mapped, review, and unresolved identity rows",
    )
    transfermarkt_truth_p.add_argument(
        "--identity-ledger", type=str, default=None,
        help="Optional local append-only manual identity-review ledger",
    )
    transfermarkt_truth_p.add_argument(
        "--label-ledger", type=str, default=None,
        help="Optional append-only import ledger used for later revocation reconciliation",
    )
    transfermarkt_truth_p.add_argument(
        "--dry-run", action="store_true",
        help="Validate, merge in memory, and print the time/coverage preview without writing",
    )
    identity_review_p = sub.add_parser(
        "transfermarkt-identity-review",
        help="Record an explicit local decision for a Transfermarkt identity review row",
    )
    identity_review_p.add_argument(
        "--report", required=True, help="Local identity review report JSON"
    )
    identity_review_p.add_argument(
        "--ledger",
        default="data/reports/data_health/transfermarkt_identity_review_ledger.jsonl",
        help="Local append-only JSONL decision ledger",
    )
    identity_review_p.add_argument("--source-row", type=int, required=True)
    identity_review_p.add_argument(
        "--action", choices=("confirmed", "rejected", "revoked"), required=True
    )
    identity_review_p.add_argument("--canonical-player-id", default=None)
    identity_review_p.add_argument("--reason", default="")

    reconcile_transfermarkt_p = sub.add_parser(
        "reconcile-transfermarkt-truth-labels",
        help="Preview or explicitly apply proven label removals after identity revocation",
    )
    reconcile_transfermarkt_p.add_argument(
        "--labels",
        default="data/gold/feature_store/player_truth_labels.parquet",
        help="Local truth-label parquet to inspect",
    )
    reconcile_transfermarkt_p.add_argument("--identity-ledger", required=True)
    reconcile_transfermarkt_p.add_argument("--label-ledger", required=True)
    reconcile_transfermarkt_p.add_argument(
        "--apply", action="store_true", help="Atomically write only proven removals"
    )

    truth_audit_p = sub.add_parser(
        "audit-truth-labels",
        help="Audit which truth labels are eligible for rating supervision",
    )
    truth_audit_p.add_argument(
        "--input", type=str,
        default="data/gold/feature_store/player_truth_labels.parquet",
        help="Truth-label Parquet input path",
    )
    truth_audit_p.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    bt_p = sub.add_parser(
        "backtest",
        help="Run probability calibration backtest (Poisson vs Dixon-Coles)",
    )
    bt_p.add_argument(
        "--n-splits", type=int, default=3,
        help="Number of time-series folds (default: 3)",
    )
    bt_p.add_argument(
        "--decay", type=float, default=0.005,
        help="Exponential decay parameter for Dixon-Coles (default: 0.005)",
    )
    bt_p.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory for backtest results",
    )

    tune_p = sub.add_parser(
        "tune-predictions",
        help="Grid-search Dixon-Coles time-decay parameter via backtest",
    )
    tune_p.add_argument(
        "--n-splits", type=int, default=3,
        help="Number of time-series folds (default: 3)",
    )
    tune_p.add_argument(
        "--metric", type=str, default="rps_1x2",
        choices=["log_loss_exact", "brier_1x2", "rps_1x2"],
        help="Selection metric to minimise (default: rps_1x2)",
    )
    tune_p.add_argument(
        "--run-backtest", action="store_true",
        help="Also run full backtest with the best decay to generate all artifacts",
    )
    tune_p.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory for tuning results",
    )

    opt_ens_p = sub.add_parser(
        "optimize-ensemble",
        help="Grid-search optimal ensemble weights and cache them",
    )
    opt_ens_p.add_argument(
        "--n-splits", type=int, default=3,
        help="Number of time-series folds (default: 3)",
    )
    opt_ens_p.add_argument(
        "--decay", type=float, default=None,
        help="Dixon-Coles time-decay parameter (default: read from tuning results)",
    )
    opt_ens_p.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory for ensemble weights artifact",
    )

    serve_p = sub.add_parser("serve", help="Start FastAPI server")
    serve_p.add_argument("--host", default="0.0.0.0")
    serve_p.add_argument("--port", type=int, default=8000)

    # Tournament state management (2026 World Cup)
    tour_p = sub.add_parser(
        "tournament",
        help="Manage 2026 World Cup tournament state, standings, and scenarios",
    )
    tour_sub = tour_p.add_subparsers(
        dest="tournament_action",
        required=True,
    )

    tour_show = tour_sub.add_parser("show", help="Show tournament summary and all standings")
    tour_show.add_argument("--state-path", type=str, default=None)
    tour_show.add_argument("--json", action="store_true", help="Emit full JSON summary")

    tour_stand = tour_sub.add_parser("standings", help="Show group standings")
    tour_stand.add_argument("--group", type=str, default=None, help="Group letter A-L")
    tour_stand.add_argument("--state-path", type=str, default=None)
    tour_stand.add_argument("--json", action="store_true")

    tour_apply = tour_sub.add_parser("apply", help="Apply a match result")
    tour_apply.add_argument("match_id", type=str, help="Match ID (see `matches`)")
    tour_apply.add_argument("home_goals", type=int)
    tour_apply.add_argument("away_goals", type=int)
    tour_apply.add_argument("--state-path", type=str, default=None)
    tour_apply.add_argument("--quiet", action="store_true", help="Skip standings print")

    tour_clear = tour_sub.add_parser("clear", help="Clear a recorded match result")
    tour_clear.add_argument("match_id", type=str)
    tour_clear.add_argument("--state-path", type=str, default=None)

    tour_reset = tour_sub.add_parser("reset", help="Reset all results to fresh state")
    tour_reset.add_argument("--state-path", type=str, default=None)
    tour_reset.add_argument("--force", action="store_true", help="Skip confirmation")

    tour_scen = tour_sub.add_parser(
        "scenarios",
        help="Show qualification scenarios for a team",
    )
    tour_scen.add_argument("team", type=str)
    tour_scen.add_argument("--max-scenarios", type=int, default=30)
    tour_scen.add_argument("--state-path", type=str, default=None)
    tour_scen.add_argument("--json", action="store_true")

    tour_matches = tour_sub.add_parser("matches", help="List matches (optionally pending)")
    tour_matches.add_argument("--group", type=str, default=None)
    tour_matches.add_argument("--pending", action="store_true", help="Only unplayed matches")
    tour_matches.add_argument("--state-path", type=str, default=None)
    tour_matches.add_argument("--json", action="store_true")

    tour_qualification = tour_sub.add_parser(
        "qualification", help="Explain local best-third cutoff impact for a group"
    )
    tour_qualification.add_argument("--group", required=True, help="Group letter A-L")
    tour_qualification.add_argument("--state-path", type=str, default=None)
    tour_qualification.add_argument("--json", action="store_true")

    tour_tiebreaks = tour_sub.add_parser(
        "tiebreaks", help="Explain local tied clusters and H2H availability"
    )
    tour_tiebreaks.add_argument("--group", required=True, help="Group letter A-L")
    tour_tiebreaks.add_argument("--state-path", type=str, default=None)
    tour_tiebreaks.add_argument("--json", action="store_true")

    # ── tournament knockout ──
    tour_ko = tour_sub.add_parser("knockout", help="Manage knockout bracket")
    tour_ko_sub = tour_ko.add_subparsers(
        dest="knockout_action",
        title="knockout actions",
        required=True,
    )
    tour_ko_gen = tour_ko_sub.add_parser(
        "generate", help="Generate knockout bracket from group standings"
    )
    tour_ko_gen.add_argument("--state-path", type=str, default=None)

    tour_ko_show = tour_ko_sub.add_parser("show", help="Show knockout bracket")
    tour_ko_show.add_argument("--state-path", type=str, default=None)
    tour_ko_show.add_argument("--json", action="store_true")

    tour_ko_apply = tour_ko_sub.add_parser("apply", help="Apply a knockout match result")
    tour_ko_apply.add_argument("match_id", type=str, help="Knockout match ID (e.g. r32-01)")
    tour_ko_apply.add_argument("home_goals", type=int)
    tour_ko_apply.add_argument("away_goals", type=int)
    tour_ko_apply.add_argument(
        "--penalties-winner", type=str, default=None,
        help="Team that won on penalties (required if draw)",
    )
    tour_ko_apply.add_argument("--state-path", type=str, default=None)

    tour_ko_clear = tour_ko_sub.add_parser("clear", help="Clear a knockout match result (cascades)")
    tour_ko_clear.add_argument("match_id", type=str)
    tour_ko_clear.add_argument("--state-path", type=str, default=None)

    # ── recruitment brief ──
    brief_create = sub.add_parser(
        "create-brief",
        help="Create a versioned recruitment brief (local personal object)",
    )
    brief_create.add_argument(
        "--title", type=str, default=None,
        help="Brief title (required unless --from-json)",
    )
    brief_create.add_argument("--team", type=str, default="", help="Target team name")
    brief_create.add_argument(
        "--position-group", type=str, default=None,
        choices=["DF", "MF", "FW", "GK"],
        help="Coarse position group (required unless --from-json)",
    )
    brief_create.add_argument(
        "--position-detail", type=str, default="",
        help="Detailed position (e.g. LB, RW)",
    )
    brief_create.add_argument(
        "--role", type=str, default="",
        help="Role name (e.g. attacking_fullback)",
    )
    brief_create.add_argument("--budget-eur", type=int, default=None, help="Budget in EUR")
    brief_create.add_argument("--age-min", type=int, default=None, help="Minimum age")
    brief_create.add_argument("--age-max", type=int, default=None, help="Maximum age")
    brief_create.add_argument(
        "--contract-years-min", type=int, default=None,
        help="Minimum contract years",
    )
    brief_create.add_argument(
        "--league-preferences", nargs="+", default=None,
        help="Preferred leagues (space-separated)",
    )
    brief_create.add_argument(
        "--language-preferences", nargs="+", default=None,
        help="Preferred languages (space-separated)",
    )
    brief_create.add_argument(
        "--risk-tolerance", type=str, default="medium",
        choices=["low", "medium", "high"],
        help="Risk tolerance (default: medium)",
    )
    brief_create.add_argument(
        "--minimum-minutes", type=int, default=None,
        help="Minimum minutes played",
    )
    brief_create.add_argument("--notes", type=str, default="", help="Free-form notes")
    brief_create.add_argument("--author", type=str, default="maintainer", help="Author name")
    brief_create.add_argument(
        "--brief-id", type=str, default=None,
        help="Explicit brief ID (auto-generated if omitted)",
    )
    brief_create.add_argument(
        "--from-json", type=str, default=None,
        help="Load brief payload from a local JSON file instead of CLI flags",
    )
    brief_create.add_argument("--json", action="store_true", help="Emit JSON output")

    list_briefs_p = sub.add_parser(
        "list-briefs",
        help="List stored recruitment briefs (most recent first)",
    )
    list_briefs_p.add_argument("--limit", type=int, default=100, help="Max results (default 100)")
    list_briefs_p.add_argument("--json", action="store_true", help="Emit JSON output")

    show_brief_p = sub.add_parser(
        "show-brief",
        help="Show one stored recruitment brief by ID",
    )
    show_brief_p.add_argument("brief_id", type=str, help="Brief ID to show")
    show_brief_p.add_argument("--json", action="store_true", help="Emit JSON output")

    validate_brief_p = sub.add_parser(
        "validate-brief",
        help="Validate a local brief JSON file without saving it",
    )
    validate_brief_p.add_argument("path", type=str, help="Path to local brief JSON file")
    validate_brief_p.add_argument("--json", action="store_true", help="Emit JSON output")

    # ── recruitment decision dossier ──
    dossier_create = sub.add_parser(
        "create-dossier",
        help="Create a versioned decision dossier (local personal object)",
    )
    dossier_create.add_argument(
        "--title", type=str, default=None,
        help="Dossier title (required unless --from-json)",
    )
    dossier_create.add_argument(
        "--brief-id", type=str, default="",
        help="ID of the linked recruitment brief",
    )
    dossier_create.add_argument(
        "--candidate-player-id", type=str, default="",
        help="Candidate player ID (e.g. understat|1234)",
    )
    dossier_create.add_argument(
        "--candidate-player-name", type=str, default="",
        help="Candidate player display name",
    )
    dossier_create.add_argument(
        "--candidate-team-name", type=str, default="",
        help="Candidate's current team name",
    )
    dossier_create.add_argument(
        "--candidate-season-id", type=str, default="",
        help="Candidate season ID (e.g. 2425)",
    )
    dossier_create.add_argument(
        "--status", type=str, default="draft",
        choices=["draft", "decided", "rejected", "superseded"],
        help="Dossier workflow status (default: draft; forced to 'decided' when --decision is set)",
    )
    dossier_create.add_argument(
        "--decision", type=str, default=None,
        choices=["proceed", "hold", "reject", "defer"],
        help="Final decision; requires status='decided' (forces status to 'decided' if set)",
    )
    dossier_create.add_argument(
        "--decision-note", type=str, default="",
        help="Free-form note explaining the decision",
    )
    dossier_create.add_argument(
        "--human-opinion", type=str, default="",
        help="Maintainer free-form opinion text",
    )
    dossier_create.add_argument(
        "--recommendation", type=str, default="",
        help="Final actionable recommendation",
    )
    dossier_create.add_argument(
        "--linked-artifacts", nargs="+", default=None,
        help="Additional linked artifact IDs (space-separated)",
    )
    dossier_create.add_argument("--notes", type=str, default="", help="Free-form notes")
    dossier_create.add_argument("--author", type=str, default="maintainer", help="Author name")
    dossier_create.add_argument(
        "--dossier-id", type=str, default=None,
        help="Explicit dossier ID (auto-generated if omitted)",
    )
    dossier_create.add_argument(
        "--from-json", type=str, default=None,
        help="Load dossier payload from a local JSON file instead of CLI flags",
    )
    dossier_create.add_argument("--json", action="store_true", help="Emit JSON output")

    list_dossiers_p = sub.add_parser(
        "list-dossiers",
        help="List stored decision dossiers (most recent first)",
    )
    list_dossiers_p.add_argument("--limit", type=int, default=100, help="Max results (default 100)")
    list_dossiers_p.add_argument("--json", action="store_true", help="Emit JSON output")

    show_dossier_p = sub.add_parser(
        "show-dossier",
        help="Show one stored decision dossier by ID",
    )
    show_dossier_p.add_argument("dossier_id", type=str, help="Dossier ID to show")
    show_dossier_p.add_argument("--json", action="store_true", help="Emit JSON output")

    validate_dossier_p = sub.add_parser(
        "validate-dossier",
        help="Validate a local dossier JSON file without saving it",
    )
    validate_dossier_p.add_argument("path", type=str, help="Path to local dossier JSON file")
    validate_dossier_p.add_argument("--json", action="store_true", help="Emit JSON output")

    # ── opposition briefing ──
    briefing_create = sub.add_parser(
        "create-briefing",
        help="Create a source-limited match briefing (local personal object)",
    )
    briefing_create.add_argument(
        "--title", type=str, default=None,
        help="Briefing title (required unless --from-json)",
    )
    briefing_create.add_argument("--home-team", type=str, default="", help="Home team name")
    briefing_create.add_argument("--away-team", type=str, default="", help="Away team name")
    briefing_create.add_argument(
        "--kickoff-at", type=str, default=None,
        help="Kickoff ISO datetime (e.g. 2026-08-15T15:00:00+00:00)",
    )
    briefing_create.add_argument("--competition", type=str, default="", help="Competition name")
    briefing_create.add_argument(
        "--season", type=str, default="", help="Season label (e.g. 2026-27)"
    )
    briefing_create.add_argument("--match-id", type=str, default="", help="External match id")
    briefing_create.add_argument(
        "--section", action="append", default=None,
        help=(
            "Briefing section as '<section_id>:<fact_tier>:<summary>'; "
            "section_id is one of opponent_strength/recent_form/key_players/"
            "set_pieces/injuries/tactical_notes or 'custom:<tail>'; "
            "fact_tier is one of official/recorded/estimated/unknown"
        ),
    )
    briefing_create.add_argument(
        "--section-evidence", action="append", default=None,
        help="Evidence ref as '<section_id>:<ref>' (may be repeated)",
    )
    briefing_create.add_argument(
        "--linked-pattern-card-ids", nargs="+", default=None,
        help="Linked pattern card IDs (space-separated)",
    )
    briefing_create.add_argument(
        "--linked-scenario-tree-id", type=str, default=None,
        help="Linked scenario tree ID",
    )
    briefing_create.add_argument(
        "--linked-post-match-review-id", type=str, default=None,
        help="Linked post-match review ID",
    )
    briefing_create.add_argument("--notes", type=str, default="", help="Free-form notes")
    briefing_create.add_argument("--author", type=str, default="maintainer", help="Author name")
    briefing_create.add_argument(
        "--briefing-id", type=str, default=None,
        help="Explicit briefing ID (auto-generated if omitted)",
    )
    briefing_create.add_argument(
        "--from-json", type=str, default=None,
        help="Load briefing payload from a local JSON file instead of CLI flags",
    )
    briefing_create.add_argument("--json", action="store_true", help="Emit JSON output")

    list_briefings_p = sub.add_parser(
        "list-briefings",
        help="List stored match briefings (most recent first)",
    )
    list_briefings_p.add_argument(
        "--limit", type=int, default=100, help="Max results (default 100)"
    )
    list_briefings_p.add_argument("--json", action="store_true", help="Emit JSON output")

    show_briefing_p = sub.add_parser(
        "show-briefing",
        help="Show one stored match briefing by ID",
    )
    show_briefing_p.add_argument("briefing_id", type=str, help="Briefing ID to show")
    show_briefing_p.add_argument("--json", action="store_true", help="Emit JSON output")

    validate_briefing_p = sub.add_parser(
        "validate-briefing",
        help="Validate a local briefing JSON file without saving it",
    )
    validate_briefing_p.add_argument("path", type=str, help="Path to local briefing JSON file")
    validate_briefing_p.add_argument("--json", action="store_true", help="Emit JSON output")

    # ── opposition post-match review ──
    review_create = sub.add_parser(
        "create-review",
        help="Create a versioned post-match review (local personal object)",
    )
    review_create.add_argument(
        "--title", type=str, default=None,
        help="Review title (required unless --from-json)",
    )
    review_create.add_argument(
        "--briefing-id", type=str, default="",
        help="ID of the linked opposition briefing",
    )
    review_create.add_argument("--match-id", type=str, default="", help="External match id")
    review_create.add_argument("--home-team", type=str, default="", help="Home team name")
    review_create.add_argument("--away-team", type=str, default="", help="Away team name")
    review_create.add_argument(
        "--kickoff-at", type=str, default=None,
        help="Kickoff ISO datetime (e.g. 2026-08-15T15:00:00+00:00)",
    )
    review_create.add_argument("--competition", type=str, default="", help="Competition name")
    review_create.add_argument(
        "--season", type=str, default="", help="Season label (e.g. 2026-27)"
    )
    review_create.add_argument(
        "--final-score-home", type=int, default=None,
        help="Final home score (non-negative integer)",
    )
    review_create.add_argument(
        "--final-score-away", type=int, default=None,
        help="Final away score (non-negative integer)",
    )
    review_create.add_argument(
        "--status", type=str, default="draft",
        choices=["draft", "finalized", "superseded"],
        help=(
            "Review workflow status (default: draft; forced to 'finalized' "
            "when --decision is set)"
        ),
    )
    review_create.add_argument(
        "--decision", type=str, default=None,
        choices=["confirmed", "falsified", "partial", "inconclusive"],
        help="Final decision; requires status='finalized' (forces status to 'finalized' if set)",
    )
    review_create.add_argument(
        "--decision-note", type=str, default="",
        help="Free-form note explaining the decision",
    )
    review_create.add_argument(
        "--human-opinion", type=str, default="",
        help="Maintainer free-form opinion text",
    )
    review_create.add_argument(
        "--recommendation", type=str, default="",
        help="Final actionable recommendation",
    )
    review_create.add_argument(
        "--linked-artifacts", nargs="+", default=None,
        help="Additional linked artifact IDs (space-separated)",
    )
    review_create.add_argument("--notes", type=str, default="", help="Free-form notes")
    review_create.add_argument("--author", type=str, default="maintainer", help="Author name")
    review_create.add_argument(
        "--review-id", type=str, default=None,
        help="Explicit review ID (auto-generated if omitted)",
    )
    review_create.add_argument(
        "--from-json", type=str, default=None,
        help="Load review payload from a local JSON file instead of CLI flags",
    )
    review_create.add_argument("--json", action="store_true", help="Emit JSON output")

    list_reviews_p = sub.add_parser(
        "list-reviews",
        help="List stored post-match reviews (most recent first)",
    )
    list_reviews_p.add_argument("--limit", type=int, default=100, help="Max results (default 100)")
    list_reviews_p.add_argument("--json", action="store_true", help="Emit JSON output")

    show_review_p = sub.add_parser(
        "show-review",
        help="Show one stored post-match review by ID",
    )
    show_review_p.add_argument("review_id", type=str, help="Review ID to show")
    show_review_p.add_argument("--json", action="store_true", help="Emit JSON output")

    validate_review_p = sub.add_parser(
        "validate-review",
        help="Validate a local review JSON file without saving it",
    )
    validate_review_p.add_argument("path", type=str, help="Path to local review JSON file")
    validate_review_p.add_argument("--json", action="store_true", help="Emit JSON output")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "info": _cmd_info,
        "capabilities": _cmd_capabilities,
        "data-contracts": _cmd_data_contracts,
        "list-adapters": _cmd_list_adapters,
        "adapter-compatibility": _cmd_adapter_compatibility,
        "ingest": _cmd_ingest,
        "build-features": _cmd_build_features,
        "train": _cmd_train,
        "train-rating-nn": _cmd_train_rating_nn,
        "validate": _cmd_validate,
        "source-health": _cmd_source_health,
        "contract-quality": _cmd_contract_quality,
        "model-admission": _cmd_model_admission,
        "research-health": _cmd_research_health,
        "discard-model-run": _cmd_discard_model_run,
        "reject-model-run": _cmd_reject_model_run,
        "promote-model-run": _cmd_promote_model_run,
        "rollback-model-run": _cmd_rollback_model_run,
        "validate-decision-package": _cmd_validate_decision_package,
        "record-source-snapshot": _cmd_record_source_snapshot,
        "inspect-raw-source": _cmd_inspect_raw_source,
        "reep-identity-lookup": _cmd_reep_identity_lookup,
        "record-source-policy": _cmd_record_source_policy,
        "record-quality-audit": _cmd_record_quality_audit,
        "record-quality-threshold": _cmd_record_quality_threshold,
        "optimizer-preflight": _cmd_optimizer_preflight,
        "preflight": _cmd_preflight,
        "action-value": _cmd_action_value,
        "action-value-matches": _cmd_action_value_matches,
        "export-ratings": _cmd_export_ratings,
        "export-local-pack": _cmd_export_local_pack,
        "import-local-pack": _cmd_import_local_pack,
        "import-truth-labels": _cmd_import_truth_labels,
        "import-transfermarkt-truth-labels": _cmd_import_transfermarkt_truth_labels,
        "transfermarkt-identity-review": _cmd_transfermarkt_identity_review,
        "reconcile-transfermarkt-truth-labels": _cmd_reconcile_transfermarkt_truth_labels,
        "audit-truth-labels": _cmd_audit_truth_labels,
        "backtest": _cmd_backtest,
        "tune-predictions": _cmd_tune_predictions,
        "optimize-ensemble": _cmd_optimize_ensemble,
        "serve": _cmd_serve,
        "tournament": _cmd_tournament,
        "create-brief": _cmd_create_brief,
        "list-briefs": _cmd_list_briefs,
        "show-brief": _cmd_show_brief,
        "validate-brief": _cmd_validate_brief,
        "create-dossier": _cmd_create_dossier,
        "list-dossiers": _cmd_list_dossiers,
        "show-dossier": _cmd_show_dossier,
        "validate-dossier": _cmd_validate_dossier,
        "create-briefing": _cmd_create_briefing,
        "list-briefings": _cmd_list_briefings,
        "show-briefing": _cmd_show_briefing,
        "validate-briefing": _cmd_validate_briefing,
        "create-review": _cmd_create_review,
        "list-reviews": _cmd_list_reviews,
        "show-review": _cmd_show_review,
        "validate-review": _cmd_validate_review,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)
    handler(args)


if __name__ == "__main__":
    main()

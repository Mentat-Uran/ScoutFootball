"""Read-only admission checks for local rating-optimizer candidates."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.optimizer_preflight import REQUIRED_ARTIFACTS

MODEL_ADMISSION_VERSION = "1.0.3"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _finite_metric(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _check(name: str, passed: bool, note: str) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "note": note}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_file_short(path: Path) -> str:
    """Return sha256[:16] of *path*, matching the hash format written by
    optimizer_preflight into ``meta.json.lineage.feature_manifest.hash``.

    A 16-character prefix is what the rating-feature manifest writers use
    for ``input_hash`` (see ``features.manifest.hash_file``); the same
    prefix length is used here so meta.json hashes and on-disk manifest
    hashes are directly comparable without slicing.
    """
    return _sha256_file(path)[:16]


def _rating_feature_matrix_manifest_path(settings: PlatformSettings) -> Path:
    """Return the absolute path to the on-disk rating_feature_matrix manifest."""
    return (
        settings.data_root
        / "gold"
        / "feature_store"
        / "rating_feature_matrix_manifest.json"
    )


def _current_rating_manifest_hash(settings: PlatformSettings) -> str | None:
    """Return sha256[:16] of the current on-disk rating_feature_matrix_manifest.json.

    Returns ``None`` when the manifest is absent so callers can distinguish
    'cannot verify chain of custody' (no on-disk manifest) from 'chain of
    custody broken' (manifest present but hash differs). The pre-training
    validation gate already fails when the manifest is missing, so admission
    only hardens the case where the manifest exists but does not match the
    training-time snapshot recorded in meta.json.
    """
    manifest_path = _rating_feature_matrix_manifest_path(settings)
    if not manifest_path.is_file():
        return None
    return _sha256_file_short(manifest_path)


def _evaluate_candidate_rating_artifact(
    meta: dict[str, Any], directory: Path
) -> tuple[str, bool]:
    """Verify the candidate rating parquet exists and matches its recorded SHA-256.

    A reviewable run must not rely on a missing or tampered candidate score
    snapshot. The maintainer promotion path re-checks the hash, but admission
    surfaces the same problem earlier so reviewable status is not misleading.
    Returns a human-readable note and a boolean pass flag.
    """
    artifacts = meta.get("candidate_artifacts")
    if not isinstance(artifacts, dict):
        return "candidate_artifacts metadata is missing", False
    ratings_meta = artifacts.get("ratings")
    if not isinstance(ratings_meta, dict):
        return "candidate rating metadata is missing", False
    rel_path = ratings_meta.get("path")
    expected_hash = ratings_meta.get("sha256")
    if not isinstance(rel_path, str) or not rel_path:
        return "candidate rating path is missing", False
    if not isinstance(expected_hash, str) or not expected_hash:
        return "candidate rating sha256 is missing", False
    # Reject absolute paths or parent traversal to keep the check scoped to the
    # run directory.
    ratings_path = (directory / rel_path).resolve()
    try:
        ratings_path.relative_to(directory.resolve())
    except ValueError:
        return f"candidate rating path escapes run directory: {rel_path}", False
    if not ratings_path.is_file():
        return f"candidate rating file is missing: {rel_path}", False
    actual_hash = _sha256_file(ratings_path)
    if actual_hash != expected_hash:
        return (
            f"candidate rating sha256 mismatch: metadata={expected_hash} actual={actual_hash}",
            False,
        )
    return "candidate rating artifact verified", True


def _evaluate_recorded_lineage(
    lineage: dict[str, Any], settings: PlatformSettings | None
) -> tuple[str, bool]:
    """Verify that meta.json.lineage records both required snapshots and that
    the training-time ``feature_manifest.hash`` still matches the on-disk
    rating_feature_matrix_manifest.json when *settings* is provided.

    Returns a human-readable note and a boolean pass flag. The note explains
    *why* the check failed so maintainers can decide between retraining on
    the current feature_store, rolling back the feature_store to the
    training-time snapshot, or treating the run as historical evidence only.
    """
    status_ok = lineage.get("status") == "recorded"
    dataset_hash = (lineage.get("dataset_snapshot") or {}).get("input_hash")
    manifest_hash = (lineage.get("feature_manifest") or {}).get("hash")
    base_ok = status_ok and bool(dataset_hash) and bool(manifest_hash)
    if not base_ok:
        return "dataset snapshot and feature manifest must both be recorded", False

    # When settings is None (legacy callers, unit tests without a real
    # feature_store on disk) the chain-of-custody check is skipped — the
    # pre-training validation gate already covers manifest existence and
    # freshness, so admission only hardens the case where we can actually
    # read the current on-disk manifest.
    if settings is None:
        return "dataset snapshot and feature manifest must both be recorded", True

    current_manifest_hash = _current_rating_manifest_hash(settings)
    if current_manifest_hash is None:
        # On-disk manifest missing: pre-training validation gate covers this
        # case (manifest_exists check fails), so admission does not duplicate
        # the failure here. The run remains reviewable on its own evidence.
        return (
            "dataset snapshot and feature manifest recorded; on-disk "
            "rating_feature_matrix_manifest.json missing, chain of custody "
            "not verifiable by admission (covered by pre-training validation)",
            True,
        )
    if manifest_hash == current_manifest_hash:
        return (
            f"dataset snapshot and feature manifest hash both verified against "
            f"current on-disk manifest (hash={current_manifest_hash})",
            True,
        )
    return (
        f"training-time feature_manifest.hash={manifest_hash} differs from "
        f"current on-disk rating_feature_matrix_manifest.json hash="
        f"{current_manifest_hash}; rating_feature_matrix was rebuilt after "
        f"training, so the candidate cannot be reviewed against current data",
        False,
    )


def evaluate_optimizer_run(
    run_dir: Path | str,
    *,
    settings: PlatformSettings | None = None,
) -> dict[str, Any]:
    """Assess whether one run carries the minimum evidence for human review.

    Passing this report does not promote a model. It only establishes that the
    local candidate is complete enough for a maintainer to compare and decide.

    When *settings* is provided, the ``recorded_lineage`` check additionally
    verifies that the training-time ``feature_manifest.hash`` recorded in
    meta.json still matches the sha256[:16] of the current on-disk
    ``rating_feature_matrix_manifest.json``. This closes the chain-of-custody
    gap where rebuilding ``feature_store`` after training would let a stale
    candidate remain ``reviewable``. When *settings* is None the check
    falls back to the legacy behavior (hash only needs to be non-empty).
    """
    directory = Path(run_dir).resolve()
    meta_path = directory / "meta.json"
    if not meta_path.exists():
        return {
            "run_id": directory.name,
            "status": "not_available",
            "checks": [_check("metadata", False, "meta.json is missing")],
            "failed_checks": ["metadata"],
        }
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "run_id": directory.name,
            "status": "not_available",
            "checks": [_check("metadata", False, f"meta.json unreadable: {type(exc).__name__}")],
            "failed_checks": ["metadata"],
        }
    lineage = meta.get("lineage") if isinstance(meta.get("lineage"), dict) else {}
    metrics = meta.get("metrics") if isinstance(meta.get("metrics"), dict) else {}
    baseline = metrics.get("baseline_test")
    candidate = metrics.get("optimized_test")
    has_baseline = isinstance(baseline, dict) and _finite_metric(baseline.get("spearman"))
    has_candidate = isinstance(candidate, dict) and _finite_metric(candidate.get("spearman"))
    data_coverage = meta.get("data_coverage")
    artifact_statuses = (
        data_coverage.get("artifact_statuses", []) if isinstance(data_coverage, dict) else []
    )
    statuses_by_source: dict[str, set[str]] = {}
    if isinstance(artifact_statuses, list):
        for item in artifact_statuses:
            if isinstance(item, dict) and isinstance(item.get("source"), str):
                status = item.get("status")
                if isinstance(status, str):
                    statuses_by_source.setdefault(item["source"], set()).add(status)
    required_input_failures = []
    for source in REQUIRED_ARTIFACTS:
        statuses = statuses_by_source.get(source, set())
        if "loaded" not in statuses:
            detail = "not_recorded" if not statuses else ", ".join(sorted(statuses))
            required_input_failures.append(f"{source}: {detail}")
    train = meta.get("train_seasons")
    test = meta.get("test_seasons")
    candidate_rating_note, candidate_rating_ok = _evaluate_candidate_rating_artifact(
        meta, directory
    )
    lineage_note, lineage_ok = _evaluate_recorded_lineage(lineage, settings)
    checks = [
        _check(
            "parameter_artifact",
            (directory / "optimized_params.npy").exists(),
            "candidate parameters",
        ),
        _check("recorded_lineage", lineage_ok, lineage_note),
        _check(
            "time_split",
            isinstance(train, list) and bool(train) and isinstance(test, list) and bool(test),
            "train and holdout seasons",
        ),
        _check("baseline_holdout", has_baseline, "structured finite baseline_test.spearman"),
        _check("candidate_holdout", has_candidate, "structured finite optimized_test.spearman"),
        _check(
            "error_cases",
            isinstance(meta.get("error_cases"), dict) and bool(meta.get("error_cases")),
            "bounded holdout error examples",
        ),
        _check(
            "required_inputs",
            not required_input_failures,
            (
                "required optimizer inputs loaded"
                if not required_input_failures
                else str(required_input_failures)
            ),
        ),
        _check("candidate_rating_artifact", candidate_rating_ok, candidate_rating_note),
    ]
    failed = [item["name"] for item in checks if item["status"] == "fail"]
    comparison = None
    if has_baseline and has_candidate:
        comparison = {
            "baseline_spearman": float(baseline["spearman"]),
            "candidate_spearman": float(candidate["spearman"]),
            "delta_spearman": float(candidate["spearman"] - baseline["spearman"]),
        }
    return {
        "run_id": directory.name,
        "status": "reviewable" if not failed else "not_reviewable",
        "checks": checks,
        "failed_checks": failed,
        "comparison": comparison,
        "limitations": [
            (
                "Reviewable means evidence is present, not that the candidate is "
                "automatically promoted."
            ),
            (
                "Promotion additionally requires maintainer judgment of calibration, "
                "slices, error cases, and scope."
            ),
        ],
    }


def build_model_admission_report(
    settings: PlatformSettings | None = None, *, run_id: str | None = None
) -> dict[str, Any]:
    """Report all available local optimizer runs or one requested run."""
    resolved = settings or PlatformSettings.from_root()
    runs_dir = resolved.model_root / "runs"
    available = (
        sorted((path for path in runs_dir.iterdir() if path.is_dir()), reverse=True)
        if runs_dir.exists()
        else []
    )
    if run_id is not None:
        available = [runs_dir / run_id]
    runs = [evaluate_optimizer_run(path, settings=resolved) for path in available]
    return {
        "report_type": "scoutfootball.model_admission",
        "report_version": MODEL_ADMISSION_VERSION,
        "generated_at": _now(),
        "run_count": len(runs),
        "reviewable_run_count": sum(run["status"] == "reviewable" for run in runs),
        "runs": runs,
        "limitations": [
            "This report is read-only and does not change the active rating artifact.",
            "Legacy runs lacking structured evidence remain visible as not_reviewable.",
        ],
    }


def format_model_admission_report(report: dict[str, Any]) -> str:
    lines = [
        f"Model admission: {report['reviewable_run_count']}/{report['run_count']} reviewable"
    ]
    for run in report["runs"]:
        lines.append(f"  - {run['run_id']}: {run['status']}")
        if run["failed_checks"]:
            lines.append("    missing: " + ", ".join(run["failed_checks"]))
    return "\n".join(lines)

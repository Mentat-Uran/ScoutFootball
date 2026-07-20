"""Fail-closed local lifecycle actions for optimizer candidate directories."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.model_admission import evaluate_optimizer_run


class ModelRunLifecycleError(ValueError):
    """Raised when a requested model-run lifecycle action is unsafe."""


ACTIVE_ARTIFACT_FILENAMES = (
    "player_ratings_optimized.parquet",
    "optimized_params.npy",
    "optimized_params_meta.json",
)
REQUIRED_RATING_COLUMNS = {
    "player",
    "team",
    "league",
    "season",
    "sub_position",
    "minutes",
    "optimized_score",
    "same_position_score",
}
RATING_KEY_COLUMNS = ["player", "team", "league", "season", "sub_position"]
MODEL_LIFECYCLE_SCHEMA = "scoutfootball.local-model-lifecycle"
MODEL_LIFECYCLE_VERSION = "1.0"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _runs_root(settings: PlatformSettings) -> Path:
    return (settings.model_root / "runs").resolve()


def _feature_store(settings: PlatformSettings) -> Path:
    return (settings.gold_root / "feature_store").resolve()


def _backups_root(settings: PlatformSettings) -> Path:
    return (settings.model_root / "backups").resolve()


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


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink():
        raise ModelRunLifecycleError(f"{label} must not be a symlink")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelRunLifecycleError(f"{label} is unreadable: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise ModelRunLifecycleError(f"{label} must contain a JSON object")
    return value


def _candidate_file(directory: Path, filename: str, *, label: str) -> Path:
    if not filename or Path(filename).name != filename:
        raise ModelRunLifecycleError(f"{label} must be a direct candidate filename")
    path = directory / filename
    if path.is_symlink() or not path.is_file():
        raise ModelRunLifecycleError(f"{label} is missing or not a regular file")
    return path


def _require_decision(decision: str) -> str:
    cleaned = decision.strip()
    if not cleaned:
        raise ModelRunLifecycleError("a non-empty maintainer decision is required")
    return cleaned


def _validate_rating_frame(frame: pd.DataFrame, *, label: str) -> None:
    if frame.empty:
        raise ModelRunLifecycleError(f"{label} has no rows")
    missing = sorted(REQUIRED_RATING_COLUMNS - set(frame.columns))
    if missing:
        raise ModelRunLifecycleError(f"{label} is missing required columns: {', '.join(missing)}")
    if frame[RATING_KEY_COLUMNS].isna().any().any():
        raise ModelRunLifecycleError(f"{label} has null rating identity keys")
    if frame.duplicated(RATING_KEY_COLUMNS).any():
        raise ModelRunLifecycleError(f"{label} has duplicate rating identity keys")
    scores = pd.to_numeric(frame["optimized_score"], errors="coerce")
    percentiles = pd.to_numeric(frame["same_position_score"], errors="coerce")
    if not np.isfinite(scores.to_numpy(dtype=float)).all():
        raise ModelRunLifecycleError(f"{label} has non-finite optimized scores")
    if not np.isfinite(percentiles.to_numpy(dtype=float)).all():
        raise ModelRunLifecycleError(f"{label} has non-finite position percentiles")
    expected = frame.groupby(["sub_position", "season"], observed=True)["optimized_score"].rank(
        pct=True
    ) * 100.0
    if not np.array_equal(percentiles.to_numpy(dtype=float), expected.to_numpy(dtype=float)):
        raise ModelRunLifecycleError(f"{label} does not satisfy the position-percentile contract")


def _validate_params(path: Path, *, label: str) -> int:
    if path.is_symlink() or not path.is_file():
        raise ModelRunLifecycleError(f"{label} is missing or not a regular file")
    try:
        params = np.load(path, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise ModelRunLifecycleError(
            f"{label} cannot be loaded safely: {type(exc).__name__}"
        ) from exc
    if params.size == 0 or not np.isfinite(np.asarray(params, dtype=float)).all():
        raise ModelRunLifecycleError(f"{label} must contain finite numeric values")
    return int(params.size)


def _active_paths(settings: PlatformSettings) -> dict[str, Path]:
    root = _feature_store(settings)
    return {name: root / name for name in ACTIVE_ARTIFACT_FILENAMES}


def _validate_active_artifacts(settings: PlatformSettings) -> dict[str, Path]:
    paths = _active_paths(settings)
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ModelRunLifecycleError(
            "active artifacts required for reversible promotion are missing: " + ", ".join(missing)
        )
    try:
        active_ratings = pd.read_parquet(paths["player_ratings_optimized.parquet"])
        _validate_rating_frame(active_ratings, label="active ratings")
    except (OSError, ValueError, TypeError) as exc:
        if isinstance(exc, ModelRunLifecycleError):
            raise
        raise ModelRunLifecycleError(
            f"active ratings are unreadable: {type(exc).__name__}"
        ) from exc
    _validate_params(paths["optimized_params.npy"], label="active parameters")
    _read_json_object(paths["optimized_params_meta.json"], label="active metadata")
    return paths


def _candidate_promotion_inputs(
    settings: PlatformSettings, run_id: str
) -> tuple[Path, dict[str, Any], Path, Path, dict[str, Any]]:
    directory = _run_directory(settings, run_id)
    meta = _read_json_object(directory / "meta.json", label="candidate metadata")
    activation = meta.get("activation")
    if not isinstance(activation, dict) or activation.get("status") != "not_activated":
        raise ModelRunLifecycleError("candidate is not explicitly not_activated")
    admission = evaluate_optimizer_run(directory, settings=settings)
    if admission["status"] != "reviewable":
        raise ModelRunLifecycleError(
            "candidate is not reviewable: " + ", ".join(admission["failed_checks"])
        )
    artifacts = meta.get("candidate_artifacts")
    ratings_meta = artifacts.get("ratings") if isinstance(artifacts, dict) else None
    if not isinstance(ratings_meta, dict):
        raise ModelRunLifecycleError("candidate rating artifact metadata is missing")
    ratings_path = _candidate_file(
        directory, str(ratings_meta.get("path", "")), label="candidate ratings"
    )
    expected_hash = ratings_meta.get("sha256")
    if not isinstance(expected_hash, str) or _sha256_file(ratings_path) != expected_hash:
        raise ModelRunLifecycleError("candidate rating artifact SHA-256 does not match metadata")
    try:
        ratings = pd.read_parquet(ratings_path)
    except (OSError, ValueError, TypeError) as exc:
        raise ModelRunLifecycleError(
            f"candidate ratings are unreadable: {type(exc).__name__}"
        ) from exc
    if (
        ratings_meta.get("rows") != len(ratings)
        or ratings_meta.get("columns") != list(ratings.columns)
    ):
        raise ModelRunLifecycleError(
            "candidate rating artifact rows or columns do not match metadata"
        )
    _validate_rating_frame(ratings, label="candidate ratings")
    params_path = _candidate_file(directory, "optimized_params.npy", label="candidate parameters")
    _validate_params(params_path, label="candidate parameters")
    return directory, meta, ratings_path, params_path, admission


def _backup_id(run_id: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{run_id}-{uuid.uuid4().hex[:8]}"


def _copy_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_json_atomic(destination: Path, payload: dict[str, Any]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _create_backup(
    settings: PlatformSettings, *, run_id: str, active_paths: dict[str, Path], backup_id: str
) -> tuple[Path, dict[str, Any]]:
    backup_dir = _backups_root(settings) / backup_id
    if backup_dir.exists():
        raise ModelRunLifecycleError(f"backup directory already exists: {backup_id}")
    backup_dir.mkdir(parents=True)
    files = {}
    try:
        for name, source in active_paths.items():
            target = backup_dir / name
            shutil.copyfile(source, target)
            files[name] = {"sha256": _sha256_file(target), "size_bytes": target.stat().st_size}
        manifest = {
            "schema": MODEL_LIFECYCLE_SCHEMA,
            "version": MODEL_LIFECYCLE_VERSION,
            "backup_id": backup_id,
            "created_at": _now(),
            "promoted_run_id": run_id,
            "files": files,
        }
        _write_json_atomic(backup_dir / "manifest.json", manifest)
        return backup_dir, manifest
    except Exception:
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise


def _active_metadata(
    candidate_meta: dict[str, Any], *, run_id: str, decision: str, backup_id: str, params_count: int
) -> dict[str, Any]:
    result = deepcopy(candidate_meta)
    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
    holdout = {
        "train_seasons": result.get("train_seasons", []),
        "test_seasons": result.get("test_seasons", []),
        "baseline_train": metrics.get("baseline_train", {}),
        "baseline_test": metrics.get("baseline_test", {}),
        "optimized_train": metrics.get("optimized_train", {}),
        "optimized_test": metrics.get("optimized_test", {}),
    }
    result.update(
        {
            "timestamp": _now(),
            "run_id": run_id,
            "n_params": params_count,
            "holdout": holdout,
            "active_model": {
                "schema": MODEL_LIFECYCLE_SCHEMA,
                "version": MODEL_LIFECYCLE_VERSION,
                "run_id": run_id,
                "backup_id": backup_id,
                "activated_at": _now(),
                "decision": decision,
            },
        }
    )
    return result


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


def inspect_optimizer_run_rejection(
    settings: PlatformSettings, run_id: str, *, decision: str
) -> dict[str, Any]:
    """Preview a retained, explicit rejection of an unactivated candidate."""
    cleaned_decision = _require_decision(decision)
    directory = _run_directory(settings, run_id)
    meta = _read_json_object(directory / "meta.json", label="candidate metadata")
    activation = meta.get("activation")
    if not isinstance(activation, dict) or activation.get("status") != "not_activated":
        raise ModelRunLifecycleError("only explicitly unactivated candidates can be rejected")
    return {
        "run_id": run_id,
        "path": str(directory),
        "action": "reject",
        "decision": cleaned_decision,
        "current_activation_status": "not_activated",
        "will_retain_candidate": True,
    }


def reject_optimizer_run(
    settings: PlatformSettings, run_id: str, *, decision: str, confirm: bool = False
) -> dict[str, Any]:
    """Record an explicit local rejection without deleting a candidate."""
    report = inspect_optimizer_run_rejection(settings, run_id, decision=decision)
    report["confirmed"] = bool(confirm)
    report["rejected"] = False
    if not confirm:
        return report
    directory = _run_directory(settings, run_id)
    meta = _read_json_object(directory / "meta.json", label="candidate metadata")
    activation = meta.get("activation")
    if not isinstance(activation, dict) or activation.get("status") != "not_activated":
        raise ModelRunLifecycleError("candidate activation status changed; refusing rejection")
    meta["activation"] = {
        "status": "rejected",
        "rejected_at": _now(),
        "decision": report["decision"],
        "note": "Candidate retained locally for later review; no active artifacts were changed.",
    }
    _write_json_atomic(directory / "meta.json", meta)
    report["rejected"] = True
    return report


def inspect_optimizer_run_promotion(
    settings: PlatformSettings, run_id: str, *, decision: str
) -> dict[str, Any]:
    """Preview a reversible local promotion without changing active artifacts."""
    cleaned_decision = _require_decision(decision)
    _, meta, ratings_path, params_path, admission = _candidate_promotion_inputs(settings, run_id)
    active_paths = _validate_active_artifacts(settings)
    backup_id = _backup_id(run_id)
    return {
        "run_id": run_id,
        "action": "promote",
        "decision": cleaned_decision,
        "admission_status": admission["status"],
        "candidate_ratings": {
            "path": str(ratings_path),
            "sha256": _sha256_file(ratings_path),
            "rows": meta["candidate_artifacts"]["ratings"]["rows"],
        },
        "candidate_params": {"path": str(params_path), "sha256": _sha256_file(params_path)},
        "active_artifacts": {name: str(path) for name, path in active_paths.items()},
        "backup_id": backup_id,
        "backup_path": str(_backups_root(settings) / backup_id),
        "will_replace_active_artifacts": list(ACTIVE_ARTIFACT_FILENAMES),
    }


def promote_optimizer_run(
    settings: PlatformSettings, run_id: str, *, decision: str, confirm: bool = False
) -> dict[str, Any]:
    """Promote one reviewable candidate after backing up active local artifacts.

    The default is a preview. Confirmed execution replaces three active files
    only after they have been read and copied into a complete backup; a failure
    while replacing restores those original files before surfacing the error.
    """
    report = inspect_optimizer_run_promotion(settings, run_id, decision=decision)
    report["confirmed"] = bool(confirm)
    report["promoted"] = False
    if not confirm:
        return report

    directory, meta, ratings_path, params_path, _ = _candidate_promotion_inputs(settings, run_id)
    active_paths = _validate_active_artifacts(settings)
    backup_id = report["backup_id"]
    backup_dir, backup_manifest = _create_backup(
        settings, run_id=run_id, active_paths=active_paths, backup_id=backup_id
    )
    params_count = _validate_params(params_path, label="candidate parameters")
    active_meta = _active_metadata(
        meta,
        run_id=run_id,
        decision=report["decision"],
        backup_id=backup_id,
        params_count=params_count,
    )
    activated_meta = deepcopy(meta)
    activated_meta["activation"] = {
        "status": "activated",
        "activated_at": active_meta["active_model"]["activated_at"],
        "decision": report["decision"],
        "backup_id": backup_id,
        "note": "Active artifacts were replaced from this reviewed local candidate.",
    }
    replacements = {
        "player_ratings_optimized.parquet": ratings_path,
        "optimized_params.npy": params_path,
    }
    replaced = False
    try:
        for name, source in replacements.items():
            _copy_atomic(source, active_paths[name])
        _write_json_atomic(active_paths["optimized_params_meta.json"], active_meta)
        replaced = True
        _write_json_atomic(directory / "meta.json", activated_meta)
    except Exception as exc:
        if replaced or any(
            _sha256_file(active_paths[name]) != backup_manifest["files"][name]["sha256"]
            for name in ACTIVE_ARTIFACT_FILENAMES
            if active_paths[name].is_file()
        ):
            for name in ACTIVE_ARTIFACT_FILENAMES:
                _copy_atomic(backup_dir / name, active_paths[name])
        raise ModelRunLifecycleError(
            f"promotion failed and active artifacts were restored: {type(exc).__name__}"
        ) from exc
    report["promoted"] = True
    report["activated_at"] = active_meta["active_model"]["activated_at"]
    return report


def _backup_directory(settings: PlatformSettings, backup_id: str) -> Path:
    if not backup_id or Path(backup_id).name != backup_id:
        raise ModelRunLifecycleError("backup_id must be a single backup directory name")
    root = _backups_root(settings)
    requested = root / backup_id
    if requested.is_symlink():
        raise ModelRunLifecycleError("backup directory must not be a symlink")
    directory = requested.resolve()
    if directory.parent != root or not directory.is_dir():
        raise ModelRunLifecycleError(f"backup does not exist: {backup_id}")
    return directory


def _backup_manifest(settings: PlatformSettings, backup_id: str) -> tuple[Path, dict[str, Any]]:
    directory = _backup_directory(settings, backup_id)
    manifest = _read_json_object(directory / "manifest.json", label="backup manifest")
    if manifest.get("schema") != MODEL_LIFECYCLE_SCHEMA:
        raise ModelRunLifecycleError("backup manifest schema is not supported")
    if manifest.get("backup_id") != backup_id:
        raise ModelRunLifecycleError("backup manifest id does not match directory")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ModelRunLifecycleError("backup manifest has no file inventory")
    for name in ACTIVE_ARTIFACT_FILENAMES:
        item = files.get(name)
        path = directory / name
        if not isinstance(item, dict) or not isinstance(item.get("sha256"), str):
            raise ModelRunLifecycleError(f"backup manifest has no hash for {name}")
        if path.is_symlink() or not path.is_file() or _sha256_file(path) != item["sha256"]:
            raise ModelRunLifecycleError(f"backup file verification failed for {name}")
    return directory, manifest


def inspect_optimizer_run_rollback(
    settings: PlatformSettings, backup_id: str, *, decision: str
) -> dict[str, Any]:
    """Preview restoration of the currently active candidate's exact backup."""
    cleaned_decision = _require_decision(decision)
    backup_dir, manifest = _backup_manifest(settings, backup_id)
    run_id = manifest.get("promoted_run_id")
    if not isinstance(run_id, str):
        raise ModelRunLifecycleError("backup does not identify its promoted candidate")
    directory = _run_directory(settings, run_id)
    candidate_meta = _read_json_object(directory / "meta.json", label="candidate metadata")
    activation = candidate_meta.get("activation")
    if not isinstance(activation, dict) or activation.get("status") != "activated":
        raise ModelRunLifecycleError("backup candidate is not currently activated")
    if activation.get("backup_id") != backup_id:
        raise ModelRunLifecycleError("candidate activation does not match requested backup")
    active_meta = _read_json_object(
        _active_paths(settings)["optimized_params_meta.json"], label="active metadata"
    )
    active_model = active_meta.get("active_model")
    if not isinstance(active_model, dict) or active_model.get("backup_id") != backup_id:
        raise ModelRunLifecycleError("requested backup is not the active model's rollback point")
    return {
        "backup_id": backup_id,
        "backup_path": str(backup_dir),
        "run_id": run_id,
        "action": "rollback",
        "decision": cleaned_decision,
        "will_restore_active_artifacts": list(ACTIVE_ARTIFACT_FILENAMES),
    }


def rollback_optimizer_run(
    settings: PlatformSettings, backup_id: str, *, decision: str, confirm: bool = False
) -> dict[str, Any]:
    """Restore a verified local backup after explicit confirmation."""
    report = inspect_optimizer_run_rollback(settings, backup_id, decision=decision)
    report["confirmed"] = bool(confirm)
    report["rolled_back"] = False
    if not confirm:
        return report
    backup_dir, manifest = _backup_manifest(settings, backup_id)
    active_paths = _active_paths(settings)
    run_id = report["run_id"]
    candidate_dir = _run_directory(settings, run_id)
    candidate_meta = _read_json_object(candidate_dir / "meta.json", label="candidate metadata")
    for name in ACTIVE_ARTIFACT_FILENAMES:
        _copy_atomic(backup_dir / name, active_paths[name])
    candidate_meta["activation"] = {
        "status": "rolled_back",
        "rolled_back_at": _now(),
        "decision": report["decision"],
        "backup_id": backup_id,
        "note": "The prior active local artifacts were restored from the verified backup.",
    }
    _write_json_atomic(candidate_dir / "meta.json", candidate_meta)
    _write_json_atomic(
        backup_dir / "rollback.json",
        {
            "schema": MODEL_LIFECYCLE_SCHEMA,
            "version": MODEL_LIFECYCLE_VERSION,
            "backup_id": backup_id,
            "run_id": run_id,
            "rolled_back_at": _now(),
            "decision": report["decision"],
            "restored_files": {
                name: manifest["files"][name]["sha256"] for name in ACTIVE_ARTIFACT_FILENAMES
            },
        },
    )
    report["rolled_back"] = True
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


def format_optimizer_run_action(report: dict[str, Any]) -> str:
    """Render a concise preview or confirmed model lifecycle action."""
    action = report["action"]
    completed = {
        "promote": report.get("promoted", False),
        "reject": report.get("rejected", False),
        "rollback": report.get("rolled_back", False),
    }.get(action, False)
    prefix = "Completed" if completed else "Dry run"
    lines = [f"{prefix}: {action}"]
    if "run_id" in report:
        lines.append(f"  Run: {report['run_id']}")
    if "backup_id" in report:
        lines.append(f"  Backup: {report['backup_id']}")
    lines.append(f"  Decision: {report['decision']}")
    if not completed:
        lines.append("  No active artifacts changed; rerun with --confirm to apply.")
    return "\n".join(lines)

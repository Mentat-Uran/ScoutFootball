"""Tests for explicit optimizer-candidate admission reporting."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.model_admission import (
    build_model_admission_report,
    evaluate_optimizer_run,
)


def _sha256_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_disk_rating_manifest(root, manifest_content: dict | None = None) -> str:
    """Write a rating_feature_matrix_manifest.json under root/data/gold/feature_store/.

    Returns the sha256[:16] of the written file so tests can record it in
    meta.json.lineage.feature_manifest.hash to simulate a training-time
    snapshot that matches (or differs from) the current on-disk state.
    """
    manifest_path = (
        root / "data" / "gold" / "feature_store" / "rating_feature_matrix_manifest.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    content = manifest_content or {"artifact": "rating_feature_matrix", "total_rows": 1}
    manifest_path.write_text(json.dumps(content), encoding="utf-8")
    return _sha256_file(manifest_path)[:16]


def _write_run(root, name: str, *, complete: bool) -> None:
    run = root / "data" / "models" / "runs" / name
    run.mkdir(parents=True)
    np.save(run / "optimized_params.npy", np.array([1.0]))
    meta = {
        "lineage": {
            "status": "recorded" if complete else "partial",
            "dataset_snapshot": {"input_hash": "input" if complete else None},
            "feature_manifest": {"hash": "manifest" if complete else None},
        },
        "train_seasons": ["2324"] if complete else [],
        "test_seasons": ["2425"] if complete else [],
        "metrics": (
            {
                "baseline_test": {"spearman": 0.5},
                "optimized_test": {"spearman": 0.6},
            }
            if complete
            else {"baseline_test": "{'spearman': 0.5}"}
        ),
        "error_cases": {"over_estimated": [{"team": "A"}]} if complete else {},
        "data_coverage": {
            "artifact_statuses": [
                {"source": "fbref_standard", "status": "loaded"},
                {"source": "football_data_results", "status": "loaded"},
            ]
        },
    }
    if complete:
        ratings_path = run / "player_ratings_candidate.parquet"
        pd.DataFrame(
            {
                "player": ["A", "B"],
                "optimized_score": [0.6, 0.4],
                "same_position_score": [80.0, 40.0],
            }
        ).to_parquet(ratings_path, index=False)
        meta["candidate_artifacts"] = {
            "ratings": {
                "path": "player_ratings_candidate.parquet",
                "sha256": _sha256_file(ratings_path),
                "rows": 2,
                "columns": ["player", "optimized_score", "same_position_score"],
            }
        }
    (run / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_admission_marks_complete_run_reviewable(tmp_path) -> None:
    _write_run(tmp_path, "complete", complete=True)

    report = build_model_admission_report(PlatformSettings.from_root(tmp_path))

    assert report["reviewable_run_count"] == 1
    assert report["runs"][0]["comparison"]["delta_spearman"] == pytest.approx(0.1)


def test_admission_keeps_legacy_opaque_metrics_out_of_reviewable_set(tmp_path) -> None:
    _write_run(tmp_path, "legacy", complete=False)

    report = build_model_admission_report(PlatformSettings.from_root(tmp_path))

    run = report["runs"][0]
    assert run["status"] == "not_reviewable"
    assert "recorded_lineage" in run["failed_checks"]
    assert "baseline_holdout" in run["failed_checks"]


def test_admission_rejects_a_required_football_data_input_that_was_not_loaded(tmp_path) -> None:
    _write_run(tmp_path, "missing-input", complete=True)
    meta_path = tmp_path / "data" / "models" / "runs" / "missing-input" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["data_coverage"]["artifact_statuses"][1]["status"] = "unreadable"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    report = build_model_admission_report(PlatformSettings.from_root(tmp_path))

    assert "required_inputs" in report["runs"][0]["failed_checks"]


def test_admission_rejects_an_unrecorded_required_input(tmp_path) -> None:
    _write_run(tmp_path, "unrecorded-input", complete=True)
    meta_path = tmp_path / "data" / "models" / "runs" / "unrecorded-input" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["data_coverage"]["artifact_statuses"] = [
        {"source": "fbref_standard", "status": "loaded"},
    ]
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    report = build_model_admission_report(PlatformSettings.from_root(tmp_path))

    run = report["runs"][0]
    assert "required_inputs" in run["failed_checks"]
    assert "football_data_results: not_recorded" in next(
        check["note"] for check in run["checks"] if check["name"] == "required_inputs"
    )


def test_admission_can_target_missing_run(tmp_path) -> None:
    report = build_model_admission_report(
        PlatformSettings.from_root(tmp_path), run_id="not-there"
    )

    assert report["runs"][0]["status"] == "not_available"


def test_admission_rejects_run_when_candidate_rating_parquet_is_missing(tmp_path) -> None:
    _write_run(tmp_path, "missing-parquet", complete=True)
    run_dir = tmp_path / "data" / "models" / "runs" / "missing-parquet"
    (run_dir / "player_ratings_candidate.parquet").unlink()

    report = build_model_admission_report(PlatformSettings.from_root(tmp_path))

    run = report["runs"][0]
    assert run["status"] == "not_reviewable"
    assert "candidate_rating_artifact" in run["failed_checks"]
    note = next(c["note"] for c in run["checks"] if c["name"] == "candidate_rating_artifact")
    assert "missing" in note


def test_admission_rejects_run_when_candidate_rating_sha256_mismatches(tmp_path) -> None:
    _write_run(tmp_path, "tampered-parquet", complete=True)
    meta_path = tmp_path / "data" / "models" / "runs" / "tampered-parquet" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["candidate_artifacts"]["ratings"]["sha256"] = "0" * 64
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    report = build_model_admission_report(PlatformSettings.from_root(tmp_path))

    run = report["runs"][0]
    assert run["status"] == "not_reviewable"
    assert "candidate_rating_artifact" in run["failed_checks"]
    note = next(c["note"] for c in run["checks"] if c["name"] == "candidate_rating_artifact")
    assert "mismatch" in note


def test_admission_rejects_run_when_candidate_artifacts_metadata_is_absent(tmp_path) -> None:
    _write_run(tmp_path, "no-candidate-meta", complete=True)
    meta_path = tmp_path / "data" / "models" / "runs" / "no-candidate-meta" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["candidate_artifacts"]
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    report = build_model_admission_report(PlatformSettings.from_root(tmp_path))

    run = report["runs"][0]
    assert run["status"] == "not_reviewable"
    assert "candidate_rating_artifact" in run["failed_checks"]


def test_admission_rejects_candidate_rating_path_that_escapes_run_directory(tmp_path) -> None:
    _write_run(tmp_path, "escaped-path", complete=True)
    meta_path = tmp_path / "data" / "models" / "runs" / "escaped-path" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["candidate_artifacts"]["ratings"]["path"] = "../outside.parquet"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    report = build_model_admission_report(PlatformSettings.from_root(tmp_path))

    run = report["runs"][0]
    assert "candidate_rating_artifact" in run["failed_checks"]
    note = next(c["note"] for c in run["checks"] if c["name"] == "candidate_rating_artifact")
    assert "escapes" in note


# ---------------------------------------------------------------------------
# recorded_lineage chain-of-custody against on-disk rating_feature_matrix manifest
# ---------------------------------------------------------------------------


def test_admission_passes_when_training_manifest_hash_matches_disk(tmp_path) -> None:
    """When meta.json.lineage.feature_manifest.hash matches the sha256[:16]
    of the current on-disk rating_feature_matrix_manifest.json, recorded_lineage
    passes and the note explicitly verifies the chain of custody. This is the
    path that prevents a stale candidate (trained on an older feature_store)
    from being reviewed against current data without the maintainer noticing.
    """
    _write_run(tmp_path, "matches-disk", complete=True)
    disk_hash = _write_disk_rating_manifest(tmp_path)
    meta_path = tmp_path / "data" / "models" / "runs" / "matches-disk" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["lineage"]["feature_manifest"]["hash"] = disk_hash
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    report = build_model_admission_report(PlatformSettings.from_root(tmp_path))

    run = report["runs"][0]
    assert run["status"] == "reviewable"
    assert "recorded_lineage" not in run["failed_checks"]
    note = next(c["note"] for c in run["checks"] if c["name"] == "recorded_lineage")
    assert "verified against current on-disk manifest" in note
    assert disk_hash in note


def test_admission_fails_when_training_manifest_hash_differs_from_disk(tmp_path) -> None:
    """When meta.json.lineage.feature_manifest.hash differs from the current
    on-disk manifest hash, recorded_lineage fails. This catches the provenance
    drift case: training was done on feature_store v1, the maintainer rebuilt
    feature_store (v2), and the candidate is now stale relative to current
    data. Without this check, promote would succeed on hash-mismatched data
    because model_run_lifecycle only verifies candidate rating/params sha256.
    """
    _write_run(tmp_path, "stale-hash", complete=True)
    _write_disk_rating_manifest(tmp_path)  # creates some on-disk manifest
    meta_path = tmp_path / "data" / "models" / "runs" / "stale-hash" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    # Set a hash that definitely doesn't match the on-disk file.
    meta["lineage"]["feature_manifest"]["hash"] = "0" * 16
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    report = build_model_admission_report(PlatformSettings.from_root(tmp_path))

    run = report["runs"][0]
    assert run["status"] == "not_reviewable"
    assert "recorded_lineage" in run["failed_checks"]
    note = next(c["note"] for c in run["checks"] if c["name"] == "recorded_lineage")
    assert "differs from current on-disk" in note
    assert "rating_feature_matrix was rebuilt after training" in note


def test_admission_passes_when_disk_manifest_missing(tmp_path) -> None:
    """When the on-disk rating_feature_matrix_manifest.json is missing,
    recorded_lineage still passes (assuming meta.json has the required
    fields). This keeps backward compatibility with test environments and
    legacy installs that don't have the manifest yet — pre-training
    validation already fails on missing manifest, so admission doesn't
    duplicate that check; admission only hardens the case where the
    manifest exists but doesn't match the training-time snapshot.
    """
    _write_run(tmp_path, "no-disk-manifest", complete=True)
    # Note: no _write_disk_rating_manifest() call here.

    report = build_model_admission_report(PlatformSettings.from_root(tmp_path))

    run = report["runs"][0]
    assert run["status"] == "reviewable"
    assert "recorded_lineage" not in run["failed_checks"]
    note = next(c["note"] for c in run["checks"] if c["name"] == "recorded_lineage")
    assert "on-disk" in note
    assert "missing" in note


def test_admission_skips_chain_of_custody_when_settings_is_none(tmp_path) -> None:
    """When evaluate_optimizer_run is called without settings (legacy
    callers, programmatic use), the chain-of-custody check is skipped.
    This preserves the original contract: only the meta.json lineage
    fields are required, and the caller is responsible for any external
    state verification. The note matches the pre-1.0.3 behavior so
    downstream consumers parsing notes are not broken.
    """
    _write_run(tmp_path, "no-settings", complete=True)

    run = evaluate_optimizer_run(
        tmp_path / "data" / "models" / "runs" / "no-settings",
        settings=None,
    )

    assert run["status"] == "reviewable"
    note = next(c["note"] for c in run["checks"] if c["name"] == "recorded_lineage")
    assert note == "dataset snapshot and feature manifest must both be recorded"

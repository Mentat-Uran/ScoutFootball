"""Tests for explicit optimizer-candidate admission reporting."""

from __future__ import annotations

import json

import numpy as np
import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.model_admission import build_model_admission_report


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

"""API-facing coverage for local optimizer admission summaries."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from scoutfootball.config import PlatformSettings


def _sha256_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_model_run_api_exposes_read_only_admission_summary(tmp_path, monkeypatch) -> None:
    from scoutfootball import api

    run = tmp_path / "data" / "models" / "runs" / "candidate"
    run.mkdir(parents=True)
    np.save(run / "optimized_params.npy", np.array([1.0]))
    ratings_path = run / "player_ratings_candidate.parquet"
    pd.DataFrame({"player": ["A"], "optimized_score": [0.6]}).to_parquet(
        ratings_path, index=False
    )
    (run / "meta.json").write_text(
        json.dumps(
            {
                "lineage": {
                    "status": "recorded",
                    "dataset_snapshot": {"input_hash": "input"},
                    "feature_manifest": {"hash": "manifest"},
                },
                "train_seasons": ["2324"],
                "test_seasons": ["2425"],
                "metrics": {
                    "baseline_test": {"spearman": 0.5},
                    "optimized_test": {"spearman": 0.6},
                },
                "error_cases": {"over_estimated": [{"team": "A", "residual": 1.0}]},
                "data_coverage": {
                    "artifact_statuses": [
                        {"source": "fbref_standard", "status": "loaded"},
                        {"source": "football_data_results", "status": "loaded"},
                    ]
                },
                "candidate_artifacts": {
                    "ratings": {
                        "path": "player_ratings_candidate.parquet",
                        "sha256": _sha256_file(ratings_path),
                        "rows": 1,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(api, "_settings", lambda: PlatformSettings.from_root(tmp_path))

    result = api.get_model_runs()

    assert result["runs"][0]["admission"]["status"] == "reviewable"
    assert result["runs"][0]["admission"]["comparison"]["delta_spearman"] == pytest.approx(0.1)
    assert "activation" not in result["runs"][0]["admission"]


def test_model_training_api_reads_active_run_history(tmp_path, monkeypatch) -> None:
    from scoutfootball import api

    run_id = "candidate-neural"
    run = tmp_path / "data" / "models" / "runs" / run_id
    run.mkdir(parents=True)
    (run / "meta.json").write_text(
        json.dumps({"model_type": "team_points_mlp", "architecture": "mlp"}),
        encoding="utf-8",
    )
    (run / "training_history.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "history": [{"epoch": 1, "train_loss": 0.9, "validation_loss": 0.8}],
                "training_device": "cuda",
                "cuda_device": "NVIDIA test GPU",
            }
        ),
        encoding="utf-8",
    )
    feature_store = tmp_path / "data" / "gold" / "feature_store"
    feature_store.mkdir(parents=True)
    (feature_store / "optimized_params_meta.json").write_text(
        json.dumps({"active_model": {"run_id": run_id}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(api, "_settings", lambda: PlatformSettings.from_root(tmp_path))

    result = api.get_model_training_history()

    assert result["status"] == "ok"
    assert result["run_id"] == run_id
    assert result["training_device"] == "cuda"
    assert result["history"][0]["validation_loss"] == pytest.approx(0.8)

"""API-facing coverage for local optimizer admission summaries."""

from __future__ import annotations

import json

import numpy as np
import pytest

from scoutfootball.config import PlatformSettings


def test_model_run_api_exposes_read_only_admission_summary(tmp_path, monkeypatch) -> None:
    from scoutfootball import api

    run = tmp_path / "data" / "models" / "runs" / "candidate"
    run.mkdir(parents=True)
    np.save(run / "optimized_params.npy", np.array([1.0]))
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
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(api, "_settings", lambda: PlatformSettings.from_root(tmp_path))

    result = api.get_model_runs()

    assert result["runs"][0]["admission"]["status"] == "reviewable"
    assert result["runs"][0]["admission"]["comparison"]["delta_spearman"] == pytest.approx(0.1)
    assert "activation" not in result["runs"][0]["admission"]

"""Tests for the model run detail API endpoint.

Verifies that get_model_run_detail returns the enriched fields
(data_attribution, feature_importance, params_summary) that the
frontend report view consumes on first expand.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from scoutfootball.api import get_model_run_detail


class TestGetModelRunDetail:
    """Verify get_model_run_detail returns enriched fields."""

    @patch("scoutfootball.api._settings")
    def test_returns_data_attribution(
        self, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        run_dir = tmp_path / "models" / "runs" / "test_run_001"
        run_dir.mkdir(parents=True)
        meta = {
            "timestamp": "2026-07-11T10:00:00+00:00",
            "metrics": {"spearman": 0.72},
            "args": {"seed": 42, "pop_size": 32, "n_steps": 500},
        }
        (run_dir / "meta.json").write_text(json.dumps(meta))
        mock_settings.return_value.data_root = tmp_path

        result = get_model_run_detail("test_run_001")
        assert result["run_id"] == "test_run_001"
        assert "data_attribution" in result
        da = result["data_attribution"]
        assert "primary_source" in da
        assert "license_note" in da
        assert "statsbomb_attribution_required" in da
        assert "StatsBomb" in da["statsbomb_attribution_required"]

    @patch("scoutfootball.api._settings")
    def test_returns_recorded_lineage_and_marks_legacy_runs(
        self, mock_settings: MagicMock, tmp_path: Path
    ) -> None:
        run_dir = tmp_path / "models" / "runs" / "test_run_lineage"
        run_dir.mkdir(parents=True)
        meta = {
            "input_hash": "legacy-hash",
            "lineage": {
                "schema": "scoutfootball.model-run-lineage",
                "version": "1.0.0",
                "status": "recorded",
                "dataset_snapshot": {"input_hash": "dataset-hash"},
                "feature_manifest": {"hash": "manifest-hash", "schema_version": "2.4.0"},
            },
        }
        (run_dir / "meta.json").write_text(json.dumps(meta))
        mock_settings.return_value.data_root = tmp_path

        result = get_model_run_detail("test_run_lineage")

        assert result["lineage"]["status"] == "recorded"
        assert result["lineage"]["dataset_snapshot"]["input_hash"] == "dataset-hash"

        (run_dir / "meta.json").write_text(json.dumps({"input_hash": "legacy-hash"}))
        legacy = get_model_run_detail("test_run_lineage")
        assert legacy["lineage"]["status"] == "not_recorded"
        assert legacy["lineage"]["dataset_snapshot"]["input_hash"] == "legacy-hash"

    @patch("scoutfootball.api._settings")
    def test_returns_params_summary_from_npy(
        self, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        run_dir = tmp_path / "models" / "runs" / "test_run_002"
        run_dir.mkdir(parents=True)
        meta = {"metrics": {"spearman": 0.65}, "args": {"seed": 1}}
        (run_dir / "meta.json").write_text(json.dumps(meta))
        params = np.random.randn(77).astype(np.float32)
        np.save(run_dir / "optimized_params.npy", params)
        mock_settings.return_value.data_root = tmp_path

        result = get_model_run_detail("test_run_002")
        assert "params_summary" in result
        ps = result["params_summary"]
        assert ps["shape"] == [77]
        assert "mean" in ps
        assert "std" in ps
        assert "min" in ps
        assert "max" in ps

    @patch("scoutfootball.api._settings")
    def test_returns_feature_importance_from_parquet(
        self, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        run_dir = tmp_path / "models" / "runs" / "test_run_003"
        run_dir.mkdir(parents=True)
        meta = {"metrics": {"spearman": 0.65}, "args": {}}
        (run_dir / "meta.json").write_text(json.dumps(meta))
        fi_df = pd.DataFrame({
            "name": ["feature_a", "feature_b", "feature_c"],
            "importance": [0.25, 0.18, 0.10],
        })
        fi_df.to_parquet(run_dir / "feature_importance.parquet", index=False)
        mock_settings.return_value.data_root = tmp_path

        result = get_model_run_detail("test_run_003")
        assert "feature_importance" in result
        fi = result["feature_importance"]
        assert isinstance(fi, list)
        assert len(fi) == 3
        assert fi[0]["name"] == "feature_a"

    @patch("scoutfootball.api._settings")
    def test_returns_holdout_summary(
        self, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        run_dir = tmp_path / "models" / "runs" / "test_run_004"
        run_dir.mkdir(parents=True)
        meta = {
            "metrics": {
                "spearman": 0.72,
                "optimized_test": {
                    "spearman": 0.72, "pearson": 0.75, "rank_loss": 0.15,
                    "n_players": 2500, "n_team_seasons": 100, "team_coverage": 0.95,
                },
            },
            "args": {"seed": 42},
        }
        (run_dir / "meta.json").write_text(json.dumps(meta))
        mock_settings.return_value.data_root = tmp_path

        result = get_model_run_detail("test_run_004")
        assert "holdout_summary" in result
        hs = result["holdout_summary"]
        assert "optimized_test" in hs
        assert hs["optimized_test"]["spearman"] == 0.72

    @patch("scoutfootball.api._settings")
    def test_returns_reproduce_command(
        self, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        run_dir = tmp_path / "models" / "runs" / "test_run_005"
        run_dir.mkdir(parents=True)
        meta = {
            "metrics": {"spearman": 0.65},
            "args": {"seed": 42, "pop_size": 32, "n_steps": 500, "lr": 0.05},
        }
        (run_dir / "meta.json").write_text(json.dumps(meta))
        mock_settings.return_value.data_root = tmp_path

        result = get_model_run_detail("test_run_005")
        cmd = result.get("reproduce_command", "")
        assert "--seed 42" in cmd
        assert "--pop 32" in cmd

    @patch("scoutfootball.api._settings")
    def test_nonexistent_run_returns_error(
        self, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        mock_settings.return_value.data_root = tmp_path
        result = get_model_run_detail("nonexistent_run")
        assert "error" in result
        assert "not found" in result["error"]

    @patch("scoutfootball.api._settings")
    def test_fallback_to_latest_meta(
        self, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """When run_id is 'latest', fall back to optimized_params_meta.json."""
        gold_dir = tmp_path / "gold" / "feature_store"
        gold_dir.mkdir(parents=True)
        meta = {"metrics": {"spearman": 0.60}, "args": {"seed": 1}}
        (gold_dir / "optimized_params_meta.json").write_text(json.dumps(meta))
        mock_settings.return_value.data_root = tmp_path

        result = get_model_run_detail("latest")
        assert result["run_id"] == "latest"
        assert "data_attribution" in result

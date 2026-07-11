"""Tests for model run registry."""
import argparse
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

# Save the real torch module before mocking (if it exists)
_real_torch = sys.modules.get("torch", None)

# Mock torch before importing the script — it's a top-level dependency
# that may not be installed in the test environment. Must provide enough
# structure for scipy to import without errors.
_mock_torch = MagicMock()
_mock_torch.Tensor = type("Tensor", (), {})
_mock_torch.is_tensor = lambda x: False
sys.modules["torch"] = _mock_torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from optimizer.data import compute_input_hash, save_model_run  # noqa: E402

# Restore real torch so other test files are not poisoned
if _real_torch is not None:
    sys.modules["torch"] = _real_torch
else:
    sys.modules.pop("torch", None)


class TestSaveModelRun:
    def test_creates_run_directory(self, tmp_path):
        params = np.random.randn(77).astype(np.float32)
        metrics = {"spearman": 0.65, "pearson": 0.68, "overfit_gap": 0.02}
        run_dir = save_model_run(params, metrics, output_dir=tmp_path)
        assert run_dir.exists()
        assert (run_dir / "optimized_params.npy").exists()
        assert (run_dir / "meta.json").exists()

    def test_meta_json_content(self, tmp_path):
        params = np.random.randn(77).astype(np.float32)
        metrics = {"spearman": 0.65, "pearson": 0.68}
        run_dir = save_model_run(params, metrics, output_dir=tmp_path)
        with open(run_dir / "meta.json") as f:
            meta = json.load(f)
        assert "timestamp" in meta
        assert meta["params_shape"] == [77]
        assert abs(meta["params_mean"] - params.mean()) < 0.01
        assert abs(meta["metrics"]["spearman"] - 0.65) < 0.01

    def test_with_args(self, tmp_path):
        params = np.random.randn(77).astype(np.float32)
        metrics = {"spearman": 0.65}
        args = argparse.Namespace(
            pop=32, steps=500, lr=0.05, patience=80, seed=42,
            spearman_weight=0.50, ndcg_weight=0.20,
            position_consistency_weight=0.15,
            extreme_penalty_weight=0.10, prior_weight=0.05,
        )
        run_dir = save_model_run(params, metrics, args=args, output_dir=tmp_path)
        with open(run_dir / "meta.json") as f:
            meta = json.load(f)
        assert meta["args"]["pop_size"] == 32
        assert meta["args"]["seed"] == 42

    def test_params_saved_correctly(self, tmp_path):
        params = np.random.randn(77).astype(np.float32)
        metrics = {"spearman": 0.65}
        run_dir = save_model_run(params, metrics, output_dir=tmp_path)
        loaded = np.load(run_dir / "optimized_params.npy")
        np.testing.assert_allclose(loaded, params, rtol=1e-5)

    def test_dependency_versions_present(self, tmp_path):
        params = np.random.randn(77).astype(np.float32)
        metrics = {"spearman": 0.65}
        run_dir = save_model_run(params, metrics, output_dir=tmp_path)
        with open(run_dir / "meta.json") as f:
            meta = json.load(f)
        assert "dependency_versions" in meta
        dep = meta["dependency_versions"]
        assert "python" in dep
        assert "numpy" in dep
        assert "pandas" in dep

    def test_train_test_seasons_from_args(self, tmp_path):
        params = np.random.randn(77).astype(np.float32)
        metrics = {"spearman": 0.65}
        args = argparse.Namespace(
            pop=32, steps=500, lr=0.05, patience=80, seed=42,
            train_seasons="2021,2022,2023",
            test_seasons="2024",
        )
        run_dir = save_model_run(params, metrics, args=args, output_dir=tmp_path)
        with open(run_dir / "meta.json") as f:
            meta = json.load(f)
        assert meta["train_seasons"] == ["2021,2022,2023"]
        assert meta["test_seasons"] == ["2024"]

    def test_position_metrics_persisted(self, tmp_path):
        params = np.random.randn(77).astype(np.float32)
        metrics = {
            "spearman": 0.65,
            "position_metrics": {
                "GK": {"spearman": 0.70, "n": 50},
                "DF": {"spearman": 0.63, "n": 120},
            },
        }
        run_dir = save_model_run(params, metrics, output_dir=tmp_path)
        with open(run_dir / "meta.json") as f:
            meta = json.load(f)
        assert "position_metrics" in meta
        assert meta["position_metrics"]["GK"]["spearman"] == 0.70

    def test_error_cases_computed_when_holdout_exists(self, tmp_path):
        # Create a holdout predictions parquet in the expected location
        feature_store_dir = tmp_path / "gold" / "feature_store"
        feature_store_dir.mkdir(parents=True)
        holdout_df = pd.DataFrame({
            "team": ["TeamA", "TeamB", "TeamC", "TeamD", "TeamE",
                     "TeamF", "TeamG", "TeamH", "TeamI", "TeamJ"],
            "predicted_points": [80, 70, 60, 50, 40, 30, 20, 10, 5, 1],
            "actual_points": [60, 75, 50, 55, 30, 40, 10, 20, 2, 5],
        })
        holdout_df.to_parquet(feature_store_dir / "rating_holdout_predictions.parquet", index=False)

        params = np.random.randn(77).astype(np.float32)
        metrics = {"spearman": 0.65}
        # output_dir is tmp_path / "models" / "runs", so output_dir.parent = tmp_path / "models"
        # and output_dir.parent.parent = tmp_path. _compute_error_cases searches output_dir.parent
        # (gold/feature_store) and output_dir.parent.parent (gold/). We need the holdout file
        # to be findable. Let's place output_dir inside tmp_path/gold so parent paths match.
        out_dir = feature_store_dir / "runs"
        run_dir = save_model_run(params, metrics, output_dir=out_dir)
        with open(run_dir / "meta.json") as f:
            meta = json.load(f)
        assert "error_cases" in meta
        ec = meta["error_cases"]
        assert "over_estimated" in ec
        assert "under_estimated" in ec
        assert len(ec["over_estimated"]) <= 5
        assert len(ec["under_estimated"]) <= 5


class TestComputeInputHash:
    def test_returns_hex_string(self, tmp_path):
        h = compute_input_hash(tmp_path)
        assert isinstance(h, str)
        assert len(h) == 16

    def test_deterministic(self, tmp_path):
        h1 = compute_input_hash(tmp_path)
        h2 = compute_input_hash(tmp_path)
        assert h1 == h2

    def test_changes_with_file_content(self, tmp_path):
        h1 = compute_input_hash(tmp_path)
        # Create a file that changes the hash
        gold_dir = tmp_path / "gold" / "feature_store"
        gold_dir.mkdir(parents=True)
        (gold_dir / "rating_feature_matrix.parquet").write_bytes(b"test")
        h2 = compute_input_hash(tmp_path)
        assert h1 != h2

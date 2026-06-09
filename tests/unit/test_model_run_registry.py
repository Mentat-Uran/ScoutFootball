"""Tests for model run registry."""
import argparse
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

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

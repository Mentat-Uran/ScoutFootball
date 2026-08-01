"""Tests for evaluation/calibration.py — isotonic calibration and Brier score."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scoutfootball.evaluation.calibration import (
    CalibrationResult,
    brier_score,
    calibrate_probabilities_isotonic,
)


class TestBrierScore:
    def test_perfect_predictions(self) -> None:
        y_true = np.array([1, 1, 0, 0])
        y_prob = np.array([1.0, 1.0, 0.0, 0.0])
        assert brier_score(y_true, y_prob) == pytest.approx(0.0)

    def test_worst_predictions(self) -> None:
        y_true = np.array([1, 1, 0, 0])
        y_prob = np.array([0.0, 0.0, 1.0, 1.0])
        assert brier_score(y_true, y_prob) == pytest.approx(1.0)

    def test_constant_05(self) -> None:
        y_true = np.array([1, 0, 1, 0])
        y_prob = np.array([0.5, 0.5, 0.5, 0.5])
        assert brier_score(y_true, y_prob) == pytest.approx(0.25)

    def test_handles_nan(self) -> None:
        y_true = np.array([1, np.nan, 0, 0])
        y_prob = np.array([0.9, 0.5, 0.1, np.nan])
        # Only indices 2 is clean (both non-nan)
        # Actually indices 0 and 2 are clean
        score = brier_score(y_true, y_prob)
        assert score == pytest.approx(np.mean([(1 - 0.9) ** 2, (0 - 0.1) ** 2]))

    def test_pandas_input(self) -> None:
        y_true = pd.Series([1, 0, 1])
        y_prob = pd.Series([0.8, 0.3, 0.7])
        score = brier_score(y_true, y_prob)
        expected = np.mean([(1 - 0.8) ** 2, (0 - 0.3) ** 2, (1 - 0.7) ** 2])
        assert score == pytest.approx(expected)


class TestCalibrateProbabilitiesIsotonic:
    def test_returns_tuple(self) -> None:
        y_true = np.array([0, 0, 1, 1])
        y_prob = np.array([0.1, 0.4, 0.6, 0.9])
        calibrated, result = calibrate_probabilities_isotonic(y_true, y_prob)
        assert isinstance(result, CalibrationResult)

    def test_output_shape_preserved(self) -> None:
        y_true = np.array([0, 0, 1, 1, 0, 1])
        y_prob = np.array([0.1, 0.2, 0.7, 0.9, 0.3, 0.8])
        calibrated, _ = calibrate_probabilities_isotonic(y_true, y_prob)
        assert calibrated.shape == y_prob.shape

    def test_calibrated_in_01(self) -> None:
        y_true = np.array([0, 0, 1, 1, 0, 1, 0, 1])
        y_prob = np.array([0.1, 0.2, 0.7, 0.9, 0.3, 0.8, 0.4, 0.6])
        calibrated, _ = calibrate_probabilities_isotonic(y_true, y_prob)
        assert np.all(calibrated >= 0.0)
        assert np.all(calibrated <= 1.0)

    def test_improvement_non_negative_for_miscalibrated(self) -> None:
        # Deliberately miscalibrated: high prob for negatives, low for positives
        rng = np.random.default_rng(42)
        n = 200
        y_true = rng.integers(0, 2, n)
        y_prob = np.clip(y_true * 0.3 + (1 - y_true) * 0.7 + rng.normal(0, 0.1, n), 0.01, 0.99)
        _, result = calibrate_probabilities_isotonic(y_true, y_prob)
        # Isotonic calibration should not make Brier score worse
        assert result.improvement >= -1e-10

    def test_small_sample_passthrough(self) -> None:
        # Fewer than 10 samples: should pass through unchanged
        y_true = np.array([0, 1, 0])
        y_prob = np.array([0.2, 0.8, 0.3])
        calibrated, result = calibrate_probabilities_isotonic(y_true, y_prob)
        np.testing.assert_array_almost_equal(calibrated, y_prob)
        assert result.improvement == pytest.approx(0.0)

    def test_method_field(self) -> None:
        y_true = np.array([0, 0, 1, 1])
        y_prob = np.array([0.1, 0.4, 0.6, 0.9])
        _, result = calibrate_probabilities_isotonic(y_true, y_prob)
        assert result.method == "isotonic"

    def test_handles_nan_inputs(self) -> None:
        y_true = np.array([0, 1, np.nan, 1, 0, 1, 0, 1, 0, 1, 0, 1])
        y_prob = np.array([0.1, 0.9, 0.5, 0.8, 0.2, 0.7, 0.3, 0.6, 0.15, 0.85, 0.25, 0.75])
        calibrated, result = calibrate_probabilities_isotonic(y_true, y_prob)
        assert calibrated.shape == y_prob.shape
        assert isinstance(result.brier_before, float)

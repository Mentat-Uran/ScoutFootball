"""Probability calibration for classification and regression models."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression


@dataclass(frozen=True)
class CalibrationResult:
    method: str
    brier_before: float
    brier_after: float
    improvement: float


def calibrate_probabilities_isotonic(
    y_true: pd.Series | np.ndarray,
    y_prob: pd.Series | np.ndarray,
) -> tuple[np.ndarray, CalibrationResult]:
    y_true_arr = np.asarray(y_true, dtype=float)
    y_prob_arr = np.asarray(y_prob, dtype=float)

    mask = ~(np.isnan(y_true_arr) | np.isnan(y_prob_arr))
    y_true_clean = y_true_arr[mask]
    y_prob_clean = y_prob_arr[mask]

    if len(y_true_clean) < 10:
        result = CalibrationResult(
            method="isotonic",
            brier_before=float(np.mean((y_true_clean - y_prob_clean) ** 2)),
            brier_after=float(np.mean((y_true_clean - y_prob_clean) ** 2)),
            improvement=0.0,
        )
        return y_prob_arr.copy(), result

    brier_before = float(np.mean((y_true_clean - y_prob_clean) ** 2))

    iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    iso.fit(y_prob_clean, y_true_clean)
    calibrated = iso.transform(y_prob_arr)

    calibrated_clean = calibrated[mask]
    brier_after = float(np.mean((y_true_clean - calibrated_clean) ** 2))

    result = CalibrationResult(
        method="isotonic",
        brier_before=brier_before,
        brier_after=brier_after,
        improvement=brier_before - brier_after,
    )
    return calibrated, result


def brier_score(
    y_true: pd.Series | np.ndarray,
    y_prob: pd.Series | np.ndarray,
) -> float:
    y_true_arr = np.asarray(y_true, dtype=float)
    y_prob_arr = np.asarray(y_prob, dtype=float)
    mask = ~(np.isnan(y_true_arr) | np.isnan(y_prob_arr))
    return float(np.mean((y_true_arr[mask] - y_prob_arr[mask]) ** 2))

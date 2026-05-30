"""Evaluation package for backtests, calibration, validation and reports."""

from __future__ import annotations

from .backtests import PoissonBacktestResult, run_poisson_backtest
from .calibration import CalibrationResult, brier_score, calibrate_probabilities_isotonic
from .validation import (
    ValidationReport,
    run_pre_training_validation,
    validate_date_range,
    validate_no_null_keys,
    validate_parquet_exists,
    validate_row_count,
)

__all__ = [
    "CalibrationResult",
    "PoissonBacktestResult",
    "ValidationReport",
    "brier_score",
    "calibrate_probabilities_isotonic",
    "run_poisson_backtest",
    "run_pre_training_validation",
    "validate_date_range",
    "validate_no_null_keys",
    "validate_parquet_exists",
    "validate_row_count",
]

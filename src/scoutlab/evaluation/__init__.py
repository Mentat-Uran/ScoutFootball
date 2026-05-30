"""Evaluation package for backtests, calibration and reports."""

from .backtests import PoissonBacktestResult, run_poisson_backtest

__all__ = ["PoissonBacktestResult", "run_poisson_backtest"]

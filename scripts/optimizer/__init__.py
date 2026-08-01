"""ScoutFootball player-rating optimizer package.

Only the constants are imported eagerly.  The optimization runtime needs the
optional PyTorch dependency, while position mapping and team-weight validation
must remain usable without importing that runtime.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .constants import N_DIM, N_PARAMS, N_POS, POS_TO_IDX, POSITIONS

_LAZY_EXPORTS = {
    "build_dc_tensors": ("data", "build_dc_tensors"),
    "evaluate_params": ("data", "evaluate_params"),
    "fit_team_points_calibrator": ("data", "fit_team_points_calibrator"),
    "load_data": ("data", "load_data"),
    "make_holdout_split": ("data", "make_holdout_split"),
    "save_model_run": ("data", "save_model_run"),
    "objective_torch": ("losses", "objective_torch"),
    "_get_default_params_tensor": ("optimization", "_get_default_params_tensor"),
    "optimize": ("optimization", "optimize"),
    "build_feature_tensors": ("scoring", "build_feature_tensors"),
    "compute_ratings_torch": ("scoring", "compute_ratings_torch"),
    "compute_team_avg_ratings": ("scoring", "compute_team_avg_ratings"),
    "build_team_aggregation_weights": ("team_aggregation", "build_team_aggregation_weights"),
    "build_truth_label_anchor": ("truth", "build_truth_label_anchor"),
    "resolve_truth_labels": ("truth", "resolve_truth_labels"),
    "ConsoleViz": ("viz", "ConsoleViz"),
    "LiveTrainingViz": ("viz", "LiveTrainingViz"),
    "TrainingStep": ("viz", "TrainingStep"),
    "create_visualizer": ("viz", "create_visualizer"),
}

__all__ = [
    "POSITIONS",
    "POS_TO_IDX",
    "N_POS",
    "N_DIM",
    "N_PARAMS",
    *_LAZY_EXPORTS,
]


def __getattr__(name: str) -> Any:
    """Load optional optimizer components only when a caller requests them."""
    try:
        module_name, attribute = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(f".{module_name}", __name__), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))

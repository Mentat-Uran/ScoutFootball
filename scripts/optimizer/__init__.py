# optimizer package — ScoutFootball player rating optimizer
#
# Submodules:
#   constants.py  — team aliases, position mapping, config constants
#   data.py       — data loading, evaluation, calibration, dc_tensors
#   scoring.py    — rating computation, tensor building, team aggregation
#   losses.py     — loss functions, Dixon-Coles, composite objective
#   optimization.py — optimization loop, learning rate schedule
#   truth.py      — player-level supervised label anchors
#   cv.py         — cross-validation, parameter stability
#   viz.py        — training visualization (Plotly/Console)

from .constants import N_DIM, N_PARAMS, N_POS, POS_TO_IDX, POSITIONS
from .data import (
    build_dc_tensors,
    evaluate_params,
    fit_team_points_calibrator,
    load_data,
    make_holdout_split,
    save_model_run,
)
from .losses import objective_torch
from .optimization import _get_default_params_tensor, optimize
from .scoring import (
    build_feature_tensors,
    compute_ratings_torch,
    compute_team_avg_ratings,
)
from .truth import build_truth_label_anchor, resolve_truth_labels
from .viz import ConsoleViz, LiveTrainingViz, TrainingStep, create_visualizer

__all__ = [
    # constants
    "POSITIONS", "POS_TO_IDX", "N_POS", "N_DIM", "N_PARAMS",
    # data
    "build_dc_tensors", "evaluate_params", "fit_team_points_calibrator",
    "load_data", "make_holdout_split", "save_model_run",
    # losses
    "objective_torch",
    # optimization
    "_get_default_params_tensor", "optimize",
    # scoring
    "build_feature_tensors", "compute_ratings_torch", "compute_team_avg_ratings",
    # truth anchors
    "build_truth_label_anchor", "resolve_truth_labels",
    # viz
    "ConsoleViz", "LiveTrainingViz", "TrainingStep", "create_visualizer",
]

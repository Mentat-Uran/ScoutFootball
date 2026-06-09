"""Expected Threat (xT) model.

xT assigns a value to each location on the pitch representing the
probability that possession from that location will lead to a goal.

The model divides the pitch into a grid (e.g., 16x12) and iteratively
computes the threat value of each cell based on:
- Shot probability from that cell
- Transition probability to neighboring cells

Reference: Karun Singh, "Expected Threat" (2018)
https://karun.in/blog/expected-threat.html

Current status: P2 skeleton. Grid dimensions and transition matrix
need to be calibrated from StatsBomb sample data.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence

import numpy as np

from scoutfootball.action_value.schema import ActionType, InternalAction

logger = logging.getLogger(__name__)

# Default grid dimensions
DEFAULT_X_CELLS = 16
DEFAULT_Y_CELLS = 12


def create_xt_grid(
    x_cells: int = DEFAULT_X_CELLS,
    y_cells: int = DEFAULT_Y_CELLS,
) -> np.ndarray:
    """Create an initial xT grid (all zeros)."""
    return np.zeros((y_cells, x_cells))


def get_cell(
    x: float,
    y: float,
    x_cells: int = DEFAULT_X_CELLS,
    y_cells: int = DEFAULT_Y_CELLS,
) -> tuple[int, int]:
    """Get grid cell indices for a normalized coordinate (0-100)."""
    xi = min(int(x / 100.0 * x_cells), x_cells - 1)
    yi = min(int(y / 100.0 * y_cells), y_cells - 1)
    return max(0, xi), max(0, yi)


def compute_shot_matrix(
    actions: Sequence[InternalAction],
    x_cells: int = DEFAULT_X_CELLS,
    y_cells: int = DEFAULT_Y_CELLS,
) -> np.ndarray:
    """Compute shot probability per cell from actions.

    Returns a (y_cells, x_cells) matrix where each cell is the
    probability of a shot originating from that location.
    """
    total = np.zeros((y_cells, x_cells))
    shots = np.zeros((y_cells, x_cells))

    for action in actions:
        if action.action_type in (ActionType.PASS, ActionType.CARRY, ActionType.DRIBBLE):
            xi, yi = get_cell(action.start_x, action.start_y, x_cells, y_cells)
            total[yi, xi] += 1
        elif action.action_type == ActionType.SHOT:
            xi, yi = get_cell(action.start_x, action.start_y, x_cells, y_cells)
            shots[yi, xi] += 1

    # Avoid division by zero
    with np.errstate(divide="ignore", invalid="ignore"):
        shot_prob = np.where(total > 0, shots / total, 0.0)

    return shot_prob


def compute_transition_matrix(
    actions: Sequence[InternalAction],
    x_cells: int = DEFAULT_X_CELLS,
    y_cells: int = DEFAULT_Y_CELLS,
) -> np.ndarray:
    """Compute transition probability matrix from actions.

    Returns a (y_cells*x_cells, y_cells*x_cells) matrix where
    entry [i][j] is the probability of moving from cell i to cell j.
    """
    n_cells = x_cells * y_cells
    transitions = np.zeros((n_cells, n_cells))

    for action in actions:
        if action.action_type in (ActionType.PASS, ActionType.CARRY, ActionType.DRIBBLE):
            sx, sy = get_cell(action.start_x, action.start_y, x_cells, y_cells)
            ex, ey = get_cell(action.end_x, action.end_y, x_cells, y_cells)
            from_idx = sy * x_cells + sx
            to_idx = ey * x_cells + ex
            transitions[from_idx, to_idx] += 1

    # Normalize rows
    row_sums = transitions.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        transitions = np.where(row_sums > 0, transitions / row_sums, 0.0)

    return transitions


def iterate_xt(
    shot_prob: np.ndarray,
    transitions: np.ndarray,
    x_cells: int = DEFAULT_X_CELLS,
    y_cells: int = DEFAULT_Y_CELLS,
    n_iterations: int = 10,
    convergence_threshold: float = 1e-6,
) -> np.ndarray:
    """Iteratively compute xT values.

    xT(cell) = shot_prob(cell) * 1 + (1 - shot_prob(cell)) * sum(transitions[cell, j] * xT(j))

    Returns a (y_cells, x_cells) grid of xT values.
    """
    xt = np.zeros((y_cells, x_cells))

    for iteration in range(n_iterations):
        xt_flat = xt.flatten()
        new_xt = shot_prob.flatten() + (1 - shot_prob.flatten()) * (transitions @ xt_flat)
        new_xt = new_xt.reshape(y_cells, x_cells)

        diff = np.abs(new_xt - xt).max()
        xt = new_xt

        if diff < convergence_threshold:
            logger.info("xT converged after %d iterations (diff=%.8f)", iteration + 1, diff)
            break

    return xt


def compute_xt(actions: Sequence[InternalAction]) -> np.ndarray:
    """Compute xT grid from a sequence of actions.

    This is the main entry point for xT computation.
    """
    if not actions:
        logger.warning("No actions provided for xT computation")
        return create_xt_grid()

    shot_prob = compute_shot_matrix(actions)
    transitions = compute_transition_matrix(actions)
    xt = iterate_xt(shot_prob, transitions)

    logger.info("Computed xT grid: min=%.4f, max=%.4f, mean=%.4f", xt.min(), xt.max(), xt.mean())
    return xt


def action_xt_value(
    action: InternalAction,
    xt_grid: np.ndarray,
    x_cells: int = DEFAULT_X_CELLS,
    y_cells: int = DEFAULT_Y_CELLS,
) -> float:
    """Compute the xT value added by a single action.

    xT_added = xT(end_location) - xT(start_location)
    """
    sx, sy = get_cell(action.start_x, action.start_y, x_cells, y_cells)
    ex, ey = get_cell(action.end_x, action.end_y, x_cells, y_cells)

    start_xt = xt_grid[sy, sx]
    end_xt = xt_grid[ey, ex]

    return float(end_xt - start_xt)

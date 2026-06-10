"""Expected Threat (xT) model.

xT assigns a value to each location on the pitch representing the
probability that possession from that location will lead to a goal
within the next N actions.

The model divides the pitch into a grid (e.g., 12x8) and iteratively
computes the threat value of each cell based on:
- Shot probability from that cell (fraction of possessions that result in a shot)
- Goal probability given a shot from that cell
- Transition probability to other cells (move/pass/carry)

Reference: Karun Singh, "Expected Threat" (2018)
https://karun.in/blog/expected-threat.html

Current status: P2. Uses StatsBomb Open Data sample only.
Grid dimensions are reduced (12x8) due to small sample size (3 matches).
"""
from __future__ import annotations

import logging
from collections.abc import Sequence

import numpy as np

from scoutfootball.action_value.schema import ActionType, InternalAction

logger = logging.getLogger(__name__)

# Reduced grid for small sample (3 matches, ~12K events)
DEFAULT_X_CELLS = 12
DEFAULT_Y_CELLS = 8


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


def compute_shot_goal_matrices(
    actions: Sequence[InternalAction],
    x_cells: int = DEFAULT_X_CELLS,
    y_cells: int = DEFAULT_Y_CELLS,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute shot probability and goal probability per cell.

    shot_prob[cell] = P(shot | possession in cell)
    goal_prob[cell] = P(goal | shot from cell)

    Returns (shot_prob, goal_prob) each as (y_cells, x_cells) matrices.
    """
    possession_count = np.zeros((y_cells, x_cells))
    shot_count = np.zeros((y_cells, x_cells))
    goal_count = np.zeros((y_cells, x_cells))

    for action in actions:
        if action.action_type in (ActionType.PASS, ActionType.CARRY, ActionType.DRIBBLE,
                                   ActionType.TACKLE, ActionType.INTERCEPTION,
                                   ActionType.CLEARANCE, ActionType.BLOCK,
                                   ActionType.GOALKEEPER, ActionType.DRIBBLE,
                                   ActionType.TAKE_ON):
            xi, yi = get_cell(action.start_x, action.start_y, x_cells, y_cells)
            possession_count[yi, xi] += 1
        elif action.action_type == ActionType.SHOT:
            xi, yi = get_cell(action.start_x, action.start_y, x_cells, y_cells)
            shot_count[yi, xi] += 1
            possession_count[yi, xi] += 1
            if action.result.value == "success":
                goal_count[yi, xi] += 1

    # Shot probability: fraction of possessions that result in a shot
    with np.errstate(divide="ignore", invalid="ignore"):
        shot_prob = np.where(possession_count > 0, shot_count / possession_count, 0.0)
    # Clip to [0, 1] for safety
    shot_prob = np.clip(shot_prob, 0.0, 1.0)

    # Goal probability: fraction of shots that result in a goal
    with np.errstate(divide="ignore", invalid="ignore"):
        goal_prob = np.where(shot_count > 0, goal_count / shot_count, 0.0)
    # Default goal probability based on distance (rough heuristic for cells with no shots)
    # Closer to goal = higher goal probability
    for yi in range(y_cells):
        for xi in range(x_cells):
            if shot_count[yi, xi] == 0:
                # x position normalized: 0 = own goal, 100 = opponent goal
                x_norm = (xi + 0.5) / x_cells
                # Rough: goal prob increases with proximity to goal
                goal_prob[yi, xi] = max(0.01, 0.3 * x_norm ** 2)
    goal_prob = np.clip(goal_prob, 0.0, 1.0)

    logger.info(
        "Shot prob: min=%.4f, max=%.4f, nonzero_cells=%d",
        shot_prob.min(), shot_prob.max(), (shot_prob > 0).sum(),
    )
    logger.info(
        "Goal prob: min=%.4f, max=%.4f, nonzero_cells=%d",
        goal_prob.min(), goal_prob.max(), (goal_prob > 0).sum(),
    )

    return shot_prob, goal_prob


def compute_transition_matrix(
    actions: Sequence[InternalAction],
    x_cells: int = DEFAULT_X_CELLS,
    y_cells: int = DEFAULT_Y_CELLS,
) -> np.ndarray:
    """Compute transition probability matrix from actions.

    Returns a (y_cells*x_cells, y_cells*x_cells) matrix where
    entry [i][j] is the probability of moving from cell i to cell j
    given a move action (pass/carry/dribble).
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
    goal_prob: np.ndarray,
    transitions: np.ndarray,
    x_cells: int = DEFAULT_X_CELLS,
    y_cells: int = DEFAULT_Y_CELLS,
    n_iterations: int = 100,
    convergence_threshold: float = 1e-6,
) -> np.ndarray:
    """Iteratively compute xT values.

    xT(cell) = shot_prob(cell) * goal_prob(cell)
             + (1 - shot_prob(cell)) * sum(transitions[cell, j] * xT(j))

    This is the standard xT formulation where:
    - shot_prob * goal_prob = expected goals from shooting
    - (1 - shot_prob) * transitions @ xT = expected goals from moving

    Returns a (y_cells, x_cells) grid of xT values.
    """
    xt = np.zeros((y_cells, x_cells))

    shot_flat = shot_prob.flatten()
    goal_flat = goal_prob.flatten()

    for iteration in range(n_iterations):
        xt_flat = xt.flatten()
        new_xt = shot_flat * goal_flat + (1 - shot_flat) * (transitions @ xt_flat)
        new_xt = new_xt.reshape(y_cells, x_cells)

        # Clip to prevent divergence
        new_xt = np.clip(new_xt, 0.0, 1.0)

        diff = np.abs(new_xt - xt).max()
        xt = new_xt

        if diff < convergence_threshold:
            logger.info("xT converged after %d iterations (diff=%.8f)", iteration + 1, diff)
            break
    else:
        logger.info("xT did not converge after %d iterations (diff=%.8f)", n_iterations, diff)

    return xt


def compute_xt(actions: Sequence[InternalAction]) -> np.ndarray:
    """Compute xT grid from a sequence of actions.

    This is the main entry point for xT computation.
    """
    if not actions:
        logger.warning("No actions provided for xT computation")
        return create_xt_grid()

    shot_prob, goal_prob = compute_shot_goal_matrices(actions)
    transitions = compute_transition_matrix(actions)
    xt = iterate_xt(shot_prob, goal_prob, transitions)

    logger.info("Computed xT grid: min=%.6f, max=%.6f, mean=%.6f", xt.min(), xt.max(), xt.mean())
    return xt


def action_xt_value(
    action: InternalAction,
    xt_grid: np.ndarray,
    x_cells: int = DEFAULT_X_CELLS,
    y_cells: int = DEFAULT_Y_CELLS,
) -> float:
    """Compute the xT value added by a single action.

    xT_added = xT(end_location) - xT(start_location)

    Positive value means the action moved the ball to a more dangerous
    position. Negative means it moved to a less dangerous position.
    """
    sx, sy = get_cell(action.start_x, action.start_y, x_cells, y_cells)
    ex, ey = get_cell(action.end_x, action.end_y, x_cells, y_cells)

    start_xt = xt_grid[sy, sx]
    end_xt = xt_grid[ey, ex]

    return float(end_xt - start_xt)

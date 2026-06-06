"""Training monitor: real-time visualization of optimization progress."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class TrainingIteration:
    """Single iteration data point during training."""
    iteration: int
    spearman: float
    pearson: float
    n_teams: int
    loss: float


@dataclass
class TrainingMonitor:
    """Real-time training monitor with live plotting support.

    Tracks optimization progress and provides hooks for live visualization.
    Works in both CLI mode (text updates) and GUI mode (matplotlib/plotly).
    """

    max_history: int = 500
    baseline_spearman: float = 0.0
    baseline_pearson: float = 0.0
    _history: deque[TrainingIteration] = field(default_factory=deque)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # Plotly/matplotlib figure handles (set by visualization layer)
    fig: object = None
    ax_loss: object = None
    ax_correlation: object = None
    use_plotly: bool = False

    def record(
        self,
        iteration: int,
        spearman: float,
        pearson: float,
        n_teams: int = 0,
        loss: float = 0.0,
    ) -> None:
        """Record a single iteration result."""
        with self._lock:
            self._history.append(
                TrainingIteration(
                    iteration=iteration,
                    spearman=spearman,
                    pearson=pearson,
                    n_teams=n_teams,
                    loss=loss,
                )
            )
            # Trim old entries
            while len(self._history) > self.max_history:
                self._history.popleft()

    def get_history(self) -> list[TrainingIteration]:
        """Get full iteration history as list."""
        with self._lock:
            return list(self._history)

    def get_latest(self) -> TrainingIteration | None:
        """Get most recent iteration."""
        with self._lock:
            if self._history:
                return self._history[-1]
            return None

    def print_progress(self, iteration: int, spearman: float, pearson: float) -> None:
        """Print progress to console (for CLI mode)."""
        best = self.get_best_spearman()
        delta = spearman - self.baseline_spearman
        indicator = "+" if delta >= 0 else ""
        print(
            f"  Iter {iteration:>3}: "
            f"Spearman={spearman:.4f} "
            f"Pearson={pearson:.4f} "
            f"Best={best:.4f} "
            f"({indicator}{delta:+.4f} vs baseline)"
        )

    def get_best_spearman(self) -> float:
        """Get best Spearman correlation so far."""
        history = self.get_history()
        if not history:
            return 0.0
        return max(h.spearman for h in history)

    def get_best_iteration(self) -> TrainingIteration | None:
        """Get iteration with best Spearman."""
        history = self.get_history()
        if not history:
            return None
        return max(history, key=lambda h: h.spearman)

    def generate_text_report(self) -> str:
        """Generate a text summary report."""
        history = self.get_history()
        if not history:
            return "No training data recorded."

        best = max(history, key=lambda h: h.spearman)
        final = history[-1]
        improvement = final.spearman - self.baseline_spearman

        lines = [
            "=" * 60,
            "Training Progress Report",
            "=" * 60,
            f"Baseline:  Spearman={self.baseline_spearman:.4f}, Pearson={self.baseline_pearson:.4f}",
            f"Final:     Spearman={final.spearman:.4f}, Pearson={final.pearson:.4f}",
            f"Best:      Iter={best.iteration}, Spearman={best.spearman:.4f}",
            f"Improvement: {improvement:+.4f}",
            f"Total iterations: {len(history)}",
            "=" * 60,
        ]
        return "\n".join(lines)

    def save_history(self, output_path: Path) -> None:
        """Save iteration history to CSV."""
        import csv

        history = self.get_history()
        if not history:
            return

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["iteration", "spearman", "pearson", "n_teams", "loss"],
            )
            writer.writeheader()
            for h in history:
                writer.writerow({
                    "iteration": h.iteration,
                    "spearman": h.spearman,
                    "pearson": h.pearson,
                    "n_teams": h.n_teams,
                    "loss": h.loss,
                })

    # ── Live matplotlib visualization ────────────────────────────────────────

    def init_matplotlib_figure(self, figsize: tuple[float, float] = (12, 5)) -> None:
        """Initialize matplotlib figure for live plotting."""
        import matplotlib
        matplotlib.use("TkAgg")  # Interactive backend
        import matplotlib.pyplot as plt

        self.fig, (self.ax_loss, self.ax_correlation) = plt.subplots(1, 2, figsize=figsize)
        self.use_plotly = False

        # Setup loss subplot
        self.ax_loss.set_xlabel("Iteration")
        self.ax_loss.set_ylabel("Loss (negative correlation)")
        self.ax_loss.set_title("Optimization Loss")
        self.ax_loss.grid(True, alpha=0.3)
        self.ax_loss.set_xlim(0, self.max_history)

        # Setup correlation subplot
        self.ax_correlation.set_xlabel("Iteration")
        self.ax_correlation.set_ylabel("Correlation")
        self.ax_correlation.set_title("Spearman & Pearson Correlation")
        self.ax_correlation.set_ylim(-0.1, 1.0)
        self.ax_correlation.grid(True, alpha=0.3)
        self.ax_correlation.axhline(
            self.baseline_spearman, color="gray", linestyle="--", alpha=0.5, label="baseline"
        )
        self.ax_correlation.legend()

        plt.ion()  # Interactive mode
        plt.tight_layout()
        plt.show(block=False)

    def update_matplotlib(self) -> None:
        """Update matplotlib figure with latest data."""
        if self.fig is None:
            return

        history = self.get_history()
        if not history:
            return

        iterations = [h.iteration for h in history]
        spearman_vals = [h.spearman for h in history]
        pearson_vals = [h.pearson for h in history]
        loss_vals = [h.loss for h in history]

        # Update loss plot
        self.ax_loss.clear()
        self.ax_loss.plot(iterations, loss_vals, "b-", linewidth=2)
        self.ax_loss.set_xlabel("Iteration")
        self.ax_loss.set_ylabel("Loss")
        self.ax_loss.set_title(f"Optimization Loss (latest={loss_vals[-1]:.4f})")
        self.ax_loss.grid(True, alpha=0.3)

        # Update correlation plot
        self.ax_correlation.clear()
        self.ax_correlation.plot(iterations, spearman_vals, "g-", linewidth=2, label="Spearman")
        self.ax_correlation.plot(iterations, pearson_vals, "r--", linewidth=2, label="Pearson")
        self.ax_correlation.axhline(
            self.baseline_spearman, color="gray", linestyle="--", alpha=0.5, label="baseline"
        )
        self.ax_correlation.set_xlabel("Iteration")
        self.ax_correlation.set_ylabel("Correlation")
        self.ax_correlation.set_ylim(-0.1, 1.0)
        self.ax_correlation.set_title(
            f"Correlation (best={max(spearman_vals):.4f})"
        )
        self.ax_correlation.grid(True, alpha=0.3)
        self.ax_correlation.legend()

        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def close_matplotlib(self) -> None:
        """Close matplotlib figure."""
        if self.fig is not None:
            import matplotlib.pyplot as plt
            plt.close(self.fig)
            self.fig = None

    # ── Plotly visualization ──────────────────────────────────────────────────

    def generate_plotly_figure(self) -> dict:
        """Generate a Plotly figure spec for web/Streamlit display."""
        history = self.get_history()

        iterations = [h.iteration for h in history]
        spearman_vals = [h.spearman for h in history]
        pearson_vals = [h.pearson for h in history]
        loss_vals = [h.loss for h in history]

        return {
            "data": [
                {
                    "x": iterations,
                    "y": spearman_vals,
                    "type": "scatter",
                    "mode": "lines",
                    "name": "Spearman",
                    "line": {"color": "green", "width": 2},
                },
                {
                    "x": iterations,
                    "y": pearson_vals,
                    "type": "scatter",
                    "mode": "lines",
                    "name": "Pearson",
                    "line": {"color": "red", "width": 2, "dash": "dash"},
                },
            ],
            "layout": {
                "title": "Optimization Progress: Correlation vs Iteration",
                "xaxis": {"title": "Iteration"},
                "yaxis": {"title": "Correlation", "range": [-0.1, 1.0]},
                "shapes": [
                    {
                        "type": "line",
                        "x0": 0,
                        "x1": max(iterations) if iterations else 1,
                        "y0": self.baseline_spearman,
                        "y1": self.baseline_spearman,
                        "line": {"color": "gray", "width": 1, "dash": "dot"},
                    }
                ],
                "height": 400,
            },
        }


# ── Integration helper ────────────────────────────────────────────────────────


def create_callback(monitor: TrainingMonitor, update_interval: int = 5):
    """Create a callback function for scipy.optimize differential_evolution.

    Args:
        monitor: TrainingMonitor instance to record progress
        update_interval: How often to print progress (every N iterations)

    Returns:
        Callback function that can be passed to scipy.optimize
    """

    def callback(xk, convergence=0.0):
        # Extract current metrics from the optimization state
        # Note: scipy's callback only gets the current solution, not metrics
        # We rely on the objective function to update the monitor
        iteration = len(monitor.get_history())
        latest = monitor.get_latest()

        if latest and iteration % update_interval == 0:
            monitor.print_progress(
                iteration=latest.iteration,
                spearman=latest.spearman,
                pearson=latest.pearson,
            )
            if monitor.fig is not None:
                monitor.update_matplotlib()

    return callback


def create_objective_wrapper(
    original_objective,
    monitor: TrainingMonitor,
    player_df,
    team_standings,
):
    """Wrap original objective function to record metrics during optimization.

    Args:
        original_objective: Original objective function (params, ...) -> loss
        monitor: TrainingMonitor to record metrics
        player_df: Player dataframe
        team_standings: Team standings dataframe

    Returns:
        Wrapped objective function that records metrics
    """

    def wrapped_objective(params, *args, **kwargs):
        # Call original objective
        loss = original_objective(params, player_df, team_standings, *args, **kwargs)

        # Compute correlation metrics
        from scipy.stats import spearmanr, pearsonr

        weights = _params_to_weights(params)
        ratings = _compute_ratings(player_df, weights)
        team_ratings = _compute_team_ratings(player_df, ratings)

        merged = team_ratings.merge(
            team_standings, on=["team", "league", "season"], how="inner"
        )

        if len(merged) >= 10:
            spearman_corr, _ = spearmanr(merged["avg_rating"], merged["total_points"])
            pearson_corr, _ = pearsonr(merged["avg_rating"], merged["total_points"])
        else:
            spearman_corr, pearson_corr = 0.0, 0.0

        # Record iteration
        iteration = len(monitor.get_history()) + 1
        monitor.record(
            iteration=iteration,
            spearman=spearman_corr,
            pearson=pearson_corr,
            n_teams=len(merged),
            loss=loss,
        )

        return loss

    return wrapped_objective


# ── Helper functions (simplified versions from optimize_ratings.py) ──────────


def _params_to_weights(params):
    """Convert flat parameter vector to structured weight dicts."""
    POSITIONS = ["ST", "W", "AM", "CM", "DM", "FB", "CB", "GK"]
    DIMENSIONS = ["availability", "attack", "defense", "possession", "quality"]
    ATTACK_METRICS = ["npxg_p90", "assists_p90", "g_a_volume"]

    def softmax(x):
        e = np.exp(x - np.max(x))
        return e / e.sum()

    idx = 0

    # Position weights (8×5)
    pw = {}
    for pos in POSITIONS:
        raw = params[idx : idx + 5]
        norm = softmax(raw)
        pw[pos] = dict(zip(DIMENSIONS, norm))
        idx += 5

    # Attack weights (8×3)
    aw = {}
    for pos in POSITIONS:
        raw = params[idx : idx + 3]
        norm = softmax(raw)
        aw[pos] = dict(zip(ATTACK_METRICS, norm))
        idx += 3

    # Availability sub-weights (4)
    avail_raw = params[idx : idx + 4]
    avail_sw = softmax(avail_raw)
    idx += 4

    # Quality sub-weights (4)
    qual_raw = params[idx : idx + 4]
    qual_sw = softmax(qual_raw)
    idx += 4

    # League log scale
    league_log_scale = params[idx]
    idx += 1

    # Reliability params
    rel_minutes_ref = 900 + params[idx] * 1800
    idx += 1
    rel_starts_ref = 0.3 + params[idx] * 0.4
    idx += 1

    return {
        "position_weights": pw,
        "attack_weights": aw,
        "avail_sub_weights": avail_sw,
        "qual_sub_weights": qual_sw,
        "league_log_scale": league_log_scale,
        "rel_minutes_ref": rel_minutes_ref,
        "rel_starts_ref": rel_starts_ref,
    }


def _compute_ratings(player_df, weights):
    """Compute player ratings with given weights."""
    import numpy as np

    pw = weights["position_weights"]
    aw = weights["attack_weights"]
    avail_sw = weights["avail_sub_weights"]
    qual_sw = weights["qual_sub_weights"]
    league_log_scale = weights["league_log_scale"]
    rel_min_ref = weights["rel_minutes_ref"]
    rel_starts_ref = weights["rel_starts_ref"]

    # UEFA coefficients
    uefa = {
        "ENG-Premier League": 119.52,
        "ESP-La Liga": 93.00,
        "GER-Bundesliga": 92.90,
        "ITA-Serie A": 81.93,
        "FRA-Ligue 1": 83.50,
    }
    eng_coeff = uefa["ENG-Premier League"]
    league_coeff = {k: (np.log(v) / np.log(eng_coeff)) ** league_log_scale for k, v in uefa.items()}

    league_med_min = player_df.groupby("league")["minutes"].median().to_dict()
    pos_groups = player_df.groupby("sub_position")

    ratings = []
    for _, row in player_df.iterrows():
        pos = row["sub_position"]
        pos_data = pos_groups.get_group(pos) if pos in pos_groups.groups else player_df

        # Availability
        med_min = league_med_min.get(row["league"], 1800)
        min_share = min(row["minutes"] / max(med_min, 1), 1) * 100
        start_rate_score = row["starts"] / max(row["matches"], 1) * 100
        avail_pct = min(row["matches"] / 38, 1) * 100
        role_stab = 50.0
        availability = (
            min_share * avail_sw[0]
            + start_rate_score * avail_sw[1]
            + avail_pct * avail_sw[2]
            + role_stab * avail_sw[3]
        )

        # Attack
        def percentile(values, value):
            if len(values) == 0:
                return 50.0
            return (values < value).sum() / len(values) * 100

        npg_pct = percentile(pos_data["npg_p90"].values, row["npg_p90"])
        ast_pct = percentile(pos_data["assists_p90"].values, row["assists_p90"])
        vol_pct = percentile(pos_data["g_a_volume"].values, row["g_a_volume"])

        pos_aw = aw.get(pos, aw.get("CM"))
        attack = (
            npg_pct * pos_aw["npxg_p90"]
            + ast_pct * pos_aw["assists_p90"]
            + vol_pct * pos_aw["g_a_volume"]
        )

        defense = 50.0
        possession = 50.0

        q_npg = percentile(pos_data["npg_p90"].values, row["npg_p90"])
        q_ast = percentile(pos_data["assists_p90"].values, row["assists_p90"])
        quality = q_npg * qual_sw[0] + q_ast * qual_sw[1] + 50 * qual_sw[2] + 50 * qual_sw[3]

        pos_pw = pw.get(pos, pw.get("CM"))
        base = (
            availability * pos_pw["availability"]
            + attack * pos_pw["attack"]
            + defense * pos_pw["defense"]
            + possession * pos_pw["possession"]
            + quality * pos_pw["quality"]
        )

        # Reliability
        min_rel = 0.5 + 0.5 * min(row["minutes"] / rel_min_ref, 1)
        sr = row["starts"] / max(row["matches"], 1) if row["matches"] > 0 else 0
        start_rel = 0.85 + 0.15 * min(sr / rel_starts_ref, 1)
        reliability = min_rel * start_rel

        lcoeff = league_coeff.get(row["league"], 1.0)
        overall = base * reliability * lcoeff
        ratings.append(overall)

    return np.array(ratings)


def _compute_team_ratings(player_df, ratings):
    """Compute per-team average rating."""
    df = player_df[["team", "league", "season", "minutes"]].copy()
    df["rating"] = ratings

    def weighted_avg(group):
        w = group["minutes"].clip(lower=1)
        return np.average(group["rating"], weights=w)

    team_ratings = df.groupby(["team", "league", "season"]).apply(
        weighted_avg, include_groups=False
    ).reset_index(name="avg_rating")
    return team_ratings

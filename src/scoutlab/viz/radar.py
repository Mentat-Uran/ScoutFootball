"""Dual-player radar chart for position-relative comparison."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

RADAR_METRICS = (
    "goals_p90_shrunk_10",
    "assists_p90_shrunk_10",
    "shots_p90_shrunk_10",
    "npxg_p90_shrunk_10",
    "xa_p90_shrunk_10",
    "xT_added_p90_shrunk_10",
    "tackles_p90_shrunk_10",
    "passes_p90_shrunk_10",
)

RADAR_LABELS = {
    "goals_p90_shrunk_10": "Goals/90",
    "assists_p90_shrunk_10": "Assists/90",
    "shots_p90_shrunk_10": "Shots/90",
    "npxg_p90_shrunk_10": "NPxG/90",
    "xa_p90_shrunk_10": "xA/90",
    "xT_added_p90_shrunk_10": "xT/90",
    "tackles_p90_shrunk_10": "Tackles/90",
    "passes_p90_shrunk_10": "Passes/90",
}


def plot_player_radar(
    player_a: pd.Series,
    player_b: pd.Series,
    position_pool: pd.DataFrame,
    *,
    metrics: tuple[str, ...] = RADAR_METRICS,
) -> go.Figure:
    available = [m for m in metrics if m in player_a.index and m in player_b.index]
    if not available:
        return _empty_figure("No overlapping metrics for radar comparison.")

    labels = [RADAR_LABELS.get(m, m) for m in available]
    a_pct = _percentile_rank(player_a, position_pool, available)
    b_pct = _percentile_rank(player_b, position_pool, available)

    name_a = str(player_a.get("player_name", "Player A"))
    name_b = str(player_b.get("player_name", "Player B"))

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(r=a_pct, theta=labels, fill="toself", name=name_a)
    )
    fig.add_trace(
        go.Scatterpolar(r=b_pct, theta=labels, fill="toself", name=name_b)
    )
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True,
        title="Position-Relative Radar",
    )
    return fig


def _percentile_rank(
    player: pd.Series,
    pool: pd.DataFrame,
    metrics: tuple[str, ...] | list[str],
) -> list[float]:
    ranks = []
    for m in metrics:
        if m not in pool.columns:
            ranks.append(50.0)
            continue
        col = pd.to_numeric(pool[m], errors="coerce").dropna()
        if col.empty:
            ranks.append(50.0)
            continue
        val = pd.to_numeric(player.get(m), errors="coerce")
        if pd.isna(val):
            ranks.append(0.0)
            continue
        ranks.append(float((col < val).mean() * 100))
    return ranks


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=message)
    return fig

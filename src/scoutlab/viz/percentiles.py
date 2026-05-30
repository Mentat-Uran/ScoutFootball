"""Position-relative percentile bar chart."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

PERCENTILE_METRICS = (
    "goals_p90_shrunk_10",
    "assists_p90_shrunk_10",
    "shots_p90_shrunk_10",
    "npxg_p90_shrunk_10",
    "xa_p90_shrunk_10",
    "xT_added_p90_shrunk_10",
    "tackles_p90_shrunk_10",
    "passes_p90_shrunk_10",
)

PERCENTILE_LABELS = {
    "goals_p90_shrunk_10": "Goals/90",
    "assists_p90_shrunk_10": "Assists/90",
    "shots_p90_shrunk_10": "Shots/90",
    "npxg_p90_shrunk_10": "NPxG/90",
    "xa_p90_shrunk_10": "xA/90",
    "xT_added_p90_shrunk_10": "xT/90",
    "tackles_p90_shrunk_10": "Tackles/90",
    "passes_p90_shrunk_10": "Passes/90",
}


def plot_percentile_bars(
    player: pd.Series,
    position_pool: pd.DataFrame,
    *,
    metrics: tuple[str, ...] = PERCENTILE_METRICS,
) -> go.Figure:
    available = [m for m in metrics if m in player.index]
    if not available:
        return _empty_figure("No metrics available for percentile chart.")

    labels = [PERCENTILE_LABELS.get(m, m) for m in available]
    pcts = _compute_percentiles(player, position_pool, available)

    colors = [_pct_color(p) for p in pcts]
    texts = [f"{p:.0f}" for p in pcts]

    fig = go.Figure(
        go.Bar(
            x=pcts,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=texts,
            textposition="outside",
        )
    )
    player_name = player.get("player_name", "Player")
    fig.update_layout(
        title=f"{player_name} — Position Percentiles",
        xaxis_title="Percentile",
        xaxis=dict(range=[0, 105]),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def _compute_percentiles(
    player: pd.Series,
    pool: pd.DataFrame,
    metrics: list[str],
) -> list[float]:
    result = []
    for m in metrics:
        if m not in pool.columns:
            result.append(50.0)
            continue
        col = pd.to_numeric(pool[m], errors="coerce").dropna()
        val = pd.to_numeric(player.get(m), errors="coerce")
        if pd.isna(val) or col.empty:
            result.append(0.0)
            continue
        result.append(float((col < val).mean() * 100))
    return result


def _pct_color(pct: float) -> str:
    if pct >= 80:
        return "#2ca02c"
    if pct >= 50:
        return "#1f77b4"
    if pct >= 25:
        return "#ff7f0e"
    return "#d62728"


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=message)
    return fig

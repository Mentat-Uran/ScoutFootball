"""Player and team trend charts over time."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

DEFAULT_TREND_METRICS = (
    "goals_p90_shrunk_10",
    "assists_p90_shrunk_10",
    "npxg_p90_shrunk_10",
    "xa_p90_shrunk_10",
)

TREND_LABELS = {
    "goals_p90_shrunk_10": "Goals/90",
    "assists_p90_shrunk_10": "Assists/90",
    "npxg_p90_shrunk_10": "NPxG/90",
    "xa_p90_shrunk_10": "xA/90",
    "xT_added_p90_shrunk_10": "xT/90",
    "points_per_match_10": "Pts/Match",
    "goal_diff_per_match_10": "GD/Match",
    "elo_pre_mean_10": "Elo (avg)",
}


def plot_trend(
    entity_df: pd.DataFrame,
    metric: str = "goals_p90_shrunk_10",
    *,
    date_col: str = "match_date",
    entity_name: str | None = None,
) -> go.Figure:
    if metric not in entity_df.columns:
        return _empty_figure(f"Metric '{metric}' not found in data.")

    plot_df = entity_df.copy()
    plot_df[date_col] = pd.to_datetime(plot_df[date_col], errors="coerce")
    plot_df = plot_df.dropna(subset=[date_col, metric]).sort_values(date_col)

    label = TREND_LABELS.get(metric, metric)
    title = f"{entity_name or 'Entity'} — {label} Trend"

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=plot_df[date_col],
            y=plot_df[metric],
            mode="lines+markers",
            name=label,
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=label,
        hovermode="x unified",
    )
    return fig


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=message)
    return fig

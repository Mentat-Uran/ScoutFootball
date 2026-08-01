"""Market value vs performance scatter plot."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def plot_value_scatter(
    oof_df: pd.DataFrame,
    *,
    performance_col: str = "predicted_market_value_log",
    value_col: str = "actual_market_value_log",
    label_col: str = "fairness_label",
    name_col: str = "player_name",
    date_col: str = "snapshot_date",
) -> go.Figure:
    for col in (performance_col, value_col, label_col):
        if col not in oof_df.columns:
            return _empty_figure(f"Column '{col}' not found in data.")

    plot_df = oof_df.dropna(subset=[performance_col, value_col]).copy()
    if plot_df.empty:
        return _empty_figure("No data after dropping NaNs.")

    color_map = {"cheap": "#2ca02c", "fair": "#1f77b4", "expensive": "#d62728"}
    colors = plot_df[label_col].map(color_map).fillna("#999999")

    hover_text = plot_df.apply(
        lambda row: (
            f"{row.get(name_col, '')}<br>"
            f"Date: {row.get(date_col, '')}<br>"
            f"Label: {row.get(label_col, '')}"
        ),
        axis=1,
    )

    fig = go.Figure(
        go.Scatter(
            x=plot_df[performance_col],
            y=plot_df[value_col],
            mode="markers",
            marker=dict(color=colors, size=8, opacity=0.7),
            text=hover_text,
            hoverinfo="text",
        )
    )
    lo = min(plot_df[performance_col].min(), plot_df[value_col].min())
    hi = max(plot_df[performance_col].max(), plot_df[value_col].max())
    fig.add_shape(
        type="line",
        x0=lo,
        y0=lo,
        x1=hi,
        y1=hi,
        line=dict(dash="dash", color="gray"),
    )

    fig.update_layout(
        title="Market Value vs Predicted Value",
        xaxis_title="Predicted log(market_value)",
        yaxis_title="Actual log(market_value)",
        hovermode="closest",
    )
    return fig


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=message)
    return fig

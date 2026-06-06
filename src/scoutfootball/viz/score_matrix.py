"""Score probability matrix heatmap for match prediction."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def plot_score_matrix(
    score_matrix: pd.DataFrame,
    *,
    home_team: str = "Home",
    away_team: str = "Away",
    summary: dict[str, float] | None = None,
) -> go.Figure:
    fig = go.Figure(
        go.Heatmap(
            z=score_matrix.values,
            x=[str(c) for c in score_matrix.columns],
            y=[str(i) for i in score_matrix.index],
            colorscale="Blues",
            text=[[f"{v:.3f}" for v in row] for row in score_matrix.values],
            texttemplate="%{text}",
            hovertemplate=("Home %{y} - Away %{x}: %{z:.4f}<extra></extra>"),
        )
    )

    title_parts = [f"Score Matrix: {home_team} vs {away_team}"]
    if summary:
        hw = summary.get("home_win", 0)
        dr = summary.get("draw", 0)
        aw = summary.get("away_win", 0)
        title_parts.append(f"1X2: {hw:.1%} / {dr:.1%} / {aw:.1%}")
        o25 = summary.get("over_2_5", 0)
        btts = summary.get("btts_yes", 0)
        title_parts.append(f"O2.5: {o25:.1%}  BTTS: {btts:.1%}")

    fig.update_layout(
        title="<br>".join(title_parts),
        xaxis_title=f"{away_team} Goals",
        yaxis_title=f"{home_team} Goals",
    )
    return fig

"""Value Deviation page: actual vs predicted market value, overvalued/undervalued rankings."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats as sp_stats

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scoutfootball.app.data_loader import load_oof_predictions
from scoutfootball.evaluation.coverage_confidence import display_confidence_badge

COLOR_SEQ = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


def _fmt_value(v: float) -> str:
    """Format market value to human-readable string."""
    if pd.isna(v):
        return "\u2014"
    if v >= 1e6:
        return f"\u20ac{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"\u20ac{v / 1e3:.0f}K"
    return f"\u20ac{v:,.0f}"


def _build_scatter(df: pd.DataFrame, color_col: str | None = None) -> go.Figure:
    """Build actual vs predicted market value scatter with 45-degree reference line."""
    x_col = "actual_market_value"
    y_col = "predicted_market_value"
    for col in (x_col, y_col):
        if col not in df.columns:
            return go.Figure().update_layout(title=f"Column '{col}' not found")

    plot_df = df.dropna(subset=[x_col, y_col]).copy()
    if plot_df.empty:
        return go.Figure().update_layout(title="No data after dropping NaNs")

    # Color by position group if available
    if color_col and color_col in plot_df.columns:
        groups = sorted(plot_df[color_col].dropna().unique())
        fig = go.Figure()
        for i, grp in enumerate(groups):
            sub = plot_df[plot_df[color_col] == grp]
            hover = sub.apply(
                lambda row: (
                    f"{row.get('player_name', '')}<br>"
                    f"Team: {row.get('team_name', '—')}<br>"
                    f"Actual: {_fmt_value(row[x_col])}<br>"
                    f"Predicted: {_fmt_value(row[y_col])}<br>"
                    f"Residual: {row.get('residual_log', np.nan):.3f}"
                ),
                axis=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=sub[x_col],
                    y=sub[y_col],
                    mode="markers",
                    name=str(grp),
                    marker=dict(size=8, opacity=0.7, color=COLOR_SEQ[i % len(COLOR_SEQ)]),
                    text=hover,
                    hoverinfo="text",
                )
            )
    else:
        hover = plot_df.apply(
            lambda row: (
                f"{row.get('player_name', '')}<br>"
                f"Team: {row.get('team_name', '—')}<br>"
                f"Actual: {_fmt_value(row[x_col])}<br>"
                f"Predicted: {_fmt_value(row[y_col])}<br>"
                f"Residual: {row.get('residual_log', np.nan):.3f}"
            ),
            axis=1,
        )
        fig = go.Figure(
            go.Scatter(
                x=plot_df[x_col],
                y=plot_df[y_col],
                mode="markers",
                marker=dict(size=8, opacity=0.7, color="#1f77b4"),
                text=hover,
                hoverinfo="text",
            )
        )

    # 45-degree reference line (fair value)
    lo = min(plot_df[x_col].min(), plot_df[y_col].min())
    hi = max(plot_df[x_col].max(), plot_df[y_col].max())
    margin = (hi - lo) * 0.05
    fig.add_shape(
        type="line",
        x0=lo - margin, y0=lo - margin,
        x1=hi + margin, y1=hi + margin,
        line=dict(dash="dash", color="gray"),
    )

    fig.update_layout(
        title="Actual vs Predicted Market Value",
        xaxis_title="Actual Market Value",
        yaxis_title="Predicted Market Value",
        hovermode="closest",
    )
    return fig


def _build_residual_histogram(df: pd.DataFrame) -> tuple:
    """Build histogram of residuals with KDE overlay."""
    residuals = df["residual_log"].dropna()
    mean_r = residuals.mean()
    median_r = residuals.median()
    std_r = residuals.std()

    fig = go.Figure()

    # Histogram
    fig.add_trace(go.Histogram(
        x=residuals,
        nbinsx=50,
        name="Residuals",
        marker_color="#1f77b4",
        opacity=0.7,
        histnorm="probability density",
    ))

    # KDE overlay
    if len(residuals) > 1:
        kde_x = np.linspace(residuals.min() - 0.5, residuals.max() + 0.5, 300)
        try:
            kde = sp_stats.gaussian_kde(residuals.values)
            kde_y = kde(kde_x)
            fig.add_trace(go.Scatter(
                x=kde_x,
                y=kde_y,
                mode="lines",
                name="KDE",
                line=dict(color="#d62728", width=2),
            ))
        except Exception:
            pass  # KDE may fail on degenerate data

    # Vertical lines for mean and median
    fig.add_vline(x=mean_r, line_dash="dash", line_color="#ff7f0e",
                  annotation_text=f"Mean: {mean_r:.3f}", annotation_position="top right")
    fig.add_vline(x=median_r, line_dash="dot", line_color="#2ca02c",
                  annotation_text=f"Median: {median_r:.3f}", annotation_position="top left")
    fig.add_vline(x=0, line_dash="solid", line_color="gray", line_width=1, opacity=0.5)

    fig.update_layout(
        title="OOF Residual Distribution (predicted - actual, log scale)",
        xaxis_title="Residual (log)",
        yaxis_title="Density",
        hovermode="x unified",
        showlegend=True,
    )
    return fig, mean_r, median_r, std_r


def _build_group_bias_chart(df: pd.DataFrame, group_col: str, title: str,
                            xaxis_title: str) -> go.Figure:
    """Build bar chart of mean residual per group, colored by over/under estimation."""
    grp = df.groupby(group_col)["residual_log"].agg(["mean", "std", "count"]).reset_index()
    grp = grp.sort_values("mean")

    colors = ["#d62728" if v > 0 else "#2ca02c" for v in grp["mean"]]

    fig = go.Figure(go.Bar(
        x=grp[group_col],
        y=grp["mean"],
        marker_color=colors,
        error_y=dict(type="data", array=grp["std"], visible=True, thickness=1),
        text=[f"n={int(c)}" for c in grp["count"]],
        textposition="outside",
        hovertemplate=(
            f"{group_col}: %{{x}}<br>"
            "Mean residual: %{y:.3f}<br>"
            "Std: %{customdata[0]:.3f}<br>"
            "Count: %{customdata[1]}"
        ),
        customdata=grp[["std", "count"]].values,
    ))

    fig.add_hline(y=0, line_dash="solid", line_color="gray", line_width=1)

    fig.update_layout(
        title=title,
        xaxis_title=xaxis_title,
        yaxis_title="Mean Residual (log)",
        hovermode="closest",
    )
    return fig


def _build_age_scatter(df: pd.DataFrame, color_col: str | None = None) -> go.Figure:
    """Build scatter plot of age vs residual, colored by position group."""
    plot_df = df.dropna(subset=["age", "residual_log"]).copy()

    if color_col and color_col in plot_df.columns:
        groups = sorted(plot_df[color_col].dropna().unique())
        fig = go.Figure()
        for i, grp in enumerate(groups):
            sub = plot_df[plot_df[color_col] == grp]
            fig.add_trace(go.Scatter(
                x=sub["age"],
                y=sub["residual_log"],
                mode="markers",
                name=str(grp),
                marker=dict(size=7, opacity=0.6, color=COLOR_SEQ[i % len(COLOR_SEQ)]),
                text=sub.apply(
                    lambda r: (
                        f"{r.get('player_name', '')}<br>"
                        f"Age: {r['age']}<br>"
                        f"Residual: {r['residual_log']:.3f}"
                    ),
                    axis=1,
                ),
                hoverinfo="text",
            ))
    else:
        fig = go.Figure(go.Scatter(
            x=plot_df["age"],
            y=plot_df["residual_log"],
            mode="markers",
            marker=dict(size=7, opacity=0.6, color="#1f77b4"),
            text=plot_df.apply(
                lambda r: (
                    f"{r.get('player_name', '')}<br>"
                    f"Age: {r['age']}<br>"
                    f"Residual: {r['residual_log']:.3f}"
                ),
                axis=1,
            ),
            hoverinfo="text",
            name="Players",
        ))

    # Trend line (LOWESS-like via polynomial fit)
    if len(plot_df) > 2:
        try:
            x_sorted = np.linspace(plot_df["age"].min(), plot_df["age"].max(), 200)
            coeffs = np.polyfit(
                plot_df["age"].to_numpy(dtype=float),
                plot_df["residual_log"].to_numpy(dtype=float),
                deg=2,
            )
            y_trend = np.polyval(coeffs, x_sorted)
            fig.add_trace(go.Scatter(
                x=x_sorted,
                y=y_trend,
                mode="lines",
                name="Trend",
                line=dict(color="black", width=2, dash="dash"),
            ))
        except Exception:
            pass

    fig.add_hline(y=0, line_dash="solid", line_color="gray", line_width=1, opacity=0.5)

    fig.update_layout(
        title="Age vs Residual",
        xaxis_title="Age",
        yaxis_title="Residual (log)",
        hovermode="closest",
    )
    return fig


def _top_bottom_tables(df: pd.DataFrame) -> None:
    """Show top 10 over-estimated and top 10 under-estimated players."""
    need_cols = ["player_name", "predicted_market_value", "actual_market_value", "residual_log"]
    available = [c for c in need_cols if c in df.columns]
    if "residual_log" not in available:
        st.info("Cannot build over/under-estimated tables: missing residual_log column.")
        return

    display_cols = []
    rename_map = {}

    if "player_name" in df.columns:
        display_cols.append("player_name")
        rename_map["player_name"] = "Player"
    if "team_name" in df.columns:
        display_cols.append("team_name")
        rename_map["team_name"] = "Team"
    if "position_group" in df.columns:
        display_cols.append("position_group")
        rename_map["position_group"] = "Position"
    if "actual_market_value" in df.columns:
        display_cols.append("actual_market_value")
        rename_map["actual_market_value"] = "Actual Value"
    if "predicted_market_value" in df.columns:
        display_cols.append("predicted_market_value")
        rename_map["predicted_market_value"] = "Predicted Value"
    display_cols.append("residual_log")
    rename_map["residual_log"] = "Residual (log)"

    col_over, col_under = st.columns(2)

    with col_over:
        st.subheader("Top 10 Over-Estimated")
        st.caption("Players where predicted value > actual value (residual > 0)")
        over_df = df.loc[df["residual_log"] > 0].sort_values(
            "residual_log", ascending=False
        ).head(10)
        if over_df.empty:
            st.info("No over-estimated players in filtered data.")
        else:
            show: pd.DataFrame = over_df[display_cols].copy()
            show.columns = [rename_map.get(c, c) for c in display_cols]
            show = show.reset_index(drop=True)
            for col in ("Actual Value", "Predicted Value"):
                if col in show.columns:
                    show[col] = show[col].apply(_fmt_value)
            show.index = show.index + 1
            st.dataframe(show, use_container_width=True)

    with col_under:
        st.subheader("Top 10 Under-Estimated")
        st.caption("Players where predicted value < actual value (residual < 0)")
        under_df = df.loc[df["residual_log"] < 0].sort_values(
            "residual_log", ascending=True
        ).head(10)
        if under_df.empty:
            st.info("No under-estimated players in filtered data.")
        else:
            show: pd.DataFrame = under_df[display_cols].copy()
            show.columns = [rename_map.get(c, c) for c in display_cols]
            show = show.reset_index(drop=True)
            for col in ("Actual Value", "Predicted Value"):
                if col in show.columns:
                    show[col] = show[col].apply(_fmt_value)
            show.index = show.index + 1
            st.dataframe(show, use_container_width=True)


def _deviation_table(df: pd.DataFrame, sort_ascending: bool, label: str) -> None:
    """Render a Top 20 deviation table."""
    if "residual_log" not in df.columns:
        st.info(f"Cannot generate {label} table: missing residual_log column.")
        return

    sorted_df = df.sort_values("residual_log", ascending=sort_ascending).head(20)
    display_cols = []
    rename_map = {}

    if "player_name" in sorted_df.columns:
        display_cols.append("player_name")
        rename_map["player_name"] = "Player"
    if "team_name" in sorted_df.columns:
        display_cols.append("team_name")
        rename_map["team_name"] = "Team"
    if "league" in sorted_df.columns:
        display_cols.append("league")
        rename_map["league"] = "League"
    if "actual_market_value" in sorted_df.columns:
        display_cols.append("actual_market_value")
        rename_map["actual_market_value"] = "Actual Value"
    if "predicted_market_value" in sorted_df.columns:
        display_cols.append("predicted_market_value")
        rename_map["predicted_market_value"] = "Predicted Value"
    display_cols.append("residual_log")
    rename_map["residual_log"] = "Residual (log)"

    show_df = sorted_df[display_cols].copy()
    # Format value columns
    for col in ("actual_market_value", "predicted_market_value"):
        if col in show_df.columns:
            show_df[col] = show_df[col].apply(_fmt_value)

    show_df = show_df.rename(columns=rename_map).reset_index(drop=True)
    show_df.index = show_df.index + 1  # 1-based ranking

    st.dataframe(show_df, use_container_width=True)


# -- Page ------------------------------------------------------------------

st.header("Value Deviation Analysis")

oof = load_oof_predictions()

if oof.empty:
    st.warning(
        "No OOF prediction data available. To generate this data, run "
        "`scoutfootball train` which produces `models/oof_predictions/value_fairness_oof.parquet`."
    )
    st.stop()

if oof.get("is_synthetic", pd.Series(dtype=bool)).any():
    st.info(
        "Currently using synthetic demo data. Results are for illustration only. "
        "Run `scoutfootball train` to generate real predictions."
    )

# -- Sidebar filters -------------------------------------------------------

with st.sidebar:
    st.subheader("Filters")

    # League filter
    league_col = "league"
    if league_col in oof.columns:
        leagues = sorted(oof[league_col].dropna().unique())
        selected_leagues = st.multiselect("League", leagues, default=leagues, key="vd_league")
    else:
        selected_leagues = None

    # Position filter
    pos_col = "position_group"
    if pos_col in oof.columns:
        positions = sorted(oof[pos_col].dropna().unique())
        selected_pos = st.multiselect("Position", positions, default=positions, key="vd_position")
    else:
        selected_pos = None

    # Age band filter
    age_col = "age"
    if age_col in oof.columns:
        age_vals = oof[age_col].dropna()
        if age_vals.empty:
            st.info('No valid age data available.')
            st.stop()
        age_min = int(age_vals.min())
        age_max = int(age_vals.max())
        age_range = st.slider("Age Range", age_min, age_max, (age_min, age_max), key="vd_age")
    else:
        age_range = None

    # Sort direction
    sort_mode = st.radio("Sort Direction", ["Over-Estimated", "Under-Estimated"],
                         index=0, key="vd_sort")

# -- Apply filters ---------------------------------------------------------

filtered = oof.copy()

if selected_leagues is not None and league_col in filtered.columns:
    filtered = filtered[filtered[league_col].isin(selected_leagues)]

if selected_pos is not None and pos_col in filtered.columns:
    filtered = filtered[filtered[pos_col].isin(selected_pos)]

if age_range is not None and age_col in filtered.columns:
    filtered = filtered[(filtered[age_col] >= age_range[0]) & (filtered[age_col] <= age_range[1])]

if filtered.empty:
    st.warning("No data after applying filters.")
    st.stop()

# -- Confidence badge ------------------------------------------------------

if "confidence_level" in filtered.columns:
    mode_conf = filtered["confidence_level"].mode()
    if not mode_conf.empty:
        display_confidence_badge(mode_conf.iloc[0])

# -- Scatter plot -----------------------------------------------------------

fig = _build_scatter(filtered, color_col=pos_col if pos_col in filtered.columns else None)
st.plotly_chart(fig, use_container_width=True)

# -- Summary metrics --------------------------------------------------------

if "residual_log" in filtered.columns:
    col1, col2, col3 = st.columns(3)
    col1.metric("Sample Size", len(filtered))
    col2.metric("Mean Residual (log)", f"{filtered['residual_log'].mean():.3f}")
    col3.metric("MAE (log)", f"{float(np.abs(filtered['residual_log']).mean()):.3f}")

# -- OOF Residual Distribution ---------------------------------------------

if "residual_log" in filtered.columns:
    st.subheader("OOF Residual Distribution")
    hist_fig, mean_r, median_r, std_r = _build_residual_histogram(filtered)
    c1, c2, c3 = st.columns(3)
    c1.metric("Mean Residual", f"{mean_r:.4f}")
    c2.metric("Median Residual", f"{median_r:.4f}")
    c3.metric("Std of Residuals", f"{std_r:.4f}")
    st.plotly_chart(hist_fig, use_container_width=True)

# -- Top 10 Over / Under Tables -------------------------------------------

if "residual_log" in filtered.columns:
    st.subheader("Top 10 Over/Under-Estimated Players")
    _top_bottom_tables(filtered)

# -- League Bias Analysis --------------------------------------------------

if "residual_log" in filtered.columns and "league" in filtered.columns:
    st.subheader("League Bias Analysis")
    st.caption(
        "Mean residual per league. Bars above zero indicate systematic over-estimation "
        "(model predicts higher than actual); bars below zero indicate under-estimation."
    )
    league_fig = _build_group_bias_chart(
        filtered, "league",
        title="Mean Residual by League",
        xaxis_title="League",
    )
    st.plotly_chart(league_fig, use_container_width=True)

# -- Position Bias Analysis ------------------------------------------------

if "residual_log" in filtered.columns and "position_group" in filtered.columns:
    st.subheader("Position Bias Analysis")
    st.caption(
        "Mean residual per position group. Bars above zero indicate systematic over-estimation; "
        "bars below zero indicate under-estimation."
    )
    pos_fig = _build_group_bias_chart(
        filtered, "position_group",
        title="Mean Residual by Position",
        xaxis_title="Position Group",
    )
    st.plotly_chart(pos_fig, use_container_width=True)

# -- Age vs Residual Scatter -----------------------------------------------

if "residual_log" in filtered.columns and "age" in filtered.columns:
    st.subheader("Age vs Residual")
    st.caption(
        "Scatter plot of player age against prediction residual. "
        "A trend line shows whether the model has systematic age-related bias."
    )
    age_fig = _build_age_scatter(
        filtered,
        color_col=pos_col if pos_col in filtered.columns else None,
    )
    st.plotly_chart(age_fig, use_container_width=True)
elif "residual_log" in filtered.columns and "age" not in filtered.columns:
    st.info(
        "Age vs residual analysis requires an 'age' column"
        " in the OOF data, which is not present."
    )

# -- Legacy Top 20 tables (original functionality) -------------------------

st.subheader("Top 20 Deviation Tables")

tab_over, tab_under = st.tabs(["Over-Estimated Top 20", "Under-Estimated Top 20"])

with tab_over:
    # Overvalued: residual_log > 0 means predicted > actual (model says worth more)
    st.caption(
        "Players the model thinks should be worth more"
        " than their actual market value (residual > 0)"
    )
    has_residual = "residual_log" in filtered.columns
    over_df = (
        filtered[filtered["residual_log"] > 0] if has_residual else filtered
    )
    _deviation_table(over_df, sort_ascending=False, label="over-estimated")

with tab_under:
    # Undervalued: residual_log < 0 means predicted < actual (model says worth less)
    st.caption(
        "Players the model thinks should be worth less"
        " than their actual market value (residual < 0)"
    )
    under_df = (
        filtered[filtered["residual_log"] < 0] if has_residual else filtered
    )
    _deviation_table(under_df, sort_ascending=True, label="under-estimated")

# -- Low confidence marker -------------------------------------------------

if "confidence_level" in filtered.columns:
    low_conf = filtered[filtered["confidence_level"] == "low"]
    if not low_conf.empty:
        st.warning(
            f"{len(low_conf)} players have insufficient data coverage. "
            "Results for these players have low confidence."
        )

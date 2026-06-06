"""Value Deviation page: actual vs predicted market value, overvalued/undervalued rankings."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scoutfootball.app.data_loader import load_oof_predictions
from scoutfootball.evaluation.coverage_confidence import display_confidence_badge


def _fmt_value(v: float) -> str:
    """Format market value to human-readable string."""
    if pd.isna(v):
        return "—"
    if v >= 1e6:
        return f"€{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"€{v / 1e3:.0f}K"
    return f"€{v:,.0f}"


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
        color_seq = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        ]
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
                    marker=dict(size=8, opacity=0.7, color=color_seq[i % len(color_seq)]),
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
        title="实际身价 vs 预测身价",
        xaxis_title="实际身价 (€)",
        yaxis_title="预测身价 (€)",
        hovermode="closest",
    )
    return fig


def _deviation_table(df: pd.DataFrame, sort_ascending: bool, label: str) -> None:
    """Render a Top 20 deviation table."""
    if "residual_log" not in df.columns:
        st.info(f"无法生成{label}榜：缺少 residual_log 列")
        return

    sorted_df = df.sort_values("residual_log", ascending=sort_ascending).head(20)
    display_cols = []
    rename_map = {}

    if "player_name" in sorted_df.columns:
        display_cols.append("player_name")
        rename_map["player_name"] = "球员"
    if "team_name" in sorted_df.columns:
        display_cols.append("team_name")
        rename_map["team_name"] = "球队"
    if "league" in sorted_df.columns:
        display_cols.append("league")
        rename_map["league"] = "联赛"
    if "actual_market_value" in sorted_df.columns:
        display_cols.append("actual_market_value")
        rename_map["actual_market_value"] = "实际身价"
    if "predicted_market_value" in sorted_df.columns:
        display_cols.append("predicted_market_value")
        rename_map["predicted_market_value"] = "预测身价"
    display_cols.append("residual_log")
    rename_map["residual_log"] = "残差(log)"

    show_df = sorted_df[display_cols].copy()
    # Format value columns
    for col in ("actual_market_value", "predicted_market_value"):
        if col in show_df.columns:
            show_df[col] = show_df[col].apply(_fmt_value)

    show_df = show_df.rename(columns=rename_map).reset_index(drop=True)
    show_df.index = show_df.index + 1  # 1-based ranking

    st.dataframe(show_df, use_container_width=True)


# ── Page ──────────────────────────────────────────────────────────────────

st.header("身价偏离榜")

oof = load_oof_predictions()

if oof.empty:
    st.warning("暂无 OOF 预测数据。请先运行 `scoutfootball train`。")
    st.stop()

if oof.get("is_synthetic", pd.Series(dtype=bool)).any():
    st.info("当前使用合成演示数据，结果仅供参考。请运行 `scoutfootball train` 生成真实预测。")

# ── Sidebar filters ───────────────────────────────────────────────────────

with st.sidebar:
    st.subheader("筛选条件")

    # League filter
    league_col = "league"
    if league_col in oof.columns:
        leagues = sorted(oof[league_col].dropna().unique())
        selected_leagues = st.multiselect("联赛", leagues, default=leagues, key="vd_league")
    else:
        selected_leagues = None

    # Position filter
    pos_col = "position_group"
    if pos_col in oof.columns:
        positions = sorted(oof[pos_col].dropna().unique())
        selected_pos = st.multiselect("位置", positions, default=positions, key="vd_position")
    else:
        selected_pos = None

    # Age band filter
    age_col = "age"
    if age_col in oof.columns:
        age_min = int(oof[age_col].min())
        age_max = int(oof[age_col].max())
        age_range = st.slider("年龄范围", age_min, age_max, (age_min, age_max), key="vd_age")
    else:
        age_range = None

    # Sort direction
    sort_mode = st.radio("排序方式", ["高估", "低估"], index=0, key="vd_sort")

# ── Apply filters ─────────────────────────────────────────────────────────

filtered = oof.copy()

if selected_leagues is not None and league_col in filtered.columns:
    filtered = filtered[filtered[league_col].isin(selected_leagues)]

if selected_pos is not None and pos_col in filtered.columns:
    filtered = filtered[filtered[pos_col].isin(selected_pos)]

if age_range is not None and age_col in filtered.columns:
    filtered = filtered[(filtered[age_col] >= age_range[0]) & (filtered[age_col] <= age_range[1])]

if filtered.empty:
    st.warning("筛选后无数据。")
    st.stop()

# ── Confidence badge ──────────────────────────────────────────────────────

if "confidence_level" in filtered.columns:
    mode_conf = filtered["confidence_level"].mode()
    if not mode_conf.empty:
        display_confidence_badge(mode_conf.iloc[0])

# ── Scatter plot ──────────────────────────────────────────────────────────

fig = _build_scatter(filtered, color_col=pos_col if pos_col in filtered.columns else None)
st.plotly_chart(fig, use_container_width=True)

# ── Summary metrics ───────────────────────────────────────────────────────

if "residual_log" in filtered.columns:
    col1, col2, col3 = st.columns(3)
    col1.metric("样本数", len(filtered))
    col2.metric("平均残差(log)", f"{filtered['residual_log'].mean():.3f}")
    col3.metric("MAE(log)", f"{filtered['residual_log'].abs().mean():.3f}")

# ── Top 20 tables ─────────────────────────────────────────────────────────

tab_over, tab_under = st.tabs(["高估 Top 20", "低估 Top 20"])

with tab_over:
    # Overvalued: residual_log > 0 means predicted > actual (model says worth more)
    st.caption("模型认为应值更高但实际身价偏低的球员（residual > 0）")
    has_residual = "residual_log" in filtered.columns
    over_df = (
        filtered[filtered["residual_log"] > 0] if has_residual else filtered
    )
    _deviation_table(over_df, sort_ascending=False, label="高估")

with tab_under:
    # Undervalued: residual_log < 0 means predicted < actual (model says worth less)
    st.caption("模型认为应值更低但实际身价偏高的球员（residual < 0）")
    under_df = (
        filtered[filtered["residual_log"] < 0] if has_residual else filtered
    )
    _deviation_table(under_df, sort_ascending=True, label="低估")

# ── Low confidence marker ─────────────────────────────────────────────────

if "confidence_level" in filtered.columns:
    low_conf = filtered[filtered["confidence_level"] == "low"]
    if not low_conf.empty:
        st.warning(f"有 {len(low_conf)} 名球员数据覆盖不足，结果置信度低，仅供参考。")

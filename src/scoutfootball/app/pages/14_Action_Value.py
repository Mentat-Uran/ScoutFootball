"""Action value sample page backed by local StatsBomb-derived metrics."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scoutfootball.app.data_loader import load_player_value_metrics

st.header("动作价值样本")
st.caption(
    "当前页面只展示 `player_value_metrics.parquet` 中的 StatsBomb 样本球员，"
    "不代表全量联赛动作价值。"
)

frame = load_player_value_metrics()
if frame.empty:
    st.warning("暂无动作价值产物。请先生成 `player_value_metrics.parquet`。")
    st.stop()

working = frame.copy()
if "composite_score" in working.columns:
    working = working.sort_values("composite_score", ascending=False).reset_index(drop=True)

metric_col1, metric_col2, metric_col3 = st.columns(3)
metric_col1.metric("样本球员", len(working))
metric_col2.metric(
    "有 xT/90",
    int(working["xT_per_90"].notna().sum()) if "xT_per_90" in working.columns else 0,
)
metric_col3.metric(
    "有 finishing delta",
    int(working["finishing_delta"].notna().sum()) if "finishing_delta" in working.columns else 0,
)

st.subheader("Top Action Value Players")
display_cols = [
    col
    for col in [
        "player_name",
        "composite_score",
        "xT_per_90",
        "finishing_delta",
        "progressive_carries_per_90",
        "final_third_touches_per_90",
    ]
    if col in working.columns
]
st.dataframe(working[display_cols], use_container_width=True, hide_index=True)

if {"player_name", "xT_per_90", "composite_score"}.issubset(working.columns):
    chart_df = working.dropna(subset=["xT_per_90"]).head(15).copy()
    if not chart_df.empty:
        st.subheader("xT/90 vs Composite Score")
        fig = px.scatter(
            chart_df,
            x="xT_per_90",
            y="composite_score",
            hover_name="player_name",
            size=(
                "progressive_carries_per_90"
                if "progressive_carries_per_90" in chart_df.columns
                else None
            ),
            color="finishing_delta" if "finishing_delta" in chart_df.columns else None,
        )
        st.plotly_chart(fig, use_container_width=True)

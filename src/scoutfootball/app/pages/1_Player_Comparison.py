"""Dual-player comparison page with radar chart and percentile table."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scoutfootball.app.data_loader import load_player_rolling
from scoutfootball.evaluation.confidence import (
    assess_player_confidence,
    display_confidence_warnings,
)
from scoutfootball.viz.radar import RADAR_LABELS, RADAR_METRICS, plot_player_radar

st.header("Player Comparison")

df = load_player_rolling()

player_names = sorted(df["player_name"].dropna().unique()) if "player_name" in df.columns else []
if not player_names:
    st.warning("No player data available.")
    st.stop()

col_a, col_b = st.columns(2)
with col_a:
    name_a = st.selectbox("Player A", player_names, index=0, key="player_a")
with col_b:
    default_b = min(1, len(player_names) - 1)
    name_b = st.selectbox("Player B", player_names, index=default_b, key="player_b")

if name_a == name_b:
    st.info("Select two different players for comparison.")
    st.stop()

mask_a = df["player_name"] == name_a
row_a = df.loc[mask_a].iloc[-1] if mask_a.any() else None

mask_b = df["player_name"] == name_b
row_b = df.loc[mask_b].iloc[-1] if mask_b.any() else None

if row_a is None or row_b is None:
    st.warning("Selected player(s) not found in rolling data.")
    st.stop()

has_pos = "position_group" in df.columns
if has_pos:
    positions = ["All"] + sorted(df["position_group"].dropna().unique().tolist())
else:
    positions = ["All"]
position = st.selectbox("Position filter for reference pool", positions)

pool = df if position == "All" else df.loc[df["position_group"] == position]

# Confidence warnings for selected players
for _label, row in [("Player A", row_a), ("Player B", row_b)]:
    assessment = assess_player_confidence(row)
    if assessment.is_low_confidence:
        display_confidence_warnings(assessment)

fig = plot_player_radar(row_a, row_b, pool)
st.plotly_chart(fig, use_container_width=True)

# ── Percentile comparison table ──────────────────────────────────────────────
st.subheader("Position-Relative Percentiles")

available_metrics = [
    m for m in RADAR_METRICS
    if m in pool.columns and m in row_a.index and m in row_b.index
]
if available_metrics:
    pct_rows = []
    for metric in available_metrics:
        pool_vals = pool[metric].dropna()
        if len(pool_vals) < 3:
            continue
        pct_a = float((pool_vals < row_a.get(metric, 0)).mean() * 100)
        pct_b = float((pool_vals < row_b.get(metric, 0)).mean() * 100)
        label = RADAR_LABELS.get(metric, metric)
        val_a = row_a.get(metric, 0)
        val_b = row_b.get(metric, 0)
        pct_rows.append({
            "Metric": label,
            f"{name_a}": f"{val_a:.2f}",
            f"{name_a} %ile": f"{pct_a:.0f}",
            f"{name_b}": f"{val_b:.2f}",
            f"{name_b} %ile": f"{pct_b:.0f}",
            "Diff %ile": f"{pct_a - pct_b:+.0f}",
        })

    if pct_rows:
        pct_df = pd.DataFrame(pct_rows)
        st.dataframe(pct_df, use_container_width=True, hide_index=True)

        # Highlight the better performer per metric
        better_a = sum(1 for r in pct_rows if float(r["Diff %ile"]) > 0)
        better_b = sum(1 for r in pct_rows if float(r["Diff %ile"]) < 0)
        ties = len(pct_rows) - better_a - better_b
        st.caption(
            f"Summary: {name_a} leads in {better_a} metrics, "
            f"{name_b} leads in {better_b}, {ties} tied."
        )
else:
    st.info("No overlapping metrics with sufficient data for percentile comparison.")

# ── Raw stats ────────────────────────────────────────────────────────────────
st.subheader("Raw Stats")
col1, col2 = st.columns(2)
with col1:
    st.dataframe(row_a.to_frame().T, use_container_width=True)
with col2:
    st.dataframe(row_b.to_frame().T, use_container_width=True)

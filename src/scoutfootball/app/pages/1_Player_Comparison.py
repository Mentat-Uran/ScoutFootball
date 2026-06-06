"""Dual-player comparison page with radar chart."""

from __future__ import annotations

import streamlit as st

from scoutfootball.app.data_loader import load_player_rolling
from scoutfootball.evaluation.confidence import (
    assess_player_confidence,
    display_confidence_warnings,
)
from scoutfootball.viz.radar import plot_player_radar

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

st.subheader("Raw Stats")
col1, col2 = st.columns(2)
with col1:
    st.dataframe(row_a.to_frame().T, use_container_width=True)
with col2:
    st.dataframe(row_b.to_frame().T, use_container_width=True)

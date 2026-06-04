"""Position-relative percentile bar chart page."""

from __future__ import annotations

import streamlit as st

from scoutlab.app.data_loader import load_player_rolling
from scoutlab.viz.percentiles import plot_percentile_bars

st.header("Position Percentiles")

df = load_player_rolling()

positions = sorted(df["position_group"].dropna().unique()) if "position_group" in df.columns else []
if not positions:
    st.warning("No position data available.")
    st.stop()

pos = st.selectbox("Position", positions)
pool = df.loc[df["position_group"] == pos]

player_names = (
    sorted(pool["player_name"].dropna().unique()) if "player_name" in pool.columns else []
)
if not player_names:
    st.warning("No players found for this position.")
    st.stop()

player_name = st.selectbox("Player", player_names)

mask = pool["player_name"] == player_name
row = pool.loc[mask].iloc[-1] if mask.any() else None
if row is None:
    st.warning("Player not found.")
    st.stop()

fig = plot_percentile_bars(row, pool)
st.plotly_chart(fig, use_container_width=True)

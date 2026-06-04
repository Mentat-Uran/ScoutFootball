"""Player and team trend chart page."""

from __future__ import annotations

import streamlit as st

from scoutlab.app.data_loader import load_player_rolling, load_team_rolling
from scoutlab.viz.trends import DEFAULT_TREND_METRICS, TREND_LABELS, plot_trend

st.header("Trends")

mode = st.radio("Entity type", ["Player", "Team"], horizontal=True)

if mode == "Player":
    df = load_player_rolling()
    name_col = "player_name"
else:
    df = load_team_rolling()
    name_col = "team_name"

entity_names = sorted(df[name_col].dropna().unique()) if name_col in df.columns else []
if not entity_names:
    st.warning("No data available.")
    st.stop()

entity = st.selectbox("Select entity", entity_names)

available_metrics = [m for m in DEFAULT_TREND_METRICS if m in df.columns]

if not available_metrics:
    st.warning("No trend metrics found in data.")
    st.stop()

metric_choice = st.selectbox(
    "Metric",
    available_metrics,
    format_func=lambda m: TREND_LABELS.get(m, m),
)

entity_df = df.loc[df[name_col] == entity].copy()
if entity_df.empty:
    st.warning("No data for selected entity.")
    st.stop()

fig = plot_trend(entity_df, metric_choice, entity_name=entity)
st.plotly_chart(fig, use_container_width=True)

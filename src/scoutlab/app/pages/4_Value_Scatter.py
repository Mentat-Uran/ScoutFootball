"""Market value vs performance scatter page."""

from __future__ import annotations

import streamlit as st

from scoutlab.app.data_loader import load_oof_predictions
from scoutlab.viz.scatter import plot_value_scatter

st.header("Value vs Performance")

oof = load_oof_predictions()
if oof.empty:
    st.warning("No OOF prediction data available.")
    st.stop()

fig = plot_value_scatter(oof)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Fairness Distribution")
if "fairness_label" in oof.columns:
    st.bar_chart(oof["fairness_label"].value_counts())

st.subheader("Summary Metrics")
if "residual_log" in oof.columns:
    col1, col2, col3 = st.columns(3)
    col1.metric("Mean Residual", f"{oof['residual_log'].mean():.3f}")
    col2.metric("MAE (log)", f"{oof['residual_log'].abs().mean():.3f}")
    col3.metric("Samples", len(oof))

"""ScoutLab Streamlit application entry point."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="ScoutLab", page_icon="⚽", layout="wide")

st.title("⚽ ScoutLab")
st.caption("Local-first football data research platform")

from scoutlab.app.data_loader import data_source_label  # noqa: E402

source = data_source_label()
st.sidebar.info(f"Data source: {source}")

pg = st.navigation(
    [
        st.Page(
            "scoutlab/app/pages/1_Player_Comparison.py",
            title="Player Comparison",
            icon="👥",
        ),
        st.Page(
            "scoutlab/app/pages/2_Position_Percentiles.py",
            title="Position Percentiles",
            icon="📊",
        ),
        st.Page(
            "scoutlab/app/pages/3_Trends.py",
            title="Trends",
            icon="📈",
        ),
        st.Page(
            "scoutlab/app/pages/4_Value_Scatter.py",
            title="Value vs Performance",
            icon="💰",
        ),
        st.Page(
            "scoutlab/app/pages/5_Score_Matrix.py",
            title="Score Matrix",
            icon="🎯",
        ),
        st.Page(
            "scoutlab/app/pages/6_Player_Rankings.py",
            title="Player Rankings",
            icon="🏆",
        ),
        st.Page(
            "scoutlab/app/pages/7_Value_Deviation.py",
            title="Value Deviation",
            icon="💎",
        ),
        st.Page(
            "scoutlab/app/pages/8_Match_Prediction.py",
            title="Match Prediction",
            icon="⚽",
        ),
    ]
)
pg.run()

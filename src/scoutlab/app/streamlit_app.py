"""ScoutLab Streamlit application entry point."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

st.set_page_config(page_title="ScoutLab", page_icon="⚽", layout="wide")

st.title("⚽ ScoutLab")
st.caption("Local-first football data research platform")

from scoutlab.app.data_loader import data_source_label  # noqa: E402

APP_DIR = Path(__file__).resolve().parent

source = data_source_label()
st.sidebar.info(f"Data source: {source}")

pg = st.navigation(
    [
        st.Page(
            APP_DIR / "pages/1_Player_Comparison.py",
            title="Player Comparison",
            icon="👥",
        ),
        st.Page(
            APP_DIR / "pages/2_Position_Percentiles.py",
            title="Position Percentiles",
            icon="📊",
        ),
        st.Page(
            APP_DIR / "pages/3_Trends.py",
            title="Trends",
            icon="📈",
        ),
        st.Page(
            APP_DIR / "pages/4_Value_Scatter.py",
            title="Value vs Performance",
            icon="💰",
        ),
        st.Page(
            APP_DIR / "pages/5_Score_Matrix.py",
            title="Score Matrix",
            icon="🎯",
        ),
        st.Page(
            APP_DIR / "pages/6_Player_Rankings.py",
            title="Player Rankings",
            icon="🏆",
        ),
        st.Page(
            APP_DIR / "pages/7_Value_Deviation.py",
            title="Value Deviation",
            icon="💎",
        ),
        st.Page(
            APP_DIR / "pages/8_Match_Prediction.py",
            title="Match Prediction",
            icon="⚽",
        ),
    ]
)
pg.run()

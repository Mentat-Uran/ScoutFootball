"""ScoutFootball Streamlit application entry point."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

st.set_page_config(page_title="ScoutFootball", page_icon="⚽", layout="wide")

st.title("⚽ ScoutFootball for World Cup")
st.caption("2026 美加墨世界杯分析工具箱")

from scoutfootball.app.data_loader import data_source_label  # noqa: E402

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
        st.Page(
            APP_DIR / "pages/9_World_Cup_Schedule.py",
            title="World Cup Schedule",
            icon="🌍",
        ),
        st.Page(
            APP_DIR / "pages/10_World_Cup_Squads.py",
            title="World Cup Squads",
            icon="🇺🇳",
        ),
        st.Page(
            APP_DIR / "pages/11_World_Cup_Compare.py",
            title="World Cup Compare",
            icon="⚔️",
        ),
        st.Page(
            APP_DIR / "pages/12_World_Cup_Probability.py",
            title="World Cup Probability",
            icon="🎲",
        ),
    ]
)
pg.run()

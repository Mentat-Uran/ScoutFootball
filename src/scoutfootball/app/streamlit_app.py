"""ScoutFootball Streamlit application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

st.set_page_config(
    page_title="ScoutFootball — Local-First Football Analytics & Player Research",
    page_icon="⚽",
    layout="wide",
)

st.title("⚽ ScoutFootball — Local-First Football Analytics & Player Research")
st.caption("本地优先的足球分析与球员研究工具箱")

from scoutfootball.app.data_loader import data_source_label  # noqa: E402

APP_DIR = Path(__file__).resolve().parent

source = data_source_label()
st.sidebar.info(f"Data source: {source}")

pg = st.navigation(
    [
        st.Page(
            APP_DIR / "pages/0_Overview.py",
            title="Overview",
            icon="🧭",
        ),
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
        st.Page(
            APP_DIR / "pages/13_Scouting_Queue.py",
            title="Scouting Queue",
            icon="🗂️",
        ),
        st.Page(
            APP_DIR / "pages/14_Action_Value.py",
            title="Action Value",
            icon="🧪",
        ),
    ]
)
pg.run()

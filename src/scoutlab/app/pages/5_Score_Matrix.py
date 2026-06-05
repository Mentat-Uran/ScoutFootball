"""Score probability matrix page."""

from __future__ import annotations

import streamlit as st

from scoutlab.app.data_loader import load_score_prediction, load_team_match
from scoutlab.viz.score_matrix import plot_score_matrix

st.header("Score Probability Matrix")

team_df = load_team_match()
team_names = (
    sorted(team_df["team_name"].dropna().unique()) if "team_name" in team_df.columns else []
)

if len(team_names) < 2:
    st.warning("Need at least two teams for match prediction.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    home = st.selectbox("Home Team", team_names, index=0, key="home_team")
with col2:
    away_options = [t for t in team_names if t != home]
    away = st.selectbox("Away Team", away_options, index=0, key="away_team")

prediction = load_score_prediction()

summary_dict = {
    "home_win": prediction.summary.home_win,
    "draw": prediction.summary.draw,
    "away_win": prediction.summary.away_win,
    "over_2_5": prediction.summary.over_2_5,
    "under_2_5": prediction.summary.under_2_5,
    "btts_yes": prediction.summary.btts_yes,
    "btts_no": prediction.summary.btts_no,
}

fig = plot_score_matrix(
    prediction.score_matrix,
    home_team=home,
    away_team=away,
    summary=summary_dict,
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Match Probabilities")
c1, c2, c3 = st.columns(3)
c1.metric("Home Win", f"{prediction.summary.home_win:.1%}")
c2.metric("Draw", f"{prediction.summary.draw:.1%}")
c3.metric("Away Win", f"{prediction.summary.away_win:.1%}")

c4, c5, c6 = st.columns(3)
c4.metric("Over 2.5", f"{prediction.summary.over_2_5:.1%}")
c5.metric("Under 2.5", f"{prediction.summary.under_2_5:.1%}")
c6.metric("BTTS Yes", f"{prediction.summary.btts_yes:.1%}")

eg_home = prediction.home_lambda
eg_away = prediction.away_lambda
st.caption(f"Expected Goals — Home: {eg_home:.2f}  Away: {eg_away:.2f}")

# Model confidence note
n_teams = len(team_names)
if n_teams < 20:
    st.warning(
        f"模型置信度低：仅覆盖 {n_teams} 支球队，预测结果仅供参考。"
    )
else:
    st.info("比分概率基于独立 Poisson 模型，实际比赛受伤病、战术、天气等因素影响，预测仅供参考。")

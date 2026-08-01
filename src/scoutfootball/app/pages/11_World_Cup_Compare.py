"""World Cup 2026 Team Comparison: head-to-head squad analysis."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scoutfootball.app.data_loader import load_player_ratings
from scoutfootball.worldcup.data import (
    BIG5_LEAGUES,
    GROUPS,
    enrich_squad_with_ratings,
    get_squad,
)

st.header("世界杯球队实力对比")

st.caption(
    "选择两支国家队，对比双方阵容中有评分球员的分布、位置覆盖和关键球员。"
)

# ── Load ratings ──────────────────────────────────────────────────────────
ratings_df = load_player_ratings()

# ── Team selectors ────────────────────────────────────────────────────────
all_teams = []
for teams in GROUPS.values():
    all_teams.extend(teams)

col1, col2 = st.columns(2)
with col1:
    team_a = st.selectbox(
        "球队 A",
        all_teams,
        index=all_teams.index("Argentina") if "Argentina" in all_teams else 0,
        key="wc_compare_a",
    )
with col2:
    team_b = st.selectbox(
        "球队 B",
        all_teams,
        index=all_teams.index("France") if "France" in all_teams else 1,
        key="wc_compare_b",
    )

# ── Enrich squads ─────────────────────────────────────────────────────────
squad_a = enrich_squad_with_ratings(get_squad(team_a), ratings_df)
squad_b = enrich_squad_with_ratings(get_squad(team_b), ratings_df)

rated_a = [p for p in squad_a if p.has_rating]
rated_b = [p for p in squad_b if p.has_rating]

# ── Summary comparison ────────────────────────────────────────────────────
st.subheader(f"{team_a} vs {team_b}")

def _team_summary(team_name: str, squad, rated):
    total = len(squad)
    n_rated = len(rated)
    n_big5 = sum(1 for p in squad if p.club_league in BIG5_LEAGUES)
    avg = sum(p.rating for p in rated) / n_rated if n_rated > 0 else 0
    max_r = max((p.rating for p in rated), default=0)
    return {
        "球队": team_name,
        "名单人数": total,
        "有评分": n_rated,
        "五大联赛": n_big5,
        "平均评分": f"{avg:.2f}" if n_rated > 0 else "—",
        "最高评分": f"{max_r:.2f}" if n_rated > 0 else "—",
    }

summary_df = pd.DataFrame([
    _team_summary(team_a, squad_a, rated_a),
    _team_summary(team_b, squad_b, rated_b),
])
st.dataframe(summary_df, use_container_width=True, hide_index=True)

# ── Position coverage comparison ──────────────────────────────────────────
st.divider()
st.subheader("位置覆盖对比")

positions = ["GK", "CB", "FB", "DM", "CM", "AM", "W", "ST"]
pos_rows = []
for pos in positions:
    a_players = [p for p in squad_a if p.position == pos]
    b_players = [p for p in squad_b if p.position == pos]
    a_rated = [p for p in a_players if p.has_rating]
    b_rated = [p for p in b_players if p.has_rating]
    a_avg = sum(p.rating for p in a_rated) / len(a_rated) if a_rated else 0
    b_avg = sum(p.rating for p in b_rated) / len(b_rated) if b_rated else 0
    pos_rows.append({
        "位置": pos,
        f"{team_a} 人数": len(a_players),
        f"{team_a} 有评分": len(a_rated),
        f"{team_a} 均分": f"{a_avg:.2f}" if a_rated else "—",
        f"{team_b} 人数": len(b_players),
        f"{team_b} 有评分": len(b_rated),
        f"{team_b} 均分": f"{b_avg:.2f}" if b_rated else "—",
    })

pos_df = pd.DataFrame(pos_rows)
st.dataframe(pos_df, use_container_width=True, hide_index=True)

# ── Rating distribution comparison ────────────────────────────────────────
if rated_a or rated_b:
    st.divider()
    st.subheader("评分分布对比")

    chart_rows = []
    for p in rated_a:
        chart_rows.append({"球队": team_a, "球员": p.name, "评分": p.rating, "位置": p.position})
    for p in rated_b:
        chart_rows.append({"球队": team_b, "球员": p.name, "评分": p.rating, "位置": p.position})

    chart_df = pd.DataFrame(chart_rows)
    if not chart_df.empty:
        st.bar_chart(chart_df, x="球员", y="评分", color="球队")

# ── Key players comparison ────────────────────────────────────────────────
if rated_a or rated_b:
    st.divider()
    st.subheader("关键球员对比")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown(f"**{team_a}**")
        if rated_a:
            top_a = sorted(rated_a, key=lambda p: p.rating or 0, reverse=True)[:5]
            for p in top_a:
                st.markdown(
                    f"- **{p.name}** ({p.position}) — {p.rating:.2f} | {p.club}"
                )
        else:
            st.info("无评分数据")

    with col_b:
        st.markdown(f"**{team_b}**")
        if rated_b:
            top_b = sorted(rated_b, key=lambda p: p.rating or 0, reverse=True)[:5]
            for p in top_b:
                st.markdown(
                    f"- **{p.name}** ({p.position}) — {p.rating:.2f} | {p.club}"
                )
        else:
            st.info("无评分数据")

# ── Confidence warning ────────────────────────────────────────────────────
low_coverage = []
for team_name, squad, rated in [(team_a, squad_a, rated_a), (team_b, squad_b, rated_b)]:
    if len(squad) > 0 and len(rated) / len(squad) < 0.5:
        low_coverage.append(team_name)

if low_coverage:
    st.warning(
        f"⚠️ {', '.join(low_coverage)} 评分覆盖率低于 50%，"
        f"对比结论置信度较低。"
    )

"""World Cup 2026 Squad Ratings: view each team's squad with system ratings."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from scoutfootball.app.data_loader import load_player_ratings
from scoutfootball.worldcup.data import (
    BIG5_LEAGUES,
    GROUPS,
    enrich_squad_with_ratings,
    get_squad,
)

st.header("世界杯球队名单 & 评分")

st.caption(
    "查看各国家队大名单球员在 25-26 赛季的评分。"
    "五大联赛球员评分置信度较高，非五大联赛球员标注为'无评分数据'。"
)

# ── Load ratings ──────────────────────────────────────────────────────────
ratings_df = load_player_ratings()

# ── Team selector ─────────────────────────────────────────────────────────
all_teams = []
for teams in GROUPS.values():
    all_teams.extend(teams)

with st.sidebar:
    st.subheader("球队选择")
    selected_team = st.selectbox(
        "国家队",
        all_teams,
        index=all_teams.index("Argentina") if "Argentina" in all_teams else 0,
        key="wc_squad_team",
    )

# ── Get and enrich squad ──────────────────────────────────────────────────
squad = get_squad(selected_team)
squad = enrich_squad_with_ratings(squad, ratings_df)

# ── Group info ────────────────────────────────────────────────────────────
team_group = None
for letter, teams in GROUPS.items():
    if selected_team in teams:
        team_group = letter
        break

st.subheader(f"{selected_team} — {team_group} 组")

# ── Squad summary ─────────────────────────────────────────────────────────
rated_count = sum(1 for p in squad if p.has_rating)
total_count = len(squad)
big5_count = sum(
    1 for p in squad if p.club_league in BIG5_LEAGUES
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("名单人数", f"{total_count}")
with col2:
    st.metric("有评分", f"{rated_count}")
with col3:
    st.metric("五大联赛球员", f"{big5_count}")
with col4:
    if rated_count > 0:
        avg_rating = sum(p.rating for p in squad if p.has_rating) / rated_count
        st.metric("平均评分", f"{avg_rating:.2f}")
    else:
        st.metric("平均评分", "—")

# ── Position coverage ─────────────────────────────────────────────────────
if squad:
    st.divider()
    st.subheader("位置覆盖度")

    positions = ["GK", "CB", "FB", "DM", "CM", "AM", "W", "ST"]
    pos_data = []
    for pos in positions:
        pos_players = [p for p in squad if p.position == pos]
        pos_rated = [p for p in pos_players if p.has_rating]
        pos_data.append({
            "位置": pos,
            "人数": len(pos_players),
            "有评分": len(pos_rated),
            "覆盖率": (
                f"{len(pos_rated) / len(pos_players) * 100:.0f}%"
                if pos_players else "—"
            ),
        })

    pos_df = pd.DataFrame(pos_data)
    st.dataframe(pos_df, use_container_width=True, hide_index=True)

# ── Squad table ───────────────────────────────────────────────────────────
if squad:
    st.divider()
    st.subheader("球员名单")

    rows = []
    for p in squad:
        rating_str = f"{p.rating:.2f}" if p.has_rating else "—"
        confidence_str = {
            "high": "高",
            "medium": "中",
            "low": "低",
            "none": "无数据",
        }.get(p.rating_confidence, "无数据")
        rows.append({
            "球员": p.name,
            "位置": p.position,
            "俱乐部": p.club,
            "联赛": p.club_league,
            "评分": rating_str,
            "置信度": confidence_str,
        })

    squad_df = pd.DataFrame(rows)
    st.dataframe(squad_df, use_container_width=True, hide_index=True)

# ── Rating distribution chart ─────────────────────────────────────────────
rated_players = [p for p in squad if p.has_rating]
if rated_players:
    st.divider()
    st.subheader("评分分布")

    chart_data = pd.DataFrame({
        "球员": [p.name for p in rated_players],
        "评分": [p.rating for p in rated_players],
        "位置": [p.position for p in rated_players],
    }).sort_values("评分", ascending=False)

    st.bar_chart(chart_data, x="球员", y="评分", color="位置")

# ── Warning for low coverage ──────────────────────────────────────────────
if total_count > 0 and rated_count / total_count < 0.5:
    st.warning(
        f"⚠️ 该队仅有 {rated_count}/{total_count} 名球员有评分数据，"
        f"结论置信度较低。非五大联赛球员数据暂未覆盖。"
    )
elif total_count == 0:
    st.info(
        "📋 该队大名单尚未录入。官方 26 人名单公布后将更新。"
    )

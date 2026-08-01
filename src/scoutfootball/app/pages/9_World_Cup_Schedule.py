"""World Cup 2026 Schedule: groups, fixtures, and venues."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scoutfootball.worldcup.data import (
    GROUPS,
    HOSTS,
    generate_group_stage_matches,
)

st.header("2026 美加墨世界杯赛程")

st.caption(
    "2026年6月11日 - 7月19日 | 美国 · 加拿大 · 墨西哥 | "
    "48支球队 · 12个小组 · 104场比赛"
)

# ── Group overview ────────────────────────────────────────────────────────
st.subheader("分组一览")

group_data = []
for letter, teams in GROUPS.items():
    for i, team in enumerate(teams):
        host_marker = " (东道主)" if team in HOSTS else ""
        group_data.append({
            "小组": letter,
            "球队": team + host_marker,
            "档位": i + 1,
        })

group_df = pd.DataFrame(group_data)

# Display as wide table with groups as columns
cols = st.columns(4)
group_letters = sorted(GROUPS.keys())
for idx, col in enumerate(cols):
    with col:
        for g_idx in range(idx, len(group_letters), 4):
            letter = group_letters[g_idx]
            teams = GROUPS[letter]
            host_info = " (东道主)" if any(t in HOSTS for t in teams) else ""
            st.markdown(f"**{letter} 组{host_info}**")
            for i, team in enumerate(teams):
                host_marker = " 🏠" if team in HOSTS else ""
                st.markdown(f"{i + 1}. {team}{host_marker}")
            st.markdown("")

# ── Group stage fixtures ──────────────────────────────────────────────────
st.divider()
st.subheader("小组赛赛程")

matches = generate_group_stage_matches()

# Filter controls
with st.sidebar:
    st.subheader("赛程筛选")
    selected_group = st.selectbox(
        "小组",
        ["All"] + list(GROUPS.keys()),
        index=0,
        key="wc_schedule_group",
    )
    selected_matchday = st.selectbox(
        "比赛日",
        ["All", "1", "2", "3"],
        index=0,
        key="wc_schedule_matchday",
    )

filtered = matches
if selected_group != "All":
    filtered = [m for m in filtered if m.group == selected_group]
if selected_matchday != "All":
    filtered = [m for m in filtered if m.matchday == int(selected_matchday)]

# Display matches
match_rows = []
for m in filtered:
    match_rows.append({
        "日期": m.date,
        "时间(ET)": m.time_et,
        "小组": m.group or "—",
        "主队": m.home,
        "客队": m.away,
        "场馆": m.venue,
        "城市": m.city,
    })

if match_rows:
    match_df = pd.DataFrame(match_rows)
    st.dataframe(match_df, use_container_width=True, hide_index=True)
    st.caption(f"共 {len(match_rows)} 场小组赛")
else:
    st.info("无匹配赛程。")

# ── Tournament info ───────────────────────────────────────────────────────
st.divider()
st.subheader("赛制说明")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**小组赛**")
    st.markdown("12 组 x 4 队，每组前 2 名 + 8 个最佳第 3 名晋级")
with col2:
    st.markdown("**淘汰赛**")
    st.markdown("32 强 → 16 强 → 8 强 → 半决赛 → 决赛")
with col3:
    st.markdown("**总计**")
    st.markdown("104 场比赛，7 月 19 日决赛")

st.info(
    "⚠️ 赛程日期和场馆为基于官方赛制的近似安排，具体开球时间以 FIFA 官方公布为准。"
)

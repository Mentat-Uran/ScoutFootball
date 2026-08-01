"""World Cup 2026 Group Stage Probability: estimated advancement odds."""

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
    GROUPS,
    compute_group_predictions,
    compute_team_strengths,
    enrich_squads_with_ratings,
)

st.header("世界杯小组出线概率")

st.caption(
    "基于球队阵容评分均值和 Opta 公开先验的娱乐性估算，"
    "置信度有限，仅供参考。评分数据来源：FBref/Understat。"
)

# ── Load ratings ──────────────────────────────────────────────────────────
ratings_df = load_player_ratings()

# ── Compute team strength scores ──────────────────────────────────────────
@st.cache_data
def compute_strengths_cached() -> dict[str, float]:
    """Compute a strength score for each World Cup team using shared logic."""
    enriched = enrich_squads_with_ratings(ratings_df)
    return compute_team_strengths(enriched_squads=enriched)


strengths = compute_strengths_cached()

# ── Group advancement probability ─────────────────────────────────────────
st.subheader("各小组出线概率")

st.markdown(
    "每组前 2 名直接晋级，8 个最佳第 3 名也可晋级（共 32 队进淘汰赛）。"
    "以下概率基于简化模型估算。"
)


# Use shared prediction logic
group_predictions = compute_group_predictions(strengths)


def _prediction_to_dataframe(group_pred: dict) -> pd.DataFrame:
    """Convert a group prediction dict to a display DataFrame."""
    rows = []
    for t in group_pred["teams"]:
        rows.append({
            "球队": t["team"],
            "实力评分": f"{t['strength']:.3f}",
            "第1名概率": f"{t['p1st'] * 100:.1f}%",
            "第2名概率": f"{t['p2nd'] * 100:.1f}%",
            "第3名概率": f"{t['p3rd'] * 100:.1f}%",
            "出线概率": f"{t['p_advance'] * 100:.1f}%",
        })
    return pd.DataFrame(rows)


# Display each group
group_letters = sorted(GROUPS.keys())
cols = st.columns(3)

for idx, letter in enumerate(group_letters):
    gp = next((g for g in group_predictions if g["group"] == letter), None)
    if not gp:
        continue
    with cols[idx % 3]:
        st.markdown(f"**{letter} 组**")
        prob_df = _prediction_to_dataframe(gp)
        st.dataframe(prob_df, use_container_width=True, hide_index=True)
        st.markdown("")

# ── Overall strength ranking ──────────────────────────────────────────────
st.divider()
st.subheader("48 队实力排名")

ranked_teams = sorted(strengths.items(), key=lambda x: x[1], reverse=True)
rank_rows = []
for rank, (team, strength) in enumerate(ranked_teams, 1):
    group = None
    for letter, teams in GROUPS.items():
        if team in teams:
            group = letter
            break
    rank_rows.append({
        "排名": rank,
        "球队": team,
        "小组": group or "—",
        "实力评分": f"{strength:.3f}",
    })

rank_df = pd.DataFrame(rank_rows)
st.dataframe(rank_df, use_container_width=True, hide_index=True)

# ── Best 3rd-place teams ──────────────────────────────────────────────────
st.divider()
st.subheader("最佳第 3 名预测")

st.markdown(
    "12 个小组的第 3 名中，8 个成绩最好的晋级淘汰赛。"
    "以下是基于实力评分的预测。"
)

third_place_rows = []
for gp in group_predictions:
    teams = gp["teams"]
    if len(teams) >= 3:
        third = teams[2]
        third_place_rows.append({
            "小组": gp["group"],
            "预计第3名": third["team"],
            "实力评分": f"{third['strength']:.3f}",
        })

third_df = pd.DataFrame(third_place_rows)
third_df = third_df.sort_values("实力评分", ascending=False)
st.dataframe(third_df, use_container_width=True, hide_index=True)

# ── Disclaimer ────────────────────────────────────────────────────────────
st.warning(
    "⚠️ 以上概率为基于简化模型的娱乐性估算，不代表真实比赛结果预测。"
    "模型仅考虑了阵容评分均值和公开先验数据，未包含伤病、状态、战术等因素。"
    "非五大联赛球队的数据覆盖不足，概率可能严重偏低。"
    "评分数据来源：FBref/Understat via ScoutFootball optimizer。"
)

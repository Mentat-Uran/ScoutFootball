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
    WIN_PROBABILITY,
    enrich_squad_with_ratings,
    get_squad,
)

st.header("世界杯小组出线概率")

st.caption(
    "基于球队阵容评分均值和 Opta 公开预测的娱乐性估算，"
    "置信度有限，仅供参考。"
)

# ── Load ratings ──────────────────────────────────────────────────────────
ratings_df = load_player_ratings()

# ── Compute team strength scores ──────────────────────────────────────────
@st.cache_data
def compute_team_strengths() -> dict[str, float]:
    """Compute a strength score for each World Cup team.

    Combines:
    1. Average rating of squad players with system ratings (weight: 0.5)
    2. Opta win probability if available (weight: 0.3)
    3. Number of Big5 players as a proxy (weight: 0.2)

    Returns a dict of team -> strength score (0-1).
    """
    strengths: dict[str, float] = {}

    for team_name in [t for ts in GROUPS.values() for t in ts]:
        squad = enrich_squad_with_ratings(get_squad(team_name), ratings_df)
        rated = [p for p in squad if p.has_rating]

        # Component 1: average rating (normalized to 0-1)
        if rated:
            avg_rating = sum(p.rating for p in rated) / len(rated)
            # Ratings are typically 0.3-0.8, normalize to 0-1
            rating_score = min(max((avg_rating - 0.3) / 0.5, 0), 1)
        else:
            rating_score = 0.2  # baseline for teams without data

        # Component 2: Opta win probability (already 0-1)
        opta_score = WIN_PROBABILITY.get(team_name, 0.01)
        # Normalize: top team ~0.16 -> 1.0
        opta_normalized = min(opta_score / 0.16, 1.0)

        # Component 3: Big5 player count (proxy for squad quality)
        big5_count = sum(1 for p in squad if p.club_league in {
            "Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1",
        })
        # 10+ Big5 players = strong squad
        big5_score = min(big5_count / 10, 1.0)

        # Weighted combination
        strength = (
            0.5 * rating_score
            + 0.3 * opta_normalized
            + 0.2 * big5_score
        )
        strengths[team_name] = strength

    return strengths


strengths = compute_team_strengths()

# ── Group advancement probability ─────────────────────────────────────────
st.subheader("各小组出线概率")

st.markdown(
    "每组前 2 名直接晋级，8 个最佳第 3 名也可晋级（共 32 队进淘汰赛）。"
    "以下概率基于简化模型估算。"
)


def estimate_group_probabilities(
    group_teams: list[str], team_strengths: dict[str, float],
) -> pd.DataFrame:
    """Estimate advancement probability for each team in a group.

    Uses a simple strength-ratio model:
    - P(1st) proportional to strength
    - P(2nd) proportional to strength among remaining
    - P(3rd) = 1 - P(1st) - P(2nd)

    This is a rough approximation; real models would use Monte Carlo
    simulation with match-level predictions.
    """
    team_strength_pairs = [
        (t, team_strengths.get(t, 0.2)) for t in group_teams
    ]
    total = sum(s for _, s in team_strength_pairs)

    results = []
    for team, strength in team_strength_pairs:
        p1 = strength / total if total > 0 else 0.25
        # P(2nd): proportional to strength among non-1st teams
        remaining_strength = total - strength
        p2 = (
            (remaining_strength / total)
            * (strength / remaining_strength)
            if remaining_strength > 0
            else 0
        )
        p3 = 1 - p1 - p2
        results.append({
            "球队": team,
            "实力评分": f"{strength:.3f}",
            "第1名概率": f"{p1 * 100:.1f}%",
            "第2名概率": f"{p2 * 100:.1f}%",
            "第3名概率": f"{max(p3, 0) * 100:.1f}%",
            "出线概率": f"{min((p1 + p2) * 100, 100):.1f}%",
        })

    return pd.DataFrame(results)


# Display each group
group_letters = sorted(GROUPS.keys())
cols = st.columns(3)

for idx, letter in enumerate(group_letters):
    teams = GROUPS[letter]
    with cols[idx % 3]:
        st.markdown(f"**{letter} 组**")
        prob_df = estimate_group_probabilities(teams, strengths)
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
for letter in group_letters:
    teams = GROUPS[letter]
    team_strength_pairs = [(t, strengths.get(t, 0.2)) for t in teams]
    team_strength_pairs.sort(key=lambda x: x[1], reverse=True)
    if len(team_strength_pairs) >= 3:
        third_team, third_strength = team_strength_pairs[2]
        third_place_rows.append({
            "小组": letter,
            "预计第3名": third_team,
            "实力评分": f"{third_strength:.3f}",
        })

third_df = pd.DataFrame(third_place_rows)
third_df = third_df.sort_values("实力评分", ascending=False)
st.dataframe(third_df, use_container_width=True, hide_index=True)

# ── Disclaimer ────────────────────────────────────────────────────────────
st.warning(
    "⚠️ 以上概率为基于简化模型的娱乐性估算，不代表真实比赛结果预测。"
    "模型仅考虑了阵容评分均值和公开预测数据，未包含伤病、状态、战术等因素。"
    "非五大联赛球队的数据覆盖不足，概率可能严重偏低。"
)

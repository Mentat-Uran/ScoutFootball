"""Player Rankings page: position-specific pizza chart, Top 20, and detail card."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from scoutfootball.app.data_loader import load_player_rolling
from scoutfootball.evaluation.coverage_confidence import display_confidence_badge
from scoutfootball.evaluation.position_metrics import (
    POSITION_GROUP_MAP,
    compute_player_position_metrics,
)
from scoutfootball.viz.pitch import plot_pizza_chart

st.header("球员雷达/排名")

# ── Data loading ──────────────────────────────────────────────────────────
df = load_player_rolling()

if df.empty:
    st.warning("无球员数据可用。")
    st.stop()

# ── Resolve position column ───────────────────────────────────────────────
pos_col = "position_group" if "position_group" in df.columns else None
if pos_col is None:
    st.warning("数据中缺少 position_group 列。")
    st.stop()

raw_positions = sorted(df[pos_col].dropna().unique().tolist())
standard_positions = ["GK", "CB", "FB", "DM", "CM", "AM", "W", "ST"]
available_positions = [
    p
    for p in standard_positions
    if p in raw_positions or POSITION_GROUP_MAP.get(p) in raw_positions
]
if not available_positions:
    available_positions = raw_positions[:1] if raw_positions else []

# ── Sidebar controls ──────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("筛选条件")

    position = st.selectbox(
        "位置",
        ["All"] + available_positions,
        index=0,
        key="rankings_position",
    )

    view_mode = st.radio(
        "榜单模式",
        ["位置内榜单", "跨位置总榜"],
        index=0,
        key="rankings_view_mode",
    )

    # Season selector
    season_col = "season_id" if "season_id" in df.columns else None
    selected_season: str | None = None
    if season_col:
        seasons = sorted(
            df[season_col].dropna().unique().tolist(),
            reverse=True,
        )
        if seasons:
            selected_season = st.selectbox(
                "赛季",
                ["All"] + seasons,
                index=0,
                key="rankings_season",
            )

# ── Filter data ───────────────────────────────────────────────────────────
pool = df.copy()

if position != "All":
    # Map standard position back to raw position_group values
    reverse_map: dict[str, list[str]] = {}
    for raw, std in POSITION_GROUP_MAP.items():
        reverse_map.setdefault(std, []).append(raw)
    raw_vals = reverse_map.get(position, [position])
    pool = pool[pool[pos_col].isin(raw_vals)]

if selected_season and selected_season != "All" and season_col:
    pool = pool[pool[season_col] == selected_season]

if pool.empty:
    st.warning("当前筛选条件下无球员数据。")
    st.stop()

# ── Compute per-player aggregates ─────────────────────────────────────────
name_col = "player_name" if "player_name" in pool.columns else None
if name_col is None:
    st.warning("数据中缺少 player_name 列。")
    st.stop()

# Aggregate: take the last row per player (most recent)
agg_df = pool.groupby(name_col, sort=False).last().reset_index()

# ── Compute rating / ranking ──────────────────────────────────────────────
rating_col: str | None = None
if "optimized_score" in agg_df.columns:
    rating_col = "optimized_score"
elif "goals_p90_shrunk_3" in agg_df.columns and "assists_p90_shrunk_3" in agg_df.columns:
    # Fallback: simple composite from available shrunk p90 stats
    stat_cols = [c for c in agg_df.columns if c.endswith("_p90_shrunk_3")]
    if stat_cols:
        composite = (
            agg_df[stat_cols]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0)
            .mean(axis=1)
        )
        agg_df["_composite_rating"] = composite
        rating_col = "_composite_rating"

if rating_col is None:
    # Last resort: use minutes_played as a proxy for availability
    if "minutes_played" in agg_df.columns:
        agg_df["_composite_rating"] = pd.to_numeric(
            agg_df["minutes_played"], errors="coerce",
        ).fillna(0)
        rating_col = "_composite_rating"
    else:
        st.warning("无法计算评分，缺少相关指标列。")
        st.stop()

agg_df["_rating_numeric"] = pd.to_numeric(
    agg_df[rating_col], errors="coerce",
).fillna(0)

# ── Position vs cross-position ranking ────────────────────────────────────
ranked = agg_df.sort_values("_rating_numeric", ascending=False).reset_index(drop=True)
ranked["rank"] = range(1, len(ranked) + 1)
ranked["percentile"] = ranked["_rating_numeric"].rank(pct=True) * 100

top_n = 20
top_df = ranked.head(top_n)

# ── Display ranking table ─────────────────────────────────────────────────
display_cols = ["rank", name_col]
if "team_name" in top_df.columns:
    display_cols.append("team_name")
if pos_col in top_df.columns:
    display_cols.append(pos_col)
display_cols.append("_rating_numeric")

rename_map = {
    "_rating_numeric": "评分",
    name_col: "球员",
    "team_name": "球队",
    pos_col: "位置",
    "rank": "排名",
}
show_df = top_df[display_cols].rename(columns=rename_map)
pos_label = f" — {position}" if position != "All" else ""
st.subheader(f"Top {min(top_n, len(ranked))} 排名{pos_label}")
st.dataframe(show_df, use_container_width=True, hide_index=True)

# ── Player detail card ────────────────────────────────────────────────────
st.divider()
st.subheader("球员详情")

player_options = ranked[name_col].tolist()
selected_player = st.selectbox(
    "选择球员查看详情",
    player_options,
    index=0,
    key="rankings_player_detail",
)

if not selected_player:
    st.stop()

player_row = ranked[ranked[name_col] == selected_player].iloc[0]

# Determine position for metrics
player_pos_raw = str(player_row.get(pos_col, ""))
player_pos = POSITION_GROUP_MAP.get(player_pos_raw, player_pos_raw)

# ── Player info card ──────────────────────────────────────────────────────
info_col1, info_col2, info_col3 = st.columns(3)
with info_col1:
    st.markdown(f"**{selected_player}**")
    team_val = player_row.get("team_name", "—")
    st.caption(f"球队: {team_val}")
with info_col2:
    st.caption(f"位置: {player_pos_raw}")
    rating_val = player_row.get("_rating_numeric", 0)
    if isinstance(rating_val, (int, float)):
        st.caption(f"评分: {rating_val:.2f}")
    else:
        st.caption(f"评分: {rating_val}")
with info_col3:
    rank_val = player_row.get("rank", "—")
    pct_val = player_row.get("percentile", 0)
    st.caption(f"排名: #{rank_val}")
    st.caption(f"百分位: {pct_val:.1f}%")

# ── Confidence badge ──────────────────────────────────────────────────────
league_col = "league" if "league" in player_row.index else "competition_id"
if league_col in player_row.index and season_col and season_col in player_row.index:
    from scoutfootball.evaluation.coverage_confidence import assess_league_season

    league_val = str(player_row.get(league_col, ""))
    season_val = str(player_row.get(season_col, ""))
    # Simplified: assume high confidence for demo;
    # real usage would check coverage data
    assessment = assess_league_season(
        league=league_val,
        season=season_val,
        target_teams=20,
        rated_teams=18,
        matched_teams=18,
    )
    display_confidence_badge(assessment.confidence_level)

# ── Pizza chart ───────────────────────────────────────────────────────────
position_pool = pool.copy()
if position == "All":
    # Filter pool to same position as selected player
    reverse_map2: dict[str, list[str]] = {}
    for raw, std in POSITION_GROUP_MAP.items():
        reverse_map2.setdefault(std, []).append(raw)
    raw_vals2 = reverse_map2.get(player_pos, [player_pos_raw])
    position_pool = pool[pool[pos_col].isin(raw_vals2)]

# Get the latest row from the original pool for this player
player_orig = pool[pool[name_col] == selected_player]
player_orig_row = player_orig.iloc[-1] if not player_orig.empty else player_row

metrics = compute_player_position_metrics(
    player_orig_row,
    position_pool,
    position=player_pos,
)

# Build percentiles dict for pizza chart
percentiles = {d.label: d.percentile for d in metrics.dimensions}

if percentiles:
    fig = plot_pizza_chart(
        percentiles,
        player_name=selected_player,
        position=player_pos,
    )
    st.pyplot(fig)
else:
    st.info("无可用位置维度数据，无法生成雷达图。")

# ── Key stats ─────────────────────────────────────────────────────────────
st.subheader("关键数据")
stat_items = []
for col, label in [
    ("goals", "进球"),
    ("assists", "助攻"),
    ("npxg", "NPxG"),
    ("xa", "xA"),
    ("minutes_played", "出场时间"),
    ("shots", "射门"),
    ("tackles", "抢断"),
    ("passes", "传球"),
]:
    if col in player_orig_row.index:
        val = player_orig_row[col]
        stat_items.append((label, val))

if stat_items:
    cols = st.columns(min(len(stat_items), 4))
    for i, (label, val) in enumerate(stat_items):
        with cols[i % len(cols)]:
            display_val = f"{val:.2f}" if isinstance(val, float) else str(val)
            st.metric(label, display_val)

# ── Missing dimension flags ───────────────────────────────────────────────
missing_dims = [d for d in metrics.dimensions if d.is_missing]
if missing_dims:
    st.warning(
        "以下维度数据缺失，百分位为默认值："
        + "、".join(d.label for d in missing_dims)
    )

# ── Natural language explanation ──────────────────────────────────────────
if metrics.explanation:
    st.info(metrics.explanation)

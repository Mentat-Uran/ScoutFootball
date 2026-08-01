"""Read-only scouting queues: review queue, watchlist and shortlist."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scoutfootball.api import get_review_queue, get_shortlist, get_watchlist
from scoutfootball.storage.csv_safety import dataframe_to_csv

st.header("球探队列")

# --- Load data ---
review_queue = get_review_queue(limit=200)
watchlist = get_watchlist(limit=200)
shortlist = get_shortlist(limit=200)

# --- Summary metrics ---
metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
metric_col1.metric("Review Queue", review_queue.get("count", 0))
metric_col2.metric("Watchlist", watchlist.get("count", 0))
metric_col3.metric("Shortlist", shortlist.get("count", 0))
total = review_queue.get("count", 0) + watchlist.get("count", 0) + shortlist.get("count", 0)
metric_col4.metric("Total", total)

# --- Confidence distribution ---
all_rows = (
    review_queue.get("players", [])
    + watchlist.get("players", [])
    + shortlist.get("players", [])
)
if all_rows:
    conf_counts = pd.DataFrame(all_rows).get(
        "confidence_level", pd.Series(dtype=str)
    ).value_counts()
    conf_cols = st.columns(min(len(conf_counts), 4))
    for i, (level, count) in enumerate(conf_counts.items()):
        if i < len(conf_cols):
            conf_cols[i].metric(str(level), int(count))


def _render_table(title: str, payload: dict, queue_type: str) -> None:
    """Render a scouting queue table with filters and sorting."""
    st.subheader(title)
    rows = payload.get("players", [])
    if not rows:
        st.info(f"{title} 暂无数据。")
        return

    frame = pd.DataFrame(rows)

    # --- Filters ---
    filter_cols = st.columns(3)

    # League filter
    with filter_cols[0]:
        if "league" in frame.columns:
            leagues = sorted(frame["league"].dropna().unique().tolist())
            selected_leagues = st.multiselect(
                f"联赛筛选 ({title})",
                leagues,
                default=[],
                key=f"league_{queue_type}",
            )
            if selected_leagues:
                frame = frame[frame["league"].isin(selected_leagues)]

    # Position filter
    with filter_cols[1]:
        if "position_group" in frame.columns:
            positions = sorted(frame["position_group"].dropna().unique().tolist())
            selected_positions = st.multiselect(
                f"位置筛选 ({title})",
                positions,
                default=[],
                key=f"pos_{queue_type}",
            )
            if selected_positions:
                frame = frame[frame["position_group"].isin(selected_positions)]

    # Confidence filter
    with filter_cols[2]:
        if "confidence_level" in frame.columns:
            conf_levels = sorted(frame["confidence_level"].dropna().unique().tolist())
            selected_conf = st.multiselect(
                f"置信度 ({title})",
                conf_levels,
                default=[],
                key=f"conf_{queue_type}",
            )
            if selected_conf:
                frame = frame[frame["confidence_level"].isin(selected_conf)]

    if frame.empty:
        st.info(f"筛选后 {title} 无数据。")
        return

    # --- Sort ---
    sort_cols = st.columns(2)
    with sort_cols[0]:
        sort_options = [
            c for c in ["optimized_score", "minutes", "player_name", "league"]
            if c in frame.columns
        ]
        if sort_options:
            sort_by = st.selectbox(
                "排序字段",
                sort_options,
                index=0,
                key=f"sort_{queue_type}",
            )
        else:
            sort_by = None
    with sort_cols[1]:
        sort_asc = st.checkbox("升序", value=False, key=f"asc_{queue_type}")

    if sort_by:
        frame = frame.sort_values(sort_by, ascending=sort_asc, na_position="last")

    # --- Display columns ---
    preferred = [
        "player_name",
        "team",
        "league",
        "season",
        "position_group",
        "optimized_score",
        "minutes",
        "confidence_level",
        "reason_code",
        "review_status",
    ]
    present = [col for col in preferred if col in frame.columns]

    # Format score to 1 decimal
    if "optimized_score" in frame.columns:
        frame["optimized_score"] = pd.to_numeric(frame["optimized_score"], errors="coerce").round(1)
    if "minutes" in frame.columns:
        frame["minutes"] = pd.to_numeric(frame["minutes"], errors="coerce").round(0).astype("Int64")

    st.dataframe(
        frame[present],
        use_container_width=True,
        hide_index=True,
        height=min(len(frame) * 35 + 40, 500),
    )

    # --- Export ---
    csv = dataframe_to_csv(frame[present])
    st.download_button(
        f"导出 {title} CSV",
        csv,
        file_name=f"{queue_type}.csv",
        mime="text/csv",
        key=f"export_{queue_type}",
    )


# --- Render queues in tabs ---
tab1, tab2, tab3 = st.tabs([
    f"Review Queue ({review_queue.get('count', 0)})",
    f"Watchlist ({watchlist.get('count', 0)})",
    f"Shortlist ({shortlist.get('count', 0)})",
])

with tab1:
    _render_table("Review Queue", review_queue, "review")

with tab2:
    _render_table("Watchlist", watchlist, "watchlist")

with tab3:
    _render_table("Shortlist", shortlist, "shortlist")

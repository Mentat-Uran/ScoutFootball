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

st.header("球探队列")

review_queue = get_review_queue(limit=100)
watchlist = get_watchlist(limit=100)
shortlist = get_shortlist(limit=100)

metric_col1, metric_col2, metric_col3 = st.columns(3)
metric_col1.metric("Review Queue", review_queue.get("count", 0))
metric_col2.metric("Watchlist", watchlist.get("count", 0))
metric_col3.metric("Shortlist", shortlist.get("count", 0))


def _render_table(title: str, payload: dict) -> None:
    st.subheader(title)
    rows = payload.get("players", [])
    if not rows:
        st.info(f"{title} 暂无数据。")
        return
    frame = pd.DataFrame(rows)
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
        "rating_snapshot_id",
    ]
    present = [col for col in preferred if col in frame.columns]
    st.dataframe(frame[present], use_container_width=True, hide_index=True)


_render_table("Review Queue", review_queue)
_render_table("Watchlist", watchlist)
_render_table("Shortlist", shortlist)

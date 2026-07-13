"""Conservative links from StatsBomb action-value rows to rating artifacts.

StatsBomb player identifiers and the rating artifact do not share a stable key.
This module therefore exposes *candidates*, never a confirmed identity: a row
is eligible only when its normalized name, team, and season all agree.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd

from scoutfootball.action_value.identity import _identifier, _text

RATING_LINK_SCHEMA = "scoutfootball.action-value-rating-links"
RATING_LINK_VERSION = "1.0.0"


def _key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _text(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def _season_key(value: Any) -> str:
    text = _text(value)
    match = re.search(r"(\d{2,4})\D+(\d{2,4})", text)
    if match:
        left, right = match.groups()
        return f"{left[-2:]}{right[-2:]}"
    return re.sub(r"\D", "", text)[-4:]


def build_action_value_rating_links(
    player_id: str,
    action_rows: pd.DataFrame,
    rating_rows: pd.DataFrame,
) -> dict[str, Any]:
    """Return strict rating candidates for one StatsBomb action-value player.

    The result deliberately avoids confidence scores and automatic linking.
    Identical display names can still belong to different people, so a human
    must verify every candidate before using it for a scouting decision.
    """
    normalized_id = _identifier(player_id)
    empty = {
        "schema": RATING_LINK_SCHEMA,
        "version": RATING_LINK_VERSION,
        "player_id": normalized_id,
        "status": "not_found",
        "action_identity": {"player_name": "", "contexts": []},
        "rating_candidates": [],
        "limitations": [
            "StatsBomb identifiers and rating artifacts do not share a stable identifier.",
            "Candidates require normalized name, team, and season agreement and "
            "still need human verification.",
            "A candidate is not a merged model feature, shortlist entry, or "
            "confirmed player identity.",
        ],
    }
    if not normalized_id:
        empty["status"] = "invalid_player_id"
        return empty
    if action_rows.empty or "player_id" not in action_rows.columns:
        return empty

    actions = action_rows.copy()
    actions["player_id"] = actions["player_id"].map(_identifier)
    actions = actions.loc[actions["player_id"] == normalized_id].copy()
    if actions.empty:
        return empty

    for column in ("player_name", "team_name", "season"):
        if column not in actions.columns:
            actions[column] = ""
    actions["name_key"] = actions["player_name"].map(_key)
    actions["team_key"] = actions["team_name"].map(_key)
    actions["season_key"] = actions["season"].map(_season_key)
    contexts = (
        actions[["player_name", "team_name", "season", "name_key", "team_key", "season_key"]]
        .drop_duplicates()
        .sort_values(["season", "team_name", "player_name"])
    )
    visible_contexts = [
        {
            "player_name": _text(row.player_name),
            "team_name": _text(row.team_name),
            "season": _text(row.season),
            "matchable": bool(row.name_key and row.team_key and row.season_key),
        }
        for row in contexts.itertuples(index=False)
    ]
    empty["action_identity"] = {
        "player_name": next(
            (item["player_name"] for item in visible_contexts if item["player_name"]), ""
        ),
        "contexts": visible_contexts,
    }

    required = {"player", "team", "season"}
    if rating_rows.empty or not required.issubset(rating_rows.columns):
        empty["status"] = "rating_artifact_unavailable"
        return empty
    ratings = rating_rows.copy()
    ratings["name_key"] = ratings["player"].map(_key)
    ratings["team_key"] = ratings["team"].map(_key)
    ratings["season_key"] = ratings["season"].map(_season_key)
    rating_index = {
        (row.name_key, row.team_key, row.season_key): row
        for row in ratings.itertuples(index=False)
        if row.name_key and row.team_key and row.season_key
    }
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for context in contexts.itertuples(index=False):
        key = (context.name_key, context.team_key, context.season_key)
        row = rating_index.get(key)
        if row is None or key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "player": _text(row.player),
                "team": _text(row.team),
                "league": _text(getattr(row, "league", "")),
                "season": _text(row.season),
                "position_group": _text(getattr(row, "sub_position", "")),
                "optimized_score": float(getattr(row, "optimized_score", 0) or 0),
                "minutes": int(float(getattr(row, "minutes", 0) or 0)),
                "match_basis": "normalized_name_team_season",
            }
        )
    empty["rating_candidates"] = candidates
    empty["status"] = "candidate_available" if candidates else "no_strict_candidate"
    return empty

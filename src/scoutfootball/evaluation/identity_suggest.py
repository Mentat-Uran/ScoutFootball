"""Canonical identity mapping suggestions (PRS-1 R-005).

Read-only tool that suggests ``(source_name, source_player_id) → canonical_player_id``
mappings by cross-referencing statsbomb players against fbref/understat players
in the same season + competition using normalized name + team matching.

The tool does NOT auto-apply suggestions — it outputs candidates for human
review. The maintainer then uses the identity registry CLI (``append_decision``)
to confirm or reject each suggestion.

Matching strategy:
1. Exact normalized name match (``normalize_person_name`` strips accents,
   lowercases, removes non-alphanumeric characters).
2. Team name verification (``normalize_team_name`` handles aliases like
   "Man City" → "Manchester City").
3. Season + competition scope (only matches within the same
   ``season_id`` + ``competition_id``).

Confidence levels:
- ``"high"``: exact normalized name + team match + season match.
- ``"medium"``: exact normalized name + season match, team differs (possible
  transfer or different team-name vocabulary across sources).
- ``"no_match"``: no normalized name match found in the same
  season + competition.

Limitations:
- No fuzzy matching (Levenshtein, token overlap). StatsBomb uses full legal
  names (e.g. "Rodrigo Andrés Battaglia") while understat/fbref may use shorter
  common names (e.g. "Rodrigo Battaglia"); these won't match exactly and are
  reported as ``"no_match"`` for manual review.
- Only matches within the same ``season_id`` + ``competition_id``. Cross-season
  or cross-competition matches are not attempted.
- Does not check the existing registry for already-mapped players. The caller
  should filter out already-mapped ``(source_name, source_player_id)`` pairs
  before presenting suggestions.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from scoutfootball.config import PlatformSettings
from scoutfootball.entities.normalize import normalize_person_name, normalize_team_name

# Sources that use descriptive player IDs (e.g. "understat|1000" or
# "Lionel Messi|1920|Argentina"). When a statsbomb player matches one of
# these, the canonical_player_id is suggested as the matched player's ID
# because it is more descriptive and stable than the statsbomb numeric ID.
DESCRIPTIVE_ID_SOURCES = frozenset({"fbref", "understat"})

# The source whose players need canonical resolution (numeric IDs).
PRIMARY_SOURCE = "statsbomb_open"


def _load_player_match(settings: PlatformSettings) -> pd.DataFrame:
    """Read player_match.parquet from the gold feature store."""
    path = settings.gold_root / "feature_store" / "player_match.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _unique_players(
    df: pd.DataFrame, source_filter: str | None = None
) -> pd.DataFrame:
    """Return one row per unique (player_id, player_name, team_name,
    season_id, competition_id, source_name) combination."""
    cols = [
        "player_id",
        "player_name",
        "team_name",
        "season_id",
        "competition_id",
        "source_name",
    ]
    available = [c for c in cols if c in df.columns]
    if len(available) < len(cols):
        missing = set(cols) - set(available)
        raise ValueError(f"player_match missing required columns: {sorted(missing)}")
    sub = df[available].copy()
    if source_filter:
        sub = sub[sub["source_name"] == source_filter]
    return sub.drop_duplicates().reset_index(drop=True)


def suggest_canonical_mappings(
    *,
    settings: PlatformSettings | None = None,
    player_match: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Suggest canonical identity mappings for statsbomb players.

    Reads ``player_match.parquet`` (or uses the provided ``player_match``
    DataFrame), cross-references statsbomb players against fbref/understat
    players in the same season + competition, and returns a report with
    suggested mappings.

    The report is a dict with:
    - ``schema``: ``"scoutfootball.identity-suggest"``
    - ``schema_version``: ``"1.0.0"``
    - ``total_primary_players``: number of unique statsbomb players examined.
    - ``matched``: list of suggestion dicts (confidence "high" or "medium").
    - ``unmatched``: list of dicts for players with no name match found.
    - ``summary``: dict with counts by confidence level.
    - ``limitations``: list of honest limitation strings.

    Each suggestion dict in ``matched`` has:
    - ``source_name``: ``"statsbomb_open"``
    - ``source_player_id``: the statsbomb numeric ID (as string).
    - ``source_player_name``: original name from statsbomb.
    - ``source_team_name``: original team name from statsbomb.
    - ``candidate_source_name``: ``"fbref"`` or ``"understat"``.
    - ``candidate_source_player_id``: the fbref/understat player ID.
    - ``candidate_player_name``: original name from fbref/understat.
    - ``candidate_team_name``: original team name from fbref/understat.
    - ``suggested_canonical_player_id``: the suggested canonical ID
      (uses the candidate's player_id since descriptive-ID sources have
      more stable and human-readable IDs than statsbomb numeric IDs).
    - ``confidence``: ``"high"`` (name + team + season match) or
      ``"medium"`` (name + season match, team differs).
    - ``evidence``: human-readable string explaining the match basis.
    - ``season_id`` / ``competition_id``: the scope of the match.

    Each dict in ``unmatched`` has:
    - ``source_name``: ``"statsbomb_open"``
    - ``source_player_id``: the statsbomb numeric ID.
    - ``source_player_name``: original name.
    - ``source_team_name``: original team name.
    - ``season_id`` / ``competition_id``: the scope searched.
    - ``reason``: ``"no_normalized_name_match_in_season_competition"``.
    """
    resolved_settings = settings or PlatformSettings.from_root()
    pm = player_match if player_match is not None else _load_player_match(resolved_settings)

    if pm.empty:
        return {
            "schema": "scoutfootball.identity-suggest",
            "schema_version": "1.0.0",
            "total_primary_players": 0,
            "matched": [],
            "unmatched": [],
            "summary": {"high": 0, "medium": 0, "no_match": 0},
            "limitations": _LIMITATIONS,
        }

    primary = _unique_players(pm, source_filter=PRIMARY_SOURCE)
    if primary.empty:
        return {
            "schema": "scoutfootball.identity-suggest",
            "schema_version": "1.0.0",
            "total_primary_players": 0,
            "matched": [],
            "unmatched": [],
            "summary": {"high": 0, "medium": 0, "no_match": 0},
            "limitations": _LIMITATIONS,
        }

    # Build a lookup index of candidate players (fbref/understat) keyed by
    # (season_id, competition_id, normalized_name) → list of candidate rows.
    # Multiple candidates per key are possible (e.g. same name in different
    # teams within the same season+competition — rare but handled).
    candidates_df = pm[pm["source_name"].isin(DESCRIPTIVE_ID_SOURCES)].copy()
    candidates_df["_norm_name"] = candidates_df["player_name"].apply(normalize_person_name)
    candidates_df["_norm_team"] = candidates_df["team_name"].apply(normalize_team_name)

    # Also normalize the primary (statsbomb) names + teams.
    primary = primary.copy()
    primary["_norm_name"] = primary["player_name"].apply(normalize_person_name)
    primary["_norm_team"] = primary["team_name"].apply(normalize_team_name)

    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for _, prow in primary.iterrows():
        season = prow["season_id"]
        competition = prow["competition_id"]
        norm_name = prow["_norm_name"]
        norm_team = prow["_norm_team"]

        if pd.isna(season) or pd.isna(competition) or not norm_name:
            # Cannot search without season+competition or a name.
            unmatched.append({
                "source_name": PRIMARY_SOURCE,
                "source_player_id": str(prow["player_id"]),
                "source_player_name": prow["player_name"],
                "source_team_name": prow["team_name"],
                "season_id": season if not pd.isna(season) else None,
                "competition_id": competition if not pd.isna(competition) else None,
                "reason": "missing_season_or_competition_or_name",
            })
            continue

        # Find candidates in the same season + competition with the same
        # normalized name.
        mask = (
            (candidates_df["season_id"] == season)
            & (candidates_df["competition_id"] == competition)
            & (candidates_df["_norm_name"] == norm_name)
        )
        candidates = candidates_df[mask]

        if candidates.empty:
            unmatched.append({
                "source_name": PRIMARY_SOURCE,
                "source_player_id": str(prow["player_id"]),
                "source_player_name": prow["player_name"],
                "source_team_name": prow["team_name"],
                "season_id": str(season),
                "competition_id": str(competition),
                "reason": "no_normalized_name_match_in_season_competition",
            })
            continue

        # One or more candidates found. For each candidate, determine
        # confidence based on team match.
        for _, crow in candidates.iterrows():
            team_match = norm_team == crow["_norm_team"] and norm_team != ""
            confidence = "high" if team_match else "medium"

            evidence_parts = [
                f"normalized name match: '{norm_name}'",
                f"season={season}",
                f"competition={competition}",
            ]
            if team_match:
                evidence_parts.append(f"team match: '{norm_team}'")
            else:
                evidence_parts.append(
                    f"team differs: statsbomb='{prow['team_name']}' "
                    f"vs candidate='{crow['team_name']}' (possible transfer "
                    f"or vocabulary difference)"
                )

            matched.append({
                "source_name": PRIMARY_SOURCE,
                "source_player_id": str(prow["player_id"]),
                "source_player_name": prow["player_name"],
                "source_team_name": prow["team_name"],
                "candidate_source_name": crow["source_name"],
                "candidate_source_player_id": str(crow["player_id"]),
                "candidate_player_name": crow["player_name"],
                "candidate_team_name": crow["team_name"],
                "suggested_canonical_player_id": str(crow["player_id"]),
                "confidence": confidence,
                "evidence": "; ".join(evidence_parts),
                "season_id": str(season),
                "competition_id": str(competition),
            })

    high_count = sum(1 for m in matched if m["confidence"] == "high")
    medium_count = sum(1 for m in matched if m["confidence"] == "medium")
    no_match_count = len(unmatched)

    return {
        "schema": "scoutfootball.identity-suggest",
        "schema_version": "1.0.0",
        "total_primary_players": len(primary),
        "matched": matched,
        "unmatched": unmatched,
        "summary": {
            "high": high_count,
            "medium": medium_count,
            "no_match": no_match_count,
        },
        "limitations": _LIMITATIONS,
    }


_LIMITATIONS = [
    (
        "No fuzzy matching: only exact normalized name matches are suggested. "
        "StatsBomb full legal names (e.g. 'Rodrigo Andrés Battaglia') that "
        "differ from understat/fbref common names (e.g. 'Rodrigo Battaglia') "
        "are reported as 'no_match' for manual review."
    ),
    (
        "Only matches within the same season_id + competition_id. Cross-season "
        "or cross-competition matches are not attempted."
    ),
    (
        "Does not check the existing identity registry for already-mapped "
        "players. The caller should filter out already-mapped "
        "(source_name, source_player_id) pairs before presenting suggestions."
    ),
    (
        "When multiple candidates match the same primary player, all are "
        "reported. The maintainer must pick the correct one (or none) during "
        "review. Ambiguous matches are not auto-resolved."
    ),
]

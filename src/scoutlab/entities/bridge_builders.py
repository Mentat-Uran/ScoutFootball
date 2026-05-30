"""Bridge-table builders for canonical team and player matching."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher

import pandas as pd

from scoutlab.entities.normalize import (
    normalize_country_name,
    normalize_person_name,
    normalize_position_group,
    normalize_team_name,
)

HIGH_CONFIDENCE_THRESHOLD = 0.97
REVIEW_THRESHOLD = 0.90
SYSTEM_APPROVER = "system:auto"


@dataclass(frozen=True)
class BridgeBuildResult:
    """Successful bridge rows plus review and rejection queues."""

    bridges: pd.DataFrame
    review_queue: pd.DataFrame
    rejected: pd.DataFrame


def match_teams(
    source_teams: pd.DataFrame,
    canonical_teams: pd.DataFrame,
    *,
    source_name: str,
) -> BridgeBuildResult:
    """Match external team rows to canonical teams."""

    source = _prepare_team_frame(source_teams, source_side=True)
    canonical = _prepare_team_frame(canonical_teams, source_side=False)
    bridges: list[dict] = []
    review_queue: list[dict] = []
    rejected: list[dict] = []

    for _, source_row in source.iterrows():
        exact_candidates = canonical.loc[
            (canonical["normalized_name"] == source_row["normalized_name"])
            & (canonical["normalized_country"] == source_row["normalized_country"])
            & (source_row["normalized_country"] != "")
        ]
        if len(exact_candidates) == 1:
            bridges.append(
                _build_team_bridge_row(
                    source_name=source_name,
                    source_row=source_row,
                    canonical_row=exact_candidates.iloc[0],
                    method="deterministic_exact",
                    score=1.0,
                )
            )
            continue
        if len(exact_candidates) > 1:
            review_queue.append(
                _build_team_decision_row(
                    source_name=source_name,
                    source_row=source_row,
                    decision="review",
                    reason="ambiguous_exact_match",
                    score=1.0,
                    candidate_ids=exact_candidates["team_id"].tolist(),
                )
            )
            continue

        same_name_candidates = canonical.loc[
            canonical["normalized_name"] == source_row["normalized_name"]
        ]
        if (
            source_row["normalized_country"]
            and not same_name_candidates.empty
            and not (
                same_name_candidates["normalized_country"] == source_row["normalized_country"]
            ).any()
        ):
            rejected.append(
                _build_team_decision_row(
                    source_name=source_name,
                    source_row=source_row,
                    decision="rejected",
                    reason="country_conflict",
                    score=0.0,
                    candidate_ids=same_name_candidates["team_id"].tolist(),
                )
            )
            continue

        fuzzy_candidates = canonical
        if source_row["normalized_country"]:
            fuzzy_candidates = fuzzy_candidates.loc[
                fuzzy_candidates["normalized_country"] == source_row["normalized_country"]
            ]
        if fuzzy_candidates.empty:
            rejected.append(
                _build_team_decision_row(
                    source_name=source_name,
                    source_row=source_row,
                    decision="rejected",
                    reason="no_candidates",
                    score=0.0,
                    candidate_ids=[],
                )
            )
            continue

        top_candidate, top_score, candidate_ids = _top_team_candidate(
            source_row["normalized_name"],
            fuzzy_candidates,
        )
        if top_score >= HIGH_CONFIDENCE_THRESHOLD and top_candidate is not None:
            bridges.append(
                _build_team_bridge_row(
                    source_name=source_name,
                    source_row=source_row,
                    canonical_row=top_candidate,
                    method="fuzzy_auto",
                    score=top_score,
                )
            )
        elif top_score >= REVIEW_THRESHOLD:
            review_queue.append(
                _build_team_decision_row(
                    source_name=source_name,
                    source_row=source_row,
                    decision="review",
                    reason="fuzzy_review",
                    score=top_score,
                    candidate_ids=candidate_ids,
                )
            )
        else:
            rejected.append(
                _build_team_decision_row(
                    source_name=source_name,
                    source_row=source_row,
                    decision="rejected",
                    reason="low_similarity",
                    score=top_score,
                    candidate_ids=candidate_ids,
                )
            )

    return BridgeBuildResult(
        bridges=pd.DataFrame.from_records(bridges),
        review_queue=pd.DataFrame.from_records(review_queue),
        rejected=pd.DataFrame.from_records(rejected),
    )


def match_players(
    source_players: pd.DataFrame,
    canonical_players: pd.DataFrame,
    *,
    source_name: str,
) -> BridgeBuildResult:
    """Match external player rows to canonical players."""

    source = _prepare_player_frame(source_players, source_side=True)
    canonical = _prepare_player_frame(canonical_players, source_side=False)
    bridges: list[dict] = []
    review_queue: list[dict] = []
    rejected: list[dict] = []

    for _, source_row in source.iterrows():
        exact_candidates = canonical.loc[
            (canonical["normalized_name"] == source_row["normalized_name"])
            & (canonical["normalized_dob"] == source_row["normalized_dob"])
            & (canonical["normalized_nationality"] == source_row["normalized_nationality"])
            & (source_row["normalized_dob"] != "")
            & (source_row["normalized_nationality"] != "")
        ]
        if len(exact_candidates) == 1:
            bridges.append(
                _build_player_bridge_row(
                    source_name=source_name,
                    source_row=source_row,
                    canonical_row=exact_candidates.iloc[0],
                    method="deterministic_exact",
                    score=1.0,
                )
            )
            continue
        if len(exact_candidates) > 1:
            review_queue.append(
                _build_player_decision_row(
                    source_name=source_name,
                    source_row=source_row,
                    decision="review",
                    reason="ambiguous_exact_match",
                    score=1.0,
                    candidate_ids=exact_candidates["player_id"].tolist(),
                )
            )
            continue

        same_name_candidates = canonical.loc[
            canonical["normalized_name"] == source_row["normalized_name"]
        ]
        if (
            source_row["normalized_dob"]
            and not same_name_candidates.empty
            and not (
                same_name_candidates["normalized_dob"] == source_row["normalized_dob"]
            ).any()
        ):
            rejected.append(
                _build_player_decision_row(
                    source_name=source_name,
                    source_row=source_row,
                    decision="rejected",
                    reason="dob_conflict",
                    score=0.0,
                    candidate_ids=same_name_candidates["player_id"].tolist(),
                )
            )
            continue

        if source_row["normalized_dob"] == "":
            fallback_candidates = canonical.loc[
                (canonical["normalized_name"] == source_row["normalized_name"])
                & (canonical["normalized_team_name"] == source_row["normalized_team_name"])
                & (canonical["season"] == source_row["season"])
                & (
                    canonical["normalized_position_group"]
                    == source_row["normalized_position_group"]
                )
                & (source_row["normalized_team_name"] != "")
                & (source_row["season"] != "")
                & (source_row["normalized_position_group"] != "")
            ]
            if len(fallback_candidates) == 1:
                bridges.append(
                    _build_player_bridge_row(
                        source_name=source_name,
                        source_row=source_row,
                        canonical_row=fallback_candidates.iloc[0],
                        method="deterministic_team_season_position",
                        score=0.98,
                    )
                )
                continue
            if len(fallback_candidates) > 1:
                review_queue.append(
                    _build_player_decision_row(
                        source_name=source_name,
                        source_row=source_row,
                        decision="review",
                        reason="ambiguous_team_season_position_match",
                        score=0.98,
                        candidate_ids=fallback_candidates["player_id"].tolist(),
                    )
                )
                continue

        fuzzy_candidates = same_name_candidates if not same_name_candidates.empty else canonical
        if source_row["normalized_nationality"]:
            filtered = fuzzy_candidates.loc[
                fuzzy_candidates["normalized_nationality"] == source_row["normalized_nationality"]
            ]
            if not filtered.empty:
                fuzzy_candidates = filtered
        top_candidate, top_score, candidate_ids = _top_player_candidate(
            source_row["normalized_name"],
            fuzzy_candidates,
        )
        if top_candidate is None:
            rejected.append(
                _build_player_decision_row(
                    source_name=source_name,
                    source_row=source_row,
                    decision="rejected",
                    reason="no_candidates",
                    score=0.0,
                    candidate_ids=[],
                )
            )
        elif top_score >= HIGH_CONFIDENCE_THRESHOLD:
            bridges.append(
                _build_player_bridge_row(
                    source_name=source_name,
                    source_row=source_row,
                    canonical_row=top_candidate,
                    method="fuzzy_auto",
                    score=top_score,
                )
            )
        elif top_score >= REVIEW_THRESHOLD:
            review_queue.append(
                _build_player_decision_row(
                    source_name=source_name,
                    source_row=source_row,
                    decision="review",
                    reason="fuzzy_review",
                    score=top_score,
                    candidate_ids=candidate_ids,
                )
            )
        else:
            rejected.append(
                _build_player_decision_row(
                    source_name=source_name,
                    source_row=source_row,
                    decision="rejected",
                    reason="low_similarity",
                    score=top_score,
                    candidate_ids=candidate_ids,
                )
            )

    return BridgeBuildResult(
        bridges=pd.DataFrame.from_records(bridges),
        review_queue=pd.DataFrame.from_records(review_queue),
        rejected=pd.DataFrame.from_records(rejected),
    )


def _prepare_team_frame(frame: pd.DataFrame, *, source_side: bool) -> pd.DataFrame:
    prepared = frame.copy()
    id_column = _find_first_column(prepared, ["source_team_id", "team_id", "id"])
    name_column = _find_first_column(prepared, ["team_name", "title", "squad", "club", "team"])
    country_column = _find_first_column(prepared, ["country_name", "country", "nation"])

    if not source_side and "team_id" not in prepared.columns:
        raise ValueError("canonical_teams must include team_id")

    prepared["source_team_id"] = prepared[id_column].astype("string")
    prepared["team_name"] = prepared[name_column].astype("string")
    prepared["country_name"] = (
        prepared[country_column].astype("string") if country_column is not None else ""
    )
    prepared["normalized_name"] = prepared["team_name"].map(normalize_team_name)
    prepared["normalized_country"] = prepared["country_name"].map(normalize_country_name)
    return prepared


def _prepare_player_frame(frame: pd.DataFrame, *, source_side: bool) -> pd.DataFrame:
    prepared = frame.copy()
    id_column = _find_first_column(prepared, ["source_player_id", "player_id", "id"])
    name_column = _find_first_column(prepared, ["player_name", "player", "name"])
    dob_column = _find_first_column(prepared, ["date_of_birth", "dob", "birth_date"])
    nationality_column = _find_first_column(prepared, ["nationality", "country_name", "country"])
    team_name_column = _find_first_column(
        prepared,
        ["team_name", "team_title", "squad", "club", "team"],
    )
    position_column = _find_first_column(
        prepared,
        ["primary_position_group", "position_group", "position", "pos"],
    )
    season_column = _find_first_column(prepared, ["season", "season_name"])

    if not source_side and "player_id" not in prepared.columns:
        raise ValueError("canonical_players must include player_id")

    prepared["source_player_id"] = prepared[id_column].astype("string")
    prepared["player_name"] = prepared[name_column].astype("string")
    prepared["date_of_birth"] = (
        pd.to_datetime(prepared[dob_column], errors="coerce").dt.date
        if dob_column is not None
        else pd.NaT
    )
    prepared["nationality"] = (
        prepared[nationality_column].astype("string") if nationality_column is not None else ""
    )
    prepared["team_name"] = (
        prepared[team_name_column].astype("string") if team_name_column is not None else ""
    )
    prepared["position_group"] = (
        prepared[position_column].astype("string") if position_column is not None else ""
    )
    prepared["season"] = (
        prepared[season_column].astype("string") if season_column is not None else ""
    )
    prepared["normalized_name"] = prepared["player_name"].map(normalize_person_name)
    prepared["normalized_dob"] = prepared["date_of_birth"].astype("string").fillna("")
    prepared["normalized_nationality"] = prepared["nationality"].map(normalize_country_name)
    prepared["normalized_team_name"] = prepared["team_name"].map(normalize_team_name)
    prepared["normalized_position_group"] = prepared["position_group"].map(
        normalize_position_group,
    )
    return prepared


def _build_team_bridge_row(
    *,
    source_name: str,
    source_row: pd.Series,
    canonical_row: pd.Series,
    method: str,
    score: float,
) -> dict:
    approved_at = datetime.now(tz=UTC).isoformat()
    return {
        "source_name": source_name,
        "source_team_id": source_row["source_team_id"],
        "team_id": canonical_row["team_id"],
        "method": method,
        "score": score,
        "approved_by": SYSTEM_APPROVER,
        "approved_at": approved_at,
    }


def _build_player_bridge_row(
    *,
    source_name: str,
    source_row: pd.Series,
    canonical_row: pd.Series,
    method: str,
    score: float,
) -> dict:
    approved_at = datetime.now(tz=UTC).isoformat()
    return {
        "source_name": source_name,
        "source_player_id": source_row["source_player_id"],
        "player_id": canonical_row["player_id"],
        "method": method,
        "score": score,
        "approved_by": SYSTEM_APPROVER,
        "approved_at": approved_at,
    }


def _build_team_decision_row(
    *,
    source_name: str,
    source_row: pd.Series,
    decision: str,
    reason: str,
    score: float,
    candidate_ids: list[str],
) -> dict:
    return {
        "source_name": source_name,
        "source_team_id": source_row["source_team_id"],
        "team_name": source_row["team_name"],
        "country_name": source_row["country_name"],
        "decision": decision,
        "reason": reason,
        "score": score,
        "candidate_team_ids": candidate_ids,
    }


def _build_player_decision_row(
    *,
    source_name: str,
    source_row: pd.Series,
    decision: str,
    reason: str,
    score: float,
    candidate_ids: list[str],
) -> dict:
    return {
        "source_name": source_name,
        "source_player_id": source_row["source_player_id"],
        "player_name": source_row["player_name"],
        "decision": decision,
        "reason": reason,
        "score": score,
        "candidate_player_ids": candidate_ids,
    }


def _top_team_candidate(
    normalized_name: str,
    candidates: pd.DataFrame,
) -> tuple[pd.Series | None, float, list[str]]:
    if candidates.empty:
        return None, 0.0, []
    scored = [
        (
            SequenceMatcher(None, normalized_name, candidate_name).ratio(),
            row,
        )
        for _, row in candidates.iterrows()
        for candidate_name in [row["normalized_name"]]
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    top_score, top_row = scored[0]
    return top_row, top_score, candidates["team_id"].tolist()


def _top_player_candidate(
    normalized_name: str,
    candidates: pd.DataFrame,
) -> tuple[pd.Series | None, float, list[str]]:
    if candidates.empty:
        return None, 0.0, []
    scored = [
        (
            SequenceMatcher(None, normalized_name, candidate_name).ratio(),
            row,
        )
        for _, row in candidates.iterrows()
        for candidate_name in [row["normalized_name"]]
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    top_score, top_row = scored[0]
    return top_row, top_score, candidates["player_id"].tolist()


def _find_first_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    return None

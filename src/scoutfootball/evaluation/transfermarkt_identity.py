"""Conservative identity resolution for local Transfermarkt value snapshots.

The rating matrix and a manually supplied market-value file do not share a
stable provider ID.  This module deliberately maps only unambiguous
name/season or name/team/season records and produces review rows for the rest.
It never treats fuzzy name similarity as a confirmed player identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from scoutfootball.entities.normalize import normalize_person_name, normalize_team_name

MAPPING_COLUMNS = [
    "source_row",
    "player_name",
    "team_name",
    "snapshot_date",
    "canonical_player_id",
    "method",
    "score",
]
DECISION_COLUMNS = [
    "source_row",
    "player_name",
    "team_name",
    "snapshot_date",
    "reason",
    "candidate_player_ids",
]


@dataclass(frozen=True)
class TransfermarktIdentityResult:
    """Confirmed mappings and source rows requiring human attention."""

    mappings: pd.DataFrame
    review_queue: pd.DataFrame
    unresolved: pd.DataFrame


def resolve_transfermarkt_snapshot_identities(
    snapshot: pd.DataFrame,
    feature_matrix: pd.DataFrame,
    *,
    season: str,
) -> TransfermarktIdentityResult:
    """Resolve a local snapshot against one season of the rating matrix.

    A unique name in the target season is accepted when the matrix lacks team
    context.  When both sides provide team context, an exact normalized team
    match is preferred; a differing team is sent to review rather than assumed
    to be a harmless transfer or alias.
    """
    required_snapshot = {"player_name", "team_name", "snapshot_date"}
    required_features = {"player_id", "player_name", "season_id"}
    missing_snapshot = sorted(required_snapshot - set(snapshot.columns))
    missing_features = sorted(required_features - set(feature_matrix.columns))
    if missing_snapshot:
        raise ValueError(f"Transfermarkt snapshot missing identity columns: {missing_snapshot}")
    if missing_features:
        raise ValueError(f"Rating feature matrix missing identity columns: {missing_features}")

    source = snapshot.reset_index(drop=True).copy()
    source["source_row"] = source.index.astype(int)
    source["normalized_name"] = source["player_name"].map(normalize_person_name)
    source["normalized_team"] = source["team_name"].map(normalize_team_name)

    canonical_columns = [
        column for column in ["player_id", "player_name", "team_name"] if column in feature_matrix
    ]
    canonical = feature_matrix.loc[
        feature_matrix["season_id"].astype(str) == str(season),
        canonical_columns,
    ].copy()
    canonical["normalized_name"] = canonical["player_name"].map(normalize_person_name)
    canonical["normalized_team"] = (
        canonical["team_name"].map(normalize_team_name) if "team_name" in canonical else ""
    )

    mappings: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for row in source.itertuples(index=False):
        candidates = canonical.loc[canonical["normalized_name"] == row.normalized_name]
        candidate_ids = sorted(set(candidates["player_id"].astype(str)))
        decision = {
            "source_row": int(row.source_row),
            "player_name": str(row.player_name),
            "team_name": str(row.team_name),
            "snapshot_date": str(row.snapshot_date),
        }
        if not candidate_ids:
            unresolved.append(
                {
                    **decision,
                    "reason": "no_name_season_candidate",
                    "candidate_player_ids": [],
                },
            )
            continue

        team_candidates = (
            candidates.loc[candidates["normalized_team"] == row.normalized_team]
            if row.normalized_team
            else candidates.iloc[0:0]
        )
        team_candidate_ids = sorted(set(team_candidates["player_id"].astype(str)))
        if len(team_candidate_ids) == 1:
            mappings.append(
                {
                    **decision,
                    "canonical_player_id": team_candidate_ids[0],
                    "method": "name_team_season_exact",
                    "score": 1.0,
                },
            )
        elif len(candidate_ids) == 1 and not row.normalized_team:
            mappings.append(
                {
                    **decision,
                    "canonical_player_id": candidate_ids[0],
                    "method": "name_season_unique",
                    "score": 0.98,
                },
            )
        elif len(candidate_ids) == 1 and not candidates["normalized_team"].iloc[0]:
            mappings.append(
                {
                    **decision,
                    "canonical_player_id": candidate_ids[0],
                    "method": "name_season_unique_matrix_team_missing",
                    "score": 0.95,
                },
            )
        elif len(candidate_ids) == 1:
            review.append(
                {
                    **decision,
                    "reason": "team_conflict",
                    "candidate_player_ids": candidate_ids,
                },
            )
        else:
            review.append(
                {
                    **decision,
                    "reason": "ambiguous_name_season",
                    "candidate_player_ids": candidate_ids,
                },
            )

    return TransfermarktIdentityResult(
        mappings=pd.DataFrame(mappings, columns=MAPPING_COLUMNS),
        review_queue=pd.DataFrame(review, columns=DECISION_COLUMNS),
        unresolved=pd.DataFrame(unresolved, columns=DECISION_COLUMNS),
    )


def apply_resolved_transfermarkt_identities(
    labels: pd.DataFrame,
    result: TransfermarktIdentityResult,
) -> pd.DataFrame:
    """Return only labels with a confirmed canonical rating-matrix identity."""
    if labels.empty or result.mappings.empty:
        return labels.iloc[0:0].copy()
    resolved = labels.reset_index(drop=True).copy()
    ids = result.mappings.set_index("source_row")["canonical_player_id"]
    resolved["_canonical_player_id"] = resolved.index.map(ids)
    resolved = resolved.loc[resolved["_canonical_player_id"].notna()].copy()
    resolved["player_id"] = resolved.pop("_canonical_player_id").astype("string")
    return resolved


def transfermarkt_identity_report(result: TransfermarktIdentityResult) -> dict[str, Any]:
    """Build a compact, explicit coverage report for import previews and API use."""
    mapped = len(result.mappings)
    review = len(result.review_queue)
    unresolved = len(result.unresolved)
    total = mapped + review + unresolved
    methods = result.mappings["method"].value_counts().to_dict() if mapped else {}
    reasons = pd.concat([result.review_queue, result.unresolved], ignore_index=True)
    return {
        "total_rows": total,
        "mapped_rows": mapped,
        "review_rows": review,
        "unresolved_rows": unresolved,
        "coverage_rate": (mapped / total) if total else 0.0,
        "mapping_methods": {str(key): int(value) for key, value in methods.items()},
        "decision_reasons": (
            {str(key): int(value) for key, value in reasons["reason"].value_counts().items()}
            if not reasons.empty
            else {}
        ),
        "caveat": (
            "Only deterministic name-and-season identities are imported; review and unresolved "
            "rows are not supervision labels."
        ),
    }

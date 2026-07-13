"""Tests for conservative Transfermarkt-to-rating identity resolution."""

from __future__ import annotations

import pandas as pd

from scoutfootball.evaluation.transfermarkt_identity import (
    apply_resolved_transfermarkt_identities,
    resolve_transfermarkt_snapshot_identities,
    transfermarkt_identity_report,
)


def _snapshot(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["player_name", "team_name", "snapshot_date"])


def _matrix(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["player_id", "player_name", "team_name", "season_id"])


def test_exact_name_team_season_maps_to_canonical_player_id() -> None:
    result = resolve_transfermarkt_snapshot_identities(
        _snapshot(
            [{"player_name": "Joao Felix", "team_name": "Milan", "snapshot_date": "2025-05-20"}]
        ),
        _matrix(
            [
                {
                    "player_id": "joao felix|1999|portugal",
                    "player_name": "Joao Felix",
                    "team_name": "Milan",
                    "season_id": "2425",
                }
            ]
        ),
        season="2425",
    )

    assert result.review_queue.empty
    assert result.unresolved.empty
    assert result.mappings.loc[0, "canonical_player_id"] == "joao felix|1999|portugal"
    assert result.mappings.loc[0, "method"] == "name_team_season_exact"


def test_team_conflict_requires_review_even_when_name_is_unique() -> None:
    result = resolve_transfermarkt_snapshot_identities(
        _snapshot(
            [{"player_name": "Alex Smith", "team_name": "Club A", "snapshot_date": "2025-05-20"}]
        ),
        _matrix(
            [
                {
                    "player_id": "alex smith|2000|england",
                    "player_name": "Alex Smith",
                    "team_name": "Club B",
                    "season_id": "2425",
                }
            ]
        ),
        season="2425",
    )

    assert result.mappings.empty
    assert result.review_queue.loc[0, "reason"] == "team_conflict"


def test_same_name_multiple_players_requires_review() -> None:
    result = resolve_transfermarkt_snapshot_identities(
        _snapshot([{"player_name": "Alex Smith", "team_name": "", "snapshot_date": "2025-05-20"}]),
        _matrix(
            [
                {
                    "player_id": "alex smith|2000|england",
                    "player_name": "Alex Smith",
                    "team_name": "Club A",
                    "season_id": "2425",
                },
                {
                    "player_id": "alex smith|2001|scotland",
                    "player_name": "Alex Smith",
                    "team_name": "Club B",
                    "season_id": "2425",
                },
            ],
        ),
        season="2425",
    )

    assert result.mappings.empty
    assert result.review_queue.loc[0, "reason"] == "ambiguous_name_season"


def test_unmatched_rows_are_excluded_from_labels_and_reported() -> None:
    result = resolve_transfermarkt_snapshot_identities(
        _snapshot(
            [
                {
                    "player_name": "Unknown Player",
                    "team_name": "Club A",
                    "snapshot_date": "2025-05-20",
                }
            ]
        ),
        _matrix([]),
        season="2425",
    )
    labels = pd.DataFrame(
        {
            "player_id": ["Unknown Player"],
            "season": ["2425"],
            "label_source": ["transfermarkt_value"],
        },
    )

    resolved = apply_resolved_transfermarkt_identities(labels, result)
    report = transfermarkt_identity_report(result)

    assert resolved.empty
    assert report["unresolved_rows"] == 1
    assert report["coverage_rate"] == 0.0

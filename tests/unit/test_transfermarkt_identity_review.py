from __future__ import annotations

import pandas as pd
import pytest

from scoutfootball.evaluation.transfermarkt_identity import (
    TransfermarktIdentityResult,
    apply_transfermarkt_identity_review_decisions,
)
from scoutfootball.evaluation.transfermarkt_identity_review import (
    append_identity_review_decision,
    build_identity_review_decision,
    read_identity_review_ledger,
)


def _report() -> dict:
    return {
        "season": "2425",
        "input_provenance": {
            "snapshot": {"sha256": "snapshot-hash"},
            "feature_matrix": {"sha256": "matrix-hash"},
        },
        "review_queue": [
            {
                "source_row": 3,
                "player_name": "Alex Smith",
                "team_name": "Club A",
                "snapshot_date": "2025-05-20",
                "reason": "ambiguous_name_season",
                "candidate_player_ids": ["alex|one", "alex|two"],
            }
        ],
    }


def _result() -> TransfermarktIdentityResult:
    return TransfermarktIdentityResult(
        mappings=pd.DataFrame(
            columns=[
                "source_row",
                "player_name",
                "team_name",
                "snapshot_date",
                "canonical_player_id",
                "method",
                "score",
            ]
        ),
        review_queue=pd.DataFrame(_report()["review_queue"]),
        unresolved=pd.DataFrame(
            columns=[
                "source_row",
                "player_name",
                "team_name",
                "snapshot_date",
                "reason",
                "candidate_player_ids",
            ]
        ),
    )


def test_confirmed_review_is_append_only_and_applies_only_to_its_input_context(tmp_path) -> None:
    record = build_identity_review_decision(
        _report(),
        source_row=3,
        action="confirmed",
        canonical_player_id="alex|two",
        revision=1,
        recorded_at="2026-07-17T00:00:00Z",
    )
    ledger = tmp_path / "identity-ledger.jsonl"
    append_identity_review_decision(record, ledger)

    resolved, audit = apply_transfermarkt_identity_review_decisions(
        _result(),
        snapshot_sha256="snapshot-hash",
        feature_matrix_sha256="matrix-hash",
        season="2425",
        ledger_path=str(ledger),
    )

    assert resolved.review_queue.empty
    assert resolved.mappings.loc[0, "canonical_player_id"] == "alex|two"
    assert resolved.mappings.loc[0, "method"] == "manual_review_confirmed"
    assert audit["confirmed_rows"] == 1
    assert read_identity_review_ledger(ledger) == [record]

    unchanged, audit = apply_transfermarkt_identity_review_decisions(
        _result(),
        snapshot_sha256="different-snapshot",
        feature_matrix_sha256="matrix-hash",
        season="2425",
        ledger_path=str(ledger),
    )
    assert len(unchanged.review_queue) == 1
    assert audit["confirmed_rows"] == 0


def test_rejected_and_revoked_decisions_never_select_a_candidate() -> None:
    with pytest.raises(ValueError, match="identity_confirmation_not_a_review_candidate"):
        build_identity_review_decision(
            _report(),
            source_row=3,
            action="confirmed",
            canonical_player_id="not-a-candidate",
            revision=1,
        )


def test_revocation_reverts_a_manual_confirmation_for_future_imports(tmp_path) -> None:
    ledger = tmp_path / "identity-ledger.jsonl"
    confirmed = build_identity_review_decision(
        _report(),
        source_row=3,
        action="confirmed",
        canonical_player_id="alex|one",
        revision=1,
    )
    revoked = build_identity_review_decision(
        _report(), source_row=3, action="revoked", revision=2
    )
    append_identity_review_decision(confirmed, ledger)
    append_identity_review_decision(revoked, ledger)

    resolved, audit = apply_transfermarkt_identity_review_decisions(
        _result(),
        snapshot_sha256="snapshot-hash",
        feature_matrix_sha256="matrix-hash",
        season="2425",
        ledger_path=str(ledger),
    )
    assert resolved.mappings.empty
    assert len(resolved.review_queue) == 1
    assert audit["revoked_rows"] == 1
    with pytest.raises(ValueError, match="identity_nonconfirmation_cannot_select_candidate"):
        build_identity_review_decision(
            _report(),
            source_row=3,
            action="revoked",
            canonical_player_id="alex|one",
            revision=1,
        )

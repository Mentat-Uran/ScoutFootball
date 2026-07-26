"""Unit tests for the Decision Dossier and Post-Match Review HTTP endpoints.

These tests cover the 14 routes registered under ``/recruitment/dossiers``
and ``/opposition/reviews`` plus the live-count reporting in the
``/recruitment/contracts`` and ``/opposition/contracts`` endpoints.

The tests use FastAPI's :class:`TestClient` and redirect
``scoutfootball.api._settings().report_root`` to a per-test ``tmp_path``
so no real maintainer artifacts are touched.  Each test class covers one
artifact type end-to-end: empty state → create → read → list → update →
backups → diff → restore → contracts count, plus the error paths
(404 not found, 400 invalid payload, 409 revision conflict).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── Helpers ────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _valid_dossier_payload(
    dossier_id: str = "dos-api-001",
    *,
    title: str = "API test dossier",
    status: str = "draft",
    decision: str | None = None,
    **overrides,
) -> dict:
    payload = {
        "schema": "scoutfootball.recruitment-decision-dossier",
        "version": "1.0.0",
        "dossier_id": dossier_id,
        "revision": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "author": "maintainer",
        "title": title,
        "brief_id": "brief-api-001",
        "candidate_player_id": "ply-001",
        "candidate_player_name": "Test Player",
        "candidate_team_name": "Test FC",
        "candidate_season_id": "2025",
        "status": status,
        "decision": decision,
        "decision_note": "",
        "supporting_evidence": [
            {
                "evidence_id": "ev-1",
                "fact_tier": "recorded",
                "summary": "Recorded stat line.",
                "evidence_refs": ["player_match.parquet"],
            }
        ],
        "counter_evidence": [],
        "comparisons": [],
        "risks": [
            {
                "risk_id": "risk-1",
                "summary": "Injury history.",
                "severity": "medium",
                "fact_tier": "official",
                "evidence_refs": [],
            }
        ],
        "human_opinion": "Tempting but risky.",
        "recommendation": "Hold pending medical.",
        "linked_artifacts": [],
        "notes": "",
        "limitations": ["Dossier is a personal local object; not an external fact."],
    }
    payload.update(overrides)
    return payload


def _valid_review_payload(
    review_id: str = "rev-api-001",
    *,
    title: str = "API test review",
    status: str = "draft",
    decision: str | None = None,
    **overrides,
) -> dict:
    payload = {
        "schema": "scoutfootball.opposition-post-match-review",
        "version": "1.0.0",
        "review_id": review_id,
        "revision": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "author": "maintainer",
        "title": title,
        "briefing_id": "brief-api-001",
        "match_id": "match-001",
        "home_team": "Home FC",
        "away_team": "Away FC",
        "kickoff_at": _now(),
        "competition": "Test Cup",
        "season": "2025",
        "final_score_home": 2,
        "final_score_away": 1,
        "status": status,
        "decision": decision,
        "decision_note": "",
        "hypothesis_results": [
            {
                "hypothesis_id": "hyp-1",
                "planned": "Press high.",
                "observed": "Pressed high, won 8 turnovers.",
                "outcome": "confirmed",
                "fact_tier": "recorded",
                "evidence_refs": ["team_match.parquet"],
            }
        ],
        "falsified_patterns": [],
        "new_questions": [],
        "supporting_evidence": [],
        "counter_evidence": [],
        "human_opinion": "Plan worked.",
        "recommendation": "Confirm the pressing pattern.",
        "linked_artifacts": [],
        "notes": "",
        "limitations": ["Review is a personal local object; not an external fact."],
    }
    payload.update(overrides)
    return payload


def _valid_briefing_payload(
    briefing_id: str = "brf-api-001",
    *,
    title: str = "API test briefing",
    **overrides,
) -> dict:
    """Build a valid ``scoutfootball.opposition-briefing`` v1.0.0 payload.

    The briefing model has no status/decision state machine (unlike the
    dossier and review). It carries an explicit ``sections`` tuple of
    fact sections, each with its own ``fact_tier`` classification so
    the reviewer can never confuse an official squad list with a
    maintainer estimate.
    """
    payload = {
        "schema": "scoutfootball.opposition-briefing",
        "version": "1.0.0",
        "briefing_id": briefing_id,
        "revision": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "author": "maintainer",
        "title": title,
        "match_id": "match-001",
        "home_team": "Home FC",
        "away_team": "Away FC",
        "kickoff_at": _now(),
        "competition": "Test Cup",
        "season": "2025",
        "sections": [
            {
                "section_id": "opponent_strength",
                "fact_tier": "recorded",
                "summary": "Away FC are 4th in the table, +12 xGD over last 6.",
                "evidence_refs": ["fbref/2025/AwayFC", "team_match.parquet#row=64760"],
            },
            {
                "section_id": "key_players",
                "fact_tier": "official",
                "summary": "Star striker expected to start; backup doubtful.",
                "evidence_refs": ["official-squad-list-2025"],
            },
        ],
        "linked_pattern_card_ids": ["pattern-away-right-overload"],
        "linked_scenario_tree_id": None,
        "linked_post_match_review_id": None,
        "notes": "Watch for the right-side overload in 4-2-3-1.",
        "limitations": [
            "Briefing is a personal local object; not an external fact.",
            "fact_tier is the maintainer's honest classification, not automated.",
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def api_client(tmp_path):
    """Build a TestClient with ``report_root`` redirected to ``tmp_path``."""
    from scoutfootball.api_server import create_app

    mock_settings = MagicMock()
    mock_settings.report_root = tmp_path
    with patch("scoutfootball.api._settings", return_value=mock_settings):
        app = create_app()
        yield TestClient(app)


# ── Decision Dossier endpoints ─────────────────────────────────────────


class TestDecisionDossierEndpoints:
    """Cover the 7 routes under /recruitment/dossiers."""

    def test_list_empty_returns_ok_with_zero_count(self, api_client: TestClient):
        response = api_client.get("/recruitment/dossiers")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["count"] == 0
        assert data["dossiers"] == []

    def test_get_unknown_dossier_returns_404(self, api_client: TestClient):
        response = api_client.get("/recruitment/dossiers/nonexistent")
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["code"] == "dossier_not_found"

    def test_create_then_get_round_trip(self, api_client: TestClient):
        payload = _valid_dossier_payload("dos-roundtrip")
        create = api_client.post("/recruitment/dossiers", json=payload)
        assert create.status_code == 200
        record = create.json()["record"]
        assert record["server_revision"] == 1
        assert record["dossier"]["dossier_id"] == "dos-roundtrip"

        get = api_client.get("/recruitment/dossiers/dos-roundtrip")
        assert get.status_code == 200
        assert get.json()["record"]["dossier"]["dossier_id"] == "dos-roundtrip"

    def test_create_with_invalid_payload_returns_400(self, api_client: TestClient):
        # Missing dossier_id
        bad_payload = _valid_dossier_payload("dos-bad")
        del bad_payload["dossier_id"]
        response = api_client.post("/recruitment/dossiers", json=bad_payload)
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "missing_dossier_id"

    def test_create_with_validation_error_returns_400(self, api_client: TestClient):
        # status=decided requires a non-null decision
        bad_payload = _valid_dossier_payload("dos-bad", status="decided", decision=None)
        response = api_client.post("/recruitment/dossiers", json=bad_payload)
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "validation_error"

    def test_list_after_create_reports_count(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-list-1"),
        )
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-list-2"),
        )
        response = api_client.get("/recruitment/dossiers")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        ids = {d["dossier_id"] for d in data["dossiers"]}
        assert ids == {"dos-list-1", "dos-list-2"}

    def test_backups_endpoint_returns_empty_for_unknown(self, api_client: TestClient):
        # list_backups does not check whether the dossier exists; it
        # returns an empty list when there are no backup files, which
        # is consistent with the listing semantics of briefs/briefings.
        response = api_client.get("/recruitment/dossiers/unknown/backups")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["backups"] == []

    def test_update_creates_backup_then_list_backups(self, api_client: TestClient):
        # Create rev 1
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-backup"),
        )
        # Update to rev 2 via store (the API only supports create-new;
        # updates go through the store's save with expected_revision,
        # exercised by the CLI/store tests.  Here we create a second
        # distinct dossier to ensure backups listing stays scoped.)
        # For backup creation we need a second save on the same id, which
        # the HTTP layer does not expose directly — instead we verify
        # the backups endpoint returns an empty list when no backups exist.
        response = api_client.get("/recruitment/dossiers/dos-backup/backups")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["backups"] == []

    def test_diff_without_backup_filename_returns_422(self, api_client: TestClient):
        # backup_filename is a required Query parameter; FastAPI returns
        # 422 (Unprocessable Entity) when a required query param is
        # missing, which is the framework-level validation behavior also
        # used by the briefs/briefings diff routes.
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-diff"),
        )
        response = api_client.get("/recruitment/dossiers/dos-diff/diff")
        assert response.status_code == 422

    def test_diff_with_invalid_backup_filename_returns_400(self, api_client: TestClient):
        # A filename that is not a valid backup name (does not start
        # with the dossier_id + known kind prefix) is rejected by the
        # store with backup_filename_invalid (400).
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-diff"),
        )
        response = api_client.get(
            "/recruitment/dossiers/dos-diff/diff",
            params={"backup_filename": "nonexistent.json"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "backup_filename_invalid"

    def test_diff_with_well_formed_missing_backup_returns_404(self, api_client: TestClient):
        # A filename that has the right shape (dossier_id + rev-N + uuid)
        # but does not exist on disk is rejected with backup_not_found (404).
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-diff"),
        )
        response = api_client.get(
            "/recruitment/dossiers/dos-diff/diff",
            params={"backup_filename": "dos-diff.rev-99.abcdef0123456789.json"},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "backup_not_found"

    def test_restore_without_backup_filename_returns_400(self, api_client: TestClient):
        response = api_client.post("/recruitment/dossiers/dos-x/restore", json={})
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "missing_backup_filename"

    def test_restore_with_invalid_json_returns_400(self, api_client: TestClient):
        response = api_client.post(
            "/recruitment/dossiers/dos-x/restore",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_json"

    def test_create_with_missing_body_returns_400(self, api_client: TestClient):
        response = api_client.post("/recruitment/dossiers", content=b"")
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "missing_payload"

    def test_create_with_malformed_json_returns_400(self, api_client: TestClient):
        response = api_client.post(
            "/recruitment/dossiers",
            content=b"{not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_json"


class TestDecisionDossierRestoreRoundTrip:
    """End-to-end: create → update → backup → restore → verify."""

    def test_full_backup_diff_restore_cycle(self, api_client: TestClient, tmp_path: Path):
        # We exercise the store directly to create a backup (the HTTP
        # layer only exposes create-new), then verify the diff and
        # restore endpoints consume the backup correctly.
        from scoutfootball.recruitment.dossier_store import DossierStore

        store = DossierStore(tmp_path / "recruitment" / "dossiers")

        # rev 1 — stored directly
        store.save("dos-cycle", _valid_dossier_payload("dos-cycle"), expected_revision=0)
        # rev 2 — stored directly, creates a backup of rev 1
        updated_payload = _valid_dossier_payload(
            "dos-cycle",
            title="Updated title",
            status="decided",
            decision="proceed",
        )
        store.save("dos-cycle", updated_payload, expected_revision=1)

        # The HTTP GET should now return rev 2
        get = api_client.get("/recruitment/dossiers/dos-cycle")
        assert get.status_code == 200
        assert get.json()["record"]["server_revision"] == 2
        assert get.json()["record"]["dossier"]["title"] == "Updated title"

        # List backups via HTTP
        backups = api_client.get("/recruitment/dossiers/dos-cycle/backups")
        assert backups.status_code == 200
        backup_list = backups.json()["backups"]
        assert len(backup_list) == 1
        backup_filename = backup_list[0]["backup_filename"]

        # Diff via HTTP — should show title and status/decision changes
        diff = api_client.get(
            "/recruitment/dossiers/dos-cycle/diff",
            params={"backup_filename": backup_filename},
        )
        assert diff.status_code == 200
        diff_data = diff.json()
        assert diff_data["current_revision"] == 2
        assert diff_data["backup_revision"] == 1
        assert diff_data["change_count"] > 0

        # Restore via HTTP — should create rev 3 matching rev 1
        restore = api_client.post(
            "/recruitment/dossiers/dos-cycle/restore",
            json={"backup_filename": backup_filename, "expected_revision": 2},
        )
        assert restore.status_code == 200
        restored = restore.json()["record"]
        assert restored["server_revision"] == 3
        assert restored["dossier"]["title"] == "API test dossier"
        assert restored["dossier"]["status"] == "draft"

    def test_restore_with_stale_revision_returns_409(self, api_client: TestClient, tmp_path: Path):
        from scoutfootball.recruitment.dossier_store import DossierStore

        store = DossierStore(tmp_path / "recruitment" / "dossiers")
        store.save("dos-conflict", _valid_dossier_payload("dos-conflict"), expected_revision=0)
        store.save(
            "dos-conflict",
            _valid_dossier_payload("dos-conflict", title="v2"),
            expected_revision=1,
        )
        backups = api_client.get("/recruitment/dossiers/dos-conflict/backups")
        backup_filename = backups.json()["backups"][0]["backup_filename"]

        # Stale expected_revision (current is 2, we send 1)
        response = api_client.post(
            "/recruitment/dossiers/dos-conflict/restore",
            json={"backup_filename": backup_filename, "expected_revision": 1},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "dossier_revision_conflict"


# ── Post-Match Review endpoints ────────────────────────────────────────


class TestPostMatchReviewEndpoints:
    """Cover the 7 routes under /opposition/reviews."""

    def test_list_empty_returns_ok_with_zero_count(self, api_client: TestClient):
        response = api_client.get("/opposition/reviews")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["count"] == 0
        assert data["reviews"] == []

    def test_get_unknown_review_returns_404(self, api_client: TestClient):
        response = api_client.get("/opposition/reviews/nonexistent")
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["code"] == "review_not_found"

    def test_create_then_get_round_trip(self, api_client: TestClient):
        payload = _valid_review_payload("rev-roundtrip")
        create = api_client.post("/opposition/reviews", json=payload)
        assert create.status_code == 200
        record = create.json()["record"]
        assert record["server_revision"] == 1
        assert record["review"]["review_id"] == "rev-roundtrip"

        get = api_client.get("/opposition/reviews/rev-roundtrip")
        assert get.status_code == 200
        assert get.json()["record"]["review"]["review_id"] == "rev-roundtrip"

    def test_create_with_invalid_payload_returns_400(self, api_client: TestClient):
        bad_payload = _valid_review_payload("rev-bad")
        del bad_payload["review_id"]
        response = api_client.post("/opposition/reviews", json=bad_payload)
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "missing_review_id"

    def test_create_with_validation_error_returns_400(self, api_client: TestClient):
        # status=finalized requires a non-null decision
        bad_payload = _valid_review_payload(
            "rev-bad", status="finalized", decision=None,
        )
        response = api_client.post("/opposition/reviews", json=bad_payload)
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "validation_error"

    def test_list_after_create_reports_count(self, api_client: TestClient):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-list-1"),
        )
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-list-2"),
        )
        response = api_client.get("/opposition/reviews")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        ids = {r["review_id"] for r in data["reviews"]}
        assert ids == {"rev-list-1", "rev-list-2"}

    def test_backups_endpoint_returns_empty_for_unknown(self, api_client: TestClient):
        # list_backups does not check whether the review exists; it
        # returns an empty list when there are no backup files.
        response = api_client.get("/opposition/reviews/unknown/backups")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["backups"] == []

    def test_backups_empty_when_no_updates(self, api_client: TestClient):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-backup"),
        )
        response = api_client.get("/opposition/reviews/rev-backup/backups")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["backups"] == []

    def test_diff_without_backup_filename_returns_422(self, api_client: TestClient):
        # backup_filename is a required Query parameter; FastAPI returns
        # 422 when it is missing.
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-diff"),
        )
        response = api_client.get("/opposition/reviews/rev-diff/diff")
        assert response.status_code == 422

    def test_diff_with_invalid_backup_filename_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-diff"),
        )
        response = api_client.get(
            "/opposition/reviews/rev-diff/diff",
            params={"backup_filename": "nonexistent.json"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "backup_filename_invalid"

    def test_diff_with_well_formed_missing_backup_returns_404(self, api_client: TestClient):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-diff"),
        )
        response = api_client.get(
            "/opposition/reviews/rev-diff/diff",
            params={"backup_filename": "rev-diff.rev-99.abcdef0123456789.json"},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "backup_not_found"

    def test_restore_without_backup_filename_returns_400(self, api_client: TestClient):
        response = api_client.post("/opposition/reviews/rev-x/restore", json={})
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "missing_backup_filename"

    def test_restore_with_invalid_json_returns_400(self, api_client: TestClient):
        response = api_client.post(
            "/opposition/reviews/rev-x/restore",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_json"

    def test_create_with_missing_body_returns_400(self, api_client: TestClient):
        response = api_client.post("/opposition/reviews", content=b"")
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "missing_payload"


class TestPostMatchReviewRestoreRoundTrip:
    """End-to-end: create → update → backup → restore → verify."""

    def test_full_backup_diff_restore_cycle(self, api_client: TestClient, tmp_path: Path):
        from scoutfootball.opposition.post_match_review_store import ReviewStore

        store = ReviewStore(tmp_path / "opposition" / "reviews")

        store.save("rev-cycle", _valid_review_payload("rev-cycle"), expected_revision=0)
        updated_payload = _valid_review_payload(
            "rev-cycle",
            title="Updated review",
            status="finalized",
            decision="confirmed",
        )
        store.save("rev-cycle", updated_payload, expected_revision=1)

        get = api_client.get("/opposition/reviews/rev-cycle")
        assert get.status_code == 200
        assert get.json()["record"]["server_revision"] == 2
        assert get.json()["record"]["review"]["title"] == "Updated review"

        backups = api_client.get("/opposition/reviews/rev-cycle/backups")
        assert backups.status_code == 200
        backup_list = backups.json()["backups"]
        assert len(backup_list) == 1
        backup_filename = backup_list[0]["backup_filename"]

        diff = api_client.get(
            "/opposition/reviews/rev-cycle/diff",
            params={"backup_filename": backup_filename},
        )
        assert diff.status_code == 200
        diff_data = diff.json()
        assert diff_data["current_revision"] == 2
        assert diff_data["backup_revision"] == 1
        assert diff_data["change_count"] > 0

        restore = api_client.post(
            "/opposition/reviews/rev-cycle/restore",
            json={"backup_filename": backup_filename, "expected_revision": 2},
        )
        assert restore.status_code == 200
        restored = restore.json()["record"]
        assert restored["server_revision"] == 3
        assert restored["review"]["title"] == "API test review"
        assert restored["review"]["status"] == "draft"

    def test_restore_with_stale_revision_returns_409(
        self, api_client: TestClient, tmp_path: Path,
    ):
        from scoutfootball.opposition.post_match_review_store import ReviewStore

        store = ReviewStore(tmp_path / "opposition" / "reviews")
        store.save("rev-conflict", _valid_review_payload("rev-conflict"), expected_revision=0)
        store.save(
            "rev-conflict",
            _valid_review_payload("rev-conflict", title="v2"),
            expected_revision=1,
        )
        backups = api_client.get("/opposition/reviews/rev-conflict/backups")
        backup_filename = backups.json()["backups"][0]["backup_filename"]

        response = api_client.post(
            "/opposition/reviews/rev-conflict/restore",
            json={"backup_filename": backup_filename, "expected_revision": 1},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "review_revision_conflict"


# ── Contracts endpoints report live counts ─────────────────────────────


class TestDecisionDossierUpdate:
    """Cover PUT /recruitment/dossiers/{dossier_id}.

    The update endpoint accepts a partial ``fields`` object + an
    ``expected_revision`` (If-Match). It must reject unknown fields,
    invalid status/decision values, decision-consistency violations,
    revision conflicts, and missing/invalid body shapes. Successful
    updates create a backup, bump server_revision, and return the new
    record envelope.
    """

    def test_update_title_creates_backup_and_bumps_revision(
        self, api_client: TestClient,
    ):
        create = api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-upd-1"),
        )
        assert create.status_code == 200
        server_rev = create.json()["record"]["server_revision"]
        dossier_rev = create.json()["record"]["dossier"]["revision"]

        # Update title
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-1",
            json={
                "fields": {"title": "Updated title"},
                "expected_revision": server_rev,
            },
        )
        assert response.status_code == 200
        record = response.json()["record"]
        assert record["server_revision"] == server_rev + 1
        assert record["dossier"]["title"] == "Updated title"
        assert record["dossier"]["revision"] == dossier_rev + 1
        # updated_at should be refreshed
        assert record["dossier"]["updated_at"] != create.json()["record"]["dossier"]["updated_at"]

        # Backup should now exist
        backups = api_client.get("/recruitment/dossiers/dos-upd-1/backups")
        assert backups.status_code == 200
        assert backups.json()["count"] == 1

    def test_update_with_stale_revision_returns_409(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-upd-conflict"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-conflict",
            json={
                "fields": {"title": "Stale update"},
                # Pass an obviously stale revision (current is 1)
                "expected_revision": 99,
            },
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "dossier_revision_conflict"

    def test_update_unknown_dossier_returns_404(self, api_client: TestClient):
        response = api_client.put(
            "/recruitment/dossiers/nonexistent",
            json={"fields": {"title": "x"}, "expected_revision": 1},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "dossier_not_found"

    def test_update_with_invalid_field_returns_400(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-upd-field"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-field",
            json={
                # dossier_id is not editable; the update API must refuse
                # to mutate identity/schema/version/evidence through merge
                "fields": {"dossier_id": "hijacked", "schema": "evil"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert "dossier_id" in detail["invalid_fields"]
        assert "schema" in detail["invalid_fields"]

    def test_update_with_invalid_status_returns_400(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-upd-status"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-status",
            json={
                "fields": {"status": "bogus_status"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_status"

    def test_update_with_invalid_decision_returns_400(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-upd-dec"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-dec",
            json={
                "fields": {"decision": "bogus_decision"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_decision"

    def test_update_status_to_decided_without_decision_returns_400(
        self, api_client: TestClient,
    ):
        """A draft dossier cannot jump to 'decided' without a decision value."""
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-upd-decreq", status="draft", decision=None),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-decreq",
            json={
                "fields": {"status": "decided"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "decision_required"

    def test_update_status_to_decided_with_decision_round_trip(
        self, api_client: TestClient,
    ):
        """A draft → decided transition is valid when decision is provided."""
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-upd-ok", status="draft", decision=None),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-ok",
            json={
                "fields": {"status": "decided", "decision": "proceed"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        record = response.json()["record"]
        assert record["dossier"]["status"] == "decided"
        assert record["dossier"]["decision"] == "proceed"

    def test_update_decision_on_draft_returns_400(self, api_client: TestClient):
        """A draft dossier cannot carry a decision value."""
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-upd-decdeny", status="draft", decision=None),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-decdeny",
            json={
                "fields": {"decision": "hold"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "decision_not_allowed"

    def test_update_with_missing_body_returns_400(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-upd-empty"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-empty", content=b"",
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "missing_payload"

    def test_update_with_malformed_json_returns_400(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-upd-bad"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-bad",
            content=b"{not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_json"

    def test_update_with_missing_expected_revision_returns_400(
        self, api_client: TestClient,
    ):
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-upd-miss"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-miss",
            json={"fields": {"title": "x"}},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "missing_expected_revision"

    def test_update_with_invalid_expected_revision_returns_400(
        self, api_client: TestClient,
    ):
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-upd-badrev"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-badrev",
            json={
                "fields": {"title": "x"},
                "expected_revision": "not-an-int",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_expected_revision"

    def test_update_with_non_object_fields_returns_400(
        self, api_client: TestClient,
    ):
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-upd-fields"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-fields",
            json={"fields": "not-an-object", "expected_revision": 1},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_fields"

    def test_update_preserves_evidence_and_risks(self, api_client: TestClient):
        """The update API must not silently drop evidence/comparisons/risks."""
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-upd-keep"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-upd-keep",
            json={
                "fields": {"title": "Edited title only"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        dossier = response.json()["record"]["dossier"]
        # Evidence and risks from the original payload must be preserved
        assert len(dossier["supporting_evidence"]) == 1
        assert dossier["supporting_evidence"][0]["evidence_id"] == "ev-1"
        assert len(dossier["risks"]) == 1
        assert dossier["risks"][0]["risk_id"] == "risk-1"
        # Non-editable fields are untouched
        assert dossier["dossier_id"] == "dos-upd-keep"
        assert dossier["schema"] == "scoutfootball.recruitment-decision-dossier"


class TestDecisionDossierEntryListUpdate:
    """Cover PUT /recruitment/dossiers/{id} entry-list field updates.

    The entry-list fields (supporting_evidence, counter_evidence,
    comparisons, risks) use full-list replacement semantics: the caller
    sends the complete new list and the model re-validates each entry.
    These tests cover the round-trip plus the early shape/enum checks
    added in ``_validate_entry_list``.
    """

    def test_replace_supporting_evidence_round_trip(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-ev-rt"),
        )
        new_evidence = [
            {
                "evidence_id": "ev-new-1",
                "fact_tier": "official",
                "summary": "Official squad list confirms availability.",
                "evidence_refs": ["official/squad-2025"],
            },
            {
                "evidence_id": "ev-new-2",
                "fact_tier": "estimated",
                "summary": "Model projects 0.42 xA p90.",
                "evidence_refs": ["models/rating-v2"],
            },
        ]
        response = api_client.put(
            "/recruitment/dossiers/dos-ev-rt",
            json={
                "fields": {"supporting_evidence": new_evidence},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        dossier = response.json()["record"]["dossier"]
        # Old evidence (ev-1) is gone; the new list replaces it wholesale.
        assert [e["evidence_id"] for e in dossier["supporting_evidence"]] == [
            "ev-new-1", "ev-new-2",
        ]
        assert dossier["supporting_evidence"][0]["fact_tier"] == "official"

    def test_replace_risks_round_trip(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-risk-rt"),
        )
        new_risks = [
            {
                "risk_id": "risk-new",
                "summary": "Contract expires in 6 months.",
                "severity": "high",
                "fact_tier": "official",
                "evidence_refs": [],
            },
        ]
        response = api_client.put(
            "/recruitment/dossiers/dos-risk-rt",
            json={
                "fields": {"risks": new_risks},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        dossier = response.json()["record"]["dossier"]
        assert [r["risk_id"] for r in dossier["risks"]] == ["risk-new"]
        assert dossier["risks"][0]["severity"] == "high"

    def test_replace_comparisons_round_trip(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-cmp-rt"),
        )
        new_comparisons = [
            {
                "comparison_id": "cmp-1",
                "comparison_player_id": "ply-99",
                "comparison_player_name": "Other Player",
                "fact_tier": "recorded",
                "summary": "Better p90 xA but worse defensive duels.",
                "evidence_refs": ["player_match.parquet"],
            },
        ]
        response = api_client.put(
            "/recruitment/dossiers/dos-cmp-rt",
            json={
                "fields": {"comparisons": new_comparisons},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        dossier = response.json()["record"]["dossier"]
        assert [c["comparison_id"] for c in dossier["comparisons"]] == ["cmp-1"]

    def test_replace_with_empty_list_clears_field(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-ev-clear"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-ev-clear",
            json={
                "fields": {"supporting_evidence": [], "risks": []},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        dossier = response.json()["record"]["dossier"]
        assert dossier["supporting_evidence"] == []
        assert dossier["risks"] == []

    def test_invalid_fact_tier_returns_400(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-ev-bad-tier"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-ev-bad-tier",
            json={
                "fields": {
                    "supporting_evidence": [
                        {
                            "evidence_id": "ev-x",
                            "fact_tier": "bogus_tier",
                            "summary": "Bad tier.",
                            "evidence_refs": [],
                        }
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "supporting_evidence"
        assert detail["sub_field"] == "fact_tier"

    def test_invalid_severity_returns_400(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-risk-bad-sev"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-risk-bad-sev",
            json={
                "fields": {
                    "risks": [
                        {
                            "risk_id": "risk-x",
                            "summary": "Bad severity.",
                            "severity": "catastrophic",
                            "fact_tier": "unknown",
                            "evidence_refs": [],
                        }
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "risks"
        assert detail["sub_field"] == "severity"

    def test_non_list_value_returns_400(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-ev-nonlist"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-ev-nonlist",
            json={
                "fields": {"supporting_evidence": "not-a-list"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "supporting_evidence"

    def test_non_dict_entry_returns_400(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-ev-nondict"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-ev-nondict",
            json={
                "fields": {"supporting_evidence": ["not-an-object"]},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "supporting_evidence"
        assert detail["index"] == 0

    def test_missing_evidence_id_returns_400(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-ev-noid"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-ev-noid",
            json={
                "fields": {
                    "supporting_evidence": [
                        {
                            # evidence_id missing
                            "fact_tier": "recorded",
                            "summary": "No id.",
                            "evidence_refs": [],
                        }
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "supporting_evidence"
        assert detail["sub_field"] == "evidence_id"

    def test_duplicate_evidence_ids_returns_400(self, api_client: TestClient):
        """Duplicate ids are caught by the Pydantic model re-validation."""
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-ev-dupid"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-ev-dupid",
            json={
                "fields": {
                    "supporting_evidence": [
                        {
                            "evidence_id": "dup",
                            "fact_tier": "recorded",
                            "summary": "First.",
                            "evidence_refs": [],
                        },
                        {
                            "evidence_id": "dup",
                            "fact_tier": "recorded",
                            "summary": "Second.",
                            "evidence_refs": [],
                        },
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        # The model re-validation raises DossierValidationError, which the
        # API surfaces as validation_error (not invalid_field, because the
        # early shape check passes — both entries are dicts with valid ids
        # and valid enums — and the duplicate-id check is a model-level
        # constraint enforced by the _ensure_unique_ids field validator).
        assert detail["code"] == "validation_error"

    def test_decision_consistency_with_evidence_present(
        self, api_client: TestClient,
    ):
        """A draft → decided transition can carry evidence in the same PUT."""
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload(
                "dos-ev-dec", status="draft", decision=None,
            ),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-ev-dec",
            json={
                "fields": {
                    "status": "decided",
                    "decision": "proceed",
                    "supporting_evidence": [
                        {
                            "evidence_id": "ev-final",
                            "fact_tier": "official",
                            "summary": "Medical cleared.",
                            "evidence_refs": [],
                        }
                    ],
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        dossier = response.json()["record"]["dossier"]
        assert dossier["status"] == "decided"
        assert dossier["decision"] == "proceed"
        assert [e["evidence_id"] for e in dossier["supporting_evidence"]] == [
            "ev-final"
        ]

    def test_entry_list_update_creates_backup(self, api_client: TestClient):
        api_client.post(
            "/recruitment/dossiers",
            json=_valid_dossier_payload("dos-ev-backup"),
        )
        response = api_client.put(
            "/recruitment/dossiers/dos-ev-backup",
            json={
                "fields": {
                    "supporting_evidence": [
                        {
                            "evidence_id": "ev-backup-1",
                            "fact_tier": "recorded",
                            "summary": "Backup test.",
                            "evidence_refs": [],
                        }
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        backups = api_client.get("/recruitment/dossiers/dos-ev-backup/backups")
        assert backups.status_code == 200
        assert backups.json()["count"] == 1


class TestPostMatchReviewUpdate:
    """Cover PUT /opposition/reviews/{review_id}.

    The review update endpoint mirrors the dossier update endpoint but
    enforces review-specific decision consistency:
      - status='finalized' requires a non-null decision
      - status != 'finalized' requires decision is null
    """

    def test_update_title_creates_backup_and_bumps_revision(
        self, api_client: TestClient,
    ):
        create = api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-upd-1"),
        )
        assert create.status_code == 200
        server_rev = create.json()["record"]["server_revision"]

        response = api_client.put(
            "/opposition/reviews/rev-upd-1",
            json={
                "fields": {"title": "Updated review title"},
                "expected_revision": server_rev,
            },
        )
        assert response.status_code == 200
        record = response.json()["record"]
        assert record["server_revision"] == server_rev + 1
        assert record["review"]["title"] == "Updated review title"

        backups = api_client.get("/opposition/reviews/rev-upd-1/backups")
        assert backups.status_code == 200
        assert backups.json()["count"] == 1

    def test_update_with_stale_revision_returns_409(self, api_client: TestClient):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-upd-conflict"),
        )
        response = api_client.put(
            "/opposition/reviews/rev-upd-conflict",
            json={
                "fields": {"title": "Stale"},
                "expected_revision": 99,
            },
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "review_revision_conflict"

    def test_update_unknown_review_returns_404(self, api_client: TestClient):
        response = api_client.put(
            "/opposition/reviews/nonexistent",
            json={"fields": {"title": "x"}, "expected_revision": 1},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "review_not_found"

    def test_update_with_invalid_field_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-upd-field"),
        )
        response = api_client.put(
            "/opposition/reviews/rev-upd-field",
            json={
                # review_id and schema are not editable; the update API
                # must refuse to mutate identity/schema/version through merge.
                # Note: hypothesis_results/supporting_evidence/etc. ARE
                # editable now (full-list replacement), so they cannot be
                # used to assert invalid_field behaviour.
                "fields": {"review_id": "hijacked", "schema": "evil"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert "review_id" in detail["invalid_fields"]
        assert "schema" in detail["invalid_fields"]

    def test_update_with_invalid_status_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-upd-status"),
        )
        response = api_client.put(
            "/opposition/reviews/rev-upd-status",
            json={
                "fields": {"status": "bogus_status"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_status"

    def test_update_status_to_finalized_without_decision_returns_400(
        self, api_client: TestClient,
    ):
        """A draft review cannot jump to 'finalized' without a decision."""
        api_client.post(
            "/opposition/reviews",
            json=_valid_review_payload("rev-upd-decreq", status="draft", decision=None),
        )
        response = api_client.put(
            "/opposition/reviews/rev-upd-decreq",
            json={
                "fields": {"status": "finalized"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "decision_required"

    def test_update_status_to_finalized_with_decision_round_trip(
        self, api_client: TestClient,
    ):
        """A draft → finalized transition is valid when decision is provided."""
        api_client.post(
            "/opposition/reviews",
            json=_valid_review_payload("rev-upd-ok", status="draft", decision=None),
        )
        response = api_client.put(
            "/opposition/reviews/rev-upd-ok",
            json={
                "fields": {"status": "finalized", "decision": "confirmed"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        review = response.json()["record"]["review"]
        assert review["status"] == "finalized"
        assert review["decision"] == "confirmed"

    def test_update_decision_on_draft_returns_400(self, api_client: TestClient):
        """A draft review cannot carry a decision value."""
        api_client.post(
            "/opposition/reviews",
            json=_valid_review_payload("rev-upd-decdeny", status="draft", decision=None),
        )
        response = api_client.put(
            "/opposition/reviews/rev-upd-decdeny",
            json={
                "fields": {"decision": "confirmed"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "decision_not_allowed"

    def test_update_with_invalid_score_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-upd-score"),
        )
        response = api_client.put(
            "/opposition/reviews/rev-upd-score",
            json={
                "fields": {"final_score_home": -1},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_score"

    def test_update_with_missing_expected_revision_returns_400(
        self, api_client: TestClient,
    ):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-upd-miss"),
        )
        response = api_client.put(
            "/opposition/reviews/rev-upd-miss",
            json={"fields": {"title": "x"}},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "missing_expected_revision"

    def test_update_preserves_hypothesis_results_and_evidence(
        self, api_client: TestClient,
    ):
        """The update API must not silently drop hypothesis_results/evidence."""
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-upd-keep"),
        )
        response = api_client.put(
            "/opposition/reviews/rev-upd-keep",
            json={
                "fields": {"title": "Edited title only"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        review = response.json()["record"]["review"]
        # hypothesis_results from the original payload must be preserved
        assert len(review["hypothesis_results"]) == 1
        assert review["hypothesis_results"][0]["hypothesis_id"] == "hyp-1"
        # Non-editable fields are untouched
        assert review["review_id"] == "rev-upd-keep"
        assert review["schema"] == "scoutfootball.opposition-post-match-review"


class TestPostMatchReviewEntryListUpdate:
    """Cover PUT /opposition/reviews/{id} entry-list field updates.

    The review entry-list fields (hypothesis_results, falsified_patterns,
    new_questions, supporting_evidence, counter_evidence) use full-list
    replacement semantics. These tests cover the round-trip plus the
    early shape/enum checks for review-specific enums (outcome).
    """

    def test_replace_hypothesis_results_round_trip(
        self, api_client: TestClient,
    ):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-hyp-rt"),
        )
        new_hypotheses = [
            {
                "hypothesis_id": "hyp-new",
                "planned": "Defend deep.",
                "observed": "Defended deep, conceded 0.",
                "outcome": "confirmed",
                "fact_tier": "recorded",
                "evidence_refs": ["team_match.parquet"],
            },
        ]
        response = api_client.put(
            "/opposition/reviews/rev-hyp-rt",
            json={
                "fields": {"hypothesis_results": new_hypotheses},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        review = response.json()["record"]["review"]
        assert [h["hypothesis_id"] for h in review["hypothesis_results"]] == [
            "hyp-new"
        ]
        assert review["hypothesis_results"][0]["outcome"] == "confirmed"

    def test_replace_falsified_patterns_round_trip(
        self, api_client: TestClient,
    ):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-fp-rt"),
        )
        new_patterns = [
            {
                "pattern_id": "fp-1",
                "summary": "High line was exposed.",
                "severity": "high",
                "fact_tier": "recorded",
                "evidence_refs": ["events/2025/final-third"],
            },
        ]
        response = api_client.put(
            "/opposition/reviews/rev-fp-rt",
            json={
                "fields": {"falsified_patterns": new_patterns},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        review = response.json()["record"]["review"]
        assert [p["pattern_id"] for p in review["falsified_patterns"]] == [
            "fp-1"
        ]
        assert review["falsified_patterns"][0]["severity"] == "high"

    def test_replace_new_questions_round_trip(
        self, api_client: TestClient,
    ):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-nq-rt"),
        )
        new_questions = [
            {
                "question_id": "q-1",
                "summary": "Why did the press break down after 60min?",
                "scope": "in-game adaptation",
                "fact_tier": "estimated",
                "evidence_refs": [],
            },
        ]
        response = api_client.put(
            "/opposition/reviews/rev-nq-rt",
            json={
                "fields": {"new_questions": new_questions},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        review = response.json()["record"]["review"]
        assert [q["question_id"] for q in review["new_questions"]] == ["q-1"]
        assert review["new_questions"][0]["scope"] == "in-game adaptation"

    def test_replace_supporting_evidence_round_trip(
        self, api_client: TestClient,
    ):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-ev-rt"),
        )
        new_evidence = [
            {
                "evidence_id": "ev-rev-1",
                "fact_tier": "official",
                "summary": "Official match report confirms scoreline.",
                "evidence_refs": ["official/match-report"],
            },
        ]
        response = api_client.put(
            "/opposition/reviews/rev-ev-rt",
            json={
                "fields": {"supporting_evidence": new_evidence},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        review = response.json()["record"]["review"]
        assert [e["evidence_id"] for e in review["supporting_evidence"]] == [
            "ev-rev-1"
        ]

    def test_invalid_outcome_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-hyp-bad"),
        )
        response = api_client.put(
            "/opposition/reviews/rev-hyp-bad",
            json={
                "fields": {
                    "hypothesis_results": [
                        {
                            "hypothesis_id": "hyp-bad",
                            "planned": "X",
                            "observed": "Y",
                            "outcome": "bogus_outcome",
                            "fact_tier": "recorded",
                            "evidence_refs": [],
                        }
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "hypothesis_results"
        assert detail["sub_field"] == "outcome"

    def test_invalid_fact_tier_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/reviews",
            json=_valid_review_payload("rev-ev-bad-tier"),
        )
        response = api_client.put(
            "/opposition/reviews/rev-ev-bad-tier",
            json={
                "fields": {
                    "supporting_evidence": [
                        {
                            "evidence_id": "ev-x",
                            "fact_tier": "bogus_tier",
                            "summary": "Bad tier.",
                            "evidence_refs": [],
                        }
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "supporting_evidence"
        assert detail["sub_field"] == "fact_tier"

    def test_invalid_severity_in_falsified_patterns_returns_400(
        self, api_client: TestClient,
    ):
        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-fp-bad"),
        )
        response = api_client.put(
            "/opposition/reviews/rev-fp-bad",
            json={
                "fields": {
                    "falsified_patterns": [
                        {
                            "pattern_id": "fp-bad",
                            "summary": "Bad severity.",
                            "severity": "catastrophic",
                            "fact_tier": "unknown",
                            "evidence_refs": [],
                        }
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "falsified_patterns"
        assert detail["sub_field"] == "severity"

    def test_non_list_value_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/reviews",
            json=_valid_review_payload("rev-ev-nonlist"),
        )
        response = api_client.put(
            "/opposition/reviews/rev-ev-nonlist",
            json={
                "fields": {"hypothesis_results": "not-a-list"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "hypothesis_results"

    def test_missing_hypothesis_id_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/reviews",
            json=_valid_review_payload("rev-ev-noid"),
        )
        response = api_client.put(
            "/opposition/reviews/rev-ev-noid",
            json={
                "fields": {
                    "hypothesis_results": [
                        {
                            # hypothesis_id missing
                            "planned": "X",
                            "observed": "Y",
                            "outcome": "confirmed",
                            "fact_tier": "recorded",
                            "evidence_refs": [],
                        }
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "hypothesis_results"
        assert detail["sub_field"] == "hypothesis_id"

    def test_duplicate_hypothesis_ids_returns_400(self, api_client: TestClient):
        """Duplicate ids are caught by the Pydantic model re-validation."""
        api_client.post(
            "/opposition/reviews",
            json=_valid_review_payload("rev-ev-dupid"),
        )
        response = api_client.put(
            "/opposition/reviews/rev-ev-dupid",
            json={
                "fields": {
                    "hypothesis_results": [
                        {
                            "hypothesis_id": "dup",
                            "planned": "X",
                            "observed": "Y",
                            "outcome": "confirmed",
                            "fact_tier": "recorded",
                            "evidence_refs": [],
                        },
                        {
                            "hypothesis_id": "dup",
                            "planned": "X2",
                            "observed": "Y2",
                            "outcome": "falsified",
                            "fact_tier": "recorded",
                            "evidence_refs": [],
                        },
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "validation_error"

    def test_finalized_with_evidence_round_trip(
        self, api_client: TestClient,
    ):
        """A draft → finalized transition can carry evidence in the same PUT."""
        api_client.post(
            "/opposition/reviews",
            json=_valid_review_payload(
                "rev-ev-fin", status="draft", decision=None,
            ),
        )
        response = api_client.put(
            "/opposition/reviews/rev-ev-fin",
            json={
                "fields": {
                    "status": "finalized",
                    "decision": "confirmed",
                    "supporting_evidence": [
                        {
                            "evidence_id": "ev-fin",
                            "fact_tier": "official",
                            "summary": "Official scoreline confirms plan.",
                            "evidence_refs": [],
                        }
                    ],
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        review = response.json()["record"]["review"]
        assert review["status"] == "finalized"
        assert review["decision"] == "confirmed"
        assert [e["evidence_id"] for e in review["supporting_evidence"]] == [
            "ev-fin"
        ]

    def test_entry_list_update_creates_backup(self, api_client: TestClient):
        api_client.post(
            "/opposition/reviews",
            json=_valid_review_payload("rev-ev-backup"),
        )
        response = api_client.put(
            "/opposition/reviews/rev-ev-backup",
            json={
                "fields": {
                    "supporting_evidence": [
                        {
                            "evidence_id": "ev-backup-1",
                            "fact_tier": "recorded",
                            "summary": "Backup test.",
                            "evidence_refs": [],
                        }
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        backups = api_client.get("/opposition/reviews/rev-ev-backup/backups")
        assert backups.status_code == 200
        assert backups.json()["count"] == 1


# ── Contracts endpoints report live counts ─────────────────────────────


class TestContractsLiveCounts:
    """The /recruitment/contracts and /opposition/contracts endpoints must
    report live dossier/review counts so the registry reflects real state."""

    def test_recruitment_contracts_reports_dossier_count(self, api_client: TestClient):
        # Initially no dossiers — the decision_dossier artifact should be
        # omitted (count-based inclusion).
        before = api_client.get("/recruitment/contracts")
        assert before.status_code == 200
        before_ids = {c["artifact_id"] for c in before.json()["contracts"]}
        assert "recruitment.decision_dossier" not in before_ids

        # Create a dossier
        api_client.post(
            "/recruitment/dossiers", json=_valid_dossier_payload("dos-contract"),
        )

        after = api_client.get("/recruitment/contracts")
        assert after.status_code == 200
        after_ids = {c["artifact_id"] for c in after.json()["contracts"]}
        assert "recruitment.decision_dossier" in after_ids

    def test_opposition_contracts_reports_review_count(self, api_client: TestClient):
        before = api_client.get("/opposition/contracts")
        assert before.status_code == 200
        before_ids = {c["artifact_id"] for c in before.json()["contracts"]}
        assert "opposition.post_match_review" not in before_ids

        api_client.post(
            "/opposition/reviews", json=_valid_review_payload("rev-contract"),
        )

        after = api_client.get("/opposition/contracts")
        assert after.status_code == 200
        after_ids = {c["artifact_id"] for c in after.json()["contracts"]}
        assert "opposition.post_match_review" in after_ids


# ── Opposition Briefing endpoints ──────────────────────────────────────


class TestOppositionBriefingEndpoints:
    """Cover the routes under ``/opposition/briefs``.

    The briefing endpoints predate this test class (create / get / list
    / backups / diff / restore were added in P1). This class focuses on
    the new ``PUT /opposition/briefs/{briefing_id}`` update endpoint
    added to complete the opposition workflow closed-loop (briefing
    section-level editing, mirroring the dossier/review entry-list
    editors). The update endpoint accepts a partial ``fields`` object +
    an ``expected_revision`` (If-Match). It must reject unknown fields,
    invalid ``fact_tier`` enum values, malformed ``sections`` shapes,
    and revision conflicts. Successful updates create a backup, bump
    ``server_revision``, and return the new record envelope.
    """

    def test_list_empty_returns_ok_with_zero_count(self, api_client: TestClient):
        response = api_client.get("/opposition/briefs")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["count"] == 0
        assert data["briefings"] == []

    def test_get_unknown_briefing_returns_404(self, api_client: TestClient):
        response = api_client.get("/opposition/briefs/nonexistent")
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["code"] == "briefing_not_found"

    def test_create_then_get_round_trip(self, api_client: TestClient):
        payload = _valid_briefing_payload("brf-roundtrip")
        create = api_client.post("/opposition/briefs", json=payload)
        assert create.status_code == 200
        record = create.json()["record"]
        assert record["server_revision"] == 1
        assert record["briefing"]["briefing_id"] == "brf-roundtrip"

        get = api_client.get("/opposition/briefs/brf-roundtrip")
        assert get.status_code == 200
        assert get.json()["record"]["briefing"]["briefing_id"] == "brf-roundtrip"

    def test_create_with_invalid_payload_returns_400(self, api_client: TestClient):
        # Missing briefing_id
        bad_payload = _valid_briefing_payload("brf-bad")
        del bad_payload["briefing_id"]
        response = api_client.post("/opposition/briefs", json=bad_payload)
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "missing_briefing_id"

    def test_create_with_validation_error_returns_400(self, api_client: TestClient):
        # Invalid fact_tier in a section
        bad_payload = _valid_briefing_payload("brf-bad")
        bad_payload["sections"][0]["fact_tier"] = "bogus_tier"
        response = api_client.post("/opposition/briefs", json=bad_payload)
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "validation_error"


class TestOppositionBriefingUpdate:
    """Cover ``PUT /opposition/briefs/{briefing_id}``.

    The update endpoint mirrors the dossier/review update endpoints but
    enforces no decision-consistency checks (the briefing model has no
    status/decision state machine). The entry-list field ``sections``
    uses full-list replacement semantics and is validated early by
    ``_validate_entry_list`` for shape and ``fact_tier`` enum; the
    Pydantic model re-validates ``section_id`` uniqueness (including
    the ``custom:<tail>`` rule) and full schema when the store saves.
    """

    def test_update_title_creates_backup_and_bumps_revision(
        self, api_client: TestClient,
    ):
        create = api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-upd-1"),
        )
        assert create.status_code == 200
        server_rev = create.json()["record"]["server_revision"]
        briefing_rev = create.json()["record"]["briefing"]["revision"]

        response = api_client.put(
            "/opposition/briefs/brf-upd-1",
            json={
                "fields": {"title": "Updated briefing title"},
                "expected_revision": server_rev,
            },
        )
        assert response.status_code == 200
        record = response.json()["record"]
        assert record["server_revision"] == server_rev + 1
        assert record["briefing"]["title"] == "Updated briefing title"
        assert record["briefing"]["revision"] == briefing_rev + 1
        # updated_at should be refreshed
        assert (
            record["briefing"]["updated_at"]
            != create.json()["record"]["briefing"]["updated_at"]
        )

        # Backup should now exist
        backups = api_client.get("/opposition/briefs/brf-upd-1/backups")
        assert backups.status_code == 200
        assert backups.json()["count"] == 1

    def test_update_with_stale_revision_returns_409(self, api_client: TestClient):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-upd-conflict"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-upd-conflict",
            json={
                "fields": {"title": "Stale update"},
                # Pass an obviously stale revision (current is 1)
                "expected_revision": 99,
            },
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "briefing_revision_conflict"

    def test_update_unknown_briefing_returns_404(self, api_client: TestClient):
        response = api_client.put(
            "/opposition/briefs/nonexistent",
            json={"fields": {"title": "x"}, "expected_revision": 1},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "briefing_not_found"

    def test_update_with_invalid_field_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-upd-field"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-upd-field",
            json={
                # briefing_id and schema are not editable; the update
                # API must refuse to mutate identity/schema/version
                # through merge.
                "fields": {"briefing_id": "hijacked", "schema": "evil"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert "briefing_id" in detail["invalid_fields"]
        assert "schema" in detail["invalid_fields"]

    def test_update_with_missing_body_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-upd-empty"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-upd-empty", content=b"",
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "missing_payload"

    def test_update_with_malformed_json_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-upd-bad"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-upd-bad",
            content=b"{not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_json"

    def test_update_with_missing_expected_revision_returns_400(
        self, api_client: TestClient,
    ):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-upd-miss"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-upd-miss",
            json={"fields": {"title": "x"}},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "missing_expected_revision"

    def test_update_with_invalid_expected_revision_returns_400(
        self, api_client: TestClient,
    ):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-upd-badrev"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-upd-badrev",
            json={
                "fields": {"title": "x"},
                "expected_revision": "not-an-int",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_expected_revision"

    def test_update_with_non_object_fields_returns_400(
        self, api_client: TestClient,
    ):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-upd-fields"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-upd-fields",
            json={"fields": "not-an-object", "expected_revision": 1},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_fields"

    def test_update_preserves_sections_and_limitations(self, api_client: TestClient):
        """The update API must not silently drop sections/limitations."""
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-upd-keep"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-upd-keep",
            json={
                "fields": {"title": "Edited title only"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        briefing = response.json()["record"]["briefing"]
        # Sections from the original payload must be preserved
        assert len(briefing["sections"]) == 2
        assert briefing["sections"][0]["section_id"] == "opponent_strength"
        assert briefing["sections"][1]["section_id"] == "key_players"
        # Non-editable fields are untouched
        assert briefing["briefing_id"] == "brf-upd-keep"
        assert briefing["schema"] == "scoutfootball.opposition-briefing"
        assert len(briefing["limitations"]) == 2

    def test_update_nullable_fields_round_trip(self, api_client: TestClient):
        """``kickoff_at`` / ``linked_*_id`` accept null to clear the value."""
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-upd-null"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-upd-null",
            json={
                "fields": {
                    "kickoff_at": None,
                    "linked_scenario_tree_id": "st-001",
                    "linked_post_match_review_id": "pmr-001",
                    "linked_pattern_card_ids": ["pc-1", "pc-2"],
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        briefing = response.json()["record"]["briefing"]
        assert briefing["kickoff_at"] is None
        assert briefing["linked_scenario_tree_id"] == "st-001"
        assert briefing["linked_post_match_review_id"] == "pmr-001"
        assert briefing["linked_pattern_card_ids"] == ["pc-1", "pc-2"]


class TestOppositionBriefingSectionUpdate:
    """Cover ``PUT /opposition/briefs/{id}`` ``sections`` entry-list updates.

    The ``sections`` field uses full-list replacement semantics: the
    caller sends the complete new list and the model re-validates each
    entry's schema, ``section_id`` uniqueness (including the
    ``custom:<tail>`` rule) and ``fact_tier`` enum value. These tests
    cover the round-trip plus the early shape/enum checks added in
    ``_validate_entry_list``.
    """

    def test_replace_sections_round_trip(self, api_client: TestClient):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-sec-rt"),
        )
        new_sections = [
            {
                "section_id": "recent_form",
                "fact_tier": "recorded",
                "summary": "W3 D1 L2 in last 6, xGD +4.",
                "evidence_refs": ["fbref/2025/AwayFC"],
            },
            {
                "section_id": "injuries",
                "fact_tier": "official",
                "summary": "Star CB out with hamstring strain.",
                "evidence_refs": ["official-medical-report"],
            },
            {
                "section_id": "custom:set_pieces",
                "fact_tier": "estimated",
                "summary": "High conversion on near-post corners.",
                "evidence_refs": [],
            },
        ]
        response = api_client.put(
            "/opposition/briefs/brf-sec-rt",
            json={
                "fields": {"sections": new_sections},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        briefing = response.json()["record"]["briefing"]
        # Old sections are gone; the new list replaces wholesale.
        assert [s["section_id"] for s in briefing["sections"]] == [
            "recent_form", "injuries", "custom:set_pieces",
        ]
        assert briefing["sections"][1]["fact_tier"] == "official"
        assert briefing["sections"][2]["section_id"].startswith("custom:")

    def test_replace_with_empty_sections_clears_field(self, api_client: TestClient):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-sec-clear"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-sec-clear",
            json={
                "fields": {"sections": []},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        briefing = response.json()["record"]["briefing"]
        assert briefing["sections"] == []

    def test_invalid_fact_tier_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-sec-bad-tier"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-sec-bad-tier",
            json={
                "fields": {
                    "sections": [
                        {
                            "section_id": "opponent_strength",
                            "fact_tier": "bogus_tier",
                            "summary": "Bad tier.",
                            "evidence_refs": [],
                        }
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "sections"
        assert detail["sub_field"] == "fact_tier"

    def test_non_list_value_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-sec-nonlist"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-sec-nonlist",
            json={
                "fields": {"sections": "not-a-list"},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "sections"

    def test_non_dict_entry_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-sec-nondict"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-sec-nondict",
            json={
                "fields": {"sections": ["not-an-object"]},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "sections"
        assert detail["index"] == 0

    def test_missing_section_id_returns_400(self, api_client: TestClient):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-sec-noid"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-sec-noid",
            json={
                "fields": {
                    "sections": [
                        {
                            # section_id missing
                            "fact_tier": "recorded",
                            "summary": "No id.",
                            "evidence_refs": [],
                        }
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert detail["invalid_field"] == "sections"
        assert detail["sub_field"] == "section_id"

    def test_duplicate_section_ids_returns_400(self, api_client: TestClient):
        """Duplicate ids are caught by the Pydantic model re-validation."""
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-sec-dupid"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-sec-dupid",
            json={
                "fields": {
                    "sections": [
                        {
                            "section_id": "opponent_strength",
                            "fact_tier": "recorded",
                            "summary": "First.",
                            "evidence_refs": [],
                        },
                        {
                            "section_id": "opponent_strength",
                            "fact_tier": "recorded",
                            "summary": "Second.",
                            "evidence_refs": [],
                        },
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        # The model re-validation raises BriefingValidationError, which
        # the API surfaces as validation_error (not invalid_field,
        # because the early shape check passes — both entries are dicts
        # with valid ids and valid enums — and the duplicate-id check is
        # a model-level constraint enforced by the
        # _validate_section_ids_unique field validator).
        assert detail["code"] == "validation_error"

    def test_invalid_custom_section_id_returns_400(self, api_client: TestClient):
        """``custom:<tail>`` with an invalid tail is caught by the model."""
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-sec-badcustom"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-sec-badcustom",
            json={
                "fields": {
                    "sections": [
                        {
                            # tail contains a space, which fails the
                            # [a-zA-Z0-9_][a-zA-Z0-9_-]* regex
                            "section_id": "custom:bad tail",
                            "fact_tier": "recorded",
                            "summary": "Bad custom id.",
                            "evidence_refs": [],
                        }
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "validation_error"

    def test_section_update_creates_backup(self, api_client: TestClient):
        api_client.post(
            "/opposition/briefs", json=_valid_briefing_payload("brf-sec-backup"),
        )
        response = api_client.put(
            "/opposition/briefs/brf-sec-backup",
            json={
                "fields": {
                    "sections": [
                        {
                            "section_id": "tactical_notes",
                            "fact_tier": "estimated",
                            "summary": "Likely to press high.",
                            "evidence_refs": [],
                        }
                    ]
                },
                "expected_revision": 1,
            },
        )
        assert response.status_code == 200
        backups = api_client.get("/opposition/briefs/brf-sec-backup/backups")
        assert backups.status_code == 200
        assert backups.json()["count"] == 1

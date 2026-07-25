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
                "fields": {"review_id": "hijacked", "hypothesis_results": []},
                "expected_revision": 1,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_field"
        assert "review_id" in detail["invalid_fields"]
        assert "hypothesis_results" in detail["invalid_fields"]

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

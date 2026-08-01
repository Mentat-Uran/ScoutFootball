"""Contract tests for local decision-package evidence validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scoutfootball.evaluation.decision_package import (
    DecisionPackageValidationError,
    validate_decision_package,
    validate_decision_package_file,
)


def _briefing() -> dict:
    return {
        "schema": "scoutfootball.world-cup-match-briefing",
        "version": "1.0.0",
        "status": "ok",
        "fixture": {"home_team": "Mexico", "away_team": "South Africa"},
        "prediction": {
            "model_type": "world_cup_strength_poisson",
            "model_version": "wc-1.0",
            "home_win": 0.45,
            "draw": 0.25,
            "away_win": 0.30,
        },
        "input_snapshot": {
            "status": "recorded",
            "rating_model_run_id": "run-1",
            "rating_input_hash": "input-hash",
        },
        "teams": {
            "home": {"team": "Mexico", "squad": {"rating_coverage": 0.50}},
            "away": {"team": "South Africa", "squad": {"rating_coverage": 0.25}},
        },
        "source_attribution": "Local ScoutFootball source-bound input.",
        "limitations": ["Not a confirmed lineup or live team news."],
    }


def test_validates_world_cup_briefing_export_with_recorded_snapshot() -> None:
    package = {
        "schema": "scoutfootball.world-cup-match-briefing-export",
        "version": "1.0.0",
        "exported_at": "2026-07-17T12:00:00.000Z",
        "storage_scope": "browser-local-download",
        "briefing": _briefing(),
    }

    report = validate_decision_package(package)

    assert report["status"] == "valid"
    assert report["details"]["input_snapshot_status"] == "recorded"


def test_rejects_recorded_snapshot_without_input_hash() -> None:
    package = _briefing()
    package["input_snapshot"].pop("rating_input_hash")

    report = validate_decision_package(package)

    assert report["status"] == "invalid"
    assert "input_snapshot_record" in report["failed_checks"]


def test_rejects_probability_claim_that_is_not_a_distribution() -> None:
    package = _briefing()
    package["prediction"]["away_win"] = 0.45

    report = validate_decision_package(package)

    assert report["status"] == "invalid"
    assert "probabilities" in report["failed_checks"]


def test_validates_browser_local_shortlist_without_claiming_server_audit() -> None:
    package = {
        "schema": "scoutfootball.shortlist-decision-pack",
        "version": "1.2.0",
        "status": "ok",
        "exported_at": "2026-07-17T12:00:00.000Z",
        "storage_scope": "browser-local-download",
        "player_count": 1,
        "players": [{"player": "A"}],
        "watchlist_player_count": 0,
        "watchlist_players": [],
        "provenance_log": [],
        "limitations": ["Browser-local decision context, not server-side audit."],
    }

    report = validate_decision_package(package)

    assert report["status"] == "valid"
    assert report["details"]["provenance_status"] == "browser_local_context"


def test_rejects_shortlist_with_mismatched_declared_count() -> None:
    package = {
        "schema": "scoutfootball.shortlist-decision-pack",
        "version": "1.2.0",
        "status": "empty",
        "exported_at": "2026-07-17T12:00:00.000Z",
        "storage_scope": "browser-local-download",
        "player_count": 2,
        "players": [],
        "watchlist_player_count": 0,
        "watchlist_players": [],
        "provenance_log": [],
        "limitations": ["Browser-local decision context, not server-side audit."],
    }

    report = validate_decision_package(package)

    assert report["status"] == "invalid"
    assert "player_count" in report["failed_checks"]


def test_rejects_empty_status_when_a_shortlist_row_is_present() -> None:
    package = {
        "schema": "scoutfootball.shortlist-decision-pack",
        "version": "1.2.0",
        "status": "empty",
        "exported_at": "2026-07-17T12:00:00.000Z",
        "storage_scope": "browser-local-download",
        "player_count": 1,
        "players": [{"player": "A"}],
        "watchlist_player_count": 0,
        "watchlist_players": [],
        "provenance_log": [],
        "limitations": ["Browser-local decision context, not server-side audit."],
    }

    report = validate_decision_package(package)

    assert report["status"] == "invalid"
    assert "status" in report["failed_checks"]


def test_validates_current_static_world_cup_briefings_content() -> None:
    path = Path(__file__).resolve().parents[2] / "frontend" / "data" / "worldcup"
    path = path / "match_briefings.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    briefings = payload["briefings"]

    reports = [validate_decision_package(copy.deepcopy(briefing)) for briefing in briefings]
    collection_report = validate_decision_package_file(path)

    assert briefings
    assert {report["status"] for report in reports} == {"valid"}
    assert collection_report["status"] == "valid"
    assert collection_report["details"]["briefing_count"] == len(briefings)


def test_file_validation_rejects_invalid_json_and_leaves_file_unchanged(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(DecisionPackageValidationError, match="UTF-8 JSON"):
        validate_decision_package_file(path)

    assert path.read_bytes() == before

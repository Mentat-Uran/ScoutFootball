"""Unit tests for post-match review CLI commands.

Covers:
- ``create-review`` from CLI flags (auto-generates review_id, saves record)
- ``create-review --json`` emits JSON record
- ``create-review --from-json`` loads payload from a local file
- ``create-review --decision`` forces status='finalized'
- ``create-review --review-id`` uses an explicit id
- ``create-review`` error paths: missing --title, invalid --review-id
- ``list-reviews`` on empty and non-empty stores (text + JSON)
- ``show-review`` text and JSON output
- ``show-review`` on nonexistent id exits non-zero
- ``validate-review`` on a valid file and an invalid file
- ``validate-review`` does not write to the store
- ``validate-review`` on missing file exits non-zero
- End-to-end create → list → show → validate round-trip via CLI
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

import pytest

from scoutfootball.__main__ import main
from scoutfootball.opposition.post_match_review import (
    REVIEW_SCHEMA,
    REVIEW_VERSION,
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _valid_review_json(review_id: str = "review-cli-001") -> dict:
    return {
        "schema": REVIEW_SCHEMA,
        "version": REVIEW_VERSION,
        "review_id": review_id,
        "revision": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "author": "maintainer",
        "title": "CLI test review",
        "briefing_id": "briefing-cli-001",
        "match_id": "fd-match-64766",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "kickoff_at": "2026-08-15T15:00:00+00:00",
        "competition": "Premier League",
        "season": "2026-27",
        "final_score_home": 2,
        "final_score_away": 1,
        "status": "draft",
        "decision": None,
        "decision_note": "",
        "hypothesis_results": [
            {
                "hypothesis_id": "h-001",
                "planned": "Chelsea right-side overload",
                "observed": "Chelsea overloaded the left",
                "outcome": "falsified",
                "fact_tier": "recorded",
                "evidence_refs": ["events/2026-08-15/left-overload"],
            }
        ],
        "falsified_patterns": [
            {
                "pattern_id": "p-001",
                "summary": "Right-side overload did not occur.",
                "severity": "high",
                "fact_tier": "recorded",
                "evidence_refs": [],
            }
        ],
        "new_questions": [
            {
                "question_id": "q-001",
                "summary": "Why did Chelsea flip sides?",
                "scope": "in-game adaptation",
                "fact_tier": "estimated",
                "evidence_refs": [],
            }
        ],
        "supporting_evidence": [
            {
                "evidence_id": "ev-001",
                "fact_tier": "official",
                "summary": "Final scoreline 2-1.",
                "evidence_refs": ["official/match/64766/scoreline"],
            }
        ],
        "counter_evidence": [],
        "human_opinion": "Arsenal executed the plan.",
        "recommendation": "Add left-side contingency.",
        "linked_artifacts": ["briefing-cli-001"],
        "notes": "CLI test.",
        "limitations": [
            "PostMatchReview is a personal local object; not an external fact.",
            "Decision is the maintainer's honest judgment, not an automated recommendation.",
        ],
    }


@pytest.fixture
def isolated_data_root(tmp_path, monkeypatch):
    """Point SCOUTFOOTBALL_DATA_ROOT at a temp dir so CLI writes are isolated."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("SCOUTFOOTBALL_DATA_ROOT", str(data_root))
    return data_root


def _run_cli(argv: list[str], capsys):
    """Run the CLI with the given argv and return (exit_code, out, err)."""
    old_argv = sys.argv
    sys.argv = ["scoutfootball"] + argv
    try:
        main()
        captured = capsys.readouterr()
        return 0, captured.out, captured.err
    except SystemExit as exc:
        captured = capsys.readouterr()
        return exc.code, captured.out, captured.err
    finally:
        sys.argv = old_argv


# ── create-review ─────────────────────────────────────────────────────


class TestCreateReview:
    def test_create_review_from_flags(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-review",
                "--title", "Flag-based review",
                "--briefing-id", "briefing-001",
                "--match-id", "fd-match-64766",
                "--home-team", "Arsenal",
                "--away-team", "Chelsea",
                "--kickoff-at", "2026-08-15T15:00:00+00:00",
                "--competition", "Premier League",
                "--season", "2026-27",
                "--final-score-home", "2",
                "--final-score-away", "1",
            ],
            capsys,
        )
        assert code == 0
        assert "Created review:" in out
        assert "Flag-based review" in out
        assert "Arsenal" in out
        assert "Chelsea" in out

    def test_create_review_json_output(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-review",
                "--title", "JSON review",
                "--home-team", "Arsenal",
                "--away-team", "Chelsea",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        assert record["schema"] == "scoutfootball.opposition-post-match-review-record"
        assert record["review"]["title"] == "JSON review"
        assert record["review"]["status"] == "draft"
        assert record["review"]["decision"] is None
        assert record["server_revision"] == 1

    def test_create_review_from_json_file(self, isolated_data_root, tmp_path, capsys):
        review_file = tmp_path / "review.json"
        review_file.write_text(
            json.dumps(_valid_review_json("review-from-file")), encoding="utf-8"
        )
        code, out, _ = _run_cli(
            ["create-review", "--from-json", str(review_file)],
            capsys,
        )
        assert code == 0
        assert "review-from-file" in out

    def test_create_review_from_json_file_json_output(
        self, isolated_data_root, tmp_path, capsys
    ):
        review_file = tmp_path / "review.json"
        review_file.write_text(
            json.dumps(_valid_review_json("review-from-file-json")), encoding="utf-8"
        )
        code, out, _ = _run_cli(
            ["create-review", "--from-json", str(review_file), "--json"],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        assert record["review"]["review_id"] == "review-from-file-json"
        assert record["review"]["title"] == "CLI test review"

    def test_create_review_decision_forces_finalized_status(
        self, isolated_data_root, capsys
    ):
        code, out, _ = _run_cli(
            [
                "create-review",
                "--title", "Finalized review",
                "--decision", "confirmed",
                "--decision-note", "Hypothesis confirmed by scoreline.",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        assert record["review"]["status"] == "finalized"
        assert record["review"]["decision"] == "confirmed"
        assert record["review"]["decision_note"] == "Hypothesis confirmed by scoreline."

    def test_create_review_explicit_review_id(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-review",
                "--title", "Explicit id",
                "--review-id", "review-explicit-001",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        assert record["review"]["review_id"] == "review-explicit-001"

    def test_create_review_missing_title_exits(self, isolated_data_root, capsys):
        code, _, err = _run_cli(
            ["create-review", "--home-team", "No title"],
            capsys,
        )
        assert code != 0
        assert "--title is required" in err

    def test_create_review_invalid_review_id_exits(
        self, isolated_data_root, capsys
    ):
        code, _, err = _run_cli(
            [
                "create-review",
                "--title", "Bad id",
                "--review-id", "bad/id/with/slashes",
            ],
            capsys,
        )
        assert code != 0
        assert "error" in err.lower()

    def test_create_review_linked_artifacts(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-review",
                "--title", "Linked artifacts",
                "--linked-artifacts", "briefing-001", "scenario-002",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        record = json.loads(out)
        assert record["review"]["linked_artifacts"] == ["briefing-001", "scenario-002"]

    def test_create_review_final_score_displayed(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-review",
                "--title", "Scored match",
                "--final-score-home", "3",
                "--final-score-away", "0",
            ],
            capsys,
        )
        assert code == 0
        assert "final score: 3 - 0" in out


# ── list-reviews ──────────────────────────────────────────────────────


class TestListReviews:
    def test_list_empty_store(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(["list-reviews"], capsys)
        assert code == 0
        assert "No reviews" in out

    def test_list_empty_store_json(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(["list-reviews", "--json"], capsys)
        assert code == 0
        result = json.loads(out)
        assert result["count"] == 0
        assert result["reviews"] == []

    def test_list_after_create(self, isolated_data_root, capsys):
        _run_cli(
            ["create-review", "--title", "First", "--json"],
            capsys,
        )
        _run_cli(
            ["create-review", "--title", "Second", "--json"],
            capsys,
        )
        code, out, _ = _run_cli(["list-reviews", "--json"], capsys)
        assert code == 0
        result = json.loads(out)
        assert result["count"] == 2
        titles = {item["title"] for item in result["reviews"]}
        assert titles == {"First", "Second"}

    def test_list_text_output(self, isolated_data_root, capsys):
        _run_cli(
            ["create-review", "--title", "Text review", "--json"],
            capsys,
        )
        code, out, _ = _run_cli(["list-reviews"], capsys)
        assert code == 0
        assert "Text review" in out
        assert "Found 1 review" in out

    def test_list_includes_status_and_decision(self, isolated_data_root, capsys):
        _run_cli(
            [
                "create-review",
                "--title", "Finalized one",
                "--decision", "confirmed",
                "--json",
            ],
            capsys,
        )
        code, out, _ = _run_cli(["list-reviews"], capsys)
        assert code == 0
        assert "status=finalized" in out
        assert "decision=confirmed" in out


# ── show-review ───────────────────────────────────────────────────────


class TestShowReview:
    def test_show_review_text(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-review",
                "--title", "Show me",
                "--home-team", "Arsenal",
                "--away-team", "Chelsea",
                "--briefing-id", "briefing-show-001",
                "--json",
            ],
            capsys,
        )
        assert code == 0
        create_result = json.loads(out)
        review_id = create_result["review"]["review_id"]

        code, out, _ = _run_cli(["show-review", review_id], capsys)
        assert code == 0
        assert "Show me" in out
        assert "Arsenal" in out
        assert "Chelsea" in out
        assert "briefing-show-001" in out

    def test_show_review_json(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            ["create-review", "--title", "JSON show", "--json"],
            capsys,
        )
        assert code == 0
        create_result = json.loads(out)
        review_id = create_result["review"]["review_id"]

        code, out, _ = _run_cli(["show-review", review_id, "--json"], capsys)
        assert code == 0
        record = json.loads(out)
        assert record["review"]["review_id"] == review_id
        assert record["review"]["title"] == "JSON show"
        assert record["server_revision"] == 1

    def test_show_review_displays_hypothesis_and_evidence(
        self, isolated_data_root, tmp_path, capsys
    ):
        """show-review text output must surface hypothesis, evidence and patterns."""
        payload = _valid_review_json("review-rich-001")
        review_file = tmp_path / "rich.json"
        review_file.write_text(json.dumps(payload), encoding="utf-8")
        _run_cli(["create-review", "--from-json", str(review_file)], capsys)

        code, out, _ = _run_cli(["show-review", "review-rich-001"], capsys)
        assert code == 0
        assert "hypothesis results" in out
        assert "h-001" in out
        assert "right-side overload" in out
        assert "falsified patterns" in out
        assert "p-001" in out
        assert "supporting evidence" in out
        assert "ev-001" in out

    def test_show_review_nonexistent_exits(self, isolated_data_root, capsys):
        code, _, err = _run_cli(["show-review", "nonexistent-id"], capsys)
        assert code != 0
        assert "review_not_found" in err

    def test_show_review_displays_final_score(self, isolated_data_root, capsys):
        code, out, _ = _run_cli(
            [
                "create-review",
                "--title", "Scored",
                "--final-score-home", "2",
                "--final-score-away", "1",
                "--json",
            ],
            capsys,
        )
        review_id = json.loads(out)["review"]["review_id"]
        code, out, _ = _run_cli(["show-review", review_id], capsys)
        assert code == 0
        assert "final score: 2 - 1" in out


# ── validate-review ───────────────────────────────────────────────────


class TestValidateReview:
    def test_validate_valid_review(self, isolated_data_root, tmp_path, capsys):
        review_file = tmp_path / "valid.json"
        review_file.write_text(
            json.dumps(_valid_review_json("review-valid")), encoding="utf-8"
        )
        code, out, _ = _run_cli(["validate-review", str(review_file)], capsys)
        assert code == 0
        assert "VALID" in out
        assert "review-valid" in out

    def test_validate_valid_review_json(self, isolated_data_root, tmp_path, capsys):
        review_file = tmp_path / "valid.json"
        review_file.write_text(
            json.dumps(_valid_review_json("review-valid")), encoding="utf-8"
        )
        code, out, _ = _run_cli(
            ["validate-review", str(review_file), "--json"], capsys
        )
        assert code == 0
        result = json.loads(out)
        assert result["status"] == "valid"
        assert result["review_id"] == "review-valid"

    def test_validate_invalid_review_exits(self, isolated_data_root, tmp_path, capsys):
        bad_payload = _valid_review_json("review-invalid")
        bad_payload["status"] = "bogus_status"
        review_file = tmp_path / "invalid.json"
        review_file.write_text(json.dumps(bad_payload), encoding="utf-8")
        code, _, err = _run_cli(["validate-review", str(review_file)], capsys)
        assert code != 0
        assert "INVALID" in err

    def test_validate_finalized_without_decision_exits(
        self, isolated_data_root, tmp_path, capsys
    ):
        """validate-review must catch semantic errors, not just schema ones."""
        bad_payload = _valid_review_json("review-semantics")
        bad_payload["status"] = "finalized"
        bad_payload["decision"] = None
        review_file = tmp_path / "semantics.json"
        review_file.write_text(json.dumps(bad_payload), encoding="utf-8")
        code, _, err = _run_cli(["validate-review", str(review_file)], capsys)
        assert code != 0
        assert "INVALID" in err

    def test_validate_missing_file_exits(self, isolated_data_root, tmp_path, capsys):
        code, _, err = _run_cli(
            ["validate-review", str(tmp_path / "nonexistent.json")], capsys
        )
        assert code != 0
        assert "error" in err.lower()

    def test_validate_does_not_save(self, isolated_data_root, tmp_path, capsys):
        """validate-review must not write anything to the store."""
        review_file = tmp_path / "valid.json"
        review_file.write_text(
            json.dumps(_valid_review_json("review-nosave")), encoding="utf-8"
        )
        _run_cli(["validate-review", str(review_file)], capsys)
        # list-reviews should still be empty.
        code, out, _ = _run_cli(["list-reviews", "--json"], capsys)
        assert code == 0
        result = json.loads(out)
        assert result["count"] == 0


# ── End-to-end round-trip ─────────────────────────────────────────────


class TestReviewCliRoundTrip:
    """Create → list → show → validate round-trip via the CLI only."""

    def test_create_list_show_round_trip(self, isolated_data_root, tmp_path, capsys):
        # 1. Create from a JSON file with rich content.
        payload = _valid_review_json("review-e2e-001")
        payload["title"] = "End to end"
        payload["status"] = "finalized"
        payload["decision"] = "confirmed"
        payload["decision_note"] = "Hypothesis confirmed."
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            json.dump(payload, handle)
            tmp_json = Path(handle.name)

        try:
            code, out, _ = _run_cli(
                ["create-review", "--from-json", str(tmp_json), "--json"], capsys
            )
            assert code == 0
            created = json.loads(out)
            assert created["review"]["review_id"] == "review-e2e-001"
            assert created["review"]["status"] == "finalized"
            assert created["review"]["decision"] == "confirmed"
        finally:
            tmp_json.unlink(missing_ok=True)

        # 2. List and confirm it appears.
        code, out, _ = _run_cli(["list-reviews", "--json"], capsys)
        assert code == 0
        listed = json.loads(out)
        assert listed["count"] == 1
        assert listed["reviews"][0]["review_id"] == "review-e2e-001"
        assert listed["reviews"][0]["status"] == "finalized"
        assert listed["reviews"][0]["decision"] == "confirmed"

        # 3. Show by id and confirm full payload round-trips.
        code, out, _ = _run_cli(["show-review", "review-e2e-001", "--json"], capsys)
        assert code == 0
        shown = json.loads(out)
        assert shown["review"]["title"] == "End to end"
        assert shown["review"]["decision_note"] == "Hypothesis confirmed."
        assert shown["review"]["hypothesis_results"][0]["hypothesis_id"] == "h-001"

        # 4. Validate the original file again (idempotent).
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            json.dump(payload, handle)
            tmp_json = Path(handle.name)
        try:
            code, out, _ = _run_cli(
                ["validate-review", str(tmp_json), "--json"], capsys
            )
            assert code == 0
            result = json.loads(out)
            assert result["status"] == "valid"
            assert result["review_id"] == "review-e2e-001"
        finally:
            tmp_json.unlink(missing_ok=True)

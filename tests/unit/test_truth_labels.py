"""Tests for truth labels data contract."""

import pandas as pd

from scoutfootball.evaluation.truth_labels import (
    TRUTH_LABELS_COLUMNS,
    TRUTH_LABELS_SCHEMA,
    LabelConfidence,
    LabelSource,
    create_empty_truth_labels,
    validate_truth_labels,
    workspace_to_truth_labels,
)


class TestLabelEnums:
    def test_label_source_values(self) -> None:
        assert LabelSource.TRANSFERMARKT_VALUE.value == "transfermarkt_value"
        assert LabelSource.AWARD.value == "award"
        assert LabelSource.EXPERT_TIER.value == "expert_tier"
        assert LabelSource.MANUAL_CALIBRATION.value == "manual_calibration"
        assert LabelSource.SCOUTING_REVIEW.value == "scouting_review"

    def test_label_confidence_values(self) -> None:
        assert LabelConfidence.HIGH.value == "high"
        assert LabelConfidence.MEDIUM.value == "medium"
        assert LabelConfidence.LOW.value == "low"


class TestSchemaDefinition:
    def test_schema_has_required_columns(self) -> None:
        required = {
            "player_id", "season", "label_source", "label_confidence",
            "label_value", "as_of_date", "position_scope", "manual_review_flag",
        }
        assert required == set(TRUTH_LABELS_SCHEMA.keys())

    def test_columns_list_matches_schema(self) -> None:
        assert TRUTH_LABELS_COLUMNS == list(TRUTH_LABELS_SCHEMA.keys())


class TestCreateEmptyTruthLabels:
    def test_empty_df_has_correct_columns(self) -> None:
        df = create_empty_truth_labels()
        assert list(df.columns) == TRUTH_LABELS_COLUMNS

    def test_empty_df_has_zero_rows(self) -> None:
        df = create_empty_truth_labels()
        assert len(df) == 0

    def test_empty_df_dtypes(self) -> None:
        df = create_empty_truth_labels()
        assert df["player_id"].dtype.name == "string"
        assert df["label_value"].dtype == "float64"
        assert df["manual_review_flag"].dtype == "bool"


class TestValidateTruthLabels:
    def test_valid_labels_pass(self) -> None:
        df = pd.DataFrame({
            "player_id": ["p1", "p2"],
            "season": ["2425", "2425"],
            "label_source": ["transfermarkt_value", "award"],
            "label_confidence": ["high", "medium"],
            "label_value": [50.0, 80.0],
            "as_of_date": ["2025-06-01", "2025-06-01"],
            "position_scope": ["AM", "ST"],
            "manual_review_flag": [False, False],
        })
        errors = validate_truth_labels(df)
        assert errors == []

    def test_missing_columns_detected(self) -> None:
        df = pd.DataFrame({"player_id": ["p1"]})
        errors = validate_truth_labels(df)
        assert any("Missing columns" in e for e in errors)

    def test_invalid_label_source_detected(self) -> None:
        df = create_empty_truth_labels()
        df = pd.concat([df, pd.DataFrame({
            "player_id": ["p1"],
            "season": ["2425"],
            "label_source": ["invalid_source"],
            "label_confidence": ["high"],
            "label_value": [50.0],
            "as_of_date": ["2025-06-01"],
            "position_scope": ["AM"],
            "manual_review_flag": [False],
        })], ignore_index=True)
        errors = validate_truth_labels(df)
        assert any("Invalid label_source" in e for e in errors)

    def test_invalid_confidence_detected(self) -> None:
        df = create_empty_truth_labels()
        df = pd.concat([df, pd.DataFrame({
            "player_id": ["p1"],
            "season": ["2425"],
            "label_source": ["award"],
            "label_confidence": ["ultra"],
            "label_value": [50.0],
            "as_of_date": ["2025-06-01"],
            "position_scope": ["AM"],
            "manual_review_flag": [False],
        })], ignore_index=True)
        errors = validate_truth_labels(df)
        assert any("Invalid label_confidence" in e for e in errors)

    def test_duplicate_records_detected(self) -> None:
        df = pd.DataFrame({
            "player_id": ["p1", "p1"],
            "season": ["2425", "2425"],
            "label_source": ["transfermarkt_value", "transfermarkt_value"],
            "label_confidence": ["high", "high"],
            "label_value": [50.0, 60.0],
            "as_of_date": ["2025-06-01", "2025-06-02"],
            "position_scope": ["AM", "AM"],
            "manual_review_flag": [False, False],
        })
        errors = validate_truth_labels(df)
        assert any("duplicate" in e for e in errors)

    def test_empty_df_passes(self) -> None:
        df = create_empty_truth_labels()
        errors = validate_truth_labels(df)
        assert errors == []


class TestWorkspaceToTruthLabels:
    """Tests for converting scouting workspace decisions to truth labels."""

    def _make_workspace(self, statuses=None, shortlist=None, snapshot_ids=None):
        """Build a minimal valid workspace payload."""
        return {
            "schema": "scoutfootball.scouting-workspace",
            "version": "1.0",
            "audit": {
                "workspace_id": "test-ws",
                "revision": 1,
                "created_at": "2026-07-11T10:00:00Z",
                "updated_at": "2026-07-11T12:00:00Z",
            },
            "review": {
                "statuses": statuses or {},
                "shortlist_notes": {},
                "watchlist_notes": {},
            },
            "selections": {
                "watchlist": [],
                "shortlist": shortlist or [],
            },
            "source": {
                "rating_snapshot_ids": snapshot_ids or [],
            },
            "watchlist_snapshot": {
                "player_keys": [],
                "saved_at": "2026-07-11T10:00:00Z",
            },
            "exported_at": "2026-07-11T12:00:00Z",
        }

    def test_approved_becomes_high_confidence_label(self) -> None:
        ws = self._make_workspace(
            statuses={"player-1": "approved"},
            shortlist=[{"key": "player-1", "player_id": "pid-1", "name": "Alice"}],
        )
        df = workspace_to_truth_labels(ws)
        assert len(df) == 1
        row = df.iloc[0]
        assert row["player_id"] == "pid-1"
        assert row["label_source"] == "scouting_review"
        assert row["label_value"] == 1.0
        assert row["label_confidence"] == "high"
        assert bool(row["manual_review_flag"]) is True

    def test_rejected_becomes_medium_confidence_label(self) -> None:
        ws = self._make_workspace(
            statuses={"player-2": "rejected"},
            shortlist=[{"key": "player-2", "player_id": "pid-2", "name": "Bob"}],
        )
        df = workspace_to_truth_labels(ws)
        assert len(df) == 1
        row = df.iloc[0]
        assert row["label_value"] == 0.0
        assert row["label_confidence"] == "medium"

    def test_pending_and_reviewing_skipped(self) -> None:
        ws = self._make_workspace(
            statuses={
                "p1": "approved",
                "p2": "pending",
                "p3": "reviewing",
                "p4": "rejected",
            },
            shortlist=[
                {"key": "p1", "player_id": "pid-1", "name": "A"},
                {"key": "p2", "player_id": "pid-2", "name": "B"},
                {"key": "p3", "player_id": "pid-3", "name": "C"},
                {"key": "p4", "player_id": "pid-4", "name": "D"},
            ],
        )
        df = workspace_to_truth_labels(ws)
        assert len(df) == 2  # only approved and rejected
        ids = set(df["player_id"])
        assert ids == {"pid-1", "pid-4"}

    def test_no_decisions_returns_empty(self) -> None:
        ws = self._make_workspace(statuses={"p1": "pending"})
        df = workspace_to_truth_labels(ws)
        assert len(df) == 0
        assert list(df.columns) == TRUTH_LABELS_COLUMNS

    def test_season_auto_detected_from_snapshot(self) -> None:
        ws = self._make_workspace(
            statuses={"p1": "approved"},
            shortlist=[{"key": "p1", "player_id": "pid-1", "name": "A"}],
            snapshot_ids=["2526-run-001"],
        )
        df = workspace_to_truth_labels(ws)
        assert df.iloc[0]["season"] == "2526"

    def test_season_override(self) -> None:
        ws = self._make_workspace(
            statuses={"p1": "approved"},
            shortlist=[{"key": "p1", "player_id": "pid-1", "name": "A"}],
        )
        df = workspace_to_truth_labels(ws, default_season="2425")
        assert df.iloc[0]["season"] == "2425"

    def test_player_id_falls_back_to_key(self) -> None:
        """When shortlist doesn't have explicit player_id, use key."""
        ws = self._make_workspace(
            statuses={"my-key": "approved"},
            shortlist=[{"key": "my-key", "name": "Test"}],
        )
        df = workspace_to_truth_labels(ws)
        assert df.iloc[0]["player_id"] == "my-key"

    def test_output_validates(self) -> None:
        """Output should pass validate_truth_labels."""
        ws = self._make_workspace(
            statuses={"p1": "approved", "p2": "rejected"},
            shortlist=[
                {"key": "p1", "player_id": "pid-1", "name": "A"},
                {"key": "p2", "player_id": "pid-2", "name": "B"},
            ],
        )
        df = workspace_to_truth_labels(ws, default_season="2526")
        errors = validate_truth_labels(df)
        assert errors == []

    def test_as_of_date_from_audit(self) -> None:
        ws = self._make_workspace(
            statuses={"p1": "approved"},
            shortlist=[{"key": "p1", "player_id": "pid-1", "name": "A"}],
        )
        df = workspace_to_truth_labels(ws)
        assert "2026-07-11" in df.iloc[0]["as_of_date"]

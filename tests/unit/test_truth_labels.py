"""Tests for truth labels data contract."""

import pandas as pd

from scoutfootball.evaluation.truth_labels import (
    TRUTH_LABELS_COLUMNS,
    TRUTH_LABELS_SCHEMA,
    LabelConfidence,
    LabelSource,
    create_empty_truth_labels,
    validate_truth_labels,
)


class TestLabelEnums:
    def test_label_source_values(self) -> None:
        assert LabelSource.TRANSFERMARKT_VALUE.value == "transfermarkt_value"
        assert LabelSource.AWARD.value == "award"
        assert LabelSource.EXPERT_TIER.value == "expert_tier"
        assert LabelSource.MANUAL_CALIBRATION.value == "manual_calibration"

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

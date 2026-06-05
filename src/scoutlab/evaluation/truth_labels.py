"""Player truth labels data contract and validation."""

from __future__ import annotations

import enum

import pandas as pd


class LabelSource(enum.Enum):
    """Source of the truth label."""

    TRANSFERMARKT_VALUE = "transfermarkt_value"
    AWARD = "award"
    EXPERT_TIER = "expert_tier"
    MANUAL_CALIBRATION = "manual_calibration"


class LabelConfidence(enum.Enum):
    """Confidence level of the truth label."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Schema definition for player_truth_labels
TRUTH_LABELS_SCHEMA: dict[str, str] = {
    "player_id": "string",
    "season": "string",
    "label_source": "string",  # LabelSource enum values
    "label_confidence": "string",  # LabelConfidence enum values
    "label_value": "float64",
    "as_of_date": "string",  # ISO date
    "position_scope": "string",  # e.g., "GK", "CB", "AM", "ST", or "all"
    "manual_review_flag": "bool",
}

TRUTH_LABELS_COLUMNS = list(TRUTH_LABELS_SCHEMA.keys())


def validate_truth_labels(df: pd.DataFrame) -> list[str]:
    """Validate a truth labels DataFrame against the schema.

    Returns a list of error messages. Empty list means valid.
    """
    errors: list[str] = []

    # Check required columns
    missing_cols = set(TRUTH_LABELS_COLUMNS) - set(df.columns)
    if missing_cols:
        errors.append(f"Missing columns: {sorted(missing_cols)}")

    # Check label_source enum values
    valid_sources = {e.value for e in LabelSource}
    if "label_source" in df.columns:
        invalid_sources = set(df["label_source"].unique()) - valid_sources
        if invalid_sources:
            errors.append(
                f"Invalid label_source values: {sorted(invalid_sources)}. "
                f"Valid: {sorted(valid_sources)}"
            )

    # Check label_confidence enum values
    valid_confidences = {e.value for e in LabelConfidence}
    if "label_confidence" in df.columns:
        invalid_confidences = set(df["label_confidence"].unique()) - valid_confidences
        if invalid_confidences:
            errors.append(
                f"Invalid label_confidence values: {sorted(invalid_confidences)}. "
                f"Valid: {sorted(valid_confidences)}"
            )

    # Check no duplicate player_id+season+label_source
    if all(col in df.columns for col in ["player_id", "season", "label_source"]):
        dupes = df.duplicated(subset=["player_id", "season", "label_source"], keep=False)
        if dupes.any():
            n_dupes = int(dupes.sum())
            errors.append(
                f"Found {n_dupes} duplicate player_id+season+label_source records"
            )

    return errors


def create_empty_truth_labels() -> pd.DataFrame:
    """Create an empty truth labels DataFrame with correct schema."""
    return pd.DataFrame(
        {
            "player_id": pd.Series(dtype="string"),
            "season": pd.Series(dtype="string"),
            "label_source": pd.Series(dtype="string"),
            "label_confidence": pd.Series(dtype="string"),
            "label_value": pd.Series(dtype="float64"),
            "as_of_date": pd.Series(dtype="string"),
            "position_scope": pd.Series(dtype="string"),
            "manual_review_flag": pd.Series(dtype="bool"),
        }
    )

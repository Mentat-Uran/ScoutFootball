"""Evaluation package for backtests, calibration, validation and reports."""

from __future__ import annotations

from .availability_diagnostic import (
    AvailabilityDiagnosticReport,
    compute_permutation_importance,
    compute_position_availability_weights,
    compute_team_aggregation_weights,
    generate_availability_diagnostic,
    identify_availability_driven_players,
    save_availability_diagnostic,
)
from .backtests import PoissonBacktestResult, run_poisson_backtest
from .calibration import CalibrationResult, brier_score, calibrate_probabilities_isotonic
from .confidence import (
    COARSE_POSITION_GROUPS,
    MIN_MINUTES_THRESHOLD,
    ConfidenceAssessment,
    assess_batch_confidence,
    assess_player_confidence,
    display_confidence_warnings,
)
from .coverage_confidence import (
    ConfidenceLevel,
    CoverageAssessment,
    add_confidence_to_ratings,
    assess_coverage_batch,
    assess_league_season,
    classify_confidence,
    display_confidence_badge,
)
from .position_metrics import (
    POSITION_DIMENSIONS,
    POSITION_GROUP_MAP,
    PlayerPositionMetrics,
    PositionDimensionScore,
    compute_cross_position_ranking,
    compute_dimension_percentile,
    compute_player_position_metrics,
    compute_position_rankings,
    generate_explanation,
)
from .truth_labels import (
    TRUTH_LABELS_COLUMNS,
    TRUTH_LABELS_SCHEMA,
    LabelConfidence,
    LabelSource,
    create_empty_truth_labels,
    validate_truth_labels,
)
from .validation import (
    ValidationReport,
    run_pre_training_validation,
    validate_date_range,
    validate_no_null_keys,
    validate_parquet_exists,
    validate_row_count,
)

__all__ = [
    "AvailabilityDiagnosticReport",
    "COARSE_POSITION_GROUPS",
    "CalibrationResult",
    "ConfidenceAssessment",
    "ConfidenceLevel",
    "CoverageAssessment",
    "LabelConfidence",
    "LabelSource",
    "MIN_MINUTES_THRESHOLD",
    "PlayerPositionMetrics",
    "PoissonBacktestResult",
    "PositionDimensionScore",
    "POSITION_DIMENSIONS",
    "POSITION_GROUP_MAP",
    "TRUTH_LABELS_COLUMNS",
    "TRUTH_LABELS_SCHEMA",
    "ValidationReport",
    "add_confidence_to_ratings",
    "assess_batch_confidence",
    "assess_coverage_batch",
    "assess_league_season",
    "assess_player_confidence",
    "brier_score",
    "calibrate_probabilities_isotonic",
    "classify_confidence",
    "compute_cross_position_ranking",
    "compute_dimension_percentile",
    "compute_permutation_importance",
    "compute_player_position_metrics",
    "compute_position_availability_weights",
    "compute_position_rankings",
    "compute_team_aggregation_weights",
    "create_empty_truth_labels",
    "display_confidence_badge",
    "display_confidence_warnings",
    "generate_availability_diagnostic",
    "generate_explanation",
    "identify_availability_driven_players",
    "run_poisson_backtest",
    "run_pre_training_validation",
    "save_availability_diagnostic",
    "validate_date_range",
    "validate_no_null_keys",
    "validate_parquet_exists",
    "validate_row_count",
    "validate_truth_labels",
]

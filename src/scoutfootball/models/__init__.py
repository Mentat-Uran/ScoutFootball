"""Models package for supervised and probabilistic baselines."""

from .match_prediction import (
    DixonColesModel,
    EnsemblePrediction,
    IndependentPoissonModel,
    MatchProbabilitySummary,
    PoissonPrediction,
    PredictionConfidenceInterval,
    bootstrap_prediction_confidence,
    compute_form_weights,
    ensemble_prediction,
    fit_dixon_coles,
    fit_dixon_coles_with_form,
    fit_independent_poisson,
    optimize_ensemble_weights,
    predict_match,
    predict_match_dc,
)
from .player_rating_nn import (
    PlayerRatingNNConfig,
    PlayerRatingNNResult,
    train_player_rating_nn,
    train_player_rating_nn_from_files,
)
from .value_fairness import (
    TimeSplitConfig,
    ValueFairnessResult,
    classify_fairness,
    fit_regressor,
)

__all__ = [
    "DixonColesModel",
    "EnsemblePrediction",
    "IndependentPoissonModel",
    "MatchProbabilitySummary",
    "PlayerRatingNNConfig",
    "PlayerRatingNNResult",
    "PoissonPrediction",
    "PredictionConfidenceInterval",
    "TimeSplitConfig",
    "ValueFairnessResult",
    "bootstrap_prediction_confidence",
    "classify_fairness",
    "compute_form_weights",
    "ensemble_prediction",
    "fit_dixon_coles",
    "fit_dixon_coles_with_form",
    "fit_independent_poisson",
    "fit_regressor",
    "optimize_ensemble_weights",
    "predict_match",
    "predict_match_dc",
    "train_player_rating_nn",
    "train_player_rating_nn_from_files",
]

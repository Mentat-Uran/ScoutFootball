"""Models package for supervised and probabilistic baselines."""

from .match_prediction import (
    DixonColesModel,
    IndependentPoissonModel,
    MatchProbabilitySummary,
    PoissonPrediction,
    fit_dixon_coles,
    fit_independent_poisson,
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
    "IndependentPoissonModel",
    "MatchProbabilitySummary",
    "PlayerRatingNNConfig",
    "PlayerRatingNNResult",
    "PoissonPrediction",
    "TimeSplitConfig",
    "ValueFairnessResult",
    "classify_fairness",
    "fit_dixon_coles",
    "fit_independent_poisson",
    "fit_regressor",
    "predict_match",
    "predict_match_dc",
    "train_player_rating_nn",
    "train_player_rating_nn_from_files",
]

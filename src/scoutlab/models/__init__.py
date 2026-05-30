"""Models package for supervised and probabilistic baselines."""

from .match_prediction import (
    IndependentPoissonModel,
    MatchProbabilitySummary,
    PoissonPrediction,
    fit_dixon_coles_placeholder,
    fit_independent_poisson,
    predict_match,
)
from .value_fairness import (
    TimeSplitConfig,
    ValueFairnessResult,
    classify_fairness,
    fit_regressor,
)

__all__ = [
    "IndependentPoissonModel",
    "MatchProbabilitySummary",
    "PoissonPrediction",
    "TimeSplitConfig",
    "ValueFairnessResult",
    "classify_fairness",
    "fit_dixon_coles_placeholder",
    "fit_independent_poisson",
    "fit_regressor",
    "predict_match",
]

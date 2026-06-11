"""Action value module: StatsBomb events -> internal actions -> xT -> VAEP.

This module converts raw event data into standardized internal actions,
then computes expected threat (xT) and VAEP metrics.

Current status: P2 skeleton. StatsBomb Open Data is the first data source.
"""

from scoutfootball.action_value.vaep import (
    compute_vaep_from_actions,
    create_vaep_features,
    create_vaep_labels,
    create_vaep_labels_fast,
    predict_vaep_value,
    train_vaep_model,
)

__all__ = [
    "compute_vaep_from_actions",
    "create_vaep_features",
    "create_vaep_labels",
    "create_vaep_labels_fast",
    "predict_vaep_value",
    "train_vaep_model",
]

"""Player-level truth label anchors for the rating optimizer."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from scoutfootball.evaluation.truth_labels import (
    filter_supervision_eligible_truth_labels,
    truth_label_supervision_report,
)

CONFIDENCE_WEIGHTS = {
    "high": 1.0,
    "medium": 0.65,
    "low": 0.35,
}


def normalize_player_key(value: object) -> str:
    """Normalize player names for cross-artifact matching."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().replace(".", " ").replace("-", " ").split())


def resolve_truth_labels(
    data_dir: Path,
    *,
    labels_path: Path | None = None,
    feature_matrix_path: Path | None = None,
) -> pd.DataFrame:
    """Resolve player truth labels to normalized player-name + season keys.

    The optimizer's FBref/Understat table does not have the same player_id as
    the rating feature matrix. When labels only contain player_id, use
    rating_feature_matrix.parquet as the bridge to player_name and season.
    """
    labels_path = labels_path or data_dir / "gold" / "feature_store" / "player_truth_labels.parquet"
    feature_matrix_path = (
        feature_matrix_path
        or data_dir / "gold" / "feature_store" / "rating_feature_matrix.parquet"
    )
    if not labels_path.exists():
        return pd.DataFrame()

    labels = pd.read_parquet(labels_path)
    if labels.empty:
        return pd.DataFrame()
    required = {"player_id", "season", "label_value", "label_confidence"}
    missing = required - set(labels.columns)
    if missing:
        raise ValueError(f"truth labels missing columns: {sorted(missing)}")

    supervision_report = truth_label_supervision_report(labels)
    work = filter_supervision_eligible_truth_labels(labels)
    work["season"] = work["season"].astype(str)
    work["label_value"] = pd.to_numeric(work["label_value"], errors="coerce")
    work = work[work["label_value"].notna() & np.isfinite(work["label_value"])]
    if work.empty:
        work.attrs["supervision_report"] = supervision_report
        return work

    if "player_name" not in work.columns:
        # Try bridge merge via feature matrix (player_id as key)
        if feature_matrix_path.exists():
            matrix = pd.read_parquet(feature_matrix_path)
            bridge_cols = [
                col
                for col in ["player_id", "season_id", "player_name", "position_group"]
                if col in matrix.columns
            ]
            if not ({"player_id", "season_id", "player_name"} - set(bridge_cols)):
                bridge = matrix[bridge_cols].copy()
                bridge["season"] = bridge["season_id"].astype(str)
                bridge = bridge.drop(columns=["season_id"]).drop_duplicates(
                    subset=["player_id", "season"],
                )
                work = work.merge(bridge, on=["player_id", "season"], how="left")

    # If bridge merge failed, treat player_id as player_name directly
    # (truth labels may store player names in the player_id column)
    if "player_name" not in work.columns or work["player_name"].isna().all():
        work["player_name"] = work["player_id"]

    if "player_name" not in work.columns:
        return pd.DataFrame()
    work = work[work["player_name"].notna()].copy()
    if work.empty:
        return pd.DataFrame()

    work["player_key"] = work["player_name"].map(normalize_player_key)
    work["confidence_weight"] = (
        work["label_confidence"].astype(str).str.lower().map(CONFIDENCE_WEIGHTS).fillna(0.35)
    )
    work = work[work["player_key"] != ""].copy()
    if work.empty:
        return pd.DataFrame()

    def _weighted_label(group: pd.DataFrame) -> float:
        weights = group["confidence_weight"].to_numpy(dtype=float)
        values = group["label_value"].to_numpy(dtype=float)
        if np.sum(weights) <= 0:
            return float(np.mean(values))
        return float(np.average(values, weights=weights))

    grouped = (
        work.groupby(["player_key", "season"], as_index=False)
        .apply(
            lambda g: pd.Series(
                {
                    "label_value": _weighted_label(g),
                    "label_weight": float(g["confidence_weight"].max()),
                    "label_sources": ",".join(sorted(set(g["label_source"].astype(str))))
                    if "label_source" in g.columns
                    else "",
                },
            ),
            include_groups=False,
        )
        .reset_index(drop=True)
    )
    grouped.attrs["supervision_report"] = supervision_report
    return grouped


def build_truth_label_anchor(
    data_dir: Path,
    train_df: pd.DataFrame,
    device: torch.device,
    *,
    min_labels: int = 50,
) -> dict:
    """Build row-indexed truth anchors for a training DataFrame."""
    labels = resolve_truth_labels(data_dir)
    if labels.empty:
        report = labels.attrs.get("supervision_report", {})
        reason = (
            "no supervision-eligible player truth labels"
            if report.get("status") == "no_eligible_labels"
            else "no resolved player truth labels"
        )
        return {
            "enabled": False,
            "reason": reason,
            "n_labels": 0,
            "n_matched": 0,
            "supervision_report": report,
        }

    players = pd.DataFrame(
        {
            "row_idx": np.arange(len(train_df), dtype=np.int64),
            "player_key": train_df["player"].map(normalize_player_key).to_numpy(),
            "season": train_df["season"].astype(str).to_numpy(),
        },
    )
    matched = players.merge(labels, on=["player_key", "season"], how="inner")
    matched = matched.drop_duplicates(subset=["row_idx"])
    n_matched = int(len(matched))
    if n_matched < int(min_labels):
        return {
            "enabled": False,
            "reason": f"matched truth labels below min_labels ({n_matched} < {int(min_labels)})",
            "n_labels": int(len(labels)),
            "n_matched": n_matched,
            "supervision_report": labels.attrs.get("supervision_report", {}),
        }

    return {
        "enabled": True,
        "reason": "enabled",
        "n_labels": int(len(labels)),
        "n_matched": n_matched,
        "supervision_report": labels.attrs.get("supervision_report", {}),
        "row_idx": torch.tensor(matched["row_idx"].to_numpy(), dtype=torch.long, device=device),
        "label_value": torch.tensor(
            matched["label_value"].to_numpy(dtype=np.float32),
            dtype=torch.float32,
            device=device,
        ),
        "label_weight": torch.tensor(
            matched["label_weight"].to_numpy(dtype=np.float32),
            dtype=torch.float32,
            device=device,
        ),
    }

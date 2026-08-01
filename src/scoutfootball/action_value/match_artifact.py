"""Versioned, explicitly sample-bounded player-match xT artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

SCHEMA_VERSION = "scoutfootball.player-match-action-value.v1"
SOURCE = "StatsBomb Open Data"
_REQUIRED = {"match_id", "team_id", "player_id", "minute", "action_type", "xt_delta"}
_ACTION_TYPES = ("pass", "carry", "shot", "dribble", "tackle", "interception")


def _identifier(value: object) -> str:
    if pd.isna(value):
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value)


def _input_hash(frame: pd.DataFrame) -> str:
    relevant = frame[[column for column in sorted(_REQUIRED) if column in frame]].copy()
    return hashlib.sha256(
        pd.util.hash_pandas_object(relevant, index=False).values.tobytes()
    ).hexdigest()


def build_player_match_action_values(
    valued_actions: pd.DataFrame,
    matches: pd.DataFrame | None = None,
    *,
    coverage_scope: str = "sample",
    player_names: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Aggregate valued actions to player-team-match rows with honest coverage metadata."""
    missing = _REQUIRED.difference(valued_actions.columns)
    if valued_actions.empty or missing:
        empty = pd.DataFrame()
        return empty, {
            "schema_version": SCHEMA_VERSION,
            "status": "no_data",
            "coverage_scope": coverage_scope,
            "missing_columns": sorted(missing),
            "player_match_rows": 0,
            "match_count": 0,
        }

    actions = valued_actions.copy()
    for column in ("match_id", "team_id", "player_id"):
        actions[column] = actions[column].map(_identifier)
    actions = actions[actions["player_id"] != ""].copy()
    if actions.empty:
        return build_player_match_action_values(
            pd.DataFrame(), matches, coverage_scope=coverage_scope
        )

    keys = ["player_id", "team_id", "match_id"]
    actions["_positive_xt"] = (
        pd.to_numeric(actions["xt_delta"], errors="coerce").fillna(0).clip(lower=0)
    )
    actions["_negative_xt"] = (
        pd.to_numeric(actions["xt_delta"], errors="coerce").fillna(0).clip(upper=0)
    )
    actions["_minute"] = pd.to_numeric(actions["minute"], errors="coerce").fillna(0)
    action_type = actions["action_type"].astype(str)
    for name in _ACTION_TYPES:
        actions[f"n_{name}"] = (action_type == name).astype("int32")

    aggregate: dict[str, tuple[str, str]] = {
        "n_actions": ("xt_delta", "size"),
        "xt_total": ("xt_delta", "sum"),
        "positive_xt": ("_positive_xt", "sum"),
        "negative_xt": ("_negative_xt", "sum"),
        "first_minute": ("_minute", "min"),
        "last_minute": ("_minute", "max"),
    }
    aggregate.update({f"n_{name}": (f"n_{name}", "sum") for name in _ACTION_TYPES})
    result = actions.groupby(keys, as_index=False).agg(**aggregate)
    result["estimated_minutes"] = (result["last_minute"] - result["first_minute"]).clip(lower=45)
    result["minutes_90"] = result["estimated_minutes"] / 90.0
    result["xt_per_90"] = result["xt_total"] / result["minutes_90"]

    names = (
        actions.loc[
            actions.get("player_name", "").fillna("") != "", ["player_id", "player_name"]
        ].drop_duplicates("player_id")
        if "player_name" in actions
        else pd.DataFrame(columns=["player_id", "player_name"])
    )
    result = result.merge(names, on="player_id", how="left")
    result["player_name"] = result["player_name"].fillna("")
    if player_names:
        result["player_name"] = result["player_name"].mask(
            result["player_name"] == "",
            result["player_id"].map(player_names),
        ).fillna("")

    if matches is not None and not matches.empty and "match_id" in matches:
        metadata_columns = [
            column
            for column in (
                "match_id",
                "match_date",
                "competition_name",
                "season_name",
                "home_team_name",
                "away_team_name",
                "home_score",
                "away_score",
            )
            if column in matches
        ]
        metadata = matches[metadata_columns].copy()
        metadata["match_id"] = metadata["match_id"].map(_identifier)
        result = result.merge(metadata.drop_duplicates("match_id"), on="match_id", how="left")
    for column in (
        "match_date",
        "competition_name",
        "season_name",
        "home_team_name",
        "away_team_name",
    ):
        if column not in result:
            result[column] = ""
        result[column] = result[column].fillna("")

    result["source"] = SOURCE
    result["source_coverage"] = coverage_scope
    result["comparability_note"] = (
        "xT is computed on this artifact input only; do not compare or add it "
        "to a differently scoped xT grid."
    )
    result = result.sort_values(["match_date", "xt_total"], ascending=[False, False]).reset_index(
        drop=True
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "source": SOURCE,
        "coverage_scope": coverage_scope,
        "input_hash": _input_hash(actions),
        "input_action_rows": int(len(actions)),
        "player_match_rows": int(len(result)),
        "match_count": int(result["match_id"].nunique()),
        "competition_count": int(result["competition_name"].replace("", pd.NA).nunique()),
        "comparability_note": result["comparability_note"].iloc[0],
    }
    return result, manifest


def save_player_match_action_values(
    frame: pd.DataFrame, manifest: dict[str, Any], output_path: Path
) -> None:
    """Persist the Parquet artifact and adjacent JSON manifest atomically enough for local use."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_path, index=False)
    output_path.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

"""Build non-additive player action-value research dossiers."""

from __future__ import annotations

from typing import Any

import pandas as pd

from scoutfootball.action_value.identity import _identifier, _text

CONTEXT_SCHEMA = "scoutfootball.action-value-player-context"
CONTEXT_VERSION = "1.0.0"


def _records(frame: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    available = [column for column in columns if column in frame.columns]
    if frame.empty:
        return []
    return frame.loc[:, available].to_dict(orient="records")


def _sorted(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    present = [column for column in columns if column in frame.columns]
    return frame.sort_values(present, ascending=False) if present else frame


def build_player_action_value_context(
    player_id: str,
    xt_rows: pd.DataFrame,
    vaep_rows: pd.DataFrame,
    match_rows: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Return one player's model-specific rows without combining their values.

    xT and VAEP use different aggregation keys.  This helper deliberately
    returns separate model sections and a machine-readable comparability rule
    so callers cannot accidentally turn the output into a summed score.
    """
    normalized_id = _identifier(player_id)
    if not normalized_id:
        return {
            "schema": CONTEXT_SCHEMA,
            "version": CONTEXT_VERSION,
            "status": "invalid_player_id",
            "player_id": "",
            "models": {},
            "match_sample": {"status": "not_available", "rows": []},
        }

    def matching(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty or "player_id" not in frame.columns:
            return pd.DataFrame()
        result = frame.copy()
        result["player_id"] = result["player_id"].map(_identifier)
        return result.loc[result["player_id"] == normalized_id].copy()

    xt = matching(xt_rows)
    vaep = matching(vaep_rows)
    sample = matching(match_rows if match_rows is not None else pd.DataFrame())
    names = [
        _text(value)
        for frame in (xt, vaep, sample)
        if "player_name" in frame.columns
        for value in frame["player_name"].tolist()
        if _text(value)
    ]
    player_name = names[0] if names else ""

    xt_columns = [
        "player_id",
        "player_name",
        "team_id",
        "team_name",
        "season",
        "competition",
        "estimated_minutes",
        "n_matches",
        "n_actions",
        "xt_total",
        "xt_per_90",
    ]
    vaep_columns = [
        "player_id",
        "player_name",
        "team_id",
        "team_name",
        "season_context",
        "competition_context",
        "season_count",
        "competition_count",
        "estimated_minutes",
        "n_matches",
        "n_actions",
        "vaep_total",
        "vaep_per_90",
        "identity_status",
    ]
    sample_columns = [
        "match_id",
        "match_date",
        "competition_name",
        "season_name",
        "home_team_name",
        "away_team_name",
        "home_score",
        "away_score",
        "estimated_minutes",
        "n_actions",
        "xt_total",
        "xt_per_90",
        "source_coverage",
        "comparability_note",
    ]
    xt_records = _records(_sorted(xt, ["season", "competition"]), xt_columns)
    vaep_records = _records(_sorted(vaep, ["vaep_per_90"]), vaep_columns)
    sample_records = _records(_sorted(sample, ["match_date"]), sample_columns)
    status = "ok" if xt_records or vaep_records or sample_records else "not_found"
    return {
        "schema": CONTEXT_SCHEMA,
        "version": CONTEXT_VERSION,
        "status": status,
        "player_id": normalized_id,
        "player_name": player_name,
        "models": {
            "xt": {
                "status": "available" if xt_records else "not_available",
                "granularity": "player_team_season",
                "rows": xt_records,
                "interpretation": "Each xT row is a player-team-season sample.",
            },
            "vaep": {
                "status": "available" if vaep_records else "not_available",
                "granularity": "player_team_career",
                "rows": vaep_records,
                "interpretation": (
                    "VAEP rows are player-team career aggregates; season fields are "
                    "coverage context only."
                ),
            },
        },
        "match_sample": {
            "status": "available" if sample_records else "not_available",
            "coverage_scope": "sample",
            "rows": sample_records,
            "interpretation": "Match xT is recomputed from the tracked sample only.",
        },
        "comparability": {
            "direct_numeric_comparison": False,
            "additive": False,
            "reason": (
                "xT is player-team-season, VAEP is player-team career, and match evidence "
                "uses a separately recomputed sample xT grid. Display them side by side only."
            ),
        },
    }

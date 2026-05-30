"""Team-match feature builders."""

from __future__ import annotations

import pandas as pd

TEAM_STAT_ALIASES = {
    "shots": ("shots", "shot", "sh"),
    "shots_on_target": ("shots_on_target", "sot", "shots_ot", "shot_on_target"),
    "xg": ("xg", "expected_goals"),
}


def build_team_match_features(
    matches_df: pd.DataFrame,
    *,
    elo_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build per-team match features from match-level rows."""

    required = {
        "match_id",
        "match_date",
        "home_team_id",
        "away_team_id",
        "home_goals",
        "away_goals",
    }
    missing = sorted(required.difference(matches_df.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"matches_df is missing required columns: {missing_text}")

    matches = matches_df.copy()
    matches["match_date"] = pd.to_datetime(matches["match_date"], errors="raise")

    stat_columns = _resolve_team_stat_columns(matches.columns)
    home_rows = _build_side_rows(
        matches,
        side="home",
        opponent_side="away",
        stat_columns=stat_columns,
    )
    away_rows = _build_side_rows(
        matches,
        side="away",
        opponent_side="home",
        stat_columns=stat_columns,
    )
    team_match = pd.concat((home_rows, away_rows), ignore_index=True, sort=False)
    team_match = team_match.sort_values(
        ["team_id", "match_date", "match_id"],
    ).reset_index(drop=True)
    team_match["rest_days"] = (
        team_match.groupby("team_id")["match_date"].diff().dt.total_seconds().div(86400.0)
    )

    if elo_df is not None:
        team_match = _merge_pre_match_elo(team_match, elo_df)
    else:
        team_match["elo_pre"] = pd.NA
        team_match["opponent_elo_pre"] = pd.NA
        team_match["elo_diff"] = pd.NA

    return team_match


def _build_side_rows(
    matches: pd.DataFrame,
    *,
    side: str,
    opponent_side: str,
    stat_columns: dict[str, str | None],
) -> pd.DataFrame:
    prefix = f"{side}_"
    opponent_prefix = f"{opponent_side}_"
    result = pd.DataFrame(
        {
            "match_id": matches["match_id"],
            "match_date": matches["match_date"],
            "competition_id": matches.get("competition_id"),
            "season_id": matches.get("season_id"),
            "team_id": matches[f"{side}_team_id"],
            "opponent_team_id": matches[f"{opponent_side}_team_id"],
            "is_home": side == "home",
            "goals_for": matches[f"{side}_goals"],
            "goals_against": matches[f"{opponent_side}_goals"],
        },
    )
    result["goal_diff"] = result["goals_for"] - result["goals_against"]
    result["result_points"] = result["goal_diff"].map(
        lambda diff: 3 if diff > 0 else (1 if diff == 0 else 0),
    )

    for stat_name, alias in stat_columns.items():
        if alias is None:
            result[stat_name] = pd.NA
            if stat_name == "xg":
                result[f"{stat_name}_against"] = pd.NA
                result[f"has_{stat_name}_data"] = False
            else:
                result[f"has_{stat_name}_data"] = False
            continue

        side_column = f"{prefix}{alias}"
        opponent_column = f"{opponent_prefix}{alias}"
        result[stat_name] = matches[side_column]
        if stat_name == "xg":
            result["xg_against"] = matches[opponent_column]
            result["xg_diff"] = result["xg"] - result["xg_against"]
            result["has_xg_data"] = result["xg"].notna()
        else:
            result[f"has_{stat_name}_data"] = result[stat_name].notna()

    return result


def _resolve_team_stat_columns(columns: pd.Index) -> dict[str, str | None]:
    resolved: dict[str, str | None] = {}
    for stat_name, aliases in TEAM_STAT_ALIASES.items():
        chosen = None
        for alias in aliases:
            if f"home_{alias}" in columns and f"away_{alias}" in columns:
                chosen = alias
                break
        resolved[stat_name] = chosen
    return resolved


def _merge_pre_match_elo(team_match: pd.DataFrame, elo_df: pd.DataFrame) -> pd.DataFrame:
    prepared = team_match.copy()
    prepared["match_date"] = pd.to_datetime(prepared["match_date"], errors="raise")

    ratings = elo_df.copy()
    date_column = _find_first_column(ratings, ["rating_date", "date", "from"])
    team_column = _find_first_column(ratings, ["team_id", "club", "Club", "team"])
    elo_column = _find_first_column(ratings, ["elo", "Elo"])
    if date_column is None or team_column is None or elo_column is None:
        raise ValueError("elo_df must contain rating date, team identifier, and elo columns")

    ratings = ratings.rename(
        columns={
            date_column: "rating_date",
            team_column: "rating_team_id",
            elo_column: "elo_value",
        },
    )
    ratings["rating_date"] = pd.to_datetime(ratings["rating_date"], errors="raise")
    ratings = ratings.sort_values(["rating_team_id", "rating_date"]).reset_index(drop=True)

    prepared = prepared.reset_index().rename(columns={"index": "_row_order"})
    team_merged = _merge_entity_elo(
        prepared,
        ratings,
        entity_column="team_id",
        output_column="elo_pre",
    )
    opponent_merged = _merge_entity_elo(
        team_merged,
        ratings,
        entity_column="opponent_team_id",
        output_column="opponent_elo_pre",
    )
    opponent_merged["elo_diff"] = (
        opponent_merged["elo_pre"] - opponent_merged["opponent_elo_pre"]
    )
    return opponent_merged.drop(columns="_row_order").sort_values(
        ["team_id", "match_date", "match_id"],
    ).reset_index(drop=True)


def _merge_entity_elo(
    team_match: pd.DataFrame,
    ratings: pd.DataFrame,
    *,
    entity_column: str,
    output_column: str,
) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for entity_id, subset in team_match.groupby(entity_column, sort=False, dropna=False):
        ordered_subset = subset.sort_values("match_date").copy()
        candidate_ratings = ratings.loc[
            ratings["rating_team_id"] == entity_id,
            ["rating_date", "elo_value"],
        ].sort_values("rating_date")
        if candidate_ratings.empty:
            ordered_subset[output_column] = pd.NA
            pieces.append(ordered_subset)
            continue
        merged = pd.merge_asof(
            ordered_subset,
            candidate_ratings,
            left_on="match_date",
            right_on="rating_date",
            direction="backward",
            allow_exact_matches=True,
        )
        merged[output_column] = merged["elo_value"]
        pieces.append(merged.drop(columns=["rating_date", "elo_value"]))
    return pd.concat(pieces, ignore_index=True, sort=False).sort_values("_row_order")


def _find_first_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    return None

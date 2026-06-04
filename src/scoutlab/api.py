"""FastAPI service layer draft for ScoutLab."""

from __future__ import annotations

from dataclasses import dataclass

from scoutlab.app.data_loader import (
    data_source_label,
    load_oof_predictions,
    load_player_match,
    load_score_prediction,
    load_team_match,
)


@dataclass(frozen=True)
class HealthResponse:
    status: str
    data_source: str
    version: str


@dataclass(frozen=True)
class PlayerListResponse:
    player_count: int
    players: list[str]


def health_check() -> HealthResponse:
    from scoutlab import __version__

    return HealthResponse(
        status="ok",
        data_source=data_source_label(),
        version=__version__,
    )


def list_players() -> PlayerListResponse:
    df = load_player_match()
    if "player_name" not in df.columns:
        return PlayerListResponse(player_count=0, players=[])
    names = sorted(df["player_name"].dropna().unique().tolist())
    return PlayerListResponse(player_count=len(names), players=names[:100])


def list_teams() -> list[str]:
    df = load_team_match()
    if "team_name" in df.columns:
        return sorted(df["team_name"].dropna().unique().tolist())[:100]
    return []


def get_match_prediction(home_team: str, away_team: str) -> dict:
    try:
        prediction = load_score_prediction(home_team, away_team)
    except ValueError as exc:
        return {"error": str(exc)}
    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_lambda": prediction.home_lambda,
        "away_lambda": prediction.away_lambda,
        "home_win": prediction.summary.home_win,
        "draw": prediction.summary.draw,
        "away_win": prediction.summary.away_win,
        "over_2_5": prediction.summary.over_2_5,
        "btts_yes": prediction.summary.btts_yes,
    }


def get_value_summary() -> dict:
    oof = load_oof_predictions()
    if oof.empty:
        return {"status": "no_data"}
    return {
        "sample_count": len(oof),
        "fairness_distribution": oof["fairness_label"].value_counts().to_dict()
        if "fairness_label" in oof.columns
        else {},
        "mean_residual_log": float(oof["residual_log"].mean())
        if "residual_log" in oof.columns
        else None,
    }

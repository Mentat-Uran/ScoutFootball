"""FastAPI application factory for ScoutLab API server."""

from __future__ import annotations

from fastapi import FastAPI

from scoutlab.api import (
    get_match_prediction,
    get_value_summary,
    health_check,
    list_players,
    list_teams,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="ScoutLab API",
        version="0.2.0",
        description="Local-first football data research platform API",
    )

    @app.get("/health")
    def health():
        return health_check()

    @app.get("/players")
    def players():
        return list_players()

    @app.get("/teams")
    def teams():
        return list_teams()

    @app.get("/prediction/{home_team}/{away_team}")
    def prediction(home_team: str, away_team: str):
        return get_match_prediction(home_team, away_team)

    @app.get("/value-summary")
    def value_summary():
        return get_value_summary()

    return app

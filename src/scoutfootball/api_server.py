"""FastAPI application factory for ScoutFootball API server."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from scoutfootball import __version__
from scoutfootball.api import (
    _clean_json_value,
    _settings,
    apply_wc_knockout_result,
    apply_wc_tournament_result,
    clear_wc_knockout_result,
    clear_wc_tournament_result,
    export_wc_tournament_state,
    generate_wc_knockout_bracket,
    get_action_value_evidence,
    get_action_value_evidence_index,
    get_action_value_summary,
    get_artifacts_summary,
    get_backtest_comparison,
    get_calibration_comparison,
    get_calibration_drift,
    get_calibration_drift_heatmap,
    get_calibration_drift_timeline,
    get_ci_coverage,
    get_confidence_distribution,
    get_confidence_interval_plot,
    get_decay_tuning,
    get_ensemble_attribution,
    get_ensemble_attribution_ci,
    get_ensemble_prediction,
    get_ensemble_weights,
    get_error_analysis,
    get_feature_importance,
    get_fold_comparison,
    get_form_weighted_prediction,
    get_h2h_bias_correction,
    get_head_to_head,
    get_league_error_analysis,
    get_match_momentum,
    get_match_prediction,
    get_match_prediction_dc,
    get_model_comparison,
    get_model_run_detail,
    get_model_runs,
    get_outcome_distribution,
    get_player_comparison,
    get_player_profile,
    get_player_ratings,
    get_prediction_attribution,
    get_prediction_attribution_ci,
    get_prediction_calibration,
    get_prediction_diagnostics,
    get_prediction_staleness,
    get_prediction_summary,
    get_probability_heatmap,
    get_ratings_meta,
    get_reliability_diagram,
    get_review_queue,
    get_scoreline_calibration,
    get_shortlist,
    get_team_accuracy,
    get_team_comparison,
    get_team_strength,
    get_temporal_validation,
    get_value_bet_analysis,
    get_value_summary,
    get_watchlist,
    get_wc_group_stage_simulation,
    get_wc_groups,
    get_wc_knockout,
    get_wc_knockout_bracket,
    get_wc_knockout_probabilities,
    get_wc_knockout_scenarios,
    get_wc_predictions,
    get_wc_schedule,
    get_wc_squad,
    get_wc_team_outlook,
    get_wc_teams,
    get_wc_tournament_matches,
    get_wc_tournament_scenarios,
    get_wc_tournament_standings,
    get_wc_tournament_summary,
    get_world_cup_match_briefing,
    get_world_cup_match_prediction,
    health_check,
    import_wc_tournament_state,
    list_players,
    list_teams,
    reset_wc_tournament,
    search_players_and_teams,
)
from scoutfootball.storage.scouting_workspace import (
    MAX_WORKSPACE_BYTES,
    WORKSPACE_SCHEMA,
    ScoutingWorkspaceStore,
    WorkspaceStoreError,
    is_loopback_client,
    remote_workspace_access_enabled,
    workspace_persistence_enabled,
)

_DEFAULT_CORS_ORIGINS = [
    "https://scoutfootball.vercel.app",
    "https://scoutfootball-for-world-cup.vercel.app",
    "http://localhost:8600",
    "http://127.0.0.1:8600",
    "http://localhost:8601",
    "http://127.0.0.1:8601",
    "http://localhost:8000",
]


def _cors_origins() -> list[str]:
    """Read allowed CORS origins from SCOUTFOOTBALL_CORS_ORIGINS env var."""
    raw = os.environ.get("SCOUTFOOTBALL_CORS_ORIGINS", "")
    if raw.strip():
        return [o.strip() for o in raw.split(",") if o.strip()]
    return _DEFAULT_CORS_ORIGINS


def _scouting_workspace_store() -> ScoutingWorkspaceStore:
    return ScoutingWorkspaceStore(_settings().report_root / "scouting" / "workspaces")


def _workspace_access_allowed(request: Request) -> bool:
    host = request.client.host if request.client else None
    return is_loopback_client(host) or remote_workspace_access_enabled()


def _require_workspace_access(request: Request) -> None:
    if not workspace_persistence_enabled():
        raise HTTPException(
            status_code=403,
            detail={"code": "workspace_persistence_disabled"},
        )
    if not _workspace_access_allowed(request):
        raise HTTPException(
            status_code=403,
            detail={"code": "workspace_remote_access_denied"},
        )


def _workspace_error(exc: WorkspaceStoreError) -> HTTPException:
    return HTTPException(
        status_code=exc.http_status,
        detail={"code": exc.code, **exc.metadata},
    )


def _parse_if_match(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip()
    if normalized.startswith("W/"):
        normalized = normalized[2:]
    normalized = normalized.strip('"')
    try:
        revision = int(normalized)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "workspace_if_match_invalid"},
        ) from exc
    if revision < 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "workspace_if_match_invalid"},
        )
    return revision


def _workspace_record_response(record: dict) -> dict:
    return {
        "status": "ok",
        "server_revision": record["server_revision"],
        "stored_at": record["stored_at"],
        "workspace": record["workspace"],
    }


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Startup: warm up World Cup cache to avoid 40-50s first-request delay
    import logging
    logger = logging.getLogger(__name__)
    try:
        import time

        from scoutfootball.api import _get_wc_enriched_squads

        t0 = time.time()
        _get_wc_enriched_squads()
        logger.info("WC cache warmed up in %.1fs", time.time() - t0)
    except Exception as e:
        logger.warning("WC cache warmup failed (will compute on first request): %s", e)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="ScoutFootball API",
        version=__version__,
        description="Local-first football data research platform API",
        lifespan=_lifespan,
    )

    # Configurable CORS — set SCOUTFOOTBALL_CORS_ORIGINS env var for production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Global exception handler — return JSON instead of raw traceback
    import logging

    from fastapi.responses import JSONResponse

    logger = logging.getLogger(__name__)

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

    @app.get("/health")
    def health():
        return health_check()

    @app.get("/license")
    def license_info():
        artifacts = get_artifacts_summary()
        artifact_list = artifacts.get("artifacts", [])
        updated = artifact_list[0].get("updated_at") if artifact_list else None
        return {
            "license_attribution": artifacts.get("license_attribution", {}),
            "data_source_label": artifacts.get("data_source_label", ""),
            "updated_at": updated,
        }

    @app.get("/players")
    def players():
        return list_players()

    @app.get("/search")
    def search_suggestions(q: str = "", type: str = "all", limit: int = 10):
        return search_players_and_teams(q, type, limit)

    @app.get("/teams")
    def teams_list():
        return {"teams": list_teams()}

    @app.get("/teams/strength")
    def teams_strength(
        league: str | None = None,
        season: str | None = None,
        limit: int = 100,
    ):
        return get_team_strength(league=league, season=season, limit=limit)

    @app.get("/teams/compare")
    def teams_compare(a: str, b: str):
        return get_team_comparison(a, b)

    @app.get("/predictions/ensemble/weights")
    def predictions_ensemble_weights():
        return get_ensemble_weights()

    @app.get("/predictions/calibration/comparison")
    def predictions_calibration_comparison():
        return get_calibration_comparison()

    @app.get("/predictions/calibration/reliability")
    def predictions_calibration_reliability(n_bins: int = Query(10, ge=2, le=50)):
        return get_reliability_diagram(n_bins=n_bins)

    @app.get("/predictions/team-accuracy/{team_id}")
    def predictions_team_accuracy(
        team_id: str,
        min_predictions: int = Query(3, ge=1, le=100),
    ):
        return get_team_accuracy(team_id, min_predictions=min_predictions)

    @app.get("/predictions/models/comparison")
    def predictions_models_comparison():
        return get_model_comparison()

    @app.get("/predictions/calibration/scoreline")
    def predictions_calibration_scoreline(
        max_scoreline: int = Query(5, ge=1, le=10),
        min_samples: int = Query(3, ge=1, le=100),
    ):
        return get_scoreline_calibration(
            max_scoreline=max_scoreline, min_samples=min_samples,
        )

    @app.get("/predictions/calibration/confidence-distribution")
    def predictions_calibration_confidence_distribution(
        n_bins: int = Query(10, ge=2, le=50),
        min_samples_per_bucket: int = Query(5, ge=1, le=100),
    ):
        return get_confidence_distribution(
            n_bins=n_bins, min_samples_per_bucket=min_samples_per_bucket,
        )

    @app.get("/predictions/calibration/error-analysis")
    def predictions_calibration_error_analysis(
        n_bins: int = Query(5, ge=2, le=20),
        min_samples_per_bucket: int = Query(5, ge=1, le=100),
        top_n: int = Query(5, ge=1, le=50),
    ):
        return get_error_analysis(
            n_bins=n_bins,
            min_samples_per_bucket=min_samples_per_bucket,
            top_n=top_n,
        )

    @app.get("/predictions/calibration/outcome-distribution")
    def predictions_calibration_outcome_distribution():
        return get_outcome_distribution()

    @app.get("/predictions/calibration/temporal-validation")
    def predictions_calibration_temporal_validation(
        n_windows: int = Query(6, ge=2, le=20),
        min_samples_per_window: int = Query(10, ge=1, le=100),
    ):
        return get_temporal_validation(
            n_windows=n_windows,
            min_samples_per_window=min_samples_per_window,
        )

    @app.get("/predictions/calibration/probability-heatmap")
    def predictions_calibration_probability_heatmap(
        n_bins: int = Query(5, ge=2, le=15),
        min_samples_per_cell: int = Query(3, ge=1, le=100),
    ):
        return get_probability_heatmap(
            n_bins=n_bins,
            min_samples_per_cell=min_samples_per_cell,
        )

    @app.get("/predictions/staleness")
    def predictions_staleness():
        return get_prediction_staleness()

    @app.get("/predictions/calibration/ci-plot")
    def predictions_calibration_ci_plot(
        max_points: int = Query(500, ge=10, le=5000),
        ci_lower_col: str = Query("home_win_ci_lower", max_length=64),
        ci_upper_col: str = Query("home_win_ci_upper", max_length=64),
    ):
        return get_confidence_interval_plot(
            max_points=max_points,
            ci_lower_col=ci_lower_col,
            ci_upper_col=ci_upper_col,
        )

    @app.get("/predictions/calibration/fold-comparison")
    def predictions_calibration_fold_comparison(
        min_samples_per_fold: int = Query(5, ge=1, le=100),
    ):
        return get_fold_comparison(min_samples_per_fold=min_samples_per_fold)

    @app.get("/predictions/calibration/league-errors")
    def predictions_calibration_league_errors(
        min_matches_per_league: int = Query(10, ge=1, le=200),
        top_n: int = Query(3, ge=1, le=20),
    ):
        return get_league_error_analysis(
            min_matches_per_league=min_matches_per_league,
            top_n=top_n,
        )

    @app.get("/predictions/calibration/feature-importance")
    def predictions_calibration_feature_importance(
        n_bins: int = Query(5, ge=2, le=20),
        min_samples_per_bin: int = Query(10, ge=1, le=100),
    ):
        return get_feature_importance(
            n_bins=n_bins,
            min_samples_per_bin=min_samples_per_bin,
        )

    @app.get("/predictions/calibration/ci-coverage")
    def predictions_calibration_ci_coverage(
        ci_lower_col: str = Query("home_win_ci_lower", max_length=64),
        ci_upper_col: str = Query("home_win_ci_upper", max_length=64),
        nominal_level: float | None = Query(None, ge=0.0, le=1.0),
        n_bins: int = Query(5, ge=2, le=20),
        min_samples_per_bucket: int = Query(10, ge=1, le=100),
    ):
        return get_ci_coverage(
            ci_lower_col=ci_lower_col,
            ci_upper_col=ci_upper_col,
            nominal_level=nominal_level,
            n_bins=n_bins,
            min_samples_per_bucket=min_samples_per_bucket,
        )

    @app.get("/predictions/calibration/drift-heatmap")
    def predictions_calibration_drift_heatmap(
        window_size: str = Query("90D", max_length=16),
        n_confidence_bins: int = Query(4, ge=2, le=15),
        min_samples_per_cell: int = Query(5, ge=1, le=100),
    ):
        return get_calibration_drift_heatmap(
            window_size=window_size,
            n_confidence_bins=n_confidence_bins,
            min_samples_per_cell=min_samples_per_cell,
        )

    @app.get("/predictions/{home_team}/{away_team}/attribution")
    def predictions_attribution(home_team: str, away_team: str):
        return get_prediction_attribution(home_team, away_team)

    @app.get("/predictions/{home_team}/{away_team}/attribution/ci")
    def predictions_attribution_ci(
        home_team: str, away_team: str,
        n_bootstrap: int = Query(30, ge=5, le=100),
    ):
        return get_prediction_attribution_ci(
            home_team, away_team, n_bootstrap=n_bootstrap,
        )

    @app.get("/predictions/{home_team}/{away_team}/ensemble-attribution")
    def predictions_ensemble_attribution(home_team: str, away_team: str):
        return get_ensemble_attribution(home_team, away_team)

    @app.get("/predictions/{home_team}/{away_team}/ensemble-attribution/ci")
    def predictions_ensemble_attribution_ci(
        home_team: str, away_team: str,
        n_bootstrap: int = Query(30, ge=5, le=100),
    ):
        return get_ensemble_attribution_ci(
            home_team, away_team, n_bootstrap=n_bootstrap,
        )

    @app.get("/predictions/{home_team}/{away_team}/diagnostics")
    def predictions_diagnostics(home_team: str, away_team: str):
        return get_prediction_diagnostics(home_team, away_team)

    @app.get("/predictions/{home_team}/{away_team}/value")
    def predictions_value(
        home_team: str,
        away_team: str,
        home_odds: float = Query(..., ge=1.0, le=1000.0),
        draw_odds: float = Query(..., ge=1.0, le=1000.0),
        away_odds: float = Query(..., ge=1.0, le=1000.0),
    ):
        return get_value_bet_analysis(
            home_team, away_team,
            home_odds=home_odds, draw_odds=draw_odds, away_odds=away_odds,
        )

    @app.get("/predictions/{home_team}/{away_team}/h2h-bias-correction")
    def predictions_h2h_bias_correction(
        home_team: str,
        away_team: str,
        max_correction: float = Query(0.10, ge=0.0, le=0.30),
        min_meetings: int = Query(3, ge=1, le=50),
        blend_weight: float = Query(0.25, ge=0.0, le=1.0),
    ):
        return get_h2h_bias_correction(
            home_team, away_team,
            max_correction=max_correction,
            min_meetings=min_meetings,
            blend_weight=blend_weight,
        )

    @app.get("/predictions/{home_team}/{away_team}")
    def predictions(
        home_team: str,
        away_team: str,
        model: str = "poisson",
        recalibrate: bool = Query(False, description="Apply isotonic recalibration to ensemble"),
    ):
        if model == "dixon_coles":
            return get_match_prediction_dc(home_team, away_team)
        if model == "form":
            return get_form_weighted_prediction(home_team, away_team)
        if model == "ensemble":
            return get_ensemble_prediction(home_team, away_team, recalibrate=recalibrate)
        return get_match_prediction(home_team, away_team)

    @app.get("/predictions/{home_team}/{away_team}/h2h")
    def predictions_h2h(
        home_team: str,
        away_team: str,
        limit: int = Query(10, ge=1, le=100),
        form_limit: int = Query(10, ge=1, le=50),
    ):
        return get_head_to_head(home_team, away_team, limit=limit, form_limit=form_limit)

    @app.get("/predictions/{home_team}/{away_team}/momentum")
    def predictions_momentum(
        home_team: str,
        away_team: str,
        home_goals: int = Query(0, ge=0, le=20),
        away_goals: int = Query(0, ge=0, le=20),
        minute: int = Query(0, ge=0, le=120),
    ):
        return get_match_momentum(
            home_team, away_team,
            home_goals=home_goals, away_goals=away_goals, minute=minute,
        )

    @app.get("/predictions/meta")
    def predictions_meta():
        return get_prediction_summary()

    @app.get("/predictions/calibration")
    def predictions_calibration():
        return get_prediction_calibration()

    @app.get("/predictions/backtest")
    def predictions_backtest():
        return get_backtest_comparison()

    @app.get("/predictions/tuning")
    def predictions_tuning():
        return get_decay_tuning()

    @app.get("/predictions/drift")
    def predictions_drift():
        return get_calibration_drift()

    @app.get("/predictions/drift/timeline")
    def predictions_drift_timeline():
        return get_calibration_drift_timeline()

    @app.get("/value-summary")
    def value_summary():
        return get_value_summary()

    @app.get("/action-values")
    def action_values(limit: int = 20, offset: int = 0):
        return get_action_value_summary(limit=limit, offset=offset)

    @app.get("/action-values/evidence")
    def action_value_evidence_index():
        return get_action_value_evidence_index()

    @app.get("/action-values/evidence/{player_id}")
    def action_value_evidence(player_id: str):
        return get_action_value_evidence(player_id)

    @app.get("/action-values/matches")
    def player_match_action_values(limit: int = 100, offset: int = 0):
        from scoutfootball.api import get_player_match_action_values
        return get_player_match_action_values(limit=limit, offset=offset)

    @app.get("/ratings")
    def ratings(
        position: str | None = None,
        league: str | None = None,
        team: str | None = None,
        season: str | None = None,
        limit: int = 20000,
    ):
        return get_player_ratings(
            position=position, league=league, team=team, season=season, limit=limit,
        )

    @app.get("/ratings/snapshots")
    def rating_snapshots(
        position: str | None = None,
        league: str | None = None,
        team: str | None = None,
        season: str | None = None,
        limit: int = 20000,
    ):
        return get_player_ratings(
            position=position, league=league, team=team, season=season, limit=limit,
        )

    @app.get("/ratings/meta")
    def ratings_meta():
        return get_ratings_meta()

    @app.get("/players/compare")
    def players_compare(a: str, b: str):
        return get_player_comparison(a, b)

    @app.get("/players/{player_name}/similar")
    def players_similar(
        player_name: str,
        season: str | None = None,
        limit: int = 10,
        same_position_only: bool = True,
        league: str | None = None,
        min_minutes: float | None = None,
    ):
        from scoutfootball.api import find_similar_players
        return find_similar_players(
            player_name,
            season=season,
            limit=limit,
            same_position_only=same_position_only,
            league=league,
            min_minutes=min_minutes,
        )

    @app.get("/player/{player_name}/profile")
    def player_profile(player_name: str, season: str | None = None):
        return get_player_profile(player_name, season=season)

    @app.get("/players/{player_name}")
    def player_detail(
        player_name: str,
        season: str | None = None,
        position_group: str | None = None,
        limit: int = 50,
        offset: int = 0,
        format: str = "json",
    ):
        from fastapi.responses import PlainTextResponse

        result = get_player_profile(
            player_name,
            season=season,
            position_group=position_group,
            limit=limit,
            offset=offset,
            fmt=format,
        )
        if format == "csv" and isinstance(result, str):
            return PlainTextResponse(result, media_type="text/csv")
        return result

    @app.get("/artifacts")
    def artifacts():
        return get_artifacts_summary()

    @app.get("/review-queue")
    def review_queue(limit: int = 200):
        return get_review_queue(limit=limit)

    @app.get("/watchlist")
    def watchlist(limit: int = 100):
        return get_watchlist(limit=limit)

    @app.get("/shortlist")
    def shortlist(limit: int = 100):
        return get_shortlist(limit=limit)

    @app.get("/scouting-workspaces/capabilities")
    def scouting_workspace_capabilities(request: Request):
        configured = workspace_persistence_enabled()
        accessible = _workspace_access_allowed(request)
        return {
            "status": "ok",
            "enabled": configured and accessible,
            "configured": configured,
            "local_only": not remote_workspace_access_enabled(),
            "access_denied": configured and not accessible,
            "schema": WORKSPACE_SCHEMA,
            "max_bytes": MAX_WORKSPACE_BYTES,
            "concurrency": "if-match-server-revision",
            "backup_policy": "immutable-before-update",
        }

    @app.get("/scouting-workspaces/latest")
    def scouting_workspace_latest(request: Request):
        _require_workspace_access(request)
        try:
            return _workspace_record_response(_scouting_workspace_store().latest())
        except WorkspaceStoreError as exc:
            raise _workspace_error(exc) from exc

    @app.get("/scouting-workspaces")
    def scouting_workspaces(request: Request, limit: int = Query(default=100, ge=1, le=100)):
        _require_workspace_access(request)
        records = _scouting_workspace_store().list_records(limit=limit)
        return {"status": "ok", "count": len(records), "workspaces": records}

    @app.get("/scouting-workspaces/{workspace_id}")
    def scouting_workspace(workspace_id: str, request: Request):
        _require_workspace_access(request)
        try:
            return _workspace_record_response(
                _scouting_workspace_store().load(workspace_id)
            )
        except WorkspaceStoreError as exc:
            raise _workspace_error(exc) from exc

    @app.put("/scouting-workspaces/{workspace_id}")
    async def save_scouting_workspace(workspace_id: str, request: Request):
        _require_workspace_access(request)
        body = await request.body()
        if len(body) > MAX_WORKSPACE_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"code": "workspace_too_large"},
            )
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "workspace_json_invalid"},
            ) from exc
        expected_revision = _parse_if_match(request.headers.get("if-match"))
        try:
            record = _scouting_workspace_store().save(
                workspace_id,
                payload,
                expected_revision=expected_revision,
            )
        except WorkspaceStoreError as exc:
            raise _workspace_error(exc) from exc
        return _workspace_record_response(record)

    @app.get("/model-runs")
    def model_runs():
        return get_model_runs()

    @app.get("/reports/model-runs")
    def report_model_runs():
        return get_model_runs()

    @app.get("/reports/model-runs/{run_id}")
    def report_model_run_detail(run_id: str):
        return get_model_run_detail(run_id)

    # ── World Cup endpoints ──────────────────────────────────────────────

    @app.get("/world-cup/groups")
    def wc_groups():
        return get_wc_groups()

    @app.get("/world-cup/schedule")
    def wc_schedule(group: str | None = None, matchday: int | None = None):
        return get_wc_schedule(group=group, matchday=matchday)

    @app.get("/world-cup/squads/{team}")
    def wc_squad(team: str):
        return get_wc_squad(team)

    @app.get("/world-cup/predictions")
    def wc_predictions():
        return get_wc_predictions()

    @app.get("/world-cup/knockout")
    def wc_knockout():
        return get_wc_knockout()

    @app.get("/world-cup/outlook/{team}")
    def wc_team_outlook(team: str):
        return get_wc_team_outlook(team)

    @app.get("/world-cup/predictions/{home_team}/{away_team}")
    def wc_match_prediction(home_team: str, away_team: str):
        return get_world_cup_match_prediction(home_team, away_team)

    @app.get("/world-cup/match-briefings/{home_team}/{away_team}")
    def wc_match_briefing(home_team: str, away_team: str):
        return get_world_cup_match_briefing(home_team, away_team)

    @app.get("/worldcup/teams")
    def wc_teams():
        return get_wc_teams()

    # ── Tournament state endpoints ──────────────────────────────────────
    @app.get("/world-cup/tournament/summary")
    def wc_tournament_summary():
        return get_wc_tournament_summary()

    @app.get("/world-cup/tournament/standings")
    def wc_tournament_standings(group: str | None = None):
        return get_wc_tournament_standings(group=group)

    @app.get("/world-cup/tournament/matches")
    def wc_tournament_matches(
        group: str | None = None,
        pending: bool = False,
    ):
        return get_wc_tournament_matches(group=group, pending=pending)

    @app.get("/world-cup/tournament/scenarios/{team}")
    def wc_tournament_scenarios(team: str, max_scenarios: int = Query(30, ge=1, le=200)):
        return get_wc_tournament_scenarios(team, max_scenarios=max_scenarios)

    @app.post("/world-cup/tournament/result")
    def wc_tournament_apply_result(
        match_id: str = Query(...),
        home_goals: int = Query(..., ge=0, le=30),
        away_goals: int = Query(..., ge=0, le=30),
    ):
        return apply_wc_tournament_result(match_id, home_goals, away_goals)

    @app.delete("/world-cup/tournament/result")
    def wc_tournament_clear_result(match_id: str = Query(...)):
        return clear_wc_tournament_result(match_id)

    @app.post("/world-cup/tournament/reset")
    def wc_tournament_reset():
        return reset_wc_tournament()

    # ── Knockout bracket endpoints ─────────────────────────────────
    @app.get("/world-cup/tournament/knockout")
    def wc_knockout_bracket():
        return get_wc_knockout_bracket()

    @app.post("/world-cup/tournament/knockout/generate")
    def wc_knockout_generate():
        return generate_wc_knockout_bracket()

    @app.post("/world-cup/tournament/knockout/result")
    def wc_knockout_apply_result(
        match_id: str = Query(...),
        home_goals: int = Query(..., ge=0, le=30),
        away_goals: int = Query(..., ge=0, le=30),
        penalties_winner: str | None = Query(None),
    ):
        return apply_wc_knockout_result(
            match_id, home_goals, away_goals, penalties_winner=penalties_winner
        )

    @app.delete("/world-cup/tournament/knockout/result")
    def wc_knockout_clear_result(match_id: str = Query(...)):
        return clear_wc_knockout_result(match_id)

    @app.get("/world-cup/tournament/knockout/probabilities")
    def wc_knockout_probabilities():
        return get_wc_knockout_probabilities()

    @app.get("/world-cup/tournament/knockout/scenarios/{team}")
    def wc_knockout_scenarios(team: str, num_simulations: int = 5000):
        return get_wc_knockout_scenarios(team, num_simulations=num_simulations)

    @app.get("/world-cup/tournament/group-simulation")
    def wc_group_stage_simulation(
        mode: str = "random", num_simulations: int = 1000
    ):
        return get_wc_group_stage_simulation(
            mode=mode, num_simulations=num_simulations
        )

    @app.get("/world-cup/tournament/export")
    def wc_tournament_export():
        return export_wc_tournament_state()

    @app.post("/world-cup/tournament/import")
    async def wc_tournament_import(request: Request):
        import json as _json

        raw = await request.body()
        body = _json.loads(raw.decode("utf-8")) if raw else {}
        encoded = body.get("encoded", "")
        if not encoded:
            raise HTTPException(status_code=400, detail={"code": "missing_encoded"})
        return import_wc_tournament_state(encoded)

    # ── Tactical board export helpers ─────────────────────────────
    @app.get("/tactical-board/capabilities")
    def tactical_board_capabilities():
        """Detect available export capabilities (ffmpeg, etc.)."""
        import shutil

        ffmpeg_path = shutil.which("ffmpeg")
        return {
            "ffmpeg_available": ffmpeg_path is not None,
            "ffmpeg_path": ffmpeg_path,
            "supported_formats": {
                "png": True,
                "webm": True,  # MediaRecorder-based, browser-side
                "mp4": ffmpeg_path is not None,
                "gif": True,  # gif.js-based, browser-side
                "pdf": True,  # Browser print-based
            },
            "export_dir": str(
                _settings().data_root / "reports" / "tactical_exports"
            ),
        }

    @app.post("/tactical-board/export/mp4")
    async def tactical_board_export_mp4(request: Request):
        """Convert a WebM file to MP4 using ffmpeg (backend-side)."""
        import shutil
        import subprocess
        import tempfile

        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            return _clean_json_value({
                "status": "error",
                "error": "ffmpeg not found on system PATH",
            })

        try:
            body = await request.body()

            # Reject uploads larger than 50 MB to prevent abuse
            if len(body) > 50 * 1024 * 1024:
                return _clean_json_value({
                    "status": "error",
                    "error": "Upload exceeds 50 MB size limit",
                })

            export_dir = _settings().data_root / "reports" / "tactical_exports"
            export_dir.mkdir(parents=True, exist_ok=True)

            # Save uploaded WebM to temp file
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
                tmp_in.write(body)
                tmp_in_path = tmp_in.name

            # Generate output path
            import time

            ts = int(time.time())
            out_path = export_dir / f"tactical-board-{ts}.mp4"

            # Convert using ffmpeg
            result = subprocess.run(
                [
                    ffmpeg_path,
                    "-y",
                    "-i", tmp_in_path,
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "23",
                    "-pix_fmt", "yuv420p",
                    str(out_path),
                ],
                capture_output=True,
                timeout=60,
            )

            # Clean up temp file
            Path(tmp_in_path).unlink(missing_ok=True)

            if result.returncode != 0:
                return _clean_json_value({
                    "status": "error",
                    "error": f"ffmpeg failed: {result.stderr.decode()[:200]}",
                })

            return _clean_json_value({
                "status": "ok",
                "path": str(out_path),
                "size_bytes": out_path.stat().st_size,
            })
        except subprocess.TimeoutExpired:
            return _clean_json_value({"status": "error", "error": "ffmpeg timeout (60s)"})
        except Exception as exc:
            return _clean_json_value({"status": "error", "error": str(exc)})

    # Serve frontend static files
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


# Module-level app instance for uvicorn / PyInstaller
app = create_app()

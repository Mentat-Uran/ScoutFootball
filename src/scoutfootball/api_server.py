"""FastAPI application factory for ScoutFootball API server."""

from __future__ import annotations

import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from scoutfootball import __version__
from scoutfootball.api import (
    _clean_json_value,
    _settings,
    apply_wc_knockout_result,
    apply_wc_tournament_result,
    clear_wc_knockout_result,
    clear_wc_tournament_result,
    create_decision_dossier,
    create_opposition_briefing,
    create_post_match_review,
    create_recruitment_brief,
    diff_decision_dossier_versions,
    diff_opposition_briefing_versions,
    diff_post_match_review_versions,
    diff_recruitment_brief_versions,
    export_local_pack,
    export_wc_tournament_state,
    generate_wc_knockout_bracket,
    get_action_based_position_similarity,
    get_action_value_evidence,
    get_action_value_evidence_index,
    get_action_value_player_context,
    get_action_value_rating_links,
    get_action_value_summary,
    get_adapter_compatibility_matrix,
    get_adapter_registry,
    get_artifacts_summary,
    get_backtest_comparison,
    get_backtest_report_card,
    get_calibration_comparison,
    get_calibration_drift,
    get_calibration_drift_heatmap,
    get_calibration_drift_timeline,
    get_ci_coverage,
    get_ci_width_analysis,
    get_cluster_recruits,
    get_cluster_similarity_matrix,
    get_confidence_distribution,
    get_confidence_interval_plot,
    get_cross_league_action_comparison,
    get_cross_league_position_comparison,
    get_cross_league_team_depth,
    get_cumulative_trajectory,
    get_data_drift,
    get_decay_tuning,
    get_decision_dossier,
    get_decision_dossiers,
    get_detailed_health,
    get_difficulty_stratification,
    get_ensemble_attribution,
    get_ensemble_attribution_ci,
    get_ensemble_prediction,
    get_ensemble_weights,
    get_error_analysis,
    get_error_clustering,
    get_feature_importance,
    get_fixture_difficulty,
    get_fold_comparison,
    get_form_weighted_prediction,
    get_h2h_bias_correction,
    get_head_to_head,
    get_league_action_atlas,
    get_league_action_evolution,
    get_league_action_percentiles,
    get_league_error_analysis,
    get_league_form_table,
    get_league_style_evolution,
    get_league_style_percentiles,
    get_market_value_summary,
    get_match_momentum,
    get_match_prediction,
    get_match_prediction_dc,
    get_model_comparison,
    get_model_run_detail,
    get_model_runs,
    get_model_training_history,
    get_opposition_briefing,
    get_opposition_briefings,
    get_opposition_contracts,
    get_outcome_distribution,
    get_player_career_trajectory,
    get_player_comparison,
    get_player_comparison_multi,
    get_player_market_value_history,
    get_player_peer_benchmark,
    get_player_profile,
    get_player_ratings,
    get_player_role_fit,
    get_player_style_fit,
    get_position_action_profile,
    get_position_depth_profile,
    get_position_gap_report,
    get_position_style_drift,
    get_position_style_drift_neighbors,
    get_position_style_evolution,
    get_position_trend_overlay,
    get_post_match_review,
    get_post_match_reviews,
    get_prediction_anomalies,
    get_prediction_attribution,
    get_prediction_attribution_ci,
    get_prediction_calibration,
    get_prediction_diagnostics,
    get_prediction_staleness,
    get_prediction_streaks,
    get_prediction_summary,
    get_prediction_uncertainty,
    get_probability_heatmap,
    get_profit_loss_simulation,
    get_ratings_meta,
    get_recruitment_brief,
    get_recruitment_briefs,
    get_recruitment_contracts,
    get_reliability_diagram,
    get_research_health,
    get_review_queue,
    get_riser_decliner_watchlist,
    get_scenario_stress_test,
    get_scoreline_calibration,
    get_scouting_dashboard,
    get_scouting_target_style_match,
    get_scouting_targets,
    get_season_projection,
    get_shortlist,
    get_style_atlas,
    get_style_drift_neighbors,
    get_style_matchup,
    get_style_neighbors,
    get_team_accuracy,
    get_team_action_profile,
    get_team_action_similarity,
    get_team_calibration_drift,
    get_team_comparison,
    get_team_performance_profile,
    get_team_strength,
    get_team_style_clusters,
    get_team_style_drift,
    get_temporal_validation,
    get_transfermarkt_identity_report,
    get_truth_label_supervision,
    get_value_bet_analysis,
    get_value_summary,
    get_watchlist,
    get_wc_contracts,
    get_wc_group_stage_simulation,
    get_wc_group_tiebreak_diagnostics,
    get_wc_groups,
    get_wc_knockout,
    get_wc_knockout_bracket,
    get_wc_knockout_match_briefing,
    get_wc_knockout_match_review,
    get_wc_knockout_probabilities,
    get_wc_knockout_review_ledger,
    get_wc_knockout_scenarios,
    get_wc_match_player_spotlight,
    get_wc_predictions,
    get_wc_qualification_impact,
    get_wc_schedule,
    get_wc_squad,
    get_wc_squad_balance_comparison,
    get_wc_squad_scouting_needs,
    get_wc_team_form_trend,
    get_wc_team_outlook,
    get_wc_teams,
    get_wc_tournament_knockout_match_impact,
    get_wc_tournament_match_impact,
    get_wc_tournament_match_predictions,
    get_wc_tournament_matches,
    get_wc_tournament_overall_leaderboard,
    get_wc_tournament_scenarios,
    get_wc_tournament_standings,
    get_wc_tournament_standings_probabilities,
    get_wc_tournament_summary,
    get_wc_tournament_top_matches,
    get_world_cup_match_briefing,
    get_world_cup_match_prediction,
    health_check,
    import_local_pack,
    import_wc_tournament_state,
    list_decision_dossier_backups,
    list_market_value_players,
    list_opposition_briefing_backups,
    list_players,
    list_post_match_review_backups,
    list_recruitment_brief_backups,
    list_teams,
    load_decision_dossier_backup,
    load_opposition_briefing_backup,
    load_post_match_review_backup,
    load_recruitment_brief_backup,
    preview_wc_tournament_import,
    reset_wc_tournament,
    restore_decision_dossier_from_backup,
    restore_opposition_briefing_from_backup,
    restore_post_match_review_from_backup,
    restore_recruitment_brief_from_backup,
    search_players_and_teams,
    update_decision_dossier,
    update_opposition_briefing,
    update_post_match_review,
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


_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def require_local_write_access(request: Request) -> None:
    """Allow writes only from loopback or an explicitly supplied bearer token.

    CORS controls browser read permissions; it is not an authorization layer.
    The local API therefore defaults to loopback-only writes. A maintainer may
    opt into a remote, authenticated write path by setting
    ``SCOUTFOOTBALL_WRITE_TOKEN`` and sending the matching bearer token. The
    token itself is never included in error responses or logs.
    """
    host = request.client.host if request.client else None
    if is_loopback_client(host):
        return

    configured_token = os.environ.get("SCOUTFOOTBALL_WRITE_TOKEN", "").strip()
    authorization = request.headers.get("authorization", "")
    expected = f"Bearer {configured_token}" if configured_token else ""
    if expected and secrets.compare_digest(authorization, expected):
        return

    raise HTTPException(
        status_code=403,
        detail={"code": "local_write_access_required"},
    )


class _LocalWriteRoute(APIRoute):
    """Attach the write guard to every mutating route at registration time.

    Keeping this in the route class makes a newly added POST/PUT/PATCH/DELETE
    route fail closed by default without relying on a reviewer to remember a
    decorator argument. The route dependency remains inspectable in tests.
    """

    def __init__(self, *args, **kwargs):
        methods = {str(method).upper() for method in (kwargs.get("methods") or [])}
        dependencies = list(kwargs.get("dependencies") or [])
        if methods & _WRITE_METHODS:
            already_guarded = any(
                getattr(dependency, "dependency", None) is require_local_write_access
                for dependency in dependencies
            )
            if not already_guarded:
                dependencies.append(Depends(require_local_write_access))
            kwargs["dependencies"] = dependencies
        super().__init__(*args, **kwargs)


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
    try:
        import time

        from scoutfootball.api import get_research_health

        t0 = time.time()
        get_research_health()
        logger.info("research health cache warmed up in %.1fs", time.time() - t0)
    except Exception as e:
        logger.warning(
            "research health cache warmup failed (will compute on first request): %s",
            e,
        )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="ScoutFootball API",
        version=__version__,
        description="Local-first football data research platform API",
        lifespan=_lifespan,
    )
    app.router.route_class = _LocalWriteRoute

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

    @app.get("/health/detailed")
    def health_detailed(force_refresh: bool = Query(False)):
        return get_detailed_health(force_refresh=force_refresh)

    @app.get("/health/research")
    def health_research(force_refresh: bool = Query(False)):
        """Five-layer research health for the rating system (PRS-0 R-003/R-004).

        Fail-closed verdict: a stale, unreviewable, synthetic or
        non-independent-label rating system is reported as ``not_ready``,
        never hidden behind a top-level ``ok``. Read-only and local.
        """
        return get_research_health(force_refresh=force_refresh)

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

    @app.get("/adapters")
    def adapters():
        """Provider adapter manifest registry (I1: open interop baseline).

        Returns capabilities, schema mappings and conversion-loss notes
        for every registered source adapter. Read-only metadata only.
        """
        return get_adapter_registry()

    @app.get("/adapters/compatibility")
    def adapter_compatibility():
        """Project-local adapter admission and input-contract coverage.

        This does not validate an upstream license or make a publication
        decision; it only prevents experimental or uncontracted adapters from
        being mistaken for admitted local workflow inputs.
        """
        return get_adapter_compatibility_matrix()

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

    @app.get("/predictions/calibration/error-clustering")
    def predictions_calibration_error_clustering(
        n_clusters: int = Query(3, ge=2, le=8),
        error_percentile: float = Query(0.1, ge=0.01, le=0.5),
        min_samples_per_cluster: int = Query(5, ge=1, le=100),
    ):
        return get_error_clustering(
            n_clusters=n_clusters,
            error_percentile=error_percentile,
            min_samples_per_cluster=min_samples_per_cluster,
        )

    @app.get("/predictions/calibration/data-drift")
    def predictions_calibration_data_drift(
        split_ratio: float = Query(0.7, ge=0.1, le=0.9),
        split_date: str | None = Query(None, max_length=32),
        p_value_threshold: float = Query(0.05, ge=0.001, le=0.999),
        min_samples: int = Query(20, ge=5, le=500),
    ):
        return get_data_drift(
            split_ratio=split_ratio,
            split_date=split_date,
            p_value_threshold=p_value_threshold,
            min_samples=min_samples,
        )

    @app.get("/predictions/calibration/ci-width")
    def predictions_calibration_ci_width(
        ci_lower_col: str = Query("home_win_ci_lower", max_length=64),
        ci_upper_col: str = Query("home_win_ci_upper", max_length=64),
        n_bins: int = Query(5, ge=2, le=20),
        min_samples_per_bucket: int = Query(10, ge=1, le=100),
    ):
        return get_ci_width_analysis(
            ci_lower_col=ci_lower_col,
            ci_upper_col=ci_upper_col,
            n_bins=n_bins,
            min_samples_per_bucket=min_samples_per_bucket,
        )

    @app.get("/predictions/calibration/stress-test")
    def predictions_calibration_stress_test(
        shift_type: str = Query("outcome_swap", max_length=32),
        shift_ratio: float = Query(0.2, ge=0.0, le=1.0),
        random_state: int = Query(42, ge=0, le=2**31 - 1),
    ):
        return get_scenario_stress_test(
            shift_type=shift_type,
            shift_ratio=shift_ratio,
            random_state=random_state,
        )

    @app.get("/predictions/calibration/team-drift")
    def predictions_calibration_team_drift(
        team_col: str = Query("home_team", max_length=64),
        team_name: str = Query(..., max_length=128),
        window_size: str = Query("180D", max_length=16),
        min_samples_per_window: int = Query(5, ge=1, le=100),
        n_windows: int | None = Query(None, ge=1, le=100),
    ):
        return get_team_calibration_drift(
            team_col=team_col,
            team_name=team_name,
            window_size=window_size,
            min_samples_per_window=min_samples_per_window,
            n_windows=n_windows,
        )

    @app.get("/predictions/calibration/uncertainty")
    def predictions_calibration_uncertainty(
        max_points: int = Query(500, ge=10, le=5000),
    ):
        return get_prediction_uncertainty(max_points=max_points)

    @app.get("/predictions/calibration/profit-loss")
    def predictions_calibration_profit_loss(
        max_points: int = Query(500, ge=10, le=5000),
    ):
        return get_profit_loss_simulation(max_points=max_points)

    @app.get("/predictions/calibration/trajectory")
    def predictions_calibration_trajectory(
        rolling_window: int = Query(50, ge=5, le=500),
        max_points: int = Query(500, ge=10, le=5000),
        change_threshold: float = Query(0.05, ge=0.01, le=0.5),
    ):
        return get_cumulative_trajectory(
            rolling_window=rolling_window,
            max_points=max_points,
            change_threshold=change_threshold,
        )

    @app.get("/predictions/calibration/difficulty")
    def predictions_calibration_difficulty(
        easy_threshold: float = Query(0.6, ge=0.3, le=0.95),
        hard_threshold: float = Query(0.4, ge=0.05, le=0.7),
        n_bins: int = Query(5, ge=2, le=20),
    ):
        return get_difficulty_stratification(
            easy_threshold=easy_threshold,
            hard_threshold=hard_threshold,
            n_bins=n_bins,
        )

    @app.get("/predictions/calibration/streaks")
    def predictions_calibration_streaks(
        high_confident_threshold: float = Query(0.60, ge=0.05, le=1.0),
        low_confident_threshold: float = Query(0.40, ge=0.0, le=0.95),
        max_points: int = Query(500, ge=10, le=5000),
    ):
        return get_prediction_streaks(
            high_confident_threshold=high_confident_threshold,
            low_confident_threshold=low_confident_threshold,
            max_points=max_points,
        )

    @app.get("/predictions/calibration/report-card")
    def predictions_calibration_report_card():
        return get_backtest_report_card()

    @app.get("/predictions/calibration/anomalies")
    def predictions_calibration_anomalies(
        high_entropy_threshold: float = Query(0.85, ge=0.01, le=1.0),
        overconfident_threshold: float = Query(0.60, ge=0.01, le=0.99),
        underconfident_threshold: float = Query(0.40, ge=0.01, le=0.99),
        outlier_high_threshold: float = Query(0.90, ge=0.01, le=1.0),
        outlier_low_threshold: float = Query(0.35, ge=0.01, le=0.99),
        max_anomalies: int = Query(500, ge=10, le=5000),
    ):
        return get_prediction_anomalies(
            high_entropy_threshold=high_entropy_threshold,
            overconfident_threshold=overconfident_threshold,
            underconfident_threshold=underconfident_threshold,
            outlier_high_threshold=outlier_high_threshold,
            outlier_low_threshold=outlier_low_threshold,
            max_anomalies=max_anomalies,
        )

    @app.get("/predictions/calibration/team-profile")
    def predictions_calibration_team_profile(
        team: str = Query(..., max_length=128),
        top_n: int = Query(5, ge=1, le=50),
        min_matches: int = Query(3, ge=1, le=100),
    ):
        return get_team_performance_profile(
            team, top_n=top_n, min_matches=min_matches,
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

    # ── Market value (身价) endpoints ──────────────────────────────
    # Read-only Transfermarkt market value access. All responses carry
    # source attribution and the Transfermarkt ToS license boundary so
    # consumers cannot mistake subjective valuations for market prices.
    @app.get("/market-value/summary")
    def market_value_summary():
        """Aggregate market value stats with source attribution.

        Returns total_players, total_snapshots, value distribution by
        EUR band, and top-10 players by latest market value. Reads
        local raw Transfermarkt data only; never scrapes.
        """
        return get_market_value_summary()

    @app.get("/market-value/players")
    def market_value_players(
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        min_value_eur: float | None = Query(None, ge=0.0),
        max_value_eur: float | None = Query(None, ge=0.0),
        team: str | None = Query(None, max_length=128),
        position: str | None = Query(None, max_length=64),
        sort_by: str = Query("market_value_eur", max_length=32),
        sort_order: str = Query("desc", max_length=4),
    ):
        """List players with their latest market value (paginated).

        Returns one row per player (the latest snapshot). Filters by
        value range, team name (substring), and position (substring).
        """
        return list_market_value_players(
            limit=limit,
            offset=offset,
            min_value_eur=min_value_eur,
            max_value_eur=max_value_eur,
            team=team,
            position=position,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    @app.get("/market-value/players/{player_name}")
    def market_value_player_history(player_name: str):
        """Full market value history for a single player.

        Case-insensitive exact match first, then substring fallback.
        Returns all matching histories grouped by player_id so the
        caller can disambiguate common names.
        """
        return get_player_market_value_history(player_name)

    @app.get("/action-values")
    def action_values(limit: int = 20, offset: int = 0):
        return get_action_value_summary(limit=limit, offset=offset)

    @app.get("/action-values/evidence")
    def action_value_evidence_index():
        return get_action_value_evidence_index()

    @app.get("/action-values/evidence/{player_id}")
    def action_value_evidence(player_id: str):
        return get_action_value_evidence(player_id)

    @app.get("/action-values/players/{player_id}/context")
    def action_value_player_context(player_id: str):
        return get_action_value_player_context(player_id)

    @app.get("/action-values/players/{player_id}/rating-links")
    def action_value_rating_links(player_id: str):
        return get_action_value_rating_links(player_id)

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

    @app.get("/players/compare-multi")
    def players_compare_multi(
        names: str,
        season: str | None = None,
    ):
        """Compare 2-6 players side-by-side.

        ``names`` is a comma-separated list (e.g. ``?names=Alice,Bob,Carol``).
        Whitespace around each name is trimmed. The endpoint resolves each
        name to its best season (or to ``season`` when supplied) and returns
        a percentile matrix, metric rankings, composite ranking and pairwise
        similarity matrix.
        """
        player_names = [n.strip() for n in names.split(",") if n.strip()]
        return get_player_comparison_multi(player_names, season=season)

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

    @app.get("/players/{player_name}/career-trajectory")
    def player_career_trajectory(
        player_name: str,
        season: str | None = None,
        position_group: str | None = None,
    ):
        return get_player_career_trajectory(
            player_name, season=season, position_group=position_group
        )

    @app.get("/players/{player_name}/role-fit")
    def player_role_fit(
        player_name: str,
        season: str | None = None,
        position_group: str | None = None,
    ):
        return get_player_role_fit(
            player_name, season=season, position_group=position_group
        )

    @app.get("/players/{player_name}/peer-benchmark")
    def player_peer_benchmark(
        player_name: str,
        season: str | None = None,
        position_group: str | None = None,
    ):
        return get_player_peer_benchmark(
            player_name, season=season, position_group=position_group
        )

    @app.get("/scouting/risers-decliners")
    def risers_decliners(
        season: str | None = None,
        min_seasons: int = 2,
        min_minutes_latest: float = 300.0,
        top_n: int = 20,
        riser_threshold: float = 1.0,
        decliner_threshold: float = -1.0,
    ):
        return get_riser_decliner_watchlist(
            season=season,
            min_seasons=min_seasons,
            min_minutes_latest=min_minutes_latest,
            top_n=min(50, max(1, top_n)),
            riser_threshold=riser_threshold,
            decliner_threshold=decliner_threshold,
        )

    @app.get("/teams/style-clusters")
    def team_style_clusters(
        season: str | None = None,
        league: str | None = None,
        n_clusters: int = 4,
        min_minutes_total: float = 1800.0,
    ):
        return get_team_style_clusters(
            season=season,
            league=league,
            n_clusters=min(8, max(2, n_clusters)),
            min_minutes_total=min_minutes_total,
        )

    @app.get("/players/{player_name}/style-fit")
    def player_style_fit(
        player_name: str,
        season: str | None = None,
        league: str | None = None,
        n_clusters: int = 4,
        min_minutes_total: float = 1800.0,
    ):
        return get_player_style_fit(
            player_name,
            season=season,
            league=league,
            n_clusters=min(8, max(2, n_clusters)),
            min_minutes_total=min_minutes_total,
        )

    @app.get("/teams/style-clusters/recruits")
    def cluster_recruits(
        cluster_id: int,
        season: str | None = None,
        league: str | None = None,
        n_clusters: int = 4,
        min_minutes_total: float = 1800.0,
        min_player_minutes: float = 500.0,
        position_group: str | None = None,
        top_n: int = 20,
        exclude_cluster_teams: bool = True,
    ):
        return get_cluster_recruits(
            cluster_id,
            season=season,
            league=league,
            n_clusters=min(8, max(2, n_clusters)),
            min_minutes_total=min_minutes_total,
            min_player_minutes=min_player_minutes,
            position_group=position_group,
            top_n=min(100, max(1, top_n)),
            exclude_cluster_teams=exclude_cluster_teams,
        )

    @app.get("/teams/style-clusters/similarity")
    def team_style_clusters_similarity(
        season: str | None = None,
        league: str | None = None,
        n_clusters: int = 4,
        min_minutes_total: float = 1800.0,
    ):
        return get_cluster_similarity_matrix(
            season=season,
            league=league,
            n_clusters=min(8, max(2, n_clusters)),
            min_minutes_total=min_minutes_total,
        )

    @app.get("/teams/style-matchup")
    def team_style_matchup(
        home_team: str,
        away_team: str,
        season: str | None = None,
        league: str | None = None,
        n_clusters: int = 4,
        min_minutes_total: float = 1800.0,
    ):
        return get_style_matchup(
            home_team,
            away_team,
            season=season,
            league=league,
            n_clusters=min(8, max(2, n_clusters)),
            min_minutes_total=min_minutes_total,
        )

    @app.get("/teams/{team}/style-neighbors")
    def team_style_neighbors(
        team: str,
        season: str | None = None,
        league: str | None = None,
        top_n: int = 10,
        n_clusters: int = 4,
        min_minutes_total: float = 1800.0,
    ):
        return get_style_neighbors(
            team,
            season=season,
            league=league,
            top_n=min(50, max(1, top_n)),
            n_clusters=min(8, max(2, n_clusters)),
            min_minutes_total=min_minutes_total,
        )

    @app.get("/teams/{team}/style-percentiles")
    def team_style_percentiles(
        team: str,
        season: str | None = None,
        league: str | None = None,
        min_minutes_total: float = 1800.0,
    ):
        return get_league_style_percentiles(
            team,
            season=season,
            league=league,
            min_minutes_total=min_minutes_total,
        )

    @app.get("/teams/style-atlas")
    def team_style_atlas(
        season: str | None = None,
        league: str | None = None,
        n_bins: int = 8,
        min_minutes_total: float = 1800.0,
    ):
        return get_style_atlas(
            season=season,
            league=league,
            n_bins=min(20, max(3, n_bins)),
            min_minutes_total=min_minutes_total,
        )

    @app.get("/teams/{team}/style-drift")
    def team_style_drift(
        team: str,
        league: str | None = None,
        min_minutes_total: float = 1800.0,
    ):
        return get_team_style_drift(
            team,
            league=league,
            min_minutes_total=min_minutes_total,
        )

    @app.get("/teams/style-evolution")
    def team_style_evolution(
        league: str | None = None,
        min_minutes_total: float = 1800.0,
    ):
        return get_league_style_evolution(
            league=league,
            min_minutes_total=min_minutes_total,
        )

    @app.get("/teams/{team}/style-drift-neighbors")
    def team_style_drift_neighbors(
        team: str,
        league: str | None = None,
        top_n: int = 10,
        min_seasons: int = 2,
        min_minutes_total: float = 1800.0,
    ):
        return get_style_drift_neighbors(
            team,
            league=league,
            top_n=min(50, max(1, top_n)),
            min_seasons=max(2, min_seasons),
            min_minutes_total=min_minutes_total,
        )

    @app.get("/positions/style-evolution")
    def position_style_evolution(
        league: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_position_style_evolution(
            league=league,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/positions/depth-profile")
    def position_depth_profile(
        league: str | None = None,
        season: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_position_depth_profile(
            league=league,
            season=season,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/positions/action-profile")
    def position_action_profile(
        league: str | None = None,
        season: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_position_action_profile(
            league=league,
            season=season,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/positions/trend-overlay")
    def position_trend_overlay(
        league: str | None = None,
        season: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_position_trend_overlay(
            league=league,
            season=season,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/positions/{position_group}/style-drift")
    def position_style_drift(
        position_group: str,
        league: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_position_style_drift(
            position_group,
            league=league,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/positions/{position_group}/style-drift-neighbors")
    def position_style_drift_neighbors(
        position_group: str,
        league: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_position_style_drift_neighbors(
            position_group,
            league=league,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/positions/{position_group}/cross-league")
    def cross_league_position_comparison(
        position_group: str,
        season: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_cross_league_position_comparison(
            position_group,
            season=season,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/positions/{position_group}/action-similarity")
    def action_based_position_similarity(
        position_group: str,
        league: str | None = None,
        season: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_action_based_position_similarity(
            position_group,
            league=league,
            season=season,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/teams/action-profile")
    def team_action_profile(
        league: str | None = None,
        season: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_team_action_profile(
            league=league,
            season=season,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/teams/action-atlas")
    def team_action_atlas(
        season: str | None = None,
        league: str | None = None,
        n_bins: int = Query(8, ge=3, le=20),
        min_player_minutes: float = 500.0,
    ):
        return get_league_action_atlas(
            season=season,
            league=league,
            n_bins=n_bins,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/teams/action-evolution")
    def team_action_evolution(
        league: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_league_action_evolution(
            league=league,
            min_player_minutes=min_player_minutes,
        )

    # ── League season projection & form analysis ──
    # Static routes registered before any /teams/{team} parameterized routes
    # to avoid path conflicts.
    @app.get("/league/form-table")
    def league_form_table(
        league: str | None = None,
        season: str | None = None,
        last_n: int = Query(6, ge=1, le=30),
    ):
        return get_league_form_table(
            league=league,
            season=season,
            last_n=last_n,
        )

    @app.get("/league/fixture-difficulty")
    def league_fixture_difficulty(
        league: str | None = None,
        season: str | None = None,
        team: str | None = None,
        upcoming_n: int = Query(10, ge=1, le=30),
    ):
        return get_fixture_difficulty(
            league=league,
            season=season,
            team=team,
            upcoming_n=upcoming_n,
        )

    @app.get("/league/season-projection")
    def league_season_projection(
        league: str | None = None,
        season: str | None = None,
        num_simulations: int = Query(1000, ge=100, le=10000),
        random_seed: int = Query(42, ge=0, le=2_000_000_000),
        top_n: int = Query(4, ge=1, le=20),
        relegation_slots: int = Query(3, ge=0, le=10),
    ):
        return get_season_projection(
            league=league,
            season=season,
            num_simulations=num_simulations,
            random_seed=random_seed,
            top_n=top_n,
            relegation_slots=relegation_slots,
        )

    @app.get("/teams/cross-league-action")
    def team_cross_league_action(
        season: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_cross_league_action_comparison(
            season=season,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/teams/cross-league-depth")
    def team_cross_league_depth(
        team_a: str = Query(..., min_length=1),
        team_b: str = Query(..., min_length=1),
        season: str | None = None,
        min_player_minutes: float = Query(500.0, ge=0.0),
    ):
        return get_cross_league_team_depth(
            team_a,
            team_b,
            season=season,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/teams/{team}/scouting-targets")
    def team_scouting_targets(
        team: str,
        season: str | None = None,
        min_player_minutes: float = Query(500.0, ge=0.0),
        top_n: int = Query(10, ge=1, le=50),
        exclude_same_league: bool = True,
    ):
        return get_scouting_targets(
            team,
            season=season,
            min_player_minutes=min_player_minutes,
            top_n=top_n,
            exclude_same_league=exclude_same_league,
        )

    @app.get("/teams/{team}/scouting-style-match/{position_group}")
    def team_scouting_style_match(
        team: str,
        position_group: str,
        season: str | None = None,
        min_player_minutes: float = Query(500.0, ge=0.0),
        top_n: int = Query(10, ge=1, le=50),
        exclude_same_league: bool = True,
        use_position_weights: bool = False,
    ):
        return get_scouting_target_style_match(
            team,
            position_group,
            season=season,
            min_player_minutes=min_player_minutes,
            top_n=top_n,
            exclude_same_league=exclude_same_league,
            use_position_weights=use_position_weights,
        )

    @app.get("/teams/{team}/scouting-dashboard")
    def team_scouting_dashboard(
        team: str,
        season: str | None = None,
        min_player_minutes: float = Query(500.0, ge=0.0),
        top_n: int = Query(10, ge=1, le=50),
        exclude_same_league: bool = True,
        max_positions: int = Query(3, ge=1, le=8),
        use_position_weights: bool = False,
    ):
        return get_scouting_dashboard(
            team,
            season=season,
            min_player_minutes=min_player_minutes,
            top_n=top_n,
            exclude_same_league=exclude_same_league,
            max_positions=max_positions,
            use_position_weights=use_position_weights,
        )

    @app.get("/teams/{team}/action-percentiles")
    def team_action_percentiles(
        team: str,
        league: str | None = None,
        season: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_league_action_percentiles(
            team,
            league=league,
            season=season,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/teams/{team}/action-similarity")
    def team_action_similarity(
        team: str,
        league: str | None = None,
        season: str | None = None,
        top_n: int = 10,
        min_player_minutes: float = 500.0,
    ):
        return get_team_action_similarity(
            team,
            league=league,
            season=season,
            top_n=top_n,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/teams/{team}/position-gap-report")
    def position_gap_report(
        team: str,
        season: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_position_gap_report(
            team,
            season=season,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/player/{player_name}/profile")
    def player_profile(
        player_name: str,
        season: str | None = None,
        canonical_player_id: str | None = None,
    ):
        return get_player_profile(
            player_name,
            season=season,
            canonical_player_id=canonical_player_id,
        )

    @app.get("/players/{player_name}")
    def player_detail(
        player_name: str,
        season: str | None = None,
        position_group: str | None = None,
        limit: int = 50,
        offset: int = 0,
        format: str = "json",
        canonical_player_id: str | None = None,
    ):
        from fastapi.responses import PlainTextResponse

        result = get_player_profile(
            player_name,
            season=season,
            position_group=position_group,
            limit=limit,
            offset=offset,
            fmt=format,
            canonical_player_id=canonical_player_id,
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

    @app.get("/reports/model-training")
    def report_model_training(run_id: str | None = None):
        return get_model_training_history(run_id=run_id)

    @app.get("/reports/model-runs/{run_id}")
    def report_model_run_detail(run_id: str):
        return get_model_run_detail(run_id)

    @app.get("/reports/truth-labels")
    def report_truth_labels():
        return get_truth_label_supervision()

    @app.get("/reports/transfermarkt-identities")
    def report_transfermarkt_identities():
        return get_transfermarkt_identity_report()

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

    @app.get("/world-cup/squads/{team}/scouting-needs")
    def wc_squad_scouting_needs(
        team: str,
        season: str | None = None,
        min_player_minutes: float = 500.0,
    ):
        return get_wc_squad_scouting_needs(
            team,
            season=season,
            min_player_minutes=min_player_minutes,
        )

    @app.get("/world-cup/squad-balance-comparison/{team_a}/{team_b}")
    def wc_squad_balance_comparison(team_a: str, team_b: str):
        return get_wc_squad_balance_comparison(team_a, team_b)

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

    @app.get("/world-cup/contracts")
    def wc_contracts():
        return get_wc_contracts()

    @app.get("/world-cup/tournament/standings")
    def wc_tournament_standings(group: str | None = None):
        return get_wc_tournament_standings(group=group)

    @app.get("/world-cup/tournament/standings-probabilities")
    def wc_tournament_standings_probabilities(
        group: str | None = None,
        num_simulations: int = 2000,
    ):
        return get_wc_tournament_standings_probabilities(
            group=group, num_simulations=num_simulations
        )

    @app.get("/world-cup/tournament/overall-leaderboard")
    def wc_tournament_overall_leaderboard(
        num_simulations: int = 2000,
        sort_by: str = "advance_prob",
    ):
        return get_wc_tournament_overall_leaderboard(
            num_simulations=num_simulations, sort_by=sort_by
        )

    @app.get("/world-cup/tournament/qualification-impact")
    def wc_tournament_qualification_impact(group: str):
        return get_wc_qualification_impact(group)

    @app.get("/world-cup/tournament/tiebreak-diagnostics")
    def wc_tournament_tiebreak_diagnostics(group: str):
        return get_wc_group_tiebreak_diagnostics(group)

    @app.get("/world-cup/tournament/matches")
    def wc_tournament_matches(
        group: str | None = None,
        pending: bool = False,
    ):
        return get_wc_tournament_matches(group=group, pending=pending)

    @app.get("/world-cup/tournament/match-predictions")
    def wc_tournament_match_predictions(group: str | None = None):
        return get_wc_tournament_match_predictions(group=group)

    @app.get("/world-cup/tournament/match-impact")
    def wc_tournament_match_impact(
        group: str | None = None,
        num_simulations: int = Query(1000, ge=100, le=10000),
        top_n: int = Query(10, ge=1, le=50),
    ):
        return get_wc_tournament_match_impact(
            group=group, num_simulations=num_simulations, top_n=top_n
        )

    @app.get("/world-cup/tournament/knockout/match-impact")
    def wc_tournament_knockout_match_impact(
        num_simulations: int = Query(5000, ge=100, le=20000),
        top_n: int = Query(10, ge=1, le=50),
    ):
        return get_wc_tournament_knockout_match_impact(
            num_simulations=num_simulations, top_n=top_n
        )

    @app.get("/world-cup/tournament/top-matches")
    def wc_tournament_top_matches(
        group_top_n: int = Query(5, ge=1, le=20),
        knockout_top_n: int = Query(5, ge=1, le=20),
        num_simulations: int = Query(1000, ge=100, le=10000),
    ):
        return get_wc_tournament_top_matches(
            group_top_n=group_top_n,
            knockout_top_n=knockout_top_n,
            num_simulations=num_simulations,
        )

    @app.get("/world-cup/match-briefings/{home}/{away}/spotlight")
    def wc_match_player_spotlight(
        home: str, away: str, top_n: int = Query(5, ge=1, le=10)
    ):
        return get_wc_match_player_spotlight(home, away, top_n=top_n)

    @app.get("/world-cup/teams/{team}/form-trend")
    def wc_team_form_trend(team: str, last_n: int = Query(6, ge=1, le=20)):
        return get_wc_team_form_trend(team, last_n=last_n)

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

    @app.get("/world-cup/tournament/knockout/{match_id}/briefing")
    def wc_knockout_match_briefing(match_id: str):
        return get_wc_knockout_match_briefing(match_id)

    @app.get("/world-cup/tournament/knockout/{match_id}/review")
    def wc_knockout_match_review(match_id: str):
        return get_wc_knockout_match_review(match_id)

    @app.get("/world-cup/tournament/knockout/reviews")
    def wc_knockout_review_ledger():
        return get_wc_knockout_review_ledger()

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
        fingerprint = body.get("expected_current_fingerprint")
        if fingerprint is not None and not isinstance(fingerprint, str):
            raise HTTPException(status_code=400, detail={"code": "invalid_fingerprint"})
        return import_wc_tournament_state(
            encoded, expected_current_fingerprint=fingerprint
        )

    @app.post("/world-cup/tournament/import/preview")
    async def wc_tournament_import_preview(request: Request):
        import json as _json

        raw = await request.body()
        body = _json.loads(raw.decode("utf-8")) if raw else {}
        encoded = body.get("encoded", "")
        if not encoded:
            raise HTTPException(status_code=400, detail={"code": "missing_encoded"})
        return preview_wc_tournament_import(encoded)

    # ── Recruitment Pack endpoints ──────────────────────────────────
    @app.get("/recruitment/contracts")
    def recruitment_contracts():
        return get_recruitment_contracts()

    @app.get("/recruitment/briefs")
    def recruitment_briefs(limit: int = Query(100, ge=1, le=100)):
        return get_recruitment_briefs(limit=limit)

    @app.get("/recruitment/briefs/{brief_id}")
    def recruitment_brief(brief_id: str):
        return get_recruitment_brief(brief_id)

    @app.post("/recruitment/briefs")
    async def recruitment_create_brief(request: Request):
        import json as _json

        raw = await request.body()
        if not raw:
            raise HTTPException(
                status_code=400, detail={"code": "missing_payload"}
            )
        try:
            payload = _json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_json", "message": str(exc)},
            ) from exc
        result = create_recruitment_brief(payload)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 400)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.get("/recruitment/briefs/{brief_id}/backups")
    def recruitment_brief_backups(brief_id: str):
        result = list_recruitment_brief_backups(brief_id)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 404)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.get("/recruitment/briefs/{brief_id}/backups/{backup_filename}")
    def recruitment_brief_backup(brief_id: str, backup_filename: str):
        result = load_recruitment_brief_backup(brief_id, backup_filename)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 404)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.get("/recruitment/briefs/{brief_id}/diff")
    def recruitment_brief_diff(
        brief_id: str,
        backup_filename: str = Query(..., description="backup filename to diff against current"),
    ):
        result = diff_recruitment_brief_versions(brief_id, backup_filename)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 400)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.post("/recruitment/briefs/{brief_id}/restore")
    async def recruitment_brief_restore(brief_id: str, request: Request):
        import json as _json

        raw = await request.body()
        payload: dict = {}
        if raw:
            try:
                payload = _json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "invalid_json", "message": str(exc)},
                ) from exc
        backup_filename = payload.get("backup_filename")
        if not isinstance(backup_filename, str) or not backup_filename:
            raise HTTPException(
                status_code=400,
                detail={"code": "missing_backup_filename"},
            )
        expected_revision = payload.get("expected_revision")
        if expected_revision is not None:
            try:
                expected_revision = int(expected_revision)
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "invalid_expected_revision"},
                ) from exc
        result = restore_recruitment_brief_from_backup(
            brief_id,
            backup_filename,
            expected_revision=expected_revision,
        )
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 409)),
                detail={
                    "code": result.get("code"),
                    "message": result.get("message"),
                    **result.get("metadata", {}),
                },
            )
        return result

    # ── Opposition & Match briefings ──────────────────────────────
    @app.get("/opposition/contracts")
    def opposition_contracts():
        return get_opposition_contracts()

    @app.get("/opposition/briefs")
    def opposition_briefs(limit: int = Query(100, ge=1, le=100)):
        return get_opposition_briefings(limit=limit)

    @app.get("/opposition/briefs/{briefing_id}")
    def opposition_brief(briefing_id: str):
        result = get_opposition_briefing(briefing_id)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 404)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.post("/opposition/briefs")
    async def opposition_create_brief(request: Request):
        import json as _json

        raw = await request.body()
        if not raw:
            raise HTTPException(
                status_code=400, detail={"code": "missing_payload"}
            )
        try:
            payload = _json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_json", "message": str(exc)},
            ) from exc
        result = create_opposition_briefing(payload)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 400)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.put("/opposition/briefs/{briefing_id}")
    async def opposition_update_briefing(briefing_id: str, request: Request):
        import json as _json

        raw = await request.body()
        if not raw:
            raise HTTPException(
                status_code=400, detail={"code": "missing_payload"}
            )
        try:
            payload = _json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_json", "message": str(exc)},
            ) from exc

        # Body shape: {"fields": {...}, "expected_revision": <int>}
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_payload", "message": "body must be a JSON object"},
            )
        fields = payload.get("fields")
        if not isinstance(fields, dict):
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_fields", "message": "fields must be a JSON object"},
            )
        expected_revision = payload.get("expected_revision")
        if expected_revision is None:
            raise HTTPException(
                status_code=400,
                detail={"code": "missing_expected_revision"},
            )
        try:
            expected_revision = int(expected_revision)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_expected_revision"},
            ) from exc

        result = update_opposition_briefing(
            briefing_id, fields, expected_revision=expected_revision,
        )
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 409)),
                detail={
                    "code": result.get("code"),
                    "message": result.get("message"),
                    **result.get("metadata", {}),
                },
            )
        return result

    @app.get("/opposition/briefs/{briefing_id}/backups")
    def opposition_briefing_backups(briefing_id: str):
        result = list_opposition_briefing_backups(briefing_id)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 404)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.get("/opposition/briefs/{briefing_id}/backups/{backup_filename}")
    def opposition_briefing_backup(briefing_id: str, backup_filename: str):
        result = load_opposition_briefing_backup(briefing_id, backup_filename)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 404)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.get("/opposition/briefs/{briefing_id}/diff")
    def opposition_briefing_diff(
        briefing_id: str,
        backup_filename: str = Query(..., description="backup filename to diff against current"),
    ):
        result = diff_opposition_briefing_versions(briefing_id, backup_filename)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 400)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.post("/opposition/briefs/{briefing_id}/restore")
    async def opposition_briefing_restore(briefing_id: str, request: Request):
        import json as _json

        raw = await request.body()
        payload: dict = {}
        if raw:
            try:
                payload = _json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "invalid_json", "message": str(exc)},
                ) from exc
        backup_filename = payload.get("backup_filename")
        if not isinstance(backup_filename, str) or not backup_filename:
            raise HTTPException(
                status_code=400,
                detail={"code": "missing_backup_filename"},
            )
        expected_revision = payload.get("expected_revision")
        if expected_revision is not None:
            try:
                expected_revision = int(expected_revision)
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "invalid_expected_revision"},
                ) from exc
        result = restore_opposition_briefing_from_backup(
            briefing_id,
            backup_filename,
            expected_revision=expected_revision,
        )
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 409)),
                detail={
                    "code": result.get("code"),
                    "message": result.get("message"),
                    **result.get("metadata", {}),
                },
            )
        return result

    # ── Recruitment decision dossiers ────────────────────────────
    @app.get("/recruitment/dossiers")
    def recruitment_dossiers(limit: int = Query(100, ge=1, le=100)):
        return get_decision_dossiers(limit=limit)

    @app.get("/recruitment/dossiers/{dossier_id}")
    def recruitment_dossier(dossier_id: str):
        result = get_decision_dossier(dossier_id)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 404)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.post("/recruitment/dossiers")
    async def recruitment_create_dossier(request: Request):
        import json as _json

        raw = await request.body()
        if not raw:
            raise HTTPException(
                status_code=400, detail={"code": "missing_payload"}
            )
        try:
            payload = _json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_json", "message": str(exc)},
            ) from exc
        result = create_decision_dossier(payload)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 400)),
                detail={
                    "code": result.get("code"),
                    "message": result.get("message"),
                    **result.get("metadata", {}),
                },
            )
        return result

    @app.put("/recruitment/dossiers/{dossier_id}")
    async def recruitment_update_dossier(dossier_id: str, request: Request):
        import json as _json

        raw = await request.body()
        if not raw:
            raise HTTPException(
                status_code=400, detail={"code": "missing_payload"}
            )
        try:
            payload = _json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_json", "message": str(exc)},
            ) from exc

        # Body shape: {"fields": {...}, "expected_revision": <int>}
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_payload", "message": "body must be a JSON object"},
            )
        fields = payload.get("fields")
        if not isinstance(fields, dict):
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_fields", "message": "fields must be a JSON object"},
            )
        expected_revision = payload.get("expected_revision")
        if expected_revision is None:
            raise HTTPException(
                status_code=400,
                detail={"code": "missing_expected_revision"},
            )
        try:
            expected_revision = int(expected_revision)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_expected_revision"},
            ) from exc

        result = update_decision_dossier(
            dossier_id, fields, expected_revision=expected_revision,
        )
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 409)),
                detail={
                    "code": result.get("code"),
                    "message": result.get("message"),
                    **result.get("metadata", {}),
                },
            )
        return result

    @app.get("/recruitment/dossiers/{dossier_id}/backups")
    def recruitment_dossier_backups(dossier_id: str):
        result = list_decision_dossier_backups(dossier_id)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 404)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.get("/recruitment/dossiers/{dossier_id}/backups/{backup_filename}")
    def recruitment_dossier_backup(dossier_id: str, backup_filename: str):
        result = load_decision_dossier_backup(dossier_id, backup_filename)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 404)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.get("/recruitment/dossiers/{dossier_id}/diff")
    def recruitment_dossier_diff(
        dossier_id: str,
        backup_filename: str = Query(..., description="backup filename to diff against current"),
    ):
        result = diff_decision_dossier_versions(dossier_id, backup_filename)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 400)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.post("/recruitment/dossiers/{dossier_id}/restore")
    async def recruitment_dossier_restore(dossier_id: str, request: Request):
        import json as _json

        raw = await request.body()
        payload: dict = {}
        if raw:
            try:
                payload = _json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "invalid_json", "message": str(exc)},
                ) from exc
        backup_filename = payload.get("backup_filename")
        if not isinstance(backup_filename, str) or not backup_filename:
            raise HTTPException(
                status_code=400,
                detail={"code": "missing_backup_filename"},
            )
        expected_revision = payload.get("expected_revision")
        if expected_revision is not None:
            try:
                expected_revision = int(expected_revision)
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "invalid_expected_revision"},
                ) from exc
        result = restore_decision_dossier_from_backup(
            dossier_id,
            backup_filename,
            expected_revision=expected_revision,
        )
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 409)),
                detail={
                    "code": result.get("code"),
                    "message": result.get("message"),
                    **result.get("metadata", {}),
                },
            )
        return result

    # ── Opposition post-match reviews ────────────────────────────
    @app.get("/opposition/reviews")
    def opposition_reviews(limit: int = Query(100, ge=1, le=100)):
        return get_post_match_reviews(limit=limit)

    @app.get("/opposition/reviews/{review_id}")
    def opposition_review(review_id: str):
        result = get_post_match_review(review_id)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 404)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.post("/opposition/reviews")
    async def opposition_create_review(request: Request):
        import json as _json

        raw = await request.body()
        if not raw:
            raise HTTPException(
                status_code=400, detail={"code": "missing_payload"}
            )
        try:
            payload = _json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_json", "message": str(exc)},
            ) from exc
        result = create_post_match_review(payload)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 400)),
                detail={
                    "code": result.get("code"),
                    "message": result.get("message"),
                    **result.get("metadata", {}),
                },
            )
        return result

    @app.put("/opposition/reviews/{review_id}")
    async def opposition_update_review(review_id: str, request: Request):
        import json as _json

        raw = await request.body()
        if not raw:
            raise HTTPException(
                status_code=400, detail={"code": "missing_payload"}
            )
        try:
            payload = _json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_json", "message": str(exc)},
            ) from exc

        # Body shape: {"fields": {...}, "expected_revision": <int>}
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_payload", "message": "body must be a JSON object"},
            )
        fields = payload.get("fields")
        if not isinstance(fields, dict):
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_fields", "message": "fields must be a JSON object"},
            )
        expected_revision = payload.get("expected_revision")
        if expected_revision is None:
            raise HTTPException(
                status_code=400,
                detail={"code": "missing_expected_revision"},
            )
        try:
            expected_revision = int(expected_revision)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_expected_revision"},
            ) from exc

        result = update_post_match_review(
            review_id, fields, expected_revision=expected_revision,
        )
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 409)),
                detail={
                    "code": result.get("code"),
                    "message": result.get("message"),
                    **result.get("metadata", {}),
                },
            )
        return result

    @app.get("/opposition/reviews/{review_id}/backups")
    def opposition_review_backups(review_id: str):
        result = list_post_match_review_backups(review_id)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 404)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.get("/opposition/reviews/{review_id}/backups/{backup_filename}")
    def opposition_review_backup(review_id: str, backup_filename: str):
        result = load_post_match_review_backup(review_id, backup_filename)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 404)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.get("/opposition/reviews/{review_id}/diff")
    def opposition_review_diff(
        review_id: str,
        backup_filename: str = Query(..., description="backup filename to diff against current"),
    ):
        result = diff_post_match_review_versions(review_id, backup_filename)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 400)),
                detail={"code": result.get("code"), "message": result.get("message")},
            )
        return result

    @app.post("/opposition/reviews/{review_id}/restore")
    async def opposition_review_restore(review_id: str, request: Request):
        import json as _json

        raw = await request.body()
        payload: dict = {}
        if raw:
            try:
                payload = _json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "invalid_json", "message": str(exc)},
                ) from exc
        backup_filename = payload.get("backup_filename")
        if not isinstance(backup_filename, str) or not backup_filename:
            raise HTTPException(
                status_code=400,
                detail={"code": "missing_backup_filename"},
            )
        expected_revision = payload.get("expected_revision")
        if expected_revision is not None:
            try:
                expected_revision = int(expected_revision)
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "invalid_expected_revision"},
                ) from exc
        result = restore_post_match_review_from_backup(
            review_id,
            backup_filename,
            expected_revision=expected_revision,
        )
        if result.get("status") == "error":
            raise HTTPException(
                status_code=int(result.get("http_status", 409)),
                detail={
                    "code": result.get("code"),
                    "message": result.get("message"),
                    **result.get("metadata", {}),
                },
            )
        return result

    # ── Portable offline pack ─────────────────────────────────────
    @app.get("/local-pack/export")
    def local_pack_export():
        """Export all local personal artifacts as a portable offline pack."""
        return export_local_pack()

    @app.post("/local-pack/import")
    def local_pack_import(payload: dict, overwrite: bool = Query(False)):
        """Import a portable pack into the local stores.

        The request body is the inner ``pack`` object from an export
        response (``response["pack"]``). ``overwrite`` controls conflict
        handling: ``False`` (default) skips records whose ID already
        exists locally; ``True`` replaces them via revision bump.
        """
        pack = payload.get("pack", payload) if isinstance(payload, dict) else payload
        return import_local_pack(pack, overwrite=overwrite)

    # ── Tactical board export helpers ─────────────────────────────
    @app.get("/tactical-board/capabilities")
    def tactical_board_capabilities():
        """Detect available export capabilities (ffmpeg, etc.)."""
        import shutil

        ffmpeg_path = shutil.which("ffmpeg")
        return {
            "ffmpeg_available": ffmpeg_path is not None,
            "supported_formats": {
                "png": True,
                "webm": True,  # MediaRecorder-based, browser-side
                "mp4": ffmpeg_path is not None,
                "gif": True,  # gif.js-based, browser-side
                "pdf": True,  # Browser print-based
            },
        }

    @app.post("/tactical-board/export/mp4")
    async def tactical_board_export_mp4(request: Request):
        """Convert a WebM file to MP4 using ffmpeg (backend-side)."""
        import shutil
        import subprocess
        import tempfile
        import time

        max_upload_bytes = 50 * 1024 * 1024
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise HTTPException(
                status_code=503,
                detail={"code": "ffmpeg_unavailable"},
            )

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail={"code": "tactical_upload_too_large"},
                    )
            except ValueError:
                pass

        tmp_in_path: Path | None = None
        out_path: Path | None = None
        completed = False
        try:
            export_dir = _settings().data_root / "reports" / "tactical_exports"
            export_dir.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
                tmp_in_path = Path(tmp_in.name)
                total_bytes = 0
                async for chunk in request.stream():
                    total_bytes += len(chunk)
                    if total_bytes > max_upload_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail={"code": "tactical_upload_too_large"},
                        )
                    tmp_in.write(chunk)

            if total_bytes == 0:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "tactical_upload_empty"},
                )

            ts = int(time.time() * 1000)
            out_path = export_dir / f"tactical-board-{ts}.mp4"

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

            if result.returncode != 0:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "tactical_conversion_failed"},
                )

            completed = True
            return _clean_json_value({
                "status": "ok",
                "filename": out_path.name,
                "size_bytes": out_path.stat().st_size,
            })
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=504,
                detail={"code": "tactical_conversion_timeout"},
            ) from None
        finally:
            if tmp_in_path is not None:
                tmp_in_path.unlink(missing_ok=True)
            if not completed and out_path is not None:
                out_path.unlink(missing_ok=True)

    # Serve frontend static files
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


# Module-level app instance for uvicorn / PyInstaller
app = create_app()

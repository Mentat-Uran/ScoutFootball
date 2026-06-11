"""FastAPI read-only service layer for ScoutFootball."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scoutfootball.app.data_loader import (
    data_source_label,
    load_league_metrics,
    load_model_meta,
    load_oof_predictions,
    load_player_match,
    load_player_ratings,
    load_player_value_metrics,
    load_score_prediction,
    load_score_prediction_dc,
    load_team_match,
)
from scoutfootball.evaluation.scouting_queue import build_scouting_queues
from scoutfootball.worldcup.data import (
    BIG5_LEAGUES,
    GROUPS,
    HOSTS,
    compute_group_predictions,
    compute_team_strengths,
    enrich_squad_with_ratings,
    enrich_squads_with_ratings,
    generate_group_stage_matches,
    get_squad,
    get_team_group,
)


def _read_parquet(path: Path):
    """Read a Parquet file via DuckDB (avoids pyarrow dependency)."""
    import duckdb
    return duckdb.read_parquet(str(path)).fetchdf()


@dataclass(frozen=True)
class HealthResponse:
    status: str
    data_source: str
    version: str


@dataclass(frozen=True)
class PlayerListResponse:
    player_count: int
    players: list[str]


def _settings():
    from scoutfootball.config import PlatformSettings

    return PlatformSettings.from_root()


def _clean_json_value(value: Any) -> Any:
    import numpy as np

    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    # Handle pandas NA/NaT
    try:
        import pandas as pd
        if value is pd.NA or value is pd.NaT:
            return None
    except (ImportError, AttributeError):
        pass
    if isinstance(value, dict):
        return {key: _clean_json_value(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_clean_json_value(item) for item in value]
    return value


def _read_json(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        return json.load(handle)


def _artifact_file_info(path: Path, label: str, *, rows: int | None = None) -> dict[str, Any]:
    return {
        "label": label,
        "path": str(path),
        "exists": path.exists(),
        "rows": rows,
        "updated_at": path.stat().st_mtime if path.exists() else None,
    }


def _latest_run_id() -> str:
    runs = get_model_runs()
    run_list = runs.get("runs", [])
    if run_list:
        return str(run_list[0].get("run_id", "latest-local"))
    return "latest-local"


def _queue_payload(frame, *, limit: int) -> dict[str, Any]:
    limited = frame.head(limit).copy()
    records = _clean_json_value(limited.to_dict(orient="records"))
    return {"count": len(frame), "players": records}


def health_check() -> HealthResponse:
    from scoutfootball import __version__

    return HealthResponse(
        status="ok",
        data_source=data_source_label(),
        version=__version__,
    )


def list_players() -> PlayerListResponse:
    """Return all unique player names from the ratings dataset."""
    df = load_player_ratings()
    col = (
        "player" if "player" in df.columns
        else ("player_name" if "player_name" in df.columns else None)
    )
    if col is None:
        return PlayerListResponse(player_count=0, players=[])
    names = sorted(df[col].dropna().unique().tolist())
    return PlayerListResponse(player_count=len(names), players=names)


def list_teams() -> list[str]:
    """Return team names from ratings data (covers all 5 leagues)."""
    df = load_player_ratings()
    if "team" in df.columns:
        return sorted(df["team"].dropna().unique().tolist())
    # Fallback to team_match
    tm = load_team_match()
    if "team_name" in tm.columns:
        return sorted(tm["team_name"].dropna().unique().tolist())[:200]
    return []


def _score_matrix_to_list(prediction) -> list[list[float]]:
    """Convert a score_matrix DataFrame to a 2-D list (0-5 goals)."""
    sm = prediction.score_matrix
    max_goals = 5
    rows = min(max_goals + 1, sm.shape[0])
    cols = min(max_goals + 1, sm.shape[1])
    matrix = []
    for i in range(rows):
        row = []
        for j in range(cols):
            val = float(sm.iloc[i, j]) if i < sm.shape[0] and j < sm.shape[1] else 0.0
            row.append(round(val, 4))
        # Pad if score_matrix is smaller than 6x6
        while len(row) < max_goals + 1:
            row.append(0.0)
        matrix.append(row)
    while len(matrix) < max_goals + 1:
        matrix.append([0.0] * (max_goals + 1))
    return matrix


def _prediction_calibration() -> dict[str, Any]:
    """Load Brier/RPS from prediction artifacts."""
    settings = _settings()
    artifact_dir = settings.data_root / "models" / "artifacts"
    calibration: dict[str, Any] = {}

    # Poisson calibration
    poisson_path = artifact_dir / "poisson_baseline_results.parquet"
    if poisson_path.exists():
        try:
            pf = _read_parquet(poisson_path)
            if not pf.empty:
                row = pf.iloc[0].to_dict()
                calibration["brier"] = _clean_json_value(row.get("brier_1x2"))
                calibration["rps"] = _clean_json_value(row.get("rps_1x2"))
                calibration["log_loss"] = _clean_json_value(row.get("log_loss_exact"))
        except Exception:
            pass

    # DC calibration (overrides if available)
    dc_path = artifact_dir / "dixon_coles_results.parquet"
    if dc_path.exists():
        try:
            dc_df = _read_parquet(dc_path)
            if not dc_df.empty:
                dc_row = dc_df.iloc[0].to_dict()
                calibration["brier"] = _clean_json_value(
                    dc_row.get("brier_1x2", calibration.get("brier"))
                )
                calibration["rps"] = _clean_json_value(
                    dc_row.get("rps_1x2", calibration.get("rps"))
                )
        except Exception:
            pass

    return calibration


def get_match_prediction(home_team: str, away_team: str) -> dict:
    try:
        prediction = load_score_prediction(home_team, away_team)
    except Exception as exc:
        return {"error": str(exc)}
    if isinstance(prediction, dict):
        return prediction
    result = {
        "home_team": home_team,
        "away_team": away_team,
        "model_type": "poisson",
        "model_version": "1.0",
        "home_lambda": prediction.home_lambda,
        "away_lambda": prediction.away_lambda,
        "home_win": prediction.summary.home_win,
        "draw": prediction.summary.draw,
        "away_win": prediction.summary.away_win,
        "over_2_5": prediction.summary.over_2_5,
        "btts_yes": prediction.summary.btts_yes,
        "score_matrix": _score_matrix_to_list(prediction),
        "calibration": _prediction_calibration(),
    }
    return _clean_json_value(result)


def get_match_prediction_dc(home_team: str, away_team: str) -> dict:
    """Predict a match using the Dixon-Coles model.

    Returns the same structure as get_match_prediction but with model_type='dixon_coles'
    and includes rho / home_advantage when available.
    Falls back gracefully when DC artifacts are missing.
    """
    try:
        prediction = load_score_prediction_dc(home_team, away_team)
    except Exception as exc:
        return {"error": str(exc)}
    if isinstance(prediction, dict):
        prediction["model_type"] = prediction.get("model_type", "dixon_coles")
        return prediction
    result = {
        "home_team": home_team,
        "away_team": away_team,
        "model_type": "dixon_coles",
        "model_version": "1.0",
        "home_lambda": prediction.home_lambda,
        "away_lambda": prediction.away_lambda,
        "home_win": prediction.summary.home_win,
        "draw": prediction.summary.draw,
        "away_win": prediction.summary.away_win,
        "over_2_5": prediction.summary.over_2_5,
        "btts_yes": prediction.summary.btts_yes,
        "score_matrix": _score_matrix_to_list(prediction),
        "calibration": _prediction_calibration(),
    }
    # Try to enrich with DC-specific parameters (rho, home_advantage)
    try:
        dc_path = (
            _settings().data_root / "models" / "artifacts" / "dixon_coles_results.parquet"
        )
        if dc_path.exists():


            dc_df = _read_parquet(dc_path)
            if not dc_df.empty:
                dc_row = dc_df.iloc[0].to_dict()
                if "rho" in dc_row:
                    result["rho"] = _clean_json_value(dc_row["rho"])
                if "home_advantage" in dc_row:
                    result["home_advantage"] = _clean_json_value(dc_row["home_advantage"])
    except Exception:
        pass  # enrichment is optional
    return _clean_json_value(result)


def get_value_summary() -> dict:
    oof = load_oof_predictions()
    if oof.empty:
        return {"status": "no_data", "players": [], "metrics": {}}

    # Filter out records with suspiciously low market values (Transfermarkt placeholder)
    # Values <= 200k are almost certainly data errors, not real valuations
    if "actual_market_value" in oof.columns:
        oof = oof[oof["actual_market_value"] > 200000].copy()

    # Build player-level value data
    player_data = []
    for _, row in oof.iterrows():
        record = {
            "player": row.get("player_name", ""),
            "team": row.get("team_name", ""),
            "actual_value": row.get("actual_market_value"),
            "predicted_value": row.get("predicted_market_value"),
            "residual_log": row.get("residual_log"),
            "fairness_label": row.get("fairness_label", ""),
        }
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                record[key] = None
        player_data.append(_clean_json_value(record))

    metrics: dict[str, Any] = {}
    results_path = _settings().data_root / "models" / "artifacts" / "value_fairness_results.parquet"
    if results_path.exists():
        try:


            results_df = _read_parquet(results_path)
            if not results_df.empty:
                metrics = _clean_json_value(results_df.iloc[0].to_dict())
        except Exception:
            pass

    mean_residual = None
    if "residual_log" in oof.columns:
        try:
            raw = oof["residual_log"].mean()
            mean_residual = float(raw) if raw == raw else None
        except Exception:
            mean_residual = None

    return _clean_json_value({
        "status": "ok",
        "sample_count": len(oof),
        "fairness_distribution": oof["fairness_label"].value_counts().to_dict()
        if "fairness_label" in oof.columns
        else {},
        "mean_residual_log": mean_residual,
        "metrics": metrics,
        "players": player_data,
    })


def get_player_ratings(
    position: str | None = None,
    league: str | None = None,
    team: str | None = None,
    season: str | None = None,
    limit: int = 20000,
) -> dict:
    """Return player ratings from DuckDB, sorted by optimized_score DESC."""
    df = load_player_ratings(position=position, league=league, team=team, season=season)
    if df.empty:
        return {"count": 0, "players": []}

    # Normalize confidence_level to uppercase for frontend
    if "confidence_level" in df.columns:
        df["confidence_level"] = df["confidence_level"].str.upper()

    # Alias sub_position → position_group for frontend compatibility
    if "sub_position" in df.columns and "position_group" not in df.columns:
        df["position_group"] = df["sub_position"]

    # Limit results
    df = df.head(limit)

    players = df.to_dict(orient="records")
    # Convert NaN to None for JSON serialization
    return _clean_json_value({"count": len(players), "players": players})


def get_ratings_meta() -> dict:
    """Return model metadata and league metrics."""
    meta_df = load_model_meta()
    league_df = load_league_metrics()

    meta = {}
    if not meta_df.empty:
        meta = meta_df.iloc[0].to_dict()

    leagues = league_df.to_dict(orient="records") if not league_df.empty else []

    return _clean_json_value({"model_meta": meta, "league_metrics": leagues})


def get_prediction_summary() -> dict[str, Any]:
    """Return baseline prediction artifact metadata."""
    artifact_path = (
        _settings().data_root
        / "models"
        / "artifacts"
        / "poisson_baseline_results.parquet"
    )
    poisson_info: dict[str, Any] = {"status": "no_data"}
    if artifact_path.exists():


        try:
            frame = _read_parquet(artifact_path)
            if not frame.empty:
                poisson_info = frame.iloc[0].to_dict()
                poisson_info["status"] = "ok"
        except Exception:
            pass

    # Dixon-Coles artifact info
    dc_path = (
        _settings().data_root
        / "models"
        / "artifacts"
        / "dixon_coles_results.parquet"
    )
    dc_info: dict[str, Any] = {"status": "not_available"}
    if dc_path.exists():


        try:
            dc_frame = _read_parquet(dc_path)
            if not dc_frame.empty:
                dc_info = dc_frame.iloc[0].to_dict()
                dc_info["status"] = "ok"
        except Exception:
            dc_info["status"] = "error"

    return _clean_json_value({
        "status": poisson_info.get("status", "no_data"),
        "model_type": poisson_info.get("model_type", "independent_poisson"),
        "num_teams": poisson_info.get("num_teams"),
        "train_rows": poisson_info.get("train_rows"),
        "coverage": poisson_info.get("coverage"),
        "poisson": poisson_info,
        "dixon_coles": dc_info,
        "available_models": (
            ["poisson"] + (["dixon_coles"] if dc_info.get("status") == "ok" else [])
        ),
    })


def get_prediction_calibration() -> dict[str, Any]:
    """Return calibration metrics for match prediction models.

    Compares Poisson vs Dixon-Coles side by side.
    Includes low-score breakdown (0-0, 1-0, 0-1, 1-1) and league coverage.
    """
    settings = _settings()
    model_root = settings.data_root / "models"
    artifact_dir = model_root / "artifacts"

    # --- DC calibration detail ---
    dc_detail_path = artifact_dir / "dc_calibration_detail.parquet"
    dc_metrics: dict[str, Any] = {"status": "not_available"}
    dc_low_score: list[dict[str, Any]] = []
    dc_calibration_plot: list[dict[str, Any]] = []
    dc_league_coverage: list[dict[str, Any]] = []

    if dc_detail_path.exists():
        import numpy as np


        try:
            dc_df = _read_parquet(dc_detail_path)
            if not dc_df.empty:
                # Compute metrics from detail
                clipped = dc_df["exact_score_probability"].clip(lower=1e-12)
                log_loss = float(-(np.log(clipped)).mean())

                probs_1x2 = dc_df.loc[
                    :,
                    ["home_win_probability", "draw_probability", "away_win_probability"],
                ].to_numpy()
                actual_map = {
                    "home_win": [1.0, 0.0, 0.0],
                    "draw": [0.0, 1.0, 0.0],
                    "away_win": [0.0, 0.0, 1.0],
                }
                actual = np.vstack(dc_df["actual_outcome"].map(actual_map))
                brier = float(np.mean(np.sum((probs_1x2 - actual) ** 2, axis=1)))

                # RPS
                probs_rps = dc_df.loc[
                    :,
                    ["away_win_probability", "draw_probability", "home_win_probability"],
                ].to_numpy()
                actual_rps = np.vstack(
                    dc_df["actual_outcome"].map(
                        {
                            "away_win": [1.0, 0.0, 0.0],
                            "draw": [0.0, 1.0, 0.0],
                            "home_win": [0.0, 0.0, 1.0],
                        },
                    ),
                )
                cum_probs = np.cumsum(probs_rps, axis=1)
                cum_actual = np.cumsum(actual_rps, axis=1)
                rps = float(np.mean(np.sum((cum_probs - cum_actual) ** 2, axis=1) / 2.0))

                dc_metrics = {
                    "status": "ok",
                    "log_loss_exact": round(log_loss, 4),
                    "brier_1x2": round(brier, 4),
                    "rps_1x2": round(rps, 4),
                    "n_matches": len(dc_df),
                }

                # Low-score breakdown
                for bucket in ["0-0", "1-0", "0-1", "1-1"]:
                    group = dc_df[dc_df["score_bucket"] == bucket]
                    n = len(group)
                    actual_pct = n / len(dc_df) * 100.0 if len(dc_df) > 0 else 0.0
                    mean_pred = (
                        float(group["exact_score_probability"].mean()) * 100.0
                        if n > 0 else 0.0
                    )
                    dc_low_score.append({
                        "score_bucket": bucket,
                        "n_matches": n,
                        "actual_pct": round(actual_pct, 2),
                        "mean_predicted_pct": round(mean_pred, 2),
                        "calibration_error": round(abs(actual_pct - mean_pred), 2),
                    })

                # Calibration plot data (decile bins of predicted home-win)
                bin_edges = np.linspace(0, 1, 11)
                hw_probs = dc_df["home_win_probability"].to_numpy()
                hw_actual = (dc_df["actual_outcome"] == "home_win").to_numpy().astype(float)
                bin_idx = np.clip(np.digitize(hw_probs, bin_edges) - 1, 0, 9)
                for b in range(10):
                    mask = bin_idx == b
                    if mask.sum() == 0:
                        continue
                    dc_calibration_plot.append({
                        "bin_center": round(float((bin_edges[b] + bin_edges[b + 1]) / 2), 2),
                        "n_matches": int(mask.sum()),
                        "mean_predicted": round(float(hw_probs[mask].mean()), 4),
                        "mean_actual": round(float(hw_actual[mask].mean()), 4),
                    })

                # League coverage
                if "league" in dc_df.columns:
                    for league, lg in dc_df.groupby("league", sort=True):
                        n_lg = len(lg)
                        if n_lg == 0:
                            continue
                        ll_lg = float(
                            -(np.log(
                                lg["exact_score_probability"].clip(lower=1e-12)
                            )).mean()
                        )
                        probs_lg = lg.loc[
                            :, ["home_win_probability", "draw_probability", "away_win_probability"]
                        ].to_numpy()
                        actual_lg = np.vstack(lg["actual_outcome"].map(actual_map))
                        brier_lg = float(np.mean(np.sum((probs_lg - actual_lg) ** 2, axis=1)))
                        dc_league_coverage.append({
                            "league": str(league),
                            "n_matches": n_lg,
                            "mean_log_loss": round(ll_lg, 4),
                            "mean_brier": round(brier_lg, 4),
                        })

        except Exception:
            dc_metrics = {"status": "error"}

    # --- Poisson calibration (from existing results parquet) ---
    poisson_metrics: dict[str, Any] = {"status": "not_available"}
    poisson_results_path = artifact_dir / "poisson_baseline_results.parquet"
    if poisson_results_path.exists():


        try:
            pf = _read_parquet(poisson_results_path)
            if not pf.empty:
                row = pf.iloc[0].to_dict()
                poisson_metrics = {
                    "status": "ok",
                    "log_loss_exact": _clean_json_value(row.get("log_loss_exact")),
                    "brier_1x2": _clean_json_value(row.get("brier_1x2")),
                    "rps_1x2": _clean_json_value(row.get("rps_1x2")),
                    "n_matches": _clean_json_value(row.get("n_matches")),
                }
        except Exception:
            poisson_metrics = {"status": "error"}

    return _clean_json_value({
        "dixon_coles": dc_metrics,
        "poisson": poisson_metrics,
        "low_score_breakdown": dc_low_score,
        "calibration_plot": dc_calibration_plot,
        "league_coverage": dc_league_coverage,
    })


def get_action_value_summary(
    limit: int = 20,
    offset: int = 0,
    full: bool = False,
) -> dict[str, Any]:
    """Return action value data combining xT and VAEP sources.

    When full=True, returns the complete merged dataset (xT + VAEP).
    Otherwise returns a sample (legacy behavior).
    Supports pagination via limit/offset.
    """
    import pandas as pd

    settings = _settings()
    xt_path = settings.data_root / "gold" / "feature_store" / "player_action_value.parquet"
    vaep_path = settings.data_root / "gold" / "feature_store" / "player_vaep.parquet"

    # Load xT data
    xt_df = pd.DataFrame()
    if xt_path.exists():
        try:
            xt_df = _read_parquet(xt_path)
        except Exception:
            pass

    # Load VAEP data
    vaep_df = pd.DataFrame()
    if vaep_path.exists():
        try:
            vaep_df = _read_parquet(vaep_path)
        except Exception:
            pass

    if xt_df.empty and vaep_df.empty:
        # Fallback to legacy player_value_metrics
        frame = load_player_value_metrics()
        if frame.empty:
            return {"status": "no_data", "count": 0, "players": []}

        working = frame.copy()
        if "composite_score" in working.columns:
            working = working.sort_values("composite_score", ascending=False)

        return _clean_json_value({
            "status": "ok",
            "count": len(working),
            "data_source": "StatsBomb Open Data + xT/VAEP model",
            "metrics": {
                "players_with_xt": (
                    int(working["xT_per_90"].notna().sum())
                    if "xT_per_90" in working.columns
                    else 0
                ),
                "players_with_finishing": int(working["finishing_delta"].notna().sum())
                if "finishing_delta" in working.columns
                else 0,
                "mean_xt_per_90": (
                    float(working["xT_per_90"].dropna().mean())
                    if "xT_per_90" in working.columns
                    else None
                ),
                "mean_composite_score": float(working["composite_score"].dropna().mean())
                if "composite_score" in working.columns
                else None,
            },
            "players": working.head(limit).to_dict(orient="records"),
        })

    # Merge xT + VAEP
    # Check if VAEP has usable player_name (non-empty)
    vaep_has_names = (
        not vaep_df.empty
        and "player_name" in vaep_df.columns
        and vaep_df["player_name"].replace("", pd.NA).notna().any()
    )

    if not vaep_df.empty and not vaep_has_names:
        # VAEP lacks usable player_name — return as separate sections
        xt_cols = [
            "player_name", "season", "team_id", "competition",
            "n_actions", "n_matches", "estimated_minutes",
            "xt_total", "xt_per_90",
            "passes_per_90", "shots_per_90", "carries_per_90", "dribbles_per_90",
            "final_third_per_90", "penalty_area_per_90",
            "pass_completion_rate", "forward_pass_rate",
        ]
        xt_select = [c for c in xt_cols if c in xt_df.columns]
        xt_part = xt_df[xt_select].copy()

        # Sort xT by xt_per_90 desc
        if "xt_per_90" in xt_part.columns:
            xt_part = xt_part.sort_values("xt_per_90", ascending=False)

        # Aggregate VAEP by player_id for summary
        vaep_summary_cols = [
            "player_id", "vaep_total", "vaep_per_90", "vaep_mean",
            "n_actions", "n_matches", "estimated_minutes", "minutes_90",
        ]
        vaep_select = [c for c in vaep_summary_cols if c in vaep_df.columns]
        vaep_summary = vaep_df[vaep_select].copy()
        numeric_cols = vaep_summary.select_dtypes(include=["number"]).columns.tolist()
        if "player_id" in vaep_summary.columns and numeric_cols:
            vaep_summary = vaep_summary.groupby("player_id", as_index=False)[numeric_cols].mean()
        if "vaep_per_90" in vaep_summary.columns:
            vaep_summary = vaep_summary.sort_values("vaep_per_90", ascending=False)

        total_count = len(xt_part) + len(vaep_summary)
        xt_page = xt_part.iloc[offset : offset + limit]
        vaep_offset = max(0, offset - len(xt_part))
        vaep_limit = max(0, limit - len(xt_page))
        vaep_page = vaep_summary.iloc[vaep_offset : vaep_offset + vaep_limit]

        metrics: dict[str, Any] = {
            "total_rows": total_count,
            "xt_rows": len(xt_part),
            "vaep_rows": len(vaep_summary),
        }
        if "xt_per_90" in xt_part.columns:
            metrics["mean_xt_per_90"] = round(float(xt_part["xt_per_90"].dropna().mean()), 4)
            metrics["players_with_xt"] = int(xt_part["xt_per_90"].notna().sum())
        if "vaep_per_90" in vaep_summary.columns:
            metrics["mean_vaep_per_90"] = round(
                float(vaep_summary["vaep_per_90"].dropna().mean()), 4
            )
            metrics["players_with_vaep"] = int(vaep_summary["vaep_per_90"].notna().sum())

        return _clean_json_value({
            "status": "ok",
            "count": total_count,
            "offset": offset,
            "limit": limit,
            "data_source": "StatsBomb Open Data + xT/VAEP model",
            "metrics": metrics,
            "players": xt_page.to_dict(orient="records"),
            "xt_players": xt_page.to_dict(orient="records"),
            "vaep_players": vaep_page.to_dict(orient="records"),
        })

    # Both have usable player_name — merge on player_name (+ season if both have it)
    xt_cols = [
        "player_name", "season", "team_id", "competition",
        "n_actions", "n_matches", "estimated_minutes",
        "xt_total", "xt_per_90",
        "passes_per_90", "shots_per_90", "carries_per_90", "dribbles_per_90",
        "final_third_per_90", "penalty_area_per_90",
        "pass_completion_rate", "forward_pass_rate",
    ]
    vaep_cols = [
        "player_name", "season",
        "vaep_total", "vaep_per_90", "vaep_mean",
        "n_actions", "n_matches", "estimated_minutes",
        "minutes_90",
    ]

    xt_select = [c for c in xt_cols if c in xt_df.columns]
    vaep_select = [c for c in vaep_cols if c in vaep_df.columns]

    xt_part = xt_df[xt_select].copy()
    vaep_part = vaep_df[vaep_select].copy()

    # If VAEP lacks season, aggregate to player level
    if not vaep_part.empty and "season" not in vaep_part.columns:
        agg_dict: dict[str, Any] = {}
        for c in vaep_part.columns:
            if c == "player_name":
                continue
            if vaep_part[c].dtype in ["float64", "float32", "int64", "int32"]:
                agg_dict[c] = "mean"
            else:
                agg_dict[c] = "first"
        if agg_dict:
            vaep_part = vaep_part.groupby("player_name", as_index=False).agg(agg_dict)

    # Rename overlapping columns in vaep to avoid collision
    overlap = set(xt_select) - {"player_name", "season"}
    rename_map = {c: f"vaep_{c}" for c in vaep_select if c in overlap}
    vaep_part = vaep_part.rename(columns=rename_map)

    # Determine merge keys
    merge_keys = ["player_name"]
    if "season" in xt_part.columns and "season" in vaep_part.columns:
        merge_keys.append("season")

    if not xt_part.empty and not vaep_part.empty:
        merged = pd.merge(xt_part, vaep_part, on=merge_keys, how="outer")
    elif not xt_part.empty:
        merged = xt_part
    else:
        merged = vaep_part

    if merged.empty:
        return {"status": "no_data", "count": 0, "players": []}

    # Sort by xt_per_90 descending (or vaep_per_90 as fallback)
    sort_col = "xt_per_90" if "xt_per_90" in merged.columns else "vaep_per_90"
    if sort_col in merged.columns:
        merged = merged.sort_values(sort_col, ascending=False)

    total_count = len(merged)
    page = merged.iloc[offset : offset + limit]

    # Summary metrics
    metrics: dict[str, Any] = {
        "total_rows": total_count,
        "xt_rows": len(xt_df),
        "vaep_rows": len(vaep_df),
        "merged_rows": total_count,
    }
    if "xt_per_90" in merged.columns:
        metrics["mean_xt_per_90"] = round(float(merged["xt_per_90"].dropna().mean()), 4)
        metrics["players_with_xt"] = int(merged["xt_per_90"].notna().sum())
    if "vaep_per_90" in merged.columns:
        metrics["mean_vaep_per_90"] = round(float(merged["vaep_per_90"].dropna().mean()), 4)
        metrics["players_with_vaep"] = int(merged["vaep_per_90"].notna().sum())

    return _clean_json_value({
        "status": "ok",
        "count": total_count,
        "offset": offset,
        "limit": limit,
        "data_source": "StatsBomb Open Data + xT/VAEP model",
        "metrics": metrics,
        "players": page.to_dict(orient="records"),
    })


def get_artifacts_summary() -> dict:
    """Return artifact counts and data health for the overview page."""
    ratings = load_player_ratings()
    player_match = load_player_match()
    team_match = load_team_match()
    oof = load_oof_predictions()

    settings = _settings()

    # Count events from StatsBomb
    events_count = 0
    events_path = settings.raw_root / "statsbomb_open" / "events_all.parquet"
    if events_path.exists():
        try:

            events_count = len(_read_parquet(events_path))
        except Exception:
            events_count = 0

    # Data health flags
    has_oof = not oof.empty
    has_truth = False
    truth_rows = 0
    truth_path = settings.data_root / "gold" / "feature_store" / "player_truth_labels.parquet"
    if truth_path.exists():
        try:

            truth_df = _read_parquet(truth_path)
            has_truth = len(truth_df) > 0
            truth_rows = len(truth_df)
        except Exception:
            pass

    # Player match coverage
    pm_coverage = ""
    if not player_match.empty and "data_granularity" in player_match.columns:
        match_count = (player_match["data_granularity"] == "match").sum()
        proxy_count = (player_match["data_granularity"] == "season_proxy").sum()
        pm_coverage = f"{match_count} real + {proxy_count} season proxy"

    artifact_registry = [
        _artifact_file_info(
            settings.data_root / "gold" / "feature_store" / "player_match.parquet",
            "player_match",
            rows=len(player_match),
        ),
        _artifact_file_info(
            settings.data_root / "gold" / "feature_store" / "team_match.parquet",
            "team_match",
            rows=len(team_match),
        ),
        _artifact_file_info(
            settings.data_root / "gold" / "feature_store" / "player_ratings_optimized.parquet",
            "player_ratings_optimized",
            rows=len(ratings),
        ),
        _artifact_file_info(events_path, "events_all", rows=events_count),
        _artifact_file_info(
            settings.data_root / "models" / "oof_predictions" / "value_fairness_oof.parquet",
            "value_fairness_oof",
            rows=len(oof),
        ),
        _artifact_file_info(truth_path, "player_truth_labels", rows=truth_rows),
    ]

    return _clean_json_value({
        "player_match_rows": len(player_match),
        "team_match_rows": len(team_match),
        "rating_rows": len(ratings),
        "event_samples": events_count,
        "data_source_label": data_source_label(),
        "artifacts": artifact_registry,
        "data_health": {
            "oof_available": has_oof,
            "truth_labels_available": has_truth,
            "player_match_coverage": pm_coverage,
            "confidence_gate": "coverage < 0.90 → low confidence only",
        },
        "license_attribution": {
            "statsbomb": "StatsBomb Open Data — free for research, must attribute source",
            "fbref": "FBref via soccerdata — personal research use only",
            "football_data": "Football-Data.co.uk — free for non-commercial use",
            "understat": "Understat — public data, attribution appreciated",
            "transfermarkt": "Transfermarkt — manual import only, no automated scraping",
        },
    })


def get_review_queue(limit: int = 200) -> dict:
    """Return low-confidence players from ratings data as a review queue."""
    df = load_player_ratings()
    if df.empty:
        return {"count": 0, "players": []}

    queues = build_scouting_queues(
        df,
        run_id=_latest_run_id(),
        reports_root=_settings().data_root / "reports",
    )
    return _queue_payload(queues.review_queue, limit=limit)


def get_watchlist(limit: int = 100) -> dict:
    df = load_player_ratings()
    if df.empty:
        return {"count": 0, "players": []}
    queues = build_scouting_queues(
        df,
        run_id=_latest_run_id(),
        reports_root=_settings().data_root / "reports",
    )
    return _queue_payload(queues.watchlist, limit=limit)


def get_shortlist(limit: int = 100) -> dict:
    df = load_player_ratings()
    if df.empty:
        return {"count": 0, "players": []}
    queues = build_scouting_queues(
        df,
        run_id=_latest_run_id(),
        reports_root=_settings().data_root / "reports",
    )
    return _queue_payload(queues.shortlist, limit=limit)


def _enrich_holdout_summary(meta: dict[str, Any]) -> None:
    """Extract a flat holdout summary from metrics for easy frontend display."""
    metrics = meta.get("metrics", {})
    holdout = meta.get("holdout", {})

    # Source: prefer holdout dict, fallback to metrics dict
    src = holdout if holdout else metrics

    # Find the optimized test metrics (most relevant for reporting)
    # Metrics may be stored as JSON strings in meta.json
    def _parse(m: Any) -> dict:
        if isinstance(m, str):
            try:
                return json.loads(m)
            except (json.JSONDecodeError, TypeError):
                return {}
        return m if isinstance(m, dict) else {}

    opt_test = _parse(src.get("optimized_test", {}))
    base_test = _parse(src.get("baseline_test", {}))
    opt_train = _parse(src.get("optimized_train", {}))
    base_train = _parse(src.get("baseline_train", {}))

    def _pick(m: dict) -> dict:
        return {k: v for k, v in m.items() if k in (
            "spearman", "pearson", "rank_loss", "z_mse", "calibration_mae",
            "points_mae", "points_rmse", "points_bias",
            "points_spread_ratio", "raw_spread_ratio",
            "n_players", "n_team_seasons", "team_coverage",
            "split",
        )}

    summary: dict[str, Any] = {}
    if opt_test:
        summary["optimized_test"] = _pick(opt_test)
    elif "optimized_test" in metrics:
        summary["optimized_test"] = _pick(_parse(metrics["optimized_test"]))
    if base_test:
        summary["baseline_test"] = _pick(base_test)
    if opt_train:
        summary["optimized_train"] = _pick(opt_train)
    if base_train:
        summary["baseline_train"] = _pick(base_train)

    # Flat top-level aliases for simple frontend display
    best = opt_test or _parse(metrics.get("optimized_test", {})) or metrics
    for key in ("spearman", "pearson", "rank_loss", "calibration_mae",
                "n_players", "n_team_seasons", "team_coverage"):
        if key in best and key not in meta:
            meta[key] = best[key]

    # Overfit gap
    if "overfit_rank_loss_gap" in src:
        summary["overfit_rank_loss_gap"] = src["overfit_rank_loss_gap"]
    elif "overfit_rank_loss_gap" in metrics:
        summary["overfit_rank_loss_gap"] = metrics["overfit_rank_loss_gap"]

    meta["holdout_summary"] = summary


def _build_reproduce_command(run_id: str, args: dict[str, Any]) -> str:
    """Build a reproduce command string from stored run args."""
    parts = ["PYTHONPATH=src", "uv run python scripts/optimize_ratings_gpu.py"]
    if args.get("seed") is not None:
        parts.append(f"--seed {args['seed']}")
    if args.get("pop_size") is not None:
        parts.append(f"--pop {args['pop_size']}")
    if args.get("n_steps") is not None:
        parts.append(f"--steps {args['n_steps']}")
    if args.get("lr") is not None:
        parts.append(f"--lr {args['lr']}")
    if args.get("patience") is not None:
        parts.append(f"--patience {args['patience']}")
    if args.get("spearman_weight") is not None:
        parts.append(f"--spearman-weight {args['spearman_weight']}")
    if args.get("ndcg_weight") is not None:
        parts.append(f"--ndcg-weight {args['ndcg_weight']}")
    if args.get("position_consistency_weight") is not None:
        parts.append(f"--position-consistency-weight {args['position_consistency_weight']}")
    if args.get("points_regression_weight") is not None:
        parts.append(f"--points-regression-weight {args['points_regression_weight']}")
    if args.get("warmup_steps") is not None:
        parts.append(f"--warmup-steps {args['warmup_steps']}")
    if args.get("grad_clip") is not None:
        parts.append(f"--grad-clip {args['grad_clip']}")
    if args.get("dc_likelihood_weight") is not None and args["dc_likelihood_weight"] > 0:
        parts.append(f"--dc-likelihood-weight {args['dc_likelihood_weight']}")
    if args.get("dc_rho") is not None:
        parts.append(f"--dc-rho {args['dc_rho']}")
    return " ".join(parts)


def get_model_runs() -> dict:
    """Return model run registry from local artifacts."""
    settings = _settings()
    runs = []
    ds_label = data_source_label()

    # Check data/models/runs/ directory
    runs_dir = settings.data_root / "models" / "runs"
    if runs_dir.exists():
        for run_dir in sorted(runs_dir.iterdir(), reverse=True):
            meta_path = run_dir / "meta.json"
            if meta_path.exists():
                meta = _read_json(meta_path)
                meta["run_id"] = run_dir.name
                meta["updated_at"] = meta_path.stat().st_mtime
                meta["data_source"] = ds_label
                # Build reproduce command from stored args
                run_args = meta.get("args", {})
                meta["reproduce_command"] = _build_reproduce_command(
                    run_dir.name, run_args,
                )
                # Extract holdout metrics summary for easy frontend access
                _enrich_holdout_summary(meta)
                runs.append(meta)

    # Fallback: read optimized_params_meta.json
    if not runs:
        meta_path = settings.data_root / "gold" / "feature_store" / "optimized_params_meta.json"
        if meta_path.exists():
            meta = _read_json(meta_path)
            meta["run_id"] = "latest"
            meta["updated_at"] = meta_path.stat().st_mtime
            meta["data_source"] = ds_label
            run_args = meta.get("args", {})
            meta["reproduce_command"] = _build_reproduce_command("latest", run_args)
            _enrich_holdout_summary(meta)
            runs.append(meta)

    return _clean_json_value({"runs": runs, "count": len(runs)})


def _get_run_ids() -> list[str]:
    """Return list of available run IDs."""
    settings = _settings()
    runs_dir = settings.data_root / "models" / "runs"
    if runs_dir.exists():
        return sorted([d.name for d in runs_dir.iterdir() if d.is_dir()], reverse=True)
    return []


def get_model_run_detail(run_id: str) -> dict[str, Any]:
    """Return full details for a single model run.

    Includes run_id, timestamp, input_hash, params, metrics,
    train/test split, feature importance, and data source attribution.
    """
    settings = _settings()
    ds_label = data_source_label()
    runs_dir = settings.data_root / "models" / "runs"

    # Check the runs directory for the specific run
    if runs_dir.exists():
        run_dir = runs_dir / run_id
        meta_path = run_dir / "meta.json"
        if meta_path.exists():
            meta = _read_json(meta_path)
            meta["run_id"] = run_id
            meta["updated_at"] = meta_path.stat().st_mtime
            meta["data_source"] = ds_label

            # Build reproduce command from stored args
            run_args = meta.get("args", {})
            meta["reproduce_command"] = _build_reproduce_command(run_id, run_args)

            # Extract holdout metrics summary
            _enrich_holdout_summary(meta)

            # Load feature importance if available
            importance_path = run_dir / "feature_importance.parquet"
            if importance_path.exists():
    
                try:
                    fi_df = _read_parquet(importance_path)
                    meta["feature_importance"] = _clean_json_value(
                        fi_df.to_dict(orient="records"),
                    )
                except Exception:
                    meta["feature_importance"] = []

            # Load optimized params info
            params_path = run_dir / "optimized_params.npy"
            if params_path.exists():
                import numpy as np
                try:
                    params = np.load(params_path)
                    meta["params_summary"] = {
                        "shape": list(params.shape),
                        "mean": round(float(params.mean()), 6),
                        "std": round(float(params.std()), 6),
                        "min": round(float(params.min()), 6),
                        "max": round(float(params.max()), 6),
                    }
                except Exception:
                    pass

            # Data source attribution
            meta["data_attribution"] = {
                "primary_source": ds_label,
                "license_note": (
                    "Player ratings derived from FBref/Understat data. "
                    "Match results from Football-Data.co.uk. "
                    "Event data from StatsBomb Open Data."
                ),
            }

            return _clean_json_value(meta)

    # Fallback: check optimized_params_meta.json
    meta_path = settings.data_root / "gold" / "feature_store" / "optimized_params_meta.json"
    if meta_path.exists() and run_id in ("latest", "latest-local"):
        meta = _read_json(meta_path)
        meta["run_id"] = "latest"
        meta["updated_at"] = meta_path.stat().st_mtime
        meta["data_source"] = ds_label
        run_args = meta.get("args", {})
        meta["reproduce_command"] = _build_reproduce_command("latest", run_args)
        _enrich_holdout_summary(meta)
        meta["data_attribution"] = {
            "primary_source": ds_label,
            "license_note": (
                "Player ratings derived from FBref/Understat data. "
                "Match results from Football-Data.co.uk. "
                "Event data from StatsBomb Open Data."
            ),
        }
        return _clean_json_value(meta)

    return {"error": f"Run '{run_id}' not found", "available_runs": _get_run_ids()}


def _player_list_to_csv(player_list: list[dict]) -> str:
    """Convert a list of player dicts to CSV text."""
    import csv
    import io

    if not player_list:
        return ""
    buf = io.StringIO()
    fieldnames = list(player_list[0].keys())
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in player_list:
        writer.writerow(row)
    return buf.getvalue()


def _confidence_reason(minutes: float, matches_count: int, pool_size: int) -> str:
    """Return a human-readable explanation for the confidence level."""
    reasons = []
    if minutes < 450:
        reasons.append("very few minutes (<450)")
    elif minutes < 900:
        reasons.append("limited minutes (<900)")
    if matches_count < 10:
        reasons.append("few matches (<10)")
    elif matches_count < 20:
        reasons.append("below 20 matches")
    if pool_size < 10:
        reasons.append("small position pool (<10)")
    if not reasons:
        return "adequate minutes, matches, and peer pool"
    return "; ".join(reasons)


def _build_position_explanation(
    row: Any,
    pos_pool: Any,
    attack_score: float,
    defense: float,
    possession: float,
    minutes: float,
    score: float,
) -> dict[str, Any]:
    """Build position-wise explanation for each rating dimension."""
    import pandas as _pd

    def _pct_rank(value: float, pool: Any, col: str) -> float:
        clean = _pd.to_numeric(pool[col], errors="coerce").dropna()
        if clean.empty or value != value:
            return 50.0
        return float((clean < value).sum() / len(clean) * 100)

    def _confidence_label(minutes_val: float, pool_size: int) -> str:
        if minutes_val >= 2700 and pool_size >= 20:
            return "HIGH"
        if minutes_val >= 900 and pool_size >= 10:
            return "MEDIUM"
        return "LOW"

    dims: dict[str, Any] = {}
    pool_size = len(pos_pool)
    conf = _confidence_label(minutes, pool_size)

    # Attack
    attack_col = "npg_p90" if "npg_p90" in pos_pool.columns else "optimized_score"
    attack_pct = _pct_rank(attack_score, pos_pool, attack_col)
    # Adjust: add assists percentile
    if "assists_p90" in pos_pool.columns:
        assists_vals = _pd.to_numeric(
            pos_pool["assists_p90"], errors="coerce",
        ).fillna(0)
        player_assists = float(row.get("assists_p90", 0) or 0)
        assists_pct = float(
            (assists_vals < player_assists).sum()
            / max(len(assists_vals), 1) * 100
        )
        attack_pct = (attack_pct + assists_pct) / 2
    dims["attack"] = {
        "raw_score": round(attack_score, 3),
        "percentile_rank": round(attack_pct, 1),
        "contribution": round(attack_pct * 0.30, 1),
        "confidence": conf,
    }

    # Defense
    if "defense_composite" in pos_pool.columns:
        defense_pct = _pct_rank(
            defense, pos_pool, "defense_composite",
        )
    else:
        defense_pct = 50.0
    dims["defense"] = {
        "raw_score": round(defense, 2) if defense == defense else None,
        "percentile_rank": round(defense_pct, 1),
        "contribution": round(defense_pct * 0.20, 1),
        "confidence": conf,
    }

    # Possession
    if "possession_composite" in pos_pool.columns:
        poss_pct = _pct_rank(
            possession, pos_pool, "possession_composite",
        )
    else:
        poss_pct = 50.0
    dims["possession"] = {
        "raw_score": round(possession, 2) if possession == possession else None,
        "percentile_rank": round(poss_pct, 1),
        "contribution": round(poss_pct * 0.20, 1),
        "confidence": conf,
    }

    # Availability
    avail_pct = min(100.0, minutes / 2700 * 100)
    dims["availability"] = {
        "raw_score": round(minutes),
        "percentile_rank": round(min(100.0, avail_pct), 1),
        "contribution": round(avail_pct * 0.10, 1),
        "confidence": conf,
    }

    # Quality (overall score percentile)
    if "optimized_score" in pos_pool.columns:
        quality_pct = _pct_rank(
            score, pos_pool, "optimized_score",
        )
    else:
        quality_pct = 50.0
    dims["quality"] = {
        "raw_score": round(score, 1),
        "percentile_rank": round(quality_pct, 1),
        "contribution": round(quality_pct * 0.20, 1),
        "confidence": conf,
    }

    return dims


def _compute_position_percentiles(row: Any, pos_pool: Any) -> dict[str, Any]:
    """Compute within-position percentile ranks for key metrics."""
    import pandas as pd

    from scoutfootball.evaluation.position_metrics import (
        POSITION_DIMENSIONS,
        POSITION_GROUP_MAP,
        compute_dimension_percentile,
    )

    raw_position = str(row.get("position_group", ""))
    resolved = POSITION_GROUP_MAP.get(raw_position, raw_position)
    dim_defs = POSITION_DIMENSIONS.get(resolved, {})

    result: dict[str, Any] = {}
    for dim_key, dim_cfg in dim_defs.items():
        label = dim_cfg.get("label", dim_key)
        pct = compute_dimension_percentile(pos_pool, dim_cfg, row)
        result[dim_key] = {"label": label, "percentile": round(pct, 1)}

    # Add overall optimized_score percentile within position
    if "optimized_score" in pos_pool.columns:
        clean = pd.to_numeric(pos_pool["optimized_score"], errors="coerce").dropna()
        score_val = pd.to_numeric(row.get("optimized_score"), errors="coerce")
        if not clean.empty and pd.notna(score_val):
            overall_pct = float((clean < score_val).mean() * 100)
        else:
            overall_pct = None
    else:
        overall_pct = None
    result["overall_score"] = {
        "label": "综合评分",
        "percentile": round(overall_pct, 1) if overall_pct is not None else None,
    }

    return result


def _compute_low_confidence_reasons(row: Any) -> list[str]:
    """Compute low-confidence reasons using the confidence module."""
    from scoutfootball.evaluation.confidence import assess_player_confidence

    assessment = assess_player_confidence(row)
    return list(assessment.reasons)


def _compute_3season_trend(player_rows: Any) -> list[dict[str, Any]]:
    """Compute 3-season trend data for a player from their season rows."""

    if player_rows.empty:
        return []

    # Sort by season descending, take up to 3
    sorted_rows = player_rows.sort_values("season", ascending=False).head(3)

    trends = []
    for _, r in sorted_rows.iterrows():
        entry: dict[str, Any] = {
            "season": str(r.get("season", "")),
            "optimized_score": round(float(r.get("optimized_score", 0) or 0), 1),
            "goals": round(float(r.get("npg_p90", 0) or 0), 3),
            "assists": round(float(r.get("assists_p90", 0) or 0), 3),
            "minutes": round(float(r.get("minutes", 0) or 0)),
        }
        trends.append(entry)

    # Compute deltas (newest vs oldest)
    if len(trends) >= 2:
        newest = trends[0]
        oldest = trends[-1]
        delta = {
            "season_from": oldest["season"],
            "season_to": newest["season"],
            "score_change": round(newest["optimized_score"] - oldest["optimized_score"], 1),
            "goals_change": round(newest["goals"] - oldest["goals"], 3),
            "assists_change": round(newest["assists"] - oldest["assists"], 3),
            "minutes_change": round(newest["minutes"] - oldest["minutes"]),
        }
        return {"seasons": trends, "delta": delta}
    return {"seasons": trends, "delta": None}


def get_player_profile(
    player_name: str,
    season: str | None = None,
    position_group: str | None = None,
    limit: int = 50,
    offset: int = 0,
    fmt: str = "json",
) -> dict:
    """Return detailed player profile with radar dimensions.

    Supports fuzzy name matching, pagination, position/season filters,
    rating snapshot history, xT integration, confidence explanation,
    and CSV export.
    """
    import pandas as pd

    df = load_player_ratings()

    # Alias sub_position → position_group for frontend compatibility
    if "sub_position" in df.columns and "position_group" not in df.columns:
        df["position_group"] = df["sub_position"]

    # Fuzzy search: exact match first, then partial case-insensitive
    exact_mask = df["player"] == player_name
    if exact_mask.any():
        mask = exact_mask
    else:
        mask = df["player"].str.contains(player_name, case=False, na=False)
    if position_group:
        mask = mask & (df["position_group"] == position_group)
    if season:
        mask = mask & (df["season"] == season)
    rows = df[mask]
    total = int(rows.shape[0])

    # If multiple players matched (fuzzy), return list with pagination
    if not exact_mask.any() and total > 1:
        unique_names = rows["player"].unique()
        page_names = unique_names[offset : offset + limit]
        page_rows = rows[rows["player"].isin(page_names)]
        player_list = []
        for pname in page_names:
            pr = page_rows[page_rows["player"] == pname]
            best = pr.loc[pr["optimized_score"].idxmax()] if not pr.empty else pr.iloc[0]
            player_list.append(_clean_json_value({
                "player": pname,
                "found": True,
                "team": best.get("team", ""),
                "league": best.get("league", ""),
                "season": best.get("season", ""),
                "position_group": best.get("position_group", ""),
                "optimized_score": round(float(best.get("optimized_score", 0) or 0), 1),
                "minutes": round(float(best.get("minutes", 0) or 0)),
            }))
        # CSV export
        if fmt == "csv" and player_list:
            return _player_list_to_csv(player_list)
        return _clean_json_value({
            "player": player_name,
            "found": True,
            "fuzzy_match": True,
            "total": total,
            "offset": offset,
            "limit": limit,
            "players": player_list,
        })

    if rows.empty:
        return {"player": player_name, "found": False}

    # Pick the best season (highest score) if multiple
    try:
        row = rows.loc[rows["optimized_score"].idxmax()]
    except (ValueError, TypeError):
        row = rows.iloc[0]

    # Build radar dimensions from available data
    # Attack: npg_p90 + assists_p90 percentile within position
    # Possession: possession_composite
    # Defense: defense_composite
    # Reliability: minutes-based (900+ = high, 450+ = medium)
    # Impact: optimized_score percentile within position

    position = row.get("position_group", "")
    pos_pool = df[df["position_group"] == position]

    def _pct(value: float, pool: pd.Series) -> float:
        clean = pd.to_numeric(pool, errors="coerce").dropna()
        if clean.empty or value != value:
            return 50.0
        return float((clean < value).sum() / len(clean) * 100)

    npg = float(row.get("npg_p90", 0) or 0)
    assists = float(row.get("assists_p90", 0) or 0)
    attack_score = npg + assists
    defense = float(row.get("defense_composite", 0) or 0)
    possession = float(row.get("possession_composite", 0) or 0)
    minutes = float(row.get("minutes", 0) or 0)
    score = float(row.get("optimized_score", 0) or 0)

    radar = [
        round(_pct(attack_score, pos_pool["npg_p90"].fillna(0) + pos_pool["assists_p90"].fillna(0)), 1),  # noqa: E501
        round(_pct(possession, pos_pool["possession_composite"]), 1),
        round(_pct(defense, pos_pool["defense_composite"]), 1),
        round(min(100, minutes / 2700 * 100), 1),  # 2700 min = 30 full matches
        round(_pct(score, pos_pool["optimized_score"]), 1),
    ]

    # All seasons for this player
    seasons = []
    for _, r in rows.sort_values("season").iterrows():
        seasons.append({
            "season": r.get("season", ""),
            "team": r.get("team", ""),
            "league": r.get("league", ""),
            "position_group": r.get("position_group", ""),
            "optimized_score": round(float(r.get("optimized_score", 0) or 0), 1),
            "minutes": round(float(r.get("minutes", 0) or 0)),
        })

    low_appearance = bool(row.get("low_appearance", False))
    matches_count = int(row.get("matches", 0) or 0)

    # xT integration from player_value_metrics
    xt_summary: dict[str, Any] = {"available": False}
    try:
        vm = load_player_value_metrics()
        if not vm.empty and "player_name" in vm.columns:
            player_xt = vm[vm["player_name"].str.lower() == player_name.lower()]
            if not player_xt.empty:
                xt_row = player_xt.iloc[0]
                xt_per_90 = xt_row.get("xT_per_90")
                xt_total = xt_row.get("total_xt")
                # Compute xT percentile within position
                xt_pct = None
                if "xT_per_90" in vm.columns and position:
                    pos_names = df[df["position_group"] == position]["player"].unique()
                    pos_xt = vm[vm["player_name"].isin(pos_names)]["xT_per_90"].dropna()
                    if not pos_xt.empty and pd.notna(xt_per_90):
                        xt_pct = round(float((pos_xt < xt_per_90).sum() / len(pos_xt) * 100), 1)
                # xT contribution estimate
                xt_contribution = None
                if pd.notna(xt_per_90) and score > 0:
                    xt_contribution = round(float(xt_per_90 / 0.3 * 10), 1)
                xt_summary = {
                    "available": True,
                    "xT_per_90": round(float(xt_per_90), 4) if pd.notna(xt_per_90) else None,
                    "xT_total": round(float(xt_total), 4) if pd.notna(xt_total) else None,
                    "xT_percentile": xt_pct,
                    "xT_contribution": xt_contribution,
                    "coverage_note": "StatsBomb Open Data sample only",
                }
    except Exception:
        xt_summary = {"available": False, "reason": "xT data not available for this player"}

    # Confidence reason explanation
    pool_size = len(pos_pool)
    conf_reason = _confidence_reason(minutes, matches_count, pool_size)

    # Build position explanation with xT
    position_explanation = _build_position_explanation(
        row, pos_pool, attack_score, defense, possession, minutes, score,
    )
    if xt_summary.get("available"):
        _cov = xt_summary.get("coverage_note") or ""
        _xt_conf = "LOW" if "StatsBomb" in _cov else "MEDIUM"
        position_explanation["xT"] = {
            "xT_per_90": xt_summary.get("xT_per_90"),
            "percentile_rank": xt_summary.get("xT_percentile"),
            "contribution": xt_summary.get("xT_contribution"),
            "confidence": _xt_conf,
        }
    else:
        position_explanation["xT"] = {
            "xT_per_90": None,
            "percentile_rank": None,
            "contribution": None,
            "confidence": "N/A",
            "note": "xT data not available for this player",
        }

    result = _clean_json_value({
        "player": player_name,
        "found": True,
        "team": row.get("team", ""),
        "league": row.get("league", ""),
        "season": row.get("season", ""),
        "position_group": position,
        "optimized_score": round(score, 1),
        "minutes": round(minutes),
        "matches": matches_count,
        "low_appearance": low_appearance,
        "confidence_level": str(row.get("confidence_level", "LOW")).upper(),
        "confidence_reason": conf_reason,
        "npg_p90": round(npg, 3),
        "assists_p90": round(assists, 3),
        "defense_composite": round(defense, 2) if defense == defense else None,
        "possession_composite": round(possession, 2) if possession == possession else None,
        "radar": radar,
        "seasons": seasons,
        "position_explanation": position_explanation,
        "xt_summary": xt_summary,
        "position_percentiles": _compute_position_percentiles(row, pos_pool),
        "low_confidence_reasons": _compute_low_confidence_reasons(row),
        "trend_3seasons": _compute_3season_trend(rows),
    })
    # CSV export
    if fmt == "csv":
        return _player_list_to_csv([result])
    return result


# ── World Cup endpoints ──────────────────────────────────────────────────


def get_wc_groups() -> dict:
    """Return World Cup group data with team strength ratings."""
    ratings_df = load_player_ratings()
    enriched = enrich_squads_with_ratings(ratings_df)
    strengths = compute_team_strengths(enriched_squads=enriched)

    groups_data = []
    for letter, teams in GROUPS.items():
        group_teams = []
        for team in teams:
            squad = enriched.get(team, [])
            rated = [p for p in squad if p.has_rating]
            big5_count = sum(1 for p in squad if p.club_league in BIG5_LEAGUES)
            avg_rating = (
                round(sum(p.rating for p in rated) / len(rated), 2)
                if rated else None
            )
            group_teams.append({
                "team": team,
                "is_host": team in HOSTS,
                "strength": round(strengths.get(team, 0), 3),
                "rated_players": len(rated),
                "total_players": len(squad),
                "big5_players": big5_count,
                "avg_rating": avg_rating,
            })
        groups_data.append({
            "group": letter,
            "teams": group_teams,
        })

    return _clean_json_value({
        "status": "ok",
        "source_attribution": (
            "Ratings derived from FBref/Understat data "
            "via ScoutFootball optimizer"
        ),
        "disclaimer": (
            "Squad ratings are from domestic league performance, "
            "not national team matches. Non-Big5 league players "
            "may lack rating data."
        ),
        "groups": groups_data,
    })


def get_wc_schedule(
    group: str | None = None,
    matchday: int | None = None,
) -> dict:
    """Return World Cup group stage schedule."""
    matches = generate_group_stage_matches()

    match_dicts = []
    for m in matches:
        if group and m.group != group:
            continue
        if matchday and m.matchday != matchday:
            continue
        match_dicts.append({
            "matchday": m.matchday,
            "date": m.date,
            "time_et": m.time_et,
            "home": m.home,
            "away": m.away,
            "venue": m.venue,
            "city": m.city,
            "group": m.group,
            "stage": m.stage,
        })

    return _clean_json_value({
        "status": "ok",
        "count": len(match_dicts),
        "source_attribution": (
            "Schedule generated from official FIFA fixture pattern; "
            "dates/venues are approximate"
        ),
        "matches": match_dicts,
    })


def get_wc_squad(team: str) -> dict:
    """Return a specific team's World Cup squad with player ratings."""
    ratings_df = load_player_ratings()
    squad = get_squad(team)
    squad = enrich_squad_with_ratings(squad, ratings_df)

    group = get_team_group(team)
    rated = [p for p in squad if p.has_rating]
    big5_count = sum(1 for p in squad if p.club_league in BIG5_LEAGUES)
    avg_rating = (
        round(sum(p.rating for p in rated) / len(rated), 2)
        if rated else None
    )

    players = []
    for p in squad:
        players.append({
            "name": p.name,
            "position": p.position,
            "club": p.club,
            "club_league": p.club_league,
            "has_rating": p.has_rating,
            "rating": round(p.rating, 2) if p.rating is not None else None,
            "rating_confidence": p.rating_confidence,
        })

    # Sort: rated players first, then by rating desc
    players.sort(key=lambda p: (not p["has_rating"], -(p["rating"] or 0)))

    return _clean_json_value({
        "status": "ok",
        "team": team,
        "group": group,
        "is_host": team in HOSTS,
        "total_players": len(squad),
        "rated_players": len(rated),
        "big5_players": big5_count,
        "avg_rating": avg_rating,
        "source_attribution": (
            "Ratings derived from FBref/Understat data "
            "via ScoutFootball optimizer"
        ),
        "disclaimer": (
            "Squad rosters are placeholder lists; official 26-man "
            "squads not yet announced. Ratings from domestic league "
            "performance only."
        ),
        "players": players,
    })


def get_wc_predictions() -> dict:
    """Return World Cup group stage predictions based on team strengths."""
    ratings_df = load_player_ratings()
    enriched = enrich_squads_with_ratings(ratings_df)
    strengths = compute_team_strengths(enriched_squads=enriched)
    group_preds = compute_group_predictions(strengths)

    # Build 48-team ranking
    ranked = sorted(strengths.items(), key=lambda x: x[1], reverse=True)
    ranking = []
    for rank, (team, strength) in enumerate(ranked, 1):
        group = get_team_group(team)
        squad = enriched.get(team, [])
        rated = [p for p in squad if p.has_rating]
        ranking.append({
            "rank": rank,
            "team": team,
            "group": group,
            "strength": round(strength, 3),
            "rated_players": len(rated),
        })

    # Best 3rd-place predictions
    third_place = []
    for gp in group_preds:
        teams = gp["teams"]
        if len(teams) >= 3:
            third = teams[2]
            third["group"] = gp["group"]
            third_place.append(third)
    third_place.sort(key=lambda x: x["strength"], reverse=True)

    return _clean_json_value({
        "status": "ok",
        "source_attribution": (
            "Predictions based on squad ratings from "
            "FBref/Understat data and Opta public priors"
        ),
        "disclaimer": (
            "Probabilities are rough estimates from a simplified "
            "strength-ratio model. Non-Big5 league team strengths "
            "may be underestimated. Not a real match prediction."
        ),
        "groups": group_preds,
        "ranking": ranking,
        "best_third_place": third_place[:8],
    })


def get_wc_teams() -> dict:
    """Return all 48 World Cup teams with strength ratings and group info."""
    ratings_df = load_player_ratings()
    enriched = enrich_squads_with_ratings(ratings_df)
    strengths = compute_team_strengths(enriched_squads=enriched)

    teams_data = []
    for letter, team_names in GROUPS.items():
        for team in team_names:
            squad = enriched.get(team, [])
            rated = [p for p in squad if p.has_rating]
            big5_count = sum(1 for p in squad if p.club_league in BIG5_LEAGUES)
            avg_rating = (
                round(sum(p.rating for p in rated) / len(rated), 2)
                if rated else None
            )
            teams_data.append({
                "team": team,
                "group": letter,
                "is_host": team in HOSTS,
                "strength": round(strengths.get(team, 0), 3),
                "rated_players": len(rated),
                "total_players": len(squad),
                "big5_players": big5_count,
                "avg_rating": avg_rating,
            })

    return _clean_json_value({
        "status": "ok",
        "count": len(teams_data),
        "source_attribution": (
            "Ratings derived from FBref/Understat data "
            "via ScoutFootball optimizer"
        ),
        "disclaimer": (
            "Squad ratings are from domestic league performance, "
            "not national team matches. Non-Big5 league players "
            "may lack rating data."
        ),
        "teams": teams_data,
    })

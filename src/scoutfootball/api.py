"""FastAPI read-only service layer for ScoutFootball."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scoutfootball.config import PlatformSettings

import numpy as np
import pandas as pd

# Preload the recruitment and opposition packs so their parent-package
# ``__init__.py`` runs single-threaded at module load time.  The store
# helpers below (``_brief_store``, ``_dossier_store``, ``_briefing_store``,
# ``_review_store``) still use local ``from ... import ...`` statements
# for symmetry, but those become no-ops once the parent package is in
# ``sys.modules``.  Without this preload, two concurrent FastAPI request
# threads can trigger the parent package's first import simultaneously
# and deadlock on the module lock (one thread holds
# ``scoutfootball.opposition`` and waits for ``scoutfootball.opposition.store``;
# the other holds ``scoutfootball.opposition.store`` and waits for
# ``scoutfootball.opposition``).
import scoutfootball.opposition  # noqa: E402,F401
import scoutfootball.recruitment  # noqa: E402,F401
from scoutfootball.action_value.evidence import (
    get_action_value_evidence as _get_action_value_evidence,
)
from scoutfootball.action_value.evidence import (
    get_action_value_evidence_index as _get_action_value_evidence_index,
)
from scoutfootball.app.data_loader import (
    _MISSING,
    _TTLCache,
    data_source_label,
    frame_is_synthetic,
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
from scoutfootball.evaluation.canonical_resolver import load_resolved_player_ratings
from scoutfootball.evaluation.scouting_queue import build_scouting_queues
from scoutfootball.head_to_head import get_head_to_head as _compute_head_to_head
from scoutfootball.head_to_head import load_match_results as _load_match_results
from scoutfootball.storage.csv_safety import sanitize_csv_row
from scoutfootball.worldcup.data import (
    BIG5_LEAGUES,
    GROUPS,
    HOSTS,
    compute_group_predictions,
    compute_squad_balance,
    compute_team_strength_details,
    enrich_squads_with_ratings,
    generate_group_stage_matches,
    get_squad,
    get_team_group,
)
from scoutfootball.worldcup.data import (
    compute_team_outlook as _compute_team_outlook,
)
from scoutfootball.worldcup.data import (
    simulate_knockout as _simulate_knockout,
)

logger = logging.getLogger(__name__)

_STATSBOMB_ATTRIBUTION = (
    "StatsBomb Open Data must be attributed in any public display. "
    "License: CC-BY-SA 4.0. See https://github.com/statsbomb/open-data"
)


def _make_error_response(error: str, *, message: str | None = None) -> dict[str, Any]:
    """Build a uniform error response dict.

    All API-level error responses use this shape so callers can check
    ``response.get("status") == "error"`` uniformly and read either
    ``response["error"]`` (short code or exception message) or
    ``response["message"]`` (human-readable description) without
    shape-specific branching. ``error`` and ``message`` carry the same
    string by default; pass an explicit ``message`` when ``error`` is
    an enum-like code (e.g. ``"no_data"``) and a friendlier description
    should be displayed to the user.
    """
    return {"status": "error", "error": error, "message": message or error}


def _read_parquet(path: Path):
    """Read a Parquet file via DuckDB (avoids pyarrow dependency)."""
    import duckdb

    con = duckdb.connect()
    try:
        return con.execute("SELECT * FROM read_parquet(?)", [str(path)]).fetchdf()
    finally:
        con.close()


def _infer_evidence_grain(df: pd.DataFrame | None) -> str:
    """Infer the evidence grain of a ratings or value frame (PRS-1 R-006).

    Returns the grain string used by the PRS-1 grain audit:
    - ``"match"`` if the frame carries per-match rows
      (``data_granularity == "match"``).
    - ``"season_proxy"`` if the frame carries season-aggregated rows.
    - ``"unknown"`` if the grain cannot be determined.

    The legacy ``player_ratings_optimized.parquet`` does not carry a
    ``data_granularity`` column, but it is built from season-proxy
    inputs (one row per player-season), so we infer ``"season_proxy"``
    when the column is missing but the frame looks like a
    season-aggregated ratings table (has ``player`` + ``season``
    columns). This keeps the legacy artifact honest in API responses
    until PRS-2 baselines replace it with a grain-stamped successor.
    """
    if df is None or df.empty:
        return "unknown"
    if "data_granularity" in df.columns:
        grains = df["data_granularity"].dropna().unique().tolist()
        if not grains:
            return "unknown"
        if len(grains) == 1:
            return str(grains[0])
        # Mixed grain — return the set joined by | for transparency,
        # matching the data_granularity_set convention in rating_matrix.
        return "|".join(sorted(str(g) for g in grains))
    # Legacy ratings table without data_granularity column.
    # player_ratings_optimized is built from season-proxy inputs
    # (one row per player-season), so we infer "season_proxy".
    if "player" in df.columns and "season" in df.columns:
        return "season_proxy"
    return "unknown"


# ── World Cup data cache ──────────────────────────────────────────
_wc_cache = _TTLCache()
_WC_ENRICHED_KEY = "wc_enriched"
_WC_SCOUTING_KEY = "wc_scouting_queues"


def _get_wc_enriched_squads(force_refresh: bool = False):
    """Return enriched WC squads, computing once and caching with TTL.

    Pass ``force_refresh=True`` to bypass the cache (e.g. after model retraining).
    """
    cached = _wc_cache.get(_WC_ENRICHED_KEY)
    if cached is _MISSING or force_refresh:
        ratings_df = load_player_ratings(force_refresh=force_refresh)
        enriched_squads = enrich_squads_with_ratings(ratings_df)
        strength_details = compute_team_strength_details(
            enriched_squads=enriched_squads
        )
        strengths = {
            team: values["strength"]
            for team, values in strength_details.items()
        }
        cached = {
            "enriched_squads": enriched_squads,
            "strengths": strengths,
            "strength_details": strength_details,
        }
        _wc_cache.set(_WC_ENRICHED_KEY, cached)
    return cached["enriched_squads"], cached["strengths"]


def _get_wc_strength_details(force_refresh: bool = False) -> dict:
    """Return WC team strength details (cached alongside enriched squads)."""
    _get_wc_enriched_squads(force_refresh=force_refresh)
    cached = _wc_cache.get(_WC_ENRICHED_KEY)
    if cached is _MISSING:
        return {}
    return cached.get("strength_details", {})


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


def _artifact_file_info(
    path: Path,
    label: str,
    *,
    rows: int | None = None,
    display_root: Path | None = None,
) -> dict[str, Any]:
    display_path = path
    if display_root is not None:
        try:
            display_path = path.resolve().relative_to(display_root.resolve())
        except ValueError:
            display_path = path
    return {
        "label": label,
        "path": str(display_path).replace("\\", "/"),
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


# ── Detailed health ────────────────────────────────────────────────────
# L1 退出门槛第 6 项要求"本地健康页显示数据质量、模型失效、存储、任务失败
# 和适配器状态，不向项目维护者上传遥测"。``/health/detailed`` 端点是这一项
# 的后端入口：组合 validate / model-admission / contract-quality /
# source-health / artifacts 五类信号，让维护者在前端 overview 视图一眼看
# 到本地真实状态，而不是硬编码值。
#
# 设计原则：
# 1. 不替换 ``/health`` liveness probe（``HealthResponse`` 保持精简）。
# 2. 不向外部上传任何数据——所有 builder 都在本地读取，无网络请求。
# 3. 昂贵操作（validation re-hashes lineage、model-admission sha256s
#    candidate parquets、contract-quality 调用 source-health）通过 TTL
#    cache 缓存，默认 300s 与 data_loader 的 cache 一致。
# 4. 任何子 builder 失败时记录日志并返回 ``status="unavailable"`` 而非
#    抛出，让健康页仍能渲染其他可用部分（fail-soft 而非 fail-closed，
#    因为这是只读诊断端点，不是发布门禁）。
# 5. 所有 builder 都是已有的只读函数，``get_detailed_health`` 只是组合层。

_detailed_health_cache = _TTLCache()


def _safe_call(builder_name: str, fn):
    """Call a health sub-builder; log and return None on any exception.

    Health sub-builders read local files and may fail for many reasons
    (missing data root, corrupt parquet, racy file deletion). A failed
    sub-builder must not break the whole ``/health/detailed`` response—
    the health page should still render the other available sections.
    """
    try:
        return fn()
    except Exception as exc:
        logger.warning(
            "get_detailed_health: %s builder failed: %s", builder_name, exc,
            exc_info=True,
        )
        return None


def _build_validation_section(settings) -> dict[str, Any]:
    from scoutfootball.evaluation.validation import run_pre_training_validation

    report = run_pre_training_validation(settings)
    checks_payload = [
        {
            "check_name": c.check_name,
            "passed": c.passed,
            "message": c.message,
        }
        for c in report.checks
    ]
    return {
        "status": "pass" if report.passed else "fail",
        "total_checks": len(report.checks),
        "passed_count": sum(1 for c in report.checks if c.passed),
        "failed_count": len(report.failures),
        "failures": [
            {"check_name": c.check_name, "message": c.message}
            for c in report.failures
        ],
        "checks": checks_payload,
        "summary": report.summary(),
    }


def _build_model_admission_section(settings) -> dict[str, Any]:
    from scoutfootball.evaluation.model_admission import build_model_admission_report

    report = build_model_admission_report(settings=settings)
    runs = report.get("runs", [])
    not_reviewable_count = sum(
        1 for r in runs if r.get("status") == "not_reviewable"
    )
    not_available_count = sum(
        1 for r in runs if r.get("status") == "not_available"
    )
    return {
        "status": "ok",
        "report_version": report.get("report_version"),
        "run_count": report.get("run_count", 0),
        "reviewable_run_count": report.get("reviewable_run_count", 0),
        "not_reviewable_run_count": not_reviewable_count,
        "not_available_run_count": not_available_count,
        "limitations": report.get("limitations", []),
        # 不返回完整 runs 列表——可能很长，且每个 run 含完整 8 项检查 +
        # comparison 数据。前端 overview 视图只需要计数摘要。维护者需要
        # 详情时走 ``model-admission --json`` CLI 或 ``/model-runs`` API。
        "runs_summary_omitted": True,
    }


def _build_contract_quality_section(settings) -> dict[str, Any]:
    from scoutfootball.evaluation.contract_quality import (
        build_contract_quality_report,
    )

    report = build_contract_quality_report(settings=settings)
    return {
        "status": report.get("overall_status", "unknown"),
        "report_version": report.get("report_version"),
        "failed_checks": report.get("failed_checks", []),
        "incomplete_checks": report.get("incomplete_checks", []),
        "checks_count": len(report.get("checks", [])),
        "limitations": report.get("limitations", []),
    }


def _build_source_health_section(settings) -> dict[str, Any]:
    from scoutfootball.evaluation.source_health import build_source_health_report

    report = build_source_health_report(settings=settings)
    sources = report.get("registered_sources", [])
    with_snapshot = sum(
        1 for s in sources
        if s.get("snapshot", {}).get("status") == "recorded"
    )
    without_snapshot = len(sources) - with_snapshot
    return {
        "status": "ok",
        "report_version": report.get("report_version"),
        "registered_source_count": report.get("registered_source_count", 0),
        "sources_with_snapshot": with_snapshot,
        "sources_without_snapshot": without_snapshot,
        "unregistered_raw_directories": report.get(
            "unregistered_raw_directories", []
        ),
        # 简短摘要：source_id + snapshot status，让前端能显示一行表
        "sources": [
            {
                "source_id": s.get("source_id"),
                "snapshot_status": s.get("snapshot", {}).get("status"),
                "local_status": s.get("local_observation", {}).get("status"),
                "license_status": s.get("license", {}).get("status"),
            }
            for s in sources
        ],
    }


def _build_research_health_section(settings) -> dict[str, Any]:
    """PRS-0 R-003/R-004: five-layer fail-closed research health summary.

    Returns a compact summary (verdict + per-layer status + blocking reasons)
    suitable for the overview page. The full five-layer report with evidence
    is available via ``scoutfootball research-health`` CLI or
    ``GET /health/research``.
    """
    from scoutfootball.evaluation.research_health import (
        build_research_health_report,
    )

    report = build_research_health_report(settings=settings)
    return {
        "verdict": report.get("verdict"),
        "blocking_reasons": report.get("blocking_reasons", []),
        "layers": {
            "storage_health": report.get("storage_health", {}).get("status"),
            "lineage_health": report.get("lineage_health", {}).get("status"),
            "model_reviewability": report.get("model_reviewability", {}).get(
                "status"
            ),
            "active_rating_freshness": report.get(
                "active_rating_freshness", {}
            ).get("status"),
            "research_readiness": report.get("research_readiness", {}).get(
                "status"
            ),
        },
    }


def get_detailed_health(*, force_refresh: bool = False) -> dict[str, Any]:
    """Compose a comprehensive local health snapshot for the overview page.

    Combines:
    - ``health_check()`` (status / data_source / version)
    - ``get_artifacts_summary()`` (row counts, artifact files, license)
    - ``run_pre_training_validation()`` (31 checks)
    - ``build_model_admission_report()`` (reviewable / not_reviewable)
    - ``build_contract_quality_report()`` (8 checks, overall_status)
    - ``build_source_health_report()`` (source snapshot coverage)

    All sub-builders are read-only and local. Expensive builders are
    cached via ``_detailed_health_cache`` with a TTL matching the
    data_loader cache (default 300s). Pass ``force_refresh=True`` to
    bypass the cache (e.g. after a model retrain or build-features run).

    Sub-builder failures are logged and returned as
    ``status="unavailable"`` sections rather than raising—the health
    page should render available sections even when one source fails.
    """
    from scoutfootball import __version__

    cache_key = "get_detailed_health"
    if not force_refresh:
        cached = _detailed_health_cache.get(cache_key)
        if cached is not _MISSING:
            return cached

    settings = _settings()
    generated_at = datetime.now(UTC).isoformat()

    # Cheap sub-builders run every call (already cached at data_loader
    # level for parquet reads; health_check + artifacts_summary are fast).
    base_health = {
        "status": "ok",
        "data_source": data_source_label(),
        "version": __version__,
    }
    artifacts = _safe_call(
        "artifacts_summary", lambda: get_artifacts_summary()
    )

    # Expensive sub-builders run inside _safe_call so a failure in one
    # doesn't break the whole response.
    validation = _safe_call(
        "validation", lambda: _build_validation_section(settings)
    )
    model_admission = _safe_call(
        "model_admission", lambda: _build_model_admission_section(settings)
    )
    contract_quality = _safe_call(
        "contract_quality",
        lambda: _build_contract_quality_section(settings),
    )
    source_health = _safe_call(
        "source_health", lambda: _build_source_health_section(settings)
    )
    # PRS-0 R-003/R-004: research_health is the fail-closed layered verdict
    # for the rating system. It reuses model_admission and truth_labels
    # evidence so a 0-reviewable-run or stale-lineage state can no longer be
    # hidden by a top-level ok. Computed in its own _safe_call so a failure
    # here degrades this section without breaking the rest of the report.
    research_health = _safe_call(
        "research_health", lambda: _build_research_health_section(settings)
    )

    # Compute top-level status: "ok" if all sub-builders succeeded and
    # validation + contract_quality both pass; "degraded" if any sub-builder
    # failed or any critical check failed; "error" only if base_health
    # itself failed (should not happen since data_source_label is cheap).
    sub_builders = {
        "artifacts": artifacts,
        "validation": validation,
        "model_admission": model_admission,
        "contract_quality": contract_quality,
        "source_health": source_health,
        "research_health": research_health,
    }
    unavailable = [k for k, v in sub_builders.items() if v is None]
    failed_checks = []
    if validation and validation.get("status") == "fail":
        failed_checks.append("validation")
    if (
        contract_quality
        and contract_quality.get("status") in ("fail", "incomplete")
    ):
        failed_checks.append(f"contract_quality:{contract_quality.get('status')}")
    # R-004: a not_ready/unavailable research verdict is a failed check at
    # the top level. Before this, model_admission's reviewable_run_count=0
    # was invisible to top_status because model_admission's own status was
    # hardcoded "ok".
    if research_health and research_health.get("verdict") in (
        "not_ready",
        "unavailable",
    ):
        failed_checks.append(f"research_health:{research_health.get('verdict')}")

    if unavailable:
        top_status = "degraded"
    elif failed_checks:
        top_status = "degraded"
    else:
        top_status = "ok"

    result = _clean_json_value({
        "schema": "scoutfootball.detailed-health",
        "schema_version": "1.0.0",
        "generated_at": generated_at,
        "status": top_status,
        "base": base_health,
        "artifacts": artifacts if artifacts is not None else {"status": "unavailable"},
        "validation": validation if validation is not None else {"status": "unavailable"},
        "model_admission": (
            model_admission if model_admission is not None
            else {"status": "unavailable"}
        ),
        "contract_quality": (
            contract_quality if contract_quality is not None
            else {"status": "unavailable"}
        ),
        "source_health": (
            source_health if source_health is not None
            else {"status": "unavailable"}
        ),
        "research_health": (
            research_health if research_health is not None
            else {"verdict": "unavailable"}
        ),
        "unavailable_sections": unavailable,
        "failed_sections": failed_checks,
        "limitations": [
            "Local-only diagnostic; no telemetry is uploaded to any external service.",
            (
                "Sub-builders are read-only; failures degrade individual "
                "sections rather than the whole response."
            ),
            (
                "Expensive builders (validation, model-admission, "
                "contract-quality, source-health, research-health) are TTL-cached "
                "(default 300s); pass force_refresh=True to bypass."
            ),
            (
                "model_admission runs_summary_omitted=True—use CLI "
                "model-admission --json or /model-runs API for per-run "
                "details."
            ),
            (
                "research_health is a fail-closed layered verdict (PRS-0 "
                "R-003/R-004); use CLI research-health or /health/research "
                "for the full five-layer report."
            ),
        ],
    })

    _detailed_health_cache.set(cache_key, result)
    return result


def get_research_health() -> dict[str, Any]:
    """Return the five-layer research health snapshot for the rating system.

    Thin wrapper around ``research_health.build_research_health_report`` so
    the API layer stays consistent with the CLI (``scoutfootball
    research-health``). PRS-0 R-003/R-004: the verdict is fail-closed — a
    stale, unreviewable, synthetic or non-independent-label rating system is
    reported as ``not_ready`` and can no longer be hidden behind a top-level
    ``ok``. Read-only and local; no synthetic fallback.
    """
    from scoutfootball.evaluation.research_health import (
        build_research_health_report,
    )

    return build_research_health_report()


def get_adapter_registry() -> dict[str, Any]:
    """Return the provider adapter manifest registry (I1 baseline).

    The registry is a machine-readable catalog of every source adapter
    the project knows about, including its capabilities, schema
    mappings and conversion-loss notes. It is read-only metadata: no
    ingester runs here and no source data is uploaded.
    """
    from scoutfootball.adapters.registry import build_adapter_registry

    registry = build_adapter_registry()
    return registry.model_dump(mode="json")


def get_adapter_compatibility_matrix() -> dict[str, Any]:
    """Return project-local adapter admission derived from contracts.

    The matrix is read-only metadata.  It does not start an ingester, validate
    an upstream license, or authorize publication of source or derived data.
    """
    from scoutfootball.adapters.compatibility import build_adapter_compatibility_matrix

    return build_adapter_compatibility_matrix().model_dump(mode="json")


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
    """Return teams supported by the active match-prediction artifacts.

    Player-rating rows can contain comma-joined club histories for transferred
    players. Those values are useful in the rating dataset, but they are not
    valid team identifiers for the prediction model. Prefer the exact team ids
    saved with Dixon-Coles/Poisson and only fall back to ratings data when no
    prediction artifact is available.
    """
    artifact_dir = _settings().model_root / "artifacts"
    for filename in ("dc_team_strengths.parquet", "team_strengths.parquet"):
        path = artifact_dir / filename
        if not path.exists():
            continue
        try:
            frame = _read_parquet(path)
        except Exception:
            logger.warning("list_teams: parquet read failed", exc_info=True)
            continue
        if "team_id" not in frame.columns:
            continue
        teams = {
            str(team).strip()
            for team in frame["team_id"].dropna().tolist()
            if str(team).strip()
        }
        if teams:
            return sorted(teams)

    df = load_player_ratings()
    if "team" in df.columns:
        teams = {
            str(team).strip()
            for team in df["team"].dropna().tolist()
            if str(team).strip() and "," not in str(team)
        }
        return sorted(teams)
    # Fallback to team_match
    tm = load_team_match()
    if "team_name" in tm.columns:
        return sorted(tm["team_name"].dropna().unique().tolist())[:200]
    return []


def search_players_and_teams(
    q: str,
    search_type: str = "all",
    limit: int = 10,
) -> dict[str, Any]:
    """Return matching player and team name suggestions for autocomplete.

    Matches are ranked prefix-first (alphabetical), then substring matches
    (alphabetical). Returns ``{"players": [...], "teams": [...]}``.

    Player entries include ``player_name``, ``team``, ``position``, ``rating``
    (optimized_score) and ``league``. Team entries include ``team_name`` and
    ``league``. Comma-joined club histories (transferred players) are excluded
    from team suggestions.
    """
    empty_result: dict[str, Any] = {"players": [], "teams": []}

    # Input validation — require at least 2 characters
    if not q or len(q.strip()) < 2:
        return empty_result
    q = q.strip()

    # Limit clamping (1..25, default 10)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 25))

    # Type validation — invalid values default to "all"
    if search_type not in ("players", "teams", "all"):
        search_type = "all"

    # Load ratings via TTL cache (no forced refresh)
    df = load_player_ratings(force_refresh=False)
    if df is None or df.empty:
        return _clean_json_value(empty_result)

    # Resolve column names (normalize_ratings_frame ensures aliases exist)
    name_col = (
        "player" if "player" in df.columns
        else ("player_name" if "player_name" in df.columns else None)
    )
    team_col = (
        "team" if "team" in df.columns
        else ("team_name" if "team_name" in df.columns else None)
    )
    league_col = "league" if "league" in df.columns else None
    pos_col = (
        "position_group" if "position_group" in df.columns
        else ("sub_position" if "sub_position" in df.columns else None)
    )
    score_col = (
        "optimized_score" if "optimized_score" in df.columns
        else ("rating" if "rating" in df.columns else None)
    )

    players_out: list[dict[str, Any]] = []
    teams_out: list[dict[str, Any]] = []

    # ── Player search ──────────────────────────────────────────────
    if search_type in ("players", "all") and name_col is not None:
        q_lower = q.lower()

        # Deduplicate by player name, keeping the best row (highest score)
        if score_col is not None and score_col in df.columns:
            dedup = df.sort_values(score_col, ascending=False).drop_duplicates(
                subset=[name_col], keep="first",
            )
        else:
            dedup = df.drop_duplicates(subset=[name_col], keep="first")
        dedup = dedup[dedup[name_col].notna()]
        dedup = dedup[dedup[name_col].astype(str).str.strip() != ""]

        dedup_names = dedup[name_col].astype(str).str.lower()
        prefix_mask = dedup_names.str.startswith(q_lower, na=False)
        substring_mask = (
            ~prefix_mask
            & dedup_names.str.contains(q_lower, na=False, regex=False)
        )

        prefix_df = dedup[prefix_mask].sort_values(name_col)
        substring_df = dedup[substring_mask].sort_values(name_col)
        combined = pd.concat([prefix_df, substring_df]).head(limit)

        for _, row in combined.iterrows():
            score_val = row.get(score_col) if score_col else None
            rating = (
                round(float(score_val), 1)
                if score_col and pd.notna(score_val)
                else None
            )
            players_out.append({
                "player_name": str(row.get(name_col, "")),
                "team": str(row.get(team_col, "")) if team_col else "",
                "position": str(row.get(pos_col, "")) if pos_col else "",
                "rating": rating,
                "league": str(row.get(league_col, "")) if league_col else "",
            })

    # ── Team search ────────────────────────────────────────────────
    if search_type in ("teams", "all") and team_col is not None:
        q_lower = q.lower()
        team_df = df[df[team_col].notna()].copy()
        # Exclude comma-joined club histories (transferred players)
        team_df = team_df[~team_df[team_col].astype(str).str.contains(",", na=False)]
        team_df = team_df[team_df[team_col].astype(str).str.strip() != ""]

        if not team_df.empty:
            # Unique teams with league info (first occurrence)
            teams_unique = team_df.drop_duplicates(subset=[team_col], keep="first")
            team_names_lower = teams_unique[team_col].astype(str).str.lower()

            prefix_mask = team_names_lower.str.startswith(q_lower, na=False)
            substring_mask = (
                ~prefix_mask
                & team_names_lower.str.contains(q_lower, na=False, regex=False)
            )

            prefix_teams = teams_unique[prefix_mask].sort_values(team_col)
            substring_teams = teams_unique[substring_mask].sort_values(team_col)
            combined_teams = pd.concat([prefix_teams, substring_teams]).head(limit)

            for _, row in combined_teams.iterrows():
                teams_out.append({
                    "team_name": str(row.get(team_col, "")),
                    "league": str(row.get(league_col, "")) if league_col else "",
                })

    return _clean_json_value({"players": players_out, "teams": teams_out})


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
            logger.warning("prediction calibration: poisson read failed", exc_info=True)
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
            logger.warning("prediction calibration: dixon_coles read failed", exc_info=True)
            pass

    # Full calibration detail is produced by the training backtest. Prefer
    # those evaluated metrics when available; the model-summary parquet only
    # stores fitted parameters and therefore cannot populate Brier/RPS.
    try:
        detail = get_prediction_calibration()
        detail_metrics = detail.get("dixon_coles", {})
        if detail_metrics.get("status") != "ok":
            detail_metrics = detail.get("poisson", {})
        if detail_metrics.get("status") == "ok":
            calibration["brier"] = detail_metrics.get("brier_1x2")
            calibration["rps"] = detail_metrics.get("rps_1x2")
            calibration["log_loss"] = detail_metrics.get("log_loss_exact")
    except Exception:
        logger.warning("prediction calibration: detail metrics failed", exc_info=True)
        pass

    return calibration


def _world_cup_score_matrix(
    home_lambda: float, away_lambda: float, *, max_goals: int = 5
) -> list[list[float]]:
    from scipy.stats import poisson

    goals = np.arange(max_goals + 1)
    home_probs = poisson.pmf(goals, home_lambda)
    away_probs = poisson.pmf(goals, away_lambda)
    matrix = np.outer(home_probs, away_probs)
    matrix = matrix / matrix.sum()
    return [
        [round(float(matrix[i, j]), 4) for j in range(max_goals + 1)]
        for i in range(max_goals + 1)
    ]


def _world_cup_market_summary(score_matrix: list[list[float]]) -> dict[str, float]:
    home_win = 0.0
    draw = 0.0
    away_win = 0.0
    over_2_5 = 0.0
    btts_yes = 0.0
    for home_goals, row in enumerate(score_matrix):
        for away_goals, prob in enumerate(row):
            if home_goals > away_goals:
                home_win += prob
            elif home_goals == away_goals:
                draw += prob
            else:
                away_win += prob
            if home_goals + away_goals >= 3:
                over_2_5 += prob
            if home_goals > 0 and away_goals > 0:
                btts_yes += prob
    return {
        "home_win": round(home_win, 4),
        "draw": round(draw, 4),
        "away_win": round(away_win, 4),
        "over_2_5": round(over_2_5, 4),
        "under_2_5": round(1 - over_2_5, 4),
        "btts_yes": round(btts_yes, 4),
        "btts_no": round(1 - btts_yes, 4),
    }


def _most_likely_wc_scoreline(score_matrix: list[list[float]]) -> dict[str, Any]:
    """Return the (home_goals, away_goals, probability) with highest probability."""
    best_h, best_a, best_p = 0, 0, 0.0
    for i, row in enumerate(score_matrix):
        for j, prob in enumerate(row):
            if prob > best_p:
                best_h, best_a, best_p = i, j, prob
    return {
        "home_goals": best_h,
        "away_goals": best_a,
        "probability": round(best_p, 4),
    }


def _classify_prediction_delta(
    home_win_prob: float,
    draw_prob: float,
    away_win_prob: float,
    home_goals: int,
    away_goals: int,
) -> dict[str, Any]:
    """Classify an actual result vs the pre-match prediction.

    Returns one of three classifications:
    - ``as_expected``: actual outcome matches the argmax prediction.
    - ``upset``: actual outcome's pre-match probability was < 0.30 (and not as_expected).
    - ``hold``: middle-probability outcome happened (neither as_expected nor upset).
    """
    probs = {
        "home_win": float(home_win_prob),
        "draw": float(draw_prob),
        "away_win": float(away_win_prob),
    }
    if home_goals > away_goals:
        actual = "home_win"
    elif home_goals == away_goals:
        actual = "draw"
    else:
        actual = "away_win"
    predicted = max(probs, key=probs.get)
    actual_prob = probs[actual]
    if actual == predicted:
        classification = "as_expected"
    elif actual_prob < 0.30:
        classification = "upset"
    else:
        classification = "hold"
    return {
        "classification": classification,
        "actual_outcome": actual,
        "predicted_outcome": predicted,
        "actual_prob": round(actual_prob, 4),
        "predicted_prob": round(probs[predicted], 4),
    }


def get_world_cup_match_prediction(home_team: str, away_team: str) -> dict[str, Any]:
    enriched_squads, strengths = _get_wc_enriched_squads()
    valid_teams = set(enriched_squads)
    if home_team not in valid_teams:
        return _make_error_response(f"World Cup home team '{home_team}' not found")
    if away_team not in valid_teams:
        return _make_error_response(f"World Cup away team '{away_team}' not found")
    if home_team == away_team:
        return _make_error_response("Home and away World Cup teams must be different")

    home_strength = float(strengths.get(home_team, 0.2))
    away_strength = float(strengths.get(away_team, 0.2))

    strength_gap = math.log((home_strength + 0.05) / (away_strength + 0.05))
    host_bonus = 0.12 if home_team in HOSTS else 0.0
    if away_team in HOSTS:
        host_bonus -= 0.12

    total_goals = 2.35 + 0.55 * ((home_strength + away_strength) - 1.0)
    total_goals = min(max(total_goals, 2.05), 3.35)

    home_share = 1 / (1 + math.exp(-(0.62 * strength_gap + host_bonus)))
    home_share = min(max(home_share, 0.22), 0.78)

    home_lambda = min(max(total_goals * home_share, 0.25), 3.2)
    away_lambda = min(max(total_goals - home_lambda, 0.2), 3.0)

    score_matrix = _world_cup_score_matrix(home_lambda, away_lambda)
    summary = _world_cup_market_summary(score_matrix)

    result = {
        "home_team": home_team,
        "away_team": away_team,
        "model_type": "world_cup_strength_poisson",
        "model_version": "wc-1.0",
        "home_lambda": round(home_lambda, 4),
        "away_lambda": round(away_lambda, 4),
        "home_strength": round(home_strength, 4),
        "away_strength": round(away_strength, 4),
        "host_bonus": round(host_bonus, 4),
        "strength_gap": round(strength_gap, 4),
        "score_matrix": score_matrix,
        **summary,
    }
    return _clean_json_value(result)


def _world_cup_briefing_team_snapshot(
    team: str,
    squad: list[Any],
    strength_detail: dict[str, Any],
) -> dict[str, Any]:
    rated = [player for player in squad if player.has_rating and player.rating is not None]
    top_players = sorted(rated, key=lambda player: float(player.rating), reverse=True)[:5]
    return {
        "team": team,
        "group": get_team_group(team),
        "is_host": team in HOSTS,
        "squad": {
            "total_players": len(squad),
            "rated_players": len(rated),
            "rating_coverage": strength_detail.get("coverage", 0.0),
            "core_avg_rating": strength_detail.get("core_avg_rating"),
            "depth_avg_rating": strength_detail.get("depth_avg_rating"),
            "balance": compute_squad_balance(squad),
            "top_rated_players": [
                {
                    "name": player.name,
                    "position": player.position,
                    "club": player.club,
                    "rating": round(float(player.rating), 2),
                    "rating_confidence": player.rating_confidence,
                }
                for player in top_players
            ],
        },
        "strength": {
            "score": strength_detail.get("strength", 0.0),
            "league_component": strength_detail.get("league_score", 0.0),
            "coverage_component": strength_detail.get("coverage_score", 0.0),
            "big5_component": strength_detail.get("big5_score", 0.0),
        },
    }


def _world_cup_briefing_input_snapshot() -> dict[str, Any]:
    """Expose recorded rating-run lineage without inventing missing hashes."""
    latest_run = (get_model_runs().get("runs") or [{}])[0]
    lineage = latest_run.get("lineage") if isinstance(latest_run, dict) else {}
    if not isinstance(lineage, dict):
        lineage = {}
    dataset_value = lineage.get("dataset_snapshot")
    manifest_value = lineage.get("feature_manifest")
    dataset = dataset_value if isinstance(dataset_value, dict) else {}
    manifest = manifest_value if isinstance(manifest_value, dict) else {}
    input_hash = dataset.get("input_hash") or manifest.get("input_hash") or ""
    return {
        "status": "recorded" if input_hash else "not_recorded",
        "rating_model_run_id": latest_run.get("run_id", "") if isinstance(latest_run, dict) else "",
        "rating_input_hash": input_hash,
        "feature_manifest_hash": manifest.get("hash") or "",
        "strength_model": {
            "type": "world_cup_strength_ratio_poisson",
            "version": "wc-1.0",
            "score_matrix_max_goals": 5,
            "host_bonus": 0.12,
        },
    }


def get_world_cup_match_briefing(home_team: str, away_team: str) -> dict[str, Any]:
    """Return a source-bounded pre-match briefing for a World Cup pairing.

    This combines the simplified tournament prediction with roster-rating
    coverage, but deliberately does not turn placeholder squads or strength
    proxies into live team news or tactical advice.
    """
    prediction = get_world_cup_match_prediction(home_team, away_team)
    if prediction.get("error"):
        return prediction
    enriched_squads, _ = _get_wc_enriched_squads()
    strength_details = _get_wc_strength_details()
    return _clean_json_value({
        "schema": "scoutfootball.world-cup-match-briefing",
        "version": "1.0.0",
        "status": "ok",
        "fixture": {"home_team": home_team, "away_team": away_team},
        "prediction": prediction,
        "input_snapshot": _world_cup_briefing_input_snapshot(),
        "teams": {
            "home": _world_cup_briefing_team_snapshot(
                home_team,
                enriched_squads.get(home_team, []),
                strength_details.get(home_team, {}),
            ),
            "away": _world_cup_briefing_team_snapshot(
                away_team,
                enriched_squads.get(away_team, []),
                strength_details.get(away_team, {}),
            ),
        },
        "source_attribution": (
            "World Cup squad ratings are derived from ScoutFootball local "
            "FBref/Understat artifacts; the tournament strength model also "
            "uses public Opta priors."
        ),
        "limitations": [
            "Squad lists are placeholders and are not confirmed matchday rosters.",
            "Probabilities come from a simplified strength-ratio Poisson model, "
            "not live team news or market odds.",
            "Lower rating coverage and non-Big5 league proxies can reduce comparability.",
        ],
    })


# ── Player spotlight position weights ────────────────────────────────────
# Higher weight = more likely to be flagged as "player to watch".
# Attackers and creative mids rank higher than defensive roles for
# spotlight purposes; this is a presentation heuristic, not a rating.
_WC_SPOTLIGHT_POSITION_WEIGHTS: dict[str, float] = {
    "ST": 1.20,
    "W": 1.15,
    "AM": 1.10,
    "CM": 1.00,
    "DM": 0.85,
    "FB": 0.80,
    "CB": 0.80,
    "GK": 0.60,
}

_WC_SPOTLIGHT_CONFIDENCE_MULTIPLIER: dict[str, float] = {
    "high": 1.00,
    "medium": 0.85,
    "low": 0.65,
    "none": 0.40,
}


def _wc_spotlight_opponent_weakness(
    squad: list[Any], opponent_squad: list[Any]
) -> dict[str, float]:
    """Score how weak each opponent defensive role is.

    Returns a dict mapping opponent role -> weakness_score (0..1), where
    higher means the opponent is weaker at that role (lower average
    rating among their players in that role, scaled to 0..1).

    Used to boost attacking player weights when they line up against
    a weak opposing defensive role.
    """
    role_ratings: dict[str, list[float]] = {"CB": [], "FB": [], "DM": [], "GK": []}
    for player in opponent_squad:
        if not player.has_rating or player.rating is None:
            continue
        if player.position in role_ratings:
            role_ratings[player.position].append(float(player.rating))

    weakness: dict[str, float] = {}
    for role, ratings in role_ratings.items():
        if not ratings:
            # No rated player at this role = unknown, treat as neutral 0.5
            weakness[role] = 0.5
            continue
        avg = sum(ratings) / len(ratings)
        # WC ratings observed range ~30..85; map [30, 85] -> [1.0, 0.0]
        # so a low-rated defender (avg ~30) yields weakness ~1.0 (very weak)
        # and a top defender (avg ~85) yields weakness ~0.0 (very strong).
        scaled = max(0.0, min(1.0, (85.0 - avg) / 55.0))
        weakness[role] = scaled
    return weakness


def _wc_spotlight_player_score(
    player: Any,
    team_rated: list[Any],
    opponent_weakness: dict[str, float],
    team_avg_rating: float,
) -> tuple[float, str]:
    """Compute a single player's spotlight score and the reason text.

    The score blends absolute rating, rating confidence, the player's
    role's general "watchability" weight, and a position-vs-opponent
    matchup bonus (e.g. an ST facing a weak CB line gets a boost).
    """
    if not player.has_rating or player.rating is None:
        return 0.0, ""
    rating = float(player.rating)
    confidence = _WC_SPOTLIGHT_CONFIDENCE_MULTIPLIER.get(
        player.rating_confidence, 0.40
    )
    position_weight = _WC_SPOTLIGHT_POSITION_WEIGHTS.get(player.position, 1.0)

    # Normalize rating above team average (above-average players get a boost).
    rating_delta = max(0.0, rating - team_avg_rating) if team_avg_rating else 0.0

    # Position-vs-opponent matchup bonus.
    matchup_bonus = 0.0
    matchup_reason = ""
    pos = player.position
    if pos == "ST":
        cb_weak = opponent_weakness.get("CB", 0.5)
        gk_weak = opponent_weakness.get("GK", 0.5)
        matchup_bonus = 0.10 * cb_weak + 0.05 * gk_weak
        if cb_weak >= 0.6:
            matchup_reason = "faces a weak CB line"
        elif gk_weak >= 0.6:
            matchup_reason = "faces a weak GK"
    elif pos == "W":
        fb_weak = opponent_weakness.get("FB", 0.5)
        matchup_bonus = 0.10 * fb_weak
        if fb_weak >= 0.6:
            matchup_reason = "vs weak fullbacks"
    elif pos == "AM":
        dm_weak = opponent_weakness.get("DM", 0.5)
        matchup_bonus = 0.08 * dm_weak
        if dm_weak >= 0.6:
            matchup_reason = "vs weak defensive mid"
    elif pos in ("CM", "DM"):
        # Central mids benefit from opponent having a weak midfield generally.
        matchup_bonus = 0.05 * opponent_weakness.get("DM", 0.5)

    base_score = (
        0.55 * (rating / 100.0)
        + 0.20 * confidence
        + 0.15 * position_weight
        + 0.10 * (rating_delta / 30.0 if rating_delta else 0.0)
        + matchup_bonus
    )
    return base_score, matchup_reason


def get_wc_match_player_spotlight(
    home_team: str, away_team: str, *, top_n: int = 5
) -> dict[str, Any]:
    """Return ranked 'players to watch' for a World Cup fixture.

    Each team contributes up to ``max(2, top_n // 2)`` candidates. Players
    are scored by absolute rating, rating confidence, role watchability,
    team-relative rating delta, and a position-vs-opponent matchup bonus.

    The output is *illustrative* — based on placeholder squads and local
    ratings, not a confirmed lineup, injury report, or tactical forecast.
    """
    if home_team == away_team:
        return _clean_json_value({
            "status": "error",
            "code": "invalid_fixture",
            "message": "Home and away World Cup teams must be different.",
        })

    enriched_squads, strengths = _get_wc_enriched_squads()
    valid_teams = set(enriched_squads)
    if home_team not in valid_teams:
        return _clean_json_value({
            "status": "error",
            "code": "unknown_team",
            "message": f"World Cup home team '{home_team}' not found.",
        })
    if away_team not in valid_teams:
        return _clean_json_value({
            "status": "error",
            "code": "unknown_team",
            "message": f"World Cup away team '{away_team}' not found.",
        })

    home_squad = enriched_squads.get(home_team, [])
    away_squad = enriched_squads.get(away_team, [])

    home_rated = [
        p for p in home_squad if p.has_rating and p.rating is not None
    ]
    away_rated = [
        p for p in away_squad if p.has_rating and p.rating is not None
    ]

    if not home_rated and not away_rated:
        return _clean_json_value({
            "schema": "scoutfootball.world-cup-match-player-spotlight",
            "version": "1.0.0",
            "status": "no_rated_players",
            "fixture": {"home_team": home_team, "away_team": away_team},
            "players": [],
            "limitations": [
                "No rated players available for either side; spotlight "
                "cannot be computed.",
            ],
        })

    home_avg = (
        sum(float(p.rating) for p in home_rated) / len(home_rated)
        if home_rated else 0.0
    )
    away_avg = (
        sum(float(p.rating) for p in away_rated) / len(away_rated)
        if away_rated else 0.0
    )

    home_weakness = _wc_spotlight_opponent_weakness(home_squad, away_squad)
    away_weakness = _wc_spotlight_opponent_weakness(away_squad, home_squad)

    # Each side contributes up to ceil(top_n/2) + 1 candidates, then we merge.
    per_side_cap = max(2, (top_n + 1) // 2 + 1)

    def _rank_side(
        team: str,
        squad: list[Any],
        rated: list[Any],
        opponent_weakness: dict[str, float],
        team_avg: float,
    ) -> list[dict[str, Any]]:
        scored: list[tuple[float, dict[str, Any]]] = []
        for player in rated:
            score, matchup_reason = _wc_spotlight_player_score(
                player, rated, opponent_weakness, team_avg
            )
            reason_parts = []
            if player.rating is not None and team_avg:
                delta = float(player.rating) - team_avg
                if delta >= 5.0:
                    reason_parts.append(
                        f"top-rated in squad (+{delta:.1f})"
                    )
                elif delta <= -5.0:
                    reason_parts.append(
                        f"role depth (rating {float(player.rating):.1f})"
                    )
            if matchup_reason:
                reason_parts.append(matchup_reason)
            pos_label = _WC_SPOTLIGHT_POSITION_WEIGHTS.get(
                player.position, 1.0
            )
            if pos_label >= 1.10 and not reason_parts:
                reason_parts.append("attacking threat role")
            scored.append((
                score,
                {
                    "name": player.name,
                    "team": team,
                    "position": player.position,
                    "club": player.club,
                    "club_league": player.club_league,
                    "rating": round(float(player.rating), 2) if player.rating else None,
                    "rating_confidence": player.rating_confidence,
                    "spotlight_score": round(score, 4),
                    "reason": "; ".join(reason_parts) if reason_parts else "rated contributor",
                },
            ))
        scored.sort(key=lambda x: -x[0])
        return [entry for _, entry in scored[:per_side_cap]]

    home_candidates = _rank_side(
        home_team, home_squad, home_rated, away_weakness, home_avg
    )
    away_candidates = _rank_side(
        away_team, away_squad, away_rated, home_weakness, away_avg
    )

    all_candidates = home_candidates + away_candidates
    all_candidates.sort(key=lambda p: -p["spotlight_score"])
    top = all_candidates[:top_n]

    return _clean_json_value({
        "schema": "scoutfootball.world-cup-match-player-spotlight",
        "version": "1.0.0",
        "status": "ok",
        "fixture": {"home_team": home_team, "away_team": away_team},
        "prediction_summary": {
            "home_strength": round(float(strengths.get(home_team, 0.0)), 4),
            "away_strength": round(float(strengths.get(away_team, 0.0)), 4),
            "home_advantage_flag": home_team in HOSTS,
        },
        "players": top,
        "total_candidates": len(all_candidates),
        "source_attribution": (
            "Spotlight scores blend ScoutFootball local ratings, rating "
            "confidence, role watchability, and opponent-position weakness. "
            "Squads are placeholder callup snapshots, not confirmed lineups."
        ),
        "limitations": [
            "Spotlight is an illustrative presentation heuristic, not a "
            "performance forecast or lineup prediction.",
            "Rating coverage gaps for non-Big5 leagues reduce the reliability "
            "of position-vs-opponent matchup bonuses.",
            "The matchup bonus assumes position-vs-position confrontation; "
            "actual tactical matchups depend on the manager's setup.",
        ],
    })


def get_wc_team_form_trend(team: str, *, last_n: int = 6) -> dict[str, Any]:
    """Return a team's recent form trend for the World Cup view.

    Combines two signal sources:
    1. Recorded group-stage results from local tournament state (if any).
    2. Pre-tournament expected-results trajectory derived from the
       team's strength and the group-stage schedule order.

    The trend is illustrative only — pre-tournament matches are
    strength-derived expectations, not actual fixtures.
    """
    from scoutfootball.worldcup.data import get_team_group
    from scoutfootball.worldcup.tournament import _match_completed

    enriched_squads, strengths = _get_wc_enriched_squads()
    if team not in enriched_squads:
        return _clean_json_value({
            "status": "error",
            "code": "unknown_team",
            "message": f"World Cup team '{team}' not found.",
        })

    team_strength = float(strengths.get(team, 0.2))
    state = _wc_tournament_state()

    # 1) Pull recorded WC results (group stage + knockout if any).
    recorded: list[dict[str, Any]] = []
    for m in state.matches:
        if team not in (m.get("home"), m.get("away")):
            continue
        result = state.results.get(m["match_id"])
        if not _match_completed(result):
            continue
        hg = int(result.get("home_goals", 0))
        ag = int(result.get("away_goals", 0))
        is_home = m.get("home") == team
        team_goals = hg if is_home else ag
        opp_goals = ag if is_home else hg
        opp = m.get("away") if is_home else m.get("home")
        if team_goals > opp_goals:
            outcome = "W"
            points = 3
        elif team_goals == opp_goals:
            outcome = "D"
            points = 1
        else:
            outcome = "L"
            points = 0
        recorded.append({
            "kind": "recorded",
            "date": m.get("date", ""),
            "opponent": opp,
            "venue": "home" if is_home else "away",
            "team_goals": team_goals,
            "opponent_goals": opp_goals,
            "outcome": outcome,
            "points": points,
            "group": m.get("group"),
        })

    # 2) Project expected group-stage results from strength for unrecorded
    #    matches in this team's group (pre-tournament form proxy).
    group = get_team_group(team)
    projected: list[dict[str, Any]] = []
    if group:
        for m in state.matches:
            if m.get("group") != group:
                continue
            if team not in (m.get("home"), m.get("away")):
                continue
            if _match_completed(state.results.get(m["match_id"])):
                continue  # already in `recorded`
            opp = m.get("away") if m.get("home") == team else m.get("home")
            opp_strength = float(strengths.get(opp, 0.2))
            # Simple expected score: stronger team wins more often, ~2.3 goals.
            strength_diff = team_strength - opp_strength
            expected_team_goals = max(0.3, min(4.0, 1.55 + 1.2 * strength_diff))
            expected_opp_goals = max(0.3, min(4.0, 1.55 - 1.2 * strength_diff))
            if expected_team_goals > expected_opp_goals + 0.25:
                outcome = "W"
                points = 3
            elif expected_team_goals < expected_opp_goals - 0.25:
                outcome = "L"
                points = 0
            else:
                outcome = "D"
                points = 1
            is_home = m.get("home") == team
            projected.append({
                "kind": "projected",
                "date": m.get("date", ""),
                "opponent": opp,
                "venue": "home" if is_home else "away",
                "team_goals": round(expected_team_goals, 2),
                "opponent_goals": round(expected_opp_goals, 2),
                "outcome": outcome,
                "points": points,
                "group": m.get("group"),
            })

    # Recorded matches take priority; fill the rest with projected up to last_n.
    recorded_sorted = sorted(recorded, key=lambda r: r["date"], reverse=True)
    projected_sorted = sorted(projected, key=lambda r: r["date"])

    # Combine: show projected (chronological) then recorded (most recent first)
    # so the user sees the projected trajectory then live results on top.
    combined = projected_sorted + recorded_sorted

    # Trim to last_n entries for the trend chart.
    if len(combined) > last_n:
        combined = combined[-last_n:]

    # Compute a simple form score: weighted recent points (decay 0.8 per match).
    form_score = 0.0
    decay = 1.0
    total_decay = 0.0
    # iterate from most recent to oldest
    for entry in reversed(combined):
        form_score += entry["points"] * decay
        total_decay += decay
        decay *= 0.8
    form_score = form_score / total_decay if total_decay else 0.0
    # Normalize to 0..1 (3 points = 1.0)
    form_score_normalized = form_score / 3.0

    # Build a simple trajectory of cumulative points.
    cumulative = 0
    trajectory = []
    for entry in combined:
        cumulative += entry["points"]
        trajectory.append({
            "date": entry["date"],
            "opponent": entry["opponent"],
            "outcome": entry["outcome"],
            "team_goals": entry["team_goals"],
            "opponent_goals": entry["opponent_goals"],
            "points": entry["points"],
            "cumulative_points": cumulative,
            "kind": entry["kind"],
            "venue": entry["venue"],
        })

    wins = sum(1 for e in combined if e["outcome"] == "W")
    draws = sum(1 for e in combined if e["outcome"] == "D")
    losses = sum(1 for e in combined if e["outcome"] == "L")

    return _clean_json_value({
        "schema": "scoutfootball.world-cup-team-form-trend",
        "version": "1.0.0",
        "status": "ok",
        "team": team,
        "group": group,
        "strength": round(team_strength, 4),
        "matches": trajectory,
        "summary": {
            "recorded_count": len(recorded),
            "projected_count": len(projected),
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "form_score": round(form_score, 3),
            "form_score_normalized": round(form_score_normalized, 3),
        },
        "source_attribution": (
            "Recorded results come from local tournament state; projected "
            "matches use strength-derived expected scorelines. Pre-tournament "
            "form is illustrative only."
        ),
        "limitations": [
            "Projected outcomes are strength-based expectations, not actual "
            "match results or forecasts.",
            "Form score uses exponential decay (0.8) weighting of recent "
            "points; it is a presentation summary, not a model probability.",
            "Recorded and projected matches may interleave; the trajectory "
            "shows projected (chronological) then recorded (most recent first).",
        ],
    })


def _match_model_comparison(home_team: str, away_team: str) -> dict[str, Any] | None:
    """Return 1x2 probabilities from both Poisson and Dixon-Coles for a match.

    Used to populate the ``model_comparison`` field in per-match prediction
    responses so the frontend can render a side-by-side comparison without
    making two separate API calls.
    """
    comparison: dict[str, Any] = {}
    try:
        prediction = load_score_prediction(home_team, away_team)
        if not isinstance(prediction, dict):
            comparison["poisson"] = {
                "home": round(float(prediction.summary.home_win), 4),
                "draw": round(float(prediction.summary.draw), 4),
                "away": round(float(prediction.summary.away_win), 4),
            }
    except Exception:
        logger.warning("match model comparison: poisson failed", exc_info=True)
        pass
    try:
        prediction = load_score_prediction_dc(home_team, away_team)
        if not isinstance(prediction, dict):
            comparison["dixon_coles"] = {
                "home": round(float(prediction.summary.home_win), 4),
                "draw": round(float(prediction.summary.draw), 4),
                "away": round(float(prediction.summary.away_win), 4),
            }
    except Exception:
        logger.warning("match model comparison: dixon_coles failed", exc_info=True)
        pass
    return comparison if len(comparison) >= 2 else None


def get_match_prediction(home_team: str, away_team: str) -> dict:
    try:
        prediction = load_score_prediction(home_team, away_team)
    except Exception as exc:
        logger.warning("get_match_prediction failed", exc_info=True)
        return _make_error_response(str(exc))
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
    model_cmp = _match_model_comparison(home_team, away_team)
    if model_cmp:
        result["model_comparison"] = model_cmp
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
        logger.warning("get_match_prediction_dc failed", exc_info=True)
        return _make_error_response(str(exc))
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
        logger.warning("get_match_prediction_dc: enrichment failed", exc_info=True)
        pass  # enrichment is optional
    model_cmp = _match_model_comparison(home_team, away_team)
    if model_cmp:
        result["model_comparison"] = model_cmp
    # Add bootstrap confidence intervals (cached, best-effort)
    ci = _get_prediction_confidence(home_team, away_team)
    if ci:
        result["confidence_intervals"] = ci
    return _clean_json_value(result)


# --- Prediction confidence interval cache ---
_PREDICTION_CI_CACHE: dict[str, Any] = {}
_PREDICTION_CI_TTL_SECONDS = 600  # 10 minutes


def _resolve_tuned_decay() -> float | None:
    """Read the tuned DC decay from calibration backtest results, if available."""
    try:
        tuning_path = (
            _settings().report_root
            / "calibration_backtest"
            / "decay_tuning_results.json"
        )
        if tuning_path.exists():
            data = _read_json(tuning_path)
            best = data.get("best_decay")
            if isinstance(best, (int, float)) and best >= 0:
                return float(best)
    except Exception:
        logger.warning("resolve tuned decay failed", exc_info=True)
        pass
    return None


def _get_prediction_confidence(
    home_team: str, away_team: str, *, force_refresh: bool = False,
    model_type: str = "dixon_coles",
) -> dict[str, Any] | None:
    """Return cached bootstrap confidence intervals for a match prediction.

    Uses n_bootstrap=50 for API-friendly latency. Returns None on failure.
    The cache is keyed by ``(home, away, model_type)`` so that ensemble
    predictions do not silently reuse DC-only CIs (and vice versa).
    """
    import time as _time

    cache_key = f"{home_team}__{away_team}__{model_type}"
    now = _time.time()
    cached = _PREDICTION_CI_CACHE.get(cache_key)
    if (
        not force_refresh
        and cached is not None
        and now - cached.get("timestamp", 0) < _PREDICTION_CI_TTL_SECONDS
    ):
        cached_data = cached.get("data")
        if isinstance(cached_data, dict):
            # Mark as cache hit for transparency
            cached_data["cached"] = True
            cached_data["cache_age_seconds"] = int(now - cached.get("timestamp", 0))
        return cached_data

    try:
        from scoutfootball.models import bootstrap_prediction_confidence

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return None

        decay = _resolve_tuned_decay()
        ci = bootstrap_prediction_confidence(
            team_match,
            str(home_team),
            str(away_team),
            n_bootstrap=50,
            confidence_level=0.90,
            decay=decay,
        )
        result = _clean_json_value({
            "n_bootstrap": ci.n_bootstrap,
            "confidence_level": 0.90,
            "failed_iterations": ci.failed_iterations,
            "model_type": model_type,
            "cached": False,
            "home_win": [ci.home_win_low, ci.home_win_high],
            "draw": [ci.draw_low, ci.draw_high],
            "away_win": [ci.away_win_low, ci.away_win_high],
            "home_lambda": [ci.home_lambda_low, ci.home_lambda_high],
            "away_lambda": [ci.away_lambda_low, ci.away_lambda_high],
        })
        _PREDICTION_CI_CACHE[cache_key] = {"data": result, "timestamp": now}
        return result
    except Exception:
        logger.warning("get prediction confidence failed", exc_info=True)
        return None


def get_form_weighted_prediction(home_team: str, away_team: str) -> dict:
    """Predict a match using form-weighted Dixon-Coles.

    Uses :func:`fit_dixon_coles_with_form` to apply form-based match weights
    on top of the tuned time-decay parameter. Returns the same structure as
    :func:`get_match_prediction_dc` plus form-specific metadata.
    """
    try:
        from scoutfootball.models import (
            fit_dixon_coles_with_form,
            predict_match_dc,
        )

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return _make_error_response("Insufficient team_match data for form-weighted prediction")

        decay = _resolve_tuned_decay()
        model = fit_dixon_coles_with_form(
            team_match,
            decay=decay,
            form_lookback=5,
            form_factor=0.3,
        )
        pred = predict_match_dc(model, str(home_team), str(away_team))

        result = {
            "home_team": home_team,
            "away_team": away_team,
            "model_type": "dixon_coles_form",
            "model_version": "1.0",
            "home_lambda": pred.home_lambda,
            "away_lambda": pred.away_lambda,
            "home_win": pred.summary.home_win,
            "draw": pred.summary.draw,
            "away_win": pred.summary.away_win,
            "over_2_5": pred.summary.over_2_5,
            "btts_yes": pred.summary.btts_yes,
            "score_matrix": _score_matrix_to_list(pred),
            "form_config": {
                "lookback": 5,
                "form_factor": 0.3,
                "decay": decay,
            },
            "rho": model.rho,
            "home_advantage": model.home_advantage,
        }
        # Add confidence intervals (cached, best-effort)
        ci = _get_prediction_confidence(home_team, away_team, model_type="dixon_coles_form")
        if ci:
            result["confidence_intervals"] = ci
        return _clean_json_value(result)
    except Exception as exc:
        logger.warning("get_form_weighted_prediction failed", exc_info=True)
        return _make_error_response(str(exc))


def get_ensemble_prediction(home_team: str, away_team: str, *, recalibrate: bool = False) -> dict:
    """Predict a match using an ensemble of Poisson, DC, and form-weighted DC.

    Blends the three model predictions using cached optimal weights when
    available (falling back to equal weights). When ``recalibrate`` is True,
    applies isotonic recalibration to the blended 1x2 probabilities if a
    fitted calibrator is available from the backtest artifacts.
    """
    try:
        from scoutfootball.models import (
            ensemble_prediction,
            fit_dixon_coles,
            fit_dixon_coles_with_form,
            fit_independent_poisson,
            load_ensemble_weights,
            predict_match,
            predict_match_dc,
        )

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return _make_error_response("Insufficient team_match data for ensemble prediction")

        decay = _resolve_tuned_decay()

        # Fit all three models
        poisson_model = fit_independent_poisson(team_match)
        dc_model = fit_dixon_coles(team_match, decay=decay)
        form_model = fit_dixon_coles_with_form(
            team_match, decay=decay, form_lookback=5, form_factor=0.3,
        )

        # Predict with each model
        poisson_pred = predict_match(poisson_model, str(home_team), str(away_team))
        dc_pred = predict_match_dc(dc_model, str(home_team), str(away_team))
        form_pred = predict_match_dc(form_model, str(home_team), str(away_team))

        # Use cached optimal weights if available, otherwise equal weights
        weights_path = (
            _settings().report_root
            / "calibration_backtest"
            / "ensemble_optimal_weights.json"
        )
        cached_weights = load_ensemble_weights(weights_path)
        weights_source = "equal"
        if cached_weights:
            weights = cached_weights
            weights_source = "optimized"
        else:
            weights = None
            weights_source = "equal"

        ens = ensemble_prediction({
            "poisson": poisson_pred,
            "dixon_coles": dc_pred,
            "dixon_coles_form": form_pred,
        }, weights=weights)

        result = {
            "home_team": home_team,
            "away_team": away_team,
            "model_type": "ensemble",
            "model_version": "1.0",
            "home_lambda": ens.home_lambda,
            "away_lambda": ens.away_lambda,
            "home_win": ens.home_win,
            "draw": ens.draw,
            "away_win": ens.away_win,
            "over_2_5": ens.over_2_5,
            "btts_yes": ens.btts_yes,
            "score_matrix": _clean_json_value(ens.score_matrix.to_numpy().tolist()),
            "weights": ens.weights,
            "weights_source": weights_source,
            "model_predictions": ens.model_predictions,
        }

        # Apply isotonic recalibration if requested and calibrator available
        if recalibrate:
            calibrator = _get_isotonic_calibrator()
            if calibrator is not None:
                from scoutfootball.models import apply_recalibration

                hw, dr, aw = apply_recalibration(
                    calibrator,
                    float(ens.home_win),
                    float(ens.draw),
                    float(ens.away_win),
                )
                result["raw_home_win"] = ens.home_win
                result["raw_draw"] = ens.draw
                result["raw_away_win"] = ens.away_win
                result["home_win"] = hw
                result["draw"] = dr
                result["away_win"] = aw
                result["recalibrated"] = True
                result["calibration_n_samples"] = calibrator.n_samples
            else:
                result["recalibrated"] = False
                result["recalibration_note"] = "No calibration artifacts available"

        # Add confidence intervals (cached, best-effort)
        ci = _get_prediction_confidence(home_team, away_team, model_type="ensemble")
        if ci:
            result["confidence_intervals"] = ci
        return _clean_json_value(result)
    except Exception as exc:
        logger.warning("get_ensemble_prediction failed", exc_info=True)
        return _make_error_response(str(exc))


def get_match_momentum(
    home_team: str,
    away_team: str,
    *,
    home_goals: int = 0,
    away_goals: int = 0,
    minute: int = 0,
) -> dict:
    """Return in-play win probability timeline for a match.

    Computes momentum based on pre-match Dixon-Coles prediction lambdas and
    the current scoreline/minute. Returns a timeline of win/draw/loss
    probabilities at 5-minute intervals from the current minute to 90'.
    """
    try:
        from scoutfootball.models import compute_momentum

        # Get pre-match prediction to extract lambdas
        dc_pred = get_match_prediction_dc(home_team, away_team)
        if "error" in dc_pred:
            return dc_pred

        home_lambda = float(dc_pred.get("home_lambda", 1.3))
        away_lambda = float(dc_pred.get("away_lambda", 1.1))

        momentum = compute_momentum(
            home_team,
            away_team,
            home_lambda,
            away_lambda,
            current_home_goals=home_goals,
            current_away_goals=away_goals,
            current_minute=minute,
        )

        return _clean_json_value({
            "home_team": home_team,
            "away_team": away_team,
            "home_lambda": home_lambda,
            "away_lambda": away_lambda,
            "current_minute": minute,
            "current_home_goals": home_goals,
            "current_away_goals": away_goals,
            "timeline": [
                {
                    "minute": p.minute,
                    "home_win": p.home_win,
                    "draw": p.draw,
                    "away_win": p.away_win,
                    "remaining_home_lambda": p.remaining_home_lambda,
                    "remaining_away_lambda": p.remaining_away_lambda,
                }
                for p in momentum.timeline
            ],
        })
    except Exception as exc:
        logger.warning("get_match_momentum failed", exc_info=True)
        return _make_error_response(str(exc))


def get_calibration_drift() -> dict:
    """Return calibration drift report for the latest backtest predictions.

    Reads the Poisson backtest predictions artifact and computes per-window
    RPS/Brier/LogLoss to detect calibration degradation over time.
    """
    import time

    cache_key = "drift_data"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get("drift_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_calibration_drift

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "poisson_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                # Ensure actual_outcome column exists
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )

                if "match_date" not in preds_df.columns:
                    result = {"status": "no_date_column"}
                else:
                    report = compute_calibration_drift(preds_df)
                    result = _clean_json_value({
                        "status": "ok",
                        "drift_detected": report.drift_detected,
                        "drift_metric": report.drift_metric,
                        "drift_threshold": report.drift_threshold,
                        "overall_metrics": report.overall_metrics,
                        "n_windows": len(report.windows),
                        "windows": report.windows,
                        "latest_window": report.latest_window,
                    })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE["drift_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_calibration_drift failed", exc_info=True)
        return _make_error_response(str(exc))


def get_calibration_drift_timeline() -> dict:
    """Return a chart-ready calibration drift timeline.

    Wraps :func:`get_calibration_drift` and projects the per-window metrics
    into a flat ``points`` array suitable for a line chart (date + rps/brier/
    log_loss + n_matches). Includes the drift metric name, threshold, and
    detected flag so the frontend can draw a threshold reference line.
    """
    try:
        report = get_calibration_drift()
        if report.get("status") != "ok":
            return report

        windows = report.get("windows", [])
        points: list[dict[str, Any]] = []
        for w in windows:
            points.append({
                "date": w.get("end_date") or w.get("start_date") or "",
                "start_date": w.get("start_date", ""),
                "end_date": w.get("end_date", ""),
                "n_matches": w.get("n_matches", 0),
                "rps_1x2": w.get("rps_1x2"),
                "brier_1x2": w.get("brier_1x2"),
                "log_loss_exact": w.get("log_loss_exact"),
            })

        return _clean_json_value({
            "status": "ok",
            "metric": report.get("drift_metric", "rps_1x2"),
            "threshold": report.get("drift_threshold", 0.05),
            "drift_detected": report.get("drift_detected", False),
            "n_points": len(points),
            "points": points,
            "overall_metrics": report.get("overall_metrics", {}),
        })
    except Exception as exc:
        logger.warning("get_calibration_drift_timeline failed", exc_info=True)
        return _make_error_response(str(exc))


# --- Isotonic calibrator cache ---
_CALIBRATOR_CACHE: dict[str, Any] = {"calibrator": None, "timestamp": 0.0}
_CALIBRATOR_TTL_SECONDS = 600  # 10 minutes


def _get_isotonic_calibrator(*, force_refresh: bool = False) -> object | None:
    """Return a cached IsotonicCalibrator fitted from backtest predictions.

    Reads the DC decay backtest predictions parquet (which has the best
    calibration) and fits isotonic regression. Returns None if artifacts
    are missing.
    """
    import time as _time

    now = _time.time()
    cached = _CALIBRATOR_CACHE.get("calibrator")
    if (
        not force_refresh
        and cached is not None
        and now - _CALIBRATOR_CACHE.get("timestamp", 0) < _CALIBRATOR_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.models import fit_isotonic_calibrator

        settings = _settings()
        # Prefer DC-with-decay predictions (best calibrated model)
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            # Fall back to Poisson predictions
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            return None

        preds_df = _read_parquet(pred_path)
        if preds_df.empty:
            return None

        # Ensure actual_outcome column exists
        if "actual_outcome" not in preds_df.columns:
            if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                import numpy as np

                preds_df["actual_outcome"] = np.where(
                    preds_df["home_goals"] > preds_df["away_goals"],
                    "home_win",
                    np.where(
                        preds_df["home_goals"] == preds_df["away_goals"],
                        "draw",
                        "away_win",
                    ),
                )
            else:
                return None

        calibrator = fit_isotonic_calibrator(preds_df)
        _CALIBRATOR_CACHE["calibrator"] = calibrator
        _CALIBRATOR_CACHE["timestamp"] = now
        return calibrator
    except Exception:
        logger.warning("get isotonic calibrator failed", exc_info=True)
        return None


def get_ensemble_weights() -> dict:
    """Return the cached ensemble optimal weights and their provenance.

    If no optimization has been run yet, returns ``not_available`` with
    instructions on how to generate the weights.
    """
    import json

    try:
        weights_path = (
            _settings().report_root
            / "calibration_backtest"
            / "ensemble_optimal_weights.json"
        )
        if not weights_path.exists():
            return {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball optimize-ensemble' to compute "
                    "and cache optimal ensemble weights"
                ),
                "default_weights": {
                    "poisson": 0.33,
                    "dixon_coles": 0.34,
                    "dixon_coles_form": 0.33,
                },
            }

        with open(weights_path, encoding="utf-8") as f:
            data = json.load(f)
        return _clean_json_value({
            "status": "ok",
            "weights": data.get("weights"),
            "rps": data.get("rps"),
            "n_matches": data.get("n_matches"),
            "saved_at": data.get("saved_at"),
            "format": data.get("format"),
            "path": str(weights_path),
        })
    except Exception as exc:
        logger.warning("get_ensemble_weights failed", exc_info=True)
        return _make_error_response(str(exc))


def get_calibration_comparison() -> dict:
    """Return a per-score-line comparison of raw vs recalibrated predictions.

    Fits an isotonic calibrator from the backtest predictions and compares
    raw vs recalibrated Brier/RPS overall and per score line.
    """
    import time

    cache_key = "calibration_comparison"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get("calibration_comparison_timestamp", 0)
        < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_calibration_comparison

        calibrator = _get_isotonic_calibrator()
        if calibrator is None:
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts first"
                ),
            }
        else:
            settings = _settings()
            # Use the same predictions the calibrator was fitted on
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "dixon_coles_decay_backtest_predictions.parquet"
            )
            if not pred_path.exists():
                pred_path = (
                    settings.report_root
                    / "calibration_backtest"
                    / "poisson_backtest_predictions.parquet"
                )
            if not pred_path.exists():
                result = {
                    "status": "not_available",
                    "instructions": "No backtest predictions found",
                }
            else:
                preds_df = _read_parquet(pred_path)
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )

                comparison = compute_calibration_comparison(preds_df, calibrator)
                result = _clean_json_value({
                    "status": "ok",
                    "overall": comparison.overall,
                    "improvement": comparison.improvement,
                    "by_score_line": comparison.by_score_line,
                    "by_league": list(comparison.by_league) if comparison.by_league else [],
                    "n_matches": comparison.n_matches,
                    "calibrator_metrics": {
                        "brier_before": calibrator.brier_before,
                        "brier_after": calibrator.brier_after,
                        "rps_before": calibrator.rps_before,
                        "rps_after": calibrator.rps_after,
                        "n_samples": calibrator.n_samples,
                    },
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE["calibration_comparison_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_calibration_comparison failed", exc_info=True)
        return _make_error_response(str(exc))


def get_prediction_attribution(home_team: str, away_team: str) -> dict:
    """Return permutation-based feature attribution for a match prediction.

    Fits a Dixon-Coles model on the current team-match data and quantifies
    how each factor (home attack, home defense, away attack, away defense,
    home advantage, league mean goals, rho correction) contributes to the
    home-win probability by neutralizing one factor at a time.
    """
    try:
        from scoutfootball.models import (
            compute_prediction_attribution,
            fit_dixon_coles,
        )

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return {
                "status": "not_available",
                "instructions": "Insufficient team_match data for attribution",
            }

        decay = _resolve_tuned_decay()
        model = fit_dixon_coles(team_match, decay=decay)
        attribution = compute_prediction_attribution(
            model, str(home_team), str(away_team)
        )
        return _clean_json_value({
            "status": "ok",
            "home_team": attribution.home_team,
            "away_team": attribution.away_team,
            "baseline_home_win": attribution.baseline_home_win,
            "baseline_draw": attribution.baseline_draw,
            "baseline_away_win": attribution.baseline_away_win,
            "factors": attribution.factors,
            "model_type": "dixon_coles",
            "method": "permutation-neutralize",
            "n_factors": len(attribution.factors),
        })
    except Exception as exc:
        logger.warning("get_prediction_attribution failed", exc_info=True)
        return _make_error_response(str(exc))


def get_prediction_attribution_ci(
    home_team: str, away_team: str, *, n_bootstrap: int = 30,
) -> dict:
    """Return bootstrap confidence intervals for prediction attribution deltas.

    Fits Dixon-Coles on the current team-match data, then bootstraps the
    attribution to produce 90% CIs on each factor's delta.
    """
    try:
        from scoutfootball.models import (
            bootstrap_attribution_confidence,
        )

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return {
                "status": "not_available",
                "instructions": "Insufficient team_match data for bootstrap CI",
            }

        decay = _resolve_tuned_decay()
        ci = bootstrap_attribution_confidence(
            team_match,
            str(home_team),
            str(away_team),
            n_bootstrap=n_bootstrap,
            confidence_level=0.90,
            decay=decay,
            seed=42,
        )
        return _clean_json_value({
            "status": "ok",
            "home_team": ci.home_team,
            "away_team": ci.away_team,
            "n_bootstrap": ci.n_bootstrap,
            "failed_iterations": ci.failed_iterations,
            "confidence_level": 0.90,
            "factor_cis": ci.factor_cis,
        })
    except Exception as exc:
        logger.warning("get_prediction_attribution_ci failed", exc_info=True)
        return _make_error_response(str(exc))


def get_ensemble_attribution(home_team: str, away_team: str) -> dict:
    """Return per-model and blended prediction attribution for the ensemble.

    Fits Dixon-Coles and form-weighted Dixon-Coles, computes attribution
    for each, and blends with equal weights (or cached optimal weights
    if available).
    """
    try:
        from scoutfootball.models import (
            compute_ensemble_attribution,
            fit_dixon_coles,
            fit_dixon_coles_with_form,
            load_ensemble_weights,
        )

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return {
                "status": "not_available",
                "instructions": "Insufficient team_match data for ensemble attribution",
            }

        decay = _resolve_tuned_decay()
        dc_model = fit_dixon_coles(team_match, decay=decay)
        form_model = fit_dixon_coles_with_form(team_match, decay=decay)

        models = {"dixon_coles": dc_model, "dixon_coles_form": form_model}

        # Try to load cached optimal weights
        weights = None
        try:
            cached = load_ensemble_weights()
            if cached and "weights" in cached:
                w = cached["weights"]
                weights = {
                    "dixon_coles": w.get("dixon_coles", 0.5),
                    "dixon_coles_form": w.get("dixon_coles_form", 0.5),
                }
        except Exception:
            logger.warning("get_ensemble_attribution: load_ensemble_weights failed", exc_info=True)
            pass

        ensemble_attr = compute_ensemble_attribution(
            models, str(home_team), str(away_team), weights=weights,
        )

        return _clean_json_value({
            "status": "ok",
            "home_team": ensemble_attr.home_team,
            "away_team": ensemble_attr.away_team,
            "weights": ensemble_attr.weights,
            "weights_source": "optimized" if weights else "equal",
            "blended": {
                "baseline_home_win": ensemble_attr.blended.baseline_home_win,
                "baseline_draw": ensemble_attr.blended.baseline_draw,
                "baseline_away_win": ensemble_attr.blended.baseline_away_win,
                "factors": ensemble_attr.blended.factors,
            },
            "per_model": {
                name: {
                    "baseline_home_win": attr.baseline_home_win,
                    "baseline_draw": attr.baseline_draw,
                    "baseline_away_win": attr.baseline_away_win,
                    "factors": attr.factors,
                }
                for name, attr in ensemble_attr.per_model.items()
            },
        })
    except Exception as exc:
        logger.warning("get_ensemble_attribution failed", exc_info=True)
        return _make_error_response(str(exc))


def get_ensemble_attribution_ci(
    home_team: str, away_team: str, *, n_bootstrap: int = 30,
) -> dict:
    """Return bootstrap CIs for ensemble attribution blended factor deltas.

    Fits both Dixon-Coles and form-weighted Dixon-Coles, bootstraps the
    ensemble attribution to produce 90% CIs on each factor's blended delta.
    """
    try:
        from scoutfootball.models import (
            bootstrap_ensemble_attribution_confidence,
        )

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return {
                "status": "not_available",
                "instructions": "Insufficient team_match data for ensemble CI",
            }

        decay = _resolve_tuned_decay()

        # Load cached optimal weights if available
        weights = None
        try:
            from scoutfootball.models import load_ensemble_weights

            cached = load_ensemble_weights()
            if cached and "weights" in cached:
                w = cached["weights"]
                weights = {
                    "dixon_coles": w.get("dixon_coles", 0.5),
                    "dixon_coles_form": w.get("dixon_coles_form", 0.5),
                }
        except Exception:
            logger.warning(
                "get_ensemble_attribution_ci: load_ensemble_weights failed", exc_info=True
            )
            pass

        ci = bootstrap_ensemble_attribution_confidence(
            team_match,
            str(home_team),
            str(away_team),
            n_bootstrap=n_bootstrap,
            confidence_level=0.90,
            decay=decay,
            weights=weights,
            seed=42,
        )
        return _clean_json_value({
            "status": "ok",
            "home_team": ci.home_team,
            "away_team": ci.away_team,
            "n_bootstrap": ci.n_bootstrap,
            "failed_iterations": ci.failed_iterations,
            "confidence_level": 0.90,
            "weights_source": "optimized" if weights else "equal",
            "factor_cis": ci.factor_cis,
        })
    except Exception as exc:
        logger.warning("get_ensemble_attribution_ci failed", exc_info=True)
        return _make_error_response(str(exc))


def get_value_bet_analysis(
    home_team: str,
    away_team: str,
    *,
    home_odds: float,
    draw_odds: float,
    away_odds: float,
) -> dict:
    """Compute value betting analysis for a match given market odds.

    Fetches the Dixon-Coles prediction for the fixture, then computes
    per-outcome expected value, edge, Kelly fraction, and recommendation.
    """
    try:
        if home_odds < 1.0 or draw_odds < 1.0 or away_odds < 1.0:
            return _make_error_response("All odds must be >= 1.0")

        prediction = get_match_prediction_dc(home_team, away_team)
        if "error" in prediction:
            return _make_error_response(prediction["error"])

        model_probs = {
            "home_win": float(prediction.get("home_win", 0.0)),
            "draw": float(prediction.get("draw", 0.0)),
            "away_win": float(prediction.get("away_win", 0.0)),
        }
        odds = {
            "home_win": float(home_odds),
            "draw": float(draw_odds),
            "away_win": float(away_odds),
        }

        from scoutfootball.evaluation.backtests import compute_value_bets

        analysis = compute_value_bets(model_probs, odds)
        return _clean_json_value({
            "status": "ok",
            "home_team": home_team,
            "away_team": away_team,
            "model_type": prediction.get("model_type", "dixon_coles"),
            "outcomes": [
                {
                    "outcome": o.outcome,
                    "model_probability": o.model_probability,
                    "decimal_odds": o.decimal_odds,
                    "implied_probability": o.implied_probability,
                    "expected_value": o.expected_value,
                    "edge": o.edge,
                    "kelly_fraction": o.kelly_fraction,
                    "recommendation": o.recommendation,
                }
                for o in analysis.outcomes
            ],
            "best_bet": (
                {
                    "outcome": analysis.best_bet.outcome,
                    "model_probability": analysis.best_bet.model_probability,
                    "decimal_odds": analysis.best_bet.decimal_odds,
                    "expected_value": analysis.best_bet.expected_value,
                    "edge": analysis.best_bet.edge,
                    "kelly_fraction": analysis.best_bet.kelly_fraction,
                }
                if analysis.best_bet
                else None
            ),
            "overround": analysis.overround,
            "total_implied": analysis.total_implied,
            "disclaimer": (
                "Analysis uses model probabilities, not live market data. "
                "For research purposes only."
            ),
        })
    except ValueError as exc:
        return _make_error_response(str(exc))
    except Exception as exc:
        logger.warning("get_value_bet_analysis failed", exc_info=True)
        return _make_error_response(str(exc))


def get_reliability_diagram(*, n_bins: int = 10) -> dict:
    """Return a reliability diagram for 1X2 prediction calibration.

    Reads the backtest predictions artifact and bins predicted probabilities
    against observed frequencies for chart-ready visualization.
    """
    import time

    cache_key = f"reliability_{n_bins}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_reliability_diagram

        settings = _settings()
        # Prefer DC decay predictions, fall back to Poisson
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                diagram = compute_reliability_diagram(preds_df, n_bins=n_bins)
                result = _clean_json_value({
                    "status": "ok",
                    "n_bins": diagram.n_bins,
                    "n_predictions": diagram.n_predictions,
                    "overall": diagram.overall,
                    "per_outcome": {
                        outcome: [
                            {
                                "bin_lower": b.bin_lower,
                                "bin_upper": b.bin_upper,
                                "bin_center": b.bin_center,
                                "mean_predicted": b.mean_predicted,
                                "observed_frequency": b.observed_frequency,
                                "n_samples": b.n_samples,
                            }
                            for b in bins
                        ]
                        for outcome, bins in diagram.per_outcome.items()
                    },
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_reliability_diagram failed", exc_info=True)
        return _make_error_response(str(exc))


def get_team_accuracy(team_id: str, *, min_predictions: int = 3) -> dict:
    """Return per-team prediction accuracy from backtest predictions.

    Computes historical hit rate, average confidence, and calibration gap
    for the specified team (as home or away).
    """
    import time

    cache_key = f"team_accuracy_{team_id}_{min_predictions}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_team_accuracy

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_team_accuracy(preds_df, min_predictions=min_predictions)
                # Filter to the requested team
                team_entry = next(
                    (e for e in report.entries if e.team_id == team_id),
                    None,
                )
                if team_entry is None:
                    result = {
                        "status": "not_found",
                        "team_id": team_id,
                        "message": (
                            f"Team '{team_id}' not found in backtest predictions "
                            f"or has fewer than {min_predictions} predictions"
                        ),
                    }
                else:
                    result = _clean_json_value({
                        "status": "ok",
                        "team_id": team_entry.team_id,
                        "n_predictions": team_entry.n_predictions,
                        "n_correct": team_entry.n_correct,
                        "hit_rate": team_entry.hit_rate,
                        "avg_confidence": team_entry.avg_confidence,
                        "calibration_gap": team_entry.calibration_gap,
                        "last_match_date": team_entry.last_match_date,
                        "overall_hit_rate": report.overall_hit_rate,
                        "total_predictions": report.total_predictions,
                    })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_team_accuracy failed", exc_info=True)
        return _make_error_response(str(exc))


def get_model_comparison() -> dict:
    """Return a unified comparison of all available backtest models.

    Loads all backtest prediction parquet files (Poisson, Dixon-Coles,
    Dixon-Coles-decay) and computes aligned metrics (log_loss, brier, rps,
    accuracy, avg_confidence, calibration_gap) on the intersection of
    matches. Determines the winning model per metric. Cached for 5 minutes.
    """
    import time

    cache_key = "model_comparison"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_model_comparison

        settings = _settings()
        bt_dir = settings.report_root / "calibration_backtest"

        model_files = [
            ("poisson", "poisson_backtest_predictions.parquet"),
            ("dixon_coles", "dixon_coles_backtest_predictions.parquet"),
            ("dixon_coles_decay", "dixon_coles_decay_backtest_predictions.parquet"),
        ]

        model_predictions: dict[str, Any] = {}
        for model_key, filename in model_files:
            path = bt_dir / filename
            if not path.exists():
                continue
            df = _read_parquet(path)
            if df.empty:
                continue
            if "actual_outcome" not in df.columns:
                if "home_goals" in df.columns and "away_goals" in df.columns:
                    import numpy as np

                    df["actual_outcome"] = np.where(
                        df["home_goals"] > df["away_goals"],
                        "home_win",
                        np.where(
                            df["home_goals"] == df["away_goals"],
                            "draw",
                            "away_win",
                        ),
                    )
            model_predictions[model_key] = df

        if not model_predictions:
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball backtest' to generate prediction artifacts"
                ),
            }
        else:
            comparison = compute_model_comparison(model_predictions)
            result = _clean_json_value({
                "status": "ok",
                "n_aligned": comparison.n_aligned,
                "n_models": comparison.n_models,
                "models": [
                    {
                        "model": e.model,
                        "label": e.label,
                        "n_predictions": e.n_predictions,
                        "log_loss": e.log_loss,
                        "brier": e.brier,
                        "rps": e.rps,
                        "accuracy": e.accuracy,
                        "avg_confidence": e.avg_confidence,
                        "calibration_gap": e.calibration_gap,
                    }
                    for e in comparison.models
                ],
                "metric_winners": comparison.metric_winners,
            })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_model_comparison failed", exc_info=True)
        return _make_error_response(str(exc))


def get_scoreline_calibration(*, max_scoreline: int = 5, min_samples: int = 3) -> dict:
    """Return score-line calibration from backtest predictions.

    Groups predictions by actual score-line and compares predicted vs
    actual 1x2 outcome rates per score-line bucket. Prefers Dixon-Coles
    decay predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"scoreline_cal_{max_scoreline}_{min_samples}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_scoreline_calibration

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_scoreline_calibration(
                    preds_df,
                    max_scoreline=max_scoreline,
                    min_samples=min_samples,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "n_scorelines": report.n_scorelines,
                    "entries": [
                        {
                            "scoreline": e.scoreline,
                            "outcome": e.outcome,
                            "n_matches": e.n_matches,
                            "avg_home_win_prob": e.avg_home_win_prob,
                            "avg_draw_prob": e.avg_draw_prob,
                            "avg_away_win_prob": e.avg_away_win_prob,
                            "actual_home_win_rate": e.actual_home_win_rate,
                            "actual_draw_rate": e.actual_draw_rate,
                            "actual_away_win_rate": e.actual_away_win_rate,
                        }
                        for e in report.entries
                    ],
                    "outcome_summary": report.outcome_summary,
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_scoreline_calibration failed", exc_info=True)
        return _make_error_response(str(exc))


def get_confidence_distribution(*, n_bins: int = 10, min_samples_per_bucket: int = 5) -> dict:
    """Return prediction confidence distribution from backtest predictions.

    Buckets predictions by max probability (confidence) and computes
    accuracy per bucket. Prefers Dixon-Coles decay predictions, falls back
    to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"confidence_dist_{n_bins}_{min_samples_per_bucket}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_confidence_distribution

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_confidence_distribution(
                    preds_df,
                    n_bins=n_bins,
                    min_samples_per_bucket=min_samples_per_bucket,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_predictions": report.n_predictions,
                    "n_buckets": report.n_buckets,
                    "overall_accuracy": report.overall_accuracy,
                    "overall_confidence": report.overall_confidence,
                    "buckets": [
                        {
                            "bucket_label": b.bucket_label,
                            "bucket_lower": b.bucket_lower,
                            "bucket_upper": b.bucket_upper,
                            "n_predictions": b.n_predictions,
                            "accuracy": b.accuracy,
                            "avg_confidence": b.avg_confidence,
                            "calibration_gap": b.calibration_gap,
                        }
                        for b in report.buckets
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_confidence_distribution failed", exc_info=True)
        return _make_error_response(str(exc))


def get_h2h_bias_correction(
    home_team: str,
    away_team: str,
    *,
    max_correction: float = 0.10,
    min_meetings: int = 3,
    blend_weight: float = 0.25,
) -> dict:
    """Return H2H bias-corrected 1x2 probabilities for a fixture.

    Fetches the baseline DC prediction for the fixture, retrieves the
    historical H2H summary, and nudges the baseline probabilities toward
    the historical outcome rates by ``blend_weight`` (clipped to
    ``±max_correction``).
    """
    try:
        from scoutfootball.evaluation.backtests import compute_h2h_bias_correction

        baseline = get_match_prediction_dc(home_team, away_team)
        if baseline.get("status") not in (None, "ok"):
            return {
                "status": "not_available",
                "reason": "baseline_prediction_unavailable",
                "home_team": home_team,
                "away_team": away_team,
            }

        summary_block = baseline.get("summary", {}) or {}
        baseline_probs = {
            "home_win": float(summary_block.get("home_win_probability", 0.0)),
            "draw": float(summary_block.get("draw_probability", 0.0)),
            "away_win": float(summary_block.get("away_win_probability", 0.0)),
        }

        h2h = get_head_to_head(home_team, away_team)
        h2h_summary = h2h.get("summary", {}) or {}

        report = compute_h2h_bias_correction(
            home_team,
            away_team,
            baseline_probs,
            h2h_summary,
            max_correction=max_correction,
            min_meetings=min_meetings,
            blend_weight=blend_weight,
        )

        return _clean_json_value({
            "status": "ok",
            "home_team": report.home_team,
            "away_team": report.away_team,
            "baseline_probabilities": report.baseline_probabilities,
            "corrected_probabilities": report.corrected_probabilities,
            "h2h_rates": report.h2h_rates,
            "adjustments": report.adjustments,
            "n_meetings": report.n_meetings,
            "correction_applied": report.correction_applied,
            "disclaimer": report.disclaimer,
        })
    except Exception as exc:
        logger.warning("get_h2h_bias_correction failed", exc_info=True)
        return _make_error_response(str(exc))


def get_error_analysis(
    *,
    n_bins: int = 5,
    min_samples_per_bucket: int = 5,
    top_n: int = 5,
) -> dict:
    """Return prediction error analysis from backtest predictions.

    Buckets predictions by confidence, computes per-bucket accuracy/Brier/
    log-loss, and surfaces the worst matches (highest Brier) per bucket
    and overall. Prefers Dixon-Coles decay predictions, falls back to
    Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"error_analysis_{n_bins}_{min_samples_per_bucket}_{top_n}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_error_analysis

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_error_analysis(
                    preds_df,
                    n_bins=n_bins,
                    min_samples_per_bucket=min_samples_per_bucket,
                    top_n=top_n,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_predictions": report.n_predictions,
                    "n_buckets": report.n_buckets,
                    "overall_accuracy": report.overall_accuracy,
                    "overall_avg_brier": report.overall_avg_brier,
                    "overall_avg_log_loss": report.overall_avg_log_loss,
                    "buckets": [
                        {
                            "bucket_label": b.bucket_label,
                            "bucket_lower": b.bucket_lower,
                            "bucket_upper": b.bucket_upper,
                            "n_predictions": b.n_predictions,
                            "avg_confidence": b.avg_confidence,
                            "accuracy": b.accuracy,
                            "avg_brier": b.avg_brier,
                            "avg_log_loss": b.avg_log_loss,
                            "worst_matches": [
                                {
                                    "match_id": m.match_id,
                                    "home_goals": m.home_goals,
                                    "away_goals": m.away_goals,
                                    "actual_outcome": m.actual_outcome,
                                    "predicted_home_win": m.predicted_home_win,
                                    "predicted_draw": m.predicted_draw,
                                    "predicted_away_win": m.predicted_away_win,
                                    "predicted_outcome": m.predicted_outcome,
                                    "confidence": m.confidence,
                                    "brier": m.brier,
                                    "log_loss": m.log_loss,
                                    "correct": m.correct,
                                }
                                for m in b.worst_matches
                            ],
                        }
                        for b in report.buckets
                    ],
                    "worst_matches_overall": [
                        {
                            "match_id": m.match_id,
                            "home_goals": m.home_goals,
                            "away_goals": m.away_goals,
                            "actual_outcome": m.actual_outcome,
                            "predicted_home_win": m.predicted_home_win,
                            "predicted_draw": m.predicted_draw,
                            "predicted_away_win": m.predicted_away_win,
                            "predicted_outcome": m.predicted_outcome,
                            "confidence": m.confidence,
                            "brier": m.brier,
                            "log_loss": m.log_loss,
                            "correct": m.correct,
                        }
                        for m in report.worst_matches_overall
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_error_analysis failed", exc_info=True)
        return _make_error_response(str(exc))


def get_outcome_distribution() -> dict:
    """Return predicted vs actual 1x2 outcome distribution from backtest.

    Reveals whether the model systematically over- or under-predicts a
    particular outcome class (e.g. too many home wins). Prefers Dixon-Coles
    decay predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = "outcome_distribution"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_outcome_distribution

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_outcome_distribution(preds_df)
                result = _clean_json_value({
                    "status": "ok",
                    "n_predictions": report.n_predictions,
                    "predicted_most_likely": report.predicted_most_likely,
                    "actual_counts": report.actual_counts,
                    "dominant_bias": report.dominant_bias,
                    "disclaimer": report.disclaimer,
                    "entries": [
                        {
                            "outcome": e.outcome,
                            "predicted_count": e.predicted_count,
                            "predicted_share": e.predicted_share,
                            "actual_count": e.actual_count,
                            "actual_share": e.actual_share,
                            "distribution_gap": e.distribution_gap,
                        }
                        for e in report.entries
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_outcome_distribution failed", exc_info=True)
        return _make_error_response(str(exc))


def get_temporal_validation(
    *, n_windows: int = 6, min_samples_per_window: int = 10,
) -> dict:
    """Return per-window metric trends from backtest predictions.

    Groups predictions into time windows and computes accuracy, Brier, RPS,
    LogLoss, and avg_confidence per window. Prefers Dixon-Coles decay
    predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"temporal_validation_{n_windows}_{min_samples_per_window}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_temporal_validation

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_temporal_validation(
                    preds_df,
                    n_windows=n_windows,
                    min_samples_per_window=min_samples_per_window,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_total_matches": report.n_total_matches,
                    "n_windows": report.n_windows,
                    "overall_accuracy": report.overall_accuracy,
                    "overall_brier": report.overall_brier,
                    "overall_rps": report.overall_rps,
                    "overall_log_loss": report.overall_log_loss,
                    "trend": report.trend,
                    "disclaimer": report.disclaimer,
                    "windows": [
                        {
                            "window_label": w.window_label,
                            "window_start": w.window_start,
                            "window_end": w.window_end,
                            "n_matches": w.n_matches,
                            "accuracy": w.accuracy,
                            "brier": w.brier,
                            "rps": w.rps,
                            "log_loss": w.log_loss,
                            "avg_confidence": w.avg_confidence,
                        }
                        for w in report.windows
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_temporal_validation failed", exc_info=True)
        return _make_error_response(str(exc))


def get_probability_heatmap(
    *, n_bins: int = 5, min_samples_per_cell: int = 3,
) -> dict:
    """Return 2D probability heatmap from backtest predictions.

    Buckets predictions into an n_bins × n_bins grid of home_win vs
    away_win probability. Prefers Dixon-Coles decay predictions, falls
    back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"probability_heatmap_{n_bins}_{min_samples_per_cell}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_probability_heatmap

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_probability_heatmap(
                    preds_df,
                    n_bins=n_bins,
                    min_samples_per_cell=min_samples_per_cell,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_predictions": report.n_predictions,
                    "n_bins": report.n_bins,
                    "total_density": report.total_density,
                    "disclaimer": report.disclaimer,
                    "cells": [
                        {
                            "home_bin": c.home_bin,
                            "away_bin": c.away_bin,
                            "home_lo": c.home_lo,
                            "home_hi": c.home_hi,
                            "away_lo": c.away_lo,
                            "away_hi": c.away_hi,
                            "count": c.count,
                            "density": c.density,
                            "accuracy": c.accuracy,
                            "avg_confidence": c.avg_confidence,
                        }
                        for c in report.cells
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_probability_heatmap failed", exc_info=True)
        return _make_error_response(str(exc))


def get_prediction_staleness() -> dict:
    """Return model staleness indicator from backtest data coverage.

    Reports the backtest data date range, days since last match, and
    staleness level (fresh/aging/stale). Prefers Dixon-Coles decay
    predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = "prediction_staleness"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_prediction_staleness

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        model_type = "dixon_coles_decay"
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
            model_type = "poisson"
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                report = compute_prediction_staleness(
                    preds_df, model_type=model_type,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "has_backtest": report.has_backtest,
                    "backtest_start": report.backtest_start,
                    "backtest_end": report.backtest_end,
                    "n_backtest_matches": report.n_backtest_matches,
                    "model_type": report.model_type,
                    "days_since_backtest_end": report.days_since_backtest_end,
                    "staleness_level": report.staleness_level,
                    "disclaimer": report.disclaimer,
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_prediction_staleness failed", exc_info=True)
        return _make_error_response(str(exc))


def get_confidence_interval_plot(
    *, max_points: int = 500,
    ci_lower_col: str = "home_win_ci_lower",
    ci_upper_col: str = "home_win_ci_upper",
) -> dict:
    """Return CI width vs match confidence scatter plot data.

    Each prediction becomes a scatter point with confidence, CI bounds,
    CI width, and correctness flag. Prefers Dixon-Coles decay predictions,
    falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"ci_plot_{max_points}_{ci_lower_col}_{ci_upper_col}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_confidence_interval_plot,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif (
                ci_lower_col not in preds_df.columns
                or ci_upper_col not in preds_df.columns
            ):
                result = {
                    "status": "not_available",
                    "instructions": (
                        f"Backtest predictions do not include CI columns "
                        f"({ci_lower_col}, {ci_upper_col}). Re-run "
                        f"backtest with bootstrap CI generation enabled."
                    ),
                }
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_confidence_interval_plot(
                    preds_df,
                    ci_lower_col=ci_lower_col,
                    ci_upper_col=ci_upper_col,
                    max_points=max_points,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_predictions": report.n_predictions,
                    "avg_confidence": report.avg_confidence,
                    "avg_ci_width": report.avg_ci_width,
                    "correlation": report.correlation,
                    "disclaimer": report.disclaimer,
                    "points": [
                        {
                            "match_id": p.match_id,
                            "home_team": p.home_team,
                            "away_team": p.away_team,
                            "confidence": p.confidence,
                            "ci_lower": p.ci_lower,
                            "ci_upper": p.ci_upper,
                            "ci_width": p.ci_width,
                            "actual_outcome": p.actual_outcome,
                            "correct": p.correct,
                        }
                        for p in report.points
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_confidence_interval_plot failed", exc_info=True)
        return _make_error_response(str(exc))


def get_fold_comparison(*, min_samples_per_fold: int = 5) -> dict:
    """Return per-fold metrics comparison from backtest predictions.

    Groups backtest predictions by the ``fold`` column and computes
    accuracy, Brier, RPS, LogLoss, and avg_confidence per fold, plus a
    stability indicator. Prefers Dixon-Coles decay predictions, falls
    back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"fold_comparison_{min_samples_per_fold}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_fold_comparison

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif "fold" not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        "Backtest predictions do not include a 'fold' column. "
                        "Re-run backtest with cross-validation fold assignment."
                    ),
                }
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_fold_comparison(
                    preds_df, min_samples_per_fold=min_samples_per_fold,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_folds": report.n_folds,
                    "n_total_matches": report.n_total_matches,
                    "overall_accuracy": report.overall_accuracy,
                    "overall_brier": report.overall_brier,
                    "overall_rps": report.overall_rps,
                    "overall_log_loss": report.overall_log_loss,
                    "accuracy_std": report.accuracy_std,
                    "brier_std": report.brier_std,
                    "rps_std": report.rps_std,
                    "stability": report.stability,
                    "disclaimer": report.disclaimer,
                    "folds": [
                        {
                            "fold": f.fold,
                            "n_matches": f.n_matches,
                            "accuracy": f.accuracy,
                            "brier": f.brier,
                            "rps": f.rps,
                            "log_loss": f.log_loss,
                            "avg_confidence": f.avg_confidence,
                        }
                        for f in report.folds
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_fold_comparison failed", exc_info=True)
        return _make_error_response(str(exc))


def get_league_error_analysis(
    *, min_matches_per_league: int = 10, top_n: int = 3,
) -> dict:
    """Return per-league error analysis from backtest predictions.

    Groups backtest predictions by the ``league`` column and computes
    accuracy, Brier, RPS, LogLoss, and avg_confidence per league, plus
    the top-N worst predictions per league. Prefers Dixon-Coles decay
    predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"league_error_{min_matches_per_league}_{top_n}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_league_error_analysis,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif "league" not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        "Backtest predictions do not include a 'league' "
                        "column. Re-run backtest with league metadata."
                    ),
                }
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_league_error_analysis(
                    preds_df,
                    min_matches_per_league=min_matches_per_league,
                    top_n=top_n,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_leagues": report.n_leagues,
                    "n_total_matches": report.n_total_matches,
                    "overall_accuracy": report.overall_accuracy,
                    "overall_brier": report.overall_brier,
                    "disclaimer": report.disclaimer,
                    "leagues": [
                        {
                            "league": lg.league,
                            "n_matches": lg.n_matches,
                            "accuracy": lg.accuracy,
                            "brier": lg.brier,
                            "rps": lg.rps,
                            "log_loss": lg.log_loss,
                            "avg_confidence": lg.avg_confidence,
                            "worst_matches": [
                                {
                                    "match_id": m.match_id,
                                    "home_goals": m.home_goals,
                                    "away_goals": m.away_goals,
                                    "actual_outcome": m.actual_outcome,
                                    "predicted_home_win": m.predicted_home_win,
                                    "predicted_draw": m.predicted_draw,
                                    "predicted_away_win": m.predicted_away_win,
                                    "predicted_outcome": m.predicted_outcome,
                                    "confidence": m.confidence,
                                    "brier": m.brier,
                                    "log_loss": m.log_loss,
                                    "correct": m.correct,
                                }
                                for m in lg.worst_matches
                            ],
                        }
                        for lg in report.leagues
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_league_error_analysis failed", exc_info=True)
        return _make_error_response(str(exc))


def get_feature_importance(
    *, n_bins: int = 5, min_samples_per_bin: int = 10,
) -> dict:
    """Return feature importance ranking from backtest predictions.

    Ranks input feature columns by how strongly they separate prediction
    error (bin-wise Brier standard deviation). Prefers Dixon-Coles decay
    predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"feature_importance_{n_bins}_{min_samples_per_bin}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_feature_importance,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_feature_importance(
                    preds_df,
                    n_bins=n_bins,
                    min_samples_per_bin=min_samples_per_bin,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_features": report.n_features,
                    "n_total_matches": report.n_total_matches,
                    "overall_brier": report.overall_brier,
                    "disclaimer": report.disclaimer,
                    "features": [
                        {
                            "feature": fe.feature,
                            "importance": fe.importance,
                            "mean_value": fe.mean_value,
                            "std_value": fe.std_value,
                            "n_matches": fe.n_matches,
                            "bins": [
                                {
                                    "bin_label": b.bin_label,
                                    "bin_lower": b.bin_lower,
                                    "bin_upper": b.bin_upper,
                                    "n_matches": b.n_matches,
                                    "accuracy": b.accuracy,
                                    "brier": b.brier,
                                    "avg_confidence": b.avg_confidence,
                                }
                                for b in fe.bins
                            ],
                        }
                        for fe in report.features
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_feature_importance failed", exc_info=True)
        return _make_error_response(str(exc))


def get_ci_coverage(
    *,
    ci_lower_col: str = "home_win_ci_lower",
    ci_upper_col: str = "home_win_ci_upper",
    nominal_level: float | None = None,
    n_bins: int = 5,
    min_samples_per_bucket: int = 10,
) -> dict:
    """Return confidence band coverage analysis from backtest predictions.

    Validates whether bootstrap confidence intervals achieve their nominal
    coverage. Prefers Dixon-Coles decay predictions, falls back to Poisson.
    Cached for 5 minutes.
    """
    import time

    cache_key = (
        f"ci_coverage_{ci_lower_col}_{ci_upper_col}_{nominal_level}_"
        f"{n_bins}_{min_samples_per_bucket}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_ci_coverage

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif ci_lower_col not in preds_df.columns or ci_upper_col not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        f"Backtest predictions do not include CI columns "
                        f"'{ci_lower_col}'/'{ci_upper_col}'. Re-run backtest "
                        f"with bootstrap CI generation enabled."
                    ),
                }
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_ci_coverage(
                    preds_df,
                    ci_lower_col=ci_lower_col,
                    ci_upper_col=ci_upper_col,
                    nominal_level=nominal_level,
                    n_bins=n_bins,
                    min_samples_per_bucket=min_samples_per_bucket,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "overall_coverage": report.overall_coverage,
                    "avg_ci_width": report.avg_ci_width,
                    "n_matches": report.n_matches,
                    "nominal_level": report.nominal_level,
                    "coverage_assessment": report.coverage_assessment,
                    "disclaimer": report.disclaimer,
                    "buckets": [
                        {
                            "bucket_label": b.bucket_label,
                            "confidence_lower": b.confidence_lower,
                            "confidence_upper": b.confidence_upper,
                            "n_matches": b.n_matches,
                            "empirical_coverage": b.empirical_coverage,
                            "avg_ci_width": b.avg_ci_width,
                            "nominal_coverage": b.nominal_coverage,
                        }
                        for b in report.buckets
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_ci_coverage failed", exc_info=True)
        return _make_error_response(str(exc))


def get_calibration_drift_heatmap(
    *,
    window_size: str = "90D",
    n_confidence_bins: int = 4,
    min_samples_per_cell: int = 5,
) -> dict:
    """Return calibration drift heatmap from backtest predictions.

    Computes a 2D grid of accuracy/Brier/RPS/LogLoss over time windows ×
    confidence buckets. Prefers Dixon-Coles decay predictions, falls back
    to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = (
        f"drift_heatmap_{window_size}_{n_confidence_bins}_{min_samples_per_cell}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_calibration_drift_heatmap,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif "match_date" not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        "Backtest predictions do not include a 'match_date' "
                        "column. Re-run backtest with match date metadata."
                    ),
                }
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_calibration_drift_heatmap(
                    preds_df,
                    window_size=window_size,
                    n_confidence_bins=n_confidence_bins,
                    min_samples_per_cell=min_samples_per_cell,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_windows": report.n_windows,
                    "n_confidence_buckets": report.n_confidence_buckets,
                    "n_total_matches": report.n_total_matches,
                    "window_labels": report.window_labels,
                    "confidence_bucket_labels": report.confidence_bucket_labels,
                    "drift_detected": report.drift_detected,
                    "disclaimer": report.disclaimer,
                    "cells": [
                        {
                            "window_label": c.window_label,
                            "window_start": c.window_start,
                            "window_end": c.window_end,
                            "confidence_bucket": c.confidence_bucket,
                            "confidence_lower": c.confidence_lower,
                            "confidence_upper": c.confidence_upper,
                            "n_matches": c.n_matches,
                            "accuracy": c.accuracy,
                            "brier": c.brier,
                            "rps": c.rps,
                            "log_loss": c.log_loss,
                        }
                        for c in report.cells
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_calibration_drift_heatmap failed", exc_info=True)
        return _make_error_response(str(exc))


def get_error_clustering(
    *, n_clusters: int = 3, error_percentile: float = 0.1,
    min_samples_per_cluster: int = 5,
) -> dict:
    """Return prediction error clustering from backtest predictions.

    Clusters the worst predictions by feature signature using k-means.
    Prefers Dixon-Coles decay predictions, falls back to Poisson.
    Cached for 5 minutes.
    """
    import time

    cache_key = (
        f"error_clustering_{n_clusters}_{error_percentile}_"
        f"{min_samples_per_cluster}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_error_clustering,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_error_clustering(
                    preds_df,
                    n_clusters=n_clusters,
                    error_percentile=error_percentile,
                    min_samples_per_cluster=min_samples_per_cluster,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_clusters": report.n_clusters,
                    "n_total_matches": report.n_total_matches,
                    "n_features_used": report.n_features_used,
                    "error_percentile": report.error_percentile,
                    "n_worst_matches": report.n_worst_matches,
                    "overall_avg_brier": report.overall_avg_brier,
                    "disclaimer": report.disclaimer,
                    "clusters": [
                        {
                            "cluster_id": c.cluster_id,
                            "n_matches": c.n_matches,
                            "avg_brier": c.avg_brier,
                            "avg_confidence": c.avg_confidence,
                            "accuracy": c.accuracy,
                            "dominant_actual_outcome": c.dominant_actual_outcome,
                            "dominant_predicted_outcome": c.dominant_predicted_outcome,
                            "top_centroid_features": [
                                {
                                    "feature": f.feature,
                                    "centroid_value": f.centroid_value,
                                    "abs_centroid": f.abs_centroid,
                                }
                                for f in c.top_centroid_features
                            ],
                        }
                        for c in report.clusters
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_error_clustering failed", exc_info=True)
        return _make_error_response(str(exc))


def get_data_drift(
    *,
    split_ratio: float = 0.7,
    split_date: str | None = None,
    p_value_threshold: float = 0.05,
    min_samples: int = 20,
) -> dict:
    """Return data drift detection from backtest predictions.

    Detects feature distribution drift between train and holdout windows
    via two-sample Kolmogorov-Smirnov test. Prefers Dixon-Coles decay
    predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = (
        f"data_drift_{split_ratio}_{split_date}_"
        f"{p_value_threshold}_{min_samples}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_data_drift

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif "match_date" not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        "Backtest predictions do not include a 'match_date' "
                        "column. Re-run backtest with match date metadata."
                    ),
                }
            else:
                report = compute_data_drift(
                    preds_df,
                    split_ratio=split_ratio,
                    split_date=split_date,
                    p_value_threshold=p_value_threshold,
                    min_samples=min_samples,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_features": report.n_features,
                    "n_drifted": report.n_drifted,
                    "drift_ratio": report.drift_ratio,
                    "n_train": report.n_train,
                    "n_holdout": report.n_holdout,
                    "split_date": report.split_date,
                    "p_value_threshold": report.p_value_threshold,
                    "disclaimer": report.disclaimer,
                    "features": [
                        {
                            "feature": e.feature,
                            "ks_statistic": e.ks_statistic,
                            "p_value": e.p_value,
                            "drifted": e.drifted,
                            "train_mean": e.train_mean,
                            "holdout_mean": e.holdout_mean,
                            "mean_delta": e.mean_delta,
                            "train_std": e.train_std,
                            "holdout_std": e.holdout_std,
                        }
                        for e in report.features
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_data_drift failed", exc_info=True)
        return _make_error_response(str(exc))


def get_ci_width_analysis(
    *,
    ci_lower_col: str = "home_win_ci_lower",
    ci_upper_col: str = "home_win_ci_upper",
    n_bins: int = 5,
    min_samples_per_bucket: int = 10,
) -> dict:
    """Return CI width analysis from backtest predictions.

    Analyzes CI width distribution across confidence levels. Prefers
    Dixon-Coles decay predictions, falls back to Poisson. Cached for
    5 minutes.
    """
    import time

    cache_key = (
        f"ci_width_{ci_lower_col}_{ci_upper_col}_"
        f"{n_bins}_{min_samples_per_bucket}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_ci_width_analysis,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif ci_lower_col not in preds_df.columns or ci_upper_col not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        f"Backtest predictions do not include CI columns "
                        f"'{ci_lower_col}'/'{ci_upper_col}'. Re-run backtest "
                        f"with bootstrap CI generation enabled."
                    ),
                }
            else:
                report = compute_ci_width_analysis(
                    preds_df,
                    ci_lower_col=ci_lower_col,
                    ci_upper_col=ci_upper_col,
                    n_bins=n_bins,
                    min_samples_per_bucket=min_samples_per_bucket,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "overall_avg_ci_width": report.overall_avg_ci_width,
                    "overall_avg_confidence": report.overall_avg_confidence,
                    "width_confidence_correlation": report.width_confidence_correlation,
                    "widest_bucket": report.widest_bucket,
                    "narrowest_bucket": report.narrowest_bucket,
                    "assessment": report.assessment,
                    "disclaimer": report.disclaimer,
                    "buckets": [
                        {
                            "bucket_label": b.bucket_label,
                            "confidence_lower": b.confidence_lower,
                            "confidence_upper": b.confidence_upper,
                            "n_matches": b.n_matches,
                            "avg_ci_width": b.avg_ci_width,
                            "avg_ci_lower": b.avg_ci_lower,
                            "avg_ci_upper": b.avg_ci_upper,
                            "width_std": b.width_std,
                            "relative_width": b.relative_width,
                        }
                        for b in report.buckets
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_ci_width_analysis failed", exc_info=True)
        return _make_error_response(str(exc))


def get_scenario_stress_test(
    *,
    shift_type: str = "outcome_swap",
    shift_ratio: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Return scenario stress test from backtest predictions.

    Simulates distribution shifts and measures model degradation.
    Prefers Dixon-Coles decay predictions, falls back to Poisson.
    Cached for 5 minutes.
    """
    import time

    cache_key = f"stress_test_{shift_type}_{shift_ratio}_{random_state}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_scenario_stress_test,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                # Ensure actual_outcome column exists
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_scenario_stress_test(
                    preds_df,
                    shift_type=shift_type,
                    shift_ratio=shift_ratio,
                    random_state=random_state,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "shift_type": report.shift_type,
                    "shift_ratio": report.shift_ratio,
                    "baseline": {
                        "n_matches": report.baseline.n_matches,
                        "accuracy": report.baseline.accuracy,
                        "brier": report.baseline.brier,
                        "rps": report.baseline.rps,
                        "log_loss": report.baseline.log_loss,
                        "avg_confidence": report.baseline.avg_confidence,
                    },
                    "stressed": {
                        "n_matches": report.stressed.n_matches,
                        "accuracy": report.stressed.accuracy,
                        "brier": report.stressed.brier,
                        "rps": report.stressed.rps,
                        "log_loss": report.stressed.log_loss,
                        "avg_confidence": report.stressed.avg_confidence,
                    },
                    "accuracy_delta": report.accuracy_delta,
                    "brier_delta": report.brier_delta,
                    "rps_delta": report.rps_delta,
                    "log_loss_delta": report.log_loss_delta,
                    "confidence_delta": report.confidence_delta,
                    "degradation_score": report.degradation_score,
                    "assessment": report.assessment,
                    "n_shifted": report.n_shifted,
                    "disclaimer": report.disclaimer,
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_scenario_stress_test failed", exc_info=True)
        return _make_error_response(str(exc))


def get_team_calibration_drift(
    *,
    team_col: str = "home_team",
    team_name: str,
    window_size: str = "180D",
    min_samples_per_window: int = 5,
    n_windows: int | None = None,
) -> dict:
    """Return per-team calibration drift from backtest predictions.

    Filters predictions to a single team and computes per-window
    calibration drift. Prefers Dixon-Coles decay predictions, falls
    back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = (
        f"team_drift_{team_col}_{team_name}_{window_size}_"
        f"{min_samples_per_window}_{n_windows}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_team_calibration_drift,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif team_col not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        f"Backtest predictions do not include team column "
                        f"'{team_col}'."
                    ),
                }
            elif "match_date" not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        "Backtest predictions do not include 'match_date'."
                    ),
                }
            else:
                # Ensure actual_outcome column exists
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_team_calibration_drift(
                    preds_df,
                    team_col=team_col,
                    team_name=team_name,
                    window_size=window_size,
                    min_samples_per_window=min_samples_per_window,
                    n_windows=n_windows,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "team_col": report.team_col,
                    "team_name": report.team_name,
                    "n_total_matches": report.n_total_matches,
                    "n_windows": report.n_windows,
                    "drift_detected": report.drift_detected,
                    "latest_brier": report.latest_brier,
                    "historical_avg_brier": report.historical_avg_brier,
                    "relative_change": report.relative_change,
                    "trend": report.trend,
                    "disclaimer": report.disclaimer,
                    "points": [
                        {
                            "window_label": p.window_label,
                            "n_matches": p.n_matches,
                            "accuracy": p.accuracy,
                            "brier": p.brier,
                            "avg_confidence": p.avg_confidence,
                        }
                        for p in report.points
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_team_calibration_drift failed", exc_info=True)
        return _make_error_response(str(exc))


def get_prediction_uncertainty(
    *,
    max_points: int = 500,
) -> dict:
    """Return prediction uncertainty analysis from backtest predictions.

    Computes per-match Shannon entropy, margin, and dispersion.
    Prefers Dixon-Coles decay predictions, falls back to Poisson.
    Cached for 5 minutes.
    """
    import time

    cache_key = f"uncertainty_{max_points}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_prediction_uncertainty,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                # Ensure actual_outcome column exists
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_prediction_uncertainty(
                    preds_df,
                    max_points=max_points,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "avg_entropy": report.avg_entropy,
                    "avg_margin": report.avg_margin,
                    "avg_dispersion": report.avg_dispersion,
                    "high_uncertainty_count": report.high_uncertainty_count,
                    "high_uncertainty_accuracy": report.high_uncertainty_accuracy,
                    "low_uncertainty_accuracy": report.low_uncertainty_accuracy,
                    "entropy_accuracy_correlation": report.entropy_accuracy_correlation,
                    "disclaimer": report.disclaimer,
                    "points": [
                        {
                            "match_id": p.match_id,
                            "home_team": p.home_team,
                            "away_team": p.away_team,
                            "confidence": p.confidence,
                            "entropy": p.entropy,
                            "margin": p.margin,
                            "dispersion": p.dispersion,
                            "predicted_outcome": p.predicted_outcome,
                            "actual_outcome": p.actual_outcome,
                            "correct": p.correct,
                            "uncertainty_label": p.uncertainty_label,
                        }
                        for p in report.points
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_prediction_uncertainty failed", exc_info=True)
        return _make_error_response(str(exc))


def get_profit_loss_simulation(
    *,
    max_points: int = 500,
) -> dict:
    """Return profit/loss simulation from backtest predictions.

    Simulates flat-stake and Kelly betting on the model's predicted
    outcome using implied odds from model probabilities. Prefers
    Dixon-Coles decay predictions, falls back to Poisson. Cached for
    5 minutes.
    """
    import time

    cache_key = f"profit_loss_{max_points}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_profit_loss_simulation,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_profit_loss_simulation(
                    preds_df,
                    max_points=max_points,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "n_correct": report.n_correct,
                    "win_rate": report.win_rate,
                    "total_flat_stake": report.total_flat_stake,
                    "total_flat_profit": report.total_flat_profit,
                    "flat_roi": report.flat_roi,
                    "max_flat_drawdown": report.max_flat_drawdown,
                    "total_kelly_stake": report.total_kelly_stake,
                    "total_kelly_profit": report.total_kelly_profit,
                    "kelly_roi": report.kelly_roi,
                    "max_kelly_drawdown": report.max_kelly_drawdown,
                    "avg_confidence": report.avg_confidence,
                    "assessment": report.assessment,
                    "disclaimer": report.disclaimer,
                    "points": [
                        {
                            "match_index": p.match_index,
                            "predicted_outcome": p.predicted_outcome,
                            "actual_outcome": p.actual_outcome,
                            "correct": p.correct,
                            "model_probability": p.model_probability,
                            "implied_odds": p.implied_odds,
                            "flat_stake": p.flat_stake,
                            "flat_profit": p.flat_profit,
                            "cumulative_flat_profit": p.cumulative_flat_profit,
                            "kelly_fraction": p.kelly_fraction,
                            "kelly_stake": p.kelly_stake,
                            "kelly_profit": p.kelly_profit,
                            "cumulative_kelly_profit": p.cumulative_kelly_profit,
                        }
                        for p in report.points
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_profit_loss_simulation failed", exc_info=True)
        return _make_error_response(str(exc))


def get_cumulative_trajectory(
    *,
    rolling_window: int = 50,
    max_points: int = 500,
    change_threshold: float = 0.05,
) -> dict:
    """Return cumulative performance trajectory from backtest predictions.

    Tracks running accuracy, Brier, and profit over the backtest timeline.
    Prefers Dixon-Coles decay predictions, falls back to Poisson.
    Cached for 5 minutes.
    """
    import time

    cache_key = f"trajectory_{rolling_window}_{max_points}_{change_threshold}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_cumulative_trajectory,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_cumulative_trajectory(
                    preds_df,
                    rolling_window=rolling_window,
                    max_points=max_points,
                    change_threshold=change_threshold,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "final_accuracy": report.final_accuracy,
                    "final_brier": report.final_brier,
                    "final_profit": report.final_profit,
                    "trend": report.trend,
                    "best_window_accuracy": report.best_window_accuracy,
                    "worst_window_accuracy": report.worst_window_accuracy,
                    "n_change_points": report.n_change_points,
                    "disclaimer": report.disclaimer,
                    "points": [
                        {
                            "match_index": p.match_index,
                            "cumulative_accuracy": p.cumulative_accuracy,
                            "cumulative_brier": p.cumulative_brier,
                            "cumulative_profit": p.cumulative_profit,
                            "rolling_accuracy": p.rolling_accuracy,
                            "rolling_brier": p.rolling_brier,
                            "match_date": p.match_date,
                        }
                        for p in report.points
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_cumulative_trajectory failed", exc_info=True)
        return _make_error_response(str(exc))


def get_difficulty_stratification(
    *,
    easy_threshold: float = 0.6,
    hard_threshold: float = 0.4,
    n_bins: int = 5,
) -> dict:
    """Return match difficulty stratification from backtest predictions.

    Buckets predictions by difficulty (max predicted probability) and
    computes per-tier metrics. Prefers Dixon-Coles decay predictions,
    falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"difficulty_{easy_threshold}_{hard_threshold}_{n_bins}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_difficulty_stratification,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_difficulty_stratification(
                    preds_df,
                    easy_threshold=easy_threshold,
                    hard_threshold=hard_threshold,
                    n_bins=n_bins,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "overall_accuracy": report.overall_accuracy,
                    "overall_brier": report.overall_brier,
                    "best_tier": report.best_tier,
                    "worst_tier": report.worst_tier,
                    "disclaimer": report.disclaimer,
                    "tiers": [
                        {
                            "tier": t.tier,
                            "n_matches": t.n_matches,
                            "accuracy": t.accuracy,
                            "brier": t.brier,
                            "rps": t.rps,
                            "log_loss": t.log_loss,
                            "avg_confidence": t.avg_confidence,
                            "calibration_gap": t.calibration_gap,
                            "assessment": t.assessment,
                        }
                        for t in report.tiers
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_difficulty_stratification failed", exc_info=True)
        return _make_error_response(str(exc))


def get_prediction_streaks(
    *,
    high_confidence_threshold: float = 0.60,
    low_confidence_threshold: float = 0.40,
    max_points: int = 500,
) -> dict:
    """Return consecutive correct/wrong prediction streak analysis.

    Walks the backtest predictions timeline (sorted by ``match_date`` when
    available) and tracks current/longest streaks plus streak-break
    patterns: ``upset_breaks`` (high-confidence wrong ending a correct
    run), ``recovery_breaks`` (low-confidence correct ending a wrong
    run), and ``neutral_breaks``. Prefers Dixon-Coles decay predictions,
    falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = (
        f"streaks_{high_confidence_threshold}_"
        f"{low_confidence_threshold}_{max_points}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_prediction_streaks,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_prediction_streaks(
                    preds_df,
                    high_confidence_threshold=high_confidence_threshold,
                    low_confidence_threshold=low_confidence_threshold,
                    max_points=max_points,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "current_streak": report.current_streak,
                    "current_streak_type": report.current_streak_type,
                    "longest_correct_streak": report.longest_correct_streak,
                    "longest_wrong_streak": report.longest_wrong_streak,
                    "total_streak_breaks": report.total_streak_breaks,
                    "upset_breaks": report.upset_breaks,
                    "recovery_breaks": report.recovery_breaks,
                    "neutral_breaks": report.neutral_breaks,
                    "upset_rate": report.upset_rate,
                    "recovery_rate": report.recovery_rate,
                    "avg_correct_streak_length": report.avg_correct_streak_length,
                    "avg_wrong_streak_length": report.avg_wrong_streak_length,
                    "disclaimer": report.disclaimer,
                    "points": [
                        {
                            "match_index": p.match_index,
                            "streak_sign": p.streak_sign,
                            "streak_length": p.streak_length,
                            "confidence": p.confidence,
                            "predicted_outcome": p.predicted_outcome,
                            "actual_outcome": p.actual_outcome,
                            "correct": p.correct,
                            "streak_break_type": p.streak_break_type,
                            "match_id": p.match_id,
                            "home_team": p.home_team,
                            "away_team": p.away_team,
                            "match_date": p.match_date,
                        }
                        for p in report.points
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_prediction_streaks failed", exc_info=True)
        return _make_error_response(str(exc))


def get_prediction_diagnostics(home_team: str, away_team: str) -> dict:
    """Return an aggregated prediction diagnostics summary for a fixture.

    Combines calibration comparison highlights, drift status, and the top
    attribution factors into one response for quick model-trust assessment.
    """
    try:
        # Calibration comparison summary
        cal = get_calibration_comparison()
        cal_summary: dict[str, Any] = {"status": cal.get("status", "unknown")}
        if cal.get("status") == "ok":
            overall = cal.get("overall", {})
            improvement = cal.get("improvement", {})
            cal_summary = {
                "status": "ok",
                "n_matches": cal.get("n_matches", 0),
                "brier_raw": overall.get("brier_raw"),
                "brier_recalibrated": overall.get("brier_recalibrated"),
                "brier_improvement_pct": improvement.get("brier_improvement_pct"),
                "rps_raw": overall.get("rps_raw"),
                "rps_recalibrated": overall.get("rps_recalibrated"),
                "rps_improvement_pct": improvement.get("rps_improvement_pct"),
                "n_leagues": len(cal.get("by_league", [])),
            }

        # Drift status
        drift = get_calibration_drift()
        drift_summary: dict[str, Any] = {"status": drift.get("status", "unknown")}
        if drift.get("status") == "ok":
            drift_summary = {
                "status": "ok",
                "drift_detected": drift.get("drift_detected", False),
                "drift_metric": drift.get("drift_metric"),
                "threshold": drift.get("threshold"),
                "n_windows": drift.get("n_windows", 0),
                "latest_window": drift.get("latest_window"),
            }

        # Attribution top factors
        attr = get_prediction_attribution(home_team, away_team)
        attr_summary: dict[str, Any] = {"status": attr.get("status", "unknown")}
        if attr.get("status") == "ok":
            factors = attr.get("factors", [])
            attr_summary = {
                "status": "ok",
                "baseline_home_win": attr.get("baseline_home_win"),
                "top_factors": factors[:3] if factors else [],
                "n_factors": len(factors),
                "model_type": attr.get("model_type", "dixon_coles"),
            }

        # CI cache status
        ci_status: dict[str, Any] = {"available": False}
        try:
            ci_cache_key = f"{home_team}__{away_team}__dixon_coles"
            cached = _PREDICTION_CI_CACHE.get(ci_cache_key)
            if cached:
                ci_status = {
                    "available": True,
                    "age_seconds": int(__import__("time").time() - cached.get("timestamp", 0)),
                }
        except Exception:
            logger.warning("get_prediction_diagnostics: ci cache check failed", exc_info=True)
            pass

        return _clean_json_value({
            "status": "ok",
            "home_team": home_team,
            "away_team": away_team,
            "calibration": cal_summary,
            "drift": drift_summary,
            "attribution": attr_summary,
            "ci_cache": ci_status,
        })
    except Exception as exc:
        logger.warning("get_prediction_diagnostics failed", exc_info=True)
        return _make_error_response(str(exc))


def get_head_to_head(
    home_team: str, away_team: str, limit: int = 10, form_limit: int = 10
) -> dict:
    """Return head-to-head history, team form, and matchup summary.

    Wraps :func:`scoutfootball.head_to_head.get_head_to_head` with JSON-safe
    serialization and graceful error handling so the API never crashes.
    """
    empty_form_summary = {
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
        "points": 0,
        "streak": [],
    }
    empty_summary = {
        "total_meetings": 0,
        "home_wins": 0,
        "draws": 0,
        "away_wins": 0,
        "home_goals_avg": 0.0,
        "away_goals_avg": 0.0,
        "last_meeting_date": None,
    }
    fallback = {
        "home_team": home_team,
        "away_team": away_team,
        "head_to_head": [],
        "home_form": [],
        "home_form_summary": empty_form_summary,
        "away_form": [],
        "away_form_summary": {**empty_form_summary},
        "summary": empty_summary,
        "data_coverage": {
            "seasons_covered": [],
            "total_matches_scanned": 0,
            "source": "Football-Data",
        },
    }
    try:
        result = _compute_head_to_head(
            home_team, away_team, limit=limit, form_limit=form_limit
        )
        return _clean_json_value(result)
    except Exception:
        logger.warning("get_head_to_head failed, returning fallback", exc_info=True)
        return _clean_json_value(fallback)


def get_value_summary() -> dict:
    oof = load_oof_predictions()
    if oof.empty:
        return {"status": "no_data", "players": [], "metrics": {}}
    is_synthetic = (
        "is_synthetic" in oof.columns
        and bool(oof["is_synthetic"].fillna(False).all())
    )

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
            logger.warning("get_value_summary: results parquet read failed", exc_info=True)
            pass

    mean_residual = None
    if "residual_log" in oof.columns:
        try:
            raw = oof["residual_log"].mean()
            mean_residual = float(raw) if raw == raw else None
        except Exception:
            logger.warning("get_value_summary: residual_log mean failed", exc_info=True)
            mean_residual = None

    return _clean_json_value({
        "status": "demo" if is_synthetic else "ok",
        "data_mode": "synthetic" if is_synthetic else "artifact",
        # PRS-1 R-006: stamp the evidence grain so season-proxy OOF data
        # cannot be mistaken for match-level evidence in the UI/exports.
        "evidence_grain": _infer_evidence_grain(oof),
        "sample_count": len(oof),
        "fairness_distribution": oof["fairness_label"].value_counts().to_dict()
        if "fairness_label" in oof.columns
        else {},
        "mean_residual_log": mean_residual,
        "metrics": metrics,
        "players": player_data,
    })


# ── Market value (身价) service ────────────────────────────────────────
#
# 切片目标：把 Transfermarkt 身价数据接入 API，让维护者能在前端/CLI
# 直接查询球员的最新身价、历史身价序列，以及全库聚合统计。
#
# 数据源优先级（fail-closed，绝不编造数据）：
# 1. ``data/raw/transfermarkt_datasets/player_valuations.parquet``
#    — 通过 ``adapters.transfermarkt_datasets.export_table`` 或
#      ``load_csv_table`` 从 dcaribou/transfermarkt-datasets DuckDB 或
#      Kaggle CSV 导出的官方表（schema 见
#      ``adapters/transfermarkt_datasets.py``）。
# 2. ``data/raw/transfermarkt_manual/player_latest_market_value.csv``
#    + ``player_profiles.csv`` — 维护者手动放置的快照 CSV，schema
#    见 ``adapters/transfermarkt_manual.py``。这是当前磁盘上唯一真实
#    存在的数据路径。
#
# 所有响应必须携带：
# - ``source_name``：``"transfermarkt_datasets"`` 或 ``"transfermarkt_manual"``
# - ``source_uri``：实际读取的文件相对路径
# - ``license_boundary``：Transfermarkt ToS 边界（个人本地使用，不可再分发）
# - ``currency``：``"EUR"``（Transfermarkt 原始货币）
#
# 当两个数据源都不存在时返回 ``status="no_data"``，并附 ``evidence``
# 字段说明检查了哪些路径，让前端能诚实渲染空状态而非假装有数据。

_MARKET_VALUE_LICENSE_BOUNDARY = (
    "Personal local use only. Transfermarkt ToS prohibit scraping, "
    "redistribution, and commercial reuse without written permission. "
    "See docs/DATA_RIGHTS.md §2.1. Market values are subjective "
    "Transfermarkt estimates, not market prices."
)


def _load_market_value_frame() -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Load and normalize the market value frame from local raw data.

    Returns ``(frame, source_meta)`` where ``frame`` is None when no
    data source is available, and ``source_meta`` always carries
    ``source_name``, ``source_uri``, ``license_boundary``, ``currency``,
    and ``checked_paths`` so the API can render an honest empty state.

    Normalized columns:
        - ``player_id`` (str): source-native Transfermarkt numeric ID
        - ``player_name`` (str): from profiles join
        - ``team_name`` (str): current club name (may be empty)
        - ``position`` (str): source position label (may be empty)
        - ``snapshot_date`` (pd.Timestamp): valuation date
        - ``market_value_eur`` (float): market value in EUR
    """
    settings = _settings()
    checked: list[str] = []

    # Path 1: transfermarkt_datasets bulk export (player_valuations.parquet)
    tm_datasets_dir = settings.raw_root / "transfermarkt_datasets"
    valuations_path = tm_datasets_dir / "player_valuations.parquet"
    checked.append(str(valuations_path.relative_to(settings.data_root)))
    if valuations_path.exists():
        try:
            df = _read_parquet(valuations_path)
        except Exception:
            logger.warning(
                "market_value: player_valuations.parquet read failed",
                exc_info=True,
            )
            df = None
        if df is not None and not df.empty:
            normalized = _normalize_tm_datasets_valuations(df, tm_datasets_dir)
            if normalized is not None and not normalized.empty:
                return normalized, {
                    "source_name": "transfermarkt_datasets",
                    "source_uri": str(valuations_path.relative_to(settings.data_root)),
                    "license_boundary": _MARKET_VALUE_LICENSE_BOUNDARY,
                    "currency": "EUR",
                    "checked_paths": checked,
                }

    # Path 2: transfermarkt_manual raw CSVs (player_latest_market_value.csv
    # or player_market_value.csv) + player_profiles.csv
    tm_manual_dir = settings.raw_root / "transfermarkt_manual"
    profiles_path = tm_manual_dir / "player_profiles.csv"
    latest_path = tm_manual_dir / "player_latest_market_value.csv"
    history_path = tm_manual_dir / "player_market_value.csv"

    checked.append(str(latest_path.relative_to(settings.data_root)))
    checked.append(str(history_path.relative_to(settings.data_root)))
    checked.append(str(profiles_path.relative_to(settings.data_root)))

    mv_path = latest_path if latest_path.exists() else history_path
    if not mv_path.exists() or not profiles_path.exists():
        return None, {
            "source_name": "none",
            "source_uri": None,
            "license_boundary": _MARKET_VALUE_LICENSE_BOUNDARY,
            "currency": "EUR",
            "checked_paths": checked,
        }

    try:
        mv_df = pd.read_csv(mv_path)
        profiles_df = pd.read_csv(
            profiles_path,
            usecols=lambda c: c in {
                "player_id",
                "player_name",
                "current_club_name",
                "position",
                "main_position",
            },
        )
    except Exception:
        logger.warning(
            "market_value: transfermarkt_manual CSV read failed",
            exc_info=True,
        )
        return None, {
            "source_name": "none",
            "source_uri": None,
            "license_boundary": _MARKET_VALUE_LICENSE_BOUNDARY,
            "currency": "EUR",
            "checked_paths": checked,
        }

    merged = mv_df.merge(profiles_df, on="player_id", how="left")
    # Transfermarkt profiles append the numeric player_id to the display
    # name to disambiguate duplicates (e.g. "Lamine Yamal (937958)"). Strip
    # the trailing "(<id>)" suffix so API responses carry the bare name;
    # the canonical player_id remains in the dedicated ``player_id`` field.
    raw_names = merged["player_name"].astype("string").str.strip()
    raw_names = raw_names.str.replace(
        r"\s*\(\d+\)\s*$", "", regex=True
    ).str.strip()
    normalized = pd.DataFrame(
        {
            "player_id": merged["player_id"].astype("string"),
            "player_name": raw_names,
            "team_name": merged.get(
                "current_club_name", pd.Series(index=merged.index, dtype="object")
            ).astype("string").str.strip(),
            "position": merged.get(
                "position", pd.Series(index=merged.index, dtype="object")
            ).astype("string").str.strip(),
            "snapshot_date": pd.to_datetime(
                merged["date_unix"], errors="coerce"
            ),
            "market_value_eur": pd.to_numeric(
                merged["value"], errors="coerce"
            ).astype("float64"),
        }
    )
    # Drop rows with missing critical fields (player_name or market_value_eur).
    # A missing snapshot_date is kept (some latest-snapshot rows omit it) but
    # surfaced as NaT in the response.
    normalized = normalized.dropna(
        subset=["player_name", "market_value_eur"]
    ).reset_index(drop=True)

    return normalized, {
        "source_name": "transfermarkt_manual",
        "source_uri": str(mv_path.relative_to(settings.data_root)),
        "license_boundary": _MARKET_VALUE_LICENSE_BOUNDARY,
        "currency": "EUR",
        "checked_paths": checked,
    }


def _normalize_tm_datasets_valuations(
    df: pd.DataFrame, tm_datasets_dir: Path
) -> pd.DataFrame | None:
    """Normalize the player_valuations table from transfermarkt-datasets.

    The upstream schema (dcaribou/transfermarkt-datasets) columns:
        - ``player_id`` (int)
        - ``date`` (datetime)
        - ``market_value_in_eur`` (float)
        - ``player_club_id`` (int)
        - ``last_update`` (datetime)

    Player name / team name live in the sibling ``players`` / ``clubs``
    tables. When those parquet files are present we join them; otherwise
    we return the valuations with empty name columns rather than
    blocking the endpoint.
    """
    required = {"player_id", "date", "market_value_in_eur"}
    if not required.issubset(df.columns):
        return None

    players_path = tm_datasets_dir / "players.parquet"
    clubs_path = tm_datasets_dir / "clubs.parquet"

    out = pd.DataFrame(
        {
            "player_id": df["player_id"].astype("string"),
            "player_name": pd.Series(index=df.index, dtype="object"),
            "team_name": pd.Series(index=df.index, dtype="object"),
            "position": pd.Series(index=df.index, dtype="object"),
            "snapshot_date": pd.to_datetime(df["date"], errors="coerce"),
            "market_value_eur": pd.to_numeric(
                df["market_value_in_eur"], errors="coerce"
            ).astype("float64"),
        }
    )

    # Best-effort name/team enrichment. Failures here do not block the
    # endpoint — the valuations are still valid, just less readable.
    if players_path.exists():
        try:
            players_df = _read_parquet(players_path)
            if "player_id" in players_df.columns:
                name_cols = [
                    c
                    for c in ("name", "pretty_name", "player_name")
                    if c in players_df.columns
                ]
                pos_cols = [
                    c
                    for c in ("position", "main_position", "sub_type")
                    if c in players_df.columns
                ]
                cols = ["player_id"] + name_cols[:1] + pos_cols[:1]
                players_df = players_df[cols].copy()
                players_df["player_id"] = players_df["player_id"].astype("string")
                if name_cols:
                    players_df = players_df.rename(
                        columns={name_cols[0]: "player_name"}
                    )
                if pos_cols:
                    players_df = players_df.rename(
                        columns={pos_cols[0]: "position"}
                    )
                out = out.merge(
                    players_df, on="player_id", how="left", suffixes=("", "_p")
                )
                if "player_name_p" in out.columns:
                    out["player_name"] = out["player_name"].fillna(
                        out["player_name_p"]
                    )
                    out = out.drop(columns=["player_name_p"])
                if "position_p" in out.columns:
                    out["position"] = out["position"].fillna(out["position_p"])
                    out = out.drop(columns=["position_p"])
        except Exception:
            logger.warning(
                "market_value: players.parquet enrichment failed",
                exc_info=True,
            )

    if clubs_path.exists() and "player_club_id" in df.columns:
        try:
            clubs_df = _read_parquet(clubs_path)
            name_cols = [
                c
                for c in ("name", "pretty_name", "club_name")
                if c in clubs_df.columns
            ]
            if "club_id" in clubs_df.columns and name_cols:
                clubs_df = clubs_df[["club_id", name_cols[0]]].copy()
                clubs_df = clubs_df.rename(
                    columns={name_cols[0]: "team_name", "club_id": "player_club_id"}
                )
                clubs_df["player_club_id"] = clubs_df[
                    "player_club_id"
                ].astype("string")
                df_join = df.copy()
                df_join["player_club_id"] = df_join[
                    "player_club_id"
                ].astype("string")
                out["team_name"] = df_join.merge(
                    clubs_df, on="player_club_id", how="left"
                )["team_name"].astype("string").str.strip().values
        except Exception:
            logger.warning(
                "market_value: clubs.parquet enrichment failed",
                exc_info=True,
            )

    out["player_name"] = out["player_name"].astype("string").str.strip()
    out["team_name"] = out["team_name"].astype("string").str.strip()
    out["position"] = out["position"].astype("string").str.strip()

    # Drop rows with no usable identity or value.
    out = out.dropna(subset=["market_value_eur"])
    out = out[out["market_value_eur"] > 0].reset_index(drop=True)
    return out


def get_market_value_summary() -> dict:
    """Return aggregate market value stats with source attribution.

    Reads the local raw Transfermarkt data and reports:
    - ``total_players``: distinct players with at least one valuation
    - ``total_snapshots``: total valuation rows
    - ``latest_snapshot_date``: most recent valuation date across all players
    - ``value_distribution``: count of players in each EUR band
    - ``top_players``: top 10 players by latest market value
    - ``source``: source_name, source_uri, license_boundary, currency

    Fail-closed: when no data is available, returns ``status="no_data"``
    with the checked paths so the maintainer can see what's missing
    rather than guessing.
    """
    df, source_meta = _load_market_value_frame()
    if df is None or df.empty:
        return {
            "status": "no_data",
            "source": source_meta,
            "evidence": {
                "reason": (
                    "No Transfermarkt market value data found locally. "
                    "Run `python scripts/download_transfermarkt_kaggle.py` "
                    "or place CSVs in data/raw/transfermarkt_manual/."
                ),
            },
        }

    df = df.dropna(subset=["market_value_eur"])
    df = df[df["market_value_eur"] > 0]

    if df.empty:
        return {
            "status": "no_data",
            "source": source_meta,
            "evidence": {"reason": "All rows have non-positive market_value_eur"},
        }

    # Latest snapshot per player for distribution + top players.
    latest_per_player = df.sort_values("snapshot_date").drop_duplicates(
        subset=["player_id"], keep="last"
    )

    bands = [
        (0, 1_000_000, "<1m"),
        (1_000_000, 5_000_000, "1m-5m"),
        (5_000_000, 20_000_000, "5m-20m"),
        (20_000_000, 50_000_000, "20m-50m"),
        (50_000_000, float("inf"), ">=50m"),
    ]
    distribution: dict[str, int] = {}
    for low, high, label in bands:
        mask = (latest_per_player["market_value_eur"] >= low) & (
            latest_per_player["market_value_eur"] < high
        )
        distribution[label] = int(mask.sum())

    top = latest_per_player.nlargest(10, "market_value_eur")
    top_records = []
    for _, row in top.iterrows():
        top_records.append(
            {
                "player_name": row.get("player_name") or None,
                "player_id": row.get("player_id"),
                "team_name": row.get("team_name") or None,
                "position": row.get("position") or None,
                "market_value_eur": float(row["market_value_eur"]),
                "snapshot_date": (
                    row["snapshot_date"].strftime("%Y-%m-%d")
                    if pd.notna(row["snapshot_date"])
                    else None
                ),
            }
        )

    latest_date = df["snapshot_date"].max()
    earliest_date = df["snapshot_date"].min()

    return _clean_json_value(
        {
            "status": "ok",
            "source": source_meta,
            "total_players": int(latest_per_player["player_id"].nunique()),
            "total_snapshots": int(len(df)),
            "latest_snapshot_date": (
                latest_date.strftime("%Y-%m-%d") if pd.notna(latest_date) else None
            ),
            "earliest_snapshot_date": (
                earliest_date.strftime("%Y-%m-%d") if pd.notna(earliest_date) else None
            ),
            "value_distribution_eur": distribution,
            "top_players": top_records,
        }
    )


def list_market_value_players(
    *,
    limit: int = 100,
    offset: int = 0,
    min_value_eur: float | None = None,
    max_value_eur: float | None = None,
    team: str | None = None,
    position: str | None = None,
    sort_by: str = "market_value_eur",
    sort_order: str = "desc",
) -> dict:
    """List players with their latest market value (paginated).

    Returns one row per player (the latest snapshot). Filters:
    - ``min_value_eur`` / ``max_value_eur``: inclusive range
    - ``team``: case-insensitive substring match on team_name
    - ``position``: case-insensitive substring match on position
    - ``sort_by``: ``"market_value_eur"`` (default) or ``"player_name"`` or
      ``"snapshot_date"``
    - ``sort_order``: ``"desc"`` (default) or ``"asc"``

    ``limit`` is capped at 1000 to protect against unbounded payloads.
    """
    if limit < 1 or limit > 1000:
        limit = max(1, min(1000, limit))
    if offset < 0:
        offset = 0

    df, source_meta = _load_market_value_frame()
    if df is None or df.empty:
        return {
            "status": "no_data",
            "source": source_meta,
            "count": 0,
            "players": [],
            "evidence": {"reason": "No Transfermarkt market value data found locally"},
        }

    df = df.dropna(subset=["market_value_eur"])
    df = df[df["market_value_eur"] > 0]

    if min_value_eur is not None:
        df = df[df["market_value_eur"] >= float(min_value_eur)]
    if max_value_eur is not None:
        df = df[df["market_value_eur"] <= float(max_value_eur)]
    if team:
        team_lower = team.lower()
        df = df[df["team_name"].fillna("").str.lower().str.contains(team_lower)]
    if position:
        pos_lower = position.lower()
        df = df[df["position"].fillna("").str.lower().str.contains(pos_lower)]

    if df.empty:
        return _clean_json_value(
            {
                "status": "ok",
                "source": source_meta,
                "count": 0,
                "players": [],
                "filters_applied": {
                    "min_value_eur": min_value_eur,
                    "max_value_eur": max_value_eur,
                    "team": team,
                    "position": position,
                },
            }
        )

    # Latest snapshot per player.
    latest = df.sort_values("snapshot_date").drop_duplicates(
        subset=["player_id"], keep="last"
    )

    valid_sort_by = {"market_value_eur", "player_name", "snapshot_date"}
    if sort_by not in valid_sort_by:
        sort_by = "market_value_eur"
    ascending = sort_order.lower() != "desc"
    latest = latest.sort_values(by=sort_by, ascending=ascending, na_position="last")

    total = len(latest)
    page = latest.iloc[offset : offset + limit]

    players = []
    for _, row in page.iterrows():
        players.append(
            {
                "player_id": row.get("player_id"),
                "player_name": row.get("player_name") or None,
                "team_name": row.get("team_name") or None,
                "position": row.get("position") or None,
                "market_value_eur": float(row["market_value_eur"]),
                "snapshot_date": (
                    row["snapshot_date"].strftime("%Y-%m-%d")
                    if pd.notna(row["snapshot_date"])
                    else None
                ),
            }
        )

    return _clean_json_value(
        {
            "status": "ok",
            "source": source_meta,
            "count": total,
            "returned": len(players),
            "offset": offset,
            "limit": limit,
            "players": players,
            "filters_applied": {
                "min_value_eur": min_value_eur,
                "max_value_eur": max_value_eur,
                "team": team,
                "position": position,
            },
            "sort": {"by": sort_by, "order": sort_order},
        }
    )


def get_player_market_value_history(player_name: str) -> dict:
    """Return the full market value history for a single player.

    ``player_name`` is matched case-insensitively against the
    ``player_name`` column. When multiple players match (e.g. common
    names), all matching histories are returned grouped by player_id so
    the caller can disambiguate.
    """
    if not player_name or not player_name.strip():
        return _make_error_response(
            "invalid_player_name",
            message="player_name must be a non-empty string",
        )

    df, source_meta = _load_market_value_frame()
    if df is None or df.empty:
        return {
            "status": "no_data",
            "source": source_meta,
            "player_name": player_name,
            "histories": [],
            "evidence": {"reason": "No Transfermarkt market value data found locally"},
        }

    target = player_name.strip().lower()
    matches = df[df["player_name"].fillna("").str.lower() == target]
    if matches.empty:
        # Fall back to substring match for friendlier UX.
        matches = df[df["player_name"].fillna("").str.lower().str.contains(target)]

    if matches.empty:
        return _clean_json_value(
            {
                "status": "not_found",
                "source": source_meta,
                "player_name": player_name,
                "histories": [],
                "evidence": {
                    "reason": (
                        f"No market value records found for player '{player_name}'"
                    ),
                },
            }
        )

    histories: list[dict[str, Any]] = []
    for player_id, group in matches.groupby("player_id", sort=False):
        group = group.sort_values("snapshot_date")
        snapshots = []
        for _, row in group.iterrows():
            snapshots.append(
                {
                    "snapshot_date": (
                        row["snapshot_date"].strftime("%Y-%m-%d")
                        if pd.notna(row["snapshot_date"])
                        else None
                    ),
                    "market_value_eur": float(row["market_value_eur"]),
                    "team_name": row.get("team_name") or None,
                }
            )
        first_row = group.iloc[0]
        histories.append(
            {
                "player_id": player_id,
                "player_name": first_row.get("player_name") or None,
                "position": first_row.get("position") or None,
                "team_name": first_row.get("team_name") or None,
                "snapshot_count": int(len(snapshots)),
                "first_snapshot_date": snapshots[0]["snapshot_date"] if snapshots else None,
                "latest_snapshot_date": snapshots[-1]["snapshot_date"] if snapshots else None,
                "latest_market_value_eur": (
                    snapshots[-1]["market_value_eur"] if snapshots else None
                ),
                "snapshots": snapshots,
            }
        )

    return _clean_json_value(
        {
            "status": "ok",
            "source": source_meta,
            "player_name": player_name,
            "matched_players": len(histories),
            "histories": histories,
        }
    )


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
        return {"count": 0, "players": [], "data_mode": "empty"}

    canonical_resolution = "unavailable"
    if {
        "player",
        "season",
    }.issubset(df.columns) and "canonical_player_id" not in df.columns:
        try:
            df = load_resolved_player_ratings(settings=_settings(), ratings_df=df)
            canonical_resolution = "ok"
        except Exception as exc:  # noqa: BLE001 — ratings remain read-only
            logger.warning("Canonical ratings resolution unavailable: %s", exc)
            df = df.copy()
            df["canonical_player_id"] = "unresolved:unknown:missing"
            df["canonical_match_ambiguous"] = False

    # PRS-0 R-003: stamp synthetic fallback in the response so consumers
    # cannot mistake demo data for a real rating artifact. The data is still
    # served (so the UI does not break) but is clearly labeled.
    synthetic = frame_is_synthetic(df)

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
    return _clean_json_value({
        "count": len(players),
        "players": players,
        "data_mode": "synthetic" if synthetic else "artifact",
        "canonical_resolution": canonical_resolution,
        # PRS-1 R-006: stamp the evidence grain so season-proxy ratings
        # cannot be mistaken for match-level evidence in the UI/exports.
        "evidence_grain": _infer_evidence_grain(df),
    })


def get_ratings_meta() -> dict:
    """Return model metadata, league metrics, and rating-source disclosure."""
    meta_df = load_model_meta()
    league_df = load_league_metrics()

    meta = {}
    if not meta_df.empty:
        meta = meta_df.iloc[0].to_dict()

    leagues = league_df.to_dict(orient="records") if not league_df.empty else []

    # The active table is a legacy optimizer artifact. Expose the nearest
    # recorded run and manifest comparison without mutating or silently
    # promoting it to a reviewed rating. The frontend uses this disclosure to
    # avoid presenting a proxy objective as independently validated ability.
    settings = _settings()
    latest_run_meta: dict[str, Any] = {}
    runs_dir = settings.data_root / "models" / "runs"
    if runs_dir.exists():
        for run_dir in sorted(
            (path for path in runs_dir.iterdir() if path.is_dir()),
            key=lambda path: path.name,
            reverse=True,
        ):
            candidate = _read_json(run_dir / "meta.json")
            if candidate:
                latest_run_meta = {**candidate, "run_id": run_dir.name}
                break

    current_manifest = _read_json(
        settings.data_root / "gold" / "feature_store" / "rating_feature_matrix_manifest.json"
    )
    training_manifest_hash = (
        latest_run_meta.get("lineage", {})
        .get("feature_manifest", {})
        .get("hash")
    )
    current_manifest_hash = current_manifest.get("hash")
    rating_source = {
        "kind": "optimizer_proxy_objective",
        "label": "优化器代理目标产物（非独立验证的球员能力）",
        "latest_run_id": latest_run_meta.get("run_id"),
        "training_objective": (
            "球队积分代理目标：Spearman/NDCG、积分回归、分布/校准与联赛偏差惩罚"
        ),
        "training_manifest_hash": training_manifest_hash,
        "current_manifest_hash": current_manifest_hash,
        "manifest_match": (
            training_manifest_hash is not None
            and current_manifest_hash is not None
            and training_manifest_hash == current_manifest_hash
        ),
        "research_health_endpoint": "/health/research",
        "limitations": [
            "该评分优化球队积分代理目标，不等同于独立监督的球员能力真值。",
            "research_health=not_ready 时，主界面不得把它作为强排名结论。",
        ],
    }

    return _clean_json_value({
        "model_meta": meta,
        "league_metrics": leagues,
        "rating_source": rating_source,
    })


# ── Position group mapping for team strength aggregation ──────────
_POS_GROUP_MAP: dict[str, str] = {
    "GK": "GK",
    "CB": "DEF", "FB": "DEF", "LB": "DEF", "RB": "DEF", "RWB": "DEF", "LWB": "DEF",
    "DM": "MID", "CM": "MID", "AM": "MID", "CDM": "MID", "CAM": "MID", "LM": "MID", "RM": "MID",
    "W": "ATT", "ST": "ATT", "CF": "ATT", "RW": "ATT", "LW": "ATT", "WF": "ATT",
}


def _broad_position(pos: str | None) -> str:
    """Map a granular position to GK/DEF/MID/ATT."""
    if not pos:
        return "UNK"
    key = str(pos).strip().upper()
    return _POS_GROUP_MAP.get(key, "UNK")


def get_team_strength(
    league: str | None = None,
    season: str | None = None,
    limit: int = 100,
) -> dict:
    """Aggregate player ratings to team-level strength metrics.

    Returns overall team rating, position-group breakdowns, top players,
    squad depth and average confidence for each team.
    """
    df = load_player_ratings(league=league, season=season)
    if df.empty:
        return {"count": 0, "teams": [], "data_mode": "empty"}

    # PRS-0 R-003: stamp synthetic fallback so consumers cannot mistake demo
    # data for a real team-strength artifact.
    synthetic = frame_is_synthetic(df)

    # Resolve column aliases
    team_col = "team" if "team" in df.columns else (
        "team_name" if "team_name" in df.columns else None
    )
    score_col = "optimized_score" if "optimized_score" in df.columns else (
        "rating" if "rating" in df.columns else None
    )
    pos_col = "position_group" if "position_group" in df.columns else (
        "sub_position" if "sub_position" in df.columns else None
    )
    minutes_col = "minutes" if "minutes" in df.columns else None
    name_col = "player_name" if "player_name" in df.columns else (
        "player" if "player" in df.columns else None
    )
    league_col = "league" if "league" in df.columns else None
    season_col = "season" if "season" in df.columns else None
    conf_col = "confidence_level" if "confidence_level" in df.columns else None

    if team_col is None or score_col is None:
        return {"count": 0, "teams": []}

    # Filter out rows with no team or score
    df = df[df[team_col].notna() & df[score_col].notna()].copy()
    # Exclude comma-joined club histories (transferred players)
    df = df[~df[team_col].astype(str).str.contains(",", na=False)]
    # Normalize team name
    df[team_col] = df[team_col].astype(str).str.strip()
    df = df[df[team_col] != ""]

    if df.empty:
        return {"count": 0, "teams": []}

    # Add broad position group
    if pos_col:
        df["broad_pos"] = df[pos_col].map(_broad_position)
    else:
        df["broad_pos"] = "UNK"

    # Ensure numeric score
    df[score_col] = pd.to_numeric(df[score_col], errors="coerce").fillna(0.0)
    if minutes_col:
        df[minutes_col] = pd.to_numeric(df[minutes_col], errors="coerce").fillna(0.0)
    else:
        df["minutes"] = 0.0
        minutes_col = "minutes"

    teams: list[dict[str, Any]] = []

    for team_name, group in df.groupby(team_col):
        # Minutes-weighted overall rating
        total_minutes = group[minutes_col].sum()
        if total_minutes > 0:
            overall = float((group[score_col] * group[minutes_col]).sum() / total_minutes)
        else:
            overall = float(group[score_col].mean())

        # Position group breakdown
        pos_breakdown: dict[str, dict[str, Any]] = {}
        for bpos, pg in group.groupby("broad_pos"):
            pg_minutes = pg[minutes_col].sum()
            if pg_minutes > 0:
                pg_rating = float((pg[score_col] * pg[minutes_col]).sum() / pg_minutes)
            else:
                pg_rating = float(pg[score_col].mean())
            pos_breakdown[bpos] = {
                "rating": round(pg_rating, 2),
                "player_count": int(len(pg)),
                "avg_minutes": round(float(pg[minutes_col].mean()), 0) if len(pg) > 0 else 0,
            }

        # Top players by score (with minutes weighting)
        top_players_df = group.nlargest(5, score_col)
        top_players = []
        for _, row in top_players_df.iterrows():
            top_players.append({
                "name": str(row.get(name_col, "")) if name_col else "",
                "position": str(row.get(pos_col, "")) if pos_col else "",
                "broad_pos": str(row.get("broad_pos", "")),
                "rating": round(float(row[score_col]), 1),
                "minutes": int(row.get(minutes_col, 0)) if minutes_col else 0,
                "confidence": str(row.get(conf_col, "LOW")).upper() if conf_col else "LOW",
            })

        # Average confidence
        if conf_col and conf_col in group.columns:
            conf_counts = group[conf_col].astype(str).str.upper().value_counts().to_dict()
        else:
            conf_counts = {}

        team_entry = {
            "team": team_name,
            "league": str(group[league_col].iloc[0])
            if league_col and league_col in group.columns else "",
            "season": str(group[season_col].iloc[0])
            if season_col and season_col in group.columns else "",
            "overall_rating": round(overall, 2),
            "squad_size": int(len(group)),
            "total_minutes": int(total_minutes),
            "position_groups": pos_breakdown,
            "top_players": top_players,
            "confidence_distribution": conf_counts,
        }
        teams.append(team_entry)

    # Sort by overall rating descending
    teams.sort(key=lambda t: t["overall_rating"], reverse=True)

    # Apply limit
    teams = teams[:limit]

    return _clean_json_value({
        "count": len(teams),
        "teams": teams,
        "data_mode": "synthetic" if synthetic else "artifact",
    })


def get_team_comparison(team_a: str, team_b: str) -> dict:
    """Compare two teams side-by-side using team strength data.

    Returns position group diffs, top player comparison and squad metrics.
    """
    # Normalize team names for matching
    strength = get_team_strength(limit=500)
    all_teams = strength.get("teams", [])

    # Find teams by name (case-insensitive partial match)
    def _find(name):
        name_lower = name.lower().strip()
        for t in all_teams:
            if t["team"].lower() == name_lower:
                return t
        for t in all_teams:
            if name_lower in t["team"].lower():
                return t
        return None

    a = _find(team_a)
    b = _find(team_b)

    if not a:
        return _make_error_response(f"Team '{team_a}' not found")
    if not b:
        return _make_error_response(f"Team '{team_b}' not found")

    # Position group comparison
    pos_groups = ["GK", "DEF", "MID", "ATT"]
    pos_comparison = []
    for pg in pos_groups:
        pg_a = (a.get("position_groups") or {}).get(pg)
        pg_b = (b.get("position_groups") or {}).get(pg)
        rating_a = pg_a["rating"] if pg_a else None
        rating_b = pg_b["rating"] if pg_b else None
        diff = None
        advantage = "tie"
        if rating_a is not None and rating_b is not None:
            diff = round(rating_a - rating_b, 2)
            advantage = "a" if rating_a > rating_b else ("b" if rating_b > rating_a else "tie")
        pos_comparison.append({
            "group": pg,
            "rating_a": rating_a,
            "rating_b": rating_b,
            "diff": diff,
            "advantage": advantage,
            "players_a": pg_a["player_count"] if pg_a else 0,
            "players_b": pg_b["player_count"] if pg_b else 0,
        })

    # Top players side-by-side (top 5 each)
    top_a = a.get("top_players", [])
    top_b = b.get("top_players", [])
    max_top = max(len(top_a), len(top_b))
    top_comparison = []
    for i in range(max_top):
        pa = top_a[i] if i < len(top_a) else None
        pb = top_b[i] if i < len(top_b) else None
        top_comparison.append({
            "player_a": pa,
            "player_b": pb,
        })

    # Overall metrics comparison
    overall_a = a.get("overall_rating", 0)
    overall_b = b.get("overall_rating", 0)
    overall_diff = round(overall_a - overall_b, 2)

    # Depth dimension: normalize squad_size to 0-100 scale relative to both teams
    squad_a = a.get("squad_size", 0)
    squad_b = b.get("squad_size", 0)
    max_squad = max(squad_a, squad_b, 1)
    depth_a = round(float(squad_a) / max_squad * 100, 1)
    depth_b = round(float(squad_b) / max_squad * 100, 1)

    return _clean_json_value({
        "team_a": {
            "name": a["team"],
            "league": a.get("league", ""),
            "overall_rating": overall_a,
            "squad_size": a.get("squad_size", 0),
            "total_minutes": a.get("total_minutes", 0),
            "confidence_distribution": a.get("confidence_distribution", {}),
        },
        "team_b": {
            "name": b["team"],
            "league": b.get("league", ""),
            "overall_rating": overall_b,
            "squad_size": b.get("squad_size", 0),
            "total_minutes": b.get("total_minutes", 0),
            "confidence_distribution": b.get("confidence_distribution", {}),
        },
        "overall_diff": overall_diff,
        "overall_advantage": "a" if overall_diff > 0 else ("b" if overall_diff < 0 else "tie"),
        "position_group_comparison": pos_comparison,
        "top_players_comparison": top_comparison,
        "radar_labels": ["GK", "DEF", "MID", "ATT", "Overall", "Depth"],
        "radar_a": [
            (a.get("position_groups") or {}).get("GK", {}).get("rating", 0),
            (a.get("position_groups") or {}).get("DEF", {}).get("rating", 0),
            (a.get("position_groups") or {}).get("MID", {}).get("rating", 0),
            (a.get("position_groups") or {}).get("ATT", {}).get("rating", 0),
            overall_a,
            depth_a,
        ],
        "radar_b": [
            (b.get("position_groups") or {}).get("GK", {}).get("rating", 0),
            (b.get("position_groups") or {}).get("DEF", {}).get("rating", 0),
            (b.get("position_groups") or {}).get("MID", {}).get("rating", 0),
            (b.get("position_groups") or {}).get("ATT", {}).get("rating", 0),
            overall_b,
            depth_b,
        ],
    })


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
            logger.warning("get_prediction_summary: poisson read failed", exc_info=True)
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
            logger.warning("get_prediction_summary: DC read failed", exc_info=True)
            dc_info["status"] = "error"

    poisson_ready = poisson_info.get("status") == "ok"
    dc_ready = dc_info.get("status") == "ok"
    preferred = dc_info if dc_ready else poisson_info

    return _clean_json_value({
        "status": "ok" if (poisson_ready or dc_ready) else "no_data",
        "model_type": preferred.get("model_type", "independent_poisson"),
        "num_teams": preferred.get("num_teams"),
        "train_rows": poisson_info.get("train_rows"),
        "coverage": poisson_info.get("coverage"),
        "poisson": poisson_info,
        "dixon_coles": dc_info,
        "available_models": (
            (["poisson"] if poisson_ready else [])
            + (["dixon_coles"] if dc_ready else [])
        ),
    })


_calibration_cache: dict[str, Any] = {"data": None, "timestamp": 0.0}
_CALIBRATION_TTL_SECONDS = 300  # 5 minutes


def get_prediction_calibration(force_refresh: bool = False) -> dict[str, Any]:
    """Return calibration metrics for match prediction models.

    Compares Poisson vs Dixon-Coles side by side.
    Includes low-score breakdown (0-0, 1-0, 0-1, 1-1) and league coverage.

    Results are cached for 5 minutes to avoid repeated parquet reads.
    Pass force_refresh=True to bypass the cache (e.g. after model retraining).
    """
    import time

    now = time.time()
    if (
        not force_refresh
        and _calibration_cache["data"] is not None
        and now - _calibration_cache["timestamp"] < _CALIBRATION_TTL_SECONDS
    ):
        return _calibration_cache["data"]
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
            logger.warning("get_prediction_calibration: DC detail failed", exc_info=True)
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
            logger.warning("get_prediction_calibration: poisson results failed", exc_info=True)
            poisson_metrics = {"status": "error"}

    result = _clean_json_value({
        "dixon_coles": dc_metrics,
        "poisson": poisson_metrics,
        "low_score_breakdown": dc_low_score,
        "calibration_plot": dc_calibration_plot,
        "league_coverage": dc_league_coverage,
    })
    _calibration_cache["data"] = result
    _calibration_cache["timestamp"] = time.time()
    return result


_BACKTEST_CACHE: dict[str, Any] = {"data": None, "timestamp": 0.0}
_BACKTEST_TTL_SECONDS = 300


def get_backtest_comparison(force_refresh: bool = False) -> dict[str, Any]:
    """Return a side-by-side comparison of Poisson vs Dixon-Coles backtests.

    Reads the metrics JSON files produced by ``scoutfootball backtest`` from
    ``data/reports/calibration_backtest/``. Returns a structured comparison
    including overall metrics (log_loss_exact, brier_1x2, rps_1x2), per-fold
    metrics, and a winner per metric. If no backtest artifacts exist, returns
    a status of ``not_available`` with instructions on how to generate them.

    Results are cached for 5 minutes.
    """
    import time

    now = time.time()
    if (
        not force_refresh
        and _BACKTEST_CACHE["data"] is not None
        and now - _BACKTEST_CACHE["timestamp"] < _BACKTEST_TTL_SECONDS
    ):
        return _BACKTEST_CACHE["data"]

    settings = _settings()
    bt_dir = settings.report_root / "calibration_backtest"

    models: list[dict[str, Any]] = []
    metric_files = [
        ("independent_poisson", "poisson_backtest_metrics.json"),
        ("dixon_coles", "dixon_coles_backtest_metrics.json"),
        ("dixon_coles_decay", "dixon_coles_decay_backtest_metrics.json"),
    ]

    available = False
    for model_key, filename in metric_files:
        path = bt_dir / filename
        if not path.exists():
            continue
        try:
            data = _read_json(path)
        except Exception:
            logger.warning("get_backtest_comparison: metric file read failed", exc_info=True)
            continue
        available = True
        overall = data.get("overall", {}) or {}
        folds = data.get("folds", []) or []
        models.append({
            "model": model_key,
            "label": data.get("model", model_key),
            "decay": data.get("decay"),
            "n_splits": data.get("n_splits"),
            "total_predictions": data.get("total_predictions"),
            "overall": {
                "log_loss_exact": overall.get("log_loss_exact"),
                "brier_1x2": overall.get("brier_1x2"),
                "rps_1x2": overall.get("rps_1x2"),
            },
            "folds": [
                {
                    "fold": f.get("fold"),
                    "train_start": str(f.get("train_start", "")),
                    "train_end": str(f.get("train_end", "")),
                    "test_start": str(f.get("test_start", "")),
                    "test_end": str(f.get("test_end", "")),
                    "train_matches": f.get("train_matches"),
                    "test_matches": f.get("test_matches"),
                    "log_loss_exact": f.get("log_loss_exact"),
                    "brier_1x2": f.get("brier_1x2"),
                    "rps_1x2": f.get("rps_1x2"),
                }
                for f in folds
            ],
        })

    # Calibration report (isotonic) if present
    cal_path = bt_dir / "dc_calibration_report.json"
    calibration: dict[str, Any] = {"status": "not_available"}
    if cal_path.exists():
        try:
            cal_data = _read_json(cal_path)
            calibration = {
                "status": "ok",
                "method": cal_data.get("method"),
                "decay": cal_data.get("decay"),
                "brier_before": cal_data.get("brier_before"),
                "brier_after": cal_data.get("brier_after"),
                "rps_before": cal_data.get("rps_before"),
                "rps_after": cal_data.get("rps_after"),
                "n_matches": cal_data.get("n_matches"),
            }
        except Exception:
            logger.warning("get_backtest_comparison: calibration data read failed", exc_info=True)
            pass

    if not available:
        result = {
            "status": "not_available",
            "backtest_dir": str(bt_dir).replace("\\", "/"),
            "models": [],
            "metric_comparison": [],
            "folds": [],
            "calibration": calibration,
            "instructions": (
                "Run `PYTHONPATH=src uv run python -m scoutfootball backtest` "
                "to generate backtest artifacts."
            ),
        }
    else:
        # Build metric comparison table — pick winner (lower is better)
        metric_keys = ["log_loss_exact", "brier_1x2", "rps_1x2"]
        metric_comparison: list[dict[str, Any]] = []
        for mk in metric_keys:
            row: dict[str, Any] = {"metric": mk}
            values: list[tuple[str, float]] = []
            for m in models:
                v = m["overall"].get(mk)
                row[m["model"]] = v
                if v is not None:
                    values.append((m["model"], float(v)))
            if values:
                winner = min(values, key=lambda x: x[1])[0]
                row["winner"] = winner
            else:
                row["winner"] = None
            metric_comparison.append(row)

        # Collect all fold timelines (union of folds across models)
        max_folds = max((len(m["folds"]) for m in models), default=0)
        folds_table: list[dict[str, Any]] = []
        for i in range(max_folds):
            row: dict[str, Any] = {"fold": i + 1}
            for m in models:
                prefix = m["model"]
                if i < len(m["folds"]):
                    f = m["folds"][i]
                    row[f"{prefix}_test_matches"] = f.get("test_matches")
                    row[f"{prefix}_log_loss"] = f.get("log_loss_exact")
                    row[f"{prefix}_brier"] = f.get("brier_1x2")
                    row[f"{prefix}_rps"] = f.get("rps_1x2")
                else:
                    row[f"{prefix}_test_matches"] = None
                    row[f"{prefix}_log_loss"] = None
                    row[f"{prefix}_brier"] = None
                    row[f"{prefix}_rps"] = None
            folds_table.append(row)

        result = _clean_json_value({
            "status": "ok",
            "backtest_dir": str(bt_dir).replace("\\", "/"),
            "models": models,
            "metric_comparison": metric_comparison,
            "folds": folds_table,
            "calibration": calibration,
        })

    _BACKTEST_CACHE["data"] = result
    _BACKTEST_CACHE["timestamp"] = time.time()
    return result


def get_decay_tuning(force_refresh: bool = False) -> dict[str, Any]:
    """Return Dixon-Coles decay tuning results.

    Reads ``data/reports/calibration_backtest/decay_tuning_results.json``
    produced by ``scoutfootball tune-predictions``. Returns the best decay,
    selection metric, and per-candidate comparison table. If no tuning
    artifacts exist, returns a ``not_available`` status with instructions.

    Results are cached for 5 minutes.
    """
    import time

    now = time.time()
    if (
        not force_refresh
        and _BACKTEST_CACHE.get("tuning_data") is not None
        and now - _BACKTEST_CACHE.get("tuning_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return _BACKTEST_CACHE["tuning_data"]

    settings = _settings()
    tuning_path = settings.report_root / "calibration_backtest" / "decay_tuning_results.json"

    if not tuning_path.exists():
        result = {
            "status": "not_available",
            "tuning_path": str(tuning_path).replace("\\", "/"),
            "instructions": (
                "Run `PYTHONPATH=src uv run python -m scoutfootball tune-predictions` "
                "to generate decay tuning results."
            ),
        }
    else:
        try:
            data = _read_json(tuning_path)
            result = _clean_json_value({
                "status": "ok",
                "tuning_path": str(tuning_path).replace("\\", "/"),
                "best_decay": data.get("best_decay"),
                "selection_metric": data.get("selection_metric"),
                "n_folds": data.get("n_folds"),
                "n_matches": data.get("n_matches"),
                "candidates": data.get("candidates", []),
            })
        except Exception as exc:
            logger.warning("get_decay_tuning failed", exc_info=True)
            result = {
                **_make_error_response(str(exc)),
                "tuning_path": str(tuning_path).replace("\\", "/"),
            }

    _BACKTEST_CACHE["tuning_data"] = result
    _BACKTEST_CACHE["tuning_timestamp"] = time.time()
    return result


def get_action_value_summary(
    limit: int = 20,
    offset: int = 0,
    full: bool = False,
) -> dict[str, Any]:
    """Return independently paged xT and VAEP action-value rows.

    xT is a player-team-season artifact.  VAEP is currently a player-team
    career aggregate and receives display identity plus season *context* from
    the xT artifact.  The two models are kept in separate arrays because
    joining them on a display name would blur those different granularities.

    ``full`` is retained for backwards compatibility with the static exporter;
    ``limit`` and ``offset`` apply independently to each model section.
    """
    import pandas as pd

    from scoutfootball.action_value.identity import (
        attach_team_names,
        build_identity_coverage_report,
        enrich_vaep_identities,
    )

    del full  # Compatibility flag; callers still control row count with limit.
    limit = max(0, min(int(limit), 20_000))
    offset = max(0, int(offset))
    settings = _settings()
    xt_path = settings.data_root / "gold" / "feature_store" / "player_action_value.parquet"
    vaep_path = settings.data_root / "gold" / "feature_store" / "player_vaep.parquet"
    matches_path = settings.raw_root / "statsbomb_open" / "matches_all.parquet"

    # Load xT data
    xt_df = pd.DataFrame()
    if xt_path.exists():
        try:
            xt_df = _read_parquet(xt_path)
        except Exception:
            logger.warning("get_action_value_summary: xT load failed", exc_info=True)
            pass

    # Load VAEP data
    vaep_df = pd.DataFrame()
    if vaep_path.exists():
        try:
            vaep_df = _read_parquet(vaep_path)
        except Exception:
            logger.warning("get_action_value_summary: VAEP load failed", exc_info=True)
            pass

    matches_df = pd.DataFrame()
    if matches_path.exists():
        try:
            matches_df = _read_parquet(matches_path)
        except Exception:
            logger.warning("get_action_value_summary: matches load failed", exc_info=True)
            pass

    if xt_df.empty and vaep_df.empty:
        # Fallback to legacy player_value_metrics
        frame = load_player_value_metrics()
        if frame.empty:
            return _clean_json_value({
            "status": "no_data", "count": 0, "players": [],
            "attribution_required": _STATSBOMB_ATTRIBUTION,
        })

        working = frame.copy()
        if "composite_score" in working.columns:
            working = working.sort_values("composite_score", ascending=False)

        return _clean_json_value({
            "status": "ok",
            "count": len(working),
            "data_source": "StatsBomb Open Data + xT/VAEP model",
            "attribution_required": _STATSBOMB_ATTRIBUTION,
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

    xt_part = attach_team_names(xt_df, matches_df)
    vaep_part = enrich_vaep_identities(vaep_df, xt_df, matches_df)
    if "xt_per_90" in xt_part.columns:
        xt_part = xt_part.sort_values("xt_per_90", ascending=False)
    if "vaep_per_90" in vaep_part.columns:
        vaep_part = vaep_part.sort_values("vaep_per_90", ascending=False)

    total_count = len(xt_part) + len(vaep_part)
    xt_page = xt_part.iloc[offset : offset + limit]
    vaep_page = vaep_part.iloc[offset : offset + limit]
    metrics: dict[str, Any] = {
        "total_rows": total_count,
        "xt_rows": len(xt_part),
        "vaep_rows": len(vaep_part),
    }
    if "xt_per_90" in xt_part.columns and xt_part["xt_per_90"].notna().any():
        metrics["mean_xt_per_90"] = round(float(xt_part["xt_per_90"].dropna().mean()), 4)
        metrics["players_with_xt"] = int(xt_part["xt_per_90"].notna().sum())
    if "vaep_per_90" in vaep_part.columns and vaep_part["vaep_per_90"].notna().any():
        metrics["mean_vaep_per_90"] = round(
            float(vaep_part["vaep_per_90"].dropna().mean()), 4
        )
        metrics["players_with_vaep"] = int(vaep_part["vaep_per_90"].notna().sum())

    return _clean_json_value({
        "status": "ok",
        "count": total_count,
        "offset": offset,
        "limit": limit,
        "data_source": "StatsBomb Open Data + xT/VAEP model",
        "attribution_required": _STATSBOMB_ATTRIBUTION,
        "model_granularity": {
            "xt": "player_team_season",
            "vaep": "player_team_career",
        },
        "metrics": metrics,
        "identity_coverage": build_identity_coverage_report(vaep_part),
        "players": xt_page.to_dict(orient="records"),
        "xt_players": xt_page.to_dict(orient="records"),
        "vaep_players": vaep_page.to_dict(orient="records"),
    })


def get_action_value_evidence_index() -> dict[str, Any]:
    """Return the players and coverage available in the match evidence sample."""
    return _clean_json_value(_get_action_value_evidence_index())


def get_action_value_evidence(player_id: str) -> dict[str, Any]:
    """Return match, action-type, zone and time evidence for one player."""
    return _clean_json_value(_get_action_value_evidence(player_id))


def get_action_value_player_context(player_id: str) -> dict[str, Any]:
    """Return a non-additive xT/VAEP/match-evidence dossier for one player."""
    import pandas as pd

    from scoutfootball.action_value.context import build_player_action_value_context
    from scoutfootball.action_value.identity import attach_team_names, enrich_vaep_identities

    settings = _settings()
    feature_root = settings.data_root / "gold" / "feature_store"

    def read(name: str) -> pd.DataFrame:
        path = feature_root / name
        if not path.exists():
            return pd.DataFrame()
        try:
            return _read_parquet(path)
        except Exception:
            logger.warning("get_action_value_player_context: read failed", exc_info=True)
            return pd.DataFrame()

    xt = read("player_action_value.parquet")
    vaep = read("player_vaep.parquet")
    sample = read("player_match_action_value_sample.parquet")
    matches_path = settings.raw_root / "statsbomb_open" / "matches_all.parquet"
    try:
        matches = _read_parquet(matches_path) if matches_path.exists() else pd.DataFrame()
    except Exception:
        logger.warning("get_action_value_player_context: matches load failed", exc_info=True)
        matches = pd.DataFrame()
    return _clean_json_value(
        build_player_action_value_context(
            player_id,
            attach_team_names(xt, matches),
            enrich_vaep_identities(vaep, xt, matches),
            sample,
        )
    )


def get_action_value_rating_links(player_id: str) -> dict[str, Any]:
    """Return conservative, human-verifiable rating candidates for an action player."""
    import pandas as pd

    from scoutfootball.action_value.identity import attach_team_names
    from scoutfootball.action_value.rating_links import build_action_value_rating_links

    settings = _settings()
    xt_path = settings.data_root / "gold" / "feature_store" / "player_action_value.parquet"
    matches_path = settings.raw_root / "statsbomb_open" / "matches_all.parquet"
    try:
        xt = pd.read_parquet(xt_path) if xt_path.exists() else pd.DataFrame()
    except Exception:
        logger.warning("get_action_value_rating_links: xT load failed", exc_info=True)
        xt = pd.DataFrame()
    try:
        matches = pd.read_parquet(matches_path) if matches_path.exists() else pd.DataFrame()
    except Exception:
        logger.warning("get_action_value_rating_links: matches load failed", exc_info=True)
        matches = pd.DataFrame()
    try:
        ratings = load_player_ratings()
    except Exception:
        logger.warning("get_action_value_rating_links: ratings load failed", exc_info=True)
        ratings = pd.DataFrame()
    return _clean_json_value(
        build_action_value_rating_links(player_id, attach_team_names(xt, matches), ratings)
    )


def get_player_match_action_values(limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read the generated, sample-bounded player-match xT artifact."""
    import json

    limit, offset = max(0, min(int(limit), 2_000)), max(0, int(offset))
    path = (
        _settings().data_root
        / "gold"
        / "feature_store"
        / "player_match_action_value_sample.parquet"
    )
    manifest_path = path.with_suffix(".manifest.json")
    if not path.exists() or not manifest_path.exists():
        return _clean_json_value(
            {
                "status": "not_generated",
                "rows": [],
                "count": 0,
                "build_command": "scoutfootball action-value-matches",
                "coverage_scope": "sample",
                "attribution_required": _STATSBOMB_ATTRIBUTION,
            }
        )
    try:
        frame = _read_parquet(path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("get_player_match_action_values failed", exc_info=True)
        return _clean_json_value(
            {"status": "error", "rows": [], "count": 0, "error": str(exc)}
        )
    if frame.empty:
        return _clean_json_value(
            {"status": "no_data", "rows": [], "count": 0, "manifest": manifest}
        )
    frame = frame.sort_values("xt_total", ascending=False)
    return _clean_json_value(
        {
            "status": "ok",
            "count": len(frame),
            "offset": offset,
            "limit": limit,
            "rows": frame.iloc[offset : offset + limit].to_dict(orient="records"),
            "manifest": manifest,
            "attribution_required": _STATSBOMB_ATTRIBUTION,
        }
    )


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
            logger.warning("get_artifacts_summary: events count failed", exc_info=True)
            events_count = 0

    # Data health flags. Demo fallback rows keep the UI usable, but must never
    # be presented as a real trained artifact.
    oof_path = settings.data_root / "models" / "oof_predictions" / "value_fairness_oof.parquet"
    oof_is_synthetic = (
        "is_synthetic" in oof.columns
        and bool(oof["is_synthetic"].fillna(False).all())
    )
    has_oof = oof_path.exists() and not oof.empty and not oof_is_synthetic
    oof_rows = len(oof) if has_oof else 0
    has_truth = False
    truth_rows = 0
    truth_path = settings.data_root / "gold" / "feature_store" / "player_truth_labels.parquet"
    if truth_path.exists():
        try:

            truth_df = _read_parquet(truth_path)
            has_truth = len(truth_df) > 0
            truth_rows = len(truth_df)
        except Exception:
            logger.warning("get_artifacts_summary: truth labels read failed", exc_info=True)
            pass

    # Player match coverage
    pm_coverage = ""
    if not player_match.empty and "data_granularity" in player_match.columns:
        match_count = (player_match["data_granularity"] == "match").sum()
        proxy_count = (player_match["data_granularity"] == "season_proxy").sum()
        source_counts = (
            player_match["source_name"].fillna("unknown").value_counts().sort_index().to_dict()
            if "source_name" in player_match.columns
            else {}
        )
        source_summary = ", ".join(
            f"{source}={int(count)}" for source, count in source_counts.items()
        )
        pm_coverage = (
            f"{match_count} real + {proxy_count} season proxy"
            + (f" ({source_summary})" if source_summary else "")
        )

    artifact_registry = [
        _artifact_file_info(
            settings.data_root / "gold" / "feature_store" / "player_match.parquet",
            "player_match",
            rows=len(player_match),
            display_root=settings.project_root,
        ),
        _artifact_file_info(
            settings.data_root / "gold" / "feature_store" / "team_match.parquet",
            "team_match",
            rows=len(team_match),
            display_root=settings.project_root,
        ),
        _artifact_file_info(
            settings.data_root / "gold" / "feature_store" / "player_ratings_optimized.parquet",
            "player_ratings_optimized",
            rows=len(ratings),
            display_root=settings.project_root,
        ),
        _artifact_file_info(
            events_path,
            "events_all",
            rows=events_count,
            display_root=settings.project_root,
        ),
        _artifact_file_info(
            oof_path,
            "value_fairness_oof",
            rows=oof_rows,
            display_root=settings.project_root,
        ),
        _artifact_file_info(
            truth_path,
            "player_truth_labels",
            rows=truth_rows,
            display_root=settings.project_root,
        ),
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
            "clubelo": "ClubElo — public data, attribution appreciated",
            "transfermarkt": "Transfermarkt — manual import only, no automated scraping",
        },
    })


def get_truth_label_supervision() -> dict:
    """Report source-policy eligibility for rating supervision labels.

    The endpoint is deliberately diagnostic: a source-policy eligible label is
    not automatically presented as independent proof of player impact.
    """
    from scoutfootball.evaluation.truth_labels import truth_label_supervision_report

    path = _settings().gold_root / "feature_store" / "player_truth_labels.parquet"
    if not path.exists():
        return {
            "schema": "scoutfootball.truth-label-supervision",
            "version": "1.0.0",
            "status": "no_data",
            "path": path.name,
            "report": truth_label_supervision_report(pd.DataFrame()),
        }
    try:
        labels = _read_parquet(path)
    except Exception as exc:
        logger.warning("Unable to read truth labels for supervision report: %s", exc, exc_info=True)
        return {
            "schema": "scoutfootball.truth-label-supervision",
            "version": "1.0.0",
            "status": "unavailable",
            "path": path.name,
            "report": truth_label_supervision_report(pd.DataFrame()),
        }
    report = truth_label_supervision_report(labels)
    return _clean_json_value(
        {
            "schema": "scoutfootball.truth-label-supervision",
            "version": "1.0.0",
            "status": report["status"],
            "path": path.name,
            "report": report,
        },
    )


def get_transfermarkt_identity_report() -> dict:
    """Return the latest local Transfermarkt identity resolution audit."""
    path = _settings().gold_root / "feature_store" / "transfermarkt_identity_report.json"
    if not path.exists():
        return {
            "schema": "scoutfootball.transfermarkt-identity-report",
            "version": "1.0.0",
            "status": "no_data",
            "path": path.name,
            "report": {},
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Unable to read Transfermarkt identity report: %s", exc)
        return {
            "schema": "scoutfootball.transfermarkt-identity-report",
            "version": "1.0.0",
            "status": "unavailable",
            "path": path.name,
            "report": {},
        }
    if not isinstance(payload, dict):
        return {
            "schema": "scoutfootball.transfermarkt-identity-report",
            "version": "1.0.0",
            "status": "unavailable",
            "path": path.name,
            "report": {},
        }
    return _clean_json_value(
        {
            "schema": "scoutfootball.transfermarkt-identity-report",
            "version": "1.0.0",
            "status": "available",
            "path": path.name,
            "report": payload,
        },
    )


def _get_scouting_queues(force_refresh: bool = False):
    """Build and cache scouting queues to avoid redundant computation.

    Each of get_review_queue / get_watchlist / get_shortlist previously
    called build_scouting_queues independently on the full ratings
    DataFrame.  This helper computes the queues once per process and
    reuses the result for all three endpoints.

    Pass ``force_refresh=True`` to bypass the cache (e.g. after model retraining).
    """
    cached = _wc_cache.get(_WC_SCOUTING_KEY)
    if cached is _MISSING or force_refresh:
        df = load_player_ratings(force_refresh=force_refresh)
        if df.empty:
            from scoutfootball.evaluation.scouting_queue import ScoutingQueues
            queues = ScoutingQueues(
                review_queue=df, watchlist=df, shortlist=df,
            )
        else:
            queues = build_scouting_queues(
                df,
                run_id=_latest_run_id(),
                reports_root=_settings().data_root / "reports",
            )
        _wc_cache.set(_WC_SCOUTING_KEY, queues)
    return _wc_cache.get(_WC_SCOUTING_KEY)


def get_review_queue(limit: int = 200) -> dict:
    """Return low-confidence players from ratings data as a review queue."""
    df = load_player_ratings()
    if df.empty:
        return {"count": 0, "players": []}

    queues = _get_scouting_queues()
    return _queue_payload(queues.review_queue, limit=limit)


def get_watchlist(limit: int = 100) -> dict:
    df = load_player_ratings()
    if df.empty:
        return {"count": 0, "players": []}
    queues = _get_scouting_queues()
    return _queue_payload(queues.watchlist, limit=limit)


def get_shortlist(limit: int = 100) -> dict:
    df = load_player_ratings()
    if df.empty:
        return {"count": 0, "players": []}
    queues = _get_scouting_queues()
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


def _model_run_lineage(meta: dict[str, Any]) -> dict[str, Any]:
    """Return explicit lineage status for current and legacy model-run metadata."""
    lineage = meta.get("lineage")
    if isinstance(lineage, dict):
        return lineage
    return {
        "schema": "scoutfootball.model-run-lineage",
        "version": "1.0.0",
        "status": "not_recorded",
        "dataset_snapshot": {"input_hash": meta.get("input_hash")},
        "feature_manifest": {"hash": None, "schema_version": None},
        "note": "This legacy run predates feature-manifest lineage capture.",
    }


def _model_run_admission(
    run_dir: Path, settings: PlatformSettings | None = None
) -> dict[str, Any]:
    """Expose a compact, read-only admission summary for one local run.

    Forwards *settings* to evaluate_optimizer_run so the recorded_lineage
    chain-of-custody check compares meta.json.lineage.feature_manifest.hash
    against the current on-disk rating_feature_matrix_manifest.json. When
    *settings* is None the function falls back to PlatformSettings.from_root
    so the API endpoints behave consistently with the CLI model-admission.
    """
    from scoutfootball.evaluation.model_admission import evaluate_optimizer_run

    resolved = settings if settings is not None else _settings()
    report = evaluate_optimizer_run(run_dir, settings=resolved)
    return {
        "status": report["status"],
        "failed_checks": report.get("failed_checks", []),
        "comparison": report.get("comparison"),
        "limitations": report.get("limitations", []),
    }


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
                meta["lineage"] = _model_run_lineage(meta)
                meta["admission"] = _model_run_admission(run_dir, settings=settings)
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
            meta["lineage"] = _model_run_lineage(meta)
            meta["admission"] = {
                "status": "not_available",
                "failed_checks": ["run_directory"],
                "comparison": None,
                "limitations": [
                    "The fallback parameter metadata has no model-run directory to review."
                ],
            }
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
            meta["lineage"] = _model_run_lineage(meta)
            meta["admission"] = _model_run_admission(run_dir, settings=settings)

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
                    logger.warning(
                        "get_model_run_detail: feature importance read failed", exc_info=True
                    )
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
                    logger.warning(
                        "get_model_run_detail: optimized params load failed", exc_info=True
                    )
                    pass

            # Data source attribution
            meta["data_attribution"] = {
                "primary_source": ds_label,
                "license_note": (
                    "Player ratings derived from FBref/Understat data. "
                    "Match results from Football-Data.co.uk. "
                    "Event data from StatsBomb Open Data."
                ),
                "statsbomb_attribution_required": _STATSBOMB_ATTRIBUTION,
            }

            return _clean_json_value(meta)

    # Fallback: check optimized_params_meta.json
    meta_path = settings.data_root / "gold" / "feature_store" / "optimized_params_meta.json"
    if meta_path.exists() and run_id in ("latest", "latest-local"):
        meta = _read_json(meta_path)
        meta["run_id"] = "latest"
        meta["updated_at"] = meta_path.stat().st_mtime
        meta["data_source"] = ds_label
        meta["lineage"] = _model_run_lineage(meta)
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
            "statsbomb_attribution_required": _STATSBOMB_ATTRIBUTION,
        }
        return _clean_json_value(meta)

    return {**_make_error_response(f"Run '{run_id}' not found"), "available_runs": _get_run_ids()}


def _player_list_to_csv(player_list: list[dict]) -> str:
    """Convert a list of player dicts to CSV text.

    All cells are sanitized through :func:`sanitize_csv_row` to guard
    against spreadsheet formula injection (AGENTS.md requirement).
    """
    import csv
    import io

    if not player_list:
        return ""
    buf = io.StringIO()
    fieldnames = list(player_list[0].keys())
    writer = csv.writer(buf)
    writer.writerow(sanitize_csv_row(fieldnames))
    for row in player_list:
        writer.writerow(sanitize_csv_row(row.get(f, "") for f in fieldnames))
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
    canonical_player_id: str | None = None,
) -> dict:
    """Return detailed player profile with radar dimensions.

    Supports fuzzy name matching, pagination, position/season filters,
    rating snapshot history, xT integration, confidence explanation,
    and CSV export.
    """
    import pandas as pd

    df = load_player_ratings()

    # Canonical identity is optional for backward-compatible name routes, but
    # when supplied it becomes the primary detail selector. This keeps the
    # UI from silently switching to a same-name row after entity aggregation.
    if canonical_player_id and {
        "player",
        "season",
    }.issubset(df.columns) and "canonical_player_id" not in df.columns:
        try:
            df = load_resolved_player_ratings(
                settings=_settings(),
                ratings_df=df,
            )
            canonical_mask = (
                df["canonical_player_id"].astype(str) == canonical_player_id
            )
            df = df[canonical_mask].reset_index(drop=True)
        except Exception as exc:  # noqa: BLE001 — keep legacy name fallback
            logger.warning("Canonical profile resolution unavailable: %s", exc)

    # PRS-0 R-003: refuse to export synthetic fallback as real research CSV.
    # Check at the top so the maintainer gets an immediate, clear error
    # instead of waiting for the full profile build to fail or — worse —
    # silently exporting demo data as a real artifact. The JSON path still
    # serves synthetic data (clearly labeled) so the UI does not break.
    if fmt == "csv" and frame_is_synthetic(df):
        return _make_error_response(
            "synthetic_data_refused",
            message=(
                "Cannot export CSV: player ratings are synthetic fallback, "
                "not a real artifact. Run `scoutfootball build-features` "
                "and `scoutfootball train` to produce real ratings."
            ),
        )

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
            "data_mode": "synthetic" if frame_is_synthetic(df) else "artifact",
            # PRS-1 R-006: stamp the evidence grain so season-proxy ratings
            # cannot be mistaken for match-level evidence in the UI/exports.
            "evidence_grain": _infer_evidence_grain(df),
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
        logger.warning("get_player_profile: xT integration failed", exc_info=True)
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
        "canonical_player_id": row.get("canonical_player_id"),
        "canonical_match_ambiguous": bool(row.get("canonical_match_ambiguous", False)),
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
        "data_mode": "synthetic" if frame_is_synthetic(df) else "artifact",
        # PRS-1 R-006: stamp the evidence grain so season-proxy ratings
        # cannot be mistaken for match-level evidence in the UI/exports.
        "evidence_grain": _infer_evidence_grain(df),
    })

    # Embed career intelligence blocks. Each block is wrapped in a
    # defensive try/except so a failure in one helper never breaks the
    # base profile response (frontend degrades to "unavailable").
    try:
        from scoutfootball.player_intel import compute_career_trajectory
        result["career_trajectory"] = _clean_json_value(
            compute_career_trajectory(rows)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_player_profile: career_trajectory failed", exc_info=True)
        result["career_trajectory"] = {
            "available": False,
            "error": str(exc),
        }

    try:
        from scoutfootball.player_intel import compute_role_fit_scores
        result["role_fit"] = _clean_json_value(
            compute_role_fit_scores(row, df)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_player_profile: role_fit failed", exc_info=True)
        result["role_fit"] = {"available": False, "error": str(exc)}

    try:
        from scoutfootball.player_intel import compute_peer_benchmark
        result["peer_benchmark"] = _clean_json_value(
            compute_peer_benchmark(row, df)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_player_profile: peer_benchmark failed", exc_info=True)
        result["peer_benchmark"] = {"available": False, "error": str(exc)}

    # CSV export
    if fmt == "csv":
        return _player_list_to_csv([result])
    return result


# ── Player comparison ────────────────────────────────────────────────────

_RADAR_LABELS = ["Attack", "Possession", "Defense", "Reliability", "Impact"]


def get_player_comparison(player_a: str, player_b: str) -> dict:
    """Compare two players side-by-side with radar overlay and metric diffs.

    Calls get_player_profile for both players, then builds a unified
    comparison structure with per-dimension deltas.
    """
    profile_a = get_player_profile(player_a)
    profile_b = get_player_profile(player_b)

    if not profile_a.get("found"):
        return {**_make_error_response(f"Player '{player_a}' not found"), "found_a": False}
    if not profile_b.get("found"):
        return {**_make_error_response(f"Player '{player_b}' not found"), "found_b": False}

    # Build radar comparison
    radar_a = profile_a.get("radar", [0, 0, 0, 0, 0])
    radar_b = profile_b.get("radar", [0, 0, 0, 0, 0])
    # Pad to 5 elements if needed
    while len(radar_a) < 5:
        radar_a.append(0)
    while len(radar_b) < 5:
        radar_b.append(0)

    radar_comparison = []
    for i, label in enumerate(_RADAR_LABELS):
        val_a = float(radar_a[i]) if i < len(radar_a) else 0.0
        val_b = float(radar_b[i]) if i < len(radar_b) else 0.0
        radar_comparison.append({
            "dimension": label,
            "player_a": round(val_a, 1),
            "player_b": round(val_b, 1),
            "diff": round(val_a - val_b, 1),
            "advantage": "a" if val_a > val_b else ("b" if val_b > val_a else "tie"),
        })

    # Position percentiles comparison
    # position_percentiles is a dict: {dim_key: {label, percentile}}
    pp_a = profile_a.get("position_percentiles", {})
    pp_b = profile_b.get("position_percentiles", {})

    # Merge dimension keys from both (dict keys, preserving order)
    all_dims = list(dict.fromkeys(
        list(pp_a.keys()) + list(pp_b.keys())
    ))

    pct_comparison = []
    for dim in all_dims:
        entry_a = pp_a.get(dim, {})
        entry_b = pp_b.get(dim, {})
        val_a = entry_a.get("percentile") if isinstance(entry_a, dict) else None
        val_b = entry_b.get("percentile") if isinstance(entry_b, dict) else None
        label = entry_a.get("label") or entry_b.get("label") or dim
        diff = None
        advantage = "tie"
        if val_a is not None and val_b is not None:
            diff = round(float(val_a) - float(val_b), 1)
            advantage = "a" if val_a > val_b else ("b" if val_b > val_a else "tie")
        pct_comparison.append({
            "dimension": dim,
            "label": label,
            "player_a": val_a,
            "player_b": val_b,
            "diff": diff,
            "advantage": advantage,
        })

    # Key stats comparison
    stats_fields = [
        "optimized_score", "minutes", "matches", "npg_p90",
        "assists_p90", "defense_composite", "possession_composite",
    ]
    stats_comparison = []
    for field in stats_fields:
        val_a = profile_a.get(field)
        val_b = profile_b.get(field)
        diff = None
        if val_a is not None and val_b is not None:
            try:
                diff = round(float(val_a) - float(val_b), 2)
            except (ValueError, TypeError):
                pass
        stats_comparison.append({
            "metric": field,
            "player_a": val_a,
            "player_b": val_b,
            "diff": diff,
        })

    return _clean_json_value({
        "player_a": {
            "name": profile_a.get("player", player_a),
            "team": profile_a.get("team", ""),
            "league": profile_a.get("league", ""),
            "season": profile_a.get("season", ""),
            "position_group": profile_a.get("position_group", ""),
            "optimized_score": profile_a.get("optimized_score"),
            "confidence_level": profile_a.get("confidence_level", "LOW"),
        },
        "player_b": {
            "name": profile_b.get("player", player_b),
            "team": profile_b.get("team", ""),
            "league": profile_b.get("league", ""),
            "season": profile_b.get("season", ""),
            "position_group": profile_b.get("position_group", ""),
            "optimized_score": profile_b.get("optimized_score"),
            "confidence_level": profile_b.get("confidence_level", "LOW"),
        },
        "radar_labels": _RADAR_LABELS,
        "radar_a": [r["player_a"] for r in radar_comparison],
        "radar_b": [r["player_b"] for r in radar_comparison],
        "radar_comparison": radar_comparison,
        "position_percentile_comparison": pct_comparison,
        "stats_comparison": stats_comparison,
        "same_position": (
            profile_a.get("position_group", "") == profile_b.get("position_group", "")
        ),
        # PRS-0 R-003: propagate synthetic flag from underlying profiles so
        # consumers cannot mistake a demo-data comparison for a real one.
        "data_mode": (
            "synthetic"
            if profile_a.get("data_mode") == "synthetic"
            or profile_b.get("data_mode") == "synthetic"
            else "artifact"
        ),
    })


# ── Player similarity search ─────────────────────────────────────────────

_SIMILARITY_FEATURES = [
    ("npg_p90", "Attack"),
    ("assists_p90", "Creation"),
    ("defense_composite", "Defense"),
    ("possession_composite", "Possession"),
    ("optimized_score", "Overall"),
    ("minutes", "Availability"),
]

# Per-position feature weights. Each weight scales the corresponding z-scored
# feature before cosine similarity is computed, so that dimensions more
# relevant to a position carry more signal. Weights are normalised inside
# ``find_similar_players`` so absolute magnitude does not matter, only ratios.
_POSITION_FEATURE_WEIGHTS: dict[str, dict[str, float]] = {
    "GK": {"npg_p90": 0.0, "assists_p90": 0.0, "defense_composite": 3.0,
           "possession_composite": 1.0, "optimized_score": 2.0, "minutes": 1.0},
    "CB": {"npg_p90": 0.5, "assists_p90": 0.5, "defense_composite": 3.0,
           "possession_composite": 1.5, "optimized_score": 1.5, "minutes": 1.0},
    "FB": {"npg_p90": 0.5, "assists_p90": 1.0, "defense_composite": 2.0,
           "possession_composite": 2.0, "optimized_score": 1.5, "minutes": 1.0},
    "DM": {"npg_p90": 0.5, "assists_p90": 1.0, "defense_composite": 2.5,
           "possession_composite": 2.5, "optimized_score": 1.5, "minutes": 1.0},
    "CM": {"npg_p90": 1.0, "assists_p90": 1.5, "defense_composite": 1.5,
           "possession_composite": 3.0, "optimized_score": 1.5, "minutes": 1.0},
    "AM": {"npg_p90": 2.0, "assists_p90": 2.5, "defense_composite": 0.5,
           "possession_composite": 2.5, "optimized_score": 1.5, "minutes": 1.0},
    "W":  {"npg_p90": 2.5, "assists_p90": 2.5, "defense_composite": 0.5,
           "possession_composite": 1.5, "optimized_score": 1.5, "minutes": 1.0},
    "ST": {"npg_p90": 3.0, "assists_p90": 1.5, "defense_composite": 0.5,
           "possession_composite": 1.0, "optimized_score": 1.5, "minutes": 1.0},
}
_DEFAULT_FEATURE_WEIGHTS = {fc[0]: 1.0 for fc in _SIMILARITY_FEATURES}


def _position_weights(position_group: str) -> dict[str, float]:
    """Return feature weights for a position group, falling back to uniform."""
    pos = (position_group or "").strip().upper()
    return _POSITION_FEATURE_WEIGHTS.get(pos, _DEFAULT_FEATURE_WEIGHTS)


def find_similar_players(
    player_name: str,
    season: str | None = None,
    limit: int = 10,
    *,
    same_position_only: bool = True,
    league: str | None = None,
    min_minutes: float | None = None,
) -> dict:
    """Find players with similar profiles.

    Uses z-scored feature vectors (attack/creation/defense/possession/
    overall/availability), position-weighted before cosine similarity is
    computed. Returns top-N comparable players with similarity score, shared
    strengths and weaknesses.

    Parameters
    ----------
    same_position_only:
        When ``True`` (default), only compare within the target player's
        position group, z-scoring against that pool. When ``False``, build a
        cross-position pool where each player is z-scored against their own
        position group first, so profiles stay comparable across positions.
    league:
        Optional league filter applied to the candidate pool. The target
        player is still resolved from the full dataset (ignoring this filter
        if necessary) so a known player is never hidden by a league filter.
    min_minutes:
        Optional minimum minutes threshold applied to the candidate pool.
        Players below this threshold are excluded as low-reliability.
    """
    df = load_player_ratings(season=season)
    if df.empty:
        return {"count": 0, "target": None, "similar": [], "error": "no_data"}

    # Resolve position_group column
    if "position_group" not in df.columns:
        if "sub_position" in df.columns:
            df["position_group"] = df["sub_position"]
        else:
            return {"count": 0, "target": None, "similar": [], "error": "no_position"}

    name_col = "player_name" if "player_name" in df.columns else "player"
    if name_col not in df.columns:
        name_col = "player"

    # Fuzzy match target player
    exact_mask = df["player"] == player_name
    if exact_mask.any():
        mask = exact_mask
    else:
        mask = df["player"].str.contains(player_name, case=False, na=False)
    if season:
        mask = mask & (df["season"] == season)
    target_rows = df[mask]
    if target_rows.empty:
        return {"count": 0, "target": None, "similar": [], "error": "not_found"}

    # Pick best season for target
    try:
        target_row = target_rows.loc[target_rows["optimized_score"].idxmax()]
    except (ValueError, TypeError):
        target_row = target_rows.iloc[0]

    target_pos = str(target_row.get("position_group", ""))
    target_player = str(target_row.get("player", player_name))
    target_season = str(target_row.get("season", ""))

    feature_cols = [fc[0] for fc in _SIMILARITY_FEATURES]
    # Coerce feature columns to numeric across the full frame once.
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Build candidate pool with optional filters.
    pool = df.copy()
    if min_minutes is not None and min_minutes > 0:
        pool = pool[pool["minutes"].fillna(0.0) >= float(min_minutes)]
    if league:
        pool = pool[pool["league"].astype(str).str.lower() == str(league).lower()]

    # Resolve target feature vector (raw, before z-scoring).
    target_features = np.array(
        [float(target_row.get(col, 0.0) or 0.0) for col in feature_cols],
        dtype=float,
    )

    if same_position_only:
        pool = pool[pool["position_group"] == target_pos]
        if len(pool) < 2:
            return {
                "count": 0,
                "target": _target_payload(target_row, target_player, target_season, target_pos),
                "similar": [],
                "error": "pool_too_small",
            }
        # Z-score within the single-position pool. The target's z-score is
        # computed using the same pool statistics even when filters excluded
        # the target row from the pool (cross-league scouting use case).
        means = pool[feature_cols].mean()
        stds = pool[feature_cols].std(ddof=0).replace(0, 1.0)
        z_matrix = (pool[feature_cols] - means) / stds
        weights = _position_weights(target_pos)
        weight_vec = np.array([weights.get(col, 1.0) for col in feature_cols], dtype=float)
        z_values = z_matrix.values * weight_vec
        pool_indices = list(pool.index)
        # Compute target z-score against pool statistics (target may be absent
        # from pool when league/min_minutes filters exclude it).
        target_z = (target_features - means.values) / stds.values
        target_vec = target_z * weight_vec
        # Percentile ranks for the pool (used for strengths/weaknesses).
        pct_ranks = pool[feature_cols].rank(pct=True) * 100
        # Target percentile ranks: rank target against the pool by counting
        # how many pool members fall below the target's raw value.
        target_pcts_series = pd.Series(index=feature_cols, dtype=float)
        for col in feature_cols:
            col_vals = pool[col]
            target_val = float(target_row.get(col, 0.0) or 0.0)
            target_pcts_series[col] = (
                (col_vals < target_val).sum() / max(len(col_vals), 1) * 100
            )
    else:
        # Cross-position pool: z-score each player against their own position
        # group first, so profiles stay comparable across positions.
        if len(pool) < 2:
            return {
                "count": 0,
                "target": _target_payload(target_row, target_player, target_season, target_pos),
                "similar": [],
                "error": "pool_too_small",
            }
        # Compute per-position means/stds from the full df (not the filtered
        # pool) so z-scores are stable regardless of league/minute filters.
        z_full = pd.DataFrame(index=df.index, columns=feature_cols, dtype=float)
        pct_full = pd.DataFrame(index=df.index, columns=feature_cols, dtype=float)
        per_pos_stats: dict[str, tuple[pd.Series, pd.Series]] = {}
        for pos, pos_frame in df.groupby("position_group"):
            means = pos_frame[feature_cols].mean()
            stds = pos_frame[feature_cols].std(ddof=0).replace(0, 1.0)
            per_pos_stats[pos] = (means, stds)
            z_full.loc[pos_frame.index] = (
                (pos_frame[feature_cols] - means) / stds
            ).values
            pct_full.loc[pos_frame.index] = (
                pos_frame[feature_cols].rank(pct=True) * 100
            ).values
        # Apply target player's position weights (consistent comparison axis).
        weights = _position_weights(target_pos)
        weight_vec = np.array([weights.get(col, 1.0) for col in feature_cols], dtype=float)
        z_full_weighted = z_full.values * weight_vec
        # Restrict to filtered pool (preserving pool row order).
        pool_indices = list(pool.index)
        pool_pos_in_df = [list(df.index).index(i) for i in pool_indices]
        z_values = z_full_weighted[pool_pos_in_df]
        # Re-resolve pool from df for downstream metadata access.
        pool = df.loc[pool_indices].copy()
        # Compute target z-score against target's own position group stats.
        target_pos_stats = per_pos_stats.get(target_pos)
        if target_pos_stats is None:
            # Position group had only the target row (no groupby entry with
            # others); fall back to pool statistics.
            t_means = pool[feature_cols].mean()
            t_stds = pool[feature_cols].std(ddof=0).replace(0, 1.0)
        else:
            t_means, t_stds = target_pos_stats
        target_z = (target_features - t_means.values) / t_stds.values
        target_vec = target_z * weight_vec
        pct_ranks = pct_full.loc[pool_indices]
        target_pcts_series = pd.Series(index=feature_cols, dtype=float)
        for col in feature_cols:
            target_pcts_series[col] = float(pct_full.loc[target_row.name, col]) \
                if target_row.name in pct_full.index else 50.0

    # Cosine similarity
    target_norm = float(np.linalg.norm(target_vec))
    if target_norm == 0:
        return {
            "count": 0,
            "target": _target_payload(target_row, target_player, target_season, target_pos),
            "similar": [],
            "error": "zero_vector",
        }

    norms = np.linalg.norm(z_values, axis=1)
    safe_norms = np.where(norms == 0, 1.0, norms)
    similarities = (z_values @ target_vec) / (safe_norms * target_norm)
    # Clamp to [0, 1] — negative cosine similarity means "opposite" profile,
    # which is not meaningful as a similarity score for users
    similarities = np.clip(similarities, 0, 1)

    # Exclude target from results. Target may or may not be in the pool
    # (filtered out by league/min_minutes). When present, skip that row.
    candidates = []
    for i, idx in enumerate(pool_indices):
        row = pool.loc[idx]
        pname = str(row.get("player", ""))
        if pname == target_player:
            continue  # exclude target and same-player other-season rows
        candidates.append((i, idx, pname, row, similarities[i]))

    # Sort by similarity descending
    candidates.sort(key=lambda c: c[4], reverse=True)
    candidates = candidates[:limit]

    similar_list = []
    for _i, idx, pname, row, sim in candidates:
        cand_pcts = pct_ranks.loc[idx]
        # Shared strengths: both > 70th percentile
        shared_strengths = []
        shared_weaknesses = []
        for col, label in _SIMILARITY_FEATURES:
            t_pct = float(target_pcts_series.get(col, 50))
            c_pct = float(cand_pcts.get(col, 50))
            if t_pct > 70 and c_pct > 70:
                shared_strengths.append(label)
            elif t_pct < 30 and c_pct < 30:
                shared_weaknesses.append(label)

        similar_list.append(_clean_json_value({
            "name": pname,
            "team": str(row.get("team", "")),
            "league": str(row.get("league", "")),
            "season": str(row.get("season", "")),
            "position_group": str(row.get("position_group", "")),
            "optimized_score": round(float(row.get("optimized_score", 0) or 0), 1),
            "similarity": round(float(sim) * 100, 1),
            "shared_strengths": shared_strengths,
            "shared_weaknesses": shared_weaknesses,
            "minutes": round(float(row.get("minutes", 0) or 0)),
        }))

    # Surface the active weights + filters in the response so callers can
    # explain why a given candidate ranked where it did.
    weights_out = {label: round(float(weights.get(col, 1.0)), 3)
                   for col, label in _SIMILARITY_FEATURES}

    return _clean_json_value({
        "count": len(similar_list),
        "target": _target_payload(target_row, target_player, target_season, target_pos),
        "features": [fc[1] for fc in _SIMILARITY_FEATURES],
        "feature_weights": weights_out,
        "filters": {
            "same_position_only": bool(same_position_only),
            "league": league,
            "min_minutes": min_minutes,
            "season": season,
        },
        "similar": similar_list,
    })


def _target_payload(target_row, target_player: str, target_season: str, target_pos: str) -> dict:
    return _clean_json_value({
        "name": target_player,
        "team": str(target_row.get("team", "")),
        "league": str(target_row.get("league", "")),
        "season": target_season,
        "position_group": target_pos,
        "optimized_score": round(float(target_row.get("optimized_score", 0) or 0), 1),
    })


# ── Player career intelligence (trajectory / multi-compare / role-fit / peer) ──


def _resolve_player_rows(
    player_name: str,
    season: str | None = None,
    position_group: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series | None]:
    """Resolve a player's rows from the ratings matrix.

    Returns ``(full_df, player_rows, best_row)``. ``best_row`` is the
    highest-scoring season for the resolved player (or ``None`` when the
    player cannot be found). The full frame is returned so callers can pass
    it to peer / similarity helpers without re-loading.
    """
    df = load_player_ratings()
    if df.empty:
        return df, df, None

    if "sub_position" in df.columns and "position_group" not in df.columns:
        df["position_group"] = df["sub_position"]

    exact_mask = df["player"] == player_name
    if exact_mask.any():
        mask = exact_mask
    else:
        mask = df["player"].str.contains(player_name, case=False, na=False)
    if position_group:
        mask = mask & (df["position_group"] == position_group)
    if season:
        mask = mask & (df["season"] == season)
    player_rows = df[mask]
    if player_rows.empty:
        return df, player_rows, None

    try:
        best_row = player_rows.loc[player_rows["optimized_score"].idxmax()]
    except (ValueError, TypeError):
        best_row = player_rows.iloc[0]
    return df, player_rows, best_row


def get_player_career_trajectory(
    player_name: str,
    season: str | None = None,
    position_group: str | None = None,
) -> dict:
    """Return the full career trajectory for a player.

    Wraps :func:`scoutfootball.player_intel.compute_career_trajectory` with
    the standard data-loading and fuzzy-match layer used by other player
    endpoints.
    """
    from scoutfootball.player_intel import compute_career_trajectory

    _df, player_rows, _best = _resolve_player_rows(
        player_name, season=season, position_group=position_group
    )
    if player_rows.empty:
        return {"player": player_name, "found": False}
    trajectory = compute_career_trajectory(player_rows)
    return _clean_json_value({
        "player": player_name,
        "found": True,
        **trajectory,
    })


def get_player_comparison_multi(
    player_names: list[str],
    season: str | None = None,
) -> dict:
    """Compare 2–6 players side-by-side with a percentile matrix.

    Wraps :func:`scoutfootball.player_intel.compute_multi_player_comparison`.
    Each player is resolved to its best season row (highest score), or to
    ``season`` when supplied.
    """
    from scoutfootball.player_intel import compute_multi_player_comparison

    if not isinstance(player_names, list) or len(player_names) < 2:
        return {
            **_make_error_response("need_at_least_two_players"),
            "n_players": len(player_names) if isinstance(player_names, list) else 0,
            "min_required": 2,
        }
    if len(player_names) > 6:
        return {
            **_make_error_response("too_many_players"),
            "n_players": len(player_names),
            "max_allowed": 6,
        }

    df = load_player_ratings()
    if df.empty:
        return _make_error_response("no_data", message="No data available")
    if "sub_position" in df.columns and "position_group" not in df.columns:
        df["position_group"] = df["sub_position"]

    # PRS-0 R-003: stamp synthetic fallback so consumers cannot mistake
    # demo data for a real multi-player comparison.
    synthetic = frame_is_synthetic(df)

    rows_by_name: dict[str, Any] = {}
    missing: list[str] = []
    for name in player_names:
        exact_mask = df["player"] == name
        if exact_mask.any():
            mask = exact_mask
        else:
            mask = df["player"].str.contains(name, case=False, na=False)
        if season:
            mask = mask & (df["season"] == season)
        player_rows = df[mask]
        if player_rows.empty:
            missing.append(name)
            continue
        try:
            best_row = player_rows.loc[player_rows["optimized_score"].idxmax()]
        except (ValueError, TypeError):
            best_row = player_rows.iloc[0]
        resolved_name = str(best_row.get("player", name))
        rows_by_name[resolved_name] = best_row

    if missing:
        return {
            **_make_error_response("player_not_found"),
            "missing": missing,
            "resolved": list(rows_by_name.keys()),
        }

    result = compute_multi_player_comparison(rows_by_name, df)
    result["data_mode"] = "synthetic" if synthetic else "artifact"
    return _clean_json_value(result)


def get_player_role_fit(
    player_name: str,
    season: str | None = None,
    position_group: str | None = None,
) -> dict:
    """Return multi-position role-fit scores for a player.

    Wraps :func:`scoutfootball.player_intel.compute_role_fit_scores`.
    """
    from scoutfootball.player_intel import compute_role_fit_scores

    df, player_rows, best_row = _resolve_player_rows(
        player_name, season=season, position_group=position_group
    )
    if best_row is None:
        return {"player": player_name, "found": False}
    result = compute_role_fit_scores(best_row, df)
    return _clean_json_value({
        "player": str(best_row.get("player", player_name)),
        "found": True,
        "season": str(best_row.get("season", "")),
        "position_group": str(best_row.get("position_group", "")),
        "team": str(best_row.get("team", "")),
        "league": str(best_row.get("league", "")),
        **result,
    })


def get_player_peer_benchmark(
    player_name: str,
    season: str | None = None,
    position_group: str | None = None,
) -> dict:
    """Return peer-group benchmark for a player.

    Wraps :func:`scoutfootball.player_intel.compute_peer_benchmark`.
    """
    from scoutfootball.player_intel import compute_peer_benchmark

    df, player_rows, best_row = _resolve_player_rows(
        player_name, season=season, position_group=position_group
    )
    if best_row is None:
        return {"player": player_name, "found": False}
    result = compute_peer_benchmark(best_row, df)
    return _clean_json_value({
        "player": str(best_row.get("player", player_name)),
        "found": True,
        "season": str(best_row.get("season", "")),
        "position_group": str(best_row.get("position_group", "")),
        "team": str(best_row.get("team", "")),
        "league": str(best_row.get("league", "")),
        **result,
    })


def get_riser_decliner_watchlist(
    season: str | None = None,
    *,
    min_seasons: int = 2,
    min_minutes_latest: float = 300.0,
    top_n: int = 20,
    riser_threshold: float = 1.0,
    decliner_threshold: float = -1.0,
) -> dict:
    """Return players on the steepest upward or downward career trajectories.

    Wraps :func:`scoutfootball.player_intel.compute_riser_decliner_watchlist`.
    """
    from scoutfootball.player_intel import compute_riser_decliner_watchlist

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "risers": [], "decliners": [], "n_scanned": 0}
    if season:
        df = df[df["season"].astype(str) == str(season)]
    result = compute_riser_decliner_watchlist(
        df,
        min_seasons=min_seasons,
        min_minutes_latest=min_minutes_latest,
        top_n=top_n,
        riser_threshold=riser_threshold,
        decliner_threshold=decliner_threshold,
    )
    return _clean_json_value(result)


def get_team_style_clusters(
    season: str | None = None,
    league: str | None = None,
    *,
    n_clusters: int = 4,
    min_minutes_total: float = 1800.0,
) -> dict:
    """Cluster teams into tactical-style groups via k-means.

    Wraps :func:`scoutfootball.features.team_style.compute_team_style_clusters`.
    """
    from scoutfootball.features.team_style import compute_team_style_clusters

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "clusters": [], "team_profiles": []}
    result = compute_team_style_clusters(
        df,
        season=season,
        league=league,
        n_clusters=n_clusters,
        min_minutes_total=min_minutes_total,
    )
    return _clean_json_value(result)


def get_player_style_fit(
    player_name: str,
    season: str | None = None,
    league: str | None = None,
    *,
    n_clusters: int = 4,
    min_minutes_total: float = 1800.0,
) -> dict:
    """Compute a player's style-fit to each team-style cluster.

    Wraps :func:`scoutfootball.features.team_style.compute_player_style_fit`.
    """
    from scoutfootball.features.team_style import compute_player_style_fit

    df = load_player_ratings()
    if df.empty:
        return {
            "status": "no_data",
            "player": player_name,
            "clusters": [],
        }
    result = compute_player_style_fit(
        df,
        player_name,
        season=season,
        league=league,
        n_clusters=n_clusters,
        min_minutes_total=min_minutes_total,
    )
    return _clean_json_value(result)


def get_cluster_recruits(
    cluster_id: int,
    season: str | None = None,
    league: str | None = None,
    *,
    n_clusters: int = 4,
    min_minutes_total: float = 1800.0,
    min_player_minutes: float = 500.0,
    position_group: str | None = None,
    top_n: int = 20,
    exclude_cluster_teams: bool = True,
) -> dict:
    """Rank players by style-fit to a specific team-style cluster.

    Wraps :func:`scoutfootball.features.team_style.compute_cluster_recruits`.
    """
    from scoutfootball.features.team_style import compute_cluster_recruits

    df = load_player_ratings()
    if df.empty:
        return {
            "status": "no_data",
            "cluster_id": cluster_id,
            "recruits": [],
        }
    result = compute_cluster_recruits(
        df,
        cluster_id,
        season=season,
        league=league,
        n_clusters=n_clusters,
        min_minutes_total=min_minutes_total,
        min_player_minutes=min_player_minutes,
        position_group=position_group,
        top_n=top_n,
        exclude_cluster_teams=exclude_cluster_teams,
    )
    return _clean_json_value(result)


def get_cluster_similarity_matrix(
    season: str | None = None,
    league: str | None = None,
    *,
    n_clusters: int = 4,
    min_minutes_total: float = 1800.0,
) -> dict:
    """Compute an NxN similarity matrix between team-style clusters.

    Wraps :func:`scoutfootball.features.team_style.compute_cluster_similarity_matrix`.
    """
    from scoutfootball.features.team_style import (
        compute_cluster_similarity_matrix,
    )

    df = load_player_ratings()
    if df.empty:
        return {
            "status": "no_data",
            "n_clusters": 0,
            "labels": [],
            "matrix": [],
            "pairs": [],
        }
    result = compute_cluster_similarity_matrix(
        df,
        season=season,
        league=league,
        n_clusters=n_clusters,
        min_minutes_total=min_minutes_total,
    )
    return _clean_json_value(result)


def get_style_matchup(
    home_team: str,
    away_team: str,
    season: str | None = None,
    league: str | None = None,
    *,
    n_clusters: int = 4,
    min_minutes_total: float = 1800.0,
) -> dict:
    """Diagnostic of how two teams' tactical styles clash.

    Wraps :func:`scoutfootball.features.team_style.compute_style_matchup`.
    This is a non-additive interpretive overlay — it does not modify the
    match-probability model.
    """
    from scoutfootball.features.team_style import compute_style_matchup

    df = load_player_ratings()
    if df.empty:
        return {
            "status": "no_data",
            "home_team": home_team,
            "away_team": away_team,
        }
    result = compute_style_matchup(
        df,
        home_team,
        away_team,
        season=season,
        league=league,
        n_clusters=n_clusters,
        min_minutes_total=min_minutes_total,
    )
    return _clean_json_value(result)


def get_style_neighbors(
    team: str,
    season: str | None = None,
    league: str | None = None,
    *,
    top_n: int = 10,
    n_clusters: int = 4,
    min_minutes_total: float = 1800.0,
) -> dict:
    """Find the nearest tactical-style neighbors for a team.

    Wraps :func:`scoutfootball.features.team_style.compute_style_neighbors`.
    Interpretive overlay — does not predict match outcomes or rank by quality.
    """
    from scoutfootball.features.team_style import compute_style_neighbors

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "team": team}
    result = compute_style_neighbors(
        df,
        team,
        season=season,
        league=league,
        top_n=top_n,
        n_clusters=n_clusters,
        min_minutes_total=min_minutes_total,
    )
    return _clean_json_value(result)


def get_league_style_percentiles(
    team: str,
    season: str | None = None,
    league: str | None = None,
    *,
    min_minutes_total: float = 1800.0,
) -> dict:
    """Per-dimension percentile rank of a team within its league population.

    Wraps :func:`scoutfootball.features.team_style.compute_league_style_percentiles`.
    Descriptive overlay — percentiles are relative, not absolute.
    """
    from scoutfootball.features.team_style import (
        compute_league_style_percentiles,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "team": team}
    result = compute_league_style_percentiles(
        df,
        team,
        season=season,
        league=league,
        min_minutes_total=min_minutes_total,
    )
    return _clean_json_value(result)


def get_style_atlas(
    season: str | None = None,
    league: str | None = None,
    *,
    n_bins: int = 8,
    min_minutes_total: float = 1800.0,
) -> dict:
    """League-wide distribution of team styles across all dimensions.

    Wraps :func:`scoutfootball.features.team_style.compute_style_atlas`.
    Descriptive population view — does not rank teams by quality.
    """
    from scoutfootball.features.team_style import compute_style_atlas

    df = load_player_ratings()
    if df.empty:
        return {
            "status": "no_data",
            "dimensions": [],
        }
    result = compute_style_atlas(
        df,
        season=season,
        league=league,
        n_bins=n_bins,
        min_minutes_total=min_minutes_total,
    )
    return _clean_json_value(result)


def get_team_style_drift(
    team: str,
    league: str | None = None,
    *,
    min_minutes_total: float = 1800.0,
) -> dict:
    """Compute a single team's style trajectory across seasons.

    Wraps :func:`scoutfootball.features.team_style.compute_team_style_drift`.
    Descriptive overlay — does not predict future style or rank by quality.
    """
    from scoutfootball.features.team_style import compute_team_style_drift

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "team": team}
    result = compute_team_style_drift(
        df,
        team,
        league=league,
        min_minutes_total=min_minutes_total,
    )
    return _clean_json_value(result)


def get_league_style_evolution(
    league: str | None = None,
    *,
    min_minutes_total: float = 1800.0,
) -> dict:
    """Compute league-wide style evolution across seasons.

    Wraps :func:`scoutfootball.features.team_style.compute_league_style_evolution`.
    Descriptive population view — does not predict future style.
    """
    from scoutfootball.features.team_style import compute_league_style_evolution

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "dimensions": []}
    result = compute_league_style_evolution(
        df,
        league=league,
        min_minutes_total=min_minutes_total,
    )
    return _clean_json_value(result)


def get_style_drift_neighbors(
    team: str,
    league: str | None = None,
    *,
    top_n: int = 10,
    min_seasons: int = 2,
    min_minutes_total: float = 1800.0,
) -> dict:
    """Find teams with similar style-drift patterns.

    Wraps :func:`scoutfootball.features.team_style.compute_style_drift_neighbors`.
    Descriptive overlay — does not imply similar quality or future trajectory.
    """
    from scoutfootball.features.team_style import compute_style_drift_neighbors

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "team": team}
    result = compute_style_drift_neighbors(
        df,
        team,
        league=league,
        top_n=top_n,
        min_seasons=min_seasons,
        min_minutes_total=min_minutes_total,
    )
    return _clean_json_value(result)


def get_position_style_evolution(
    league: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Compute per-position-group style evolution across seasons.

    Wraps :func:`scoutfootball.features.team_style.compute_position_style_evolution`.
    Descriptive population view — does not predict future style.
    """
    from scoutfootball.features.team_style import (
        compute_position_style_evolution,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "position_groups": []}
    result = compute_position_style_evolution(
        df,
        league=league,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_position_style_drift(
    position_group: str,
    league: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Compute a single position group's style drift across seasons.

    Wraps :func:`scoutfootball.features.team_style.compute_position_style_drift`.
    Descriptive overlay — does not predict future style.
    """
    from scoutfootball.features.team_style import (
        compute_position_style_drift,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "position_group": position_group}
    result = compute_position_style_drift(
        df,
        position_group,
        league=league,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_position_style_drift_neighbors(
    position_group: str,
    league: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Find position groups with similar style-drift patterns.

    Wraps :func:`scoutfootball.features.team_style.compute_position_style_drift_neighbors`.
    Descriptive overlay — does not imply similar quality.
    """
    from scoutfootball.features.team_style import (
        compute_position_style_drift_neighbors,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "position_group": position_group}
    result = compute_position_style_drift_neighbors(
        df,
        position_group,
        league=league,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_position_depth_profile(
    league: str | None = None,
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Depth profile for each standard position group.

    Wraps :func:`scoutfootball.features.team_style.compute_position_depth_profile`.
    Descriptive overlay — does not rank positions by quality.
    """
    from scoutfootball.features.team_style import (
        compute_position_depth_profile,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "position_groups": []}
    result = compute_position_depth_profile(
        df,
        league=league,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_cross_league_position_comparison(
    position_group: str,
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Compare one position group's depth across leagues.

    Wraps :func:`scoutfootball.features.team_style.compute_cross_league_position_comparison`.
    Descriptive overlay — does not rank leagues by overall quality.
    """
    from scoutfootball.features.team_style import (
        compute_cross_league_position_comparison,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "position_group": position_group}
    result = compute_cross_league_position_comparison(
        df,
        position_group,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_position_gap_report(
    team: str,
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Identify shallow and low-quality position groups for one team.

    Wraps :func:`scoutfootball.features.team_style.compute_position_gap_report`.
    Descriptive overlay — does not recommend transfers or tactical changes.
    """
    from scoutfootball.features.team_style import (
        compute_position_gap_report,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "team": team}
    result = compute_position_gap_report(
        df,
        team,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_position_action_profile(
    league: str | None = None,
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Granular per-90 action profile for each standard position group.

    Wraps :func:`scoutfootball.features.team_style.compute_position_action_profile`.
    Descriptive overlay — does not rank positions by quality.
    """
    from scoutfootball.features.team_style import (
        compute_position_action_profile,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "position_groups": []}
    result = compute_position_action_profile(
        df,
        league=league,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_action_based_position_similarity(
    position_group: str,
    league: str | None = None,
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Find position groups with similar per-90 action signatures.

    Wraps :func:`scoutfootball.features.team_style.compute_action_based_position_similarity`.
    Descriptive overlay — similar action signatures do not imply similar
    quality or tactical roles.
    """
    from scoutfootball.features.team_style import (
        compute_action_based_position_similarity,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "position_group": position_group}
    result = compute_action_based_position_similarity(
        df,
        position_group,
        league=league,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_position_trend_overlay(
    league: str | None = None,
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Collective improvement/decline trends for each position group.

    Wraps :func:`scoutfootball.features.team_style.compute_position_trend_overlay`.
    Descriptive overlay — does not predict future trends.
    """
    from scoutfootball.features.team_style import (
        compute_position_trend_overlay,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "position_groups": []}
    result = compute_position_trend_overlay(
        df,
        league=league,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_team_action_profile(
    league: str | None = None,
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Granular per-90 action profile for each team.

    Wraps :func:`scoutfootball.features.team_style.compute_team_action_profile`.
    Descriptive overlay — does not rank teams by quality.
    """
    from scoutfootball.features.team_style import (
        compute_team_action_profile,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "teams": []}
    result = compute_team_action_profile(
        df,
        league=league,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_league_action_percentiles(
    team: str,
    league: str | None = None,
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Per-action percentile rank of one team within its league population.

    Wraps :func:`scoutfootball.features.team_style.compute_league_action_percentiles`.
    Descriptive overlay — percentiles describe relative standing, not
    absolute quality.
    """
    from scoutfootball.features.team_style import (
        compute_league_action_percentiles,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "team": team}
    result = compute_league_action_percentiles(
        df,
        team,
        league=league,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_team_action_similarity(
    team: str,
    league: str | None = None,
    season: str | None = None,
    *,
    top_n: int = 10,
    min_player_minutes: float = 500.0,
) -> dict:
    """Find teams with similar per-90 action signatures.

    Wraps :func:`scoutfootball.features.team_style.compute_team_action_similarity`.
    Descriptive overlay — similar action signatures do not imply similar
    quality or tactical systems.
    """
    from scoutfootball.features.team_style import (
        compute_team_action_similarity,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "team": team}
    result = compute_team_action_similarity(
        df,
        team,
        league=league,
        season=season,
        top_n=top_n,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_league_action_atlas(
    season: str | None = None,
    league: str | None = None,
    *,
    n_bins: int = 8,
    min_player_minutes: float = 500.0,
) -> dict:
    """League-wide distribution of team per-90 actions across 7 features.

    Wraps :func:`scoutfootball.features.team_style.compute_league_action_atlas`.
    Descriptive overlay — does not rank teams by quality.
    """
    from scoutfootball.features.team_style import (
        compute_league_action_atlas,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "league": league, "season": season}
    result = compute_league_action_atlas(
        df,
        season=season,
        league=league,
        n_bins=n_bins,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_league_action_evolution(
    league: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """League-wide action evolution across seasons.

    Wraps :func:`scoutfootball.features.team_style.compute_league_action_evolution`.
    Descriptive overlay — does not predict future league actions.
    """
    from scoutfootball.features.team_style import (
        compute_league_action_evolution,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "league": league}
    result = compute_league_action_evolution(
        df,
        league=league,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_cross_league_action_comparison(
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Compare per-90 action profiles across leagues.

    Wraps :func:`scoutfootball.features.team_style.compute_cross_league_action_comparison`.
    Descriptive overlay — does not rank leagues by overall quality.
    """
    from scoutfootball.features.team_style import (
        compute_cross_league_action_comparison,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "season": season}
    result = compute_cross_league_action_comparison(
        df,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_cross_league_team_depth(
    team_a: str,
    team_b: str,
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Compare two teams' per-position depth profiles side-by-side.

    Wraps :func:`scoutfootball.features.team_style.compute_cross_league_team_depth`.
    Descriptive overlay — does not predict match outcomes or recommend
    transfers. The advantage flag uses a 0.5-point mean-score threshold.
    """
    from scoutfootball.features.team_style import (
        compute_cross_league_team_depth,
    )

    df = load_player_ratings()
    if df.empty:
        return {
            "status": "no_data",
            "team_a": team_a,
            "team_b": team_b,
            "season": season,
        }
    result = compute_cross_league_team_depth(
        df,
        team_a,
        team_b,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    return _clean_json_value(result)


def get_scouting_targets(
    team: str,
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
    top_n: int = 10,
    exclude_same_league: bool = True,
) -> dict:
    """Find players from other leagues who could fill a team's position gaps.

    Wraps :func:`scoutfootball.features.team_style.compute_scouting_targets`.
    Descriptive overlay — NOT a transfer recommendation. Candidates are
    filtered by minutes, score threshold, and top-quartile (p75) rank in
    their own league at the gap position.
    """
    from scoutfootball.features.team_style import (
        compute_scouting_targets,
    )

    df = load_player_ratings()
    if df.empty:
        return {"status": "no_data", "team": team, "season": season}
    result = compute_scouting_targets(
        df,
        team,
        season=season,
        min_player_minutes=min_player_minutes,
        top_n=top_n,
        exclude_same_league=exclude_same_league,
    )
    return _clean_json_value(result)


def get_scouting_target_style_match(
    team: str,
    position_group: str,
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
    top_n: int = 10,
    exclude_same_league: bool = True,
    use_position_weights: bool = False,
) -> dict:
    """Find players from other leagues with similar style to a team's top player.

    Wraps :func:`scoutfootball.features.team_style.compute_scouting_target_style_match`.
    Builds a 4-dim style vector for the team's highest-scored player at
    ``position_group`` and finds the most similar players in other leagues
    by cosine similarity. Descriptive overlay — NOT a transfer recommendation.

    When ``use_position_weights=True``, the 4 style dimensions are weighted
    per position (e.g. defense_composite emphasized for CB, npg_p90 for ST)
    before cosine similarity is computed. Weights are sourced from
    ``_POSITION_STYLE_WEIGHTS`` in ``features/team_style.py``.
    """
    from scoutfootball.features.team_style import (
        compute_scouting_target_style_match,
    )

    df = load_player_ratings()
    if df.empty:
        return {
            "status": "no_data",
            "team": team,
            "position_group": position_group,
            "season": season,
        }
    result = compute_scouting_target_style_match(
        df,
        team,
        position_group,
        season=season,
        min_player_minutes=min_player_minutes,
        top_n=top_n,
        exclude_same_league=exclude_same_league,
        use_position_weights=use_position_weights,
    )
    return _clean_json_value(result)


def get_scouting_dashboard(
    team: str,
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
    top_n: int = 10,
    exclude_same_league: bool = True,
    max_positions: int = 3,
    use_position_weights: bool = False,
) -> dict:
    """Aggregate scouting dashboard: gap targets + multi-position style match.

    Wraps :func:`scoutfootball.features.team_style.compute_scouting_dashboard`.
    Returns a single report card combining:

    * ``gap_targets`` — top N position gaps for ``team`` (reuses
      :func:`compute_scouting_targets`), each with cross-league candidates.
    * ``position_style_matches`` — for each of the top ``max_positions`` gap
      positions, a style-match list of cross-league players similar to the
      team's current starter at that position.

    When ``use_position_weights=True``, the per-position weights from
    ``_POSITION_STYLE_WEIGHTS`` are applied to both target and candidate
    style vectors before cosine similarity.

    Descriptive overlay — NOT a transfer recommendation.
    """
    from scoutfootball.features.team_style import compute_scouting_dashboard

    df = load_player_ratings()
    if df.empty:
        return {
            "status": "no_data",
            "team": team,
            "season": season,
        }
    result = compute_scouting_dashboard(
        df,
        team,
        season=season,
        min_player_minutes=min_player_minutes,
        top_n=top_n,
        exclude_same_league=exclude_same_league,
        max_positions=max_positions,
        use_position_weights=use_position_weights,
    )
    return _clean_json_value(result)


# ── League season projection & form analysis ──────────────────────────────


def get_league_form_table(
    league: str | None = None,
    season: str | None = None,
    last_n: int = 6,
) -> dict:
    """Last-N form table for every team in a league-season.

    Wraps :func:`scoutfootball.features.season_projection.compute_league_form_table`
    using Football-Data ``combined_results.parquet``. Descriptive overlay —
    does not use the Dixon-Coles model or rating matrix.
    """
    from scoutfootball.features.season_projection import (
        compute_league_form_table,
    )

    if not season:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "last_n": last_n,
            "teams": [],
            "disclaimer": "Season parameter is required.",
        }
    try:
        df = _load_match_results()
        if df.empty:
            return {
                "status": "no_data",
                "league": league,
                "season": season,
                "last_n": last_n,
                "teams": [],
                "disclaimer": "Match results data unavailable.",
            }
        result = compute_league_form_table(
            df, league=league, season=season, last_n=last_n
        )
        return _clean_json_value(result)
    except Exception as exc:
        logger.warning("get_league_form_table failed: %s", exc, exc_info=True)
        return {
            **_make_error_response(str(exc)),
            "league": league,
            "season": season,
            "last_n": last_n,
            "teams": [],
        }


def get_fixture_difficulty(
    league: str | None = None,
    season: str | None = None,
    team: str | None = None,
    upcoming_n: int = 10,
) -> dict:
    """Fixture difficulty rating for each team's most recent N matches.

    Wraps :func:`scoutfootball.features.season_projection.compute_fixture_difficulty`
    using Football-Data ``combined_results.parquet``. Descriptive overlay —
    uses a Bradley-Terry strength estimate from in-season PPG, not the
    Dixon-Coles model.
    """
    from scoutfootball.features.season_projection import (
        compute_fixture_difficulty,
    )

    if not season:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "team": team,
            "upcoming_n": upcoming_n,
            "teams": [],
            "disclaimer": "Season parameter is required.",
        }
    try:
        df = _load_match_results()
        if df.empty:
            return {
                "status": "no_data",
                "league": league,
                "season": season,
                "team": team,
                "upcoming_n": upcoming_n,
                "teams": [],
                "disclaimer": "Match results data unavailable.",
            }
        result = compute_fixture_difficulty(
            df,
            league=league,
            season=season,
            team=team,
            upcoming_n=upcoming_n,
        )
        return _clean_json_value(result)
    except Exception as exc:
        logger.warning("get_fixture_difficulty failed: %s", exc, exc_info=True)
        return {
            **_make_error_response(str(exc)),
            "league": league,
            "season": season,
            "team": team,
            "upcoming_n": upcoming_n,
            "teams": [],
        }


def get_season_projection(
    league: str | None = None,
    season: str | None = None,
    num_simulations: int = 1000,
    random_seed: int = 42,
    top_n: int = 4,
    relegation_slots: int = 3,
) -> dict:
    """Monte Carlo projection of final league standings.

    Wraps :func:`scoutfootball.features.season_projection.compute_season_projection`
    using Football-Data ``combined_results.parquet``. Descriptive overlay —
    uses a Bradley-Terry strength estimate from in-season PPG and a
    reproducible random seed, not the Dixon-Coles model.
    """
    from scoutfootball.features.season_projection import (
        compute_season_projection,
    )

    if not season:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "num_simulations": num_simulations,
            "teams": [],
            "disclaimer": "Season parameter is required.",
        }
    try:
        df = _load_match_results()
        if df.empty:
            return {
                "status": "no_data",
                "league": league,
                "season": season,
                "num_simulations": num_simulations,
                "teams": [],
                "disclaimer": "Match results data unavailable.",
            }
        result = compute_season_projection(
            df,
            league=league,
            season=season,
            num_simulations=num_simulations,
            random_seed=random_seed,
            top_n=top_n,
            relegation_slots=relegation_slots,
        )
        return _clean_json_value(result)
    except Exception as exc:
        logger.warning("get_season_projection failed: %s", exc, exc_info=True)
        return {
            **_make_error_response(str(exc)),
            "league": league,
            "season": season,
            "num_simulations": num_simulations,
            "teams": [],
        }


# ── World Cup endpoints ──────────────────────────────────────────────────


def get_wc_groups() -> dict:
    """Return World Cup group data with team strength ratings."""
    enriched, strengths = _get_wc_enriched_squads()

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

    # Core DataContracts: groups combine expected_callup (squad lists) +
    # rating_coverage (per-player rating join) + model_probability (strength).
    from scoutfootball.worldcup.contracts import (
        build_expected_callups_contract,
        build_model_probability_contract,
        build_rating_coverage_contract,
        contract_to_dict,
        fact_type_for_artifact,
    )
    from scoutfootball.worldcup.data import count_expected_callups

    expected_contract = build_expected_callups_contract(
        record_count=count_expected_callups()
    )
    total_rated = sum(
        1 for s in enriched.values() for p in s if p.has_rating
    )
    rating_contract = build_rating_coverage_contract(record_count=total_rated)
    model_contract = build_model_probability_contract(
        record_count=len(strengths)
    )
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
        "contracts": [
            contract_to_dict(expected_contract),
            contract_to_dict(rating_contract),
            contract_to_dict(model_contract),
        ],
        "fact_types": [
            fact_type_for_artifact(expected_contract.artifact_id).value,
            fact_type_for_artifact(rating_contract.artifact_id).value,
            fact_type_for_artifact(model_contract.artifact_id).value,
        ],
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

    # Core DataContract: the full 72-match schedule is the artifact; group
    # and matchday filters are view-level, so the contract always reports
    # the full-schedule record count.
    from scoutfootball.worldcup.contracts import (
        build_schedule_contract,
        contract_to_dict,
        fact_type_for_artifact,
    )

    schedule_contract = build_schedule_contract(record_count=len(matches))
    return _clean_json_value({
        "status": "ok",
        "count": len(match_dicts),
        "source_attribution": (
            "Schedule generated from official FIFA fixture pattern; "
            "dates/venues are approximate"
        ),
        "contracts": [contract_to_dict(schedule_contract)],
        "fact_types": [fact_type_for_artifact(schedule_contract.artifact_id).value],
        "matches": match_dicts,
    })


def get_wc_squad(team: str) -> dict:
    """Return a specific team's World Cup squad with player ratings."""
    enriched, _ = _get_wc_enriched_squads()
    squad = enriched.get(team, get_squad(team))

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

    # Core DataContracts: the squad payload combines expected_callup
    # (static SQUADS table) with rating_coverage (per-player rating join).
    # The contract record counts cover all 48 teams so consumers can
    # verify the artifact identity regardless of which team they inspect.
    from scoutfootball.worldcup.contracts import (
        build_expected_callups_contract,
        build_rating_coverage_contract,
        contract_to_dict,
        fact_type_for_artifact,
    )
    from scoutfootball.worldcup.data import count_expected_callups

    expected_contract = build_expected_callups_contract(
        record_count=count_expected_callups()
    )
    # rating_coverage record_count uses the global rated-player count
    # across all 48 teams, not just this team, so the artifact identity
    # is stable across per-team views.
    all_enriched = enriched
    total_rated = sum(
        1 for s in all_enriched.values() for p in s if p.has_rating
    )
    rating_contract = build_rating_coverage_contract(record_count=total_rated)
    return _clean_json_value({
        "status": "ok",
        "team": team,
        "group": group,
        "is_host": team in HOSTS,
        "total_players": len(squad),
        "rated_players": len(rated),
        "big5_players": big5_count,
        "avg_rating": avg_rating,
        "squad_balance": compute_squad_balance(squad),
        "source_attribution": (
            "Ratings derived from FBref/Understat data "
            "via ScoutFootball optimizer"
        ),
        "disclaimer": (
            "Squad rosters are placeholder lists; official 26-man "
            "squads not yet announced. Ratings from domestic league "
            "performance only."
        ),
        "contracts": [
            contract_to_dict(expected_contract),
            contract_to_dict(rating_contract),
        ],
        "fact_types": [
            fact_type_for_artifact(expected_contract.artifact_id).value,
            fact_type_for_artifact(rating_contract.artifact_id).value,
        ],
        "players": players,
    })


def get_wc_squad_scouting_needs(
    team: str,
    season: str | None = None,
    *,
    min_player_minutes: float = 500.0,
) -> dict:
    """Per-player scouting-need overlay for a World Cup squad.

    For each unique club team appearing in the squad, runs
    :func:`compute_position_gap_report` and aggregates the gaps by
    ``position_group``. Each squad player is then annotated with a
    ``scouting_need`` object describing the gap (if any) at their position
    within their club team's roster, plus a link target for the scouting
    dashboard.

    Descriptive overlay — does not recommend transfers. Players whose club
    team is not present in the rating matrix get ``scouting_need: null`` and
    ``club_gap_status: "team_not_found"`` rather than a fabricated gap.
    """
    from scoutfootball.features.team_style import (
        compute_position_gap_report,
    )

    enriched, _ = _get_wc_enriched_squads()
    squad = enriched.get(team, get_squad(team))

    df = load_player_ratings()
    if df.empty:
        return _clean_json_value({
            "status": "no_data",
            "team": team,
            "club_gaps": {},
            "players": [],
            "disclaimer": (
                "Rating matrix unavailable; scouting-need overlay cannot "
                "be computed."
            ),
        })

    # Build a map of club_team -> {position_group -> gap dict} so each
    # player can be annotated in O(1) without re-running the report.
    club_gaps: dict[str, dict] = {}
    for p in squad:
        club = p.club
        if not club or club in club_gaps:
            continue
        try:
            result = compute_position_gap_report(
                df,
                club,
                season=season,
                min_player_minutes=min_player_minutes,
            )
        except Exception:  # noqa: BLE001 — defensive on user-facing path
            logger.warning(
                "compute_position_gap_report failed for club %r", club, exc_info=True
            )
            result = {"status": "error", "gaps": []}
        gaps_by_pos: dict[str, dict] = {}
        if result.get("status") == "ok":
            for g in result.get("gaps", []) or []:
                pos = g.get("position_group")
                if pos:
                    gaps_by_pos[pos] = g
        club_gaps[club] = {
            "status": result.get("status", "error"),
            "league": result.get("league"),
            "n_gaps": result.get("n_gaps", 0),
            "gaps_by_position": gaps_by_pos,
        }

    players = []
    for p in squad:
        club = p.club
        club_entry = club_gaps.get(club) if club else None
        gap = None
        if club_entry and club_entry.get("status") == "ok":
            gap = club_entry.get("gaps_by_position", {}).get(p.position)
        players.append({
            "name": p.name,
            "position": p.position,
            "club": p.club,
            "club_league": p.club_league,
            "has_rating": p.has_rating,
            "rating": round(p.rating, 2) if p.rating is not None else None,
            "rating_confidence": p.rating_confidence,
            "club_gap_status": club_entry.get("status") if club_entry else "team_not_found",
            "scouting_need": gap,
        })

    return _clean_json_value({
        "status": "ok",
        "team": team,
        "group": get_team_group(team),
        "is_host": team in HOSTS,
        "season": season,
        "club_gaps": club_gaps,
        "players": players,
        "source_attribution": (
            "Gap reports derived from FBref/Understat rating matrix via "
            "ScoutFootball optimizer; club names matched against the "
            "rating matrix's `team` column."
        ),
        "disclaimer": (
            "Scouting-need pills reflect the player's club team depth at "
            "their listed position; they are descriptive overlays and do "
            "not constitute transfer recommendations. Players at non-Big5 "
            "clubs may have no rating-matrix coverage and show no pill."
        ),
    })


def get_wc_squad_balance_comparison(team_a: str, team_b: str) -> dict:
    """Compare two expected-callup snapshots without inferring a lineup."""
    enriched_squads, _ = _get_wc_enriched_squads()
    missing = [team for team in (team_a, team_b) if team not in enriched_squads]
    if missing:
        return _make_error_response(
            f"Team(s) not found in World Cup data: {', '.join(missing)}"
        )

    team_a_balance = compute_squad_balance(enriched_squads[team_a])
    team_b_balance = compute_squad_balance(enriched_squads[team_b])
    role_rows = []
    for role, team_a_role in team_a_balance["roles"].items():
        team_b_role = team_b_balance["roles"][role]
        role_rows.append({
            "role": role,
            "team_a": team_a_role,
            "team_b": team_b_role,
            "count_difference": team_a_role["count"] - team_b_role["count"],
            "rated_player_difference": (
                team_a_role["rated_players"] - team_b_role["rated_players"]
            ),
            "rating_coverage_difference": round(
                team_a_role["rating_coverage"] - team_b_role["rating_coverage"], 4
            ),
        })

    return _clean_json_value({
        "schema": "scoutfootball.world-cup-squad-balance-comparison",
        "version": "1.0.0",
        "status": "ok",
        "scope": "expected_callup_snapshot",
        "teams": {
            "team_a": {"team": team_a, "balance": team_a_balance},
            "team_b": {"team": team_b, "balance": team_b_balance},
        },
        "roles": role_rows,
        "disclaimer": (
            "This compares local expected-callup snapshots only. It is not a "
            "confirmed roster, lineup, injury report, tactical recommendation, "
            "or claim that one team is stronger in a role."
        ),
    })


def get_wc_predictions() -> dict:
    """Return World Cup group stage predictions based on team strengths."""
    enriched, strengths = _get_wc_enriched_squads()
    strength_details = _get_wc_strength_details()
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
            "coverage": strength_details.get(team, {}).get("coverage"),
            "core_avg_rating": strength_details.get(team, {}).get("core_avg_rating"),
            "shrunk_avg_rating": strength_details.get(team, {}).get("shrunk_avg_rating"),
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

    # Core DataContract: model_probability (Bradley-Terry + Opta priors).
    from scoutfootball.worldcup.contracts import (
        build_model_probability_contract,
        contract_to_dict,
        fact_type_for_artifact,
    )

    model_contract = build_model_probability_contract(
        record_count=len(strengths)
    )
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
        "contracts": [contract_to_dict(model_contract)],
        "fact_types": [fact_type_for_artifact(model_contract.artifact_id).value],
        "groups": group_preds,
        "ranking": ranking,
        "best_third_place": third_place[:8],
    })


def get_wc_knockout() -> dict:
    """Return World Cup knockout bracket simulation with round-by-round probabilities.

    Simulates the Round of 32 through the Final using a Bradley-Terry
    strength model and Monte Carlo tournament win probabilities.
    Requires the World Cup enriched squad data to be available.
    """
    enriched_squads, strengths = _get_wc_enriched_squads()
    if not enriched_squads:
        return _make_error_response("World Cup squad data not available")

    group_preds = compute_group_predictions(strengths)
    bracket = _simulate_knockout(strengths, group_preds, num_simulations=10000)

    # Core DataContract: model_probability (Monte Carlo knockout sim).
    from scoutfootball.worldcup.contracts import (
        build_model_probability_contract,
        contract_to_dict,
        fact_type_for_artifact,
    )

    model_contract = build_model_probability_contract(
        record_count=len(strengths)
    )
    if isinstance(bracket, dict):
        bracket["contracts"] = [contract_to_dict(model_contract)]
        bracket["fact_types"] = [
            fact_type_for_artifact(model_contract.artifact_id).value
        ]
    return _clean_json_value(bracket)


def get_wc_team_outlook(team: str) -> dict:
    """Return a comprehensive tournament outlook for a single World Cup team.

    Aggregates group finish probabilities, projected knockout path,
    championship probability, and squad strength breakdown.
    """
    enriched_squads, strengths = _get_wc_enriched_squads()
    if not enriched_squads:
        return _make_error_response("World Cup squad data not available")
    if team not in strengths:
        return _make_error_response(f"Team '{team}' not found in World Cup data")

    strength_details = _get_wc_strength_details()
    group_preds = compute_group_predictions(strengths)
    bracket = _simulate_knockout(strengths, group_preds, num_simulations=10000)
    outlook = _compute_team_outlook(
        team, strengths, group_preds, bracket, strength_details,
    )
    outlook["squad_balance"] = compute_squad_balance(enriched_squads.get(team, []))
    return _clean_json_value(outlook)


def get_wc_teams() -> dict:
    """Return all 48 World Cup teams with strength ratings and group info."""
    enriched, strengths = _get_wc_enriched_squads()
    strength_details = _get_wc_strength_details()

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
            details = strength_details.get(team, {})
            teams_data.append({
                "team": team,
                "group": letter,
                "is_host": team in HOSTS,
                "strength": round(strengths.get(team, 0), 3),
                "rated_players": len(rated),
                "total_players": len(squad),
                "big5_players": big5_count,
                "avg_rating": avg_rating,
                "coverage": details.get("coverage"),
                "observed_avg_rating": details.get("observed_avg_rating"),
                "proxy_avg_rating": details.get("proxy_avg_rating"),
                "shrunk_avg_rating": details.get("shrunk_avg_rating"),
                "core_avg_rating": details.get("core_avg_rating"),
                "depth_avg_rating": details.get("depth_avg_rating"),
                "reserve_avg_rating": details.get("reserve_avg_rating"),
                "squad_quality_rating": details.get("squad_quality_rating"),
                "rating_score": details.get("rating_score"),
                "opta_score": details.get("opta_score"),
                "league_score": details.get("league_score"),
                "coverage_score": details.get("coverage_score"),
                "big5_score": details.get("big5_score"),
            })

    # Core DataContracts: teams payload combines expected_callup +
    # rating_coverage + model_probability (strength).
    from scoutfootball.worldcup.contracts import (
        build_expected_callups_contract,
        build_model_probability_contract,
        build_rating_coverage_contract,
        contract_to_dict,
        fact_type_for_artifact,
    )
    from scoutfootball.worldcup.data import count_expected_callups

    expected_contract = build_expected_callups_contract(
        record_count=count_expected_callups()
    )
    total_rated = sum(
        1 for s in enriched.values() for p in s if p.has_rating
    )
    rating_contract = build_rating_coverage_contract(record_count=total_rated)
    model_contract = build_model_probability_contract(
        record_count=len(strengths)
    )
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
        "contracts": [
            contract_to_dict(expected_contract),
            contract_to_dict(rating_contract),
            contract_to_dict(model_contract),
        ],
        "fact_types": [
            fact_type_for_artifact(expected_contract.artifact_id).value,
            fact_type_for_artifact(rating_contract.artifact_id).value,
            fact_type_for_artifact(model_contract.artifact_id).value,
        ],
        "teams": teams_data,
    })


# ── Tournament state endpoints ───────────────────────────────────────────


def _wc_tournament_state():
    """Load the current tournament state (lazy-init if no file exists)."""
    from scoutfootball.worldcup.tournament import load_state

    # load_state() returns a fresh init_state() if the default file is missing
    return load_state()


def get_wc_tournament_summary() -> dict:
    """Return a comprehensive summary of the current tournament state."""
    from scoutfootball.worldcup.tournament import (
        get_tournament_state_contract,
        tournament_summary,
    )

    state = _wc_tournament_state()
    summary = tournament_summary(state)
    summary["status"] = "ok"
    # Core DataContract: tournament_state (maintainer-recorded results).
    summary["contracts"] = [get_tournament_state_contract(state)]
    summary["fact_types"] = ["expected_callup"]
    return _clean_json_value(summary)


def get_wc_contracts() -> dict:
    """Return the full Core DataContract registry for the World Cup pack.

    Enumerates every World Cup artifact (schedule, expected_callups,
    rating_coverage, model_probability, tournament_state, plus the
    official_roster and injury_report stubs) so consumers can audit
    the full provenance graph in one request.  Counts are derived from
    live state so the registry is reproducible at any time.
    """
    from scoutfootball.worldcup.contracts import (
        build_worldcup_contract_registry,
        contracts_to_dict,
        fact_type_for_artifact,
    )
    from scoutfootball.worldcup.data import count_expected_callups

    enriched, strengths = _get_wc_enriched_squads()
    total_rated = sum(
        1 for s in enriched.values() for p in s if p.has_rating
    )
    state = _wc_tournament_state()
    knockout_matches = state.knockout.get("matches", []) if state.knockout else []
    completed_knockout = sum(
        1 for m in knockout_matches if m.get("status") == "completed"
    )
    tournament_state_result_count = len(state.results) + completed_knockout

    registry = build_worldcup_contract_registry(
        schedule_match_count=72,
        expected_callups_player_count=count_expected_callups(),
        rating_coverage_player_count=total_rated,
        model_probability_team_count=len(strengths),
        tournament_state_result_count=tournament_state_result_count,
        include_stubs=True,
    )
    contracts = contracts_to_dict(registry)
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.world-cup-contract-registry",
        "version": "1.0.0",
        "count": len(contracts),
        "contracts": contracts,
        "fact_types": [
            fact_type_for_artifact(c["artifact_id"]).value for c in contracts
        ],
        "disclaimer": (
            "Registry enumerates all World Cup artifacts reusing the Core "
            "DataContract type.  Stubs (official_roster, injury_report) are "
            "included so consumers can see what is intentionally absent."
        ),
    })


# ── Recruitment Pack API ─────────────────────────────────────────────────


def _brief_store():
    """Build a BriefStore rooted at the platform report_root/recruitment/briefs."""
    from scoutfootball.recruitment.store import BriefStore

    return BriefStore(_settings().report_root / "recruitment" / "briefs")


def get_recruitment_contracts() -> dict:
    """Return the Core DataContract registry for the Recruitment pack.

    Enumerates recruitment artifacts (briefs, role profiles, decision
    dossiers) that currently have at least one stored record.  Counts
    are derived from live store state so the registry is reproducible.
    """
    from scoutfootball.recruitment.contracts import (
        build_recruitment_contract_registry,
        contracts_to_dict,
        fact_type_for_artifact,
    )

    store = _brief_store()
    brief_count = store.count()

    dossier_store = _dossier_store()
    dossier_count = dossier_store.count()

    registry = build_recruitment_contract_registry(
        brief_count=brief_count,
        role_profile_count=0,
        decision_dossier_count=dossier_count,
    )
    contracts = contracts_to_dict(registry)
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-contract-registry",
        "version": "1.0.0",
        "count": len(contracts),
        "contracts": contracts,
        "fact_types": [
            fact_type_for_artifact(c["artifact_id"]).value for c in contracts
        ],
        "disclaimer": (
            "Registry enumerates recruitment artifacts reusing the Core "
            "DataContract type.  Only artifacts with at least one stored "
            "record are included; absent artifacts are omitted, not stubbed, "
            "because recruitment data is maintainer-authored on demand."
        ),
    })


def get_recruitment_briefs(limit: int = 100) -> dict:
    """List stored recruitment briefs (most recent first)."""
    store = _brief_store()
    records = store.list_records(limit=limit)
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-brief-list",
        "version": "1.0.0",
        "count": len(records),
        "briefs": records,
    })


def get_recruitment_brief(brief_id: str) -> dict:
    """Load one stored recruitment brief by ID."""
    from scoutfootball.recruitment.store import BriefStoreError

    store = _brief_store()
    try:
        record = store.load(brief_id)
    except BriefStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-brief-record",
        "version": "1.0.0",
        "record": record,
    })


def create_recruitment_brief(payload: dict) -> dict:
    """Create a new recruitment brief from a JSON payload.

    The payload must be a valid ``scoutfootball.recruitment-brief`` v1.0.0
    object.  Returns the stored record envelope on success.
    """
    from scoutfootball.recruitment.brief import BriefValidationError
    from scoutfootball.recruitment.store import BriefStoreError

    if not isinstance(payload, dict):
        return _clean_json_value({
            "status": "error",
            "code": "invalid_payload",
            "message": "payload must be a JSON object",
            "http_status": 400,
        })

    brief_id = payload.get("brief_id")
    if not isinstance(brief_id, str) or not brief_id:
        return _clean_json_value({
            "status": "error",
            "code": "missing_brief_id",
            "message": "brief_id is required",
            "http_status": 400,
        })

    store = _brief_store()
    try:
        record = store.save(brief_id, payload, expected_revision=0)
    except BriefValidationError as exc:
        return _clean_json_value({
            "status": "error",
            "code": "validation_error",
            "message": str(exc),
            "http_status": 400,
        })
    except BriefStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
            "metadata": exc.metadata,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-brief-record",
        "version": "1.0.0",
        "record": record,
    })


def list_recruitment_brief_backups(brief_id: str) -> dict:
    """List on-disk backups for one recruitment brief."""
    from scoutfootball.recruitment.store import BriefStoreError

    store = _brief_store()
    try:
        backups = store.list_backups(brief_id)
    except BriefStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-brief-backup-list",
        "version": "1.0.0",
        "brief_id": brief_id,
        "count": len(backups),
        "backups": backups,
    })


def load_recruitment_brief_backup(brief_id: str, backup_filename: str) -> dict:
    """Load one backup record for a recruitment brief."""
    from scoutfootball.recruitment.store import BriefStoreError

    store = _brief_store()
    try:
        record = store.load_backup(brief_id, backup_filename)
    except BriefStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-brief-record",
        "version": "1.0.0",
        "record": record,
    })


def diff_recruitment_brief_versions(
    brief_id: str,
    backup_filename: str | None = None,
) -> dict:
    """Diff the current brief against a backup (or two backups).

    If ``backup_filename`` is provided, the backup is diffed against the
    current on-disk record.  If the current record is missing (e.g. the
    brief was deleted and only a deletion backup remains), the diff is
    ``added`` from None to the backup payload.
    """
    from scoutfootball.recruitment.store import BriefStoreError
    from scoutfootball.storage.record_diff import diff_records

    store = _brief_store()
    try:
        backup_record = store.load_backup(brief_id, backup_filename) if backup_filename else None
    except BriefStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })

    current_record: dict | None
    try:
        current_record = store.load(brief_id)
    except BriefStoreError as exc:
        if exc.code != "brief_not_found":
            return _clean_json_value({
                "status": "error",
                "code": exc.code,
                "message": exc.code,
                "http_status": exc.http_status,
            })
        current_record = None

    if backup_record is None:
        return _clean_json_value({
            "status": "error",
            "code": "backup_filename_required",
            "message": "backup_filename query parameter is required",
            "http_status": 400,
        })

    changes = diff_records(current_record, backup_record)
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-brief-diff",
        "version": "1.0.0",
        "brief_id": brief_id,
        "current_revision": current_record.get("server_revision") if current_record else None,
        "backup_revision": backup_record.get("server_revision"),
        "change_count": len(changes),
        "changes": changes,
    })


def restore_recruitment_brief_from_backup(
    brief_id: str,
    backup_filename: str,
    *,
    expected_revision: int | None = None,
) -> dict:
    """Restore a recruitment brief from a backup, creating a new revision."""
    from scoutfootball.recruitment.store import BriefStoreError

    store = _brief_store()
    try:
        record = store.restore_from_backup(
            brief_id, backup_filename, expected_revision=expected_revision,
        )
    except BriefStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
            "metadata": exc.metadata,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-brief-record",
        "version": "1.0.0",
        "restored_from": backup_filename,
        "record": record,
    })


# ── Recruitment decision dossier API ─────────────────────────────────────


def _dossier_store():
    """Build a DossierStore rooted at report_root/recruitment/dossiers."""
    from scoutfootball.recruitment.dossier_store import DossierStore

    return DossierStore(_settings().report_root / "recruitment" / "dossiers")


def get_decision_dossiers(limit: int = 100) -> dict:
    """List stored decision dossiers (most recent first)."""
    store = _dossier_store()
    records = store.list_records(limit=limit)
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-decision-dossier-list",
        "version": "1.0.0",
        "count": len(records),
        "dossiers": records,
    })


def get_decision_dossier(dossier_id: str) -> dict:
    """Load one stored decision dossier by ID."""
    from scoutfootball.recruitment.dossier_store import DossierStoreError

    store = _dossier_store()
    try:
        record = store.load(dossier_id)
    except DossierStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-decision-dossier-record",
        "version": "1.0.0",
        "record": record,
    })


def create_decision_dossier(payload: dict) -> dict:
    """Create a new decision dossier from a JSON payload.

    The payload must be a valid ``scoutfootball.recruitment-decision-dossier``
    v1.0.0 object.  Returns the stored record envelope on success.
    """
    from scoutfootball.recruitment.dossier import DossierValidationError
    from scoutfootball.recruitment.dossier_store import DossierStoreError

    if not isinstance(payload, dict):
        return _clean_json_value({
            "status": "error",
            "code": "invalid_payload",
            "message": "payload must be a JSON object",
            "http_status": 400,
        })

    dossier_id = payload.get("dossier_id")
    if not isinstance(dossier_id, str) or not dossier_id:
        return _clean_json_value({
            "status": "error",
            "code": "missing_dossier_id",
            "message": "dossier_id is required",
            "http_status": 400,
        })

    store = _dossier_store()
    try:
        record = store.save(dossier_id, payload, expected_revision=0)
    except DossierValidationError as exc:
        return _clean_json_value({
            "status": "error",
            "code": "validation_error",
            "message": str(exc),
            "http_status": 400,
        })
    except DossierStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
            "metadata": exc.metadata,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-decision-dossier-record",
        "version": "1.0.0",
        "record": record,
    })


def list_decision_dossier_backups(dossier_id: str) -> dict:
    """List on-disk backups for one decision dossier."""
    from scoutfootball.recruitment.dossier_store import DossierStoreError

    store = _dossier_store()
    try:
        backups = store.list_backups(dossier_id)
    except DossierStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-decision-dossier-backup-list",
        "version": "1.0.0",
        "dossier_id": dossier_id,
        "count": len(backups),
        "backups": backups,
    })


def load_decision_dossier_backup(dossier_id: str, backup_filename: str) -> dict:
    """Load one backup record for a decision dossier."""
    from scoutfootball.recruitment.dossier_store import DossierStoreError

    store = _dossier_store()
    try:
        record = store.load_backup(dossier_id, backup_filename)
    except DossierStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-decision-dossier-record",
        "version": "1.0.0",
        "record": record,
    })


def diff_decision_dossier_versions(
    dossier_id: str,
    backup_filename: str | None = None,
) -> dict:
    """Diff the current dossier against a backup.

    If the current record is missing (e.g. the dossier was deleted and
    only a deletion backup remains), the diff is ``added`` from None to
    the backup payload.
    """
    from scoutfootball.recruitment.dossier_store import DossierStoreError
    from scoutfootball.storage.record_diff import diff_records

    store = _dossier_store()
    try:
        backup_record = (
            store.load_backup(dossier_id, backup_filename) if backup_filename else None
        )
    except DossierStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })

    current_record: dict | None
    try:
        current_record = store.load(dossier_id)
    except DossierStoreError as exc:
        if exc.code != "dossier_not_found":
            return _clean_json_value({
                "status": "error",
                "code": exc.code,
                "message": exc.code,
                "http_status": exc.http_status,
            })
        current_record = None

    if backup_record is None:
        return _clean_json_value({
            "status": "error",
            "code": "backup_filename_required",
            "message": "backup_filename query parameter is required",
            "http_status": 400,
        })

    changes = diff_records(current_record, backup_record)
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-decision-dossier-diff",
        "version": "1.0.0",
        "dossier_id": dossier_id,
        "current_revision": (
            current_record.get("server_revision") if current_record else None
        ),
        "backup_revision": backup_record.get("server_revision"),
        "change_count": len(changes),
        "changes": changes,
    })


def restore_decision_dossier_from_backup(
    dossier_id: str,
    backup_filename: str,
    *,
    expected_revision: int | None = None,
) -> dict:
    """Restore a decision dossier from a backup, creating a new revision."""
    from scoutfootball.recruitment.dossier_store import DossierStoreError

    store = _dossier_store()
    try:
        record = store.restore_from_backup(
            dossier_id, backup_filename, expected_revision=expected_revision,
        )
    except DossierStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
            "metadata": exc.metadata,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-decision-dossier-record",
        "version": "1.0.0",
        "restored_from": backup_filename,
        "record": record,
    })


def _validate_entry_list(field_name, value, *, entry_id_field, valid_enums=None):
    """Validate the shape and enum values of an entry-list field.

    Returns an error dict (without ``_clean_json_value`` wrapping) if
    early shape checks fail, or ``None`` if the value passes. Detailed
    schema validation (required string fields, id uniqueness, max
    length, evidence_refs shape) is left to the Pydantic model
    re-validation in the store; this helper only catches the most
    common caller mistakes (non-list value, non-dict entry, missing
    id, invalid enum) so callers get fast, specific feedback before
    the current record is loaded.
    """
    if not isinstance(value, list):
        return {
            "status": "error",
            "code": "invalid_field",
            "message": (
                f"{field_name} must be a list of objects "
                f"(got {type(value).__name__})"
            ),
            "http_status": 400,
            "metadata": {"invalid_field": field_name},
        }
    for idx, entry in enumerate(value):
        if not isinstance(entry, dict):
            return {
                "status": "error",
                "code": "invalid_field",
                "message": (
                    f"{field_name}[{idx}] must be an object "
                    f"(got {type(entry).__name__})"
                ),
                "http_status": 400,
                "metadata": {"invalid_field": field_name, "index": idx},
            }
        entry_id = entry.get(entry_id_field)
        if not isinstance(entry_id, str) or not entry_id.strip():
            return {
                "status": "error",
                "code": "invalid_field",
                "message": (
                    f"{field_name}[{idx}].{entry_id_field} must be a "
                    f"non-empty string"
                ),
                "http_status": 400,
                "metadata": {
                    "invalid_field": field_name,
                    "index": idx,
                    "sub_field": entry_id_field,
                },
            }
        if valid_enums:
            for enum_field, allowed in valid_enums.items():
                enum_value = entry.get(enum_field)
                if enum_value is None:
                    continue
                if enum_value not in allowed:
                    return {
                        "status": "error",
                        "code": "invalid_field",
                        "message": (
                            f"{field_name}[{idx}].{enum_field}="
                            f"{enum_value!r} is not one of "
                            f"{sorted(allowed)}"
                        ),
                        "http_status": 400,
                        "metadata": {
                            "invalid_field": field_name,
                            "index": idx,
                            "sub_field": enum_field,
                        },
                    }
    return None


# Editable fields for a decision dossier. The update API only accepts keys
# in this set; everything else (schema, version, dossier_id, limitations,
# linked_artifacts, etc.) is preserved from the current revision and cannot
# be mutated through this endpoint. The entry-list fields (supporting_evidence,
# counter_evidence, comparisons, risks) use full-list replacement semantics:
# the caller sends the complete new list and the model re-validates each
# entry's schema, id uniqueness and enum values (fact_tier / severity).
_DOSSIER_EDITABLE_FIELDS = frozenset({
    "title",
    "brief_id",
    "candidate_player_name",
    "candidate_team_name",
    "human_opinion",
    "recommendation",
    "status",
    "decision",
    "decision_note",
    "notes",
    "supporting_evidence",
    "counter_evidence",
    "comparisons",
    "risks",
})


def update_decision_dossier(
    dossier_id: str,
    fields: dict,
    *,
    expected_revision: int,
) -> dict:
    """Apply a partial update to a decision dossier, creating a new revision.

    ``fields`` may contain any subset of :data:`_DOSSIER_EDITABLE_FIELDS`.
    Keys outside that set are rejected with ``invalid_field`` so the
    endpoint cannot be used to mutate schema/version/dossier_id/
    limitations/linked_artifacts/etc. The entry-list fields
    (supporting_evidence, counter_evidence, comparisons, risks) ARE
    editable and use full-list replacement semantics: the caller sends
    the complete new list and the model re-validates each entry's
    schema, id uniqueness and enum values (fact_tier / severity).

    The current record is loaded, the editable fields are merged in, the
    ``revision`` is bumped and ``updated_at`` is refreshed, then the
    merged payload is saved with ``expected_revision`` (If-Match style).
    The store handles backup creation and atomic write.
    """
    from scoutfootball.recruitment.dossier import (
        VALID_DECISION_VALUES,
        VALID_DOSSIER_STATUS,
        DossierValidationError,
    )
    from scoutfootball.recruitment.dossier import (
        VALID_FACT_TIERS as DOSSIER_VALID_FACT_TIERS,
    )
    from scoutfootball.recruitment.dossier import (
        VALID_RISK_SEVERITY as DOSSIER_VALID_RISK_SEVERITY,
    )
    from scoutfootball.recruitment.dossier_store import DossierStoreError

    if not isinstance(fields, dict):
        return _clean_json_value({
            "status": "error",
            "code": "invalid_payload",
            "message": "fields must be a JSON object",
            "http_status": 400,
        })

    # Reject any field the update API does not own. This keeps the
    # endpoint's surface explicit and prevents callers from silently
    # mutating schema/version/evidence through merge.
    invalid_keys = set(fields.keys()) - _DOSSIER_EDITABLE_FIELDS
    if invalid_keys:
        return _clean_json_value({
            "status": "error",
            "code": "invalid_field",
            "message": (
                "fields must be a subset of: "
                + ", ".join(sorted(_DOSSIER_EDITABLE_FIELDS))
            ),
            "http_status": 400,
            "metadata": {"invalid_fields": sorted(invalid_keys)},
        })

    # Validate status / decision enum values before loading the current
    # record so callers get fast, specific feedback.
    if "status" in fields:
        if fields["status"] not in VALID_DOSSIER_STATUS:
            return _clean_json_value({
                "status": "error",
                "code": "invalid_status",
                "message": (
                    f"invalid status: {fields['status']!r} "
                    f"(must be one of {sorted(VALID_DOSSIER_STATUS)})"
                ),
                "http_status": 400,
            })
    if "decision" in fields and fields["decision"] is not None:
        if fields["decision"] not in VALID_DECISION_VALUES:
            return _clean_json_value({
                "status": "error",
                "code": "invalid_decision",
                "message": (
                    f"invalid decision: {fields['decision']!r} "
                    f"(must be one of {sorted(VALID_DECISION_VALUES)} or null)"
                ),
                "http_status": 400,
            })

    # Early shape/enum validation for entry-list fields. The Pydantic
    # model re-validates each entry's full schema (required fields, id
    # uniqueness, max length, evidence_refs shape) when the store saves;
    # these checks just give callers fast, specific feedback for the
    # most common mistakes (non-list value, non-dict entry, missing id,
    # invalid enum) before the current record is loaded.
    _dossier_entry_list_specs = {
        "supporting_evidence": (
            "evidence_id", {"fact_tier": DOSSIER_VALID_FACT_TIERS},
        ),
        "counter_evidence": (
            "evidence_id", {"fact_tier": DOSSIER_VALID_FACT_TIERS},
        ),
        "comparisons": (
            "comparison_id", {"fact_tier": DOSSIER_VALID_FACT_TIERS},
        ),
        "risks": (
            "risk_id",
            {
                "fact_tier": DOSSIER_VALID_FACT_TIERS,
                "severity": DOSSIER_VALID_RISK_SEVERITY,
            },
        ),
    }
    for list_field, (id_field, enum_map) in _dossier_entry_list_specs.items():
        if list_field in fields:
            err = _validate_entry_list(
                list_field,
                fields[list_field],
                entry_id_field=id_field,
                valid_enums=enum_map,
            )
            if err is not None:
                return _clean_json_value(err)

    store = _dossier_store()
    try:
        current_record = store.load(dossier_id)
    except DossierStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })

    current_dossier = current_record["dossier"]
    merged = dict(current_dossier)
    merged.update(fields)

    # The DecisionDossier model_validator requires:
    #   - status='decided' => decision != null
    #   - status != 'decided' => decision is null
    # If the caller moves status to 'decided' without providing a
    # decision, reject early with a clear code. If the caller moves
    # status away from 'decided' but leaves a decision, also reject.
    merged_status = merged.get("status")
    merged_decision = merged.get("decision")
    if merged_status == "decided" and not merged_decision:
        return _clean_json_value({
            "status": "error",
            "code": "decision_required",
            "message": (
                "decision is required when status is 'decided' "
                f"(one of: {sorted(VALID_DECISION_VALUES)})"
            ),
            "http_status": 400,
        })
    if merged_status != "decided" and merged_decision is not None:
        return _clean_json_value({
            "status": "error",
            "code": "decision_not_allowed",
            "message": (
                f"decision can only be set when status='decided' "
                f"(got status={merged_status!r}, decision={merged_decision!r})"
            ),
            "http_status": 400,
        })

    # Bump revision + updated_at. The store re-validates via the model,
    # so this is convenience, not a security boundary.
    merged["revision"] = int(current_dossier.get("revision", 1)) + 1
    merged["updated_at"] = _utc_now_iso_helper()

    try:
        record = store.save(
            dossier_id, merged, expected_revision=expected_revision,
        )
    except DossierValidationError as exc:
        return _clean_json_value({
            "status": "error",
            "code": "validation_error",
            "message": str(exc),
            "http_status": 400,
        })
    except DossierStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
            "metadata": exc.metadata,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.recruitment-decision-dossier-record",
        "version": "1.0.0",
        "record": record,
    })


# ── Opposition & Match Pack API ─────────────────────────────────────────


def _briefing_store():
    """Build a BriefingStore rooted at report_root/opposition/briefings."""
    from scoutfootball.opposition.store import BriefingStore

    return BriefingStore(_settings().report_root / "opposition" / "briefings")


def get_opposition_contracts() -> dict:
    """Return the Core DataContract registry for the Opposition pack."""
    from scoutfootball.opposition.contracts import (
        build_opposition_contract_registry,
        contracts_to_dict,
        fact_type_for_artifact,
    )

    store = _briefing_store()
    briefing_count = store.count()

    review_store = _review_store()
    review_count = review_store.count()

    registry = build_opposition_contract_registry(
        briefing_count=briefing_count,
        post_match_review_count=review_count,
    )
    contracts = contracts_to_dict(registry)
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-contract-registry",
        "version": "1.0.0",
        "count": len(contracts),
        "contracts": contracts,
        "fact_types": [
            fact_type_for_artifact(c["artifact_id"]).value for c in contracts
        ],
        "disclaimer": (
            "Registry enumerates opposition & match artifacts reusing the "
            "Core DataContract type.  Only artifacts with at least one "
            "stored record are included; absent artifacts are omitted, not "
            "stubbed, because opposition data is maintainer-authored on "
            "demand."
        ),
    })


def get_opposition_briefings(limit: int = 100) -> dict:
    """List stored source-limited match briefings (most recent first)."""
    store = _briefing_store()
    records = store.list_records(limit=limit)
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-briefing-list",
        "version": "1.0.0",
        "count": len(records),
        "briefings": records,
    })


def get_opposition_briefing(briefing_id: str) -> dict:
    """Load one stored match briefing by ID."""
    from scoutfootball.opposition.store import BriefingStoreError

    store = _briefing_store()
    try:
        record = store.load(briefing_id)
    except BriefingStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-briefing-record",
        "version": "1.0.0",
        "record": record,
    })


def create_opposition_briefing(payload: dict) -> dict:
    """Create a new source-limited match briefing from a JSON payload.

    The payload must be a valid ``scoutfootball.opposition-briefing``
    v1.0.0 object.  Returns the stored record envelope on success.
    """
    from scoutfootball.opposition.briefing import BriefingValidationError
    from scoutfootball.opposition.store import BriefingStoreError

    if not isinstance(payload, dict):
        return _clean_json_value({
            "status": "error",
            "code": "invalid_payload",
            "message": "payload must be a JSON object",
            "http_status": 400,
        })

    briefing_id = payload.get("briefing_id")
    if not isinstance(briefing_id, str) or not briefing_id:
        return _clean_json_value({
            "status": "error",
            "code": "missing_briefing_id",
            "message": "briefing_id is required",
            "http_status": 400,
        })

    store = _briefing_store()
    try:
        record = store.save(briefing_id, payload, expected_revision=0)
    except BriefingValidationError as exc:
        return _clean_json_value({
            "status": "error",
            "code": "validation_error",
            "message": str(exc),
            "http_status": 400,
        })
    except BriefingStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
            "metadata": exc.metadata,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-briefing-record",
        "version": "1.0.0",
        "record": record,
    })


def list_opposition_briefing_backups(briefing_id: str) -> dict:
    """List on-disk backups for one match briefing."""
    from scoutfootball.opposition.store import BriefingStoreError

    store = _briefing_store()
    try:
        backups = store.list_backups(briefing_id)
    except BriefingStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-briefing-backup-list",
        "version": "1.0.0",
        "briefing_id": briefing_id,
        "count": len(backups),
        "backups": backups,
    })


def load_opposition_briefing_backup(briefing_id: str, backup_filename: str) -> dict:
    """Load one backup record for a match briefing."""
    from scoutfootball.opposition.store import BriefingStoreError

    store = _briefing_store()
    try:
        record = store.load_backup(briefing_id, backup_filename)
    except BriefingStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-briefing-record",
        "version": "1.0.0",
        "record": record,
    })


def diff_opposition_briefing_versions(
    briefing_id: str,
    backup_filename: str | None = None,
) -> dict:
    """Diff the current briefing against a backup."""
    from scoutfootball.opposition.store import BriefingStoreError
    from scoutfootball.storage.record_diff import diff_records

    store = _briefing_store()
    try:
        backup_record = (
            store.load_backup(briefing_id, backup_filename) if backup_filename else None
        )
    except BriefingStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })

    current_record: dict | None
    try:
        current_record = store.load(briefing_id)
    except BriefingStoreError as exc:
        if exc.code != "briefing_not_found":
            return _clean_json_value({
                "status": "error",
                "code": exc.code,
                "message": exc.code,
                "http_status": exc.http_status,
            })
        current_record = None

    if backup_record is None:
        return _clean_json_value({
            "status": "error",
            "code": "backup_filename_required",
            "message": "backup_filename query parameter is required",
            "http_status": 400,
        })

    changes = diff_records(current_record, backup_record)
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-briefing-diff",
        "version": "1.0.0",
        "briefing_id": briefing_id,
        "current_revision": current_record.get("server_revision") if current_record else None,
        "backup_revision": backup_record.get("server_revision"),
        "change_count": len(changes),
        "changes": changes,
    })


def restore_opposition_briefing_from_backup(
    briefing_id: str,
    backup_filename: str,
    *,
    expected_revision: int | None = None,
) -> dict:
    """Restore a match briefing from a backup, creating a new revision."""
    from scoutfootball.opposition.store import BriefingStoreError

    store = _briefing_store()
    try:
        record = store.restore_from_backup(
            briefing_id, backup_filename, expected_revision=expected_revision,
        )
    except BriefingStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
            "metadata": exc.metadata,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-briefing-record",
        "version": "1.0.0",
        "restored_from": backup_filename,
        "record": record,
    })


# ── Opposition post-match review API ─────────────────────────────────────


def _review_store():
    """Build a ReviewStore rooted at report_root/opposition/reviews."""
    from scoutfootball.opposition.post_match_review_store import ReviewStore

    return ReviewStore(_settings().report_root / "opposition" / "reviews")


def get_post_match_reviews(limit: int = 100) -> dict:
    """List stored post-match reviews (most recent first)."""
    store = _review_store()
    records = store.list_records(limit=limit)
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-post-match-review-list",
        "version": "1.0.0",
        "count": len(records),
        "reviews": records,
    })


def get_post_match_review(review_id: str) -> dict:
    """Load one stored post-match review by ID."""
    from scoutfootball.opposition.post_match_review_store import ReviewStoreError

    store = _review_store()
    try:
        record = store.load(review_id)
    except ReviewStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-post-match-review-record",
        "version": "1.0.0",
        "record": record,
    })


def create_post_match_review(payload: dict) -> dict:
    """Create a new post-match review from a JSON payload.

    The payload must be a valid ``scoutfootball.opposition-post-match-review``
    v1.0.0 object.  Returns the stored record envelope on success.
    """
    from scoutfootball.opposition.post_match_review import ReviewValidationError
    from scoutfootball.opposition.post_match_review_store import ReviewStoreError

    if not isinstance(payload, dict):
        return _clean_json_value({
            "status": "error",
            "code": "invalid_payload",
            "message": "payload must be a JSON object",
            "http_status": 400,
        })

    review_id = payload.get("review_id")
    if not isinstance(review_id, str) or not review_id:
        return _clean_json_value({
            "status": "error",
            "code": "missing_review_id",
            "message": "review_id is required",
            "http_status": 400,
        })

    store = _review_store()
    try:
        record = store.save(review_id, payload, expected_revision=0)
    except ReviewValidationError as exc:
        return _clean_json_value({
            "status": "error",
            "code": "validation_error",
            "message": str(exc),
            "http_status": 400,
        })
    except ReviewStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
            "metadata": exc.metadata,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-post-match-review-record",
        "version": "1.0.0",
        "record": record,
    })


def list_post_match_review_backups(review_id: str) -> dict:
    """List on-disk backups for one post-match review."""
    from scoutfootball.opposition.post_match_review_store import ReviewStoreError

    store = _review_store()
    try:
        backups = store.list_backups(review_id)
    except ReviewStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-post-match-review-backup-list",
        "version": "1.0.0",
        "review_id": review_id,
        "count": len(backups),
        "backups": backups,
    })


def load_post_match_review_backup(review_id: str, backup_filename: str) -> dict:
    """Load one backup record for a post-match review."""
    from scoutfootball.opposition.post_match_review_store import ReviewStoreError

    store = _review_store()
    try:
        record = store.load_backup(review_id, backup_filename)
    except ReviewStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-post-match-review-record",
        "version": "1.0.0",
        "record": record,
    })


def diff_post_match_review_versions(
    review_id: str,
    backup_filename: str | None = None,
) -> dict:
    """Diff the current review against a backup.

    If the current record is missing (e.g. the review was deleted and
    only a deletion backup remains), the diff is ``added`` from None to
    the backup payload.
    """
    from scoutfootball.opposition.post_match_review_store import ReviewStoreError
    from scoutfootball.storage.record_diff import diff_records

    store = _review_store()
    try:
        backup_record = (
            store.load_backup(review_id, backup_filename) if backup_filename else None
        )
    except ReviewStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })

    current_record: dict | None
    try:
        current_record = store.load(review_id)
    except ReviewStoreError as exc:
        if exc.code != "review_not_found":
            return _clean_json_value({
                "status": "error",
                "code": exc.code,
                "message": exc.code,
                "http_status": exc.http_status,
            })
        current_record = None

    if backup_record is None:
        return _clean_json_value({
            "status": "error",
            "code": "backup_filename_required",
            "message": "backup_filename query parameter is required",
            "http_status": 400,
        })

    changes = diff_records(current_record, backup_record)
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-post-match-review-diff",
        "version": "1.0.0",
        "review_id": review_id,
        "current_revision": (
            current_record.get("server_revision") if current_record else None
        ),
        "backup_revision": backup_record.get("server_revision"),
        "change_count": len(changes),
        "changes": changes,
    })


def restore_post_match_review_from_backup(
    review_id: str,
    backup_filename: str,
    *,
    expected_revision: int | None = None,
) -> dict:
    """Restore a post-match review from a backup, creating a new revision."""
    from scoutfootball.opposition.post_match_review_store import ReviewStoreError

    store = _review_store()
    try:
        record = store.restore_from_backup(
            review_id, backup_filename, expected_revision=expected_revision,
        )
    except ReviewStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
            "metadata": exc.metadata,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-post-match-review-record",
        "version": "1.0.0",
        "restored_from": backup_filename,
        "record": record,
    })


# Editable fields for a post-match review. The update API only accepts
# keys in this set; everything else (schema, version, review_id,
# hypothesis_results, falsified_patterns, new_questions, evidence,
# linked_artifacts, limitations, etc.) is preserved from the current
# revision and cannot be mutated through this endpoint. The entry-list
# fields (hypothesis_results, falsified_patterns, new_questions,
# supporting_evidence, counter_evidence) use full-list replacement
# semantics: the caller sends the complete new list and the model
# re-validates each entry's schema, id uniqueness and enum values
# (fact_tier / severity / outcome).
_REVIEW_EDITABLE_FIELDS = frozenset({
    "title",
    "briefing_id",
    "match_id",
    "home_team",
    "away_team",
    "competition",
    "season",
    "final_score_home",
    "final_score_away",
    "human_opinion",
    "recommendation",
    "status",
    "decision",
    "decision_note",
    "notes",
    "hypothesis_results",
    "falsified_patterns",
    "new_questions",
    "supporting_evidence",
    "counter_evidence",
})


def update_post_match_review(
    review_id: str,
    fields: dict,
    *,
    expected_revision: int,
) -> dict:
    """Apply a partial update to a post-match review, creating a new revision.

    ``fields`` may contain any subset of :data:`_REVIEW_EDITABLE_FIELDS`.
    Keys outside that set are rejected with ``invalid_field`` so the
    endpoint cannot be used to mutate schema/version/review_id/
    limitations/linked_artifacts/etc. The entry-list fields
    (hypothesis_results, falsified_patterns, new_questions,
    supporting_evidence, counter_evidence) ARE editable and use
    full-list replacement semantics: the caller sends the complete new
    list and the model re-validates each entry's schema, id uniqueness
    and enum values (fact_tier / severity / outcome).

    The current record is loaded, the editable fields are merged in, the
    ``revision`` is bumped and ``updated_at`` is refreshed, then the
    merged payload is saved with ``expected_revision`` (If-Match style).
    The store handles backup creation and atomic write.
    """
    from scoutfootball.opposition.post_match_review import (
        VALID_FACT_TIERS as REVIEW_VALID_FACT_TIERS,
    )
    from scoutfootball.opposition.post_match_review import (
        VALID_HYPOTHESIS_OUTCOMES,
        VALID_REVIEW_DECISIONS,
        VALID_REVIEW_STATUS,
        ReviewValidationError,
    )
    from scoutfootball.opposition.post_match_review import (
        VALID_RISK_SEVERITY as REVIEW_VALID_RISK_SEVERITY,
    )
    from scoutfootball.opposition.post_match_review_store import ReviewStoreError

    if not isinstance(fields, dict):
        return _clean_json_value({
            "status": "error",
            "code": "invalid_payload",
            "message": "fields must be a JSON object",
            "http_status": 400,
        })

    # Reject any field the update API does not own. This keeps the
    # endpoint's surface explicit and prevents callers from silently
    # mutating schema/version/evidence through merge.
    invalid_keys = set(fields.keys()) - _REVIEW_EDITABLE_FIELDS
    if invalid_keys:
        return _clean_json_value({
            "status": "error",
            "code": "invalid_field",
            "message": (
                "fields must be a subset of: "
                + ", ".join(sorted(_REVIEW_EDITABLE_FIELDS))
            ),
            "http_status": 400,
            "metadata": {"invalid_fields": sorted(invalid_keys)},
        })

    # Validate status / decision enum values before loading the current
    # record so callers get fast, specific feedback.
    if "status" in fields:
        if fields["status"] not in VALID_REVIEW_STATUS:
            return _clean_json_value({
                "status": "error",
                "code": "invalid_status",
                "message": (
                    f"invalid status: {fields['status']!r} "
                    f"(must be one of {sorted(VALID_REVIEW_STATUS)})"
                ),
                "http_status": 400,
            })
    if "decision" in fields and fields["decision"] is not None:
        if fields["decision"] not in VALID_REVIEW_DECISIONS:
            return _clean_json_value({
                "status": "error",
                "code": "invalid_decision",
                "message": (
                    f"invalid decision: {fields['decision']!r} "
                    f"(must be one of {sorted(VALID_REVIEW_DECISIONS)} or null)"
                ),
                "http_status": 400,
            })
    if "final_score_home" in fields and fields["final_score_home"] is not None:
        if not isinstance(fields["final_score_home"], int) or fields["final_score_home"] < 0:
            return _clean_json_value({
                "status": "error",
                "code": "invalid_score",
                "message": "final_score_home must be a non-negative integer or null",
                "http_status": 400,
            })
    if "final_score_away" in fields and fields["final_score_away"] is not None:
        if not isinstance(fields["final_score_away"], int) or fields["final_score_away"] < 0:
            return _clean_json_value({
                "status": "error",
                "code": "invalid_score",
                "message": "final_score_away must be a non-negative integer or null",
                "http_status": 400,
            })

    # Early shape/enum validation for entry-list fields. The Pydantic
    # model re-validates each entry's full schema (required fields, id
    # uniqueness, max length, evidence_refs shape) when the store saves;
    # these checks just give callers fast, specific feedback for the
    # most common mistakes (non-list value, non-dict entry, missing id,
    # invalid enum) before the current record is loaded.
    _review_entry_list_specs = {
        "hypothesis_results": (
            "hypothesis_id",
            {
                "outcome": VALID_HYPOTHESIS_OUTCOMES,
                "fact_tier": REVIEW_VALID_FACT_TIERS,
            },
        ),
        "falsified_patterns": (
            "pattern_id",
            {
                "severity": REVIEW_VALID_RISK_SEVERITY,
                "fact_tier": REVIEW_VALID_FACT_TIERS,
            },
        ),
        "new_questions": (
            "question_id", {"fact_tier": REVIEW_VALID_FACT_TIERS},
        ),
        "supporting_evidence": (
            "evidence_id", {"fact_tier": REVIEW_VALID_FACT_TIERS},
        ),
        "counter_evidence": (
            "evidence_id", {"fact_tier": REVIEW_VALID_FACT_TIERS},
        ),
    }
    for list_field, (id_field, enum_map) in _review_entry_list_specs.items():
        if list_field in fields:
            err = _validate_entry_list(
                list_field,
                fields[list_field],
                entry_id_field=id_field,
                valid_enums=enum_map,
            )
            if err is not None:
                return _clean_json_value(err)

    store = _review_store()
    try:
        current_record = store.load(review_id)
    except ReviewStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })

    current_review = current_record["review"]
    merged = dict(current_review)
    merged.update(fields)

    # The PostMatchReview model_validator requires:
    #   - status='finalized' => decision != null
    #   - status != 'finalized' => decision is null
    # If the caller moves status to 'finalized' without providing a
    # decision, reject early with a clear code. If the caller moves
    # status away from 'finalized' but leaves a decision, also reject.
    merged_status = merged.get("status")
    merged_decision = merged.get("decision")
    if merged_status == "finalized" and not merged_decision:
        return _clean_json_value({
            "status": "error",
            "code": "decision_required",
            "message": (
                "decision is required when status is 'finalized' "
                "(one of: confirmed, falsified, partial, inconclusive)"
            ),
            "http_status": 400,
        })
    if merged_status != "finalized" and merged_decision is not None:
        return _clean_json_value({
            "status": "error",
            "code": "decision_not_allowed",
            "message": (
                f"decision can only be set when status='finalized' "
                f"(got status={merged_status!r}, decision={merged_decision!r})"
            ),
            "http_status": 400,
        })

    # Bump revision + updated_at. The store re-validates via the model,
    # so this is convenience, not a security boundary.
    merged["revision"] = int(current_review.get("revision", 1)) + 1
    merged["updated_at"] = _utc_now_iso_helper()

    try:
        record = store.save(
            review_id, merged, expected_revision=expected_revision,
        )
    except ReviewValidationError as exc:
        return _clean_json_value({
            "status": "error",
            "code": "validation_error",
            "message": str(exc),
            "http_status": 400,
        })
    except ReviewStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
            "metadata": exc.metadata,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-post-match-review-record",
        "version": "1.0.0",
        "record": record,
    })


# Editable fields for an opposition briefing. The update API only accepts
# keys in this set; everything else (schema, version, briefing_id,
# revision, created_at, updated_at, author, limitations, etc.) is
# preserved from the current revision and cannot be mutated through
# this endpoint. The entry-list field ``sections`` uses full-list
# replacement semantics: the caller sends the complete new list and
# the model re-validates each entry's schema, ``section_id`` uniqueness
# and ``fact_tier`` enum value. The briefing model has no
# status/decision state machine (unlike dossier/review), so the
# consistency checks are limited to shape and enum validation.
_BRIEFING_EDITABLE_FIELDS = frozenset({
    "title",
    "home_team",
    "away_team",
    "match_id",
    "kickoff_at",
    "competition",
    "season",
    "sections",
    "linked_pattern_card_ids",
    "linked_scenario_tree_id",
    "linked_post_match_review_id",
    "notes",
})


def update_opposition_briefing(
    briefing_id: str,
    fields: dict,
    *,
    expected_revision: int,
) -> dict:
    """Apply a partial update to an opposition briefing, creating a new revision.

    ``fields`` may contain any subset of :data:`_BRIEFING_EDITABLE_FIELDS`.
    Keys outside that set are rejected with ``invalid_field`` so the
    endpoint cannot be used to mutate schema/version/briefing_id/
    revision/created_at/updated_at/author/limitations through merge.
    The entry-list field ``sections`` IS editable and uses full-list
    replacement semantics: the caller sends the complete new list and
    the model re-validates each entry's schema, ``section_id``
    uniqueness (including the ``custom:<tail>`` rule) and ``fact_tier``
    enum value.

    The briefing model has no status/decision state machine (unlike the
    decision dossier and post-match review), so this endpoint does not
    perform decision-consistency checks. ``kickoff_at`` accepts an ISO
    8601 datetime string or null; ``linked_scenario_tree_id`` /
    ``linked_post_match_review_id`` accept a string or null;
    ``linked_pattern_card_ids`` accepts a list of strings. These are
    re-validated by the Pydantic model when the store saves.

    The current record is loaded, the editable fields are merged in, the
    ``revision`` is bumped and ``updated_at`` is refreshed, then the
    merged payload is saved with ``expected_revision`` (If-Match style).
    The store handles backup creation and atomic write.
    """
    from scoutfootball.opposition.briefing import (
        VALID_FACT_TIERS as BRIEFING_VALID_FACT_TIERS,
    )
    from scoutfootball.opposition.briefing import BriefingValidationError
    from scoutfootball.opposition.store import BriefingStoreError

    if not isinstance(fields, dict):
        return _clean_json_value({
            "status": "error",
            "code": "invalid_payload",
            "message": "fields must be a JSON object",
            "http_status": 400,
        })

    # Reject any field the update API does not own. This keeps the
    # endpoint's surface explicit and prevents callers from silently
    # mutating schema/version/briefing_id/limitations through merge.
    invalid_keys = set(fields.keys()) - _BRIEFING_EDITABLE_FIELDS
    if invalid_keys:
        return _clean_json_value({
            "status": "error",
            "code": "invalid_field",
            "message": (
                "fields must be a subset of: "
                + ", ".join(sorted(_BRIEFING_EDITABLE_FIELDS))
            ),
            "http_status": 400,
            "metadata": {"invalid_fields": sorted(invalid_keys)},
        })

    # Early shape/enum validation for the ``sections`` entry-list field.
    # The Pydantic model re-validates each entry's full schema (required
    # section_id, custom section_id tail pattern, fact_tier enum, summary
    # max length, evidence_refs shape, section_id uniqueness) when the
    # store saves; these checks just give callers fast, specific feedback
    # for the most common mistakes (non-list value, non-dict entry,
    # missing section_id, invalid fact_tier) before the current record is
    # loaded.
    if "sections" in fields:
        err = _validate_entry_list(
            "sections",
            fields["sections"],
            entry_id_field="section_id",
            valid_enums={"fact_tier": BRIEFING_VALID_FACT_TIERS},
        )
        if err is not None:
            return _clean_json_value(err)

    store = _briefing_store()
    try:
        current_record = store.load(briefing_id)
    except BriefingStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
        })

    current_briefing = current_record["briefing"]
    merged = dict(current_briefing)
    merged.update(fields)

    # Bump revision + updated_at. The store re-validates via the model,
    # so this is convenience, not a security boundary.
    merged["revision"] = int(current_briefing.get("revision", 1)) + 1
    merged["updated_at"] = _utc_now_iso_helper()

    try:
        record = store.save(
            briefing_id, merged, expected_revision=expected_revision,
        )
    except BriefingValidationError as exc:
        return _clean_json_value({
            "status": "error",
            "code": "validation_error",
            "message": str(exc),
            "http_status": 400,
        })
    except BriefingStoreError as exc:
        return _clean_json_value({
            "status": "error",
            "code": exc.code,
            "message": exc.code,
            "http_status": exc.http_status,
            "metadata": exc.metadata,
        })
    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.opposition-briefing-record",
        "version": "1.0.0",
        "record": record,
    })


def export_local_pack() -> dict:
    """Bundle all local personal artifacts into a portable offline pack.

    The pack is a single JSON document with a manifest, hashes and the
    full records for every recruitment brief and opposition briefing
    stored under ``report_root``.  It is intended for offline backup,
    migration to a new machine, or hand-off to another reviewer via
    file transfer.  No cloud, no account, no telemetry.

    The pack schema is ``scoutfootball.portable-pack`` v1.0.0.  Each
    section carries its own schema/version so consumers can validate
    individual sections without parsing the whole pack.
    """
    import hashlib
    import json

    brief_store = _brief_store()
    briefing_store = _briefing_store()

    brief_records = brief_store.list_records(limit=100)
    briefing_records = briefing_store.list_records(limit=100)

    # Pull full records for each summary entry, skipping any that fail
    # to load (corrupted records are reported in ``skipped`` but do not
    # abort the export).
    full_briefs: list[dict] = []
    skipped_briefs: list[dict] = []
    seen_brief_ids: set[str] = set()
    for summary in brief_records:
        brief_id = summary.get("brief_id")
        if brief_id:
            seen_brief_ids.add(brief_id)
        try:
            full_briefs.append(brief_store.load(brief_id))
        except Exception as exc:  # noqa: BLE001 — report, don't crash export
            logger.warning("export_local_pack: brief load failed", exc_info=True)
            skipped_briefs.append({
                "brief_id": brief_id,
                "reason": str(exc) or type(exc).__name__,
            })

    # ``list_records`` silently skips files that fail to parse, so corrupt
    # JSON files would otherwise vanish from the export without a trace.
    # Detect them by globbing the store root directly and reporting any
    # ``*.json`` file whose stem is not in ``seen_brief_ids``.
    if brief_store.root.exists():
        for path in brief_store.root.glob("*.json"):
            stem = path.stem
            if stem not in seen_brief_ids:
                logger.warning(
                    "export_local_pack: corrupt brief file skipped: %s",
                    path,
                )
                skipped_briefs.append({
                    "brief_id": stem,
                    "reason": "file failed to parse (corrupt JSON or schema violation)",
                })

    full_briefings: list[dict] = []
    skipped_briefings: list[dict] = []
    seen_briefing_ids: set[str] = set()
    for summary in briefing_records:
        briefing_id = summary.get("briefing_id")
        if briefing_id:
            seen_briefing_ids.add(briefing_id)
        try:
            full_briefings.append(briefing_store.load(briefing_id))
        except Exception as exc:  # noqa: BLE001 — report, don't crash export
            logger.warning("export_local_pack: briefing load failed", exc_info=True)
            skipped_briefings.append({
                "briefing_id": briefing_id,
                "reason": str(exc) or type(exc).__name__,
            })

    if briefing_store.root.exists():
        for path in briefing_store.root.glob("*.json"):
            stem = path.stem
            if stem not in seen_briefing_ids:
                logger.warning(
                    "export_local_pack: corrupt briefing file skipped: %s",
                    path,
                )
                skipped_briefings.append({
                    "briefing_id": stem,
                    "reason": "file failed to parse (corrupt JSON or schema violation)",
                })

    sections = {
        "recruitment_briefs": {
            "schema": "scoutfootball.recruitment-brief-record",
            "version": "1.0.0",
            "count": len(full_briefs),
            "records": full_briefs,
        },
        "opposition_briefings": {
            "schema": "scoutfootball.opposition-briefing-record",
            "version": "1.0.0",
            "count": len(full_briefings),
            "records": full_briefings,
        },
    }

    # Stable per-section SHA-256 over the canonical JSON of each section
    # (sorted keys, no ASCII escaping, 2-space indent).  Used by
    # importers to detect in-transit corruption.
    section_hashes: dict[str, str] = {}
    for name, section in sections.items():
        canonical = json.dumps(section, ensure_ascii=False, sort_keys=True, indent=2)
        section_hashes[name] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    pack = {
        "schema": "scoutfootball.portable-pack",
        "version": "1.0.0",
        "exported_at": _utc_now_iso_helper(),
        "app_version": _app_version_helper(),
        "sections": sections,
        "section_hashes": section_hashes,
        "skipped": {
            "recruitment_briefs": skipped_briefs,
            "opposition_briefings": skipped_briefings,
        },
        "license_summary": _portable_pack_license_summary(),
    }
    return _clean_json_value({
        "status": "ok",
        "pack": pack,
    })


_PORTABLE_PACK_SCHEMA = "scoutfootball.portable-pack"
_PORTABLE_PACK_VERSION = "1.0.0"
_PORTABLE_PACK_SECTIONS = ("recruitment_briefs", "opposition_briefings")
_PORTABLE_PACK_MAX_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB hard cap


def import_local_pack(pack: dict, *, overwrite: bool = False) -> dict:
    """Import a portable pack into the local stores.

    Mirrors :func:`export_local_pack`: the ``pack`` argument is the inner
    ``pack`` object from an export response (``response["pack"]``). The
    function writes each section's records into the corresponding local
    store via the standard ``save()`` API, so revision history and backup
    semantics are preserved.

    Failure model (three tiers):

    1. **Pack-level (fail-closed)**: unknown schema, unsupported version,
       or missing mandatory keys reject the entire pack. No records are
       written.
    2. **Section-level (fail-closed per section)**: ``section_hashes``
       mismatch indicates in-transit corruption; the entire section is
       skipped and reported in ``section_errors``. Other sections are
       still imported.
    3. **Record-level (fail-soft)**: a record that fails validation or
       conflicts with an existing local ID is reported in ``skipped`` or
       ``conflicts`` and does not abort the import. This matches
       :func:`export_local_pack`'s behavior of skipping corrupt records
       rather than aborting the export.

    Conflict handling:

    - ``overwrite=False`` (default): records whose ID already exists
      locally are reported in ``conflicts`` and not modified. This is the
      safe default for "merge pack into existing local store".
    - ``overwrite=True``: existing local records are replaced by calling
      ``save(id, payload, expected_revision=current_revision)``, which
      bumps ``server_revision`` and creates a revision backup. This is
      the appropriate mode for "restore from pack" or "sync from another
      machine".

    The pack's envelope fields (``server_revision``, ``stored_at``) are
    NOT preserved — the target store manages its own revision counter.
    Only the inner ``brief`` / ``briefing`` payload (the user-authored
    content) is imported.

    Size guard: packs larger than ``_PORTABLE_PACK_MAX_SIZE_BYTES``
    (100 MB) are rejected to prevent accidental memory exhaustion from
    malformed or hostile payloads. The export currently produces packs
    well under 1 MB (100 briefs × ~5 KB each), so 100 MB is a generous
    ceiling that catches pathological inputs without rejecting any
    legitimate pack.
    """
    import hashlib
    import json

    # ── Pack-level validation ───────────────────────────────────────
    if not isinstance(pack, dict):
        return _clean_json_value({
            "status": "error",
            "code": "invalid_pack",
            "message": "pack must be a JSON object",
        })

    pack_size = len(json.dumps(pack, ensure_ascii=False).encode("utf-8"))
    if pack_size > _PORTABLE_PACK_MAX_SIZE_BYTES:
        return _clean_json_value({
            "status": "error",
            "code": "pack_too_large",
            "message": (
                f"pack is {pack_size} bytes, exceeds "
                f"{_PORTABLE_PACK_MAX_SIZE_BYTES} byte limit"
            ),
        })

    schema = pack.get("schema")
    version = pack.get("version")
    if schema != _PORTABLE_PACK_SCHEMA:
        return _clean_json_value({
            "status": "error",
            "code": "incompatible_schema",
            "message": (
                f"pack schema '{schema}' is not '{_PORTABLE_PACK_SCHEMA}'"
            ),
        })
    if version != _PORTABLE_PACK_VERSION:
        return _clean_json_value({
            "status": "error",
            "code": "incompatible_version",
            "message": (
                f"pack version '{version}' is not "
                f"'{_PORTABLE_PACK_VERSION}'"
            ),
        })

    sections = pack.get("sections")
    section_hashes = pack.get("section_hashes")
    if not isinstance(sections, dict) or not isinstance(section_hashes, dict):
        return _clean_json_value({
            "status": "error",
            "code": "invalid_pack",
            "message": "pack.sections and pack.section_hashes must be objects",
        })

    # ── Section-level: hash verification + record import ────────────
    brief_store = _brief_store()
    briefing_store = _briefing_store()

    # Build existing-ID → revision maps for conflict detection. Using
    # list_records() avoids N load() calls; each list_records() is a
    # single glob + parse of small summary fields.
    existing_brief_revs: dict[str, int] = {
        s["brief_id"]: int(s["server_revision"])
        for s in brief_store.list_records(limit=100)
    }
    existing_briefing_revs: dict[str, int] = {
        s["briefing_id"]: int(s["server_revision"])
        for s in briefing_store.list_records(limit=100)
    }

    section_results: list[dict] = []
    section_errors: list[dict] = []

    for section_name in _PORTABLE_PACK_SECTIONS:
        section = sections.get(section_name)
        if not isinstance(section, dict):
            section_errors.append({
                "section": section_name,
                "code": "missing_section",
                "message": f"section '{section_name}' is missing or not an object",
            })
            continue

        # Hash verification (fail-closed for this section only)
        recorded_hash = section_hashes.get(section_name)
        if not isinstance(recorded_hash, str) or len(recorded_hash) != 64:
            section_errors.append({
                "section": section_name,
                "code": "missing_or_invalid_hash",
                "message": (
                    f"section_hashes['{section_name}'] must be a 64-char "
                    f"SHA-256 hex string"
                ),
            })
            continue
        canonical = json.dumps(section, ensure_ascii=False, sort_keys=True, indent=2)
        actual_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if actual_hash != recorded_hash:
            section_errors.append({
                "section": section_name,
                "code": "hash_mismatch",
                "message": (
                    f"section hash mismatch (recorded={recorded_hash[:12]}…, "
                    f"actual={actual_hash[:12]}…); section may be corrupted "
                    f"in transit"
                ),
            })
            continue

        # Record-level import
        records = section.get("records")
        if not isinstance(records, list):
            section_errors.append({
                "section": section_name,
                "code": "invalid_records",
                "message": "section.records must be a list",
            })
            continue

        # Pick the right store / payload key / id field for this section
        if section_name == "recruitment_briefs":
            store = brief_store
            payload_key = "brief"
            id_field = "brief_id"
            existing_revs = existing_brief_revs
        else:
            store = briefing_store
            payload_key = "briefing"
            id_field = "briefing_id"
            existing_revs = existing_briefing_revs

        imported = 0
        conflicts: list[dict] = []
        skipped: list[dict] = []

        for record in records:
            if not isinstance(record, dict):
                skipped.append({
                    "reason": "record is not an object",
                })
                continue

            payload = record.get(payload_key)
            record_id = record.get(id_field) or (
                payload.get(id_field) if isinstance(payload, dict) else None
            )
            if not isinstance(record_id, str) or not record_id:
                skipped.append({
                    "reason": f"missing or invalid {id_field}",
                })
                continue

            if not isinstance(payload, dict):
                skipped.append({
                    id_field: record_id,
                    "reason": f"missing or invalid '{payload_key}' payload",
                })
                continue

            current_revision = existing_revs.get(record_id)
            try:
                if current_revision is None:
                    # New record: create with revision 1
                    store.save(record_id, payload, expected_revision=None)
                    imported += 1
                elif overwrite:
                    # Existing record: replace via revision bump
                    # (creates a revision backup automatically)
                    store.save(
                        record_id, payload,
                        expected_revision=current_revision,
                    )
                    imported += 1
                else:
                    # Conflict: existing record, overwrite not authorized
                    conflicts.append({
                        id_field: record_id,
                        "local_revision": current_revision,
                    })
            except Exception as exc:  # noqa: BLE001 — report, don't abort
                logger.warning(
                    "import_local_pack: save failed for %s=%s: %s",
                    id_field, record_id, exc,
                    exc_info=True,
                )
                skipped.append({
                    id_field: record_id,
                    "reason": str(exc) or type(exc).__name__,
                })

            # If we just imported or overwrote, update the existing_revs
            # cache so a second record with the same ID in the pack would
            # be detected as a conflict (rather than creating a duplicate).
            if current_revision is None or overwrite:
                existing_revs[record_id] = existing_revs.get(record_id, 0) + 1

        section_results.append({
            "section": section_name,
            "schema": section.get("schema"),
            "version": section.get("version"),
            "total_records": len(records),
            "imported": imported,
            "conflicts": conflicts,
            "skipped": skipped,
        })

    # ── Compose summary ─────────────────────────────────────────────
    total_imported = sum(s["imported"] for s in section_results)
    total_conflicts = sum(len(s["conflicts"]) for s in section_results)
    total_skipped = sum(len(s["skipped"]) for s in section_results)

    return _clean_json_value({
        "status": "ok",
        "schema": "scoutfootball.portable-pack-import",
        "version": "1.0.0",
        "imported_at": _utc_now_iso_helper(),
        "overwrite_mode": bool(overwrite),
        "summary": {
            "total_imported": total_imported,
            "total_conflicts": total_conflicts,
            "total_skipped": total_skipped,
        },
        "section_results": section_results,
        "section_errors": section_errors,
        "limitations": [
            "Pack envelope fields (server_revision, stored_at) are not "
            "preserved; the target store manages its own revision counter.",
            "Record-level failures (validation, conflict) are reported in "
            "skipped/conflicts and do not abort the import.",
            "Section hash mismatch skips the entire section; other sections "
            "are still imported.",
            "Local-only operation; no telemetry is uploaded.",
        ],
    })


def _utc_now_iso_helper() -> str:
    from datetime import UTC, datetime

    return datetime.now(tz=UTC).isoformat()


def _app_version_helper() -> str:
    from scoutfootball import __version__

    return __version__


def _portable_pack_license_summary() -> dict:
    """Return a compact license summary for the portable pack header."""
    artifacts = get_artifacts_summary()
    return {
        "default": "maintainer-local MIT",
        "note": (
            "All records in this pack are personal local objects authored "
            "by the maintainer.  Derived metrics reusing public StatsBomb "
            "Open Data retain that source's CC-BY-SA-4.0 attribution "
            "requirement; raw event data is NOT included in this pack."
        ),
        "sources_attribution": artifacts.get("license_attribution", {}),
    }


def get_wc_tournament_standings(group: str | None = None) -> dict:
    """Return standings for one or all groups."""
    from dataclasses import asdict

    from scoutfootball.worldcup.tournament import (
        compute_all_standings,
        compute_group_standings,
    )

    state = _wc_tournament_state()
    if group:
        letter = group.upper()
        if letter not in GROUPS:
            return _clean_json_value({
                "status": "error",
                "code": "unknown_group",
                "message": f"Unknown group '{group}'. Valid: A-L",
            })
        standings = {letter: [asdict(s) for s in compute_group_standings(state, letter)]}
    else:
        all_standings = compute_all_standings(state)
        standings = {
            letter: [asdict(s) for s in rows]
            for letter, rows in all_standings.items()
        }

    return _clean_json_value({
        "status": "ok",
        "standings": standings,
    })


def get_wc_tournament_standings_probabilities(
    group: str | None = None,
    num_simulations: int = 2000,
) -> dict:
    """Return group standings enriched with Monte Carlo advancement probabilities.

    Runs a strength-weighted group-stage simulation and returns per-team
    ``advance_prob`` and ``win_group_prob`` alongside the current standings.
    When ``group`` is provided, only that group's data is returned; otherwise
    all 12 groups are included.

    Uses the existing ``simulate_group_stage`` function with ``mode="strength"``
    and a fixed seed for stability across calls with the same input state.
    """
    from dataclasses import asdict

    from scoutfootball.worldcup.tournament import (
        compute_all_standings,
        compute_group_standings,
    )

    state = _wc_tournament_state()

    if group:
        letter = group.upper()
        if letter not in GROUPS:
            return _clean_json_value({
                "status": "error",
                "code": "unknown_group",
                "message": f"Unknown group '{group}'. Valid: A-L",
            })
        group_filter = letter
    else:
        group_filter = None

    enriched_squads, strengths = _get_wc_enriched_squads()
    if not enriched_squads or not strengths:
        return _clean_json_value({
            "status": "no_data",
            "group": group_filter,
            "groups": {},
            "num_simulations": 0,
            "disclaimer": (
                "World Cup squad data unavailable; probability estimates "
                "cannot be computed."
            ),
        })

    from scoutfootball.worldcup.data import simulate_group_stage

    sim_result = simulate_group_stage(
        state,
        team_strengths=strengths,
        num_simulations=num_simulations,
        mode="strength",
        seed=42,
    )

    prob_by_team: dict[str, dict[str, float]] = {}
    for entry in sim_result.get("advancement_probability", []):
        prob_by_team[entry["team"]] = {
            "advance_prob": entry.get("advance_prob", 0.0),
            "win_group_prob": entry.get("win_group_prob", 0.0),
        }

    if group_filter:
        standings_rows = compute_group_standings(state, group_filter)
        groups_out = {
            group_filter: [
                {
                    **asdict(s),
                    "advance_prob": prob_by_team.get(s.team, {}).get(
                        "advance_prob", 0.0
                    ),
                    "win_group_prob": prob_by_team.get(s.team, {}).get(
                        "win_group_prob", 0.0
                    ),
                }
                for s in standings_rows
            ],
        }
    else:
        all_standings = compute_all_standings(state)
        groups_out = {
            letter: [
                {
                    **asdict(s),
                    "advance_prob": prob_by_team.get(s.team, {}).get(
                        "advance_prob", 0.0
                    ),
                    "win_group_prob": prob_by_team.get(s.team, {}).get(
                        "win_group_prob", 0.0
                    ),
                }
                for s in rows
            ]
            for letter, rows in all_standings.items()
        }

    return _clean_json_value({
        "status": "ok",
        "group": group_filter,
        "groups": groups_out,
        "num_simulations": sim_result.get("num_simulations", 0),
        "remaining_matches": sim_result.get("remaining_matches", 0),
        "mode": "strength",
        "source_attribution": _STATSBOMB_ATTRIBUTION,
        "disclaimer": sim_result.get(
            "disclaimer",
            (
                "Advancement probabilities use strength-weighted Monte Carlo "
                "simulation of remaining group matches. Illustrative only."
            ),
        ),
    })


def get_wc_tournament_overall_leaderboard(
    num_simulations: int = 2000,
    sort_by: str = "advance_prob",
) -> dict:
    """Return all 48 World Cup teams ranked by advancement probability.

    Runs a strength-weighted group-stage simulation and returns a flat list
    of all teams sorted by the requested metric, alongside their group,
    current standings position, advance probability, and group-win probability.

    Parameters
    ----------
    num_simulations:
        Number of Monte Carlo iterations.
    sort_by:
        Column to sort by. One of ``"advance_prob"`` (default),
        ``"win_group_prob"``, ``"points"``, ``"goal_difference"``,
        ``"goals_for"``.
    """
    from scoutfootball.worldcup.tournament import compute_all_standings

    state = _wc_tournament_state()

    if sort_by not in ("advance_prob", "win_group_prob", "points", "goal_difference", "goals_for"):
        return _clean_json_value({
            "status": "error",
            "code": "invalid_sort",
            "message": (
                f"Invalid sort_by '{sort_by}'. Valid: advance_prob, "
                "win_group_prob, points, goal_difference, goals_for"
            ),
        })

    enriched_squads, strengths = _get_wc_enriched_squads()
    if not enriched_squads or not strengths:
        return _clean_json_value({
            "status": "no_data",
            "teams": [],
            "num_simulations": 0,
            "sort_by": sort_by,
            "disclaimer": (
                "World Cup squad data unavailable; probability estimates "
                "cannot be computed."
            ),
        })

    from scoutfootball.worldcup.data import simulate_group_stage

    sim_result = simulate_group_stage(
        state,
        team_strengths=strengths,
        num_simulations=num_simulations,
        mode="strength",
        seed=42,
    )

    prob_by_team: dict[str, dict[str, float]] = {}
    for entry in sim_result.get("advancement_probability", []):
        prob_by_team[entry["team"]] = {
            "advance_prob": entry.get("advance_prob", 0.0),
            "win_group_prob": entry.get("win_group_prob", 0.0),
        }

    all_standings = compute_all_standings(state)

    teams: list[dict[str, Any]] = []
    for letter, rows in all_standings.items():
        for pos, s in enumerate(rows, start=1):
            prob = prob_by_team.get(s.team, {})
            teams.append({
                "team": s.team,
                "group": letter,
                "position": pos,
                "played": s.played,
                "won": s.won,
                "drawn": s.drawn,
                "lost": s.lost,
                "goals_for": s.goals_for,
                "goals_against": s.goals_against,
                "goal_difference": s.goal_difference,
                "points": s.points,
                "advance_prob": prob.get("advance_prob", 0.0),
                "win_group_prob": prob.get("win_group_prob", 0.0),
            })

    if sort_by == "advance_prob":
        teams.sort(key=lambda t: (-t["advance_prob"], -t["points"], -t["goal_difference"]))
    elif sort_by == "win_group_prob":
        teams.sort(key=lambda t: (-t["win_group_prob"], -t["points"], -t["goal_difference"]))
    elif sort_by == "points":
        teams.sort(key=lambda t: (-t["points"], -t["goal_difference"], -t["goals_for"]))
    elif sort_by == "goal_difference":
        teams.sort(key=lambda t: (-t["goal_difference"], -t["points"]))
    elif sort_by == "goals_for":
        teams.sort(key=lambda t: (-t["goals_for"], -t["points"]))

    for rank, t in enumerate(teams, start=1):
        t["rank"] = rank

    return _clean_json_value({
        "status": "ok",
        "teams": teams,
        "num_simulations": sim_result.get("num_simulations", 0),
        "remaining_matches": sim_result.get("remaining_matches", 0),
        "mode": "strength",
        "sort_by": sort_by,
        "source_attribution": _STATSBOMB_ATTRIBUTION,
        "disclaimer": sim_result.get(
            "disclaimer",
            (
                "Advancement probabilities use strength-weighted Monte Carlo "
                "simulation of remaining group matches. Illustrative only."
            ),
        ),
    })


def get_wc_tournament_matches(
    group: str | None = None,
    pending: bool = False,
) -> dict:
    """Return matches with optional group filter and pending-only flag."""
    from scoutfootball.worldcup.tournament import _match_completed

    state = _wc_tournament_state()
    matches_out = []
    for m in state.matches:
        if group and m.get("group") != group.upper():
            continue
        result = state.results.get(m["match_id"])
        is_done = _match_completed(result)
        if pending and is_done:
            continue
        entry = {"match_id": m["match_id"], **m}
        if is_done:
            entry["result"] = result
            entry["completed"] = True
        else:
            entry["completed"] = False
        matches_out.append(entry)

    return _clean_json_value({
        "status": "ok",
        "count": len(matches_out),
        "matches": matches_out,
    })


def get_wc_tournament_match_predictions(group: str | None = None) -> dict:
    """Batch Poisson predictions for scheduled group-stage matches.

    Returns a compact per-match prediction summary for all scheduled
    group-stage matches in the tournament state (filtered by ``group``
    when provided). Reuses the existing ``world_cup_strength_poisson``
    model. Completed matches are annotated with their actual result and
    a prediction-delta classification (``as_expected`` / ``upset`` /
    ``hold``) so the frontend can surface actual-vs-predicted badges.
    """
    from scoutfootball.worldcup.tournament import _match_completed

    state = _wc_tournament_state()

    if group:
        letter = group.upper()
        if letter not in GROUPS:
            return _clean_json_value({
                "status": "error",
                "code": "unknown_group",
                "message": f"Unknown group '{group}'. Valid: A-L",
            })

    enriched_squads, _strengths = _get_wc_enriched_squads()
    if not enriched_squads:
        return _clean_json_value({
            "status": "no_data",
            "group": group.upper() if group else None,
            "count": 0,
            "predictions": [],
            "model": "world_cup_strength_poisson",
            "disclaimer": (
                "World Cup squad data unavailable; predictions cannot be "
                "computed."
            ),
        })

    predictions: list[dict[str, Any]] = []
    for m in state.matches:
        if group and m.get("group") != group.upper():
            continue
        home = m.get("home")
        away = m.get("away")
        if not home or not away or home == away:
            continue
        match_base = {
            "match_id": m["match_id"],
            "home": home,
            "away": away,
            "group": m.get("group"),
            "matchday": m.get("matchday"),
            "date": m.get("date"),
            "venue": m.get("venue"),
            "city": m.get("city"),
        }
        if home not in enriched_squads or away not in enriched_squads:
            predictions.append({
                **match_base,
                "status": "team_not_found",
                "completed": False,
            })
            continue
        pred = get_world_cup_match_prediction(home, away)
        if "error" in pred:
            predictions.append({
                **match_base,
                "status": "error",
                "message": pred["error"],
                "completed": False,
            })
            continue
        result = state.results.get(m["match_id"])
        completed = _match_completed(result)
        entry: dict[str, Any] = {
            **match_base,
            "status": "ok",
            "completed": completed,
            "home_win_prob": pred["home_win"],
            "draw_prob": pred["draw"],
            "away_win_prob": pred["away_win"],
            "expected_goals_home": pred["home_lambda"],
            "expected_goals_away": pred["away_lambda"],
            "home_strength": pred["home_strength"],
            "away_strength": pred["away_strength"],
            "host_bonus": pred["host_bonus"],
            "home_is_host": home in HOSTS,
            "away_is_host": away in HOSTS,
            "most_likely_scoreline": _most_likely_wc_scoreline(
                pred["score_matrix"]
            ),
        }
        if completed and result is not None:
            entry["result"] = {
                "home_goals": result.get("home_goals"),
                "away_goals": result.get("away_goals"),
                "winner": result.get("winner"),
                "decided_by": result.get("decided_by"),
            }
            entry["delta"] = _classify_prediction_delta(
                pred["home_win"],
                pred["draw"],
                pred["away_win"],
                int(result.get("home_goals", 0)),
                int(result.get("away_goals", 0)),
            )
        predictions.append(entry)

    return _clean_json_value({
        "status": "ok",
        "group": group.upper() if group else None,
        "count": len(predictions),
        "predictions": predictions,
        "model": "world_cup_strength_poisson",
        "model_version": "wc-1.0",
        "source_attribution": _STATSBOMB_ATTRIBUTION,
        "disclaimer": (
            "Per-match predictions use the world_cup_strength_poisson "
            "baseline model. Pre-recording only; does not reflect in-play "
            "state. Delta classification compares actual result to argmax "
            "prediction; outcomes with pre-match probability < 0.30 are "
            "flagged as upsets."
        ),
    })


def get_wc_tournament_match_impact(
    group: str | None = None,
    num_simulations: int = 1000,
    top_n: int = 10,
) -> dict:
    """Rank remaining group-stage matches by their impact on advancement odds.

    For each pending match, simulates three outcomes (home win / draw / away
    win) and measures how much each team's advancement probability shifts
    across the three scenarios. Matches are ranked by total impact (sum of
    absolute probability swings across all teams in the group).

    Parameters
    ----------
    group:
        Optional group letter filter (A-L). All groups when omitted.
    num_simulations:
        Monte Carlo iterations per outcome scenario (default 1000).
    top_n:
        Maximum number of matches to return (default 10).
    """
    import copy

    from scoutfootball.worldcup.data import simulate_group_stage
    from scoutfootball.worldcup.tournament import (
        GROUPS,
        _match_completed,
    )

    state = _wc_tournament_state()

    # Cache keyed on tournament state fingerprint + parameters; state changes
    # (e.g. marking a result) invalidate the cache automatically.
    cache_key = (
        f"wc_match_impact::{_wc_tournament_state_fingerprint(state)}"
        f"::{group}::{num_simulations}::{top_n}"
    )
    cached = _wc_cache.get(cache_key)
    if cached is not _MISSING:
        return cached

    enriched_squads, strengths = _get_wc_enriched_squads()
    if not enriched_squads or not strengths:
        return _clean_json_value({
            "status": "no_data",
            "matches": [],
            "num_simulations": 0,
            "disclaimer": (
                "World Cup squad data unavailable; match impact estimates "
                "cannot be computed."
            ),
        })

    if group:
        group_upper = group.upper()
        if group_upper not in GROUPS:
            return _clean_json_value({
                "status": "error",
                "code": "unknown_group",
                "message": f"Unknown group '{group}'. Valid: A-L",
            })
        groups_to_check = [group_upper]
    else:
        groups_to_check = list(GROUPS.keys())

    pending_matches = []
    for m in state.matches:
        m_group = m.get("group")
        if not m_group or m_group in ("r32", "r16", "qf", "sf", "final"):
            continue
        if m_group not in groups_to_check:
            continue
        result = state.results.get(m["match_id"])
        if _match_completed(result):
            continue
        pending_matches.append(m)

    if not pending_matches:
        result = _clean_json_value({
            "status": "ok",
            "matches": [],
            "num_simulations": num_simulations,
            "mode": "strength",
            "source_attribution": _STATSBOMB_ATTRIBUTION,
            "disclaimer": "No remaining group-stage matches to analyze.",
        })
        _wc_cache.set(cache_key, result)
        return result

    def _sim_with_result(match_id, home_goals, away_goals):
        modified = copy.deepcopy(state)
        modified.results[match_id] = {
            "status": "completed",
            "home_goals": home_goals,
            "away_goals": away_goals,
            "winner": (
                "home" if home_goals > away_goals
                else "away" if away_goals > home_goals
                else "draw"
            ),
            "decided_by": "regular",
        }
        sim = simulate_group_stage(
            modified,
            team_strengths=strengths,
            num_simulations=num_simulations,
            mode="strength",
            seed=42,
        )
        prob_map = {}
        for entry in sim.get("advancement_probability", []):
            prob_map[entry["team"]] = entry
        return prob_map

    impact_matches = []
    for m in pending_matches:
        mid = m["match_id"]
        home = m.get("home", "")
        away = m.get("away", "")
        m_group = m.get("group", "")

        # Use model-derived scorelines from the WC strength Poisson model
        # instead of hardcoded 2-1/1-1/1-2. Falls back to defaults if the
        # prediction endpoint is unavailable.
        try:
            prediction = get_world_cup_match_prediction(home, away)
            if prediction.get("error") or "score_matrix" not in prediction:
                raise ValueError("prediction unavailable")
            mls = _most_likely_wc_scoreline(prediction["score_matrix"])
            # mls format: {"home_goals": int, "away_goals": int, "probability": float}
            base_home = int(mls.get("home_goals", 1))
            base_away = int(mls.get("away_goals", 1))
            # Build three distinct outcome scorelines (home win / draw / away win).
            if base_home > base_away:
                home_win_goals = (base_home, base_away)
                draw_goals = (base_away, base_away)
                away_win_goals = (max(0, base_away - 1), base_away + 1)
            elif base_home < base_away:
                home_win_goals = (base_away, max(0, base_away - 1))
                draw_goals = (base_home, base_home)
                away_win_goals = (base_home, base_away)
            else:
                # Most likely was a draw — nudge to distinct W/D/L.
                home_win_goals = (base_home + 1, base_away)
                draw_goals = (base_home, base_away)
                away_win_goals = (base_home, base_away + 1)
            # Safety: ensure W/D/L span.
            if (
                home_win_goals[0] <= home_win_goals[1]
                or draw_goals[0] != draw_goals[1]
                or away_win_goals[0] >= away_win_goals[1]
            ):
                home_win_goals = (2, 1)
                draw_goals = (1, 1)
                away_win_goals = (1, 2)
        except Exception:
            logger.warning(
                "get_wc_tournament_match_impact: scoreline prediction failed, using fallback",
                exc_info=True,
            )
            # Fallback: classic 2-1 / 1-1 / 1-2 scenarios.
            home_win_goals = (2, 1)
            draw_goals = (1, 1)
            away_win_goals = (1, 2)

        home_win_probs = _sim_with_result(mid, home_win_goals[0], home_win_goals[1])
        draw_probs = _sim_with_result(mid, draw_goals[0], draw_goals[1])
        away_win_probs = _sim_with_result(mid, away_win_goals[0], away_win_goals[1])

        all_teams = set(home_win_probs.keys()) | set(draw_probs.keys()) | set(away_win_probs.keys())

        total_impact = 0.0
        max_swing = 0.0
        max_swing_team = ""
        per_team_impact = []

        for team in sorted(all_teams):
            hw = home_win_probs.get(team, {}).get("advance_prob", 0.0)
            dr = draw_probs.get(team, {}).get("advance_prob", 0.0)
            aw = away_win_probs.get(team, {}).get("advance_prob", 0.0)
            team_max = max(hw, dr, aw)
            team_min = min(hw, dr, aw)
            swing = team_max - team_min
            total_impact += swing
            if swing > max_swing:
                max_swing = swing
                max_swing_team = team
            per_team_impact.append({
                "team": team,
                "home_win_prob": hw,
                "draw_prob": dr,
                "away_win_prob": aw,
                "swing": swing,
            })

        per_team_impact.sort(key=lambda t: -t["swing"])

        impact_matches.append({
            "match_id": mid,
            "home": home,
            "away": away,
            "group": m_group,
            "matchday": m.get("matchday"),
            "date": m.get("date"),
            "venue": m.get("venue"),
            "city": m.get("city"),
            "scenario_scorelines": {
                "home_win": list(home_win_goals),
                "draw": list(draw_goals),
                "away_win": list(away_win_goals),
            },
            "total_impact": total_impact,
            "max_swing": max_swing,
            "max_swing_team": max_swing_team,
            "per_team": per_team_impact,
        })

    impact_matches.sort(key=lambda m: -m["total_impact"])
    top_matches = impact_matches[:top_n]

    result = _clean_json_value({
        "status": "ok",
        "matches": top_matches,
        "total_pending": len(pending_matches),
        "num_simulations": num_simulations,
        "mode": "strength",
        "source_attribution": _STATSBOMB_ATTRIBUTION,
        "disclaimer": (
            "Match impact uses strength-weighted Monte Carlo simulation of "
            "remaining group matches. Impact = sum of advancement probability "
            "swings across all teams in the group when the match outcome "
            "varies. Scenario scorelines are derived from the WC strength "
            "Poisson model's most likely outcome. Illustrative only."
        ),
    })
    _wc_cache.set(cache_key, result)
    return result


def get_wc_tournament_knockout_match_impact(
    *, num_simulations: int = 5000, top_n: int = 10
) -> dict:
    """Rank remaining knockout matches by championship-probability swing.

    Mirrors :func:`get_wc_tournament_match_impact` but for knockout fixtures:
    for each pending KO match with both teams populated, simulates the three
    outcomes (home win / draw / away win; draws resolved by penalties
    assigned to the home side for the simulation only) and measures each
    team's championship probability swing across the scenarios.

    Returns the top-N matches sorted by total championship-probability impact.
    """
    import copy

    from scoutfootball.worldcup.data import project_knockout_probabilities
    from scoutfootball.worldcup.tournament import (
        get_knockout_overview,
    )

    state = _wc_tournament_state()

    # Cache keyed on tournament state fingerprint + parameters; state changes
    # (e.g. marking a result or regenerating the bracket) invalidate the cache.
    cache_key = (
        f"wc_ko_match_impact::{_wc_tournament_state_fingerprint(state)}"
        f"::{num_simulations}::{top_n}"
    )
    cached = _wc_cache.get(cache_key)
    if cached is not _MISSING:
        return cached

    overview = get_knockout_overview(state)
    if not overview.get("generated"):
        return _clean_json_value({
            "status": "not_generated",
            "matches": [],
            "num_simulations": 0,
            "disclaimer": (
                "No knockout bracket has been generated. Call "
                "/world-cup/tournament/knockout/generate first."
            ),
        })

    enriched_squads, strengths = _get_wc_enriched_squads()
    if not enriched_squads or not strengths:
        return _clean_json_value({
            "status": "no_data",
            "matches": [],
            "num_simulations": 0,
            "disclaimer": (
                "World Cup squad data unavailable; knockout match impact "
                "cannot be computed."
            ),
        })

    pending = []
    for m in overview.get("matches", []):
        if m.get("status") == "completed":
            continue
        home = m.get("home")
        away = m.get("away")
        if not home or not away:
            continue
        pending.append(m)

    if not pending:
        result = _clean_json_value({
            "status": "ok",
            "matches": [],
            "num_simulations": num_simulations,
            "mode": "strength",
            "source_attribution": _STATSBOMB_ATTRIBUTION,
            "disclaimer": "No remaining knockout matches with both teams set.",
        })
        _wc_cache.set(cache_key, result)
        return result

    def _sim_knockout_with_result(match_id: str, winner: str):
        modified = copy.deepcopy(state)
        ko_match = modified.knockout_match_by_id(match_id)
        if not ko_match:
            return {}
        # Apply a 1-0 or 0-1 result depending on winner.
        if winner == ko_match.get("home"):
            hg, ag = 1, 0
        else:
            hg, ag = 0, 1
        ko_match["status"] = "completed"
        ko_match["home_goals"] = hg
        ko_match["away_goals"] = ag
        ko_match["winner"] = winner
        ko_match["decided_by"] = "regular"
        modified.results[match_id] = {
            "status": "completed",
            "home_goals": hg,
            "away_goals": ag,
            "winner": winner,
            "decided_by": "regular",
        }
        if "matches" not in modified.knockout:
            modified.knockout["matches"] = []
        for i, km in enumerate(modified.knockout.get("matches", [])):
            if km.get("match_id") == match_id:
                modified.knockout["matches"][i] = ko_match
                break
        # Re-project KO bracket from modified state. Pass num_simulations so
        # the caller's requested MC iteration count is actually honored.
        new_overview = get_knockout_overview(modified)
        result = project_knockout_probabilities(
            new_overview, strengths, num_simulations=num_simulations
        )
        prob_map = {}
        for entry in result.get("tournament_win_probability", []):
            prob_map[entry["team"]] = entry.get("win_probability", 0.0)
        return prob_map

    impact_matches = []
    for m in pending:
        mid = m.get("match_id", "")
        home = m.get("home", "")
        away = m.get("away", "")
        round_label = m.get("round_label", m.get("round", ""))

        home_win_probs = _sim_knockout_with_result(mid, home)
        away_win_probs = _sim_knockout_with_result(mid, away)
        # No draw scenario in KO; assign draw column to a 50/50 split for
        # presentation parity with the group-stage panel.
        draw_probs = {
            team: (home_win_probs.get(team, 0.0) + away_win_probs.get(team, 0.0)) / 2.0
            for team in set(home_win_probs) | set(away_win_probs)
        }

        all_teams = set(home_win_probs) | set(away_win_probs) | set(draw_probs)
        total_impact = 0.0
        max_swing = 0.0
        max_swing_team = ""
        per_team_impact = []
        for team in sorted(all_teams):
            hw = home_win_probs.get(team, 0.0)
            dr = draw_probs.get(team, 0.0)
            aw = away_win_probs.get(team, 0.0)
            team_max = max(hw, dr, aw)
            team_min = min(hw, dr, aw)
            swing = team_max - team_min
            total_impact += swing
            if swing > max_swing:
                max_swing = swing
                max_swing_team = team
            per_team_impact.append({
                "team": team,
                "home_win_prob": hw,
                "draw_prob": dr,
                "away_win_prob": aw,
                "swing": swing,
            })
        per_team_impact.sort(key=lambda t: -t["swing"])

        impact_matches.append({
            "match_id": mid,
            "home": home,
            "away": away,
            "round": round_label,
            "position": m.get("position"),
            "total_impact": total_impact,
            "max_swing": max_swing,
            "max_swing_team": max_swing_team,
            "per_team": per_team_impact,
        })

    impact_matches.sort(key=lambda m: -m["total_impact"])
    top_matches = impact_matches[:top_n]

    result = _clean_json_value({
        "status": "ok",
        "matches": top_matches,
        "total_pending": len(pending),
        "num_simulations": num_simulations,
        "mode": "strength",
        "source_attribution": _STATSBOMB_ATTRIBUTION,
        "disclaimer": (
            "Knockout match impact uses Bradley-Terry strength model with "
            "Monte Carlo tournament win probability. Impact = sum of "
            "championship probability swings across all teams when the "
            "match winner varies. Draw column is the average of the two "
            "win scenarios because knockout matches cannot end in a draw. "
            "Illustrative only."
        ),
    })
    _wc_cache.set(cache_key, result)
    return result


def get_wc_tournament_top_matches(
    *, group_top_n: int = 5, knockout_top_n: int = 5, num_simulations: int = 1000
) -> dict:
    """Combine group-stage and KO match impact into a single top-N view.

    Returns a unified leaderboard of the most impactful remaining matches
    across the whole tournament, suitable for a 'Top Matches to Watch'
    panel. Normalizes the impact metric so group-stage advancement swings
    are comparable to KO championship swings.
    """
    group_impact = get_wc_tournament_match_impact(
        num_simulations=num_simulations, top_n=group_top_n
    )
    ko_impact = get_wc_tournament_knockout_match_impact(
        num_simulations=max(num_simulations, 5000), top_n=knockout_top_n
    )

    unified: list[dict[str, Any]] = []

    if group_impact.get("status") == "ok":
        for m in group_impact.get("matches", []):
            unified.append({
                "match_id": m["match_id"],
                "stage": "group",
                "home": m["home"],
                "away": m["away"],
                "stage_label": f"Group {m.get('group', '')}",
                "date": m.get("date", ""),
                "venue": m.get("venue", ""),
                "city": m.get("city", ""),
                "total_impact": m["total_impact"],
                "max_swing": m["max_swing"],
                "max_swing_team": m["max_swing_team"],
                "impact_metric": "advancement_prob_swing",
                "per_team": m.get("per_team", []),
            })

    if ko_impact.get("status") == "ok":
        for m in ko_impact.get("matches", []):
            unified.append({
                "match_id": m["match_id"],
                "stage": "knockout",
                "home": m["home"],
                "away": m["away"],
                "stage_label": m.get("round", "Knockout"),
                "date": "",
                "venue": "",
                "city": "",
                "total_impact": m["total_impact"],
                "max_swing": m["max_swing"],
                "max_swing_team": m["max_swing_team"],
                "impact_metric": "championship_prob_swing",
                "per_team": m.get("per_team", []),
            })

    # Sort by total_impact (which is naturally on different scales between
    # group and KO; we keep raw values so the user can see the actual swing
    # magnitude per stage, but rank by total_impact).
    unified.sort(key=lambda m: -m["total_impact"])

    return _clean_json_value({
        "schema": "scoutfootball.world-cup-top-matches",
        "version": "1.0.0",
        "status": "ok",
        "matches": unified[: group_top_n + knockout_top_n],
        "group_stage_count": len(group_impact.get("matches", [])),
        "knockout_count": len(ko_impact.get("matches", [])),
        "group_stage_status": group_impact.get("status", "no_data"),
        "knockout_status": ko_impact.get("status", "no_data"),
        "source_attribution": _STATSBOMB_ATTRIBUTION,
        "disclaimer": (
            "Unified top matches to watch, combining group-stage advancement "
            "swings and knockout championship swings. The two stages use "
            "different baseline probabilities, so total_impact is not strictly "
            "comparable across stages — review per_team swings for context. "
            "Illustrative only."
        ),
    })


def get_wc_tournament_scenarios(team: str, max_scenarios: int = 30) -> dict:
    """Return qualification scenarios for a single team."""
    from dataclasses import asdict

    from scoutfootball.worldcup.tournament import compute_team_scenarios

    state = _wc_tournament_state()
    try:
        result = compute_team_scenarios(state, team, max_scenarios=max_scenarios)
    except ValueError as exc:
        return _clean_json_value({
            "status": "error",
            "code": "invalid_team",
            "message": str(exc),
        })

    return _clean_json_value({
        "status": "ok",
        "team": result.team,
        "group": result.group,
        "current_standing": result.current_standing,
        "remaining_matches": result.remaining_matches,
        "advance_probability": result.advance_probability,
        "scenarios": [asdict(s) for s in result.scenarios],
        "summary": result.summary,
    })


def get_backtest_report_card() -> dict:
    """Return a letter-graded report card aggregating model quality.

    Grades six dimensions (accuracy, calibration, discrimination, sharpness,
    confidence alignment, stability) on a 0–100 scale mapped to A/B/C/D/F.
    Prefers Dixon-Coles decay predictions, falls back to Poisson. Cached
    for 5 minutes.
    """
    import time

    cache_key = "report_card"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_backtest_report_card,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        model_type = "dixon_coles_decay"
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
            model_type = "poisson"
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_backtest_report_card(
                    preds_df, model_type=model_type
                )
                result = _clean_json_value({
                    "status": "ok",
                    "overall_grade": report.overall_grade,
                    "overall_score": report.overall_score,
                    "n_matches": report.n_matches,
                    "model_type": report.model_type,
                    "summary": report.summary,
                    "disclaimer": report.disclaimer,
                    "dimensions": [
                        {
                            "name": d.name,
                            "grade": d.grade,
                            "score": d.score,
                            "metric_value": d.metric_value,
                            "metric_name": d.metric_name,
                            "assessment": d.assessment,
                            "threshold": d.threshold,
                        }
                        for d in report.dimensions
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_backtest_report_card failed", exc_info=True)
        return _make_error_response(str(exc))


def get_prediction_anomalies(
    *,
    high_entropy_threshold: float = 0.85,
    overconfident_threshold: float = 0.60,
    underconfident_threshold: float = 0.40,
    outlier_high_threshold: float = 0.90,
    outlier_low_threshold: float = 0.35,
    max_anomalies: int = 500,
) -> dict:
    """Return flagged prediction anomalies for review.

    Detects high-entropy, overconfident-wrong, underconfident-correct, and
    outlier-confidence predictions. Prefers Dixon-Coles decay predictions,
    falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = (
        f"anomalies_{high_entropy_threshold}_{overconfident_threshold}_"
        f"{underconfident_threshold}_{outlier_high_threshold}_"
        f"{outlier_low_threshold}_{max_anomalies}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_prediction_anomalies,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_prediction_anomalies(
                    preds_df,
                    high_entropy_threshold=high_entropy_threshold,
                    overconfident_threshold=overconfident_threshold,
                    underconfident_threshold=underconfident_threshold,
                    outlier_high_threshold=outlier_high_threshold,
                    outlier_low_threshold=outlier_low_threshold,
                    max_anomalies=max_anomalies,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "n_anomalies": report.n_anomalies,
                    "anomaly_counts": report.anomaly_counts,
                    "severity_counts": report.severity_counts,
                    "high_entropy_count": report.high_entropy_count,
                    "overconfident_wrong_count": report.overconfident_wrong_count,
                    "underconfident_correct_count": report.underconfident_correct_count,
                    "outlier_confidence_count": report.outlier_confidence_count,
                    "disclaimer": report.disclaimer,
                    "anomalies": [
                        {
                            "match_index": a.match_index,
                            "anomaly_type": a.anomaly_type,
                            "severity": a.severity,
                            "confidence": a.confidence,
                            "predicted_outcome": a.predicted_outcome,
                            "actual_outcome": a.actual_outcome,
                            "correct": a.correct,
                            "explanation": a.explanation,
                            "match_id": a.match_id,
                            "home_team": a.home_team,
                            "away_team": a.away_team,
                        }
                        for a in report.anomalies
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_prediction_anomalies failed", exc_info=True)
        return _make_error_response(str(exc))


def get_team_performance_profile(
    team: str,
    *,
    top_n: int = 5,
    min_matches: int = 3,
) -> dict:
    """Return a backtest-derived performance profile for a single team.

    Filters backtest predictions to matches involving *team* and computes
    accuracy, over/underperformance, goals, clean sheets, common scorelines,
    and worst/best predictions. Prefers Dixon-Coles decay predictions, falls
    back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"team_profile_{team}_{top_n}_{min_matches}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_team_performance_profile,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                profile = compute_team_performance_profile(
                    preds_df,
                    team,
                    top_n=top_n,
                    min_matches=min_matches,
                )
                if profile is None:
                    result = {
                        "status": "not_found",
                        "team": team,
                        "message": (
                            f"Team '{team}' has fewer than {min_matches} "
                            f"backtest predictions."
                        ),
                    }
                else:
                    result = _clean_json_value({
                        "status": "ok",
                        "team": profile.team,
                        "n_matches": profile.n_matches,
                        "n_home": profile.n_home,
                        "n_away": profile.n_away,
                        "overall_accuracy": profile.overall_accuracy,
                        "home_accuracy": profile.home_accuracy,
                        "away_accuracy": profile.away_accuracy,
                        "avg_confidence": profile.avg_confidence,
                        "calibration_gap": profile.calibration_gap,
                        "overperformance": profile.overperformance,
                        "n_wins": profile.n_wins,
                        "n_draws": profile.n_draws,
                        "n_losses": profile.n_losses,
                        "avg_goals_scored": profile.avg_goals_scored,
                        "avg_goals_conceded": profile.avg_goals_conceded,
                        "clean_sheet_rate": profile.clean_sheet_rate,
                        "btts_rate": profile.btts_rate,
                        "common_scorelines": [
                            {"scoreline": s, "count": c}
                            for s, c in profile.common_scorelines
                        ],
                        "worst_predictions": profile.worst_predictions,
                        "best_predictions": profile.best_predictions,
                        "assessment": profile.assessment,
                        "disclaimer": profile.disclaimer,
                    })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        logger.warning("get_team_performance_profile failed", exc_info=True)
        return _make_error_response(str(exc))


def apply_wc_tournament_result(
    match_id: str,
    home_goals: int,
    away_goals: int,
) -> dict:
    """Record a match result and persist state. Returns updated group standings."""
    from dataclasses import asdict

    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        apply_result,
        compute_group_standings,
        save_state,
    )

    state = _wc_tournament_state()
    match = state.match_by_id(match_id)
    if not match:
        return _clean_json_value({
            "status": "error",
            "code": "match_not_found",
            "message": f"Match id '{match_id}' not found",
        })

    ok = apply_result(state, match_id, home_goals, away_goals)
    if not ok:
        return _clean_json_value({
            "status": "error",
            "code": "invalid_result",
            "message": (
                f"Failed to apply {home_goals}-{away_goals} to {match_id} "
                "(goals must be 0-30)"
            ),
        })

    save_state(state, DEFAULT_STATE_PATH)

    group = match.get("group")
    standings = (
        [asdict(s) for s in compute_group_standings(state, group)]
        if group else []
    )

    return _clean_json_value({
        "status": "ok",
        "match_id": match_id,
        "home": match["home"],
        "away": match["away"],
        "home_goals": home_goals,
        "away_goals": away_goals,
        "group": group,
        "standings": standings,
    })


def clear_wc_tournament_result(match_id: str) -> dict:
    """Clear a recorded match result and persist state."""
    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        clear_result,
        save_state,
    )

    state = _wc_tournament_state()
    if not clear_result(state, match_id):
        return _clean_json_value({
            "status": "error",
            "code": "no_result",
            "message": f"No result recorded for {match_id}",
        })
    save_state(state, DEFAULT_STATE_PATH)
    return _clean_json_value({
        "status": "ok",
        "match_id": match_id,
        "cleared": True,
    })


def reset_wc_tournament() -> dict:
    """Reset tournament state to fresh (no results)."""
    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        init_state,
        save_state,
        tournament_summary,
    )

    state = init_state()
    save_state(state, DEFAULT_STATE_PATH)
    return _clean_json_value({
        "status": "ok",
        "reset": True,
        "summary": tournament_summary(state),
    })


def get_wc_knockout_bracket() -> dict:
    """Return the current knockout bracket state."""
    from scoutfootball.worldcup.tournament import (
        get_knockout_overview,
        get_tournament_state_contract,
    )

    state = _wc_tournament_state()
    overview = get_knockout_overview(state)
    overview["status"] = "ok"
    # Core DataContract: tournament_state (knockout bracket is part of state).
    overview["contracts"] = [get_tournament_state_contract(state)]
    overview["fact_types"] = ["expected_callup"]
    return _clean_json_value(overview)


def get_wc_knockout_match_briefing(match_id: str) -> dict[str, Any]:
    """Return a source-bounded briefing for a populated knockout matchup.

    The bracket state determines whether a fixture is known.  Placeholder
    winner slots stay explicitly unavailable instead of receiving a synthetic
    briefing or a predicted opponent.
    """
    state = _wc_tournament_state()
    if not state.knockout or not state.knockout.get("matches"):
        return _clean_json_value({
            "schema": "scoutfootball.world-cup-knockout-match-briefing",
            "version": "1.0.0",
            "status": "not_generated",
            "match_id": match_id,
            "limitations": ["No local knockout bracket has been generated."],
        })
    match = state.knockout_match_by_id(match_id)
    if not match:
        return _clean_json_value({
            "schema": "scoutfootball.world-cup-knockout-match-briefing",
            "version": "1.0.0",
            "status": "not_found",
            "match_id": match_id,
            "limitations": ["The requested match ID is not in the local knockout bracket."],
        })
    context = {
        "match_id": match.get("match_id"),
        "round": match.get("round"),
        "round_label": match.get("round_label"),
        "position": match.get("position"),
        "bracket_provisional": bool(state.knockout.get("provisional", True)),
        "match_status": match.get("status"),
    }
    if not match.get("home") or not match.get("away"):
        return _clean_json_value({
            "schema": "scoutfootball.world-cup-knockout-match-briefing",
            "version": "1.0.0",
            "status": "not_ready",
            "knockout_context": context,
            "fixture": {"home_team": match.get("home"), "away_team": match.get("away")},
            "limitations": [
                "This knockout slot has an unresolved participant; no opponent or "
                "briefing is inferred.",
            ],
        })
    briefing = get_world_cup_match_briefing(match["home"], match["away"])
    if briefing.get("error"):
        return _clean_json_value({
            "schema": "scoutfootball.world-cup-knockout-match-briefing",
            "version": "1.0.0",
            "status": "briefing_unavailable",
            "knockout_context": context,
            "fixture": {"home_team": match["home"], "away_team": match["away"]},
            "limitations": [
                "The local match briefing was unavailable for this populated bracket fixture.",
            ],
        })
    briefing["knockout_context"] = context
    briefing["knockout_context"]["source"] = "local application tournament state"
    briefing["limitations"] = [
        *briefing.get("limitations", []),
        "Knockout placement reflects the local bracket state and is not an official "
        "fixture confirmation.",
    ]
    return _clean_json_value(briefing)


def _capture_wc_knockout_prediction_snapshot(state: Any, match_id: str) -> dict[str, Any] | None:
    """Capture the live matchup projection before a local result is recorded.

    This deliberately uses the knockout Bradley-Terry projection, not the
    post-result projection that marks a completed fixture as probability 1.0.
    The snapshot is optional: unavailable squad-strength artifacts must not
    prevent a user from recording a local bracket result.
    """
    from scoutfootball.worldcup.data import project_knockout_probabilities
    from scoutfootball.worldcup.tournament import get_knockout_overview

    try:
        overview = get_knockout_overview(state)
        _squads, strengths = _get_wc_enriched_squads()
        if not overview.get("generated") or not strengths:
            return None
        projection = project_knockout_probabilities(
            overview, strengths, num_simulations=0
        )
        match_probability = next(
            (
                item
                for item in projection.get("match_probabilities", [])
                if item.get("match_id") == match_id
            ),
            None,
        )
        if not match_probability:
            return None
        home = match_probability.get("home")
        away = match_probability.get("away")
        home_probability = match_probability.get("home_win_probability")
        away_probability = match_probability.get("away_win_probability")
        if not home or not away or home_probability is None or away_probability is None:
            return None
        return {
            "schema": "scoutfootball.world-cup-knockout-prediction-snapshot",
            "version": "1.0.0",
            "captured_at": datetime.now(UTC).isoformat(),
            "fixture": {"home_team": home, "away_team": away},
            "prediction": {
                "home_win_probability": home_probability,
                "away_win_probability": away_probability,
                "model_type": "bradley_terry_strength",
                "model_version": "wc-knockout-1.0",
                "home_strength": strengths.get(home, 0.2),
                "away_strength": strengths.get(away, 0.2),
            },
            "source": "pre-recording local knockout bracket projection",
            "limitations": [
                "This is a locally captured pre-recording model snapshot, not an "
                "official fixture or result feed.",
                "The simplified strength model does not include live availability, "
                "tactics, form, or market odds.",
            ],
        }
    except Exception:
        logger.warning("capture wc knockout prediction snapshot failed", exc_info=True)
        return None


def _build_wc_knockout_match_review(state: Any, match_id: str) -> dict[str, Any]:
    """Compare a locally recorded result with its captured pre-result snapshot.

    It is intentionally a one-fixture comparison, not a claim about model
    calibration or predictive quality. Older and non-API bracket entries can
    have a completed result without a snapshot and remain explicitly unknown.
    """
    base = {
        "schema": "scoutfootball.world-cup-knockout-result-review",
        "version": "1.0.0",
        "match_id": match_id,
        "recording_scope": "local application tournament state",
    }
    if not state.knockout or not state.knockout.get("matches"):
        return _clean_json_value({
            **base,
            "status": "not_generated",
            "limitations": ["No local knockout bracket has been generated."],
        })
    match = state.knockout_match_by_id(match_id)
    if not match:
        return _clean_json_value({
            **base,
            "status": "not_found",
            "limitations": ["The requested match ID is not in the local knockout bracket."],
        })
    fixture = {"home_team": match.get("home"), "away_team": match.get("away")}
    outcome = {
        "home_goals": match.get("home_goals"),
        "away_goals": match.get("away_goals"),
        "recorded_winner": match.get("winner"),
        "decided_by": match.get("decided_by"),
    }
    if not match.get("winner"):
        return _clean_json_value({
            **base,
            "status": "not_completed",
            "fixture": fixture,
            "recorded_outcome": outcome,
            "limitations": ["A local result must be recorded before a review is available."],
        })
    snapshot = match.get("prediction_snapshot")
    if not isinstance(snapshot, dict):
        return _clean_json_value({
            **base,
            "status": "snapshot_not_recorded",
            "fixture": fixture,
            "recorded_outcome": outcome,
            "limitations": [
                "This local result has no pre-recording prediction snapshot, so no "
                "retrospective model comparison is inferred.",
            ],
        })
    prediction = snapshot.get("prediction")
    if not isinstance(prediction, dict):
        return _clean_json_value({
            **base,
            "status": "snapshot_unusable",
            "fixture": fixture,
            "recorded_outcome": outcome,
            "limitations": [
                "The stored pre-recording snapshot has no usable matchup probabilities."
            ],
        })
    home_probability = prediction.get("home_win_probability")
    away_probability = prediction.get("away_win_probability")
    home = fixture["home_team"]
    away = fixture["away_team"]
    if not isinstance(home_probability, (int, float)) or not isinstance(
        away_probability, (int, float)
    ):
        return _clean_json_value({
            **base,
            "status": "snapshot_unusable",
            "fixture": fixture,
            "recorded_outcome": outcome,
            "limitations": [
                "The stored pre-recording snapshot has invalid matchup probabilities."
            ],
        })
    if home_probability > away_probability:
        predicted_winner = home
    elif away_probability > home_probability:
        predicted_winner = away
    else:
        predicted_winner = None
    recorded_winner = outcome["recorded_winner"]
    result_label = (
        "no_directional_call" if predicted_winner is None
        else "matched_direction" if predicted_winner == recorded_winner
        else "recorded_upset"
    )
    recorded_probability = home_probability if recorded_winner == home else away_probability
    return _clean_json_value({
        **base,
        "status": "ok",
        "fixture": fixture,
        "recorded_outcome": outcome,
        "prediction_snapshot": snapshot,
        "comparison": {
            "predicted_winner": predicted_winner,
            "recorded_winner": recorded_winner,
            "recorded_winner_probability": recorded_probability,
            "directional_result": result_label,
        },
        "limitations": [
            "This compares one locally recorded result with a captured pre-recording "
            "snapshot; it is not a calibration, accuracy, or official-result assessment.",
            "Clearing the local result also removes this snapshot to avoid retaining "
            "a stale matchup comparison.",
        ],
    })


def get_wc_knockout_match_review(match_id: str) -> dict[str, Any]:
    """Return one local knockout result review."""
    return _build_wc_knockout_match_review(_wc_tournament_state(), match_id)


def get_wc_knockout_review_ledger() -> dict[str, Any]:
    """Return a compact, local-only summary of recorded knockout reviews.

    This aggregates only completed locally recorded bracket entries. It does
    not fill missing snapshots, and the directional counts are explicitly not
    calibration or accuracy metrics.
    """
    state = _wc_tournament_state()
    base = {
        "schema": "scoutfootball.world-cup-knockout-review-ledger",
        "version": "1.0.0",
        "recording_scope": "local application tournament state",
    }
    if not state.knockout or not state.knockout.get("matches"):
        return _clean_json_value({
            **base,
            "status": "not_generated",
            "reviews": [],
            "summary": {"completed_matches": 0, "reviews_with_snapshot": 0},
            "limitations": ["No local knockout bracket has been generated."],
        })
    completed = [
        match for match in state.knockout["matches"] if match.get("winner")
    ]
    reviews = [
        _build_wc_knockout_match_review(state, match["match_id"])
        for match in completed
    ]
    direction_counts = {
        label: sum(
            review.get("comparison", {}).get("directional_result") == label
            for review in reviews
        )
        for label in ("matched_direction", "recorded_upset", "no_directional_call")
    }
    return _clean_json_value({
        **base,
        "status": "ok",
        "reviews": reviews,
        "summary": {
            "completed_matches": len(completed),
            "reviews_with_snapshot": sum(review.get("status") == "ok" for review in reviews),
            "snapshots_missing": sum(
                review.get("status") == "snapshot_not_recorded" for review in reviews
            ),
            **direction_counts,
        },
        "limitations": [
            "This is a local-result audit summary, not an official tournament feed "
            "or a model calibration report.",
            "Completed entries without a captured pre-recording snapshot remain "
            "missing rather than being inferred after the result.",
        ],
    })


def generate_wc_knockout_bracket() -> dict:
    """Generate the knockout bracket from current group standings and persist."""
    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        generate_knockout_bracket,
        save_state,
    )

    state = _wc_tournament_state()
    try:
        ko = generate_knockout_bracket(state)
    except ValueError as exc:
        return _clean_json_value({"status": "error", "message": str(exc)})
    state.knockout = ko
    save_state(state, DEFAULT_STATE_PATH)
    return _clean_json_value({
        "status": "ok",
        "generated": True,
        "provisional": ko["provisional"],
        "total_matches": len(ko["matches"]),
        "saved_to": DEFAULT_STATE_PATH,
    })


def apply_wc_knockout_result(
    match_id: str,
    home_goals: int,
    away_goals: int,
    penalties_winner: str | None = None,
) -> dict:
    """Record a knockout match result and auto-advance the winner."""
    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        apply_knockout_result,
        save_state,
    )

    state = _wc_tournament_state()
    prediction_snapshot = _capture_wc_knockout_prediction_snapshot(state, match_id)
    try:
        apply_knockout_result(
            state,
            match_id,
            home_goals,
            away_goals,
            penalties_winner=penalties_winner,
        )
    except ValueError as exc:
        return _clean_json_value({"status": "error", "message": str(exc)})

    match = state.knockout_match_by_id(match_id)
    if prediction_snapshot is not None:
        match["prediction_snapshot"] = prediction_snapshot
    save_state(state, DEFAULT_STATE_PATH)
    return _clean_json_value({
        "status": "ok",
        "match_id": match_id,
        "home": match["home"],
        "away": match["away"],
        "home_goals": home_goals,
        "away_goals": away_goals,
        "winner": match["winner"],
        "decided_by": match.get("decided_by"),
        "prediction_snapshot_recorded": prediction_snapshot is not None,
        "saved_to": DEFAULT_STATE_PATH,
    })


def clear_wc_knockout_result(match_id: str) -> dict:
    """Clear a knockout match result (cascades to downstream matches)."""
    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        clear_knockout_result,
        save_state,
    )

    state = _wc_tournament_state()
    try:
        clear_knockout_result(state, match_id)
    except ValueError as exc:
        return _clean_json_value({"status": "error", "message": str(exc)})
    save_state(state, DEFAULT_STATE_PATH)
    return _clean_json_value({
        "status": "ok",
        "match_id": match_id,
        "cleared": True,
        "saved_to": DEFAULT_STATE_PATH,
    })


def get_wc_knockout_probabilities() -> dict:
    """Project per-matchup win probabilities for the live knockout bracket.

    Uses the Bradley-Terry strength model to compute home/away win
    probabilities for each match with both teams filled. When all R32
    matches have teams, also runs Monte Carlo tournament win odds
    respecting already-completed matches.
    """
    from scoutfootball.worldcup.data import project_knockout_probabilities
    from scoutfootball.worldcup.tournament import get_knockout_overview

    state = _wc_tournament_state()
    overview = get_knockout_overview(state)
    if not overview.get("generated"):
        return _clean_json_value({
            "status": "error",
            "message": (
                "No knockout bracket generated. "
                "Call /world-cup/tournament/knockout/generate first."
            ),
        })

    enriched_squads, strengths = _get_wc_enriched_squads()
    if not enriched_squads:
        return _clean_json_value({
            "status": "error",
            "message": "World Cup squad data not available for strength model.",
        })

    result = project_knockout_probabilities(overview, strengths)
    return _clean_json_value(result)


def get_wc_qualification_impact(group: str) -> dict:
    """Return the local standings impact for a selected World Cup group."""
    from scoutfootball.worldcup.tournament import qualification_impact

    return _clean_json_value(qualification_impact(_wc_tournament_state(), group))


def get_wc_group_tiebreak_diagnostics(group: str) -> dict:
    """Return local tied-cluster diagnostics for one group standings table."""
    from scoutfootball.worldcup.tournament import group_tiebreak_diagnostics

    return _clean_json_value(group_tiebreak_diagnostics(_wc_tournament_state(), group))


def get_wc_knockout_scenarios(team: str, num_simulations: int = 5000) -> dict:
    """Return knockout advancement scenarios for a specific team.

    Shows the team's current championship probability and what-if analysis
    for each remaining knockout stage (win/lose championship impact).
    """
    from scoutfootball.worldcup.data import compute_knockout_scenarios
    from scoutfootball.worldcup.tournament import get_knockout_overview

    state = _wc_tournament_state()
    overview = get_knockout_overview(state)
    if not overview.get("generated"):
        return _clean_json_value({
            "status": "error",
            "message": (
                "No knockout bracket generated. "
                "Call /world-cup/tournament/knockout/generate first."
            ),
        })

    enriched_squads, strengths = _get_wc_enriched_squads()
    if not enriched_squads:
        return _clean_json_value({
            "status": "error",
            "message": "World Cup squad data not available for strength model.",
        })

    result = compute_knockout_scenarios(
        overview, strengths, team, num_simulations=num_simulations
    )
    return _clean_json_value(result)


def get_wc_group_stage_simulation(
    mode: str = "random", num_simulations: int = 1000
) -> dict:
    """Simulate remaining group-stage matches and report advancement odds.

    *mode* is ``"random"`` (uniform) or ``"strength"`` (Bradley-Terry-biased).
    """
    from scoutfootball.worldcup.data import simulate_group_stage

    state = _wc_tournament_state()

    strengths: dict[str, float] | None = None
    if mode == "strength":
        enriched_squads, strengths = _get_wc_enriched_squads()
        if not enriched_squads:
            return _clean_json_value({
                "status": "error",
                "message": "World Cup squad data not available for strength model.",
            })

    result = simulate_group_stage(
        state,
        team_strengths=strengths,
        num_simulations=num_simulations,
        mode=mode,
    )
    return _clean_json_value(result)


def export_wc_tournament_state() -> dict:
    """Export the full tournament state as a shareable JSON string.

    Returns the complete state (matches + results + knockout) encoded as
    a base64-URL-safe string that can be shared via URL or saved to a file.
    The importing side uses ``import_wc_tournament_state`` to reconstruct.
    """
    import base64
    import json

    from scoutfootball.worldcup.tournament import state_to_dict

    state = _wc_tournament_state()
    state_dict = state_to_dict(state)
    json_bytes = json.dumps(state_dict, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(json_bytes).decode("ascii")
    return _clean_json_value({
        "status": "ok",
        "format": "base64url-json-v1",
        "schema_version": state_dict.get("schema_version", "1.0.0"),
        "state_size": len(json_bytes),
        "encoded": encoded,
        "exported_at": state_dict.get("updated_at", ""),
    })


def _decode_wc_tournament_import(encoded: str) -> tuple[Any | None, dict | None]:
    """Decode an imported tournament state without writing local state."""
    import base64
    import json

    from scoutfootball.worldcup.tournament import (
        state_from_dict,
        validate_tournament_state_integrity,
    )

    try:
        # Add padding if missing
        padded = encoded + "=" * (4 - len(encoded) % 4) if len(encoded) % 4 else encoded
        json_bytes = base64.urlsafe_b64decode(padded)
        state_dict = json.loads(json_bytes.decode("utf-8"))
    except Exception as exc:
        logger.warning("decode wc tournament import failed", exc_info=True)
        return None, _clean_json_value({
            "status": "error",
            "code": "decode_failed",
            "message": f"Failed to decode state: {exc}",
        })

    try:
        state = state_from_dict(state_dict, validate_integrity=False)
    except ValueError as exc:
        return None, _clean_json_value({
            "status": "error",
            "code": "invalid_state",
            "message": str(exc),
        })

    integrity_errors = validate_tournament_state_integrity(state)
    if integrity_errors:
        return None, _clean_json_value({
            "status": "error",
            "code": "integrity_failed",
            "message": "Tournament state failed integrity validation.",
            "integrity_errors": integrity_errors,
            "recording_scope": "local application tournament state",
        })

    return state, None


def _wc_import_state_counts(state: Any) -> dict[str, int]:
    """Return bounded counts used by import preview and confirmation UI."""
    knockout_matches = (state.knockout or {}).get("matches", [])
    return {
        "group_results": len(state.results),
        "knockout_matches_completed": sum(
            bool(match.get("winner")) for match in knockout_matches
        ),
        "knockout_prediction_snapshots": sum(
            isinstance(match.get("prediction_snapshot"), dict)
            for match in knockout_matches
        ),
    }


def _wc_tournament_state_fingerprint(state: Any) -> str:
    """Return a stable local-state version token for import confirmation."""
    import hashlib
    import json

    from scoutfootball.worldcup.tournament import state_to_dict

    payload = json.dumps(
        state_to_dict(state), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _wc_import_result_change_ledger(current: Any, incoming: Any, *, limit: int = 20) -> dict:
    """Describe bounded group-result replacement effects in schedule order."""
    changes: list[dict] = []
    for match in current.matches:
        match_id = match["match_id"]
        before = current.results.get(match_id)
        after = incoming.results.get(match_id)
        if before == after:
            continue
        if before is None:
            change_type = "added"
        elif after is None:
            change_type = "removed"
        else:
            change_type = "changed"
        changes.append({
            "match_id": match_id,
            "group": match.get("group"),
            "home": match.get("home"),
            "away": match.get("away"),
            "change_type": change_type,
            "current_result": before,
            "incoming_result": after,
        })
    return {
        "items": changes[:limit],
        "total": len(changes),
        "truncated": len(changes) > limit,
    }


def _wc_import_knockout_change_ledger(current: Any, incoming: Any, *, limit: int = 20) -> dict:
    """Describe bounded knockout record effects without interpreting them as facts."""
    def indexed_matches(state: Any) -> dict[str, dict]:
        matches = (state.knockout or {}).get("matches", [])
        return {
            match["match_id"]: match
            for match in matches
            if isinstance(match, dict) and isinstance(match.get("match_id"), str)
        }

    current_matches = indexed_matches(current)
    incoming_matches = indexed_matches(incoming)
    changes: list[dict] = []
    for match_id in sorted(set(current_matches) | set(incoming_matches)):
        before = current_matches.get(match_id)
        after = incoming_matches.get(match_id)
        if before == after:
            continue
        if before is None:
            change_type = "added"
        elif after is None:
            change_type = "removed"
        else:
            change_type = "changed"
        reference = after or before or {}
        changes.append({
            "match_id": match_id,
            "round": reference.get("round"),
            "home": reference.get("home"),
            "away": reference.get("away"),
            "change_type": change_type,
            "current_completed": bool((before or {}).get("winner")),
            "incoming_completed": bool((after or {}).get("winner")),
            "current_snapshot_recorded": isinstance(
                (before or {}).get("prediction_snapshot"), dict
            ),
            "incoming_snapshot_recorded": isinstance(
                (after or {}).get("prediction_snapshot"), dict
            ),
        })
    return {
        "items": changes[:limit],
        "total": len(changes),
        "truncated": len(changes) > limit,
    }


def preview_wc_tournament_import(encoded: str) -> dict:
    """Validate an import and report bounded local-state replacement risks."""
    incoming, error = _decode_wc_tournament_import(encoded)
    if error:
        return error
    current = _wc_tournament_state()
    current_result_ids = set(current.results)
    incoming_result_ids = set(incoming.results)
    changed_results = sum(
        current.results.get(match_id) != incoming.results.get(match_id)
        for match_id in current_result_ids & incoming_result_ids
    )
    current_counts = _wc_import_state_counts(current)
    incoming_counts = _wc_import_state_counts(incoming)
    result_change_ledger = _wc_import_result_change_ledger(current, incoming)
    knockout_change_ledger = _wc_import_knockout_change_ledger(current, incoming)
    return _clean_json_value({
        "schema": "scoutfootball.world-cup-tournament-import-preview",
        "version": "1.0.0",
        "status": "ok",
        "recording_scope": "local application tournament state",
        "current_state_fingerprint": _wc_tournament_state_fingerprint(current),
        "incoming": {
            "schema_version": incoming.schema_version,
            "matches": len(incoming.matches),
            **incoming_counts,
        },
        "current": {
            "schema_version": current.schema_version,
            "matches": len(current.matches),
            **current_counts,
        },
        "differences": {
            "group_results_added": len(incoming_result_ids - current_result_ids),
            "group_results_removed": len(current_result_ids - incoming_result_ids),
            "group_results_changed": changed_results,
            "knockout_snapshots_removed": max(
                0,
                current_counts["knockout_prediction_snapshots"]
                - incoming_counts["knockout_prediction_snapshots"],
            ),
        },
        "result_changes": result_change_ledger,
        "knockout_changes": knockout_change_ledger,
        "requires_confirmation": True,
        "limitations": [
            "Preview validates the encoded local tournament state but does not write it.",
            "Confirming import replaces the entire local application tournament "
            "state; it is not a merge or official result synchronization.",
        ],
    })


def import_wc_tournament_state(
    encoded: str, *, expected_current_fingerprint: str | None = None
) -> dict:
    """Import a shared tournament state and persist it after UI confirmation.

    Programmatic callers remain supported; the application UI first calls the
    preview endpoint and requires an explicit confirmation before this write.
    """
    from scoutfootball.worldcup.tournament import DEFAULT_STATE_PATH, save_state

    state, error = _decode_wc_tournament_import(encoded)
    if error:
        return error

    if expected_current_fingerprint is not None:
        current_fingerprint = _wc_tournament_state_fingerprint(_wc_tournament_state())
        if current_fingerprint != expected_current_fingerprint:
            return _clean_json_value({
                "status": "error",
                "code": "stale_preview",
                "message": (
                    "Local tournament state changed after preview; "
                    "preview again before importing."
                ),
                "recording_scope": "local application tournament state",
            })

    save_state(state, DEFAULT_STATE_PATH)
    return _clean_json_value({
        "status": "ok",
        "imported": True,
        "schema_version": state.schema_version,
        "matches": len(state.matches),
        "results": len(state.results),
        "has_knockout": bool(state.knockout),
        "saved_to": str(DEFAULT_STATE_PATH),
    })

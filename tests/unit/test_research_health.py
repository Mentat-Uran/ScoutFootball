"""Tests for the five-layer research health calculator (PRS-0 R-003/R-004).

Covers the fail-closed verdict: a stale, unreviewable, synthetic or
non-independent-label rating system must be reported as ``not_ready`` and can
no longer be hidden behind a top-level ``ok``.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.research_health import (
    LINEAGE_OK,
    LINEAGE_STALE,
    LINEAGE_UNVERIFIED,
    READINESS_BLOCKED,
    READINESS_INSUFFICIENT,
    READINESS_READY,
    REVIEWABILITY_NONE,
    REVIEWABILITY_OK,
    STORAGE_DEGRADED,
    STORAGE_OK,
    VERDICT_NOT_READY,
    VERDICT_READY,
    VERDICT_UNAVAILABLE,
    build_research_health_report,
)


def _sha256_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(root, content: dict | None = None) -> str:
    """Write rating_feature_matrix_manifest.json; return sha256[:16] of file."""
    path = root / "data" / "gold" / "feature_store" / "rating_feature_matrix_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = content or {"artifact": "rating_feature_matrix", "total_rows": 1}
    path.write_text(json.dumps(body), encoding="utf-8")
    return _sha256_file(path)[:16]


def _write_feature_matrix(root, rows: int = 2) -> None:
    path = root / "data" / "gold" / "feature_store" / "rating_feature_matrix.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"player_id": ["p1", "p2"][:rows], "season_id": ["2425"] * rows}).to_parquet(
        path, index=False
    )


def _write_active_rating(root, *, synthetic: bool = False) -> None:
    path = root / "data" / "gold" / "feature_store" / "player_ratings_optimized.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({"player_id": ["p1", "p2"], "optimized_score": [0.6, 0.4]})
    if synthetic:
        df["is_synthetic"] = [True, True]
    df.to_parquet(path, index=False)


def _write_truth_labels(root, *, sources: list[str]) -> None:
    """Write truth labels with the given label_source values (one row each)."""
    path = root / "data" / "gold" / "feature_store" / "player_truth_labels.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        {
            "player_id": [f"p{i}" for i in range(len(sources))],
            "season": ["2425"] * len(sources),
            "label_source": sources,
            "label_confidence": ["high"] * len(sources),
            "label_value": [0.5] * len(sources),
            "as_of_date": ["2025-05-01"] * len(sources),
            "position_scope": ["all"] * len(sources),
            "manual_review_flag": [False] * len(sources),
        }
    )
    df.to_parquet(path, index=False)


def _write_run(
    root,
    name: str,
    *,
    manifest_hash: str | None,
    activated: bool = False,
    reviewable: bool = True,
) -> str:
    """Write a model run directory; returns the run_id (name).

    When ``manifest_hash`` is provided it is recorded as the training-time
    feature_manifest.hash, so lineage matches (or mismatches) the on-disk
    manifest. When ``activated`` is True, the meta.json activation block is
    set to status="activated" and an active_model block is written to
    optimized_params_meta.json.
    """
    run = root / "data" / "models" / "runs" / name
    run.mkdir(parents=True, exist_ok=True)
    np.save(run / "optimized_params.npy", np.array([1.0]))
    meta: dict = {
        "lineage": {
            "status": "recorded" if reviewable else "partial",
            "dataset_snapshot": {"input_hash": "input"} if reviewable else {"input_hash": None},
            "feature_manifest": {"hash": manifest_hash} if manifest_hash else {},
        },
        "train_seasons": ["2324"] if reviewable else [],
        "test_seasons": ["2425"] if reviewable else [],
        "metrics": (
            {"baseline_test": {"spearman": 0.5}, "optimized_test": {"spearman": 0.6}}
            if reviewable
            else {"baseline_test": "{'spearman': 0.5}"}
        ),
        "error_cases": {"over_estimated": [{"team": "A"}]} if reviewable else {},
        "data_coverage": {
            "artifact_statuses": [
                {"source": "fbref_standard", "status": "loaded"},
                {"source": "football_data_results", "status": "loaded"},
            ]
        },
    }
    if reviewable:
        ratings_path = run / "player_ratings_candidate.parquet"
        pd.DataFrame(
            {"player": ["A", "B"], "optimized_score": [0.6, 0.4]}
        ).to_parquet(ratings_path, index=False)
        meta["candidate_artifacts"] = {
            "ratings": {
                "path": "player_ratings_candidate.parquet",
                "sha256": _sha256_file(ratings_path),
                "rows": 2,
            }
        }
    if activated:
        meta["activation"] = {
            "status": "activated",
            "backup_id": "backup-1",
            "activated_at": "2026-07-29T00:00:00Z",
            "decision": "test promote",
        }
        active_meta_path = (
            root / "data" / "gold" / "feature_store" / "optimized_params_meta.json"
        )
        active_meta_path.parent.mkdir(parents=True, exist_ok=True)
        active_meta = {
            "optimizer": "adamw",
            "active_model": {
                "schema": "scoutfootball.local-model-lifecycle",
                "version": "1.0",
                "run_id": name,
                "backup_id": "backup-1",
                "activated_at": "2026-07-29T00:00:00Z",
                "decision": "test promote",
            },
        }
        active_meta_path.write_text(json.dumps(active_meta), encoding="utf-8")
    (run / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return name


def _build_healthy_workspace(root) -> str:
    """Build a workspace where every layer should be ok/ready.

    Returns the manifest hash so individual tests can perturb one layer.
    """
    manifest_hash = _write_manifest(root)
    _write_feature_matrix(root)
    _write_active_rating(root, synthetic=False)
    _write_truth_labels(root, sources=["scouting_review", "award"])
    _write_run(
        root,
        "20260729T000000Z-healthy",
        manifest_hash=manifest_hash,
        activated=True,
        reviewable=True,
    )
    return manifest_hash


# ---------------------------------------------------------------------------
# Layer-level tests
# ---------------------------------------------------------------------------


def test_empty_workspace_is_not_ready(tmp_path) -> None:
    """No artifacts at all → storage degraded, verdict not_ready/unavailable."""
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    assert report["verdict"] in (VERDICT_NOT_READY, VERDICT_UNAVAILABLE)
    assert report["storage_health"]["status"] == STORAGE_DEGRADED
    assert report["lineage_health"]["status"] == LINEAGE_UNVERIFIED
    assert report["model_reviewability"]["status"] == REVIEWABILITY_NONE
    # Empty workspace has no truth labels file → readiness is unavailable
    # (cannot assess) rather than blocked. This is honest: we do not claim
    # the system is blocked when we cannot even read the labels.
    assert report["research_readiness"]["status"] in (
        READINESS_BLOCKED,
        READINESS_INSUFFICIENT,
        "unavailable",
    )
    assert report["blocking_reasons"]


def test_healthy_workspace_is_ready(tmp_path) -> None:
    """All layers ok + independent labels + non-synthetic → verdict ready."""
    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    assert report["verdict"] == VERDICT_READY, report
    assert report["storage_health"]["status"] == STORAGE_OK
    assert report["lineage_health"]["status"] == LINEAGE_OK
    assert report["model_reviewability"]["status"] == REVIEWABILITY_OK
    assert report["research_readiness"]["status"] == READINESS_READY
    assert report["blocking_reasons"] == []


def test_stale_lineage_forces_not_ready(tmp_path) -> None:
    """Manifest rebuilt after training → lineage stale, verdict not_ready."""
    manifest_hash = _build_healthy_workspace(tmp_path)
    # Rewrite the manifest with different content → file hash changes while
    # the activated run still records the old training-time hash.
    _write_manifest(tmp_path, content={"artifact": "rating_feature_matrix", "total_rows": 999})
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    assert report["lineage_health"]["status"] == LINEAGE_STALE
    assert report["lineage_health"]["evidence"]["training_manifest_hash"] == manifest_hash
    assert (
        report["lineage_health"]["evidence"]["current_manifest_hash"]
        != manifest_hash
    )
    assert report["verdict"] == VERDICT_NOT_READY
    assert any("lineage_health" in r for r in report["blocking_reasons"])


def test_zero_reviewable_runs_forces_not_ready(tmp_path) -> None:
    """All runs not_reviewable → reviewability none, verdict not_ready."""
    manifest_hash = _build_healthy_workspace(tmp_path)
    # Overwrite the healthy run with an incomplete (not_reviewable) one that
    # is still activated, so lineage can still be verified but reviewability
    # drops to none.
    import shutil

    shutil.rmtree(tmp_path / "data" / "models" / "runs" / "20260729T000000Z-healthy")
    _write_run(
        tmp_path,
        "20260729T000000Z-broken",
        manifest_hash=manifest_hash,
        activated=True,
        reviewable=False,
    )
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    assert report["model_reviewability"]["status"] == REVIEWABILITY_NONE
    assert report["verdict"] == VERDICT_NOT_READY
    assert any("model_reviewability" in r for r in report["blocking_reasons"])


def test_only_expert_tier_labels_forces_blocked(tmp_path) -> None:
    """Labels are all self-referential expert_tier → readiness blocked."""
    _build_healthy_workspace(tmp_path)
    # Replace truth labels with only expert_tier (model-derived, not independent).
    _write_truth_labels(tmp_path, sources=["expert_tier", "expert_tier"])
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    assert report["research_readiness"]["status"] == READINESS_BLOCKED
    assert report["research_readiness"]["evidence"]["label_report"]["eligible_rows"] == 0
    assert report["verdict"] == VERDICT_NOT_READY
    readiness_reasons = report["research_readiness"]["evidence"]["blocking_reasons"]
    assert any("no supervision-eligible labels" in r for r in readiness_reasons)


def test_synthetic_active_rating_forces_blocked(tmp_path) -> None:
    """Active rating is fully synthetic → readiness blocked, verdict not_ready."""
    _build_healthy_workspace(tmp_path)
    _write_active_rating(tmp_path, synthetic=True)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    assert report["research_readiness"]["status"] == READINESS_BLOCKED
    assert report["research_readiness"]["evidence"]["active_rating_is_synthetic"] is True
    assert report["verdict"] == VERDICT_NOT_READY
    readiness_reasons = report["research_readiness"]["evidence"]["blocking_reasons"]
    assert any("synthetic" in r for r in readiness_reasons)


def test_legacy_rating_without_activated_run_is_unverified(tmp_path) -> None:
    """Active rating exists but no activated run → lineage/freshness unverified."""
    manifest_hash = _write_manifest(tmp_path)
    _write_feature_matrix(tmp_path)
    _write_active_rating(root=tmp_path, synthetic=False)
    _write_truth_labels(tmp_path, sources=["scouting_review"])
    # A reviewable run that is NOT activated — the active rating is a legacy
    # artifact with no chain of custody.
    _write_run(
        tmp_path,
        "20260729T000000Z-notactivated",
        manifest_hash=manifest_hash,
        activated=False,
        reviewable=True,
    )
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    assert report["lineage_health"]["status"] == LINEAGE_UNVERIFIED
    assert "no activated model run" in report["lineage_health"]["evidence"]["reason"]
    assert report["verdict"] == VERDICT_NOT_READY


def test_rating_older_than_feature_matrix_is_stale(tmp_path) -> None:
    """Active rating mtime < feature matrix mtime → freshness stale."""
    _build_healthy_workspace(tmp_path)
    # Touch the feature matrix so it is newer than the active rating.
    import os
    import time

    fm = tmp_path / "data" / "gold" / "feature_store" / "rating_feature_matrix.parquet"
    rating = tmp_path / "data" / "gold" / "feature_store" / "player_ratings_optimized.parquet"
    # Ensure feature matrix mtime is strictly after rating mtime.
    now = time.time()
    os.utime(rating, (now, now))
    os.utime(fm, (now + 120, now + 120))
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    # Lineage is still ok (hash matches), but freshness drops to stale.
    assert report["lineage_health"]["status"] == LINEAGE_OK
    assert report["active_rating_freshness"]["status"] == "stale"
    assert report["verdict"] == VERDICT_NOT_READY


# ---------------------------------------------------------------------------
# Top-level detailed health integration (R-004 fix)
# ---------------------------------------------------------------------------


def test_research_health_section_is_in_detailed_health(tmp_path, monkeypatch) -> None:
    """get_detailed_health includes a research_health summary section."""
    _build_healthy_workspace(tmp_path)
    from scoutfootball.api import _detailed_health_cache, get_detailed_health

    monkeypatch.setattr(
        "scoutfootball.api._settings",
        lambda: PlatformSettings.from_root(tmp_path),
    )
    _detailed_health_cache.invalidate("get_detailed_health")
    report = get_detailed_health(force_refresh=True)
    assert "research_health" in report
    assert report["research_health"]["verdict"] == VERDICT_READY


def test_detailed_health_top_status_degrades_when_research_not_ready(
    tmp_path, monkeypatch
) -> None:
    """R-004 fix: 0 reviewable runs forces top-level status to degraded.

    Before PRS-0, model_admission's reviewable_run_count=0 was invisible to
    the top-level status because model_admission's own status was hardcoded
    "ok". Now research_health surfaces it as not_ready, which degrades the
    top-level detailed-health status.
    """
    # Empty workspace: no runs → reviewability none → research not_ready.
    monkeypatch.setattr(
        "scoutfootball.api._settings",
        lambda: PlatformSettings.from_root(tmp_path),
    )
    # Stub the other expensive builders to ok so the only failure path is
    # research_health (isolating the R-004 fix from validation/contract drift).

    def _ok_validation(_settings):
        return {
            "status": "pass",
            "total_checks": 1,
            "passed_count": 1,
            "failed_count": 0,
            "failures": [],
            "checks": [],
            "summary": "ok",
        }

    def _ok_model_admission(_settings):
        return {
            "status": "ok",
            "reviewable_run_count": 0,
            "not_reviewable_run_count": 0,
            "run_count": 0,
            "limitations": [],
        }

    def _ok_contract_quality(_settings):
        return {
            "status": "pass",
            "checks_count": 0,
            "failed_checks": [],
            "incomplete_checks": [],
            "limitations": [],
        }

    def _ok_source_health(_settings):
        return {
            "status": "ok",
            "registered_source_count": 0,
            "sources_with_snapshot": 0,
            "sources_without_snapshot": 0,
            "sources": [],
        }

    monkeypatch.setattr(
        "scoutfootball.api._build_validation_section", _ok_validation
    )
    monkeypatch.setattr(
        "scoutfootball.api._build_model_admission_section", _ok_model_admission
    )
    monkeypatch.setattr(
        "scoutfootball.api._build_contract_quality_section", _ok_contract_quality
    )
    monkeypatch.setattr(
        "scoutfootball.api._build_source_health_section", _ok_source_health
    )
    from scoutfootball.api import _detailed_health_cache, get_detailed_health

    _detailed_health_cache.invalidate("get_detailed_health")
    report = get_detailed_health(force_refresh=True)
    # Top-level status must NOT be "ok" now that research_health is not_ready.
    assert report["status"] != "ok"
    assert report["status"] == "degraded"
    assert report["research_health"]["verdict"] in (
        VERDICT_NOT_READY,
        VERDICT_UNAVAILABLE,
    )
    assert any(
        r.startswith("research_health:") for r in report["failed_sections"]
    )


# ── feature_coverage and data_grain evidence sections (PRS-0 R-003) ──


def _write_rich_feature_matrix(root) -> None:
    """Write a rating_feature_matrix with _missing markers and FIELD_GROUPS cols."""
    path = root / "data" / "gold" / "feature_store" / "rating_feature_matrix.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "player_id": ["p1", "p2", "p3"],
            "season_id": ["2425", "2425", "2425"],
            "tackles": [1.0, 2.0, 3.0],
            "interceptions": [0.5, 1.0, 1.5],
            "tackles_won": [0.5, 1.0, 1.5],
            "fouls_committed": [1, 2, 3],
            "fouls_drawn": [1, 2, 3],
            "crosses": [0, 1, 2],
            "own_goals": [0, 0, 0],
            "xt_total": [None, 0.1, 0.2],
            "xt_per_90": [None, 0.01, 0.02],
            "vaep_total": [None, 0.3, 0.4],
            "vaep_per_90": [None, 0.03, 0.04],
            "defense_missing": [False, False, False],
            "xT_VAEP_missing": [True, False, False],
        }
    ).to_parquet(path, index=False)


def _write_player_match_with_grain(root) -> None:
    """Write a player_match parquet with data_granularity and source_name."""
    path = root / "data" / "gold" / "feature_store" / "player_match.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "player_id": ["p1", "p2", "p3", "p4"],
            "season_id": ["2425"] * 4,
            "data_granularity": ["season_proxy", "season_proxy", "match", "match"],
            "source_name": ["understat", "fbref", "statsbomb_open", "statsbomb_open"],
        }
    ).to_parquet(path, index=False)


def test_feature_coverage_reports_missing_rates(tmp_path) -> None:
    """feature_coverage surfaces per-group missing_rate using _missing markers."""
    _write_rich_feature_matrix(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)

    fc = report["feature_coverage"]
    assert fc["status"] == "ok"
    groups = fc["evidence"]["field_groups"]
    # defense_missing marker is all False → missing_rate 0.0
    assert groups["defense"]["missing_rate"] == 0.0
    # xT_VAEP_missing marker has 1/3 True → missing_rate ~0.333
    assert abs(groups["xT_VAEP"]["missing_rate"] - (1.0 / 3.0)) < 1e-6
    # possession and goalkeeper have no fields in schema → missing_rate 1.0
    assert groups["possession"]["missing_rate"] == 1.0
    assert groups["goalkeeper"]["missing_rate"] == 1.0


def test_feature_coverage_unavailable_when_matrix_missing(tmp_path) -> None:
    """When rating_feature_matrix is absent, feature_coverage is unavailable."""
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    assert report["feature_coverage"]["status"] == "unavailable"


def test_data_grain_reports_granularity_distribution(tmp_path) -> None:
    """data_grain surfaces data_granularity and source_name value_counts."""
    _write_player_match_with_grain(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)

    dg = report["data_grain"]
    assert dg["status"] == "ok"
    assert dg["evidence"]["total_rows"] == 4
    assert dg["evidence"]["data_granularity"] == {
        "season_proxy": 2,
        "match": 2,
    }
    assert dg["evidence"]["source_name"] == {
        "understat": 1,
        "fbref": 1,
        "statsbomb_open": 2,
    }


def test_data_grain_unavailable_when_player_match_missing(tmp_path) -> None:
    """When player_match is absent, data_grain is unavailable."""
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    assert report["data_grain"]["status"] == "unavailable"


def test_feature_coverage_and_data_grain_do_not_affect_verdict(tmp_path) -> None:
    """Evidence-only sections must not change the fail-closed verdict.

    Even if feature_coverage and data_grain report ok, the verdict is still
    driven by the five layers. An empty workspace (no runs, no labels) must
    remain not_ready regardless of these evidence sections.
    """
    _write_rich_feature_matrix(tmp_path)
    _write_player_match_with_grain(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)

    assert report["feature_coverage"]["status"] == "ok"
    assert report["data_grain"]["status"] == "ok"
    # Verdict is still fail-closed (not_ready or unavailable — the latter
    # because no truth_labels were written so research_readiness is
    # unavailable) regardless of these evidence sections being ok.
    assert report["verdict"] in (VERDICT_NOT_READY, VERDICT_UNAVAILABLE)
    assert "feature_coverage" not in report["blocking_reasons"]
    assert "data_grain" not in report["blocking_reasons"]

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


def test_proxy_only_labels_do_not_make_research_ready(tmp_path) -> None:
    """Market value can anchor a proxy model but cannot prove ability truth."""
    manifest_hash = _write_manifest(tmp_path)
    _write_feature_matrix(tmp_path)
    _write_active_rating(tmp_path, synthetic=False)
    _write_truth_labels(tmp_path, sources=["transfermarkt_value"])
    _write_run(
        tmp_path,
        "20260729T000000Z-proxy-only",
        manifest_hash=manifest_hash,
        activated=True,
        reviewable=True,
    )

    report = build_research_health_report(settings=PlatformSettings.from_root(tmp_path))

    assert report["verdict"] == VERDICT_NOT_READY
    assert report["research_readiness"]["status"] == READINESS_BLOCKED
    evidence = report["research_readiness"]["evidence"]
    assert evidence["label_report"]["proxy_rows"] == 1
    assert evidence["label_report"]["independent_rows"] == 0
    assert any(
        "no independent player-ability labels" in reason
        for reason in evidence["blocking_reasons"]
    )


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
# identity_registry evidence section (PRS-1 R-005)
# ---------------------------------------------------------------------------


def test_identity_registry_section_present_and_empty_by_default(tmp_path) -> None:
    """No registry file → identity_registry section shows zero counts.

    An empty registry is the honest default before any human decision
    has been recorded; it must not block the verdict (unresolved status
    is not a failure).
    """
    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    section = report["identity_registry"]
    assert section["schema"] == "scoutfootball.identity_registry"
    assert section["schema_version"] == "1.0"
    assert section["total_records"] == 0
    assert section["active_mapping_count"] == 0
    assert section["records_by_action"] == {"confirmed": 0, "revoked": 0}
    assert section["active_mappings_by_source"] == {}
    assert section["latest_revision"] == 0
    assert section["latest_recorded_at"] is None
    # Must not appear in blocking_reasons — unresolved is not a failure.
    assert all("identity_registry" not in r for r in report["blocking_reasons"])


def test_identity_registry_section_reflects_recorded_decisions(tmp_path) -> None:
    """A confirmed mapping is reflected in the health report's counts."""
    from scoutfootball.evaluation.identity_registry import (
        append_decision,
        build_decision,
        read_registry,
    )

    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    existing = read_registry(settings=settings)
    record = build_decision(
        source_name="fbref",
        source_player_id="lara|1998|ar",
        action="confirmed",
        canonical_player_id="canonical:fbref:lara:1998:ar",
        evidence="transfermarkt snapshot row 12 maps here",
        decided_by="maintainer",
        revision=len(existing) + 1,
    )
    append_decision(record, settings=settings)

    report = build_research_health_report(settings=settings)
    section = report["identity_registry"]
    assert section["total_records"] == 1
    assert section["active_mapping_count"] == 1
    assert section["records_by_action"] == {"confirmed": 1, "revoked": 0}
    assert section["active_mappings_by_source"] == {"fbref": 1}
    assert section["latest_revision"] == 1
    assert section["latest_recorded_at"] == record["recorded_at"]


def test_identity_registry_section_surfaces_revoked_decisions(tmp_path) -> None:
    """A revoked mapping clears active count but stays in total_records."""
    from scoutfootball.evaluation.identity_registry import (
        append_decision,
        build_decision,
        read_registry,
    )

    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    existing = read_registry(settings=settings)
    r1 = build_decision(
        source_name="fbref",
        source_player_id="lara|1998|ar",
        action="confirmed",
        canonical_player_id="canonical:fbref:lara:1998:ar",
        evidence="first attempt",
        decided_by="maintainer",
        revision=len(existing) + 1,
    )
    append_decision(r1, settings=settings)
    r2 = build_decision(
        source_name="fbref",
        source_player_id="lara|1998|ar",
        action="revoked",
        canonical_player_id=None,
        evidence="was wrong; no replacement",
        decided_by="maintainer",
        revision=len(read_registry(settings=settings)) + 1,
    )
    append_decision(r2, settings=settings)

    report = build_research_health_report(settings=settings)
    section = report["identity_registry"]
    assert section["total_records"] == 2
    assert section["active_mapping_count"] == 0
    assert section["records_by_action"] == {"confirmed": 1, "revoked": 1}
    assert section["active_mappings_by_source"] == {}


def test_identity_registry_section_unavailable_on_corrupt_file(tmp_path) -> None:
    """A corrupt registry JSONL is surfaced as unavailable, not crashed."""
    _build_healthy_workspace(tmp_path)
    registry = tmp_path / "data" / "gold" / "identity_registry" / "decisions.jsonl"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text("{not valid json}\n", encoding="utf-8")
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    section = report["identity_registry"]
    assert section["schema"] == "scoutfootball.identity_registry"
    assert section["status"] == "unavailable"
    assert "identity registry read failed" in section["evidence"]["reason"]
    # The verdict is unaffected — the registry is evidence-only.
    assert report["verdict"] == VERDICT_READY


# ---------------------------------------------------------------------------
# canonical_resolution evidence section (PRS-1 R-005 slice 3)
# ---------------------------------------------------------------------------


def _write_player_match_for_resolver(
    root, *, rows: int = 4
) -> None:
    """Write a minimal player_match.parquet the resolver can read."""
    path = root / "data" / "gold" / "feature_store" / "player_match.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        {
            "player_id": ["lara|1998|ar", "understat|12345", "10605", "martin|1997|dk"][:rows],
            "player_name": ["Lara", "Marco", "Stats", "Martin"][:rows],
            "source_name": ["fbref", "understat", "statsbomb_open", "fbref"][:rows],
            "season_id": ["2425"] * rows,
        }
    )
    df.to_parquet(path, index=False)


def test_canonical_resolution_section_unavailable_without_player_match(tmp_path) -> None:
    """No player_match.parquet → canonical_resolution is unavailable.

    The healthy workspace fixture writes rating_feature_matrix.parquet but
    not player_match.parquet, so the resolver cannot run. This is honest:
    the section reports unavailable rather than claiming 0 resolved rows.
    """
    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    section = report["canonical_resolution"]
    assert section["schema"] == "scoutfootball.canonical-resolver"
    assert section["schema_version"] == "1.0.0"
    assert section["status"] == "unavailable"
    assert "player_match.parquet missing" in section["evidence"]["reason"]
    # Evidence-only — must not affect the verdict.
    assert all("canonical_resolution" not in r for r in report["blocking_reasons"])


def test_canonical_resolution_section_all_unresolved_with_empty_registry(tmp_path) -> None:
    """player_match.parquet present + empty registry → ok, all unresolved.

    An all-unresolved result is the honest default before any human
    decision has been recorded; it must not block the verdict.
    """
    _build_healthy_workspace(tmp_path)
    _write_player_match_for_resolver(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    section = report["canonical_resolution"]
    assert section["status"] == "ok"
    evidence = section["evidence"]
    assert evidence["total_rows"] == 4
    assert evidence["resolved_rows"] == 0
    assert evidence["unresolved_rows"] == 4
    assert set(evidence["by_source"].keys()) == {"fbref", "understat", "statsbomb_open"}
    # Unresolved is honest default — verdict is unaffected.
    assert all("canonical_resolution" not in r for r in report["blocking_reasons"])


def test_canonical_resolution_section_reflects_confirmed_mapping(tmp_path) -> None:
    """A confirmed registry decision resolves one row in the derived view."""
    from scoutfootball.evaluation.identity_registry import (
        append_decision,
        build_decision,
        read_registry,
    )

    _build_healthy_workspace(tmp_path)
    _write_player_match_for_resolver(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    existing = read_registry(settings=settings)
    record = build_decision(
        source_name="fbref",
        source_player_id="lara|1998|ar",
        action="confirmed",
        canonical_player_id="canonical:fbref:lara:1998:ar",
        evidence="transfermarkt snapshot row 12 maps here",
        decided_by="maintainer",
        revision=len(existing) + 1,
    )
    append_decision(record, settings=settings)

    report = build_research_health_report(settings=settings)
    section = report["canonical_resolution"]
    assert section["status"] == "ok"
    evidence = section["evidence"]
    assert evidence["resolved_rows"] == 1
    assert evidence["unresolved_rows"] == 3
    assert evidence["distinct_canonical_ids"] == 1
    assert evidence["by_source"]["fbref"] == {"resolved": 1, "unresolved": 1}


def test_canonical_resolution_section_revoked_falls_back_to_unresolved(tmp_path) -> None:
    """A revoked mapping clears the resolved count back to 0."""
    from scoutfootball.evaluation.identity_registry import (
        append_decision,
        build_decision,
    )

    _build_healthy_workspace(tmp_path)
    _write_player_match_for_resolver(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    # Confirm then revoke the same key.
    append_decision(
        build_decision(
            source_name="fbref",
            source_player_id="lara|1998|ar",
            action="confirmed",
            canonical_player_id="canonical:fbref:lara:1998:ar",
            evidence="first attempt",
            decided_by="maintainer",
            revision=1,
        ),
        settings=settings,
    )
    append_decision(
        build_decision(
            source_name="fbref",
            source_player_id="lara|1998|ar",
            action="revoked",
            canonical_player_id=None,
            evidence="was wrong; no replacement",
            decided_by="maintainer",
            revision=2,
        ),
        settings=settings,
    )

    report = build_research_health_report(settings=settings)
    section = report["canonical_resolution"]
    evidence = section["evidence"]
    assert evidence["resolved_rows"] == 0
    assert evidence["unresolved_rows"] == 4


def test_canonical_resolution_section_unavailable_on_corrupt_registry(tmp_path) -> None:
    """A corrupt registry JSONL is surfaced as unavailable, not crashed."""
    _build_healthy_workspace(tmp_path)
    _write_player_match_for_resolver(tmp_path)
    registry = tmp_path / "data" / "gold" / "identity_registry" / "decisions.jsonl"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text("{not valid json}\n", encoding="utf-8")
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    section = report["canonical_resolution"]
    assert section["schema"] == "scoutfootball.canonical-resolver"
    assert section["status"] == "unavailable"
    assert "identity registry read failed" in section["evidence"]["reason"]
    # Verdict is unaffected — the section is evidence-only.
    assert report["verdict"] == VERDICT_READY


# ---------------------------------------------------------------------------
# Source-lineage verification (PRS-0 R-003: manifest → raw snapshot chain)
# ---------------------------------------------------------------------------


def _write_manifest_with_source_lineage(
    root, *, sources: list[dict] | None = None
) -> str:
    """Write a manifest whose source_lineage points at real source files.

    Each entry in *sources* should be ``{"name": ..., "relative_path": ...,
    "content": <bytes>}``. The helper writes the source file, stamps its
    sha256[:16] as ``input_hash``, and records it in the manifest's
    ``source_lineage``. Returns the sha256[:16] of the manifest file itself
    (so callers can build a matching activated run).
    """
    source_lineage: list[dict] = []
    for entry in sources or []:
        rel = entry["relative_path"]
        full = root / "data" / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(entry["content"])
        source_lineage.append({
            "name": entry["name"],
            "relative_path": rel,
            "rows_read": 1,
            "input_hash": _sha256_file(full)[:16],
            "notes": None,
        })
    return _write_manifest(
        root,
        content={
            "artifact": "rating_feature_matrix",
            "total_rows": 1,
            "source_lineage": source_lineage,
        },
    )


def test_source_lineage_drift_forces_stale(tmp_path) -> None:
    """Source parquet rewritten without manifest rebuild → lineage stale.

    Closes the PRS-0 R-003 gap: before this check, upstream parquet could
    be silently rewritten and lineage_health would still report ok because
    the manifest file itself had not changed.
    """
    manifest_hash = _write_manifest_with_source_lineage(
        tmp_path,
        sources=[
            {
                "name": "player_match",
                "relative_path": "gold/feature_store/player_match.parquet",
                "content": b"player_match v1",
            }
        ],
    )
    _write_feature_matrix(tmp_path)
    _write_active_rating(root=tmp_path, synthetic=False)
    _write_truth_labels(tmp_path, sources=["scouting_review"])
    _write_run(
        tmp_path,
        "20260730T000000Z-sourcechain",
        manifest_hash=manifest_hash,
        activated=True,
        reviewable=True,
    )
    # Rewrite the source parquet without rebuilding the manifest. The
    # manifest file hash is unchanged, so the old check would still pass;
    # the new source_lineage check must catch the drift.
    (tmp_path / "data" / "gold" / "feature_store" / "player_match.parquet").write_bytes(
        b"player_match v2 - drifted"
    )
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    assert report["lineage_health"]["status"] == LINEAGE_STALE
    sl = report["lineage_health"]["evidence"]["source_lineage"]
    assert sl["status"] == "stale"
    assert any(s["status"] == "drift" for s in sl["sources"])
    assert report["verdict"] == VERDICT_NOT_READY
    assert any("lineage_health" in r for r in report["blocking_reasons"])


def test_source_lineage_verified_keeps_ok(tmp_path) -> None:
    """All source files match recorded input_hash → lineage ok with evidence."""
    manifest_hash = _write_manifest_with_source_lineage(
        tmp_path,
        sources=[
            {
                "name": "player_match",
                "relative_path": "gold/feature_store/player_match.parquet",
                "content": b"player_match v1",
            },
            {
                "name": "player_rolling",
                "relative_path": "gold/feature_store/player_rolling.parquet",
                "content": b"player_rolling v1",
            },
        ],
    )
    _write_feature_matrix(tmp_path)
    _write_active_rating(root=tmp_path, synthetic=False)
    _write_truth_labels(tmp_path, sources=["scouting_review"])
    _write_run(
        tmp_path,
        "20260730T000000Z-sourcechain-ok",
        manifest_hash=manifest_hash,
        activated=True,
        reviewable=True,
    )
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    assert report["lineage_health"]["status"] == LINEAGE_OK
    sl = report["lineage_health"]["evidence"]["source_lineage"]
    assert sl["status"] == "verified"
    assert len(sl["sources"]) == 2
    assert all(s["status"] == "match" for s in sl["sources"])
    assert "source_lineage verified" in report["lineage_health"]["evidence"]["reason"]


def test_source_lineage_missing_file_is_unverified(tmp_path) -> None:
    """Declared source file is missing → lineage unverified (chain broken)."""
    manifest_hash = _write_manifest_with_source_lineage(
        tmp_path,
        sources=[
            {
                "name": "player_match",
                "relative_path": "gold/feature_store/player_match.parquet",
                "content": b"player_match v1",
            }
        ],
    )
    _write_feature_matrix(tmp_path)
    _write_active_rating(root=tmp_path, synthetic=False)
    _write_truth_labels(tmp_path, sources=["scouting_review"])
    _write_run(
        tmp_path,
        "20260730T000000Z-sourcechain-missing",
        manifest_hash=manifest_hash,
        activated=True,
        reviewable=True,
    )
    # Remove the declared source file. The chain to the raw snapshot is
    # broken (not stale — we cannot compare hashes against a missing file).
    (tmp_path / "data" / "gold" / "feature_store" / "player_match.parquet").unlink()
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    assert report["lineage_health"]["status"] == LINEAGE_UNVERIFIED
    sl = report["lineage_health"]["evidence"]["source_lineage"]
    assert sl["status"] == "broken"
    assert any(s["status"] == "missing" for s in sl["sources"])
    assert report["verdict"] == VERDICT_NOT_READY


def test_source_lineage_absent_keeps_ok_with_note(tmp_path) -> None:
    """Manifest without source_lineage → lineage ok but evidence notes gap.

    Legacy manifests written before source_lineage existed must not be
    downgraded (we cannot verify what was never declared), but the evidence
    must honestly say the raw-snapshot chain is unverified rather than
    silently claiming full lineage.
    """
    manifest_hash = _write_manifest(
        tmp_path,
        content={"artifact": "rating_feature_matrix", "total_rows": 1},
    )
    _write_feature_matrix(tmp_path)
    _write_active_rating(root=tmp_path, synthetic=False)
    _write_truth_labels(tmp_path, sources=["scouting_review"])
    _write_run(
        tmp_path,
        "20260730T000000Z-no-source-lineage",
        manifest_hash=manifest_hash,
        activated=True,
        reviewable=True,
    )
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    assert report["lineage_health"]["status"] == LINEAGE_OK
    sl = report["lineage_health"]["evidence"]["source_lineage"]
    assert sl["status"] == "unverified"
    assert "not declared" in report["lineage_health"]["evidence"]["reason"]


def test_lineage_evidence_includes_training_args(tmp_path) -> None:
    """Activated run with args block → lineage evidence surfaces a summary.

    PRS-0 R-003 wants the lineage chain to surface training configuration,
    not just hashes. The summary is a small subset of args (optimizer,
    learning_rate, seed, etc.); the full args remain in the run's meta.json.
    """
    manifest_hash = _write_manifest(tmp_path)
    _write_feature_matrix(tmp_path)
    _write_active_rating(root=tmp_path, synthetic=False)
    _write_truth_labels(tmp_path, sources=["scouting_review"])
    _write_run(
        tmp_path,
        "20260730T000000Z-with-args",
        manifest_hash=manifest_hash,
        activated=True,
        reviewable=True,
    )
    # Inject an args block into the activated run's meta.json.
    run_meta_path = (
        tmp_path
        / "data"
        / "models"
        / "runs"
        / "20260730T000000Z-with-args"
        / "meta.json"
    )
    meta = json.loads(run_meta_path.read_text(encoding="utf-8"))
    meta["args"] = {
        "optimizer": "adamw",
        "learning_rate": 0.001,
        "epochs": 50,
        "seed": 42,
        "feature_set": "v1",
        # Large/noisy fields that should NOT appear in the summary:
        "data_paths": ["a", "b", "c"],
        "cohort_filter": {"season": ["2425"], "league": ["EPL"]},
    }
    run_meta_path.write_text(json.dumps(meta), encoding="utf-8")

    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    args_summary = report["lineage_health"]["evidence"]["training_args"]
    assert args_summary is not None
    assert args_summary["optimizer"] == "adamw"
    assert args_summary["learning_rate"] == 0.001
    assert args_summary["seed"] == 42
    # Noisy fields must not leak into the summary.
    assert "data_paths" not in args_summary
    assert "cohort_filter" not in args_summary


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


# ---------------------------------------------------------------------------
# label_ledger evidence section (PRS-3 slice 1)
# ---------------------------------------------------------------------------


def test_label_ledger_section_present_and_empty_by_default(tmp_path) -> None:
    """No ledger file → label_ledger section shows zero counts.

    An empty ledger is the honest default before any personal evaluation
    has been recorded; it must not block the verdict (the absence of
    independent labels is already reflected in research_readiness).
    """
    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    section = report["label_ledger"]
    assert section["schema"] == "scoutfootball.label_ledger"
    assert section["schema_version"] == "1.0"
    assert section["total_records"] == 0
    assert section["active_label_count"] == 0
    assert section["blind_annotation_count"] == 0
    assert section["records_by_action"] == {}
    assert section["records_by_label_type"] == {}
    assert section["records_by_cohort_hash"] == {}
    assert section["latest_revision"] == 0
    # Independence audit is attached and clean on an empty ledger.
    audit = section["independence_audit"]
    assert audit["status"] == "ok"
    assert audit["supervision_eligible_count"] == 0
    assert audit["model_derived_active_count"] == 0
    assert audit["violation_count"] == 0
    # Must not appear in blocking_reasons — empty ledger is not a failure.
    assert all("label_ledger" not in r for r in report["blocking_reasons"])


def test_label_ledger_section_reflects_recorded_labels(tmp_path) -> None:
    """A confirmed pairwise + tier label is reflected in the section counts."""
    from scoutfootball.evaluation.label_ledger import (
        append_label,
        build_label,
        read_ledger,
    )

    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    existing = read_ledger(settings=settings)
    pairwise = build_label(
        action="confirmed",
        label_type="human_pairwise_preference",
        cohort_hash="abc123def4567890",
        role_family="CB",
        season_id="2425",
        observation_window="2024-08-01/2025-05-31",
        confidence="high",
        evidence="Player A had more interceptions/90 than Player B",
        decided_by="maintainer",
        revision=len(existing) + 1,
        player_a_id="unresolved:u:1",
        player_b_id="unresolved:u:2",
        preferred_player="a",
    )
    append_label(pairwise, settings=settings)
    tier = build_label(
        action="confirmed",
        label_type="human_tier",
        cohort_hash="abc123def4567890",
        role_family="CB",
        season_id="2425",
        observation_window="2024-08-01/2025-05-31",
        confidence="medium",
        evidence="Elite ball-playing CB, top progressive passes",
        decided_by="maintainer",
        revision=len(read_ledger(settings=settings)) + 1,
        canonical_player_id="canonical:fbref:lara:1998:ar",
        tier=1,
    )
    append_label(tier, settings=settings)

    report = build_research_health_report(settings=settings)
    section = report["label_ledger"]
    assert section["total_records"] == 2
    assert section["active_label_count"] == 2
    assert section["blind_annotation_count"] == 2
    assert section["records_by_action"] == {"confirmed": 2}
    assert section["records_by_label_type"] == {
        "human_pairwise_preference": 1,
        "human_tier": 1,
    }
    assert section["records_by_confidence"] == {"high": 1, "medium": 1}
    assert section["records_by_role_family"] == {"CB": 2}
    assert section["records_by_cohort_hash"] == {"abc123def4567890": 2}
    assert section["latest_revision"] == 2
    # Independence audit sees 2 supervision-eligible active labels.
    audit = section["independence_audit"]
    assert audit["status"] == "ok"
    assert audit["supervision_eligible_count"] == 2
    assert audit["supervision_eligible_by_type"] == {
        "human_pairwise_preference": 1,
        "human_tier": 1,
    }
    assert audit["violation_count"] == 0


def test_label_ledger_section_surfaces_revoked_and_superseded(tmp_path) -> None:
    """A revoked label clears active count; a supersede replaces it."""
    from scoutfootball.evaluation.label_ledger import (
        append_label,
        build_label,
        build_revoke_label,
        read_ledger,
    )

    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    existing = read_ledger(settings=settings)
    r1 = build_label(
        action="confirmed",
        label_type="human_pairwise_preference",
        cohort_hash="abc123def4567890",
        role_family="CB",
        season_id="2425",
        observation_window="2024-08-01/2025-05-31",
        confidence="high",
        evidence="first attempt: prefer A",
        decided_by="maintainer",
        revision=len(existing) + 1,
        player_a_id="unresolved:u:1",
        player_b_id="unresolved:u:2",
        preferred_player="a",
    )
    append_label(r1, settings=settings)
    # Revoke r1.
    revoke = build_revoke_label(
        target_decision_id=r1["decision_id"],
        label_type="human_pairwise_preference",
        cohort_hash="abc123def4567890",
        role_family="CB",
        season_id="2425",
        observation_window="2024-08-01/2025-05-31",
        evidence="re-review showed B was better",
        decided_by="maintainer",
        revision=len(read_ledger(settings=settings)) + 1,
    )
    append_label(revoke, settings=settings)

    report = build_research_health_report(settings=settings)
    section = report["label_ledger"]
    assert section["total_records"] == 2
    assert section["active_label_count"] == 0
    assert section["records_by_action"] == {"confirmed": 1, "revoked": 1}
    audit = section["independence_audit"]
    assert audit["supervision_eligible_count"] == 0
    assert audit["status"] == "ok"


def test_label_ledger_section_unavailable_on_corrupt_file(tmp_path) -> None:
    """A corrupt ledger JSONL is surfaced as unavailable, not crashed."""
    _build_healthy_workspace(tmp_path)
    ledger = tmp_path / "data" / "gold" / "label_ledger" / "decisions.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("{not valid json}\n", encoding="utf-8")
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    section = report["label_ledger"]
    assert section["schema"] == "scoutfootball.label_ledger"
    assert section["status"] == "unavailable"
    assert "label ledger read failed" in section["evidence"]["reason"]
    # The verdict is unaffected — the ledger is evidence-only.
    assert report["verdict"] == VERDICT_READY


def test_label_ledger_section_independence_audit_surfaces_violations(tmp_path) -> None:
    """A model_derived active label is flagged by the independence audit."""
    from scoutfootball.evaluation.label_ledger import (
        append_label,
        build_label,
        read_ledger,
    )

    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    existing = read_ledger(settings=settings)
    bad = build_label(
        action="confirmed",
        label_type="model_derived",
        cohort_hash="abc123def4567890",
        role_family="CB",
        season_id="2425",
        observation_window="2024-08-01/2025-05-31",
        confidence="low",
        evidence="leaked model-derived label must not supervise ratings",
        decided_by="maintainer",
        revision=len(existing) + 1,
    )
    append_label(bad, settings=settings)

    report = build_research_health_report(settings=settings)
    section = report["label_ledger"]
    assert section["active_label_count"] == 1
    audit = section["independence_audit"]
    # model_derived is self-referential: it must be flagged and excluded
    # from the supervision-eligible count.
    assert audit["status"] == "violations_found"
    assert audit["model_derived_active_count"] == 1
    assert audit["supervision_eligible_count"] == 0
    assert audit["violation_count"] >= 1
    # Even with a violation, the ledger is evidence-only and must not
    # block the verdict — research_readiness already gates on label
    # independence at its own layer.
    assert all("label_ledger" not in r for r in report["blocking_reasons"])


def test_label_ledger_limitation_present_in_report(tmp_path) -> None:
    """The limitations list must explain the label_ledger section."""
    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    joined = " ".join(report["limitations"])
    assert "label_ledger" in joined
    assert "PRS-3" in joined
    assert "independence" in joined
    assert "label-append" in joined


# ---------------------------------------------------------------------------
# label_stability evidence section (PRS-LABEL-006 / PRS-3 slice 3)
# ---------------------------------------------------------------------------


def test_label_stability_section_present_and_empty_by_default(tmp_path) -> None:
    """No ledger file -> label_stability section shows zero counts.

    An empty ledger must return 0/0/0/0 honestly and must not block the
    verdict (stability metrics are signals, not gates).
    """
    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    section = report["label_stability"]
    assert section["schema"] == "scoutfootball.label-stability"
    assert section["schema_version"] == "1.0.0"
    assert section["status"] == "ok"
    summary = section["summary"]
    assert summary["total_retest_pairs"] == 0
    assert summary["consistent_retest_pairs"] == 0
    assert summary["retest_consistency_rate"] is None
    assert summary["total_agreement_groups"] == 0
    assert summary["consistent_agreement_groups"] == 0
    assert summary["agreement_rate"] is None
    assert summary["active_label_count"] == 0
    # Must not appear in blocking_reasons — stability is evidence-only.
    assert all("label_stability" not in r for r in report["blocking_reasons"])


def test_label_stability_section_empty_when_ledger_corrupt(tmp_path) -> None:
    """A corrupt ledger JSONL surfaces as empty in label_stability.

    The label_ledger audit catches the read failure and returns an empty
    records list (with its own status=unavailable); downstream sections
    like label_stability therefore see an empty list and honestly report
    0/0/0/0 with status=ok. The corrupt-file failure is surfaced by the
    label_ledger section, not duplicated here. The verdict stays READY
    because stability is evidence-only.
    """
    _build_healthy_workspace(tmp_path)
    ledger = tmp_path / "data" / "gold" / "label_ledger" / "decisions.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("{not valid json}\n", encoding="utf-8")
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    # label_ledger surfaces the corrupt-file failure.
    assert report["label_ledger"]["status"] == "unavailable"
    # label_stability sees an empty list and reports 0/0/0/0 honestly.
    section = report["label_stability"]
    assert section["schema"] == "scoutfootball.label-stability"
    assert section["status"] == "ok"
    assert section["summary"]["total_retest_pairs"] == 0
    assert section["summary"]["total_agreement_groups"] == 0
    assert report["verdict"] == VERDICT_READY


def test_label_stability_section_reflects_retest_pair(tmp_path) -> None:
    """A confirmed pairwise label plus its retest produces a retest_pair."""
    from scoutfootball.evaluation.label_ledger import (
        append_label,
        build_label,
        read_ledger,
    )

    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    existing = read_ledger(settings=settings)
    original = build_label(
        action="confirmed",
        label_type="human_pairwise_preference",
        cohort_hash="abc123def4567890",
        role_family="CB",
        season_id="2425",
        observation_window="2024-08-01/2025-05-31",
        confidence="high",
        evidence="Player A had more interceptions/90 than Player B",
        decided_by="maintainer",
        revision=len(existing) + 1,
        player_a_id="unresolved:understat:u|1",
        player_b_id="unresolved:understat:u|2",
        preferred_player="a",
    )
    append_label(original, settings=settings)

    existing = read_ledger(settings=settings)
    retest = build_label(
        action="confirmed",
        label_type="human_pairwise_preference",
        cohort_hash="abc123def4567890",
        role_family="CB",
        season_id="2425",
        observation_window="2024-08-01/2025-05-31",
        confidence="high",
        evidence="Retest confirms Player A still preferred over Player B",
        decided_by="maintainer",
        revision=len(existing) + 1,
        player_a_id="unresolved:understat:u|1",
        player_b_id="unresolved:understat:u|2",
        preferred_player="a",
        supersedes_decision_id=original["decision_id"],
    )
    append_label(retest, settings=settings)

    report = build_research_health_report(settings=settings)
    section = report["label_stability"]
    assert section["status"] == "ok"
    summary = section["summary"]
    assert summary["total_retest_pairs"] == 1
    assert summary["consistent_retest_pairs"] == 1
    assert summary["retest_consistency_rate"] == 1.0
    # Evidence-only: must not block the verdict.
    assert all("label_stability" not in r for r in report["blocking_reasons"])


def test_label_stability_limitation_present_in_report(tmp_path) -> None:
    """The limitations list must explain the label_stability section."""
    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    joined = " ".join(report["limitations"])
    assert "label_stability" in joined
    assert "PRS-LABEL-006" in joined
    assert "retest_pairs" in joined
    assert "annotator_agreement" in joined
    assert "label-stability" in joined


# ---------------------------------------------------------------------------
# weight_sensitivity evidence section (PRS-MODEL-011)
# ---------------------------------------------------------------------------


def test_weight_sensitivity_section_present(tmp_path) -> None:
    """The weight_sensitivity section is always present in the report.

    With the healthy-workspace fixture the feature matrix is minimal
    (no position_group), so the report returns status=ok with empty
    role_summaries. The section must not block the verdict (sensitivity
    metrics are evidence-only signals).
    """
    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    section = report["weight_sensitivity"]
    assert section["schema"] == "scoutfootball.weight-sensitivity"
    assert section["schema_version"] == "1.0.0"
    # Either ok (matrix readable, no scored roles) or unavailable (if
    # the minimal fixture lacks columns the loader needs). Both are
    # honest; neither blocks the verdict.
    assert section["status"] in ("ok", "unavailable")
    assert all("weight_sensitivity" not in r for r in report["blocking_reasons"])


def test_weight_sensitivity_section_unavailable_when_matrix_missing(
    tmp_path,
) -> None:
    """No feature matrix -> weight_sensitivity reports unavailable."""
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    section = report["weight_sensitivity"]
    assert section["schema"] == "scoutfootball.weight-sensitivity"
    assert section["status"] == "unavailable"
    # Evidence-only: must not appear in blocking_reasons.
    assert all("weight_sensitivity" not in r for r in report["blocking_reasons"])


def test_weight_sensitivity_limitation_present_in_report(tmp_path) -> None:
    """The limitations list must explain the weight_sensitivity section."""
    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    joined = " ".join(report["limitations"])
    assert "weight_sensitivity" in joined
    assert "PRS-MODEL-011" in joined
    assert "weight-sensitivity" in joined


# ---------------------------------------------------------------------------
# minutes_sensitivity evidence section (PRS-MODEL-012)
# ---------------------------------------------------------------------------


def test_minutes_sensitivity_section_present(tmp_path) -> None:
    """The minutes_sensitivity section is always present in the report.

    With the healthy-workspace fixture the feature matrix is minimal
    (no position_group), so the report returns status=ok with empty
    role_summaries. The section must not block the verdict (sensitivity
    metrics are evidence-only signals).
    """
    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    section = report["minutes_sensitivity"]
    assert section["schema"] == "scoutfootball.minutes-sensitivity"
    assert section["schema_version"] == "1.0.0"
    assert section["status"] in ("ok", "unavailable")
    assert all("minutes_sensitivity" not in r for r in report["blocking_reasons"])


def test_minutes_sensitivity_section_unavailable_when_matrix_missing(
    tmp_path,
) -> None:
    """No feature matrix -> minutes_sensitivity reports unavailable."""
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    section = report["minutes_sensitivity"]
    assert section["schema"] == "scoutfootball.minutes-sensitivity"
    assert section["status"] == "unavailable"
    assert all("minutes_sensitivity" not in r for r in report["blocking_reasons"])


def test_minutes_sensitivity_limitation_present_in_report(tmp_path) -> None:
    """The limitations list must explain the minutes_sensitivity section."""
    _build_healthy_workspace(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_research_health_report(settings=settings)
    joined = " ".join(report["limitations"])
    assert "minutes_sensitivity" in joined
    assert "PRS-MODEL-012" in joined
    assert "minutes-sensitivity" in joined

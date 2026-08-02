"""Layered research health for the local player-rating research system.

PRS-0 (see ``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`` R-003/R-004) requires
that the health of the rating research system no longer be hidden behind a
single top-level ``ok``. A rating artifact that is stale, unreviewable,
synthetic or trained on non-independent labels must be reported as not ready,
even when the underlying parquet files are readable and the contract checks
pass.

This module computes five independent layers and a fail-closed top-level
verdict:

``storage_health``
    Do the critical rating artifacts exist and are they readable?

``lineage_health``
    Can the active rating be traced to a model run whose training-time
    feature manifest hash still matches the current on-disk manifest?

``model_reviewability``
    Does at least one local model run carry the minimum evidence for human
    review?

``active_rating_freshness``
    Is the active rating artifact at least as new as the feature matrix it
    claims to score, and is it backed by an activated model run?

``research_readiness``
    Are there independent supervision-eligible labels, and is the rating free
    of synthetic fallback data?

All layers are read-only and local. The module reads parquet files directly
rather than going through ``app.data_loader`` (which falls back to synthetic
demo data); a missing or unreadable file is reported as ``unavailable`` rather
than silently replaced.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scoutfootball.config import PlatformSettings

RESEARCH_HEALTH_SCHEMA = "scoutfootball.research-health"
RESEARCH_HEALTH_VERSION = "1.0.0"

# Layer status vocabulary. Each layer uses a subset; the top-level verdict
# is the worst of all layers (fail-closed for research readability).
STORAGE_OK = "ok"
STORAGE_DEGRADED = "degraded"
STORAGE_UNAVAILABLE = "unavailable"

LINEAGE_OK = "ok"
LINEAGE_STALE = "stale"
LINEAGE_UNVERIFIED = "unverified"
LINEAGE_UNAVAILABLE = "unavailable"

REVIEWABILITY_OK = "ok"
REVIEWABILITY_NONE = "no_reviewable_runs"
REVIEWABILITY_UNAVAILABLE = "unavailable"

FRESHNESS_OK = "ok"
FRESHNESS_STALE = "stale"
FRESHNESS_MISSING = "missing"
FRESHNESS_UNVERIFIED = "unverified"
FRESHNESS_UNAVAILABLE = "unavailable"

READINESS_READY = "ready"
READINESS_INSUFFICIENT = "insufficient_labels"
READINESS_BLOCKED = "blocked"
READINESS_UNAVAILABLE = "unavailable"

VERDICT_READY = "ready"
VERDICT_NOT_READY = "not_ready"
VERDICT_UNAVAILABLE = "unavailable"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _active_rating_path(settings: PlatformSettings) -> Path:
    return settings.gold_root / "feature_store" / "player_ratings_optimized.parquet"


def _feature_matrix_path(settings: PlatformSettings) -> Path:
    return settings.gold_root / "feature_store" / "rating_feature_matrix.parquet"


def _feature_manifest_path(settings: PlatformSettings) -> Path:
    return settings.gold_root / "feature_store" / "rating_feature_matrix_manifest.json"


def _truth_labels_path(settings: PlatformSettings) -> Path:
    return settings.gold_root / "feature_store" / "player_truth_labels.parquet"


def _player_match_path(settings: PlatformSettings) -> Path:
    return settings.gold_root / "feature_store" / "player_match.parquet"


def _active_meta_path(settings: PlatformSettings) -> Path:
    return settings.gold_root / "feature_store" / "optimized_params_meta.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _find_activated_run(settings: PlatformSettings) -> dict[str, Any] | None:
    """Return the meta.json of the currently activated model run, or None.

    The activation state lives in two places that must agree:

    1. ``optimized_params_meta.json`` on the active artifact side carries an
       ``active_model`` block written by ``promote_optimizer_run``.
    2. The promoted run's ``meta.json`` carries ``activation.status ==
       "activated"`` with a matching ``backup_id``.

    Legacy active ratings (written before the lifecycle flow existed) have
    neither block; they are reported as ``unverified`` rather than silently
    treated as fresh.
    """
    active_meta = _read_json(_active_meta_path(settings))
    if active_meta and isinstance(active_meta.get("active_model"), dict):
        run_id = active_meta["active_model"].get("run_id")
        if isinstance(run_id, str) and run_id:
            run_meta = _read_json(settings.model_root / "runs" / run_id / "meta.json")
            if run_meta is not None:
                return run_meta
            # active_model block points at a missing run; fall through to scan
            # so the report still explains the gap.
    # Scan runs for one marked activated. This is the same pattern
    # ``inspect_optimizer_run_rollback`` uses to locate the active candidate.
    runs_dir = settings.model_root / "runs"
    if not runs_dir.is_dir():
        return None
    for run_dir in sorted(
        (p for p in runs_dir.iterdir() if p.is_dir()), reverse=True
    ):
        run_meta = _read_json(run_dir / "meta.json")
        if not run_meta:
            continue
        activation = run_meta.get("activation")
        if isinstance(activation, dict) and activation.get("status") == "activated":
            return run_meta
    return None


def _build_storage_health(settings: PlatformSettings) -> dict[str, Any]:
    """Check that the critical rating research artifacts exist and are readable."""
    critical = {
        "active_rating": _active_rating_path(settings),
        "feature_matrix": _feature_matrix_path(settings),
        "feature_manifest": _feature_manifest_path(settings),
        "truth_labels": _truth_labels_path(settings),
    }
    present: dict[str, bool] = {}
    readable: dict[str, bool] = {}
    for name, path in critical.items():
        present[name] = path.exists()
        if present[name]:
            try:
                # Touch the file to confirm it is readable; do not load the
                # full parquet here (the lineage/freshness layers do that
                # selectively). A corrupt parquet will surface as unreadable
                # when the readiness layer reads it.
                with path.open("rb"):
                    pass
                readable[name] = True
            except OSError:
                readable[name] = False
        else:
            readable[name] = False

    missing = [name for name, ok in present.items() if not ok]
    unreadable = [name for name, ok in readable.items() if present[name] and not ok]
    if missing or unreadable:
        status = STORAGE_DEGRADED if not missing else STORAGE_DEGRADED
        # All-missing critical files is degraded, not unavailable, so the
        # other layers can still explain *why* research is not ready. The
        # top-level verdict will be not_ready regardless.
    else:
        status = STORAGE_OK
    return {
        "status": status,
        "evidence": {
            "present": present,
            "readable": readable,
            "missing": missing,
            "unreadable": unreadable,
        },
    }


def _build_feature_coverage(
    settings: PlatformSettings, *, storage: dict[str, Any]
) -> dict[str, Any]:
    """Compute per-field-group missing rates in ``rating_feature_matrix``.

    PRS-0 R-003 status report must surface feature missingness so the
    maintainer does not have to hand-copy percentages into docs. This
    section is evidence-only: it does not participate in the fail-closed
    verdict (the five layers do), but it gives the same command
    (``scoutfootball research-health``) the machine-readable coverage
    snapshot that ``PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`` section 3.2
    used to maintain by hand.
    """
    if storage["status"] == STORAGE_UNAVAILABLE:
        return {"status": "unavailable", "evidence": {"reason": "storage unavailable"}}

    matrix_path = _feature_matrix_path(settings)
    if not matrix_path.exists():
        return {
            "status": "unavailable",
            "evidence": {"reason": "rating_feature_matrix.parquet missing"},
        }
    try:
        import pandas as pd

        from scoutfootball.features.rating_matrix import FIELD_GROUPS

        df = pd.read_parquet(matrix_path)
    except Exception as exc:  # noqa: BLE001 — read-only diagnostic
        return {
            "status": "unavailable",
            "evidence": {"reason": f"read failed: {exc}"},
        }

    total_rows = int(len(df))
    if total_rows == 0:
        return {
            "status": "unavailable",
            "evidence": {"reason": "rating_feature_matrix has 0 rows"},
        }

    groups: dict[str, Any] = {}
    for group_name, field_list in FIELD_GROUPS.items():
        present_cols = [c for c in field_list if c in df.columns]
        missing_marker = f"{group_name}_missing"
        # Prefer the explicit _missing marker column (written before median
        # imputation) over post-imputation NaN checks — imputation hides
        # the original missingness that PRS-0 R-007 requires to be visible.
        if missing_marker in df.columns:
            missing_rate = float(df[missing_marker].astype(bool).mean())
            per_col_missing = {
                col: float(df[col].isna().mean()) for col in present_cols
            }
        elif not present_cols:
            missing_rate = 1.0
            per_col_missing = {}
        else:
            # No marker column: fall back to NaN-based check.
            group_df = df[present_cols]
            per_col_missing = {
                col: float(group_df[col].isna().mean()) for col in present_cols
            }
            missing_rate = float(group_df.isna().all(axis=1).mean())
        groups[group_name] = {
            "fields_present": present_cols,
            "fields_missing_from_schema": [
                c for c in field_list if c not in df.columns
            ],
            "missing_rate": missing_rate,
            "per_field_missing_rate": per_col_missing,
        }

    return {
        "status": "ok",
        "evidence": {
            "total_rows": total_rows,
            "columns": list(df.columns),
            "field_groups": groups,
        },
    }


def _build_data_grain(
    settings: PlatformSettings, *, storage: dict[str, Any]
) -> dict[str, Any]:
    """Report ``player_match`` observation grain and source distribution.

    PRS-0 R-006: season-proxy rows (27,504) and real match-level rows
    (94 from StatsBomb open data) must not be conflated. This section
    surfaces the counts so the maintainer can verify grain at a glance
    instead of hand-copying numbers into planning docs.
    """
    if storage["status"] == STORAGE_UNAVAILABLE:
        return {"status": "unavailable", "evidence": {"reason": "storage unavailable"}}

    pm_path = _player_match_path(settings)
    if not pm_path.exists():
        return {
            "status": "unavailable",
            "evidence": {"reason": "player_match.parquet missing"},
        }
    try:
        import pandas as pd

        df = pd.read_parquet(pm_path)
    except Exception as exc:  # noqa: BLE001 — read-only diagnostic
        return {
            "status": "unavailable",
            "evidence": {"reason": f"read failed: {exc}"},
        }

    total_rows = int(len(df))
    if total_rows == 0:
        return {
            "status": "unavailable",
            "evidence": {"reason": "player_match has 0 rows"},
        }

    grain_counts: dict[str, int] = {}
    if "data_granularity" in df.columns:
        grain_counts = {
            str(k): int(v) for k, v in df["data_granularity"].value_counts().items()
        }
    source_counts: dict[str, int] = {}
    if "source_name" in df.columns:
        source_counts = {
            str(k): int(v) for k, v in df["source_name"].value_counts().items()
        }

    return {
        "status": "ok",
        "evidence": {
            "total_rows": total_rows,
            "data_granularity": grain_counts,
            "source_name": source_counts,
        },
    }


def _build_lineage_health(
    settings: PlatformSettings, *, storage: dict[str, Any]
) -> dict[str, Any]:
    """Verify the active rating's training-time feature manifest still matches
    the current on-disk manifest.

    Reuses ``model_admission._current_rating_manifest_hash`` (sha256[:16] of
    the manifest file) so the comparison is byte-for-byte consistent with the
    admission gate rather than a second hash definition.
    """
    from scoutfootball.evaluation.model_admission import _current_rating_manifest_hash

    if storage["status"] == STORAGE_UNAVAILABLE:
        return {"status": LINEAGE_UNAVAILABLE, "evidence": {"reason": "storage unavailable"}}

    current_manifest_hash = _current_rating_manifest_hash(settings)
    if current_manifest_hash is None:
        return {
            "status": LINEAGE_UNVERIFIED,
            "evidence": {
                "reason": "rating_feature_matrix_manifest.json missing on disk",
                "current_manifest_hash": None,
                "training_manifest_hash": None,
            },
        }

    activated_meta = _find_activated_run(settings)
    if activated_meta is None:
        return {
            "status": LINEAGE_UNVERIFIED,
            "evidence": {
                "reason": (
                    "active rating has no activated model run; it is a legacy "
                    "artifact with no chain of custody to a reviewable run"
                ),
                "current_manifest_hash": current_manifest_hash,
                "training_manifest_hash": None,
            },
        }

    lineage = activated_meta.get("lineage")
    if not isinstance(lineage, dict):
        return {
            "status": LINEAGE_UNVERIFIED,
            "evidence": {
                "reason": "activated run meta.json has no lineage block",
                "current_manifest_hash": current_manifest_hash,
                "training_manifest_hash": None,
            },
        }
    training_hash = (lineage.get("feature_manifest") or {}).get("hash")
    lineage_status = lineage.get("status")
    if not isinstance(training_hash, str) or not training_hash:
        return {
            "status": LINEAGE_UNVERIFIED,
            "evidence": {
                "reason": "activated run lineage has no feature_manifest.hash",
                "current_manifest_hash": current_manifest_hash,
                "training_manifest_hash": None,
                "lineage_status": lineage_status,
            },
        }
    if training_hash != current_manifest_hash:
        return {
            "status": LINEAGE_STALE,
            "evidence": {
                "reason": (
                    "rating_feature_matrix was rebuilt after the active model "
                    "was trained; the active rating cannot be reviewed against "
                    "the current feature snapshot"
                ),
                "current_manifest_hash": current_manifest_hash,
                "training_manifest_hash": training_hash,
                "lineage_status": lineage_status,
            },
        }
    # Manifest hash matches training-time hash. Now verify the manifest's
    # declared source files still match their recorded input_hash. This
    # closes the chain to the raw snapshot: without it, upstream parquet
    # could be silently rewritten without the manifest being rebuilt, and
    # lineage_health would still report ok.
    source_check = _verify_manifest_source_lineage(settings)
    training_args = _summarise_training_args(activated_meta)
    if source_check["status"] == "stale":
        return {
            "status": LINEAGE_STALE,
            "evidence": {
                "reason": (
                    "manifest hash matches training-time hash, but at least "
                    "one declared source_lineage file has drifted; the active "
                    "rating's chain to the raw snapshot is broken"
                ),
                "current_manifest_hash": current_manifest_hash,
                "training_manifest_hash": training_hash,
                "lineage_status": lineage_status,
                "source_lineage": source_check,
                "training_args": training_args,
            },
        }
    if source_check["status"] == "broken":
        return {
            "status": LINEAGE_UNVERIFIED,
            "evidence": {
                "reason": (
                    "manifest hash matches training-time hash, but at least "
                    "one declared source_lineage file is missing; the chain "
                    "to the raw snapshot cannot be completed"
                ),
                "current_manifest_hash": current_manifest_hash,
                "training_manifest_hash": training_hash,
                "lineage_status": lineage_status,
                "source_lineage": source_check,
                "training_args": training_args,
            },
        }
    return {
        "status": LINEAGE_OK,
        "evidence": {
            "reason": (
                "active model training-time manifest hash matches current "
                "on-disk manifest"
                + (
                    "; source_lineage verified against raw snapshot"
                    if source_check["status"] == "verified"
                    else "; source_lineage not declared in manifest, raw snapshot chain unverified"
                )
            ),
            "current_manifest_hash": current_manifest_hash,
            "training_manifest_hash": training_hash,
            "lineage_status": lineage_status,
            "source_lineage": source_check,
            "training_args": training_args,
        },
    }


def _summarise_training_args(run_meta: dict[str, Any]) -> dict[str, Any] | None:
    """Return a small summary of the activated run's training args.

    PRS-0 R-003 wants the lineage chain to surface training configuration,
    not just hashes. The full ``args`` block can be large, so we keep only
    the fields that identify *which* training configuration produced the
    active rating. Returns ``None`` when the run has no args block (e.g.
    legacy runs written before args were recorded).
    """
    args = run_meta.get("args")
    if not isinstance(args, dict):
        return None
    # Keep only stable identifying fields; drop large lists/data paths that
    # would bloat the health report. Callers needing the full args can read
    # the run's meta.json directly.
    keep = (
        "optimizer",
        "learning_rate",
        "weight_decay",
        "epochs",
        "batch_size",
        "hidden_dims",
        "dropout",
        "seed",
        "feature_set",
        "target",
        "cohort",
    )
    summary = {key: args[key] for key in keep if key in args}
    return summary or None


def _hash_file_short(path: Path) -> str | None:
    """Return sha256[:16] of *path* bytes, or None if the file is missing.

    Mirrors ``scoutfootball.features.manifest.hash_file`` so source_lineage
    verification is byte-for-byte consistent with how manifests are written.
    """
    if not path.exists():
        return None
    import hashlib

    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def _verify_manifest_source_lineage(
    settings: PlatformSettings,
) -> dict[str, Any]:
    """Verify each ``source_lineage`` entry still matches the on-disk source.

    PRS-0 R-003 requires the lineage chain to reach the raw snapshot, not
    just the feature manifest file. The manifest declares each upstream
    parquet via ``source_lineage[i].{relative_path, input_hash}`` (written
    by ``features.manifest`` using ``hash_file``). This helper recomputes
    each source file's sha256[:16] and compares it to the recorded hash so
    that upstream drift is detected even when the manifest file itself was
    not rebuilt.

    Returns a dict with:

    - ``status``: ``verified`` | ``stale`` | ``broken`` | ``unverified``
    - ``sources``: per-source evidence list
    - ``reason``: short human-readable explanation
    """
    manifest = _read_json(_feature_manifest_path(settings))
    if manifest is None:
        return {
            "status": "unverified",
            "sources": [],
            "reason": "manifest missing or unreadable",
        }
    source_lineage = manifest.get("source_lineage")
    if not isinstance(source_lineage, list) or not source_lineage:
        return {
            "status": "unverified",
            "sources": [],
            "reason": "manifest has no source_lineage block; raw snapshot chain not declared",
        }

    sources: list[dict[str, Any]] = []
    any_drift = False
    any_missing = False
    for entry in source_lineage:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or entry.get("relative_path") or "unknown"
        rel_path = entry.get("relative_path")
        recorded_hash = entry.get("input_hash")
        if not isinstance(rel_path, str) or not rel_path:
            sources.append({
                "name": name,
                "relative_path": None,
                "recorded_hash": recorded_hash,
                "current_hash": None,
                "status": "invalid_entry",
            })
            continue
        # Resolve relative to the data root (manifest paths are data-root
        # relative, e.g. ``gold/feature_store/player_match.parquet``).
        current_path = settings.data_root / rel_path
        current_hash = _hash_file_short(current_path)
        if current_hash is None:
            any_missing = True
            entry_status = "missing"
        elif not isinstance(recorded_hash, str) or not recorded_hash:
            # Manifest recorded the source but did not stamp its hash; we
            # can only say the file exists, not that it matches.
            entry_status = "no_recorded_hash"
        elif current_hash != recorded_hash:
            any_drift = True
            entry_status = "drift"
        else:
            entry_status = "match"
        sources.append({
            "name": name,
            "relative_path": rel_path,
            "recorded_hash": recorded_hash,
            "current_hash": current_hash,
            "status": entry_status,
        })

    if any_drift:
        return {
            "status": "stale",
            "sources": sources,
            "reason": (
                "at least one source_lineage input_hash differs from the "
                "current on-disk file; the manifest no longer reflects the "
                "raw snapshot it was built from"
            ),
        }
    if any_missing:
        return {
            "status": "broken",
            "sources": sources,
            "reason": (
                "at least one source_lineage file is missing; the chain to "
                "the raw snapshot cannot be completed"
            ),
        }
    return {
        "status": "verified",
        "sources": sources,
        "reason": "all source_lineage input hashes match current on-disk files",
    }


def _build_model_reviewability(
    settings: PlatformSettings, *, storage: dict[str, Any]
) -> dict[str, Any]:
    """Summarise whether any local model run is reviewable."""
    if storage["status"] == STORAGE_UNAVAILABLE:
        return {
            "status": REVIEWABILITY_UNAVAILABLE,
            "evidence": {"reason": "storage unavailable"},
        }
    try:
        from scoutfootball.evaluation.model_admission import build_model_admission_report

        report = build_model_admission_report(settings=settings)
    except Exception:  # read-only diagnostic; never raise
        return {
            "status": REVIEWABILITY_UNAVAILABLE,
            "evidence": {"reason": "model_admission builder failed"},
        }
    reviewable = int(report.get("reviewable_run_count", 0))
    run_count = int(report.get("run_count", 0))
    not_reviewable = sum(
        1 for r in report.get("runs", []) if r.get("status") == "not_reviewable"
    )
    not_available = sum(
        1 for r in report.get("runs", []) if r.get("status") == "not_available"
    )
    status = REVIEWABILITY_OK if reviewable > 0 else REVIEWABILITY_NONE
    return {
        "status": status,
        "evidence": {
            "run_count": run_count,
            "reviewable_run_count": reviewable,
            "not_reviewable_run_count": not_reviewable,
            "not_available_run_count": not_available,
        },
    }


def _build_active_rating_freshness(
    settings: PlatformSettings, *, storage: dict[str, Any], lineage: dict[str, Any]
) -> dict[str, Any]:
    """Check the active rating artifact is not older than the feature matrix
    and is backed by an activated model run."""
    rating_path = _active_rating_path(settings)
    feature_path = _feature_matrix_path(settings)
    if not rating_path.exists():
        return {
            "status": FRESHNESS_MISSING,
            "evidence": {"reason": "active rating parquet missing", "rating_mtime": None},
        }
    rating_mtime = _iso_mtime(rating_path)
    feature_mtime = _iso_mtime(feature_path) if feature_path.exists() else None

    # No activated run → unverified freshness, regardless of mtime. A legacy
    # rating that predates the lifecycle flow cannot be called fresh.
    if lineage["status"] == LINEAGE_UNVERIFIED and lineage["evidence"].get(
        "training_manifest_hash"
    ) is None:
        return {
            "status": FRESHNESS_UNVERIFIED,
            "evidence": {
                "reason": lineage["evidence"].get("reason", "no activated model run"),
                "rating_mtime": rating_mtime,
                "feature_matrix_mtime": feature_mtime,
            },
        }

    # When lineage is stale or unverified-with-hash, freshness follows lineage:
    # a stale lineage means the rating was trained on a different snapshot.
    if lineage["status"] == LINEAGE_STALE:
        return {
            "status": FRESHNESS_STALE,
            "evidence": {
                "reason": "active rating lineage is stale (manifest hash mismatch)",
                "rating_mtime": rating_mtime,
                "feature_matrix_mtime": feature_mtime,
            },
        }

    # Compare mtimes as a second line of defense: even with a matching
    # manifest hash, a rating file older than the feature matrix parquet
    # suggests the rating was not rebuilt against the current feature store.
    if (
        rating_path.exists()
        and feature_path.exists()
        and rating_path.stat().st_mtime < feature_path.stat().st_mtime
    ):
        return {
            "status": FRESHNESS_STALE,
            "evidence": {
                "reason": "active rating parquet is older than rating_feature_matrix.parquet",
                "rating_mtime": rating_mtime,
                "feature_matrix_mtime": feature_mtime,
            },
        }
    return {
        "status": FRESHNESS_OK,
        "evidence": {
            "reason": (
                "active rating is backed by an activated run and not older "
                "than the feature matrix"
            ),
            "rating_mtime": rating_mtime,
            "feature_matrix_mtime": feature_mtime,
        },
    }


def _rating_is_synthetic(rating_path: Path) -> bool | None:
    """Return True if the active rating parquet is fully synthetic.

    Reads the parquet directly (not via ``data_loader``) so a missing file is
    reported as ``None`` rather than replaced by demo data. Returns ``None``
    when the file is missing, unreadable, or has no ``is_synthetic`` column.
    """
    if not rating_path.exists():
        return None
    try:
        import pandas as pd

        df = pd.read_parquet(rating_path, columns=["is_synthetic"])
    except Exception:
        return None
    if "is_synthetic" not in df.columns:
        return None
    if len(df) == 0:
        return None
    return bool(df["is_synthetic"].fillna(False).astype(bool).all())


def _build_grain_and_missingness_audit(
    settings: PlatformSettings,
) -> dict[str, Any]:
    """Wrap ``grain.build_grain_and_missingness_report`` so the health
    report never crashes when the audit module is unavailable.

    The audit is read-only and local; failures are surfaced as
    ``unavailable`` rather than raising, mirroring the other evidence
    sections in this module.
    """
    try:
        from scoutfootball.evaluation.grain import (
            build_grain_and_missingness_report,
        )

        return build_grain_and_missingness_report(settings=settings)
    except Exception as exc:  # read-only diagnostic; never raise
        return {
            "schema": "scoutfootball.grain-audit",
            "schema_version": "1.0.0",
            "status": "unavailable",
            "evidence": {"reason": f"grain audit failed: {exc}"},
        }


def _build_identity_registry_audit(
    settings: PlatformSettings,
) -> dict[str, Any]:
    """Surface the canonical identity registry state in the health report.

    PRS-1 R-005: the registry is the maintainer's append-only ledger of
    explicit ``(source_name, source_player_id) -> canonical_player_id``
    decisions. An empty or unresolved registry is **not** a failure — it
    is the honest default before any human decision has been recorded.
    The health report therefore surfaces counts and the latest revision
    without participating in the fail-closed verdict, so the maintainer
    can see at a glance how many source IDs have been canonicalised.
    """
    try:
        from scoutfootball.evaluation.identity_registry import (
            read_registry,
            registry_summary,
        )

        records = read_registry(settings=settings)
        return registry_summary(records)
    except Exception as exc:  # read-only diagnostic; never raise
        return {
            "schema": "scoutfootball.identity_registry",
            "schema_version": "1.0",
            "status": "unavailable",
            "evidence": {"reason": f"identity registry read failed: {exc}"},
        }


def _build_canonical_resolution_audit(
    settings: PlatformSettings,
) -> dict[str, Any]:
    """Surface the canonical ID resolution state in the health report.

    PRS-1 R-005: the resolver applies the identity registry's active
    ``confirmed`` mappings to a derived view of ``player_match.parquet``
    and counts how many rows received a real canonical ID vs how many
    fell back to the ``unresolved:<source>:<id>`` marker. An all-unresolved
    result is **not** a failure — it is the honest default before any
    human decision has been recorded. The section is evidence-only and
    does not participate in the fail-closed verdict.
    """
    try:
        from scoutfootball.evaluation.canonical_resolver import (
            build_canonical_resolution_report,
        )

        return build_canonical_resolution_report(settings=settings)
    except Exception as exc:  # read-only diagnostic; never raise
        return {
            "schema": "scoutfootball.canonical-resolver",
            "schema_version": "1.0.0",
            "status": "unavailable",
            "evidence": {"reason": f"canonical resolution failed: {exc}"},
        }


def _build_role_system_audit(
    settings: PlatformSettings,
) -> dict[str, Any]:
    """Surface the role family distribution in the health report.

    PRS-1 R-009 role system v1: a typed ``RoleFamily`` vocabulary of 8
    families (GK/CB/FB/DM/CM/AM/W/ST) plus a default classifier that
    maps the existing ``position_group`` column to a typed family. The
    audit reports the raw distribution, the family distribution, and
    how many rows still carry a coarse ``DF``/``MF``/``FW`` label (which
    get a default fine role but are flagged for a future behaviour-
    based role suggestion tool).

    v1 does not auto-invent DM labels from MF players, and does not
    include a role override registry. An all-unknown result is
    ``status=ok`` because unknown is the honest default, not a failure.
    The section is evidence-only and does not participate in the
    fail-closed verdict.
    """
    try:
        from scoutfootball.evaluation.role_system import (
            build_role_system_report,
        )

        return build_role_system_report(settings=settings)
    except Exception as exc:  # read-only diagnostic; never raise
        return {
            "schema": "scoutfootball.role-system",
            "schema_version": "1.0.0",
            "status": "unavailable",
            "evidence": {"reason": f"role system audit failed: {exc}"},
        }


def _build_label_ledger_audit(
    settings: PlatformSettings,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Surface the PRS-3 personal evaluation label ledger in the health report.

    PRS-3 slice 1: the ledger is the maintainer's append-only JSONL record
    of ``human_pairwise_preference`` (A vs B within a role + observation
    window) and ``human_tier`` (1-5 tier) labels, plus
    ``external_reference`` / ``future_outcome`` / ``model_derived`` types
    reserved by the schema. An empty ledger is **not** a failure — it is
    the honest default before the maintainer has recorded any personal
    evaluation. The health report therefore surfaces counts, the
    supervision-eligible breakdown, and the independence audit status
    without participating in the fail-closed verdict, so the maintainer
    can see at a glance how many independent labels exist and whether
    any ``model_derived`` label has leaked into the supervision-eligible
    set.

    Returns ``(summary, records)`` where ``records`` is the raw ledger
    list, so downstream sections (e.g. ``label_review_queue``) can reuse
    it without re-reading the JSONL file.
    """
    try:
        from scoutfootball.evaluation.label_ledger import (
            label_independence_audit,
            ledger_summary,
            read_ledger,
        )

        records = read_ledger(settings=settings)
        summary = ledger_summary(records)
        # Attach the independence audit so the report surfaces whether any
        # model_derived label has leaked into the supervision-eligible
        # active set. The audit is structural; it does not prove the
        # annotator was truly blind or that evidence is correct.
        summary = {**summary, "independence_audit": label_independence_audit(records)}
        return summary, records
    except Exception as exc:  # read-only diagnostic; never raise
        return (
            {
                "schema": "scoutfootball.label_ledger",
                "schema_version": "1.0",
                "status": "unavailable",
                "evidence": {"reason": f"label ledger read failed: {exc}"},
            },
            [],
        )


def _build_label_review_queue_audit(
    settings: PlatformSettings,
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Surface the PRS-LABEL-005 review queue in the health report.

    PRS-3 slice 2: identifies active labels that need maintainer re-review
    — pairwise preference contradictions, tier rating conflicts, low-
    confidence/thin-evidence labels, and aged labels for re-test. Like
    the label ledger audit, this section does **not** participate in the
    fail-closed verdict: the presence of review items is not a storage
    or lineage failure, it is a signal to the maintainer. ``status=ok``
    only means no auto-detectable review signals exist, not that the
    labels are correct or supervision-ready.

    If ``records`` is provided (e.g. by ``_build_label_ledger_audit``
    returning the raw list), reuse it to avoid re-reading the JSONL.
    Otherwise read the ledger here.
    """
    try:
        from scoutfootball.evaluation.label_review_queue import build_review_queue

        if records is None:
            from scoutfootball.evaluation.label_ledger import read_ledger
            records = read_ledger(settings=settings)

        return build_review_queue(records)
    except Exception as exc:  # read-only diagnostic; never raise
        return {
            "schema": "scoutfootball.label-review-queue",
            "schema_version": "1.0.0",
            "status": "unavailable",
            "evidence": {"reason": f"label review queue build failed: {exc}"},
        }


def _build_label_stability_audit(
    settings: PlatformSettings,
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Surface the PRS-LABEL-006 stability report in the health report.

    PRS-3 slice 3: quantifies annotation stability along two axes:

    - ``retest_pairs``: re-annotation pairs traced via
      ``supersedes_decision_id`` chains (original -> retest), comparing
      the original and retest label values for consistency.
    - ``annotator_agreement``: groups of confirmed labels (including
      superseded ones) on the same business key that were decided by
      multiple distinct annotators, reporting whether they agreed.

    Like the label ledger and review queue audits, this section does
    **not** participate in the fail-closed verdict: stability metrics
    are signals for the maintainer, not gates. ``status=ok`` only means
    the report could be built, not that the labels are correct or
    supervision-ready. An empty ledger returns 0/0/0/0 honestly.

    If ``records`` is provided (e.g. by ``_build_label_ledger_audit``
    returning the raw list), reuse it to avoid re-reading the JSONL.
    Otherwise read the ledger here.
    """
    try:
        from scoutfootball.evaluation.label_stability import build_stability_report

        if records is None:
            from scoutfootball.evaluation.label_ledger import read_ledger
            records = read_ledger(settings=settings)

        return build_stability_report(records)
    except Exception as exc:  # read-only diagnostic; never raise
        return {
            "schema": "scoutfootball.label-stability",
            "schema_version": "1.0.0",
            "status": "unavailable",
            "evidence": {"reason": f"label stability build failed: {exc}"},
        }


def _build_weight_sensitivity_audit(
    settings: PlatformSettings,
) -> dict[str, Any]:
    """Surface the PRS-MODEL-011 B1 weight sensitivity report.

    Perturbs each B1 dimension weight by configurable multiplicative
    deltas, recomputes B1 scores, and measures ranking stability versus
    the baseline. Like the other evidence-only sections, this does not
    participate in the fail-closed verdict: sensitivity metrics are
    signals for the maintainer, not gates. ``status=ok`` only means the
    report could be built, not that the weights are correct or that the
    ranking is trustworthy. A missing feature matrix returns
    ``unavailable`` honestly.
    """
    try:
        from scoutfootball.evaluation.sensitivity import (
            compute_weight_sensitivity_report,
        )

        return compute_weight_sensitivity_report(settings=settings)
    except Exception as exc:  # read-only diagnostic; never raise
        return {
            "schema": "scoutfootball.weight-sensitivity",
            "schema_version": "1.0.0",
            "status": "unavailable",
            "evidence": {"reason": f"weight sensitivity build failed: {exc}"},
        }


def _build_minutes_sensitivity_audit(
    settings: PlatformSettings,
) -> dict[str, Any]:
    """Surface the PRS-MODEL-012 B2 minutes-threshold sensitivity report.

    Perturbs B2's ``reference_minutes`` by configurable absolute minute
    deltas, recomputes B2 scores (shrinkage weight + prior_mean +
    stable_core membership all change), and measures ranking stability
    versus the baseline. Like the other evidence-only sections, this
    does not participate in the fail-closed verdict: sensitivity metrics
    are signals for the maintainer, not gates. ``status=ok`` only means
    the report could be built, not that the threshold is correct or that
    the ranking is trustworthy. A missing feature matrix returns
    ``unavailable`` honestly.
    """
    try:
        from scoutfootball.evaluation.minutes_sensitivity import (
            compute_minutes_sensitivity_report,
        )

        return compute_minutes_sensitivity_report(settings=settings)
    except Exception as exc:  # read-only diagnostic; never raise
        return {
            "schema": "scoutfootball.minutes-sensitivity",
            "schema_version": "1.0.0",
            "status": "unavailable",
            "evidence": {"reason": f"minutes sensitivity build failed: {exc}"},
        }


def _build_research_readiness(
    settings: PlatformSettings,
    *,
    storage: dict[str, Any],
    lineage: dict[str, Any],
    reviewability: dict[str, Any],
    freshness: dict[str, Any],
) -> dict[str, Any]:
    """Combine label independence, synthetic isolation and the other layers
    into a single research-readiness verdict for the rating system."""
    if storage["status"] == STORAGE_UNAVAILABLE:
        return {
            "status": READINESS_UNAVAILABLE,
            "evidence": {"reason": "storage unavailable"},
        }

    truth_path = _truth_labels_path(settings)
    label_report: dict[str, Any] | None = None
    if truth_path.exists():
        try:
            import pandas as pd

            from scoutfootball.evaluation.truth_labels import (
                truth_label_supervision_report,
            )

            labels = pd.read_parquet(truth_path)
            label_report = truth_label_supervision_report(labels)
        except Exception:
            label_report = None

    if label_report is None:
        return {
            "status": READINESS_UNAVAILABLE,
            "evidence": {"reason": "truth labels unreadable or missing"},
        }

    eligible_rows = int(label_report.get("eligible_rows", 0))
    proxy_rows = int(label_report.get("proxy_rows", 0))
    independent_rows = int(label_report.get("independent_rows", 0))
    total_rows = int(label_report.get("total_rows", 0))
    excluded_rows = int(label_report.get("excluded_rows", 0))
    independent_temporal = label_report.get("independent_temporal")
    independent_temporally_eligible = (
        int(independent_temporal.get("temporally_eligible_rows", 0))
        if isinstance(independent_temporal, dict)
        else independent_rows
    )

    # Synthetic isolation: a fully-synthetic active rating cannot be research-ready.
    rating_synthetic = _rating_is_synthetic(_active_rating_path(settings))

    blocking_reasons: list[str] = []
    if independent_rows == 0:
        prefix = "no supervision-eligible labels; " if eligible_rows == 0 else ""
        blocking_reasons.append(
            f"{prefix}no independent player-ability labels (independent={independent_rows}, "
            f"proxy={proxy_rows}, supervision-eligible={eligible_rows}, "
            f"self-referential/excluded={excluded_rows} of {total_rows} total)"
        )
    elif independent_temporally_eligible < independent_rows:
        blocking_reasons.append(
            "independent labels are not all temporally eligible for the recorded "
            f"season ({independent_temporally_eligible}/{independent_rows}); "
            "they may be used as post-season benchmarks but not as causal training evidence"
        )
    if rating_synthetic is True:
        blocking_reasons.append("active rating parquet is fully synthetic")
    if reviewability["status"] != REVIEWABILITY_OK:
        blocking_reasons.append(
            f"model reviewability is {reviewability['status']}"
        )
    if freshness["status"] not in (FRESHNESS_OK,):
        blocking_reasons.append(f"active rating freshness is {freshness['status']}")
    if lineage["status"] != LINEAGE_OK:
        blocking_reasons.append(f"lineage health is {lineage['status']}")

    if not blocking_reasons:
        status = READINESS_READY
    elif independent_rows == 0 or rating_synthetic is True:
        # Proxy labels can support a disclosed proxy experiment, but they are
        # not enough to claim independently validated player-ability research.
        status = READINESS_BLOCKED
    else:
        status = READINESS_INSUFFICIENT

    return {
        "status": status,
        "evidence": {
            "label_report": label_report,
            "active_rating_is_synthetic": rating_synthetic,
            "blocking_reasons": blocking_reasons,
        },
    }


# Status severity ordering for the top-level verdict. Higher index = worse.
_LAYER_WORST_TOKENS = {
    STORAGE_UNAVAILABLE,
    LINEAGE_UNAVAILABLE,
    REVIEWABILITY_UNAVAILABLE,
    FRESHNESS_UNAVAILABLE,
    READINESS_UNAVAILABLE,
}
_LAYER_BLOCKING_STATUSES = {
    LINEAGE_STALE,
    LINEAGE_UNVERIFIED,
    REVIEWABILITY_NONE,
    FRESHNESS_STALE,
    FRESHNESS_MISSING,
    FRESHNESS_UNVERIFIED,
    READINESS_INSUFFICIENT,
    READINESS_BLOCKED,
    STORAGE_DEGRADED,
}


def _compute_verdict(layers: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    """Return (verdict, blocking_reasons) from the five layers.

    Fail-closed: any unavailable layer makes the whole report unavailable
    (we cannot claim readiness when we could not compute a layer); any
    blocking-status layer makes the verdict not_ready with the specific
    reasons. Only all-ok/ready layers yield ``ready``.
    """
    reasons: list[str] = []
    for name, layer in layers.items():
        status = layer.get("status")
        if status in _LAYER_WORST_TOKENS:
            reasons.append(f"{name}: {status}")
        elif status in _LAYER_BLOCKING_STATUSES:
            reasons.append(f"{name}: {status}")
    if not reasons:
        return VERDICT_READY, []
    if any(
        layers[name].get("status") in _LAYER_WORST_TOKENS for name in layers
    ):
        return VERDICT_UNAVAILABLE, reasons
    return VERDICT_NOT_READY, reasons


def build_research_health_report(
    settings: PlatformSettings | None = None,
) -> dict[str, Any]:
    """Compute the five-layer research health snapshot for the rating system.

    Read-only and local: reads parquet/JSON artifacts under the configured
    data root, reuses ``model_admission`` and ``truth_labels`` builders, and
    never falls back to synthetic data. A missing or unreadable file is
    reported as ``unavailable``/``unverified`` rather than silently replaced.

    The top-level ``verdict`` is fail-closed: it is ``ready`` only when every
    layer reports ok/ready. Stale lineage, zero reviewable runs, missing
    independent labels or synthetic active ratings all force ``not_ready``
    or ``unavailable`` so the rating system can no longer be described as
    ready while hiding a broken chain of custody.
    """
    resolved = settings or PlatformSettings.from_root()
    storage = _build_storage_health(resolved)
    lineage = _build_lineage_health(resolved, storage=storage)
    reviewability = _build_model_reviewability(resolved, storage=storage)
    freshness = _build_active_rating_freshness(
        resolved, storage=storage, lineage=lineage
    )
    readiness = _build_research_readiness(
        resolved,
        storage=storage,
        lineage=lineage,
        reviewability=reviewability,
        freshness=freshness,
    )
    # Evidence-only sections (PRS-0 R-003 status report): surface feature
    # missingness and data grain so the maintainer no longer hand-copies
    # these into planning docs. They do not participate in the verdict.
    feature_coverage = _build_feature_coverage(resolved, storage=storage)
    data_grain = _build_data_grain(resolved, storage=storage)
    # PRS-1 R-006/R-007 typed grain + missingness audit. Read-only and
    # local; surfaces typed EvidenceGrain / ObservationType / MissingReason
    # so the maintainer can verify "unknown" vs "actual_zero" vs
    # "not_recorded" without hand-inspecting parquet. Like the other
    # evidence sections, this does not participate in the fail-closed
    # verdict — PRS-1 verification will gate on it later.
    grain_and_missingness = _build_grain_and_missingness_audit(resolved)
    identity_registry = _build_identity_registry_audit(resolved)
    canonical_resolution = _build_canonical_resolution_audit(resolved)
    role_system = _build_role_system_audit(resolved)
    label_ledger, ledger_records = _build_label_ledger_audit(resolved)
    label_review_queue = _build_label_review_queue_audit(
        resolved, records=ledger_records
    )
    label_stability = _build_label_stability_audit(
        resolved, records=ledger_records
    )
    weight_sensitivity = _build_weight_sensitivity_audit(resolved)
    minutes_sensitivity = _build_minutes_sensitivity_audit(resolved)
    layers = {
        "storage_health": storage,
        "lineage_health": lineage,
        "model_reviewability": reviewability,
        "active_rating_freshness": freshness,
        "research_readiness": readiness,
    }
    verdict, blocking_reasons = _compute_verdict(layers)
    return {
        "schema": RESEARCH_HEALTH_SCHEMA,
        "schema_version": RESEARCH_HEALTH_VERSION,
        "generated_at": _now(),
        "verdict": verdict,
        "blocking_reasons": blocking_reasons,
        **layers,
        "feature_coverage": feature_coverage,
        "data_grain": data_grain,
        "grain_and_missingness": grain_and_missingness,
        "identity_registry": identity_registry,
        "canonical_resolution": canonical_resolution,
        "role_system": role_system,
        "label_ledger": label_ledger,
        "label_review_queue": label_review_queue,
        "label_stability": label_stability,
        "weight_sensitivity": weight_sensitivity,
        "minutes_sensitivity": minutes_sensitivity,
        "limitations": [
            (
                "Local-only read-only diagnostic; no telemetry is uploaded. "
                "verdict=ready means the rating system is computationally "
                "reviewable, not that the underlying model is correct."
            ),
            (
                "Synthetic fallback data is isolated from this report: the "
                "active rating parquet is read directly, never via data_loader."
            ),
            (
                "Label independence is a source-policy check, not proof of "
                "collection independence; expert_tier is always excluded."
            ),
            (
                "Use `scoutfootball research-health` or GET /health/research "
                "for this report; get_detailed_health surfaces a summary."
            ),
            (
                "grain_and_missingness is PRS-1 R-006/R-007 best-evidence "
                "audit, not canonical schema enforcement. "
                "MissingReason.ACTUAL_ZERO is not auto-detected; the enum "
                "exists so downstream code can label rows when the "
                "source-level event join (planned for a later PRS-1 slice) "
                "provides that evidence."
            ),
            (
                "identity_registry is PRS-1 R-005's append-only ledger of "
                "explicit human (source, source_id) -> canonical_player_id "
                "decisions. An empty registry is the honest default before "
                "any decision has been recorded; it does not block the "
                "verdict because unresolved status is not a failure. Use "
                "`scoutfootball identity-registry-*` CLI to record or "
                "inspect decisions."
            ),
            (
                "canonical_resolution is PRS-1 R-005's read-only resolver "
                "output: it applies the registry's active confirmed "
                "mappings to a derived view of player_match.parquet and "
                "counts resolved vs unresolved rows. Unresolved rows are "
                "marked `unresolved:<source>:<id>` so they stay visible "
                "instead of being silently promoted to canonical. The "
                "original player_match.parquet is never modified. An "
                "all-unresolved result does not block the verdict."
            ),
            (
                "role_system is PRS-1 R-009's v1 position-family audit: "
                "it classifies position_group into 8 typed RoleFamily "
                "values (GK/CB/FB/DM/CM/AM/W/ST) so PRS-2 in-role "
                "baseline slicing has a stable vocabulary. Coarse source "
                "labels DF/MF/FW collapse to default fine roles "
                "(CB/CM/ST) and are flagged via coarse_position_rows; "
                "v1 does not auto-invent DM from MF and does not include "
                "a role override registry. An all-unknown result does "
                "not block the verdict."
            ),
            (
                "label_ledger is PRS-3 slice 1's append-only JSONL ledger "
                "of maintainer personal evaluations (human_pairwise_"
                "preference and human_tier labels). The independence "
                "audit excludes model_derived labels from the "
                "supervision-eligible set, checks pairwise labels do not "
                "self-compare, and checks observation windows are valid. "
                "An empty ledger is the honest default before any "
                "personal evaluation has been recorded; it does not "
                "block the verdict because the absence of independent "
                "labels is already reflected in research_readiness. The "
                "audit is structural only; it does not prove the "
                "annotator was truly blind or that evidence is correct. "
                "Use `scoutfootball label-append`/`label-list`/`label-"
                "stats`/`label-audit` CLI to record or inspect labels."
            ),
            (
                "label_review_queue is PRS-LABEL-005's diagnostic of "
                "which active labels need maintainer re-review: pairwise "
                "preference contradictions, tier rating conflicts (span "
                ">= 2), low-confidence/thin-evidence labels, and aged "
                "labels (>= 180 days). It does not participate in the "
                "fail-closed verdict because review items are signals, "
                "not failures. status=ok only means no auto-detectable "
                "review signals exist, not that labels are correct or "
                "supervision-ready. Use `scoutfootball label-review-"
                "queue` CLI for the full report."
            ),
            (
                "label_stability is PRS-LABEL-006's read-only diagnostic "
                "of annotation stability: retest_pairs traced via "
                "supersedes_decision_id chains (original -> retest), and "
                "annotator_agreement groups where multiple distinct "
                "decided_by values annotated the same business key. It "
                "does not participate in the fail-closed verdict because "
                "stability metrics are signals, not gates. An empty "
                "ledger returns 0/0/0/0 honestly; absence of retest or "
                "agreement signals does not mean labels are correct or "
                "supervision-ready. The report does not prove annotators "
                "were truly blind or that evidence is correct; it only "
                "compares label values structurally. Use "
                "`scoutfootball label-stability` CLI for the full report."
            ),
            (
                "weight_sensitivity is PRS-MODEL-011's read-only "
                "diagnostic of B1 expert-weight robustness: it perturbs "
                "each dimension weight by multiplicative deltas "
                "(default ±10%/±20%), renormalises, recomputes B1 "
                "scores, and measures ranking stability (Spearman, mean/"
                "max rank shift, top-N overlap) versus the baseline. It "
                "does not participate in the fail-closed verdict because "
                "sensitivity metrics are signals, not gates. status=ok "
                "only means the report could be built, not that the "
                "weights are correct or that the ranking is trustworthy. "
                "Use `scoutfootball weight-sensitivity` CLI for the "
                "full report with custom deltas."
            ),
            (
                "minutes_sensitivity is PRS-MODEL-012's read-only "
                "diagnostic of B2 minutes-threshold robustness: it "
                "perturbs reference_minutes by absolute minute deltas "
                "(default ±150/±300/±600), recomputes B2 scores "
                "(shrinkage weight + prior_mean + stable_core membership "
                "all change), and measures ranking stability versus the "
                "baseline. It does not participate in the fail-closed "
                "verdict because sensitivity metrics are signals, not "
                "gates. status=ok only means the report could be built, "
                "not that the threshold is correct or that the ranking "
                "is trustworthy. Use `scoutfootball minutes-sensitivity` "
                "CLI for the full report with custom deltas."
            ),
        ],
    }

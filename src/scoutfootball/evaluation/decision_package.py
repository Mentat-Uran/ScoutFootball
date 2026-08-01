"""Fail-closed validation for local ScoutFootball decision-package exports."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

DECISION_PACKAGE_REPORT_SCHEMA = "scoutfootball.decision-package-validation"
DECISION_PACKAGE_REPORT_VERSION = "1.0.0"
MAX_DECISION_PACKAGE_BYTES = 5 * 1024 * 1024

_WC_BRIEFING_SCHEMA = "scoutfootball.world-cup-match-briefing"
_WC_BRIEFING_EXPORT_SCHEMA = "scoutfootball.world-cup-match-briefing-export"
_WC_BRIEFING_COLLECTION_SCHEMA = "scoutfootball.world-cup-match-briefings"
_SHORTLIST_SCHEMA = "scoutfootball.shortlist-decision-pack"


class DecisionPackageValidationError(ValueError):
    """Raised when a caller asks to read an unsafe local decision-package file."""


def _check(name: str, passed: bool, note: str) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail", "note": note}


def _is_object(value: object) -> bool:
    return isinstance(value, dict)


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_iso_timestamp(value: object) -> bool:
    if not _is_nonempty_string(value):
        return False
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _finite_probability(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value)) and 0.0 <= value <= 1.0


def _limitations_check(value: object) -> bool:
    return (
        isinstance(value, list) and bool(value) and all(_is_nonempty_string(item) for item in value)
    )


def _build_report(
    package: dict[str, Any],
    *,
    package_type: str,
    checks: list[dict[str, str]],
    details: dict[str, Any],
) -> dict[str, Any]:
    failed = [check["name"] for check in checks if check["status"] == "fail"]
    return {
        "schema": DECISION_PACKAGE_REPORT_SCHEMA,
        "version": DECISION_PACKAGE_REPORT_VERSION,
        "package_schema": package.get("schema"),
        "package_version": package.get("version"),
        "package_type": package_type,
        "status": "valid" if not failed else "invalid",
        "checks": checks,
        "failed_checks": failed,
        "details": details,
        "limitations": [
            (
                "Validation checks the local export contract and recorded evidence fields; "
                "it does not verify upstream facts."
            ),
            (
                "A valid package remains subject to its own coverage, source, model, "
                "and browser-local limitations."
            ),
        ],
    }


def _validate_world_cup_briefing(briefing: dict[str, Any]) -> dict[str, Any]:
    fixture = briefing.get("fixture") if _is_object(briefing.get("fixture")) else {}
    prediction = briefing.get("prediction") if _is_object(briefing.get("prediction")) else {}
    teams = briefing.get("teams") if _is_object(briefing.get("teams")) else {}
    snapshot = briefing.get("input_snapshot") if _is_object(briefing.get("input_snapshot")) else {}
    probabilities = [prediction.get(key) for key in ("home_win", "draw", "away_win")]
    total_probability = sum(float(value) for value in probabilities if _finite_probability(value))
    snapshot_status = snapshot.get("status")
    snapshot_is_honest = snapshot_status in {"recorded", "not_recorded"}
    snapshot_complete = snapshot_status != "recorded" or (
        _is_nonempty_string(snapshot.get("rating_model_run_id"))
        and _is_nonempty_string(snapshot.get("rating_input_hash"))
    )
    home = teams.get("home") if _is_object(teams.get("home")) else {}
    away = teams.get("away") if _is_object(teams.get("away")) else {}
    coverage_values = [
        (home.get("squad") or {}).get("rating_coverage") if _is_object(home.get("squad")) else None,
        (away.get("squad") or {}).get("rating_coverage") if _is_object(away.get("squad")) else None,
    ]
    checks = [
        _check(
            "briefing_schema",
            briefing.get("schema") == _WC_BRIEFING_SCHEMA,
            "world-cup briefing schema",
        ),
        _check(
            "briefing_version", briefing.get("version") == "1.0.0", "supported briefing version"
        ),
        _check(
            "briefing_status",
            briefing.get("status") == "ok",
            "only an available briefing is a decision package",
        ),
        _check(
            "fixture",
            _is_nonempty_string(fixture.get("home_team"))
            and _is_nonempty_string(fixture.get("away_team"))
            and fixture.get("home_team") != fixture.get("away_team"),
            "two distinct named teams",
        ),
        _check(
            "prediction_model",
            _is_nonempty_string(prediction.get("model_type"))
            and _is_nonempty_string(prediction.get("model_version")),
            "model type and version are recorded",
        ),
        _check(
            "probabilities",
            all(_finite_probability(value) for value in probabilities)
            and abs(total_probability - 1.0) <= 0.002,
            "home/draw/away probabilities are finite and sum to approximately one",
        ),
        _check(
            "source_attribution",
            _is_nonempty_string(briefing.get("source_attribution")),
            "source attribution",
        ),
        _check(
            "limitations", _limitations_check(briefing.get("limitations")), "non-empty limitations"
        ),
        _check("input_snapshot_status", snapshot_is_honest, "recorded or explicitly not_recorded"),
        _check(
            "input_snapshot_record",
            snapshot_complete,
            "recorded snapshots include run id and input hash",
        ),
        _check(
            "team_context",
            home.get("team") == fixture.get("home_team")
            and away.get("team") == fixture.get("away_team"),
            "team context matches fixture",
        ),
        _check(
            "coverage_range",
            all(_finite_probability(value) for value in coverage_values),
            "both rating coverage values are finite proportions",
        ),
    ]
    return _build_report(
        briefing,
        package_type="world_cup_match_briefing",
        checks=checks,
        details={
            "fixture": fixture,
            "input_snapshot_status": snapshot_status,
            "source_attribution": briefing.get("source_attribution"),
            "coverage": {"home": coverage_values[0], "away": coverage_values[1]},
        },
    )


def _validate_world_cup_briefing_export(package: dict[str, Any]) -> dict[str, Any]:
    briefing = package.get("briefing") if _is_object(package.get("briefing")) else {}
    briefing_report = _validate_world_cup_briefing(briefing)
    checks = [
        _check(
            "export_schema",
            package.get("schema") == _WC_BRIEFING_EXPORT_SCHEMA,
            "briefing export schema",
        ),
        _check("export_version", package.get("version") == "1.0.0", "supported export version"),
        _check(
            "exported_at", _is_iso_timestamp(package.get("exported_at")), "ISO-8601 export time"
        ),
        _check(
            "storage_scope",
            package.get("storage_scope") == "browser-local-download",
            "explicit browser-local download scope",
        ),
        *briefing_report["checks"],
    ]
    return _build_report(
        package,
        package_type="world_cup_match_briefing_export",
        checks=checks,
        details=briefing_report["details"],
    )


def _validate_world_cup_briefing_collection(package: dict[str, Any]) -> dict[str, Any]:
    briefings = package.get("briefings")
    child_reports = (
        [_validate_world_cup_briefing(item) for item in briefings]
        if isinstance(briefings, list) and all(_is_object(item) for item in briefings)
        else []
    )
    failed_briefings = [
        index for index, report in enumerate(child_reports) if report["status"] != "valid"
    ]
    checks = [
        _check(
            "collection_schema",
            package.get("schema") == _WC_BRIEFING_COLLECTION_SCHEMA,
            "world-cup briefing collection schema",
        ),
        _check(
            "collection_version", package.get("version") == "1.0.0", "supported collection version"
        ),
        _check(
            "briefings", isinstance(briefings, list) and bool(briefings), "non-empty briefing array"
        ),
        _check(
            "briefing_contracts",
            bool(child_reports) and not failed_briefings,
            "every embedded briefing satisfies the decision-package contract",
        ),
    ]
    return _build_report(
        package,
        package_type="world_cup_match_briefing_collection",
        checks=checks,
        details={
            "briefing_count": len(briefings) if isinstance(briefings, list) else 0,
            "invalid_briefing_indexes": failed_briefings,
        },
    )


def _validate_shortlist_package(package: dict[str, Any]) -> dict[str, Any]:
    players = package.get("players")
    watchlist = package.get("watchlist_players")
    provenance = package.get("provenance_log")
    declared_players = package.get("player_count")
    declared_watchlist = package.get("watchlist_player_count")
    player_count_matches = (
        isinstance(players, list)
        and type(declared_players) is int
        and declared_players == len(players)
    )
    watchlist_count_matches = (
        isinstance(watchlist, list)
        and type(declared_watchlist) is int
        and declared_watchlist == len(watchlist)
    )
    declared_status_matches = (
        player_count_matches
        and watchlist_count_matches
        and package.get("status") == ("ok" if declared_players + declared_watchlist else "empty")
    )
    checks = [
        _check(
            "shortlist_schema",
            package.get("schema") == _SHORTLIST_SCHEMA,
            "shortlist decision-pack schema",
        ),
        _check(
            "shortlist_version",
            package.get("version") in {"1.0.0", "1.1.0", "1.2.0"},
            "supported pack version",
        ),
        _check(
            "exported_at", _is_iso_timestamp(package.get("exported_at")), "ISO-8601 export time"
        ),
        _check(
            "storage_scope",
            package.get("storage_scope") == "browser-local-download",
            "browser-local only",
        ),
        _check(
            "status",
            declared_status_matches,
            "status matches the declared shortlist and watchlist counts",
        ),
        _check("players", isinstance(players, list), "players is an array"),
        _check(
            "player_count",
            player_count_matches,
            "declared player count matches rows",
        ),
        _check(
            "watchlist",
            watchlist_count_matches,
            "declared watchlist count matches rows",
        ),
        _check("provenance_log", isinstance(provenance, list), "browser-local provenance array"),
        _check(
            "limitations",
            _limitations_check(package.get("limitations")),
            "non-empty local-scope limitations",
        ),
    ]
    return _build_report(
        package,
        package_type="shortlist_decision_pack",
        checks=checks,
        details={
            "storage_scope": package.get("storage_scope"),
            "player_count": declared_players,
            "watchlist_player_count": declared_watchlist,
            "provenance_status": "browser_local_context",
        },
    )


def validate_decision_package(package: object) -> dict[str, Any]:
    """Validate one local decision package without changing it or its sources."""
    if not _is_object(package):
        return _build_report(
            {},
            package_type="unknown",
            checks=[_check("package_object", False, "top-level JSON value must be an object")],
            details={},
        )
    schema = package.get("schema")
    if schema == _WC_BRIEFING_EXPORT_SCHEMA:
        return _validate_world_cup_briefing_export(package)
    if schema == _WC_BRIEFING_COLLECTION_SCHEMA:
        return _validate_world_cup_briefing_collection(package)
    if schema == _WC_BRIEFING_SCHEMA:
        return _validate_world_cup_briefing(package)
    if schema == _SHORTLIST_SCHEMA:
        return _validate_shortlist_package(package)
    return _build_report(
        package,
        package_type="unknown",
        checks=[
            _check("supported_schema", False, f"unsupported decision-package schema: {schema!r}")
        ],
        details={},
    )


def validate_decision_package_file(path: Path | str) -> dict[str, Any]:
    """Read and validate one user-selected local JSON export safely."""
    file_path = Path(path)
    if file_path.is_symlink() or not file_path.is_file():
        raise DecisionPackageValidationError("decision package must be a regular local file")
    if file_path.stat().st_size > MAX_DECISION_PACKAGE_BYTES:
        raise DecisionPackageValidationError(
            f"decision package exceeds {MAX_DECISION_PACKAGE_BYTES} byte local limit"
        )
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DecisionPackageValidationError(
            f"decision package cannot be read as UTF-8 JSON: {type(exc).__name__}"
        ) from exc
    report = validate_decision_package(payload)
    report["path"] = str(file_path.resolve())
    report["size_bytes"] = file_path.stat().st_size
    return report


def format_decision_package_report(report: dict[str, Any]) -> str:
    """Render a compact local decision-package validation result."""
    lines = [
        f"Decision package: {report['status']} ({report['package_type']})",
        f"  Schema: {report.get('package_schema')} v{report.get('package_version')}",
    ]
    if report["failed_checks"]:
        lines.append("  Failed: " + ", ".join(report["failed_checks"]))
    return "\n".join(lines)

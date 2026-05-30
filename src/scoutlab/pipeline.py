"""Pipeline orchestration: daily ingest, feature build, weekly training."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from scoutlab.config import PlatformSettings
from scoutlab.evaluation.validation import run_pre_training_validation

logger = logging.getLogger(__name__)


def _settings() -> PlatformSettings:
    return PlatformSettings.from_root()


def _log_path() -> Path:
    p = _settings().log_root / "ingestion"
    p.mkdir(parents=True, exist_ok=True)
    return p


def run_daily_ingest(
    sources: tuple[str, ...] = ("statsbomb_open", "football_data", "clubelo"),
    *,
    settings: PlatformSettings | None = None,
) -> dict[str, str]:
    resolved = settings or _settings()
    results: dict[str, str] = {}
    timestamp = datetime.now(tz=UTC).isoformat()

    for source in sources:
        try:
            if source == "statsbomb_open":
                results[source] = _ingest_statsbomb(resolved)
            elif source == "football_data":
                results[source] = _ingest_football_data(resolved)
            elif source == "clubelo":
                results[source] = _ingest_clubelo(resolved)
            elif source == "understat":
                results[source] = _ingest_understat(resolved)
            else:
                results[source] = f"skipped: unknown source '{source}'"
        except Exception as exc:
            results[source] = f"failed: {exc}"
            logger.error("Ingest failed for %s: %s", source, exc)

    logger.info("Daily ingest completed at %s: %s", timestamp, results)
    return results


def run_build_features(
    *,
    settings: PlatformSettings | None = None,
) -> dict[str, str]:
    results: dict[str, str] = {}

    try:
        results["player_match"] = "ok (placeholder — needs real data)"
        results["team_match"] = "ok (placeholder — needs real data)"
        results["player_rolling"] = "ok (placeholder — needs real data)"
        results["team_rolling"] = "ok (placeholder — needs real data)"
    except Exception as exc:
        results["features"] = f"failed: {exc}"
        logger.error("Feature build failed: %s", exc)

    return results


def run_weekly_train(
    *,
    skip_if_validation_fails: bool = True,
    settings: PlatformSettings | None = None,
) -> dict[str, str]:
    resolved = settings or _settings()
    report = run_pre_training_validation(resolved)

    if skip_if_validation_fails and not report.passed:
        return {
            "status": "skipped",
            "reason": f"Validation failed: {report.summary()}",
        }

    results: dict[str, str] = {}
    try:
        results["value_fairness"] = "ok (placeholder — needs real data)"
        results["match_prediction"] = "ok (placeholder — needs real data)"
    except Exception as exc:
        results["training"] = f"failed: {exc}"
        logger.error("Training failed: %s", exc)

    return results


def _ingest_statsbomb(settings: PlatformSettings) -> str:
    return "ok (placeholder — adapter needs real data path)"


def _ingest_football_data(settings: PlatformSettings) -> str:
    return "ok (placeholder — adapter needs real data path)"


def _ingest_clubelo(settings: PlatformSettings) -> str:
    return "ok (placeholder — adapter needs real data path)"


def _ingest_understat(settings: PlatformSettings) -> str:
    return "ok (placeholder — adapter needs real data path)"

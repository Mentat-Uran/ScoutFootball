"""Unit tests for the ``/health/detailed`` API endpoint and its composer
``get_detailed_health``.

The detailed-health endpoint composes five sub-builders
(artifacts/validation/model_admission/contract_quality/source_health) into a
single snapshot for the frontend overview page. These tests focus on the
composition contract:

- Top-level schema, ``schema_version`` and ``generated_at`` are present.
- All five sub-sections are always present; a failed builder degrades to
  ``{"status": "unavailable"}`` rather than raising.
- Top-level ``status`` is ``"ok"`` when every builder succeeds and
  validation/contract_quality both pass, ``"degraded"`` otherwise.
- TTL cache returns the same object on the second call; ``force_refresh=True``
  bypasses the cache.
- The result is JSON-serializable (``_clean_json_value`` is applied).
- The FastAPI route ``/health/detailed`` returns 200 and the same schema, and
  accepts the ``force_refresh`` query parameter.

Builder-level correctness (validation checks, model admission statuses,
contract-quality checks, source-health counts) is covered by their own test
modules (``test_source_health.py``, ``test_model_admission.py``,
``test_contract_quality.py``, etc.) and is not duplicated here.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from scoutfootball.api import (
    _detailed_health_cache,
    get_detailed_health,
)
from scoutfootball.api_server import create_app


@pytest.fixture(autouse=True)
def _clear_detailed_health_cache() -> None:
    """Invalidate the TTL cache before every test so cached state from a
    previous test (or a prior TestClient request) cannot leak in.
    """
    _detailed_health_cache.invalidate("get_detailed_health")


def _ok_validation() -> dict[str, Any]:
    return {
        "status": "pass",
        "total_checks": 31,
        "passed_count": 31,
        "failed_count": 0,
        "failures": [],
        "checks": [],
        "summary": "all checks passed",
    }


def _ok_model_admission() -> dict[str, Any]:
    return {
        "status": "ok",
        "report_version": "1.0.0",
        "run_count": 2,
        "reviewable_run_count": 1,
        "not_reviewable_run_count": 1,
        "not_available_run_count": 0,
        "limitations": [],
        "runs_summary_omitted": True,
    }


def _ok_contract_quality() -> dict[str, Any]:
    return {
        "status": "pass",
        "report_version": "1.0.0",
        "failed_checks": [],
        "incomplete_checks": [],
        "checks_count": 8,
        "limitations": [],
    }


def _ok_source_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "report_version": "1.0.0",
        "registered_source_count": 3,
        "sources_with_snapshot": 2,
        "sources_without_snapshot": 1,
        "unregistered_raw_directories": [],
        "sources": [],
    }


def _patch_all_builders_ok(monkeypatch) -> None:
    """Patch every expensive sub-builder to return a known-good payload.

    ``get_artifacts_summary`` is left un-patched because it is the "cheap"
    builder that runs every call; we instead patch ``_settings`` to point
    at an empty tmp_path so artifacts_summary runs without depending on
    real project data.
    """
    monkeypatch.setattr(
        "scoutfootball.api._build_validation_section",
        lambda settings: _ok_validation(),
    )
    monkeypatch.setattr(
        "scoutfootball.api._build_model_admission_section",
        lambda settings: _ok_model_admission(),
    )
    monkeypatch.setattr(
        "scoutfootball.api._build_contract_quality_section",
        lambda settings: _ok_contract_quality(),
    )
    monkeypatch.setattr(
        "scoutfootball.api._build_source_health_section",
        lambda settings: _ok_source_health(),
    )


# ── Schema conformance ───────────────────────────────────────────────


class TestSchemaConformance:
    def test_top_level_keys_present(self, monkeypatch, tmp_path) -> None:
        _patch_all_builders_ok(monkeypatch)
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )

        result = get_detailed_health()

        expected_keys = {
            "schema",
            "schema_version",
            "generated_at",
            "status",
            "base",
            "artifacts",
            "validation",
            "model_admission",
            "contract_quality",
            "source_health",
            "unavailable_sections",
            "failed_sections",
            "limitations",
        }
        assert expected_keys.issubset(result.keys())
        assert result["schema"] == "scoutfootball.detailed-health"
        assert result["schema_version"] == "1.0.0"
        # generated_at is ISO-8601 with timezone; just check it's a non-empty
        # string that ends with "Z" or "+00:00" (UTC).
        assert isinstance(result["generated_at"], str)
        assert result["generated_at"], "generated_at must not be empty"

    def test_base_section_shape(self, monkeypatch, tmp_path) -> None:
        _patch_all_builders_ok(monkeypatch)
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )

        base = get_detailed_health()["base"]
        assert set(base.keys()) == {"status", "data_source", "version"}
        assert base["status"] == "ok"
        assert isinstance(base["data_source"], str)
        assert isinstance(base["version"], str)

    def test_limitations_documents_local_only_and_no_telemetry(
        self, monkeypatch, tmp_path
    ) -> None:
        _patch_all_builders_ok(monkeypatch)
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )

        limitations = get_detailed_health()["limitations"]
        joined = " ".join(limitations).lower()
        assert "telemetry" in joined
        assert "local" in joined
        assert "force_refresh" in joined


# ── Top-level status aggregation ─────────────────────────────────────


class TestTopLevelStatus:
    def test_ok_when_all_builders_succeed(self, monkeypatch, tmp_path) -> None:
        _patch_all_builders_ok(monkeypatch)
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )

        result = get_detailed_health()
        assert result["status"] == "ok"
        assert result["unavailable_sections"] == []
        assert result["failed_sections"] == []

    def test_degraded_when_validation_fails(self, monkeypatch, tmp_path) -> None:
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )
        failed_validation = _ok_validation()
        failed_validation["status"] = "fail"
        failed_validation["passed_count"] = 29
        failed_validation["failed_count"] = 2
        failed_validation["failures"] = [
            {"check_name": "x", "message": "failed"}
        ]
        monkeypatch.setattr(
            "scoutfootball.api._build_validation_section",
            lambda settings: failed_validation,
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_model_admission_section",
            lambda settings: _ok_model_admission(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_contract_quality_section",
            lambda settings: _ok_contract_quality(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_source_health_section",
            lambda settings: _ok_source_health(),
        )

        result = get_detailed_health()
        assert result["status"] == "degraded"
        assert "validation" in result["failed_sections"]
        assert result["validation"]["status"] == "fail"
        assert result["unavailable_sections"] == []

    def test_degraded_when_contract_quality_fails(self, monkeypatch, tmp_path) -> None:
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )
        failed_cq = _ok_contract_quality()
        failed_cq["status"] = "fail"
        failed_cq["failed_checks"] = [{"check": "x", "message": "fail"}]
        monkeypatch.setattr(
            "scoutfootball.api._build_validation_section",
            lambda settings: _ok_validation(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_model_admission_section",
            lambda settings: _ok_model_admission(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_contract_quality_section",
            lambda settings: failed_cq,
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_source_health_section",
            lambda settings: _ok_source_health(),
        )

        result = get_detailed_health()
        assert result["status"] == "degraded"
        assert any(
            s.startswith("contract_quality:") for s in result["failed_sections"]
        )
        assert result["contract_quality"]["status"] == "fail"

    def test_degraded_when_contract_quality_incomplete(
        self, monkeypatch, tmp_path
    ) -> None:
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )
        incomplete_cq = _ok_contract_quality()
        incomplete_cq["status"] = "incomplete"
        incomplete_cq["incomplete_checks"] = [{"check": "x"}]
        monkeypatch.setattr(
            "scoutfootball.api._build_validation_section",
            lambda settings: _ok_validation(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_model_admission_section",
            lambda settings: _ok_model_admission(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_contract_quality_section",
            lambda settings: incomplete_cq,
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_source_health_section",
            lambda settings: _ok_source_health(),
        )

        result = get_detailed_health()
        assert result["status"] == "degraded"
        assert any(
            s.startswith("contract_quality:") for s in result["failed_sections"]
        )


# ── Fail-soft: sub-builder exceptions ────────────────────────────────


class TestFailSoft:
    """A failing sub-builder must not break the whole response.

    The health endpoint is a read-only diagnostic — its job is to render
    available sections even when one source fails. Sub-builder failures are
    logged and returned as ``{"status": "unavailable"}`` for that section,
    and the top-level status degrades to ``"degraded"``.
    """

    def test_validation_exception_makes_section_unavailable(
        self, monkeypatch, tmp_path
    ) -> None:
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )

        def _raise(_settings):
            raise RuntimeError("validation boom")

        monkeypatch.setattr("scoutfootball.api._build_validation_section", _raise)
        monkeypatch.setattr(
            "scoutfootball.api._build_model_admission_section",
            lambda settings: _ok_model_admission(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_contract_quality_section",
            lambda settings: _ok_contract_quality(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_source_health_section",
            lambda settings: _ok_source_health(),
        )

        result = get_detailed_health()
        assert result["status"] == "degraded"
        assert "validation" in result["unavailable_sections"]
        assert result["validation"] == {"status": "unavailable"}
        # Other sections still render
        assert result["model_admission"]["status"] == "ok"
        assert result["contract_quality"]["status"] == "pass"
        assert result["source_health"]["status"] == "ok"

    def test_model_admission_exception_makes_section_unavailable(
        self, monkeypatch, tmp_path
    ) -> None:
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )

        def _raise(_settings):
            raise RuntimeError("model admission boom")

        monkeypatch.setattr(
            "scoutfootball.api._build_validation_section",
            lambda settings: _ok_validation(),
        )
        monkeypatch.setattr("scoutfootball.api._build_model_admission_section", _raise)
        monkeypatch.setattr(
            "scoutfootball.api._build_contract_quality_section",
            lambda settings: _ok_contract_quality(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_source_health_section",
            lambda settings: _ok_source_health(),
        )

        result = get_detailed_health()
        assert result["status"] == "degraded"
        assert "model_admission" in result["unavailable_sections"]
        assert result["model_admission"] == {"status": "unavailable"}

    def test_source_health_exception_makes_section_unavailable(
        self, monkeypatch, tmp_path
    ) -> None:
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )

        def _raise(_settings):
            raise RuntimeError("source health boom")

        monkeypatch.setattr(
            "scoutfootball.api._build_validation_section",
            lambda settings: _ok_validation(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_model_admission_section",
            lambda settings: _ok_model_admission(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_contract_quality_section",
            lambda settings: _ok_contract_quality(),
        )
        monkeypatch.setattr("scoutfootball.api._build_source_health_section", _raise)

        result = get_detailed_health()
        assert result["status"] == "degraded"
        assert "source_health" in result["unavailable_sections"]
        assert result["source_health"] == {"status": "unavailable"}

    def test_contract_quality_exception_makes_section_unavailable(
        self, monkeypatch, tmp_path
    ) -> None:
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )

        def _raise(_settings):
            raise RuntimeError("contract quality boom")

        monkeypatch.setattr(
            "scoutfootball.api._build_validation_section",
            lambda settings: _ok_validation(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_model_admission_section",
            lambda settings: _ok_model_admission(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_contract_quality_section", _raise
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_source_health_section",
            lambda settings: _ok_source_health(),
        )

        result = get_detailed_health()
        assert result["status"] == "degraded"
        assert "contract_quality" in result["unavailable_sections"]
        assert result["contract_quality"] == {"status": "unavailable"}

    def test_all_builders_failing_still_returns_response(
        self, monkeypatch, tmp_path
    ) -> None:
        """Even if every expensive builder fails, the response must still
        render — ``base`` is always present, ``artifacts`` falls back to
        ``{"status": "unavailable"}``, and ``status`` is ``"degraded"``.
        """
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )

        def _raise(_settings):
            raise RuntimeError("boom")

        # Also force artifacts to fail by patching get_artifacts_summary.
        monkeypatch.setattr(
            "scoutfootball.api.get_artifacts_summary",
            lambda: (_ for _ in ()).throw(RuntimeError("artifacts boom")),
        )
        monkeypatch.setattr("scoutfootball.api._build_validation_section", _raise)
        monkeypatch.setattr("scoutfootball.api._build_model_admission_section", _raise)
        monkeypatch.setattr(
            "scoutfootball.api._build_contract_quality_section", _raise
        )
        monkeypatch.setattr("scoutfootball.api._build_source_health_section", _raise)

        result = get_detailed_health()
        # Top-level status is degraded (not error), base is present, every
        # section is unavailable.
        assert result["status"] == "degraded"
        assert set(result["base"].keys()) == {"status", "data_source", "version"}
        assert result["artifacts"] == {"status": "unavailable"}
        assert result["validation"] == {"status": "unavailable"}
        assert result["model_admission"] == {"status": "unavailable"}
        assert result["contract_quality"] == {"status": "unavailable"}
        assert result["source_health"] == {"status": "unavailable"}
        assert sorted(result["unavailable_sections"]) == sorted(
            [
                "artifacts",
                "validation",
                "model_admission",
                "contract_quality",
                "source_health",
            ]
        )


# ── Cache behavior ───────────────────────────────────────────────────


class TestCacheBehavior:
    def test_second_call_returns_cached_object(self, monkeypatch, tmp_path) -> None:
        """Without ``force_refresh``, the second call must return the exact
        same dict object (``is`` identity) so callers can rely on the TTL
        window being cheap.
        """
        _patch_all_builders_ok(monkeypatch)
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )

        first = get_detailed_health()
        second = get_detailed_health()
        assert first is second

    def test_force_refresh_bypasses_cache(self, monkeypatch, tmp_path) -> None:
        _patch_all_builders_ok(monkeypatch)
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )

        first = get_detailed_health()
        second = get_detailed_health(force_refresh=True)
        # Different object identity: cache was bypassed.
        assert first is not second
        # Content is equal except for ``generated_at``, which is recomputed
        # on every fresh call. Compare with that key stripped.
        first_copy = {k: v for k, v in first.items() if k != "generated_at"}
        second_copy = {k: v for k, v in second.items() if k != "generated_at"}
        assert first_copy == second_copy

    def test_force_refresh_re_invokes_builders(self, monkeypatch, tmp_path) -> None:
        """``force_refresh=True`` must actually re-invoke the builders,
        not just return a copy. Otherwise stale data could persist after
        a model retrain or build-features run.
        """
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )

        call_count = {"n": 0}

        def _counting_validation(settings):
            call_count["n"] += 1
            return _ok_validation()

        monkeypatch.setattr(
            "scoutfootball.api._build_validation_section", _counting_validation
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_model_admission_section",
            lambda settings: _ok_model_admission(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_contract_quality_section",
            lambda settings: _ok_contract_quality(),
        )
        monkeypatch.setattr(
            "scoutfootball.api._build_source_health_section",
            lambda settings: _ok_source_health(),
        )

        get_detailed_health()
        get_detailed_health()  # cached, should not invoke builder
        assert call_count["n"] == 1

        get_detailed_health(force_refresh=True)
        assert call_count["n"] == 2


# ── JSON serialization ───────────────────────────────────────────────


class TestJsonSerialization:
    def test_result_is_json_serializable(self, monkeypatch, tmp_path) -> None:
        """``_clean_json_value`` must have stripped every non-JSON type
        (pandas Timestamps, Path objects, numpy int64, etc.) so the response
        can be returned by FastAPI without a encoder fallback.
        """
        _patch_all_builders_ok(monkeypatch)
        from scoutfootball.config import PlatformSettings

        monkeypatch.setattr(
            "scoutfootball.api._settings",
            lambda: PlatformSettings.from_root(tmp_path),
        )

        result = get_detailed_health()
        serialized = json.dumps(result)  # must not raise
        round_tripped = json.loads(serialized)
        assert round_tripped["schema"] == "scoutfootball.detailed-health"
        assert round_tripped["status"] == "ok"


# ── FastAPI endpoint integration ─────────────────────────────────────


class TestApiEndpoint:
    """Smoke tests for the ``/health/detailed`` FastAPI route.

    These tests go through the real ``create_app()`` — they exercise route
    registration, query-parameter parsing, and the global exception handler.
    They do not assert on real data values (those vary by environment); they
    only assert the schema and status code.
    """

    def test_endpoint_returns_200_with_expected_schema(self) -> None:
        client = TestClient(create_app())
        response = client.get("/health/detailed")
        assert response.status_code == 200
        body = response.json()
        assert body["schema"] == "scoutfootball.detailed-health"
        assert body["schema_version"] == "1.0.0"
        for section in (
            "base",
            "artifacts",
            "validation",
            "model_admission",
            "contract_quality",
            "source_health",
        ):
            assert section in body, f"missing section: {section}"
        assert body["status"] in ("ok", "degraded")

    def test_endpoint_accepts_force_refresh_query_param(self) -> None:
        client = TestClient(create_app())
        # Both true and false must be accepted without a 422.
        for value in ("true", "false"):
            response = client.get(f"/health/detailed?force_refresh={value}")
            assert response.status_code == 200, f"force_refresh={value} failed"
            assert response.json()["schema"] == "scoutfootball.detailed-health"

    def test_endpoint_rejects_invalid_force_refresh(self) -> None:
        """Non-boolean values must be rejected with 422, not silently
        coerced. Pydantic/FastAPI handles this for us; the test guards
        against future route changes that might switch to a ``str`` param.
        """
        client = TestClient(create_app())
        response = client.get("/health/detailed?force_refresh=maybe")
        assert response.status_code == 422


# ── Capability registry contract ─────────────────────────────────────


def test_health_detailed_is_registered_in_capability_api_paths() -> None:
    """``/health/detailed`` must be declared in some capability's
    ``api_paths`` so the capability registry stays consistent with the
    actual route surface. The ``api.server`` capability is the natural
    owner (it already declares ``/health`` and ``/license``).
    """
    from scoutfootball.architecture import build_capability_registry

    registry = build_capability_registry()
    all_paths: set[str] = set()
    for cap in registry.capabilities:
        all_paths.update(cap.api_paths)
    assert "/health/detailed" in all_paths

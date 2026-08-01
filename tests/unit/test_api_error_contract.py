"""API error-response contract tests.

Verifies that all top-level error responses returned by
``scoutfootball.api`` adhere to the uniform shape produced by
``_make_error_response``:

    {"status": "error", "error": str, "message": str}

Sub-capability inline reasons (e.g. ``{"available": False, "error": ...}``
nested inside an otherwise successful response, or ``find_similar_players``
returning ``{"count": 0, "target": None, "similar": [], "error": ...}``)
are intentionally NOT top-level errors and are excluded from the contract.

The static AST scan protects against regressions: any new ``return {...}``
in ``api.py`` that introduces a top-level ``"error"`` key must go through
``_make_error_response`` (direct call or dict spread).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scoutfootball.api import (
    _BACKTEST_CACHE,
    _make_error_response,
    get_decay_tuning,
    get_ensemble_prediction,
    get_form_weighted_prediction,
    get_world_cup_match_prediction,
)


class TestMakeErrorResponseHelper:
    """Direct contract tests for the uniform error-response builder."""

    def test_returns_dict_with_required_fields(self) -> None:
        result = _make_error_response("boom")

        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["error"] == "boom"
        assert result["message"] == "boom"

    def test_message_defaults_to_error_when_omitted(self) -> None:
        result = _make_error_response("no_data")

        assert result["error"] == "no_data"
        assert result["message"] == "no_data"

    def test_explicit_message_is_preserved(self) -> None:
        result = _make_error_response("no_data", message="No data available")

        assert result["error"] == "no_data"
        assert result["message"] == "No data available"

    def test_returns_fresh_dict_each_call(self) -> None:
        a = _make_error_response("x")
        b = _make_error_response("x")

        assert a == b
        assert a is not b
        a["mutated"] = True
        assert "mutated" not in b

    def test_all_values_are_strings(self) -> None:
        result = _make_error_response("code", message="desc")

        assert isinstance(result["status"], str)
        assert isinstance(result["error"], str)
        assert isinstance(result["message"], str)

    def test_no_extra_keys_by_default(self) -> None:
        result = _make_error_response("x")

        assert set(result.keys()) == {"status", "error", "message"}


def _assert_error_contract(payload: object, *, expected_error_substring: str | None = None) -> None:
    """Assert a payload conforms to the uniform error-response contract."""
    assert isinstance(payload, dict), f"expected dict, got {type(payload)!r}"
    assert payload.get("status") == "error", f"missing/invalid status: {payload!r}"
    assert isinstance(payload.get("error"), str) and payload["error"], (
        f"missing error: {payload!r}"
    )
    assert isinstance(payload.get("message"), str) and payload["message"], (
        f"missing message: {payload!r}"
    )
    if expected_error_substring is not None:
        assert expected_error_substring in payload["error"], (
            f"error {payload['error']!r} does not contain {expected_error_substring!r}"
        )


@pytest.fixture
def _wc_env(monkeypatch):
    """Stub WC enriched squads so only 'Alpha' and 'Beta' are valid teams."""
    fake_squads = {"Alpha": [], "Beta": []}
    monkeypatch.setattr(
        "scoutfootball.api._get_wc_enriched_squads",
        lambda *_, **__: (fake_squads, {"Alpha": 0.5, "Beta": 0.5}),
    )
    return fake_squads


class TestWorldCupPredictionErrorContract:
    """Verify World Cup prediction errors conform to the uniform contract."""

    def test_unknown_home_team(self, _wc_env) -> None:
        payload = get_world_cup_match_prediction("NotARealTeam", "Beta")

        _assert_error_contract(payload, expected_error_substring="home team")
        assert "NotARealTeam" in payload["error"]

    def test_unknown_away_team(self, _wc_env) -> None:
        payload = get_world_cup_match_prediction("Alpha", "NotARealTeam")

        _assert_error_contract(payload, expected_error_substring="away team")
        assert "NotARealTeam" in payload["error"]

    def test_same_home_and_away(self, _wc_env) -> None:
        payload = get_world_cup_match_prediction("Alpha", "Alpha")

        _assert_error_contract(payload, expected_error_substring="different")


class TestFormWeightedAndEnsembleErrorContract:
    """Trigger exception-path errors and verify contract conformance."""

    def test_form_weighted_prediction_insufficient_data(self, monkeypatch) -> None:
        monkeypatch.setattr("scoutfootball.api.load_team_match", lambda *_, **__: None)

        payload = get_form_weighted_prediction("A", "B")

        _assert_error_contract(payload, expected_error_substring="Insufficient team_match data")

    def test_ensemble_prediction_insufficient_data(self, monkeypatch) -> None:
        monkeypatch.setattr("scoutfootball.api.load_team_match", lambda *_, **__: None)

        payload = get_ensemble_prediction("A", "B")

        _assert_error_contract(payload, expected_error_substring="Insufficient team_match data")

    def test_form_weighted_prediction_exception_path(self, monkeypatch) -> None:
        # Sufficient rows (100 >= 50) but the model fit raises.
        monkeypatch.setattr(
            "scoutfootball.api.load_team_match",
            lambda *_, **__: ["row"] * 100,
        )

        def _raise(*_, **__):
            raise RuntimeError("form model failure")

        monkeypatch.setattr(
            "scoutfootball.models.fit_dixon_coles_with_form",
            _raise,
            raising=False,
        )

        payload = get_form_weighted_prediction("A", "B")

        _assert_error_contract(payload, expected_error_substring="form model failure")


class TestDecayTuningErrorContract:
    """Verify get_decay_tuning's exception path conforms to the contract.

    get_decay_tuning builds its error response by assigning to a local
    ``result`` variable and returning it at the end of the function, so
    the AST-based static scan in ``TestApiErrorContractStaticScan`` does
    not see it. This runtime test closes that gap.
    """

    def test_exception_path_returns_uniform_error_with_tuning_path(
        self, monkeypatch, tmp_path
    ) -> None:
        # Clear the cache so the function actually executes its body.
        _BACKTEST_CACHE.pop("tuning_data", None)
        _BACKTEST_CACHE.pop("tuning_timestamp", None)

        # tuning_path = settings.report_root / "calibration_backtest"
        # / "decay_tuning_results.json"; create the file at that exact path
        # so tuning_path.exists() returns True and we enter the else branch
        # where the _read_json exception path lives.
        calibration_dir = tmp_path / "calibration_backtest"
        calibration_dir.mkdir()
        fake_path = calibration_dir / "decay_tuning_results.json"
        fake_path.touch()

        class _FakeSettings:
            report_root = tmp_path

        monkeypatch.setattr("scoutfootball.api._settings", lambda: _FakeSettings())

        def _raise(*_, **__):
            raise RuntimeError("decay tuning read failure")

        monkeypatch.setattr("scoutfootball.api._read_json", _raise)

        payload = get_decay_tuning()

        _assert_error_contract(payload, expected_error_substring="decay tuning read failure")
        # Contextual field preserved via {**_make_error_response(...), ...} spread.
        assert payload["tuning_path"].endswith("decay_tuning_results.json")


_API_PATH = Path(__file__).resolve().parents[2] / "src" / "scoutfootball" / "api.py"


def _dict_literal_keys(node: ast.Dict) -> set[str]:
    """Return the set of string keys for an ast.Dict literal."""
    keys: set[str] = set()
    for k in node.keys:
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            keys.add(k.value)
    return keys


def _is_make_error_response_call(node: ast.AST) -> bool:
    """True when node is `_make_error_response(...)`."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return isinstance(func, ast.Name) and func.id == "_make_error_response"


def _dict_uses_make_error_response_spread(node: ast.Dict) -> bool:
    """True when the dict literal spreads _make_error_response(...)."""
    for value in node.values:
        if isinstance(value, ast.Starred) and _is_make_error_response_call(value.value):
            return True
    return False


def _collect_top_level_error_returns(tree: ast.Module) -> list[tuple[int, str]]:
    """Return (line_no, reason) for each return {...} that has a top-level
    "error" key but is NOT routed through _make_error_response.

    Excluded:
    - The helper's own return statement inside ``_make_error_response``.
    - Sub-capability inline reasons (containing "available", "count", "target"
      or "similar" keys): these are NOT top-level errors, they are embedded
      failure reasons inside an otherwise-successful payload.
    """
    offenders: list[tuple[int, str]] = []

    # Find the helper's own function body so we can skip its return statement.
    helper_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_make_error_response":
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Return):
                    helper_lines.add(stmt.lineno)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Dict):
            continue
        if node.lineno in helper_lines:
            continue

        keys = _dict_literal_keys(node.value)
        if "error" not in keys:
            continue

        # Sub-capability inline reason: success-shape carries failure reason.
        # These are intentionally exempt from the top-level error contract.
        sub_capability_markers = {"available", "count", "target", "similar"}
        if keys & sub_capability_markers:
            continue

        if _dict_uses_make_error_response_spread(node.value):
            continue

        offenders.append(
            (
                node.lineno,
                f"return dict with 'error' key bypasses _make_error_response: "
                f"keys={sorted(keys)}",
            ),
        )

    return offenders


class TestApiErrorContractStaticScan:
    """Static source-level contract: every top-level error return in
    api.py must go through _make_error_response.
    """

    def test_all_top_level_error_returns_use_helper(self) -> None:
        source = _API_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(_API_PATH))

        offenders = _collect_top_level_error_returns(tree)

        assert not offenders, (
            "Found top-level error returns in api.py that bypass _make_error_response. "
            "All new error returns must use _make_error_response(...) directly or via "
            "{**_make_error_response(...), ...} spread. Offenders:\n" +
            "\n".join(f"  line {line}: {msg}" for line, msg in offenders)
        )

    def test_helper_is_defined_in_api_module(self) -> None:
        source = _API_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(_API_PATH))

        defined = any(
            isinstance(node, ast.FunctionDef)
            and node.name == "_make_error_response"
            and any(
                isinstance(stmt, ast.Return)
                and isinstance(stmt.value, ast.Dict)
                for stmt in node.body
            )
            for node in ast.walk(tree)
        )

        assert defined, "_make_error_response must be defined in api.py and return a dict literal"

    def test_helper_returns_uniform_shape(self) -> None:
        """Inspect the helper's return statement statically."""
        source = _API_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(_API_PATH))

        helper = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "_make_error_response"
        )

        return_stmt = next(
            s for s in helper.body if isinstance(s, ast.Return) and isinstance(s.value, ast.Dict)
        )

        keys = _dict_literal_keys(return_stmt.value)
        assert keys == {"status", "error", "message"}, (
            f"_make_error_response must return exactly {{status, error, message}}; "
            f"got {sorted(keys)}"
        )

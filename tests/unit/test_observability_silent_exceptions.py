"""Observability contract: silent exception handlers must log.

Verifies two layers:

1. **Runtime**: when ``predict_match_dc`` raises inside
   ``run_dc_calibration_backtest``, a warning is emitted with the
   failing ``match_id`` and the backtest continues (so metrics are
   still produced for the remaining fixtures, but the skip is now
   visible instead of silent).

2. **Static AST scan**: every ``except Exception:`` block in the
   scoped observability modules must contain a ``logger.<level>(...)``
   call. This prevents regressions where a new silent exception handler
   is added without observability.

Scoped modules:
    - ``evaluation/backtests.py``
    - ``evaluation/scouting_queue.py``
    - ``pipeline.py``
    - ``features/manifest.py``  (data provenance / hashing)
    - ``features/rating_matrix.py``  (rating feature matrix + xT/VAEP merge)

The previously duplicated hash functions ``pipeline._hash_input_frames``
and ``rating_matrix._compute_dataframe_hash`` were consolidated into
``manifest.compute_dataframe_hash``; the fallback path now logs at
WARNING level, so no exemption is required.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pandas as pd
import pytest

from scoutfootball.evaluation.backtests import run_dc_calibration_backtest
from scoutfootball.models.match_prediction import fit_dixon_coles


def _make_team_match_df(n_teams: int = 6, n_seasons: int = 3) -> pd.DataFrame:
    """Mirror of the helper in test_backtests.py (kept local to avoid cross-
    module coupling for fixture construction)."""
    import numpy as np

    rng = np.random.default_rng(42)
    teams = [f"team_{i}" for i in range(n_teams)]
    rows = []
    match_id = 0
    for season in range(n_seasons):
        season_year = 2022 + season
        for round_num in range(4):
            for i in range(0, n_teams, 2):
                home, away = teams[i], teams[i + 1]
                hg = rng.poisson(1.5)
                ag = rng.poisson(1.1)
                match_date = f"{season_year}-{1 + round_num:02d}-{15 + i:02d}"
                rows.append({
                    "match_id": str(match_id),
                    "match_date": match_date,
                    "team_id": home,
                    "is_home": True,
                    "goals_for": hg,
                    "goals_against": ag,
                })
                rows.append({
                    "match_id": str(match_id),
                    "match_date": match_date,
                    "team_id": away,
                    "is_home": False,
                    "goals_for": ag,
                    "goals_against": hg,
                })
                match_id += 1
    return pd.DataFrame(rows)


def _write_dc_artifacts(tmp_path: Path, df: pd.DataFrame) -> None:
    """Write valid DC artifacts so _load_dc_artifacts succeeds."""
    model = fit_dixon_coles(df)
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    pd.DataFrame([
        {
            "model_type": "dixon_coles",
            "num_matches": model.num_matches,
            "rho": model.rho,
            "home_advantage": model.home_advantage,
            "league_mean_goals": model.league_mean_goals,
            "num_teams": len(model.team_attack),
            "half_life_days": model.half_life_days,
            "decay": model.decay,
        },
    ]).to_parquet(artifact_dir / "dixon_coles_results.parquet", index=False)
    pd.DataFrame({
        "team_id": sorted(model.team_attack),
        "attack_strength": [model.team_attack[t] for t in sorted(model.team_attack)],
        "defense_strength": [model.team_defense[t] for t in sorted(model.team_attack)],
    }).to_parquet(artifact_dir / "dc_team_strengths.parquet", index=False)


class TestDCCalibrationBacktestLogsPredictionFailures:
    """Runtime contract: failed predictions must be logged, not silent."""

    def test_failed_prediction_logs_warning_with_match_id(
        self, tmp_path, caplog, monkeypatch
    ) -> None:
        df = _make_team_match_df()
        _write_dc_artifacts(tmp_path, df)

        # Pick a real match_id from the fixtures and force its prediction to
        # raise. The backtest must continue and emit a warning containing
        # the failing match_id so operators can trace which matches were
        # silently dropped from calibration metrics.
        target_match_id = str(df.iloc[0]["match_id"])
        target_home = str(df.iloc[0]["team_id"])

        from scoutfootball.evaluation import backtests as bt_module

        original_predict = bt_module.predict_match_dc

        def _flaky_predict(model, home_id, away_id, *, max_goals=10):
            if home_id == target_home:
                raise RuntimeError("forced prediction failure for test")
            return original_predict(model, home_id, away_id, max_goals=max_goals)

        monkeypatch.setattr(bt_module, "predict_match_dc", _flaky_predict)

        with caplog.at_level(logging.WARNING, logger="scoutfootball.evaluation.backtests"):
            result = run_dc_calibration_backtest(df, tmp_path, save_detail=False)

        # Backtest still produces a result (other matches succeed).
        assert result.metrics["n_matches"] > 0

        warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and "DC calibration backtest" in r.getMessage()
        ]
        assert warnings, (
            "Expected a WARNING log from run_dc_calibration_backtest when "
            "predict_match_dc raises; got none. Silent exception swallowing "
            "regression detected."
        )
        # The match_id must appear in the log so operators can trace drops.
        assert any(target_match_id in r.getMessage() for r in warnings), (
            f"WARNING log did not include failing match_id={target_match_id!r}. "
            f"Messages: {[r.getMessage() for r in warnings]}"
        )


# ---------------------------------------------------------------------------
# Static AST scan: no silent ``except Exception:`` in observability modules.
# ---------------------------------------------------------------------------

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "scoutfootball"

# Modules in scope for the observability contract. Each must define a
# module-level ``logger = logging.getLogger(__name__)`` and every
# ``except Exception:`` block must contain a ``logger.<level>(...)`` call.
_OBSERVABILITY_MODULES = [
    _SRC_ROOT / "evaluation" / "backtests.py",
    _SRC_ROOT / "evaluation" / "scouting_queue.py",
    _SRC_ROOT / "pipeline.py",
    _SRC_ROOT / "features" / "manifest.py",
    _SRC_ROOT / "features" / "rating_matrix.py",
]

# Intentional exemptions: (module_relative_path, function_name).
# Kept empty by design — every silent ``except Exception:`` in scoped
# modules must either log or be refactored. Add an entry here only after
# confirming the silence is genuinely correct AND the surrounding code
# already provides equivalent observability (e.g. a downstream handler
# logs the terminal failure). The previously duplicated hash functions
# ``pipeline._hash_input_frames`` and ``rating_matrix._compute_dataframe_hash``
# were consolidated into ``manifest.compute_dataframe_hash``; the fallback
# path now logs at WARNING level, so no exemption is required.
_INTENTIONAL_EXEMPTIONS: set[tuple[str, str]] = set()


def _module_name(rel_path: str) -> str:
    return rel_path.replace("\\", "/").rsplit("/", 1)[-1]


def _function_name_containing(tree: ast.Module, lineno: int) -> str | None:
    """Return the name of the function/method enclosing ``lineno``."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= lineno <= node.end_lineno:
                return node.name
    return None


def _handler_has_logger_call(handler_body: list[ast.stmt]) -> bool:
    """True if the except handler body contains a ``logger.<level>(...)`` call."""
    for stmt in ast.walk(ast.Module(body=handler_body, type_ignores=[])):
        if isinstance(stmt, ast.Call):
            func = stmt.func
            # logger.warning(...), logger.debug(...), logger.info(...), etc.
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "logger"
            ):
                return True
    return False


def _collect_silent_exception_handlers(
    source_path: Path,
) -> list[tuple[int, str, str]]:
    """Return (line, func_name, reason) for each ``except Exception:`` block
    that lacks a ``logger.<level>(...)`` call.

    Only bare ``except Exception:`` (no ``as exc``) is flagged, because
    those are the silent-skip patterns. ``except Exception as exc:`` is
    typically followed by code that uses ``exc`` (e.g. building an error
    report) and is reviewed separately.
    """
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))

    offenders: list[tuple[int, str, str]] = []
    rel = str(source_path.relative_to(_SRC_ROOT))
    module_name = _module_name(rel)

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        # Only flag bare ``except Exception:`` (no ``as`` binding).
        if node.name is not None:
            continue
        # Check the type is ``Exception`` (a bare Name).
        if not (isinstance(node.type, ast.Name) and node.type.id == "Exception"):
            continue

        if _handler_has_logger_call(node.body):
            continue

        func_name = _function_name_containing(tree, node.lineno) or "<module>"
        # Apply intentional exemptions.
        if (module_name, func_name) in _INTENTIONAL_EXEMPTIONS:
            continue

        offenders.append(
            (
                node.lineno,
                func_name,
                f"except Exception: in {module_name}:{func_name} has no "
                f"logger.<level>(...) call",
            )
        )
    return offenders


class TestObservabilityStaticScan:
    """Static contract: every bare ``except Exception:`` in scoped modules
    must contain a ``logger.<level>(...)`` call."""

    @pytest.mark.parametrize(
        "module_rel",
        [
            "evaluation/backtests.py",
            "evaluation/scouting_queue.py",
            "pipeline.py",
            "features/manifest.py",
            "features/rating_matrix.py",
        ],
    )
    def test_module_has_logger_defined(self, module_rel: str) -> None:
        path = _SRC_ROOT / module_rel
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        has_logger = False
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "logger"
                        and isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Attribute)
                        and isinstance(node.value.func.value, ast.Name)
                        and node.value.func.value.id == "logging"
                        and node.value.func.attr == "getLogger"
                    ):
                        has_logger = True
                        break

        assert has_logger, (
            f"{module_rel} must define a module-level "
            f"``logger = logging.getLogger(__name__)`` for observability."
        )

    @pytest.mark.parametrize(
        "module_rel",
        [
            "evaluation/backtests.py",
            "evaluation/scouting_queue.py",
            "pipeline.py",
            "features/manifest.py",
            "features/rating_matrix.py",
        ],
    )
    def test_no_silent_exception_handlers(self, module_rel: str) -> None:
        path = _SRC_ROOT / module_rel
        offenders = _collect_silent_exception_handlers(path)

        assert not offenders, (
            f"Found silent ``except Exception:`` handlers in {module_rel} "
            f"without a logger call. All such handlers must log with "
            f"``logger.<level>(..., exc_info=True)`` so failures are "
            f"observable. Offenders:\n" +
            "\n".join(f"  line {line}: {msg}" for line, _, msg in offenders)
        )

    def test_intentional_exemptions_are_documented(self) -> None:
        """Sanity check: the exemption set must remain small and each entry
        must still exist in the source. This prevents stale exemptions from
        accumulating silently."""
        for module_rel, func_name in _INTENTIONAL_EXEMPTIONS:
            path = _SRC_ROOT / module_rel
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))

            exists = any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == func_name
                for node in ast.walk(tree)
            )
            assert exists, (
                f"Intentional exemption ({module_rel}, {func_name}) no longer "
                f"exists in source. Remove it from _INTENTIONAL_EXEMPTIONS."
            )

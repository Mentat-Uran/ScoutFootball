"""Tests for the GPU optimizer pre-training validation gate.

The gate lives in ``scripts/optimizer/validation_gate.py`` so it can be
imported without ``torch`` (an optional dependency). These tests mirror the
``test_cli_train_rating_nn_*`` pattern in ``test_phase10.py``: they verify
that the gate is fail-closed by default, that ``--force`` overrides, that
validation pass lets training proceed, and that ``add_force_flag`` parses
correctly.

Background: ``scripts/optimize_ratings_gpu.py`` is the third training path
that produces candidate runs reviewed by ``model-admission`` (the other two
are ``scoutfootball train`` and ``scoutfootball train-rating-nn``, gated in
Round 17 and Round 19). Without this gate, a maintainer could silently
train an optimizer candidate on inconsistent data by using the GPU script
instead of the gated CLI commands.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_SCRIPT = REPO_ROOT / "scripts" / "optimizer" / "validation_gate.py"


def _load_gate_module():
    """Import ``scripts/optimizer/validation_gate.py`` as a module.

    Uses ``importlib.util.spec_from_file_location`` (same pattern as
    ``test_optimizer_console_output.py`` and ``test_check_frontend_manifest.py``)
    so we can test the gate without importing ``torch`` or the rest of the
    ``optimizer`` package.
    """
    spec = importlib.util.spec_from_file_location("optimizer_validation_gate", GATE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestAddForceFlag:
    def test_force_flag_defaults_to_false(self):
        """``add_force_flag`` must default ``--force`` to ``False`` (fail-closed)."""
        gate = _load_gate_module()
        parser = argparse.ArgumentParser()
        gate.add_force_flag(parser)
        args = parser.parse_args([])
        assert args.force is False

    def test_force_flag_parses_explicit_true(self):
        """Explicit ``--force`` must parse to ``True``."""
        gate = _load_gate_module()
        parser = argparse.ArgumentParser()
        gate.add_force_flag(parser)
        args = parser.parse_args(["--force"])
        assert args.force is True


class TestRunValidationGate:
    """Verify ``run_validation_gate`` mirrors the CLI gate semantics.

    The gate must:
    - Fail-closed (return ``should_proceed=False``) when validation fails
      and ``--force`` is not set.
    - Fail-open (return ``should_proceed=True`` with a warning) when
      validation fails but ``--force`` is set.
    - Proceed silently (return ``should_proceed=True, None``) when
      validation passes.
    - Fail-closed on import errors unless ``--force`` is set.
    """

    def _make_args(self, force: bool) -> argparse.Namespace:
        return argparse.Namespace(force=force)

    def test_gate_skips_training_when_validation_fails(self, monkeypatch, tmp_path):
        """Default (no ``--force``) must skip training when validation fails."""
        gate = _load_gate_module()
        from scoutfootball.evaluation.validation import ValidationCheckResult, ValidationReport

        failed_report = ValidationReport(
            checks=[ValidationCheckResult("fake_check", False, "fake failure")]
        )

        # Patch run_pre_training_validation on the validation module so the
        # lazy import inside run_validation_gate picks up the fake.
        from scoutfootball.evaluation import validation as validation_module

        monkeypatch.setattr(
            validation_module, "run_pre_training_validation", lambda *_a, **_kw: failed_report
        )

        args = self._make_args(force=False)
        should_proceed, msg = gate.run_validation_gate(args, tmp_path / "data")

        assert should_proceed is False
        assert msg is not None
        assert "Pre-training validation failed" in msg
        assert "--force" in msg

    def test_gate_force_flag_overrides_validation_failure(self, monkeypatch, tmp_path):
        """``--force`` must let training proceed despite validation failure."""
        gate = _load_gate_module()
        from scoutfootball.evaluation.validation import ValidationCheckResult, ValidationReport

        failed_report = ValidationReport(
            checks=[ValidationCheckResult("fake_check", False, "fake failure")]
        )

        from scoutfootball.evaluation import validation as validation_module

        monkeypatch.setattr(
            validation_module, "run_pre_training_validation", lambda *_a, **_kw: failed_report
        )

        args = self._make_args(force=True)
        should_proceed, msg = gate.run_validation_gate(args, tmp_path / "data")

        assert should_proceed is True
        assert msg is not None
        assert "WARNING" in msg
        assert "--force" in msg

    def test_gate_proceeds_silently_when_validation_passes(self, monkeypatch, tmp_path):
        """When validation passes, the gate must proceed with no message."""
        gate = _load_gate_module()
        from scoutfootball.evaluation.validation import ValidationCheckResult, ValidationReport

        passed_report = ValidationReport(
            checks=[ValidationCheckResult("fake_check", True, "ok")]
        )

        from scoutfootball.evaluation import validation as validation_module

        monkeypatch.setattr(
            validation_module, "run_pre_training_validation", lambda *_a, **_kw: passed_report
        )

        args = self._make_args(force=False)
        should_proceed, msg = gate.run_validation_gate(args, tmp_path / "data")

        assert should_proceed is True
        assert msg is None

    def test_gate_fail_closed_on_import_error_without_force(self, monkeypatch, tmp_path):
        """Import failure must fail-closed unless ``--force`` is set.

        This covers the GPU server deployment where only ``data/`` is copied
        without ``src/scoutfootball``. The gate must refuse to proceed
        silently rather than let training run ungated.

        Setting ``sys.modules[name] = None`` is the documented way to make
        ``import name`` raise ``ImportError`` (PEP 328 / CPython import
        semantics), which lets us simulate the missing-package case without
        patching ``builtins.__import__``.
        """
        gate = _load_gate_module()

        monkeypatch.setitem(sys.modules, "scoutfootball.config", None)

        args = self._make_args(force=False)
        should_proceed, msg = gate.run_validation_gate(args, tmp_path / "data")

        assert should_proceed is False
        assert msg is not None
        assert "ERROR" in msg
        assert "cannot import scoutfootball validation module" in msg

    def test_gate_force_overrides_import_error(self, monkeypatch, tmp_path):
        """``--force`` must let training proceed even when validation can't import.

        This is the escape hatch for the GPU server case where the maintainer
        explicitly accepts the risk of training without the gate.
        """
        gate = _load_gate_module()

        monkeypatch.setitem(sys.modules, "scoutfootball.config", None)

        args = self._make_args(force=True)
        should_proceed, msg = gate.run_validation_gate(args, tmp_path / "data")

        assert should_proceed is True
        assert msg is not None
        assert "WARNING" in msg
        assert "--force" in msg

    def test_gate_restores_data_root_env_var(self, monkeypatch, tmp_path):
        """The gate must restore ``SCOUTFOOTBALL_DATA_ROOT`` after running.

        The gate sets the env var so ``PlatformSettings.from_root`` resolves
        to the user-supplied ``--data_dir``. If it leaks, downstream code
        that reads the env var would see a stale value. This test verifies
        save/restore behavior for both the "env var was unset" and "env var
        was set" cases.
        """
        import os

        gate = _load_gate_module()
        from scoutfootball.evaluation.validation import ValidationCheckResult, ValidationReport

        passed_report = ValidationReport(
            checks=[ValidationCheckResult("fake_check", True, "ok")]
        )

        from scoutfootball.evaluation import validation as validation_module

        monkeypatch.setattr(
            validation_module, "run_pre_training_validation", lambda *_a, **_kw: passed_report
        )

        # Case 1: env var was unset before the gate ran.
        monkeypatch.delenv("SCOUTFOOTBALL_DATA_ROOT", raising=False)
        args = self._make_args(force=False)
        gate.run_validation_gate(args, tmp_path / "data")
        assert "SCOUTFOOTBALL_DATA_ROOT" not in os.environ

        # Case 2: env var was set before the gate ran.
        monkeypatch.setenv("SCOUTFOOTBALL_DATA_ROOT", "/pre/existing/value")
        gate.run_validation_gate(args, tmp_path / "data")
        assert os.environ.get("SCOUTFOOTBALL_DATA_ROOT") == "/pre/existing/value"


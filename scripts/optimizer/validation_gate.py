"""Pre-training validation gate for the GPU optimizer script.

Extracted into a separate module so it can be unit-tested without importing
``torch`` (which is an optional dependency only available in the optimizer
environment). The gate mirrors the fail-closed behavior of the
``scoutfootball train`` and ``scoutfootball train-rating-nn`` CLI commands
(Round 17 and Round 19 fixes): by default it runs
``run_pre_training_validation`` and skips training when validation fails;
``--force`` is the explicit escape hatch for debugging or for training on
known-incomplete data at the maintainer's risk.

Without this gate, ``scripts/optimize_ratings_gpu.py`` would be a third
parallel training path that produces the same kind of candidate runs
(``data/models/runs/<timestamp>/``) reviewed by ``model-admission``, but
without any of the 31 pre-training validation checks that the other two
paths now enforce. A maintainer could silently train an optimizer candidate
on inconsistent data (NaN goals, stale manifests, broken source_lineage,
duplicate keys, negative metrics, corrupted truth labels) by using the GPU
optimizer instead of the gated CLI commands.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def add_force_flag(parser: argparse.ArgumentParser) -> None:
    """Add the ``--force`` flag to ``parser``.

    Default is ``False`` (fail-closed). The flag is the supported escape
    hatch for debugging or for training on known-incomplete data at the
    maintainer's risk, mirroring ``train --force`` and
    ``train-rating-nn --force``.
    """
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Skip pre-training validation gate (at your own risk)",
    )


def run_validation_gate(args: argparse.Namespace, data_dir: Path) -> tuple[bool, str | None]:
    """Run the pre-training validation gate before optimizer training.

    Returns ``(should_proceed, message)``:

    - ``(True, None)`` — validation passed; training should proceed.
    - ``(True, msg)`` — validation failed or unavailable, but ``--force``
      was used; ``msg`` is a warning string that should be printed before
      training proceeds.
    - ``(False, msg)`` — validation failed and ``--force`` was not used;
      ``msg`` is an error string that should be printed before the script
      exits without training.

    The gate is fail-closed on import errors too: if the
    ``scoutfootball`` package cannot be imported (e.g., the script is run
    on a GPU server where only ``data/`` was copied without ``src/``),
    the gate refuses to proceed unless ``--force`` is used. This prevents
    a silent ungated training run when the validation module is missing.
    """
    try:
        from scoutfootball.config import PlatformSettings
        from scoutfootball.evaluation.validation import run_pre_training_validation
    except ImportError as exc:
        if args.force:
            return True, (
                f"WARNING: cannot import scoutfootball validation module ({exc}); "
                "--force used, proceeding without pre-training validation gate."
            )
        return False, (
            f"ERROR: cannot import scoutfootball validation module ({exc}). "
            "Ensure src/scoutfootball is in PYTHONPATH (or run from the repo root "
            "with PYTHONPATH=src), or pass --force to bypass at your own risk."
        )

    # PlatformSettings.from_root uses SCOUTFOOTBALL_DATA_ROOT if set, otherwise
    # derives data_root as project_root / "data". We set the env var so the
    # gate works for non-standard --data_dir paths too, and restore the old
    # value afterwards to avoid leaking state into the training run.
    old_data_root = os.environ.get("SCOUTFOOTBALL_DATA_ROOT")
    try:
        os.environ["SCOUTFOOTBALL_DATA_ROOT"] = str(data_dir)
        settings = PlatformSettings.from_root(data_dir.parent)
        report = run_pre_training_validation(settings)
    finally:
        if old_data_root is None:
            os.environ.pop("SCOUTFOOTBALL_DATA_ROOT", None)
        else:
            os.environ["SCOUTFOOTBALL_DATA_ROOT"] = old_data_root

    if report.passed:
        return True, None

    summary = report.summary()
    if args.force:
        return True, (
            f"WARNING: pre-training validation failed, but --force used; "
            f"proceeding anyway.\n{summary}"
        )
    return False, (
        f"Pre-training validation failed.\n{summary}\n"
        "Run `scoutfootball validate` for details.\n"
        "To train anyway, pass --force (at your own risk)."
    )

"""Regression coverage for optimizer progress output on legacy consoles."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def test_console_progress_bar_is_gbk_safe(capsys) -> None:
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "optimizer_viz", root / "scripts/optimizer/viz.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    live = module.LiveTrainingViz(n_steps=1, pop_size=1, enable=False)
    live._print_progress(step=1, loss=0.1, spearman=0.2, pearson=0.3)
    console = module.ConsoleViz(n_steps=10, pop_size=1, enable=False)
    console.update(step=10, pop_idx=0, loss=0.1, spearman=0.2, pearson=0.3)

    capsys.readouterr().out.encode("gbk")

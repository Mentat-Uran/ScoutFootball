from __future__ import annotations

import sys
from types import SimpleNamespace

import pandas as pd

from scoutfootball.evaluation import optimizer_preflight as preflight


def test_preflight_reports_missing_required_inputs(tmp_path) -> None:
    report = preflight.optimizer_preflight(tmp_path)

    assert report["schema"] == "scoutfootball.optimizer-preflight"
    assert not report["ready"]
    assert report["install_hint"] == "uv sync --extra optimizer"
    assert all(item["status"] == "missing" for item in report["artifacts"])


def test_preflight_reports_readable_sources_and_torch(monkeypatch, tmp_path) -> None:
    for path in (*preflight.REQUIRED_ARTIFACTS.values(), *preflight.OPTIONAL_ARTIFACTS.values()):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fixture")

    monkeypatch.setattr(preflight.pd, "read_parquet", lambda _path: pd.DataFrame({"x": [1, 2]}))
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(__version__="2.5.0", cuda=SimpleNamespace(is_available=lambda: False)),
    )

    report = preflight.optimizer_preflight(tmp_path)

    assert report["ready"]
    assert report["runtime"]["torch"] == {"status": "available", "version": "2.5.0", "cuda": False}
    assert {item["status"] for item in report["artifacts"]} == {"readable"}
    assert {item["rows"] for item in report["artifacts"]} == {2}

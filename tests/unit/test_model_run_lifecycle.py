"""Safety coverage for local optimizer candidate discard actions."""

from __future__ import annotations

import json

import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.model_run_lifecycle import (
    ModelRunLifecycleError,
    discard_optimizer_run,
    inspect_optimizer_run_discard,
)


def _candidate(root, run_id: str, *, activation: str | None = "not_activated"):
    directory = root / "data" / "models" / "runs" / run_id
    directory.mkdir(parents=True)
    (directory / "optimized_params.npy").write_bytes(b"candidate")
    meta = {"activation": {"status": activation}} if activation is not None else {}
    (directory / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return directory


def test_discard_dry_run_keeps_unactivated_candidate(tmp_path) -> None:
    directory = _candidate(tmp_path, "candidate")

    report = discard_optimizer_run(
        PlatformSettings.from_root(tmp_path), "candidate", confirm=False
    )

    assert report["discardable"] is True
    assert report["deleted"] is False
    assert directory.exists()


def test_discard_confirm_removes_unactivated_candidate(tmp_path) -> None:
    directory = _candidate(tmp_path, "candidate")

    report = discard_optimizer_run(
        PlatformSettings.from_root(tmp_path), "candidate", confirm=True
    )

    assert report["deleted"] is True
    assert not directory.exists()


def test_discard_rejects_legacy_or_activated_run(tmp_path) -> None:
    directory = _candidate(tmp_path, "legacy", activation=None)

    with pytest.raises(ModelRunLifecycleError, match="lacks explicit not_activated"):
        discard_optimizer_run(PlatformSettings.from_root(tmp_path), "legacy", confirm=True)

    assert directory.exists()


def test_discard_incomplete_candidate_requires_opt_in(tmp_path) -> None:
    directory = tmp_path / "data" / "models" / "runs" / "interrupted"
    directory.mkdir(parents=True)
    (directory / "optimized_params.npy").write_bytes(b"partial")
    settings = PlatformSettings.from_root(tmp_path)

    report = inspect_optimizer_run_discard(settings, "interrupted")
    assert report["discardable"] is False
    with pytest.raises(ModelRunLifecycleError, match="requires --allow-incomplete"):
        discard_optimizer_run(settings, "interrupted", confirm=True)

    discarded = discard_optimizer_run(
        settings, "interrupted", confirm=True, allow_incomplete=True
    )
    assert discarded["deleted"] is True
    assert not directory.exists()


def test_discard_rejects_path_traversal(tmp_path) -> None:
    with pytest.raises(ModelRunLifecycleError, match="single candidate directory name"):
        inspect_optimizer_run_discard(PlatformSettings.from_root(tmp_path), "../outside")

"""Safety coverage for local optimizer candidate discard actions."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.model_run_lifecycle import (
    ModelRunLifecycleError,
    discard_optimizer_run,
    inspect_optimizer_run_discard,
    promote_optimizer_run,
    reject_optimizer_run,
    rollback_optimizer_run,
)


def _candidate(root, run_id: str, *, activation: str | None = "not_activated"):
    directory = root / "data" / "models" / "runs" / run_id
    directory.mkdir(parents=True)
    (directory / "optimized_params.npy").write_bytes(b"candidate")
    meta = {"activation": {"status": activation}} if activation is not None else {}
    (directory / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return directory


def _ratings(score_offset: float = 0.0) -> pd.DataFrame:
    scores = [10.0 + score_offset, 20.0 + score_offset]
    return pd.DataFrame(
        {
            "player": ["A", "B"],
            "team": ["Team A", "Team B"],
            "league": ["League", "League"],
            "season": ["2526", "2526"],
            "sub_position": ["ST", "ST"],
            "minutes": [1000.0, 1200.0],
            "optimized_score": scores,
            "same_position_score": [50.0, 100.0],
        }
    )


def _write_active(root, *, score_offset: float = 0.0) -> None:
    store = root / "data" / "gold" / "feature_store"
    store.mkdir(parents=True)
    _ratings(score_offset).to_parquet(store / "player_ratings_optimized.parquet", index=False)
    np.save(store / "optimized_params.npy", np.array([1.0, 2.0], dtype=np.float32))
    (store / "optimized_params_meta.json").write_text(
        json.dumps({"timestamp": "old", "holdout": {"optimized_test": {"spearman": 0.5}}}),
        encoding="utf-8",
    )


def _write_reviewable_candidate(root, run_id: str, *, score_offset: float = 100.0):
    directory = root / "data" / "models" / "runs" / run_id
    directory.mkdir(parents=True)
    ratings = _ratings(score_offset)
    ratings_path = directory / "player_ratings_candidate.parquet"
    ratings.to_parquet(ratings_path, index=False)
    np.save(directory / "optimized_params.npy", np.array([3.0, 4.0], dtype=np.float32))
    meta = {
        "run_id": run_id,
        "timestamp": run_id,
        "lineage": {
            "status": "recorded",
            "dataset_snapshot": {"input_hash": "input"},
            "feature_manifest": {"hash": "manifest"},
        },
        "train_seasons": ["2324"],
        "test_seasons": ["2425"],
        "metrics": {
            "baseline_train": {"spearman": 0.55},
            "baseline_test": {"spearman": 0.5, "pearson": 0.5},
            "optimized_train": {"spearman": 0.65},
            "optimized_test": {"spearman": 0.6, "pearson": 0.6},
        },
        "error_cases": {"over_estimated": [{"team": "A"}]},
        "data_coverage": {
            "artifact_statuses": [
                {"source": "fbref_standard", "status": "loaded"},
                {"source": "football_data_results", "status": "loaded"},
            ]
        },
        "candidate_artifacts": {
            "ratings": {
                "path": ratings_path.name,
                "sha256": hashlib.sha256(ratings_path.read_bytes()).hexdigest(),
                "rows": len(ratings),
                "columns": list(ratings.columns),
                "scope": "unactivated_local_candidate",
            }
        },
        "activation": {"status": "not_activated"},
    }
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


def test_rejection_is_a_confirmed_metadata_action_that_keeps_candidate(tmp_path) -> None:
    directory = _write_reviewable_candidate(tmp_path, "candidate")
    settings = PlatformSettings.from_root(tmp_path)

    preview = reject_optimizer_run(settings, "candidate", decision="holdout slices need review")
    assert preview["rejected"] is False
    assert json.loads((directory / "meta.json").read_text(encoding="utf-8"))["activation"][
        "status"
    ] == "not_activated"

    result = reject_optimizer_run(
        settings, "candidate", decision="holdout slices need review", confirm=True
    )
    assert result["rejected"] is True
    assert directory.exists()
    assert json.loads((directory / "meta.json").read_text(encoding="utf-8"))["activation"][
        "status"
    ] == "rejected"


def test_promotion_previews_without_touching_active_artifacts(tmp_path) -> None:
    _write_active(tmp_path)
    _write_reviewable_candidate(tmp_path, "candidate")
    settings = PlatformSettings.from_root(tmp_path)
    ratings_path = tmp_path / "data" / "gold" / "feature_store" / "player_ratings_optimized.parquet"
    before = hashlib.sha256(ratings_path.read_bytes()).hexdigest()

    report = promote_optimizer_run(settings, "candidate", decision="review accepted")

    assert report["promoted"] is False
    assert hashlib.sha256(ratings_path.read_bytes()).hexdigest() == before
    assert not (tmp_path / "data" / "models" / "backups").exists()


def test_promotion_creates_verified_backup_and_rollback_restores_active_artifacts(tmp_path) -> None:
    _write_active(tmp_path)
    candidate = _write_reviewable_candidate(tmp_path, "candidate")
    settings = PlatformSettings.from_root(tmp_path)
    store = tmp_path / "data" / "gold" / "feature_store"
    original_ratings = (store / "player_ratings_optimized.parquet").read_bytes()
    original_params = (store / "optimized_params.npy").read_bytes()
    original_meta = (store / "optimized_params_meta.json").read_bytes()

    promoted = promote_optimizer_run(
        settings, "candidate", decision="reviewed local candidate", confirm=True
    )

    assert promoted["promoted"] is True
    backup_id = promoted["backup_id"]
    promoted_scores = pd.read_parquet(store / "player_ratings_optimized.parquet")[
        "optimized_score"
    ].tolist()
    assert promoted_scores == [110.0, 120.0]
    active_meta = json.loads((store / "optimized_params_meta.json").read_text(encoding="utf-8"))
    assert active_meta["active_model"]["run_id"] == "candidate"
    assert active_meta["holdout"]["optimized_test"]["spearman"] == 0.6
    assert json.loads((candidate / "meta.json").read_text(encoding="utf-8"))["activation"][
        "status"
    ] == "activated"
    manifest = json.loads(
        (tmp_path / "data" / "models" / "backups" / backup_id / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["promoted_run_id"] == "candidate"

    rolled_back = rollback_optimizer_run(
        settings, backup_id, decision="candidate calibration rejected", confirm=True
    )

    assert rolled_back["rolled_back"] is True
    assert (store / "player_ratings_optimized.parquet").read_bytes() == original_ratings
    assert (store / "optimized_params.npy").read_bytes() == original_params
    assert (store / "optimized_params_meta.json").read_bytes() == original_meta
    assert json.loads((candidate / "meta.json").read_text(encoding="utf-8"))["activation"][
        "status"
    ] == "rolled_back"
    assert (tmp_path / "data" / "models" / "backups" / backup_id / "rollback.json").exists()


def test_promotion_fails_closed_when_candidate_artifact_hash_changes(tmp_path) -> None:
    _write_active(tmp_path)
    candidate = _write_reviewable_candidate(tmp_path, "candidate")
    ratings_path = candidate / "player_ratings_candidate.parquet"
    ratings_path.write_bytes(ratings_path.read_bytes() + b"tampered")

    with pytest.raises(ModelRunLifecycleError, match="candidate_rating_artifact"):
        promote_optimizer_run(
            PlatformSettings.from_root(tmp_path),
            "candidate",
            decision="review accepted",
            confirm=True,
        )

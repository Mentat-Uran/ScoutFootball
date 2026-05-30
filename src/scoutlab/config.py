"""Project-level settings and path resolution."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class PlatformSettings(BaseModel):
    """Resolved project paths for local development."""

    model_config = ConfigDict(frozen=True)

    project_root: Path
    source_root: Path
    test_root: Path
    data_root: Path
    raw_root: Path
    silver_root: Path
    gold_root: Path
    model_root: Path
    report_root: Path
    log_root: Path

    @classmethod
    def from_root(cls, root: Path | None = None) -> PlatformSettings:
        project_root = (root or Path(__file__).resolve().parents[2]).resolve()
        data_root = project_root / "data"
        return cls(
            project_root=project_root,
            source_root=project_root / "src",
            test_root=project_root / "tests",
            data_root=data_root,
            raw_root=data_root / "raw",
            silver_root=data_root / "silver",
            gold_root=data_root / "gold",
            model_root=data_root / "models",
            report_root=data_root / "reports",
            log_root=data_root / "logs",
        )

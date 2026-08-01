"""Filesystem layout helpers for the local lakehouse scaffold."""

from __future__ import annotations

from pathlib import Path

from scoutfootball.architecture import build_default_architecture
from scoutfootball.config import PlatformSettings


def collect_required_directories(
    settings: PlatformSettings | None = None,
) -> tuple[Path, ...]:
    resolved_settings = settings or PlatformSettings.from_root()
    architecture = build_default_architecture()
    return tuple(
        resolved_settings.data_root / spec.relative_path for spec in architecture.data_directories
    )

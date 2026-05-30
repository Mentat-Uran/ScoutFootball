"""Architecture schema definitions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModuleBoundary(BaseModel):
    """Describes one source-code module boundary."""

    model_config = ConfigDict(frozen=True)

    name: str
    purpose: str
    planned_components: tuple[str, ...] = ()


class DataDirectorySpec(BaseModel):
    """Describes one persistent storage directory."""

    model_config = ConfigDict(frozen=True)

    layer: str
    relative_path: str
    purpose: str


class ProjectArchitecture(BaseModel):
    """Top-level architecture manifest for the scaffold."""

    model_config = ConfigDict(frozen=True)

    package_name: str
    status: str
    module_boundaries: tuple[ModuleBoundary, ...]
    data_directories: tuple[DataDirectorySpec, ...]
    supported_commands: tuple[str, ...] = Field(default_factory=tuple)

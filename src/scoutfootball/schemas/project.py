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
    source_name: str = ""
    license_name: str = ""
    recorded: bool = True
    recorded_note: str = ""


class Capability(BaseModel):
    """A single discoverable capability of the package.

    Each capability has a unique id, a human-readable name and
    description, a status flag, and entry points across the API, CLI,
    and frontend. Capabilities are grouped by domain so related features
    can be discovered together.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str
    domain: str
    status: str = "delivered"
    api_paths: tuple[str, ...] = ()
    cli_commands: tuple[str, ...] = ()
    frontend_views: tuple[str, ...] = ()
    data_artifacts: tuple[str, ...] = ()
    notes: str = ""


class CapabilityRegistry(BaseModel):
    """Machine-readable index of all capabilities in the package.

    The registry is the single source of truth for "what can this
    project do". It is generated automatically from code (CLI
    subparsers, FastAPI routes, frontend navigation, static manifests)
    and consumed by docs, tests, and the info command.
    """

    model_config = ConfigDict(frozen=True)

    generated_at: str
    package_version: str = ""
    domains: tuple[str, ...] = ()
    capabilities: tuple[Capability, ...] = ()

    def by_domain(self, domain: str) -> tuple[Capability, ...]:
        return tuple(c for c in self.capabilities if c.domain == domain)

    def count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.capabilities:
            counts[c.status] = counts.get(c.status, 0) + 1
        return counts


class ProjectArchitecture(BaseModel):
    """Top-level architecture manifest for the scaffold."""

    model_config = ConfigDict(frozen=True)

    package_name: str
    status: str
    module_boundaries: tuple[ModuleBoundary, ...]
    data_directories: tuple[DataDirectorySpec, ...]
    supported_commands: tuple[str, ...] = Field(default_factory=tuple)

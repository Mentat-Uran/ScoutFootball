"""Schema models for project structure, storage metadata, and match/event/tracking."""

from .match import (
    InternalEvent,
    InternalLineup,
    InternalMatch,
    MatchStatus,
    PeriodType,
    TrackingFrame,
)
from .project import (
    Capability,
    CapabilityRegistry,
    DataDirectorySpec,
    ModuleBoundary,
    ProjectArchitecture,
)
from .storage import (
    ColumnDefinition,
    IngestMetadata,
    SourceRequestLogEntry,
    TableDefinition,
    build_core_table_definitions,
)

__all__ = [
    "Capability",
    "CapabilityRegistry",
    "ColumnDefinition",
    "DataDirectorySpec",
    "IngestMetadata",
    "InternalEvent",
    "InternalLineup",
    "InternalMatch",
    "MatchStatus",
    "ModuleBoundary",
    "PeriodType",
    "ProjectArchitecture",
    "SourceRequestLogEntry",
    "TableDefinition",
    "TrackingFrame",
    "build_core_table_definitions",
]

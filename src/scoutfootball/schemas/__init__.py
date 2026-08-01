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
    CoverageInfo,
    DataContract,
    DataContractRegistry,
    IngestMetadata,
    LineageEntry,
    SnapshotInfo,
    SourceLicense,
    SourceRequestLogEntry,
    TableDefinition,
    build_core_table_definitions,
)

__all__ = [
    "Capability",
    "CapabilityRegistry",
    "ColumnDefinition",
    "CoverageInfo",
    "DataContract",
    "DataContractRegistry",
    "DataDirectorySpec",
    "IngestMetadata",
    "InternalEvent",
    "InternalLineup",
    "InternalMatch",
    "LineageEntry",
    "MatchStatus",
    "ModuleBoundary",
    "PeriodType",
    "ProjectArchitecture",
    "SnapshotInfo",
    "SourceLicense",
    "SourceRequestLogEntry",
    "TableDefinition",
    "TrackingFrame",
    "build_core_table_definitions",
]

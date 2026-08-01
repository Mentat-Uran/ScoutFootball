"""Shared adapter result types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scoutfootball.schemas import SourceRequestLogEntry


@dataclass(frozen=True)
class SourceMetadata:
    """Metadata emitted by one adapter fetch or load operation."""

    source_name: str
    source_uri: str
    cache_path: Path
    parser_version: str
    source_file_sha256: str
    request_log: SourceRequestLogEntry
    record_count: int


@dataclass(frozen=True)
class AdapterResult:
    """Tabular adapter output paired with source metadata."""

    dataframe: pd.DataFrame
    metadata: SourceMetadata

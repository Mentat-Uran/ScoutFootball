"""Features package for reusable analytical tables."""

from .manifest import (
    MANIFEST_SCHEMA_VERSION,
    PLAYER_MATCH_COLUMN_SOURCES,
    PLAYER_ROLLING_COLUMN_SOURCES,
    TEAM_MATCH_COLUMN_SOURCES,
    TEAM_ROLLING_COLUMN_SOURCES,
    SourceLineageEntry,
    count_parquet_rows,
    extract_lineage_attrs,
    hash_file,
    relative_to_data_root,
    write_player_match_manifest,
    write_player_rolling_manifest,
    write_team_match_manifest,
    write_team_rolling_manifest,
)
from .player_match import build_player_match_features
from .player_rolling import build_player_rolling_features
from .rating_matrix import (
    RATING_MATRIX_COLUMN_SOURCES,
    build_rating_feature_matrix,
    fill_missing_with_position_median,
    mark_missing_fields,
    write_feature_manifest,
)
from .team_match import build_team_match_features
from .team_rolling import build_team_rolling_features
from .understat_history import build_understat_season_proxy

__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "PLAYER_MATCH_COLUMN_SOURCES",
    "PLAYER_ROLLING_COLUMN_SOURCES",
    "RATING_MATRIX_COLUMN_SOURCES",
    "SourceLineageEntry",
    "TEAM_MATCH_COLUMN_SOURCES",
    "TEAM_ROLLING_COLUMN_SOURCES",
    "build_player_match_features",
    "build_player_rolling_features",
    "build_rating_feature_matrix",
    "build_team_match_features",
    "build_team_rolling_features",
    "build_understat_season_proxy",
    "count_parquet_rows",
    "extract_lineage_attrs",
    "fill_missing_with_position_median",
    "hash_file",
    "mark_missing_fields",
    "relative_to_data_root",
    "write_feature_manifest",
    "write_player_match_manifest",
    "write_player_rolling_manifest",
    "write_team_match_manifest",
    "write_team_rolling_manifest",
]

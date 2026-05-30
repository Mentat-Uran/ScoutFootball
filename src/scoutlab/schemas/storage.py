"""Storage metadata and core table drafts for the first Phase 2 slice."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ColumnDefinition(BaseModel):
    """Describes one table column in the local analytical lakehouse."""

    model_config = ConfigDict(frozen=True)

    name: str
    dtype: str
    nullable: bool = True
    description: str = ""


class TableDefinition(BaseModel):
    """Draft schema contract for one persisted table."""

    model_config = ConfigDict(frozen=True)

    name: str
    layer: str
    purpose: str
    primary_keys: tuple[str, ...] = Field(default_factory=tuple)
    columns: tuple[ColumnDefinition, ...] = Field(default_factory=tuple)

    def validate_columns(self, columns: Iterable[str]) -> None:
        """Raise when required columns are missing from a candidate frame."""

        observed = set(columns)
        missing = tuple(column.name for column in self.columns if column.name not in observed)
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"{self.name} is missing required columns: {missing_text}")


class SourceRequestLogEntry(BaseModel):
    """Structured request log for one external source access."""

    model_config = ConfigDict(frozen=True)

    source_name: str
    source_uri: str
    requested_at: datetime
    parser_version: str
    response_sha256: str = Field(min_length=64, max_length=64)
    cache_hit: bool = False
    status_code: int | None = Field(default=None, ge=100, le=599)


class IngestMetadata(BaseModel):
    """Metadata persisted for every dataset write."""

    model_config = ConfigDict(frozen=True)

    source_name: str
    dataset_name: str
    layer: str
    source_uri: str
    ingested_at: datetime
    parser_version: str
    source_file_sha256: str = Field(min_length=64, max_length=64)
    primary_keys: tuple[str, ...] = Field(default_factory=tuple)
    source_record_count: int = Field(ge=0)
    request_log: SourceRequestLogEntry | None = None


def _column(
    name: str,
    dtype: str,
    *,
    nullable: bool = True,
    description: str = "",
) -> ColumnDefinition:
    return ColumnDefinition(
        name=name,
        dtype=dtype,
        nullable=nullable,
        description=description,
    )


def build_core_table_definitions() -> tuple[TableDefinition, ...]:
    """Return the draft core schemas promised by Phase 2."""

    return (
        TableDefinition(
            name="competition",
            layer="silver",
            purpose="Canonical competition dimension shared across sources.",
            primary_keys=("competition_id",),
            columns=(
                _column("competition_id", "string", nullable=False),
                _column("competition_name", "string", nullable=False),
                _column("country_name", "string"),
                _column("competition_gender", "string"),
                _column("source_name", "string", nullable=False),
            ),
        ),
        TableDefinition(
            name="season",
            layer="silver",
            purpose="Canonical season dimension keyed independently from source IDs.",
            primary_keys=("season_id",),
            columns=(
                _column("season_id", "string", nullable=False),
                _column("competition_id", "string", nullable=False),
                _column("season_name", "string", nullable=False),
                _column("start_date", "date"),
                _column("end_date", "date"),
            ),
        ),
        TableDefinition(
            name="team",
            layer="silver",
            purpose="Canonical team dimension for cross-source joins.",
            primary_keys=("team_id",),
            columns=(
                _column("team_id", "string", nullable=False),
                _column("team_name", "string", nullable=False),
                _column("normalized_name", "string", nullable=False),
                _column("country_name", "string"),
                _column("gender", "string"),
            ),
        ),
        TableDefinition(
            name="player",
            layer="silver",
            purpose="Canonical player dimension for cross-source joins.",
            primary_keys=("player_id",),
            columns=(
                _column("player_id", "string", nullable=False),
                _column("player_name", "string", nullable=False),
                _column("normalized_name", "string", nullable=False),
                _column("date_of_birth", "date"),
                _column("nationality", "string"),
                _column("primary_position_group", "string"),
            ),
        ),
        TableDefinition(
            name="match",
            layer="silver",
            purpose="Canonical match fact without source-specific primary keys.",
            primary_keys=("match_id",),
            columns=(
                _column("match_id", "string", nullable=False),
                _column("competition_id", "string", nullable=False),
                _column("season_id", "string", nullable=False),
                _column("match_date", "timestamp", nullable=False),
                _column("home_team_id", "string", nullable=False),
                _column("away_team_id", "string", nullable=False),
                _column("home_goals", "integer"),
                _column("away_goals", "integer"),
            ),
        ),
        TableDefinition(
            name="team_match",
            layer="silver",
            purpose="Team-level match facts used for rolling features and probability models.",
            primary_keys=("match_id", "team_id"),
            columns=(
                _column("match_id", "string", nullable=False),
                _column("team_id", "string", nullable=False),
                _column("opponent_team_id", "string", nullable=False),
                _column("is_home", "boolean", nullable=False),
                _column("goals_for", "integer"),
                _column("goals_against", "integer"),
                _column("result_points", "integer"),
            ),
        ),
        TableDefinition(
            name="player_match",
            layer="silver",
            purpose="Player-level appearance facts used for rolling features.",
            primary_keys=("match_id", "player_id"),
            columns=(
                _column("match_id", "string", nullable=False),
                _column("player_id", "string", nullable=False),
                _column("team_id", "string", nullable=False),
                _column("minutes_played", "integer"),
                _column("goals", "integer"),
                _column("assists", "integer"),
                _column("position_group", "string"),
            ),
        ),
        TableDefinition(
            name="event",
            layer="silver",
            purpose="Event-level actions primarily sourced from StatsBomb Open Data.",
            primary_keys=("match_id", "event_id"),
            columns=(
                _column("match_id", "string", nullable=False),
                _column("event_id", "string", nullable=False),
                _column("period", "integer", nullable=False),
                _column("minute", "integer", nullable=False),
                _column("second", "integer", nullable=False),
                _column("team_id", "string"),
                _column("player_id", "string"),
                _column("event_type", "string", nullable=False),
            ),
        ),
        TableDefinition(
            name="bridge_source_team",
            layer="silver",
            purpose="Cross-source team identifier bridge with review metadata.",
            primary_keys=("source_name", "source_team_id"),
            columns=(
                _column("source_name", "string", nullable=False),
                _column("source_team_id", "string", nullable=False),
                _column("team_id", "string", nullable=False),
                _column("method", "string", nullable=False),
                _column("score", "double"),
                _column("approved_by", "string"),
                _column("approved_at", "timestamp"),
            ),
        ),
        TableDefinition(
            name="bridge_source_player",
            layer="silver",
            purpose="Cross-source player identifier bridge with review metadata.",
            primary_keys=("source_name", "source_player_id"),
            columns=(
                _column("source_name", "string", nullable=False),
                _column("source_player_id", "string", nullable=False),
                _column("player_id", "string", nullable=False),
                _column("method", "string", nullable=False),
                _column("score", "double"),
                _column("approved_by", "string"),
                _column("approved_at", "timestamp"),
            ),
        ),
        TableDefinition(
            name="market_snapshot",
            layer="silver",
            purpose="Manually imported or authorized market-value and contract snapshots.",
            primary_keys=("player_id", "snapshot_date"),
            columns=(
                _column("player_id", "string", nullable=False),
                _column("snapshot_date", "date", nullable=False),
                _column("market_value", "double"),
                _column("contract_end", "date"),
                _column("data_source", "string", nullable=False),
                _column("import_method", "string", nullable=False),
            ),
        ),
    )

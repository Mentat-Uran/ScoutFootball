import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from scoutlab.schemas import (
    IngestMetadata,
    SourceRequestLogEntry,
    build_core_table_definitions,
)
from scoutlab.storage import (
    append_source_request_log,
    connect_duckdb,
    metadata_path_for_dataset,
    query_parquet,
    write_parquet_dataset,
)


def test_write_parquet_dataset_is_idempotent_and_queryable(tmp_path: Path) -> None:
    dataset_path = tmp_path / "silver" / "team_match.parquet"
    table_definition = next(
        table for table in build_core_table_definitions() if table.name == "team_match"
    )
    metadata = IngestMetadata(
        source_name="statsbomb_open",
        dataset_name="team_match",
        layer="silver",
        source_uri="file:///tmp/statsbomb-open/sample.json",
        ingested_at=datetime(2026, 5, 31, 12, 0, tzinfo=UTC),
        parser_version="phase2-test",
        source_file_sha256="a" * 64,
        primary_keys=("match_id", "team_id"),
        source_record_count=2,
        request_log=SourceRequestLogEntry(
            source_name="statsbomb_open",
            source_uri="https://github.com/statsbomb/open-data",
            requested_at=datetime(2026, 5, 31, 11, 30, tzinfo=UTC),
            parser_version="phase2-test",
            response_sha256="b" * 64,
            cache_hit=True,
            status_code=200,
        ),
    )

    initial_frame = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "team_id": "t1",
                "opponent_team_id": "t2",
                "is_home": True,
                "goals_for": 2,
                "goals_against": 1,
                "result_points": 3,
            },
            {
                "match_id": "m2",
                "team_id": "t3",
                "opponent_team_id": "t4",
                "is_home": False,
                "goals_for": 1,
                "goals_against": 1,
                "result_points": 1,
            },
        ]
    )
    update_frame = pd.DataFrame(
        [
            {
                "match_id": "m2",
                "team_id": "t3",
                "opponent_team_id": "t4",
                "is_home": False,
                "goals_for": 3,
                "goals_against": 1,
                "result_points": 3,
            },
            {
                "match_id": "m3",
                "team_id": "t5",
                "opponent_team_id": "t6",
                "is_home": True,
                "goals_for": 0,
                "goals_against": 0,
                "result_points": 1,
            },
        ]
    )

    first_result = write_parquet_dataset(
        initial_frame,
        dataset_path,
        metadata=metadata,
        table_definition=table_definition,
    )
    second_result = write_parquet_dataset(
        update_frame,
        dataset_path,
        metadata=metadata.model_copy(update={"source_record_count": 2}),
        table_definition=table_definition,
    )

    assert first_result.output_row_count == 2
    assert second_result.output_row_count == 3
    assert second_result.deduplicated_rows == 1
    assert metadata_path_for_dataset(dataset_path) == second_result.metadata_path

    connection = connect_duckdb()
    queried = query_parquet(connection, dataset_path).sort_values(["match_id", "team_id"])

    assert queried["match_id"].tolist() == ["m1", "m2", "m3"]
    assert queried.loc[queried["match_id"] == "m2", "goals_for"].item() == 3

    metadata_payload = json.loads(second_result.metadata_path.read_text(encoding="utf-8"))
    assert metadata_payload["metadata"]["source_name"] == "statsbomb_open"
    assert metadata_payload["metadata"]["parser_version"] == "phase2-test"
    assert metadata_payload["metadata"]["source_file_sha256"] == "a" * 64
    assert metadata_payload["output_row_count"] == 3
    assert metadata_payload["deduplicated_rows"] == 1


def test_append_source_request_log_writes_jsonl(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "ingestion" / "source_request_log.jsonl"
    entry = SourceRequestLogEntry(
        source_name="football_data",
        source_uri="https://www.football-data.co.uk/data.php",
        requested_at=datetime(2026, 5, 31, 9, 0, tzinfo=UTC),
        parser_version="phase2-test",
        response_sha256="c" * 64,
        cache_hit=False,
        status_code=200,
    )

    append_source_request_log(log_path, entry)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["source_name"] == "football_data"

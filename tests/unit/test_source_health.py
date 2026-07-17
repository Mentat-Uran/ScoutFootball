from __future__ import annotations

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.source_health import build_source_health_report


def test_source_health_marks_local_observation_separately_from_snapshot(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    source_file = settings.data_root / "raw" / "football_data" / "results.csv"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("date,result\n", encoding="utf-8")
    (settings.data_root / "raw" / "unregistered_source").mkdir()

    report = build_source_health_report(settings)

    football_data = next(
        item for item in report["registered_sources"] if item["source_id"] == "football_data"
    )
    assert football_data["license"]["status"] == "recorded"
    assert football_data["local_observation"]["file_count"] == 1
    assert football_data["snapshot"]["status"] == "not_recorded"
    assert report["unregistered_raw_directories"] == ["unregistered_source"]

from pathlib import Path

from scoutfootball.config import PlatformSettings
from scoutfootball.storage import collect_required_directories


def test_collect_required_directories_stays_under_data_root(tmp_path: Path) -> None:
    settings = PlatformSettings.from_root(tmp_path)

    directories = collect_required_directories(settings)

    assert directories
    assert all(directory.is_relative_to(tmp_path / "data") for directory in directories)
    assert any(directory.name == "feature_store" for directory in directories)

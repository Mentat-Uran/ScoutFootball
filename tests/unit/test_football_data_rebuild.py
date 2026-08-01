"""Unit tests for Football-Data combined_results.parquet rebuild."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scoutfootball.adapters.football_data import LEAGUE_CODE_NAMES, rebuild_combined_results


def _write_csv(path: Path, rows: list[dict]) -> None:
    """Write a small CSV with the minimum required Football-Data columns."""
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def _e0_row(
    home: str, away: str, fthg: int = 1, ftag: int = 0, date: str = "01/01/2025",
) -> dict:
    return {
        "Div": "E0", "Date": date,
        "HomeTeam": home, "AwayTeam": away,
        "FTHG": fthg, "FTAG": ftag,
    }


def _sp1_row(
    home: str, away: str, fthg: int = 1, ftag: int = 0, date: str = "01/01/2025",
) -> dict:
    return {
        "Div": "SP1", "Date": date,
        "HomeTeam": home, "AwayTeam": away,
        "FTHG": fthg, "FTAG": ftag,
    }


def _d1_row(
    home: str, away: str, fthg: int = 1, ftag: int = 0, date: str = "01/01/2025",
) -> dict:
    return {
        "Div": "D1", "Date": date,
        "HomeTeam": home, "AwayTeam": away,
        "FTHG": fthg, "FTAG": ftag,
    }


@pytest.fixture()
def sample_data_dir(tmp_path: Path) -> Path:
    """Create a temp directory with sample Football-Data CSVs."""
    fd_dir = tmp_path / "football_data"
    fd_dir.mkdir()

    # Season 2425: E0 + SP1
    s1 = fd_dir / "2425"
    s1.mkdir()
    _write_csv(s1 / "E0.csv", [
        _e0_row("Arsenal", "Chelsea", 2, 1),
        _e0_row("Liverpool", "Man City", 1, 1, date="02/01/2025"),
    ])
    _write_csv(s1 / "SP1.csv", [
        _sp1_row("Barcelona", "Real Madrid", 3, 2),
    ])

    # Season 2526: E0 + D1
    s2 = fd_dir / "2526"
    s2.mkdir()
    _write_csv(s2 / "E0.csv", [
        _e0_row("Man United", "West Ham", 0, 0, date="01/08/2025"),
    ])
    _write_csv(s2 / "D1.csv", [
        _d1_row("Bayern Munich", "Dortmund", 4, 2, date="01/08/2025"),
    ])

    return fd_dir


class TestRebuildCombinedResults:
    def test_reads_all_csvs_from_season_dirs(self, sample_data_dir: Path) -> None:
        output = sample_data_dir / "combined_results.parquet"
        meta = rebuild_combined_results(sample_data_dir, output_path=output)

        assert meta["total_rows"] == 5
        assert meta["parquet_rows"] == 5

        df = pd.read_parquet(output)
        assert len(df) == 5

    def test_adds_league_and_season_columns(self, sample_data_dir: Path) -> None:
        output = sample_data_dir / "combined_results.parquet"
        rebuild_combined_results(sample_data_dir, output_path=output)

        df = pd.read_parquet(output)
        assert "league" in df.columns
        assert "season" in df.columns

        e0_rows = df[df["Div"] == "E0"]
        assert (e0_rows["league"] == "Premier League").all()

        sp1_rows = df[df["Div"] == "SP1"]
        assert (sp1_rows["league"] == "La Liga").all()

        d1_rows = df[df["Div"] == "D1"]
        assert (d1_rows["league"] == "Bundesliga").all()

    def test_league_season_coverage_reported(self, sample_data_dir: Path) -> None:
        output = sample_data_dir / "combined_results.parquet"
        meta = rebuild_combined_results(sample_data_dir, output_path=output)

        ls = meta["league_seasons"]
        assert isinstance(ls, list)
        assert "D1/2526" in ls
        assert "E0/2425" in ls
        assert "E0/2526" in ls
        assert "SP1/2425" in ls
        assert len(ls) == 4

    def test_input_hash_deterministic(self, sample_data_dir: Path) -> None:
        output = sample_data_dir / "combined_results.parquet"
        meta1 = rebuild_combined_results(sample_data_dir, output_path=output)
        meta2 = rebuild_combined_results(sample_data_dir, output_path=output)
        assert meta1["input_hash"] == meta2["input_hash"]

    def test_rebuild_time_is_iso_format(self, sample_data_dir: Path) -> None:
        output = sample_data_dir / "combined_results.parquet"
        meta = rebuild_combined_results(sample_data_dir, output_path=output)
        assert isinstance(meta["rebuild_time"], str)
        assert "T" in meta["rebuild_time"]

    def test_empty_dir_produces_empty_parquet(self, tmp_path: Path) -> None:
        fd_dir = tmp_path / "football_data"
        fd_dir.mkdir()
        output = fd_dir / "combined_results.parquet"
        meta = rebuild_combined_results(fd_dir, output_path=output)

        assert meta["total_rows"] == 0
        assert meta["parquet_rows"] == 0
        assert meta["league_seasons"] == []
        assert meta["input_hash"] == ""

    def test_skips_non_season_dirs(self, tmp_path: Path) -> None:
        fd_dir = tmp_path / "football_data"
        fd_dir.mkdir()
        other = fd_dir / "archive"
        other.mkdir()
        _write_csv(other / "E0.csv", [
            _e0_row("A", "B"),
        ])
        s = fd_dir / "2425"
        s.mkdir()
        _write_csv(s / "E0.csv", [
            _e0_row("C", "D", 2, 1),
        ])

        output = fd_dir / "combined_results.parquet"
        meta = rebuild_combined_results(fd_dir, output_path=output)
        assert meta["total_rows"] == 1
        assert meta["league_seasons"] == ["E0/2425"]

    def test_unknown_league_code_uses_code_as_name(self, tmp_path: Path) -> None:
        fd_dir = tmp_path / "football_data"
        fd_dir.mkdir()
        s = fd_dir / "2425"
        s.mkdir()
        row = {
            "Div": "XX9", "Date": "01/01/2025",
            "HomeTeam": "A", "AwayTeam": "B", "FTHG": 1, "FTAG": 0,
        }
        _write_csv(s / "XX9.csv", [row])

        output = fd_dir / "combined_results.parquet"
        rebuild_combined_results(fd_dir, output_path=output)
        df = pd.read_parquet(output)
        assert df.iloc[0]["league"] == "XX9"

    def test_default_output_path(self, sample_data_dir: Path) -> None:
        rebuild_combined_results(sample_data_dir)
        default_path = sample_data_dir / "combined_results.parquet"
        assert default_path.exists()
        df = pd.read_parquet(default_path)
        assert len(df) == 5

    def test_alias_patch_still_works_after_rebuild(self, sample_data_dir: Path) -> None:
        """Verify that the 2526 team-name alias mapping is preserved in raw data.

        The rebuild reads raw CSVs as-is; alias patching happens downstream
        in the pipeline. This test confirms the raw data retains the original
        Football-Data short names so downstream alias logic can map them.
        """
        output = sample_data_dir / "combined_results.parquet"
        rebuild_combined_results(sample_data_dir, output_path=output)

        df = pd.read_parquet(output)
        e0_2526 = df[(df["Div"] == "E0") & (df["season"] == "2526")]
        assert "Man United" in e0_2526["HomeTeam"].values
        assert "West Ham" in e0_2526["AwayTeam"].values

    def test_all_known_league_codes_in_mapping(self) -> None:
        """Ensure LEAGUE_CODE_NAMES covers all codes from the task spec."""
        expected_codes = [
            "E0", "E1", "E2", "E3", "EC",
            "SC0", "SC1", "SC2", "SC3",
            "D1", "D2",
            "I1", "I2",
            "SP1", "SP2",
            "F1", "F2",
            "N1", "B1", "P1", "T1", "G1",
        ]
        for code in expected_codes:
            assert code in LEAGUE_CODE_NAMES, f"Missing league code: {code}"

"""Unit tests for ``scoutfootball.evaluation.role_system`` (PRS-1 R-009 v1)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.role_system import (
    COARSE_POSITION_LABELS,
    POSITION_TO_ROLE,
    ROLE_SYSTEM_SCHEMA,
    ROLE_SYSTEM_VERSION,
    RoleFamily,
    build_role_system_report,
    classify_role_family,
)

# ---------------------------------------------------------------------------
# RoleFamily enum stability
# ---------------------------------------------------------------------------


class TestRoleFamilyEnum:
    def test_eight_families_plus_unknown(self) -> None:
        """v1 must expose exactly 8 role families + UNKNOWN sentinel."""
        expected = {"GK", "CB", "FB", "DM", "CM", "AM", "W", "ST", "UNKNOWN"}
        actual = {f.value for f in RoleFamily}
        assert actual == expected

    def test_enum_values_are_stable_strings(self) -> None:
        """Values must be stable strings for JSON/parquet serialisation."""
        for family in RoleFamily:
            assert isinstance(family.value, str)
            assert family.value == family.value.upper()  # all uppercase

    def test_unknown_is_sentinel_not_real_role(self) -> None:
        """UNKNOWN is the catch-all for missing/unmapped values."""
        assert RoleFamily.UNKNOWN.value == "UNKNOWN"
        assert RoleFamily.UNKNOWN != RoleFamily.CM


# ---------------------------------------------------------------------------
# classify_role_family
# ---------------------------------------------------------------------------


class TestClassifyRoleFamily:
    def test_none_returns_unknown(self) -> None:
        assert classify_role_family(None) == RoleFamily.UNKNOWN

    def test_nan_returns_unknown(self) -> None:
        assert classify_role_family(float("nan")) == RoleFamily.UNKNOWN

    def test_empty_string_returns_unknown(self) -> None:
        assert classify_role_family("") == RoleFamily.UNKNOWN

    def test_whitespace_only_returns_unknown(self) -> None:
        assert classify_role_family("   ") == RoleFamily.UNKNOWN

    def test_bool_returns_unknown(self) -> None:
        """bools are not valid position labels."""
        assert classify_role_family(True) == RoleFamily.UNKNOWN
        assert classify_role_family(False) == RoleFamily.UNKNOWN

    def test_integer_returns_unknown(self) -> None:
        """Numeric values are not valid position labels."""
        assert classify_role_family(42) == RoleFamily.UNKNOWN

    @pytest.mark.parametrize(
        "label,expected",
        [
            ("GK", RoleFamily.GK),
            ("CB", RoleFamily.CB),
            ("FB", RoleFamily.FB),
            ("DM", RoleFamily.DM),
            ("CM", RoleFamily.CM),
            ("AM", RoleFamily.AM),
            ("W", RoleFamily.W),
            ("ST", RoleFamily.ST),
        ],
    )
    def test_known_fine_roles_map_directly(self, label: str, expected: RoleFamily) -> None:
        assert classify_role_family(label) == expected

    @pytest.mark.parametrize(
        "coarse,expected",
        [
            ("DF", RoleFamily.CB),
            ("MF", RoleFamily.CM),
            ("FW", RoleFamily.ST),
        ],
    )
    def test_coarse_labels_map_to_default_fine_role(
        self, coarse: str, expected: RoleFamily
    ) -> None:
        """DF/MF/FW collapse to CB/CM/ST — the source did not provide
        enough info to pick a finer role."""
        assert classify_role_family(coarse) == expected

    def test_case_insensitive(self) -> None:
        assert classify_role_family("gk") == RoleFamily.GK
        assert classify_role_family("cm") == RoleFamily.CM
        assert classify_role_family("df") == RoleFamily.CB

    def test_whitespace_stripped(self) -> None:
        assert classify_role_family("  GK  ") == RoleFamily.GK
        assert classify_role_family(" MF ") == RoleFamily.CM

    def test_unknown_value_returns_unknown(self) -> None:
        assert classify_role_family("XYZ") == RoleFamily.UNKNOWN
        assert classify_role_family("midfielder") == RoleFamily.UNKNOWN

    def test_position_to_role_covers_all_coarse_labels(self) -> None:
        """POSITION_TO_ROLE must include DF/MF/FW so coarse rows get a
        usable default family rather than UNKNOWN."""
        for label in COARSE_POSITION_LABELS:
            assert label in POSITION_TO_ROLE


# ---------------------------------------------------------------------------
# build_role_system_report
# ---------------------------------------------------------------------------


def _write_player_match(settings: PlatformSettings, df: pd.DataFrame) -> None:
    """Write a player_match.parquet for testing."""
    path = settings.gold_root / "feature_store" / "player_match.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


class TestBuildRoleSystemReport:
    def test_missing_player_match_returns_unavailable(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        report = build_role_system_report(settings=settings)
        assert report["schema"] == ROLE_SYSTEM_SCHEMA
        assert report["schema_version"] == ROLE_SYSTEM_VERSION
        assert report["status"] == "unavailable"
        assert "reason" in report["evidence"]

    def test_empty_player_match_returns_unavailable(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, pd.DataFrame({"position_group": []}))
        report = build_role_system_report(settings=settings)
        assert report["status"] == "unavailable"
        assert "0 rows" in report["evidence"]["reason"]

    def test_no_position_group_column(self, tmp_path: Path) -> None:
        """If player_match lacks position_group, all rows are UNKNOWN."""
        settings = PlatformSettings.from_root(tmp_path)
        df = pd.DataFrame({"player_id": ["a", "b", "c"]})
        _write_player_match(settings, df)
        report = build_role_system_report(settings=settings)
        assert report["status"] == "ok"
        ev = report["evidence"]
        assert ev["total_rows"] == 3
        assert ev["position_group_present"] is False
        assert ev["role_family_distribution"]["UNKNOWN"] == 3
        assert ev["unknown_position_rows"] == 3
        assert ev["coarse_position_rows"] == 0

    def test_normal_distribution(self, tmp_path: Path) -> None:
        """Mix of fine roles, coarse labels, and an unknown value."""
        settings = PlatformSettings.from_root(tmp_path)
        df = pd.DataFrame({
            "position_group": ["GK", "CB", "FB", "DM", "CM", "AM", "W", "ST",
                               "DF", "MF", "FW", "XYZ", None],
        })
        _write_player_match(settings, df)
        report = build_role_system_report(settings=settings)
        assert report["status"] == "ok"
        ev = report["evidence"]
        assert ev["total_rows"] == 13
        assert ev["position_group_present"] is True

        # Raw distribution includes all distinct values + NaN.
        assert ev["raw_distribution"]["GK"] == 1
        assert ev["raw_distribution"]["DF"] == 1
        assert ev["raw_distribution"]["XYZ"] == 1
        # NaN is surfaced as a sentinel string, not silently dropped.
        assert ev["raw_distribution"]["<NaN>"] == 1

        # Role family distribution: 8 fine roles + 3 coarse (DF→CB, MF→CM,
        # FW→ST) + 1 unknown (XYZ) + 1 unknown (NaN) = 13.
        assert ev["role_family_distribution"]["GK"] == 1
        assert ev["role_family_distribution"]["CB"] == 2  # CB + DF
        assert ev["role_family_distribution"]["FB"] == 1
        assert ev["role_family_distribution"]["DM"] == 1
        assert ev["role_family_distribution"]["CM"] == 2  # CM + MF
        assert ev["role_family_distribution"]["AM"] == 1
        assert ev["role_family_distribution"]["W"] == 1
        assert ev["role_family_distribution"]["ST"] == 2  # ST + FW
        assert ev["role_family_distribution"]["UNKNOWN"] == 2  # XYZ + NaN

        # Coarse rows: DF, MF, FW = 3.
        assert ev["coarse_position_rows"] == 3

        # Unknown rows: XYZ + NaN = 2.
        assert ev["unknown_position_rows"] == 2

        # Distinct unknown values: only "XYZ" (NaN is structural, not
        # vocabulary drift, so it is excluded from unknown_value_samples).
        assert ev["distinct_unknown_values"] == 1
        assert ev["unknown_value_samples"] == ["XYZ"]

    def test_dm_count_is_honest_when_zero(self, tmp_path: Path) -> None:
        """If no player has DM label, DM count must be 0 — v1 does not
        auto-invent DM from MF players."""
        settings = PlatformSettings.from_root(tmp_path)
        df = pd.DataFrame({"position_group": ["MF", "MF", "CM"]})
        _write_player_match(settings, df)
        report = build_role_system_report(settings=settings)
        ev = report["evidence"]
        assert ev["role_family_distribution"]["DM"] == 0
        assert ev["role_family_distribution"]["CM"] == 3  # MF→CM + CM
        assert ev["coarse_position_rows"] == 2  # two MF rows

    def test_limitations_non_empty(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        df = pd.DataFrame({"position_group": ["GK"]})
        _write_player_match(settings, df)
        report = build_role_system_report(settings=settings)
        assert len(report["limitations"]) >= 3
        # Limitations must mention v1 scope honestly.
        joined = " ".join(report["limitations"])
        assert "does not auto-invent DM" in joined or "v1" in joined

    def test_report_is_json_serialisable(self, tmp_path: Path) -> None:
        """The report must round-trip through JSON for API/CLI use."""
        settings = PlatformSettings.from_root(tmp_path)
        df = pd.DataFrame({"position_group": ["GK", "MF", "XYZ"]})
        _write_player_match(settings, df)
        report = build_role_system_report(settings=settings)
        # Must not raise.
        json.dumps(report, ensure_ascii=False)

    def test_unknown_value_samples_capped_at_20(self, tmp_path: Path) -> None:
        """When there are many distinct unknown values, only the first
        20 (sorted) are sampled to keep the report size bounded."""
        settings = PlatformSettings.from_root(tmp_path)
        unknown_values = [f"U{i:02d}" for i in range(25)]
        df = pd.DataFrame({"position_group": unknown_values})
        _write_player_match(settings, df)
        report = build_role_system_report(settings=settings)
        ev = report["evidence"]
        assert ev["distinct_unknown_values"] == 25
        assert len(ev["unknown_value_samples"]) == 20
        assert ev["unknown_value_samples"] == sorted(unknown_values)[:20]


# ---------------------------------------------------------------------------
# research-health integration
# ---------------------------------------------------------------------------


class TestResearchHealthIntegration:
    def test_role_system_section_present_in_health_report(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """research-health must include a role_system evidence section."""
        from scoutfootball.evaluation.research_health import build_research_health_report

        settings = PlatformSettings.from_root(tmp_path)
        # Write a minimal player_match so the audit returns ok.
        _write_player_match(
            settings,
            pd.DataFrame({"position_group": ["GK", "CB", "MF"]}),
        )
        # Point PlatformSettings at the temp data root.
        monkeypatch.setenv("SCOUTFOOTBALL_DATA_ROOT", str(tmp_path))

        report = build_research_health_report(settings=settings)
        assert "role_system" in report
        role = report["role_system"]
        assert role["schema"] == ROLE_SYSTEM_SCHEMA
        assert role["status"] == "ok"

    def test_role_system_unavailable_when_player_match_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When player_match.parquet is missing, role_system must return
        unavailable rather than crashing the health report."""
        from scoutfootball.evaluation.research_health import build_research_health_report

        settings = PlatformSettings.from_root(tmp_path)
        monkeypatch.setenv("SCOUTFOOTBALL_DATA_ROOT", str(tmp_path))

        report = build_research_health_report(settings=settings)
        assert report["role_system"]["status"] == "unavailable"

    def test_role_system_limitation_in_health_report(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The health report limitations must mention role_system."""
        from scoutfootball.evaluation.research_health import build_research_health_report

        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(
            settings,
            pd.DataFrame({"position_group": ["GK"]}),
        )
        monkeypatch.setenv("SCOUTFOOTBALL_DATA_ROOT", str(tmp_path))

        report = build_research_health_report(settings=settings)
        joined = " ".join(report["limitations"])
        assert "role_system" in joined
        assert "R-009" in joined or "role" in joined.lower()

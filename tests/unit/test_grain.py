"""Tests for the typed evidence grain + missingness audit (PRS-1 R-006/R-007).

Covers:
- Enum values are stable strings (no silent renames break downstream).
- ``classify_grain`` maps known values and surfaces unknowns as UNKNOWN.
- ``classify_observation`` derives the observation type from grain + source.
- ``classify_missing_reason`` picks the strongest available reason.
- ``build_grain_and_missingness_report`` is read-only, local, and surfaces
  unavailable rather than crashing on missing/unreadable files.
- The report is integrated into ``research-health`` as evidence.
"""

from __future__ import annotations

import json

import pandas as pd

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.grain import (
    EVENT_LEVEL_GROUPS,
    EVENT_LEVEL_SOURCES,
    GRAIN_BY_DATA_GRANULARITY,
    GRAIN_SCHEMA,
    GRAIN_SCHEMA_VERSION,
    EvidenceGrain,
    MissingReason,
    ObservationType,
    build_grain_and_missingness_report,
    classify_grain,
    classify_missing_reason,
    classify_observation,
)
from scoutfootball.evaluation.research_health import build_research_health_report

# ---------------------------------------------------------------------------
# Enum stability
# ---------------------------------------------------------------------------


class TestEnumStability:
    def test_evidence_grain_values(self) -> None:
        assert EvidenceGrain.MATCH.value == "match"
        assert EvidenceGrain.SEASON_PROXY.value == "season_proxy"
        assert EvidenceGrain.AGGREGATE.value == "aggregate"
        assert EvidenceGrain.UNKNOWN.value == "unknown"

    def test_observation_type_values(self) -> None:
        assert ObservationType.OBSERVED.value == "observed"
        assert ObservationType.AGGREGATED.value == "aggregated"
        assert ObservationType.PROXY.value == "proxy"
        assert ObservationType.ESTIMATED.value == "estimated"
        assert ObservationType.NOT_RECORDED.value == "not_recorded"

    def test_missing_reason_values(self) -> None:
        assert MissingReason.NOT_RECORDED.value == "not_recorded"
        assert MissingReason.NOT_APPLICABLE.value == "not_applicable"
        assert MissingReason.NOT_AVAILABLE.value == "not_available"
        assert MissingReason.FILTERED.value == "filtered"
        assert MissingReason.ACTUAL_ZERO.value == "actual_zero"
        assert MissingReason.UNKNOWN.value == "unknown"

    def test_grain_by_data_granularity_covers_known_values(self) -> None:
        # Every known EvidenceGrain except UNKNOWN has a mapping entry.
        # UNKNOWN is the fallthrough, not a key.
        mapped = set(GRAIN_BY_DATA_GRANULARITY.values())
        assert mapped == {
            EvidenceGrain.MATCH,
            EvidenceGrain.SEASON_PROXY,
            EvidenceGrain.AGGREGATE,
        }

    def test_event_level_groups_are_frozenset(self) -> None:
        # frozenset so callers cannot mutate at runtime.
        assert isinstance(EVENT_LEVEL_GROUPS, frozenset)
        assert isinstance(EVENT_LEVEL_SOURCES, frozenset)
        # xT_VAEP and goalkeeper are the known event-level groups.
        assert "xT_VAEP" in EVENT_LEVEL_GROUPS
        assert "goalkeeper" in EVENT_LEVEL_GROUPS

    def test_schema_version_stable(self) -> None:
        assert GRAIN_SCHEMA == "scoutfootball.grain-audit"
        assert GRAIN_SCHEMA_VERSION == "1.0.0"


# ---------------------------------------------------------------------------
# classify_grain
# ---------------------------------------------------------------------------


class TestClassifyGrain:
    def test_known_values(self) -> None:
        assert classify_grain("match") == EvidenceGrain.MATCH
        assert classify_grain("season_proxy") == EvidenceGrain.SEASON_PROXY
        assert classify_grain("aggregate") == EvidenceGrain.AGGREGATE

    def test_case_insensitive(self) -> None:
        assert classify_grain("Match") == EvidenceGrain.MATCH
        assert classify_grain("SEASON_PROXY") == EvidenceGrain.SEASON_PROXY

    def test_whitespace_tolerant(self) -> None:
        assert classify_grain("  match  ") == EvidenceGrain.MATCH

    def test_unknown_value(self) -> None:
        assert classify_grain("weekly_proxy") == EvidenceGrain.UNKNOWN
        assert classify_grain("anything") == EvidenceGrain.UNKNOWN

    def test_none_value(self) -> None:
        assert classify_grain(None) == EvidenceGrain.UNKNOWN

    def test_numeric_value(self) -> None:
        # Non-string inputs should not raise; they stringify and fall through.
        assert classify_grain(42) == EvidenceGrain.UNKNOWN


# ---------------------------------------------------------------------------
# classify_observation
# ---------------------------------------------------------------------------


class TestClassifyObservation:
    def test_match_grain_is_observed(self) -> None:
        assert (
            classify_observation(EvidenceGrain.MATCH, "statsbomb_open")
            == ObservationType.OBSERVED
        )

    def test_season_proxy_grain_is_proxy(self) -> None:
        assert classify_observation(EvidenceGrain.SEASON_PROXY, "fbref") == ObservationType.PROXY

    def test_aggregate_grain_is_aggregated(self) -> None:
        assert classify_observation(EvidenceGrain.AGGREGATE, "any") == ObservationType.AGGREGATED

    def test_unknown_grain_is_not_recorded(self) -> None:
        assert classify_observation(EvidenceGrain.UNKNOWN, "any") == ObservationType.NOT_RECORDED

    def test_none_source_does_not_crash(self) -> None:
        # Match grain is OBSERVED regardless of source_name (the grain
        # already tells us an observation exists).
        assert classify_observation(EvidenceGrain.MATCH, None) == ObservationType.OBSERVED


# ---------------------------------------------------------------------------
# classify_missing_reason
# ---------------------------------------------------------------------------


class TestClassifyMissingReason:
    def test_event_level_group_on_season_proxy_is_not_applicable(self) -> None:
        """xT_VAEP on a season-proxy row cannot exist structurally."""
        reason = classify_missing_reason(
            grain=EvidenceGrain.SEASON_PROXY,
            source_name="fbref",
            group_name="xT_VAEP",
            has_missing_marker=True,
        )
        assert reason == MissingReason.NOT_APPLICABLE

    def test_event_level_group_on_aggregate_is_not_applicable(self) -> None:
        reason = classify_missing_reason(
            grain=EvidenceGrain.AGGREGATE,
            source_name="understat",
            group_name="goalkeeper",
            has_missing_marker=False,
        )
        assert reason == MissingReason.NOT_APPLICABLE

    def test_event_level_group_on_match_statsbomb_is_not_recorded(self) -> None:
        """xT missing on a statsbomb_open match row — the source could
        have supplied it but did not for this row."""
        reason = classify_missing_reason(
            grain=EvidenceGrain.MATCH,
            source_name="statsbomb_open",
            group_name="xT_VAEP",
            has_missing_marker=True,
        )
        assert reason == MissingReason.NOT_RECORDED

    def test_event_level_group_on_non_event_source_is_not_applicable(self) -> None:
        """xT on an FBref row — FBref has no event-level coverage at all."""
        reason = classify_missing_reason(
            grain=EvidenceGrain.MATCH,
            source_name="fbref",
            group_name="xT_VAEP",
            has_missing_marker=False,
        )
        assert reason == MissingReason.NOT_APPLICABLE

    def test_missing_marker_on_non_event_group_is_not_available(self) -> None:
        """defense group missing + marker True → was filled by imputation."""
        reason = classify_missing_reason(
            grain=EvidenceGrain.SEASON_PROXY,
            source_name="fbref",
            group_name="defense",
            has_missing_marker=True,
        )
        assert reason == MissingReason.NOT_AVAILABLE

    def test_no_marker_on_match_row_is_not_recorded(self) -> None:
        """defense group missing on a match row without marker → source
        could have supplied but did not."""
        reason = classify_missing_reason(
            grain=EvidenceGrain.MATCH,
            source_name="fbref",
            group_name="defense",
            has_missing_marker=False,
        )
        assert reason == MissingReason.NOT_RECORDED

    def test_no_marker_on_season_proxy_is_not_recorded(self) -> None:
        reason = classify_missing_reason(
            grain=EvidenceGrain.SEASON_PROXY,
            source_name="understat",
            group_name="defense",
            has_missing_marker=False,
        )
        assert reason == MissingReason.NOT_RECORDED

    def test_unknown_grain_falls_through_to_unknown(self) -> None:
        """When we cannot classify grain, we cannot classify missingness."""
        reason = classify_missing_reason(
            grain=EvidenceGrain.UNKNOWN,
            source_name="fbref",
            group_name="defense",
            has_missing_marker=False,
        )
        assert reason == MissingReason.UNKNOWN

    def test_empty_source_does_not_crash(self) -> None:
        reason = classify_missing_reason(
            grain=EvidenceGrain.MATCH,
            source_name=None,
            group_name="defense",
            has_missing_marker=True,
        )
        # No event-level shortcut applies; missing marker wins.
        assert reason == MissingReason.NOT_AVAILABLE

    def test_event_level_group_on_match_unknown_source_with_marker_is_not_available(
        self,
    ) -> None:
        """Event-level group on a match row from an unknown source with
        a missing marker: the imputation signal is the strongest evidence
        we have. NOT_AVAILABLE wins over NOT_RECORDED because the marker
        proves imputation happened, while the unknown source means we
        cannot claim the source could have supplied it."""
        reason = classify_missing_reason(
            grain=EvidenceGrain.MATCH,
            source_name=None,  # empty source → no event-level shortcut
            group_name="xT_VAEP",
            has_missing_marker=True,
        )
        assert reason == MissingReason.NOT_AVAILABLE

    def test_event_level_group_on_unknown_grain_is_unknown(self) -> None:
        """Event-level group + UNKNOWN grain → UNKNOWN. We cannot
        distinguish ``not_recorded`` (a match-level row from an
        event-level source that did not supply the field) from
        ``not_applicable`` (a season-proxy row where the field cannot
        exist) without knowing the grain. This is the situation the
        current ``rating_feature_matrix.parquet`` exposes, because it
        does not carry ``data_granularity``/``source_name`` forward
        from ``player_match.parquet``. The audit surfaces the gap
        rather than guessing the dominant case."""
        reason = classify_missing_reason(
            grain=EvidenceGrain.UNKNOWN,
            source_name="statsbomb_open",  # source known but grain not
            group_name="xT_VAEP",
            has_missing_marker=True,
        )
        assert reason == MissingReason.UNKNOWN

        # Same answer for goalkeeper group, regardless of marker.
        reason_gk = classify_missing_reason(
            grain=EvidenceGrain.UNKNOWN,
            source_name=None,
            group_name="goalkeeper",
            has_missing_marker=False,
        )
        assert reason_gk == MissingReason.UNKNOWN


# ---------------------------------------------------------------------------
# build_grain_and_missingness_report
# ---------------------------------------------------------------------------


def _write_player_match(
    root,
    *,
    rows: list[dict] | None = None,
) -> None:
    """Write a player_match.parquet with explicit grain + source columns."""
    path = root / "data" / "gold" / "feature_store" / "player_match.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows is None:
        rows = [
            {
                "player_id": "p1",
                "match_id": "m1",
                "data_granularity": "match",
                "source_name": "statsbomb_open",
            },
            {
                "player_id": "p2",
                "match_id": None,
                "data_granularity": "season_proxy",
                "source_name": "fbref",
            },
        ]
    pd.DataFrame(rows).to_parquet(path, index=False)


def _write_feature_matrix(
    root,
    *,
    rows: list[dict] | None = None,
) -> None:
    """Write a rating_feature_matrix.parquet with FIELD_GROUPS fields."""
    path = root / "data" / "gold" / "feature_store" / "rating_feature_matrix.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows is None:
        rows = [
            {
                "player_id": "p1",
                "data_granularity": "match",
                "source_name": "statsbomb_open",
                "tackles": 5.0,
                "interceptions": 3.0,
                "xt_total": 0.5,
                "xt_per_90": 0.05,
                "vaep_total": None,
                "vaep_per_90": None,
                "xT_VAEP_missing": False,
                "defense_missing": False,
            },
            {
                "player_id": "p2",
                "data_granularity": "season_proxy",
                "source_name": "fbref",
                "tackles": None,
                "interceptions": None,
                "xt_total": None,
                "xt_per_90": None,
                "vaep_total": None,
                "vaep_per_90": None,
                "xT_VAEP_missing": True,
                "defense_missing": True,
            },
        ]
    pd.DataFrame(rows).to_parquet(path, index=False)


class TestBuildGrainAndMissingnessReport:
    def test_missing_player_match_returns_unavailable(self, tmp_path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        report = build_grain_and_missingness_report(settings=settings)
        assert report["schema"] == GRAIN_SCHEMA
        assert report["schema_version"] == GRAIN_SCHEMA_VERSION
        assert report["player_match_grain"]["status"] == "unavailable"
        assert (
            "missing" in report["player_match_grain"]["evidence"]["reason"]
        )

    def test_missing_feature_matrix_returns_unavailable(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        report = build_grain_and_missingness_report(settings=settings)
        assert report["player_match_grain"]["status"] == "ok"
        assert report["feature_group_missingness"]["status"] == "unavailable"

    def test_empty_player_match_returns_unavailable(self, tmp_path) -> None:
        _write_player_match(tmp_path, rows=[])
        settings = PlatformSettings.from_root(tmp_path)
        report = build_grain_and_missingness_report(settings=settings)
        assert report["player_match_grain"]["status"] == "unavailable"
        assert "0 rows" in report["player_match_grain"]["evidence"]["reason"]

    def test_grain_counts_match_known_values(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        report = build_grain_and_missingness_report(settings=settings)
        evidence = report["player_match_grain"]["evidence"]
        assert evidence["total_rows"] == 2
        assert evidence["grain_counts"] == {
            EvidenceGrain.MATCH.value: 1,
            EvidenceGrain.SEASON_PROXY.value: 1,
        }
        assert evidence["unknown_grain_values"] == []

    def test_grain_by_source_crosstab(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        report = build_grain_and_missingness_report(settings=settings)
        grain_by_source = report["player_match_grain"]["evidence"]["grain_by_source"]
        assert grain_by_source["statsbomb_open"] == {EvidenceGrain.MATCH.value: 1}
        assert grain_by_source["fbref"] == {EvidenceGrain.SEASON_PROXY.value: 1}

    def test_observation_type_counts(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        report = build_grain_and_missingness_report(settings=settings)
        obs = report["player_match_grain"]["evidence"]["observation_type_counts"]
        assert obs[ObservationType.OBSERVED.value] == 1
        assert obs[ObservationType.PROXY.value] == 1

    def test_unknown_grain_value_surfaces(self, tmp_path) -> None:
        """Rows whose data_granularity is not in the known map surface as
        UNKNOWN rather than being silently bucketed."""
        _write_player_match(
            tmp_path,
            rows=[
                {
                    "player_id": "p1",
                    "data_granularity": "weekly_proxy",  # not in map
                    "source_name": "experimental",
                },
            ],
        )
        settings = PlatformSettings.from_root(tmp_path)
        report = build_grain_and_missingness_report(settings=settings)
        evidence = report["player_match_grain"]["evidence"]
        assert evidence["grain_counts"] == {EvidenceGrain.UNKNOWN.value: 1}
        assert "weekly_proxy" in evidence["unknown_grain_values"]

    def test_missing_grain_column_treats_all_as_unknown(self, tmp_path) -> None:
        _write_player_match(
            tmp_path,
            rows=[{"player_id": "p1", "source_name": "fbref"}],
        )
        settings = PlatformSettings.from_root(tmp_path)
        report = build_grain_and_missingness_report(settings=settings)
        evidence = report["player_match_grain"]["evidence"]
        assert evidence["has_data_granularity_column"] is False
        assert evidence["grain_counts"] == {EvidenceGrain.UNKNOWN.value: 1}
        assert "column_missing" in evidence["unknown_grain_values"]

    def test_feature_group_missingness_bucket_breakdown(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        _write_feature_matrix(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        report = build_grain_and_missingness_report(settings=settings)
        groups = report["feature_group_missingness"]["evidence"]["field_groups"]

        # xT_VAEP group: match+statsbomb_open has data (not missing),
        # season_proxy+fbref is missing and classified NOT_APPLICABLE.
        xt_buckets = groups["xT_VAEP"]["bucket_breakdown"]
        match_bucket = xt_buckets[f"{EvidenceGrain.MATCH.value}|statsbomb_open"]
        assert match_bucket["missing_rows"] == 0
        assert match_bucket["missing_reason"] is None
        proxy_bucket = xt_buckets[f"{EvidenceGrain.SEASON_PROXY.value}|fbref"]
        assert proxy_bucket["missing_rows"] == 1
        assert proxy_bucket["missing_reason"] == MissingReason.NOT_APPLICABLE.value

        # defense group: match row has data, season_proxy row is missing
        # with marker True → NOT_AVAILABLE.
        defense_buckets = groups["defense"]["bucket_breakdown"]
        defense_proxy = defense_buckets[f"{EvidenceGrain.SEASON_PROXY.value}|fbref"]
        assert defense_proxy["missing_rows"] == 1
        assert defense_proxy["missing_reason"] == MissingReason.NOT_AVAILABLE.value

    def test_feature_matrix_without_grain_columns_falls_back_to_unknown(
        self, tmp_path
    ) -> None:
        """When the feature matrix does not carry data_granularity/source_name
        forward, the audit still produces a single UNKNOWN bucket rather
        than crashing."""
        _write_player_match(tmp_path)
        path = tmp_path / "data" / "gold" / "feature_store" / "rating_feature_matrix.parquet"
        pd.DataFrame(
            {
                "player_id": ["p1", "p2"],
                # No data_granularity or source_name columns.
                "tackles": [5.0, None],
                "interceptions": [3.0, None],
                "defense_missing": [False, True],
            }
        ).to_parquet(path, index=False)
        settings = PlatformSettings.from_root(tmp_path)
        report = build_grain_and_missingness_report(settings=settings)
        evidence = report["feature_group_missingness"]["evidence"]
        assert evidence["has_data_granularity_column"] is False
        assert evidence["has_source_name_column"] is False
        defense_buckets = evidence["field_groups"]["defense"]["bucket_breakdown"]
        # Single unknown bucket covering both rows.
        assert len(defense_buckets) == 1
        bucket = next(iter(defense_buckets.values()))
        assert bucket["grain"] == EvidenceGrain.UNKNOWN.value
        assert bucket["source"] == "unknown"
        assert bucket["missing_rows"] == 1
        # Unknown grain + has_missing_marker=True → NOT_AVAILABLE.
        assert bucket["missing_reason"] == MissingReason.NOT_AVAILABLE.value

    def test_report_is_read_only(self, tmp_path) -> None:
        """Running the audit must not modify any artifact on disk."""
        _write_player_match(tmp_path)
        _write_feature_matrix(tmp_path)
        pm_path = tmp_path / "data" / "gold" / "feature_store" / "player_match.parquet"
        fm_path = tmp_path / "data" / "gold" / "feature_store" / "rating_feature_matrix.parquet"
        pm_before = pm_path.read_bytes()
        fm_before = fm_path.read_bytes()

        settings = PlatformSettings.from_root(tmp_path)
        build_grain_and_missingness_report(settings=settings)

        assert pm_path.read_bytes() == pm_before
        assert fm_path.read_bytes() == fm_before


# ---------------------------------------------------------------------------
# Integration with research-health
# ---------------------------------------------------------------------------


class TestResearchHealthIntegration:
    def test_research_health_report_includes_grain_and_missingness(
        self, tmp_path
    ) -> None:
        """The health report must surface the typed grain audit as an
        evidence-only section, even when other layers are unavailable."""
        _write_player_match(tmp_path)
        _write_feature_matrix(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        report = build_research_health_report(settings=settings)
        assert "grain_and_missingness" in report
        grain_section = report["grain_and_missingness"]
        assert grain_section["schema"] == GRAIN_SCHEMA
        assert grain_section["schema_version"] == GRAIN_SCHEMA_VERSION
        assert grain_section["player_match_grain"]["status"] == "ok"
        assert grain_section["feature_group_missingness"]["status"] == "ok"

    def test_research_health_grain_section_unavailable_on_empty_workspace(
        self, tmp_path
    ) -> None:
        """Empty workspace → grain section reports unavailable, never crashes."""
        settings = PlatformSettings.from_root(tmp_path)
        report = build_research_health_report(settings=settings)
        grain_section = report["grain_and_missingness"]
        # Both sub-sections should be unavailable; the audit does not
        # pretend artifacts exist when they don't.
        assert grain_section["player_match_grain"]["status"] == "unavailable"
        assert grain_section["feature_group_missingness"]["status"] == "unavailable"

    def test_research_health_grain_section_does_not_affect_verdict(
        self, tmp_path
    ) -> None:
        """The grain audit is evidence-only: it must not appear in
        blocking_reasons even when its sub-sections are unavailable.
        The verdict comes from the five layers, not from the audit."""
        _write_player_match(tmp_path)
        _write_feature_matrix(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        report = build_research_health_report(settings=settings)
        assert all(
            "grain_and_missingness" not in reason
            for reason in report["blocking_reasons"]
        )

    def test_research_health_limitations_mention_grain_audit(self, tmp_path) -> None:
        """The limitations block must call out that grain audit is
        best-evidence, not canonical schema enforcement — so consumers
        do not over-read it as a contract gate."""
        settings = PlatformSettings.from_root(tmp_path)
        report = build_research_health_report(settings=settings)
        joined = " ".join(report["limitations"])
        assert "grain_and_missingness" in joined
        assert "PRS-1" in joined


# ---------------------------------------------------------------------------
# Schema stability
# ---------------------------------------------------------------------------


def test_grain_report_schema_is_json_serializable(tmp_path) -> None:
    """The report must be JSON-serializable so it can be returned by the
    API and written to disk without further transformation."""
    _write_player_match(tmp_path)
    _write_feature_matrix(tmp_path)
    settings = PlatformSettings.from_root(tmp_path)
    report = build_grain_and_missingness_report(settings=settings)
    # If any non-serializable object (e.g. enum, numpy int) leaked in,
    # this raises and the test fails.
    serialized = json.dumps(report)
    assert GRAIN_SCHEMA in serialized
    assert EvidenceGrain.MATCH.value in serialized
    assert MissingReason.NOT_APPLICABLE.value in serialized

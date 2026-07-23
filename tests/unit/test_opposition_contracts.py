"""Unit tests for the Opposition & Match Core data contract bindings.

Covers:
- ``OppositionFactType`` enum taxonomy (4 fact types)
- ``fact_type_for_artifact`` mapping and error path
- Per-artifact contract builders (briefing / pattern_card / scenario_tree / post_match_review)
- ``build_opposition_contract_registry`` returns contracts only for
  artifacts with at least one stored record (no stubs for absent types)
- ``contract_to_dict`` / ``contracts_to_dict`` produce JSON-safe payloads
- Pattern card, scenario tree and post-match review lineage record their
  declared upstreams (briefing + events / pattern / result)
- License reflects maintainer-local (MIT), not external data
- Fact tier classification: briefing/post_match_review ``status="delivered"``;
  pattern_card/scenario_tree ``status="provisional"``
"""

from __future__ import annotations

import json

import pytest

from scoutfootball.opposition.contracts import (
    OPPOSITION_ARTIFACT_PREFIX,
    PARSER_VERSION_BRIEFING,
    PARSER_VERSION_PATTERN,
    PARSER_VERSION_REVIEW,
    PARSER_VERSION_SCENARIO,
    OppositionFactType,
    build_briefing_contract,
    build_briefing_snapshot,
    build_opposition_contract_registry,
    build_pattern_card_contract,
    build_pattern_card_lineage,
    build_pattern_card_snapshot,
    build_post_match_review_contract,
    build_post_match_review_lineage,
    build_post_match_review_snapshot,
    build_scenario_tree_contract,
    build_scenario_tree_lineage,
    build_scenario_tree_snapshot,
    contract_to_dict,
    contracts_to_dict,
    fact_type_for_artifact,
)
from scoutfootball.schemas.storage import DataContract

# ── Fact type taxonomy ─────────────────────────────────────────────────


class TestOppositionFactType:
    def test_enum_has_exactly_four_values(self):
        assert len(OppositionFactType) == 4

    def test_enum_values_match_taxonomy(self):
        expected = {
            "match_briefing",
            "pattern_card",
            "scenario_tree",
            "post_match_review",
        }
        assert {member.value for member in OppositionFactType} == expected

    def test_enum_is_str_enum_for_json_safety(self):
        assert OppositionFactType.MATCH_BRIEFING == "match_briefing"
        assert isinstance(OppositionFactType.PATTERN_CARD.value, str)

    def test_fact_type_for_artifact_briefing(self):
        ft = fact_type_for_artifact(f"{OPPOSITION_ARTIFACT_PREFIX}.briefing")
        assert ft is OppositionFactType.MATCH_BRIEFING

    def test_fact_type_for_artifact_pattern_card(self):
        ft = fact_type_for_artifact(f"{OPPOSITION_ARTIFACT_PREFIX}.pattern_card")
        assert ft is OppositionFactType.PATTERN_CARD

    def test_fact_type_for_artifact_scenario_tree(self):
        ft = fact_type_for_artifact(f"{OPPOSITION_ARTIFACT_PREFIX}.scenario_tree")
        assert ft is OppositionFactType.SCENARIO_TREE

    def test_fact_type_for_artifact_post_match_review(self):
        ft = fact_type_for_artifact(f"{OPPOSITION_ARTIFACT_PREFIX}.post_match_review")
        assert ft is OppositionFactType.POST_MATCH_REVIEW

    def test_fact_type_for_artifact_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown Opposition artifact id"):
            fact_type_for_artifact("opposition.unknown")

    def test_fact_type_for_artifact_empty_raises(self):
        with pytest.raises(ValueError, match="Unknown Opposition artifact id"):
            fact_type_for_artifact("")


# ── Snapshot builders ──────────────────────────────────────────────────


class TestSnapshotBuilders:
    def test_briefing_snapshot_uses_briefing_parser_version(self):
        snap = build_briefing_snapshot(record_count=5)
        assert snap.parser_version == PARSER_VERSION_BRIEFING
        assert snap.record_count == 5
        assert snap.snapshot_id == f"{OPPOSITION_ARTIFACT_PREFIX}.briefing.v1"

    def test_pattern_card_snapshot_uses_pattern_parser_version(self):
        snap = build_pattern_card_snapshot(record_count=2)
        assert snap.parser_version == PARSER_VERSION_PATTERN
        assert snap.record_count == 2
        assert snap.snapshot_id == f"{OPPOSITION_ARTIFACT_PREFIX}.pattern_card.v1"

    def test_scenario_tree_snapshot_uses_scenario_parser_version(self):
        snap = build_scenario_tree_snapshot(record_count=3)
        assert snap.parser_version == PARSER_VERSION_SCENARIO
        assert snap.record_count == 3
        assert snap.snapshot_id == f"{OPPOSITION_ARTIFACT_PREFIX}.scenario_tree.v1"

    def test_post_match_review_snapshot_uses_review_parser_version(self):
        snap = build_post_match_review_snapshot(record_count=1)
        assert snap.parser_version == PARSER_VERSION_REVIEW
        assert snap.record_count == 1
        assert snap.snapshot_id == f"{OPPOSITION_ARTIFACT_PREFIX}.post_match_review.v1"

    def test_default_record_count_is_one(self):
        assert build_briefing_snapshot().record_count == 1
        assert build_pattern_card_snapshot().record_count == 1
        assert build_scenario_tree_snapshot().record_count == 1
        assert build_post_match_review_snapshot().record_count == 1


# ── Per-artifact contract builders ─────────────────────────────────────


class TestBriefingContract:
    def test_briefing_contract_basic_fields(self):
        c = build_briefing_contract(record_count=3)
        assert c.artifact_id == f"{OPPOSITION_ARTIFACT_PREFIX}.briefing"
        assert c.layer == "opposition"
        assert c.status == "delivered"
        assert c.recorded is True

    def test_briefing_contract_license_is_maintainer_local(self):
        c = build_briefing_contract()
        assert c.license is not None
        assert c.license.source_name == "ScoutFootball maintainer local object"
        assert "MIT" in c.license.license_name
        assert c.license.attribution_required is True
        assert c.license.redistribution_allowed is True

    def test_briefing_contract_primary_key_is_briefing_id(self):
        c = build_briefing_contract()
        assert c.primary_keys == ("briefing_id",)

    def test_briefing_contract_has_no_lineage(self):
        c = build_briefing_contract()
        assert c.lineage == ()

    def test_briefing_contract_coverage_match_count(self):
        c = build_briefing_contract(record_count=4)
        assert c.coverage is not None
        assert c.coverage.match_count == 4

    def test_briefing_contract_snapshot_carries_record_count(self):
        c = build_briefing_contract(record_count=7)
        assert c.snapshot is not None
        assert c.snapshot.record_count == 7


class TestPatternCardContract:
    def test_pattern_card_contract_basic_fields(self):
        c = build_pattern_card_contract(record_count=2)
        assert c.artifact_id == f"{OPPOSITION_ARTIFACT_PREFIX}.pattern_card"
        assert c.layer == "opposition"
        assert c.recorded is True

    def test_pattern_card_contract_status_is_provisional(self):
        c = build_pattern_card_contract()
        assert c.status == "provisional"

    def test_pattern_card_contract_primary_key_is_pattern_id(self):
        c = build_pattern_card_contract()
        assert c.primary_keys == ("pattern_id",)

    def test_pattern_card_contract_notes_hypothesis(self):
        c = build_pattern_card_contract()
        assert c.coverage is not None
        notes = c.coverage.notes.lower()
        # Pattern cards are explicitly working hypotheses, not certified truth.
        assert "hypothes" in notes or "sample" in notes

    def test_pattern_card_contract_has_lineage(self):
        c = build_pattern_card_contract()
        assert len(c.lineage) == 2


class TestScenarioTreeContract:
    def test_scenario_tree_contract_basic_fields(self):
        c = build_scenario_tree_contract(record_count=1)
        assert c.artifact_id == f"{OPPOSITION_ARTIFACT_PREFIX}.scenario_tree"
        assert c.layer == "opposition"
        assert c.recorded is True

    def test_scenario_tree_contract_status_is_provisional(self):
        c = build_scenario_tree_contract()
        assert c.status == "provisional"

    def test_scenario_tree_contract_primary_key_is_scenario_id(self):
        c = build_scenario_tree_contract()
        assert c.primary_keys == ("scenario_id",)

    def test_scenario_tree_contract_has_lineage(self):
        c = build_scenario_tree_contract()
        assert len(c.lineage) == 2


class TestPostMatchReviewContract:
    def test_post_match_review_contract_basic_fields(self):
        c = build_post_match_review_contract(record_count=1)
        assert c.artifact_id == f"{OPPOSITION_ARTIFACT_PREFIX}.post_match_review"
        assert c.layer == "opposition"
        assert c.recorded is True

    def test_post_match_review_contract_status_is_delivered(self):
        c = build_post_match_review_contract()
        assert c.status == "delivered"

    def test_post_match_review_contract_primary_key_is_review_id(self):
        c = build_post_match_review_contract()
        assert c.primary_keys == ("review_id",)

    def test_post_match_review_contract_has_lineage(self):
        c = build_post_match_review_contract()
        assert len(c.lineage) == 3

    def test_post_match_review_coverage_match_count(self):
        c = build_post_match_review_contract(record_count=2)
        assert c.coverage is not None
        assert c.coverage.match_count == 2


# ── Lineage ────────────────────────────────────────────────────────────


class TestLineage:
    def test_pattern_card_lineage_records_briefing_upstream(self):
        lineage = build_pattern_card_lineage()
        upstream_ids = {entry.upstream_id for entry in lineage}
        assert f"{OPPOSITION_ARTIFACT_PREFIX}.briefing" in upstream_ids

    def test_pattern_card_lineage_records_events_upstream(self):
        lineage = build_pattern_card_lineage()
        upstream_ids = {entry.upstream_id for entry in lineage}
        assert "silver.facts.events" in upstream_ids

    def test_pattern_card_lineage_downstream_is_pattern_card(self):
        lineage = build_pattern_card_lineage()
        for entry in lineage:
            assert entry.downstream_id == f"{OPPOSITION_ARTIFACT_PREFIX}.pattern_card"
            assert entry.downstream_layer == "opposition"

    def test_scenario_tree_lineage_records_briefing_upstream(self):
        lineage = build_scenario_tree_lineage()
        upstream_ids = {entry.upstream_id for entry in lineage}
        assert f"{OPPOSITION_ARTIFACT_PREFIX}.briefing" in upstream_ids

    def test_scenario_tree_lineage_records_pattern_upstream(self):
        lineage = build_scenario_tree_lineage()
        upstream_ids = {entry.upstream_id for entry in lineage}
        assert f"{OPPOSITION_ARTIFACT_PREFIX}.pattern_card" in upstream_ids

    def test_scenario_tree_lineage_downstream_is_scenario_tree(self):
        lineage = build_scenario_tree_lineage()
        for entry in lineage:
            assert entry.downstream_id == f"{OPPOSITION_ARTIFACT_PREFIX}.scenario_tree"
            assert entry.downstream_layer == "opposition"

    def test_post_match_review_lineage_records_briefing_upstream(self):
        lineage = build_post_match_review_lineage()
        upstream_ids = {entry.upstream_id for entry in lineage}
        assert f"{OPPOSITION_ARTIFACT_PREFIX}.briefing" in upstream_ids

    def test_post_match_review_lineage_records_scenario_upstream(self):
        lineage = build_post_match_review_lineage()
        upstream_ids = {entry.upstream_id for entry in lineage}
        assert f"{OPPOSITION_ARTIFACT_PREFIX}.scenario_tree" in upstream_ids

    def test_post_match_review_lineage_records_result_upstream(self):
        lineage = build_post_match_review_lineage()
        upstream_ids = {entry.upstream_id for entry in lineage}
        assert "silver.facts.matches" in upstream_ids

    def test_post_match_review_lineage_downstream_is_review(self):
        lineage = build_post_match_review_lineage()
        for entry in lineage:
            assert entry.downstream_id == f"{OPPOSITION_ARTIFACT_PREFIX}.post_match_review"
            assert entry.downstream_layer == "opposition"

    def test_all_lineage_entries_are_recorded(self):
        for builder in (
            build_pattern_card_lineage,
            build_scenario_tree_lineage,
            build_post_match_review_lineage,
        ):
            lineage = builder()
            for entry in lineage:
                assert entry.status == "recorded"


# ── Registry builder ───────────────────────────────────────────────────


class TestRegistryBuilder:
    def test_empty_registry_returns_empty_tuple(self):
        registry = build_opposition_contract_registry()
        assert registry == ()

    def test_registry_with_only_briefings(self):
        registry = build_opposition_contract_registry(briefing_count=5)
        assert len(registry) == 1
        assert registry[0].artifact_id == f"{OPPOSITION_ARTIFACT_PREFIX}.briefing"
        assert registry[0].snapshot is not None
        assert registry[0].snapshot.record_count == 5

    def test_registry_with_all_four_types(self):
        registry = build_opposition_contract_registry(
            briefing_count=2,
            pattern_card_count=1,
            scenario_tree_count=3,
            post_match_review_count=1,
        )
        assert len(registry) == 4
        ids = {c.artifact_id for c in registry}
        assert ids == {
            f"{OPPOSITION_ARTIFACT_PREFIX}.briefing",
            f"{OPPOSITION_ARTIFACT_PREFIX}.pattern_card",
            f"{OPPOSITION_ARTIFACT_PREFIX}.scenario_tree",
            f"{OPPOSITION_ARTIFACT_PREFIX}.post_match_review",
        }

    def test_registry_omits_zero_count_artifacts(self):
        registry = build_opposition_contract_registry(
            briefing_count=0,
            pattern_card_count=0,
            scenario_tree_count=2,
            post_match_review_count=0,
        )
        assert len(registry) == 1
        assert registry[0].artifact_id == f"{OPPOSITION_ARTIFACT_PREFIX}.scenario_tree"

    def test_registry_all_contracts_are_data_contract_instances(self):
        registry = build_opposition_contract_registry(
            briefing_count=1,
            pattern_card_count=1,
            scenario_tree_count=1,
            post_match_review_count=1,
        )
        for contract in registry:
            assert isinstance(contract, DataContract)


# ── Serialization ──────────────────────────────────────────────────────


class TestSerialization:
    def test_contract_to_dict_has_required_keys(self):
        c = build_briefing_contract(record_count=1)
        d = contract_to_dict(c)
        for key in (
            "artifact_id",
            "layer",
            "purpose",
            "status",
            "recorded",
            "license",
            "snapshot",
            "primary_keys",
        ):
            assert key in d

    def test_contract_to_dict_lineage_present_for_pattern_card(self):
        c = build_pattern_card_contract()
        d = contract_to_dict(c)
        assert "lineage" in d
        assert len(d["lineage"]) == 2

    def test_contract_to_dict_lineage_present_for_scenario_tree(self):
        c = build_scenario_tree_contract()
        d = contract_to_dict(c)
        assert "lineage" in d
        assert len(d["lineage"]) == 2

    def test_contract_to_dict_lineage_present_for_post_match_review(self):
        c = build_post_match_review_contract()
        d = contract_to_dict(c)
        assert "lineage" in d
        assert len(d["lineage"]) == 3

    def test_contract_to_dict_no_lineage_key_for_briefing(self):
        c = build_briefing_contract()
        d = contract_to_dict(c)
        # Briefings have empty lineage; the key is omitted.
        assert "lineage" not in d

    def test_contracts_to_dict_returns_list(self):
        registry = build_opposition_contract_registry(
            briefing_count=1, post_match_review_count=1,
        )
        result = contracts_to_dict(registry)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_contract_to_dict_is_json_serializable(self):
        c = build_post_match_review_contract(record_count=2)
        d = contract_to_dict(c)
        json.dumps(d)

    def test_contracts_to_dict_all_json_serializable(self):
        registry = build_opposition_contract_registry(
            briefing_count=1,
            pattern_card_count=1,
            scenario_tree_count=1,
            post_match_review_count=1,
        )
        result = contracts_to_dict(registry)
        json.dumps(result)

    def test_contract_to_dict_coverage_present(self):
        c = build_briefing_contract()
        d = contract_to_dict(c)
        assert "coverage" in d
        assert d["coverage"]["competition_count"] == 0


# ── Constants consistency ──────────────────────────────────────────────


class TestConstants:
    def test_artifact_prefix_is_opposition(self):
        assert OPPOSITION_ARTIFACT_PREFIX == "opposition"

    def test_parser_versions_are_distinct(self):
        versions = {
            PARSER_VERSION_BRIEFING,
            PARSER_VERSION_PATTERN,
            PARSER_VERSION_SCENARIO,
            PARSER_VERSION_REVIEW,
        }
        assert len(versions) == 4

    def test_parser_versions_follow_naming_convention(self):
        assert PARSER_VERSION_BRIEFING.startswith("scoutfootball.opposition.briefing")
        assert PARSER_VERSION_PATTERN.startswith("scoutfootball.opposition.pattern")
        assert PARSER_VERSION_SCENARIO.startswith("scoutfootball.opposition.scenario")
        assert PARSER_VERSION_REVIEW.startswith("scoutfootball.opposition.review")

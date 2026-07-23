"""Unit tests for the Recruitment Core data contract bindings.

Covers:
- ``RecruitmentFactType`` enum taxonomy (3 fact types)
- ``fact_type_for_artifact`` mapping and error path
- Per-artifact contract builders (brief, role_profile, decision_dossier)
- ``build_recruitment_contract_registry`` returns contracts only for
  artifacts with at least one stored record (no stubs for absent types)
- ``contract_to_dict`` / ``contracts_to_dict`` produce JSON-safe payloads
- Decision dossier lineage records both upstream brief and rating matrix
- License reflects maintainer-local (MIT), not external data
"""

from __future__ import annotations

import json

import pytest

from scoutfootball.recruitment.contracts import (
    PARSER_VERSION_BRIEF,
    PARSER_VERSION_DOSSIER,
    PARSER_VERSION_ROLE,
    RECRUITMENT_ARTIFACT_PREFIX,
    RecruitmentFactType,
    build_brief_contract,
    build_brief_snapshot,
    build_decision_dossier_contract,
    build_decision_dossier_lineage,
    build_decision_dossier_snapshot,
    build_recruitment_contract_registry,
    build_role_profile_contract,
    build_role_profile_snapshot,
    contract_to_dict,
    contracts_to_dict,
    fact_type_for_artifact,
)
from scoutfootball.schemas.storage import DataContract

# ── Fact type taxonomy ─────────────────────────────────────────────────


class TestRecruitmentFactType:
    def test_enum_has_exactly_three_values(self):
        assert len(RecruitmentFactType) == 3

    def test_enum_values_match_taxonomy(self):
        expected = {
            "scouting_requirement",
            "role_profile",
            "decision_dossier",
        }
        assert {member.value for member in RecruitmentFactType} == expected

    def test_enum_is_str_enum_for_json_safety(self):
        assert RecruitmentFactType.SCOUTING_REQUIREMENT == "scouting_requirement"
        assert isinstance(RecruitmentFactType.ROLE_PROFILE.value, str)

    def test_fact_type_for_artifact_brief(self):
        ft = fact_type_for_artifact(f"{RECRUITMENT_ARTIFACT_PREFIX}.brief")
        assert ft is RecruitmentFactType.SCOUTING_REQUIREMENT

    def test_fact_type_for_artifact_role_profile(self):
        ft = fact_type_for_artifact(f"{RECRUITMENT_ARTIFACT_PREFIX}.role_profile")
        assert ft is RecruitmentFactType.ROLE_PROFILE

    def test_fact_type_for_artifact_decision_dossier(self):
        ft = fact_type_for_artifact(f"{RECRUITMENT_ARTIFACT_PREFIX}.decision_dossier")
        assert ft is RecruitmentFactType.DECISION_DOSSIER

    def test_fact_type_for_artifact_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown Recruitment artifact id"):
            fact_type_for_artifact("recruitment.unknown")

    def test_fact_type_for_artifact_empty_raises(self):
        with pytest.raises(ValueError, match="Unknown Recruitment artifact id"):
            fact_type_for_artifact("")


# ── Snapshot builders ──────────────────────────────────────────────────


class TestSnapshotBuilders:
    def test_brief_snapshot_uses_brief_parser_version(self):
        snap = build_brief_snapshot(record_count=5)
        assert snap.parser_version == PARSER_VERSION_BRIEF
        assert snap.record_count == 5
        assert snap.snapshot_id == f"{RECRUITMENT_ARTIFACT_PREFIX}.brief.v1"

    def test_role_profile_snapshot_uses_role_parser_version(self):
        snap = build_role_profile_snapshot(record_count=2)
        assert snap.parser_version == PARSER_VERSION_ROLE
        assert snap.record_count == 2
        assert snap.snapshot_id == f"{RECRUITMENT_ARTIFACT_PREFIX}.role_profile.v1"

    def test_decision_dossier_snapshot_uses_dossier_parser_version(self):
        snap = build_decision_dossier_snapshot(record_count=1)
        assert snap.parser_version == PARSER_VERSION_DOSSIER
        assert snap.record_count == 1
        assert snap.snapshot_id == f"{RECRUITMENT_ARTIFACT_PREFIX}.decision_dossier.v1"

    def test_default_record_count_is_one(self):
        snap = build_brief_snapshot()
        assert snap.record_count == 1


# ── Per-artifact contract builders ─────────────────────────────────────


class TestBriefContract:
    def test_brief_contract_basic_fields(self):
        c = build_brief_contract(record_count=3)
        assert c.artifact_id == f"{RECRUITMENT_ARTIFACT_PREFIX}.brief"
        assert c.layer == "recruitment"
        assert c.status == "delivered"
        assert c.recorded is True

    def test_brief_contract_license_is_maintainer_local(self):
        c = build_brief_contract()
        assert c.license is not None
        assert c.license.source_name == "ScoutFootball maintainer local object"
        assert "MIT" in c.license.license_name
        assert c.license.attribution_required is True
        assert c.license.redistribution_allowed is True

    def test_brief_contract_primary_key_is_brief_id(self):
        c = build_brief_contract()
        assert c.primary_keys == ("brief_id",)

    def test_brief_contract_has_no_lineage(self):
        c = build_brief_contract()
        assert c.lineage == ()

    def test_brief_contract_coverage_describes_requirement_not_dataset(self):
        c = build_brief_contract()
        assert c.coverage is not None
        notes = c.coverage.notes.lower()
        assert "not a dataset" in notes or "requirement" in notes

    def test_brief_contract_snapshot_carries_record_count(self):
        c = build_brief_contract(record_count=7)
        assert c.snapshot is not None
        assert c.snapshot.record_count == 7


class TestRoleProfileContract:
    def test_role_profile_contract_basic_fields(self):
        c = build_role_profile_contract(record_count=2)
        assert c.artifact_id == f"{RECRUITMENT_ARTIFACT_PREFIX}.role_profile"
        assert c.layer == "recruitment"
        assert c.status == "provisional"
        assert c.recorded is True

    def test_role_profile_contract_primary_key_is_role_id(self):
        c = build_role_profile_contract()
        assert c.primary_keys == ("role_id",)

    def test_role_profile_contract_notes_subjective(self):
        c = build_role_profile_contract()
        assert c.coverage is not None
        # Role profiles are explicitly NOT universal truth.
        notes = c.coverage.notes.lower()
        assert "subjective" in notes or "not applicable" in notes

    def test_role_profile_status_is_provisional(self):
        c = build_role_profile_contract()
        assert c.status == "provisional"


class TestDecisionDossierContract:
    def test_dossier_contract_basic_fields(self):
        c = build_decision_dossier_contract(record_count=1)
        assert c.artifact_id == f"{RECRUITMENT_ARTIFACT_PREFIX}.decision_dossier"
        assert c.layer == "recruitment"
        assert c.status == "delivered"
        assert c.recorded is True

    def test_dossier_contract_primary_key_is_dossier_id(self):
        c = build_decision_dossier_contract()
        assert c.primary_keys == ("dossier_id",)

    def test_dossier_contract_has_lineage(self):
        c = build_decision_dossier_contract()
        assert len(c.lineage) == 2

    def test_dossier_lineage_records_brief_upstream(self):
        lineage = build_decision_dossier_lineage()
        upstream_ids = {entry.upstream_id for entry in lineage}
        assert f"{RECRUITMENT_ARTIFACT_PREFIX}.brief" in upstream_ids

    def test_dossier_lineage_records_rating_upstream(self):
        lineage = build_decision_dossier_lineage()
        upstream_ids = {entry.upstream_id for entry in lineage}
        assert "rating_feature_matrix" in upstream_ids

    def test_dossier_lineage_downstream_is_dossier(self):
        lineage = build_decision_dossier_lineage()
        for entry in lineage:
            assert entry.downstream_id == f"{RECRUITMENT_ARTIFACT_PREFIX}.decision_dossier"
            assert entry.downstream_layer == "recruitment"

    def test_dossier_lineage_all_entries_recorded(self):
        lineage = build_decision_dossier_lineage()
        for entry in lineage:
            assert entry.status == "recorded"

    def test_dossier_coverage_player_count_matches(self):
        c = build_decision_dossier_contract(record_count=4)
        assert c.coverage is not None
        assert c.coverage.player_count == 4


# ── Registry builder ───────────────────────────────────────────────────


class TestRegistryBuilder:
    def test_empty_registry_returns_empty_tuple(self):
        registry = build_recruitment_contract_registry()
        assert registry == ()

    def test_registry_with_only_briefs(self):
        registry = build_recruitment_contract_registry(brief_count=5)
        assert len(registry) == 1
        assert registry[0].artifact_id == f"{RECRUITMENT_ARTIFACT_PREFIX}.brief"
        assert registry[0].snapshot is not None
        assert registry[0].snapshot.record_count == 5

    def test_registry_with_all_three_types(self):
        registry = build_recruitment_contract_registry(
            brief_count=2,
            role_profile_count=1,
            decision_dossier_count=3,
        )
        assert len(registry) == 3
        ids = {c.artifact_id for c in registry}
        assert ids == {
            f"{RECRUITMENT_ARTIFACT_PREFIX}.brief",
            f"{RECRUITMENT_ARTIFACT_PREFIX}.role_profile",
            f"{RECRUITMENT_ARTIFACT_PREFIX}.decision_dossier",
        }

    def test_registry_omits_zero_count_artifacts(self):
        registry = build_recruitment_contract_registry(
            brief_count=0,
            role_profile_count=0,
            decision_dossier_count=2,
        )
        assert len(registry) == 1
        assert registry[0].artifact_id == f"{RECRUITMENT_ARTIFACT_PREFIX}.decision_dossier"

    def test_registry_all_contracts_are_data_contract_instances(self):
        registry = build_recruitment_contract_registry(
            brief_count=1, role_profile_count=1, decision_dossier_count=1,
        )
        for contract in registry:
            assert isinstance(contract, DataContract)


# ── Serialization ──────────────────────────────────────────────────────


class TestSerialization:
    def test_contract_to_dict_has_required_keys(self):
        c = build_brief_contract(record_count=1)
        d = contract_to_dict(c)
        assert "artifact_id" in d
        assert "layer" in d
        assert "purpose" in d
        assert "status" in d
        assert "recorded" in d
        assert "license" in d
        assert "snapshot" in d
        assert "primary_keys" in d

    def test_contract_to_dict_lineage_present_for_dossier(self):
        c = build_decision_dossier_contract()
        d = contract_to_dict(c)
        assert "lineage" in d
        assert len(d["lineage"]) == 2

    def test_contract_to_dict_no_lineage_key_for_brief(self):
        c = build_brief_contract()
        d = contract_to_dict(c)
        # Briefs have empty lineage; the key is omitted.
        assert "lineage" not in d

    def test_contracts_to_dict_returns_list(self):
        registry = build_recruitment_contract_registry(
            brief_count=1, decision_dossier_count=1,
        )
        result = contracts_to_dict(registry)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_contract_to_dict_is_json_serializable(self):
        c = build_decision_dossier_contract(record_count=2)
        d = contract_to_dict(c)
        # Must be JSON-serializable for API responses.
        json.dumps(d)

    def test_contracts_to_dict_all_json_serializable(self):
        registry = build_recruitment_contract_registry(
            brief_count=1, role_profile_count=1, decision_dossier_count=1,
        )
        result = contracts_to_dict(registry)
        json.dumps(result)

    def test_contract_to_dict_coverage_present(self):
        c = build_brief_contract()
        d = contract_to_dict(c)
        assert "coverage" in d
        assert d["coverage"]["competition_count"] == 0


# ── Constants consistency ──────────────────────────────────────────────


class TestConstants:
    def test_artifact_prefix_is_recruitment(self):
        assert RECRUITMENT_ARTIFACT_PREFIX == "recruitment"

    def test_parser_versions_are_distinct(self):
        versions = {PARSER_VERSION_BRIEF, PARSER_VERSION_ROLE, PARSER_VERSION_DOSSIER}
        assert len(versions) == 3

    def test_parser_versions_follow_naming_convention(self):
        assert PARSER_VERSION_BRIEF.startswith("scoutfootball.recruitment.brief")
        assert PARSER_VERSION_ROLE.startswith("scoutfootball.recruitment.role")
        assert PARSER_VERSION_DOSSIER.startswith("scoutfootball.recruitment.dossier")

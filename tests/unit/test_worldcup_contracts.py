"""Unit tests for the World Cup Core data contract bindings.

Covers:
- ``WorldCupFactType`` enum taxonomy (5 fact types)
- ``fact_type_for_artifact`` mapping and error path
- Per-artifact contract builders (schedule, expected_callups,
  rating_coverage, model_probability, tournament_state)
- Stub contracts for not-yet-available facts (official_roster,
  injury_report)
- ``build_worldcup_contract_registry`` returns 7 contracts (5 active + 2 stubs)
- ``contract_to_dict`` / ``contracts_to_dict`` produce JSON-safe payloads
- ``count_expected_callups`` and the ``get_*_contract`` helpers in
  :mod:`scoutfootball.worldcup.data`
- ``attach_tournament_state_contract`` / ``get_tournament_state_contract``
- Tournament state round-trip preserves the embedded contract
- 1.0.0 backward compatibility: state files without ``contract`` load as None
- ``get_wc_contracts`` registry endpoint returns a self-consistent payload
"""

from __future__ import annotations

import json

import pytest

from scoutfootball.schemas.storage import DataContract
from scoutfootball.worldcup.contracts import (
    PARSER_VERSION_RATINGS,
    PARSER_VERSION_SCHEDULE,
    PARSER_VERSION_SQUADS,
    PARSER_VERSION_STRENGTH,
    PARSER_VERSION_TOURNAMENT_STATE,
    SNAPSHOT_AS_OF_EXPECTED_CALLUPS,
    SNAPSHOT_AS_OF_OPTA_PRIORS,
    SNAPSHOT_AS_OF_RATING_COVERAGE,
    WORLDCUP_ARTIFACT_PREFIX,
    WorldCupFactType,
    build_expected_callups_contract,
    build_injury_report_stub_contract,
    build_model_probability_contract,
    build_official_roster_stub_contract,
    build_rating_coverage_contract,
    build_schedule_contract,
    build_tournament_state_contract,
    build_worldcup_contract_registry,
    contract_to_dict,
    contracts_to_dict,
    fact_type_for_artifact,
)
from scoutfootball.worldcup.tournament import (
    SCHEMA_VERSION,
    attach_tournament_state_contract,
    get_tournament_state_contract,
    init_state,
    state_from_dict,
    state_to_dict,
)

# ── Fact type taxonomy ─────────────────────────────────────────────────


class TestWorldCupFactType:
    def test_enum_has_exactly_five_values(self):
        assert len(WorldCupFactType) == 5

    def test_enum_values_match_taxonomy(self):
        expected = {
            "official_roster",
            "expected_callup",
            "injury_report",
            "rating_coverage",
            "model_probability",
        }
        assert {member.value for member in WorldCupFactType} == expected

    def test_enum_is_str_enum_for_json_safety(self):
        # str enums serialise as their value without custom encoders.
        assert WorldCupFactType.OFFICIAL_ROSTER == "official_roster"
        assert isinstance(WorldCupFactType.EXPECTED_CALLUP.value, str)


# ── Artifact → fact type mapping ────────────────────────────────────────


class TestFactTypeForArtifact:
    def test_schedule_maps_to_expected_callup(self):
        # The schedule snapshot ships with the same Opta-priors as_of date
        # as the expected callups, so it shares their fact type.
        assert (
            fact_type_for_artifact(f"{WORLDCUP_ARTIFACT_PREFIX}.schedule")
            == WorldCupFactType.EXPECTED_CALLUP
        )

    def test_expected_callups_maps_to_expected_callup(self):
        assert (
            fact_type_for_artifact(f"{WORLDCUP_ARTIFACT_PREFIX}.expected_callups")
            == WorldCupFactType.EXPECTED_CALLUP
        )

    def test_official_roster_maps_to_official_roster(self):
        assert (
            fact_type_for_artifact(f"{WORLDCUP_ARTIFACT_PREFIX}.official_roster")
            == WorldCupFactType.OFFICIAL_ROSTER
        )

    def test_injury_report_maps_to_injury_report(self):
        assert (
            fact_type_for_artifact(f"{WORLDCUP_ARTIFACT_PREFIX}.injury_report")
            == WorldCupFactType.INJURY_REPORT
        )

    def test_rating_coverage_maps_to_rating_coverage(self):
        assert (
            fact_type_for_artifact(f"{WORLDCUP_ARTIFACT_PREFIX}.rating_coverage")
            == WorldCupFactType.RATING_COVERAGE
        )

    def test_model_probability_maps_to_model_probability(self):
        assert (
            fact_type_for_artifact(f"{WORLDCUP_ARTIFACT_PREFIX}.model_probability")
            == WorldCupFactType.MODEL_PROBABILITY
        )

    def test_tournament_state_maps_to_expected_callup(self):
        # The tournament state carries maintainer-recorded results for the
        # expected-callups schedule; it inherits that fact type rather than
        # introducing a new one.
        assert (
            fact_type_for_artifact(f"{WORLDCUP_ARTIFACT_PREFIX}.tournament_state")
            == WorldCupFactType.EXPECTED_CALLUP
        )

    def test_unknown_artifact_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown World Cup artifact id"):
            fact_type_for_artifact("worldcup.unknown_artifact")

    def test_unprefixed_artifact_raises_value_error(self):
        with pytest.raises(ValueError):
            fact_type_for_artifact("schedule")

    def test_all_seven_known_artifacts_resolve(self):
        ids = [
            "schedule",
            "expected_callups",
            "official_roster",
            "injury_report",
            "rating_coverage",
            "model_probability",
            "tournament_state",
        ]
        for suffix in ids:
            artifact_id = f"{WORLDCUP_ARTIFACT_PREFIX}.{suffix}"
            assert isinstance(fact_type_for_artifact(artifact_id), WorldCupFactType)


# ── Per-artifact contract builders ──────────────────────────────────────


class TestScheduleContract:
    def test_returns_data_contract(self):
        contract = build_schedule_contract(record_count=72)
        assert isinstance(contract, DataContract)

    def test_artifact_id_and_layer(self):
        contract = build_schedule_contract(record_count=72)
        assert contract.artifact_id == f"{WORLDCUP_ARTIFACT_PREFIX}.schedule"
        assert contract.layer == "worldcup"

    def test_status_delivered(self):
        contract = build_schedule_contract(record_count=72)
        assert contract.status == "delivered"

    def test_record_count_propagates_to_snapshot_and_coverage(self):
        contract = build_schedule_contract(record_count=72)
        assert contract.snapshot is not None
        assert contract.snapshot.record_count == 72
        assert contract.coverage is not None
        assert contract.coverage.match_count == 72

    def test_snapshot_uses_opta_priors_as_of(self):
        contract = build_schedule_contract(record_count=72)
        assert contract.snapshot is not None
        assert contract.snapshot.as_of == SNAPSHOT_AS_OF_OPTA_PRIORS
        assert contract.snapshot.parser_version == PARSER_VERSION_SCHEDULE

    def test_coverage_team_count_is_48(self):
        contract = build_schedule_contract(record_count=72)
        assert contract.coverage is not None
        assert contract.coverage.team_count == 48

    def test_primary_keys(self):
        contract = build_schedule_contract(record_count=72)
        assert contract.primary_keys == ("match_id",)

    def test_license_is_fifa_fixture(self):
        contract = build_schedule_contract(record_count=72)
        assert contract.license is not None
        assert "FIFA" in contract.license.source_name
        assert contract.license.redistribution_allowed is True

    def test_no_lineage(self):
        # The schedule is a static fixture pattern; it has no upstream.
        contract = build_schedule_contract(record_count=72)
        assert contract.lineage == ()

    def test_zero_record_count_is_allowed(self):
        contract = build_schedule_contract(record_count=0)
        assert contract.snapshot is not None
        assert contract.snapshot.record_count == 0


class TestExpectedCallupsContract:
    def test_artifact_id(self):
        contract = build_expected_callups_contract(record_count=1248)
        assert contract.artifact_id == f"{WORLDCUP_ARTIFACT_PREFIX}.expected_callups"

    def test_status_provisional(self):
        contract = build_expected_callups_contract(record_count=1248)
        assert contract.status == "provisional"

    def test_snapshot_uses_expected_callups_as_of(self):
        contract = build_expected_callups_contract(record_count=1248)
        assert contract.snapshot is not None
        assert contract.snapshot.as_of == SNAPSHOT_AS_OF_EXPECTED_CALLUPS
        assert contract.snapshot.parser_version == PARSER_VERSION_SQUADS

    def test_coverage_player_count_matches_record_count(self):
        contract = build_expected_callups_contract(record_count=1248)
        assert contract.coverage is not None
        assert contract.coverage.player_count == 1248
        assert contract.coverage.team_count == 48

    def test_primary_keys_team_and_player(self):
        contract = build_expected_callups_contract(record_count=1248)
        assert contract.primary_keys == ("team", "player_name")

    def test_license_allows_commercial_reuse(self):
        # Expected callups are maintainer-compiled under MIT, so commercial
        # reuse is allowed — unlike the upstream FBref/Understat ratings.
        contract = build_expected_callups_contract(record_count=1248)
        assert contract.license is not None
        assert contract.license.commercial_use_allowed is True


class TestRatingCoverageContract:
    def test_artifact_id(self):
        contract = build_rating_coverage_contract(record_count=600)
        assert contract.artifact_id == f"{WORLDCUP_ARTIFACT_PREFIX}.rating_coverage"

    def test_status_delivered(self):
        contract = build_rating_coverage_contract(record_count=600)
        assert contract.status == "delivered"

    def test_snapshot_uses_rating_coverage_as_of(self):
        contract = build_rating_coverage_contract(record_count=600)
        assert contract.snapshot is not None
        assert contract.snapshot.as_of == SNAPSHOT_AS_OF_RATING_COVERAGE
        assert contract.snapshot.parser_version == PARSER_VERSION_RATINGS

    def test_lineage_records_rating_feature_matrix_upstream(self):
        contract = build_rating_coverage_contract(record_count=600)
        upstream_ids = {entry.upstream_id for entry in contract.lineage}
        assert "rating_feature_matrix" in upstream_ids
        for entry in contract.lineage:
            assert entry.downstream_id == f"{WORLDCUP_ARTIFACT_PREFIX}.rating_coverage"
            assert entry.downstream_layer == "worldcup"

    def test_license_disallows_commercial_use(self):
        # Ratings come from FBref (CC BY-NC-SA) + Understat ToS.
        contract = build_rating_coverage_contract(record_count=600)
        assert contract.license is not None
        assert contract.license.commercial_use_allowed is False
        assert contract.license.redistribution_allowed is False


class TestModelProbabilityContract:
    def test_artifact_id(self):
        contract = build_model_probability_contract(record_count=48)
        assert contract.artifact_id == f"{WORLDCUP_ARTIFACT_PREFIX}.model_probability"

    def test_status_delivered(self):
        contract = build_model_probability_contract(record_count=48)
        assert contract.status == "delivered"

    def test_snapshot_uses_opta_priors_as_of(self):
        contract = build_model_probability_contract(record_count=48)
        assert contract.snapshot is not None
        assert contract.snapshot.as_of == SNAPSHOT_AS_OF_OPTA_PRIORS
        assert contract.snapshot.parser_version == PARSER_VERSION_STRENGTH

    def test_lineage_records_three_upstreams(self):
        # rating_coverage → model_probability, rating_feature_matrix →
        # model_probability, opta_public_priors → model_probability.
        contract = build_model_probability_contract(record_count=48)
        upstream_ids = {entry.upstream_id for entry in contract.lineage}
        assert upstream_ids == {
            f"{WORLDCUP_ARTIFACT_PREFIX}.rating_coverage",
            "rating_feature_matrix",
            "opta_public_priors",
        }

    def test_coverage_team_count_is_48(self):
        contract = build_model_probability_contract(record_count=48)
        assert contract.coverage is not None
        assert contract.coverage.team_count == 48


class TestTournamentStateContract:
    def test_artifact_id(self):
        contract = build_tournament_state_contract(record_count=12)
        assert contract.artifact_id == f"{WORLDCUP_ARTIFACT_PREFIX}.tournament_state"

    def test_status_delivered(self):
        contract = build_tournament_state_contract(record_count=12)
        assert contract.status == "delivered"

    def test_snapshot_parser_version(self):
        contract = build_tournament_state_contract(record_count=12)
        assert contract.snapshot is not None
        assert contract.snapshot.parser_version == PARSER_VERSION_TOURNAMENT_STATE

    def test_lineage_records_schedule_upstream(self):
        contract = build_tournament_state_contract(record_count=12)
        upstream_ids = {entry.upstream_id for entry in contract.lineage}
        assert upstream_ids == {f"{WORLDCUP_ARTIFACT_PREFIX}.schedule"}

    def test_license_is_local_tournament_state(self):
        contract = build_tournament_state_contract(record_count=12)
        assert contract.license is not None
        assert "local tournament state" in contract.license.source_name.lower()


# ── Stub contracts ──────────────────────────────────────────────────────


class TestOfficialRosterStub:
    def test_status_missing(self):
        contract = build_official_roster_stub_contract()
        assert contract.status == "missing"

    def test_no_license_snapshot_coverage(self):
        contract = build_official_roster_stub_contract()
        assert contract.license is None
        assert contract.snapshot is None
        assert contract.coverage is None

    def test_not_recorded(self):
        contract = build_official_roster_stub_contract()
        assert contract.recorded is False

    def test_artifact_id(self):
        contract = build_official_roster_stub_contract()
        assert contract.artifact_id == f"{WORLDCUP_ARTIFACT_PREFIX}.official_roster"


class TestInjuryReportStub:
    def test_status_not_tracked(self):
        contract = build_injury_report_stub_contract()
        assert contract.status == "not_tracked"

    def test_no_license_snapshot_coverage(self):
        contract = build_injury_report_stub_contract()
        assert contract.license is None
        assert contract.snapshot is None
        assert contract.coverage is None

    def test_not_recorded(self):
        contract = build_injury_report_stub_contract()
        assert contract.recorded is False

    def test_artifact_id(self):
        contract = build_injury_report_stub_contract()
        assert contract.artifact_id == f"{WORLDCUP_ARTIFACT_PREFIX}.injury_report"


# ── Registry builder ────────────────────────────────────────────────────


class TestBuildWorldcupContractRegistry:
    def test_returns_seven_contracts_with_stubs(self):
        contracts = build_worldcup_contract_registry()
        assert len(contracts) == 7

    def test_returns_five_contracts_without_stubs(self):
        contracts = build_worldcup_contract_registry(include_stubs=False)
        assert len(contracts) == 5

    def test_artifact_ids_unique(self):
        contracts = build_worldcup_contract_registry()
        ids = [c.artifact_id for c in contracts]
        assert len(ids) == len(set(ids))

    def test_all_contracts_in_worldcup_layer(self):
        contracts = build_worldcup_contract_registry()
        for contract in contracts:
            assert contract.layer == "worldcup"

    def test_registry_propagates_live_counts(self):
        contracts = build_worldcup_contract_registry(
            schedule_match_count=72,
            expected_callups_player_count=1248,
            rating_coverage_player_count=600,
            model_probability_team_count=48,
            tournament_state_result_count=12,
        )
        by_id = {c.artifact_id: c for c in contracts}
        assert by_id[f"{WORLDCUP_ARTIFACT_PREFIX}.schedule"].snapshot.record_count == 72
        assert (
            by_id[f"{WORLDCUP_ARTIFACT_PREFIX}.expected_callups"].snapshot.record_count
            == 1248
        )
        assert (
            by_id[f"{WORLDCUP_ARTIFACT_PREFIX}.rating_coverage"].snapshot.record_count
            == 600
        )
        assert (
            by_id[f"{WORLDCUP_ARTIFACT_PREFIX}.model_probability"].snapshot.record_count
            == 48
        )
        assert (
            by_id[f"{WORLDCUP_ARTIFACT_PREFIX}.tournament_state"].snapshot.record_count
            == 12
        )

    def test_default_counts_zero_except_schedule_and_model(self):
        contracts = build_worldcup_contract_registry(include_stubs=False)
        by_id = {c.artifact_id: c for c in contracts}
        # Defaults: schedule=72, expected_callups=0, rating_coverage=0,
        # model_probability=48, tournament_state=0
        assert by_id[f"{WORLDCUP_ARTIFACT_PREFIX}.schedule"].snapshot.record_count == 72
        assert (
            by_id[f"{WORLDCUP_ARTIFACT_PREFIX}.model_probability"].snapshot.record_count
            == 48
        )
        assert (
            by_id[f"{WORLDCUP_ARTIFACT_PREFIX}.expected_callups"].snapshot.record_count
            == 0
        )

    def test_stubs_appear_last(self):
        contracts = build_worldcup_contract_registry()
        last_two_ids = [c.artifact_id for c in contracts[-2:]]
        assert last_two_ids == [
            f"{WORLDCUP_ARTIFACT_PREFIX}.official_roster",
            f"{WORLDCUP_ARTIFACT_PREFIX}.injury_report",
        ]


# ── Serialization ────────────────────────────────────────────────────────


class TestContractToDict:
    def test_returns_dict(self):
        contract = build_schedule_contract(record_count=72)
        payload = contract_to_dict(contract)
        assert isinstance(payload, dict)

    def test_includes_required_fields(self):
        contract = build_schedule_contract(record_count=72)
        payload = contract_to_dict(contract)
        for key in ("artifact_id", "layer", "purpose", "status", "recorded"):
            assert key in payload

    def test_includes_license_when_present(self):
        contract = build_schedule_contract(record_count=72)
        payload = contract_to_dict(contract)
        assert "license" in payload
        assert payload["license"]["source_name"]

    def test_omits_license_when_absent(self):
        contract = build_official_roster_stub_contract()
        payload = contract_to_dict(contract)
        assert "license" not in payload

    def test_omits_snapshot_when_absent(self):
        contract = build_official_roster_stub_contract()
        payload = contract_to_dict(contract)
        assert "snapshot" not in payload

    def test_omits_coverage_when_absent(self):
        contract = build_official_roster_stub_contract()
        payload = contract_to_dict(contract)
        assert "coverage" not in payload

    def test_omits_lineage_when_empty(self):
        contract = build_schedule_contract(record_count=72)
        payload = contract_to_dict(contract)
        assert "lineage" not in payload

    def test_includes_lineage_when_present(self):
        contract = build_rating_coverage_contract(record_count=600)
        payload = contract_to_dict(contract)
        assert "lineage" in payload
        assert isinstance(payload["lineage"], list)
        assert payload["lineage"]

    def test_payload_is_json_serializable(self):
        # Pydantic model_dump(mode="json") should already produce JSON-safe
        # primitives; this guards against regressions if the storage schema
        # ever gains datetime or set fields without a JSON encoder.
        contracts = build_worldcup_contract_registry()
        for contract in contracts:
            payload = contract_to_dict(contract)
            json.dumps(payload)  # raises if not serializable


class TestContractsToDict:
    def test_returns_list_of_dicts(self):
        contracts = build_worldcup_contract_registry(include_stubs=False)
        payloads = contracts_to_dict(contracts)
        assert isinstance(payloads, list)
        assert len(payloads) == 5
        for payload in payloads:
            assert isinstance(payload, dict)

    def test_empty_iterable_returns_empty_list(self):
        assert contracts_to_dict([]) == []


# ── data.py bindings ────────────────────────────────────────────────────


class TestDataModuleBindings:
    def test_count_expected_callups_is_1248(self):
        # 48 teams × 26 players per squad.
        from scoutfootball.worldcup.data import count_expected_callups

        assert count_expected_callups() == 1248

    def test_count_expected_callups_matches_squads_total(self):
        from scoutfootball.worldcup.data import SQUADS, count_expected_callups

        manual = sum(len(players) for players in SQUADS.values())
        assert count_expected_callups() == manual

    def test_get_expected_callups_contract_uses_live_count(self):
        from scoutfootball.worldcup.data import get_expected_callups_contract

        contract = get_expected_callups_contract()
        assert contract.snapshot is not None
        assert contract.snapshot.record_count == 1248

    def test_get_rating_coverage_contract_propagates_count(self):
        from scoutfootball.worldcup.data import get_rating_coverage_contract

        contract = get_rating_coverage_contract(rated_player_count=42)
        assert contract.snapshot is not None
        assert contract.snapshot.record_count == 42

    def test_get_model_probability_contract_default_48(self):
        from scoutfootball.worldcup.data import get_model_probability_contract

        contract = get_model_probability_contract()
        assert contract.snapshot is not None
        assert contract.snapshot.record_count == 48

    def test_get_model_probability_contract_accepts_override(self):
        from scoutfootball.worldcup.data import get_model_probability_contract

        contract = get_model_probability_contract(team_count=32)
        assert contract.snapshot is not None
        assert contract.snapshot.record_count == 32

    def test_get_schedule_contract_default_72(self):
        from scoutfootball.worldcup.data import get_schedule_contract

        contract = get_schedule_contract()
        assert contract.snapshot is not None
        assert contract.snapshot.record_count == 72

    def test_squads_fact_type_constant(self):
        from scoutfootball.worldcup.data import SQUADS_FACT_TYPE

        assert SQUADS_FACT_TYPE == "expected_callup"

    def test_opta_priors_fact_type_constant(self):
        from scoutfootball.worldcup.data import OPTA_PRIORS_FACT_TYPE

        assert OPTA_PRIORS_FACT_TYPE == "model_probability"


# ── Tournament state contract attachment ─────────────────────────────────


class TestAttachTournamentStateContract:
    def test_sets_contract_field(self):
        state = init_state()
        assert state.contract is None
        attach_tournament_state_contract(state)
        assert state.contract is not None
        assert state.contract["artifact_id"] == (
            f"{WORLDCUP_ARTIFACT_PREFIX}.tournament_state"
        )

    def test_returns_same_state_object(self):
        state = init_state()
        returned = attach_tournament_state_contract(state)
        assert returned is state

    def test_default_result_count_is_zero_for_fresh_state(self):
        state = init_state()
        attach_tournament_state_contract(state)
        assert state.contract["snapshot"]["record_count"] == 0

    def test_explicit_result_count_propagates(self):
        state = init_state()
        attach_tournament_state_contract(state, result_count=7)
        assert state.contract["snapshot"]["record_count"] == 7

    def test_contract_payload_is_json_serializable(self):
        state = init_state()
        attach_tournament_state_contract(state)
        json.dumps(state.contract)


class TestGetTournamentStateContract:
    def test_returns_existing_contract_without_rebuild(self):
        state = init_state()
        attach_tournament_state_contract(state, result_count=3)
        contract = get_tournament_state_contract(state)
        # Should reuse the attached contract (record_count=3), not rebuild
        # with the default zero count.
        assert contract["snapshot"]["record_count"] == 3

    def test_builds_on_demand_when_absent(self):
        state = init_state()
        assert state.contract is None
        contract = get_tournament_state_contract(state)
        assert contract is not None
        assert contract["artifact_id"] == (
            f"{WORLDCUP_ARTIFACT_PREFIX}.tournament_state"
        )

    def test_on_demand_build_does_not_mutate_state(self):
        state = init_state()
        get_tournament_state_contract(state)
        # The helper must not write to state.contract; only attach_* does.
        assert state.contract is None

    def test_on_demand_build_uses_explicit_count(self):
        state = init_state()
        contract = get_tournament_state_contract(state, result_count=5)
        assert contract["snapshot"]["record_count"] == 5


# ── Tournament state round-trip with contract ────────────────────────────


class TestTournamentStateContractRoundTrip:
    def test_state_to_dict_includes_contract_when_present(self):
        state = init_state()
        attach_tournament_state_contract(state, result_count=2)
        payload = state_to_dict(state)
        assert "contract" in payload
        assert payload["contract"]["artifact_id"] == (
            f"{WORLDCUP_ARTIFACT_PREFIX}.tournament_state"
        )

    def test_state_to_dict_omits_contract_when_absent(self):
        state = init_state()
        payload = state_to_dict(state)
        assert "contract" not in payload

    def test_round_trip_preserves_contract(self):
        state = init_state()
        attach_tournament_state_contract(state, result_count=4)
        rebuilt = state_from_dict(state_to_dict(state))
        assert rebuilt.contract is not None
        assert (
            rebuilt.contract["artifact_id"]
            == state.contract["artifact_id"]
        )
        assert (
            rebuilt.contract["snapshot"]["record_count"]
            == state.contract["snapshot"]["record_count"]
        )

    def test_round_trip_preserves_schema_version_1_1_0(self):
        state = init_state()
        attach_tournament_state_contract(state)
        rebuilt = state_from_dict(state_to_dict(state))
        assert rebuilt.schema_version == SCHEMA_VERSION
        assert rebuilt.schema_version == "1.1.0"

    def test_round_trip_payload_is_json_serializable(self):
        state = init_state()
        attach_tournament_state_contract(state)
        payload = state_to_dict(state)
        # Must survive json.dumps so save_state / export work.
        json.dumps(payload)


# ── 1.0.0 backward compatibility ─────────────────────────────────────────


class TestTournamentStateBackwardCompat:
    def test_1_0_0_state_without_contract_loads_as_none(self):
        # Build a minimal 1.0.0 payload by stripping the contract field.
        state = init_state()
        payload = state_to_dict(state)
        payload["schema_version"] = "1.0.0"
        payload.pop("contract", None)
        rebuilt = state_from_dict(payload)
        assert rebuilt.contract is None

    def test_1_0_0_payload_with_explicit_null_contract_loads_as_none(self):
        state = init_state()
        payload = state_to_dict(state)
        payload["schema_version"] = "1.0.0"
        payload["contract"] = None
        rebuilt = state_from_dict(payload)
        assert rebuilt.contract is None

    def test_invalid_contract_type_raises(self):
        state = init_state()
        payload = state_to_dict(state)
        payload["contract"] = ["not", "a", "dict"]
        with pytest.raises(ValueError, match="contract"):
            state_from_dict(payload)

    def test_unsupported_schema_version_raises(self):
        state = init_state()
        payload = state_to_dict(state)
        payload["schema_version"] = "2.0.0"
        with pytest.raises(ValueError, match="schema version"):
            state_from_dict(payload)


# ── Registry endpoint ────────────────────────────────────────────────────


class TestGetWcContractsEndpoint:
    def test_returns_ok_status(self):
        from scoutfootball.api import get_wc_contracts

        result = get_wc_contracts()
        assert result["status"] == "ok"

    def test_schema_field(self):
        from scoutfootball.api import get_wc_contracts

        result = get_wc_contracts()
        assert result["schema"] == "scoutfootball.world-cup-contract-registry"

    def test_version_field(self):
        from scoutfootball.api import get_wc_contracts

        result = get_wc_contracts()
        assert result["version"] == "1.0.0"

    def test_returns_seven_contracts(self):
        from scoutfootball.api import get_wc_contracts

        result = get_wc_contracts()
        assert result["count"] == 7
        assert len(result["contracts"]) == 7

    def test_fact_types_length_matches_contracts(self):
        from scoutfootball.api import get_wc_contracts

        result = get_wc_contracts()
        assert len(result["fact_types"]) == len(result["contracts"])

    def test_artifact_ids_unique_in_registry(self):
        from scoutfootball.api import get_wc_contracts

        result = get_wc_contracts()
        ids = [c["artifact_id"] for c in result["contracts"]]
        assert len(ids) == len(set(ids))

    def test_expected_callups_contract_has_live_count(self):
        # count_expected_callups() == 1248 → registry must reflect that.
        from scoutfootball.api import get_wc_contracts

        result = get_wc_contracts()
        expected = next(
            c for c in result["contracts"]
            if c["artifact_id"] == f"{WORLDCUP_ARTIFACT_PREFIX}.expected_callups"
        )
        assert expected["snapshot"]["record_count"] == 1248

    def test_registry_payload_is_json_serializable(self):
        from scoutfootball.api import get_wc_contracts

        result = get_wc_contracts()
        json.dumps(result)

    def test_disclaimer_present(self):
        from scoutfootball.api import get_wc_contracts

        result = get_wc_contracts()
        assert "disclaimer" in result
        # Disclaimer must not be empty.
        assert result["disclaimer"]

    def test_every_contract_has_fact_type(self):
        from scoutfootball.api import get_wc_contracts

        result = get_wc_contracts()
        for fact_type in result["fact_types"]:
            assert fact_type in {member.value for member in WorldCupFactType}


# ── Endpoint contract emission ───────────────────────────────────────────
#
# These tests verify that the 8 World Cup API endpoints that emit Core
# contracts do so consistently: every emitted contract must serialise and
# its fact_type must resolve via fact_type_for_artifact.


class TestEndpointsEmitContracts:
    def test_get_wc_schedule_emits_schedule_contract(self):
        from scoutfootball.api import get_wc_schedule

        result = get_wc_schedule()
        assert result["status"] == "ok"
        assert len(result["contracts"]) == 1
        contract = result["contracts"][0]
        assert contract["artifact_id"] == f"{WORLDCUP_ARTIFACT_PREFIX}.schedule"
        assert result["fact_types"] == ["expected_callup"]
        json.dumps(contract)

    def test_get_wc_squad_emits_two_contracts(self):
        from scoutfootball.api import get_wc_squad

        result = get_wc_squad("Mexico")
        assert result["status"] == "ok"
        assert len(result["contracts"]) == 2
        ids = {c["artifact_id"] for c in result["contracts"]}
        assert ids == {
            f"{WORLDCUP_ARTIFACT_PREFIX}.expected_callups",
            f"{WORLDCUP_ARTIFACT_PREFIX}.rating_coverage",
        }
        assert set(result["fact_types"]) == {"expected_callup", "rating_coverage"}

    def test_get_wc_groups_emits_three_contracts(self):
        from scoutfootball.api import get_wc_groups

        result = get_wc_groups()
        assert result["status"] == "ok"
        assert len(result["contracts"]) == 3
        assert len(result["fact_types"]) == 3

    def test_get_wc_teams_emits_three_contracts(self):
        from scoutfootball.api import get_wc_teams

        result = get_wc_teams()
        assert result["status"] == "ok"
        assert len(result["contracts"]) == 3

    def test_get_wc_predictions_emits_model_probability_contract(self):
        from scoutfootball.api import get_wc_predictions

        result = get_wc_predictions()
        assert result["status"] == "ok"
        assert len(result["contracts"]) == 1
        contract = result["contracts"][0]
        assert contract["artifact_id"] == (
            f"{WORLDCUP_ARTIFACT_PREFIX}.model_probability"
        )
        assert result["fact_types"] == ["model_probability"]

    def test_get_wc_knockout_emits_model_probability_contract(self):
        from scoutfootball.api import get_wc_knockout

        result = get_wc_knockout()
        assert result["status"] == "ok"
        assert len(result["contracts"]) == 1
        assert result["contracts"][0]["artifact_id"] == (
            f"{WORLDCUP_ARTIFACT_PREFIX}.model_probability"
        )

    def test_get_wc_tournament_summary_emits_tournament_state_contract(self):
        from scoutfootball.api import get_wc_tournament_summary

        result = get_wc_tournament_summary()
        assert result["status"] == "ok"
        assert len(result["contracts"]) == 1
        contract = result["contracts"][0]
        assert contract["artifact_id"] == (
            f"{WORLDCUP_ARTIFACT_PREFIX}.tournament_state"
        )

    def test_get_wc_knockout_bracket_emits_tournament_state_contract(self):
        from scoutfootball.api import get_wc_knockout_bracket

        result = get_wc_knockout_bracket()
        assert result["status"] == "ok"
        assert "contracts" in result
        assert len(result["contracts"]) == 1
        assert result["contracts"][0]["artifact_id"] == (
            f"{WORLDCUP_ARTIFACT_PREFIX}.tournament_state"
        )

    def test_every_emitted_contract_resolves_fact_type(self):
        # Cross-check: every contract artifact_id emitted by any endpoint
        # must resolve through fact_type_for_artifact without raising.
        from scoutfootball.api import (
            get_wc_groups,
            get_wc_knockout,
            get_wc_knockout_bracket,
            get_wc_predictions,
            get_wc_schedule,
            get_wc_squad,
            get_wc_teams,
            get_wc_tournament_summary,
        )

        endpoints = [
            get_wc_schedule,
            get_wc_squad,
            get_wc_groups,
            get_wc_teams,
            get_wc_predictions,
            get_wc_knockout,
            get_wc_tournament_summary,
            get_wc_knockout_bracket,
        ]
        seen_ids: set[str] = set()
        for fn in endpoints:
            if fn is get_wc_squad:
                result = fn("Mexico")
            else:
                result = fn()
            for contract in result.get("contracts", []):
                seen_ids.add(contract["artifact_id"])
        for artifact_id in seen_ids:
            # Must not raise.
            assert isinstance(
                fact_type_for_artifact(artifact_id), WorldCupFactType
            )

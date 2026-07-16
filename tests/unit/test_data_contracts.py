"""Contract tests for the data contract registry.

These tests verify that the data contract registry is internally
consistent and stays in sync with the actual data directories and
table definitions defined elsewhere in the codebase.
"""

from __future__ import annotations

import re
from pathlib import Path

from scoutfootball.architecture import (
    _source_licenses,
    build_data_contract_registry,
    build_default_architecture,
)
from scoutfootball.schemas import build_core_table_definitions


def _extract_cli_subcommands() -> set[str]:
    main_py = Path(__file__).parent.parent.parent / "src" / "scoutfootball" / "__main__.py"
    text = main_py.read_text(encoding="utf-8")
    return set(re.findall(r'\bsub\.add_parser\(\s*"([^"]+)"', text))


def test_registry_is_valid() -> None:
    registry = build_data_contract_registry()
    assert registry.package_version
    assert registry.generated_at
    assert registry.contracts
    assert registry.layers


def test_contract_ids_are_unique() -> None:
    registry = build_data_contract_registry()
    ids = [c.artifact_id for c in registry.contracts]
    dups = [i for i in ids if ids.count(i) > 1]
    assert len(ids) == len(set(ids)), f"Duplicate contract ids: {dups}"


def test_layers_match_contracts() -> None:
    registry = build_data_contract_registry()
    layers_from_contracts = set(c.layer for c in registry.contracts)
    assert set(registry.layers) == layers_from_contracts


def test_raw_contracts_have_licenses() -> None:
    registry = build_data_contract_registry()
    raw_contracts = [c for c in registry.contracts if c.layer == "raw"]
    assert raw_contracts, "No raw-layer contracts found"
    for contract in raw_contracts:
        assert contract.license is not None, (
            f"Raw contract {contract.artifact_id} missing license"
        )


def test_raw_data_dirs_match_architecture() -> None:
    registry = build_data_contract_registry()
    arch = build_default_architecture()
    raw_dirs = {
        d.relative_path for d in arch.data_directories if d.layer == "raw"
    }
    raw_contracts = {
        c.artifact_id for c in registry.contracts if c.layer == "raw"
    }
    missing = raw_dirs - raw_contracts
    extra = raw_contracts - raw_dirs
    assert not missing, f"Raw data dirs missing contracts: {sorted(missing)}"
    assert not extra, f"Raw contracts not in architecture: {sorted(extra)}"


def test_silver_contracts_match_core_tables() -> None:
    registry = build_data_contract_registry()
    table_defs = build_core_table_definitions()
    table_names = {t.name for t in table_defs}
    silver_contracts = {
        c.artifact_id for c in registry.contracts if c.layer == "silver"
    }
    missing = table_names - silver_contracts
    extra = silver_contracts - table_names
    assert not missing, f"Core tables missing silver contracts: {sorted(missing)}"
    assert not extra, f"Silver contracts not in core tables: {sorted(extra)}"


def test_silver_contracts_have_primary_keys() -> None:
    registry = build_data_contract_registry()
    silver_contracts = [c for c in registry.contracts if c.layer == "silver"]
    for contract in silver_contracts:
        assert contract.primary_keys, (
            f"Silver contract {contract.artifact_id} missing primary keys"
        )


def test_source_licenses_are_complete() -> None:
    licenses = _source_licenses()
    arch = build_default_architecture()
    raw_sources = {
        d.source_name for d in arch.data_directories
        if d.layer == "raw" and d.source_name
    }
    missing = raw_sources - set(licenses.keys())
    assert not missing, f"Raw sources missing license definitions: {sorted(missing)}"


def test_every_data_dir_has_contract() -> None:
    registry = build_data_contract_registry()
    arch = build_default_architecture()
    all_dir_paths = {d.relative_path for d in arch.data_directories}
    contract_ids = {c.artifact_id for c in registry.contracts}
    missing = all_dir_paths - contract_ids
    missing_silver = {
        d for d in missing if d.startswith("silver/")
    }
    non_silver_missing = missing - missing_silver
    assert not non_silver_missing, (
        f"Data dirs missing contracts: {sorted(non_silver_missing)}"
    )


def test_data_contracts_cli_command_exists() -> None:
    cmds = _extract_cli_subcommands()
    assert "data-contracts" in cmds, "data-contracts CLI command missing"

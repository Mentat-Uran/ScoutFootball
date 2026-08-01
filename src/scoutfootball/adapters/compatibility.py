"""Project-local adapter admission matrix.

The adapter manifest says what code exists.  This module joins that declaration
to the canonical raw-data contracts so callers can distinguish an adapter that
is admitted to the maintainer's current local workflow from an experimental
implementation that must remain blocked.  It does not interpret upstream
terms, authorize network access, or make any public-export claim.
"""

from __future__ import annotations

import datetime as _dt
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from scoutfootball import __version__
from scoutfootball.adapters.manifest import AdapterCapability
from scoutfootball.adapters.registry import build_adapter_registry
from scoutfootball.architecture import build_data_contract_registry
from scoutfootball.schemas.storage import SourceLicense


class AdapterAdmissionStatus(StrEnum):
    """Project-local admission state for a registered adapter."""

    ADMITTED_LOCAL = "admitted_local"
    BLOCKED_EXPERIMENTAL = "blocked_experimental"
    BLOCKED_MISSING_CONTRACT = "blocked_missing_contract"


class AdapterCompatibility(BaseModel):
    """Compatibility and admission result for one adapter.

    ``redistribution_allowed`` is copied only from the input source's recorded
    raw-data contract.  It is not a determination about derived outputs,
    upstream terms, or a user's right to publish any particular artifact.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    admission_status: AdapterAdmissionStatus
    admitted_for_current_local_workflow: bool
    maintained: bool
    contract_registered: bool
    license_name: str = ""
    attribution_required: bool | None = None
    redistribution_allowed: bool | None = None
    capabilities: tuple[AdapterCapability, ...] = ()
    ingestion_cli: str = ""
    reasons: tuple[str, ...] = ()


class AdapterCompatibilityMatrix(BaseModel):
    """Read-only compatibility matrix derived from manifests and contracts."""

    model_config = ConfigDict(frozen=True)

    generated_at: str
    package_version: str = ""
    entries: tuple[AdapterCompatibility, ...] = ()

    def by_source(self, source_id: str) -> AdapterCompatibility | None:
        for entry in self.entries:
            if entry.source_id == source_id:
                return entry
        return None


def _raw_source_licenses() -> dict[str, SourceLicense]:
    """Return contract-owned raw source licenses keyed by source name."""
    contracts = build_data_contract_registry().by_layer("raw")
    return {
        contract.license.source_name: contract.license
        for contract in contracts
        if contract.license is not None
    }


def build_adapter_compatibility_matrix() -> AdapterCompatibilityMatrix:
    """Build the canonical project-local adapter admission matrix.

    Maintained adapters need a matching raw-data contract.  Experimental
    adapters are deliberately represented but blocked, even if their module
    is importable or a pipeline branch exists.  This keeps registry presence
    from being mistaken for workflow admission.
    """
    licenses = _raw_source_licenses()
    entries: list[AdapterCompatibility] = []

    for manifest in build_adapter_registry().manifests:
        license_record = licenses.get(manifest.source_id)
        contract_registered = license_record is not None

        if not manifest.maintained:
            status = AdapterAdmissionStatus.BLOCKED_EXPERIMENTAL
            admitted = False
            reasons = (
                "Experimental adapter not in the maintainer's real workflow.",
                "Registry presence does not admit it to a current workflow or public directory.",
            )
        elif license_record is None:
            status = AdapterAdmissionStatus.BLOCKED_MISSING_CONTRACT
            admitted = False
            reasons = (
                "Maintained adapter lacks a matching raw-data contract.",
                "It must remain blocked until source, license, snapshot, and deletion "
                "boundaries are registered.",
            )
        else:
            status = AdapterAdmissionStatus.ADMITTED_LOCAL
            admitted = True
            reasons = (
                "Admitted only to the maintainer's current local workflow.",
                "Network access, source freshness, and any derived-output publication "
                "remain separate checks.",
            )

        entries.append(
            AdapterCompatibility(
                source_id=manifest.source_id,
                admission_status=status,
                admitted_for_current_local_workflow=admitted,
                maintained=manifest.maintained,
                contract_registered=contract_registered,
                license_name=(license_record.license_name if license_record else ""),
                attribution_required=(
                    license_record.attribution_required if license_record else None
                ),
                redistribution_allowed=(
                    license_record.redistribution_allowed if license_record else None
                ),
                capabilities=manifest.capabilities,
                ingestion_cli=manifest.ingestion_cli,
                reasons=reasons,
            )
        )

    return AdapterCompatibilityMatrix(
        generated_at=_dt.datetime.now(_dt.UTC).isoformat(),
        package_version=__version__,
        entries=tuple(entries),
    )

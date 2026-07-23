"""Recruitment Pack: versioned requirement briefs, role profiles and decision dossiers.

This pack is the P1 6.1 reference implementation of the recruitment
workflow promised by the roadmap.  It reuses Core
:mod:`scoutfootball.schemas.storage` types via
:mod:`scoutfootball.recruitment.contracts` so the recruitment pack does
not duplicate identity, snapshot or export logic.

The pack is local-first and personal-use.  Briefs, role profiles and
dossiers are persisted as local JSON records under the maintainer's
``report_root/recruitment/`` directory.  There is no cloud sync, no
multi-tenant store and no account system.
"""

from __future__ import annotations

from scoutfootball.recruitment.brief import (
    BRIEF_SCHEMA,
    BRIEF_VERSION,
    BriefValidationError,
    RecruitmentBrief,
    validate_brief_id,
    validate_brief_payload,
)
from scoutfootball.recruitment.contracts import (
    RecruitmentFactType,
    build_brief_contract,
    build_decision_dossier_contract,
    build_recruitment_contract_registry,
    build_role_profile_contract,
    contract_to_dict,
    contracts_to_dict,
    fact_type_for_artifact,
)
from scoutfootball.recruitment.store import (
    BRIEF_RECORD_SCHEMA,
    BRIEF_RECORD_VERSION,
    BriefStore,
    BriefStoreError,
)

__all__ = [
    "RecruitmentFactType",
    "RecruitmentBrief",
    "BriefStore",
    "BriefStoreError",
    "BriefValidationError",
    "BRIEF_SCHEMA",
    "BRIEF_VERSION",
    "BRIEF_RECORD_SCHEMA",
    "BRIEF_RECORD_VERSION",
    "build_brief_contract",
    "build_decision_dossier_contract",
    "build_recruitment_contract_registry",
    "build_role_profile_contract",
    "contract_to_dict",
    "contracts_to_dict",
    "fact_type_for_artifact",
    "validate_brief_id",
    "validate_brief_payload",
]

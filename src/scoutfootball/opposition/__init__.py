"""Opposition & Match Pack: source-limited briefings, pattern cards,
scenario trees and post-match reviews.

This pack is the P1 6.2 reference implementation of the match
preparation workflow promised by the roadmap.  It reuses Core
:mod:`scoutfootball.schemas.storage` types via
:mod:`scoutfootball.opposition.contracts` so the pack does not duplicate
identity, snapshot or export logic.

The pack is local-first and personal-use.  Briefings, pattern cards,
scenario trees and post-match reviews are persisted as local JSON
records under the maintainer's ``report_root/opposition/`` directory.
There is no cloud sync, no multi-tenant store and no account system.
"""

from __future__ import annotations

from scoutfootball.opposition.briefing import (
    BRIEFING_SCHEMA,
    BRIEFING_VERSION,
    BriefingSection,
    BriefingValidationError,
    OppositionBriefing,
    validate_briefing_id,
    validate_briefing_payload,
)
from scoutfootball.opposition.contracts import (
    OppositionFactType,
    build_briefing_contract,
    build_opposition_contract_registry,
    build_pattern_card_contract,
    build_post_match_review_contract,
    build_scenario_tree_contract,
    contract_to_dict,
    contracts_to_dict,
    fact_type_for_artifact,
)
from scoutfootball.opposition.post_match_review import (
    MAX_REVIEW_BYTES,
    REVIEW_SCHEMA,
    REVIEW_VERSION,
    VALID_FACT_TIERS,
    VALID_HYPOTHESIS_OUTCOMES,
    VALID_REVIEW_DECISIONS,
    VALID_REVIEW_STATUS,
    VALID_RISK_SEVERITY,
    PostMatchReview,
    ReviewValidationError,
    validate_review_id,
    validate_review_payload,
)
from scoutfootball.opposition.post_match_review_store import (
    MAX_REVIEW_RECORD_BYTES,
    REVIEW_RECORD_SCHEMA,
    REVIEW_RECORD_VERSION,
    ReviewStore,
    ReviewStoreError,
)
from scoutfootball.opposition.store import (
    BRIEFING_RECORD_SCHEMA,
    BRIEFING_RECORD_VERSION,
    BriefingStore,
    BriefingStoreError,
)

__all__ = [
    "OppositionFactType",
    "OppositionBriefing",
    "BriefingSection",
    "PostMatchReview",
    "BriefingStore",
    "ReviewStore",
    "BriefingStoreError",
    "ReviewStoreError",
    "BriefingValidationError",
    "ReviewValidationError",
    "BRIEFING_SCHEMA",
    "BRIEFING_VERSION",
    "BRIEFING_RECORD_SCHEMA",
    "BRIEFING_RECORD_VERSION",
    "REVIEW_SCHEMA",
    "REVIEW_VERSION",
    "REVIEW_RECORD_SCHEMA",
    "REVIEW_RECORD_VERSION",
    "MAX_REVIEW_BYTES",
    "MAX_REVIEW_RECORD_BYTES",
    "VALID_FACT_TIERS",
    "VALID_HYPOTHESIS_OUTCOMES",
    "VALID_REVIEW_DECISIONS",
    "VALID_REVIEW_STATUS",
    "VALID_RISK_SEVERITY",
    "build_briefing_contract",
    "build_opposition_contract_registry",
    "build_pattern_card_contract",
    "build_post_match_review_contract",
    "build_scenario_tree_contract",
    "contract_to_dict",
    "contracts_to_dict",
    "fact_type_for_artifact",
    "validate_briefing_id",
    "validate_briefing_payload",
    "validate_review_id",
    "validate_review_payload",
]

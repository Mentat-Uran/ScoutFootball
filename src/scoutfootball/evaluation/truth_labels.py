"""Player truth labels data contract and validation."""

from __future__ import annotations

import enum
import re
from typing import Any

import pandas as pd


class LabelSource(enum.Enum):
    """Source of the truth label."""

    TRANSFERMARKT_VALUE = "transfermarkt_value"
    AWARD = "award"
    EXPERT_TIER = "expert_tier"
    MANUAL_CALIBRATION = "manual_calibration"
    SCOUTING_REVIEW = "scouting_review"


class LabelConfidence(enum.Enum):
    """Confidence level of the truth label."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Schema definition for player_truth_labels
TRUTH_LABELS_SCHEMA: dict[str, str] = {
    "player_id": "string",
    "season": "string",
    "label_source": "string",  # LabelSource enum values
    "label_confidence": "string",  # LabelConfidence enum values
    "label_value": "float64",
    "as_of_date": "string",  # ISO date
    "position_scope": "string",  # e.g., "GK", "CB", "AM", "ST", or "all"
    "manual_review_flag": "bool",
}

TRUTH_LABELS_COLUMNS = list(TRUTH_LABELS_SCHEMA.keys())

# A label produced from the score it is meant to supervise is useful for a
# descriptive tier, but is not evidence for training or evaluating that same
# score.  Keep this policy explicit rather than relying on callers to remember
# how an import was produced.
SUPERVISION_ELIGIBLE_SOURCES = frozenset(
    {
        LabelSource.TRANSFERMARKT_VALUE.value,
        LabelSource.AWARD.value,
        LabelSource.MANUAL_CALIBRATION.value,
        LabelSource.SCOUTING_REVIEW.value,
    },
)
# Transfermarkt market value is useful as an external proxy anchor, but it is
# not an independent observation of player ability.  Keep it eligible for
# proxy training while excluding it from the research-health readiness gate.
PROXY_LABEL_SOURCES = frozenset({LabelSource.TRANSFERMARKT_VALUE.value})
INDEPENDENT_PLAYER_LABEL_SOURCES = frozenset(
    {
        LabelSource.AWARD.value,
        LabelSource.MANUAL_CALIBRATION.value,
        LabelSource.SCOUTING_REVIEW.value,
    }
)
SELF_REFERENTIAL_LABEL_SOURCES = frozenset({LabelSource.EXPERT_TIER.value})


def _season_end_date(value: object) -> pd.Timestamp:
    """Return the conservative May 31 cut-off for a compact season code."""
    match = re.fullmatch(r"(\d{2})(\d{2})", str(value).strip())
    if match is None:
        return pd.NaT
    return pd.Timestamp(year=2000 + int(match.group(2)), month=5, day=31)


def truth_label_temporal_report(df: pd.DataFrame) -> dict[str, int]:
    """Audit whether independently sourced labels were known during a season.

    This is deliberately an audit, not automatic proof of causal collection:
    a date does not establish how a market value or manual label was produced.
    """
    required = {"label_source", "season", "as_of_date"}
    if required - set(df.columns):
        return {
            "temporally_eligible_rows": 0,
            "missing_or_invalid_as_of_rows": 0,
            "invalid_season_rows": 0,
            "post_season_rows": 0,
        }
    sources = df["label_source"].fillna("").astype(str).str.strip().str.lower()
    candidates = df.loc[sources.isin(SUPERVISION_ELIGIBLE_SOURCES)].copy()
    if candidates.empty:
        return {
            "temporally_eligible_rows": 0,
            "missing_or_invalid_as_of_rows": 0,
            "invalid_season_rows": 0,
            "post_season_rows": 0,
        }
    as_of = pd.to_datetime(candidates["as_of_date"], errors="coerce", utc=True).dt.tz_localize(None)
    season_end = candidates["season"].map(_season_end_date)
    valid_as_of = as_of.notna()
    valid_season = season_end.notna()
    eligible = valid_as_of & valid_season & as_of.le(season_end)
    return {
        "temporally_eligible_rows": int(eligible.sum()),
        "missing_or_invalid_as_of_rows": int((~valid_as_of).sum()),
        "invalid_season_rows": int((~valid_season).sum()),
        "post_season_rows": int((valid_as_of & valid_season & as_of.gt(season_end)).sum()),
    }


def truth_label_supervision_report(df: pd.DataFrame) -> dict[str, Any]:
    """Summarise which labels are eligible for supervised rating use.

    This is a source-policy guard, not proof that a manual or scouting label
    was collected independently.  It prevents known self-referential
    ``expert_tier`` rows from being used to train or anchor the optimizer.
    """
    if "label_source" not in df.columns:
        return {
            "policy": "source-policy-v1",
            "total_rows": int(len(df)),
            "eligible_rows": 0,
            "proxy_rows": 0,
            "independent_rows": 0,
            "excluded_rows": int(len(df)),
            "eligible_source_counts": {},
            "proxy_source_counts": {},
            "independent_source_counts": {},
            "excluded_source_counts": {},
            "status": "missing_label_source",
            "caveat": "Source eligibility does not prove collection independence.",
            "temporal": truth_label_temporal_report(df),
        }

    sources = df["label_source"].fillna("").astype(str).str.strip().str.lower()
    eligible_mask = sources.isin(SUPERVISION_ELIGIBLE_SOURCES)
    proxy_mask = sources.isin(PROXY_LABEL_SOURCES)
    independent_mask = sources.isin(INDEPENDENT_PLAYER_LABEL_SOURCES)
    eligible = sources[eligible_mask].value_counts().sort_index().to_dict()
    proxy = sources[proxy_mask].value_counts().sort_index().to_dict()
    independent = sources[independent_mask].value_counts().sort_index().to_dict()
    excluded = sources[~eligible_mask].value_counts().sort_index().to_dict()
    temporal = truth_label_temporal_report(df)
    independent_temporal = truth_label_temporal_report(
        df.loc[independent_mask].copy()
    )
    return {
        "policy": "source-policy-v1",
        "total_rows": int(len(df)),
        "eligible_rows": int(eligible_mask.sum()),
        "proxy_rows": int(proxy_mask.sum()),
        "independent_rows": int(independent_mask.sum()),
        "excluded_rows": int((~eligible_mask).sum()),
        "eligible_source_counts": {str(key): int(value) for key, value in eligible.items()},
        "proxy_source_counts": {str(key): int(value) for key, value in proxy.items()},
        "independent_source_counts": {
            str(key): int(value) for key, value in independent.items()
        },
        "excluded_source_counts": {str(key): int(value) for key, value in excluded.items()},
        "status": "eligible_labels_available" if eligible_mask.any() else "no_eligible_labels",
        "caveat": "Source eligibility does not prove collection independence.",
        "temporal": temporal,
        "independent_temporal": independent_temporal,
    }


def filter_supervision_eligible_truth_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Return only labels allowed for supervised training and score anchors."""
    report = truth_label_supervision_report(df)
    if "label_source" not in df.columns:
        result = df.iloc[0:0].copy()
    else:
        sources = df["label_source"].fillna("").astype(str).str.strip().str.lower()
        result = df.loc[sources.isin(SUPERVISION_ELIGIBLE_SOURCES)].copy()
    result.attrs["supervision_report"] = report
    return result


def validate_truth_labels(df: pd.DataFrame) -> list[str]:
    """Validate a truth labels DataFrame against the schema.

    Returns a list of error messages. Empty list means valid.
    """
    errors: list[str] = []

    # Check required columns
    missing_cols = set(TRUTH_LABELS_COLUMNS) - set(df.columns)
    if missing_cols:
        errors.append(f"Missing columns: {sorted(missing_cols)}")

    # Check label_source enum values
    valid_sources = {e.value for e in LabelSource}
    if "label_source" in df.columns:
        invalid_sources = set(df["label_source"].unique()) - valid_sources
        if invalid_sources:
            errors.append(
                f"Invalid label_source values: {sorted(invalid_sources)}. "
                f"Valid: {sorted(valid_sources)}"
            )

    # Check label_confidence enum values
    valid_confidences = {e.value for e in LabelConfidence}
    if "label_confidence" in df.columns:
        invalid_confidences = set(df["label_confidence"].unique()) - valid_confidences
        if invalid_confidences:
            errors.append(
                f"Invalid label_confidence values: {sorted(invalid_confidences)}. "
                f"Valid: {sorted(valid_confidences)}"
            )

    # Check no duplicate player_id+season+label_source
    if all(col in df.columns for col in ["player_id", "season", "label_source"]):
        dupes = df.duplicated(subset=["player_id", "season", "label_source"], keep=False)
        if dupes.any():
            n_dupes = int(dupes.sum())
            errors.append(
                f"Found {n_dupes} duplicate player_id+season+label_source records"
            )

    return errors


def create_empty_truth_labels() -> pd.DataFrame:
    """Create an empty truth labels DataFrame with correct schema."""
    return pd.DataFrame(
        {
            "player_id": pd.Series(dtype="string"),
            "season": pd.Series(dtype="string"),
            "label_source": pd.Series(dtype="string"),
            "label_confidence": pd.Series(dtype="string"),
            "label_value": pd.Series(dtype="float64"),
            "as_of_date": pd.Series(dtype="string"),
            "position_scope": pd.Series(dtype="string"),
            "manual_review_flag": pd.Series(dtype="bool"),
        }
    )


def merge_truth_label_rows(
    existing: pd.DataFrame,
    incoming: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """Replace only existing rows with the same player, season, and source.

    Labels from another source are deliberately retained: a market-value
    snapshot and a scouting decision can both be evidence for the same player.
    This operation is scoped enough for repeatable local imports while keeping
    the schema's duplicate-key invariant intact.
    """
    if incoming.empty:
        return existing.copy(), 0
    key_columns = ["player_id", "season", "label_source"]
    if any(column not in incoming.columns for column in key_columns):
        raise ValueError("Incoming truth labels are missing merge key columns")
    if existing.empty:
        return incoming.copy(), 0
    if any(column not in existing.columns for column in key_columns):
        raise ValueError("Existing truth labels are missing merge key columns")

    incoming_keys = pd.MultiIndex.from_frame(incoming[key_columns].astype("string"))
    existing_keys = pd.MultiIndex.from_frame(existing[key_columns].astype("string"))
    replace_mask = existing_keys.isin(incoming_keys)
    retained = existing.loc[~replace_mask].copy()
    combined = pd.concat([retained, incoming], ignore_index=True)
    return combined, int(replace_mask.sum())


def workspace_to_truth_labels(
    workspace: dict[str, Any],
    *,
    default_season: str = "",
    default_position_scope: str = "all",
) -> pd.DataFrame:
    """Convert a scouting workspace's review decisions to truth labels.

    Reads ``review.statuses`` (approved/rejected) and ``selections.shortlist``
    to build truth labels with ``label_source='scouting_review'``. Approved
    players get ``label_value=1.0`` (HIGH confidence), rejected get
    ``label_value=0.0`` (MEDIUM confidence). Players with only notes but no
    explicit decision are skipped — only explicit approved/rejected decisions
    become truth labels.

    The returned DataFrame follows ``TRUTH_LABELS_SCHEMA`` and can be
    validated with ``validate_truth_labels()``. Model prediction fields are
    never mixed in — this is a pure human-label extraction.
    """
    review = workspace.get("review") or {}
    selections = workspace.get("selections") or {}
    audit = workspace.get("audit") or {}
    source = workspace.get("source") or {}

    statuses: dict[str, str] = review.get("statuses") or {}
    shortlist: list[dict[str, Any]] = selections.get("shortlist") or []
    rating_snapshot_ids: list[str] = source.get("rating_snapshot_ids") or []

    # Resolve season from snapshot IDs or audit timestamp
    season = default_season
    if not season and rating_snapshot_ids:
        # Snapshot IDs may contain season info (e.g., "2425-run-xxx")
        for sid in rating_snapshot_ids:
            parts = str(sid).split("-")
            for part in parts:
                if len(part) == 4 and part.isdigit():
                    season = part
                    break
            if season:
                break

    as_of_date = str(audit.get("updated_at") or audit.get("created_at") or "")

    # Build player_id -> info map from shortlist
    player_info: dict[str, dict[str, Any]] = {}
    for row in shortlist:
        key = str(row.get("key") or row.get("player_id") or row.get("name") or "")
        if not key:
            continue
        player_info[key] = {
            "player_id": str(row.get("player_id") or key),
            "name": str(row.get("name") or ""),
        }

    records: list[dict[str, Any]] = []
    for key, status in statuses.items():
        if status not in ("approved", "rejected"):
            continue  # only explicit decisions become labels
        info = player_info.get(key, {})
        player_id = info.get("player_id", key)
        label_value = 1.0 if status == "approved" else 0.0
        if status == "approved":
            label_confidence = LabelConfidence.HIGH.value
        else:
            label_confidence = LabelConfidence.MEDIUM.value
        records.append({
            "player_id": player_id,
            "season": season,
            "label_source": LabelSource.SCOUTING_REVIEW.value,
            "label_confidence": label_confidence,
            "label_value": label_value,
            "as_of_date": as_of_date,
            "position_scope": default_position_scope,
            "manual_review_flag": True,
        })

    if not records:
        return create_empty_truth_labels()

    return pd.DataFrame(records, columns=TRUTH_LABELS_COLUMNS)

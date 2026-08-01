"""Typed evidence grain and missingness audit (PRS-1 R-006/R-007).

PRS-1 requires that every dataset declare what a row represents, what the
time window is, whether the value is observed/aggregated/proxy/estimated,
which fields are theoretically observable for that source, and why any
missing field is missing (``not_recorded`` / ``not_applicable`` /
``not_available`` / ``filtered`` / ``actual_zero``).

This module provides the typed vocabulary and a read-only audit that
classifies the current ``player_match.parquet`` and
``rating_feature_matrix.parquet`` rows into typed grain buckets and
assigns each feature-group missingness a best-evidence ``MissingReason``.

The audit is read-only and local. It never modifies artifacts, never
falls back to synthetic data, and never silently merges buckets: rows
whose ``data_granularity`` is not in the known map are reported as
``EvidenceGrain.UNKNOWN`` rather than guessed. The output is intended as
PRS-1 R-006/R-007 evidence inside ``research-health``, not as a
canonical schema enforcement — that comes in a later PRS-1 slice.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from scoutfootball.config import PlatformSettings

GRAIN_SCHEMA = "scoutfootball.grain-audit"
GRAIN_SCHEMA_VERSION = "1.0.0"


class EvidenceGrain(StrEnum):
    """What a single row of an artifact represents.

    Values mirror the ``data_granularity`` column vocabulary already
    written by ``pipeline.build_player_match`` and
    ``features.understat_history``. Rows whose ``data_granularity`` is
    not one of the known values are classified ``UNKNOWN`` so the audit
    surfaces the gap instead of silently bucketing them.
    """

    MATCH = "match"
    SEASON_PROXY = "season_proxy"
    AGGREGATE = "aggregate"
    UNKNOWN = "unknown"


class ObservationType(StrEnum):
    """How a row's values were produced (PRS-1 R-006 second bullet).

    ``OBSERVED``
        Direct measurement from a real match event or stat line.
    ``AGGREGATED``
        Multiple observations rolled up (e.g. season totals from real
        matches). Distinct from ``SEASON_PROXY`` grain because the
        underlying observations exist, just rolled up.
    ``PROXY``
        Season-level totals used as a stand-in for match-level evidence
        (the ``season_proxy`` grain case). The dominant case in the
        current local data: ~27.5k Understat/FBref season rows.
    ``ESTIMATED``
        Derived, imputed or model-output values (e.g. in-position
        median fill, model predictions).
    ``NOT_RECORDED``
        No observation exists; the row is structurally absent from the
        source.
    """

    OBSERVED = "observed"
    AGGREGATED = "aggregated"
    PROXY = "proxy"
    ESTIMATED = "estimated"
    NOT_RECORDED = "not_recorded"


class MissingReason(StrEnum):
    """Why a field is missing for a row (PRS-1 R-006 fifth bullet).

    ``NOT_RECORDED``
        The source could in principle supply this field but did not
        for this row (e.g. StatsBomb open-data match without the
        defensive line).
    ``NOT_APPLICABLE``
        The field cannot exist for this grain/source combination (e.g.
        xT/VAEP on a ``season_proxy`` row from FBref — event-level
        metrics have no season-aggregate value).
    ``NOT_AVAILABLE``
        The field was missing and was filled by an imputation step
        (e.g. in-position median). The current schema records this via
        ``{group}_missing`` marker columns written before imputation.
    ``FILTERED``
        The row was filtered out by an explicit pipeline rule (e.g.
        future-match placeholder rows dropped from football_data).
    ``ACTUAL_ZERO``
        The value is genuinely zero and must not be conflated with
        missing (e.g. 0 goals scored in a real match).
    ``UNKNOWN``
        The audit cannot classify the missingness from available
        evidence. Surfaces the gap instead of guessing.
    """

    NOT_RECORDED = "not_recorded"
    NOT_APPLICABLE = "not_applicable"
    NOT_AVAILABLE = "not_available"
    FILTERED = "filtered"
    ACTUAL_ZERO = "actual_zero"
    UNKNOWN = "unknown"


# Map the on-disk ``data_granularity`` string vocabulary to typed
# EvidenceGrain. Keys are the exact strings written by pipeline builders;
# unknown values fall through to ``EvidenceGrain.UNKNOWN`` via
# ``classify_grain``.
GRAIN_BY_DATA_GRANULARITY: dict[str, EvidenceGrain] = {
    EvidenceGrain.MATCH.value: EvidenceGrain.MATCH,
    EvidenceGrain.SEASON_PROXY.value: EvidenceGrain.SEASON_PROXY,
    EvidenceGrain.AGGREGATE.value: EvidenceGrain.AGGREGATE,
}


# Feature groups that require match-level event data and therefore have
# ``MissingReason.NOT_APPLICABLE`` on season-proxy rows (the value
# cannot exist for that grain, regardless of source). Mirrors
# ``features.rating_matrix.FIELD_GROUPS`` but kept as a local frozenset
# so the audit does not import the feature builder (and so a future
# rename of FIELD_GROUPS does not silently change audit semantics).
EVENT_LEVEL_GROUPS: frozenset[str] = frozenset(
    {
        "xT_VAEP",  # event-level action value
        "goalkeeper",  # match-level save/psxg data
    }
)

# Sources that supply event-level data in the current local snapshot.
# When a row from one of these sources is missing an event-level field,
# the reason is ``NOT_RECORDED`` (the source could have supplied it but
# did not for this row). For other sources, event-level fields are
# ``NOT_APPLICABLE`` regardless of grain (the source has no event-level
# coverage at all).
EVENT_LEVEL_SOURCES: frozenset[str] = frozenset(
    {
        "statsbomb_open",
    }
)


def classify_grain(data_granularity: Any) -> EvidenceGrain:
    """Return the typed ``EvidenceGrain`` for a row's ``data_granularity``.

    Unknown or missing values map to ``EvidenceGrain.UNKNOWN`` so the
    audit surfaces the gap instead of silently bucketing.
    """
    if data_granularity is None:
        return EvidenceGrain.UNKNOWN
    key = str(data_granularity).strip().lower()
    return GRAIN_BY_DATA_GRANULARITY.get(key, EvidenceGrain.UNKNOWN)


def classify_observation(grain: EvidenceGrain, source_name: Any) -> ObservationType:
    """Return the typed ``ObservationType`` for a (grain, source) pair.

    A ``MATCH`` row from an event-level source is ``OBSERVED``. A
    ``SEASON_PROXY`` row is ``PROXY`` by definition (season totals
    standing in for match-level evidence). An ``AGGREGATE`` row is
    ``AGGREGATED``. ``UNKNOWN`` grain maps to ``NOT_RECORDED`` because
    we cannot claim an observation exists for an unclassified row.
    """
    if grain == EvidenceGrain.MATCH:
        return ObservationType.OBSERVED
    if grain == EvidenceGrain.SEASON_PROXY:
        return ObservationType.PROXY
    if grain == EvidenceGrain.AGGREGATE:
        return ObservationType.AGGREGATED
    return ObservationType.NOT_RECORDED


def classify_missing_reason(
    *,
    grain: EvidenceGrain,
    source_name: Any,
    group_name: str,
    has_missing_marker: bool,
) -> MissingReason:
    """Return the best-evidence ``MissingReason`` for a missing field group.

    The classifier is intentionally conservative: when the available
    evidence does not disambiguate, it returns ``UNKNOWN`` rather than
    guessing. Callers (UI, training, exports) are expected to treat
    ``UNKNOWN`` as "do not silently fill or interpret".

    Parameters
    ----------
    grain:
        Typed grain of the row (from ``classify_grain``).
    source_name:
        Raw ``source_name`` column value for the row.
    group_name:
        Feature group name from ``FIELD_GROUPS`` (e.g. ``defense``,
        ``xT_VAEP``).
    has_missing_marker:
        Whether the row's ``{group}_missing`` marker column is True.
        When True, the field was missing before imputation and was
        filled — this maps to ``NOT_AVAILABLE`` unless a stronger
        reason applies.
    """
    source_key = _normalize_source(source_name)

    # When grain is UNKNOWN we cannot distinguish "not_recorded" (a
    # match-level row from an event-level source that simply did not
    # supply the field) from "not_applicable" (a season-proxy row where
    # the field cannot exist). Returning UNKNOWN here is honest: the
    # audit surfaces the missing grain information rather than guessing
    # the dominant case. This is the situation the current
    # ``rating_feature_matrix.parquet`` exposes, because it does not
    # carry ``data_granularity``/``source_name`` forward from
    # ``player_match.parquet`` — a gap a later PRS-1 slice will close.
    if group_name in EVENT_LEVEL_GROUPS and grain == EvidenceGrain.UNKNOWN:
        return MissingReason.UNKNOWN

    # Event-level groups on non-event-level rows cannot have a value:
    # xT/VAEP and goalkeeper match-level metrics have no season-aggregate
    # equivalent. This is structural, not a recording gap.
    if group_name in EVENT_LEVEL_GROUPS and grain != EvidenceGrain.MATCH:
        return MissingReason.NOT_APPLICABLE

    # Event-level groups on event-level sources that are missing were
    # not recorded for that specific row (the source could have supplied
    # them but did not — e.g. a StatsBomb match without the defensive
    # line, or a row outside the 3-match open-data sample).
    if (
        group_name in EVENT_LEVEL_GROUPS
        and grain == EvidenceGrain.MATCH
        and source_key in EVENT_LEVEL_SOURCES
    ):
        return MissingReason.NOT_RECORDED

    # Event-level groups on non-event-level sources are not applicable
    # at the source level (the source has no event coverage at all).
    if (
        group_name in EVENT_LEVEL_GROUPS
        and source_key not in EVENT_LEVEL_SOURCES
        and source_key != ""
    ):
        return MissingReason.NOT_APPLICABLE

    # If the row has an explicit ``{group}_missing=True`` marker, the
    # field was missing pre-imputation and was filled — the value the
    # consumer sees is imputed, not observed. This is the strongest
    # signal the current schema exposes.
    if has_missing_marker:
        return MissingReason.NOT_AVAILABLE

    # Remaining missingness on non-event-level groups (e.g. defense on
    # a season-proxy row) is best classified as ``NOT_RECORDED``: the
    # source could in principle aggregate the field but did not.
    if grain in (EvidenceGrain.MATCH, EvidenceGrain.SEASON_PROXY):
        return MissingReason.NOT_RECORDED

    return MissingReason.UNKNOWN


def _normalize_source(source_name: Any) -> str:
    if source_name is None:
        return ""
    return str(source_name).strip().lower()


def _player_match_path(settings: PlatformSettings):
    return settings.gold_root / "feature_store" / "player_match.parquet"


def _feature_matrix_path(settings: PlatformSettings):
    return settings.gold_root / "feature_store" / "rating_feature_matrix.parquet"


def build_grain_and_missingness_report(
    settings: PlatformSettings | None = None,
) -> dict[str, Any]:
    """Build a typed grain + missingness audit for the rating artifacts.

    Read-only and local. Reads ``player_match.parquet`` for per-row
    grain/source distribution and ``rating_feature_matrix.parquet`` for
    per-feature-group missingness breakdown. A missing or unreadable
    file is reported as ``unavailable`` rather than silently replaced.

    The report has three sections:

    ``player_match_grain``
        Per-row grain distribution with typed ``EvidenceGrain`` values,
        cross-tabbed by ``source_name``. Rows whose ``data_granularity``
        is not in the known map surface as ``unknown``.

    ``observation_type``
        Per-row ``ObservationType`` distribution derived from grain and
        source. Lets the maintainer see at a glance how much of the
        current data is ``observed`` vs ``proxy``.

    ``feature_group_missingness``
        Per-feature-group missingness breakdown by ``(grain, source)``
        bucket, with typed ``MissingReason`` for each bucket. Lets the
        maintainer verify that ``unknown`` and ``actual_zero`` are
        distinguishable from ``not_recorded`` and ``not_applicable``.
    """
    resolved = settings or PlatformSettings.from_root()

    pm_report = _audit_player_match_grain(resolved)
    fm_report = _audit_feature_matrix_missingness(resolved)

    return {
        "schema": GRAIN_SCHEMA,
        "schema_version": GRAIN_SCHEMA_VERSION,
        "player_match_grain": pm_report,
        "feature_group_missingness": fm_report,
        "limitations": [
            (
                "Read-only local audit; does not modify artifacts. "
                "MissingReason assignment is best-evidence from the "
                "current schema (data_granularity, source_name, "
                "{group}_missing markers). Future PRS-1 slices will "
                "add canonical schema enforcement."
            ),
            (
                "Rows whose data_granularity is not in the known map "
                "are reported as EvidenceGrain.UNKNOWN rather than "
                "guessed; this surfaces grain-vocabulary drift."
            ),
            (
                "MissingReason.ACTUAL_ZERO is partially auto-detected: "
                "the audit counts event-level fields that are exactly 0 "
                "on match-grain rows from event-level sources (where "
                "the 0 can be trusted as a true observation rather than "
                "an imputed value) and reports them as "
                "``actual_zero_rows`` in each bucket. Detection does "
                "not cover season-proxy or aggregate rows, where a 0 "
                "may still be an aggregation artefact or imputation "
                "result; those remain classified by their "
                "{group}_missing marker."
            ),
        ],
    }


def _audit_player_match_grain(settings: PlatformSettings) -> dict[str, Any]:
    """Per-row grain distribution in ``player_match.parquet``."""
    path = _player_match_path(settings)
    if not path.exists():
        return {"status": "unavailable", "evidence": {"reason": "player_match.parquet missing"}}

    try:
        import pandas as pd

        df = pd.read_parquet(path)
    except Exception as exc:  # read-only diagnostic; never raise
        return {
            "status": "unavailable",
            "evidence": {"reason": f"read failed: {exc}"},
        }

    total_rows = int(len(df))
    if total_rows == 0:
        return {"status": "unavailable", "evidence": {"reason": "player_match has 0 rows"}}

    has_grain_col = "data_granularity" in df.columns
    has_source_col = "source_name" in df.columns

    grain_counts: dict[str, int] = {}
    unknown_grain_values: list[str] = []
    if has_grain_col:
        for raw_value, count in df["data_granularity"].value_counts(dropna=False).items():
            typed = classify_grain(raw_value)
            grain_counts[typed.value] = grain_counts.get(typed.value, 0) + int(count)
            if typed == EvidenceGrain.UNKNOWN:
                unknown_grain_values.append(str(raw_value))
    else:
        grain_counts[EvidenceGrain.UNKNOWN.value] = total_rows
        unknown_grain_values.append("column_missing")

    # Cross-tab grain × source so the maintainer can see which sources
    # contribute which grain (e.g. statsbomb_open -> match, fbref/understat
    # -> season_proxy). Rows with unknown grain are kept in the cross-tab
    # so drift is visible per-source, not just in the total.
    grain_by_source: dict[str, dict[str, int]] = {}
    if has_grain_col and has_source_col:
        for (raw_grain, raw_source), count in (
            df.groupby(["data_granularity", "source_name"], dropna=False).size().items()
        ):
            typed = classify_grain(raw_grain)
            source_key = _normalize_source(raw_source) or "unknown"
            grain_by_source.setdefault(source_key, {})
            grain_by_source[source_key][typed.value] = (
                grain_by_source[source_key].get(typed.value, 0) + int(count)
            )
    elif has_source_col:
        for raw_source, count in df["source_name"].value_counts(dropna=False).items():
            source_key = _normalize_source(raw_source) or "unknown"
            grain_by_source[source_key] = {
                EvidenceGrain.UNKNOWN.value: int(count)
            }

    # Observation type distribution: derived from grain + source.
    observation_counts: dict[str, int] = {}
    if has_grain_col and has_source_col:
        for (raw_grain, raw_source), count in (
            df.groupby(["data_granularity", "source_name"], dropna=False).size().items()
        ):
            typed = classify_grain(raw_grain)
            obs = classify_observation(typed, raw_source)
            observation_counts[obs.value] = (
                observation_counts.get(obs.value, 0) + int(count)
            )
    elif has_grain_col:
        for raw_grain, count in df["data_granularity"].value_counts(dropna=False).items():
            typed = classify_grain(raw_grain)
            obs = classify_observation(typed, None)
            observation_counts[obs.value] = (
                observation_counts.get(obs.value, 0) + int(count)
            )
    else:
        observation_counts[ObservationType.NOT_RECORDED.value] = total_rows

    return {
        "status": "ok",
        "evidence": {
            "total_rows": total_rows,
            "has_data_granularity_column": has_grain_col,
            "has_source_name_column": has_source_col,
            "grain_counts": grain_counts,
            "grain_by_source": grain_by_source,
            "observation_type_counts": observation_counts,
            "unknown_grain_values": sorted(set(unknown_grain_values)),
        },
    }


def _audit_feature_matrix_missingness(settings: PlatformSettings) -> dict[str, Any]:
    """Per-feature-group missingness breakdown by (grain, source) bucket."""
    path = _feature_matrix_path(settings)
    if not path.exists():
        return {
            "status": "unavailable",
            "evidence": {"reason": "rating_feature_matrix.parquet missing"},
        }

    try:
        import pandas as pd

        from scoutfootball.features.rating_matrix import FIELD_GROUPS

        df = pd.read_parquet(path)
    except Exception as exc:  # read-only diagnostic; never raise
        return {
            "status": "unavailable",
            "evidence": {"reason": f"read failed: {exc}"},
        }

    total_rows = int(len(df))
    if total_rows == 0:
        return {
            "status": "unavailable",
            "evidence": {"reason": "rating_feature_matrix has 0 rows"},
        }

    # The feature matrix may or may not carry data_granularity/source_name
    # forward from player_match. When present, we can bucket missingness
    # by (grain, source); when absent, we fall back to whole-matrix
    # missingness with UNKNOWN reason for unclassified rows.
    has_grain_col = "data_granularity" in df.columns
    has_source_col = "source_name" in df.columns

    # Build the bucket key for each row. Even when columns are absent we
    # still produce a single "unclassified" bucket so the per-group
    # missingness counts are complete.
    if has_grain_col and has_source_col:
        df = df.assign(
            _bucket_grain=df["data_granularity"].map(classify_grain),
            _bucket_source=df["source_name"].map(_normalize_source),
        )
    elif has_grain_col:
        df = df.assign(
            _bucket_grain=df["data_granularity"].map(classify_grain),
            _bucket_source="unknown",
        )
    elif has_source_col:
        df = df.assign(
            _bucket_grain=EvidenceGrain.UNKNOWN,
            _bucket_source=df["source_name"].map(_normalize_source),
        )
    else:
        df = df.assign(
            _bucket_grain=EvidenceGrain.UNKNOWN,
            _bucket_source="unknown",
        )

    groups: dict[str, Any] = {}
    for group_name, field_list in FIELD_GROUPS.items():
        present_fields = [f for f in field_list if f in df.columns]
        missing_marker = f"{group_name}_missing"
        marker_present = missing_marker in df.columns

        # Per-bucket missingness: a row is "missing" for this group when
        # all present fields are NaN (matches ``mark_missing_fields``
        # semantics) OR the ``{group}_missing`` marker is True.
        if present_fields:
            row_group_missing = df[present_fields].isna().all(axis=1)
        else:
            # No fields from this group are in the matrix at all: every
            # row is missing the group. This is a schema gap, not a
            # per-row missingness.
            row_group_missing = df.assign(_all=True)["_all"]

        if marker_present:
            row_group_missing = row_group_missing | df[missing_marker].astype(bool)

        bucket_breakdown: dict[str, dict[str, Any]] = {}
        for (grain, source), sub in df.groupby(["_bucket_grain", "_bucket_source"]):
            bucket_key = f"{grain.value}|{source or 'unknown'}"
            missing_mask = row_group_missing.loc[sub.index]
            missing_count = int(missing_mask.sum())
            bucket_total = int(len(sub))

            # Detect ACTUAL_ZERO: event-level fields on match-level rows
            # from event-level sources where all present fields are 0
            # (not NaN) and the row was not marked as missing. This
            # distinguishes "player genuinely did 0 of this action in
            # this match" from "field was missing and filled to 0 by
            # imputation". Only applies to event-level groups on
            # match-grain rows from event-level sources, because only
            # there can we trust a 0 to be a true observation rather
            # than an aggregated or imputed value.
            actual_zero_count = 0
            if (
                group_name in EVENT_LEVEL_GROUPS
                and grain == EvidenceGrain.MATCH
                and (source or "") in EVENT_LEVEL_SOURCES
                and present_fields
            ):
                # Rows that are NOT missing (marker False or absent).
                non_missing_mask = ~missing_mask
                if marker_present:
                    non_missing_mask = non_missing_mask & (
                        ~df.loc[sub.index, missing_marker].astype(bool)
                    )
                # Among non-missing rows, count those where all present
                # fields are exactly 0. NaN is not 0, so missing values
                # do not inflate the count.
                sub_fields = df.loc[sub.index, present_fields]
                all_zero = (sub_fields == 0).all(axis=1) & sub_fields.notna().all(axis=1)
                actual_zero_count = int((non_missing_mask & all_zero).sum())

            reason: MissingReason
            if missing_count == 0:
                # No missing rows in this bucket — nothing to classify.
                # Keep the entry so consumers can see coverage is full.
                reason = MissingReason.NOT_RECORDED  # placeholder, not surfaced
            else:
                # Pick a representative row to classify. The reason is
                # bucket-level: when the (grain, source, group) triple
                # is consistent, all missing rows in the bucket share
                # the same reason.
                reason = classify_missing_reason(
                    grain=grain,
                    source_name=source,
                    group_name=group_name,
                    has_missing_marker=bool(marker_present),
                )

            bucket_breakdown[bucket_key] = {
                "grain": grain.value,
                "source": source or "unknown",
                "bucket_rows": bucket_total,
                "missing_rows": missing_count,
                "missing_rate": round(missing_count / bucket_total, 4) if bucket_total else 0.0,
                "missing_reason": reason.value if missing_count > 0 else None,
                "actual_zero_rows": actual_zero_count,
            }

        groups[group_name] = {
            "fields_present": present_fields,
            "fields_missing_from_schema": [
                f for f in field_list if f not in df.columns
            ],
            "missing_marker_column": missing_marker if marker_present else None,
            "bucket_breakdown": bucket_breakdown,
        }

    return {
        "status": "ok",
        "evidence": {
            "total_rows": total_rows,
            "has_data_granularity_column": has_grain_col,
            "has_source_name_column": has_source_col,
            "field_groups": groups,
        },
    }

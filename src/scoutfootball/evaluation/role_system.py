"""Role family vocabulary and audit (PRS-1 R-009 role system v1).

PRS-1 requires a role system v1 that can carry PRS-2 in-role baseline
slicing. The project plan (``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md``
§6.2) specifies a three-layer structure (position family + role tag +
task characteristic), but the v1 scope is only the **position family**
layer: a typed vocabulary of 8 families (GK/CB/FB/DM/CM/AM/W/ST) plus
a default classifier that maps the existing ``position_group`` column
to a ``RoleFamily``.

This module is read-only and side-effect-free. It does **not**:

- Auto-invent DM labels for players whom the source labelled ``MF``.
  The honest default is ``CM``; a future slice may add a
  behaviour-based suggestion tool (mirroring ``identity_suggest``),
  but v1 only exposes the vocabulary and the audit so the maintainer
  can see at a glance how many players fall into each family and how
  many are still on a coarse ``DF``/``MF``/``FW`` label.
- Modify ``player_match.parquet`` or ``rating_feature_matrix.parquet``.
  The existing ``position_group`` column is preserved as-is; downstream
  code that needs a typed role calls ``classify_role_family`` on the
  derived view.
- Replace ``evaluation.position_metrics.POSITION_GROUP_MAP``. That map
  is the optimizer chain's internal translation and is preserved for
  backwards compatibility. ``RoleFamily`` is the PRS-facing vocabulary
  that future PRS-2 in-role baseline slices will consume.

Why a new enum instead of reusing the optimizer's ``POSITIONS`` list:
the optimizer list lives in ``scripts/optimizer/constants.py`` (a
script namespace, not importable from ``src/scoutfootball``) and is
shaped as a plain ``list[str]``. PRS-2/PRS-3 code under
``src/scoutfootball`` needs a typed, hashable, importable vocabulary
with an explicit ``UNKNOWN`` sentinel for unmapped values — that is
what ``RoleFamily`` provides.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from scoutfootball.config import PlatformSettings

ROLE_SYSTEM_SCHEMA = "scoutfootball.role-system"
ROLE_SYSTEM_VERSION = "1.0.0"

# Families deliberately mirror the optimizer-side 8-role list (GK/CB/FB/
# DM/CM/AM/W/ST) so PRS-2 in-role baselines can reuse existing dimension
# priors and caps without renaming. UNKNOWN is the honest sentinel for
# rows whose position_group is missing, blank, or outside the known
# vocabulary — the audit never guesses.


class RoleFamily(StrEnum):
    """Typed position family vocabulary for PRS-1 role system v1.

    Values are stable strings (not enum members) so they serialise
    directly to JSON and can be persisted in parquet without a custom
    codec. ``UNKNOWN`` is the catch-all for missing or unmapped
    ``position_group`` values — the audit reports how many rows land
    there rather than silently bucketing them as ``CM``.
    """

    GK = "GK"
    CB = "CB"
    FB = "FB"
    DM = "DM"
    CM = "CM"
    AM = "AM"
    W = "W"
    ST = "ST"
    UNKNOWN = "UNKNOWN"


# Source ``position_group`` values seen in Understat/FBref/StatsBomb
# output. Coarse families DF/MF/FW are mapped to a default fine role
# (CB/CM/ST) because the source did not provide enough information to
# pick a finer role. The audit surfaces the coarse count so the
# maintainer knows how many players would benefit from a future
# behaviour-based role suggestion tool.
POSITION_TO_ROLE: dict[str, RoleFamily] = {
    "GK": RoleFamily.GK,
    "DF": RoleFamily.CB,
    "MF": RoleFamily.CM,
    "FW": RoleFamily.ST,
    "CB": RoleFamily.CB,
    "FB": RoleFamily.FB,
    "DM": RoleFamily.DM,
    "CM": RoleFamily.CM,
    "AM": RoleFamily.AM,
    "W": RoleFamily.W,
    "ST": RoleFamily.ST,
}

# Coarse source labels that collapse to a default fine role. Surfaced
# in the audit as a data-quality signal: a high coarse count means
# many players would benefit from a future behaviour-based role
# suggestion tool, but v1 does not guess.
COARSE_POSITION_LABELS: frozenset[str] = frozenset({"DF", "MF", "FW"})


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_role_family(position_group: Any) -> RoleFamily:
    """Classify a ``position_group`` value into a typed ``RoleFamily``.

    Rules (in order):
    1. ``None`` / NaN / empty / whitespace-only → ``UNKNOWN``.
    2. Uppercased stripped value in ``POSITION_TO_ROLE`` → mapped role.
       Coarse labels (``DF``/``MF``/``FW``) are deliberately included
       here so the caller gets a usable default role, but the audit
       also counts how many rows used a coarse label so the gap is
       visible.
    3. Any other value → ``UNKNOWN``. The audit surfaces the raw value
       so the maintainer can see vocabulary drift rather than silently
       bucketing it as ``CM``.
    """
    if position_group is None:
        return RoleFamily.UNKNOWN
    # pandas NaN is a float; bools are not valid position labels.
    if isinstance(position_group, bool):
        return RoleFamily.UNKNOWN
    if isinstance(position_group, float):
        if position_group != position_group:  # NaN guard
            return RoleFamily.UNKNOWN
        if position_group.is_integer():
            return RoleFamily.UNKNOWN
        return RoleFamily.UNKNOWN
    key = str(position_group).strip().upper()
    if not key:
        return RoleFamily.UNKNOWN
    return POSITION_TO_ROLE.get(key, RoleFamily.UNKNOWN)


def _player_match_path(settings: PlatformSettings):
    return settings.gold_root / "feature_store" / "player_match.parquet"


def _read_player_match(settings: PlatformSettings):
    """Read player_match.parquet; return (df, error_message)."""
    path = _player_match_path(settings)
    if not path.exists():
        return None, "player_match.parquet missing"
    try:
        import pandas as pd

        df = pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001 — read-only diagnostic
        return None, f"player_match.parquet read failed: {exc}"
    if df is None or len(df) == 0:
        return None, "player_match.parquet has 0 rows"
    return df, None


def build_role_system_report(
    settings: PlatformSettings | None = None,
) -> dict[str, Any]:
    """Read-only audit of role family distribution in ``player_match``.

    Reads ``player_match.parquet`` and reports:
    - Raw ``position_group`` value distribution (counts per distinct
      value, including NaN/blank).
    - ``RoleFamily`` distribution after applying
      ``classify_role_family``.
    - ``coarse_position_rows``: how many rows still carry a coarse
      ``DF``/``MF``/``FW`` label. These rows get a default fine role
      (CB/CM/ST) but are flagged because the source did not provide
      enough information to pick a finer role.
    - ``unknown_position_rows``: how many rows have a ``position_group``
      that is missing, blank, or outside the known vocabulary.

    The report never raises — on any read failure it returns
    ``status=unavailable`` with the reason in ``evidence``. An
    all-unknown result is ``status=ok`` because unknown is the honest
    default, not a failure.
    """
    resolved = settings or PlatformSettings.from_root()
    df, error = _read_player_match(resolved)
    if df is None:
        return {
            "schema": ROLE_SYSTEM_SCHEMA,
            "schema_version": ROLE_SYSTEM_VERSION,
            "generated_at": _now(),
            "status": "unavailable",
            "evidence": {"reason": error},
        }

    total_rows = int(len(df))
    if "position_group" not in df.columns:
        return {
            "schema": ROLE_SYSTEM_SCHEMA,
            "schema_version": ROLE_SYSTEM_VERSION,
            "generated_at": _now(),
            "status": "ok",
            "evidence": {
                "total_rows": total_rows,
                "position_group_present": False,
                "raw_distribution": {},
                "role_family_distribution": {
                    RoleFamily.UNKNOWN.value: total_rows,
                },
                "coarse_position_rows": 0,
                "unknown_position_rows": total_rows,
                "distinct_unknown_values": 0,
            },
            "limitations": _LIMITATIONS,
        }

    # Raw distribution: count each distinct position_group value,
    # including NaN. We use keepna=True so NaN rows are visible rather
    # than silently dropped.
    import pandas as pd

    raw_counts = df["position_group"].value_counts(dropna=False)
    raw_distribution: dict[str, int] = {}
    for value, count in raw_counts.items():
        # NaN/None keys are not JSON-serialisable; use sentinel strings.
        if pd.isna(value):
            key = "<NaN>"
        elif value is None:
            key = "<None>"
        else:
            key = str(value)
        raw_distribution[key] = int(count)

    # Role family distribution: apply classify_role_family to each row.
    role_families = df["position_group"].apply(classify_role_family)
    role_counts = role_families.value_counts()
    role_distribution: dict[str, int] = {}
    for family in RoleFamily:
        role_distribution[family.value] = int(role_counts.get(family, 0))

    # Coarse position rows: rows whose position_group is one of
    # DF/MF/FW. These get a default fine role but are flagged.
    pg_series = df["position_group"]
    coarse_mask = pg_series.apply(
        lambda v: (
            isinstance(v, str)
            and v.strip().upper() in COARSE_POSITION_LABELS
        )
    )
    coarse_rows = int(coarse_mask.sum())

    # Unknown position rows: rows whose RoleFamily is UNKNOWN.
    unknown_mask = role_families.apply(lambda f: f == RoleFamily.UNKNOWN)
    unknown_rows = int(unknown_mask.sum())

    # Distinct raw values that mapped to UNKNOWN (excluding NaN/blank
    # which are structural rather than vocabulary drift).
    unknown_values: set[str] = set()
    for value in pg_series[unknown_mask].dropna().unique():
        if isinstance(value, str):
            stripped = value.strip()
            if stripped and stripped.upper() not in POSITION_TO_ROLE:
                unknown_values.add(stripped)

    return {
        "schema": ROLE_SYSTEM_SCHEMA,
        "schema_version": ROLE_SYSTEM_VERSION,
        "generated_at": _now(),
        "status": "ok",
        "evidence": {
            "total_rows": total_rows,
            "position_group_present": True,
            "raw_distribution": raw_distribution,
            "role_family_distribution": role_distribution,
            "coarse_position_rows": coarse_rows,
            "unknown_position_rows": unknown_rows,
            "distinct_unknown_values": len(unknown_values),
            "unknown_value_samples": sorted(unknown_values)[:20],
        },
        "limitations": _LIMITATIONS,
    }


_LIMITATIONS: list[str] = [
    (
        "Read-only local audit; does not modify player_match.parquet "
        "or rating_feature_matrix.parquet. RoleFamily is derived from "
        "the existing position_group column on each call."
    ),
    (
        "Coarse source labels DF/MF/FW are mapped to default fine "
        "roles (CB/CM/ST) so downstream code gets a usable family, "
        "but coarse_position_rows flags how many players would "
        "benefit from a future behaviour-based role suggestion tool. "
        "v1 does not auto-invent DM labels from MF players."
    ),
    (
        "RoleFamily.UNKNOWN rows have a position_group that is "
        "missing, blank, or outside the known vocabulary. The audit "
        "surfaces distinct_unknown_values so the maintainer can see "
        "vocabulary drift rather than silently bucketing unknowns as "
        "CM."
    ),
    (
        "v1 does not include a role override registry (mirroring "
        "identity_registry). A future PRS slice may add an append-"
        "only ledger of explicit (source_name, source_player_id) -> "
        "role_family decisions so the maintainer can correct "
        "mis-classified players without waiting for a source label "
        "change."
    ),
    (
        "position_metrics.POSITION_GROUP_MAP (optimizer chain) and "
        "RoleFamily (PRS-facing vocabulary) are deliberately separate "
        "in v1 to avoid breaking the optimizer. A future slice may "
        "unify them once PRS-2 in-role baseline proves the new "
        "vocabulary works end-to-end."
    ),
]


__all__ = [
    "COARSE_POSITION_LABELS",
    "POSITION_TO_ROLE",
    "ROLE_SYSTEM_SCHEMA",
    "ROLE_SYSTEM_VERSION",
    "RoleFamily",
    "build_role_system_report",
    "classify_role_family",
]

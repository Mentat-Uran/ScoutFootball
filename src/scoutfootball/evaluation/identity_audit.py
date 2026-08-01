"""Canonical identity risk audit for the player rating research system.

PRS-1 R-005 (see ``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md``) requires that
canonical ``player_id`` runs through every rating artifact. Before migrating to
a canonical ID, the maintainer must see the current identity risk surface:

- which ``player_id`` formats are in use and from which source;
- where the same display name maps to multiple ``player_id`` values (potential
  same-name conflicts or cross-source alignment gaps);
- where a single player-season spans multiple teams (transfer records);
- where the same display name appears under different source-specific ID
  formats and therefore cannot be joined without an explicit identity decision.

This module is read-only. It does **not** resolve conflicts, merge identities,
or modify any artifact. Every risk is reported as evidence for the maintainer's
human review; unresolved status is the honest default.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from scoutfootball.config import PlatformSettings

IDENTITY_AUDIT_SCHEMA = "scoutfootball.identity-audit"
IDENTITY_AUDIT_VERSION = "1.0.0"

# Risk status vocabulary.
RISK_PRESENT = "present"
RISK_ABSENT = "absent"
RISK_UNAVAILABLE = "unavailable"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _player_match_path(settings: PlatformSettings):
    return settings.gold_root / "feature_store" / "player_match.parquet"


def _classify_player_id_format(player_id: str) -> str:
    """Classify a player_id string into a source-stable format family.

    Formats observed in the current data:

    - ``understat|<id>`` — Understat source ID, stable within source.
    - ``<name>|<year>|<country>`` — FBref-derived name+birthyear+nationality
      composite; stable per source but not a canonical person ID.
    - ``<numeric>`` or ``<numeric>.0`` — StatsBomb-derived numeric ID stored
      as string; stable within source.
    - ``unknown`` — empty, NaN-like, or unrecognised format.

    The classification is intentionally conservative: it only groups IDs by
    structural format so the audit can report cross-format alignment risk. It
    does not claim any format is a canonical person identifier.
    """
    if not isinstance(player_id, str) or not player_id:
        return "unknown"
    if "|" in player_id:
        prefix = player_id.split("|", 1)[0]
        if prefix == "understat":
            return "understat_pipe_id"
        # FBref composite uses name|year|country; the first segment is a
        # display name (lowercased), not a source ID.
        if prefix.isalpha() or " " in prefix:
            return "fbref_name_composite"
        return "other_pipe_delimited"
    # StatsBomb IDs are numeric strings, sometimes stored as "10605.0" when
    # pipeline code coerced a float to str.
    stripped = player_id.rstrip("0").rstrip(".")
    if stripped.isdigit():
        return "statsbomb_numeric"
    return "unknown"


def _read_player_match(settings: PlatformSettings):
    """Read player_match.parquet; return (df, error_message).

    On any read failure returns (None, message) so the audit report can mark
    itself unavailable rather than silently produce an empty report.
    """
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
    required = ("player_id", "player_name", "source_name", "season_id")
    missing = [c for c in required if c not in df.columns]
    if missing:
        return None, f"player_match.parquet missing required columns: {missing}"
    return df, None


def _build_id_format_distribution(df) -> dict[str, Any]:
    """Count rows and distinct players per player_id format family."""
    df = df.copy()
    df["_format"] = df["player_id"].astype(str).map(_classify_player_id_format)
    by_format: dict[str, dict[str, int]] = {}
    grouped = df.groupby("_format")
    for fmt, group in grouped:
        by_format[fmt] = {
            "row_count": int(len(group)),
            "distinct_player_id": int(group["player_id"].nunique()),
        }
    # Cross-tabulate format by source_name so the maintainer can see which
    # sources produce which ID formats.
    format_by_source: dict[str, dict[str, int]] = {}
    for (src, fmt), group in df.groupby(["source_name", "_format"]):
        format_by_source.setdefault(str(src), {})[fmt] = int(len(group))
    return {
        "status": RISK_PRESENT if len(by_format) > 1 else RISK_ABSENT,
        "evidence": {
            "formats": by_format,
            "format_by_source": format_by_source,
            "reason": (
                "multiple player_id formats in use; cross-source join requires "
                "explicit identity resolution"
                if len(by_format) > 1
                else "single player_id format in use"
            ),
        },
    }


def _build_same_name_different_id(df) -> dict[str, Any]:
    """Find player_name values that map to multiple player_id values.

    This is the primary same-name risk signal: the same display name appears
    under different IDs. This can mean (a) two different players share a name,
    or (b) the same player is recorded under source-specific IDs and has not
    been canonicalised. The audit cannot distinguish these cases without human
    review, so every match is reported as an unresolved risk.
    """
    # Normalise player_name to string; some sources may store NaN.
    name_to_ids = (
        df.dropna(subset=["player_name", "player_id"])
        .assign(player_name=lambda x: x["player_name"].astype(str))
        .groupby("player_name")["player_id"]
        .nunique()
    )
    risky = name_to_ids[name_to_ids > 1]
    samples: list[dict[str, Any]] = []
    for name, count in risky.head(50).items():
        ids = (
            df[df["player_name"].astype(str) == name]["player_id"]
            .drop_duplicates()
            .tolist()
        )
        samples.append(
            {
                "player_name": str(name),
                "distinct_player_id_count": int(count),
                "player_id_samples": [str(i) for i in ids[:5]],
            }
        )
    return {
        "status": RISK_PRESENT if len(risky) > 0 else RISK_ABSENT,
        "evidence": {
            "risky_name_count": int(len(risky)),
            "sample_count": int(len(samples)),
            "samples": samples,
            "reason": (
                f"{len(risky)} player_name value(s) map to multiple player_id; "
                "each may be a same-name conflict or an unresolved cross-source "
                "alignment gap"
                if len(risky) > 0
                else "every player_name maps to exactly one player_id"
            ),
        },
    }


def _build_multi_team_season(df) -> dict[str, Any]:
    """Report transfer records (multi_team_season=True).

    These are player-seasons where the player appeared for multiple teams in
    the same season. They are not errors, but they require explicit aggregation
    rules in any canonical view (player-team-season vs player-season).
    """
    if "multi_team_season" not in df.columns:
        return {
            "status": RISK_UNAVAILABLE,
            "evidence": {"reason": "multi_team_season column absent"},
        }
    flag_col = df["multi_team_season"]
    # pandas may store the flag as nullable boolean; treat NA as False.
    flag_filled = flag_col.fillna(False).astype(bool)
    transfer_rows = df[flag_filled]
    distinct_players = (
        int(transfer_rows["player_id"].nunique()) if len(transfer_rows) > 0 else 0
    )
    samples: list[dict[str, Any]] = []
    if len(transfer_rows) > 0:
        for _, group in transfer_rows.head(20).groupby("player_id"):
            samples.append(
                {
                    "player_id": str(group["player_id"].iloc[0]),
                    "player_name": str(group["player_name"].iloc[0]),
                    "season_id": str(group["season_id"].iloc[0]),
                    "team_names": [str(t) for t in group["team_name"].unique()[:5]],
                    "row_count": int(len(group)),
                }
            )
    return {
        "status": RISK_PRESENT if len(transfer_rows) > 0 else RISK_ABSENT,
        "evidence": {
            "transfer_row_count": int(len(transfer_rows)),
            "distinct_player_count": distinct_players,
            "sample_count": int(len(samples)),
            "samples": samples,
            "reason": (
                f"{len(transfer_rows)} row(s) flagged multi_team_season=True; "
                "transfer records require explicit player-team-season vs "
                "player-season aggregation rules"
                if len(transfer_rows) > 0
                else "no multi-team-season records"
            ),
        },
    }


def _build_cross_source_alignment_risk(df) -> dict[str, Any]:
    """Report player_name values that appear under multiple source_name values.

    When the same display name appears in e.g. both fbref and understat, the
    underlying person is likely the same, but the player_id will differ
    (fbref uses name|year|country, understat uses understat|<id>). Without an
    explicit identity registry, any join across sources will silently
    double-count or miss the player.
    """
    name_source = (
        df.dropna(subset=["player_name", "source_name"])
        .assign(player_name=lambda x: x["player_name"].astype(str))
        .groupby("player_name")["source_name"]
        .nunique()
    )
    risky = name_source[name_source > 1]
    samples: list[dict[str, Any]] = []
    for name in risky.head(30).index:
        subset = df[df["player_name"].astype(str) == name]
        samples.append(
            {
                "player_name": str(name),
                "source_names": [str(s) for s in subset["source_name"].unique()],
                "player_id_samples": [
                    str(i) for i in subset["player_id"].drop_duplicates().tolist()[:5]
                ],
            }
        )
    return {
        "status": RISK_PRESENT if len(risky) > 0 else RISK_ABSENT,
        "evidence": {
            "risky_name_count": int(len(risky)),
            "sample_count": int(len(samples)),
            "samples": samples,
            "reason": (
                f"{len(risky)} player_name value(s) appear under multiple "
                "sources; cross-source join requires explicit identity registry"
                if len(risky) > 0
                else "no player_name spans multiple sources"
            ),
        },
    }


def build_identity_audit_report(
    settings: PlatformSettings | None = None,
) -> dict[str, Any]:
    """Build a read-only canonical identity risk audit report.

    PRS-1 R-005: before canonical player_id can run through the rating system,
    the maintainer must see the current identity risk surface. This report
    scans ``player_match.parquet`` and surfaces four risk dimensions:

    1. ``id_format_distribution`` — how many player_id formats are in use and
       which sources produce which formats.
    2. ``same_name_different_id`` — player_name values that map to multiple
       player_id values (same-name conflicts or unresolved cross-source gaps).
    3. ``multi_team_season`` — transfer records that require explicit
       aggregation rules.
    4. ``cross_source_alignment`` — player_name values that span multiple
       sources and therefore cannot be joined without an identity decision.

    The report is read-only. It does not resolve conflicts, merge identities,
    or modify any artifact. Every risk is evidence for the maintainer's human
    review; ``unresolved`` is the honest default.
    """
    if settings is None:
        settings = PlatformSettings.from_root()

    df, error = _read_player_match(settings)
    if df is None:
        return {
            "schema": IDENTITY_AUDIT_SCHEMA,
            "schema_version": IDENTITY_AUDIT_VERSION,
            "generated_at": _now(),
            "verdict": "unavailable",
            "blocking_reasons": [error or "player_match.parquet unreadable"],
            "id_format_distribution": {
                "status": RISK_UNAVAILABLE,
                "evidence": {"reason": error or "unreadable"},
            },
            "same_name_different_id": {
                "status": RISK_UNAVAILABLE,
                "evidence": {"reason": error or "unreadable"},
            },
            "multi_team_season": {
                "status": RISK_UNAVAILABLE,
                "evidence": {"reason": error or "unreadable"},
            },
            "cross_source_alignment": {
                "status": RISK_UNAVAILABLE,
                "evidence": {"reason": error or "unreadable"},
            },
        }

    id_format = _build_id_format_distribution(df)
    same_name = _build_same_name_different_id(df)
    multi_team = _build_multi_team_season(df)
    cross_source = _build_cross_source_alignment_risk(df)

    # Top-level verdict: any present risk → "risks_present" (not "ready").
    # The audit never claims the identity layer is canonical; it only reports
    # whether risks have been surfaced for human review.
    risk_layers = [id_format, same_name, multi_team, cross_source]
    blocking_reasons: list[str] = []
    for name, layer in zip(
        (
            "id_format_distribution",
            "same_name_different_id",
            "multi_team_season",
            "cross_source_alignment",
        ),
        risk_layers,
        strict=True,
    ):
        if layer["status"] == RISK_PRESENT:
            blocking_reasons.append(f"{name}: {layer['evidence']['reason']}")

    verdict = "risks_present" if blocking_reasons else "no_risks_surfaced"

    return {
        "schema": IDENTITY_AUDIT_SCHEMA,
        "schema_version": IDENTITY_AUDIT_VERSION,
        "generated_at": _now(),
        "verdict": verdict,
        "blocking_reasons": blocking_reasons,
        "row_count": int(len(df)),
        "distinct_player_id": int(df["player_id"].nunique()),
        "distinct_player_name": int(df["player_name"].nunique())
        if "player_name" in df.columns
        else 0,
        "id_format_distribution": id_format,
        "same_name_different_id": same_name,
        "multi_team_season": multi_team,
        "cross_source_alignment": cross_source,
    }

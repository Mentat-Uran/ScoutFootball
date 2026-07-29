"""Tests for the canonical identity risk audit (PRS-1 R-005).

Covers the four risk dimensions surfaced by ``build_identity_audit_report``:

- ``id_format_distribution`` — multiple player_id formats in use.
- ``same_name_different_id`` — same display name maps to multiple player_id.
- ``multi_team_season`` — transfer records requiring aggregation rules.
- ``cross_source_alignment`` — same name appears under multiple sources.

The audit is read-only. The verdict is fail-closed in the sense that any
``present`` risk forces ``risks_present``; the audit never claims the identity
layer is canonical. ``unavailable`` is the honest default when
``player_match.parquet`` cannot be read.
"""

from __future__ import annotations

import pandas as pd

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.identity_audit import (
    IDENTITY_AUDIT_SCHEMA,
    IDENTITY_AUDIT_VERSION,
    RISK_ABSENT,
    RISK_PRESENT,
    RISK_UNAVAILABLE,
    _classify_player_id_format,
    build_identity_audit_report,
)

# ---------------------------------------------------------------------------
# Workspace helpers
# ---------------------------------------------------------------------------


def _player_match_path(root):
    return (
        root / "data" / "gold" / "feature_store" / "player_match.parquet"
    )


def _write_player_match(root, df: pd.DataFrame) -> None:
    """Write player_match.parquet under the isolated tmp workspace."""
    path = _player_match_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _base_row(**overrides) -> dict:
    """A single in-shape player_match row used by all fixture builders."""
    row = {
        "player_id": "understat|1",
        "player_name": "Player A",
        "source_name": "understat",
        "season_id": "2425",
        "team_name": "Team X",
        "multi_team_season": False,
    }
    row.update(overrides)
    return row


def _build_settings(root) -> PlatformSettings:
    return PlatformSettings.from_root(root)


# ---------------------------------------------------------------------------
# ID format classification (unit level)
# ---------------------------------------------------------------------------


def test_classify_understat_pipe_id() -> None:
    assert _classify_player_id_format("understat|1234") == "understat_pipe_id"


def test_classify_fbref_name_composite() -> None:
    # FBref composite: lowercased display name | birth year | nationality
    assert _classify_player_id_format("lionel messi|1987|argentina") == (
        "fbref_name_composite")


def test_classify_statsbomb_numeric() -> None:
    assert _classify_player_id_format("10605") == "statsbomb_numeric"
    # Pipeline sometimes stored float-as-string like "10605.0"
    assert _classify_player_id_format("10605.0") == "statsbomb_numeric"


def test_classify_unknown_format() -> None:
    assert _classify_player_id_format("") == "unknown"
    assert _classify_player_id_format(None) == "unknown"  # type: ignore[arg-type]
    assert _classify_player_id_format("not-a-known-format") == "unknown"


def test_classify_other_pipe_delimited_does_not_collide_with_understat() -> None:
    # A pipe-delimited ID whose prefix is not "understat" and not a display
    # name should fall through to other_pipe_delimited, not be silently
    # bucketed with the understat family.
    assert _classify_player_id_format("1234|abc") == "other_pipe_delimited"


# ---------------------------------------------------------------------------
# Unavailable paths (missing / empty / malformed)
# ---------------------------------------------------------------------------


def test_missing_player_match_returns_unavailable(tmp_path) -> None:
    """No player_match.parquet on disk → verdict unavailable, all layers down."""
    report = build_identity_audit_report(settings=_build_settings(tmp_path))
    assert report["schema"] == IDENTITY_AUDIT_SCHEMA
    assert report["schema_version"] == IDENTITY_AUDIT_VERSION
    assert report["verdict"] == "unavailable"
    assert report["blocking_reasons"]
    for layer in (
        "id_format_distribution",
        "same_name_different_id",
        "multi_team_season",
        "cross_source_alignment",
    ):
        assert report[layer]["status"] == RISK_UNAVAILABLE


def test_empty_player_match_returns_unavailable(tmp_path) -> None:
    """Zero-row parquet → unavailable, not a silent no_risks_surfaced."""
    _write_player_match(tmp_path, pd.DataFrame(columns=[
        "player_id", "player_name", "source_name", "season_id",
        "team_name", "multi_team_season",
    ]))
    report = build_identity_audit_report(settings=_build_settings(tmp_path))
    assert report["verdict"] == "unavailable"
    assert report["id_format_distribution"]["status"] == RISK_UNAVAILABLE


def test_missing_required_columns_returns_unavailable(tmp_path) -> None:
    """player_id column absent → cannot audit, must report unavailable."""
    _write_player_match(tmp_path, pd.DataFrame([{"player_name": "A"}]))
    report = build_identity_audit_report(settings=_build_settings(tmp_path))
    assert report["verdict"] == "unavailable"
    assert "missing required columns" in report["blocking_reasons"][0]


# ---------------------------------------------------------------------------
# Clean workspace: no risks surfaced
# ---------------------------------------------------------------------------


def test_single_source_single_format_no_risks(tmp_path) -> None:
    """Single source, single ID format, unique names → no_risks_surfaced.

    This is the only path that yields verdict=no_risks_surfaced. It still
    does not claim the identity layer is canonical — only that no risks were
    surfaced for human review.
    """
    _write_player_match(tmp_path, pd.DataFrame([
        _base_row(player_id="understat|1", player_name="A",
                  team_name="Team X", multi_team_season=False),
        _base_row(player_id="understat|2", player_name="B",
                  team_name="Team X", multi_team_season=False),
        _base_row(player_id="understat|3", player_name="C",
                  team_name="Team Y", multi_team_season=False),
    ]))
    report = build_identity_audit_report(settings=_build_settings(tmp_path))

    assert report["verdict"] == "no_risks_surfaced"
    assert report["blocking_reasons"] == []
    assert report["row_count"] == 3
    assert report["distinct_player_id"] == 3
    assert report["distinct_player_name"] == 3

    # Single format → id_format_distribution is absent (no risk surfaced).
    assert report["id_format_distribution"]["status"] == RISK_ABSENT
    assert report["same_name_different_id"]["status"] == RISK_ABSENT
    assert report["multi_team_season"]["status"] == RISK_ABSENT
    assert report["cross_source_alignment"]["status"] == RISK_ABSENT


# ---------------------------------------------------------------------------
# Same-name-different-ID risk
# ---------------------------------------------------------------------------


def test_same_name_different_id_forces_risks_present(tmp_path) -> None:
    """Two rows share player_name but have different player_id → risk present.

    This is the primary same-name signal: the audit cannot tell whether the
    two rows are (a) two different players sharing a name or (b) the same
    player recorded under source-specific IDs. Either way the maintainer
    must review before canonical join.
    """
    _write_player_match(tmp_path, pd.DataFrame([
        _base_row(player_id="understat|1", player_name="John Doe",
                  source_name="understat", team_name="Team X"),
        _base_row(player_id="understat|999", player_name="John Doe",
                  source_name="understat", team_name="Team Y"),
        _base_row(player_id="understat|2", player_name="Unique Player",
                  source_name="understat", team_name="Team Z"),
    ]))
    report = build_identity_audit_report(settings=_build_settings(tmp_path))

    assert report["verdict"] == "risks_present"
    same_name = report["same_name_different_id"]
    assert same_name["status"] == RISK_PRESENT
    assert same_name["evidence"]["risky_name_count"] == 1
    samples = same_name["evidence"]["samples"]
    assert len(samples) == 1
    assert samples[0]["player_name"] == "John Doe"
    assert samples[0]["distinct_player_id_count"] == 2
    assert set(samples[0]["player_id_samples"]) == {"understat|1", "understat|999"}

    # The blocking reason must reference the same-name layer.
    blocking = " ".join(report["blocking_reasons"])
    assert "same_name_different_id" in blocking


# ---------------------------------------------------------------------------
# Multi-team-season transfer records
# ---------------------------------------------------------------------------


def test_multi_team_season_transfer_records_flagged(tmp_path) -> None:
    """multi_team_season=True rows require explicit aggregation rules."""
    _write_player_match(tmp_path, pd.DataFrame([
        # Player A: stayed at one team all season — not a transfer.
        _base_row(player_id="understat|1", player_name="A",
                  season_id="2425", team_name="Team X",
                  multi_team_season=False),
        # Player B: appeared for two teams in the same season — transfer.
        _base_row(player_id="understat|2", player_name="B",
                  season_id="2425", team_name="Team X",
                  multi_team_season=True),
        _base_row(player_id="understat|2", player_name="B",
                  season_id="2425", team_name="Team Y",
                  multi_team_season=True),
    ]))
    report = build_identity_audit_report(settings=_build_settings(tmp_path))

    multi_team = report["multi_team_season"]
    assert multi_team["status"] == RISK_PRESENT
    assert multi_team["evidence"]["transfer_row_count"] == 2
    assert multi_team["evidence"]["distinct_player_count"] == 1
    samples = multi_team["evidence"]["samples"]
    assert len(samples) == 1
    assert set(samples[0]["team_names"]) == {"Team X", "Team Y"}
    assert report["verdict"] == "risks_present"


def test_multi_team_season_column_absent_reports_unavailable(tmp_path) -> None:
    """If the column is absent, that layer is unavailable — not absent.

    We cannot claim "no transfer records" when we cannot even read the flag.
    """
    df = pd.DataFrame([
        _base_row(player_id="understat|1", player_name="A",
                  source_name="understat", season_id="2425",
                  team_name="Team X"),
    ])
    df = df.drop(columns=["multi_team_season"])
    _write_player_match(tmp_path, df)
    report = build_identity_audit_report(settings=_build_settings(tmp_path))

    assert report["multi_team_season"]["status"] == RISK_UNAVAILABLE
    assert "multi_team_season column absent" in (
        report["multi_team_season"]["evidence"]["reason"])


# ---------------------------------------------------------------------------
# Cross-source alignment risk
# ---------------------------------------------------------------------------


def test_cross_source_alignment_risk_when_name_spans_sources(tmp_path) -> None:
    """Same name in fbref + understat → cross-source alignment risk.

    The two rows likely refer to the same person, but player_id will differ
    (fbref uses name|year|country, understat uses understat|<id>). Without
    an explicit identity registry, any cross-source join silently double-
    counts or misses the player.
    """
    _write_player_match(tmp_path, pd.DataFrame([
        _base_row(player_id="lionel messi|1987|argentina", player_name="Lionel Messi",
                  source_name="fbref", season_id="2425",
                  team_name="Inter Miami"),
        _base_row(player_id="understat|5583", player_name="Lionel Messi",
                  source_name="understat", season_id="2425",
                  team_name="Inter Miami"),
    ]))
    report = build_identity_audit_report(settings=_build_settings(tmp_path))

    cross = report["cross_source_alignment"]
    assert cross["status"] == RISK_PRESENT
    assert cross["evidence"]["risky_name_count"] == 1
    samples = cross["evidence"]["samples"]
    assert len(samples) == 1
    assert set(samples[0]["source_names"]) == {"fbref", "understat"}
    assert report["verdict"] == "risks_present"


# ---------------------------------------------------------------------------
# Combined: multiple ID formats + cross-source overlap
# ---------------------------------------------------------------------------


def test_multiple_id_formats_and_cross_source_overlap(tmp_path) -> None:
    """Realistic shape: fbref composite + understat pipe + StatsBomb numeric.

    This is the actual risk surface described in the PRS-1 plan section 3.2:
    fbref uses name|year|country, understat uses understat|<id>, StatsBomb
    uses a bare numeric string. Any canonical player_id system must confront
    all three formats before joining.
    """
    _write_player_match(tmp_path, pd.DataFrame([
        _base_row(player_id="lionel messi|1987|argentina", player_name="Lionel Messi",
                  source_name="fbref", season_id="2425",
                  team_name="Inter Miami"),
        _base_row(player_id="understat|5583", player_name="Lionel Messi",
                  source_name="understat", season_id="2425",
                  team_name="Inter Miami"),
        _base_row(player_id="5583", player_name="Lionel Messi",
                  source_name="statsbomb", season_id="2425",
                  team_name="Inter Miami"),
    ]))
    report = build_identity_audit_report(settings=_build_settings(tmp_path))

    # Three formats present → id_format_distribution is present.
    fmt = report["id_format_distribution"]
    assert fmt["status"] == RISK_PRESENT
    formats = fmt["evidence"]["formats"]
    assert "fbref_name_composite" in formats
    assert "understat_pipe_id" in formats
    assert "statsbomb_numeric" in formats

    # Cross-source overlap also present (same name in 3 sources).
    assert report["cross_source_alignment"]["status"] == RISK_PRESENT
    # Same-name risk also present (3 different IDs for one display name).
    assert report["same_name_different_id"]["status"] == RISK_PRESENT

    assert report["verdict"] == "risks_present"
    assert len(report["blocking_reasons"]) >= 3


def test_format_by_source_records_which_source_produces_which_format(tmp_path) -> None:
    """format_by_source cross-tab is the evidence the maintainer uses to plan joins."""
    _write_player_match(tmp_path, pd.DataFrame([
        _base_row(player_id="understat|1", player_name="A",
                  source_name="understat", team_name="Team X"),
        _base_row(player_id="understat|2", player_name="B",
                  source_name="understat", team_name="Team X"),
        _base_row(player_id="name|2000|country", player_name="C",
                  source_name="fbref", team_name="Team Y"),
    ]))
    report = build_identity_audit_report(settings=_build_settings(tmp_path))
    fmt = report["id_format_distribution"]
    by_source = fmt["evidence"]["format_by_source"]
    assert by_source["understat"]["understat_pipe_id"] == 2
    assert by_source["fbref"]["fbref_name_composite"] == 1


# ---------------------------------------------------------------------------
# Sample caps (defensive — audit must not dump entire dataset)
# ---------------------------------------------------------------------------


def test_same_name_samples_capped_at_50(tmp_path) -> None:
    """More than 50 risky names → only first 50 samples emitted.

    The audit reports the full risky_name_count but caps samples so the CLI
    output remains readable on a maintainer's terminal.
    """
    rows = []
    for i in range(60):
        # Each pair of rows shares a name but has a different player_id.
        rows.append(_base_row(
            player_id=f"understat|{i}a", player_name=f"Name{i}",
            source_name="understat", team_name="Team X"))
        rows.append(_base_row(
            player_id=f"understat|{i}b", player_name=f"Name{i}",
            source_name="understat", team_name="Team X"))
    _write_player_match(tmp_path, pd.DataFrame(rows))
    report = build_identity_audit_report(settings=_build_settings(tmp_path))

    same_name = report["same_name_different_id"]
    assert same_name["evidence"]["risky_name_count"] == 60
    assert same_name["evidence"]["sample_count"] == 50

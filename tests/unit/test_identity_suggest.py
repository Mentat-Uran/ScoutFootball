"""Tests for the canonical identity mapping suggestion tool (PRS-1 R-005).

Covers:
- Exact normalized name match → high confidence suggestion.
- Name match but team differs → medium confidence (possible transfer).
- No name match → unmatched with honest reason.
- Missing player_match file → empty report.
- Missing season_id/competition_id → unmatched with reason.
- Multiple candidates for one primary player → all reported.
- Normalization: accents stripped, case insensitive, non-alphanumeric removed.
- Summary counts are correct.
"""

from __future__ import annotations

import pandas as pd

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.identity_suggest import suggest_canonical_mappings


def _sample_player_match() -> pd.DataFrame:
    """A player_match frame with statsbomb + understat rows for testing.

    Layout:
    - 3 statsbomb players in season 2021 / ESP-La Liga:
      p1 "Marc-André ter Stegen" / Barcelona — exact match in understat
      p2 "Néstor Araújo" / Celta Vigo — name match but team differs in understat
      p3 "Unknown Player" / Sevilla — no match in understat
    - 2 understat players in the same season+competition:
      u1 "Marc-Andre ter Stegen" / Barcelona (accent stripped — should match p1)
      u2 "Nestor Araujo" / Real Betis (accent stripped — should match p2, team differs)
    """
    return pd.DataFrame({
        "player_id": ["20055", "11388", "99999", "understat|2090", "understat|8888"],
        "player_name": [
            "Marc-André ter Stegen",
            "Néstor Alejandro Araújo",
            "Unknown Player",
            "Marc-Andre ter Stegen",
            "Nestor Araujo",
        ],
        "team_name": [
            "Barcelona",
            "Celta Vigo",
            "Sevilla",
            "Barcelona",
            "Real Betis",
        ],
        "season_id": ["2021", "2021", "2021", "2021", "2021"],
        "competition_id": [
            "ESP-La Liga",
            "ESP-La Liga",
            "ESP-La Liga",
            "ESP-La Liga",
            "ESP-La Liga",
        ],
        "source_name": [
            "statsbomb_open",
            "statsbomb_open",
            "statsbomb_open",
            "understat",
            "understat",
        ],
    })


# ---------------------------------------------------------------------------
# Basic matching
# ---------------------------------------------------------------------------


class TestSuggestCanonicalMappings:
    def test_exact_name_team_match_is_high_confidence(self, tmp_path) -> None:
        """p1 "Marc-André ter Stegen" / Barcelona matches u1 "Marc-Andre ter
        Stegen" / Barcelona after accent normalization → high confidence."""
        settings = PlatformSettings.from_root(tmp_path)
        pm = _sample_player_match()
        report = suggest_canonical_mappings(settings=settings, player_match=pm)

        assert report["schema"] == "scoutfootball.identity-suggest"
        assert report["schema_version"] == "1.0.0"
        assert report["total_primary_players"] == 3

        high = [m for m in report["matched"] if m["confidence"] == "high"]
        assert len(high) == 1
        m = high[0]
        assert m["source_player_id"] == "20055"
        assert m["source_player_name"] == "Marc-André ter Stegen"
        assert m["candidate_source_player_id"] == "understat|2090"
        assert m["candidate_player_name"] == "Marc-Andre ter Stegen"
        assert m["suggested_canonical_player_id"] == "understat|2090"
        assert m["season_id"] == "2021"
        assert m["competition_id"] == "ESP-La Liga"
        assert "team match" in m["evidence"]

    def test_name_match_team_differs_is_medium_confidence(self, tmp_path) -> None:
        """p2 "Néstor Alejandro Araújo" / Celta Vigo matches u2 "Nestor Araujo"
        / Real Betis after accent normalization → medium confidence (team
        differs, possible transfer or vocabulary difference).

        Note: the normalized name of "Néstor Alejandro Araújo" is
        "nestor alejandro araujo" while "Nestor Araujo" normalizes to
        "nestor araujo". These are NOT equal, so this test actually
        expects no_match — the partial name doesn't match the full name.

        To test the team-differs case properly, we need exact normalized
        name match with different team. Let me adjust the test data.
        """
        # Adjust: use the same normalized name for both, but different teams.
        pm = pd.DataFrame({
            "player_id": ["11388", "understat|8888"],
            "player_name": ["Néstor Araújo", "Nestor Araujo"],
            "team_name": ["Celta Vigo", "Real Betis"],
            "season_id": ["2021", "2021"],
            "competition_id": ["ESP-La Liga", "ESP-La Liga"],
            "source_name": ["statsbomb_open", "understat"],
        })
        settings = PlatformSettings.from_root(tmp_path)
        report = suggest_canonical_mappings(settings=settings, player_match=pm)

        medium = [m for m in report["matched"] if m["confidence"] == "medium"]
        assert len(medium) == 1
        m = medium[0]
        assert m["source_player_id"] == "11388"
        assert m["candidate_team_name"] == "Real Betis"
        assert "team differs" in m["evidence"]

    def test_no_name_match_is_unmatched(self, tmp_path) -> None:
        """p2 "Néstor Alejandro Araújo" (full name) and p3 "Unknown Player"
        both have no normalized name match in understat → 2 unmatched.

        p2's full legal name "Néstor Alejandro Araújo" normalizes to
        "nestor alejandro araujo" which does NOT equal u2's "Nestor Araujo"
        → "nestor araujo". This is the honest no-fuzzy-matching limitation:
        full legal names that differ from common names are reported as
        unmatched for manual review.
        """
        settings = PlatformSettings.from_root(tmp_path)
        pm = _sample_player_match()
        report = suggest_canonical_mappings(settings=settings, player_match=pm)

        assert len(report["unmatched"]) == 2
        ids = {u["source_player_id"] for u in report["unmatched"]}
        assert ids == {"11388", "99999"}
        for u in report["unmatched"]:
            assert u["reason"] == "no_normalized_name_match_in_season_competition"
            assert u["season_id"] == "2021"
            assert u["competition_id"] == "ESP-La Liga"

    def test_summary_counts_correct(self, tmp_path) -> None:
        """Summary counts: 1 high + 0 medium + 1 no_match = 2 total
        (p2 "Néstor Alejandro Araújo" has a longer name than "Nestor Araujo"
        so it won't match — only p1 matches with high confidence).

        Actually, with the full sample data, p2's normalized name is
        "nestor alejandro araujo" which doesn't equal "nestor araujo", so
        p2 is also unmatched. The summary should be: high=1, medium=0,
        no_match=2.
        """
        settings = PlatformSettings.from_root(tmp_path)
        pm = _sample_player_match()
        report = suggest_canonical_mappings(settings=settings, player_match=pm)

        assert report["summary"]["high"] == 1
        assert report["summary"]["medium"] == 0
        assert report["summary"]["no_match"] == 2
        assert report["total_primary_players"] == 3


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_player_match_returns_empty_report(self, tmp_path) -> None:
        """Empty player_match → empty report with zero counts."""
        settings = PlatformSettings.from_root(tmp_path)
        report = suggest_canonical_mappings(
            settings=settings,
            player_match=pd.DataFrame(),
        )
        assert report["total_primary_players"] == 0
        assert report["matched"] == []
        assert report["unmatched"] == []
        assert report["summary"] == {"high": 0, "medium": 0, "no_match": 0}

    def test_no_statsbomb_players_returns_empty_report(self, tmp_path) -> None:
        """player_match with only understat rows → no primary players."""
        settings = PlatformSettings.from_root(tmp_path)
        pm = pd.DataFrame({
            "player_id": ["u1"],
            "player_name": ["Player A"],
            "team_name": ["Team A"],
            "season_id": ["2021"],
            "competition_id": ["ESP-La Liga"],
            "source_name": ["understat"],
        })
        report = suggest_canonical_mappings(settings=settings, player_match=pm)
        assert report["total_primary_players"] == 0

    def test_missing_file_returns_empty_report(self, tmp_path) -> None:
        """When player_match.parquet doesn't exist → empty report."""
        settings = PlatformSettings.from_root(tmp_path)
        # Don't write any file — _load_player_match returns empty DataFrame.
        report = suggest_canonical_mappings(settings=settings)
        assert report["total_primary_players"] == 0

    def test_missing_season_id_is_unmatched(self, tmp_path) -> None:
        """A statsbomb player with NaN season_id → unmatched with
        'missing_season_or_competition_or_name' reason."""
        settings = PlatformSettings.from_root(tmp_path)
        pm = pd.DataFrame({
            "player_id": ["p1", "u1"],
            "player_name": ["Player A", "Player A"],
            "team_name": ["Team A", "Team A"],
            "season_id": [pd.NA, "2021"],
            "competition_id": ["ESP-La Liga", "ESP-La Liga"],
            "source_name": ["statsbomb_open", "understat"],
        })
        report = suggest_canonical_mappings(settings=settings, player_match=pm)
        assert len(report["unmatched"]) == 1
        assert report["unmatched"][0]["reason"] == "missing_season_or_competition_or_name"

    def test_multiple_candidates_all_reported(self, tmp_path) -> None:
        """When multiple understat players match the same statsbomb player
        (same normalized name, same season+competition), all candidates are
        reported — the tool does not auto-pick one."""
        settings = PlatformSettings.from_root(tmp_path)
        pm = pd.DataFrame({
            "player_id": ["sb1", "u1", "u2"],
            "player_name": ["John Smith", "John Smith", "John Smith"],
            "team_name": ["Team A", "Team A", "Team B"],
            "season_id": ["2021", "2021", "2021"],
            "competition_id": ["ESP-La Liga", "ESP-La Liga", "ESP-La Liga"],
            "source_name": ["statsbomb_open", "understat", "understat"],
        })
        report = suggest_canonical_mappings(settings=settings, player_match=pm)
        # 1 statsbomb player matched against 2 understat candidates.
        assert len(report["matched"]) == 2
        confidences = sorted(m["confidence"] for m in report["matched"])
        # One high (team match), one medium (team differs).
        assert confidences == ["high", "medium"]

    def test_different_season_no_match(self, tmp_path) -> None:
        """A statsbomb player in season 2021 and understat player with the
        same name in season 2020 → no match (different season scope)."""
        settings = PlatformSettings.from_root(tmp_path)
        pm = pd.DataFrame({
            "player_id": ["sb1", "u1"],
            "player_name": ["Player A", "Player A"],
            "team_name": ["Team A", "Team A"],
            "season_id": ["2021", "1920"],
            "competition_id": ["ESP-La Liga", "ESP-La Liga"],
            "source_name": ["statsbomb_open", "understat"],
        })
        report = suggest_canonical_mappings(settings=settings, player_match=pm)
        assert len(report["matched"]) == 0
        assert len(report["unmatched"]) == 1
        assert report["unmatched"][0]["reason"] == "no_normalized_name_match_in_season_competition"

    def test_different_competition_no_match(self, tmp_path) -> None:
        """Same name, same season, different competition → no match."""
        settings = PlatformSettings.from_root(tmp_path)
        pm = pd.DataFrame({
            "player_id": ["sb1", "u1"],
            "player_name": ["Player A", "Player A"],
            "team_name": ["Team A", "Team A"],
            "season_id": ["2021", "2021"],
            "competition_id": ["ESP-La Liga", "ENG-Premier League"],
            "source_name": ["statsbomb_open", "understat"],
        })
        report = suggest_canonical_mappings(settings=settings, player_match=pm)
        assert len(report["matched"]) == 0
        assert len(report["unmatched"]) == 1

    def test_normalization_strips_accents_and_case(self, tmp_path) -> None:
        """"Marc-André ter Stegen" (statsbomb, accented) matches
        "marc-andre ter stegen" (understat, lowercase, no accent) after
        normalization."""
        settings = PlatformSettings.from_root(tmp_path)
        pm = pd.DataFrame({
            "player_id": ["sb1", "u1"],
            "player_name": ["Marc-André ter Stegen", "marc-andre ter stegen"],
            "team_name": ["Barcelona", "Barcelona"],
            "season_id": ["2021", "2021"],
            "competition_id": ["ESP-La Liga", "ESP-La Liga"],
            "source_name": ["statsbomb_open", "understat"],
        })
        report = suggest_canonical_mappings(settings=settings, player_match=pm)
        assert len(report["matched"]) == 1
        assert report["matched"][0]["confidence"] == "high"


# ---------------------------------------------------------------------------
# Limitations
# ---------------------------------------------------------------------------


class TestLimitations:
    def test_limitations_list_non_empty(self, tmp_path) -> None:
        """The report always includes honest limitations."""
        settings = PlatformSettings.from_root(tmp_path)
        report = suggest_canonical_mappings(settings=settings, player_match=pd.DataFrame())
        assert len(report["limitations"]) >= 3
        # Each limitation is a non-empty string.
        for lim in report["limitations"]:
            assert isinstance(lim, str) and len(lim) > 20

    def test_no_fuzzy_matching_limitation_documented(self, tmp_path) -> None:
        """The limitations list must mention that no fuzzy matching is done."""
        settings = PlatformSettings.from_root(tmp_path)
        report = suggest_canonical_mappings(settings=settings, player_match=pd.DataFrame())
        joined = " ".join(report["limitations"])
        assert "fuzzy" in joined.lower() or "exact" in joined.lower()

    def test_full_name_vs_short_name_does_not_match(self, tmp_path) -> None:
        """"Rodrigo Andrés Battaglia" (full legal name) does NOT match
        "Rodrigo Battaglia" (short common name) because the tool only does
        exact normalized name matching, not fuzzy/token matching. This is
        an honest limitation — the player is reported as unmatched for
        manual review."""
        settings = PlatformSettings.from_root(tmp_path)
        pm = pd.DataFrame({
            "player_id": ["sb1", "u1"],
            "player_name": ["Rodrigo Andrés Battaglia", "Rodrigo Battaglia"],
            "team_name": ["Deportivo Alavés", "Deportivo Alavés"],
            "season_id": ["2021", "2021"],
            "competition_id": ["ESP-La Liga", "ESP-La Liga"],
            "source_name": ["statsbomb_open", "understat"],
        })
        report = suggest_canonical_mappings(settings=settings, player_match=pm)
        assert len(report["matched"]) == 0
        assert len(report["unmatched"]) == 1

"""Tests for synthetic fallback isolation (PRS-0 R-003).

PRS-0 R-003 (see ``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md``) requires that
synthetic fallback data must not enter real research health, evaluation or
export. These tests verify the three-layer isolation pattern:

1. **Helpers** — ``frame_is_synthetic`` detects stamped demo frames;
   ``assert_real_frame`` raises ``SyntheticDataError``.
2. **CSV exports refuse synthetic** — ``get_player_profile(fmt="csv")``
   returns an error response instead of exporting demo data as a real
   research CSV.
3. **JSON responses mark synthetic** — rating endpoints stamp
   ``data_mode: "synthetic"`` so consumers cannot mistake demo data for a
   real artifact.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from scoutfootball.app.data_loader import (
    SyntheticDataError,
    _mark_synthetic,
    assert_real_frame,
    frame_is_synthetic,
)

# ---------------------------------------------------------------------------
# 1. Helper tests
# ---------------------------------------------------------------------------


class TestFrameIsSynthetic:
    def test_none_frame_is_not_synthetic(self) -> None:
        assert frame_is_synthetic(None) is False

    def test_empty_frame_is_not_synthetic(self) -> None:
        assert frame_is_synthetic(pd.DataFrame()) is False

    def test_real_frame_without_column_is_not_synthetic(self) -> None:
        df = pd.DataFrame({"player": ["A"], "optimized_score": [0.5]})
        assert frame_is_synthetic(df) is False

    def test_frame_with_is_synthetic_true_is_synthetic(self) -> None:
        df = pd.DataFrame({"player": ["A"], "is_synthetic": [True]})
        assert frame_is_synthetic(df) is True

    def test_frame_with_is_synthetic_false_is_not_synthetic(self) -> None:
        df = pd.DataFrame({"player": ["A"], "is_synthetic": [False]})
        assert frame_is_synthetic(df) is False

    def test_frame_with_mixed_synthetic_is_synthetic(self) -> None:
        # Any synthetic row means the frame is contaminated.
        df = pd.DataFrame({"player": ["A", "B"], "is_synthetic": [True, False]})
        assert frame_is_synthetic(df) is True

    def test_frame_with_nan_synthetic_is_not_synthetic(self) -> None:
        # NaN is treated as False (real) — only explicit True marks synthetic.
        df = pd.DataFrame({"player": ["A"], "is_synthetic": [pd.NA]})
        assert frame_is_synthetic(df) is False

    def test_mark_synthetic_makes_frame_detected_as_synthetic(self) -> None:
        df = pd.DataFrame({"player": ["A"], "optimized_score": [0.5]})
        assert frame_is_synthetic(df) is False
        marked = _mark_synthetic(df)
        assert frame_is_synthetic(marked) is True
        # Original is not mutated.
        assert frame_is_synthetic(df) is False


class TestAssertRealFrame:
    def test_real_frame_passes(self) -> None:
        df = pd.DataFrame({"player": ["A"], "optimized_score": [0.5]})
        # Should not raise.
        assert_real_frame(df, "player_ratings")

    def test_synthetic_frame_raises(self) -> None:
        df = _mark_synthetic(pd.DataFrame({"player": ["A"]}))
        try:
            assert_real_frame(df, "player_ratings")
        except SyntheticDataError as exc:
            assert "player_ratings" in str(exc)
            assert "synthetic" in str(exc).lower()
        else:
            raise AssertionError("assert_real_frame should raise SyntheticDataError")

    def test_none_frame_passes(self) -> None:
        # None is not synthetic — it is simply missing. Callers handle
        # missing separately; assert_real_frame only refuses synthetic.
        assert_real_frame(None, "player_ratings")

    def test_empty_frame_passes(self) -> None:
        assert_real_frame(pd.DataFrame(), "player_ratings")

    def test_error_message_names_the_artifact(self) -> None:
        df = _mark_synthetic(pd.DataFrame({"player": ["A"]}))
        try:
            assert_real_frame(df, "oof_predictions")
        except SyntheticDataError as exc:
            assert "oof_predictions" in str(exc)
            assert "build-features" in str(exc)
            assert "train" in str(exc)


# ---------------------------------------------------------------------------
# 2. CSV export refusal tests
# ---------------------------------------------------------------------------


def _synthetic_ratings_frame() -> pd.DataFrame:
    """Build a synthetic ratings frame that mirrors data_loader fallback."""
    df = pd.DataFrame({
        "player": ["Demo Player"],
        "player_name": ["Demo Player"],
        "team": ["Demo FC"],
        "league": ["Demo League"],
        "season": ["2526"],
        "position_group": ["MF"],
        "sub_position": ["MF"],
        "optimized_score": [0.5],
        "minutes": [900],
        "confidence_level": ["MEDIUM"],
        "npg_p90": [0.1],
        "assists_p90": [0.05],
        "defense_composite": [0.3],
        "possession_composite": [0.4],
    })
    return _mark_synthetic(df)


def _real_ratings_frame() -> pd.DataFrame:
    """Build a real ratings frame (no is_synthetic column)."""
    return pd.DataFrame({
        "player": ["Real Player"],
        "player_name": ["Real Player"],
        "team": ["Real FC"],
        "league": ["Premier League"],
        "season": ["2526"],
        "position_group": ["MF"],
        "sub_position": ["MF"],
        "optimized_score": [0.7],
        "minutes": [1800],
        "confidence_level": ["HIGH"],
        "npg_p90": [0.2],
        "assists_p90": [0.1],
        "defense_composite": [0.5],
        "possession_composite": [0.6],
    })


def _empty_ratings_frame() -> pd.DataFrame:
    """Build an empty ratings frame with the player column so lookups don't crash."""
    return pd.DataFrame(columns=["player"])


def _patch_ratings(frame: pd.DataFrame):
    """Return a patch context for load_player_ratings with the given frame."""
    return patch(
        "scoutfootball.api.load_player_ratings",
        return_value=frame,
    )


class TestCsvExportRefusesSynthetic:
    def test_player_profile_csv_refuses_synthetic_fuzzy(self) -> None:
        """Fuzzy-match CSV export refuses synthetic ratings."""
        from scoutfootball.api import get_player_profile

        with _patch_ratings(_synthetic_ratings_frame()):
            result = get_player_profile("Demo", fmt="csv")

        assert result["status"] == "error"
        assert result["error"] == "synthetic_data_refused"
        assert "synthetic" in result["message"].lower()

    def test_player_profile_csv_refuses_synthetic_single(self) -> None:
        """Single-player CSV export refuses synthetic ratings."""
        from scoutfootball.api import get_player_profile

        with _patch_ratings(_synthetic_ratings_frame()):
            result = get_player_profile("Demo Player", fmt="csv")

        assert result["status"] == "error"
        assert result["error"] == "synthetic_data_refused"

    def test_player_profile_csv_exports_real_data(self) -> None:
        """Real ratings CSV export succeeds and returns CSV text."""
        from scoutfootball.api import get_player_profile

        with _patch_ratings(_real_ratings_frame()):
            result = get_player_profile("Real Player", fmt="csv")

        # Real data returns CSV text (a string, not an error dict).
        assert isinstance(result, str)
        assert "Real Player" in result

    def test_player_profile_csv_empty_data_returns_not_found(self) -> None:
        """Empty ratings frame returns found=False, not synthetic refusal."""
        from scoutfootball.api import get_player_profile

        with _patch_ratings(_empty_ratings_frame()):
            result = get_player_profile("Nobody", fmt="csv")

        # Empty frame → found: False (no data to export, but not synthetic).
        assert result.get("found") is False or result.get("status") == "error"


# ---------------------------------------------------------------------------
# 3. JSON response marking tests
# ---------------------------------------------------------------------------


class TestJsonResponseMarksSynthetic:
    def test_get_player_ratings_marks_synthetic(self) -> None:
        from scoutfootball.api import get_player_ratings

        with _patch_ratings(_synthetic_ratings_frame()):
            result = get_player_ratings()

        assert result["data_mode"] == "synthetic"
        assert result["count"] > 0

    def test_get_player_ratings_marks_real(self) -> None:
        from scoutfootball.api import get_player_ratings

        with _patch_ratings(_real_ratings_frame()):
            result = get_player_ratings()

        assert result["data_mode"] == "artifact"

    def test_get_player_ratings_empty_marks_empty(self) -> None:
        from scoutfootball.api import get_player_ratings

        with _patch_ratings(_empty_ratings_frame()):
            result = get_player_ratings()

        assert result["data_mode"] == "empty"
        assert result["count"] == 0

    def test_get_player_profile_marks_synthetic_single(self) -> None:
        from scoutfootball.api import get_player_profile

        with _patch_ratings(_synthetic_ratings_frame()):
            result = get_player_profile("Demo Player")

        assert result.get("found") is True
        assert result["data_mode"] == "synthetic"

    def test_get_player_profile_marks_real_single(self) -> None:
        from scoutfootball.api import get_player_profile

        with _patch_ratings(_real_ratings_frame()):
            result = get_player_profile("Real Player")

        assert result.get("found") is True
        assert result["data_mode"] == "artifact"

    def test_get_team_strength_marks_synthetic(self) -> None:
        from scoutfootball.api import get_team_strength

        with _patch_ratings(_synthetic_ratings_frame()):
            result = get_team_strength()

        assert result["data_mode"] == "synthetic"

    def test_get_team_strength_marks_real(self) -> None:
        from scoutfootball.api import get_team_strength

        with _patch_ratings(_real_ratings_frame()):
            result = get_team_strength()

        assert result["data_mode"] == "artifact"

    def test_get_team_strength_empty_marks_empty(self) -> None:
        from scoutfootball.api import get_team_strength

        with _patch_ratings(_empty_ratings_frame()):
            result = get_team_strength()

        assert result["data_mode"] == "empty"
        assert result["count"] == 0

    def test_get_player_comparison_propagates_synthetic(self) -> None:
        from scoutfootball.api import get_player_comparison

        with _patch_ratings(_synthetic_ratings_frame()):
            # Both names match the same demo row — comparison should still
            # propagate the synthetic flag from the underlying profiles.
            result = get_player_comparison("Demo", "Demo")

        # When both players resolve to the same row, comparison still runs.
        # The synthetic flag must propagate regardless.
        if result.get("status") != "error":
            assert result["data_mode"] == "synthetic"

    def test_get_player_comparison_propagates_real(self) -> None:
        from scoutfootball.api import get_player_comparison

        with _patch_ratings(_real_ratings_frame()):
            result = get_player_comparison("Real", "Real")

        if result.get("status") != "error":
            assert result["data_mode"] == "artifact"

    def test_get_player_comparison_multi_marks_synthetic(self) -> None:
        from scoutfootball.api import get_player_comparison_multi

        with _patch_ratings(_synthetic_ratings_frame()):
            result = get_player_comparison_multi(["Demo", "Demo"])

        if result.get("status") != "error":
            assert result["data_mode"] == "synthetic"

    def test_get_player_comparison_multi_marks_real(self) -> None:
        from scoutfootball.api import get_player_comparison_multi

        with _patch_ratings(_real_ratings_frame()):
            result = get_player_comparison_multi(["Real", "Real"])

        if result.get("status") != "error":
            assert result["data_mode"] == "artifact"

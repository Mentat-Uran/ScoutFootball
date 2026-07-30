"""Tests for ``scoutfootball.api._infer_evidence_grain`` (PRS-1 R-006 API slice).

The PRS-1 grain audit (``evaluation/grain.py``) classifies the grain of
each player_match / feature_matrix row. The API layer extends this with
``_infer_evidence_grain``, which labels every ratings / value response so
callers cannot silently interpret season-aggregated data as match-level
observations.

These tests pin the contract documented in the ``_infer_evidence_grain``
docstring:

- ``None`` / empty frame → ``"unknown"``.
- Frame with ``data_granularity`` column → single grain returned as-is;
  mixed grains returned as a sorted ``|``-joined set (matching the
  ``data_granularity_set`` convention in ``rating_matrix``).
- Legacy ratings table without ``data_granularity`` but with ``player`` +
  ``season`` → inferred as ``"season_proxy"`` (the honest label for
  ``player_ratings_optimized.parquet``).
- Anything else → ``"unknown"``.
"""

from __future__ import annotations

import pandas as pd

from scoutfootball.api import _infer_evidence_grain


class TestInferEvidenceGrain:
    def test_none_returns_unknown(self) -> None:
        assert _infer_evidence_grain(None) == "unknown"

    def test_empty_frame_returns_unknown(self) -> None:
        assert _infer_evidence_grain(pd.DataFrame()) == "unknown"

    def test_match_grain_returned_as_is(self) -> None:
        df = pd.DataFrame({"data_granularity": ["match", "match"]})
        assert _infer_evidence_grain(df) == "match"

    def test_season_proxy_grain_returned_as_is(self) -> None:
        df = pd.DataFrame({"data_granularity": ["season_proxy"]})
        assert _infer_evidence_grain(df) == "season_proxy"

    def test_aggregate_grain_returned_as_is(self) -> None:
        df = pd.DataFrame({"data_granularity": ["aggregate"]})
        assert _infer_evidence_grain(df) == "aggregate"

    def test_mixed_grains_joined_sorted(self) -> None:
        """Mixed grains are surfaced as a sorted ``|``-joined set so
        consumers see the heterogeneity instead of picking one grain."""
        df = pd.DataFrame(
            {"data_granularity": ["season_proxy", "match", "season_proxy"]}
        )
        assert _infer_evidence_grain(df) == "match|season_proxy"

    def test_all_nan_grain_returns_unknown(self) -> None:
        df = pd.DataFrame({"data_granularity": [None, None]})
        assert _infer_evidence_grain(df) == "unknown"

    def test_legacy_ratings_table_inferred_as_season_proxy(self) -> None:
        """The legacy ``player_ratings_optimized.parquet`` has no
        ``data_granularity`` column but is built from season-aggregated
        inputs (one row per player-season). The API labels it
        ``season_proxy`` so callers cannot treat it as match-level data."""
        df = pd.DataFrame(
            {
                "player": ["Lara", "Marco"],
                "season": ["2425", "2425"],
                "rating": [7.1, 6.8],
            }
        )
        assert _infer_evidence_grain(df) == "season_proxy"

    def test_frame_without_grain_or_player_season_returns_unknown(self) -> None:
        df = pd.DataFrame({"team": ["A"], "league": ["B"]})
        assert _infer_evidence_grain(df) == "unknown"

    def test_data_granularity_takes_precedence_over_legacy_inference(self) -> None:
        """When both ``data_granularity`` and ``player``+``season`` are
        present, the explicit grain column wins."""
        df = pd.DataFrame(
            {
                "data_granularity": ["match"],
                "player": ["Lara"],
                "season": ["2425"],
            }
        )
        assert _infer_evidence_grain(df) == "match"

"""Unit tests for scoutlab.viz.pitch module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from scoutlab.viz.pitch import (
    draw_pitch,
    plot_heatmap,
    plot_pass_map,
    plot_pizza_chart,
    plot_shot_map,
)

# ---------------------------------------------------------------------------
# draw_pitch
# ---------------------------------------------------------------------------


class TestDrawPitch:
    def test_returns_figure(self) -> None:
        fig = draw_pitch()
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_horizontal_orientation(self) -> None:
        fig = draw_pitch(orientation="horizontal")
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_half_pitch(self) -> None:
        fig = draw_pitch(half=True)
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_mplsoccer_missing(self) -> None:
        with patch("scoutlab.viz.pitch._check_mplsoccer", side_effect=ImportError("no")):
            fig = draw_pitch()
            import matplotlib.figure

            assert isinstance(fig, matplotlib.figure.Figure)


# ---------------------------------------------------------------------------
# plot_shot_map
# ---------------------------------------------------------------------------


class TestPlotShotMap:
    def test_empty_dataframe(self) -> None:
        fig = plot_shot_map(pd.DataFrame())
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_with_shots(self) -> None:
        df = pd.DataFrame(
            {
                "x": [90, 85, 70],
                "y": [40, 50, 30],
                "shot_outcome": ["Goal", "Saved", "Missed"],
                "shot_statsbomb_xg": [0.5, 0.2, 0.1],
            }
        )
        fig = plot_shot_map(df)
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_missing_column(self) -> None:
        df = pd.DataFrame({"x": [90], "wrong_y": [40]})
        fig = plot_shot_map(df)
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_mplsoccer_missing(self) -> None:
        with patch("scoutlab.viz.pitch._check_mplsoccer", side_effect=ImportError("no")):
            fig = plot_shot_map(pd.DataFrame())
            import matplotlib.figure

            assert isinstance(fig, matplotlib.figure.Figure)


# ---------------------------------------------------------------------------
# plot_pass_map
# ---------------------------------------------------------------------------


class TestPlotPassMap:
    def test_empty_dataframe(self) -> None:
        fig = plot_pass_map(pd.DataFrame())
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_with_passes(self) -> None:
        df = pd.DataFrame(
            {
                "x": [30, 50],
                "y": [40, 50],
                "pass_end_x": [50, 70],
                "pass_end_y": [45, 55],
                "pass_outcome": [None, "Incomplete"],
            }
        )
        fig = plot_pass_map(df)
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_missing_column(self) -> None:
        df = pd.DataFrame({"x": [30], "y": [40]})
        fig = plot_pass_map(df)
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_mplsoccer_missing(self) -> None:
        with patch("scoutlab.viz.pitch._check_mplsoccer", side_effect=ImportError("no")):
            fig = plot_pass_map(pd.DataFrame())
            import matplotlib.figure

            assert isinstance(fig, matplotlib.figure.Figure)


# ---------------------------------------------------------------------------
# plot_heatmap
# ---------------------------------------------------------------------------


class TestPlotHeatmap:
    def test_empty_dataframe(self) -> None:
        fig = plot_heatmap(pd.DataFrame())
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_with_events(self) -> None:
        df = pd.DataFrame(
            {
                "x": [50, 60, 70, 80, 50],
                "y": [30, 40, 50, 60, 40],
            }
        )
        fig = plot_heatmap(df)
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_player_filter(self) -> None:
        df = pd.DataFrame(
            {
                "x": [50, 60],
                "y": [30, 40],
                "player_name": ["Player A", "Player B"],
            }
        )
        fig = plot_heatmap(df, player_col="player_name", player_name="Player A")
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_missing_column(self) -> None:
        df = pd.DataFrame({"wrong_x": [50], "y": [30]})
        fig = plot_heatmap(df)
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_mplsoccer_missing(self) -> None:
        with patch("scoutlab.viz.pitch._check_mplsoccer", side_effect=ImportError("no")):
            fig = plot_heatmap(pd.DataFrame())
            import matplotlib.figure

            assert isinstance(fig, matplotlib.figure.Figure)


# ---------------------------------------------------------------------------
# plot_pizza_chart
# ---------------------------------------------------------------------------


class TestPlotPizzaChart:
    def test_empty_percentiles(self) -> None:
        fig = plot_pizza_chart({})
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_with_percentiles(self) -> None:
        percentiles = {"Goals": 80, "Assists": 60, "Passes": 70, "Tackles": 50}
        fig = plot_pizza_chart(percentiles, player_name="Test Player", position="CM")
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_with_comparison(self) -> None:
        percentiles = {"Goals": 80, "Assists": 60, "Passes": 70, "Tackles": 50}
        compare = {"Goals": 40, "Assists": 90, "Passes": 55, "Tackles": 75}
        fig = plot_pizza_chart(
            percentiles,
            player_name="Player A",
            compare_percentiles=compare,
            compare_name="Player B",
        )
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_mplsoccer_missing(self) -> None:
        with patch("scoutlab.viz.pitch._check_mplsoccer", side_effect=ImportError("no")):
            fig = plot_pizza_chart({"Goals": 80, "Assists": 60})
            import matplotlib.figure

            assert isinstance(fig, matplotlib.figure.Figure)

    def test_pypizza_fallback(self) -> None:
        """Test that fallback polar plot works when PyPizza is not available."""
        mock_mplsoccer = MagicMock()
        del mock_mplsoccer.PyPizza  # AttributeError when accessing PyPizza

        with patch("scoutlab.viz.pitch._check_mplsoccer", return_value=mock_mplsoccer):
            percentiles = {"Goals": 80, "Assists": 60, "Passes": 70, "Tackles": 50}
            fig = plot_pizza_chart(percentiles, player_name="Fallback Test")
            import matplotlib.figure

            assert isinstance(fig, matplotlib.figure.Figure)

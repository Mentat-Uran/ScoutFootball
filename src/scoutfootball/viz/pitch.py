"""Football pitch visualization using mplsoccer.

Provides pitch drawing, shot maps, pass maps, heatmaps, and pizza charts.
All functions return matplotlib Figure objects that can be displayed in Streamlit
via st.pyplot() or saved to disk.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _check_mplsoccer() -> Any:
    """Import mplsoccer lazily; raise ImportError with helpful message if missing."""
    try:
        import mplsoccer

        return mplsoccer
    except ImportError:
        raise ImportError(
            "mplsoccer is required for pitch visualizations. "
            "Install it with: uv add mplsoccer"
        ) from None


def _make_pitch(pitch_type: str, orientation: str, half: bool = False) -> Any:
    """Create an mplsoccer Pitch or VerticalPitch instance."""
    mplsoccer = _check_mplsoccer()
    kwargs: dict[str, Any] = {
        "pitch_type": pitch_type,
        "half": half,
        "line_zorder": 2,
        "line_color": "#c7d5cc",
        "pitch_color": "#2b2b2b",
    }
    if orientation == "vertical":
        return mplsoccer.VerticalPitch(**kwargs)
    return mplsoccer.Pitch(**kwargs)


def _fallback_figure(message: str) -> Any:
    """Return a matplotlib Figure with a text message (used when mplsoccer is missing)."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=12, color="gray")
    ax.set_axis_off()
    return fig


def draw_pitch(
    pitch_type: str = "statsbomb",
    orientation: str = "vertical",
    half: bool = False,
) -> Any:
    """Draw an empty football pitch.

    Args:
        pitch_type: Pitch coordinate system ("statsbomb", "opta", "tracab", etc.)
        orientation: "vertical" or "horizontal"
        half: If True, draw only half the pitch

    Returns:
        matplotlib Figure
    """
    try:
        pitch = _make_pitch(pitch_type, orientation, half)
        fig, ax = pitch.draw(figsize=(6, 8) if orientation == "vertical" else (8, 6))
        return fig
    except ImportError:
        return _fallback_figure("mplsoccer not available")


def plot_shot_map(
    shots_df: pd.DataFrame,
    *,
    x_col: str = "x",
    y_col: str = "y",
    outcome_col: str = "shot_outcome",
    xg_col: str = "shot_statsbomb_xg",
    player_col: str = "player_name",
    pitch_type: str = "statsbomb",
) -> Any:
    """Plot shot locations on a pitch.

    Args:
        shots_df: DataFrame with shot data
        x_col, y_col: Coordinate columns
        outcome_col: Column indicating goal/miss/saved
        xg_col: xG value column
        player_col: Player name column for tooltips
        pitch_type: Pitch coordinate system

    Returns:
        matplotlib Figure
    """
    try:
        _check_mplsoccer()
    except ImportError:
        return _fallback_figure("mplsoccer not available")

    if shots_df.empty:
        pitch = _make_pitch(pitch_type, "vertical", half=True)
        fig, ax = pitch.draw(figsize=(6, 8))
        ax.text(0.5, 0.5, "No shot data", ha="center", va="center",
                fontsize=12, color="gray", transform=ax.transAxes)
        return fig

    for col in (x_col, y_col):
        if col not in shots_df.columns:
            return _fallback_figure(f"Column '{col}' not found in shot data")

    df = shots_df.dropna(subset=[x_col, y_col]).copy()
    if df.empty:
        return _fallback_figure("No valid coordinates in shot data")

    pitch = _make_pitch(pitch_type, "vertical", half=True)
    fig, ax = pitch.draw(figsize=(6, 8))

    outcome_colors: dict[str, str] = {
        "Goal": "#2ca02c",
        "Saved": "#ff7f0e",
        "Missed": "#d62728",
        "Blocked": "#9467bd",
        "Off T": "#d62728",
        "Saved to Post": "#ff7f0e",
        "Post": "#d62728",
    }

    outcomes = df[outcome_col].fillna("Unknown") if outcome_col in df.columns else "Unknown"
    colors = outcomes.map(outcome_colors).fillna("#1f77b4")

    xg_values = (
        pd.to_numeric(df[xg_col], errors="coerce").fillna(0.05)
        if xg_col in df.columns
        else 0.05
    )
    sizes = (xg_values * 300).clip(lower=20, upper=500)

    pitch.scatter(
        df[x_col], df[y_col],
        s=sizes, c=colors, alpha=0.7, edgecolors="white", linewidth=0.5,
        ax=ax, zorder=3,
    )

    handles = []
    import matplotlib.lines as mlines

    for label, color in outcome_colors.items():
        if label in outcomes.values:
            handles.append(mlines.Line2D([], [], marker="o", color="w",
                                         markerfacecolor=color, markersize=8, label=label))
    if handles:
        ax.legend(handles=handles, loc="lower left", fontsize=8, framealpha=0.8)

    return fig


def plot_pass_map(
    passes_df: pd.DataFrame,
    *,
    x_col: str = "x",
    y_col: str = "y",
    end_x_col: str = "pass_end_x",
    end_y_col: str = "pass_end_y",
    outcome_col: str = "pass_outcome",
    player_col: str = "player_name",
    pitch_type: str = "statsbomb",
) -> Any:
    """Plot pass locations and directions on a pitch.

    Args:
        passes_df: DataFrame with pass data
        x_col, y_col: Start coordinate columns
        end_x_col, end_y_col: End coordinate columns
        outcome_col: Column indicating complete/incomplete
        player_col: Player name column
        pitch_type: Pitch coordinate system

    Returns:
        matplotlib Figure
    """
    try:
        _check_mplsoccer()
    except ImportError:
        return _fallback_figure("mplsoccer not available")

    if passes_df.empty:
        pitch = _make_pitch(pitch_type, "vertical")
        fig, ax = pitch.draw(figsize=(6, 8))
        ax.text(0.5, 0.5, "No pass data", ha="center", va="center",
                fontsize=12, color="gray", transform=ax.transAxes)
        return fig

    for col in (x_col, y_col, end_x_col, end_y_col):
        if col not in passes_df.columns:
            return _fallback_figure(f"Column '{col}' not found in pass data")

    df = passes_df.dropna(subset=[x_col, y_col, end_x_col, end_y_col]).copy()
    if df.empty:
        return _fallback_figure("No valid coordinates in pass data")

    pitch = _make_pitch(pitch_type, "vertical")
    fig, ax = pitch.draw(figsize=(6, 8))

    is_complete = (
        df[outcome_col].isna() | (df[outcome_col] == "Complete")
        if outcome_col in df.columns
        else pd.Series(True, index=df.index)
    )

    complete = df[is_complete]
    incomplete = df[~is_complete]

    if not complete.empty:
        pitch.arrows(
            complete[x_col], complete[y_col],
            complete[end_x_col], complete[end_y_col],
            width=1.5, headwidth=4, headlength=4,
            color="#1f77b4", alpha=0.5, ax=ax, zorder=3,
        )

    if not incomplete.empty:
        pitch.arrows(
            incomplete[x_col], incomplete[y_col],
            incomplete[end_x_col], incomplete[end_y_col],
            width=1.5, headwidth=4, headlength=4,
            color="#d62728", alpha=0.5, ax=ax, zorder=3,
        )

    import matplotlib.lines as mlines

    handles = [
        mlines.Line2D([], [], color="#1f77b4", marker=">", linestyle="-",
                       markersize=6, label="Complete"),
        mlines.Line2D([], [], color="#d62728", marker=">", linestyle="-",
                       markersize=6, label="Incomplete"),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=8, framealpha=0.8)

    return fig


def plot_heatmap(
    events_df: pd.DataFrame,
    *,
    x_col: str = "x",
    y_col: str = "y",
    player_col: str | None = None,
    player_name: str | None = None,
    pitch_type: str = "statsbomb",
    bins: tuple[int, int] = (12, 8),
) -> Any:
    """Plot event density heatmap on a pitch.

    Args:
        events_df: DataFrame with event coordinates
        x_col, y_col: Coordinate columns
        player_col: Column to filter by player
        player_name: If provided, filter to this player
        pitch_type: Pitch coordinate system
        bins: Number of bins for heatmap

    Returns:
        matplotlib Figure
    """
    try:
        _check_mplsoccer()
    except ImportError:
        return _fallback_figure("mplsoccer not available")

    if events_df.empty:
        pitch = _make_pitch(pitch_type, "vertical")
        fig, ax = pitch.draw(figsize=(6, 8))
        ax.text(0.5, 0.5, "No event data", ha="center", va="center",
                fontsize=12, color="gray", transform=ax.transAxes)
        return fig

    for col in (x_col, y_col):
        if col not in events_df.columns:
            return _fallback_figure(f"Column '{col}' not found in event data")

    df = events_df.dropna(subset=[x_col, y_col]).copy()

    if player_col and player_name and player_col in df.columns:
        df = df[df[player_col] == player_name]

    if df.empty:
        pitch = _make_pitch(pitch_type, "vertical")
        fig, ax = pitch.draw(figsize=(6, 8))
        ax.text(0.5, 0.5, "No data after filtering", ha="center", va="center",
                fontsize=12, color="gray", transform=ax.transAxes)
        return fig

    pitch = _make_pitch(pitch_type, "vertical")
    fig, ax = pitch.draw(figsize=(6, 8))

    bin_stat = pitch.bin_statistic(df[x_col], df[y_col], bins=bins)
    pitch.heatmap(bin_stat, ax=ax, cmap="YlOrRd", zorder=2)
    pitch.label_heatmap(bin_stat, ax=ax, str_format="{:.0f}", fontsize=6, zorder=3)

    return fig


def plot_pizza_chart(
    percentiles: dict[str, float],
    *,
    player_name: str = "Player",
    position: str = "",
    compare_percentiles: dict[str, float] | None = None,
    compare_name: str | None = None,
) -> Any:
    """Plot a pizza chart (circular percentile radar) using mplsoccer PyPizza.

    Args:
        percentiles: Dict of {dimension_name: percentile_value (0-100)}
        player_name: Name of the player
        position: Position group for title
        compare_percentiles: Optional second player's percentiles for comparison
        compare_name: Name of comparison player

    Returns:
        matplotlib Figure
    """
    if not percentiles:
        return _fallback_figure("No percentile data provided")

    try:
        mplsoccer = _check_mplsoccer()
    except ImportError:
        return _fallback_figure("mplsoccer not available")

    params = list(percentiles.keys())
    values = [percentiles[p] for p in params]

    try:
        py_pizza = mplsoccer.PyPizza  # noqa: N806
    except AttributeError:
        return _pizza_fallback(params, values, player_name, position,
                               compare_percentiles, compare_name)

    if compare_percentiles:
        compare_values = [compare_percentiles.get(p, 0.0) for p in params]
        baker = py_pizza(
            params=params,
            straight_line_color="#c7d5cc",
            straight_line_lw=1,
            last_circle_lw=1,
            last_circle_color="#c7d5cc",
            other_circle_lw=0.5,
            other_circle_color="#c7d5cc",
            inner_circle_size=5,
        )
        fig, ax = baker.make_pizza(
            values,
            compare_values=compare_values,
            kwargs_slices=dict(
                facecolor="#1f77b4", edgecolor="#1f77b4", alpha=0.6,
            ),
            kwargs_compare=dict(
                facecolor="#d62728", edgecolor="#d62728", alpha=0.6,
            ),
            kwargs_params=dict(color="white", fontsize=9),
            kwargs_values=dict(color="white", fontsize=9),
        )
        title_parts = [player_name]
        if position:
            title_parts.append(f"({position})")
        title_parts.append(f"vs {compare_name or 'Comparison'}")
        ax.set_title(" ".join(title_parts), color="white", fontsize=12, pad=20)
    else:
        baker = py_pizza(
            params=params,
            straight_line_color="#c7d5cc",
            straight_line_lw=1,
            last_circle_lw=1,
            last_circle_color="#c7d5cc",
            other_circle_lw=0.5,
            other_circle_color="#c7d5cc",
            inner_circle_size=5,
        )
        fig, ax = baker.make_pizza(
            values,
            kwargs_slices=dict(
                facecolor="#1f77b4", edgecolor="#1f77b4", alpha=0.6,
            ),
            kwargs_params=dict(color="white", fontsize=9),
            kwargs_values=dict(color="white", fontsize=9),
        )
        title_parts = [player_name]
        if position:
            title_parts.append(f"({position})")
        ax.set_title(" ".join(title_parts), color="white", fontsize=12, pad=20)

    fig.patch.set_facecolor("#2b2b2b")
    return fig


def _pizza_fallback(
    params: list[str],
    values: list[float],
    player_name: str,
    position: str,
    compare_percentiles: dict[str, float] | None,
    compare_name: str | None,
) -> Any:
    """Fallback pizza chart using matplotlib polar plot when PyPizza is unavailable."""
    import matplotlib.pyplot as plt
    import numpy as np

    n = len(params)
    if n < 3:
        return _fallback_figure("Need at least 3 dimensions for pizza chart")

    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    values_closed = values + [values[0]]
    angles_closed = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    ax.set_facecolor("#2b2b2b")
    fig.patch.set_facecolor("#2b2b2b")

    ax.fill(angles_closed, values_closed, alpha=0.25, color="#1f77b4")
    ax.plot(angles_closed, values_closed, color="#1f77b4", linewidth=1.5)

    if compare_percentiles:
        compare_values = [compare_percentiles.get(p, 0.0) for p in params]
        compare_closed = compare_values + [compare_values[0]]
        ax.fill(angles_closed, compare_closed, alpha=0.25, color="#d62728")
        ax.plot(angles_closed, compare_closed, color="#d62728", linewidth=1.5)

    ax.set_xticks(angles)
    ax.set_xticklabels(params, fontsize=8, color="white")
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(["25", "50", "75", "100"], fontsize=7, color="gray")
    ax.tick_params(colors="gray")
    ax.spines["polar"].set_color("gray")

    title_parts = [player_name]
    if position:
        title_parts.append(f"({position})")
    ax.set_title(" ".join(title_parts), color="white", fontsize=12, pad=20)

    return fig

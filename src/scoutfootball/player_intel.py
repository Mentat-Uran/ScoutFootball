"""Player career intelligence helpers.

Pure-Python analytics that extend a player profile with career trajectory,
multi-position role fit, peer-group benchmarking and multi-player
comparison. The functions in this module are intentionally side-effect free
and operate on pandas DataFrames already loaded by ``data_loader`` so they
can be unit-tested with synthetic frames and reused by both the API and
CLI layers.

Design notes
------------
* ``compute_career_trajectory`` replaces the legacy 3-season trend with a
  full career arc: peak detection, development phase labelling and
  year-over-year deltas. It does **not** fabricate missing seasons — gaps
  are surfaced explicitly.
* ``compute_role_fit_scores`` measures how well a player's statistical
  profile matches each position group via cosine similarity to the
  **position centroid** (mean z-vector of players at that position),
  z-scored against the overall rated population. Cosine similarity
  captures directional alignment, so elite players who are extreme in
  their position's key dimensions still score high. Only
  role-distinguishing features (attack, creation, defense, possession)
  are used — quality/availability dimensions are excluded so elite
  players don't score high on every position. Equal feature weights are
  used because the centroid already encodes position-specific
  expectations. A position is only marked as an alternative fit when its
  peer pool has enough samples to be meaningful.
* ``compute_peer_benchmark`` groups by position + league tier + minutes
  band (no age/birth-date dependency, since the rating matrix does not
  carry a reliable birth year).
* ``compute_pairwise_similarity`` is a helper shared with the multi-player
  comparison endpoint so the similarity matrix uses the same z-scored
  cosine distance as ``find_similar_players``.

None of these functions write to disk or mutate the input frame.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# Reuse the position-weight table and feature list from ``api`` so role
# fit stays aligned with similarity search. Imported lazily inside helpers
# to avoid a circular import at module load time.

_BIG5_LEAGUES = {
    "Premier League",
    "La Liga",
    "Bundesliga",
    "Serie A",
    "Ligue 1",
}

_POSITION_GROUPS = ("GK", "CB", "FB", "DM", "CM", "AM", "W", "ST")

_MIN_PEER_SAMPLES = 5
_MIN_PEAK_MINUTES = 900.0
# Fit-score thresholds. ``alternative`` is a credible secondary position,
# ``stretch`` is a plausible but unproven conversion, anything below is
# treated as a poor fit and surfaced only for transparency.
_ALTERNATIVE_FIT_THRESHOLD = 60.0
_STRETCH_FIT_THRESHOLD = 40.0

# Features used for role-fit scoring. Unlike similarity search (which
# includes ``optimized_score`` and ``minutes``), role fit deliberately
# excludes quality/availability dimensions — a player's position fit is
# about *what* they do (attack vs defense vs possession), not *how good*
# they are. Including overall_score and minutes lets elite players score
# high on every position because their z-vector points uniformly positive,
# drowning out the role signal.
_ROLE_FIT_FEATURES = (
    "npg_p90",
    "assists_p90",
    "defense_composite",
    "possession_composite",
)


# ── Career trajectory ────────────────────────────────────────────────────


def compute_career_trajectory(player_rows: pd.DataFrame) -> dict[str, Any]:
    """Build a full career trajectory from a player's season rows.

    Parameters
    ----------
    player_rows:
        DataFrame containing every rated season for a single player.
        Must include ``season`` plus the standard rating columns
        (``optimized_score``, ``minutes`` etc.).

    Returns
    -------
    dict
        ``seasons`` (chronological list with per-season metrics),
        ``peak`` (best season by score subject to a minutes floor),
        ``phases`` (prospect / prime / decline segmentation),
        ``yoy_deltas`` (year-over-year changes), ``position_transitions``
        and ``metrics`` (summary statistics). Empty input yields an empty
        trajectory with ``n_seasons=0``.
    """
    if player_rows.empty:
        return {
            "seasons": [],
            "peak": None,
            "phases": [],
            "yoy_deltas": [],
            "position_transitions": [],
            "metrics": {
                "n_seasons": 0,
                "career_avg_score": None,
                "peak_score": None,
                "min_score": None,
                "max_score": None,
                "score_consistency_std": None,
                "trajectory_slope": None,
                "career_minutes_total": 0,
            },
            "disclaimer": (
                "Trajectory unavailable: no rated seasons on record for "
                "this player."
            ),
        }

    df = player_rows.copy()
    df["season"] = df["season"].astype(str)
    df = df.sort_values("season", ascending=True).reset_index(drop=True)

    seasons: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        score = _safe_float(r.get("optimized_score"))
        minutes = _safe_float(r.get("minutes"))
        seasons.append({
            "season": str(r.get("season", "")),
            "team": str(r.get("team", "")),
            "league": str(r.get("league", "")),
            "position_group": str(r.get("position_group", "")),
            "optimized_score": round(score, 1) if score is not None else None,
            "minutes": round(minutes) if minutes is not None else None,
            "npg_p90": _round_or_none(_safe_float(r.get("npg_p90")), 3),
            "assists_p90": _round_or_none(_safe_float(r.get("assists_p90")), 3),
            "defense_composite": _round_or_none(
                _safe_float(r.get("defense_composite")), 2
            ),
            "possession_composite": _round_or_none(
                _safe_float(r.get("possession_composite")), 2
            ),
        })

    # Peak detection: best optimized_score among seasons meeting the
    # minutes floor. Falls back to the highest-score season if none meet
    # the floor (e.g. short-career prospects).
    eligible = df[df["minutes"].fillna(0) >= _MIN_PEAK_MINUTES]
    peak_row = (
        eligible.loc[eligible["optimized_score"].idxmax()]
        if not eligible.empty
        else df.loc[df["optimized_score"].idxmax()]
    )
    peak_index = int(df.index.get_loc(peak_row.name))
    peak = {
        "season": str(peak_row.get("season", "")),
        "optimized_score": round(_safe_float(peak_row.get("optimized_score")), 1),
        "minutes": round(_safe_float(peak_row.get("minutes"))),
        "team": str(peak_row.get("team", "")),
        "league": str(peak_row.get("league", "")),
        "index": peak_index,
    }

    phases = _compute_development_phases(df, peak_index)
    yoy_deltas = _compute_yoy_deltas(df)
    position_transitions = _compute_position_transitions(df)

    scores = df["optimized_score"].dropna()
    minutes_total = float(df["minutes"].fillna(0).sum())
    metrics = {
        "n_seasons": int(len(df)),
        "career_avg_score": round(float(scores.mean()), 1) if not scores.empty else None,
        "peak_score": round(float(scores.max()), 1) if not scores.empty else None,
        "min_score": round(float(scores.min()), 1) if not scores.empty else None,
        "max_score": round(float(scores.max()), 1) if not scores.empty else None,
        "score_consistency_std": (
            round(float(scores.std(ddof=0)), 2) if len(scores) >= 2 else 0.0
        ),
        "trajectory_slope": _compute_trajectory_slope(df),
        "career_minutes_total": round(minutes_total),
    }

    return {
        "seasons": seasons,
        "peak": peak,
        "phases": phases,
        "yoy_deltas": yoy_deltas,
        "position_transitions": position_transitions,
        "metrics": metrics,
        "disclaimer": (
            "Trajectory covers only seasons present in the local rating "
            "matrix; loans, youth campaigns and unbroadcast competitions "
            "may be missing. Phases are heuristic labels, not medical or "
            "contractual career stage statements."
        ),
    }


def _compute_development_phases(
    df: pd.DataFrame, peak_index: int
) -> list[dict[str, Any]]:
    """Label career phases relative to the peak season."""
    phases: list[dict[str, Any]] = []
    if df.empty:
        return phases

    n = len(df)
    # Prime window: peak ± 1 season (clamped to the available range).
    prime_start = max(0, peak_index - 1)
    prime_end = min(n - 1, peak_index + 1)

    if prime_start > 0:
        phases.append({
            "phase": "prospect",
            "season_start": str(df.iloc[0]["season"]),
            "season_end": str(df.iloc[prime_start - 1]["season"]),
            "description": (
                "Pre-peak seasons; role, minutes and output typically still "
                "developing."
            ),
        })

    phases.append({
        "phase": "prime",
        "season_start": str(df.iloc[prime_start]["season"]),
        "season_end": str(df.iloc[prime_end]["season"]),
        "description": (
            "Peak window: seasons immediately around the career-high "
            "rating. Sample size and role usually at their strongest."
        ),
    })

    if prime_end < n - 1:
        post_peak = df.iloc[prime_end + 1:]
        peak_score = _safe_float(df.iloc[peak_index]["optimized_score"]) or 0.0
        last_score = _safe_float(post_peak.iloc[-1]["optimized_score"]) or 0.0
        drop_pct = (
            ((peak_score - last_score) / peak_score * 100.0)
            if peak_score > 0 else 0.0
        )
        phase_label = "decline" if drop_pct >= 10.0 else "veteran"
        phases.append({
            "phase": phase_label,
            "season_start": str(post_peak.iloc[0]["season"]),
            "season_end": str(post_peak.iloc[-1]["season"]),
            "description": (
                f"Post-peak seasons (rating drop ≈{drop_pct:.1f}% vs peak). "
                "May reflect age-related decline, role change or reduced "
                "minutes rather than ability loss."
                if phase_label == "decline"
                else (
                    "Post-peak seasons with rating broadly maintained. "
                    "Often reflects an experienced rotational or "
                    "specialist role."
                )
            ),
        })

    return phases


def _compute_yoy_deltas(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute season-over-season changes for the key trajectory metrics."""
    deltas: list[dict[str, Any]] = []
    if len(df) < 2:
        return deltas

    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]
        prev_score = _safe_float(prev.get("optimized_score"))
        curr_score = _safe_float(curr.get("optimized_score"))
        prev_min = _safe_float(prev.get("minutes"))
        curr_min = _safe_float(curr.get("minutes"))
        prev_npg = _safe_float(prev.get("npg_p90"))
        curr_npg = _safe_float(curr.get("npg_p90"))
        prev_ast = _safe_float(prev.get("assists_p90"))
        curr_ast = _safe_float(curr.get("assists_p90"))
        deltas.append({
            "from_season": str(prev.get("season", "")),
            "to_season": str(curr.get("season", "")),
            "score_change": round(curr_score - prev_score, 1)
            if prev_score is not None and curr_score is not None
            else None,
            "minutes_change": round(curr_min - prev_min)
            if prev_min is not None and curr_min is not None
            else None,
            "goals_change": round(curr_npg - prev_npg, 3)
            if prev_npg is not None and curr_npg is not None
            else None,
            "assists_change": round(curr_ast - prev_ast, 3)
            if prev_ast is not None and curr_ast is not None
            else None,
        })
    return deltas


def _compute_position_transitions(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Detect seasons where the recorded position group changed."""
    transitions: list[dict[str, Any]] = []
    if "position_group" not in df.columns or len(df) < 2:
        return transitions

    for i in range(1, len(df)):
        prev_pos = str(df.iloc[i - 1].get("position_group", ""))
        curr_pos = str(df.iloc[i].get("position_group", ""))
        if prev_pos and curr_pos and prev_pos != curr_pos:
            transitions.append({
                "from_season": str(df.iloc[i - 1].get("season", "")),
                "to_season": str(df.iloc[i].get("season", "")),
                "from_position": prev_pos,
                "to_position": curr_pos,
                "note": (
                    "Position label changed between seasons. May reflect a "
                    "real role change or a data-source reclassification."
                ),
            })
    return transitions


def _compute_trajectory_slope(df: pd.DataFrame) -> float | None:
    """Least-squares slope of optimized_score vs season index."""
    scores = df["optimized_score"].dropna()
    if len(scores) < 2:
        return None
    x = np.arange(len(scores), dtype=float)
    y = scores.to_numpy(dtype=float)
    if y.std() == 0:
        return 0.0
    slope = float(np.polyfit(x, y, 1)[0])
    return round(slope, 3)


# ── Role fit scores ──────────────────────────────────────────────────────


def compute_role_fit_scores(
    target_row: pd.Series, df: pd.DataFrame
) -> dict[str, Any]:
    """Estimate how well a player's profile fits each position group.

    The score is a 0–100 scaled **cosine similarity** between the
    player's z-score vector and the **position centroid** (mean z-vector
    of players actually deployed in that position). Both vectors are
    z-scored relative to the overall rated population so the centroid
    direction reflects what distinguishes a position from the league at
    large (e.g. strikers sit above-average in ``npg_p90`` and
    below-average in ``defense_composite``). Cosine similarity measures
    directional alignment, not magnitude — an elite player who is
    extreme in their position's key dimensions still scores high because
    their profile points in the same direction as the centroid.

    Only role-distinguishing features (attack, creation, defense,
    possession) are used — ``optimized_score`` and ``minutes`` are
    excluded because they measure quality/availability, not positional
    role, and would otherwise let elite players score high on every
    position. Equal feature weights are used (rather than the per-position
    weights from similarity search) because the centroid already encodes
    the position-specific profile, and zero-weight features (e.g.
    ``npg_p90`` for GK) would be silently dropped from the similarity,
    causing outfield players to spuriously match the GK centroid.

    A position is only flagged as an ``alternative`` or ``stretch`` fit
    when its peer pool has enough samples to compute a meaningful
    centroid.
    """
    feature_cols = list(_ROLE_FIT_FEATURES)
    target_pos = str(target_row.get("position_group", "")).strip().upper()

    # Overall population statistics. Z-scoring against the full pool (not a
    # per-position pool) is what makes the centroid direction meaningful:
    # a striker centroid will have positive z in npg_p90 and negative z
    # in defense_composite relative to all rated players.
    overall_mat = df[feature_cols].apply(
        pd.to_numeric, errors="coerce"
    ).fillna(0.0).to_numpy(dtype=float)
    overall_mean = overall_mat.mean(axis=0)
    overall_std = overall_mat.std(axis=0, ddof=0)
    overall_std_safe = np.where(overall_std == 0, 1.0, overall_std)

    # Z-score the target relative to the overall population.
    target_vec = np.array(
        [_safe_float(target_row.get(c)) or 0.0 for c in feature_cols],
        dtype=float,
    )
    z_target = (target_vec - overall_mean) / overall_std_safe

    scores: dict[str, dict[str, Any]] = {}
    for pos in _POSITION_GROUPS:
        pool = df[df["position_group"].str.upper() == pos]
        sample_size = int(len(pool))
        if sample_size < _MIN_PEER_SAMPLES:
            scores[pos] = {
                "fit_score": None,
                "confidence": "insufficient_samples",
                "sample_size": sample_size,
                "note": (
                    f"Fewer than {_MIN_PEER_SAMPLES} rated {pos} players in "
                    "the local matrix; fit score withheld to avoid "
                    "overreading a thin pool."
                ),
            }
            continue

        # Position centroid: mean z-vector of players at this position,
        # z-scored relative to the overall population. The centroid
        # already encodes what's typical for the position, so equal
        # feature weights are used — no position-specific weighting needed.
        pool_mat = pool[feature_cols].apply(
            pd.to_numeric, errors="coerce"
        ).fillna(0.0).to_numpy(dtype=float)
        pool_z = (pool_mat - overall_mean) / overall_std_safe
        centroid = pool_z.mean(axis=0)

        # Cosine similarity between the target and the centroid. This
        # measures directional alignment: a player whose strengths match
        # the position's typical profile gets a high score, regardless of
        # whether they are above or below the centroid's magnitude.
        norm_a = float(np.linalg.norm(z_target))
        norm_b = float(np.linalg.norm(centroid))
        if norm_a == 0 or norm_b == 0:
            fit_score = 0.0
        else:
            cos_sim = float(np.dot(z_target, centroid) / (norm_a * norm_b))
            # Map [-1, 1] -> [0, 100] so a perfectly aligned profile is
            # 100 and an anti-aligned profile is 0.
            fit_score = max(0.0, min(100.0, (cos_sim + 1.0) * 50.0))

        confidence = "HIGH" if sample_size >= 30 else "MEDIUM"
        scores[pos] = {
            "fit_score": round(fit_score, 1),
            "confidence": confidence,
            "sample_size": sample_size,
        }

    # Classify positions into primary / alternative / stretch / poor.
    classified = [
        (pos, info["fit_score"])
        for pos, info in scores.items()
        if info.get("fit_score") is not None
    ]
    classified.sort(key=lambda x: x[1], reverse=True)

    primary = classified[0] if classified else None
    alternatives = [
        {"position": p, "fit_score": s}
        for p, s in classified[1:]
        if s >= _ALTERNATIVE_FIT_THRESHOLD
    ]
    stretches = [
        {"position": p, "fit_score": s}
        for p, s in classified[1:]
        if _STRETCH_FIT_THRESHOLD <= s < _ALTERNATIVE_FIT_THRESHOLD
    ]
    poor_fits = [
        {"position": p, "fit_score": s}
        for p, s in classified[1:]
        if s < _STRETCH_FIT_THRESHOLD
    ]

    return {
        "scores": scores,
        "primary_fit": {
            "position": primary[0],
            "fit_score": primary[1],
            "matches_current_role": primary[0] == target_pos,
        }
        if primary
        else None,
        "alternative_fits": alternatives,
        "stretch_fits": stretches,
        "poor_fits": poor_fits,
        "current_position": target_pos or None,
        "disclaimer": (
            "Role fit is a heuristic overlay on the local rating matrix; "
            "it does not account for tactical system, manager preference, "
            "injury history or actual deployment. Alternative fits are "
            "exploratory leads, not positional reassignments."
        ),
    }


# ── Peer group benchmarking ──────────────────────────────────────────────


def _league_tier(league: str) -> str:
    """Classify a league as Big 5 or Other."""
    if not league:
        return "other"
    return "big5" if league in _BIG5_LEAGUES else "other"


def _minutes_band(minutes: float | None) -> str:
    """Bucket minutes into a role band."""
    if minutes is None:
        return "unknown"
    if minutes >= 1800:
        return "starter"
    if minutes >= 600:
        return "rotation"
    return "squad"


_PEER_METRICS = (
    "optimized_score",
    "npg_p90",
    "assists_p90",
    "defense_composite",
    "possession_composite",
    "minutes",
)


def compute_peer_benchmark(
    target_row: pd.Series, df: pd.DataFrame
) -> dict[str, Any]:
    """Rank a player against their position + league tier + minutes peers."""
    target_pos = str(target_row.get("position_group", "")).strip().upper()
    target_league = str(target_row.get("league", ""))
    target_minutes = _safe_float(target_row.get("minutes"))
    tier = _league_tier(target_league)
    band = _minutes_band(target_minutes)

    peer_mask = (
        df["position_group"].str.upper().eq(target_pos)
        & df["league"].apply(_league_tier).eq(tier)
        & df["minutes"].apply(_minutes_band).eq(band)
    )
    peers = df[peer_mask].copy()
    peer_size = int(len(peers))

    if peer_size < _MIN_PEER_SAMPLES:
        return {
            "peer_group": {
                "position_group": target_pos or None,
                "league_tier": tier,
                "minutes_band": band,
                "size": peer_size,
            },
            "metrics": {},
            "top_peers": [],
            "summary": {
                "overall_rank": None,
                "overall_percentile": None,
                "comparison_note": (
                    f"Peer group has only {peer_size} players; benchmark "
                    "withheld to avoid overreading a thin slice."
                ),
            },
            "disclaimer": _PEER_DISCLAIMER,
        }

    metrics: dict[str, dict[str, Any]] = {}
    for col in _PEER_METRICS:
        target_val = _safe_float(target_row.get(col))
        series = pd.to_numeric(peers[col], errors="coerce").dropna()
        if series.empty or target_val is None:
            metrics[col] = {
                "value": target_val,
                "percentile": None,
                "rank": None,
                "peer_group_size": int(len(series)),
            }
            continue
        percentile = float((series < target_val).sum() / len(series) * 100.0)
        rank = int((series > target_val).sum()) + 1
        metrics[col] = {
            "value": round(target_val, 3) if col != "minutes" else round(target_val),
            "percentile": round(percentile, 1),
            "rank": rank,
            "peer_group_size": int(len(series)),
        }

    # Overall percentile: average of available metric percentiles,
    # weighted toward optimized_score (the primary rating signal).
    weights = {
        "optimized_score": 0.40,
        "npg_p90": 0.15,
        "assists_p90": 0.15,
        "defense_composite": 0.10,
        "possession_composite": 0.10,
        "minutes": 0.10,
    }
    available = [
        (metrics[c]["percentile"], weights[c])
        for c in weights
        if metrics.get(c, {}).get("percentile") is not None
    ]
    if available:
        total_w = sum(w for _, w in available)
        overall_pct = sum(p * w for p, w in available) / total_w if total_w else 0.0
    else:
        overall_pct = None

    overall_rank = None
    if overall_pct is not None:
        overall_rank = int(peer_size - int(overall_pct * peer_size / 100.0))
        overall_rank = max(1, min(peer_size, overall_rank))

    # Top peers by optimized_score (excluding the target player).
    target_name = str(target_row.get("player", ""))
    top_peers_df = peers[peers["player"] != target_name].sort_values(
        "optimized_score", ascending=False
    ).head(5)
    top_peers: list[dict[str, Any]] = []
    for _, r in top_peers_df.iterrows():
        top_peers.append({
            "player": str(r.get("player", "")),
            "team": str(r.get("team", "")),
            "league": str(r.get("league", "")),
            "season": str(r.get("season", "")),
            "optimized_score": round(_safe_float(r.get("optimized_score")), 1),
            "minutes": round(_safe_float(r.get("minutes"))),
        })

    return {
        "peer_group": {
            "position_group": target_pos or None,
            "league_tier": tier,
            "minutes_band": band,
            "size": peer_size,
        },
        "metrics": metrics,
        "top_peers": top_peers,
        "summary": {
            "overall_rank": overall_rank,
            "overall_percentile": round(overall_pct, 1)
            if overall_pct is not None
            else None,
            "comparison_note": (
                f"Ranked against {peer_size} players in the same position "
                f"group, {tier} league tier and {band} minutes band."
            ),
        },
        "disclaimer": _PEER_DISCLAIMER,
    }


_PEER_DISCLAIMER = (
    "Peer benchmark is computed from the local rating matrix only; it does "
    "not adjust for age, contract status, tactical role or scouting "
    "preferences. Top peers are listed for exploration and are not "
    "transfer recommendations."
)


# ── Pairwise similarity (shared with multi-compare) ──────────────────────


def compute_pairwise_similarity(
    row_a: pd.Series, row_b: pd.Series, df: pd.DataFrame
) -> float | None:
    """Cosine similarity between two player rows, position-weighted.

    Reuses the per-position feature weights from ``api`` so multi-compare
    similarity is consistent with ``find_similar_players``. Returns
    ``None`` when the vectors are degenerate.
    """
    from scoutfootball.api import _POSITION_FEATURE_WEIGHTS, _SIMILARITY_FEATURES

    feature_cols = [fc[0] for fc in _SIMILARITY_FEATURES]
    pos_a = str(row_a.get("position_group", "")).strip().upper()
    # Use the target (a) position weights; this mirrors the existing
    # similarity contract where the target drives the weighting.
    weights = _POSITION_FEATURE_WEIGHTS.get(pos_a, {})

    pool = df[df["position_group"].str.upper() == pos_a]
    if len(pool) < _MIN_PEER_SAMPLES:
        # Fall back to the full dataset when the position pool is thin.
        pool = df

    pool_mat = pool[feature_cols].apply(
        pd.to_numeric, errors="coerce"
    ).fillna(0.0).to_numpy(dtype=float)
    mean = pool_mat.mean(axis=0)
    std = pool_mat.std(axis=0, ddof=0)
    std_safe = np.where(std == 0, 1.0, std)

    vec_a = np.array(
        [_safe_float(row_a.get(c)) or 0.0 for c in feature_cols], dtype=float
    )
    vec_b = np.array(
        [_safe_float(row_b.get(c)) or 0.0 for c in feature_cols], dtype=float
    )
    z_a = (vec_a - mean) / std_safe
    z_b = (vec_b - mean) / std_safe
    weight_vec = np.array(
        [float(weights.get(c, 1.0)) for c in feature_cols], dtype=float
    )
    z_a_w = z_a * weight_vec
    z_b_w = z_b * weight_vec
    norm_a = float(np.linalg.norm(z_a_w))
    norm_b = float(np.linalg.norm(z_b_w))
    if norm_a == 0 or norm_b == 0:
        return None
    cos = float(np.dot(z_a_w, z_b_w) / (norm_a * norm_b))
    # Clamp to [0, 1] for a friendly similarity scale (negative cosine
    # similarity is rare for these feature vectors but technically
    # possible).
    return round(max(0.0, min(1.0, cos)), 3)


# ── Multi-player comparison ──────────────────────────────────────────────


_MULTI_COMPARE_MIN = 2
_MULTI_COMPARE_MAX = 6


def compute_multi_player_comparison(
    player_rows_by_name: dict[str, pd.Series],
    df: pd.DataFrame,
) -> dict[str, Any]:
    """Compare 2–6 players side-by-side with a percentile matrix.

    Parameters
    ----------
    player_rows_by_name:
        Ordered mapping of player name -> chosen season row. The order
        is preserved in all output lists so the caller can map values
        back to the original query.
    df:
        Full ratings DataFrame used to compute percentiles.
    """
    n = len(player_rows_by_name)
    if n < _MULTI_COMPARE_MIN:
        return {
            "error": "need_at_least_two_players",
            "n_players": n,
            "min_required": _MULTI_COMPARE_MIN,
        }
    if n > _MULTI_COMPARE_MAX:
        return {
            "error": "too_many_players",
            "n_players": n,
            "max_allowed": _MULTI_COMPARE_MAX,
        }

    names = list(player_rows_by_name.keys())

    # Per-player summary block.
    players: list[dict[str, Any]] = []
    for name in names:
        row = player_rows_by_name[name]
        players.append({
            "name": name,
            "team": str(row.get("team", "")),
            "league": str(row.get("league", "")),
            "season": str(row.get("season", "")),
            "position_group": str(row.get("position_group", "")),
            "optimized_score": round(_safe_float(row.get("optimized_score")), 1),
            "minutes": round(_safe_float(row.get("minutes"))),
            "confidence_level": str(row.get("confidence_level", "LOW")).upper(),
        })

    # Percentile matrix across the radar dimensions. Percentiles are
    # computed within each player's own position pool (apples-to-apples
    # across positions) so a CB and an ST can sit on the same chart.
    from scoutfootball.api import _SIMILARITY_FEATURES

    percentile_matrix: list[dict[str, Any]] = []
    for col, label in _SIMILARITY_FEATURES:
        row_entry: dict[str, Any] = {
            "dimension": col,
            "label": label,
            "values": [],
        }
        for name in names:
            row = player_rows_by_name[name]
            pos = str(row.get("position_group", "")).strip().upper()
            pool = df[df["position_group"].str.upper() == pos]
            val = _safe_float(row.get(col))
            if val is None or pool.empty:
                row_entry["values"].append(None)
                continue
            series = pd.to_numeric(pool[col], errors="coerce").dropna()
            if series.empty:
                row_entry["values"].append(None)
                continue
            pct = float((series < val).sum() / len(series) * 100.0)
            row_entry["values"].append(round(pct, 1))
        percentile_matrix.append(row_entry)

    # Per-metric ranking across the chosen players (raw values).
    metric_rankings: list[dict[str, Any]] = []
    ranking_cols = (
        "optimized_score",
        "npg_p90",
        "assists_p90",
        "defense_composite",
        "possession_composite",
        "minutes",
    )
    for col in ranking_cols:
        values: list[tuple[str, float | None]] = []
        for name in names:
            v = _safe_float(player_rows_by_name[name].get(col))
            values.append((name, v))
        # Higher is better for all of these metrics.
        ranked = sorted(
            values,
            key=lambda nv: (nv[1] is not None, nv[1] or 0.0),
            reverse=True,
        )
        metric_rankings.append({
            "metric": col,
            "rankings": [
                {
                    "player": name,
                    "value": round(v, 3) if v is not None and col != "minutes"
                    else (round(v) if v is not None else None),
                    "rank": i + 1,
                }
                for i, (name, v) in enumerate(ranked)
            ],
        })

    # Composite ranking: average of percentile-matrix values per player.
    composite: list[dict[str, Any]] = []
    for idx, name in enumerate(names):
        pcts = [
            row["values"][idx]
            for row in percentile_matrix
            if row["values"][idx] is not None
        ]
        avg_pct = float(np.mean(pcts)) if pcts else 0.0
        composite.append({
            "player": name,
            "avg_percentile": round(avg_pct, 1),
            "n_dimensions": len(pcts),
        })
    composite.sort(key=lambda c: c["avg_percentile"], reverse=True)
    for i, c in enumerate(composite):
        c["rank"] = i + 1

    # Pairwise similarity matrix.
    pairwise: list[list[float | None]] = []
    for a_name in names:
        row_a = player_rows_by_name[a_name]
        row_entries: list[float | None] = []
        for b_name in names:
            if a_name == b_name:
                row_entries.append(1.0)
                continue
            row_b = player_rows_by_name[b_name]
            sim = compute_pairwise_similarity(row_a, row_b, df)
            row_entries.append(sim)
        pairwise.append(row_entries)

    same_position = len({
        str(r.get("position_group", "")).strip().upper()
        for r in player_rows_by_name.values()
    }) == 1

    return {
        "n_players": n,
        "players": players,
        "percentile_matrix": percentile_matrix,
        "metric_rankings": metric_rankings,
        "composite_ranking": composite,
        "pairwise_similarity": {
            "players": names,
            "matrix": pairwise,
        },
        "same_position": same_position,
        "disclaimer": (
            "Multi-player comparison uses each player's best rated season "
            "in the local matrix; percentile pools are position-internal "
            "so cross-position comparisons stay apples-to-apples. Pairwise "
            "similarity reuses the same position-weighted cosine distance "
            "as the similar-players endpoint."
        ),
    }


# ── Riser / decliner watchlist ───────────────────────────────────────────


def compute_riser_decliner_watchlist(
    df: pd.DataFrame,
    *,
    min_seasons: int = 2,
    min_minutes_latest: float = 300.0,
    top_n: int = 20,
    riser_threshold: float = 1.0,
    decliner_threshold: float = -1.0,
) -> dict[str, Any]:
    """Scan the full rating matrix for players on the steepest upward or
    downward career trajectories.

    The trajectory slope is the least-squares slope of ``optimized_score``
    against season index (see ``_compute_trajectory_slope``). A positive
    slope means the player has been improving across rated seasons; a
    negative slope means decline.

    Parameters
    ----------
    df:
        Full rating matrix DataFrame with one row per player-season.
    min_seasons:
        Minimum number of rated seasons required to compute a slope.
        Players with fewer seasons are excluded.
    min_minutes_latest:
        Minimum minutes in the most recent rated season. This filters out
        players whose latest season was a cameo or injury-limited campaign
        that would distort the "current" view.
    top_n:
        Maximum number of risers and decliners to return (each).
    riser_threshold:
        Minimum slope to be classified as a riser.
    decliner_threshold:
        Maximum (i.e. most negative) slope to be classified as a decliner.

    Returns
    -------
    dict
        ``risers`` and ``decliners`` lists, each with player name, team,
        position, current score, peak score, slope, n_seasons, and a
        human-readable trend label. Also returns ``n_scanned`` and a
        ``disclaimer``.
    """
    if df.empty:
        return {
            "risers": [],
            "decliners": [],
            "n_scanned": 0,
            "disclaimer": (
                "Riser/decliner scan unavailable: the local rating matrix "
                "is empty."
            ),
        }

    work = df.copy()
    # Ensure season is string for sorting.
    work["season"] = work["season"].astype(str)
    # Resolve player key: prefer player_id, fall back to player_name.
    if "player_id" in work.columns and work["player_id"].notna().any():
        key_col = "player_id"
    else:
        key_col = "player_name"

    risers: list[dict[str, Any]] = []
    decliners: list[dict[str, Any]] = []
    n_scanned = 0

    for _player_key, group in work.groupby(key_col, sort=False):
        group = group.sort_values("season", ascending=True).reset_index(drop=True)
        n_seasons = len(group)
        if n_seasons < min_seasons:
            continue

        # Check latest-season minutes floor.
        latest = group.iloc[-1]
        latest_minutes = _safe_float(latest.get("minutes")) or 0.0
        if latest_minutes < min_minutes_latest:
            continue

        n_scanned += 1
        slope = _compute_trajectory_slope(group)
        if slope is None:
            continue

        current_score = _safe_float(latest.get("optimized_score"))
        scores = group["optimized_score"].dropna()
        peak_score = float(scores.max()) if not scores.empty else None

        entry = {
            "player": str(latest.get("player", latest.get("player_name", ""))),
            "player_id": str(latest.get("player_id", "")) if "player_id" in group.columns else None,
            "team": str(latest.get("team", "")),
            "league": str(latest.get("league", "")),
            "position_group": str(latest.get("position_group", "")),
            "current_score": round(current_score, 1) if current_score is not None else None,
            "peak_score": round(peak_score, 1) if peak_score is not None else None,
            "trajectory_slope": slope,
            "n_seasons": n_seasons,
            "latest_season": str(latest.get("season", "")),
            "trend_label": (
                "rising" if slope > 0 else ("declining" if slope < 0 else "flat")
            ),
        }

        if slope >= riser_threshold:
            risers.append(entry)
        elif slope <= decliner_threshold:
            decliners.append(entry)

    # Sort risers by slope descending, decliners by slope ascending.
    risers.sort(key=lambda x: x["trajectory_slope"], reverse=True)
    decliners.sort(key=lambda x: x["trajectory_slope"])

    risers = risers[:top_n]
    decliners = decliners[:top_n]

    return {
        "risers": risers,
        "decliners": decliners,
        "n_scanned": n_scanned,
        "thresholds": {
            "min_seasons": min_seasons,
            "min_minutes_latest": min_minutes_latest,
            "riser_threshold": riser_threshold,
            "decliner_threshold": decliner_threshold,
        },
        "disclaimer": (
            "Riser/decliner classification is based on the least-squares "
            "slope of optimized_score across rated seasons in the local "
            "matrix. It does not account for injuries, tactical changes, "
            "loan spells, or seasons missing from the data. A rising "
            "slope is not a guarantee of future improvement, and a "
            "declining slope is not a transfer recommendation."
        ),
    }


# ── Small shared helpers ─────────────────────────────────────────────────


def _safe_float(value: Any) -> float | None:
    """Coerce a value to float, returning ``None`` for NaN/missing."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(f):
        return None
    return f


def _round_or_none(value: float | None, digits: int) -> float | None:
    if value is None:
        return None
    return round(value, digits)

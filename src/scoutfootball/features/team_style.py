"""Team tactical-style clustering.

Aggregates per-player style composites (attack, creation, defense,
possession) to team-season level using minutes-weighted means, then
groups teams into tactical-style clusters via k-means on standardised
features. The result is a compact, interpretable profile of how each
team plays relative to the league population.

The module is deliberately side-effect free and operates on a pandas
DataFrame already loaded by ``data_loader`` so it can be unit-tested
with synthetic frames and reused by both the API and CLI layers.

Design notes
------------
* The four style features mirror ``_ROLE_FIT_FEATURES`` in
  ``player_intel`` so that team-style clusters are directly
  interpretable in the same vocabulary as player role fit.
* Minutes-weighting follows the pattern in ``get_team_strength`` at
  ``api.py`` — players with more minutes contribute more to the team's
  style signature.
* k-means reuses the pattern from ``compute_error_clustering`` in
  ``backtests.py`` — lazy sklearn import, frozen dataclasses, defensive
  empty/degenerate handling, and a baked-in disclaimer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

_STYLE_FEATURES = (
    "npg_p90",
    "assists_p90",
    "defense_composite",
    "possession_composite",
)

_MIN_TEAMS_FOR_CLUSTERS = 4
_DEFAULT_N_CLUSTERS = 4
_MAX_N_CLUSTERS = 8
_MIN_MINUTES_TOTAL = 1800.0


@dataclass(frozen=True)
class TeamStyleProfile:
    """Single team's aggregated style signature."""

    team: str
    league: str
    season: str
    n_players: int
    total_minutes: float
    attack: float
    creation: float
    defense: float
    possession: float


@dataclass(frozen=True)
class TeamStyleCluster:
    """One k-means cluster of teams with a similar style profile."""

    cluster_id: int
    label: str
    n_teams: int
    centroid: dict[str, float]
    teams: list[str]


@dataclass(frozen=True)
class TeamStyleReport:
    """Full clustering report."""

    n_clusters: int
    n_teams: int
    n_scanned: int
    clusters: list[TeamStyleCluster]
    team_profiles: list[TeamStyleProfile]
    feature_means: dict[str, float]
    feature_stds: dict[str, float]
    disclaimer: str


def compute_team_style_profiles(
    df: pd.DataFrame,
    *,
    season: str | None = None,
    league: str | None = None,
    min_minutes_total: float = _MIN_MINUTES_TOTAL,
) -> list[TeamStyleProfile]:
    """Aggregate per-player style composites to team-season level.

    Parameters
    ----------
    df:
        Player ratings DataFrame with columns ``team``, ``league``,
        ``season``, ``minutes``, and the four style composites.
    season:
        Optional season filter (string match).
    league:
        Optional league filter (string match, case-insensitive).
    min_minutes_total:
        Minimum total minutes across all players for a team-season to
        be included. Filters out teams with too little data.
    """
    if df.empty:
        return []

    work = df.copy()
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]
    if league is not None:
        work = work[
            work["league"].astype(str).str.lower()
            == str(league).lower()
        ]
    if work.empty:
        return []

    profiles: list[TeamStyleProfile] = []
    for (team, league_v, season_v), group in work.groupby(
        ["team", "league", "season"], sort=False
    ):
        minutes = group["minutes"].apply(
            pd.to_numeric, errors="coerce"
        ).fillna(0.0).to_numpy(dtype=float)
        total_minutes = float(minutes.sum())
        if total_minutes < min_minutes_total:
            continue
        weights = minutes / total_minutes if total_minutes > 0 else None

        vals = {}
        for feat in _STYLE_FEATURES:
            col = group[feat].apply(
                pd.to_numeric, errors="coerce"
            ).fillna(0.0).to_numpy(dtype=float)
            if weights is not None:
                vals[feat] = float(np.average(col, weights=weights))
            else:
                vals[feat] = float(col.mean())

        profiles.append(
            TeamStyleProfile(
                team=str(team),
                league=str(league_v),
                season=str(season_v),
                n_players=int(len(group)),
                total_minutes=round(total_minutes),
                attack=round(vals["npg_p90"], 3),
                creation=round(vals["assists_p90"], 3),
                defense=round(vals["defense_composite"], 2),
                possession=round(vals["possession_composite"], 2),
            )
        )
    return profiles


# Human-readable labels for cluster centroids, keyed by the dominant
# feature direction. These are heuristic overlays, not definitive
# tactical classifications.
def _label_cluster(centroid: dict[str, float]) -> str:
    """Generate a heuristic label for a cluster based on its centroid."""
    if not centroid:
        return "balanced"
    max_feat = max(centroid, key=lambda k: abs(centroid[k]))
    val = centroid[max_feat]
    if abs(val) < 0.3:
        return "balanced"
    labels = {
        "npg_p90": "attacking" if val > 0 else "low-scoring",
        "assists_p90": "creative" if val > 0 else "direct",
        "defense_composite": "defensive" if val > 0 else "open",
        "possession_composite": "possession-heavy" if val > 0 else "counter-attacking",
    }
    return labels.get(max_feat, "balanced")


def compute_team_style_clusters(
    df: pd.DataFrame,
    *,
    season: str | None = None,
    league: str | None = None,
    n_clusters: int = _DEFAULT_N_CLUSTERS,
    min_minutes_total: float = _MIN_MINUTES_TOTAL,
    random_state: int = 42,
) -> dict[str, Any]:
    """Cluster teams into tactical-style groups via k-means.

    Parameters
    ----------
    df:
        Player ratings DataFrame.
    season, league:
        Optional filters passed to ``compute_team_style_profiles``.
    n_clusters:
        Number of k-means clusters (2–8).
    min_minutes_total:
        Minimum team-season total minutes for inclusion.
    random_state:
        Random seed for reproducible clustering.
    """
    n_clusters = max(2, min(_MAX_N_CLUSTERS, int(n_clusters)))

    profiles = compute_team_style_profiles(
        df,
        season=season,
        league=league,
        min_minutes_total=min_minutes_total,
    )

    if len(profiles) < _MIN_TEAMS_FOR_CLUSTERS:
        return {
            "status": "insufficient_teams",
            "n_teams": len(profiles),
            "n_clusters": 0,
            "n_scanned": len(profiles),
            "clusters": [],
            "team_profiles": [
                _profile_to_dict(p) for p in profiles
            ],
            "disclaimer": (
                f"Only {len(profiles)} team-seasons meet the minimum "
                f"minutes threshold ({min_minutes_total:.0f} min). At "
                f"least {_MIN_TEAMS_FOR_CLUSTERS} are needed for "
                "meaningful clustering."
            ),
        }

    # Build feature matrix.
    feat_cols = list(_STYLE_FEATURES)
    mat = np.array(
        [
            [getattr(p, _feat_to_attr(c)) for c in feat_cols]
            for p in profiles
        ],
        dtype=float,
    )

    means = mat.mean(axis=0)
    stds = mat.std(axis=0, ddof=0)
    stds_safe = np.where(stds == 0, 1.0, stds)
    standardized = (mat - means) / stds_safe

    # Adjust n_clusters if too few teams.
    effective_k = min(n_clusters, len(profiles))

    try:
        from sklearn.cluster import KMeans
    except ImportError:
        return {
            "status": "sklearn_unavailable",
            "n_teams": len(profiles),
            "n_clusters": 0,
            "n_scanned": len(profiles),
            "clusters": [],
            "team_profiles": [_profile_to_dict(p) for p in profiles],
            "disclaimer": (
                "scikit-learn is not installed; team-style clustering "
                "requires it. Install with `uv sync` or "
                "`pip install scikit-learn`."
            ),
        }

    km = KMeans(n_clusters=effective_k, random_state=random_state, n_init=10)
    labels = km.fit_predict(standardized)

    # Build cluster objects.
    clusters: list[dict[str, Any]] = []
    for cid in range(effective_k):
        mask = labels == cid
        members = [profiles[i] for i in range(len(profiles)) if mask[i]]
        if not members:
            continue
        centroid_std = standardized[mask].mean(axis=0)
        centroid_dict = {
            feat_cols[i]: round(float(centroid_std[i]), 3)
            for i in range(len(feat_cols))
        }
        clusters.append({
            "cluster_id": cid,
            "label": _label_cluster(centroid_dict),
            "n_teams": len(members),
            "centroid": centroid_dict,
            "teams": [p.team for p in members],
        })

    # Sort clusters by size descending.
    clusters.sort(key=lambda c: c["n_teams"], reverse=True)
    # Re-number after sort.
    for i, c in enumerate(clusters):
        c["cluster_id"] = i

    # Attach cluster assignment to each team profile.
    team_profiles_out = []
    for i, p in enumerate(profiles):
        d = _profile_to_dict(p)
        d["cluster_id"] = int(labels[i])
        team_profiles_out.append(d)

    return {
        "status": "ok",
        "n_clusters": effective_k,
        "n_teams": len(profiles),
        "n_scanned": len(profiles),
        "clusters": clusters,
        "team_profiles": team_profiles_out,
        "feature_means": {
            feat_cols[i]: round(float(means[i]), 3)
            for i in range(len(feat_cols))
        },
        "feature_stds": {
            feat_cols[i]: round(float(stds[i]), 3)
            for i in range(len(feat_cols))
        },
        "disclaimer": (
            "Team-style clusters are computed from minutes-weighted "
            "aggregates of per-player style composites in the local "
            "rating matrix. They describe statistical tendencies, not "
            "confirmed tactical systems. Cluster labels are heuristic "
            "overlays and may not match a manager's declared formation "
            "or strategy."
        ),
    }


def _feat_to_attr(feat: str) -> str:
    """Map a feature column name to the TeamStyleProfile attribute."""
    return {
        "npg_p90": "attack",
        "assists_p90": "creation",
        "defense_composite": "defense",
        "possession_composite": "possession",
    }[feat]


def _profile_to_dict(p: TeamStyleProfile) -> dict[str, Any]:
    return {
        "team": p.team,
        "league": p.league,
        "season": p.season,
        "n_players": p.n_players,
        "total_minutes": p.total_minutes,
        "attack": p.attack,
        "creation": p.creation,
        "defense": p.defense,
        "possession": p.possession,
    }

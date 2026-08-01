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

# Per-position weights over _STYLE_FEATURES, used by
# compute_scouting_target_style_match when use_position_weights=True. Each
# row sums to 1.0. Designed to emphasize the dimensions that matter most
# for evaluating similarity at that position (e.g. defense_composite
# dominates for CB, npg_p90 for ST). Cosine similarity is scale-invariant
# but not rotation-invariant, so applying different weights per dimension
# rotates both the target and candidate vectors toward the weighted axes
# and surfaces players whose style profile aligns on the position-critical
# dimensions. Non-additive interpretive overlay — does not modify the
# rating model.
_POSITION_STYLE_WEIGHTS: dict[str, dict[str, float]] = {
    "GK": {
        "npg_p90": 0.10, "assists_p90": 0.10,
        "defense_composite": 0.40, "possession_composite": 0.40,
    },
    "CB": {
        "npg_p90": 0.10, "assists_p90": 0.10,
        "defense_composite": 0.50, "possession_composite": 0.30,
    },
    "FB": {
        "npg_p90": 0.10, "assists_p90": 0.20,
        "defense_composite": 0.35, "possession_composite": 0.35,
    },
    "DM": {
        "npg_p90": 0.05, "assists_p90": 0.15,
        "defense_composite": 0.45, "possession_composite": 0.35,
    },
    "CM": {
        "npg_p90": 0.10, "assists_p90": 0.25,
        "defense_composite": 0.25, "possession_composite": 0.40,
    },
    "AM": {
        "npg_p90": 0.30, "assists_p90": 0.35,
        "defense_composite": 0.10, "possession_composite": 0.25,
    },
    "W": {
        "npg_p90": 0.30, "assists_p90": 0.35,
        "defense_composite": 0.10, "possession_composite": 0.25,
    },
    "ST": {
        "npg_p90": 0.50, "assists_p90": 0.25,
        "defense_composite": 0.10, "possession_composite": 0.15,
    },
}

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


def _aggregate_player_style_vector(
    player_df: pd.DataFrame,
) -> np.ndarray:
    """Minutes-weighted average of the four style composites for one player."""
    minutes = (
        player_df["minutes"]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
        .to_numpy(dtype=float)
    )
    total_min = float(minutes.sum())
    weights = minutes / total_min if total_min > 0 else None
    vec = np.zeros(len(_STYLE_FEATURES), dtype=float)
    for i, feat in enumerate(_STYLE_FEATURES):
        col = (
            player_df[feat]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0.0)
            .to_numpy(dtype=float)
        )
        if weights is not None:
            vec[i] = float(np.average(col, weights=weights))
        else:
            vec[i] = float(col.mean())
    return vec


def _cosine_to_fit_score(vec_std: np.ndarray, centroid: np.ndarray) -> tuple[float, float]:
    """Cosine similarity mapped to 0-100 fit score. Returns (fit_score, cos_sim)."""
    norm_p = float(np.linalg.norm(vec_std))
    norm_c = float(np.linalg.norm(centroid))
    if norm_p == 0 or norm_c == 0:
        cos_sim = 0.0
    else:
        cos_sim = float(np.dot(vec_std, centroid)) / (norm_p * norm_c)
    fit = max(0.0, min(100.0, (cos_sim + 1.0) * 50.0))
    return round(fit, 1), round(cos_sim, 3)


def compute_player_style_fit(
    df: pd.DataFrame,
    player_name: str,
    *,
    season: str | None = None,
    league: str | None = None,
    n_clusters: int = _DEFAULT_N_CLUSTERS,
    min_minutes_total: float = _MIN_MINUTES_TOTAL,
    random_state: int = 42,
) -> dict[str, Any]:
    """Compute a player's style-fit score to each team-style cluster.

    The player's four style composites are minutes-weighted across the
    matching rows, standardised using the team-style population stats,
    and compared to each cluster centroid via cosine similarity. The
    result is a per-cluster fit score (0–100) that describes statistical
    affinity — not confirmed tactical fit.

    Parameters
    ----------
    df:
        Player ratings DataFrame.
    player_name:
        Player name (case-insensitive match against ``player`` column).
    season, league:
        Optional filters applied to both cluster computation and player
        row selection.
    n_clusters, min_minutes_total, random_state:
        Forwarded to :func:`compute_team_style_clusters`.
    """
    if df.empty:
        return {
            "status": "no_data",
            "player": player_name,
            "clusters": [],
            "disclaimer": "Empty rating matrix.",
        }

    clusters_result = compute_team_style_clusters(
        df,
        season=season,
        league=league,
        n_clusters=n_clusters,
        min_minutes_total=min_minutes_total,
        random_state=random_state,
    )

    if clusters_result["status"] != "ok":
        return {
            "status": clusters_result["status"],
            "player": player_name,
            "clusters": [],
            "n_clusters": 0,
            "disclaimer": clusters_result.get("disclaimer", ""),
        }

    # Filter player rows with same season/league context.
    work = df.copy()
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]
    if league is not None:
        work = work[
            work["league"].astype(str).str.lower() == str(league).lower()
        ]
    player_df = work[
        work["player"].astype(str).str.lower() == str(player_name).lower()
    ]

    if player_df.empty:
        return {
            "status": "player_not_found",
            "player": player_name,
            "clusters": [],
            "n_clusters": len(clusters_result["clusters"]),
            "disclaimer": (
                f"No rating rows found for '{player_name}'"
                + (f" in season {season}" if season else "")
                + (f" / league {league}" if league else "")
                + "."
            ),
        }

    player_vec = _aggregate_player_style_vector(player_df)

    means = np.array(
        [clusters_result["feature_means"][f] for f in _STYLE_FEATURES],
        dtype=float,
    )
    stds = np.array(
        [clusters_result["feature_stds"][f] for f in _STYLE_FEATURES],
        dtype=float,
    )
    stds_safe = np.where(stds == 0, 1.0, stds)
    player_std = (player_vec - means) / stds_safe

    cluster_fits: list[dict[str, Any]] = []
    for cluster in clusters_result["clusters"]:
        centroid = np.array(
            [cluster["centroid"][f] for f in _STYLE_FEATURES], dtype=float
        )
        fit_score, cos_sim = _cosine_to_fit_score(player_std, centroid)
        cluster_fits.append(
            {
                "cluster_id": cluster["cluster_id"],
                "label": cluster["label"],
                "n_teams": cluster["n_teams"],
                "fit_score": fit_score,
                "cosine_similarity": cos_sim,
                "teams": cluster["teams"][:5],
            }
        )

    cluster_fits.sort(key=lambda c: c["fit_score"], reverse=True)

    # Best cluster label for convenience.
    best_label = cluster_fits[0]["label"] if cluster_fits else "unknown"

    return {
        "status": "ok",
        "player": player_name,
        "season": season,
        "league": league,
        "best_fit_cluster": best_label,
        "n_clusters": len(cluster_fits),
        "player_style": {
            feat: round(float(player_vec[i]), 3)
            for i, feat in enumerate(_STYLE_FEATURES)
        },
        "clusters": cluster_fits,
        "disclaimer": (
            "Style-fit scores are cosine similarities between the "
            "player's standardised style composites and team-style "
            "cluster centroids. They describe statistical affinity, "
            "not confirmed tactical fit. A high score does not "
            "guarantee the player would succeed in that system."
        ),
    }


def compute_cluster_recruits(
    df: pd.DataFrame,
    cluster_id: int,
    *,
    season: str | None = None,
    league: str | None = None,
    n_clusters: int = _DEFAULT_N_CLUSTERS,
    min_minutes_total: float = _MIN_MINUTES_TOTAL,
    min_player_minutes: float = 500.0,
    position_group: str | None = None,
    top_n: int = 20,
    exclude_cluster_teams: bool = True,
    random_state: int = 42,
) -> dict[str, Any]:
    """Rank players by style-fit to a specific team-style cluster.

    For each player in the filtered rating matrix, computes cosine
    similarity between their standardised style composites and the target
    cluster centroid. Returns the top-N players by fit score.

    Parameters
    ----------
    df:
        Player ratings DataFrame.
    cluster_id:
        Target cluster ID (from :func:`compute_team_style_clusters`).
    season, league:
        Optional filters for both cluster computation and candidate pool.
    min_player_minutes:
        Minimum total minutes for a player to be considered a candidate.
    position_group:
        Optional position filter (case-insensitive).
    top_n:
        Maximum number of recruits to return (1–100).
    exclude_cluster_teams:
        If True, exclude players already on teams in the target cluster.
    """
    if df.empty:
        return {
            "status": "no_data",
            "cluster_id": cluster_id,
            "recruits": [],
            "disclaimer": "Empty rating matrix.",
        }

    clusters_result = compute_team_style_clusters(
        df,
        season=season,
        league=league,
        n_clusters=n_clusters,
        min_minutes_total=min_minutes_total,
        random_state=random_state,
    )

    if clusters_result["status"] != "ok":
        return {
            "status": clusters_result["status"],
            "cluster_id": cluster_id,
            "recruits": [],
            "disclaimer": clusters_result.get("disclaimer", ""),
        }

    target: dict[str, Any] | None = None
    for c in clusters_result["clusters"]:
        if c["cluster_id"] == cluster_id:
            target = c
            break
    if target is None:
        available = [c["cluster_id"] for c in clusters_result["clusters"]]
        return {
            "status": "cluster_not_found",
            "cluster_id": cluster_id,
            "recruits": [],
            "available_clusters": available,
            "disclaimer": (
                f"Cluster {cluster_id} not found. Available: {available}."
            ),
        }

    centroid = np.array(
        [target["centroid"][f] for f in _STYLE_FEATURES], dtype=float
    )
    norm_c = float(np.linalg.norm(centroid))

    means = np.array(
        [clusters_result["feature_means"][f] for f in _STYLE_FEATURES],
        dtype=float,
    )
    stds = np.array(
        [clusters_result["feature_stds"][f] for f in _STYLE_FEATURES],
        dtype=float,
    )
    stds_safe = np.where(stds == 0, 1.0, stds)

    # Filter candidate pool.
    work = df.copy()
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]
    if league is not None:
        work = work[
            work["league"].astype(str).str.lower() == str(league).lower()
        ]
    if position_group is not None:
        work = work[
            work["position_group"].astype(str).str.lower()
            == str(position_group).lower()
        ]
    if work.empty:
        return {
            "status": "no_candidates",
            "cluster_id": cluster_id,
            "cluster_label": target["label"],
            "recruits": [],
            "disclaimer": "No players match the filter criteria.",
        }

    cluster_teams = set(target["teams"]) if exclude_cluster_teams else set()

    recruits: list[dict[str, Any]] = []
    n_scanned = 0
    for (player_name, team), group in work.groupby(
        ["player", "team"], sort=False
    ):
        if team in cluster_teams:
            continue
        minutes = (
            group["minutes"]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0.0)
            .to_numpy(dtype=float)
        )
        total_min = float(minutes.sum())
        if total_min < min_player_minutes:
            continue
        n_scanned += 1

        vec = _aggregate_player_style_vector(group)
        vec_std = (vec - means) / stds_safe
        norm_p = float(np.linalg.norm(vec_std))
        if norm_p == 0 or norm_c == 0:
            cos_sim = 0.0
        else:
            cos_sim = float(np.dot(vec_std, centroid)) / (norm_p * norm_c)
        fit_score = max(0.0, min(100.0, (cos_sim + 1.0) * 50.0))

        score = None
        if "optimized_score" in group.columns:
            scores = group["optimized_score"].apply(
                pd.to_numeric, errors="coerce"
            ).dropna()
            if not scores.empty:
                weights = (
                    minutes / total_min if total_min > 0 else None
                )
                if weights is not None:
                    score = float(
                        np.average(
                            scores.to_numpy(dtype=float), weights=weights
                        )
                    )
                else:
                    score = float(scores.mean())

        pos = (
            str(group["position_group"].iloc[0])
            if "position_group" in group.columns
            else ""
        )

        recruits.append(
            {
                "player": str(player_name),
                "team": str(team),
                "position_group": pos,
                "fit_score": round(fit_score, 1),
                "cosine_similarity": round(cos_sim, 3),
                "rating": round(score, 1) if score is not None else None,
                "minutes": round(total_min),
            }
        )

    recruits.sort(
        key=lambda r: (r["fit_score"], r["rating"] or 0), reverse=True
    )
    top_n = max(1, min(100, int(top_n)))
    n_returned = min(top_n, len(recruits))
    top_recruits = recruits[:top_n]

    return {
        "status": "ok",
        "cluster_id": cluster_id,
        "cluster_label": target["label"],
        "n_candidates_scanned": n_scanned,
        "n_returned": n_returned,
        "recruits": top_recruits,
        "disclaimer": (
            "Recruit rankings are based on cosine similarity between "
            "player style composites and the cluster centroid. They do "
            "not account for transfer availability, contract status, "
            "financial feasibility, or tactical fit within a specific "
            "manager's system. A high style-fit score is not a "
            "scouting recommendation."
        ),
    }


# ── Cluster-to-cluster similarity matrix ─────────────────────────────────


def _clash_label(similarity: float) -> str:
    """Heuristic label for how two style clusters relate."""
    if similarity >= 0.75:
        return "similar"
    if similarity >= 0.25:
        return "complementary"
    return "contrasting"


def compute_cluster_similarity_matrix(
    df: pd.DataFrame,
    *,
    season: str | None = None,
    league: str | None = None,
    n_clusters: int = _DEFAULT_N_CLUSTERS,
    min_minutes_total: float = _MIN_MINUTES_TOTAL,
    random_state: int = 42,
) -> dict[str, Any]:
    """Compute an NxN similarity matrix between team-style clusters.

    Reuses :func:`compute_team_style_clusters` to obtain the cluster
    centroids, then computes pairwise cosine similarity between every
    pair of cluster centroids. The result describes how tactically
    similar two clusters are — useful for understanding style clashes
    across the league population.

    The matrix is symmetric with 1.0 on the diagonal. An interpretable
    upper-triangle ``pairs`` list carries a heuristic clash label
    (``similar`` / ``complementary`` / ``contrasting``).
    """
    if df.empty:
        return {
            "status": "no_data",
            "n_clusters": 0,
            "labels": [],
            "matrix": [],
            "pairs": [],
            "disclaimer": "Empty rating matrix.",
        }

    clusters_result = compute_team_style_clusters(
        df,
        season=season,
        league=league,
        n_clusters=n_clusters,
        min_minutes_total=min_minutes_total,
        random_state=random_state,
    )

    if clusters_result["status"] != "ok":
        return {
            "status": clusters_result["status"],
            "n_clusters": 0,
            "labels": [],
            "matrix": [],
            "pairs": [],
            "disclaimer": clusters_result.get("disclaimer", ""),
        }

    clusters = clusters_result["clusters"]
    centroids = [
        np.array([c["centroid"][f] for f in _STYLE_FEATURES], dtype=float)
        for c in clusters
    ]
    norms = [float(np.linalg.norm(v)) for v in centroids]

    n = len(clusters)
    labels = [
        {
            "cluster_id": c["cluster_id"],
            "label": c["label"],
            "n_teams": c["n_teams"],
        }
        for c in clusters
    ]

    matrix: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        for j in range(n):
            if i == j:
                row.append(1.0)
            elif norms[i] == 0 or norms[j] == 0:
                row.append(0.0)
            else:
                sim = float(np.dot(centroids[i], centroids[j])) / (
                    norms[i] * norms[j]
                )
                row.append(round(sim, 3))
        matrix.append(row)

    pairs: list[dict[str, Any]] = []
    for i in range(n):
        for j in range(i + 1, n):
            sim = matrix[i][j]
            pairs.append(
                {
                    "a": clusters[i]["cluster_id"],
                    "b": clusters[j]["cluster_id"],
                    "label_a": clusters[i]["label"],
                    "label_b": clusters[j]["label"],
                    "similarity": sim,
                    "clash": _clash_label(sim),
                }
            )

    pairs.sort(key=lambda p: p["similarity"], reverse=True)

    return {
        "status": "ok",
        "n_clusters": n,
        "season": season,
        "league": league,
        "labels": labels,
        "matrix": matrix,
        "pairs": pairs,
        "disclaimer": (
            "Cluster similarities are cosine similarities between "
            "standardised cluster centroids. They describe statistical "
            "affinity between groupings of teams, not confirmed tactical "
            "relationships. A 'similar' rating does not mean two clusters "
            "play identically, and a 'contrasting' rating does not "
            "predict a match outcome."
        ),
    }


# ── Head-to-head style matchup diagnostic ────────────────────────────────


# Human-readable labels for each style dimension, keyed by feature column.
_DIM_LABELS = {
    "npg_p90": "attack",
    "assists_p90": "creation",
    "defense_composite": "defense",
    "possession_composite": "possession",
}


def _game_script(
    home_std: np.ndarray, away_std: np.ndarray
) -> tuple[str, str]:
    """Classify the expected game script from standardised profiles.

    Returns ``(script_key, script_label)``. This is a non-additive
    interpretive overlay — it never changes a probability model.
    """
    h_atk, h_cre, h_def, h_pos = home_std
    a_atk, a_cre, a_def, a_pos = away_std

    avg_atk = (h_atk + a_atk) / 2.0
    avg_def = (h_def + a_def) / 2.0
    avg_pos = (h_pos + a_pos) / 2.0
    atk_gap = h_atk - a_atk
    def_gap = h_def - a_def

    # Asymmetric: one side clearly attacks, the other clearly defends.
    if (h_atk > 0.4 and a_def > 0.4) or (a_atk > 0.4 and h_def > 0.4):
        if abs(atk_gap) > 0.6 or abs(def_gap) > 0.6:
            return (
                "asymmetric",
                "Attack-versus-defense: one side presses high while the "
                "other sits deep.",
            )

    # Open game: both attack above population, defenses leaky (below pop).
    if avg_atk > 0.4 and avg_def < -0.4:
        return (
            "open_game",
            "Open, high-scoring game expected — both teams attack and "
            "concede chances.",
        )

    # Defensive battle: both defend above population, attack muted.
    if avg_atk < -0.4 and avg_def > 0.4:
        return (
            "defensive_battle",
            "Defensive battle expected — both sides prioritise structure "
            "over creation.",
        )

    # Possession duel: both possession-heavy.
    if avg_pos > 0.4:
        return (
            "possession_duel",
            "Possession duel — both teams look to control the ball.",
        )

    return (
        "balanced",
        "Balanced matchup — no single style dimension dominates either "
        "side.",
    )


def _team_profile_dict(
    profile: TeamStyleProfile,
    means: np.ndarray,
    stds: np.ndarray,
) -> dict[str, Any]:
    """Build a display dict with raw + standardised style values."""
    raw = [
        profile.attack,
        profile.creation,
        profile.defense,
        profile.possession,
    ]
    stds_safe = np.where(stds == 0, 1.0, stds)
    standardized = (np.array(raw, dtype=float) - means) / stds_safe
    return {
        "team": profile.team,
        "league": profile.league,
        "season": profile.season,
        "n_players": profile.n_players,
        "total_minutes": profile.total_minutes,
        "raw": {
            _STYLE_FEATURES[i]: round(float(raw[i]), 3)
            for i in range(len(_STYLE_FEATURES))
        },
        "standardized": {
            _STYLE_FEATURES[i]: round(float(standardized[i]), 3)
            for i in range(len(_STYLE_FEATURES))
        },
    }


def compute_style_matchup(
    df: pd.DataFrame,
    home_team: str,
    away_team: str,
    *,
    season: str | None = None,
    league: str | None = None,
    n_clusters: int = _DEFAULT_N_CLUSTERS,
    min_minutes_total: float = _MIN_MINUTES_TOTAL,
    random_state: int = 42,
) -> dict[str, Any]:
    """Diagnostic of how two teams' tactical styles clash.

    Computes each team's minutes-weighted style profile, standardises
    both against the league population, and reports per-dimension
    advantage, an overall style distance, and a heuristic game-script
    classification. When clustering succeeds, each team's cluster
    assignment and the inter-cluster similarity are included.

    This is an interpretive overlay. It does **not** modify or replace
    the Dixon-Coles / Poisson match-probability model — probabilities
    remain the sole source of truth for win/draw/loss estimates.
    """
    if df.empty:
        return {
            "status": "no_data",
            "home_team": home_team,
            "away_team": away_team,
            "disclaimer": "Empty rating matrix.",
        }

    profiles = compute_team_style_profiles(
        df,
        season=season,
        league=league,
        min_minutes_total=min_minutes_total,
    )

    if not profiles:
        return {
            "status": "no_data",
            "home_team": home_team,
            "away_team": away_team,
            "disclaimer": (
                "No team-season profiles meet the minimum minutes "
                f"threshold ({min_minutes_total:.0f} min)."
            ),
        }

    # Pick the matching profile for each team. If a season filter is
    # applied there should be at most one match per team; otherwise pick
    # the most recent season available for that team.
    def _pick(team_name: str) -> TeamStyleProfile | None:
        matches = [p for p in profiles if p.team.lower() == team_name.lower()]
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        matches.sort(key=lambda p: str(p.season), reverse=True)
        return matches[0]

    home_profile = _pick(home_team)
    away_profile = _pick(away_team)

    missing = []
    if home_profile is None:
        missing.append(home_team)
    if away_profile is None:
        missing.append(away_team)
    if missing:
        return {
            "status": "team_not_found",
            "home_team": home_team,
            "away_team": away_team,
            "missing": missing,
            "disclaimer": (
                f"No style profile found for: {', '.join(missing)}."
                + (f" Season={season}." if season else "")
                + (f" League={league}." if league else "")
                + " Check the team name spelling or broaden the filters."
            ),
        }

    # Population standardisation stats from the full profile set so the
    # per-dimension deltas are comparable across scales.
    mat = np.array(
        [
            [
                getattr(p, _feat_to_attr(c))
                for c in _STYLE_FEATURES
            ]
            for p in profiles
        ],
        dtype=float,
    )
    means = mat.mean(axis=0)
    stds = mat.std(axis=0, ddof=0)
    stds_safe = np.where(stds == 0, 1.0, stds)

    home_raw = np.array(
        [getattr(home_profile, _feat_to_attr(c)) for c in _STYLE_FEATURES],
        dtype=float,
    )
    away_raw = np.array(
        [getattr(away_profile, _feat_to_attr(c)) for c in _STYLE_FEATURES],
        dtype=float,
    )
    home_std = (home_raw - means) / stds_safe
    away_std = (away_raw - means) / stds_safe

    # Per-dimension comparison.
    dimensions: list[dict[str, Any]] = []
    for i, feat in enumerate(_STYLE_FEATURES):
        delta_std = float(home_std[i] - away_std[i])
        if abs(delta_std) < 0.15:
            advantage = "even"
        elif delta_std > 0:
            advantage = "home"
        else:
            advantage = "away"
        dimensions.append(
            {
                "feature": feat,
                "label": _DIM_LABELS[feat],
                "home": round(float(home_raw[i]), 3),
                "away": round(float(away_raw[i]), 3),
                "delta_std": round(delta_std, 3),
                "advantage": advantage,
            }
        )

    # Overall style distance (Euclidean on standardised vectors).
    style_distance = float(np.linalg.norm(home_std - away_std))

    script_key, script_label = _game_script(home_std, away_std)

    result: dict[str, Any] = {
        "status": "ok",
        "home_team": home_team,
        "away_team": away_team,
        "season": season,
        "league": league,
        "home": _team_profile_dict(home_profile, means, stds_safe),
        "away": _team_profile_dict(away_profile, means, stds_safe),
        "dimensions": dimensions,
        "style_distance": round(style_distance, 3),
        "game_script": script_key,
        "game_script_label": script_label,
        "disclaimer": (
            "Style matchup is a non-additive interpretive overlay computed "
            "from minutes-weighted per-player style composites. It "
            "describes statistical tendencies, not a confirmed tactical "
            "plan. It does NOT modify the match-probability model — "
            "win/draw/loss probabilities remain the sole source of truth."
        ),
    }

    # Optional cluster context (only when clustering succeeds).
    clusters_result = compute_team_style_clusters(
        df,
        season=season,
        league=league,
        n_clusters=n_clusters,
        min_minutes_total=min_minutes_total,
        random_state=random_state,
    )
    if clusters_result["status"] == "ok":
        team_profiles = clusters_result["team_profiles"]
        cluster_map: dict[str, dict[str, Any]] = {}
        for tp in team_profiles:
            cluster_map.setdefault(tp["team"], {
                "cluster_id": int(tp["cluster_id"]),
                "label": "",
            })["cluster_id"] = int(tp["cluster_id"])

        # Attach cluster labels.
        for c in clusters_result["clusters"]:
            for team in c["teams"]:
                if team in cluster_map:
                    cluster_map[team]["label"] = c["label"]

        home_cluster = cluster_map.get(home_team)
        away_cluster = cluster_map.get(away_team)
        result["home_cluster"] = home_cluster
        result["away_cluster"] = away_cluster

        if (
            home_cluster is not None
            and away_cluster is not None
            and home_cluster["cluster_id"] == away_cluster["cluster_id"]
        ):
            result["cluster_similarity"] = 1.0
            result["cluster_clash"] = "same_cluster"
        elif home_cluster is not None and away_cluster is not None:
            centroids = {
                c["cluster_id"]: np.array(
                    [c["centroid"][f] for f in _STYLE_FEATURES],
                    dtype=float,
                )
                for c in clusters_result["clusters"]
            }
            hc = centroids.get(home_cluster["cluster_id"])
            ac = centroids.get(away_cluster["cluster_id"])
            if hc is not None and ac is not None:
                nh = float(np.linalg.norm(hc))
                na = float(np.linalg.norm(ac))
                if nh > 0 and na > 0:
                    sim = float(np.dot(hc, ac)) / (nh * na)
                    result["cluster_similarity"] = round(sim, 3)
                    result["cluster_clash"] = _clash_label(sim)

    return result


# ── Style Atlas: neighbors, percentiles, distribution ───────────────────


def _pick_profile(
    profiles: list[TeamStyleProfile], team_name: str
) -> TeamStyleProfile | None:
    """Pick a team's profile; if multiple, choose the most recent season."""
    matches = [p for p in profiles if p.team.lower() == team_name.lower()]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    matches.sort(key=lambda p: str(p.season), reverse=True)
    return matches[0]


def compute_style_neighbors(
    df: pd.DataFrame,
    team: str,
    *,
    season: str | None = None,
    league: str | None = None,
    top_n: int = 10,
    min_minutes_total: float = _MIN_MINUTES_TOTAL,
    n_clusters: int = _DEFAULT_N_CLUSTERS,
    random_state: int = 42,
) -> dict[str, Any]:
    """Find the nearest tactical-style neighbors for a given team.

    Computes each team's minutes-weighted style profile, standardises
    all profiles against the league population, then ranks every other
    team by cosine similarity and Euclidean distance on the standardised
    style vector. When clustering succeeds, each neighbor's cluster
    assignment is included so the user can see whether a neighbor is in
    the same cluster or a different one.

    This is an interpretive overlay — it does not predict match outcomes
    or rank teams by quality.
    """
    if df.empty:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": "Empty rating matrix.",
        }

    profiles = compute_team_style_profiles(
        df,
        season=season,
        league=league,
        min_minutes_total=min_minutes_total,
    )
    if not profiles:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": (
                "No team-season profiles meet the minimum minutes "
                f"threshold ({min_minutes_total:.0f} min)."
            ),
        }

    target = _pick_profile(profiles, team)
    if target is None:
        return {
            "status": "team_not_found",
            "team": team,
            "disclaimer": (
                f"No style profile found for '{team}'."
                + (f" Season={season}." if season else "")
                + (f" League={league}." if league else "")
                + " Check the team name spelling or broaden the filters."
            ),
        }

    mat = np.array(
        [
            [getattr(p, _feat_to_attr(c)) for c in _STYLE_FEATURES]
            for p in profiles
        ],
        dtype=float,
    )
    means = mat.mean(axis=0)
    stds = mat.std(axis=0, ddof=0)
    stds_safe = np.where(stds == 0, 1.0, stds)
    standardized = (mat - means) / stds_safe

    target_idx = profiles.index(target)
    target_std = standardized[target_idx]
    target_norm = float(np.linalg.norm(target_std))

    neighbors: list[dict[str, Any]] = []
    for i, p in enumerate(profiles):
        if i == target_idx:
            continue
        other_std = standardized[i]
        other_norm = float(np.linalg.norm(other_std))
        if target_norm == 0 or other_norm == 0:
            cos_sim = 0.0
        else:
            cos_sim = float(np.dot(target_std, other_std)) / (
                target_norm * other_norm
            )
        dist = float(np.linalg.norm(target_std - other_std))
        neighbors.append(
            {
                "team": p.team,
                "league": p.league,
                "season": p.season,
                "cosine_similarity": round(cos_sim, 3),
                "style_distance": round(dist, 3),
            }
        )

    # Sort by cosine similarity descending (equivalently, distance ascending).
    neighbors.sort(
        key=lambda n: (n["cosine_similarity"], -n["style_distance"]),
        reverse=True,
    )
    top_n = max(1, min(50, int(top_n)))
    n_returned = min(top_n, len(neighbors))
    top_neighbors = neighbors[:top_n]

    result: dict[str, Any] = {
        "status": "ok",
        "team": team,
        "season": season,
        "league": league,
        "target": _team_profile_dict(target, means, stds_safe),
        "n_population": len(profiles),
        "n_returned": n_returned,
        "neighbors": top_neighbors,
        "disclaimer": (
            "Style neighbors are ranked by cosine similarity between "
            "standardised minutes-weighted style composites. They "
            "describe statistical affinity, not confirmed tactical "
            "similarity or competitive level. A high similarity score "
            "does not predict a match outcome or transfer fit."
        ),
    }

    # Optional cluster context.
    clusters_result = compute_team_style_clusters(
        df,
        season=season,
        league=league,
        n_clusters=n_clusters,
        min_minutes_total=min_minutes_total,
        random_state=random_state,
    )
    if clusters_result["status"] == "ok":
        cluster_map: dict[str, dict[str, Any]] = {}
        for tp in clusters_result["team_profiles"]:
            cluster_map.setdefault(tp["team"], {
                "cluster_id": int(tp["cluster_id"]),
                "label": "",
            })["cluster_id"] = int(tp["cluster_id"])
        for c in clusters_result["clusters"]:
            for t in c["teams"]:
                if t in cluster_map:
                    cluster_map[t]["label"] = c["label"]

        target_cluster = cluster_map.get(target.team)
        result["target_cluster"] = target_cluster
        for n in top_neighbors:
            nc = cluster_map.get(n["team"])
            if nc is not None:
                n["cluster_id"] = nc["cluster_id"]
                n["cluster_label"] = nc["label"]
                if target_cluster is not None:
                    n["same_cluster"] = (
                        nc["cluster_id"] == target_cluster["cluster_id"]
                    )

    return result


def compute_league_style_percentiles(
    df: pd.DataFrame,
    team: str,
    *,
    season: str | None = None,
    league: str | None = None,
    min_minutes_total: float = _MIN_MINUTES_TOTAL,
) -> dict[str, Any]:
    """Per-dimension percentile rank of one team within its league population.

    For each of the four style dimensions (attack, creation, defense,
    possession), computes the team's percentile rank (0–100) within
    the filtered league population. A percentile of 90 means the team
    is in the top 10% for that dimension.

    This is a descriptive overlay — percentiles describe relative
    standing, not absolute quality or tactical correctness.
    """
    if df.empty:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": "Empty rating matrix.",
        }

    profiles = compute_team_style_profiles(
        df,
        season=season,
        league=league,
        min_minutes_total=min_minutes_total,
    )
    if not profiles:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": (
                "No team-season profiles meet the minimum minutes "
                f"threshold ({min_minutes_total:.0f} min)."
            ),
        }

    target = _pick_profile(profiles, team)
    if target is None:
        return {
            "status": "team_not_found",
            "team": team,
            "disclaimer": (
                f"No style profile found for '{team}'."
                + (f" Season={season}." if season else "")
                + (f" League={league}." if league else "")
                + " Check the team name spelling or broaden the filters."
            ),
        }

    mat = np.array(
        [
            [getattr(p, _feat_to_attr(c)) for c in _STYLE_FEATURES]
            for p in profiles
        ],
        dtype=float,
    )
    n_pop = len(profiles)
    target_idx = profiles.index(target)
    target_raw = mat[target_idx]

    dimensions: list[dict[str, Any]] = []
    for i, feat in enumerate(_STYLE_FEATURES):
        col = mat[:, i]
        val = float(target_raw[i])
        # Percentile rank: fraction of population at or below this value.
        if n_pop <= 1:
            pct = 50.0
        else:
            # Use average rank to handle ties deterministically.
            # percentile = 100 * (count_below + 0.5 * count_equal) / n
            rank = float((col < val).sum()) + 0.5 * float(
                (col == val).sum()
            )
            pct = round(100.0 * rank / n_pop, 1) if n_pop > 0 else 50.0
        # Quartile label.
        if pct >= 75:
            quartile = "top"
        elif pct >= 50:
            quartile = "upper_mid"
        elif pct >= 25:
            quartile = "lower_mid"
        else:
            quartile = "bottom"
        dimensions.append(
            {
                "feature": feat,
                "label": _DIM_LABELS[feat],
                "value": round(val, 3),
                "percentile": pct,
                "quartile": quartile,
                "population_min": round(float(col.min()), 3),
                "population_max": round(float(col.max()), 3),
                "population_mean": round(float(col.mean()), 3),
                "population_median": round(float(np.median(col)), 3),
            }
        )

    return {
        "status": "ok",
        "team": team,
        "season": season,
        "league": league,
        "target": _team_profile_dict(target, mat.mean(axis=0), mat.std(axis=0, ddof=0)),
        "n_population": n_pop,
        "dimensions": dimensions,
        "disclaimer": (
            "Percentile ranks describe where a team sits within the "
            "filtered league population on each style dimension. They "
            "are relative, not absolute — a 90th-percentile attack in a "
            "weak league is not equivalent to 90th-percentile in a "
            "strong one. Percentiles do not predict match outcomes."
        ),
    }


def compute_style_atlas(
    df: pd.DataFrame,
    *,
    season: str | None = None,
    league: str | None = None,
    n_bins: int = 8,
    min_minutes_total: float = _MIN_MINUTES_TOTAL,
) -> dict[str, Any]:
    """League-wide distribution of team styles across all dimensions.

    For each of the four style dimensions, computes a histogram (with
    ``n_bins`` bins between min and max), quartiles (Q1/median/Q3/IQR),
    and the list of outlier teams (z-score magnitude >= 2.0). The result
    is a league-wide "atlas" showing how styles are distributed.

    This is a descriptive population view — it does not rank teams by
    quality or predict outcomes.
    """
    if df.empty:
        return {
            "status": "no_data",
            "disclaimer": "Empty rating matrix.",
        }

    profiles = compute_team_style_profiles(
        df,
        season=season,
        league=league,
        min_minutes_total=min_minutes_total,
    )
    if not profiles:
        return {
            "status": "no_data",
            "disclaimer": (
                "No team-season profiles meet the minimum minutes "
                f"threshold ({min_minutes_total:.0f} min)."
            ),
        }

    mat = np.array(
        [
            [getattr(p, _feat_to_attr(c)) for c in _STYLE_FEATURES]
            for p in profiles
        ],
        dtype=float,
    )
    means = mat.mean(axis=0)
    stds = mat.std(axis=0, ddof=0)
    stds_safe = np.where(stds == 0, 1.0, stds)
    standardized = (mat - means) / stds_safe

    n_bins = max(3, min(20, int(n_bins)))
    n_pop = len(profiles)

    dimensions: list[dict[str, Any]] = []
    for i, feat in enumerate(_STYLE_FEATURES):
        col = mat[:, i]
        col_min = float(col.min())
        col_max = float(col.max())
        col_mean = float(col.mean())
        col_median = float(np.median(col))
        q1 = float(np.percentile(col, 25))
        q3 = float(np.percentile(col, 75))
        iqr = q3 - q1

        # Histogram with explicit bin edges.
        if col_max > col_min:
            edges = np.linspace(col_min, col_max, n_bins + 1)
            counts, _ = np.histogram(col, bins=edges)
            bins = [
                {
                    "low": round(float(edges[b]), 3),
                    "high": round(float(edges[b + 1]), 3),
                    "count": int(counts[b]),
                }
                for b in range(n_bins)
            ]
        else:
            bins = [
                {
                    "low": round(col_min, 3),
                    "high": round(col_max, 3),
                    "count": n_pop,
                }
            ]

        # Outliers: z-score magnitude >= 2.0 on the standardised dimension.
        std_col = standardized[:, i]
        outliers: list[dict[str, Any]] = []
        for j, p in enumerate(profiles):
            z = float(std_col[j])
            if abs(z) >= 2.0:
                outliers.append(
                    {
                        "team": p.team,
                        "league": p.league,
                        "season": p.season,
                        "value": round(float(col[j]), 3),
                        "z_score": round(z, 3),
                        "direction": "high" if z > 0 else "low",
                    }
                )
        outliers.sort(key=lambda o: abs(o["z_score"]), reverse=True)

        dimensions.append(
            {
                "feature": feat,
                "label": _DIM_LABELS[feat],
                "min": round(col_min, 3),
                "max": round(col_max, 3),
                "mean": round(col_mean, 3),
                "median": round(col_median, 3),
                "q1": round(q1, 3),
                "q3": round(q3, 3),
                "iqr": round(iqr, 3),
                "bins": bins,
                "outliers": outliers,
            }
        )

    return {
        "status": "ok",
        "season": season,
        "league": league,
        "n_population": n_pop,
        "dimensions": dimensions,
        "disclaimer": (
            "The style atlas is a descriptive population view computed "
            "from minutes-weighted per-player style composites. "
            "Histograms, quartiles and outliers describe how styles are "
            "distributed across the filtered league population — they do "
            "not rank teams by quality or predict match outcomes. "
            "Outliers are teams with a z-score magnitude >= 2.0 on the "
            "standardised dimension; a low sample size makes outlier "
            "labels less meaningful."
        ),
    }


# ── Cross-season style drift (Round 75) ──────────────────────────────────


def _drift_label(delta: float, mean_val: float, rel_threshold: float = 0.05) -> str:
    """Classify a dimension's drift direction.

    Uses a relative threshold: the change must exceed ``rel_threshold``
    of the absolute mean to count as rising/falling. Guarded against
    zero-mean dimensions.
    """
    eps = 1e-9
    denom = abs(mean_val) if abs(mean_val) > eps else 1.0
    if abs(delta) > rel_threshold * denom:
        return "rising" if delta > 0 else "falling"
    return "stable"


def _linear_slope_and_r2(
    x: np.ndarray, y: np.ndarray
) -> tuple[float, float]:
    """Least-squares slope and R² for a 1-D linear fit.

    Returns ``(slope, r2)``. With fewer than 2 points the slope is 0
    and R² is 0. With 2 points R² is always 1.0 (perfect linear fit).
    """
    n = len(x)
    if n < 2:
        return 0.0, 0.0
    slope = float(np.polyfit(x, y, 1)[0])
    # R² = 1 - SS_res / SS_tot
    y_pred = slope * x + (float(y.mean()) - slope * float(x.mean()))
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 1.0
    return slope, r2


def compute_team_style_drift(
    df: pd.DataFrame,
    team: str,
    *,
    league: str | None = None,
    min_minutes_total: float = _MIN_MINUTES_TOTAL,
) -> dict[str, Any]:
    """Compute a single team's style trajectory across multiple seasons.

    For each of the four style dimensions, fits a least-squares slope
    across the team's available seasons and reports the per-season
    values, the net delta (latest - earliest), the slope (change per
    season step), an R² consistency score, and a drift label
    (rising/falling/stable using a 5% relative threshold).

    Requires at least 2 seasons of profiles for the target team.
    Returns ``status="insufficient_seasons"`` otherwise.

    This is a descriptive overlay — it does not predict future style
    or rank teams by quality.
    """
    if df.empty or not team:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": "Empty rating matrix or missing team name.",
        }

    profiles = compute_team_style_profiles(
        df,
        league=league,
        min_minutes_total=min_minutes_total,
    )
    team_lower = str(team).lower()
    team_profiles = [p for p in profiles if p.team.lower() == team_lower]
    if not team_profiles:
        return {
            "status": "team_not_found",
            "team": team,
            "league": league,
            "disclaimer": (
                f"No team-season profile found for '{team}'"
                + (f" in league '{league}'." if league else ".")
            ),
        }

    # Sort by season (lexicographic works for "2324"/"2425"/"2526").
    team_profiles.sort(key=lambda p: p.season)
    seasons = [p.season for p in team_profiles]
    n_seasons = len(seasons)
    if n_seasons < 2:
        return {
            "status": "insufficient_seasons",
            "team": team_profiles[0].team,
            "league": team_profiles[0].league,
            "seasons": seasons,
            "n_seasons": n_seasons,
            "disclaimer": (
                "Style drift requires at least 2 seasons of profiles; "
                f"only {n_seasons} found."
            ),
        }

    x = np.arange(n_seasons, dtype=float)
    dimensions: list[dict[str, Any]] = []
    for feat in _STYLE_FEATURES:
        attr = _feat_to_attr(feat)
        vals = np.array(
            [getattr(p, attr) for p in team_profiles], dtype=float
        )
        slope, r2 = _linear_slope_and_r2(x, vals)
        delta = float(vals[-1] - vals[0])
        mean_val = float(vals.mean())
        label = _drift_label(delta, mean_val)
        dimensions.append(
            {
                "feature": feat,
                "label": _DIM_LABELS[feat],
                "slope": round(slope, 4),
                "delta": round(delta, 3),
                "r_squared": round(r2, 3),
                "mean": round(mean_val, 3),
                "drift_label": label,
                "per_season": [
                    {
                        "season": seasons[i],
                        "value": round(float(vals[i]), 3),
                    }
                    for i in range(n_seasons)
                ],
            }
        )

    return {
        "status": "ok",
        "team": team_profiles[0].team,
        "league": team_profiles[0].league,
        "seasons": seasons,
        "n_seasons": n_seasons,
        "dimensions": dimensions,
        "disclaimer": (
            "Style drift is a descriptive trajectory computed from "
            "minutes-weighted per-player style composites across seasons. "
            "Slopes and deltas describe observed changes — they do not "
            "predict future style or rank teams by quality. The drift "
            "label uses a 5% relative threshold and is less reliable "
            "with only 2 seasons or low sample sizes."
        ),
    }


def compute_league_style_evolution(
    df: pd.DataFrame,
    *,
    league: str | None = None,
    min_minutes_total: float = _MIN_MINUTES_TOTAL,
) -> dict[str, Any]:
    """Compute league-wide style evolution across seasons.

    Groups team-season profiles by season and computes the median and
    mean for each style dimension per season. Then fits a least-squares
    slope across seasons for each dimension to show whether the league
    average is rising, falling, or stable over time.

    Requires at least 2 seasons of data. Returns
    ``status="insufficient_seasons"`` otherwise.

    This is a descriptive population view — it does not predict future
    league style or rank seasons by quality.
    """
    if df.empty:
        return {
            "status": "no_data",
            "disclaimer": "Empty rating matrix.",
        }

    profiles = compute_team_style_profiles(
        df,
        league=league,
        min_minutes_total=min_minutes_total,
    )
    if not profiles:
        return {
            "status": "no_data",
            "disclaimer": (
                "No team-season profiles meet the minimum minutes "
                f"threshold ({min_minutes_total:.0f} min)."
            ),
        }

    # Group by season.
    by_season: dict[str, list[TeamStyleProfile]] = {}
    for p in profiles:
        by_season.setdefault(p.season, []).append(p)
    seasons_sorted = sorted(by_season.keys())
    n_seasons = len(seasons_sorted)
    if n_seasons < 2:
        return {
            "status": "insufficient_seasons",
            "league": league,
            "seasons": seasons_sorted,
            "n_seasons": n_seasons,
            "disclaimer": (
                "League evolution requires at least 2 seasons; "
                f"only {n_seasons} found."
            ),
        }

    x = np.arange(n_seasons, dtype=float)
    per_season_summary: list[dict[str, Any]] = []
    for s in seasons_sorted:
        season_profiles = by_season[s]
        entry: dict[str, Any] = {
            "season": s,
            "n_teams": len(season_profiles),
        }
        for feat in _STYLE_FEATURES:
            attr = _feat_to_attr(feat)
            vals = np.array(
                [getattr(p, attr) for p in season_profiles], dtype=float
            )
            entry[feat] = {
                "median": round(float(np.median(vals)), 3),
                "mean": round(float(vals.mean()), 3),
                "std": round(float(vals.std(ddof=0)), 3),
                "min": round(float(vals.min()), 3),
                "max": round(float(vals.max()), 3),
            }
        per_season_summary.append(entry)

    dimensions: list[dict[str, Any]] = []
    for feat in _STYLE_FEATURES:
        attr = _feat_to_attr(feat)
        medians = np.array(
            [
                float(np.median(
                    [getattr(p, attr) for p in by_season[s]]
                ))
                for s in seasons_sorted
            ],
            dtype=float,
        )
        means = np.array(
            [
                float(np.mean(
                    [getattr(p, attr) for p in by_season[s]]
                ))
                for s in seasons_sorted
            ],
            dtype=float,
        )
        slope_med, r2_med = _linear_slope_and_r2(x, medians)
        slope_mean, r2_mean = _linear_slope_and_r2(x, means)
        delta_med = float(medians[-1] - medians[0])
        delta_mean = float(means[-1] - means[0])
        label = _drift_label(delta_med, float(medians.mean()))
        dimensions.append(
            {
                "feature": feat,
                "label": _DIM_LABELS[feat],
                "median_slope": round(slope_med, 4),
                "median_delta": round(delta_med, 3),
                "median_r_squared": round(r2_med, 3),
                "mean_slope": round(slope_mean, 4),
                "mean_delta": round(delta_mean, 3),
                "mean_r_squared": round(r2_mean, 3),
                "evolution_label": label,
            }
        )

    return {
        "status": "ok",
        "league": league,
        "seasons": seasons_sorted,
        "n_seasons": n_seasons,
        "per_season": per_season_summary,
        "dimensions": dimensions,
        "disclaimer": (
            "League style evolution is a descriptive population view "
            "computed from minutes-weighted per-player style composites. "
            "Per-season medians/means and their slopes describe observed "
            "league-wide trends — they do not predict future style or "
            "rank seasons by quality. Evolution labels use a 5% relative "
            "threshold on the median delta and are less reliable with "
            "few seasons or uneven team coverage."
        ),
    }


def compute_style_drift_neighbors(
    df: pd.DataFrame,
    team: str,
    *,
    league: str | None = None,
    top_n: int = 10,
    min_seasons: int = 2,
    min_minutes_total: float = _MIN_MINUTES_TOTAL,
) -> dict[str, Any]:
    """Find teams with similar style-drift patterns.

    For every team with at least ``min_seasons`` profiles, computes a
    4-dimensional drift vector (least-squares slope per style dimension).
    Ranks other teams by cosine similarity to the target team's drift
    vector (descending), with Euclidean distance on the raw slope
    vectors for reference.

    Requires the target team to have at least ``min_seasons`` profiles
    and at least one other team with sufficient seasons. Returns
    ``status="insufficient_seasons"`` otherwise.

    This is a descriptive overlay — similar drift does not imply similar
    quality or future trajectory.
    """
    if df.empty or not team:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": "Empty rating matrix or missing team name.",
        }

    min_seasons = max(2, int(min_seasons))
    top_n = max(1, min(50, int(top_n)))

    profiles = compute_team_style_profiles(
        df,
        league=league,
        min_minutes_total=min_minutes_total,
    )
    if not profiles:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": (
                "No team-season profiles meet the minimum minutes "
                f"threshold ({min_minutes_total:.0f} min)."
            ),
        }

    # Group profiles by team.
    by_team: dict[str, list[TeamStyleProfile]] = {}
    for p in profiles:
        by_team.setdefault(p.team, []).append(p)

    # Compute drift vectors for all teams with enough seasons.
    team_lower = str(team).lower()
    drift_vectors: dict[str, np.ndarray] = {}
    team_seasons: dict[str, list[str]] = {}
    for t_name, t_profiles in by_team.items():
        t_profiles.sort(key=lambda p: p.season)
        if len(t_profiles) < min_seasons:
            continue
        x = np.arange(len(t_profiles), dtype=float)
        vec = np.zeros(len(_STYLE_FEATURES), dtype=float)
        for i, feat in enumerate(_STYLE_FEATURES):
            attr = _feat_to_attr(feat)
            vals = np.array(
                [getattr(p, attr) for p in t_profiles], dtype=float
            )
            slope, _ = _linear_slope_and_r2(x, vals)
            vec[i] = slope
        drift_vectors[t_name] = vec
        team_seasons[t_name] = [p.season for p in t_profiles]

    if team_lower not in {t.lower() for t in drift_vectors}:
        return {
            "status": "team_not_found",
            "team": team,
            "league": league,
            "min_seasons": min_seasons,
            "disclaimer": (
                f"Target team '{team}' has fewer than {min_seasons} "
                "seasons of profiles; cannot compute a drift vector."
            ),
        }

    # Find the target team's actual key (preserve original case).
    target_key = team
    for t in drift_vectors:
        if t.lower() == team_lower:
            target_key = t
            break
    target_vec = drift_vectors[target_key]
    target_norm = np.linalg.norm(target_vec)

    neighbors: list[dict[str, Any]] = []
    for t_name, vec in drift_vectors.items():
        if t_name.lower() == team_lower:
            continue
        vec_norm = np.linalg.norm(vec)
        # Cosine similarity.
        denom = target_norm * vec_norm
        if denom > 1e-12:
            cos_sim = float(
                np.dot(target_vec, vec) / denom
            )
        else:
            cos_sim = 0.0
        # Euclidean distance on raw slope vectors.
        dist = float(np.linalg.norm(target_vec - vec))
        neighbors.append(
            {
                "team": t_name,
                "league": by_team[t_name][0].league,
                "n_seasons": len(team_seasons[t_name]),
                "seasons": team_seasons[t_name],
                "cosine_similarity": round(cos_sim, 4),
                "euclidean_distance": round(dist, 4),
                "drift_vector": [
                    round(float(v), 4) for v in vec
                ],
            }
        )

    neighbors.sort(key=lambda n: n["cosine_similarity"], reverse=True)
    neighbors = neighbors[:top_n]

    return {
        "status": "ok",
        "team": target_key,
        "league": by_team[target_key][0].league,
        "seasons": team_seasons[target_key],
        "n_seasons": len(team_seasons[target_key]),
        "target_drift_vector": [
            round(float(v), 4) for v in target_vec
        ],
        "target_drift_vector_labels": list(_STYLE_FEATURES),
        "n_candidates": len(drift_vectors) - 1,
        "neighbors": neighbors,
        "disclaimer": (
            "Style drift neighbors are a descriptive overlay computed "
            "from least-squares style slopes across seasons. Cosine "
            "similarity on drift vectors identifies teams whose styles "
            "are evolving in a similar direction — it does not imply "
            "similar quality, identical tactical identity, or future "
            "trajectory. Teams with only 2 seasons have noisier slopes."
        ),
    }


# ── Per-position-group style evolution (Round 76) ────────────────────────

_POSITION_GROUPS = ("GK", "CB", "FB", "DM", "CM", "AM", "W", "ST")
_MIN_PLAYER_MINUTES_DEFAULT = 500.0


@dataclass(frozen=True)
class PositionSeasonProfile:
    """Single position-group's aggregated style signature for one season."""

    position_group: str
    season: str
    n_players: int
    total_minutes: float
    attack: float
    creation: float
    defense: float
    possession: float


def _aggregate_position_season_profiles(
    df: pd.DataFrame,
    *,
    league: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> list[PositionSeasonProfile]:
    """Aggregate per-player style composites to position-group-season level.

    Groups the rating matrix by ``(position_group, season)`` and computes
    a minutes-weighted average of the four style features across all
    players at that position group in that season. Players with fewer
    than ``min_player_minutes`` are filtered out to reduce noise from
    bench appearances.

    Returns a list of :class:`PositionSeasonProfile` sorted by
    ``(position_group, season)``.
    """
    if df.empty:
        return []

    work = df.copy()
    if league is not None:
        work = work[
            work["league"].astype(str).str.lower()
            == str(league).lower()
        ]
    # Normalize position_group column.
    if "position_group" not in work.columns:
        if "sub_position" in work.columns:
            work["position_group"] = work["sub_position"]
        else:
            return []
    if work.empty:
        return []

    # Keep only standard position groups (case-insensitive, normalize to
    # upper-case canonical form).
    work = work[
        work["position_group"].astype(str).str.upper().isin(_POSITION_GROUPS)
    ]
    if work.empty:
        return []

    profiles: list[PositionSeasonProfile] = []
    for (pos, season), group in work.groupby(
        ["position_group", "season"], sort=False
    ):
        minutes = group["minutes"].apply(
            pd.to_numeric, errors="coerce"
        ).fillna(0.0).to_numpy(dtype=float)
        mask = minutes >= min_player_minutes
        if not mask.any():
            continue
        minutes_f = minutes[mask]
        total_minutes = float(minutes_f.sum())
        if total_minutes <= 0:
            continue
        weights = minutes_f / total_minutes

        vals: dict[str, float] = {}
        for feat in _STYLE_FEATURES:
            col = (
                group[feat]
                .apply(pd.to_numeric, errors="coerce")
                .fillna(0.0)
                .to_numpy(dtype=float)[mask]
            )
            vals[feat] = float(np.average(col, weights=weights))

        profiles.append(
            PositionSeasonProfile(
                position_group=str(pos).upper(),
                season=str(season),
                n_players=int(mask.sum()),
                total_minutes=round(total_minutes),
                attack=round(vals["npg_p90"], 3),
                creation=round(vals["assists_p90"], 3),
                defense=round(vals["defense_composite"], 2),
                possession=round(vals["possession_composite"], 2),
            )
        )
    return profiles


def _pos_feat_to_attr(feat: str) -> str:
    """Map a feature column name to the PositionSeasonProfile attribute."""
    return {
        "npg_p90": "attack",
        "assists_p90": "creation",
        "defense_composite": "defense",
        "possession_composite": "possession",
    }[feat]


def compute_position_style_evolution(
    df: pd.DataFrame,
    *,
    league: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Compute per-position-group style evolution across seasons.

    For each standard position group (GK/CB/FB/DM/CM/AM/W/ST) that has
    at least 2 seasons of profiles, fits a least-squares slope across
    seasons for each style dimension and reports the per-season values,
    net delta, slope, R² consistency, and an evolution label
    (rising/falling/stable using a 5% relative threshold).

    Position groups with fewer than 2 seasons are listed in
    ``skipped_positions`` with the season count.

    This is a descriptive population view — it does not predict future
    style or rank positions by quality.
    """
    if df.empty:
        return {
            "status": "no_data",
            "disclaimer": "Empty rating matrix.",
        }

    profiles = _aggregate_position_season_profiles(
        df,
        league=league,
        min_player_minutes=min_player_minutes,
    )
    if not profiles:
        return {
            "status": "no_data",
            "disclaimer": (
                "No position-group-season profiles meet the minimum "
                f"player minutes threshold ({min_player_minutes:.0f} min)."
            ),
        }

    # Group by position_group.
    by_pos: dict[str, list[PositionSeasonProfile]] = {}
    for p in profiles:
        by_pos.setdefault(p.position_group, []).append(p)

    all_seasons = sorted({p.season for p in profiles})
    n_seasons_total = len(all_seasons)

    position_groups: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for pos in sorted(by_pos.keys()):
        pos_profiles = sorted(by_pos[pos], key=lambda p: p.season)
        seasons = [p.season for p in pos_profiles]
        n_seasons = len(seasons)
        if n_seasons < 2:
            skipped.append({
                "position_group": pos,
                "n_seasons": n_seasons,
                "seasons": seasons,
            })
            continue

        x = np.arange(n_seasons, dtype=float)
        dimensions: list[dict[str, Any]] = []
        for feat in _STYLE_FEATURES:
            attr = _pos_feat_to_attr(feat)
            vals = np.array(
                [getattr(p, attr) for p in pos_profiles], dtype=float
            )
            slope, r2 = _linear_slope_and_r2(x, vals)
            delta = float(vals[-1] - vals[0])
            mean_val = float(vals.mean())
            label = _drift_label(delta, mean_val)
            dimensions.append({
                "feature": feat,
                "label": _DIM_LABELS[feat],
                "slope": round(slope, 4),
                "delta": round(delta, 3),
                "r_squared": round(r2, 3),
                "mean": round(mean_val, 3),
                "evolution_label": label,
                "per_season": [
                    {
                        "season": seasons[i],
                        "value": round(float(vals[i]), 3),
                        "n_players": pos_profiles[i].n_players,
                    }
                    for i in range(n_seasons)
                ],
            })

        position_groups.append({
            "position_group": pos,
            "seasons": seasons,
            "n_seasons": n_seasons,
            "dimensions": dimensions,
        })

    if not position_groups:
        return {
            "status": "insufficient_seasons",
            "league": league,
            "seasons": all_seasons,
            "n_seasons": n_seasons_total,
            "skipped_positions": skipped,
            "disclaimer": (
                "Position style evolution requires at least 2 seasons; "
                "no position group has enough seasons."
            ),
        }

    return {
        "status": "ok",
        "league": league,
        "seasons": all_seasons,
        "n_seasons": n_seasons_total,
        "position_groups": position_groups,
        "skipped_positions": skipped,
        "disclaimer": (
            "Per-position-group style evolution is a descriptive "
            "population view computed from minutes-weighted per-player "
            "style composites. Slopes and deltas describe observed "
            "changes — they do not predict future style or rank positions "
            "by quality. Evolution labels use a 5% relative threshold and "
            "are less reliable with only 2 seasons or uneven player "
            "coverage."
        ),
    }


def compute_position_style_drift(
    df: pd.DataFrame,
    position_group: str,
    *,
    league: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Compute a single position group's style drift across seasons.

    For the target position group, fits a least-squares slope across
    available seasons for each style dimension and reports the
    per-season values, net delta, slope, R² consistency, and a drift
    label (rising/falling/stable using a 5% relative threshold).

    Requires at least 2 seasons of profiles for the target position
    group. Returns ``status="insufficient_seasons"`` otherwise.

    This is a descriptive overlay — it does not predict future style
    or rank positions by quality.
    """
    if df.empty or not position_group:
        return {
            "status": "no_data",
            "position_group": position_group,
            "disclaimer": (
                "Empty rating matrix or missing position group name."
            ),
        }

    target_pos = str(position_group).strip().upper()
    if target_pos not in _POSITION_GROUPS:
        return {
            "status": "invalid_position",
            "position_group": position_group,
            "valid_positions": list(_POSITION_GROUPS),
            "disclaimer": (
                f"Unknown position group '{position_group}'. "
                f"Valid groups: {', '.join(_POSITION_GROUPS)}."
            ),
        }

    profiles = _aggregate_position_season_profiles(
        df,
        league=league,
        min_player_minutes=min_player_minutes,
    )
    pos_profiles = [
        p for p in profiles if p.position_group == target_pos
    ]
    if not pos_profiles:
        return {
            "status": "position_not_found",
            "position_group": target_pos,
            "league": league,
            "disclaimer": (
                f"No profiles found for position group '{target_pos}'"
                + (f" in league '{league}'." if league else ".")
            ),
        }

    pos_profiles.sort(key=lambda p: p.season)
    seasons = [p.season for p in pos_profiles]
    n_seasons = len(seasons)
    if n_seasons < 2:
        return {
            "status": "insufficient_seasons",
            "position_group": target_pos,
            "league": league,
            "seasons": seasons,
            "n_seasons": n_seasons,
            "disclaimer": (
                "Position style drift requires at least 2 seasons; "
                f"only {n_seasons} found."
            ),
        }

    x = np.arange(n_seasons, dtype=float)
    dimensions: list[dict[str, Any]] = []
    for feat in _STYLE_FEATURES:
        attr = _pos_feat_to_attr(feat)
        vals = np.array(
            [getattr(p, attr) for p in pos_profiles], dtype=float
        )
        slope, r2 = _linear_slope_and_r2(x, vals)
        delta = float(vals[-1] - vals[0])
        mean_val = float(vals.mean())
        label = _drift_label(delta, mean_val)
        dimensions.append({
            "feature": feat,
            "label": _DIM_LABELS[feat],
            "slope": round(slope, 4),
            "delta": round(delta, 3),
            "r_squared": round(r2, 3),
            "mean": round(mean_val, 3),
            "drift_label": label,
            "per_season": [
                {
                    "season": seasons[i],
                    "value": round(float(vals[i]), 3),
                    "n_players": pos_profiles[i].n_players,
                }
                for i in range(n_seasons)
            ],
        })

    return {
        "status": "ok",
        "position_group": target_pos,
        "league": league,
        "seasons": seasons,
        "n_seasons": n_seasons,
        "dimensions": dimensions,
        "disclaimer": (
            "Position style drift is a descriptive trajectory computed "
            "from minutes-weighted per-player style composites across "
            "seasons for one position group. Slopes and deltas describe "
            "observed changes — they do not predict future style or rank "
            "positions by quality. The drift label uses a 5% relative "
            "threshold and is less reliable with only 2 seasons or low "
            "sample sizes."
        ),
    }


def compute_position_style_drift_neighbors(
    df: pd.DataFrame,
    position_group: str,
    *,
    league: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Find position groups with similar style-drift patterns.

    For every position group with at least 2 seasons of profiles,
    computes a 4-dimensional drift vector (least-squares slope per
    style dimension). Ranks other position groups by cosine similarity
    to the target's drift vector (descending), with Euclidean distance
    on the raw slope vectors for reference.

    There are at most 8 standard position groups (GK/CB/FB/DM/CM/AM/W/ST),
    so the neighbors list is short by design — it shows which positions
    are evolving in similar directions (e.g. FB and W both rising in
    attack).

    This is a descriptive overlay — similar drift does not imply similar
    quality or future trajectory.
    """
    if df.empty or not position_group:
        return {
            "status": "no_data",
            "position_group": position_group,
            "disclaimer": (
                "Empty rating matrix or missing position group name."
            ),
        }

    target_pos = str(position_group).strip().upper()
    if target_pos not in _POSITION_GROUPS:
        return {
            "status": "invalid_position",
            "position_group": position_group,
            "valid_positions": list(_POSITION_GROUPS),
            "disclaimer": (
                f"Unknown position group '{position_group}'. "
                f"Valid groups: {', '.join(_POSITION_GROUPS)}."
            ),
        }

    profiles = _aggregate_position_season_profiles(
        df,
        league=league,
        min_player_minutes=min_player_minutes,
    )
    if not profiles:
        return {
            "status": "no_data",
            "position_group": target_pos,
            "disclaimer": (
                "No position-group-season profiles meet the minimum "
                f"player minutes threshold ({min_player_minutes:.0f} min)."
            ),
        }

    # Group by position_group.
    by_pos: dict[str, list[PositionSeasonProfile]] = {}
    for p in profiles:
        by_pos.setdefault(p.position_group, []).append(p)

    # Compute drift vectors for all positions with >= 2 seasons.
    drift_vectors: dict[str, np.ndarray] = {}
    pos_seasons: dict[str, list[str]] = {}
    for pos_name, pos_profiles in by_pos.items():
        pos_profiles.sort(key=lambda p: p.season)
        if len(pos_profiles) < 2:
            continue
        x = np.arange(len(pos_profiles), dtype=float)
        vec = np.zeros(len(_STYLE_FEATURES), dtype=float)
        for i, feat in enumerate(_STYLE_FEATURES):
            attr = _pos_feat_to_attr(feat)
            vals = np.array(
                [getattr(p, attr) for p in pos_profiles], dtype=float
            )
            slope, _ = _linear_slope_and_r2(x, vals)
            vec[i] = slope
        drift_vectors[pos_name] = vec
        pos_seasons[pos_name] = [p.season for p in pos_profiles]

    if target_pos not in drift_vectors:
        return {
            "status": "position_not_found",
            "position_group": target_pos,
            "league": league,
            "disclaimer": (
                f"Target position '{target_pos}' has fewer than 2 "
                "seasons of profiles; cannot compute a drift vector."
            ),
        }

    target_vec = drift_vectors[target_pos]
    target_norm = np.linalg.norm(target_vec)

    neighbors: list[dict[str, Any]] = []
    for pos_name, vec in drift_vectors.items():
        if pos_name == target_pos:
            continue
        vec_norm = np.linalg.norm(vec)
        denom = target_norm * vec_norm
        if denom > 1e-12:
            cos_sim = float(np.dot(target_vec, vec) / denom)
        else:
            cos_sim = 0.0
        dist = float(np.linalg.norm(target_vec - vec))
        neighbors.append({
            "position_group": pos_name,
            "n_seasons": len(pos_seasons[pos_name]),
            "seasons": pos_seasons[pos_name],
            "cosine_similarity": round(cos_sim, 4),
            "euclidean_distance": round(dist, 4),
            "drift_vector": [round(float(v), 4) for v in vec],
        })

    neighbors.sort(key=lambda n: n["cosine_similarity"], reverse=True)

    return {
        "status": "ok",
        "position_group": target_pos,
        "league": league,
        "seasons": pos_seasons[target_pos],
        "n_seasons": len(pos_seasons[target_pos]),
        "target_drift_vector": [round(float(v), 4) for v in target_vec],
        "target_drift_vector_labels": list(_STYLE_FEATURES),
        "n_candidates": len(drift_vectors) - 1,
        "neighbors": neighbors,
        "disclaimer": (
            "Position style drift neighbors are a descriptive overlay "
            "computed from least-squares style slopes across seasons. "
            "Cosine similarity on drift vectors identifies position "
            "groups whose styles are evolving in a similar direction — "
            "it does not imply similar quality, identical tactical "
            "roles, or future trajectory. There are at most 8 standard "
            "position groups, so the neighbor list is short by design."
        ),
    }


# ──────────────────────────────────────────────────────────────────────────
# Round 77: Position-group depth profile & cross-league comparison
# ──────────────────────────────────────────────────────────────────────────

_DEPTH_SHALLOW_THRESHOLD = 2
_DEPTH_DEEP_THRESHOLD = 4
_GAP_LEAGUE_PERCENTILE = 40.0  # below 40th percentile = low quality


def _compute_position_depth_stats(
    group: pd.DataFrame,
    *,
    min_player_minutes: float,
) -> dict[str, Any] | None:
    """Compute depth + style stats for one position-group slice.

    Returns ``None`` when no player passes the minutes threshold.
    """
    minutes = (
        group["minutes"]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
        .to_numpy(dtype=float)
    )
    mask = minutes >= min_player_minutes
    if not mask.any():
        return None
    minutes_f = minutes[mask]
    total_minutes = float(minutes_f.sum())
    if total_minutes <= 0:
        return None
    weights = minutes_f / total_minutes

    scores = (
        group["optimized_score"]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
        .to_numpy(dtype=float)[mask]
    )
    style_vals: dict[str, float] = {}
    for feat in _STYLE_FEATURES:
        col = (
            group[feat]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0.0)
            .to_numpy(dtype=float)[mask]
        )
        style_vals[feat] = float(np.average(col, weights=weights))

    n_players = int(mask.sum())
    if n_players == 0:
        return None

    depth_label = (
        "deep" if n_players >= _DEPTH_DEEP_THRESHOLD
        else "adequate" if n_players >= _DEPTH_SHALLOW_THRESHOLD
        else "shallow"
    )

    return {
        "n_players": n_players,
        "total_minutes": round(total_minutes),
        "score_min": round(float(scores.min()), 2),
        "score_median": round(float(np.median(scores)), 2),
        "score_max": round(float(scores.max()), 2),
        "score_mean": round(float(scores.mean()), 2),
        "score_std": round(float(scores.std()) if n_players > 1 else 0.0, 2),
        "score_p25": round(float(np.percentile(scores, 25)), 2),
        "score_p75": round(float(np.percentile(scores, 75)), 2),
        "minutes_median": round(float(np.median(minutes_f)), 0),
        "minutes_mean": round(float(minutes_f.mean()), 0),
        "attack": round(style_vals["npg_p90"], 3),
        "creation": round(style_vals["assists_p90"], 3),
        "defense": round(style_vals["defense_composite"], 2),
        "possession": round(style_vals["possession_composite"], 2),
        "depth_label": depth_label,
    }


def compute_position_depth_profile(
    df: pd.DataFrame,
    *,
    league: str | None = None,
    season: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Depth profile for each standard position group.

    For every standard position group (GK/CB/FB/DM/CM/AM/W/ST) present
    in the data after filtering, computes player count, total minutes,
    score distribution (min/median/max/mean/std/p25/p75), minutes
    distribution (median/mean), minutes-weighted style means, and a
    depth_label (shallow/adequate/deep).

    Position groups with zero qualifying players are listed in
    ``missing_positions``.

    This is a descriptive overlay — it does not rank positions by
    quality or predict future depth.
    """
    if df.empty:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "position_groups": [],
            "missing_positions": list(_POSITION_GROUPS),
            "disclaimer": "Empty rating matrix.",
        }

    work = df.copy()
    if league is not None:
        work = work[
            work["league"].astype(str).str.lower() == str(league).lower()
        ]
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]
    if "position_group" not in work.columns:
        if "sub_position" in work.columns:
            work["position_group"] = work["sub_position"]
        else:
            return {
                "status": "no_data",
                "league": league,
                "season": season,
                "position_groups": [],
                "missing_positions": list(_POSITION_GROUPS),
                "disclaimer": "No position_group column in rating matrix.",
            }
    work = work[
        work["position_group"].astype(str).str.upper().isin(_POSITION_GROUPS)
    ]
    if work.empty:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "position_groups": [],
            "missing_positions": list(_POSITION_GROUPS),
            "disclaimer": "No players in standard position groups after filtering.",
        }

    position_groups: list[dict[str, Any]] = []
    missing: list[str] = []
    for pos in _POSITION_GROUPS:
        sub = work[work["position_group"].astype(str).str.upper() == pos]
        if sub.empty:
            missing.append(pos)
            continue
        stats = _compute_position_depth_stats(
            sub, min_player_minutes=min_player_minutes
        )
        if stats is None:
            missing.append(pos)
            continue
        stats["position_group"] = pos
        position_groups.append(stats)

    if not position_groups:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "position_groups": [],
            "missing_positions": list(_POSITION_GROUPS),
            "disclaimer": "No position group had players above the minutes threshold.",
        }

    return {
        "status": "ok",
        "league": league,
        "season": season,
        "n_positions": len(position_groups),
        "position_groups": position_groups,
        "missing_positions": missing,
        "disclaimer": (
            "Position depth profile is a descriptive snapshot of the "
            "current rating matrix. Depth labels (shallow/adequate/deep) "
            "are based on player count thresholds and do not account "
            "for injuries, tactical flexibility, or upcoming transfers. "
            "Score distributions reflect rated players only."
        ),
    }


def compute_cross_league_position_comparison(
    df: pd.DataFrame,
    position_group: str,
    *,
    season: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Compare one position group's depth across leagues.

    For the target position group, groups players by league and computes
    per-league depth stats (n_players/score distribution/style means).
    Leagues are ranked by mean score descending and assigned a
    quality_tier (top/middle/bottom) based on the ranking.

    This is a descriptive overlay — it does not rank leagues by overall
    quality or predict match outcomes.
    """
    if df.empty or not position_group:
        return {
            "status": "no_data",
            "position_group": position_group,
            "disclaimer": "Empty rating matrix or missing position group.",
        }

    target_pos = str(position_group).strip().upper()
    if target_pos not in _POSITION_GROUPS:
        return {
            "status": "invalid_position",
            "position_group": position_group,
            "valid_positions": list(_POSITION_GROUPS),
            "disclaimer": (
                "Position group must be one of the 8 standard groups."
            ),
        }

    work = df.copy()
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]
    if "position_group" not in work.columns:
        if "sub_position" in work.columns:
            work["position_group"] = work["sub_position"]
        else:
            return {
                "status": "no_data",
                "position_group": target_pos,
                "disclaimer": "No position_group column in rating matrix.",
            }
    work = work[
        work["position_group"].astype(str).str.upper() == target_pos
    ]
    if work.empty:
        return {
            "status": "position_not_found",
            "position_group": target_pos,
            "disclaimer": (
                "Target position group not found in the data after filtering."
            ),
        }

    league_stats: list[dict[str, Any]] = []
    for league_name, group in work.groupby(
        work["league"].astype(str), sort=False
    ):
        stats = _compute_position_depth_stats(
            group, min_player_minutes=min_player_minutes
        )
        if stats is None:
            continue
        stats["league"] = str(league_name)
        league_stats.append(stats)

    if not league_stats:
        return {
            "status": "no_data",
            "position_group": target_pos,
            "season": season,
            "disclaimer": (
                "No league had players above the minutes threshold "
                "for this position group."
            ),
        }

    # Sort by mean score descending
    league_stats.sort(key=lambda x: x["score_mean"], reverse=True)

    n_leagues = len(league_stats)
    for i, ls in enumerate(league_stats):
        if n_leagues <= 2:
            ls["quality_tier"] = "top" if i == 0 else "bottom"
        else:
            top_cutoff = max(1, n_leagues // 3)
            bottom_cutoff = n_leagues - max(1, n_leagues // 3)
            if i < top_cutoff:
                ls["quality_tier"] = "top"
            elif i >= bottom_cutoff:
                ls["quality_tier"] = "bottom"
            else:
                ls["quality_tier"] = "middle"

    mean_scores = [ls["score_mean"] for ls in league_stats]
    return {
        "status": "ok",
        "position_group": target_pos,
        "season": season,
        "n_leagues": n_leagues,
        "leagues": league_stats,
        "best_league": league_stats[0]["league"] if league_stats else None,
        "worst_league": league_stats[-1]["league"] if league_stats else None,
        "score_spread": round(max(mean_scores) - min(mean_scores), 2)
        if mean_scores
        else 0.0,
        "disclaimer": (
            "Cross-league position comparison is a descriptive overlay "
            "based on the current rating matrix. Quality tiers "
            "(top/middle/bottom) are relative rankings within the "
            "available leagues and do not account for differences in "
            "league difficulty, sample size, or rating coverage. Mean "
            "scores are minutes-weighted."
        ),
    }


def compute_position_gap_report(
    df: pd.DataFrame,
    team: str,
    *,
    season: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Identify shallow and low-quality position groups for one team.

    For the target team, computes per-position-group depth stats and
    compares them against league-wide percentiles to identify gaps:
    - ``shallow``: fewer than 2 qualifying players
    - ``low_quality``: mean score below the league's 40th percentile
    - ``deep``: >=4 players and mean score >= league's 60th percentile

    This is a descriptive overlay — it does not recommend transfers,
    lineups, or tactical changes.
    """
    if df.empty or not team:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": "Empty rating matrix or missing team name.",
        }

    work = df.copy()
    work = work[
        work["team"].astype(str).str.lower() == str(team).strip().lower()
    ]
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]
    if work.empty:
        return {
            "status": "team_not_found",
            "team": team,
            "season": season,
            "disclaimer": "Team not found in the data after filtering.",
        }
    if "position_group" not in work.columns:
        if "sub_position" in work.columns:
            work["position_group"] = work["sub_position"]
        else:
            return {
                "status": "no_data",
                "team": team,
                "season": season,
                "disclaimer": "No position_group column in rating matrix.",
            }
    work = work[
        work["position_group"].astype(str).str.upper().isin(_POSITION_GROUPS)
    ]
    if work.empty:
        return {
            "status": "no_data",
            "team": team,
            "season": season,
            "disclaimer": "No players in standard position groups for this team.",
        }

    # Determine team's league for league-wide percentile comparison
    team_leagues = work["league"].astype(str).unique()
    league_filter = str(team_leagues[0]) if len(team_leagues) > 0 else None

    # League-wide scores per position group (for percentile comparison)
    league_df = df.copy()
    if league_filter is not None:
        league_df = league_df[
            league_df["league"].astype(str).str.lower()
            == league_filter.lower()
        ]
    if season is not None:
        league_df = league_df[
            league_df["season"].astype(str) == str(season)
        ]
    if "position_group" not in league_df.columns:
        if "sub_position" in league_df.columns:
            league_df["position_group"] = league_df["sub_position"]
    league_df = league_df[
        league_df["position_group"].astype(str).str.upper().isin(
            _POSITION_GROUPS
        )
    ]

    league_percentiles: dict[str, dict[str, float]] = {}
    for pos in _POSITION_GROUPS:
        sub = league_df[
            league_df["position_group"].astype(str).str.upper() == pos
        ]
        if sub.empty:
            continue
        minutes = (
            sub["minutes"]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0.0)
            .to_numpy(dtype=float)
        )
        mask = minutes >= min_player_minutes
        if not mask.any():
            continue
        scores = (
            sub["optimized_score"]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0.0)
            .to_numpy(dtype=float)[mask]
        )
        league_percentiles[pos] = {
            "p40": round(float(np.percentile(scores, 40)), 2),
            "p60": round(float(np.percentile(scores, 60)), 2),
            "n_players": int(mask.sum()),
        }

    position_groups: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    strengths: list[dict[str, Any]] = []
    missing: list[str] = []

    for pos in _POSITION_GROUPS:
        sub = work[work["position_group"].astype(str).str.upper() == pos]
        if sub.empty:
            missing.append(pos)
            gaps.append({
                "position_group": pos,
                "gap_type": "missing",
                "n_players": 0,
                "reason": "No players in this position group.",
            })
            continue
        stats = _compute_position_depth_stats(
            sub, min_player_minutes=min_player_minutes
        )
        if stats is None:
            missing.append(pos)
            gaps.append({
                "position_group": pos,
                "gap_type": "shallow",
                "n_players": 0,
                "reason": "No players above the minutes threshold.",
            })
            continue
        stats["position_group"] = pos
        position_groups.append(stats)

        lp = league_percentiles.get(pos)
        if lp is not None:
            stats["league_p40"] = lp["p40"]
            stats["league_p60"] = lp["p60"]
            stats["league_n_players"] = lp["n_players"]

        n_players = stats["n_players"]
        mean_score = stats["score_mean"]

        if n_players < _DEPTH_SHALLOW_THRESHOLD:
            gaps.append({
                "position_group": pos,
                "gap_type": "shallow",
                "n_players": n_players,
                "mean_score": mean_score,
                "reason": (
                    f"Only {n_players} qualifying player(s) — "
                    f"depth below shallow threshold ({_DEPTH_SHALLOW_THRESHOLD})."
                ),
            })
        elif lp is not None and mean_score < lp["p40"]:
            gaps.append({
                "position_group": pos,
                "gap_type": "low_quality",
                "n_players": n_players,
                "mean_score": mean_score,
                "league_p40": lp["p40"],
                "reason": (
                    f"Mean score {mean_score} below league 40th "
                    f"percentile ({lp['p40']})."
                ),
            })
        elif n_players >= _DEPTH_DEEP_THRESHOLD and lp is not None and mean_score >= lp["p60"]:
            strengths.append({
                "position_group": pos,
                "n_players": n_players,
                "mean_score": mean_score,
                "league_p60": lp["p60"],
                "reason": (
                    f"Deep roster ({n_players} players) with mean "
                    f"score {mean_score} >= league 60th percentile "
                    f"({lp['p60']})."
                ),
            })

    return {
        "status": "ok",
        "team": team,
        "league": league_filter,
        "season": season,
        "n_positions": len(position_groups),
        "position_groups": position_groups,
        "missing_positions": missing,
        "gaps": gaps,
        "n_gaps": len(gaps),
        "strengths": strengths,
        "n_strengths": len(strengths),
        "disclaimer": (
            "Position gap report is a descriptive overlay based on the "
            "current rating matrix. Gap types (shallow/low_quality/missing) "
            "and strength labels are heuristic thresholds, not transfer "
            "recommendations or tactical advice. League percentiles are "
            "computed from rated players in the team's league and season."
        ),
    }


# ── Round 78: Per-position-group action profile & granular decomposition ──

_ACTION_FEATURES = (
    "tackles_p90",
    "interceptions_p90",
    "crosses_p90",
    "fouls_drawn_p90",
    "fouls_p90",
    "g_a_volume",
    "npg_p90",
)

_TREND_FEATURES = (
    "npg_trend",
    "def_trend",
    "pos_trend",
)

_TREND_LABEL_THRESHOLD = 0.05  # 5% relative threshold for trend labels


def _compute_position_action_stats(
    group: pd.DataFrame,
    *,
    min_player_minutes: float,
    features: tuple[str, ...],
) -> dict[str, Any] | None:
    """Compute minutes-weighted means of per-90 actions for one position-group slice.

    Returns ``None`` when no player passes the minutes threshold.
    """
    minutes = (
        group["minutes"]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
        .to_numpy(dtype=float)
    )
    mask = minutes >= min_player_minutes
    if not mask.any():
        return None
    minutes_f = minutes[mask]
    total_minutes = float(minutes_f.sum())
    if total_minutes <= 0:
        return None
    weights = minutes_f / total_minutes

    n_players = int(mask.sum())
    vals: dict[str, float] = {}
    for feat in features:
        col = (
            group[feat]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0.0)
            .to_numpy(dtype=float)[mask]
        )
        vals[feat] = float(np.average(col, weights=weights))

    return {
        "n_players": n_players,
        "total_minutes": round(total_minutes),
        **{feat: round(vals[feat], 3) for feat in features},
    }


def compute_position_action_profile(
    df: pd.DataFrame,
    *,
    league: str | None = None,
    season: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Granular per-90 action profile for each standard position group.

    Decomposes the 4 composite style features (npg_p90, assists_p90,
    defense_composite, possession_composite) into 7 granular per-90
    actions (tackles, interceptions, crosses, fouls_drawn, fouls,
    g_a_volume, npg_p90) with minutes-weighted means.

    This is a descriptive overlay — it does not modify the prediction
    model or rank positions by quality.
    """
    if df.empty:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "position_groups": [],
            "missing_positions": list(_POSITION_GROUPS),
            "disclaimer": "Empty rating matrix.",
        }

    work = df.copy()
    if league is not None:
        work = work[
            work["league"].astype(str).str.lower() == str(league).lower()
        ]
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]
    if "position_group" not in work.columns:
        if "sub_position" in work.columns:
            work["position_group"] = work["sub_position"]
        else:
            return {
                "status": "no_data",
                "league": league,
                "season": season,
                "position_groups": [],
                "missing_positions": list(_POSITION_GROUPS),
                "disclaimer": "No position_group column in rating matrix.",
            }
    # Check all required action columns exist
    missing_cols = [c for c in _ACTION_FEATURES if c not in work.columns]
    if missing_cols:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "position_groups": [],
            "missing_positions": list(_POSITION_GROUPS),
            "disclaimer": (
                f"Missing action columns: {', '.join(missing_cols)}."
            ),
        }
    work = work[
        work["position_group"].astype(str).str.upper().isin(_POSITION_GROUPS)
    ]
    if work.empty:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "position_groups": [],
            "missing_positions": list(_POSITION_GROUPS),
            "disclaimer": "No players in standard position groups after filtering.",
        }

    position_groups: list[dict[str, Any]] = []
    missing: list[str] = []
    for pos in _POSITION_GROUPS:
        sub = work[work["position_group"].astype(str).str.upper() == pos]
        if sub.empty:
            missing.append(pos)
            continue
        stats = _compute_position_action_stats(
            sub, min_player_minutes=min_player_minutes, features=_ACTION_FEATURES
        )
        if stats is None:
            missing.append(pos)
            continue
        stats["position_group"] = pos
        position_groups.append(stats)

    if not position_groups:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "position_groups": [],
            "missing_positions": list(_POSITION_GROUPS),
            "disclaimer": "No position group had players above the minutes threshold.",
        }

    return {
        "status": "ok",
        "league": league,
        "season": season,
        "n_positions": len(position_groups),
        "position_groups": position_groups,
        "missing_positions": missing,
        "action_features": list(_ACTION_FEATURES),
        "disclaimer": (
            "Position action profile decomposes composite style scores "
            "into granular per-90 actions. Values are minutes-weighted "
            "means of players above the minutes threshold. This is a "
            "descriptive overlay — it does not predict future performance "
            "or rank positions by quality."
        ),
    }


def compute_action_based_position_similarity(
    df: pd.DataFrame,
    position_group: str,
    *,
    league: str | None = None,
    season: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Find position groups with similar per-90 action signatures.

    Computes a 7-dimensional action vector (tackles/interceptions/crosses/
    fouls_drawn/fouls/g_a_volume/npg_p90) for each position group, then
    ranks others by cosine similarity to the target position group's
    action vector.

    This is a descriptive overlay — similar action signatures do not
    imply similar quality or tactical roles.
    """
    if df.empty or not position_group:
        return {
            "status": "no_data",
            "position_group": position_group,
            "disclaimer": "Empty rating matrix or missing position group.",
        }

    target_pos = str(position_group).strip().upper()
    if target_pos not in _POSITION_GROUPS:
        return {
            "status": "invalid_position",
            "position_group": position_group,
            "valid_positions": list(_POSITION_GROUPS),
            "disclaimer": "Position group must be one of the 8 standard groups.",
        }

    work = df.copy()
    if league is not None:
        work = work[
            work["league"].astype(str).str.lower() == str(league).lower()
        ]
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]
    if "position_group" not in work.columns:
        if "sub_position" in work.columns:
            work["position_group"] = work["sub_position"]
        else:
            return {
                "status": "no_data",
                "position_group": target_pos,
                "disclaimer": "No position_group column in rating matrix.",
            }
    missing_cols = [c for c in _ACTION_FEATURES if c not in work.columns]
    if missing_cols:
        return {
            "status": "no_data",
            "position_group": target_pos,
            "disclaimer": (
                f"Missing action columns: {', '.join(missing_cols)}."
            ),
        }
    work = work[
        work["position_group"].astype(str).str.upper().isin(_POSITION_GROUPS)
    ]
    if work.empty:
        return {
            "status": "position_not_found",
            "position_group": target_pos,
            "disclaimer": "No players in standard position groups after filtering.",
        }

    # Compute action vectors for each position group
    action_vectors: dict[str, np.ndarray] = {}
    for pos in _POSITION_GROUPS:
        sub = work[work["position_group"].astype(str).str.upper() == pos]
        if sub.empty:
            continue
        stats = _compute_position_action_stats(
            sub, min_player_minutes=min_player_minutes, features=_ACTION_FEATURES
        )
        if stats is None:
            continue
        vec = np.array(
            [stats[feat] for feat in _ACTION_FEATURES], dtype=float
        )
        action_vectors[pos] = vec

    if target_pos not in action_vectors:
        return {
            "status": "position_not_found",
            "position_group": target_pos,
            "disclaimer": (
                "Target position group has no players above the minutes "
                "threshold."
            ),
        }

    target_vec = action_vectors[target_pos]
    target_norm = float(np.linalg.norm(target_vec))

    neighbors: list[dict[str, Any]] = []
    for pos, vec in action_vectors.items():
        if pos == target_pos:
            continue
        vec_norm = float(np.linalg.norm(vec))
        if target_norm == 0 or vec_norm == 0:
            cos_sim = 0.0
        else:
            cos_sim = float(np.dot(target_vec, vec)) / (
                target_norm * vec_norm
            )
        euclidean = float(np.linalg.norm(target_vec - vec))
        neighbors.append({
            "position_group": pos,
            "cosine_similarity": round(cos_sim, 3),
            "euclidean_distance": round(euclidean, 3),
        })

    neighbors.sort(key=lambda n: n["cosine_similarity"], reverse=True)

    return {
        "status": "ok",
        "position_group": target_pos,
        "league": league,
        "season": season,
        "n_candidates": len(neighbors),
        "target_action_vector": [round(float(v), 3) for v in target_vec],
        "target_action_vector_labels": list(_ACTION_FEATURES),
        "neighbors": neighbors,
        "disclaimer": (
            "Action-based position similarity is a descriptive overlay "
            "based on granular per-90 action signatures. Similar action "
            "profiles do not imply similar tactical roles, quality, or "
            "future trajectories. Cosine similarity ranges from -1 to 1."
        ),
    }


def compute_position_trend_overlay(
    df: pd.DataFrame,
    *,
    league: str | None = None,
    season: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Collective improvement/decline trends for each position group.

    For each standard position group, computes the minutes-weighted mean
    of npg_trend / def_trend / pos_trend (cross-season improvement
    metrics from the rating pipeline) and assigns a trend_label
    (imving / declining / stable) per dimension using a 5% relative
    threshold.

    This is a descriptive overlay — it does not predict future trends
    or rank positions by quality.
    """
    if df.empty:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "position_groups": [],
            "missing_positions": list(_POSITION_GROUPS),
            "disclaimer": "Empty rating matrix.",
        }

    work = df.copy()
    if league is not None:
        work = work[
            work["league"].astype(str).str.lower() == str(league).lower()
        ]
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]
    if "position_group" not in work.columns:
        if "sub_position" in work.columns:
            work["position_group"] = work["sub_position"]
        else:
            return {
                "status": "no_data",
                "league": league,
                "season": season,
                "position_groups": [],
                "missing_positions": list(_POSITION_GROUPS),
                "disclaimer": "No position_group column in rating matrix.",
            }
    missing_cols = [c for c in _TREND_FEATURES if c not in work.columns]
    if missing_cols:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "position_groups": [],
            "missing_positions": list(_POSITION_GROUPS),
            "disclaimer": (
                f"Missing trend columns: {', '.join(missing_cols)}."
            ),
        }
    work = work[
        work["position_group"].astype(str).str.upper().isin(_POSITION_GROUPS)
    ]
    if work.empty:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "position_groups": [],
            "missing_positions": list(_POSITION_GROUPS),
            "disclaimer": "No players in standard position groups after filtering.",
        }

    def _trend_label(val: float) -> str:
        if abs(val) < _TREND_LABEL_THRESHOLD:
            return "stable"
        return "improving" if val > 0 else "declining"

    position_groups: list[dict[str, Any]] = []
    missing: list[str] = []
    for pos in _POSITION_GROUPS:
        sub = work[work["position_group"].astype(str).str.upper() == pos]
        if sub.empty:
            missing.append(pos)
            continue
        stats = _compute_position_action_stats(
            sub, min_player_minutes=min_player_minutes, features=_TREND_FEATURES
        )
        if stats is None:
            missing.append(pos)
            continue
        dimensions = []
        for feat in _TREND_FEATURES:
            val = stats[feat]
            dimensions.append({
                "feature": feat,
                "value": val,
                "trend_label": _trend_label(val),
            })
        position_groups.append({
            "position_group": pos,
            "n_players": stats["n_players"],
            "total_minutes": stats["total_minutes"],
            "dimensions": dimensions,
        })

    if not position_groups:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "position_groups": [],
            "missing_positions": list(_POSITION_GROUPS),
            "disclaimer": "No position group had players above the minutes threshold.",
        }

    return {
        "status": "ok",
        "league": league,
        "season": season,
        "n_positions": len(position_groups),
        "position_groups": position_groups,
        "missing_positions": missing,
        "trend_features": list(_TREND_FEATURES),
        "disclaimer": (
            "Position trend overlay aggregates per-player cross-season "
            "improvement metrics (npg_trend / def_trend / pos_trend) "
            "into minutes-weighted position-group means. Trend labels "
            "(improving/declining/stable) use a 5% relative threshold. "
            "This is a descriptive overlay — it does not predict future "
            "trends or rank positions by quality."
        ),
    }


# --- Round 79: team-level action signature layer ---------------------------
#
# Lifts the per-90 action decomposition (Round 78) from position-group
# level to team level, and clones the league-percentile template (Round
# 74) with 7 action features instead of 4 style composites. All three
# functions are descriptive overlays and do not modify the prediction
# model.

_ACTION_FEATURE_LABELS = {
    "tackles_p90": "tackles",
    "interceptions_p90": "interceptions",
    "crosses_p90": "crosses",
    "fouls_drawn_p90": "fouls_drawn",
    "fouls_p90": "fouls_committed",
    "g_a_volume": "goal_contribution_volume",
    "npg_p90": "non_penalty_goals",
}


def _build_team_action_profiles(
    df: pd.DataFrame,
    *,
    league: str | None,
    season: str | None,
    min_player_minutes: float,
) -> list[dict[str, Any]]:
    """Build minutes-weighted action profiles for each team.

    Returns a list of dicts, each containing ``team``, ``n_players``,
    ``total_minutes``, and the 7 ``_ACTION_FEATURES`` values. Reuses
    ``_compute_position_action_stats`` (which is generic — it operates
    on any group DataFrame, not just position groups).
    """
    if df.empty:
        return []

    work = df.copy()
    if league is not None:
        work = work[
            work["league"].astype(str).str.lower() == str(league).lower()
        ]
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]

    missing_cols = [c for c in _ACTION_FEATURES if c not in work.columns]
    if missing_cols or "team" not in work.columns:
        return []

    profiles: list[dict[str, Any]] = []
    for team, group in work.groupby("team", sort=False):
        stats = _compute_position_action_stats(
            group,
            min_player_minutes=min_player_minutes,
            features=_ACTION_FEATURES,
        )
        if stats is None:
            continue
        stats["team"] = str(team)
        profiles.append(stats)

    return profiles


def _pick_team_action_profile(
    profiles: list[dict[str, Any]], team_name: str
) -> dict[str, Any] | None:
    """Pick a team's action profile from a list (case-insensitive)."""
    matches = [
        p for p in profiles if str(p.get("team", "")).lower() == team_name.lower()
    ]
    if not matches:
        return None
    return matches[0]


def compute_team_action_profile(
    df: pd.DataFrame,
    *,
    league: str | None = None,
    season: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Granular per-90 action profile for each team.

    Decomposes the 4 composite style features into 7 granular per-90
    actions (tackles, interceptions, crosses, fouls_drawn, fouls,
    g_a_volume, npg_p90) with minutes-weighted means per team.

    This is a descriptive overlay — it does not modify the prediction
    model or rank teams by quality.
    """
    if df.empty:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "teams": [],
            "disclaimer": "Empty rating matrix.",
        }

    missing_cols = [c for c in _ACTION_FEATURES if c not in df.columns]
    if missing_cols:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "teams": [],
            "disclaimer": (
                f"Missing action columns: {', '.join(missing_cols)}."
            ),
        }

    profiles = _build_team_action_profiles(
        df,
        league=league,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    if not profiles:
        return {
            "status": "no_data",
            "league": league,
            "season": season,
            "teams": [],
            "disclaimer": "No team had players above the minutes threshold.",
        }

    # Sort by total minutes descending for stable display.
    profiles.sort(key=lambda p: p.get("total_minutes", 0), reverse=True)

    return {
        "status": "ok",
        "league": league,
        "season": season,
        "n_teams": len(profiles),
        "teams": profiles,
        "action_features": list(_ACTION_FEATURES),
        "disclaimer": (
            "Team action profile decomposes composite style scores into "
            "granular per-90 actions. Values are minutes-weighted means "
            "of players above the minutes threshold. This is a "
            "descriptive overlay — it does not predict future performance "
            "or rank teams by quality."
        ),
    }


def compute_league_action_percentiles(
    df: pd.DataFrame,
    team: str,
    *,
    season: str | None = None,
    league: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Per-action percentile rank of one team within its league population.

    For each of the 7 action features (tackles_p90, interceptions_p90,
    crosses_p90, fouls_drawn_p90, fouls_p90, g_a_volume, npg_p90),
    computes the team's percentile rank (0–100) within the filtered
    league population using tie-handled average ranks. A percentile of
    90 means the team is in the top 10% for that action.

    This is a descriptive overlay — percentiles describe relative
    standing, not absolute quality or tactical correctness.
    """
    if df.empty or not team:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": "Empty rating matrix or missing team name.",
        }

    profiles = _build_team_action_profiles(
        df,
        league=league,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    if not profiles:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": (
                "No team action profiles meet the minimum player-minutes "
                f"threshold ({min_player_minutes:.0f} min)."
            ),
        }

    target = _pick_team_action_profile(profiles, team)
    if target is None:
        return {
            "status": "team_not_found",
            "team": team,
            "disclaimer": (
                f"No action profile found for '{team}'."
                + (f" Season={season}." if season else "")
                + (f" League={league}." if league else "")
                + " Check the team name spelling or broaden the filters."
            ),
        }

    # Build feature matrix: rows = teams, cols = 7 action features.
    mat = np.array(
        [
            [p[feat] for feat in _ACTION_FEATURES]
            for p in profiles
        ],
        dtype=float,
    )
    n_pop = len(profiles)
    target_idx = profiles.index(target)
    target_raw = mat[target_idx]

    dimensions: list[dict[str, Any]] = []
    for i, feat in enumerate(_ACTION_FEATURES):
        col = mat[:, i]
        val = float(target_raw[i])
        # Percentile rank with tie-handling (average rank).
        if n_pop <= 1:
            pct = 50.0
        else:
            rank = float((col < val).sum()) + 0.5 * float(
                (col == val).sum()
            )
            pct = round(100.0 * rank / n_pop, 1) if n_pop > 0 else 50.0
        # Quartile label.
        if pct >= 75:
            quartile = "top"
        elif pct >= 50:
            quartile = "upper_mid"
        elif pct >= 25:
            quartile = "lower_mid"
        else:
            quartile = "bottom"
        dimensions.append(
            {
                "feature": feat,
                "label": _ACTION_FEATURE_LABELS[feat],
                "value": round(val, 3),
                "percentile": pct,
                "quartile": quartile,
                "population_min": round(float(col.min()), 3),
                "population_max": round(float(col.max()), 3),
                "population_mean": round(float(col.mean()), 3),
                "population_median": round(float(np.median(col)), 3),
            }
        )

    # Population stats for the target summary.
    pop_means = mat.mean(axis=0)
    pop_stds = mat.std(axis=0, ddof=0)

    return {
        "status": "ok",
        "team": target["team"],
        "season": season,
        "league": league,
        "target": {
            "team": target["team"],
            "n_players": target["n_players"],
            "total_minutes": target["total_minutes"],
            "action_values": {
                feat: round(float(target_raw[i]), 3)
                for i, feat in enumerate(_ACTION_FEATURES)
            },
            "population_means": {
                feat: round(float(pop_means[i]), 3)
                for i, feat in enumerate(_ACTION_FEATURES)
            },
            "population_stds": {
                feat: round(float(pop_stds[i]), 3)
                for i, feat in enumerate(_ACTION_FEATURES)
            },
        },
        "n_population": n_pop,
        "dimensions": dimensions,
        "disclaimer": (
            "Action percentiles describe where a team sits within the "
            "filtered league population on each granular per-90 action. "
            "They are relative, not absolute — a 90th-percentile cross "
            "volume in a low-cross league is not equivalent to 90th-"
            "percentile in a high-cross one. Percentiles do not predict "
            "match outcomes."
        ),
    }


def compute_team_action_similarity(
    df: pd.DataFrame,
    team: str,
    *,
    league: str | None = None,
    season: str | None = None,
    top_n: int = 10,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Find teams with similar per-90 action signatures.

    Computes a 7-dimensional action vector (tackles/interceptions/
    crosses/fouls_drawn/fouls/g_a_volume/npg_p90) for each team, then
    ranks others by cosine similarity to the target team's action
    vector. Euclidean distance is included as a reference.

    This is a descriptive overlay — similar action signatures do not
    imply similar quality, tactical systems, or match outcomes.
    """
    if df.empty or not team:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": "Empty rating matrix or missing team name.",
        }

    profiles = _build_team_action_profiles(
        df,
        league=league,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    if not profiles:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": (
                "No team action profiles meet the minimum player-minutes "
                f"threshold ({min_player_minutes:.0f} min)."
            ),
        }

    target = _pick_team_action_profile(profiles, team)
    if target is None:
        return {
            "status": "team_not_found",
            "team": team,
            "disclaimer": (
                f"No action profile found for '{team}'."
                + (f" Season={season}." if season else "")
                + (f" League={league}." if league else "")
                + " Check the team name spelling or broaden the filters."
            ),
        }

    # Build action vectors for each team.
    action_vectors: dict[str, np.ndarray] = {}
    for p in profiles:
        vec = np.array(
            [p[feat] for feat in _ACTION_FEATURES], dtype=float
        )
        action_vectors[p["team"]] = vec

    target_vec = action_vectors[target["team"]]
    target_norm = float(np.linalg.norm(target_vec))

    neighbors: list[dict[str, Any]] = []
    for t_name, vec in action_vectors.items():
        if t_name == target["team"]:
            continue
        vec_norm = float(np.linalg.norm(vec))
        if target_norm == 0 or vec_norm == 0:
            cos_sim = 0.0
        else:
            cos_sim = float(np.dot(target_vec, vec)) / (
                target_norm * vec_norm
            )
        euclidean = float(np.linalg.norm(target_vec - vec))
        # Attach n_players for context.
        neighbor_profile = next(
            (p for p in profiles if p["team"] == t_name), None
        )
        neighbors.append({
            "team": t_name,
            "cosine_similarity": round(cos_sim, 3),
            "euclidean_distance": round(euclidean, 3),
            "n_players": (
                neighbor_profile["n_players"] if neighbor_profile else 0
            ),
            "total_minutes": (
                neighbor_profile["total_minutes"] if neighbor_profile else 0
            ),
        })

    neighbors.sort(key=lambda n: n["cosine_similarity"], reverse=True)

    # Apply top_n limit.
    top_n = max(1, min(int(top_n), len(neighbors))) if neighbors else 0
    neighbors = neighbors[:top_n]

    return {
        "status": "ok",
        "team": target["team"],
        "league": league,
        "season": season,
        "n_candidates": len(neighbors),
        "target_action_vector": [round(float(v), 3) for v in target_vec],
        "target_action_vector_labels": list(_ACTION_FEATURES),
        "neighbors": neighbors,
        "disclaimer": (
            "Team action similarity is a descriptive overlay based on "
            "granular per-90 action signatures. Similar action profiles "
            "do not imply similar tactical systems, quality, or match "
            "outcomes. Cosine similarity ranges from -1 to 1."
        ),
    }


# --- Round 80: league-level action distribution layer -----------------------
#
# Lifts the team action profiles (Round 79) to the league level, mirroring
# the style-atlas (Round 74) and style-evolution (Round 75) patterns with 7
# action features instead of 4 style composites, and adds a cross-league
# comparison dimension. All three functions are descriptive overlays.


def _build_team_action_profiles_full(
    df: pd.DataFrame,
    *,
    league: str | None,
    season: str | None,
    min_player_minutes: float,
) -> list[dict[str, Any]]:
    """Build per-team-per-season action profiles with league/season metadata.

    Unlike ``_build_team_action_profiles`` (Round 79) which groups by team
    only and discards season/league, this helper groups by ``(team, season,
    league)`` so each profile retains its temporal and league context.
    This is needed for evolution (group by season) and cross-league
    comparison (group by league).
    """
    if df.empty:
        return []

    work = df.copy()
    if league is not None:
        work = work[
            work["league"].astype(str).str.lower() == str(league).lower()
        ]
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]

    missing_cols = [c for c in _ACTION_FEATURES if c not in work.columns]
    required = missing_cols + [
        c for c in ("team", "league", "season") if c not in work.columns
    ]
    if required:
        return []

    profiles: list[dict[str, Any]] = []
    for (team, ssn, lg), group in work.groupby(
        ["team", "season", "league"], sort=False
    ):
        stats = _compute_position_action_stats(
            group,
            min_player_minutes=min_player_minutes,
            features=_ACTION_FEATURES,
        )
        if stats is None:
            continue
        stats["team"] = str(team)
        stats["season"] = str(ssn)
        stats["league"] = str(lg)
        profiles.append(stats)

    return profiles


def compute_league_action_atlas(
    df: pd.DataFrame,
    *,
    season: str | None = None,
    league: str | None = None,
    n_bins: int = 8,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """League-wide distribution of team per-90 actions across all 7 features.

    For each of the 7 action features (tackles_p90, interceptions_p90,
    crosses_p90, fouls_drawn_p90, fouls_p90, g_a_volume, npg_p90), computes
    a histogram (with ``n_bins`` bins between min and max), quartiles
    (Q1/median/Q3/IQR), and the list of outlier teams (z-score magnitude
    >= 2.0). Mirrors ``compute_style_atlas`` (Round 74) with action
    features instead of style composites.

    This is a descriptive population view — it does not rank teams by
    quality or predict outcomes.
    """
    if df.empty:
        return {
            "status": "no_data",
            "season": season,
            "league": league,
            "disclaimer": "Empty rating matrix.",
        }

    profiles = _build_team_action_profiles_full(
        df,
        league=league,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    if not profiles:
        return {
            "status": "no_data",
            "season": season,
            "league": league,
            "disclaimer": (
                "No team action profiles meet the minimum player-minutes "
                f"threshold ({min_player_minutes:.0f} min)."
            ),
        }

    mat = np.array(
        [[p[feat] for feat in _ACTION_FEATURES] for p in profiles],
        dtype=float,
    )
    means = mat.mean(axis=0)
    stds = mat.std(axis=0, ddof=0)
    stds_safe = np.where(stds == 0, 1.0, stds)
    standardized = (mat - means) / stds_safe

    n_bins = max(3, min(20, int(n_bins)))
    n_pop = len(profiles)

    dimensions: list[dict[str, Any]] = []
    for i, feat in enumerate(_ACTION_FEATURES):
        col = mat[:, i]
        col_min = float(col.min())
        col_max = float(col.max())
        col_mean = float(col.mean())
        col_median = float(np.median(col))
        q1 = float(np.percentile(col, 25))
        q3 = float(np.percentile(col, 75))
        iqr = q3 - q1

        if col_max > col_min:
            edges = np.linspace(col_min, col_max, n_bins + 1)
            counts, _ = np.histogram(col, bins=edges)
            bins = [
                {
                    "low": round(float(edges[b]), 3),
                    "high": round(float(edges[b + 1]), 3),
                    "count": int(counts[b]),
                }
                for b in range(n_bins)
            ]
        else:
            bins = [
                {
                    "low": round(col_min, 3),
                    "high": round(col_max, 3),
                    "count": n_pop,
                }
            ]

        std_col = standardized[:, i]
        outliers: list[dict[str, Any]] = []
        for j, p in enumerate(profiles):
            z = float(std_col[j])
            if abs(z) >= 2.0:
                outliers.append(
                    {
                        "team": p["team"],
                        "league": p["league"],
                        "season": p["season"],
                        "value": round(float(col[j]), 3),
                        "z_score": round(z, 3),
                        "direction": "high" if z > 0 else "low",
                    }
                )
        outliers.sort(key=lambda o: abs(o["z_score"]), reverse=True)

        dimensions.append(
            {
                "feature": feat,
                "label": _ACTION_FEATURE_LABELS[feat],
                "min": round(col_min, 3),
                "max": round(col_max, 3),
                "mean": round(col_mean, 3),
                "median": round(col_median, 3),
                "q1": round(q1, 3),
                "q3": round(q3, 3),
                "iqr": round(iqr, 3),
                "bins": bins,
                "outliers": outliers,
            }
        )

    return {
        "status": "ok",
        "season": season,
        "league": league,
        "n_population": n_pop,
        "dimensions": dimensions,
        "action_features": list(_ACTION_FEATURES),
        "disclaimer": (
            "The league action atlas is a descriptive population view "
            "computed from minutes-weighted per-player per-90 actions. "
            "Histograms, quartiles and outliers describe how actions are "
            "distributed across the filtered league population — they do "
            "not rank teams by quality or predict match outcomes. "
            "Outliers are teams with a z-score magnitude >= 2.0 on the "
            "standardised dimension; a low sample size makes outlier "
            "labels less meaningful."
        ),
    }


def compute_league_action_evolution(
    df: pd.DataFrame,
    *,
    league: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """League-wide action evolution across seasons.

    Groups team-season action profiles by season and computes the median
    and mean for each of the 7 action features per season. Then fits a
    least-squares slope across seasons for each feature to show whether
    the league average is rising, falling, or stable over time. Mirrors
    ``compute_league_style_evolution`` (Round 75) with action features.

    Requires at least 2 seasons of data. Returns
    ``status="insufficient_seasons"`` otherwise.

    This is a descriptive population view — it does not predict future
    league actions or rank seasons by quality.
    """
    if df.empty:
        return {
            "status": "no_data",
            "disclaimer": "Empty rating matrix.",
        }

    profiles = _build_team_action_profiles_full(
        df,
        league=league,
        season=None,
        min_player_minutes=min_player_minutes,
    )
    if not profiles:
        return {
            "status": "no_data",
            "disclaimer": (
                "No team action profiles meet the minimum player-minutes "
                f"threshold ({min_player_minutes:.0f} min)."
            ),
        }

    by_season: dict[str, list[dict[str, Any]]] = {}
    for p in profiles:
        by_season.setdefault(p["season"], []).append(p)
    seasons_sorted = sorted(by_season.keys())
    n_seasons = len(seasons_sorted)
    if n_seasons < 2:
        return {
            "status": "insufficient_seasons",
            "league": league,
            "seasons": seasons_sorted,
            "n_seasons": n_seasons,
            "disclaimer": (
                "League action evolution requires at least 2 seasons; "
                f"only {n_seasons} found."
            ),
        }

    x = np.arange(n_seasons, dtype=float)
    per_season_summary: list[dict[str, Any]] = []
    for s in seasons_sorted:
        season_profiles = by_season[s]
        entry: dict[str, Any] = {
            "season": s,
            "n_teams": len(season_profiles),
        }
        for feat in _ACTION_FEATURES:
            vals = np.array(
                [p[feat] for p in season_profiles], dtype=float
            )
            entry[feat] = {
                "median": round(float(np.median(vals)), 3),
                "mean": round(float(vals.mean()), 3),
                "std": round(float(vals.std(ddof=0)), 3),
                "min": round(float(vals.min()), 3),
                "max": round(float(vals.max()), 3),
            }
        per_season_summary.append(entry)

    dimensions: list[dict[str, Any]] = []
    for feat in _ACTION_FEATURES:
        medians = np.array(
            [
                float(np.median([p[feat] for p in by_season[s]]))
                for s in seasons_sorted
            ],
            dtype=float,
        )
        means = np.array(
            [
                float(np.mean([p[feat] for p in by_season[s]]))
                for s in seasons_sorted
            ],
            dtype=float,
        )
        slope_med, r2_med = _linear_slope_and_r2(x, medians)
        slope_mean, r2_mean = _linear_slope_and_r2(x, means)
        delta_med = float(medians[-1] - medians[0])
        delta_mean = float(means[-1] - means[0])
        label = _drift_label(delta_med, float(medians.mean()))
        dimensions.append(
            {
                "feature": feat,
                "label": _ACTION_FEATURE_LABELS[feat],
                "median_slope": round(slope_med, 4),
                "median_delta": round(delta_med, 3),
                "median_r_squared": round(r2_med, 3),
                "mean_slope": round(slope_mean, 4),
                "mean_delta": round(delta_mean, 3),
                "mean_r_squared": round(r2_mean, 3),
                "evolution_label": label,
            }
        )

    return {
        "status": "ok",
        "league": league,
        "seasons": seasons_sorted,
        "n_seasons": n_seasons,
        "per_season": per_season_summary,
        "dimensions": dimensions,
        "action_features": list(_ACTION_FEATURES),
        "disclaimer": (
            "League action evolution is a descriptive population view "
            "computed from minutes-weighted per-player per-90 actions "
            "across seasons. Slopes and deltas describe observed changes "
            "— they do not predict future league actions or rank seasons "
            "by quality. The evolution label uses a 5% relative threshold "
            "and is less reliable with only 2 seasons or low sample sizes."
        ),
    }


def compute_cross_league_action_comparison(
    df: pd.DataFrame,
    *,
    season: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Compare per-90 action profiles across leagues.

    Groups team-season action profiles by league and computes per-league
    means and medians for each of the 7 action features. Leagues are
    ranked by mean value per action (descending), and a quality_tier is
    assigned (top/middle/bottom, or top/bottom when <= 2 leagues).

    This is a descriptive comparison — it does not rank leagues by
    overall quality or predict cross-league match outcomes.
    """
    if df.empty:
        return {
            "status": "no_data",
            "season": season,
            "disclaimer": "Empty rating matrix.",
        }

    profiles = _build_team_action_profiles_full(
        df,
        league=None,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    if not profiles:
        return {
            "status": "no_data",
            "season": season,
            "disclaimer": (
                "No team action profiles meet the minimum player-minutes "
                f"threshold ({min_player_minutes:.0f} min)."
            ),
        }

    by_league: dict[str, list[dict[str, Any]]] = {}
    for p in profiles:
        by_league.setdefault(p["league"], []).append(p)
    n_leagues = len(by_league)
    if n_leagues == 0:
        return {
            "status": "no_data",
            "season": season,
            "disclaimer": "No league groupings found.",
        }

    # Build per-league summary with all 7 action features.
    league_summaries: list[dict[str, Any]] = []
    for lg, league_profiles in by_league.items():
        entry: dict[str, Any] = {
            "league": lg,
            "n_teams": len(league_profiles),
            "total_minutes": sum(
                p["total_minutes"] for p in league_profiles
            ),
        }
        for feat in _ACTION_FEATURES:
            vals = np.array(
                [p[feat] for p in league_profiles], dtype=float
            )
            entry[feat] = {
                "mean": round(float(vals.mean()), 3),
                "median": round(float(np.median(vals)), 3),
                "std": round(float(vals.std(ddof=0)), 3),
                "min": round(float(vals.min()), 3),
                "max": round(float(vals.max()), 3),
            }
        league_summaries.append(entry)

    # Per-feature ranking and quality_tier assignment.
    dimensions: list[dict[str, Any]] = []
    for feat in _ACTION_FEATURES:
        # Sort leagues by mean value descending for this feature.
        ranked = sorted(
            league_summaries,
            key=lambda e: e[feat]["mean"],
            reverse=True,
        )
        ranks: list[dict[str, Any]] = []
        for rank_idx, entry in enumerate(ranked):
            if n_leagues <= 2:
                tier = "top" if rank_idx == 0 else "bottom"
            elif rank_idx == 0:
                tier = "top"
            elif rank_idx == n_leagues - 1:
                tier = "bottom"
            else:
                tier = "middle"
            ranks.append(
                {
                    "rank": rank_idx + 1,
                    "league": entry["league"],
                    "mean": entry[feat]["mean"],
                    "median": entry[feat]["median"],
                    "n_teams": entry["n_teams"],
                    "quality_tier": tier,
                }
            )
        dimensions.append(
            {
                "feature": feat,
                "label": _ACTION_FEATURE_LABELS[feat],
                "rankings": ranks,
            }
        )

    return {
        "status": "ok",
        "season": season,
        "n_leagues": n_leagues,
        "leagues": league_summaries,
        "dimensions": dimensions,
        "action_features": list(_ACTION_FEATURES),
        "disclaimer": (
            "Cross-league action comparison is a descriptive view "
            "computed from minutes-weighted per-player per-90 actions. "
            "League rankings per action describe relative standing in "
            "the filtered population — they do not rank leagues by "
            "overall quality, tactical sophistication, or predict "
            "cross-league match outcomes. Quality tiers are heuristic "
            "and less meaningful with few leagues."
        ),
    }


# ── Round 82: Cross-league scouting target recommendation suite ───────────

_SCOUTING_DISCLAIMER = (
    "Cross-league scouting target recommendation is a descriptive "
    "overlay based on the current rating matrix. Candidates are "
    "identified by score thresholds and style similarity — this is "
    "NOT a transfer recommendation, market valuation, or tactical "
    "advice. League percentiles are computed from rated players in "
    "the candidate's league and season."
)

_DEFAULT_SCOUTING_TOP_N = 10
_MAX_SCOUTING_TOP_N = 50
_SCOUTING_PERCENTILE_THRESHOLD = 75.0  # top quartile


def _find_team_league(work: pd.DataFrame, team: str) -> str | None:
    """Return the most common league for a team in the frame."""
    sub = work[work["team"].astype(str).str.lower() == str(team).strip().lower()]
    if sub.empty:
        return None
    leagues = sub["league"].astype(str).value_counts()
    return str(leagues.index[0]) if not leagues.empty else None


def _team_position_depth(
    work: pd.DataFrame,
    *,
    min_player_minutes: float,
) -> dict[str, dict[str, Any]]:
    """Per-position-group depth stats for one team's filtered frame."""
    out: dict[str, dict[str, Any]] = {}
    for pos in _POSITION_GROUPS:
        sub = work[work["position_group"].astype(str).str.upper() == pos]
        if sub.empty:
            continue
        stats = _compute_position_depth_stats(sub, min_player_minutes=min_player_minutes)
        if stats is None:
            continue
        stats["position_group"] = pos
        out[pos] = stats
    return out


def compute_cross_league_team_depth(
    df: pd.DataFrame,
    team_a: str,
    team_b: str,
    *,
    season: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
) -> dict[str, Any]:
    """Compare two teams' per-position-group depth profiles side-by-side.

    For each of the 8 standard position groups, reports both teams'
    n_players / mean_score / depth_label and an ``advantage`` flag
    (``a`` / ``b`` / ``tie`` using a 0.5-point mean-score threshold).
    Also lists ``complementary_positions`` where one team is deep and
    the other is shallow — useful for identifying loan/exchange targets.

    This is a descriptive overlay — it does not predict match outcomes
    or recommend transfers.
    """
    if df.empty or not team_a or not team_b:
        return {
            "status": "no_data",
            "team_a": team_a,
            "team_b": team_b,
            "disclaimer": "Empty rating matrix or missing team name.",
        }

    work = df.copy()
    if "position_group" not in work.columns:
        if "sub_position" in work.columns:
            work["position_group"] = work["sub_position"]
        else:
            return {
                "status": "no_data",
                "team_a": team_a,
                "team_b": team_b,
                "disclaimer": "No position_group column in rating matrix.",
            }
    work = work[
        work["position_group"].astype(str).str.upper().isin(_POSITION_GROUPS)
    ]
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]
    if work.empty:
        return {
            "status": "no_data",
            "team_a": team_a,
            "team_b": team_b,
            "season": season,
            "disclaimer": "No rated players after filtering.",
        }

    team_a_work = work[work["team"].astype(str).str.lower() == str(team_a).strip().lower()]
    team_b_work = work[work["team"].astype(str).str.lower() == str(team_b).strip().lower()]

    if team_a_work.empty:
        return {
            "status": "team_a_not_found",
            "team_a": team_a,
            "team_b": team_b,
            "season": season,
            "disclaimer": f"Team '{team_a}' not found in the rating matrix.",
        }
    if team_b_work.empty:
        return {
            "status": "team_b_not_found",
            "team_a": team_a,
            "team_b": team_b,
            "season": season,
            "disclaimer": f"Team '{team_b}' not found in the rating matrix.",
        }

    league_a = _find_team_league(df, team_a)
    league_b = _find_team_league(df, team_b)

    depth_a = _team_position_depth(team_a_work, min_player_minutes=min_player_minutes)
    depth_b = _team_position_depth(team_b_work, min_player_minutes=min_player_minutes)

    position_comparison: list[dict[str, Any]] = []
    complementary: list[dict[str, Any]] = []
    all_positions = sorted(set(depth_a) | set(depth_b))

    for pos in _POSITION_GROUPS:
        if pos not in all_positions:
            continue
        a_stats = depth_a.get(pos)
        b_stats = depth_b.get(pos)
        a_mean = a_stats["score_mean"] if a_stats else None
        b_mean = b_stats["score_mean"] if b_stats else None

        if a_mean is not None and b_mean is not None:
            diff = a_mean - b_mean
            if diff > 0.5:
                advantage = "a"
            elif diff < -0.5:
                advantage = "b"
            else:
                advantage = "tie"
        elif a_mean is not None:
            advantage = "a"
        elif b_mean is not None:
            advantage = "b"
        else:
            advantage = "tie"

        entry: dict[str, Any] = {
            "position_group": pos,
            "team_a": {
                "n_players": a_stats["n_players"] if a_stats else 0,
                "mean_score": a_mean,
                "depth_label": a_stats["depth_label"] if a_stats else None,
            },
            "team_b": {
                "n_players": b_stats["n_players"] if b_stats else 0,
                "mean_score": b_mean,
                "depth_label": b_stats["depth_label"] if b_stats else None,
            },
            "advantage": advantage,
        }
        position_comparison.append(entry)

        a_deep = a_stats is not None and a_stats["depth_label"] == "deep"
        b_deep = b_stats is not None and b_stats["depth_label"] == "deep"
        a_shallow = a_stats is None or a_stats["depth_label"] == "shallow"
        b_shallow = b_stats is None or b_stats["depth_label"] == "shallow"
        if a_deep and b_shallow:
            complementary.append({
                "position_group": pos,
                "deep_team": "a",
                "shallow_team": "b",
                "reason": (
                    f"Team A is deep ({a_stats['n_players']} players, "
                    f"mean {a_mean}) while Team B is shallow."
                ),
            })
        elif b_deep and a_shallow:
            complementary.append({
                "position_group": pos,
                "deep_team": "b",
                "shallow_team": "a",
                "reason": (
                    f"Team B is deep ({b_stats['n_players']} players, "
                    f"mean {b_mean}) while Team A is shallow."
                ),
            })

    return {
        "status": "ok",
        "team_a": {
            "name": str(team_a_work["team"].iloc[0]),
            "league": league_a,
            "season": season,
        },
        "team_b": {
            "name": str(team_b_work["team"].iloc[0]),
            "league": league_b,
            "season": season,
        },
        "same_league": league_a == league_b,
        "position_comparison": position_comparison,
        "complementary_positions": complementary,
        "disclaimer": (
            "Cross-league team depth comparison is a descriptive overlay "
            "based on minutes-weighted rating-matrix aggregates. The "
            "advantage flag uses a 0.5-point mean-score threshold and does "
            "not predict match outcomes. Complementary positions identify "
            "where one team has depth and the other is shallow — this is "
            "not a transfer or loan recommendation."
        ),
    }


def _league_position_percentiles(
    league_df: pd.DataFrame,
    position_group: str,
    *,
    min_player_minutes: float,
) -> dict[str, float] | None:
    """Compute p25/p50/p60/p75/p90 for one position group in one league.

    ``p60`` is included so the scouting-targets flow can reuse the same
    threshold convention as :func:`compute_position_gap_report`.
    """
    sub = league_df[
        league_df["position_group"].astype(str).str.upper() == position_group
    ]
    if sub.empty:
        return None
    minutes = (
        sub["minutes"]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
        .to_numpy(dtype=float)
    )
    mask = minutes >= min_player_minutes
    if not mask.any():
        return None
    scores = (
        sub["optimized_score"]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
        .to_numpy(dtype=float)[mask]
    )
    return {
        "p25": round(float(np.percentile(scores, 25)), 2),
        "p50": round(float(np.percentile(scores, 50)), 2),
        "p60": round(float(np.percentile(scores, 60)), 2),
        "p75": round(float(np.percentile(scores, 75)), 2),
        "p90": round(float(np.percentile(scores, 90)), 2),
        "n_players": int(mask.sum()),
    }


def compute_scouting_targets(
    df: pd.DataFrame,
    team: str,
    *,
    season: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
    top_n: int = _DEFAULT_SCOUTING_TOP_N,
    exclude_same_league: bool = True,
) -> dict[str, Any]:
    """Find players from other leagues who could fill a team's position gaps.

    For each gap position (shallow / low_quality / missing) identified by
    :func:`compute_position_gap_report`, scans players in other leagues at
    that position group who meet all of:

    * ``minutes`` >= ``min_player_minutes``
    * ``optimized_score`` above the gap's target threshold (league p60 for
      shallow/missing gaps, or the team's current mean for low_quality gaps)
    * score in the top quartile (p75) of their own league at that position

    Returns up to ``top_n`` candidates per gap, sorted by score descending.
    This is a descriptive overlay — NOT a transfer recommendation.
    """
    if df.empty or not team:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": _SCOUTING_DISCLAIMER,
        }

    top_n = max(1, min(int(top_n), _MAX_SCOUTING_TOP_N))

    work = df.copy()
    if "position_group" not in work.columns:
        if "sub_position" in work.columns:
            work["position_group"] = work["sub_position"]
        else:
            return {
                "status": "no_data",
                "team": team,
                "disclaimer": _SCOUTING_DISCLAIMER,
            }
    work = work[
        work["position_group"].astype(str).str.upper().isin(_POSITION_GROUPS)
    ]
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]
    if work.empty:
        return {
            "status": "no_data",
            "team": team,
            "season": season,
            "disclaimer": _SCOUTING_DISCLAIMER,
        }

    # Reuse gap report to identify which positions need scouting.
    gap_report = compute_position_gap_report(
        df,
        team,
        season=season,
        min_player_minutes=min_player_minutes,
    )
    if gap_report["status"] != "ok":
        return {
            "status": gap_report["status"],
            "team": team,
            "season": season,
            "disclaimer": _SCOUTING_DISCLAIMER,
        }

    gaps = gap_report.get("gaps", [])
    if not gaps:
        return {
            "status": "ok",
            "team": team,
            "league": gap_report.get("league"),
            "season": season,
            "n_gaps": 0,
            "gap_targets": [],
            "disclaimer": _SCOUTING_DISCLAIMER,
        }

    team_league = gap_report.get("league")

    # Pre-compute per-league percentiles for each gap position.
    candidate_pool = work.copy()
    if exclude_same_league and team_league is not None:
        candidate_pool = candidate_pool[
            candidate_pool["league"].astype(str).str.lower()
            != str(team_league).lower()
        ]

    gap_targets: list[dict[str, Any]] = []
    for gap in gaps:
        pos = gap["position_group"]
        gap_type = gap["gap_type"]

        # Determine the score threshold for candidates.
        if gap_type == "low_quality":
            threshold = gap.get("mean_score", 0.0)
        elif gap_type == "shallow":
            # Use the team's league p60 if available, else 0.
            if team_league is not None:
                lp = _league_position_percentiles(
                    work[work["league"].astype(str).str.lower() == str(team_league).lower()],
                    pos,
                    min_player_minutes=min_player_minutes,
                )
                threshold = lp["p60"] if lp else 0.0
            else:
                threshold = 0.0
        else:  # missing
            threshold = 0.0

        pos_candidates = candidate_pool[
            candidate_pool["position_group"].astype(str).str.upper() == pos
        ].copy()
        if pos_candidates.empty:
            gap_targets.append({
                "position_group": pos,
                "gap_type": gap_type,
                "threshold": threshold,
                "n_candidates": 0,
                "candidates": [],
            })
            continue

        # Filter by minutes.
        pos_candidates["minutes_num"] = (
            pos_candidates["minutes"]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0.0)
        )
        pos_candidates = pos_candidates[pos_candidates["minutes_num"] >= min_player_minutes]
        if pos_candidates.empty:
            gap_targets.append({
                "position_group": pos,
                "gap_type": gap_type,
                "threshold": threshold,
                "n_candidates": 0,
                "candidates": [],
            })
            continue

        pos_candidates["score_num"] = (
            pos_candidates["optimized_score"]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0.0)
        )

        # Filter by score threshold.
        pos_candidates = pos_candidates[pos_candidates["score_num"] >= threshold]

        # Filter by top-quartile in the candidate's own league.
        keep: list[bool] = []
        for _, row in pos_candidates.iterrows():
            row_league = str(row.get("league", ""))
            lp = _league_position_percentiles(
                work[work["league"].astype(str).str.lower() == row_league.lower()],
                pos,
                min_player_minutes=min_player_minutes,
            )
            if lp is None:
                keep.append(False)
                continue
            keep.append(float(row["score_num"]) >= lp["p75"])
        pos_candidates = pos_candidates.iloc[[i for i, k in enumerate(keep) if k]]

        if pos_candidates.empty:
            gap_targets.append({
                "position_group": pos,
                "gap_type": gap_type,
                "threshold": threshold,
                "n_candidates": 0,
                "candidates": [],
            })
            continue

        # Sort by score descending and take top_n.
        pos_candidates = pos_candidates.sort_values("score_num", ascending=False).head(top_n)

        candidates: list[dict[str, Any]] = []
        for _, row in pos_candidates.iterrows():
            row_league = str(row.get("league", ""))
            lp = _league_position_percentiles(
                work[work["league"].astype(str).str.lower() == row_league.lower()],
                pos,
                min_player_minutes=min_player_minutes,
            )
            # Percentile rank within league.
            league_pos = work[
                (work["league"].astype(str).str.lower() == row_league.lower())
                & (work["position_group"].astype(str).str.upper() == pos)
            ]
            league_scores = (
                league_pos["optimized_score"]
                .apply(pd.to_numeric, errors="coerce")
                .fillna(0.0)
                .to_numpy(dtype=float)
            )
            league_minutes = (
                league_pos["minutes"]
                .apply(pd.to_numeric, errors="coerce")
                .fillna(0.0)
                .to_numpy(dtype=float)
            )
            mask = league_minutes >= min_player_minutes
            if mask.any():
                league_scores = league_scores[mask]
                pct = float(
                    (league_scores < float(row["score_num"])).sum()
                    / len(league_scores)
                    * 100
                )
            else:
                pct = 0.0

            candidates.append({
                "player_name": str(row.get("player_name", row.get("player", ""))),
                "team": str(row.get("team", "")),
                "league": row_league,
                "position_group": pos,
                "optimized_score": round(float(row["score_num"]), 2),
                "minutes": int(row["minutes_num"]),
                "percentile_in_league": round(pct, 1),
                "gap_reason": gap_type,
            })

        gap_targets.append({
            "position_group": pos,
            "gap_type": gap_type,
            "threshold": round(threshold, 2),
            "n_candidates": len(candidates),
            "candidates": candidates,
        })

    return {
        "status": "ok",
        "team": team,
        "league": team_league,
        "season": season,
        "exclude_same_league": exclude_same_league,
        "n_gaps": len(gaps),
        "gap_targets": gap_targets,
        "disclaimer": _SCOUTING_DISCLAIMER,
    }


def compute_scouting_target_style_match(
    df: pd.DataFrame,
    team: str,
    position_group: str,
    *,
    season: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
    top_n: int = _DEFAULT_SCOUTING_TOP_N,
    exclude_same_league: bool = True,
    use_position_weights: bool = False,
) -> dict[str, Any]:
    """Find players from other leagues with similar style to the team's top player.

    For the target team's highest-scored player at ``position_group``,
    computes a 4-dim style vector (npg_p90 / assists_p90 /
    defense_composite / possession_composite) and finds the most similar
    players in other leagues by cosine similarity.

    This bridges "find a backup who plays like your current starter but
    in another league". Returns top-N style-matched players with
    similarity score, league, team, score, minutes.

    Descriptive overlay — NOT a transfer recommendation.
    """
    pos_upper = str(position_group).upper()
    if pos_upper not in _POSITION_GROUPS:
        return {
            "status": "invalid_position",
            "team": team,
            "position_group": position_group,
            "disclaimer": _SCOUTING_DISCLAIMER,
        }

    if df.empty or not team:
        return {
            "status": "no_data",
            "team": team,
            "position_group": pos_upper,
            "disclaimer": _SCOUTING_DISCLAIMER,
        }

    top_n = max(1, min(int(top_n), _MAX_SCOUTING_TOP_N))

    # Resolve optional per-position weights. When use_position_weights=True,
    # look up the position's weight dict from _POSITION_STYLE_WEIGHTS and
    # build a 4-dim weight vector aligned with _STYLE_FEATURES. If the
    # position is missing from the table (defensive — should not happen
    # since pos_upper was validated above), fall back to None (equal
    # weights, identical to legacy behavior).
    weight_vec: np.ndarray | None = None
    weight_dict_out: dict[str, float] | None = None
    if use_position_weights:
        weight_dict = _POSITION_STYLE_WEIGHTS.get(pos_upper)
        if weight_dict is not None:
            weight_vec = np.array(
                [float(weight_dict.get(f, 1.0)) for f in _STYLE_FEATURES],
                dtype=float,
            )
            weight_dict_out = dict(weight_dict)

    work = df.copy()
    if "position_group" not in work.columns:
        if "sub_position" in work.columns:
            work["position_group"] = work["sub_position"]
        else:
            return {
                "status": "no_data",
                "team": team,
                "position_group": pos_upper,
                "disclaimer": _SCOUTING_DISCLAIMER,
            }
    work = work[
        work["position_group"].astype(str).str.upper().isin(_POSITION_GROUPS)
    ]
    if season is not None:
        work = work[work["season"].astype(str) == str(season)]
    if work.empty:
        return {
            "status": "no_data",
            "team": team,
            "position_group": pos_upper,
            "season": season,
            "disclaimer": _SCOUTING_DISCLAIMER,
        }

    # Find the target team's top player at the position.
    team_work = work[
        work["team"].astype(str).str.lower() == str(team).strip().lower()
    ]
    pos_work = team_work[
        team_work["position_group"].astype(str).str.upper() == pos_upper
    ]
    if pos_work.empty:
        return {
            "status": "team_position_not_found",
            "team": team,
            "position_group": pos_upper,
            "season": season,
            "disclaimer": (
                f"No players found for team '{team}' at position '{pos_upper}'."
            ),
        }

    pos_work = pos_work.copy()
    pos_work["minutes_num"] = (
        pos_work["minutes"].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    )
    pos_work["score_num"] = (
        pos_work["optimized_score"].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    )
    pos_work = pos_work[pos_work["minutes_num"] >= min_player_minutes]
    if pos_work.empty:
        return {
            "status": "team_position_not_found",
            "team": team,
            "position_group": pos_upper,
            "season": season,
            "disclaimer": (
                f"No qualifying players (>= {min_player_minutes} min) for "
                f"team '{team}' at position '{pos_upper}'."
            ),
        }

    top_row = pos_work.sort_values("score_num", ascending=False).iloc[0]
    target_name = str(top_row.get("player_name", top_row.get("player", "")))
    target_team = str(top_row.get("team", ""))
    team_league = str(top_row.get("league", ""))

    # Build target style vector.
    target_vec = np.array(
        [
            float(pd.to_numeric(top_row.get(f, 0.0), errors="coerce") or 0.0)
            for f in _STYLE_FEATURES
        ],
        dtype=float,
    )
    # Apply per-position weights to rotate the vector toward position-critical
    # dimensions. Cosine similarity is scale-invariant but not rotation-
    # invariant, so weighting changes which candidates surface as "similar".
    if weight_vec is not None:
        target_vec = target_vec * weight_vec
    target_norm = np.linalg.norm(target_vec)
    if target_norm == 0:
        return {
            "status": "no_data",
            "team": team,
            "position_group": pos_upper,
            "season": season,
            "disclaimer": "Target player has zero style vector.",
        }

    # Candidate pool: same position, other leagues (optionally), sufficient minutes.
    candidate_pool = work[
        work["position_group"].astype(str).str.upper() == pos_upper
    ].copy()
    if exclude_same_league and team_league:
        candidate_pool = candidate_pool[
            candidate_pool["league"].astype(str).str.lower()
            != team_league.lower()
        ]
    candidate_pool["minutes_num"] = (
        candidate_pool["minutes"].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    )
    candidate_pool["score_num"] = (
        candidate_pool["optimized_score"]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
    )
    candidate_pool = candidate_pool[
        candidate_pool["minutes_num"] >= min_player_minutes
    ]
    # Exclude the target player themselves.
    candidate_pool = candidate_pool[
        candidate_pool.apply(
            lambda r: str(r.get("player_name", r.get("player", ""))).lower()
            != target_name.lower(),
            axis=1,
        )
    ]

    if candidate_pool.empty:
        return {
            "status": "ok",
            "team": team,
            "position_group": pos_upper,
            "season": season,
            "target_player": {
                "name": target_name,
                "team": target_team,
                "league": team_league,
                "optimized_score": round(float(top_row["score_num"]), 2),
            },
            "n_candidates": 0,
            "candidates": [],
            "weighted": weight_vec is not None,
            "position_weights": weight_dict_out,
            "disclaimer": _SCOUTING_DISCLAIMER,
        }

    # Compute cosine similarity for each candidate.
    matches: list[dict[str, Any]] = []
    for _, row in candidate_pool.iterrows():
        cand_vec = np.array(
            [
                float(pd.to_numeric(row.get(f, 0.0), errors="coerce") or 0.0)
                for f in _STYLE_FEATURES
            ],
            dtype=float,
        )
        # Apply the same per-position weights used for the target vector so
        # both vectors are rotated into the same weighted space before cosine.
        if weight_vec is not None:
            cand_vec = cand_vec * weight_vec
        cand_norm = np.linalg.norm(cand_vec)
        if cand_norm == 0:
            continue
        sim = float(np.dot(target_vec, cand_vec) / (target_norm * cand_norm))
        matches.append({
            "player_name": str(row.get("player_name", row.get("player", ""))),
            "team": str(row.get("team", "")),
            "league": str(row.get("league", "")),
            "position_group": pos_upper,
            "optimized_score": round(float(row["score_num"]), 2),
            "minutes": int(row["minutes_num"]),
            "style_similarity": round(sim, 4),
        })

    matches.sort(key=lambda m: m["style_similarity"], reverse=True)
    matches = matches[:top_n]

    # Report the raw (unweighted) style vector for the target player so
    # consumers can render radar charts without inverting the weight mask.
    target_sv = {
        "npg_p90": round(
            float(pd.to_numeric(top_row.get("npg_p90", 0.0), errors="coerce") or 0.0),
            3,
        ),
        "assists_p90": round(
            float(pd.to_numeric(top_row.get("assists_p90", 0.0), errors="coerce") or 0.0),
            3,
        ),
        "defense_composite": round(
            float(
                pd.to_numeric(top_row.get("defense_composite", 0.0), errors="coerce")
                or 0.0
            ),
            2,
        ),
        "possession_composite": round(
            float(
                pd.to_numeric(
                    top_row.get("possession_composite", 0.0), errors="coerce"
                )
                or 0.0
            ),
            2,
        ),
    }

    return {
        "status": "ok",
        "team": team,
        "position_group": pos_upper,
        "season": season,
        "target_player": {
            "name": target_name,
            "team": target_team,
            "league": team_league,
            "optimized_score": round(float(top_row["score_num"]), 2),
            "style_vector": target_sv,
        },
        "n_candidates": len(matches),
        "candidates": matches,
        "weighted": weight_vec is not None,
        "position_weights": weight_dict_out,
        "disclaimer": _SCOUTING_DISCLAIMER,
    }


def compute_scouting_dashboard(
    df: pd.DataFrame,
    team: str,
    *,
    season: str | None = None,
    min_player_minutes: float = _MIN_PLAYER_MINUTES_DEFAULT,
    top_n: int = _DEFAULT_SCOUTING_TOP_N,
    exclude_same_league: bool = True,
    max_positions: int = 3,
    use_position_weights: bool = False,
) -> dict[str, Any]:
    """Aggregate scouting targets + multi-position style match in one call.

    For the target team, identifies position gaps (reusing
    :func:`compute_scouting_targets`) and computes a style-match candidate
    list for each of the top ``max_positions`` gap positions. Returns a
    unified report card combining gap context + per-position style
    candidates, suitable for a single-call dashboard view.

    The style match for each gap position answers "if we lose our current
    starter at the gap position, who plays like them in other leagues?".
    When ``use_position_weights`` is True, the per-position weights from
    ``_POSITION_STYLE_WEIGHTS`` are applied to both target and candidate
    style vectors before cosine similarity (see
    :func:`compute_scouting_target_style_match`).

    Descriptive overlay — NOT a transfer recommendation.
    """
    if df.empty or not team:
        return {
            "status": "no_data",
            "team": team,
            "disclaimer": _SCOUTING_DISCLAIMER,
        }

    # Clamp max_positions to 1-8 (the 8 canonical position groups).
    max_positions = max(
        1, min(int(max_positions), len(_POSITION_GROUPS))
    )
    top_n = max(1, min(int(top_n), _MAX_SCOUTING_TOP_N))

    # 1) Gap targets (reuses compute_position_gap_report internally).
    targets = compute_scouting_targets(
        df,
        team,
        season=season,
        min_player_minutes=min_player_minutes,
        top_n=top_n,
        exclude_same_league=exclude_same_league,
    )
    if targets["status"] != "ok":
        return {
            "status": targets["status"],
            "team": team,
            "season": season,
            "disclaimer": _SCOUTING_DISCLAIMER,
        }

    gap_targets = targets.get("gap_targets", [])
    n_gaps = len(gap_targets)

    # 2) For each of the top max_positions gap positions, compute a style
    # match against the team's current starter at that position. This
    # answers "if we lose our current starter at the gap position, who
    # plays like them in other leagues?".
    position_style_matches: list[dict[str, Any]] = []
    for gap in gap_targets[:max_positions]:
        pos = gap.get("position_group", "")
        if not pos or str(pos).upper() not in _POSITION_GROUPS:
            continue
        style_match = compute_scouting_target_style_match(
            df,
            team,
            pos,
            season=season,
            min_player_minutes=min_player_minutes,
            top_n=top_n,
            exclude_same_league=exclude_same_league,
            use_position_weights=use_position_weights,
        )
        position_style_matches.append(style_match)

    return {
        "status": "ok",
        "team": team,
        "league": targets.get("league"),
        "season": season,
        "n_gaps": n_gaps,
        "n_positions_matched": len(position_style_matches),
        "max_positions": max_positions,
        "use_position_weights": use_position_weights,
        "gap_targets": gap_targets,
        "position_style_matches": position_style_matches,
        "disclaimer": _SCOUTING_DISCLAIMER,
    }

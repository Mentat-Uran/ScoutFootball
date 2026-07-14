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

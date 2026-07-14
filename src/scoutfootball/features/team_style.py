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

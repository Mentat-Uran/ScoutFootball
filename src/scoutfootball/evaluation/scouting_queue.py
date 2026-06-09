"""Read-only scouting queue contracts derived from ratings artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

BIG5_LEAGUES = {
    "Premier League",
    "La Liga",
    "Bundesliga",
    "Serie A",
    "Ligue 1",
}
COARSE_SOURCE_POSITIONS = {"DF", "MF", "FW"}

SCOUTING_QUEUE_COLUMNS = [
    "player_id",
    "player_name",
    "team",
    "league",
    "season",
    "position_group",
    "optimized_score",
    "minutes",
    "confidence_level",
    "reason_code",
    "rating_snapshot_id",
    "review_status",
    "reviewer_note",
    "as_of_date",
]


@dataclass(frozen=True)
class ScoutingQueues:
    review_queue: pd.DataFrame
    watchlist: pd.DataFrame
    shortlist: pd.DataFrame


def build_scouting_queues(
    ratings_df: pd.DataFrame,
    *,
    run_id: str = "latest-local",
    reports_root: Path | None = None,
) -> ScoutingQueues:
    """Return review queue, watchlist and shortlist from ratings artifacts.

    If curated parquet artifacts already exist under *reports_root/scouting*,
    prefer those; otherwise derive a deterministic read-only queue from ratings.
    """
    if reports_root is not None:
        curated = _load_curated_queues(reports_root, run_id=run_id)
        if curated is not None:
            return curated

    if ratings_df.empty:
        empty = pd.DataFrame(columns=SCOUTING_QUEUE_COLUMNS)
        return ScoutingQueues(review_queue=empty, watchlist=empty, shortlist=empty)

    frame = ratings_df.copy()
    frame = _normalize_ratings_frame(frame)
    snapshot_date = str(date.today())

    review_rows = []
    watchlist_rows = []
    shortlist_rows = []

    for _, row in frame.iterrows():
        reasons = _reason_codes(row)
        base = _base_record(row, run_id=run_id, snapshot_date=snapshot_date)

        review_reasons = (
            "low_confidence",
            "low_appearance",
            "role_remap",
            "weak_coverage",
        )
        if any(reason in reasons for reason in review_reasons):
            review_rows.append(
                {
                    **base,
                    "reason_code": "|".join(reasons) if reasons else "manual_review",
                    "review_status": "pending",
                },
            )

        score = float(row.get("optimized_score", 0.0) or 0.0)
        minutes = float(row.get("minutes", 0.0) or 0.0)
        confidence = str(row.get("confidence_level", "LOW")).upper()
        league = str(row.get("league", ""))

        if score >= 88 and confidence == "HIGH" and minutes >= 900:
            shortlist_rows.append(
                {
                    **base,
                    "reason_code": "elite_high_confidence",
                    "review_status": "candidate",
                },
            )
        elif score >= 82 and (
            league not in BIG5_LEAGUES
            or confidence != "HIGH"
            or "value_candidate" in reasons
        ):
            reason = "value_candidate" if "value_candidate" in reasons else "watchlist_candidate"
            watchlist_rows.append(
                {
                    **base,
                    "reason_code": reason,
                    "review_status": "candidate",
                },
            )

    review_queue = _finalize_queue(review_rows)
    watchlist = _finalize_queue(watchlist_rows)
    shortlist = _finalize_queue(shortlist_rows)
    return ScoutingQueues(
        review_queue=review_queue,
        watchlist=watchlist,
        shortlist=shortlist,
    )


def _load_curated_queues(reports_root: Path, *, run_id: str) -> ScoutingQueues | None:
    scouting_dir = reports_root / "scouting"
    if not scouting_dir.exists():
        return None

    paths = {
        "review_queue": scouting_dir / "review_queue.parquet",
        "watchlist": scouting_dir / "watchlist.parquet",
        "shortlist": scouting_dir / "shortlist.parquet",
    }
    if not any(path.exists() for path in paths.values()):
        return None

    def _read(path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame(columns=SCOUTING_QUEUE_COLUMNS)
        frame = pd.read_parquet(path)
        for col in SCOUTING_QUEUE_COLUMNS:
            if col not in frame.columns:
                frame[col] = pd.NA
        if "rating_snapshot_id" not in frame.columns or frame["rating_snapshot_id"].isna().all():
            frame["rating_snapshot_id"] = run_id
        return frame[SCOUTING_QUEUE_COLUMNS].copy()

    return ScoutingQueues(
        review_queue=_read(paths["review_queue"]),
        watchlist=_read(paths["watchlist"]),
        shortlist=_read(paths["shortlist"]),
    )


def _normalize_ratings_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if "position_group" not in frame.columns and "sub_position" in frame.columns:
        frame["position_group"] = frame["sub_position"]
    if "confidence_level" not in frame.columns:
        minutes = pd.to_numeric(frame.get("minutes"), errors="coerce").fillna(0.0)
        frame["confidence_level"] = minutes.map(_minutes_to_confidence)
    else:
        frame["confidence_level"] = frame["confidence_level"].astype(str).str.upper()
    frame["optimized_score"] = pd.to_numeric(
        frame.get("optimized_score"),
        errors="coerce",
    ).fillna(0.0)
    frame["minutes"] = pd.to_numeric(frame.get("minutes"), errors="coerce").fillna(0.0)
    frame["player_id"] = frame.apply(
        lambda row: (
            f"{row.get('player', 'unknown')}|"
            f"{row.get('team', 'unknown')}|"
            f"{row.get('season', 'unknown')}"
        ),
        axis=1,
    )
    return frame


def _minutes_to_confidence(minutes: float) -> str:
    if minutes >= 900:
        return "HIGH"
    if minutes >= 450:
        return "MEDIUM"
    return "LOW"


def _reason_codes(row: pd.Series) -> list[str]:
    reasons: list[str] = []
    confidence = str(row.get("confidence_level", "LOW")).upper()
    minutes = float(row.get("minutes", 0.0) or 0.0)
    league = str(row.get("league", ""))
    source_position = str(row.get("source_position", ""))
    position_group = str(row.get("position_group", ""))

    if confidence == "LOW":
        reasons.append("low_confidence")
    if minutes < 450:
        reasons.append("low_appearance")
    if (
        source_position in COARSE_SOURCE_POSITIONS
        and position_group
        and source_position != position_group
        and confidence != "HIGH"
    ):
        reasons.append("role_remap")
    if (
        league
        and league not in BIG5_LEAGUES
        and float(row.get("optimized_score", 0.0) or 0.0) >= 84
    ):
        reasons.append("weak_coverage")
    if (
        float(row.get("optimized_score", 0.0) or 0.0) >= 84
        and confidence in {"HIGH", "MEDIUM"}
        and minutes >= 700
    ):
        reasons.append("value_candidate")
    return reasons


def _base_record(row: pd.Series, *, run_id: str, snapshot_date: str) -> dict[str, object]:
    return {
        "player_id": row.get("player_id", ""),
        "player_name": row.get("player", ""),
        "team": row.get("team", ""),
        "league": row.get("league", ""),
        "season": row.get("season", ""),
        "position_group": row.get("position_group", ""),
        "optimized_score": round(float(row.get("optimized_score", 0.0) or 0.0), 3),
        "minutes": round(float(row.get("minutes", 0.0) or 0.0)),
        "confidence_level": str(row.get("confidence_level", "LOW")).upper(),
        "rating_snapshot_id": run_id,
        "review_status": "pending",
        "reviewer_note": "",
        "as_of_date": snapshot_date,
    }


def _finalize_queue(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=SCOUTING_QUEUE_COLUMNS)
    frame = frame.sort_values(
        ["optimized_score", "minutes"],
        ascending=[False, False],
    ).drop_duplicates(subset=["player_id", "reason_code"])
    for col in SCOUTING_QUEUE_COLUMNS:
        if col not in frame.columns:
            frame[col] = pd.NA
    return frame[SCOUTING_QUEUE_COLUMNS].reset_index(drop=True)

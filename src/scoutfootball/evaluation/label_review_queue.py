"""PRS-LABEL-005 标签冲突、低信心与待复核队列诊断（PRS-3 切片 2）.

PRS-3 切片 1（``label_ledger``）落地了 append-only 标签账本与独立性
审计，但独立性审计只检查结构性不变量（不自比、window 合法、evidence
非空、model_derived 不在监督集合）。它不回答维护者最关心的下一个问题：
**当前 active 标签里哪些需要复核？**

本模块在 ``label_ledger`` 之上叠加一层只读诊断，识别三类需要维护者
注意的标签子集：

1. **冲突队列 (conflict_queue)**：同 cohort + role + season +
   observation_window 下，对同一比较对象存在矛盾判断。
   - ``human_pairwise_preference``：同球员对（双向标准化后）被不同
     记录偏好到不同方向（如 r1 偏好 A，r2 偏好 B；忽略 tie 与非 tie
     的冲突，因为 tie 是"无法判断"而非"矛盾判断"）。
   - ``human_tier``：同 ``canonical_player_id`` 的 tier 差异 >=
     ``tier_conflict_threshold``（默认 2 档，例如 1 vs 3）。
   冲突分组携带所有涉及的 ``decision_id``，便于维护者一次性看到矛盾
   全貌。

2. **低信心队列 (low_confidence_queue)**：``confidence=low`` 的 active
   标签，或 ``evidence`` 长度低于 ``evidence_min_chars``（默认 50）的
   标签。这些标签不一定是错的，但维护者应优先复核。

3. **待复测队列 (retest_queue)**：``recorded_at`` 距今超过
   ``max_age_days``（默认 180 天）的 active 标签。PRS-3 退出门槛要求
   "标签一致性和维护者复测稳定性有报告"——本队列标识"哪些标签已经
   老到值得重新评估"，但不自动作废它们。

设计契约（PRS-3 退出门槛"冲突、低信心和待复核队列"）：

- **只读**。本模块不修改 ``decisions.jsonl`` 或任何 parquet 产物。
  所有函数接受 ``records`` 列表（通常来自 ``read_ledger``）并返回
  诊断 dict。
- **基于 active 集合**。冲突和队列检测只在 ``active_labels`` 上进行；
  被撤销或被 supersede 的记录不参与。这避免"已撤销的旧判断"被误报
  为冲突。
- **双向标准化 pairwise**。``player_a_id`` / ``player_b_id`` 在账本
  中是有序的（A vs B 与 B vs A 是不同记录），但语义上是同一比较。
  本模块把 pair 标准化为 sorted tuple，并把 ``preferred_player`` 同
  步映射到"first/second/tie"（first = sorted pair 的第一个球员），
  这样 (A vs B, prefer a) 与 (B vs A, prefer b) 都映射为 (A, B,
  prefer first)，不会误报为冲突。
- **tie 不与偏好冲突**。``preferred_player=tie`` 表示"无法判断"，与
  任何明确偏好（a 或 b）不构成矛盾——它们是不同强度的判断，不是
  互相矛盾的判断。两个 tie 也不冲突。只有 (prefer a) vs (prefer b)
  才是真正的矛盾。
- **age 容错**。``recorded_at`` 解析失败时该记录跳过 retest 检测并
  记入 ``retest_skipped_count``，不报错——诊断不应因单条坏记录而
  失败。
- **status 语义**。``status=ok`` 表示三个队列都为空；
  ``status=review_needed`` 表示至少有一个队列非空。``ok`` 不证明
  标签正确，只表示没有自动可检测的冲突/低信心/老化信号。

本模块的输出是 PRS-3 verified 的退出门槛之一，也是 PRS-4 严谨评估
的输入：PRS-4 的 baseline 对照在存在冲突标签时应优先解决冲突而非
直接用冲突标签监督训练。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from scoutfootball.evaluation.label_ledger import active_labels

REVIEW_QUEUE_SCHEMA = "scoutfootball.label-review-queue"
REVIEW_QUEUE_SCHEMA_VERSION = "1.0.0"

# Default thresholds. Exposed as module constants so tests and CLI can
# reference them; callers may override via function parameters.
DEFAULT_TIER_CONFLICT_THRESHOLD = 2
DEFAULT_EVIDENCE_MIN_CHARS = 50
DEFAULT_MAX_AGE_DAYS = 180


def _parse_recorded_at(recorded_at: str) -> datetime | None:
    """Parse an ISO-8601 ``recorded_at`` string to an aware datetime.

    Returns ``None`` if the string cannot be parsed. The ledger writes
    timestamps as ``%Y-%m-%dT%H:%M:%SZ`` (see ``label_ledger._now``),
    but we accept any ISO-8601 string with offset to be defensive
    against hand-edited records.
    """
    if not recorded_at or not isinstance(recorded_at, str):
        return None
    s = recorded_at.strip()
    # Normalise the trailing Z (UTC indicator) to +00:00 for fromisoformat.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        # Treat naive timestamps as UTC for consistency with the ledger's
        # _now() helper, which always writes UTC.
        dt = dt.replace(tzinfo=UTC)
    return dt


def _normalise_pairwise_pair(
    player_a_id: str,
    player_b_id: str,
    preferred_player: str,
) -> tuple[tuple[str, str], str]:
    """Return (sorted_pair, normalised_preference).

    ``normalised_preference`` is always one of ``"first"``, ``"second"``,
    ``"tie"`` where ``first`` / ``second`` refer to the position in the
    sorted pair. This makes (A vs B, prefer a) and (B vs A, prefer b)
    both map to ((A, B), "first"), so they are recognised as the same
    judgment rather than a conflict.

    If the two player IDs are equal (which ``label_independence_audit``
    would already flag as a self-comparison violation), the pair is
    returned as-is and preference is normalised to ``"tie"`` — a
    self-comparison has no meaningful preference direction, and treating
    it as tie ensures it never participates in a false conflict.
    """
    if player_a_id == player_b_id:
        return (player_a_id, player_b_id), "tie"
    if player_a_id < player_b_id:
        # Original order matches sorted order: a=first, b=second.
        if preferred_player == "a":
            return (player_a_id, player_b_id), "first"
        if preferred_player == "b":
            return (player_a_id, player_b_id), "second"
        return (player_a_id, player_b_id), "tie"
    # Original order is reversed: original a = sorted second,
    # original b = sorted first.
    if preferred_player == "a":
        return (player_b_id, player_a_id), "second"
    if preferred_player == "b":
        return (player_b_id, player_a_id), "first"
    return (player_b_id, player_a_id), "tie"


def detect_pairwise_conflicts(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect conflicting pairwise preferences in the active label set.

    Groups active ``human_pairwise_preference`` records by
    (cohort_hash, role_family, season_id, observation_window, sorted_pair)
    and flags groups where two records express contradictory preferences
    (one prefers first, another prefers second). ``tie`` records do not
    conflict with anything.

    Returns a list of conflict group dicts, each containing:
    - ``cohort_hash``, ``role_family``, ``season_id``, ``observation_window``
    - ``player_pair``: the sorted [player_a_id, player_b_id] list
    - ``decision_ids``: list of decision_ids in the conflicting group
      (all records in the group, including any tie records, so the
      maintainer sees the full context)
    - ``preferences_seen``: sorted list of normalised preferences observed
      among non-tie records (e.g. ["first", "second"] for a true conflict)
    - ``conflict_type``: ``"pairwise_preference_contradiction"``
    """
    active = active_labels(records)
    pairwise = [
        r for r in active
        if r.get("label_type") == "human_pairwise_preference"
        and r.get("player_a_id")
        and r.get("player_b_id")
        and r.get("preferred_player")
    ]

    # Group key -> list of records
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for r in pairwise:
        pair, _ = _normalise_pairwise_pair(
            r["player_a_id"],
            r["player_b_id"],
            r["preferred_player"],
        )
        key = (
            r.get("cohort_hash", ""),
            r.get("role_family", ""),
            r.get("season_id", ""),
            r.get("observation_window", ""),
            pair,
        )
        groups[key].append(r)

    conflicts: list[dict[str, Any]] = []
    for key, group_records in groups.items():
        cohort_hash, role_family, season_id, observation_window, pair = key
        # Collect normalised preferences, ignoring tie records.
        non_tie_prefs: set[str] = set()
        for r in group_records:
            _, norm_pref = _normalise_pairwise_pair(
                r["player_a_id"],
                r["player_b_id"],
                r["preferred_player"],
            )
            if norm_pref in ("first", "second"):
                non_tie_prefs.add(norm_pref)

        # A conflict exists if both "first" and "second" are present.
        if len(non_tie_prefs) >= 2:
            conflicts.append({
                "cohort_hash": cohort_hash,
                "role_family": role_family,
                "season_id": season_id,
                "observation_window": observation_window,
                "player_pair": list(pair),
                "decision_ids": [r["decision_id"] for r in group_records],
                "preferences_seen": sorted(non_tie_prefs),
                "conflict_type": "pairwise_preference_contradiction",
            })

    return conflicts


def detect_tier_conflicts(
    records: list[dict[str, Any]],
    threshold: int = DEFAULT_TIER_CONFLICT_THRESHOLD,
) -> list[dict[str, Any]]:
    """Detect conflicting tier ratings in the active label set.

    Groups active ``human_tier`` records by (cohort_hash, role_family,
    season_id, observation_window, canonical_player_id) and flags groups
    where max(tier) - min(tier) >= threshold (default 2).

    Returns a list of conflict group dicts with ``decision_ids``,
    ``tier_values``, and ``tier_range``.
    """
    active = active_labels(records)
    tier = [
        r for r in active
        if r.get("label_type") == "human_tier"
        and r.get("canonical_player_id")
        and r.get("tier") is not None
    ]

    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for r in tier:
        key = (
            r.get("cohort_hash", ""),
            r.get("role_family", ""),
            r.get("season_id", ""),
            r.get("observation_window", ""),
            r.get("canonical_player_id", ""),
        )
        groups[key].append(r)

    conflicts: list[dict[str, Any]] = []
    for key, group_records in groups.items():
        cohort_hash, role_family, season_id, observation_window, player_id = key
        tier_values = [int(r["tier"]) for r in group_records]
        tier_min = min(tier_values)
        tier_max = max(tier_values)
        if tier_max - tier_min >= threshold:
            conflicts.append({
                "cohort_hash": cohort_hash,
                "role_family": role_family,
                "season_id": season_id,
                "observation_window": observation_window,
                "canonical_player_id": player_id,
                "decision_ids": [r["decision_id"] for r in group_records],
                "tier_values": tier_values,
                "tier_range": [tier_min, tier_max],
                "conflict_type": "tier_span_exceeds_threshold",
            })

    return conflicts


def low_confidence_queue(
    records: list[dict[str, Any]],
    evidence_min_chars: int = DEFAULT_EVIDENCE_MIN_CHARS,
) -> list[dict[str, Any]]:
    """Return active labels that are low-confidence or thinly evidenced.

    A label enters the queue if:
    - ``confidence == "low"``, OR
    - ``len(evidence) < evidence_min_chars`` (thin evidence may indicate
      a rushed judgment even if confidence was marked high).

    Each entry is a dict with ``decision_id``, ``reason`` (``"low_confidence"``
    or ``"thin_evidence"`` or both), ``confidence``, ``evidence_length``,
    and ``label_type``.
    """
    active = active_labels(records)
    queue: list[dict[str, Any]] = []
    for r in active:
        reasons: list[str] = []
        confidence = r.get("confidence", "")
        evidence = r.get("evidence", "") or ""
        evidence_len = len(evidence)
        if confidence == "low":
            reasons.append("low_confidence")
        if evidence_len < evidence_min_chars:
            reasons.append("thin_evidence")
        if reasons:
            queue.append({
                "decision_id": r["decision_id"],
                "reasons": reasons,
                "confidence": confidence,
                "evidence_length": evidence_len,
                "label_type": r.get("label_type", ""),
                "cohort_hash": r.get("cohort_hash", ""),
                "role_family": r.get("role_family", ""),
                "season_id": r.get("season_id", ""),
            })
    return queue


def retest_queue(
    records: list[dict[str, Any]],
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return active labels older than ``max_age_days`` for re-test.

    Returns ``(queue, skipped_count)``. ``skipped_count`` is the number
    of active records whose ``recorded_at`` could not be parsed; they are
    silently skipped rather than failing the diagnostic, but the count
    is surfaced so the maintainer knows data quality is imperfect.

    Each queue entry includes ``decision_id``, ``recorded_at``,
    ``age_days``, ``label_type``, ``cohort_hash``, ``role_family``,
    ``season_id``.
    """
    if now is None:
        now = datetime.now(UTC)
    active = active_labels(records)
    queue: list[dict[str, Any]] = []
    skipped = 0
    for r in active:
        recorded_at = r.get("recorded_at", "")
        dt = _parse_recorded_at(recorded_at)
        if dt is None:
            skipped += 1
            continue
        age_days = (now - dt).days
        if age_days >= max_age_days:
            queue.append({
                "decision_id": r["decision_id"],
                "recorded_at": recorded_at,
                "age_days": age_days,
                "label_type": r.get("label_type", ""),
                "cohort_hash": r.get("cohort_hash", ""),
                "role_family": r.get("role_family", ""),
                "season_id": r.get("season_id", ""),
            })
    # Sort oldest first (highest age_days) for reviewer priority.
    queue.sort(key=lambda x: x["age_days"], reverse=True)
    return queue, skipped


def build_review_queue(
    records: list[dict[str, Any]],
    *,
    tier_conflict_threshold: int = DEFAULT_TIER_CONFLICT_THRESHOLD,
    evidence_min_chars: int = DEFAULT_EVIDENCE_MIN_CHARS,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the full PRS-LABEL-005 review queue report.

    This is the main entry point. It runs all three detectors on the
    active label set and returns a single JSON-serialisable dict.

    The report schema is ``scoutfootball.label-review-queue`` v1.0.0.
    ``status`` is ``"ok"`` when all three queues are empty, otherwise
    ``"review_needed"``.

    The ``limitations`` list documents what the diagnostic does NOT
    prove: it does not check whether the evidence is correct, whether
    the annotator was truly blind, or whether the labels generalise
    across cohorts. It only surfaces structural signals that warrant
    human re-review.
    """
    pairwise_conflicts = detect_pairwise_conflicts(records)
    tier_conflicts = detect_tier_conflicts(
        records, threshold=tier_conflict_threshold
    )
    low_conf = low_confidence_queue(
        records, evidence_min_chars=evidence_min_chars
    )
    retest, retest_skipped = retest_queue(
        records, max_age_days=max_age_days, now=now
    )

    total_conflicts = len(pairwise_conflicts) + len(tier_conflicts)
    total_queue = total_conflicts + len(low_conf) + len(retest)
    status = "ok" if total_queue == 0 else "review_needed"

    # Aggregate conflict decision_ids for quick lookup.
    conflict_decision_ids: set[str] = set()
    for g in pairwise_conflicts:
        conflict_decision_ids.update(g["decision_ids"])
    for g in tier_conflicts:
        conflict_decision_ids.update(g["decision_ids"])

    return {
        "schema": REVIEW_QUEUE_SCHEMA,
        "schema_version": REVIEW_QUEUE_SCHEMA_VERSION,
        "status": status,
        "parameters": {
            "tier_conflict_threshold": tier_conflict_threshold,
            "evidence_min_chars": evidence_min_chars,
            "max_age_days": max_age_days,
        },
        "summary": {
            "active_label_count": len(active_labels(records)),
            "total_review_items": total_queue,
            "pairwise_conflict_groups": len(pairwise_conflicts),
            "tier_conflict_groups": len(tier_conflicts),
            "low_confidence_items": len(low_conf),
            "retest_items": len(retest),
            "retest_skipped_count": retest_skipped,
            "conflict_decision_ids_count": len(conflict_decision_ids),
        },
        "conflict_queue": {
            "pairwise": pairwise_conflicts,
            "tier": tier_conflicts,
        },
        "low_confidence_queue": low_conf,
        "retest_queue": retest,
        "limitations": [
            "本诊断只检查结构性冲突/低信心/老化信号，不证明 evidence "
            "正确、评价者真正盲标或标签能跨 cohort 泛化。status=ok 只"
            "表示没有自动可检测的复核信号，不证明标签集可用于监督训练。",
            "pairwise 冲突检测把 (A vs B) 与 (B vs A) 标准化为同一比较"
            "（sorted pair + normalised preference），避免方向差异被误"
            "报为冲突。tie 不与任何明确偏好冲突——tie 是'无法判断'而非"
            "'矛盾判断'。",
            "tier 冲突默认阈值为 2 档（如 1 vs 3）；可通过 "
            "--tier-conflict-threshold 调整。冲突组携带所有涉及的 "
            "decision_id，便于维护者一次性看到矛盾全貌。",
            "低信心队列包含 confidence=low 或 evidence 长度 < "
            f"{evidence_min_chars} 字符的标签。薄 evidence 可能表示判断"
            "仓促，即使 confidence 标为 high。",
            f"待复测队列包含 recorded_at 距今 >= {max_age_days} 天的 "
            "active 标签。老化标签不被自动作废，仅标记为值得重新评估。"
            "recorded_at 解析失败的记录跳过 retest 检测并计入 "
            "retest_skipped_count，不报错。",
            "read-only 诊断；不修改 decisions.jsonl 或任何 parquet 产物。",
        ],
    }

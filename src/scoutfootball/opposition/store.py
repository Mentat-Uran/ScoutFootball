"""Local JSON store for source-limited match briefings.

Mirrors the atomic-write + backup + optimistic-concurrency pattern from
:mod:`scoutfootball.recruitment.store` so the opposition pack does not
re-implement safe local persistence.  Briefings are stored as individual
JSON records under ``<report_root>/opposition/briefings/``.

The store is local-only.  There is no cloud sync, no multi-tenant
isolation and no account system.  Concurrent writes from the same
machine are guarded by a process-level lock and ``If-Match`` style
``expected_revision`` checks.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scoutfootball.opposition.briefing import (
    BriefingValidationError,
    OppositionBriefing,
    validate_briefing_id,
    validate_briefing_payload,
)

BRIEFING_RECORD_SCHEMA = "scoutfootball.opposition-briefing-record"
BRIEFING_RECORD_VERSION = "1.0.0"
MAX_BRIEFING_RECORD_BYTES = 400_000  # 400 KB; includes record envelope

_STORE_LOCK = threading.Lock()


class BriefingStoreError(ValueError):
    """Raised by :class:`BriefingStore` for storage-level failures.

    ``code`` is a stable string for programmatic handling; ``http_status``
    is a hint for API layers that map store errors to HTTP responses.
    """

    def __init__(self, code: str, *, http_status: int = 500, metadata: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.metadata = metadata or {}


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


class BriefingStore:
    """JSON record store for local source-limited match briefings.

    Each briefing is persisted as a record envelope::

        {
          "schema": "scoutfootball.opposition-briefing-record",
          "version": "1.0.0",
          "server_revision": 1,
          "stored_at": "2026-07-23T10:00:00+00:00",
          "briefing": { ... OppositionBriefing payload ... }
        }

    The envelope is what's on disk; the ``briefing`` field is the
    validated :class:`OppositionBriefing` payload.  Consumers that read
    a record get the envelope; consumers that want just the briefing
    use ``record["briefing"]``.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.backup_root = self.root / "backups"

    def _path(self, briefing_id: str) -> Path:
        return self.root / f"{validate_briefing_id(briefing_id)}.json"

    def _read_record(self, path: Path) -> dict[str, Any]:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BriefingStoreError("briefing_record_invalid", http_status=500) from exc
        if (
            not isinstance(record, dict)
            or record.get("schema") != BRIEFING_RECORD_SCHEMA
            or record.get("version") != BRIEFING_RECORD_VERSION
            or not isinstance(record.get("server_revision"), int)
        ):
            raise BriefingStoreError("briefing_record_invalid", http_status=500)
        # Re-validate the embedded briefing so corrupted payloads are caught at read.
        try:
            validate_briefing_payload(record.get("briefing"))
        except BriefingValidationError as exc:
            raise BriefingStoreError("briefing_record_invalid", http_status=500) from exc
        # The on-disk briefing_id must match the filename.
        briefing = record.get("briefing", {})
        if not isinstance(briefing, dict) or briefing.get("briefing_id") != path.stem:
            raise BriefingStoreError("briefing_record_invalid", http_status=500)
        return record

    def load(self, briefing_id: str) -> dict[str, Any]:
        """Load one briefing record by id.

        Returns the full record envelope; access ``record["briefing"]``
        for the validated briefing payload.
        """
        path = self._path(briefing_id)
        if not path.exists():
            raise BriefingStoreError("briefing_not_found", http_status=404)
        with _STORE_LOCK:
            return self._read_record(path)

    def list_records(self, limit: int = 100) -> list[dict[str, Any]]:
        """List briefing records, most recently stored first.

        Returns a summary list (no full briefing payload) to keep the
        response small.  Each entry has: ``briefing_id``,
        ``server_revision``, ``briefing_revision``, ``title``,
        ``home_team``, ``away_team``, ``kickoff_at``, ``competition``,
        ``updated_at``, ``stored_at``.
        """
        if not self.root.exists():
            return []
        records: list[dict[str, Any]] = []
        with _STORE_LOCK:
            for path in self.root.glob("*.json"):
                try:
                    record = self._read_record(path)
                except BriefingStoreError:
                    continue
                briefing = record["briefing"]
                records.append({
                    "briefing_id": briefing["briefing_id"],
                    "server_revision": record["server_revision"],
                    "briefing_revision": briefing["revision"],
                    "title": briefing.get("title", ""),
                    "home_team": briefing.get("home_team", ""),
                    "away_team": briefing.get("away_team", ""),
                    "kickoff_at": briefing.get("kickoff_at"),
                    "competition": briefing.get("competition", ""),
                    "updated_at": briefing.get("updated_at", ""),
                    "stored_at": record["stored_at"],
                })
        records.sort(key=lambda item: item["stored_at"], reverse=True)
        return records[: max(1, min(int(limit), 100))]

    def save(
        self,
        briefing_id: str,
        payload: object,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Save a briefing, creating or updating the record atomically.

        Parameters
        ----------
        briefing_id:
            The briefing identifier (validated as filename-safe).
        payload:
            The briefing payload (dict or :class:`OppositionBriefing`).
        expected_revision:
            For updates, the ``server_revision`` the caller last saw.
            Required when the record already exists (``If-Match`` style);
            rejected with ``briefing_revision_conflict`` if stale.  For
            new records, pass ``None`` or ``0``.

        Returns the saved record envelope.
        """
        briefing_id = validate_briefing_id(briefing_id)
        if isinstance(payload, OppositionBriefing):
            if payload.briefing_id != briefing_id:
                raise BriefingStoreError(
                    "briefing_id_mismatch",
                    http_status=400,
                    metadata={
                        "payload_briefing_id": payload.briefing_id,
                        "path_briefing_id": briefing_id,
                    },
                )
            briefing_dict = payload.to_storage_payload()
        else:
            briefing = validate_briefing_payload(payload)
            if briefing.briefing_id != briefing_id:
                raise BriefingStoreError(
                    "briefing_id_mismatch",
                    http_status=400,
                    metadata={
                        "payload_briefing_id": briefing.briefing_id,
                        "path_briefing_id": briefing_id,
                    },
                )
            briefing_dict = briefing.to_storage_payload()

        path = self._path(briefing_id)

        with _STORE_LOCK:
            current: dict[str, Any] | None = None
            if path.exists():
                current = self._read_record(path)
                current_revision = int(current["server_revision"])
                if expected_revision is None:
                    raise BriefingStoreError(
                        "briefing_precondition_required",
                        http_status=428,
                        metadata={"current_revision": current_revision},
                    )
                if expected_revision != current_revision:
                    raise BriefingStoreError(
                        "briefing_revision_conflict",
                        http_status=409,
                        metadata={"current_revision": current_revision},
                    )
                server_revision = current_revision + 1
            else:
                if expected_revision not in {None, 0}:
                    raise BriefingStoreError(
                        "briefing_revision_conflict",
                        http_status=409,
                        metadata={"current_revision": 0},
                    )
                server_revision = 1

            stored_at = _utc_now_iso()
            record = {
                "schema": BRIEFING_RECORD_SCHEMA,
                "version": BRIEFING_RECORD_VERSION,
                "server_revision": server_revision,
                "stored_at": stored_at,
                "briefing": briefing_dict,
            }

            self.root.mkdir(parents=True, exist_ok=True)
            if current is not None:
                self.backup_root.mkdir(parents=True, exist_ok=True)
                backup_path = self.backup_root / (
                    f"{briefing_id}.rev-{current['server_revision']}.{uuid.uuid4().hex}.json"
                )
                shutil.copy2(path, backup_path)

            temp_path = self.root / f".{briefing_id}.{uuid.uuid4().hex}.tmp"
            try:
                with temp_path.open("x", encoding="utf-8", newline="\n") as handle:
                    json.dump(record, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                temp_path.replace(path)
            finally:
                temp_path.unlink(missing_ok=True)
            return record

    def delete(self, briefing_id: str, *, expected_revision: int | None = None) -> dict[str, Any]:
        """Delete a briefing record, keeping a backup.

        The record file is moved to
        ``backups/<briefing_id>.deleted-<uuid>.json`` so the deletion is
        reversible from local backups.  Returns a summary of the deleted
        record.
        """
        briefing_id = validate_briefing_id(briefing_id)
        path = self._path(briefing_id)

        with _STORE_LOCK:
            if not path.exists():
                raise BriefingStoreError("briefing_not_found", http_status=404)
            current = self._read_record(path)
            current_revision = int(current["server_revision"])
            if expected_revision is None:
                raise BriefingStoreError(
                    "briefing_precondition_required",
                    http_status=428,
                    metadata={"current_revision": current_revision},
                )
            if expected_revision != current_revision:
                raise BriefingStoreError(
                    "briefing_revision_conflict",
                    http_status=409,
                    metadata={"current_revision": current_revision},
                )

            self.backup_root.mkdir(parents=True, exist_ok=True)
            backup_path = self.backup_root / (
                f"{briefing_id}.deleted-{uuid.uuid4().hex}.json"
            )
            shutil.copy2(path, backup_path)
            path.unlink()
            return {
                "briefing_id": briefing_id,
                "server_revision": current_revision,
                "deleted_at": _utc_now_iso(),
                "backup_path": str(backup_path.relative_to(self.root)),
            }

    def count(self) -> int:
        """Return the number of stored briefing records."""
        if not self.root.exists():
            return 0
        with _STORE_LOCK:
            return sum(1 for _ in self.root.glob("*.json"))


__all__ = [
    "BRIEFING_RECORD_SCHEMA",
    "BRIEFING_RECORD_VERSION",
    "MAX_BRIEFING_RECORD_BYTES",
    "BriefingStore",
    "BriefingStoreError",
]

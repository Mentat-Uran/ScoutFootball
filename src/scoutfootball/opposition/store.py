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

    def _read_record(
        self, path: Path, *, expected_id: str | None = None,
    ) -> dict[str, Any]:
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
        # The on-disk briefing_id must match the filename (or the explicitly
        # provided expected_id, used when reading backup files whose
        # filename includes the revision suffix).
        briefing = record.get("briefing", {})
        reference_id = expected_id if expected_id is not None else path.stem
        if not isinstance(briefing, dict) or briefing.get("briefing_id") != reference_id:
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
        ``sections``, ``updated_at``, ``stored_at``.

        ``sections`` is a minimal projection ``[{section_id, fact_tier},
        ...]`` — enough for workflow inference to detect unclassified
        briefings (all ``fact_tier == "unknown"`` or empty sections)
        without fetching each record in full.  Section ``summary`` text
        and ``evidence_refs`` are not included; callers that need them
        must ``load(briefing_id)``.
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
                sections_proj = [
                    {
                        "section_id": s.get("section_id", ""),
                        "fact_tier": s.get("fact_tier", "unknown"),
                    }
                    for s in briefing.get("sections", [])
                    if isinstance(s, dict)
                ]
                records.append({
                    "briefing_id": briefing["briefing_id"],
                    "server_revision": record["server_revision"],
                    "briefing_revision": briefing["revision"],
                    "title": briefing.get("title", ""),
                    "home_team": briefing.get("home_team", ""),
                    "away_team": briefing.get("away_team", ""),
                    "kickoff_at": briefing.get("kickoff_at"),
                    "competition": briefing.get("competition", ""),
                    "sections": sections_proj,
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

    # ── Backup listing, diff and restore ──────────────────────────────

    _BACKUP_REV_PREFIX = "rev-"
    _BACKUP_DELETED_PREFIX = "deleted-"

    def _is_rev_backup(self, name: str, briefing_id: str) -> bool:
        return name.startswith(f"{briefing_id}.{self._BACKUP_REV_PREFIX}")

    def _parse_rev_backup(self, name: str, briefing_id: str) -> dict[str, Any] | None:
        """Parse ``<briefing_id>.rev-<N>.<uuid>.json`` into a summary dict."""
        if not self._is_rev_backup(name, briefing_id):
            return None
        tail = name[len(f"{briefing_id}.{self._BACKUP_REV_PREFIX}"):]
        if not tail.endswith(".json"):
            return None
        core = tail[:-len(".json")]
        if "." not in core:
            return None
        rev_str, _uuid = core.split(".", 1)
        try:
            revision = int(rev_str)
        except ValueError:
            return None
        return {
            "briefing_id": briefing_id,
            "backup_filename": name,
            "kind": "revision",
            "revision": revision,
        }

    def list_backups(self, briefing_id: str) -> list[dict[str, Any]]:
        """List on-disk backups for a briefing, newest revision first.

        Mirrors :meth:`scoutfootball.recruitment.store.BriefStore.list_backups`.
        Each entry carries ``briefing_id``, ``backup_filename``, ``kind``
        (``revision`` or ``deletion``), ``revision`` (for revision
        backups), ``stored_at`` (mtime in ISO format) and ``size_bytes``.
        """
        briefing_id = validate_briefing_id(briefing_id)
        if not self.backup_root.exists():
            return []
        backups: list[dict[str, Any]] = []
        with _STORE_LOCK:
            for path in self.backup_root.glob(f"{briefing_id}.*.json"):
                name = path.name
                parsed = self._parse_rev_backup(name, briefing_id)
                if parsed is not None:
                    stat = path.stat()
                    parsed["stored_at"] = datetime.fromtimestamp(
                        stat.st_mtime, tz=UTC,
                    ).isoformat()
                    parsed["size_bytes"] = stat.st_size
                    backups.append(parsed)
                    continue
                if name.startswith(f"{briefing_id}.{self._BACKUP_DELETED_PREFIX}"):
                    stat = path.stat()
                    backups.append({
                        "briefing_id": briefing_id,
                        "backup_filename": name,
                        "kind": "deletion",
                        "revision": None,
                        "stored_at": datetime.fromtimestamp(
                            stat.st_mtime, tz=UTC,
                        ).isoformat(),
                        "size_bytes": stat.st_size,
                    })
        backups.sort(key=lambda b: (b["kind"] != "revision", -(b.get("revision") or 0)))
        return backups

    def load_backup(self, briefing_id: str, backup_filename: str) -> dict[str, Any]:
        """Load a backup record by filename.

        ``backup_filename`` must be the basename returned by
        :meth:`list_backups`; path traversal is rejected.  The returned
        value is the full record envelope that was on disk at backup
        time, re-validated so corrupted backups are caught early.
        """
        briefing_id = validate_briefing_id(briefing_id)
        if not backup_filename or "/" in backup_filename or "\\" in backup_filename:
            raise BriefingStoreError("backup_filename_invalid", http_status=400)
        if not backup_filename.endswith(".json"):
            raise BriefingStoreError("backup_filename_invalid", http_status=400)
        if not (
            self._is_rev_backup(backup_filename, briefing_id)
            or backup_filename.startswith(
                f"{briefing_id}.{self._BACKUP_DELETED_PREFIX}"
            )
        ):
            raise BriefingStoreError("backup_filename_invalid", http_status=400)

        path = self.backup_root / backup_filename
        if not path.exists():
            raise BriefingStoreError("backup_not_found", http_status=404)
        with _STORE_LOCK:
            return self._read_record(path, expected_id=briefing_id)

    def restore_from_backup(
        self,
        briefing_id: str,
        backup_filename: str,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Restore a briefing from a backup, creating a new revision.

        The backup's payload is written back as a new server_revision on
        top of the current record (or as revision 1 if the current
        record is missing).  The backup itself is left in place so the
        restore is itself reversible.  ``expected_revision`` follows the
        same ``If-Match`` semantics as :meth:`save`.
        """
        backup_record = self.load_backup(briefing_id, backup_filename)
        # ``briefing`` is the payload key for opposition records.
        payload = backup_record.get("briefing")
        if not isinstance(payload, dict):
            raise BriefingStoreError("backup_record_invalid", http_status=500)
        return self.save(briefing_id, payload, expected_revision=expected_revision)


__all__ = [
    "BRIEFING_RECORD_SCHEMA",
    "BRIEFING_RECORD_VERSION",
    "MAX_BRIEFING_RECORD_BYTES",
    "BriefingStore",
    "BriefingStoreError",
]

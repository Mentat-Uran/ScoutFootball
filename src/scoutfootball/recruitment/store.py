"""Local JSON store for recruitment briefs.

Mirrors the atomic-write + backup + optimistic-concurrency pattern from
:mod:`scoutfootball.storage.scouting_workspace` so the recruitment pack
does not re-implement safe local persistence.  Briefs are stored as
individual JSON records under ``<report_root>/recruitment/briefs/``.

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

from scoutfootball.recruitment.brief import (
    BriefValidationError,
    RecruitmentBrief,
    validate_brief_id,
    validate_brief_payload,
)

BRIEF_RECORD_SCHEMA = "scoutfootball.recruitment-brief-record"
BRIEF_RECORD_VERSION = "1.0.0"
MAX_BRIEF_RECORD_BYTES = 200_000  # 200 KB; includes record envelope

_STORE_LOCK = threading.Lock()


class BriefStoreError(ValueError):
    """Raised by :class:`BriefStore` for storage-level failures.

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


class BriefStore:
    """JSON record store for local recruitment briefs.

    Each brief is persisted as a record envelope:

        {
          "schema": "scoutfootball.recruitment-brief-record",
          "version": "1.0.0",
          "server_revision": 1,
          "stored_at": "2026-07-23T10:00:00+00:00",
          "brief": { ... RecruitmentBrief payload ... }
        }

    The envelope is what's on disk; the ``brief`` field is the
    validated :class:`RecruitmentBrief` payload.  Consumers that read a
    record get the envelope; consumers that want just the brief use
    ``record["brief"]``.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.backup_root = self.root / "backups"

    def _path(self, brief_id: str) -> Path:
        return self.root / f"{validate_brief_id(brief_id)}.json"

    def _read_record(
        self, path: Path, *, expected_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BriefStoreError("brief_record_invalid", http_status=500) from exc
        if (
            not isinstance(record, dict)
            or record.get("schema") != BRIEF_RECORD_SCHEMA
            or record.get("version") != BRIEF_RECORD_VERSION
            or not isinstance(record.get("server_revision"), int)
        ):
            raise BriefStoreError("brief_record_invalid", http_status=500)
        # Re-validate the embedded brief so corrupted payloads are caught at read.
        try:
            validate_brief_payload(record.get("brief"))
        except BriefValidationError as exc:
            raise BriefStoreError("brief_record_invalid", http_status=500) from exc
        # The on-disk brief_id must match the filename (or the explicitly
        # provided expected_id, used when reading backup files whose
        # filename includes the revision suffix).
        brief = record.get("brief", {})
        reference_id = expected_id if expected_id is not None else path.stem
        if not isinstance(brief, dict) or brief.get("brief_id") != reference_id:
            raise BriefStoreError("brief_record_invalid", http_status=500)
        return record

    def load(self, brief_id: str) -> dict[str, Any]:
        """Load one brief record by id.

        Returns the full record envelope; access ``record["brief"]`` for
        the validated brief payload.
        """
        path = self._path(brief_id)
        if not path.exists():
            raise BriefStoreError("brief_not_found", http_status=404)
        with _STORE_LOCK:
            return self._read_record(path)

    def list_records(self, limit: int = 100) -> list[dict[str, Any]]:
        """List brief records, most recently stored first.

        Returns a summary list (no full brief payload) to keep the
        response small.  Each entry has: ``brief_id``, ``server_revision``,
        ``brief_revision``, ``title``, ``team``, ``position_group``,
        ``budget_eur``, ``minimum_minutes``, ``updated_at``, ``stored_at``.

        ``budget_eur`` and ``minimum_minutes`` are included (as nullable
        ints, mirroring the model) so workflow inference can detect
        incomplete briefs without fetching each record in full.  They may
        be ``None`` when the maintainer left them unset.
        """
        if not self.root.exists():
            return []
        records: list[dict[str, Any]] = []
        with _STORE_LOCK:
            for path in self.root.glob("*.json"):
                try:
                    record = self._read_record(path)
                except BriefStoreError:
                    continue
                brief = record["brief"]
                records.append({
                    "brief_id": brief["brief_id"],
                    "server_revision": record["server_revision"],
                    "brief_revision": brief["revision"],
                    "title": brief.get("title", ""),
                    "team": brief.get("team", ""),
                    "position_group": brief.get("position_group", ""),
                    "budget_eur": brief.get("budget_eur"),
                    "minimum_minutes": brief.get("minimum_minutes"),
                    "updated_at": brief.get("updated_at", ""),
                    "stored_at": record["stored_at"],
                })
        records.sort(key=lambda item: item["stored_at"], reverse=True)
        return records[: max(1, min(int(limit), 100))]

    def save(
        self,
        brief_id: str,
        payload: object,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Save a brief, creating or updating the record atomically.

        Parameters
        ----------
        brief_id:
            The brief identifier (validated as filename-safe).
        payload:
            The brief payload (dict or :class:`RecruitmentBrief`).
        expected_revision:
            For updates, the ``server_revision`` the caller last saw.
            Required when the record already exists (``If-Match`` style);
            rejected with ``brief_revision_conflict`` if stale.  For new
            records, pass ``None`` or ``0``.

        Returns the saved record envelope.
        """
        brief_id = validate_brief_id(brief_id)
        if isinstance(payload, RecruitmentBrief):
            if payload.brief_id != brief_id:
                raise BriefStoreError(
                    "brief_id_mismatch",
                    http_status=400,
                    metadata={"payload_brief_id": payload.brief_id, "path_brief_id": brief_id},
                )
            brief_dict = payload.to_storage_payload()
        else:
            brief = validate_brief_payload(payload)
            if brief.brief_id != brief_id:
                raise BriefStoreError(
                    "brief_id_mismatch",
                    http_status=400,
                    metadata={"payload_brief_id": brief.brief_id, "path_brief_id": brief_id},
                )
            brief_dict = brief.to_storage_payload()

        path = self._path(brief_id)

        with _STORE_LOCK:
            current: dict[str, Any] | None = None
            if path.exists():
                current = self._read_record(path)
                current_revision = int(current["server_revision"])
                if expected_revision is None:
                    raise BriefStoreError(
                        "brief_precondition_required",
                        http_status=428,
                        metadata={"current_revision": current_revision},
                    )
                if expected_revision != current_revision:
                    raise BriefStoreError(
                        "brief_revision_conflict",
                        http_status=409,
                        metadata={"current_revision": current_revision},
                    )
                server_revision = current_revision + 1
            else:
                if expected_revision not in {None, 0}:
                    raise BriefStoreError(
                        "brief_revision_conflict",
                        http_status=409,
                        metadata={"current_revision": 0},
                    )
                server_revision = 1

            stored_at = _utc_now_iso()
            record = {
                "schema": BRIEF_RECORD_SCHEMA,
                "version": BRIEF_RECORD_VERSION,
                "server_revision": server_revision,
                "stored_at": stored_at,
                "brief": brief_dict,
            }

            self.root.mkdir(parents=True, exist_ok=True)
            if current is not None:
                self.backup_root.mkdir(parents=True, exist_ok=True)
                backup_path = self.backup_root / (
                    f"{brief_id}.rev-{current['server_revision']}.{uuid.uuid4().hex}.json"
                )
                shutil.copy2(path, backup_path)

            temp_path = self.root / f".{brief_id}.{uuid.uuid4().hex}.tmp"
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

    def delete(self, brief_id: str, *, expected_revision: int | None = None) -> dict[str, Any]:
        """Delete a brief record, keeping a backup.

        The record file is moved to ``backups/<brief_id>.deleted-<uuid>.json``
        so the deletion is reversible from local backups.  Returns a
        summary of the deleted record.
        """
        brief_id = validate_brief_id(brief_id)
        path = self._path(brief_id)

        with _STORE_LOCK:
            if not path.exists():
                raise BriefStoreError("brief_not_found", http_status=404)
            current = self._read_record(path)
            current_revision = int(current["server_revision"])
            if expected_revision is None:
                raise BriefStoreError(
                    "brief_precondition_required",
                    http_status=428,
                    metadata={"current_revision": current_revision},
                )
            if expected_revision != current_revision:
                raise BriefStoreError(
                    "brief_revision_conflict",
                    http_status=409,
                    metadata={"current_revision": current_revision},
                )

            self.backup_root.mkdir(parents=True, exist_ok=True)
            backup_path = self.backup_root / (
                f"{brief_id}.deleted-{uuid.uuid4().hex}.json"
            )
            shutil.copy2(path, backup_path)
            path.unlink()
            return {
                "brief_id": brief_id,
                "server_revision": current_revision,
                "deleted_at": _utc_now_iso(),
                "backup_path": str(backup_path.relative_to(self.root)),
            }

    def count(self) -> int:
        """Return the number of stored brief records."""
        if not self.root.exists():
            return 0
        with _STORE_LOCK:
            return sum(1 for _ in self.root.glob("*.json"))

    # ── Backup listing, diff and restore ──────────────────────────────

    _BACKUP_REV_PREFIX = "rev-"
    _BACKUP_DELETED_PREFIX = "deleted-"

    def _is_rev_backup(self, name: str, brief_id: str) -> bool:
        return name.startswith(f"{brief_id}.{self._BACKUP_REV_PREFIX}")

    def _parse_rev_backup(self, name: str, brief_id: str) -> dict[str, Any] | None:
        """Parse ``<brief_id>.rev-<N>.<uuid>.json`` into a summary dict."""
        if not self._is_rev_backup(name, brief_id):
            return None
        tail = name[len(f"{brief_id}.{self._BACKUP_REV_PREFIX}"):]
        if not tail.endswith(".json"):
            return None
        core = tail[:-len(".json")]
        # core = "<N>.<uuid>"
        if "." not in core:
            return None
        rev_str, _uuid = core.split(".", 1)
        try:
            revision = int(rev_str)
        except ValueError:
            return None
        return {
            "brief_id": brief_id,
            "backup_filename": name,
            "kind": "revision",
            "revision": revision,
        }

    def list_backups(self, brief_id: str) -> list[dict[str, Any]]:
        """List on-disk backups for a brief, newest revision first.

        Backups come in two kinds:

        * ``revision`` — a snapshot taken before an update, named
          ``<brief_id>.rev-<N>.<uuid>.json``.  ``revision`` is the
          server_revision that was about to be overwritten.
        * ``deletion`` — a snapshot taken before a delete, named
          ``<brief_id>.deleted-<uuid>.json``.

        Each entry carries ``backup_filename`` (basename only), ``kind``,
        ``revision`` (for revision backups), ``stored_at`` (the backup
        file's mtime in ISO format) and ``size_bytes``.  The list is
        sorted so the newest revision comes first, then deletions.
        """
        brief_id = validate_brief_id(brief_id)
        if not self.backup_root.exists():
            return []
        backups: list[dict[str, Any]] = []
        with _STORE_LOCK:
            for path in self.backup_root.glob(f"{brief_id}.*.json"):
                name = path.name
                parsed = self._parse_rev_backup(name, brief_id)
                if parsed is not None:
                    stat = path.stat()
                    parsed["stored_at"] = datetime.fromtimestamp(
                        stat.st_mtime, tz=UTC,
                    ).isoformat()
                    parsed["size_bytes"] = stat.st_size
                    backups.append(parsed)
                    continue
                if name.startswith(f"{brief_id}.{self._BACKUP_DELETED_PREFIX}"):
                    stat = path.stat()
                    backups.append({
                        "brief_id": brief_id,
                        "backup_filename": name,
                        "kind": "deletion",
                        "revision": None,
                        "stored_at": datetime.fromtimestamp(
                            stat.st_mtime, tz=UTC,
                        ).isoformat(),
                        "size_bytes": stat.st_size,
                    })
        # Newest revision first; deletions last (sorted by stored_at).
        backups.sort(key=lambda b: (b["kind"] != "revision", -(b.get("revision") or 0)))
        return backups

    def load_backup(self, brief_id: str, backup_filename: str) -> dict[str, Any]:
        """Load a backup record by filename.

        ``backup_filename`` must be the basename returned by
        :meth:`list_backups`; path traversal is rejected.  The returned
        value is the full record envelope that was on disk at backup
        time, re-validated so corrupted backups are caught early.
        """
        brief_id = validate_brief_id(brief_id)
        if not backup_filename or "/" in backup_filename or "\\" in backup_filename:
            raise BriefStoreError("backup_filename_invalid", http_status=400)
        if not backup_filename.endswith(".json"):
            raise BriefStoreError("backup_filename_invalid", http_status=400)
        # Filename must start with the brief_id and be a known kind.
        if not (
            self._is_rev_backup(backup_filename, brief_id)
            or backup_filename.startswith(
                f"{brief_id}.{self._BACKUP_DELETED_PREFIX}"
            )
        ):
            raise BriefStoreError("backup_filename_invalid", http_status=400)

        path = self.backup_root / backup_filename
        if not path.exists():
            raise BriefStoreError("backup_not_found", http_status=404)
        with _STORE_LOCK:
            return self._read_record(path, expected_id=brief_id)

    def restore_from_backup(
        self,
        brief_id: str,
        backup_filename: str,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Restore a brief from a backup, creating a new revision.

        The backup's payload is written back as a new server_revision on
        top of the current record (or as revision 1 if the current
        record is missing).  The backup itself is left in place so the
        restore is itself reversible.  ``expected_revision`` follows the
        same ``If-Match`` semantics as :meth:`save`.
        """
        backup_record = self.load_backup(brief_id, backup_filename)
        # ``brief`` is the payload key for recruitment records.
        payload = backup_record.get("brief")
        if not isinstance(payload, dict):
            raise BriefStoreError("backup_record_invalid", http_status=500)
        return self.save(brief_id, payload, expected_revision=expected_revision)


__all__ = [
    "BRIEF_RECORD_SCHEMA",
    "BRIEF_RECORD_VERSION",
    "MAX_BRIEF_RECORD_BYTES",
    "BriefStore",
    "BriefStoreError",
]

"""Local JSON store for post-match reviews.

Mirrors the atomic-write + backup + optimistic-concurrency pattern from
:mod:`scoutfootball.opposition.store` (BriefingStore) and
:mod:`scoutfootball.recruitment.dossier_store` (DossierStore) so the
review layer does not re-implement safe local persistence.  Reviews are
stored as individual JSON records under ``<report_root>/opposition/reviews/``.

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

from scoutfootball.opposition.post_match_review import (
    PostMatchReview,
    ReviewValidationError,
    validate_review_id,
    validate_review_payload,
)

REVIEW_RECORD_SCHEMA = "scoutfootball.opposition-post-match-review-record"
REVIEW_RECORD_VERSION = "1.0.0"
MAX_REVIEW_RECORD_BYTES = 400_000  # 400 KB; includes record envelope

_STORE_LOCK = threading.Lock()


class ReviewStoreError(ValueError):
    """Raised by :class:`ReviewStore` for storage-level failures.

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


class ReviewStore:
    """JSON record store for local post-match reviews.

    Each review is persisted as a record envelope::

        {
          "schema": "scoutfootball.opposition-post-match-review-record",
          "version": "1.0.0",
          "server_revision": 1,
          "stored_at": "2026-08-16T20:00:00+00:00",
          "review": { ... PostMatchReview payload ... }
        }

    The envelope is what's on disk; the ``review`` field is the
    validated :class:`PostMatchReview` payload.  Consumers that read a
    record get the envelope; consumers that want just the review use
    ``record["review"]``.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.backup_root = self.root / "backups"

    def _path(self, review_id: str) -> Path:
        return self.root / f"{validate_review_id(review_id)}.json"

    def _read_record(
        self, path: Path, *, expected_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReviewStoreError("review_record_invalid", http_status=500) from exc
        if (
            not isinstance(record, dict)
            or record.get("schema") != REVIEW_RECORD_SCHEMA
            or record.get("version") != REVIEW_RECORD_VERSION
            or not isinstance(record.get("server_revision"), int)
        ):
            raise ReviewStoreError("review_record_invalid", http_status=500)
        # Re-validate the embedded review so corrupted payloads are caught at read.
        try:
            validate_review_payload(record.get("review"))
        except ReviewValidationError as exc:
            raise ReviewStoreError("review_record_invalid", http_status=500) from exc
        # The on-disk review_id must match the filename (or the explicitly
        # provided expected_id, used when reading backup files whose
        # filename includes the revision suffix).
        review = record.get("review", {})
        reference_id = expected_id if expected_id is not None else path.stem
        if not isinstance(review, dict) or review.get("review_id") != reference_id:
            raise ReviewStoreError("review_record_invalid", http_status=500)
        return record

    def load(self, review_id: str) -> dict[str, Any]:
        """Load one review record by id.

        Returns the full record envelope; access ``record["review"]`` for
        the validated review payload.
        """
        path = self._path(review_id)
        if not path.exists():
            raise ReviewStoreError("review_not_found", http_status=404)
        with _STORE_LOCK:
            return self._read_record(path)

    def list_records(self, limit: int = 100) -> list[dict[str, Any]]:
        """List review records, most recently stored first.

        Returns a summary list (no full review payload) to keep the
        response small.  Each entry has: ``review_id``, ``server_revision``,
        ``review_revision``, ``title``, ``briefing_id``, ``match_id``,
        ``home_team``, ``away_team``, ``status``, ``decision``,
        ``updated_at``, ``stored_at``.
        """
        if not self.root.exists():
            return []
        records: list[dict[str, Any]] = []
        with _STORE_LOCK:
            for path in self.root.glob("*.json"):
                try:
                    record = self._read_record(path)
                except ReviewStoreError:
                    continue
                review = record["review"]
                records.append({
                    "review_id": review["review_id"],
                    "server_revision": record["server_revision"],
                    "review_revision": review["revision"],
                    "title": review.get("title", ""),
                    "briefing_id": review.get("briefing_id", ""),
                    "match_id": review.get("match_id", ""),
                    "home_team": review.get("home_team", ""),
                    "away_team": review.get("away_team", ""),
                    "status": review.get("status", ""),
                    "decision": review.get("decision"),
                    "updated_at": review.get("updated_at", ""),
                    "stored_at": record["stored_at"],
                })
        records.sort(key=lambda item: item["stored_at"], reverse=True)
        return records[: max(1, min(int(limit), 100))]

    def save(
        self,
        review_id: str,
        payload: object,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Save a review, creating or updating the record atomically.

        Parameters
        ----------
        review_id:
            The review identifier (validated as filename-safe).
        payload:
            The review payload (dict or :class:`PostMatchReview`).
        expected_revision:
            For updates, the ``server_revision`` the caller last saw.
            Required when the record already exists (``If-Match`` style);
            rejected with ``review_revision_conflict`` if stale.  For new
            records, pass ``None`` or ``0``.

        Returns the saved record envelope.
        """
        review_id = validate_review_id(review_id)
        if isinstance(payload, PostMatchReview):
            if payload.review_id != review_id:
                raise ReviewStoreError(
                    "review_id_mismatch",
                    http_status=400,
                    metadata={
                        "payload_review_id": payload.review_id,
                        "path_review_id": review_id,
                    },
                )
            review_dict = payload.to_storage_payload()
        else:
            review = validate_review_payload(payload)
            if review.review_id != review_id:
                raise ReviewStoreError(
                    "review_id_mismatch",
                    http_status=400,
                    metadata={
                        "payload_review_id": review.review_id,
                        "path_review_id": review_id,
                    },
                )
            review_dict = review.to_storage_payload()

        path = self._path(review_id)

        with _STORE_LOCK:
            current: dict[str, Any] | None = None
            if path.exists():
                current = self._read_record(path)
                current_revision = int(current["server_revision"])
                if expected_revision is None:
                    raise ReviewStoreError(
                        "review_precondition_required",
                        http_status=428,
                        metadata={"current_revision": current_revision},
                    )
                if expected_revision != current_revision:
                    raise ReviewStoreError(
                        "review_revision_conflict",
                        http_status=409,
                        metadata={"current_revision": current_revision},
                    )
                server_revision = current_revision + 1
            else:
                if expected_revision not in {None, 0}:
                    raise ReviewStoreError(
                        "review_revision_conflict",
                        http_status=409,
                        metadata={"current_revision": 0},
                    )
                server_revision = 1

            stored_at = _utc_now_iso()
            record = {
                "schema": REVIEW_RECORD_SCHEMA,
                "version": REVIEW_RECORD_VERSION,
                "server_revision": server_revision,
                "stored_at": stored_at,
                "review": review_dict,
            }

            self.root.mkdir(parents=True, exist_ok=True)
            if current is not None:
                self.backup_root.mkdir(parents=True, exist_ok=True)
                backup_path = self.backup_root / (
                    f"{review_id}.rev-{current['server_revision']}.{uuid.uuid4().hex}.json"
                )
                shutil.copy2(path, backup_path)

            temp_path = self.root / f".{review_id}.{uuid.uuid4().hex}.tmp"
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

    def delete(self, review_id: str, *, expected_revision: int | None = None) -> dict[str, Any]:
        """Delete a review record, keeping a backup.

        The record file is moved to ``backups/<review_id>.deleted-<uuid>.json``
        so the deletion is reversible from local backups.  Returns a
        summary of the deleted record.
        """
        review_id = validate_review_id(review_id)
        path = self._path(review_id)

        with _STORE_LOCK:
            if not path.exists():
                raise ReviewStoreError("review_not_found", http_status=404)
            current = self._read_record(path)
            current_revision = int(current["server_revision"])
            if expected_revision is None:
                raise ReviewStoreError(
                    "review_precondition_required",
                    http_status=428,
                    metadata={"current_revision": current_revision},
                )
            if expected_revision != current_revision:
                raise ReviewStoreError(
                    "review_revision_conflict",
                    http_status=409,
                    metadata={"current_revision": current_revision},
                )

            self.backup_root.mkdir(parents=True, exist_ok=True)
            backup_path = self.backup_root / (
                f"{review_id}.deleted-{uuid.uuid4().hex}.json"
            )
            shutil.copy2(path, backup_path)
            path.unlink()
            return {
                "review_id": review_id,
                "server_revision": current_revision,
                "deleted_at": _utc_now_iso(),
                "backup_path": str(backup_path.relative_to(self.root)),
            }

    def count(self) -> int:
        """Return the number of stored review records."""
        if not self.root.exists():
            return 0
        with _STORE_LOCK:
            return sum(1 for _ in self.root.glob("*.json"))

    # ── Backup listing, diff and restore ──────────────────────────────

    _BACKUP_REV_PREFIX = "rev-"
    _BACKUP_DELETED_PREFIX = "deleted-"

    def _is_rev_backup(self, name: str, review_id: str) -> bool:
        return name.startswith(f"{review_id}.{self._BACKUP_REV_PREFIX}")

    def _parse_rev_backup(self, name: str, review_id: str) -> dict[str, Any] | None:
        """Parse ``<review_id>.rev-<N>.<uuid>.json`` into a summary dict."""
        if not self._is_rev_backup(name, review_id):
            return None
        tail = name[len(f"{review_id}.{self._BACKUP_REV_PREFIX}"):]
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
            "review_id": review_id,
            "backup_filename": name,
            "kind": "revision",
            "revision": revision,
        }

    def list_backups(self, review_id: str) -> list[dict[str, Any]]:
        """List on-disk backups for a review, newest revision first.

        Backups come in two kinds:

        * ``revision`` — a snapshot taken before an update, named
          ``<review_id>.rev-<N>.<uuid>.json``.  ``revision`` is the
          server_revision that was about to be overwritten.
        * ``deletion`` — a snapshot taken before a delete, named
          ``<review_id>.deleted-<uuid>.json``.

        Each entry carries ``backup_filename`` (basename only), ``kind``,
        ``revision`` (for revision backups), ``stored_at`` (the backup
        file's mtime in ISO format) and ``size_bytes``.  The list is
        sorted so the newest revision comes first, then deletions.
        """
        review_id = validate_review_id(review_id)
        if not self.backup_root.exists():
            return []
        backups: list[dict[str, Any]] = []
        with _STORE_LOCK:
            for path in self.backup_root.glob(f"{review_id}.*.json"):
                name = path.name
                parsed = self._parse_rev_backup(name, review_id)
                if parsed is not None:
                    stat = path.stat()
                    parsed["stored_at"] = datetime.fromtimestamp(
                        stat.st_mtime, tz=UTC,
                    ).isoformat()
                    parsed["size_bytes"] = stat.st_size
                    backups.append(parsed)
                    continue
                if name.startswith(f"{review_id}.{self._BACKUP_DELETED_PREFIX}"):
                    stat = path.stat()
                    backups.append({
                        "review_id": review_id,
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

    def load_backup(self, review_id: str, backup_filename: str) -> dict[str, Any]:
        """Load a backup record by filename.

        ``backup_filename`` must be the basename returned by
        :meth:`list_backups`; path traversal is rejected.  The returned
        value is the full record envelope that was on disk at backup
        time, re-validated so corrupted backups are caught early.
        """
        review_id = validate_review_id(review_id)
        if not backup_filename or "/" in backup_filename or "\\" in backup_filename:
            raise ReviewStoreError("backup_filename_invalid", http_status=400)
        if not backup_filename.endswith(".json"):
            raise ReviewStoreError("backup_filename_invalid", http_status=400)
        # Filename must start with the review_id and be a known kind.
        if not (
            self._is_rev_backup(backup_filename, review_id)
            or backup_filename.startswith(
                f"{review_id}.{self._BACKUP_DELETED_PREFIX}"
            )
        ):
            raise ReviewStoreError("backup_filename_invalid", http_status=400)

        path = self.backup_root / backup_filename
        if not path.exists():
            raise ReviewStoreError("backup_not_found", http_status=404)
        with _STORE_LOCK:
            return self._read_record(path, expected_id=review_id)

    def restore_from_backup(
        self,
        review_id: str,
        backup_filename: str,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Restore a review from a backup, creating a new revision.

        The backup's payload is written back as a new server_revision on
        top of the current record (or as revision 1 if the current
        record is missing).  The backup itself is left in place so the
        restore is itself reversible.  ``expected_revision`` follows the
        same ``If-Match`` semantics as :meth:`save`.
        """
        backup_record = self.load_backup(review_id, backup_filename)
        # ``review`` is the payload key for opposition review records.
        payload = backup_record.get("review")
        if not isinstance(payload, dict):
            raise ReviewStoreError("backup_record_invalid", http_status=500)
        return self.save(review_id, payload, expected_revision=expected_revision)


__all__ = [
    "REVIEW_RECORD_SCHEMA",
    "REVIEW_RECORD_VERSION",
    "MAX_REVIEW_RECORD_BYTES",
    "ReviewStore",
    "ReviewStoreError",
]

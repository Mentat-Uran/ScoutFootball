"""Field-level diff utility for local record envelopes.

Both :class:`scoutfootball.recruitment.store.BriefStore` and
:class:`scoutfootball.opposition.store.BriefingStore` persist records as
envelopes of the shape::

    {
      "schema": "...",
      "version": "1.0.0",
      "server_revision": int,
      "stored_at": "iso8601",
      "<payload_key>": { ... user payload ... },
    }

This module diffs two envelopes at the payload level, walking dicts and
lists recursively.  The output is a sorted list of change entries that a
frontend can render directly.  The diff is pure data — no HTML, no
external state — so it is safe to expose via the API and easy to test.

Design notes
------------

* Envelope metadata (``schema``/``version``/``server_revision``/
  ``stored_at``) is reported as a single ``__envelope__`` pseudo-path so
  callers can show "revision 3 → 4" without leaking internals.
* The payload key (``brief`` vs ``briefing``) is detected automatically;
  only one payload key is expected per envelope.
* Lists are diffed by index, with an ``added``/``removed`` marker for
  length changes.  We do not attempt longest-common-subsequence matching
  because brief payloads are small and explicit index diffs are easier
  to audit.
* Values are compared by equality after JSON normalisation, so dict
  payloads with the same content but different key insertion order
  compare equal.  Note that Python's ``1 == True`` is ``True``; brief
  payloads do not mix int and bool fields, so this is not a problem in
  practice.
* The diff never raises on shape mismatch — it returns a single
  ``"shape_mismatch"`` entry instead.  Callers wishing to enforce shape
  should validate envelopes before diffing.
"""

from __future__ import annotations

from typing import Any

__all__ = ["diff_records", "DiffEntry"]


# Type alias for a single change entry.  Kept as a plain dict so it
# serialises to JSON without custom hooks.
DiffEntry = dict[str, Any]

# Envelope-level keys that are NOT part of the user payload.  When we
# encounter them at the root, we collapse them into one pseudo-entry.
_ENVELOPE_KEYS = {"schema", "version", "server_revision", "stored_at"}


def _normalise(value: Any) -> Any:
    """Return a canonical form of ``value`` for equality comparison.

    JSON round-trip normalises key ordering for dicts so two payloads
    with the same content but different insertion order compare equal.
    Non-JSON-serialisable values fall through unchanged.
    """
    try:
        import json

        return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError):
        return value


def _diff_value(path: str, old: Any, new: Any, out: list[DiffEntry]) -> None:
    if _normalise(old) == _normalise(new):
        return

    if isinstance(old, dict) and isinstance(new, dict):
        _diff_dict(path, old, new, out)
        return

    if isinstance(old, list) and isinstance(new, list):
        _diff_list(path, old, new, out)
        return

    out.append({
        "path": path,
        "change": "changed",
        "old": old,
        "new": new,
    })


def _diff_dict(path: str, old: dict, new: dict, out: list[DiffEntry]) -> None:
    prefix = f"{path}." if path else ""
    for key in sorted(set(old.keys()) | set(new.keys())):
        child_path = f"{prefix}{key}"
        if key not in old:
            out.append({
                "path": child_path,
                "change": "added",
                "old": None,
                "new": new[key],
            })
        elif key not in new:
            out.append({
                "path": child_path,
                "change": "removed",
                "old": old[key],
                "new": None,
            })
        else:
            _diff_value(child_path, old[key], new[key], out)


def _diff_list(path: str, old: list, new: list, out: list[DiffEntry]) -> None:
    max_len = max(len(old), len(new))
    for idx in range(max_len):
        child_path = f"{path}[{idx}]"
        if idx >= len(old):
            out.append({
                "path": child_path,
                "change": "added",
                "old": None,
                "new": new[idx],
            })
        elif idx >= len(new):
            out.append({
                "path": child_path,
                "change": "removed",
                "old": old[idx],
                "new": None,
            })
        else:
            _diff_value(child_path, old[idx], new[idx], out)


def _payload_key(record: dict) -> str | None:
    """Return the payload key for an envelope, or ``None`` if ambiguous."""
    candidates = [k for k in record.keys() if k not in _ENVELOPE_KEYS]
    if len(candidates) == 1:
        return candidates[0]
    return None


def diff_records(old: dict | None, new: dict | None) -> list[DiffEntry]:
    """Diff two record envelopes, returning a sorted list of changes.

    Each entry has the shape::

        {"path": "brief.title", "change": "changed", "old": "...", "new": "..."}

    ``change`` is one of ``"changed"``, ``"added"``, ``"removed"`` or
    ``"shape_mismatch"``.  Paths use dot notation for dict keys and
    ``[index]`` for list elements.  The root payload key (``brief`` or
    ``briefing``) is included in the path so callers can tell domains
    apart when diffing cross-domain envelopes (which they normally
    should not, but the diff is permissive).

    Envelope metadata (revision, stored_at) is collapsed into a single
    ``__envelope__`` entry so the caller can show "rev 3 → rev 4" in
    the UI without leaking internal schema names.
    """
    if old is None and new is None:
        return []
    if old is None:
        return [{"path": "__root__", "change": "added", "old": None, "new": new}]
    if new is None:
        return [{"path": "__root__", "change": "removed", "old": old, "new": None}]

    if not isinstance(old, dict) or not isinstance(new, dict):
        return [{
            "path": "__root__",
            "change": "shape_mismatch",
            "old": old,
            "new": new,
        }]

    out: list[DiffEntry] = []

    # Envelope-level metadata, collapsed into one entry.
    old_rev = old.get("server_revision")
    new_rev = new.get("server_revision")
    envelope_changed = (
        old.get("schema") != new.get("schema")
        or old.get("version") != new.get("version")
        or old_rev != new_rev
        or old.get("stored_at") != new.get("stored_at")
    )
    if envelope_changed:
        out.append({
            "path": "__envelope__",
            "change": "changed",
            "old": {
                "schema": old.get("schema"),
                "version": old.get("version"),
                "server_revision": old_rev,
                "stored_at": old.get("stored_at"),
            },
            "new": {
                "schema": new.get("schema"),
                "version": new.get("version"),
                "server_revision": new_rev,
                "stored_at": new.get("stored_at"),
            },
        })

    # Payload diff.  If both envelopes use the same payload key, diff
    # that key's value.  Otherwise fall back to a root dict diff that
    # includes any non-envelope keys.
    old_payload_key = _payload_key(old)
    new_payload_key = _payload_key(new)
    if (
        old_payload_key
        and new_payload_key
        and old_payload_key == new_payload_key
    ):
        old_payload = old.get(old_payload_key)
        new_payload = new.get(new_payload_key)
        _diff_value(old_payload_key, old_payload, new_payload, out)
    else:
        # Diff every non-envelope key on the root.
        old_root = {k: v for k, v in old.items() if k not in _ENVELOPE_KEYS}
        new_root = {k: v for k, v in new.items() if k not in _ENVELOPE_KEYS}
        _diff_dict("", old_root, new_root, out)

    out.sort(key=lambda entry: (entry["path"], entry["change"]))
    return out

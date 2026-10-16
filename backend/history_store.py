"""Storage of the History tab: lookups, DMARC imports and URL scans (data/history/).

Layout: `index.json` holds one small row per entry (what the list and the comparison of lookups need), and
`entries/<id>.json` holds the full entry with its `data`. Reading the list therefore never touches the big files, and
one damaged entry cannot disable the whole History.

Rules this module keeps:
- every change runs under one lock (some endpoints run in worker threads);
- on write the entry file goes first, then the index; on delete the index goes first, then the file, so a crash leaves
  at worst a file without a row (picked up again by the index rebuild), never a row that promises a missing entry;
- the index is a cache of the entry files: when it is unreadable or does not match them, it is rebuilt from the files;
- a damaged entry file is skipped and logged, never deleted (only retention, "delete" and "clear" remove files);
- the single-file history of earlier versions (data/history.json) is migrated lazily on first use and only renamed
  afterwards (history.json.migrated), never deleted.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.config import HISTORY_DIR, HISTORY_ENTRIES_DIR, HISTORY_FILE, HISTORY_INDEX_FILE, HISTORY_MAX_ENTRIES
from backend.models import HistoryEntry
from backend.storage import atomic_write_json

logger = logging.getLogger("app")

_LOCK = threading.RLock()
_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_INDEX_VERSION = 1
_ROW_KEYS = ("id", "type", "created_at", "label", "risk_summary", "lang", "pinned")
_REPORTED: set[str] = set()  # problems already written to the log, so a damaged file does not repeat on every request


def _warn_once(key: str, message: str) -> None:
    if key not in _REPORTED:
        _REPORTED.add(key)
        logger.warning(message)


def _entry_path(entry_id: str) -> Path:
    return HISTORY_ENTRIES_DIR / f"{entry_id}.json"


def _read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _ensure_dirs() -> None:
    for d in (HISTORY_DIR, HISTORY_ENTRIES_DIR):
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(d, 0o700)


def _trend(entry: HistoryEntry) -> dict[str, Any] | None:
    """What the comparison of a new lookup with the earlier ones reads from an entry (so it need not open the file)."""
    if entry.type != "lookup":
        return None
    score = entry.data.get("risk_score")
    score = score if isinstance(score, dict) else {}
    trend: dict[str, Any] = {"queried_at": entry.data.get("queried_at") or entry.created_at}
    if "score" in score and "level" in score:
        trend["score"] = score["score"]
        trend["level"] = score["level"]
    components = score.get("components")
    trend["risks"] = {
        c["source"]: c.get("risk") for c in components if isinstance(c, dict) and "source" in c
    } if isinstance(components, list) else {}
    return trend


def _row(entry: HistoryEntry) -> dict[str, Any]:
    row: dict[str, Any] = {k: getattr(entry, k) for k in _ROW_KEYS}
    row["risk_summary"] = row["risk_summary"].lower() if row["risk_summary"] else row["risk_summary"]
    trend = _trend(entry)
    if trend is not None:
        row["trend"] = trend
    return row


def _row_ok(row: Any) -> bool:
    return (
        isinstance(row, dict)
        and isinstance(row.get("id"), str)
        and bool(_ID_RE.match(row["id"]))
        and row.get("type") in ("lookup", "dmarc", "urlscan")
        and all(isinstance(row.get(k), str) for k in ("created_at", "label", "lang"))
        and isinstance(row.get("pinned"), bool)
    )


def _write_index(rows: list[dict[str, Any]]) -> None:
    _ensure_dirs()
    atomic_write_json(HISTORY_INDEX_FILE, {"version": _INDEX_VERSION, "entries": rows}, dir_mode=0o700)


def _write_entry(entry: HistoryEntry) -> None:
    _ensure_dirs()
    atomic_write_json(_entry_path(entry.id), entry.model_dump(), dir_mode=0o700)


def _read_entry(entry_id: str) -> HistoryEntry | None:
    """The entry file, or None when it is missing or damaged (a damaged file is logged and left alone)."""
    if not _ID_RE.match(entry_id):
        return None
    path = _entry_path(entry_id)
    try:
        return HistoryEntry.model_validate(_read_json(path))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, ValidationError):  # ValueError covers json.JSONDecodeError
        _warn_once(f"entry:{entry_id}", f"history entry file {entry_id} is unreadable or invalid; it is left untouched")
        return None


def _unlink_entry(entry_id: str) -> None:
    try:
        _entry_path(entry_id).unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning(f"history entry file {entry_id} could not be removed: {exc.__class__.__name__}")


def _entry_file_ids() -> set[str]:
    try:
        names = os.listdir(HISTORY_ENTRIES_DIR)
    except OSError:
        return set()
    return {n[:-5] for n in names if n.endswith(".json") and _ID_RE.match(n[:-5])}


def _rebuild_index() -> list[dict[str, Any]]:
    """The index from the entry files (newest first). Damaged files are skipped and left in place."""
    rows: list[dict[str, Any]] = []
    for entry_id in sorted(_entry_file_ids()):
        entry = _read_entry(entry_id)
        if entry is not None and entry.id == entry_id:
            rows.append(_row(entry))
        elif entry is not None:
            _warn_once(f"entry:{entry_id}", f"history entry file {entry_id} holds another id; it is left untouched")
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    _write_index(rows)  # also when empty, so that an unreadable-only directory is not rebuilt on every request
    logger.warning(f"history index rebuilt from {len(rows)} entry files")
    return rows


def _migrate_legacy() -> list[dict[str, Any]] | None:
    """Moves data/history.json into the new layout. Returns the rows, or None when nothing was migrated (the old file
    is then left exactly as it is)."""
    try:
        data = _read_json(HISTORY_FILE)
        raw_entries = data["entries"]
        if not isinstance(raw_entries, list):
            raise ValueError("entries is not a list")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        _warn_once("legacy", f"history.json could not be read ({exc.__class__.__name__}); it was not migrated and is kept as it is")
        return None
    entries: list[HistoryEntry] = []
    skipped = 0
    for raw in raw_entries:
        try:
            entry = HistoryEntry.model_validate(raw)
        except ValidationError:
            skipped += 1
            continue
        if not _ID_RE.match(entry.id):
            skipped += 1
            continue
        entries.append(entry)
    seen: set[str] = set()
    entries = [e for e in entries if not (e.id in seen or seen.add(e.id))]  # a repeated id keeps its first (newest) copy
    for entry in entries:
        _write_entry(entry)
    rows = [_row(e) for e in entries]
    _write_index(rows)
    ids = {r["id"] for r in _read_json(HISTORY_INDEX_FILE)["entries"]}
    if ids != {e.id for e in entries} or not ids <= _entry_file_ids():
        logger.error("history migration check failed; history.json was not renamed")
        return rows
    target = HISTORY_FILE.with_name(HISTORY_FILE.name + ".migrated")
    n = 1
    while target.exists():  # never overwrite an earlier backup
        n += 1
        target = HISTORY_FILE.with_name(f"{HISTORY_FILE.name}.migrated{n}")
    try:
        os.rename(HISTORY_FILE, target)
    except OSError as exc:
        logger.error(f"history.json could not be renamed after migration: {exc.__class__.__name__}")
    logger.warning(f"history migrated: {len(entries)} entries moved, {skipped} skipped (kept in {target.name})")
    return rows


def _load_rows() -> list[dict[str, Any]]:
    """The index rows, newest first. Migrates the old file or rebuilds the index when needed. Call with the lock held."""
    rows: list[dict[str, Any]] | None = None
    if HISTORY_INDEX_FILE.exists():
        try:
            data = _read_json(HISTORY_INDEX_FILE)
            candidate = data["entries"]
            if isinstance(candidate, list) and all(_row_ok(r) for r in candidate):
                rows = candidate
        except (OSError, ValueError, KeyError, TypeError):
            pass
        if rows is None:
            return _rebuild_index()
        known = {r["id"] for r in rows}
        orphans = {i for i in _entry_file_ids() - known if f"entry:{i}" not in _REPORTED}
        if orphans:  # files that the index does not list (e.g. a crash between the two writes)
            return _rebuild_index()
        return rows
    if HISTORY_FILE.exists():
        migrated = _migrate_legacy()
        return migrated if migrated is not None else []
    if _entry_file_ids():
        return _rebuild_index()
    return []


def list_history_rows() -> list[dict[str, Any]]:
    """Metadata of every stored entry, newest first (rows of the index: id, type, created_at, label, risk_summary,
    lang, pinned and, for a lookup, `trend`)."""
    with _LOCK:
        return [dict(r) for r in _load_rows()]


def append_history(entry: HistoryEntry) -> None:
    """Stores a new entry at the top. Retention: the newest HISTORY_MAX_ENTRIES entries that are not pinned plus all the
    pinned ones; the files of the rest are removed."""
    with _LOCK:
        rows = _load_rows()
        if entry.risk_summary:
            entry.risk_summary = entry.risk_summary.lower()
        _write_entry(entry)
        rows.insert(0, _row(entry))
        kept: list[dict[str, Any]] = []
        dropped: list[str] = []
        unpinned = 0
        for r in rows:  # newest first; the limit counts only the entries that are not pinned
            if r["pinned"]:
                kept.append(r)
            elif unpinned < HISTORY_MAX_ENTRIES:
                kept.append(r)
                unpinned += 1
            else:
                dropped.append(r["id"])
        _write_index(kept)
        for entry_id in dropped:
            _unlink_entry(entry_id)


def get_history_entry(entry_id: str) -> HistoryEntry | None:
    with _LOCK:
        rows = _load_rows()
        if not any(r["id"] == entry_id for r in rows):
            return None
        entry = _read_entry(entry_id)
        if entry is None and not _entry_path(entry_id).exists():  # the row promises a file that is gone
            _write_index([r for r in rows if r["id"] != entry_id])
        return entry


def delete_history_entry(entry_id: str) -> bool:
    with _LOCK:
        rows = _load_rows()
        remaining = [r for r in rows if r["id"] != entry_id]
        if len(remaining) == len(rows):
            return False
        _write_index(remaining)
        _unlink_entry(entry_id)
        return True


def clear_history() -> None:
    """Removes every entry except the pinned ones."""
    with _LOCK:
        rows = _load_rows()
        _write_index([r for r in rows if r["pinned"]])
        for r in rows:
            if not r["pinned"]:
                _unlink_entry(r["id"])


def set_history_pinned(entry_id: str, pinned: bool) -> bool:
    with _LOCK:
        rows = _load_rows()
        if not any(r["id"] == entry_id for r in rows):
            return False
        entry = _read_entry(entry_id)
        if entry is None:
            return False
        entry.pinned = pinned
        _write_entry(entry)
        _write_index([{**r, "pinned": pinned} if r["id"] == entry_id else r for r in rows])
        return True

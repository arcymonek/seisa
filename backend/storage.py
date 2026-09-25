from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from backend.config import HISTORY_FILE, HISTORY_MAX_ENTRIES, REPORT_LOG_FILE, VT_USAGE_FILE
from backend.models import HistoryEntry


def atomic_write_json(path: Path, data: dict[str, Any], dir_mode: int | None = None) -> None:
    """Writes JSON through a temp file + rename (no half-written files); the file gets 0600 from mkstemp.

    `dir_mode` (e.g. 0o700) is also applied to a parent directory that already exists, unlike mkdir(mode=...).
    """
    path.parent.mkdir(parents=True, exist_ok=True, **({"mode": dir_mode} if dir_mode is not None else {}))
    if dir_mode is not None:
        os.chmod(path.parent, dir_mode)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def load_history() -> list[HistoryEntry]:
    data = _read_json(HISTORY_FILE, {"entries": []})
    return [HistoryEntry.model_validate(e) for e in data.get("entries", [])]


def save_history(entries: list[HistoryEntry]) -> None:
    atomic_write_json(HISTORY_FILE, {"entries": [e.model_dump() for e in entries]})


def append_history(entry: HistoryEntry) -> None:
    entries = load_history()
    entries.insert(0, entry)
    kept: list[HistoryEntry] = []
    unpinned = 0
    for e in entries:  # newest first; the limit counts only the entries that are not pinned
        if e.pinned:
            kept.append(e)
        elif unpinned < HISTORY_MAX_ENTRIES:
            kept.append(e)
            unpinned += 1
    save_history(kept)


def delete_history_entry(entry_id: str) -> bool:
    entries = load_history()
    remaining = [e for e in entries if e.id != entry_id]
    if len(remaining) == len(entries):
        return False
    save_history(remaining)
    return True


def clear_history() -> None:
    """Removes every entry except the pinned ones."""
    save_history([e for e in load_history() if e.pinned])


def set_history_pinned(entry_id: str, pinned: bool) -> bool:
    entries = load_history()
    for e in entries:
        if e.id == entry_id:
            e.pinned = pinned
            save_history(entries)
            return True
    return False


def get_history_entry(entry_id: str) -> HistoryEntry | None:
    for e in load_history():
        if e.id == entry_id:
            return e
    return None


def load_vt_usage() -> dict[str, Any]:
    return _read_json(VT_USAGE_FILE, {"date": "", "count": 0})


def save_vt_usage(data: dict[str, Any]) -> None:
    atomic_write_json(VT_USAGE_FILE, data)


def successful_reports(ip: str) -> list[dict[str, Any]]:
    """Reports of this IP that AbuseIPDB accepted (newest first), from the local report log."""
    entries = _read_json(REPORT_LOG_FILE, {"entries": []}).get("entries", [])
    return [e for e in entries if e.get("success") and e.get("ip") == ip]


def load_report_log() -> list[dict[str, Any]]:
    """Every report attempt of the local log (newest first): accepted ones and failed ones."""
    return _read_json(REPORT_LOG_FILE, {"entries": []}).get("entries", [])


def append_report_log(entry: dict[str, Any]) -> None:
    data = _read_json(REPORT_LOG_FILE, {"entries": []})
    data.setdefault("entries", []).insert(0, entry)
    atomic_write_json(REPORT_LOG_FILE, data)

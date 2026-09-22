from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from backend.config import HISTORY_FILE, HISTORY_MAX_ENTRIES, REPORT_LOG_FILE, VT_USAGE_FILE
from backend.models import HistoryEntry


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def load_history() -> list[HistoryEntry]:
    data = _read_json(HISTORY_FILE, {"entries": []})
    return [HistoryEntry.model_validate(e) for e in data.get("entries", [])]


def save_history(entries: list[HistoryEntry]) -> None:
    _atomic_write(HISTORY_FILE, {"entries": [e.model_dump() for e in entries]})


def append_history(entry: HistoryEntry) -> None:
    entries = load_history()
    entries.insert(0, entry)
    entries = entries[:HISTORY_MAX_ENTRIES]
    save_history(entries)


def delete_history_entry(entry_id: str) -> bool:
    entries = load_history()
    remaining = [e for e in entries if e.id != entry_id]
    if len(remaining) == len(entries):
        return False
    save_history(remaining)
    return True


def clear_history() -> None:
    save_history([])


def get_history_entry(entry_id: str) -> HistoryEntry | None:
    for e in load_history():
        if e.id == entry_id:
            return e
    return None


def load_vt_usage() -> dict[str, Any]:
    return _read_json(VT_USAGE_FILE, {"date": "", "count": 0})


def save_vt_usage(data: dict[str, Any]) -> None:
    _atomic_write(VT_USAGE_FILE, data)


def append_report_log(entry: dict[str, Any]) -> None:
    data = _read_json(REPORT_LOG_FILE, {"entries": []})
    data.setdefault("entries", []).insert(0, entry)
    _atomic_write(REPORT_LOG_FILE, data)

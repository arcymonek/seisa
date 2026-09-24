"""Zapis analiz e-maili (zakładka "Email") w osobnym podkatalogu data/analizy/.

Jeden plik JSON na analizę, razem z surowym e-mailem (zawiera dane osobowe, dlatego pliki 0600, katalog 0700
i wpis w .gitignore). Identyfikator jest walidowany, żeby nie dało się wyjść poza katalog.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Any

from backend.config import ANALIZY_DIR

_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{8}$")


def _path(analysis_id: str):
    if not _ID_RE.match(analysis_id):
        raise ValueError("nieprawidłowy identyfikator analizy")
    return ANALIZY_DIR / f"{analysis_id}.json"


def _write(analysis_id: str, record: dict[str, Any]) -> None:
    ANALIZY_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=ANALIZY_DIR, prefix=".analiza.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, _path(analysis_id))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def save_analysis(record: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    digest = hashlib.sha256(record["raw_email"].encode("utf-8", errors="replace")).hexdigest()[:8]
    analysis_id = f"{now:%Y%m%d-%H%M%S}-{digest}"
    _write(analysis_id, {"id": analysis_id, "created_at": now.isoformat(), **record})
    return analysis_id


def update_analysis(analysis_id: str, fields: dict[str, Any]) -> None:
    record = load_analysis(analysis_id)
    if record is None:
        raise FileNotFoundError(analysis_id)
    record.update(fields)
    _write(analysis_id, record)


def source_hash(src: str) -> str:
    """Odcisk znormalizowanego źródła e-maila - do wykrywania powtórnych analiz tej samej wiadomości."""
    return hashlib.sha256(src.encode("utf-8", errors="replace")).hexdigest()


def find_by_source(sha256: str) -> list[dict[str, Any]]:
    """Zapisane analizy tego samego źródła (najnowsze pierwsze). Starsze zapisy bez pola source_sha256 są
    dopasowywane po odcisku surowego e-maila."""
    if not ANALIZY_DIR.exists():
        return []
    matches = []
    for path in sorted(ANALIZY_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (data.get("source_sha256") or source_hash(data.get("raw_email", ""))) != sha256:
            continue
        usage = data.get("usage") or {}
        matches.append({
            "id": data.get("id"), "created_at": data.get("created_at"), "verdict": data.get("verdict"),
            "confidence": data.get("confidence"), "truncated": bool(data.get("truncated")),
            "cost": usage.get("cost") if isinstance(usage.get("cost"), (int, float)) else None,
        })
    return matches


def list_analyses() -> list[dict[str, Any]]:
    if not ANALIZY_DIR.exists():
        return []
    items = []
    for path in sorted(ANALIZY_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items.append({k: data.get(k) for k in ("id", "created_at", "subject", "from", "verdict", "confidence", "truncated")})
    return items


def load_analysis(analysis_id: str) -> dict[str, Any] | None:
    path = _path(analysis_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def delete_analysis(analysis_id: str) -> bool:
    path = _path(analysis_id)
    if not path.exists():
        return False
    path.unlink()
    return True

from __future__ import annotations

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from backend.config import LOGI_DIR

router = APIRouter()

RANGE_DAYS_BACK = {"today": 0, "3d": 2, "week": 6, "month": 29}
MAX_ENTRIES = 500


def _normalize_legacy_service(entry: dict) -> dict:
    """Older OpenRouter error entries used the service "app" (or "llm_analyzer"); it is now "open_router"."""
    if entry.get("service") == "llm_analyzer" or (
        entry.get("service") == "app" and str(entry.get("message", "")).startswith("OpenRouter:")
    ):
        return {**entry, "service": "open_router"}
    return entry


@router.get("/logs")
async def get_logs(log_range: str = Query("today", alias="range"), service: str = "all"):
    today = datetime.now().astimezone().date()

    if not LOGI_DIR.exists():
        return []

    if log_range == "all":
        files = sorted(LOGI_DIR.glob("*.jsonl"), reverse=True)
    else:
        days_back = RANGE_DAYS_BACK.get(log_range, 0)
        candidate_dates = [today - timedelta(days=i) for i in range(days_back + 1)]
        files = [LOGI_DIR / f"{d.isoformat()}.jsonl" for d in candidate_dates]
        files = [f for f in files if f.exists()]

    entries = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entry = _normalize_legacy_service(entry)
                if service != "all" and entry.get("service") != service:
                    continue
                entries.append(entry)

    entries.sort(key=lambda e: e.get("time", ""), reverse=True)
    return entries[:MAX_ENTRIES]

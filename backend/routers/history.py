"""History tab: the last lookups, DMARC imports and URL scans (history.json) together with the saved e-mail analyses."""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.analyses import list_analyses
from backend.config import HISTORY_MAX_ENTRIES, MAX_HISTORY_DATA_CHARS
from backend.i18n import current_lang, t
from backend.models import HistoryEntry
from backend.storage import (
    append_history,
    clear_history,
    delete_history_entry,
    get_history_entry,
    load_history,
    load_report_log,
)

router = APIRouter()


class HistoryCreateRequest(BaseModel):
    type: str
    label: str = Field(max_length=1000)
    risk_summary: str | None = Field(default=None, max_length=50)
    data: dict


THUMBNAIL_PREFIX = "data:image/jpeg;base64,"
MAX_THUMBNAIL_CHARS = 200_000  # a 640 px JPEG thumbnail is about 30-60 KB; nothing larger is stored
_THUMBNAIL_BASE64 = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")

EMAIL_VERDICT_RISK = {"legit": "Low", "inconclusive": "Medium"}


def _email_entry(item: dict) -> dict:
    """A saved analysis of the Email tab shown as a history entry (the data stays in data/analyses/)."""
    verdict = item.get("verdict")
    return {
        "id": item["id"],
        "type": "email",
        "created_at": item["created_at"],
        "label": f"{item.get('subject') or t('history.no_subject')} - {item.get('from') or '?'}",
        "risk_summary": EMAIL_VERDICT_RISK.get(verdict, "High") if verdict else None,
        "lang": item.get("lang") or "pl",
    }


def _report_entry(item: dict) -> dict:
    """An accepted AbuseIPDB report shown as a history entry (the data stays in the local report log)."""
    cats = ",".join(str(c) for c in item.get("categories") or [])
    return {
        "id": item["id"],
        "type": "report",
        "created_at": item["submitted_at"],
        "label": f"{item['ip']} - {cats}",
        "risk_summary": None,
        "lang": current_lang(),
    }


def _check_urlscan_data(data: dict) -> None:
    """A scan entry is the structured summary plus an optional thumbnail; the thumbnail is shown through an <img>, so
    only a plain base64 JPEG data URI of a bounded size is accepted."""
    if not isinstance(data.get("summary"), dict):
        raise HTTPException(status_code=400, detail=t("history.invalid_data"))
    thumbnail = data.get("thumbnail")
    if thumbnail is None:
        return
    if (
        not isinstance(thumbnail, str)
        or not thumbnail.startswith(THUMBNAIL_PREFIX)
        or len(thumbnail) > MAX_THUMBNAIL_CHARS
        or not _THUMBNAIL_BASE64.match(thumbnail[len(THUMBNAIL_PREFIX):])
    ):
        raise HTTPException(status_code=400, detail=t("history.invalid_thumbnail"))


@router.get("/history")
def list_history():
    items = [
        {
            "id": e.id,
            "type": e.type,
            "created_at": e.created_at,
            "label": e.label,
            "risk_summary": e.risk_summary,
            "lang": e.lang,
        }
        for e in load_history()
    ]
    items += [_email_entry(a) for a in list_analyses() if a.get("id") and a.get("created_at")]
    items += [_report_entry(r) for r in load_report_log() if r.get("success") and r.get("id") and r.get("submitted_at")]
    items.sort(key=lambda i: i["created_at"], reverse=True)
    return items[:HISTORY_MAX_ENTRIES]


@router.get("/history/{entry_id}")
def get_entry(entry_id: str):
    entry = get_history_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail=t("history.not_found"))
    return entry


@router.post("/history")
async def create_entry(req: HistoryCreateRequest):
    if req.type not in ("lookup", "dmarc", "urlscan"):
        raise HTTPException(status_code=400, detail=t("history.invalid_type"))
    if len(json.dumps(req.data)) > MAX_HISTORY_DATA_CHARS:
        raise HTTPException(status_code=413, detail=t("history.too_large"))
    if req.type == "urlscan":
        _check_urlscan_data(req.data)
    entry = HistoryEntry(type=req.type, label=req.label, risk_summary=req.risk_summary, lang=current_lang(), data=req.data)
    append_history(entry)
    return entry


@router.delete("/history/{entry_id}")
async def delete_entry(entry_id: str):
    if not delete_history_entry(entry_id):
        raise HTTPException(status_code=404, detail=t("history.not_found"))
    return {"deleted": entry_id}


@router.delete("/history")
async def delete_all():
    clear_history()
    return {"cleared": True}

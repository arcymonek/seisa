from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.models import HistoryEntry
from backend.storage import (
    append_history,
    clear_history,
    delete_history_entry,
    get_history_entry,
    load_history,
)

router = APIRouter()


class HistoryCreateRequest(BaseModel):
    type: str
    label: str
    risk_summary: str | None = None
    data: dict


@router.get("/history")
async def list_history():
    entries = load_history()
    return [
        {
            "id": e.id,
            "type": e.type,
            "created_at": e.created_at,
            "label": e.label,
            "risk_summary": e.risk_summary,
        }
        for e in entries
    ]


@router.get("/history/{entry_id}")
async def get_entry(entry_id: str):
    entry = get_history_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="nie znaleziono wpisu")
    return entry


@router.post("/history")
async def create_entry(req: HistoryCreateRequest):
    if req.type not in ("lookup", "dmarc"):
        raise HTTPException(status_code=400, detail="nieprawidłowy typ wpisu")
    entry = HistoryEntry(type=req.type, label=req.label, risk_summary=req.risk_summary, data=req.data)
    append_history(entry)
    return entry


@router.delete("/history/{entry_id}")
async def delete_entry(entry_id: str):
    if not delete_history_entry(entry_id):
        raise HTTPException(status_code=404, detail="nie znaleziono wpisu")
    return {"deleted": entry_id}


@router.delete("/history")
async def delete_all():
    clear_history()
    return {"cleared": True}

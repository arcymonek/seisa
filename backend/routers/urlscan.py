"""URLScan tab: submits a scan to urlscan.io (/scan) and fetches the finished result as a Markdown report (/result)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.i18n import t
from backend.services import urlscan as urlscan_service
from backend.urlscan_report import build_urlscan_markdown

router = APIRouter()


class ScanRequest(BaseModel):
    url: str


@router.post("/scan")
async def scan(req: ScanRequest):
    if not urlscan_service.is_configured():
        raise HTTPException(status_code=400, detail=t("urlscan.no_key"))
    try:
        data = await urlscan_service.submit_scan(req.url)
    except urlscan_service.UrlscanError as exc:
        raise HTTPException(status_code=502, detail=t("urlscan.submit_failed", message=exc.message)) from exc
    return {
        "uuid": data.get("uuid"),
        "result_page_url": data.get("result") or f"https://urlscan.io/result/{data.get('uuid')}/",
    }


@router.get("/result/{uuid}")
async def result(uuid: str):
    try:
        data = await urlscan_service.fetch_result(uuid)
    except urlscan_service.UrlscanError as exc:
        raise HTTPException(status_code=502, detail=t("urlscan.fetch_failed", message=exc.message)) from exc
    if data is None:
        return {"status": "pending"}

    submitted_url = data.get("task", {}).get("url", "")
    markdown = build_urlscan_markdown(submitted_url, uuid, data)
    return {"status": "done", "markdown": markdown}

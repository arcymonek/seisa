"""URLScan tab: submits a scan to urlscan.io (/scan), fetches the finished result as a structured summary plus a
Markdown report (/result) and serves the page screenshot (/screenshot)."""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from backend.i18n import t
from backend.services import urlscan as urlscan_service
from backend.urlscan_input import InvalidScanUrl, normalize_scan_url
from backend.urlscan_report import build_urlscan_markdown, build_urlscan_summary

router = APIRouter()


class ScanRequest(BaseModel):
    url: str
    visibility: str = urlscan_service.DEFAULT_VISIBILITY


@router.post("/scan")
async def scan(req: ScanRequest):
    if not urlscan_service.is_configured():
        raise HTTPException(status_code=400, detail=t("urlscan.no_key"))
    if req.visibility not in urlscan_service.VISIBILITIES:
        raise HTTPException(status_code=400, detail=t("urlscan.invalid_visibility"))
    try:
        url = normalize_scan_url(req.url)
    except InvalidScanUrl as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        data = await urlscan_service.submit_scan(url, req.visibility)
    except urlscan_service.UrlscanError as exc:
        raise HTTPException(status_code=502, detail=t("urlscan.submit_failed", message=exc.message)) from exc
    return {
        "uuid": data.get("uuid"),
        "url": url,
        "visibility": req.visibility,
        "result_page_url": data.get("result") or f"https://urlscan.io/result/{data.get('uuid')}/",
    }


_UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")


def _check_uuid(uuid: str) -> None:
    if not _UUID_RE.match(uuid):
        raise HTTPException(status_code=400, detail=t("urlscan.invalid_uuid"))


@router.get("/result/{uuid}")
async def result(uuid: str):
    _check_uuid(uuid)
    try:
        data = await urlscan_service.fetch_result(uuid)
    except urlscan_service.UrlscanError as exc:
        raise HTTPException(status_code=502, detail=t("urlscan.fetch_failed", message=exc.message)) from exc
    if data is None:
        return {"status": "pending"}

    summary = build_urlscan_summary(data.get("task", {}).get("url", ""), uuid, data)
    return {"status": "done", "summary": summary, "markdown": build_urlscan_markdown(summary, data), "raw": data}


@router.get("/screenshot/{uuid}")
async def screenshot(uuid: str):
    _check_uuid(uuid)
    try:
        image = await urlscan_service.fetch_screenshot(uuid)
    except urlscan_service.UrlscanError as exc:
        raise HTTPException(status_code=502, detail=t("urlscan.screenshot_failed", message=exc.message)) from exc
    if image is None:
        raise HTTPException(status_code=404, detail=t("urlscan.no_screenshot"))
    return Response(content=image, media_type="image/png", headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})

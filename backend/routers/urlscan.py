"""URLScan tab: submits a scan to urlscan.io (/scan), fetches the finished result as a structured summary plus a
Markdown report (/result) and serves the page screenshot (/screenshot)."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from backend.i18n import t
from backend.scoring import HIGH_FROM, MEDIUM_FROM
from backend.services import urlscan as urlscan_service
from backend.urlscan_forms import extract_forms
from backend.urlscan_input import InvalidScanUrl, normalize_scan_url
from backend.urlscan_report import build_urlscan_markdown, build_urlscan_summary

router = APIRouter()


class ScanRequest(BaseModel):
    url: str
    visibility: str = urlscan_service.DEFAULT_VISIBILITY
    country: str | None = None
    useragent: str | None = None


@router.post("/scan")
async def scan(req: ScanRequest):
    if not urlscan_service.is_configured():
        raise HTTPException(status_code=400, detail=t("urlscan.no_key"))
    if req.visibility not in urlscan_service.VISIBILITIES:
        raise HTTPException(status_code=400, detail=t("urlscan.invalid_visibility"))
    country = (req.country or "").strip().lower() or None
    if country and country not in urlscan_service.COUNTRIES:
        raise HTTPException(status_code=400, detail=t("urlscan.invalid_country"))
    useragent = (req.useragent or "").strip() or None
    if useragent and (len(useragent) > urlscan_service.MAX_USERAGENT_CHARS or not useragent.isprintable()):
        raise HTTPException(status_code=400, detail=t("urlscan.invalid_useragent"))
    try:
        url = normalize_scan_url(req.url)
    except InvalidScanUrl as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        data = await urlscan_service.submit_scan(url, req.visibility, country, useragent)
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

    page = data.get("page", {}) or {}
    dom = await urlscan_service.fetch_dom(uuid)
    forms = extract_forms(dom, page.get("url") or "", page.get("domain")) if dom is not None else None
    summary = build_urlscan_summary(data.get("task", {}).get("url", ""), uuid, data, forms)
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


_HOST_RE = re.compile(r"^[a-z0-9.-]{1,253}$")
_IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _search_verdict(item: dict) -> str | None:
    """The risk level of a search hit, when urlscan.io includes a verdict in it."""
    overall = (item.get("verdicts") or {}).get("overall") or {}
    score = overall.get("score")
    if overall.get("malicious") or (score or 0) >= HIGH_FROM:
        return "high"
    if (score or 0) >= MEDIUM_FROM:
        return "medium"
    return "low" if overall.get("hasVerdicts") else None


@router.get("/search")
async def search(url: str):
    """Earlier scans of the domain of `url` - so that a fresh scan is not ordered when a recent one already answers."""
    if not urlscan_service.is_configured():
        raise HTTPException(status_code=400, detail=t("urlscan.no_key"))
    try:
        normalized = normalize_scan_url(url)
    except InvalidScanUrl as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    host = (urlsplit(normalized).hostname or "").lower()
    if not _HOST_RE.match(host):  # the host goes into a search query: only plain host characters
        raise HTTPException(status_code=400, detail=t("urlscan.url_invalid"))
    query = f'page.ip:"{host}"' if _IPV4_RE.match(host) else f'page.domain:"{host}"'
    try:
        hits = await urlscan_service.search_scans(query)
    except urlscan_service.UrlscanError as exc:
        raise HTTPException(status_code=502, detail=t("urlscan.search_failed", message=exc.message)) from exc
    results = []
    for hit in hits:
        uuid = hit.get("_id") or ""
        if not _UUID_RE.match(uuid):
            continue
        task, page = hit.get("task") or {}, hit.get("page") or {}
        results.append({
            "uuid": uuid,
            "time": task.get("time"),
            "url": task.get("url") or page.get("url") or "",
            "ip": page.get("ip"),
            "country": page.get("country"),
            "visibility": task.get("visibility"),
            "level": _search_verdict(hit),
            "exact": (task.get("url") or "") == normalized,
        })
    return {"host": host, "url": normalized, "results": results}

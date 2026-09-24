from __future__ import annotations

import logging

import httpx

from backend.config import settings
from backend.services.base import describe_exception

logger = logging.getLogger("urlscan")

SCAN_URL = "https://urlscan.io/api/v1/scan/"
RESULT_URL = "https://urlscan.io/api/v1/result/{uuid}/"


class UrlscanError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def is_configured() -> bool:
    return bool(settings.urlscan_api_key)


def _headers() -> dict:
    return {"API-Key": settings.urlscan_api_key, "Content-Type": "application/json"}


async def submit_scan(url: str) -> dict:
    """Submits a new scan - always with 'unlisted' visibility (it does not appear on the public front
    page/search of urlscan.io, but is available by UUID and visible to verified researchers in urlscan Pro).
    The user agent and the scan country are deliberately NOT set (Default/Auto) - the fields are simply
    omitted and urlscan.io picks the default values itself."""
    if not is_configured():
        raise UrlscanError("no API key (URLSCAN_API_KEY)")
    payload = {"url": url, "visibility": "unlisted"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(SCAN_URL, headers=_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        message = f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        logger.error(f"scan submission failed: {message}")
        raise UrlscanError(message) from exc
    except httpx.HTTPError as exc:
        message = describe_exception(exc)
        logger.error(f"scan submission failed: {message}")
        raise UrlscanError(message) from exc


async def fetch_result(uuid: str) -> dict | None:
    """Returns None if the scan is still running (urlscan.io answers 404 until the result is ready - that is
    expected, not an error)."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(RESULT_URL.format(uuid=uuid), headers=_headers())
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        message = f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        logger.error(f"fetching the scan result failed: {message}")
        raise UrlscanError(message) from exc
    except httpx.HTTPError as exc:
        message = describe_exception(exc)
        logger.error(f"fetching the scan result failed: {message}")
        raise UrlscanError(message) from exc

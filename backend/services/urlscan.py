from __future__ import annotations

import logging

import httpx

from backend.config import settings
from backend.services.base import http_error_text

logger = logging.getLogger("urlscan")

SCAN_URL = "https://urlscan.io/api/v1/scan/"
RESULT_URL = "https://urlscan.io/api/v1/result/{uuid}/"
SCREENSHOT_URL = "https://urlscan.io/screenshots/{uuid}.png"
VISIBILITIES = ("unlisted", "private", "public")
DEFAULT_VISIBILITY = "unlisted"
MAX_SCREENSHOT_BYTES = 6_000_000
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class UrlscanError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def is_configured() -> bool:
    return bool(settings.urlscan_api_key)


def _headers() -> dict:
    return {"API-Key": settings.urlscan_api_key, "Content-Type": "application/json"}


async def submit_scan(url: str, visibility: str = DEFAULT_VISIBILITY) -> dict:
    """Submits a new scan. The default visibility is 'unlisted' (it does not appear on the public front page/search
    of urlscan.io, but is available by UUID and visible to verified researchers in urlscan Pro); 'private' and
    'public' are chosen explicitly in the UI. The user agent and the scan country are deliberately NOT set
    (Default/Auto) - the fields are simply omitted and urlscan.io picks the default values itself."""
    if not is_configured():
        raise UrlscanError("no API key (URLSCAN_API_KEY)")
    if visibility not in VISIBILITIES:
        raise UrlscanError(f"unsupported visibility: {visibility}")
    payload = {"url": url, "visibility": visibility}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(SCAN_URL, headers=_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        message = http_error_text(exc)
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
    except httpx.HTTPError as exc:
        message = http_error_text(exc)
        logger.error(f"fetching the scan result failed: {message}")
        raise UrlscanError(message) from exc


async def fetch_screenshot(uuid: str) -> bytes | None:
    """The page screenshot (PNG) rendered by urlscan.io - fetched here, not by the browser, so that the CSP can keep
    img-src on 'self' and the browser never talks to urlscan.io. None while the image is not there (yet)."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(SCREENSHOT_URL.format(uuid=uuid), headers={"API-Key": settings.urlscan_api_key})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        message = http_error_text(exc)
        logger.error(f"fetching the screenshot failed: {message}")
        raise UrlscanError(message) from exc
    body = resp.content
    if len(body) > MAX_SCREENSHOT_BYTES or not body.startswith(PNG_MAGIC):
        logger.error("screenshot rejected: not a PNG or too large (%d bytes)", len(body))
        raise UrlscanError("the screenshot is not a valid PNG image")
    return body

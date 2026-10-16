"""urlscan.io client for the URL scan tab: submits a scan, fetches the result, the screenshot and the DOM, and
searches earlier scans. Functions rather than an IntelService, because a scan is asynchronous and returns files.
Nothing from a scanned page is opened by Seisa.
"""
from __future__ import annotations

import logging

import httpx

from backend.config import settings
from backend.services.base import http_error_text

logger = logging.getLogger("urlscan")

SCAN_URL = "https://urlscan.io/api/v1/scan/"
RESULT_URL = "https://urlscan.io/api/v1/result/{uuid}/"
SCREENSHOT_URL = "https://urlscan.io/screenshots/{uuid}.png"
DOM_URL = "https://urlscan.io/dom/{uuid}/"
SEARCH_URL = "https://urlscan.io/api/v1/search/"
SEARCH_SIZE = 10
VISIBILITIES = ("unlisted", "private", "public")
DEFAULT_VISIBILITY = "unlisted"
COUNTRIES = ("de", "us", "jp", "fr", "gb", "nl", "ca", "it", "es", "se", "pl", "au")  # scan countries offered in the UI
MAX_USERAGENT_CHARS = 250
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


async def _request(method: str, url: str, failure: str, *, none_on_404: bool = False, log=logger.error, **kwargs) -> httpx.Response | None:
    """One request to urlscan.io. With `none_on_404` a 404 gives None: urlscan.io answers 404 until a result, screenshot
    or DOM is ready, which is expected, not an error. Any other HTTP failure is logged as "<failure>: <details>" and
    raised as UrlscanError."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.request(method, url, **kwargs)
        if none_on_404 and resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp
    except httpx.HTTPError as exc:
        message = http_error_text(exc)
        log(f"{failure}: {message}")
        raise UrlscanError(message) from exc


async def submit_scan(url: str, visibility: str = DEFAULT_VISIBILITY, country: str | None = None, useragent: str | None = None) -> dict:
    """Submits a new scan. The default visibility is 'unlisted' (it does not appear on the public front page/search
    of urlscan.io, but is available by UUID and visible to verified researchers in urlscan Pro); 'private' and
    'public' are chosen explicitly in the UI. The user agent (`customagent`) and the scan country (`country`) are
    optional: unless the user picked them in the advanced options, the fields are simply omitted and urlscan.io picks
    the default values itself."""
    if not is_configured():
        raise UrlscanError("no API key (URLSCAN_API_KEY)")
    if visibility not in VISIBILITIES:
        raise UrlscanError(f"unsupported visibility: {visibility}")
    payload = {"url": url, "visibility": visibility}
    if country:
        payload["country"] = country
    if useragent:
        payload["customagent"] = useragent
    resp = await _request("POST", SCAN_URL, "scan submission failed", headers=_headers(), json=payload)
    return resp.json()


async def fetch_result(uuid: str) -> dict | None:
    """Returns None if the scan is still running (urlscan.io answers 404 until the result is ready - that is
    expected, not an error)."""
    resp = await _request("GET", RESULT_URL.format(uuid=uuid), "fetching the scan result failed", none_on_404=True, headers=_headers())
    return resp.json() if resp else None


async def fetch_screenshot(uuid: str) -> bytes | None:
    """The page screenshot (PNG) rendered by urlscan.io - fetched here, not by the browser, so that the CSP can keep
    img-src on 'self' and the browser never talks to urlscan.io. None while the image is not there (yet)."""
    resp = await _request("GET", SCREENSHOT_URL.format(uuid=uuid), "fetching the screenshot failed", none_on_404=True,
                          headers={"API-Key": settings.urlscan_api_key})
    if resp is None:
        return None
    body = resp.content
    if len(body) > MAX_SCREENSHOT_BYTES or not body.startswith(PNG_MAGIC):
        logger.error("screenshot rejected: not a PNG or too large (%d bytes)", len(body))
        raise UrlscanError("the screenshot is not a valid PNG image")
    return body


async def fetch_dom(uuid: str) -> str | None:
    """The rendered DOM of the scanned page as text (None when urlscan.io has none). It is only ever parsed, never
    served to the browser."""
    try:
        resp = await _request("GET", DOM_URL.format(uuid=uuid), "fetching the DOM failed", none_on_404=True,
                              log=logger.warning, headers={"API-Key": settings.urlscan_api_key})
    except UrlscanError:
        return None
    return resp.text if resp else None


async def search_scans(query: str) -> list[dict]:
    """Earlier scans matching a urlscan.io search query (public scans plus the ones of this account)."""
    resp = await _request("GET", SEARCH_URL, "search failed", params={"q": query, "size": SEARCH_SIZE}, headers=_headers())
    return resp.json().get("results") or []

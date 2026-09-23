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
    """Zgłasza nowy skan - zawsze widoczność 'unlisted' (nie trafia na publiczną
    stronę główną/wyszukiwarkę urlscan.io, ale jest dostępny po UUID i widoczny
    dla zweryfikowanych badaczy w urlscan Pro). User-agent i kraj skanowania
    celowo NIE są ustawiane (Default/Auto) - to po prostu pominięcie tych pól,
    urlscan.io sam dobiera wartości domyślne."""
    if not is_configured():
        raise UrlscanError("brak klucza API (URLSCAN_API_KEY)")
    payload = {"url": url, "visibility": "unlisted"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(SCAN_URL, headers=_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        message = f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        logger.error(f"zgłoszenie skanu nie powiodło się: {message}")
        raise UrlscanError(message) from exc
    except httpx.HTTPError as exc:
        message = describe_exception(exc)
        logger.error(f"zgłoszenie skanu nie powiodło się: {message}")
        raise UrlscanError(message) from exc


async def fetch_result(uuid: str) -> dict | None:
    """Zwraca None, jeśli skan jeszcze trwa (urlscan.io odpowiada 404, dopóki
    wynik nie jest gotowy - to oczekiwane, nie błąd)."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(RESULT_URL.format(uuid=uuid), headers=_headers())
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        message = f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        logger.error(f"pobranie wyniku skanu nie powiodło się: {message}")
        raise UrlscanError(message) from exc
    except httpx.HTTPError as exc:
        message = describe_exception(exc)
        logger.error(f"pobranie wyniku skanu nie powiodło się: {message}")
        raise UrlscanError(message) from exc

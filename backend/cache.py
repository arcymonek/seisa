from __future__ import annotations

import time

from backend.models import ServiceResult

TTL_SECONDS = 15 * 60

_store: dict[tuple[str, str], tuple[ServiceResult, float]] = {}


def get(indicator: str, service: str) -> ServiceResult | None:
    key = (indicator, service)
    entry = _store.get(key)
    if not entry:
        return None
    result, expires_at = entry
    if time.monotonic() > expires_at:
        del _store[key]
        return None
    return result


def set(indicator: str, service: str, result: ServiceResult) -> None:
    _store[(indicator, service)] = (result, time.monotonic() + TTL_SECONDS)

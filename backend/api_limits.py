"""Usage of the third-party APIs against the limits of their FREE plans (Info tab, "API limits" card).

Three kinds of data, all stored in data/api_usage.json:
- read from the service on request (VirusTotal, urlscan, OpenRouter: a quota endpoint that consumes no quota),
- remembered from the rate-limit headers of the normal answers (AbuseIPDB per endpoint, Cloudflare),
- counted by Seisa itself (GreyNoise per 7 days, OTX per hour) because those services report nothing; that count is a
  lower bound - requests made outside Seisa (e.g. in the GreyNoise Visualizer) are not visible here.
Nothing is sent anywhere unless refresh_live() runs, which happens only on an explicit click in the UI.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from backend.config import settings
from backend.ratelimit import VT_PER_DAY, vt_rate_limiter
from backend.storage import load_api_usage, save_api_usage

logger = logging.getLogger("app")

# Assumed limits of the free plans for the services that do not report them (AbuseIPDB: the account's own 5 000/day).
ABUSEIPDB_DAILY = 5000
GREYNOISE_WEEKLY = 50
OTX_HOURLY = 10000
CLOUDFLARE_5MIN = 1200

_BUCKET = "%Y-%m-%dT%H"  # counters are kept per UTC hour
_KEEP_DAYS = 8
SERVICE_ORDER = ["abuseipdb", "virustotal", "urlscan", "greynoise", "otx", "cloudflare_radar", "openrouter"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _window_end(window: str, now: datetime) -> datetime | None:
    """When a fixed UTC window that contains `now` ends (VirusTotal and the hourly OTX counter)."""
    if window == "hour":
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    if window == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if window == "month":
        first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (first + timedelta(days=32)).replace(day=1)
    return None


def _row(service, scope, window, used, limit, *, unit="requests", resets_at=None, source="api", seen_at=None, assumed=False):
    return {
        "service": service, "scope": scope, "window": window, "used": used, "limit": limit, "unit": unit,
        "resets_at": _iso(resets_at) if isinstance(resets_at, datetime) else resets_at,
        "source": source, "seen_at": seen_at, "assumed": assumed,
    }


# ---- what normal requests leave behind ----

def _count(usage: dict, service: str) -> None:
    now = _now()
    counts = usage.setdefault("counts", {}).setdefault(service, {})
    key = now.strftime(_BUCKET)
    counts[key] = counts.get(key, 0) + 1
    oldest = (now - timedelta(days=_KEEP_DAYS)).strftime(_BUCKET)
    for old in [k for k in counts if k < oldest]:
        del counts[old]


def _int(headers, name: str) -> int | None:
    try:
        return int(headers.get(name))
    except (TypeError, ValueError):
        return None


def _field(header: str | None, name: str) -> int | None:
    match = re.search(rf"\b{name}=(\d+)", header or "")
    return int(match.group(1)) if match else None


def _limit_key(service: str, resp: httpx.Response) -> str:
    """The key under which an exhausted limit is remembered: AbuseIPDB has separate limits per endpoint."""
    if service == "abuseipdb":
        return f"abuseipdb:{resp.request.url.path.rstrip('/').rsplit('/', 1)[-1]}"
    return service


def _exceeded_entry(resp: httpx.Response, now: datetime) -> dict:
    """What an HTTP 429 says about the reset: Retry-After / X-RateLimit-Reset when present, else a date named in the
    body (GreyNoise: "Your searches will reset on September 29")."""
    reset_at = None
    retry = _int(resp.headers, "Retry-After")
    epoch = _int(resp.headers, "X-RateLimit-Reset")
    if retry is not None:
        reset_at = _iso(now + timedelta(seconds=retry))
    elif epoch is not None and epoch > now.timestamp():
        reset_at = _iso(datetime.fromtimestamp(epoch, timezone.utc))
    match = re.search(r"reset on ([A-Za-z]+ \d{1,2})", resp.text[:2000])
    return {"seen": _iso(now), "reset_at": reset_at, "reset_text": match.group(1) if match else None}


def _observe(service: str, resp: httpx.Response) -> None:
    usage = load_api_usage()
    now = _now()
    key = _limit_key(service, resp)
    if resp.status_code == 429:
        # the API itself says the limit is used up: shown in the Info tab until the next successful answer
        usage.setdefault("exceeded", {})[key] = _exceeded_entry(resp, now)
        save_api_usage(usage)
        return
    if resp.status_code < 400 and key in usage.get("exceeded", {}):
        del usage["exceeded"][key]
        save_api_usage(usage)
    if service == "greynoise":
        if resp.status_code in (200, 404):  # a search happened; a 403 (plan too low) and errors are not counted
            _count(usage, service)
    elif service == "otx":
        _count(usage, service)
    elif service == "abuseipdb":
        limit, remaining, reset = _int(resp.headers, "X-RateLimit-Limit"), _int(resp.headers, "X-RateLimit-Remaining"), _int(resp.headers, "X-RateLimit-Reset")
        if limit is None or remaining is None:
            return
        scope = resp.request.url.path.rstrip("/").rsplit("/", 1)[-1]
        usage.setdefault("headers", {})[f"abuseipdb:{scope}"] = {"limit": limit, "remaining": remaining, "reset": reset, "seen": _iso(now)}
    elif service == "cloudflare_radar":
        remaining = _field(resp.headers.get("ratelimit"), "r")
        reset_after = _field(resp.headers.get("ratelimit"), "t")
        limit = _field(resp.headers.get("ratelimit-policy"), "q")
        if remaining is None or limit is None:
            return
        reset = int(now.timestamp()) + reset_after if reset_after is not None else None
        usage.setdefault("headers", {})["cloudflare_radar"] = {"limit": limit, "remaining": remaining, "reset": reset, "seen": _iso(now)}
    else:
        return
    save_api_usage(usage)


def observe(service: str, resp: httpx.Response) -> None:
    """Called after every answer of a keyed service; must never break the request itself."""
    try:
        _observe(service, resp)
    except Exception as exc:  # a broken usage file must not fail a lookup
        logger.warning(f"api usage bookkeeping for {service} failed: {type(exc).__name__}")


# ---- the table ----

def _header_row(service: str, scope: str, window: str, default_limit: int, entry: dict | None, now: datetime) -> dict:
    if not entry:
        return _row(service, scope, window, None, default_limit, source="none", assumed=True)
    reset = datetime.fromtimestamp(entry["reset"], timezone.utc) if entry.get("reset") else None
    fresh = reset is None or reset > now  # once the window has passed, the remembered count says nothing any more
    used = entry["limit"] - entry["remaining"] if fresh else None
    return _row(service, scope, window, used, entry["limit"], resets_at=reset, source="headers", seen_at=entry.get("seen"))


def _counted(usage: dict, service: str, since_key: str, until_key: str | None = None) -> int:
    counts = usage.get("counts", {}).get(service, {})
    return sum(n for k, n in counts.items() if k >= since_key and (until_key is None or k <= until_key))


def _mark_exceeded(rows: list[dict], exceeded: dict, now: datetime) -> None:
    """Rows of a service that answered HTTP 429 get an `exceeded` entry. Where the count is Seisa's own or comes from
    headers, the usage is raised to the limit (a lower bound of a real count that is known to be full); the quotas
    read from the service itself are left alone."""
    for row in rows:
        key = f"abuseipdb:{row['scope']}" if row["service"] == "abuseipdb" else row["service"]
        entry = exceeded.get(key)
        if not entry:
            continue
        seen = datetime.fromisoformat(entry["seen"])
        reset = datetime.fromisoformat(entry["reset_at"]) if entry.get("reset_at") else None
        if (reset and reset <= now) or seen < now - timedelta(days=_KEEP_DAYS):
            continue  # the window has passed: the flag says nothing any more
        row["exceeded"] = entry
        if row["source"] in ("local", "headers", "none") and row["limit"] and (row["used"] is None or row["used"] < row["limit"]):
            row["used"] = row["limit"]
        if not row["resets_at"] and reset:
            row["resets_at"] = entry["reset_at"]


def limits_snapshot() -> dict:
    """Rows for every service that has a key, from what is stored - no network access."""
    usage = load_api_usage()
    now = _now()
    live = usage.get("live", {})
    headers = usage.get("headers", {})
    rows: list[dict] = []

    def placeholder(service):
        return [_row(service, "requests", "day", None, None, source="none")]

    if settings.abuseipdb_api_key:
        for scope in ("check", "report"):
            rows.append(_header_row("abuseipdb", scope, "day", ABUSEIPDB_DAILY, headers.get(f"abuseipdb:{scope}"), now))
    if settings.virustotal_api_key:
        rows += live.get("virustotal", {}).get("rows") or [
            _row("virustotal", "requests", "day", vt_rate_limiter.daily_count(), VT_PER_DAY, resets_at=_window_end("day", now), source="local")
        ]
    if settings.urlscan_api_key:
        rows += live.get("urlscan", {}).get("rows") or placeholder("urlscan")
    if settings.greynoise_api_key:
        since = (now - timedelta(days=7)).strftime(_BUCKET)
        rows.append(_row("greynoise", "searches", "week", _counted(usage, "greynoise", since), GREYNOISE_WEEKLY, source="local", assumed=True))
    if settings.otx_api_key:
        hour = now.strftime(_BUCKET)
        rows.append(_row("otx", "requests", "hour", _counted(usage, "otx", hour, hour), OTX_HOURLY, resets_at=_window_end("hour", now), source="local", assumed=True))
    if settings.cloudflare_radar_api_key:
        rows.append(_header_row("cloudflare_radar", "requests", "5min", CLOUDFLARE_5MIN, headers.get("cloudflare_radar"), now))
    if settings.openrouter_api_key:
        rows += live.get("openrouter", {}).get("rows") or placeholder("openrouter")
    _mark_exceeded(rows, usage.get("exceeded", {}), now)
    rows.sort(key=lambda r: SERVICE_ORDER.index(r["service"]))
    fetched = [v.get("fetched_at") for v in live.values() if v.get("fetched_at")]
    return {"rows": rows, "fetched_at": max(fetched) if fetched else None}


# ---- on request: the quota endpoints of the services that have one ----

async def _get_json(url: str, headers: dict) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def _virustotal(now: datetime) -> list[dict]:
    # the key doubles as the user id in the path; the URL never appears in a message (errors are reduced to a status)
    key = settings.virustotal_api_key
    data = (await _get_json(f"https://www.virustotal.com/api/v3/users/{key}/overall_quotas", {"x-apikey": key}))["data"]
    rows = []
    for name, window in (("api_requests_hourly", "hour"), ("api_requests_daily", "day"), ("api_requests_monthly", "month")):
        quota = (data.get(name) or {}).get("user") or {}
        if "allowed" in quota:
            rows.append(_row("virustotal", "requests", window, quota.get("used", 0), quota["allowed"], resets_at=_window_end(window, now), seen_at=_iso(now)))
    return rows


async def _urlscan(now: datetime) -> list[dict]:
    limits = (await _get_json("https://urlscan.io/user/quotas/", {"API-Key": settings.urlscan_api_key}))["limits"]
    rows = []
    for action, scope in (("public", "scan_public"), ("unlisted", "scan_unlisted"), ("private", "scan_private"), ("search", "search"), ("retrieve", "retrieve")):
        day = (limits.get(action) or {}).get("day")
        if day:
            rows.append(_row("urlscan", scope, "day", day.get("used", 0), day.get("limit"), resets_at=day.get("reset"), seen_at=_iso(now)))
    return rows


async def _openrouter(now: datetime) -> list[dict]:
    data = (await _get_json("https://openrouter.ai/api/v1/key", {"Authorization": f"Bearer {settings.openrouter_api_key}"}))["data"]
    limit, remaining = data.get("limit"), data.get("limit_remaining")
    window = {"daily": "day", "weekly": "week", "monthly": "month"}.get(data.get("limit_reset"), "total")
    used = round(limit - remaining, 4) if limit is not None and remaining is not None else round(data.get("usage") or 0, 4)
    rows = [_row("openrouter", "credits", window, used, limit, unit="usd", seen_at=_iso(now))]
    free = data.get("free_model_daily_requests")
    if isinstance(free, dict) and free.get("limit") is not None:
        rows.append(_row("openrouter", "free_models", "day", free.get("used", 0), free["limit"], seen_at=_iso(now)))
    return rows


def _error_text(exc: Exception) -> str:
    """Status or exception type only: the raw text of an httpx error can contain the request URL."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__


async def refresh_live() -> dict[str, str]:
    """Asks VirusTotal, urlscan and OpenRouter for their quotas (none of these calls consumes quota) and stores the
    answer. Returns {service: error text} for the ones that failed; their previous data stays."""
    now = _now()
    jobs = {}
    if settings.virustotal_api_key:
        jobs["virustotal"] = _virustotal(now)
    if settings.urlscan_api_key:
        jobs["urlscan"] = _urlscan(now)
    if settings.openrouter_api_key:
        jobs["openrouter"] = _openrouter(now)
    results = await asyncio.gather(*jobs.values(), return_exceptions=True)
    usage = load_api_usage()
    errors: dict[str, str] = {}
    for service, result in zip(jobs, results, strict=True):
        if isinstance(result, Exception):
            errors[service] = _error_text(result)
            logging.getLogger(service if service != "openrouter" else "open_router").error(f"quota query failed: {errors[service]}")
        else:
            usage.setdefault("live", {})[service] = {"rows": result, "fetched_at": _iso(now)}
    save_api_usage(usage)
    return errors

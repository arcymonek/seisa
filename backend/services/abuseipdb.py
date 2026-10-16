from __future__ import annotations

import httpx

from backend.api_limits import int_header, observe
from backend.config import settings
from backend.i18n import t
from backend.models import ServiceResult
from backend.report_builder import ABUSEIPDB_CATEGORIES
from backend.services.base import IntelService

BASE_URL = "https://api.abuseipdb.com/api/v2"


class AbuseIpdbService(IntelService):
    name = "abuseipdb"
    supports_domain = False

    def is_configured(self) -> bool:
        return bool(settings.abuseipdb_api_key)

    def _headers(self) -> dict:
        return {"Key": settings.abuseipdb_api_key, "Accept": "application/json"}

    async def query_ip(self, ip: str) -> ServiceResult:
        if not self.is_configured():
            return self.not_configured_result()
        params = {"ipAddress": ip, "maxAgeInDays": 90, "verbose": ""}
        data, err = await self.fetch_json("GET", f"{BASE_URL}/check", headers=self._headers(), params=params)
        if err:
            return err

        d = data.get("data", {})
        reports = sorted(d.get("reports") or [], key=lambda r: r.get("reportedAt") or "", reverse=True)
        latest_report = None
        if reports:
            r = reports[0]
            reporter_id = r.get("reporterId")
            cat_ids = r.get("categories") or []
            categories_label = ", ".join(f"{c} ({ABUSEIPDB_CATEGORIES.get(c, t('svc.unknown_category'))})" for c in cat_ids)
            latest_report = {
                "reportedAt": r.get("reportedAt"),
                "comment": r.get("comment"),
                "categories": categories_label,
                "reporter_country": r.get("reporterCountryName"),
                "reporter_profile": f"https://www.abuseipdb.com/user/{reporter_id}" if reporter_id else None,
            }

        summary = {
            "abuse_confidence_score": d.get("abuseConfidenceScore"),
            "total_reports": d.get("totalReports"),
            "num_distinct_users": d.get("numDistinctUsers"),
            "is_whitelisted": d.get("isWhitelisted"),
            "is_tor": d.get("isTor"),
            "is_public": d.get("isPublic"),
            "country_code": d.get("countryCode"),
            "domain": d.get("domain"),
            "hostnames": d.get("hostnames"),
            "isp": d.get("isp"),
            "usage_type": d.get("usageType"),
            "last_reported_at": d.get("lastReportedAt"),
            "latest_report": latest_report,
        }
        return ServiceResult(service=self.name, status="ok", summary=summary, raw=data)

    async def query_domain(self, domain: str) -> ServiceResult:
        return self.not_applicable_result()

    async def submit_report(self, ip: str, categories: list[int], comment: str, timestamp: str) -> tuple[dict, dict]:
        """POST /report. Returns (response body, rate-limit info); an error status raises AbuseIpdbError."""
        payload = {
            "ip": ip,
            "categories": ",".join(str(c) for c in categories),
            "comment": comment,
            "timestamp": timestamp,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{BASE_URL}/report", headers=self._headers(), data=payload)
        observe(self.name, resp)
        rate_limit = parse_rate_limit(resp.headers)
        if resp.status_code >= 400:
            error = AbuseIpdbError(resp.status_code, api_error_detail(resp), rate_limit)
            self.logger.error(f"report rejected: HTTP {resp.status_code}: {error.detail}")
            raise error
        return resp.json(), rate_limit


class AbuseIpdbError(Exception):
    """An error answer of the AbuseIPDB API: the HTTP status, the detail text and the rate-limit headers."""

    def __init__(self, status: int, detail: str, rate_limit: dict | None = None):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail
        self.rate_limit = rate_limit or {}


def parse_rate_limit(headers) -> dict:
    """X-RateLimit-Limit / -Remaining / -Reset (epoch seconds) and Retry-After (seconds) of an API answer."""
    info = {
        "limit": int_header(headers, "X-RateLimit-Limit"),
        "remaining": int_header(headers, "X-RateLimit-Remaining"),
        "reset": int_header(headers, "X-RateLimit-Reset"),
        "retry_after": int_header(headers, "Retry-After"),
    }
    return {k: v for k, v in info.items() if v is not None}


def api_error_detail(resp: httpx.Response) -> str:
    """The `errors[].detail` texts of an AbuseIPDB error body (the API documents this shape), else the raw start."""
    try:
        errors = resp.json().get("errors") or []
        texts = [str(e.get("detail")) for e in errors if isinstance(e, dict) and e.get("detail")]
        if texts:
            return "; ".join(texts)
    except (ValueError, AttributeError):
        pass
    return resp.text[:300] or resp.reason_phrase

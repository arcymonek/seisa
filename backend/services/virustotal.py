from __future__ import annotations

from backend.config import settings
from backend.i18n import t
from backend.models import ServiceResult
from backend.ratelimit import RateLimitedDaily, vt_rate_limiter
from backend.services.base import IntelService

BASE_URL = "https://www.virustotal.com/api/v3"


class VirusTotalService(IntelService):
    name = "virustotal"

    def is_configured(self) -> bool:
        return bool(settings.virustotal_api_key)

    async def query_ip(self, ip: str, on_wait=None) -> ServiceResult:
        return await self._fetch(f"{BASE_URL}/ip_addresses/{ip}", on_wait=on_wait)

    async def query_domain(self, domain: str, on_wait=None) -> ServiceResult:
        return await self._fetch(f"{BASE_URL}/domains/{domain}", on_wait=on_wait)

    async def _fetch(self, url: str, on_wait=None) -> ServiceResult:
        if not self.is_configured():
            return self.not_configured_result()
        try:
            await vt_rate_limiter.acquire(on_wait=on_wait)
        except RateLimitedDaily:
            self.logger.warning("VirusTotal daily limit exceeded (500/day)")
            return ServiceResult(
                service=self.name,
                status="rate_limited_daily",
                summary={"message": t("svc.vt_daily_limit")},
            )

        headers = {"x-apikey": settings.virustotal_api_key}
        data, err = await self.fetch_json("GET", url, headers=headers)
        if err:
            return err

        attrs = data.get("data", {}).get("attributes", {})
        stats = attrs.get("last_analysis_stats", {})
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        # only engines that gave a verdict (without timeout/failure/type-unsupported)
        total = sum(stats.get(k, 0) for k in ("malicious", "suspicious", "harmless", "undetected"))
        summary = {
            "detection_ratio": f"{malicious + suspicious}/{total}" if total else t("svc.no_data"),
            "malicious": malicious,
            "suspicious": suspicious,
            "harmless": stats.get("harmless"),
            "undetected": stats.get("undetected"),
            "total_engines": total,
            "reputation": attrs.get("reputation"),
            "as_owner": attrs.get("as_owner"),
            "asn": attrs.get("asn"),
            "country": attrs.get("country"),
            "network": attrs.get("network"),
            "regional_internet_registry": attrs.get("regional_internet_registry"),
            "categories": attrs.get("categories"),
            "tags": attrs.get("tags"),
            "total_votes": attrs.get("total_votes"),
            "last_analysis_date": attrs.get("last_analysis_date"),
            "last_modification_date": attrs.get("last_modification_date"),
            "whois": attrs.get("whois"),
        }
        return ServiceResult(service=self.name, status="ok", summary=summary, raw=data)

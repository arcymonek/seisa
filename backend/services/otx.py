from __future__ import annotations

from backend.config import settings
from backend.models import ServiceResult
from backend.services.base import IntelService

BASE_URL = "https://otx.alienvault.com/api/v1/indicators"


class OtxService(IntelService):
    name = "otx"

    def is_configured(self) -> bool:
        return bool(settings.otx_api_key)

    async def query_ip(self, ip: str) -> ServiceResult:
        return await self._fetch(f"{BASE_URL}/IPv4/{ip}/general")

    async def query_domain(self, domain: str) -> ServiceResult:
        return await self._fetch(f"{BASE_URL}/domain/{domain}/general")

    async def _fetch(self, url: str) -> ServiceResult:
        if not self.is_configured():
            return self.not_configured_result()
        headers = {"X-OTX-API-KEY": settings.otx_api_key}
        data, err = await self.fetch_json("GET", url, headers=headers)
        if err:
            return err

        pulse_info = data.get("pulse_info", {})
        pulses = pulse_info.get("pulses", [])
        summary = {
            "indicator": data.get("indicator"),
            "type_title": data.get("type_title"),
            "pulse_count": pulse_info.get("count", 0),
            "pulse_names": [p.get("name") for p in pulses[:10]],
            "pulse_tags": sorted({t for p in pulses for t in (p.get("tags") or [])})[:15],
            "country": data.get("country_name"),
            "city": data.get("city"),
            "asn": data.get("asn"),
            "reputation": data.get("reputation"),
            "whois_url": data.get("whois"),
        }
        return ServiceResult(service=self.name, status="ok", summary=summary, raw=data)

from __future__ import annotations

from backend.config import settings
from backend.models import ServiceResult
from backend.services.base import IntelService

BASE_URL = "https://api.cloudflare.com/client/v4/radar"


class CloudflareRadarService(IntelService):
    name = "cloudflare_radar"

    def is_configured(self) -> bool:
        return bool(settings.cloudflare_radar_api_key)

    async def query_ip(self, ip: str) -> ServiceResult:
        return await self._fetch(f"{BASE_URL}/entities/ip", params={"ip": ip})

    async def query_domain(self, domain: str) -> ServiceResult:
        return await self._fetch(f"{BASE_URL}/entities/domains/{domain}")

    async def _fetch(self, url: str, params: dict | None = None) -> ServiceResult:
        if not self.is_configured():
            return self.not_configured_result()
        headers = {"Authorization": f"Bearer {settings.cloudflare_radar_api_key}"}
        data, err = await self.fetch_json("GET", url, headers=headers, params=params)
        if err:
            return err

        if not data.get("success", True):
            errors = data.get("errors")
            return self.error_result(f"Cloudflare Radar returned an error: {errors}")

        result = data.get("result", {})
        summary = {
            "network_context": result,
        }
        return ServiceResult(service=self.name, status="ok", summary=summary, raw=data)

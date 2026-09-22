from __future__ import annotations

from backend.config import settings
from backend.models import ServiceResult
from backend.services.base import IntelService

BASE_URL = "https://urlscan.io/api/v1/search/"


class UrlscanService(IntelService):
    name = "urlscan"

    def is_configured(self) -> bool:
        return bool(settings.urlscan_api_key)

    async def query_ip(self, ip: str) -> ServiceResult:
        return await self._search(f"page.ip:{ip}")

    async def query_domain(self, domain: str) -> ServiceResult:
        return await self._search(f"domain:{domain}")

    async def _search(self, query: str) -> ServiceResult:
        if not self.is_configured():
            return self.not_configured_result()
        headers = {"API-Key": settings.urlscan_api_key}
        params = {"q": query, "size": 100}
        data, err = await self.fetch_json("GET", BASE_URL, headers=headers, params=params)
        if err:
            return err

        results = data.get("results", [])
        scans = [
            {
                "url": r.get("page", {}).get("url"),
                "time": r.get("task", {}).get("time"),
                "result_url": r.get("result"),
                "country": r.get("page", {}).get("country"),
                "server": r.get("page", {}).get("server"),
                "asn": r.get("page", {}).get("asn"),
                "asnname": r.get("page", {}).get("asnname"),
            }
            for r in results
        ]
        summary = {
            "total_scans": data.get("total", len(results)),
            "scans": scans,
        }
        if not scans:
            summary["note"] = "Brak innych informacji"
        return ServiceResult(service=self.name, status="ok", summary=summary, raw=data)

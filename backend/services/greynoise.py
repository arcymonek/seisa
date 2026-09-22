from __future__ import annotations

import httpx

from backend.config import settings
from backend.models import ServiceResult
from backend.services.base import IntelService, describe_exception

BASE_URL = "https://api.greynoise.io/v3/community"


class GreyNoiseService(IntelService):
    name = "greynoise"
    supports_domain = False

    def is_configured(self) -> bool:
        return bool(settings.greynoise_api_key)

    async def query_ip(self, ip: str) -> ServiceResult:
        if not self.is_configured():
            return self.not_configured_result()
        headers = {"key": settings.greynoise_api_key, "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(f"{BASE_URL}/{ip}", headers=headers)
            if resp.status_code == 404:
                return ServiceResult(
                    service=self.name,
                    status="ok",
                    summary={"classification": "brak danych", "message": "brak danych w GreyNoise"},
                )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            return self.error_result(f"HTTP {exc.response.status_code}: {exc.response.text[:300]}")
        except httpx.HTTPError as exc:
            return self.error_result(describe_exception(exc))
        except ValueError as exc:
            return self.error_result(f"nieprawidłowa odpowiedź (nie JSON): {describe_exception(exc)}")

        summary = {
            "classification": data.get("classification", "unknown"),
            "noise": data.get("noise"),
            "riot": data.get("riot"),
            "name": data.get("name"),
            "link": data.get("link"),
            "last_seen": data.get("last_seen"),
            "message": data.get("message"),
        }
        return ServiceResult(service=self.name, status="ok", summary=summary, raw=data)

    async def query_domain(self, domain: str) -> ServiceResult:
        return self.not_applicable_result()

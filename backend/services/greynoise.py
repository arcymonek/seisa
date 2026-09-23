from __future__ import annotations

import httpx

from backend.config import settings
from backend.models import ServiceResult
from backend.services.base import IntelService, describe_exception

IP_URL = "https://api.greynoise.io/v3/ip"
COMMUNITY_URL = "https://api.greynoise.io/v3/community"

NO_DATA_MESSAGE = "brak informacji w usłudze"


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
                resp = await client.get(f"{IP_URL}/{ip}", headers=headers)
            if resp.status_code == 403:
                # Klucz bez dostępu do pełnego IP Lookup (wyższy poziom planu) -
                # spadamy na darmowy endpoint community zamiast zwracać błąd.
                return await self._query_community(ip, headers)
            if resp.status_code == 404:
                # W praktyce /v3/ip/{ip} zwraca 404 (nie found=false w 200), gdy
                # GreyNoise nie ma żadnych danych o tym adresie.
                return ServiceResult(
                    service=self.name,
                    status="ok",
                    summary={"has_data": False, "message": NO_DATA_MESSAGE},
                )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            return self.error_result(f"HTTP {exc.response.status_code}: {exc.response.text[:300]}")
        except httpx.HTTPError as exc:
            return self.error_result(describe_exception(exc))
        except ValueError as exc:
            return self.error_result(f"nieprawidłowa odpowiedź (nie JSON): {describe_exception(exc)}")

        summary = _ip_lookup_summary(data)
        return ServiceResult(service=self.name, status="ok", summary=summary, raw=data)

    async def _query_community(self, ip: str, headers: dict) -> ServiceResult:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(f"{COMMUNITY_URL}/{ip}", headers=headers)
            if resp.status_code == 404:
                return ServiceResult(
                    service=self.name,
                    status="ok",
                    summary={"has_data": False, "message": NO_DATA_MESSAGE},
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
            "has_data": True,
            "source": "community (klucz bez dostępu do pełnego IP Lookup /v3/ip)",
            "classification": data.get("classification"),
            "noise": data.get("noise"),
            "riot": data.get("riot"),
            "name": data.get("name"),
            "link": data.get("link"),
            "last_seen": data.get("last_seen"),
        }
        return ServiceResult(service=self.name, status="ok", summary=summary, raw=data)

    async def query_domain(self, domain: str) -> ServiceResult:
        return self.not_applicable_result()


def _ip_lookup_summary(data: dict) -> dict:
    """Pełny GET /v3/ip/{ip} (dokumentacja: https://docs.greynoise.io/reference/v3ip) -
    dużo bogatszy niż community: aktor, tagi, metadane sieciowe/geo, surowe dane
    skanowania (porty, JA3/JA4, User-Agent), plus Business Service Intelligence
    (czy to znana, legalna usługa - np. CDN/skaner wyszukiwarki)."""
    isi = data.get("internet_scanner_intelligence") or {}
    bsi = data.get("business_service_intelligence") or {}

    if not isi.get("found") and not bsi.get("found"):
        return {"has_data": False, "message": NO_DATA_MESSAGE}

    summary: dict = {"has_data": True}

    if bsi.get("found"):
        summary["business_service"] = {
            "name": bsi.get("name"),
            "category": bsi.get("category"),
            "description": bsi.get("description"),
            "trust_level": bsi.get("trust_level"),
            "reference": bsi.get("reference"),
        }

    if isi.get("found"):
        meta = isi.get("metadata") or {}
        raw_data = isi.get("raw_data") or {}
        ports = [f"{p.get('port')}/{p.get('protocol')}" for p in (raw_data.get("scan") or []) if p.get("port")]
        summary.update(
            {
                "classification": isi.get("classification"),
                "actor": isi.get("actor"),
                "first_seen": isi.get("first_seen"),
                "last_seen": isi.get("last_seen"),
                "spoofable": isi.get("spoofable"),
                "tor": isi.get("tor"),
                "vpn": isi.get("vpn"),
                "vpn_service": isi.get("vpn_service"),
                "cves": isi.get("cves"),
                "tags": [t.get("name") for t in (isi.get("tags") or []) if t.get("name")],
                "organization": meta.get("organization"),
                "asn": meta.get("asn"),
                "rdns": meta.get("rdns"),
                "os": meta.get("os"),
                "category": meta.get("category"),
                "location": ", ".join(filter(None, [meta.get("source_city"), meta.get("source_country")])) or None,
                "datacenter": meta.get("datacenter"),
                "scanned_ports": ports or None,
                "destination_countries": meta.get("destination_countries"),
            }
        )

    return {k: v for k, v in summary.items() if v not in (None, "", [], {})}

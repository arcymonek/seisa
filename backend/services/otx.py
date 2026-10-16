"""AlienVault OTX client (IP and domain pulses), built on IntelService. Registered in aggregator.py and used by the
Lookup tab; needs OTX_API_KEY.
"""
from __future__ import annotations

from datetime import datetime, timezone

from backend.config import settings
from backend.models import ServiceResult
from backend.services.base import IntelService

BASE_URL = "https://otx.alienvault.com/api/v1/indicators"


class OtxService(IntelService):
    name = "otx"

    def is_configured(self) -> bool:
        return bool(settings.otx_api_key)

    async def query_ip(self, ip: str) -> ServiceResult:
        # the OTX documentation names the path by address family: IPv4 or IPv6
        family = "IPv6" if ":" in ip else "IPv4"
        return await self._fetch(f"{BASE_URL}/{family}/{ip}/general")

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
        now = datetime.now(timezone.utc)

        def age_days(pulse: dict) -> float | None:
            raw = pulse.get("modified") or pulse.get("created")
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                return None
            return (now - (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))).total_seconds() / 86400

        def enriched(pulse: dict) -> bool:
            return bool(pulse.get("adversary") or pulse.get("malware_families") or pulse.get("attack_ids"))

        related = (pulse_info.get("related") or {})
        related_flat = [related.get("alienvault") or {}, related.get("other") or {}]
        adversaries = sorted({a for r in related_flat for a in (r.get("adversary") or [])} | {p["adversary"] for p in pulses if p.get("adversary")})
        malware = sorted({m for r in related_flat for m in (r.get("malware_families") or [])} | {m if isinstance(m, str) else (m.get("display_name") or m.get("id") or "") for p in pulses for m in (p.get("malware_families") or [])})
        attack_ids = sorted({a if isinstance(a, str) else (a.get("id") or "") for p in pulses for a in (p.get("attack_ids") or [])})
        dates = sorted(str(p.get("modified") or p.get("created")) for p in pulses if p.get("modified") or p.get("created"))
        summary = {
            "indicator": data.get("indicator"),
            "type_title": data.get("type_title"),
            "pulse_count": pulse_info.get("count", 0),
            "recent_pulse_count": sum(1 for p in pulses if (age_days(p) or 0) <= 90),
            "enriched_pulse_count": sum(1 for p in pulses if enriched(p)),
            "latest_pulse_modified": dates[-1] if dates else None,
            "adversaries": adversaries,
            "malware_families": [m for m in malware if m],
            "attack_ids": [a for a in attack_ids if a],
            "validation": data.get("validation"),
            "false_positive": data.get("false_positive"),
            "pulse_names": [p.get("name") for p in pulses[:10]],
            "pulse_tags": sorted({t for p in pulses for t in (p.get("tags") or [])})[:15],
            "country": data.get("country_name"),
            "country_code": data.get("country_code"),
            "city": data.get("city"),
            "asn": data.get("asn"),
            "reputation": data.get("reputation"),
            "whois_url": data.get("whois"),
        }
        return ServiceResult(service=self.name, status="ok", summary=summary, raw=data)

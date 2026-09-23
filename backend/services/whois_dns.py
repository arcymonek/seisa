from __future__ import annotations

import asyncio
import socket

import whois

from backend.models import ServiceResult
from backend.services.base import IntelService

RDAP_BOOTSTRAP = "https://rdap.org/ip/{ip}"


class WhoisDnsService(IntelService):
    name = "whois_rdns"

    def is_configured(self) -> bool:
        return True

    async def query_ip(self, ip: str) -> ServiceResult:
        rdns = None
        try:
            rdns = await asyncio.to_thread(self._reverse_dns, ip)
        except Exception as exc:
            self.logger.error(f"reverse DNS nie powiódł się: {exc}")

        # rdap.org jest bootstrapem - zawsze przekierowuje (302) do właściwego RIR
        # (RIPE/ARIN/APNIC/LACNIC/AFRINIC), więc trzeba jawnie podążać za redirectem.
        rdap_data, err = await self.fetch_json("GET", RDAP_BOOTSTRAP.format(ip=ip), follow_redirects=True)
        summary = {"reverse_dns": rdns or "brak rekordu PTR"}
        if rdap_data:
            summary.update(_rdap_summary(rdap_data))
        elif err:
            summary["rdap_error"] = err.error_message

        return ServiceResult(
            service=self.name,
            status="ok",
            summary=summary,
            raw={"rdap": rdap_data} if rdap_data else None,
        )

    async def query_domain(self, domain: str) -> ServiceResult:
        try:
            data = await asyncio.to_thread(whois.whois, domain)
        except Exception as exc:
            return self.error_result(str(exc))
        summary = {
            "registrar": _first(data.get("registrar")),
            "creation_date": _stringify(_first(data.get("creation_date"))),
            "expiration_date": _stringify(_first(data.get("expiration_date"))),
            "name_servers": data.get("name_servers"),
            "status": data.get("status"),
            "emails": data.get("emails"),
        }
        return ServiceResult(service=self.name, status="ok", summary=summary, raw=dict(data))

    @staticmethod
    def _reverse_dns(ip: str) -> str | None:
        try:
            return socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror):
            return None


def _vcard_value(vcard_array, key: str) -> str | None:
    """jCard (RFC 7095) - vcardArray to ["vcard", [[nazwa, {}, typ, wartość], ...]]."""
    if not vcard_array or len(vcard_array) < 2:
        return None
    for entry in vcard_array[1]:
        if len(entry) >= 4 and entry[0] == key:
            value = entry[3]
            if isinstance(value, list):
                return ", ".join(str(v) for v in value if v)
            return str(value) if value else None
    return None


def _rdap_summary(data: dict) -> dict:
    """RDAP (RFC 9083) zastępuje klasyczne WHOIS dla adresów IP - ten sam rodzaj
    danych (zakres sieci, właściciel, kontakt abuse), ale jako ustandaryzowane
    zapytanie HTTP/JSON zamiast nieustandaryzowanego protokołu WHOIS po porcie 43,
    z automatycznym przekierowaniem do właściwego RIR (ARIN/RIPE/APNIC/LACNIC/AFRINIC)
    przez bootstrap rdap.org."""
    org = None
    abuse_contact = None
    tech_contact = None
    for entity in data.get("entities") or []:
        vcard = entity.get("vcardArray")
        roles = entity.get("roles") or []
        name = _vcard_value(vcard, "fn")
        email = _vcard_value(vcard, "email")
        if not org and ("registrant" in roles or "administrative" in roles):
            org = name or entity.get("handle")
        if "abuse" in roles and (email or name):
            abuse_contact = email or name
        if "technical" in roles and (email or name):
            tech_contact = email or name

    events = {e.get("eventAction"): e.get("eventDate") for e in (data.get("events") or [])}
    remarks = [
        " ".join(r.get("description") or [])
        for r in (data.get("remarks") or [])
        if r.get("description")
    ]

    summary = {
        "network_handle": data.get("handle"),
        "network_name": data.get("name"),
        "network_range": " - ".join(filter(None, [data.get("startAddress"), data.get("endAddress")])) or None,
        "ip_version": data.get("ipVersion"),
        "network_type": data.get("type"),
        "country": data.get("country"),
        "parent_network_handle": data.get("parentHandle"),
        "organization": org,
        "abuse_contact": abuse_contact,
        "technical_contact": tech_contact,
        "registered": events.get("registration"),
        "last_changed": events.get("last changed"),
        "remarks": remarks or None,
    }
    return {k: v for k, v in summary.items() if v not in (None, "", [], {})}


def _first(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _stringify(value):
    return str(value) if value is not None else None

"""WHOIS, reverse DNS and RDAP lookups, built on IntelService. Needs no API key. Used by the IP tab (lookup) for
the owner, network and domain-age facts and by the DMARC tab for the registration data of a sending address.
The WHOIS query has its own time limit because the library does not enforce one.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import whois

from backend.models import ServiceResult
from backend.services.base import IntelService, describe_exception
from backend.services.dns_records import resolve_domain, reverse_lookup

RDAP_BOOTSTRAP = "https://rdap.org/ip/{ip}"
WHOIS_TIMEOUT = 15  # seconds; the whois library has no timeout of its own that covers a silent server


def _first_line(text: str, limit: int = 200) -> str:
    """The first line of a long message, cut to `limit` characters. A failed WHOIS query often carries the whole
    notice of the registry (kilobytes of terms of use) - one line says what happened."""
    return (text.strip().splitlines() or [""])[0][:limit]


class WhoisDnsService(IntelService):
    name = "whois_rdns"

    def is_configured(self) -> bool:
        return True

    async def query_ip(self, ip: str) -> ServiceResult:
        rdns = None
        try:
            rdns = await reverse_lookup(ip)
        except Exception as exc:
            self.logger.error(f"reverse DNS failed: {exc}")

        # rdap.org is a bootstrap - it always redirects (302) to the right RIR
        # (RIPE/ARIN/APNIC/LACNIC/AFRINIC), so the redirect has to be followed explicitly.
        rdap_data, err = await self.fetch_json("GET", RDAP_BOOTSTRAP.format(ip=ip), follow_redirects=True)
        # None = no PTR record; the reports say so in the language of the reader (a stored text would stay in the
        # language of the request that made it)
        summary = {"reverse_dns": rdns}
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
        """WHOIS (registration data) and DNS records side by side; a failure of one still gives the other."""
        whois_data, dns_data = await asyncio.gather(
            # a thread cannot be cancelled: after the timeout it runs on in the background and its answer is dropped
            asyncio.wait_for(asyncio.to_thread(whois.whois, domain), timeout=WHOIS_TIMEOUT),
            resolve_domain(domain),
            return_exceptions=True,
        )
        if isinstance(dns_data, BaseException):
            self.logger.error(f"DNS resolution failed: {dns_data}")
            dns_data = None
        if isinstance(whois_data, BaseException):
            if not dns_data:
                return self.error_result(str(whois_data) or describe_exception(whois_data))
            # DNS works, so this is a partial result, not a failure; the registry's notice goes to the log in one line
            self.logger.warning(f"WHOIS failed: {_first_line(str(whois_data) or describe_exception(whois_data))}")
            whois_data = {}
        created = _stringify(_first(whois_data.get("creation_date")))
        summary = {
            "registrar": _first(whois_data.get("registrar")),
            "creation_date": created,
            "domain_age_days": _age_days(_first(whois_data.get("creation_date"))),
            "expiration_date": _stringify(_first(whois_data.get("expiration_date"))),
            "name_servers": whois_data.get("name_servers"),
            "status": whois_data.get("status"),
            "emails": whois_data.get("emails"),
            "dns": dns_data,
        }
        return ServiceResult(service=self.name, status="ok", summary=summary, raw=dict(whois_data) | {"dns": dns_data})


def _vcard_value(vcard_array, key: str) -> str | None:
    """jCard (RFC 7095) - vcardArray is ["vcard", [[name, {}, type, value], ...]]."""
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
    """RDAP (RFC 9083) replaces the classic WHOIS for IP addresses - the same kind of data (network range,
    owner, abuse contact), but as a standardised HTTP/JSON query instead of the non-standardised WHOIS protocol
    on port 43, with automatic redirection to the right RIR (ARIN/RIPE/APNIC/LACNIC/AFRINIC) through the
    rdap.org bootstrap."""
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


def _age_days(created) -> int | None:
    """Days since the registration date; whois returns a datetime or (for some registries) a string."""
    if isinstance(created, str):
        try:
            created = datetime.fromisoformat(created.strip()[:19])
        except ValueError:
            return None
    if not isinstance(created, datetime):
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - created).days)


def _stringify(value):
    return str(value) if value is not None else None

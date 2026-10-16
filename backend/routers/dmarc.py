"""DMARC tab: the optional "geo" lookup of one source IP. The report itself is parsed in the browser; only this click
asks the backend, which queries RDAP and reverse DNS (the same service as the IP tab), so the browser never contacts a
third party."""
from __future__ import annotations

import asyncio
import ipaddress

from fastapi import APIRouter, HTTPException

from backend.aggregator import SERVICE_REGISTRY
from backend.i18n import t
from backend.known_senders import match_known_sender, resolve_host_ips

router = APIRouter()


@router.get("/geo")
async def geo(ip: str):
    """Registration data of the address block from RDAP (country, organisation, network name; no ASN) and the reverse
    DNS name. A well-known sender is reported only when the reverse DNS name is forward-confirmed."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail=t("lookup.invalid_indicator", indicator=ip[:80])) from None
    if not address.is_global:
        raise HTTPException(status_code=400, detail=t("lookup.invalid_indicator", indicator=ip[:80]))
    result = await SERVICE_REGISTRY["whois_rdns"].query_ip(str(address))
    s = result.summary or {}
    rdns = s.get("reverse_dns")  # None = no PTR record
    rdap_ok = "rdap_error" not in s and any(s.get(k) for k in ("country", "organization", "network_name"))
    if result.status != "ok" or not (rdap_ok or rdns):
        return {"status": "unavailable"}
    known_sender = None
    if rdns and match_known_sender(rdns):
        ips = await asyncio.to_thread(resolve_host_ips, rdns)
        if str(address) in {str(ipaddress.ip_address(x)) for x in ips if _is_ip(x)}:
            known_sender = match_known_sender(rdns)
    return {
        "status": "ok",
        "country": s.get("country"),
        "organization": s.get("organization"),
        "network_name": s.get("network_name"),
        "reverse_dns": rdns,
        "known_sender": known_sender,
    }


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value.split("%")[0])
        return True
    except ValueError:
        return False

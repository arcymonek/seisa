"""DMARC tab: the optional "geo" lookup of one source IP. The report itself is parsed in the browser; only this click
asks the backend, which queries RDAP (the same service as the IP tab), so the browser never contacts a third party."""
from __future__ import annotations

import ipaddress

from fastapi import APIRouter, HTTPException

from backend.aggregator import SERVICE_REGISTRY
from backend.i18n import t

router = APIRouter()


@router.get("/geo")
async def geo(ip: str):
    """Registration data of the address block from RDAP: country, organisation and network name (no ASN)."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail=t("lookup.invalid_indicator", indicator=ip[:80])) from None
    if not address.is_global:
        raise HTTPException(status_code=400, detail=t("lookup.invalid_indicator", indicator=ip[:80]))
    result = await SERVICE_REGISTRY["whois_rdns"].query_ip(str(address))
    s = result.summary or {}
    if result.status != "ok" or "rdap_error" in s or not any(s.get(k) for k in ("country", "organization", "network_name")):
        return {"status": "unavailable"}
    return {
        "status": "ok",
        "country": s.get("country"),
        "organization": s.get("organization"),
        "network_name": s.get("network_name"),
    }

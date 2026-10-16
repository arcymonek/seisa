"""DNS records of a domain (A, AAAA, NS, MX, CAA, SPF, DMARC) resolved with the system's resolver - no third-party
service is involved; the answers are what any client would get."""
from __future__ import annotations

import asyncio
import logging
import secrets

import dns.asyncresolver
import dns.exception
import dns.resolver
import dns.reversename

logger = logging.getLogger("dns_records")
QUERY_TIMEOUT = 5.0


def _resolver() -> dns.asyncresolver.Resolver:
    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = QUERY_TIMEOUT
    resolver.timeout = QUERY_TIMEOUT
    return resolver


async def _query(name: str, rdtype: str) -> tuple[list[str], bool]:
    """(answers as text, nxdomain) - a missing record or a timeout is an empty answer, not an error."""
    try:
        answer = await _resolver().resolve(name, rdtype)
    except dns.resolver.NXDOMAIN:
        return [], True
    except (dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout, dns.exception.DNSException) as exc:
        logger.debug("%s %s: %s", rdtype, name, exc)
        return [], False
    return [r.to_text() for r in answer], False


async def reverse_lookup(ip: str) -> str | None:
    """The PTR name of an address without the trailing dot, or None when it has no PTR record (or the lookup times
    out - the same limit as every other query here). The first answer is used, like gethostbyaddr() did."""
    try:
        name = dns.reversename.from_address(ip)
    except (dns.exception.DNSException, ValueError):
        return None
    answers, _gone = await _query(str(name), "PTR")
    return answers[0].rstrip(".") if answers else None


def _txt(values: list[str]) -> list[str]:
    """TXT rdata come quoted and possibly split in 255-byte chunks: '"v=spf1 " "-all"' -> 'v=spf1 -all'."""
    return ["".join(part.strip('"') for part in v.split('" "')).strip('"') for v in values]


async def resolve_domain(domain: str) -> dict:
    host = domain.rstrip(".")
    probe = f"seisa-{secrets.token_hex(6)}.{host}"
    (a, nx), (aaaa, _), (ns, _), (mx, _), (caa, _), (txt, _), (dmarc, _), (wild, _) = await asyncio.gather(
        _query(host, "A"), _query(host, "AAAA"), _query(host, "NS"), _query(host, "MX"), _query(host, "CAA"),
        _query(host, "TXT"), _query(f"_dmarc.{host}", "TXT"), _query(probe, "A"),
    )
    ns_hosts = sorted(n.rstrip(".").lower() for n in ns)
    # A delegation to a name server whose own name does not exist ("dangling" NS): the zone cannot be resolved through
    # it, and whoever registers that name takes the zone over. Only NXDOMAIN counts - a timeout proves nothing.
    ns_gone = [h for h, (_, gone) in zip(ns_hosts, await asyncio.gather(*(_query(h, "A") for h in ns_hosts)), strict=True) if gone]
    spf = [v for v in _txt(txt) if v.lower().startswith("v=spf1")]
    dmarc_records = [v for v in _txt(dmarc) if v.lower().startswith("v=dmarc1")]
    summary = {
        "exists": not nx,
        "a": sorted(a),
        "aaaa": sorted(aaaa),
        "ns": ns_hosts,
        "ns_missing": ns_gone,
        # "0 ." is the null MX of a domain that takes no mail: no host to list
        "mx": [h for h in (m.split(None, 1)[-1].rstrip(".").lower() for m in sorted(mx, key=lambda m: int(m.split()[0]) if m.split()[0].isdigit() else 0)) if h],
        "caa": sorted(caa),
        "spf": spf[0] if spf else None,
        "dmarc": dmarc_records[0] if dmarc_records else None,
        "wildcard": bool(wild),
    }
    return {k: v for k, v in summary.items() if v not in (None, "", [])} | {"exists": not nx}

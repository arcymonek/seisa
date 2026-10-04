"""Merged identity of an IP address: ASN, owner, country, network - collected from every source that reports it.

The sources disagree more often than one would think, mostly for harmless reasons (a different spelling of the same
owner, a registry country vs a geolocation country, a network range reported at a different granularity). So every
value is first normalised (ASN -> number, country -> ISO code, owner -> set of significant words, ranges -> CIDR),
values that mean the same are grouped, and each field then gets a status:

- single:   only one source reported it (nothing to compare);
- agree:    two or more sources, one value;
- majority: several values, but one has strictly more sources - the majority value is shown;
- conflict: several values and no majority - the value of the highest-priority source is shown, flagged as unresolved.

The priority only breaks ties (RDAP is the registry itself, so it ranks first for registration data); it never
overrides a majority. The result is display-only: the reputation score does not depend on it.
"""
from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from backend.i18n import t
from backend.models import Identity, IdentityField, IdentityVariant, ServiceResult

# Highest priority first. Only sources that report the field are listed.
PRIORITY = {
    "asn": ("virustotal", "cloudflare_radar", "greynoise", "otx"),
    "organization": ("whois_rdns", "virustotal", "greynoise", "abuseipdb", "cloudflare_radar"),
    "country_location": ("abuseipdb", "virustotal", "greynoise", "otx", "cloudflare_radar"),
    "country_registration": ("whois_rdns",),
    "network": ("whois_rdns", "virustotal"),
    "network_name": ("whois_rdns",),
    "abuse_contact": ("whois_rdns",),
    "rdns": ("whois_rdns", "greynoise"),
    "usage_type": ("abuseipdb",),
    "tor": ("greynoise", "abuseipdb"),
}
FIELD_ORDER = tuple(PRIORITY)

# The same for a domain. "dns" is not a service: it stands for the records resolved by backend/services/dns_records.py
# (stored in the summary of whois_rdns).
DOMAIN_PRIORITY = {
    "registrar": ("whois_rdns",),
    "domain_created": ("whois_rdns",),
    "domain_age": ("whois_rdns",),
    "domain_expires": ("whois_rdns",),
    "domain_status": ("whois_rdns",),
    "nameservers": ("dns", "whois_rdns"),
    "addresses": ("dns",),
    "mx": ("dns",),
    "spf": ("dns",),
    "dmarc": ("dns",),
    "caa": ("dns",),
    "category": ("virustotal", "cloudflare_radar"),
    "popularity": ("cloudflare_radar",),
}

# Legal-form suffixes and filler words that say nothing about who the owner is.
_ORG_NOISE = frozenset(
    ["ltd", "limited", "llc", "llp", "lp", "inc", "incorporated", "corp", "corporation", "co", "company", "gmbh", "bv", "sa", "srl", "sas", "sarl", "ag", "plc", "pty", "pte", "kft", "oy", "ab", "as", "zoo", "sp", "the"]
)
_HOSTNAME = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+")


@dataclass(frozen=True)
class _Candidate:
    source: str
    display: str
    key: Any


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _asn(value: Any) -> tuple[str, int] | None:
    m = re.search(r"\d+", str(value or ""))
    return (f"AS{int(m.group())}", int(m.group())) if m else None


def _country(value: Any) -> str | None:
    code = str(value or "").strip().upper()
    return code if re.fullmatch(r"[A-Z]{2}", code) else None


def _org_tokens(name: str) -> frozenset[str]:
    words = re.findall(r"\w+", name.lower())
    return frozenset([w for w in words if w not in _ORG_NOISE] or words)


def _org_related(a: frozenset[str], b: frozenset[str]) -> bool:
    if not a or not b:
        return False
    return a <= b or b <= a or len(a & b) / len(a | b) >= 0.5


def _range_networks(text: Any) -> tuple:
    """RDAP 'start - end' -> the CIDR blocks covering exactly that range."""
    try:
        start, end = (ipaddress.ip_address(part.strip()) for part in str(text).split(" - "))
        return tuple(ipaddress.summarize_address_range(start, end))
    except ValueError:
        return ()


def _cidr_networks(text: Any) -> tuple:
    try:
        return (ipaddress.ip_network(str(text).strip(), strict=False),)
    except ValueError:
        return ()


def _networks_related(a: tuple, b: tuple) -> bool:
    """The same block, or one containing the other - reported at a different granularity, not a disagreement."""
    try:
        return any(x.overlaps(y) for x in a for y in b)
    except TypeError:  # IPv4 vs IPv6
        return False


def _networks_text(nets: tuple, raw: str) -> str:
    return ", ".join(str(n) for n in nets) if 0 < len(nets) <= 3 else raw


def _equal(a: Any, b: Any) -> bool:
    return a == b


def _ok_summary(results: dict[str, ServiceResult], name: str) -> dict[str, Any]:
    res = results.get(name)
    return res.summary if res is not None and res.status == "ok" else {}


def _cloudflare_ip(results: dict[str, ServiceResult]) -> dict[str, Any]:
    ctx = _ok_summary(results, "cloudflare_radar").get("network_context")
    ctx = ctx if isinstance(ctx, dict) else {}
    inner = ctx.get("ip")
    return inner if isinstance(inner, dict) else ctx


def _collect(results: dict[str, ServiceResult]) -> dict[str, list[_Candidate]]:
    found: dict[str, list[_Candidate]] = {k: [] for k in FIELD_ORDER}

    def add(field: str, source: str, display: str | None, key: Any) -> None:
        if display and key:
            found[field].append(_Candidate(source, display, key))

    whois = _ok_summary(results, "whois_rdns")
    vt = _ok_summary(results, "virustotal")
    abuse = _ok_summary(results, "abuseipdb")
    grey = _ok_summary(results, "greynoise")
    otx = _ok_summary(results, "otx")
    cf = _cloudflare_ip(results)

    for source, raw in (("virustotal", vt.get("asn")), ("cloudflare_radar", cf.get("asn")),
                        ("greynoise", grey.get("asn")), ("otx", otx.get("asn"))):
        parsed = _asn(raw)
        if parsed:
            add("asn", source, parsed[0], parsed[1])

    for source, raw in (("whois_rdns", whois.get("organization")), ("virustotal", vt.get("as_owner")),
                        ("greynoise", grey.get("organization")), ("abuseipdb", abuse.get("isp")),
                        ("cloudflare_radar", cf.get("asnOrgName") or cf.get("asnName"))):
        name = _text(raw)
        if name:
            add("organization", source, name, _org_tokens(name))

    for source, raw in (("abuseipdb", abuse.get("country_code")), ("virustotal", vt.get("country")),
                        ("greynoise", grey.get("country_code")), ("otx", otx.get("country_code")),
                        ("cloudflare_radar", cf.get("location"))):
        code = _country(raw)
        if code:
            add("country_location", source, code, code)
    code = _country(whois.get("country"))
    if code:
        add("country_registration", "whois_rdns", code, code)

    if whois.get("network_range"):
        nets = _range_networks(whois["network_range"])
        add("network", "whois_rdns", _networks_text(nets, str(whois["network_range"])), nets)
    if vt.get("network"):
        nets = _cidr_networks(vt["network"])
        add("network", "virustotal", _networks_text(nets, str(vt["network"])), nets)

    for field, source, raw in (("network_name", "whois_rdns", whois.get("network_name")),
                               ("abuse_contact", "whois_rdns", whois.get("abuse_contact")),
                               ("usage_type", "abuseipdb", abuse.get("usage_type"))):
        text = _text(raw)
        add(field, source, text, text and text.lower())

    for source, raw in (("whois_rdns", whois.get("reverse_dns")), ("greynoise", grey.get("rdns"))):
        host = _text(raw)
        if host and _HOSTNAME.fullmatch(host.rstrip(".")):  # the 'no PTR record' placeholder is not a host name
            add("rdns", source, host.rstrip("."), host.rstrip(".").lower())

    for source, raw in (("greynoise", grey.get("tor")), ("abuseipdb", abuse.get("is_tor"))):
        if isinstance(raw, bool):
            add("tor", source, t("common.yes") if raw else t("common.no"), "yes" if raw else "no")
    if not any(c.key == "yes" for c in found["tor"]):
        found["tor"] = []  # 'not a Tor node' everywhere is the normal case, not worth a row

    return found


_RELATED: dict[str, Callable[[Any, Any], bool]] = {
    "organization": _org_related,
    "network": _networks_related,
    "category": lambda a, b: bool(a & b),  # the sources name categories differently: one shared word is enough
}


def _resolve(field: str, candidates: list[_Candidate]) -> IdentityField | None:
    if not candidates:
        return None
    order = PRIORITY.get(field) or DOMAIN_PRIORITY[field]
    ranked = sorted(candidates, key=lambda c: order.index(c.source))
    related = _RELATED.get(field, _equal)

    groups: list[list[_Candidate]] = []
    for cand in ranked:
        for group in groups:
            if related(cand.key, group[0].key):
                group.append(cand)
                break
        else:
            groups.append([cand])
    groups.sort(key=lambda g: -len(g))  # stable: on equal size the group with the best-priority source stays first

    if len(groups) == 1:
        status = "agree" if len(groups[0]) > 1 else "single"
    elif len(groups[0]) > len(groups[1]):
        status = "majority"
    else:
        status = "conflict"
    top = groups[0]
    return IdentityField(
        key=field,
        value=top[0].display,
        status=status,
        agree=len(top),
        total=len(ranked),
        variants=[IdentityVariant(value=g[0].display, sources=[c.source for c in g]) for g in groups],
    )


def build_identity(results: dict[str, ServiceResult]) -> Identity:
    found = _collect(results)
    fields = [f for f in (_resolve(key, found[key]) for key in FIELD_ORDER) if f]
    by_key = {f.key: f for f in fields}
    notes: list[str] = []
    registration, location = by_key.get("country_registration"), by_key.get("country_location")
    if registration and location and registration.value != location.value:
        notes.append(t("identity.note_reg_loc", registration=registration.value, location=location.value))
    return Identity(fields=fields, notes=notes)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple, set)) else [value]
    return [str(v).strip() for v in items if str(v).strip()]


def _collect_domain(results: dict[str, ServiceResult]) -> dict[str, list[_Candidate]]:
    found: dict[str, list[_Candidate]] = {k: [] for k in DOMAIN_PRIORITY}

    def add(field: str, source: str, display: str | None, key: Any = None) -> None:
        if display:
            found[field].append(_Candidate(source, display, key if key is not None else display.lower()))

    whois = _ok_summary(results, "whois_rdns")
    dns = whois.get("dns") or {}
    vt = _ok_summary(results, "virustotal")
    cf = _ok_summary(results, "cloudflare_radar")

    add("registrar", "whois_rdns", _text(whois.get("registrar")))
    add("domain_created", "whois_rdns", (_text(whois.get("creation_date")) or "")[:10])
    if whois.get("domain_age_days") is not None:
        add("domain_age", "whois_rdns", str(whois["domain_age_days"]))
    add("domain_expires", "whois_rdns", (_text(whois.get("expiration_date")) or "")[:10])
    statuses = sorted({s.split()[0] for s in _as_list(whois.get("status"))})
    add("domain_status", "whois_rdns", ", ".join(statuses))

    for source, names in (("dns", dns.get("ns")), ("whois_rdns", whois.get("name_servers"))):
        hosts = sorted({n.rstrip(".").lower() for n in _as_list(names)})
        add("nameservers", source, ", ".join(hosts), frozenset(hosts))

    add("addresses", "dns", ", ".join(_as_list(dns.get("a")) + _as_list(dns.get("aaaa"))))
    add("mx", "dns", ", ".join(_as_list(dns.get("mx"))))
    add("spf", "dns", _text(dns.get("spf")))
    add("dmarc", "dns", _text(dns.get("dmarc")))
    add("caa", "dns", ", ".join(_as_list(dns.get("caa"))))

    for source, names in (("virustotal", list((vt.get("categories") or {}).values())), ("cloudflare_radar", cf.get("categories"))):
        words = sorted({str(n).strip().lower() for n in _as_list(names)})
        add("category", source, ", ".join(words), frozenset(w for n in words for w in re.findall(r"\w+", n)))

    if cf.get("rank") is not None:
        add("popularity", "cloudflare_radar", f"#{cf['rank']}")
    elif cf.get("bucket"):
        bucket = str(cf["bucket"])
        add("popularity", "cloudflare_radar", t("identity.popularity_top", n=bucket) if bucket.isdigit() else bucket)
    return found


def build_domain_identity(results: dict[str, ServiceResult]) -> Identity:
    """Who stands behind a domain: registration (WHOIS), delegation and records (DNS), category and popularity, merged
    by the same rules as the identity of an IP address (nameservers from WHOIS and DNS and the categories from
    VirusTotal and Cloudflare are the fields that can really disagree)."""
    found = _collect_domain(results)
    fields = [f for f in (_resolve(key, found[key]) for key in DOMAIN_PRIORITY) if f]
    notes: list[str] = []
    dns = _ok_summary(results, "whois_rdns").get("dns") or {}
    if dns and dns.get("exists") is False:
        notes.append(t("identity.note_nxdomain"))
    if dns.get("ns_missing"):
        notes.append(t("identity.note_ns_missing", hosts=", ".join(dns["ns_missing"])))
    if dns.get("wildcard"):
        notes.append(t("identity.note_wildcard"))
    return Identity(fields=fields, notes=notes)

from __future__ import annotations

import asyncio
import ipaddress
import re
from urllib.parse import quote

from backend.i18n import t
from backend.identity import build_domain_identity, build_identity
from backend.markdown_report import build_markdown
from backend.models import IndicatorType, LookupResult, ServiceResult
from backend.scoring import compute_risk_score
from backend.services.abuseipdb import AbuseIpdbService
from backend.services.base import describe_exception
from backend.services.cloudflare_radar import CloudflareRadarService
from backend.services.greynoise import GreyNoiseService
from backend.services.otx import OtxService
from backend.services.virustotal import VirusTotalService
from backend.services.whois_dns import WhoisDnsService

SERVICE_REGISTRY = {
    "whois_rdns": WhoisDnsService(),
    "cloudflare_radar": CloudflareRadarService(),
    "otx": OtxService(),
    "abuseipdb": AbuseIpdbService(),
    "virustotal": VirusTotalService(),
    "greynoise": GreyNoiseService(),
}


_DOMAIN_RE = re.compile(r"(?:[\w-]{1,63}\.)+[\w-]{1,63}\.?")


def is_valid_indicator(indicator: str, indicator_type: IndicatorType) -> bool:
    """The indicator ends up in URL paths of the intel services, so only a real IP address or a plain host name is
    accepted (no slashes, colons, dots-only labels, whitespace)."""
    if indicator_type == "ip":
        try:
            ipaddress.ip_address(indicator)
        except ValueError:
            return False
        return True
    return len(indicator) <= 253 and _DOMAIN_RE.fullmatch(indicator) is not None


_DEFANG = (("hxxp", "http"), ("[.]", "."), ("(.)", "."), ("{.}", "."), ("[dot]", "."), ("(dot)", "."), ("[:]", ":"), ("[@]", "@"))
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_PORT_RE = re.compile(r":\d{1,5}$")


def normalize_indicator(raw: str) -> str:
    """What the user typed -> the bare IP address or host name: a pasted URL (`https://Example.com:8080/a?b#c`), a
    defanged indicator (`hxxps://evil[.]example`, `1[.]2[.]3[.]4`), `ip:port`, `user@host`, an IPv6 in brackets,
    a trailing dot and upper case are all reduced to `example.com` / `1.2.3.4`. Whatever remains is still checked by
    is_valid_indicator, which is what keeps odd input out of the URL paths of the services."""
    text = raw.strip()
    for old, new in _DEFANG:
        text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
    text = _SCHEME_RE.sub("", text)
    text = re.split(r"[/?#\\\s]", text, maxsplit=1)[0]
    text = text.rsplit("@", 1)[-1]
    if text.startswith("["):
        text = text[1:].split("]", 1)[0]
    elif text.count(":") == 1:
        text = _PORT_RE.sub("", text)
    text = text.rstrip(".").lower()
    if not text.isascii():
        try:
            text = text.encode("idna").decode("ascii")
        except UnicodeError:
            pass
    return text


def is_public_ip(indicator: str) -> bool:
    """False for private, loopback, link-local, reserved and documentation ranges: no service knows anything useful
    about them, so asking would only waste the API quota."""
    try:
        return ipaddress.ip_address(indicator).is_global
    except ValueError:
        return True


def detect_indicator_type(indicator: str) -> IndicatorType:
    try:
        ipaddress.ip_address(indicator)
        return "ip"
    except ValueError:
        return "domain"


async def run_lookup(
    indicator: str,
    indicator_type: IndicatorType,
    services: list[str] | None,
) -> LookupResult:
    """Queries the selected services in parallel (all of them when `services` is empty) and builds the report.

    Every call queries the services again (there is no result cache), so the report is always fresh.
    """
    selected = services or list(SERVICE_REGISTRY.keys())
    results: dict[str, ServiceResult] = {}

    async def run_one(name: str) -> None:
        service = SERVICE_REGISTRY[name]
        try:
            if indicator_type == "ip":
                if not service.supports_ip:
                    result = service.not_applicable_result()
                else:
                    result = await service.query_ip(indicator)
            else:
                if not service.supports_domain:
                    result = service.not_applicable_result()
                else:
                    result = await service.query_domain(indicator)
        except Exception as exc:
            result = service.error_result(describe_exception(exc))

        results[name] = result

    await asyncio.gather(*(run_one(n) for n in selected if n in SERVICE_REGISTRY))

    risk_score = compute_risk_score(results, indicator_type, indicator)
    talos_url = f"https://talosintelligence.com/reputation_center/lookup?search={quote(indicator)}"
    identity = build_identity(results) if indicator_type == "ip" else build_domain_identity(results)
    markdown = build_markdown(indicator, risk_score, results, identity, indicator_type)

    return LookupResult(
        indicator=indicator,
        indicator_type=indicator_type,
        risk_score=risk_score,
        services=results,
        talos_url=talos_url,
        markdown=markdown,
        identity=identity,
    )

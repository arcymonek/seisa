from __future__ import annotations

import asyncio
import ipaddress
from urllib.parse import quote

from backend.cache import get as cache_get
from backend.cache import set as cache_set
from backend.i18n import t
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
    force_refresh: bool,
    progress_cb=None,
) -> LookupResult:
    """Queries the selected services in parallel (all of them when `services` is empty) and builds the report.

    Results are served from the in-memory cache (15 min) unless `force_refresh` is set; `progress_cb(text)` is
    called with a status line while the VirusTotal throttle makes a request wait.
    """
    selected = services or list(SERVICE_REGISTRY.keys())
    results: dict[str, ServiceResult] = {}

    async def run_one(name: str) -> None:
        service = SERVICE_REGISTRY[name]
        if not force_refresh:
            cached = cache_get(indicator, name)
            if cached:
                results[name] = cached
                return

        def on_wait(seconds: float) -> None:
            if progress_cb:
                progress_cb(t("lookup.vt_wait", seconds=f"{seconds:.0f}"))

        kwargs = {"on_wait": on_wait} if name == "virustotal" else {}
        try:
            if indicator_type == "ip":
                if not service.supports_ip:
                    result = service.not_applicable_result()
                else:
                    result = await service.query_ip(indicator, **kwargs)
            else:
                if not service.supports_domain:
                    result = service.not_applicable_result()
                else:
                    result = await service.query_domain(indicator, **kwargs)
        except Exception as exc:
            result = service.error_result(describe_exception(exc))

        results[name] = result
        if result.status == "ok":
            cache_set(indicator, name, result)

    await asyncio.gather(*(run_one(n) for n in selected if n in SERVICE_REGISTRY))

    risk_score = compute_risk_score(results, indicator_type)
    talos_url = f"https://talosintelligence.com/reputation_center/lookup?search={quote(indicator)}"
    markdown = build_markdown(indicator, risk_score, results)

    return LookupResult(
        indicator=indicator,
        indicator_type=indicator_type,
        risk_score=risk_score,
        services=results,
        talos_url=talos_url,
        markdown=markdown,
    )

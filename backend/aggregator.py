from __future__ import annotations

import asyncio
import ipaddress
from urllib.parse import quote

from backend.cache import get as cache_get
from backend.cache import set as cache_set
from backend.markdown_report import build_markdown
from backend.models import IndicatorType, LookupResult, RiskComponent, RiskScore, ServiceResult
from backend.services.abuseipdb import AbuseIpdbService
from backend.services.base import describe_exception
from backend.services.cloudflare_radar import CloudflareRadarService
from backend.services.greynoise import GreyNoiseService
from backend.services.otx import OtxService
from backend.services.virustotal import VirusTotalService
from backend.services.whois_dns import WhoisDnsService

SERVICE_REGISTRY = {
    "virustotal": VirusTotalService(),
    "otx": OtxService(),
    "cloudflare_radar": CloudflareRadarService(),
    "abuseipdb": AbuseIpdbService(),
    "greynoise": GreyNoiseService(),
    "whois_rdns": WhoisDnsService(),
}

RISK_WEIGHTS = {
    "virustotal": 0.35,
    "abuseipdb": 0.25,
    "greynoise": 0.20,
    "otx": 0.15,
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
                progress_cb(f"oczekiwanie na limit VirusTotal ({seconds:.0f}s)")

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

    risk_score = _compute_risk_score(results, indicator_type)
    talos_url = f"https://talosintelligence.com/reputation_center/lookup?search={quote(indicator)}"
    markdown = build_markdown(indicator, indicator_type, risk_score, results)

    return LookupResult(
        indicator=indicator,
        indicator_type=indicator_type,
        risk_score=risk_score,
        services=results,
        talos_url=talos_url,
        markdown=markdown,
    )


def _compute_risk_score(results: dict[str, ServiceResult], indicator_type: IndicatorType) -> RiskScore:
    components: list[RiskComponent] = []
    excluded: list[str] = []

    vt = results.get("virustotal")
    if vt and vt.status == "ok" and vt.summary.get("total_engines"):
        total = vt.summary["total_engines"]
        malicious = vt.summary.get("malicious", 0) + vt.summary.get("suspicious", 0)
        pct = (malicious / total) * 100
        components.append(
            RiskComponent(
                source="virustotal",
                signal="detection_ratio",
                value=vt.summary.get("detection_ratio", "?"),
                weight=RISK_WEIGHTS["virustotal"],
                contribution=pct * RISK_WEIGHTS["virustotal"],
            )
        )
    elif vt:
        excluded.append(f"virustotal ({vt.status})")

    if indicator_type == "ip":
        abuse = results.get("abuseipdb")
        if abuse and abuse.status == "ok":
            score = abuse.summary.get("abuse_confidence_score") or 0
            components.append(
                RiskComponent(
                    source="abuseipdb",
                    signal="confidence_score",
                    value=str(score),
                    weight=RISK_WEIGHTS["abuseipdb"],
                    contribution=score * RISK_WEIGHTS["abuseipdb"],
                )
            )
        elif abuse:
            excluded.append(f"abuseipdb ({abuse.status})")

        gn = results.get("greynoise")
        if gn and gn.status == "ok":
            classification = gn.summary.get("classification", "unknown")
            gn_value = {"malicious": 100, "unknown": 40, "benign": 0}.get(classification, 40)
            components.append(
                RiskComponent(
                    source="greynoise",
                    signal="classification",
                    value=classification,
                    weight=RISK_WEIGHTS["greynoise"],
                    contribution=gn_value * RISK_WEIGHTS["greynoise"],
                )
            )
        elif gn:
            excluded.append(f"greynoise ({gn.status})")
    else:
        excluded.append("abuseipdb (not_applicable dla domen)")
        excluded.append("greynoise (not_applicable dla domen)")

    otx = results.get("otx")
    if otx and otx.status == "ok":
        count = otx.summary.get("pulse_count", 0)
        otx_value = min(count * 10, 100)
        components.append(
            RiskComponent(
                source="otx",
                signal="pulse_count",
                value=str(count),
                weight=RISK_WEIGHTS["otx"],
                contribution=otx_value * RISK_WEIGHTS["otx"],
            )
        )
    elif otx:
        excluded.append(f"otx ({otx.status})")

    excluded.append("cloudflare_radar (dane sieciowe/kontekstowe, nie werdykt - poza wynikiem liczbowym)")

    total_weight = sum(c.weight for c in components)
    score = sum(c.contribution for c in components) / total_weight if total_weight else 0.0
    level = "high" if score >= 70 else "medium" if score >= 35 else "low"

    return RiskScore(level=level, score=round(score, 1), components=components, excluded_sources=excluded)

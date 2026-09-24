from __future__ import annotations

import json

from backend.i18n import t
from backend.markdown_report import numbered_code_block


def _get(d: dict, path: str, default=None):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur if cur is not None else default


def _bullet(label: str, value) -> str | None:
    if value in (None, "", [], {}):
        return None
    return f"- **{label}**: {value}"


def build_urlscan_markdown(submitted_url: str, uuid: str, data: dict) -> str:
    """Builds a readable Markdown report from the full response of urlscan.io GET /api/v1/result/{uuid}/
    (documentation: https://urlscan.io/docs/result/). The full raw response goes at the end in a collapsible,
    numbered code section - the same formatting as in the reports of the IP tab."""
    page = data.get("page", {}) or {}
    task = data.get("task", {}) or {}
    stats = data.get("stats", {}) or {}
    lists = data.get("lists", {}) or {}
    verdict = _get(data, "verdicts.urlscan", {}) or {}
    dlinks = _get(data, "data.links", []) or []
    dcookies = _get(data, "data.cookies", []) or []
    technologies = _get(data, "meta.processors.wappa.data", []) or []

    lines: list[str] = []
    lines.append(f"# {t('us.title')} - `{submitted_url}`")
    lines.append("")
    lines.append(f"[{t('us.open')}](<https://urlscan.io/result/{uuid}/>)")
    lines.append("")

    lines.append(f"## {t('us.summary')}")
    lines.append("")
    for entry in filter(None, [
        _bullet(t("us.submitted_url"), task.get("url") or submitted_url),
        _bullet(t("us.final_url"), page.get("url")),
        _bullet(t("us.redirected"), t("common.yes") if page.get("redirected") else t("common.no")),
        _bullet(t("us.page_title"), page.get("title")),
        _bullet(t("us.domain"), page.get("domain")),
        _bullet(t("us.apex_domain"), page.get("apexDomain")),
        _bullet(t("us.main_ip"), page.get("ip")),
        _bullet("ASN", f"{page.get('asn') or '?'} ({page.get('asnname') or '?'})"),
        _bullet(t("us.ip_location"), ", ".join(filter(None, [page.get("city"), page.get("country")])) or None),
        _bullet("PTR", page.get("ptr")),
        _bullet(t("us.http_server"), page.get("server")),
        _bullet(t("us.http_status"), page.get("status")),
        _bullet(t("us.mime_type"), page.get("mimeType")),
        _bullet(t("us.umbrella_rank"), page.get("umbrellaRank")),
    ]):
        lines.append(entry)
    lines.append("")

    if page.get("tlsIssuer"):
        lines.append(f"## {t('us.tls')}")
        lines.append("")
        for entry in filter(None, [
            _bullet(t("us.issuer"), page.get("tlsIssuer")),
            _bullet(t("us.valid_from"), page.get("tlsValidFrom")),
            _bullet(t("us.valid_days"), page.get("tlsValidDays")),
            _bullet(t("us.cert_age"), page.get("tlsAgeDays")),
        ]):
            lines.append(entry)
        lines.append("")

    lines.append(f"## {t('us.verdict')}")
    lines.append("")
    score = verdict.get("score")
    lines.append(f"- **{t('us.malice_score')}**: {score if score is not None else t('common.none')} ({t('us.malice_scale')})")
    categories = verdict.get("categories") or []
    if categories:
        lines.append(f"- **{t('us.categories')}**: {', '.join(categories)}")
    brands = verdict.get("brands") or []
    if brands:
        lines.append(f"- **{t('us.brands')}**:")
        for b in brands:
            parts = [b.get("name")]
            if b.get("vertical"):
                parts.append(f"{t('us.vertical')}: {', '.join(b['vertical']) if isinstance(b['vertical'], list) else b['vertical']}")
            if b.get("country"):
                parts.append(f"{t('us.country')}: {', '.join(b['country']) if isinstance(b['country'], list) else b['country']}")
            lines.append(f"  - {' - '.join(filter(None, parts))}")
    lines.append("")

    lines.append(f"## {t('us.stats')}")
    lines.append("")
    for entry in filter(None, [
        _bullet(t("us.requests"), stats.get("requests") if stats.get("requests") is not None else len(_get(data, "data.requests", []) or [])),
        _bullet(t("us.unique_domains"), len(lists.get("domains") or [])),
        _bullet(t("us.unique_ips"), len(lists.get("ips") or [])),
        _bullet(t("us.countries"), len(lists.get("countries") or [])),
        _bullet(t("us.asns"), len(lists.get("asns") or [])),
        _bullet(t("us.certs"), len(lists.get("certificates") or [])),
        _bullet(t("us.cookies"), len(dcookies)),
        _bullet(t("us.transfer_size"), stats.get("dataLength") or stats.get("totalSize")),
    ]):
        lines.append(entry)
    lines.append("")

    if technologies:
        lines.append(f"## {t('us.technologies')}")
        lines.append("")
        for tech in technologies:
            cats = tech.get("categories") or []
            cat_names = ", ".join(c.get("name", str(c)) if isinstance(c, dict) else str(c) for c in cats)
            ver = f" {tech['version']}" if tech.get("version") else ""
            suffix = f" ({cat_names})" if cat_names else ""
            lines.append(f"- {tech.get('app', '?')}{ver}{suffix}")
        lines.append("")

    ips = lists.get("ips") or []
    if ips:
        geoip = _get(data, "meta.processors.geoip.data", []) or []
        asn_data = _get(data, "meta.processors.asn.data", []) or []
        geoip_by_ip = {g.get("ip"): g for g in geoip if isinstance(g, dict)}
        asn_by_ip = {a.get("ip"): a for a in asn_data if isinstance(a, dict)}
        lines.append(f"## {t('us.contacted_ips', n=len(ips))}")
        lines.append("")
        for ip in ips:
            g = geoip_by_ip.get(ip, {})
            a = asn_by_ip.get(ip, {})
            extra = ", ".join(filter(None, [g.get("country"), a.get("name")]))
            lines.append(f"- {ip}" + (f" ({extra})" if extra else ""))
        lines.append("")

    domains = lists.get("domains") or []
    if domains:
        lines.append(f"## {t('us.contacted_domains', n=len(domains))}")
        lines.append("")
        for d in domains:
            lines.append(f"- {d}")
        lines.append("")

    if dlinks:
        shown = dlinks[:50]
        lines.append(f"## {t('us.links', n=len(dlinks))}{(' ' + t('us.links_first50')) if len(dlinks) > 50 else ''}")
        lines.append("")
        for link in shown:
            href = link.get("href", "?")
            text = (link.get("text") or "").strip()
            lines.append(f"- <{href}>" + (f" - {text}" if text else ""))
        lines.append("")

    lines.append(f"<details><summary>{t('md.full_api_response')}</summary>")
    lines.append("")
    raw_text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    lines.extend(numbered_code_block(raw_text))
    lines.append("")
    lines.append("</details>")
    lines.append("")

    return "\n".join(lines)

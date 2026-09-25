"""Reports of the URLScan tab: a structured summary of a urlscan.io scan result (what the UI draws and the History tab
stores) and the Markdown export built from that summary."""
from __future__ import annotations

import json
from typing import Any

from backend.i18n import t
from backend.markdown_report import numbered_code_block
from backend.scoring import HIGH_FROM, MEDIUM_FROM
from backend.urlscan_input import defang

MAX_IPS = 100
MAX_DOMAINS = 200
MAX_LINKS = 100
MD_LINKS = 50


def _get(d: Any, path: str, default=None):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur if cur is not None else default


def _names(items) -> list[str]:
    out: list[str] = []
    for item in items or []:
        name = item.get("name") or item.get("key") if isinstance(item, dict) else item
        if name and str(name) not in out:
            out.append(str(name))
    return out


def _as_list(value) -> list[str]:
    if not value:
        return []
    return [str(v) for v in value] if isinstance(value, list) else [str(value)]


def _verdict(data: dict) -> dict:
    overall = _get(data, "verdicts.overall", {}) or {}
    urlscan = _get(data, "verdicts.urlscan", {}) or {}
    engines = _get(data, "verdicts.engines", {}) or {}
    community = _get(data, "verdicts.community", {}) or {}

    score = overall.get("score") if overall.get("score") is not None else urlscan.get("score")
    malicious = bool(overall.get("malicious") or urlscan.get("malicious"))
    categories = _as_list(overall.get("categories")) or _as_list(urlscan.get("categories"))

    brands: list[dict] = []
    for b in (overall.get("brands") or []) + [x for x in (urlscan.get("brands") or []) if x not in (overall.get("brands") or [])]:
        entry = b if isinstance(b, dict) else {"name": b}
        name = entry.get("name") or entry.get("key")
        if name and name not in [x["name"] for x in brands]:
            brands.append({"name": str(name), "vertical": _as_list(entry.get("vertical")), "country": _as_list(entry.get("country"))})

    engines_malicious = engines.get("maliciousTotal") if engines.get("maliciousTotal") is not None else engines.get("malicious")
    engines_total = (engines.get("maliciousTotal") or 0) + (engines.get("benignTotal") or 0) or None
    votes_total = community.get("votesTotal")
    votes_malicious = community.get("votesMalicious")

    has_data = bool(
        overall.get("hasVerdicts") or urlscan.get("hasVerdicts") or (score not in (None, 0)) or engines_total or votes_total
    )
    engine_hits = int(engines_malicious or 0)
    vote_hits = int(votes_malicious or 0)
    if malicious or (score or 0) >= HIGH_FROM:
        level = "high"
    elif (score or 0) >= MEDIUM_FROM or engine_hits or vote_hits:
        level = "medium"
    elif has_data:
        level = "low"
    else:
        level = "unknown"

    return {
        "level": level,
        "score": score,
        "malicious": malicious,
        "categories": categories,
        "brands": brands,
        "tags": _as_list(overall.get("tags")) or _as_list(urlscan.get("tags")),
        "engines": {"malicious": engine_hits, "total": engines_total} if engines_total else None,
        "community": {"malicious": vote_hits, "total": votes_total} if votes_total else None,
        "flagged_requests": _get(data, "stats.malicious"),
    }


def _redirect_chain(data: dict, final_url: str | None, final_status) -> list[dict]:
    """The hops of the redirect chain (urlscan records each redirect in the request that follows it)."""
    hops: list[dict] = []
    for req in _get(data, "data.requests", []) or []:
        redirect = _get(req, "request.redirectResponse")
        if isinstance(redirect, dict) and redirect.get("url"):
            hops.append({"url": str(redirect["url"]), "status": redirect.get("status")})
    if final_url:
        hops.append({"url": str(final_url), "status": final_status})
    deduped: list[dict] = []
    for hop in hops:
        if not deduped or deduped[-1]["url"] != hop["url"]:
            deduped.append(hop)
    return deduped if len(deduped) > 1 else []


def _form_signal(forms: list[dict] | None) -> bool:
    """A password field whose form posts to another domain (or over plain HTTP) - the classic phishing kit."""
    return any(f["password"] and (f["external"] or f["insecure"]) for f in forms or [])


def build_urlscan_summary(submitted_url: str, uuid: str, data: dict, forms: list[dict] | None = None) -> dict:
    """The structured result: everything the UI shows, without the raw API response (which is large and is not kept in
    the History). `forms` are the facts about the forms of the page (None = the DOM was not available); a risky form
    lifts a "low" or "unknown" urlscan.io verdict to "medium" - fresh phishing pages often have no verdict yet."""
    page = data.get("page", {}) or {}
    task = data.get("task", {}) or {}
    stats = data.get("stats", {}) or {}
    lists = data.get("lists", {}) or {}
    requests = _get(data, "data.requests", []) or []
    cookies = _get(data, "data.cookies", []) or []
    links = _get(data, "data.links", []) or []

    geoip = {g.get("ip"): g for g in (_get(data, "meta.processors.geoip.data", []) or []) if isinstance(g, dict)}
    asns = {a.get("ip"): a for a in (_get(data, "meta.processors.asn.data", []) or []) if isinstance(a, dict)}
    ips = [
        {"ip": str(ip), "country": (geoip.get(ip) or {}).get("country"), "asn_name": (asns.get(ip) or {}).get("name")}
        for ip in (lists.get("ips") or [])
    ]

    technologies = []
    for tech in _get(data, "meta.processors.wappa.data", []) or []:
        if isinstance(tech, dict) and tech.get("app"):
            technologies.append({"name": str(tech["app"]), "version": tech.get("version"), "categories": _names(tech.get("categories"))})

    transfer = sum(int(_get(r, "response.dataLength", 0) or 0) for r in requests) or stats.get("dataLength") or stats.get("totalSize")
    domains = [str(d) for d in (lists.get("domains") or [])]
    final_url = page.get("url")
    verdict = _verdict(data)
    verdict["form_signal"] = _form_signal(forms)
    if verdict["form_signal"] and verdict["level"] in ("low", "unknown"):
        verdict["level"] = "medium"

    return {
        "uuid": uuid,
        "submitted_url": task.get("url") or submitted_url,
        "result_url": f"https://urlscan.io/result/{uuid}/",
        "scanned_at": task.get("time"),
        "visibility": task.get("visibility"),
        "verdict": verdict,
        "forms": forms,
        "page": {
            "final_url": final_url,
            "redirected": bool(page.get("redirected")) or bool(_redirect_chain(data, final_url, page.get("status"))),
            "title": page.get("title"),
            "domain": page.get("domain"),
            "apex_domain": page.get("apexDomain"),
            "ip": page.get("ip"),
            "asn": page.get("asn"),
            "asn_name": page.get("asnname"),
            "country": page.get("country"),
            "city": page.get("city"),
            "ptr": page.get("ptr"),
            "server": page.get("server"),
            "status": page.get("status"),
            "mime_type": page.get("mimeType"),
            "umbrella_rank": page.get("umbrellaRank"),
        },
        "redirects": _redirect_chain(data, final_url, page.get("status")),
        "tls": {
            "issuer": page.get("tlsIssuer"),
            "valid_from": page.get("tlsValidFrom"),
            "valid_days": page.get("tlsValidDays"),
            "age_days": page.get("tlsAgeDays"),
        } if page.get("tlsIssuer") else None,
        "stats": {
            "requests": len(requests) or stats.get("requests"),
            "domains": len(domains),
            "ips": len(ips),
            "countries": len(lists.get("countries") or []),
            "asns": len(lists.get("asns") or []),
            "certificates": len(lists.get("certificates") or []),
            "cookies": len(cookies),
            "transfer_bytes": transfer,
        },
        "technologies": technologies,
        "ips": ips[:MAX_IPS],
        "domains": domains[:MAX_DOMAINS],
        "links": [{"href": str(x.get("href", "")), "text": (x.get("text") or "").strip()[:200]} for x in links[:MAX_LINKS] if isinstance(x, dict)],
        "links_total": len(links),
    }


def _bullet(label: str, value) -> str | None:
    if value in (None, "", [], {}):
        return None
    return f"- **{label}**: {value}"


def build_urlscan_markdown(summary: dict, raw: dict | None = None) -> str:
    """Markdown export of a summary. URLs found on the scanned page are defanged (a saved report must not contain live
    links to a possibly malicious site); the full raw response goes at the end in a collapsible, numbered code section -
    the same formatting as in the reports of the IP tab."""
    page = summary["page"]
    verdict = summary["verdict"]
    stats = summary["stats"]
    submitted = summary["submitted_url"]

    lines: list[str] = [f"# {t('us.title')} - `{defang(submitted)}`", "", f"[{t('us.open')}](<{summary['result_url']}>)", ""]

    lines += [f"## {t('us.summary')}", ""]
    lines += filter(None, [
        _bullet(t("us.submitted_url"), f"`{defang(submitted)}`"),
        _bullet(t("us.final_url"), f"`{defang(page['final_url'])}`" if page.get("final_url") else None),
        _bullet(t("us.redirected"), t("common.yes") if page.get("redirected") else t("common.no")),
        _bullet(t("us.page_title"), page.get("title")),
        _bullet(t("us.domain"), page.get("domain")),
        _bullet(t("us.apex_domain"), page.get("apex_domain")),
        _bullet(t("us.main_ip"), page.get("ip")),
        _bullet("ASN", f"{page.get('asn') or '?'} ({page.get('asn_name') or '?'})"),
        _bullet(t("us.ip_location"), ", ".join(filter(None, [page.get("city"), page.get("country")])) or None),
        _bullet("PTR", page.get("ptr")),
        _bullet(t("us.http_server"), page.get("server")),
        _bullet(t("us.http_status"), page.get("status")),
        _bullet(t("us.mime_type"), page.get("mime_type")),
        _bullet(t("us.umbrella_rank"), page.get("umbrella_rank")),
    ])
    lines.append("")

    if summary["redirects"]:
        lines += [f"## {t('us.redirect_chain')}", ""]
        lines += [f"{i}. `{defang(h['url'])}`" + (f" ({h['status']})" if h.get("status") else "") for i, h in enumerate(summary["redirects"], 1)]
        lines.append("")

    tls = summary.get("tls")
    if tls:
        lines += [f"## {t('us.tls')}", ""]
        lines += filter(None, [
            _bullet(t("us.issuer"), tls.get("issuer")),
            _bullet(t("us.valid_from"), tls.get("valid_from")),
            _bullet(t("us.valid_days"), tls.get("valid_days")),
            _bullet(t("us.cert_age"), tls.get("age_days")),
        ])
        lines.append("")

    lines += [f"## {t('us.verdict')}", ""]
    score = verdict.get("score")
    lines.append(f"- **{t('us.malice_score')}**: {score if score is not None else t('common.none')} ({t('us.malice_scale')})")
    if verdict["categories"]:
        lines.append(f"- **{t('us.categories')}**: {', '.join(verdict['categories'])}")
    if verdict.get("form_signal"):
        lines.append(f"- **{t('us.form_signal')}**")
    if verdict["engines"]:
        lines.append(f"- **{t('us.engines')}**: {verdict['engines']['malicious']}/{verdict['engines']['total']}")
    if verdict["community"]:
        lines.append(f"- **{t('us.community')}**: {verdict['community']['malicious']}/{verdict['community']['total']}")
    if verdict["brands"]:
        lines.append(f"- **{t('us.brands')}**:")
        for b in verdict["brands"]:
            parts = [b["name"]]
            if b["vertical"]:
                parts.append(f"{t('us.vertical')}: {', '.join(b['vertical'])}")
            if b["country"]:
                parts.append(f"{t('us.country')}: {', '.join(b['country'])}")
            lines.append(f"  - {' - '.join(parts)}")
    lines.append("")

    lines += [f"## {t('us.stats')}", ""]
    lines += filter(None, [
        _bullet(t("us.requests"), stats.get("requests")),
        _bullet(t("us.unique_domains"), stats.get("domains")),
        _bullet(t("us.unique_ips"), stats.get("ips")),
        _bullet(t("us.countries"), stats.get("countries")),
        _bullet(t("us.asns"), stats.get("asns")),
        _bullet(t("us.certs"), stats.get("certificates")),
        _bullet(t("us.cookies"), stats.get("cookies")),
        _bullet(t("us.transfer_size"), stats.get("transfer_bytes")),
    ])
    lines.append("")

    forms = summary.get("forms")
    if forms:
        lines += [f"## {t('us.forms', n=len(forms))}", ""]
        for form in forms:
            flags = [x for x in (t("us.form_password") if form["password"] else "", t("us.form_external") if form["external"] else "",
                                 t("us.form_insecure") if form["insecure"] else "") if x]
            fields = f" [{', '.join(form['fields'])}]" if form["fields"] else ""
            lines.append(f"- `{defang(form['action'] or '-')}` ({form['method'].upper()}){fields}" + (f" - {'; '.join(flags)}" if flags else ""))
        lines.append("")

    if summary["technologies"]:
        lines += [f"## {t('us.technologies')}", ""]
        for tech in summary["technologies"]:
            version = f" {tech['version']}" if tech.get("version") else ""
            cats = f" ({', '.join(tech['categories'])})" if tech["categories"] else ""
            lines.append(f"- {tech['name']}{version}{cats}")
        lines.append("")

    if summary["ips"]:
        lines += [f"## {t('us.contacted_ips', n=len(summary['ips']))}", ""]
        for entry in summary["ips"]:
            extra = ", ".join(filter(None, [entry.get("country"), entry.get("asn_name")]))
            lines.append(f"- {entry['ip']}" + (f" ({extra})" if extra else ""))
        lines.append("")

    if summary["domains"]:
        lines += [f"## {t('us.contacted_domains', n=len(summary['domains']))}", ""]
        lines += [f"- {defang(d)}" for d in summary["domains"]]
        lines.append("")

    if summary["links"]:
        total = summary["links_total"]
        heading = t("us.links", n=total) + (f" {t('us.links_first50')}" if total > MD_LINKS else "")
        lines += [f"## {heading}", ""]
        for link in summary["links"][:MD_LINKS]:
            lines.append(f"- `{defang(link['href'] or '?')}`" + (f" - {link['text']}" if link["text"] else ""))
        lines.append("")

    if raw is not None:
        lines.append(f"<details><summary>{t('md.full_api_response')}</summary>")
        lines.append("")
        lines.extend(numbered_code_block(json.dumps(raw, ensure_ascii=False, indent=2, default=str)))
        lines += ["", "</details>", ""]

    return "\n".join(lines)

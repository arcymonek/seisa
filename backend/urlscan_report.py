from __future__ import annotations

import json

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
    """Buduje czytelny raport Markdown z pełnej odpowiedzi GET /api/v1/result/{uuid}/
    urlscan.io (dokumentacja: https://urlscan.io/docs/result/). Pełna surowa
    odpowiedź trafia na koniec w zwijanej, numerowanej sekcji kodu - to samo
    formatowanie co w raportach zakładki IP."""
    page = data.get("page", {}) or {}
    task = data.get("task", {}) or {}
    stats = data.get("stats", {}) or {}
    lists = data.get("lists", {}) or {}
    verdict = _get(data, "verdicts.urlscan", {}) or {}
    dlinks = _get(data, "data.links", []) or []
    dcookies = _get(data, "data.cookies", []) or []
    technologies = _get(data, "meta.processors.wappa.data", []) or []

    lines: list[str] = []
    lines.append(f"# Wynik skanowania - `{submitted_url}`")
    lines.append("")
    lines.append(f"[Otwórz w urlscan.io](<https://urlscan.io/result/{uuid}/>)")
    lines.append("")

    lines.append("## Podsumowanie")
    lines.append("")
    for entry in filter(None, [
        _bullet("URL zgłoszony", task.get("url") or submitted_url),
        _bullet("URL końcowy (po przekierowaniach)", page.get("url")),
        _bullet("Przekierowano", "tak" if page.get("redirected") else "nie"),
        _bullet("Tytuł strony", page.get("title")),
        _bullet("Domena", page.get("domain")),
        _bullet("Domena nadrzędna (apex)", page.get("apexDomain")),
        _bullet("IP główne", page.get("ip")),
        _bullet("ASN", f"{page.get('asn') or '?'} ({page.get('asnname') or '?'})"),
        _bullet("Lokalizacja IP", ", ".join(filter(None, [page.get("city"), page.get("country")])) or None),
        _bullet("PTR", page.get("ptr")),
        _bullet("Serwer HTTP", page.get("server")),
        _bullet("Status HTTP strony głównej", page.get("status")),
        _bullet("Typ MIME", page.get("mimeType")),
        _bullet("Ranking Cisco Umbrella", page.get("umbrellaRank")),
    ]):
        lines.append(entry)
    lines.append("")

    if page.get("tlsIssuer"):
        lines.append("## Certyfikat TLS")
        lines.append("")
        for entry in filter(None, [
            _bullet("Wystawca", page.get("tlsIssuer")),
            _bullet("Ważny od", page.get("tlsValidFrom")),
            _bullet("Ważność (dni)", page.get("tlsValidDays")),
            _bullet("Wiek certyfikatu w dniu skanowania (dni)", page.get("tlsAgeDays")),
        ]):
            lines.append(entry)
        lines.append("")

    lines.append("## Werdykt urlscan.io")
    lines.append("")
    score = verdict.get("score")
    lines.append(f"- **Wynik złośliwości**: {score if score is not None else 'brak'} (skala -100 do 100, wyżej = bardziej złośliwe)")
    categories = verdict.get("categories") or []
    if categories:
        lines.append(f"- **Kategorie**: {', '.join(categories)}")
    brands = verdict.get("brands") or []
    if brands:
        lines.append("- **Wykryte marki (możliwe podszycie)**:")
        for b in brands:
            parts = [b.get("name")]
            if b.get("vertical"):
                parts.append(f"branża: {', '.join(b['vertical']) if isinstance(b['vertical'], list) else b['vertical']}")
            if b.get("country"):
                parts.append(f"kraj: {', '.join(b['country']) if isinstance(b['country'], list) else b['country']}")
            lines.append(f"  - {' - '.join(filter(None, parts))}")
    lines.append("")

    lines.append("## Statystyki strony")
    lines.append("")
    for entry in filter(None, [
        _bullet("Żądania HTTP", stats.get("requests") if stats.get("requests") is not None else len(_get(data, "data.requests", []) or [])),
        _bullet("Unikalne domeny", len(lists.get("domains") or [])),
        _bullet("Unikalne adresy IP", len(lists.get("ips") or [])),
        _bullet("Kraje", len(lists.get("countries") or [])),
        _bullet("Numery ASN", len(lists.get("asns") or [])),
        _bullet("Certyfikaty TLS", len(lists.get("certificates") or [])),
        _bullet("Cookies ustawione", len(dcookies)),
        _bullet("Rozmiar transferu (bajty)", stats.get("dataLength") or stats.get("totalSize")),
    ]):
        lines.append(entry)
    lines.append("")

    if technologies:
        lines.append("## Wykryte technologie")
        lines.append("")
        for t in technologies:
            cats = t.get("categories") or []
            cat_names = ", ".join(c.get("name", str(c)) if isinstance(c, dict) else str(c) for c in cats)
            ver = f" {t['version']}" if t.get("version") else ""
            suffix = f" ({cat_names})" if cat_names else ""
            lines.append(f"- {t.get('app', '?')}{ver}{suffix}")
        lines.append("")

    ips = lists.get("ips") or []
    if ips:
        geoip = _get(data, "meta.processors.geoip.data", []) or []
        asn_data = _get(data, "meta.processors.asn.data", []) or []
        geoip_by_ip = {g.get("ip"): g for g in geoip if isinstance(g, dict)}
        asn_by_ip = {a.get("ip"): a for a in asn_data if isinstance(a, dict)}
        lines.append(f"## Kontaktowane adresy IP ({len(ips)})")
        lines.append("")
        for ip in ips:
            g = geoip_by_ip.get(ip, {})
            a = asn_by_ip.get(ip, {})
            extra = ", ".join(filter(None, [g.get("country"), a.get("name")]))
            lines.append(f"- {ip}" + (f" ({extra})" if extra else ""))
        lines.append("")

    domains = lists.get("domains") or []
    if domains:
        lines.append(f"## Kontaktowane domeny ({len(domains)})")
        lines.append("")
        for d in domains:
            lines.append(f"- {d}")
        lines.append("")

    if dlinks:
        shown = dlinks[:50]
        lines.append(f"## Linki na stronie ({len(dlinks)}{', pokazano pierwsze 50' if len(dlinks) > 50 else ''})")
        lines.append("")
        for link in shown:
            href = link.get("href", "?")
            text = (link.get("text") or "").strip()
            lines.append(f"- <{href}>" + (f" - {text}" if text else ""))
        lines.append("")

    lines.append("<details><summary>Pełna odpowiedź API</summary>")
    lines.append("")
    raw_text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    lines.extend(numbered_code_block(raw_text))
    lines.append("")
    lines.append("</details>")
    lines.append("")

    return "\n".join(lines)

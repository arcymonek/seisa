from __future__ import annotations

import json

from backend.models import RiskScore, ServiceResult

SERVICE_TITLES = {
    "virustotal": "VirusTotal",
    "otx": "AlienVault OTX",
    "cloudflare_radar": "Cloudflare Radar",
    "abuseipdb": "AbuseIPDB",
    "greynoise": "GreyNoise",
    "whois_rdns": "WHOIS / rDNS",
}

# Stała kolejność sekcji w raporcie, niezależnie od kolejności zakończenia zapytań.
SERVICE_ORDER = ["whois_rdns", "cloudflare_radar", "otx", "abuseipdb", "virustotal", "greynoise"]

STATUS_LABELS = {
    "ok": "OK",
    "error": "błąd",
    "no_key": "brak klucza API",
    "not_applicable": "nie dotyczy tego typu wskaźnika",
    "rate_limited_daily": "przekroczony dzienny limit",
}


def _format_scalar(value) -> str:
    """URL-e jako klikalne autolinki (składnia CommonMark <url>), reszta bez zmian."""
    if isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")):
        return f"<{value}>"
    return str(value)


def _render_value_lines(value, indent: int = 0) -> list[str]:
    """Zagnieżdżone dict/list jako czytelna lista wypunktowana, nie blok kodu."""
    pad = "  " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if v in (None, "", [], {}):
                continue
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}- {k}:")
                lines.extend(_render_value_lines(v, indent + 1))
            else:
                lines.append(f"{pad}- {k}: {_format_scalar(v)}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}-")
                lines.extend(_render_value_lines(item, indent + 1))
            else:
                lines.append(f"{pad}- {_format_scalar(item)}")
    else:
        lines.append(f"{pad}{_format_scalar(value)}")
    return lines


def numbered_code_block(text: str, lang: str = "json") -> list[str]:
    src_lines = text.split("\n")
    width = len(str(len(src_lines)))
    numbered = [f"{str(i + 1).rjust(width)} | {line}" for i, line in enumerate(src_lines)]
    return [f"```{lang}", *numbered, "```"]


def build_markdown(
    indicator: str,
    risk_score: RiskScore,
    services: dict[str, ServiceResult],
) -> str:
    lines: list[str] = []
    lines.append(f"# Raport reputacji - `{indicator}`")
    lines.append("")
    lines.append(f"## Wynik zbiorczy: {risk_score.level.upper()} ({risk_score.score}/100)")
    lines.append("")
    if risk_score.components:
        lines.append("### Sygnały składowe")
        lines.append("")
        lines.append("| Źródło | Sygnał | Wartość | Waga | Wkład |")
        lines.append("|---|---|---|---|---|")
        for c in risk_score.components:
            lines.append(f"| {c.source} | {c.signal} | {c.value} | {c.weight} | {round(c.contribution, 1)} |")
        lines.append("")
    if risk_score.excluded_sources:
        lines.append(f'<div class="excluded-sources">Wykluczone z wyniku: {"; ".join(risk_score.excluded_sources)}</div>')
        lines.append("")

    ordered = sorted(services.items(), key=lambda kv: SERVICE_ORDER.index(kv[0]) if kv[0] in SERVICE_ORDER else len(SERVICE_ORDER))
    for name, result in ordered:
        title = SERVICE_TITLES.get(name, name)
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"Status: **{STATUS_LABELS.get(result.status, result.status)}**")
        lines.append("")
        if result.error_message:
            lines.append(f"> {result.error_message}")
            lines.append("")
        elif result.summary:
            for key, value in result.summary.items():
                if value in (None, "", [], {}):
                    continue
                if isinstance(value, (dict, list)):
                    lines.append(f"- **{key}**:")
                    lines.extend(_render_value_lines(value, indent=1))
                elif isinstance(value, str) and "\n" in value:
                    # wielolinijkowy tekst (np. surowy rekord WHOIS) - jedna linia
                    # źródła = jeden punkt listy, żeby zwykła treść nie zlała się
                    # w jeden akapit ani nie wyglądała jak blok kodu
                    lines.append(f"- **{key}**:")
                    for raw_line in value.strip().split("\n"):
                        entry = raw_line.strip()
                        if not entry:
                            continue
                        if ":" in entry:
                            sub_key, sub_val = entry.split(":", 1)
                            lines.append(f"  - **{sub_key.strip()}**: {_format_scalar(sub_val.strip())}")
                        else:
                            lines.append(f"  - {_format_scalar(entry)}")
                else:
                    lines.append(f"- **{key}**: {_format_scalar(value)}")
            lines.append("")
        if result.raw:
            lines.append("<details><summary>Pełna odpowiedź API</summary>")
            lines.append("")
            raw_text = json.dumps(result.raw, ensure_ascii=False, indent=2, default=str)
            lines.extend(numbered_code_block(raw_text))
            lines.append("")
            lines.append("</details>")
            lines.append("")

    return "\n".join(lines)

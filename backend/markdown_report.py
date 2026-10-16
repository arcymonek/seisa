"""Builds the Markdown report of an IP or domain lookup (score, components, per-service sections) shown in the
Lookup tab and exported from it. Called by aggregator.py. All text comes from the i18n catalogs and every value
from a service is escaped for Markdown.
"""
from __future__ import annotations

import html
import json
import re

from backend.i18n import t
from backend.markdown_utils import fence, flat, md_cell, md_code, md_text
from backend.models import Identity, RiskScore, ServiceResult

SERVICE_TITLES = {
    "virustotal": "VirusTotal",
    "otx": "AlienVault OTX",
    "cloudflare_radar": "Cloudflare Radar",
    "abuseipdb": "AbuseIPDB",
    "greynoise": "GreyNoise",
    "whois_rdns": "WHOIS / rDNS",
    "dns": "DNS",
    "local_heuristics": "Seisa",
}

# Fixed order of the sections in the report, regardless of the order in which the queries finish.
SERVICE_ORDER = ["whois_rdns", "cloudflare_radar", "otx", "abuseipdb", "virustotal", "greynoise"]

STATUS_KEYS = {
    "ok": "md.status.ok",
    "error": "md.status.error",
    "no_key": "md.status.no_key",
    "not_applicable": "md.status.not_applicable",
    "rate_limited_daily": "md.status.rate_limited_daily",
}


def status_label(status: str) -> str:
    return t(STATUS_KEYS[status]) if status in STATUS_KEYS else status


# Addresses that Seisa builds itself from an identifier (the shape is checked, the identifier came from a service) stay
# clickable; every other address in a service answer is untrusted and is shown defanged.
_TRUSTED_LINK = re.compile(r"^https://www\.abuseipdb\.com/user/\d+$")


def _format_scalar(value) -> str:
    """A value from a service: a clickable autolink for an address Seisa built itself, inert text for everything else."""
    if isinstance(value, str) and _TRUSTED_LINK.fullmatch(value):
        return f"<{value}>"
    return md_text(value)


def _render_value_lines(value, indent: int = 0) -> list[str]:
    """Nested dict/list as a readable bullet list, not a code block."""
    pad = "  " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if v in (None, "", [], {}):
                continue
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}- {md_text(k)}:")
                lines.extend(_render_value_lines(v, indent + 1))
            else:
                lines.append(f"{pad}- {md_text(k)}: {_format_scalar(v)}")
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
    marker = fence(text)
    return [f"{marker}{lang}", *numbered, marker]


def _identity_lines(identity: Identity, indicator_type: str = "ip") -> list[str]:
    """Table of the merged identity: the value shown, how many sources agree, and the other values (with sources)
    wherever the sources disagree."""
    lines = [f"## {t('identity.title_domain' if indicator_type == 'domain' else 'identity.title')}", ""]
    lines.append(f"| {t('md.col_field')} | {t('md.col_value')} | {t('md.col_agreement')} |")
    lines.append("|---|---|---|")
    for f in identity.fields:
        agreement = t(f"identity.status.{f.status}", agree=f.agree, total=f.total)
        if f.status in ("majority", "conflict"):
            others = "; ".join(f"{v.value} ({', '.join(SERVICE_TITLES.get(s, s) for s in v.sources)})" for v in f.variants[1:])
            agreement = f"{agreement} - {t('identity.other_values')}: {others}"
        cells = (t(f"identity.f.{f.key}"), f.value, agreement)
        lines.append("| " + " | ".join(md_cell(c) for c in cells) + " |")
    lines.append("")
    for note in identity.notes:
        lines.append(f"> {md_text(note)}")
        lines.append("")
    return lines


def build_markdown(
    indicator: str,
    risk_score: RiskScore,
    services: dict[str, ServiceResult],
    identity: Identity | None = None,
    indicator_type: str = "ip",
) -> str:
    lines: list[str] = []
    lines.append(f"# {t('md.report_title')} - {md_code(indicator)}")
    lines.append("")
    lines.append(f"## {t('md.aggregate_score')}: {risk_score.level.upper()} ({risk_score.score}/100)")
    lines.append("")
    if risk_score.sources_possible:
        lines.append(t("md.score_based_on", used=risk_score.sources_used, possible=risk_score.sources_possible))
        lines.append("")
    for note in risk_score.notes:
        lines.append(f"> {md_text(note)}")
        lines.append("")
    if risk_score.components:
        lines.append(f"### {t('md.components')}")
        lines.append("")
        lines.append(f"| {t('md.col_source')} | {t('md.col_signal')} | {t('md.col_value')} | {t('md.col_risk')} | {t('md.col_credibility')} |")
        lines.append("|---|---|---|---|---|")
        for c in risk_score.components:
            lines.append("| " + " | ".join(md_cell(x) for x in (c.source, c.signal, c.value, c.risk, c.weight)) + " |")
        lines.append("")
    if risk_score.excluded_sources:
        lines.append(f'<div class="excluded-sources">{t("md.excluded")}: {html.escape(flat("; ".join(risk_score.excluded_sources)))}</div>')
        lines.append("")

    if identity and identity.fields:
        lines.extend(_identity_lines(identity, indicator_type))

    ordered = sorted(services.items(), key=lambda kv: SERVICE_ORDER.index(kv[0]) if kv[0] in SERVICE_ORDER else len(SERVICE_ORDER))
    for name, result in ordered:
        title = SERVICE_TITLES.get(name, name)
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"{t('md.status')}: **{status_label(result.status)}**")
        lines.append("")
        if result.error_message:
            lines.append(f"> {md_text(result.error_message)}")
            lines.append("")
        elif result.summary:
            for key, value in result.summary.items():
                if name == "whois_rdns" and key == "reverse_dns" and value is None:
                    value = t("svc.no_ptr")  # no PTR record: said in the language of the reader, not stored as text
                if value in (None, "", [], {}):
                    continue
                if isinstance(value, (dict, list)):
                    lines.append(f"- **{md_text(key)}**:")
                    lines.extend(_render_value_lines(value, indent=1))
                elif isinstance(value, str) and "\n" in value:
                    # multi-line text (e.g. a raw WHOIS record) - one source line = one list item, so that plain
                    # content neither merges into one paragraph nor looks like a code block
                    lines.append(f"- **{md_text(key)}**:")
                    for raw_line in value.strip().split("\n"):
                        entry = raw_line.strip()
                        if not entry:
                            continue
                        if ":" in entry:
                            sub_key, sub_val = entry.split(":", 1)
                            lines.append(f"  - **{md_text(sub_key)}**: {_format_scalar(sub_val)}")
                        else:
                            lines.append(f"  - {_format_scalar(entry)}")
                else:
                    lines.append(f"- **{md_text(key)}**: {_format_scalar(value)}")
            lines.append("")
        if result.raw:
            lines.append(f"<details><summary>{t('md.full_api_response')}</summary>")
            lines.append("")
            raw_text = json.dumps(result.raw, ensure_ascii=False, indent=2, default=str)
            lines.extend(numbered_code_block(raw_text))
            lines.append("")
            lines.append("</details>")
            lines.append("")

    return "\n".join(lines)

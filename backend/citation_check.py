"""Citation check: does what the LLM analysis quotes from the source really appear in it.

Pure local code (no model calls, zero cost). It checks only things that can be verified unambiguously, so as
not to flood the user with false alarms:

- IP addresses (v4/v6) mentioned in the analysis,
- header lines quoted in code blocks (fragments separated by an ellipsis are checked separately),
- `Header: value` quotes in the text, when a header of that name is in the source but the value differs,
- SCL/BCL numbers,
- `<...@...>` identifiers (e.g. Message-ID) and hex digests (sha256/md5) in code.

It does not check domains or entries such as `spf=pass`: the analysis also discusses examples and comparisons
with a legitimate message, so that would be too noisy. The result is information, not proof of an error: an
example, a paraphrase or an abbreviation may be flagged too.
"""
from __future__ import annotations

import ipaddress
import json
import re

from backend.i18n import t

MAX_ISSUES = 40

_IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
_IPV6_RE = re.compile(r"(?<![\w:.])[0-9A-Fa-f:]{3,39}(?![\w:.])")
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_CODE_SPAN_RE = re.compile(r"`([^`\n]{3,300})`")
_HEADER_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9-]*):\s*(\S.*)$")
_ELLIPSIS_RE = re.compile(r"\(\.\.\.\)|\[\.\.\.\]|\.\.\.|…")
_SCL_RE = re.compile(r"\b(SCL|BCL)\s*[:=]\s*(-?\d+)\b")
_MSGID_RE = re.compile(r"<[^<>\s@`]+@[^<>\s`]+>")
_HEX_RE = re.compile(r"\b[0-9a-fA-F]{32,128}\b")
# documentation addresses (RFC 5737 / 3849) used in examples
_DOC_NETS = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32")]


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_doc_ip(ip) -> bool:
    return any(ip in net for net in _DOC_NETS if net.version == ip.version)


def _extract_ips(text: str) -> list[str]:
    found: list[str] = []
    for m in _IPV4_RE.finditer(text):
        try:
            ip = ipaddress.ip_address(m.group(0))
        except ValueError:
            continue
        if not _is_doc_ip(ip):
            found.append(m.group(0))
    for m in _IPV6_RE.finditer(text):
        cand = m.group(0)
        if "::" not in cand and cand.count(":") != 7:
            continue  # without this, times (23:50:16) would look like IPv6
        try:
            ip = ipaddress.ip_address(cand)
        except ValueError:
            continue
        if not _is_doc_ip(ip):
            found.append(cand)
    return list(dict.fromkeys(found))


def _header_names(source: str) -> set[str]:
    names = set()
    for line in source.split("\n"):
        if line[:1] in (" ", "\t") or not line.strip():
            if not line.strip():
                break  # end of the main headers
            continue
        if ":" in line:
            names.add(line.split(":", 1)[0].strip().lower())
    return names


def verify_citations(markdown: str, source: str, extra_texts: list[str], facts: dict | None = None) -> dict:
    """Returns {"checked": int, "issues": [{"kind", "text", "note"}]}.

    `source` is the normalised e-mail source, `extra_texts` are additional texts in which a quote may be found
    (decoded text parts, the version prepared for the model), `facts` is the deterministic analysis. The `note`
    of an issue is written in the language of the current request and stored with the analysis."""
    haystack = _collapse("\n".join([source, *extra_texts, json.dumps(facts or {}, ensure_ascii=False)])).casefold()
    text = markdown.replace("[.]", ".").replace("hxxp", "http")
    loose_haystack = re.sub(r"\s+", "", haystack)  # the model may change spacing (e.g. "; " instead of ";")
    header_names = _header_names(source)
    issues: list[dict] = []
    checked = 0

    def add(kind: str, item: str, note: str) -> None:
        if len(issues) < MAX_ISSUES:
            issues.append({"kind": kind, "text": item[:200], "note": note})

    # A. IP addresses
    for ip in _extract_ips(text):
        checked += 1
        if ip.casefold() not in haystack:
            add("ip", ip, t("cite.ip_missing"))

    # B. header lines quoted in code blocks
    for block in _FENCE_RE.findall(text):
        logical: list[str] = []
        for line in block.split("\n"):
            if line[:1] in (" ", "\t") and logical:
                logical[-1] += " " + line.strip()
            elif line.strip():
                logical.append(line.strip())
        for line in logical:
            m = _HEADER_LINE_RE.match(line)
            if not m:
                continue
            checked += 1
            name = m.group(1).lower()
            fragments = [re.sub(r"\s+", "", f).casefold() for f in _ELLIPSIS_RE.split(line)]
            fragments = [f for f in fragments if len(f) >= 8]
            missing = [f for f in fragments if f not in loose_haystack]
            if name not in header_names and name not in haystack:
                add("brak_naglowka", line, t("cite.header_missing", name=m.group(1)))
            elif missing:
                add("cytat_naglowka", line, t("cite.header_mismatch"))

    # C. `Header: value` quotes in the text (only for headers present in the source)
    outside_fences = _FENCE_RE.sub("", text)
    for span in _CODE_SPAN_RE.findall(outside_fences):
        m = _HEADER_LINE_RE.match(span.strip())
        if not m or m.group(1).lower() not in header_names or len(m.group(2)) < 6:
            continue
        checked += 1
        if re.sub(r"\s+", "", span).casefold() not in loose_haystack:
            add("cytat_naglowka", span.strip(), t("cite.value_differs"))

    # D. SCL/BCL numbers
    seen = set()
    for m in _SCL_RE.finditer(text):
        key = (m.group(1).upper(), m.group(2))
        if key in seen:
            continue
        seen.add(key)
        checked += 1
        if not re.search(rf"\b{key[0].lower()}\s*[:=]\s*{re.escape(key[1])}\b", haystack):
            add("liczba", f"{key[0]}={key[1]}", t("cite.number_missing"))

    # E. <...@...> identifiers and hex digests in code
    for span in _CODE_SPAN_RE.findall(text):
        s = span.strip()
        if _MSGID_RE.fullmatch(s) or _HEX_RE.fullmatch(s):
            checked += 1
            if s.casefold() not in haystack:
                add("identyfikator", s, t("cite.identifier_missing"))

    return {"checked": checked, "issues": issues}

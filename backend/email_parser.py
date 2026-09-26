from __future__ import annotations

import html as html_module
import ipaddress
import re
from datetime import timezone
from email import message_from_string
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime

from backend.i18n import t
from backend.report_utils import attack_age, is_reportable_ip

_BTC_RE = re.compile(r"\b(bc1[a-z0-9]{25,39}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
_RANSOM_KEYWORDS = ("bitcoin", "btc", "ransom", "payment", "wallet", "crypto", "decrypt")
_FROM_BY_RE = re.compile(r"from\s+(?P<from>.+?)\s+by\s+(?P<by>\S+)", re.IGNORECASE)
_PAREN_RE = re.compile(r"\(([^)]+)\)")
_BRACKET_RE = re.compile(r"\[([^\]]+)\]")
_HEADER_START_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:")
_INDENTED_HEADER_START_RE = re.compile(r"^\s+[A-Za-z][A-Za-z0-9-]*:(\s|$)")
_HTML_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_HTML_BLOCK_CLOSE_RE = re.compile(r"</(p|div|tr|li|h[1-6]|table)>|<br\s*/?>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_BLANK_LINES_RE = re.compile(r"\n{3,}")



def _html_to_text(html: str) -> str:
    """Turns HTML into readable text without external dependencies: removes script/style, turns closing block
    tags into newlines, strips the remaining tags, decodes HTML entities and collapses extra blank lines."""
    text = _HTML_SCRIPT_STYLE_RE.sub(" ", html)
    text = _HTML_BLOCK_CLOSE_RE.sub("\n", text)
    text = _HTML_TAG_RE.sub("", text)
    text = html_module.unescape(text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def _refold_headers(raw_email: str) -> str:
    """Many mail clients/browsers lose the indentation of continuation lines (RFC 5322 folding) of long headers
    when you "show the source" - especially multi-line `Received`. For the stdlib `email` parser a line without
    a leading space that does not look like `Header-Name:` ends the header block, so a pasted e-mail like that
    can stop parsing at the very first header. We restore the missing indentation where it is unambiguous (a
    non-empty line inside the header block that starts neither with `Name:` nor with whitespace). The reverse
    also happens - the next header is wrongly indented (e.g. by a paste tool that keeps nesting) - such a line
    is recognised by the `Name:` pattern despite the indentation and un-indented, so that the stdlib treats it
    as a new header and not as a continuation."""
    lines = raw_email.split("\n")
    out: list[str] = []
    in_headers = True
    for line in lines:
        if in_headers and line.strip() == "":
            in_headers = False
            out.append(line)
            continue
        if in_headers and line.startswith((" ", "\t")):
            indented_header = _INDENTED_HEADER_START_RE.match(line)
            out.append(line.lstrip() if indented_header else line)
        elif in_headers and out and not _HEADER_START_RE.match(line):
            out.append(" " + line)
        else:
            out.append(line)
    return "\n".join(out)


def _parse_ip(candidate: str | None) -> str | None:
    if not candidate:
        return None
    try:
        return str(ipaddress.ip_address(candidate.strip()))
    except ValueError:
        return None


def _is_special_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def _extract_ip_candidates(text: str) -> list[str]:
    """Collects all IP addresses mentioned in the "from" clause of a Received header - both in the [IP] form
    (MTA convention for rDNS/real IP) and in plain parentheses (which may also hold host names such as
    "HELO foo" that do not parse as an IP and are dropped). Public addresses take precedence over loopback/
    private ones - MTAs such as Microsoft EOP may write `[127.0.0.1] (real_ip)`, where the parentheses, not the
    square brackets, carry the real sender address."""
    candidates = []
    for pattern in (_BRACKET_RE, _PAREN_RE):
        for m in pattern.finditer(text):
            ip = _parse_ip(m.group(1))
            if ip:
                candidates.append(ip)
    public = [ip for ip in candidates if not _is_special_ip(ip)]
    return public or candidates


def _extract_port(from_raw: str, ip: str | None) -> int | None:
    """The connecting client's TCP port, only when the "from" clause states it right next to the chosen IP:
    `[ip]:port` / `ip:port` (Exim, others) or `port N` / `port=N`. Never guessed - None when absent."""
    if not ip or not from_raw:
        return None
    escaped = re.escape(ip)
    for pattern in (rf"\[{escaped}\]:(\d{{1,5}})\b", rf"(?<![\w:.]){escaped}:(\d{{1,5}})\b", r"\bport[ =:]+(\d{1,5})\b"):
        m = re.search(pattern, from_raw, re.IGNORECASE)
        if m and 1 <= int(m.group(1)) <= 65535:
            return int(m.group(1))
    return None


def parse_received_header(raw_header: str) -> dict:
    normalized = re.sub(r"\s+", " ", raw_header).strip()
    match = _FROM_BY_RE.search(normalized)
    from_raw = match.group("from") if match else ""
    by_host = match.group("by").rstrip(";,") if match else None
    from_host = from_raw.split(" ", 1)[0].strip("[]") if from_raw else None
    candidates = _extract_ip_candidates(from_raw)
    ip = candidates[0] if candidates else _parse_ip(from_host)
    return {"raw": normalized, "from_host": from_host, "by_host": by_host, "ip": ip, "port": _extract_port(from_raw, ip), "is_boundary": False}


def _registrable_domain(host: str | None) -> str | None:
    """Last 2 labels of a host name (e.g. 'sub.foo.outlook.com' -> 'outlook.com').
    Returns None for IP addresses (no "trust domain" can be determined for them)."""
    if not host or _parse_ip(host) is not None:
        return None
    labels = host.lower().split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host.lower()


# Shared relays of large providers: their IP is not the sender's address and must not be reported.
_SHARED_PROVIDER_DOMAINS = {
    "outlook.com", "office365.com", "office.com", "microsoft.com", "hotmail.com", "live.com",
    "google.com", "googlemail.com",
}


def _walk_through_relays(hops: list[dict], start: int) -> tuple[int, str, bool]:
    """The boundary hop is sometimes only a provider relay (e.g. Microsoft Exchange Online hands the mail over to
    the recipient) and the real sender connected to that provider earlier. If an older hop has the provider
    domain (the "from" of the boundary hop) as "by", we walk through the provider's internal hops to the first
    one whose "from" is outside it - there the provider recorded the address of the connecting client.
    Returns (hop index, description of the walk, whether the message originated inside a shared provider)."""
    cur = start
    visited = []
    origin_inside_provider = False
    while True:
        relay = _registrable_domain(hops[cur]["from_host"])
        nxt = cur + 1
        if not relay or nxt >= len(hops) or _registrable_domain(hops[nxt]["by_host"]) != relay:
            break
        j = nxt
        while j < len(hops) and _registrable_domain(hops[j]["from_host"]) == relay:
            j += 1
        if j >= len(hops):
            origin_inside_provider = relay in _SHARED_PROVIDER_DOMAINS
            break
        found_ip = hops[j]["ip"]
        if not found_ip or _is_special_ip(found_ip):
            break  # the older hop is the provider's internal network (private address) - stay at the current one
        visited.append(relay)
        cur = j
    note = ""
    if visited:
        note = " " + t("parser.relay_note", relay=visited[0], chain=" -> ".join(visited))
    return cur, note, origin_inside_provider


def _find_boundary_hop(received_headers: list[str]) -> tuple[dict | None, list[dict], str, str]:
    """Received headers are prepended at every hop, so `received_headers[0]` is the newest (last delivery) and
    the oldest (first entry into the network) is at the end of the list. In a multi-hop chain of one provider
    (e.g. Microsoft 365) most of the initial hops are internal transfers between its own servers - they may use
    formally "public" IP addresses (not RFC1918/loopback), so a plain "is the IP private" check does not filter
    them out. Instead we walk down from the newest hop and compare the domain of the "from" host with the domain
    of the "by" host of the first hop (taken as trusted) - as long as they match, the hop is internal. The first
    hop where they differ (or where "from" is just an IP/placeholder such as [127.0.0.1], the typical way a mail
    gateway records the actually connecting client) is the boundary of the trusted infrastructure - its IP is
    the one worth reporting."""
    hops = [parse_received_header(h) for h in received_headers]
    if not hops:
        return None, [], "low", t("parser.no_received")

    # Trusted domain = "by" of the newest hop that gives it (the first Gmail header is "by <id> with SMTP"
    # without a host, so we take the first hop with a recognisable "by").
    trusted_suffix = next((d for d in (_registrable_domain(h["by_host"]) for h in hops) if d), None)
    boundary_index = len(hops) - 1
    left_trusted_domain = False
    for i, hop in enumerate(hops):
        if hop["from_host"] is None and hop["ip"] is None:
            continue  # hop without "from" (the recipient's own entry) - it says nothing about the sender
        if trusted_suffix and _registrable_domain(hop["from_host"]) == trusted_suffix:
            continue
        boundary_index = i
        left_trusted_domain = True
        break

    relay_note = ""
    origin_inside_provider = False
    if left_trusted_domain:
        boundary_index, relay_note, origin_inside_provider = _walk_through_relays(hops, boundary_index)

    # The boundary hop may have no recognised IP (e.g. an unusual header format) - in that case we keep
    # looking towards the oldest hops, where an IP does appear.
    ip_index = boundary_index
    while ip_index < len(hops) and hops[ip_index]["ip"] is None:
        ip_index += 1
    if ip_index == len(hops):
        ip_index = boundary_index

    if origin_inside_provider:
        return None, hops, "low", t("parser.origin_inside_provider")

    hops[ip_index]["is_boundary"] = True
    boundary = hops[ip_index]

    if boundary["ip"] is None:
        confidence = "low"
        reasoning = t("parser.no_ip")
    elif left_trusted_domain:
        confidence = "high"
        reasoning = t("parser.boundary", host=boundary["from_host"], domain=trusted_suffix) + relay_note
    elif trusted_suffix is None:
        confidence = "medium"
        reasoning = t("parser.single_received")
    else:
        confidence = "low"
        reasoning = t("parser.whole_chain_trusted", domain=trusted_suffix)

    return boundary, hops, confidence, reasoning


def _parse_auth_results(header_value: str) -> dict[str, str]:
    out = {}
    for mechanism in ("spf", "dkim", "dmarc"):
        m = re.search(rf"{mechanism}=(\w+)", header_value, re.IGNORECASE)
        if m:
            out[mechanism] = m.group(1).lower()
    return out


_COMMON_DISPLAY_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv",
    "jpg", "jpeg", "png", "gif", "bmp", "zip", "rar",
}


def _extract_attachments(msg: Message) -> list[dict]:
    """`declared_extension` is the real (last) extension of the file. `apparent_extension` detects the classic
    double-extension phishing trick (e.g. "invoice.pdf.exe") - it is set only when the second-to-last segment of
    the name looks like a popular, "innocent" document/image extension different from the real one."""
    attachments = []
    for part in msg.walk():
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True) or b""
        segments = filename.split(".")
        declared_ext = segments[-1].lower() if len(segments) > 1 else ""
        apparent_ext = None
        if len(segments) > 2:
            candidate = segments[-2].lower()
            if candidate in _COMMON_DISPLAY_EXTENSIONS and candidate != declared_ext:
                apparent_ext = candidate
        attachments.append(
            {
                "filename": filename,
                "size_bytes": len(payload),
                "content_type": part.get_content_type(),
                "declared_extension": declared_ext,
                "apparent_extension": apparent_ext,
            }
        )
    return attachments


def _decode_part(part: Message) -> str:
    try:
        return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_body_text(msg: Message) -> str:
    """Many phishing e-mails are pure HTML without a text/plain part - without the HTML
    fallback the message body never reached the analysis (neither the BTC/ransom detection nor the LLM prompt)."""
    if msg.is_multipart():
        plain_parts, html_parts = [], []
        for part in msg.walk():
            if part.get_filename():
                continue
            if part.get_content_type() == "text/plain":
                plain_parts.append(_decode_part(part))
            elif part.get_content_type() == "text/html":
                html_parts.append(_decode_part(part))
        if plain_parts:
            return "\n".join(plain_parts)
        if html_parts:
            return "\n".join(_html_to_text(p) for p in html_parts)
        return ""

    raw = _decode_part(msg)
    if msg.get_content_type() == "text/html":
        return _html_to_text(raw)
    return raw


def parse_message(raw_email: str) -> Message:
    """Parses the pasted source once; the functions below accept the result instead of the raw text, so that one
    request does not parse the same e-mail five times."""
    return message_from_string(_refold_headers(raw_email))


def _as_message(source: str | Message) -> Message:
    return source if isinstance(source, Message) else parse_message(source)


def extract_addresses(source: str | Message) -> dict:
    """Lower-cased addresses from From, Return-Path (envelope sender) and Delivered-To/To (recipients)."""
    msg = _as_message(source)

    def addrs(*names: str) -> list[str]:
        values = [v for name in names for v in (msg.get_all(name) or [])]
        return [a.lower() for _, a in getaddresses([str(v) for v in values]) if a]

    return {
        "from": addrs("From"),
        "return_path": addrs("Return-Path"),
        "recipients": addrs("Delivered-To", "X-Original-To", "To"),
    }


def parse_email(source: str | Message) -> dict:
    msg = _as_message(source)

    received_headers = msg.get_all("Received") or []
    boundary_hop, hop_chain, ip_confidence, ip_reasoning = _find_boundary_hop(received_headers)
    trusted_ip = boundary_hop["ip"] if boundary_hop else None

    # Servers without their own Authentication-Results (e.g. Exim) leave the results only in Microsoft/ARC headers.
    auth_header = (
        msg.get("Authentication-Results")
        or msg.get("X-MS-Exchange-Authentication-Results")
        or msg.get("ARC-Authentication-Results")
        or ""
    )
    auth_results = _parse_auth_results(auth_header)

    date_header = msg.get("Date")
    date_parsed = None
    age_days = None
    age_ok = False
    if date_header:
        try:
            date_parsed = parsedate_to_datetime(date_header)
            if date_parsed.tzinfo is None:
                date_parsed = date_parsed.replace(tzinfo=timezone.utc)
            age_days, age_ok = attack_age(date_parsed)
        except (TypeError, ValueError):
            pass

    body = _extract_body_text(msg)
    btc_matches = sorted(set(_BTC_RE.findall(body)))
    ransom_hint = any(kw in body.lower() for kw in _RANSOM_KEYWORDS)

    if trusted_ip:
        ip_ok, ip_reject_reason = is_reportable_ip(trusted_ip)
    else:
        ip_ok, ip_reject_reason = False, t("parser.no_public_ip")

    return {
        "trusted_source_ip": trusted_ip,
        "source_port": boundary_hop.get("port") if boundary_hop else None,
        "ip_ok": ip_ok,
        "ip_reject_reason": ip_reject_reason,
        "ip_confidence": ip_confidence,
        "ip_reasoning": ip_reasoning,
        "received_chain": [
            {"from_host": h["from_host"], "ip": h["ip"], "port": h["port"], "by_host": h["by_host"], "is_boundary": h["is_boundary"]}
            for h in hop_chain
        ],
        "from": msg.get("From"),
        "to": msg.get("To"),
        "subject": msg.get("Subject"),
        "message_id": msg.get("Message-ID"),
        "date": date_header,
        "date_parsed": date_parsed.isoformat() if date_parsed else None,
        "age_days": age_days,
        "age_ok": age_ok,
        "spf": auth_results.get("spf"),
        "dkim": auth_results.get("dkim"),
        "dmarc": auth_results.get("dmarc"),
        "spoofing_suspected": auth_results.get("spf") == "fail" or auth_results.get("dmarc") == "fail",
        "attachments": _extract_attachments(msg),
        "btc_addresses_found": btc_matches,
        "ransom_keywords_found": ransom_hint,
    }

from __future__ import annotations

import hashlib
import html as html_module
import re
from datetime import timezone
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime

from backend.i18n import t
from backend.mail_source import attachment_info, load_message, unfold
from backend.mail_trust import (
    PROVIDER_FAMILIES,
    family,
    hop_corroboration,
    hop_specific_auth,
    is_dotless_internal_hop,
    is_special_ip,
    parse_ip,
    receiver_auth,
    registrable_domain,
)
from backend.report_utils import attack_age, is_reportable_ip

# Candidates only: a match counts as a Bitcoin address after `is_valid_btc_address` has checked its checksum. Native
# SegWit addresses are up to 90 characters long (the bech32 limit); the usual ones are 42 (pay-to-witness-pubkey-hash)
# and 62 (pay-to-witness-script-hash, Taproot).
_BTC_RE = re.compile(r"\b(bc1[a-z0-9]{25,87}|BC1[A-Z0-9]{25,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
# Whole words only (a substring such as "subpayment" or "cryptography" is no sign of a ransom demand), with the common
# endings of the same word.
_RANSOM_RE = re.compile(
    r"\b(?:bitcoins?|btc|ransom(?:ware)?|payments?|wallets?|crypto(?:currenc(?:y|ies))?|decrypt(?:ed|ion|or)?)\b", re.IGNORECASE
)
_FROM_BY_RE = re.compile(r"from\s+(?P<from>.+?)\s+by\s+(?P<by>\S+)", re.IGNORECASE)
_HTML_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_HTML_BLOCK_CLOSE_RE = re.compile(r"</(p|div|tr|li|h[1-6]|table)>|<br\s*/?>", re.IGNORECASE)
_BLANK_LINES_RE = re.compile(r"\n{3,}")

# Size limits for hostile input (a Received header is attacker-controlled text). They bound the work of the parsers so
# one oversized message cannot keep the server busy; real headers are far below them.
MAX_RECEIVED_CHARS = 8192  # characters of ONE Received header that are analysed
MAX_RECEIVED_HEADERS = 100  # Received headers analysed, newest first (a real route has a handful)


_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BECH32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_CONST = 1  # BIP-173: native SegWit version 0
_BECH32M_CONST = 0x2BC830A3  # BIP-350: versions 1 to 16


def _base58check_valid(address: str) -> bool:
    """A legacy address (starts with 1 or 3) is 25 bytes: a version byte (0x00 pay-to-pubkey-hash, 0x05
    pay-to-script-hash), a 20-byte hash and the first 4 bytes of the double SHA-256 of the first 21 as the checksum.
    See https://en.bitcoin.it/wiki/Base58Check_encoding."""
    number = 0
    for char in address:
        number = number * 58 + _BASE58.index(char)
    if number >> 200:
        return False  # more than 25 bytes
    raw = number.to_bytes(25, "big")
    leading_ones = len(address) - len(address.lstrip("1"))
    if leading_ones != len(raw) - len(raw.lstrip(b"\0")):
        return False  # every leading "1" stands for exactly one zero byte, and only for those
    return raw[0] in (0x00, 0x05) and hashlib.sha256(hashlib.sha256(raw[:21]).digest()).digest()[:4] == raw[21:]


def _bech32_polymod(values: list[int]) -> int:
    generator = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    checksum = 1
    for value in values:
        top = checksum >> 25
        checksum = (checksum & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            if (top >> i) & 1:
                checksum ^= generator[i]
    return checksum


def _bech32_valid(address: str) -> bool:
    """A native SegWit address (starts with bc1): BIP-173 (bech32, witness version 0, program of 20 or 32 bytes) and
    BIP-350 (bech32m, versions 1 to 16, program of 2 to 40 bytes). Upper case is allowed when used throughout (QR
    codes), mixed case is not."""
    if address != address.lower() and address != address.upper():
        return False
    address = address.lower()
    if not address.startswith("bc1") or len(address) > 90:
        return False
    data_chars = address[3:]
    if any(char not in _BECH32 for char in data_chars) or len(data_chars) < 7:
        return False
    data = [_BECH32.index(char) for char in data_chars]
    checksum_ok = _bech32_polymod([ord(char) >> 5 for char in "bc"] + [0] + [ord(char) & 31 for char in "bc"] + data)
    version, payload = data[0], data[1:-6]
    if version > 16 or checksum_ok != (_BECH32_CONST if version == 0 else _BECH32M_CONST):
        return False
    # the payload is 5-bit groups of the witness program: regroup into bytes; leftover bits must be fewer than 5 and zero
    accumulator, bits, program = 0, 0, []
    for value in payload:
        accumulator = (accumulator << 5) | value
        bits += 5
        while bits >= 8:
            bits -= 8
            program.append((accumulator >> bits) & 0xFF)
        accumulator &= (1 << bits) - 1
    if bits >= 5 or accumulator:
        return False
    return (len(program) in (20, 32)) if version == 0 else 2 <= len(program) <= 40


def is_valid_btc_address(address: str) -> bool:
    """True when `address` is a well-formed Bitcoin mainnet address with a correct checksum - a random string that
    merely looks like one (a tracking number, an order id) fails the checksum with a probability of about 1 - 2^-32."""
    if address[:3].lower() == "bc1":
        return _bech32_valid(address)
    return address[:1] in ("1", "3") and all(char in _BASE58 for char in address) and _base58check_valid(address)


def _enclosed(text: str, opening: str, closing: str) -> list[str]:
    """The non-empty texts between `opening` and the next `closing`, left to right and non-overlapping - exactly what
    the regular expressions `\\(([^)]+)\\)` and `\\[([^\\]]+)\\]` returned (an opening character inside a group stays in
    it, so `(a (b)` yields `a (b`). Those expressions take quadratic time on a long run of unclosed brackets, because
    the engine rescans to the end of the text from every opening character; here a missing closing character ends
    the search at once, so the time is linear."""
    groups = []
    pos = text.find(opening)
    while pos != -1:
        end = text.find(closing, pos + 1)
        if end == -1:
            break  # no closing character anywhere after this point, so no later group can exist either
        if end > pos + 1:
            groups.append(text[pos + 1:end])
            pos = text.find(opening, end + 1)
        else:
            pos = text.find(opening, pos + 1)  # "()" holds nothing
    return groups


def _strip_html_tags(text: str) -> str:
    """Removes every `<...>` run (at least one character inside, `<` allowed inside) - the same result as
    `re.sub(r"<[^>]+>", "", text)`, but linear on a long run of unclosed `<` (see `_enclosed`)."""
    out = []
    pos = 0
    while True:
        start = text.find("<", pos)
        end = text.find(">", start + 1) if start != -1 else -1
        if end == -1:
            out.append(text[pos:])
            return "".join(out)
        if end > start + 1:
            out.append(text[pos:start])
            pos = end + 1
        else:
            out.append(text[pos:start + 1])  # "<>" is kept as it is
            pos = start + 1



def _html_to_text(html: str) -> str:
    """Turns HTML into readable text without external dependencies: removes script/style, turns closing block
    tags into newlines, strips the remaining tags, decodes HTML entities and collapses extra blank lines."""
    text = _HTML_SCRIPT_STYLE_RE.sub(" ", html)
    text = _HTML_BLOCK_CLOSE_RE.sub("\n", text)
    text = _strip_html_tags(text)
    text = html_module.unescape(text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def _extract_ip_candidates(text: str) -> list[str]:
    """Collects all IP addresses mentioned in the "from" clause of a Received header - both in the [IP] form
    (MTA convention for rDNS/real IP) and in plain parentheses (which may also hold host names such as
    "HELO foo" that do not parse as an IP and are dropped). Public addresses take precedence over loopback/
    private ones - MTAs such as Microsoft EOP may write `[127.0.0.1] (real_ip)`, where the parentheses, not the
    square brackets, carry the real sender address."""
    candidates = []
    for in_parens, group in [(False, g) for g in _enclosed(text, "[", "]")] + [(True, g) for g in _enclosed(text, "(", ")")]:
        ip = parse_ip(group)
        if ip:
            candidates.append(ip)
        elif in_parens:
            # "(host.example. 192.0.2.1)": a verified reverse-DNS name followed by the address, no brackets
            candidates.extend(found for token in re.split(r"[\s\[\]]+", group) if (found := parse_ip(token.rstrip(".,;"))))
    public = [ip for ip in candidates if not is_special_ip(ip)]
    return public or candidates


def _rdns_host(from_raw: str) -> str | None:
    """The reverse-DNS name the RECEIVING server wrote next to the address, e.g. `(mail.example.org. [192.0.2.1])`.
    Unlike the first word after "from" (the HELO name, which the connecting machine chooses freely), mail servers
    such as Postfix, Exim and Gmail print this name only after looking it up themselves, so the sender cannot
    simply claim another one."""
    for group in _enclosed(from_raw, "(", ")"):
        tokens = [tok for tok in re.split(r"[\s\[\]]+", group) if tok]
        name = tokens[0].rstrip(".").lower() if tokens else ""
        if len(tokens) >= 2 and "." in name and parse_ip(name) is None and any(parse_ip(tok.rstrip(".,;")) for tok in tokens[1:]):
            return name
    return None


def parse_received_header(raw_header: str) -> dict:
    normalized = re.sub(r"\s+", " ", raw_header[:MAX_RECEIVED_CHARS]).strip()
    match = _FROM_BY_RE.search(normalized)
    from_raw = match.group("from") if match else ""
    by_host = match.group("by").rstrip(";,") if match else None
    from_host = from_raw.split(" ", 1)[0].strip("[]") if from_raw else None
    helo_host = from_host
    # A HELO name from another operator than the verified reverse-DNS name is a claim that does not hold up (a sender
    # introducing itself as a big provider): the verified name is the one that counts for the trust decisions.
    rdns = _rdns_host(from_raw)
    if rdns and from_host and parse_ip(from_host) is None and family(registrable_domain(rdns)) != family(registrable_domain(from_host)):
        from_host = rdns
    candidates = _extract_ip_candidates(from_raw)
    ip = candidates[0] if candidates else parse_ip(from_host)
    return {"raw": normalized, "from_host": from_host, "helo_host": helo_host, "by_host": by_host, "ip": ip, "is_boundary": False}


def _walk_through_relays(hops: list[dict], start: int) -> tuple[int, str, bool, str | None]:
    """The boundary hop is sometimes only a provider relay (e.g. Microsoft Exchange Online hands the mail over to
    the recipient) and the real sender connected to that provider earlier. If an older hop has the provider
    domain (the "from" of the boundary hop) as "by", we walk through the provider's internal hops to the first
    one whose "from" is outside it - there the provider recorded the address of the connecting client. Some
    providers (e.g. OVH's "ghost" mail-out) name their internal hops after bare, dotless pod/container
    identifiers instead of a subdomain - those also count as "still inside the relay" via
    is_dotless_internal_hop, but only while their own recorded IP is itself private/absent, so a genuinely
    external hop is never mistaken for an internal one. The walk only happens for a known provider family or
    through such internal pod hops: the older lines are written by the relay, and an unknown relay may be the
    sender's own server.
    Returns (hop index, description of the walk, whether the message originated inside a shared provider, the
    relay whose older lines were deliberately NOT used, if any)."""
    cur = start
    visited = []
    origin_inside_provider = False
    declined: str | None = None
    while True:
        relay = registrable_domain(hops[cur]["from_host"])
        nxt = cur + 1
        # The older lines were written by the relay itself, so walking into them means believing the relay. That is
        # justified for a well-known provider, or when they only show internal pod names with private addresses; for
        # any other host (an unknown, possibly sender-controlled server) a forged chain of "by"/"from" links must not
        # be able to move the reported IP.
        believed = (
            nxt < len(hops)
            and (
                (
                    registrable_domain(hops[nxt]["by_host"]) == relay
                    and (family(relay) in PROVIDER_FAMILIES or is_dotless_internal_hop(hops[nxt]["from_host"], hops[nxt]["ip"]))
                )
                or is_dotless_internal_hop(hops[nxt]["by_host"], hops[nxt]["ip"])
            )
        )
        if not relay or not believed:
            if relay and nxt < len(hops) and (
                registrable_domain(hops[nxt]["by_host"]) == relay or is_dotless_internal_hop(hops[nxt]["by_host"], hops[nxt]["ip"])
            ):
                declined = relay  # older lines of this relay exist, but nothing makes them trustworthy
            break
        j = nxt
        while j < len(hops) and (
            registrable_domain(hops[j]["from_host"]) == relay
            or is_dotless_internal_hop(hops[j]["from_host"], hops[j]["ip"])
        ):
            j += 1
        if j >= len(hops):
            origin_inside_provider = family(relay) in PROVIDER_FAMILIES
            break
        found_ip = hops[j]["ip"]
        if not found_ip or is_special_ip(found_ip):
            break  # the older hop is the provider's internal network (private address) - stay at the current one
        visited.append(relay)
        cur = j
    note = ""
    if visited:
        note = " " + t("parser.relay_note", relay=visited[0], chain=" -> ".join(visited))
    return cur, note, origin_inside_provider, declined


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
    hops = [parse_received_header(h) for h in received_headers[:MAX_RECEIVED_HEADERS]]
    if not hops:
        return None, [], "low", t("parser.no_received")

    # Trusted domain = "by" of the newest hop that gives it (the first Gmail header is "by <id> with SMTP"
    # without a host, so we take the first hop with a recognisable "by").
    trusted_suffix = next((d for d in (registrable_domain(h["by_host"]) for h in hops) if d), None)
    boundary_index = len(hops) - 1
    left_trusted_domain = False
    for i, hop in enumerate(hops):
        if hop["from_host"] is None and hop["ip"] is None:
            continue  # hop without "from" (the recipient's own entry) - it says nothing about the sender
        if trusted_suffix and family(registrable_domain(hop["from_host"])) == family(trusted_suffix):
            continue
        boundary_index = i
        left_trusted_domain = True
        break

    relay_note = ""
    origin_inside_provider = False
    declined_relay = None
    first_outside_index = boundary_index  # the hop the recipient's own server wrote for the first outside machine
    if left_trusted_domain:
        boundary_index, relay_note, origin_inside_provider, declined_relay = _walk_through_relays(hops, boundary_index)

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
        if relay_note:
            # The address comes from older lines written by the relay itself, not by the recipient's server: they
            # cannot be verified here and a sender may have forged them, so say so instead of claiming certainty.
            confidence = "medium"
            reasoning += " " + t("parser.relay_walk_warning", ip=hops[first_outside_index]["ip"] or "?")
            boundary["via_relay_lines"] = True
        if declined_relay:
            reasoning += " " + t("parser.relay_declined", relay=declined_relay)
    elif trusted_suffix is None:
        confidence = "medium"
        reasoning = t("parser.single_received")
    else:
        confidence = "low"
        reasoning = t("parser.whole_chain_trusted", domain=trusted_suffix)

    return boundary, hops, confidence, reasoning


def find_boundary_index(received_headers: list[str]) -> tuple[int | None, str]:
    """Public, tab-agnostic wrapper around _find_boundary_hop: runs the exact same walk used to pick the
    AbuseIPDB report's IP (including walking through same-relay internal hops, dotless pod names included),
    but returns just the resulting hop INDEX (into `received_headers`, newest-first) and confidence - not
    AbuseIPDB's own worded reasoning - so other callers (the Email tab) can reuse the walk's result under
    their own wording instead of adopting `parser.*` phrasing. None means no usable boundary was found
    (e.g. the message never left a single shared provider, or no IP could be recovered at all)."""
    boundary, hops, confidence, _reasoning = _find_boundary_hop(received_headers)
    if boundary is None:
        return None, confidence
    return next(i for i, h in enumerate(hops) if h is boundary), confidence


_CONFIDENCE_LADDER = {"low": "medium", "medium": "high", "high": "high"}


def _apply_auth_corroboration(confidence: str, reasoning: str, corroboration: dict) -> tuple[str, str, dict | None]:
    """Turns a hop-specific SMTP-AUTH/DKIM corroboration into extra reasoning text and (only when the SMTP-AUTH
    account's domain matches the validated DKIM domain) a one-step confidence bump. Never changes which IP was
    selected - this only explains and reinforces the choice _find_boundary_hop already made."""
    per_hop = hop_corroboration(corroboration)
    if not per_hop:
        return confidence, reasoning, None
    account, dkim_domain, consistent = per_hop["smtp_auth_account"], per_hop["dkim_domain"], per_hop["consistent"]
    if consistent is True:
        reasoning += " " + t("parser.smtp_auth_consistent", account=account, domain=dkim_domain)
        confidence = _CONFIDENCE_LADDER.get(confidence, confidence)
    elif consistent is False:
        reasoning += " " + t("parser.smtp_auth_mismatch", account=account, domain=dkim_domain)
    else:
        reasoning += " " + t("parser.smtp_auth_no_dkim", account=account)
    return confidence, reasoning, per_hop


def _extract_attachments(msg: Message) -> list[dict]:
    """`declared_extension` is the real (last) extension of the file. `apparent_extension` detects the classic
    double-extension phishing trick (e.g. "invoice.pdf.exe") - it is set only when the second-to-last segment of
    the name looks like a popular, "innocent" document/image extension different from the real one. The name is
    read by `mail_source.attachment_info`, the same description the Email tab builds on."""
    attachments = []
    for part in msg.walk():
        info = attachment_info(part)
        if info:
            attachments.append(
                {
                    "filename": info["filename"],
                    "size_bytes": info["size"],
                    "content_type": info["content_type"],
                    "declared_extension": info["extension"],
                    "apparent_extension": info["double_extension_as"],
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
    request does not parse the same e-mail five times. The text is read exactly like the Email tab reads it
    (`mail_source.load_message`: BOM, mbox envelope, leading blank lines, lost header indentation)."""
    return load_message(raw_email)


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
    if len(received_headers) > MAX_RECEIVED_HEADERS:
        ip_reasoning += " " + t("parser.too_many_received", limit=MAX_RECEIVED_HEADERS, total=len(received_headers))
    trusted_ip = boundary_hop["ip"] if boundary_hop else None

    # SMTP-AUTH/DKIM corroboration for every hop (not just the boundary) - so a manual override to a different
    # candidate hop keeps this context too; only the boundary hop's result feeds the confidence/reasoning text.
    boundary_index = next((i for i, h in enumerate(hop_chain) if h.get("is_boundary")), None)
    hop_auth = hop_specific_auth(list(msg.items()), len(hop_chain))
    boundary_auth_corroboration = None
    for i, h in enumerate(hop_chain):
        per_hop = hop_corroboration(hop_auth.get(i))
        h["smtp_auth_account"] = per_hop["smtp_auth_account"] if per_hop else None
        h["dkim_domain"] = per_hop["dkim_domain"] if per_hop else None
        h["auth_consistent"] = per_hop["consistent"] if per_hop else None
        if i == boundary_index and per_hop:
            ip_confidence, ip_reasoning, boundary_auth_corroboration = _apply_auth_corroboration(
                ip_confidence, ip_reasoning, hop_auth[i]
            )

    # An SMTP-AUTH/DKIM bonus above must not lift an address taken from relay-written lines back to "high": the
    # Authentication-Results line next to a forged Received line can be forged too.
    via_relay_lines = bool(boundary_hop and boundary_hop.get("via_relay_lines"))
    if via_relay_lines and ip_confidence == "high":
        ip_confidence = "medium"

    # The receiver's own verdicts, read by the same code as in the Email tab (mail_trust.receiver_auth): Microsoft 365
    # without a server name, X-MS-Exchange-Authentication-Results and, for servers such as Exim, the ARC copy.
    auth_results = receiver_auth([(name, unfold(value)) for name, value in msg.items()], [h["by_host"] for h in hop_chain])

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
    btc_matches = sorted({found for found in _BTC_RE.findall(body) if is_valid_btc_address(found)})
    ransom_hint = bool(_RANSOM_RE.search(body))

    if trusted_ip:
        ip_ok, ip_reject_reason = is_reportable_ip(trusted_ip)
    else:
        ip_ok, ip_reject_reason = False, t("parser.no_public_ip")

    return {
        "trusted_source_ip": trusted_ip,
        "ip_ok": ip_ok,
        "ip_reject_reason": ip_reject_reason,
        "ip_confidence": ip_confidence,
        "ip_from_relay_lines": via_relay_lines,
        "ip_reasoning": ip_reasoning,
        "boundary_auth_corroboration": boundary_auth_corroboration,
        "received_chain": [
            {
                "from_host": h["from_host"], "ip": h["ip"], "by_host": h["by_host"], "is_boundary": h["is_boundary"],
                "is_private": is_special_ip(h["ip"]) if h["ip"] else None,
                "smtp_auth_account": h["smtp_auth_account"], "dkim_domain": h["dkim_domain"],
                "auth_consistent": h["auth_consistent"],
            }
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
        "spf": auth_results["spf"],
        "dkim": auth_results["dkim"],
        "dmarc": auth_results["dmarc"],
        "spoofing_suspected": auth_results["spf"] == "fail" or auth_results["dmarc"] == "fail",
        "attachments": _extract_attachments(msg),
        "btc_addresses_found": btc_matches,
        "ransom_keywords_found": ransom_hint,
    }

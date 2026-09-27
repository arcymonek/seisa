"""Shared helpers for reasoning about the trust of a mail relay chain (Received headers, host/domain
classification, SMTP-AUTH/DKIM correlation) - used by both the "AbuseIPDB" tab (email_parser.py, which picks
one boundary IP to report) and the "Email" tab (email_forensics.py, which shows the whole chain and lets an
LLM build an educational reading of it). Kept in one place because these two tabs used to carry independent,
slowly-drifting copies of the same logic - a bug fixed in one copy but not the other went unnoticed for a
release.
"""
from __future__ import annotations

import ipaddress
import re


def unfold(value: str) -> str:
    """Collapses an RFC 5322 folded header value's embedded newline+indentation into a single space, so a regex
    looking for a value that happens to sit right at a fold boundary is not cut short."""
    return re.sub(r"\n[ \t]+", " ", str(value)).strip()


def parse_ip(candidate: str | None) -> str | None:
    if not candidate:
        return None
    try:
        return str(ipaddress.ip_address(candidate.strip()))
    except ValueError:
        return None


def is_special_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


# Public suffixes that are themselves two labels long (e.g. "co.uk") - for these, the registrable domain needs
# the label before the suffix too, or unrelated organisations sharing the suffix would collapse onto one "domain".
TWO_LEVEL_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "com.au", "net.au", "com.pl", "net.pl", "org.pl", "co.jp", "com.br", "co.nz",
    "com.tr", "co.za", "com.cn", "co.in", "com.mx", "com.ar", "co.kr",
}


def registrable_domain(host: str | None) -> str | None:
    """Last 2 labels of a host name (e.g. 'sub.foo.outlook.com' -> 'outlook.com'), or the last 3 when the last 2
    are a known two-level public suffix (e.g. 'mail.example.co.uk' -> 'example.co.uk', not just 'co.uk', which
    would otherwise wrongly equate every unrelated co.uk organisation). Returns None for IP addresses (no "trust
    domain" can be determined for them)."""
    if not host or parse_ip(host) is not None:
        return None
    host = host.strip().strip(".").lower()
    labels = host.split(".")
    if len(labels) < 2:
        return host
    if ".".join(labels[-2:]) in TWO_LEVEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def is_dotless_internal_hop(host: str | None, ip: str | None) -> bool:
    """A bare internal identifier (e.g. a Kubernetes pod name such as 'ghost-submission-c7b579475-4mz8d') has no
    dot and cannot, by definition, belong to some OTHER external domain the way a real host name could - but only
    when the IP recorded alongside it is itself private/absent. A dotless name paired with a public IP is NOT
    waved through: it should still be treated as a genuine, informative hop, since a real external hop must never
    be mistaken for an internal relay step."""
    if not host or "." in host or parse_ip(host) is not None:
        return False
    return ip is None or is_special_ip(ip)


# Big mail ecosystems whose own internal relay hops are not the sender's address and must not be reported/relied
# on as "the trust boundary" by themselves - grouped into families because one operator may use several domains.
PROVIDER_FAMILIES = {
    "microsoft": {"microsoft.com", "outlook.com", "office365.com", "office.com", "hotmail.com", "live.com", "msn.com"},
    "google": {"google.com", "gmail.com", "googlemail.com"},
    "yahoo": {"yahoo.com", "yahoodns.net", "yahoo.co.jp"},
    "apple": {"icloud.com", "me.com", "apple.com"},
    "proton": {"proton.me", "protonmail.ch", "protonmail.com"},
}


def family(domain: str | None) -> str | None:
    """Operator family key for a domain (an unknown domain is its own family)."""
    if not domain:
        return None
    for key, members in PROVIDER_FAMILIES.items():
        if domain in members:
            return key
    return domain


def domains_consistent(a: str | None, b: str | None) -> bool:
    """Label-boundary-safe domain comparison (same pattern as known_senders.match_known_sender) - never a naive
    substring check, which a lookalike domain could defeat."""
    if not a or not b:
        return False
    a, b = a.lower().rstrip("."), b.lower().rstrip(".")
    return a == b or a.endswith("." + b) or b.endswith("." + a)


_SMTP_AUTH_RE = re.compile(r"(?<!smtp\.)\bauth=(\w+)", re.IGNORECASE)
_SMTP_AUTH_ACCOUNT_RE = re.compile(r"smtp\.auth=([^\s;]+)", re.IGNORECASE)
_DKIM_DOMAIN_RE = re.compile(r"header\.d=([^\s;]+)", re.IGNORECASE)


def parse_hop_auth(header_value: str) -> dict | None:
    """SMTP-AUTH/DKIM details from a single Authentication-Results value. Returns None when there is no `auth=`
    (SMTP-AUTH) verdict at all - a message with only spf/dkim/dmarc gives no SMTP-AUTH signal to correlate with
    a hop."""
    auth_match = _SMTP_AUTH_RE.search(header_value)
    if not auth_match:
        return None
    account_match = _SMTP_AUTH_ACCOUNT_RE.search(header_value)
    dkim_match = re.search(r"\bdkim=(\w+)", header_value, re.IGNORECASE)
    domain_match = _DKIM_DOMAIN_RE.search(header_value)
    dkim_domain = domain_match.group(1).strip('"') if domain_match and dkim_match and dkim_match.group(1).lower() == "pass" else None
    return {
        "auth": auth_match.group(1).lower(),
        "smtp_auth_account": account_match.group(1).strip('"') if account_match else None,
        "dkim_domain": dkim_domain,
    }


def hop_specific_auth(headers: list[tuple[str, str]], hop_count: int) -> dict[int, dict]:
    """Maps hop index -> parse_hop_auth result, for the `headers` list in original (unsorted) order, but only
    for an Authentication-Results entry that is the IMMEDIATE next header after that hop's Received entry - the
    exact pattern real MTAs use when they stamp both at once. This positional check (not a text/authserv-id
    match) is what keeps the signal from being spoofed by a fake Authentication-Results header planted
    elsewhere in a forged message: anywhere else, it is simply not correlated with any hop. `hop_count` must
    match the number of Received entries the caller itself derived from the same headers, in the same order."""
    received_positions = [i for i, (name, _) in enumerate(headers) if name.lower() == "received"]
    result: dict[int, dict] = {}
    for hop_idx, pos in enumerate(received_positions[:hop_count]):
        nxt = pos + 1
        if nxt < len(headers) and headers[nxt][0].lower() == "authentication-results":
            parsed = parse_hop_auth(unfold(headers[nxt][1]))
            if parsed:
                result[hop_idx] = parsed
    return result

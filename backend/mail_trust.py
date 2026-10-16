"""Shared helpers for reasoning about the trust of a mail relay chain (Received headers, host/domain
classification, SMTP-AUTH/DKIM correlation, the receiver's SPF/DKIM/DMARC verdicts) - used by both the "AbuseIPDB" tab (email_parser.py, which picks
one boundary IP to report) and the "Email" tab (email_forensics.py, which shows the whole chain and lets an
LLM build an educational reading of it). Kept in one place because these two tabs used to carry independent,
slowly-drifting copies of the same logic - a bug fixed in one copy but not the other went unnoticed for a
release.
"""
from __future__ import annotations

import ipaddress
import re

# `unfold` lives in mail_source now; it stays importable from here (tests and older callers use that name)
from backend.mail_source import unfold


def parse_ip(candidate: str | None) -> str | None:
    if not candidate:
        return None
    candidate = candidate.strip()
    # RFC 5321 section 4.1.3: an IPv6 address literal in a Received header is written "[IPv6:2001:db8::1]"
    if candidate[:5].lower() == "ipv6:":
        candidate = candidate[5:]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


# RFC 6598 shared address space (carrier-grade NAT): listed explicitly, the stdlib's is_private for it differs
# between Python releases
SHARED_ADDRESS_SPACE = ipaddress.ip_network("100.64.0.0/10")


def is_special_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
        or ip.is_multicast or ip.is_unspecified
        or (ip.version == 4 and ip in SHARED_ADDRESS_SPACE)
    )


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
    "microsoft": {
        "microsoft.com", "outlook.com", "office365.com", "office.com", "hotmail.com", "live.com", "msn.com",
        "exchangelabs.com",  # Exchange Online internal machines (e.g. MN2PR01CA0066.prod.exchangelabs.com)
    },
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


def hop_corroboration(corroboration: dict | None) -> dict | None:
    """Per-hop SMTP-AUTH/DKIM corroboration (smtp_auth_account/dkim_domain/consistent) from a `parse_hop_auth`
    result, or None when there is nothing to report for the hop: the SMTP-AUTH verdict must be `pass` and name an
    account. `consistent` says whether the domain of the account agrees with the DKIM-validated domain (None when
    there is no validated DKIM domain to compare with). Used by the AbuseIPDB tab (which turns the boundary hop's
    result into reasoning text) and by the Email tab (which annotates every hop); purely informational - it never
    decides which hop is the trust boundary."""
    if not corroboration:
        return None
    account = corroboration.get("smtp_auth_account")
    if corroboration.get("auth") != "pass" or not account:
        return None
    dkim_domain = corroboration.get("dkim_domain")
    account_domain = account.split("@")[-1] if "@" in account else None
    if dkim_domain and domains_consistent(account_domain, dkim_domain):
        return {"smtp_auth_account": account, "dkim_domain": dkim_domain, "consistent": True}
    if dkim_domain:
        return {"smtp_auth_account": account, "dkim_domain": dkim_domain, "consistent": False}
    return {"smtp_auth_account": account, "dkim_domain": None, "consistent": None}


# ---------------------------------------------------------------------------
# the receiver's own verdicts (SPF / DKIM / DMARC)
# ---------------------------------------------------------------------------

# Headers that carry the receiver's verdicts, in the order they are preferred when several kinds are present. The
# plain Authentication-Results is what the receiving server prepends itself (RFC 8601). Microsoft's variant is the
# same text, usually without the leading server name. ARC copies are a last resort (servers such as Exim leave their
# results only there).
AUTH_RESULT_HEADERS = ("authentication-results", "x-ms-exchange-authentication-results", "arc-authentication-results")
_AUTH_ENTRY_HEADERS = (*AUTH_RESULT_HEADERS, "received-spf")
_RESULT_RE = re.compile(r"\b(spf|dkim|dmarc|arc|dkim-atps|compauth)\s*=\s*([a-z]+)", re.IGNORECASE)
_DETAIL_RE = re.compile(r"\b(smtp\.mailfrom|smtp\.helo|header\.from|header\.d|header\.i|header\.s)\s*=\s*([^\s;]+)", re.IGNORECASE)
_RECEIVED_SPF_RE = re.compile(r"\s*(pass|fail|softfail|neutral|none|temperror|permerror)", re.IGNORECASE)


def authserv_id(value: str) -> str | None:
    """The server name an Authentication-Results value starts with (RFC 8601): the first word before the first `;`,
    after an optional ARC `i=N;`. Microsoft 365 writes no server name and starts straight with `spf=pass ...`, so a
    first word that contains `=` is a result, not a name -> None."""
    body = re.sub(r"^\s*i\s*=\s*\d+\s*;\s*", "", value)
    tokens = body.split(";", 1)[0].split()
    return tokens[0] if tokens and "=" not in tokens[0] else None


def _family_of_host(host: str | None) -> str | None:
    return family(registrable_domain((host or "").strip("[]")))


def auth_entries(headers: list[tuple[str, str]], by_hosts: list[str | None]) -> list[dict]:
    """The authentication headers of a message as structured entries, in the order they appear: `header`, `raw`
    (first 400 characters), `results` (spf/dkim/dmarc/arc/...), `details` (smtp.mailfrom, header.d, ...) and, for the
    Authentication-Results kinds, `authserv_id` and `matches_receiver`.

    `headers` are the (name, unfolded value) pairs in message order; `by_hosts` are the `by` hosts of the Received
    headers, newest first (one per Received header).

    `matches_receiver` answers "was this written by the server that received the message?": True when the server name
    belongs to an operator that wrote one of the Received lines, False when it names another one, None when unknown.
    Without a server name (Microsoft 365) the position decides, the same positional correlation as hop_specific_auth: the
    header counts as the receiver's when it directly follows a Received line written by the operator of the NEWEST
    host-named Received line. Text alone is never trusted for that, because a forged header can claim any name."""
    receiver_families = {f for f in (_family_of_host(host) for host in by_hosts) if f}
    receiver_family = next((_family_of_host(host) for host in by_hosts if host and "." in host), None)
    received_rank = {pos: rank for rank, pos in enumerate(i for i, (name, _) in enumerate(headers) if name.lower() == "received")}
    entries = []
    for pos, (name, value) in enumerate(headers):
        lname = name.lower()
        if lname not in _AUTH_ENTRY_HEADERS:
            continue
        entry: dict = {"header": name, "raw": value[:400], "results": {}, "details": {}}
        if lname == "received-spf":
            match = _RECEIVED_SPF_RE.match(value)
            if match:
                entry["results"]["spf"] = match.group(1).lower()
            for key in ("client-ip", "envelope-from", "helo", "identity"):
                found = re.search(rf"{key}\s*=\s*\"?([^;\s\"]+)", value, re.IGNORECASE)
                if found:
                    entry["details"][key] = found.group(1)
        else:
            body = re.sub(r"^\s*i\s*=\s*\d+\s*;\s*", "", value)
            server = authserv_id(value)
            entry["authserv_id"] = server
            if server:
                server_family = _family_of_host(server.lower())
                entry["matches_receiver"] = (server_family in receiver_families) if (server_family and receiver_families) else None
            else:
                previous = received_rank.get(pos - 1)
                written_by_receiver = previous is not None and previous < len(by_hosts) and receiver_family is not None \
                    and _family_of_host(by_hosts[previous]) == receiver_family
                entry["matches_receiver"] = True if written_by_receiver else None
            for found in _RESULT_RE.finditer(body):
                entry["results"].setdefault(found.group(1).lower(), found.group(2).lower())
            for found in _DETAIL_RE.finditer(body):
                entry["details"].setdefault(found.group(1).lower(), found.group(2))
        entries.append(entry)
    return entries


def receiver_auth(headers: list[tuple[str, str]], by_hosts: list[str | None], entries: list[dict] | None = None) -> dict:
    """What the receiving server concluded about the message: `{spf, dkim, dmarc, verified, authserv_id, header}`.

    Picks the Authentication-Results header written by the receiver (the first one that `matches_receiver`, else the
    first one; when the message has none, the Microsoft or ARC variant), takes SPF/DKIM/DMARC from it and fills a missing
    SPF verdict from the first Received-SPF header. `verified` is True only when the chosen header matches the
    receiver; `header` is its name (None when the message carries no verdict at all). A header planted lower in a
    forged message cannot win over the receiver's own, which sits at the top. Pass `entries` (from `auth_entries`) to
    avoid parsing the headers again."""
    entries = auth_entries(headers, by_hosts) if entries is None else entries
    pick = None
    for kind in AUTH_RESULT_HEADERS:
        group = [e for e in entries if e["header"].lower() == kind]
        if group:
            pick = next((e for e in group if e["matches_receiver"] is True), group[0])
            break
    results = dict(pick["results"]) if pick else {}
    if not results.get("spf"):
        received_spf = next((e for e in entries if e["header"].lower() == "received-spf" and e["results"].get("spf")), None)
        if received_spf:
            results["spf"] = received_spf["results"]["spf"]
    return {
        "spf": results.get("spf"),
        "dkim": results.get("dkim"),
        "dmarc": results.get("dmarc"),
        "verified": bool(pick) and pick["matches_receiver"] is True,
        "authserv_id": pick["authserv_id"] if pick else None,
        "header": pick["header"] if pick else None,
    }

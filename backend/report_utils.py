"""Comment sanitising and IP eligibility helpers: sanitize_comment, truncate_chars, is_reportable_ip, attack_age."""
from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timedelta, timezone

from backend.i18n import t
from backend.mail_trust import is_special_ip

AGE_LIMIT_DAYS = 60  # AbuseIPDB: the reported activity must be no older than 60 days
CLOCK_SKEW = timedelta(hours=1)  # a date this far in the future is treated as "now" (clock offset, not a forged date)
MAX_COMMENT_CHARS = 1024
MAX_CATEGORIES = 30  # AbuseIPDB /report: at most 30 category ids per report

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def truncate_chars(text: str, limit: int = MAX_COMMENT_CHARS) -> str:
    return text[:limit]


def sanitize_comment(text: str) -> str:
    ascii_only = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in text)
    cleaned = " ".join(ascii_only.split())
    if cleaned.startswith(_FORMULA_PREFIXES):
        cleaned = "'" + cleaned
    return cleaned


def is_reportable_ip(ip_str: str) -> tuple[bool, str | None]:
    try:
        ipaddress.ip_address(ip_str)
    except ValueError:
        return False, t("report.ip_invalid")
    if is_special_ip(ip_str):
        return False, t("report.ip_private")
    return True, None


def attack_age(ts: datetime) -> tuple[int, bool]:
    """Age of the event in whole days and whether it is within the AbuseIPDB limit (timezone-aware `ts`).

    The one age rule of both the analysis step and the hard checks before sending. A date up to CLOCK_SKEW in the
    future counts as age 0 (otherwise `.days` would give -1 for a few minutes of clock offset); a date further in
    the future gives a negative age and fails.
    """
    delta = datetime.now(timezone.utc) - ts
    if -CLOCK_SKEW <= delta < timedelta(0):
        delta = timedelta(0)
    days = delta.days
    return days, 0 <= days <= AGE_LIMIT_DAYS


# ---- personal data in the comment (AbuseIPDB: the reporter is responsible for stripping PII) ----

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
# freemail domains say nothing about the reporter, so a recipient domain like this is not searched for on its own
FREEMAIL_DOMAINS = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com", "icloud.com",
                    "me.com", "proton.me", "protonmail.com", "wp.pl", "o2.pl", "onet.pl", "interia.pl"}
_PLACEHOLDER = {"own": "[redacted]", "email": "[email removed]", "private_ip": "[internal IP]"}


def own_identifiers(recipients: list[str]) -> list[str]:
    """Recipient addresses of the analysed e-mail and their (non-freemail) domains: what identifies the reporter."""
    terms: list[str] = []
    for addr in recipients:
        for term in (addr, addr.rpartition("@")[2]):
            if term and term not in terms and term not in FREEMAIL_DOMAINS:
                terms.append(term)
    return terms


def find_pii(comment: str, own_terms: list[str] | None = None) -> list[dict]:
    """Things in the comment that should not be sent: the reporter's own identifiers (kind "own"), any other e-mail
    address ("email") and private/internal IP addresses ("private_ip"). Each finding is {kind, value}, own first."""
    found: dict[str, str] = {}
    lowered = comment.lower()
    for term in own_terms or []:
        term = term.strip().lower()
        if term and term in lowered:
            found.setdefault(term, "own")
    for match in _EMAIL_RE.findall(comment):
        if match.lower() not in found:
            found[match.lower()] = "email"
    for match in _IPV4_RE.findall(comment):
        try:
            ip = ipaddress.ip_address(match)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            found.setdefault(match, "private_ip")
    order = {"own": 0, "email": 1, "private_ip": 2}
    return sorted(({"kind": kind, "value": value} for value, kind in found.items()), key=lambda f: order[f["kind"]])


def redact_pii(comment: str, own_terms: list[str] | None = None) -> str:
    """The comment with every finding of find_pii replaced by a neutral placeholder (longest match first)."""
    for finding in sorted(find_pii(comment, own_terms), key=lambda f: len(f["value"]), reverse=True):
        comment = re.sub(re.escape(finding["value"]), _PLACEHOLDER[finding["kind"]], comment, flags=re.IGNORECASE)
    return comment

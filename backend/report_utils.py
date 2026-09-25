"""Comment sanitising and IP eligibility helpers: sanitize_comment, truncate_chars, is_reportable_ip, attack_age."""
from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta, timezone

from backend.i18n import t

AGE_LIMIT_DAYS = 60  # AbuseIPDB: the reported activity must be no older than 60 days
CLOCK_SKEW = timedelta(hours=1)  # a date this far in the future is treated as "now" (clock offset, not a forged date)
MAX_COMMENT_CHARS = 1024

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
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False, t("report.ip_invalid")
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
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

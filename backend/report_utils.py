"""Comment sanitising and IP eligibility helpers: sanitize_comment, truncate_bytes, is_reportable_ip."""
from __future__ import annotations

import ipaddress

from backend.i18n import t

MAX_COMMENT_BYTES = 1024
MAX_COMMENT_CHARS = 1024

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def truncate_bytes(text: str, limit: int = MAX_COMMENT_BYTES) -> str:
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text
    return raw[:limit].decode("utf-8", errors="ignore")


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

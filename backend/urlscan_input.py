"""Input handling of the URLScan tab: turns what the user pasted (often a defanged link from a report or an e-mail)
into a URL that urlscan.io can scan, and rejects what it can never scan (non-HTTP schemes, private or local hosts)."""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

from backend.i18n import t

MAX_URL_LENGTH = 2048
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)
_LOCAL_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home", ".home.arpa", ".corp", ".intranet")
_DEFANG_REPLACEMENTS = (
    ("[://]", "://"), ("[:]", ":"), ("[.]", "."), ("(.)", "."), ("{.}", "."), ("[dot]", "."), ("(dot)", "."),
    ("[/]", "/"), ("[at]", "@"), ("[@]", "@"),
)


class InvalidScanUrl(ValueError):
    """The message is already translated (it goes straight to the user)."""


def refang(text: str) -> str:
    """hxxps://evil[.]example -> https://evil.example (the notation used in reports and by our own e-mail tab)."""
    out = re.sub(r"^\s*hxxp", "http", text, flags=re.IGNORECASE)
    for old, new in _DEFANG_REPLACEMENTS:
        out = re.sub(re.escape(old), new, out, flags=re.IGNORECASE)
    return out


def defang(url: str) -> str:
    """The reverse, used in exports so that a saved report never contains a live link."""
    return re.sub(r"^http", "hxxp", str(url), flags=re.IGNORECASE).replace(".", "[.]")


def _is_local_host(host: str) -> bool:
    if host == "localhost" or host.endswith(_LOCAL_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return "." not in host  # a single-label name (an intranet host) cannot be reached from the internet
    return not ip.is_global


def normalize_scan_url(raw: str) -> str:
    text = refang(raw).strip().strip("<>\"'`").strip()
    if not text:
        raise InvalidScanUrl(t("urlscan.url_empty"))
    if len(text) > MAX_URL_LENGTH:
        raise InvalidScanUrl(t("urlscan.url_too_long", limit=MAX_URL_LENGTH))
    if re.search(r"[\s\x00-\x1f\x7f]", text):
        raise InvalidScanUrl(t("urlscan.url_whitespace"))
    if "://" not in text:
        if _SCHEME_RE.match(text) and not re.match(r"^[^/:]+:\d+(/|$)", text):
            raise InvalidScanUrl(t("urlscan.url_scheme", scheme=text.split(":", 1)[0][:20]))
        text = "https://" + text
    try:
        parts = urlsplit(text)
        host = (parts.hostname or "").lower()
        parts.port  # noqa: B018 - raises ValueError on a malformed port
    except ValueError as exc:
        raise InvalidScanUrl(t("urlscan.url_invalid")) from exc
    if parts.scheme.lower() not in ("http", "https"):
        raise InvalidScanUrl(t("urlscan.url_scheme", scheme=parts.scheme[:20]))
    if not host:
        raise InvalidScanUrl(t("urlscan.url_invalid"))
    if _is_local_host(host):
        raise InvalidScanUrl(t("urlscan.url_private", host=host[:100]))
    return text

from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timezone
from email import message_from_string
from email.message import Message
from email.utils import parsedate_to_datetime

_IP_RE = re.compile(r"\[?((?:\d{1,3}\.){3}\d{1,3}|[0-9a-fA-F:]{4,})\]?")
_BTC_RE = re.compile(r"\b(bc1[a-z0-9]{25,39}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
_RANSOM_KEYWORDS = ("bitcoin", "btc", "ransom", "payment", "wallet", "crypto", "decrypt")

AGE_LIMIT_DAYS = 60


def _extract_ip_from_received(header_value: str) -> str | None:
    for match in _IP_RE.finditer(header_value):
        candidate = match.group(1)
        try:
            ip = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved):
            return str(ip)
    return None


def _parse_auth_results(header_value: str) -> dict[str, str]:
    out = {}
    for mechanism in ("spf", "dkim", "dmarc"):
        m = re.search(rf"{mechanism}=(\w+)", header_value, re.IGNORECASE)
        if m:
            out[mechanism] = m.group(1).lower()
    return out


def _extract_attachments(msg: Message) -> list[dict]:
    attachments = []
    for part in msg.walk():
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True) or b""
        declared_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        attachments.append(
            {
                "filename": filename,
                "size_bytes": len(payload),
                "content_type": part.get_content_type(),
                "declared_extension": declared_ext,
            }
        )
    return attachments


def _extract_body_text(msg: Message) -> str:
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                try:
                    parts.append(part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore"))
                except Exception:
                    continue
        return "\n".join(parts)
    try:
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
    except Exception:
        return ""


def parse_email(raw_email: str) -> dict:
    msg = message_from_string(raw_email)

    received_headers = msg.get_all("Received") or []
    trusted_ip = None
    for header in received_headers:
        trusted_ip = _extract_ip_from_received(header)
        if trusted_ip:
            break

    auth_header = msg.get("Authentication-Results", "")
    auth_results = _parse_auth_results(auth_header)

    date_header = msg.get("Date")
    date_parsed = None
    age_days = None
    if date_header:
        try:
            date_parsed = parsedate_to_datetime(date_header)
            if date_parsed.tzinfo is None:
                date_parsed = date_parsed.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - date_parsed).days
        except (TypeError, ValueError):
            pass

    body = _extract_body_text(msg)
    btc_matches = sorted(set(_BTC_RE.findall(body)))
    ransom_hint = any(kw in body.lower() for kw in _RANSOM_KEYWORDS)

    ip_ok, ip_reject_reason = (True, None)
    if trusted_ip:
        try:
            ip = ipaddress.ip_address(trusted_ip)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                ip_ok, ip_reject_reason = False, "adres prywatny/zarezerwowany"
        except ValueError:
            ip_ok, ip_reject_reason = False, "nieprawidłowy adres IP"
    else:
        ip_ok, ip_reject_reason = False, "nie znaleziono wiarygodnego publicznego IP w łańcuchu Received"

    age_ok = age_days is not None and age_days <= AGE_LIMIT_DAYS

    return {
        "trusted_source_ip": trusted_ip,
        "ip_ok": ip_ok,
        "ip_reject_reason": ip_reject_reason,
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

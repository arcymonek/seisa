from __future__ import annotations

from datetime import datetime, timezone

from backend.report_utils import is_reportable_ip, sanitize_comment, truncate_chars

AGE_LIMIT_DAYS = 60

ABUSEIPDB_CATEGORIES = {
    1: "DNS Compromise",
    2: "DNS Poisoning",
    3: "Fraud Orders",
    4: "DDoS Attack",
    5: "FTP Brute-Force",
    6: "Ping of Death",
    7: "Phishing",
    8: "Fraud VoIP",
    9: "Open Proxy",
    10: "Web Spam",
    11: "Email Spam",
    12: "Blog Spam",
    13: "VPN IP",
    14: "Port Scan",
    15: "Hacking",
    16: "SQL Injection",
    17: "Spoofing",
    18: "Brute-Force",
    19: "Bad Web Bot",
    20: "Exploited Host",
    21: "Web App Attack",
    22: "SSH",
    23: "IoT Targeted",
}


def build_comment(
    ip: str,
    description: str,
    spoofing_confirmed: bool,
    attachments: list[dict],
    ransom: dict | None,
    message_id: str | None,
) -> str:
    parts = [f"Suspicious email delivered directly from IP {ip}."]

    if description and description.strip():
        parts.append(description.strip())

    if spoofing_confirmed:
        parts.append(
            "SPF/DMARC check failed for the spoofed sender domain, confirming the message "
            "did not originate from an authorized mail server for that domain."
        )

    for a in attachments or []:
        displayed = a.get("displayed_extension") or a.get("declared_extension") or "?"
        actual = a.get("actual_extension") or "unknown"
        parts.append(
            f"Attachment: {a.get('filename', '?')}, {a.get('size_bytes', '?')} bytes. "
            f"Extension: displayed as .{displayed} / actual file type .{actual}"
        )

    if ransom and (ransom.get("amount") or ransom.get("wallet")):
        if ransom.get("amount"):
            parts.append(f"Ransom/payment demand: {ransom['amount']} {ransom.get('currency', '')}".strip())
        if ransom.get("wallet"):
            parts.append(f"BTC/crypto wallet: {ransom['wallet']}")

    if message_id:
        parts.append(f"Message-ID: {message_id}")

    sanitized_parts = [sanitize_comment(p) for p in parts]
    comment = "\n\n".join(sanitized_parts)
    return truncate_chars(comment)


def validate_hard_checks(ip: str, attack_timestamp: str | None, categories: list[int], description: str) -> dict:
    ip_ok, ip_reason = is_reportable_ip(ip)

    age_ok = False
    age_reason = "brak daty ataku"
    if attack_timestamp:
        try:
            ts = datetime.fromisoformat(attack_timestamp.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - ts).days
            age_ok = 0 <= age_days <= AGE_LIMIT_DAYS
            age_reason = None if age_ok else f"atak ma {age_days} dni (limit {AGE_LIMIT_DAYS})"
        except ValueError:
            age_reason = "nieprawidłowy format daty"

    category_ok = bool(categories) and all(c in ABUSEIPDB_CATEGORIES for c in categories)
    description_ok = bool(description and description.strip())

    return {
        "ip_ok": ip_ok,
        "ip_reason": ip_reason,
        "age_ok": age_ok,
        "age_reason": age_reason,
        "category_ok": category_ok,
        "description_ok": description_ok,
        "all_passed": ip_ok and age_ok and category_ok and description_ok,
    }

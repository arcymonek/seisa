from __future__ import annotations

from datetime import datetime, timezone

from backend.email_parser import extract_addresses
from backend.i18n import t
from backend.report_utils import AGE_LIMIT_DAYS, attack_age, is_reportable_ip, sanitize_comment, truncate_chars

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
    spoofing_confirmed: bool,
    attachments: list[dict],
    ransom: dict | None,
    message_id: str | None,
) -> str:
    parts = [f"Suspicious email delivered directly from IP {ip}."]

    if spoofing_confirmed:
        parts.append(
            "SPF/DMARC check failed for the spoofed sender domain, confirming the message "
            "did not originate from an authorized mail server for that domain."
        )

    for a in attachments or []:
        line = f"Attachment: {a.get('filename', '?')}, {a.get('size_bytes', '?')} bytes, Content-Type: {a.get('content_type') or 'unknown'}."
        apparent = a.get("apparent_extension")
        declared = a.get("declared_extension")
        if apparent and declared and apparent != declared:
            line += f" Filename displays as .{apparent} but actual extension is .{declared} (double extension)."
        parts.append(line)

    if ransom and (ransom.get("amount") or ransom.get("wallet")):
        if ransom.get("amount"):
            parts.append(f"Ransom/payment demand: {ransom['amount']} {ransom.get('currency', '')}".strip())
        if ransom.get("wallet"):
            parts.append(f"BTC/crypto wallet: {ransom['wallet']}")

    if message_id:
        # only the local part: the domain after "@" usually is the reporter's own (personal data, see the policy)
        parts.append(f"Message-ID: {message_id.strip().strip('<>').split('@')[0]}")

    sanitized_parts = [sanitize_comment(p) for p in parts]
    comment = "\n\n".join(sanitized_parts)
    return truncate_chars(comment)


def local_assessment(raw_email: str, facts: dict) -> dict:
    """Cheap deterministic pre-assessment used without the LLM. It never says that a message qualifies - it only
    recognises the obvious case of a test sent from the user's own account to themselves: the sender, the envelope
    sender and a recipient are the same address, and there is no sign of an attack in the headers."""
    addr = extract_addresses(raw_email)
    sender = addr["from"][0] if len(addr["from"]) == 1 else None
    same_party = bool(sender) and addr["return_path"] == [sender] and sender in addr["recipients"]
    no_attack_signs = not (
        facts.get("spoofing_suspected")
        or facts.get("attachments")
        or facts.get("btc_addresses_found")
        or facts.get("ransom_keywords_found")
    )
    return {"self_sent": same_party and no_attack_signs, "address": sender if same_party else None}


def validate_hard_checks(ip: str, attack_timestamp: str | None, categories: list[int]) -> dict:
    """The hard checks mirror exactly what AbuseIPDB /report requires - ip and categories are required, timestamp
    and comment are optional (see https://docs.abuseipdb.com/#report-endpoint) - so only the age of the attack
    (AbuseIPDB policy: not older than 60 days) and the choice of a category are required, not the comment text."""
    ip_ok, ip_reason = is_reportable_ip(ip)

    age_ok = False
    age_reason = t("report.age_missing")
    if attack_timestamp:
        try:
            ts = datetime.fromisoformat(attack_timestamp.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_days, age_ok = attack_age(ts)
            if age_ok:
                age_reason = None
            elif age_days < 0:
                age_reason = t("report.age_future")
            else:
                age_reason = t("report.age_too_old", days=age_days, limit=AGE_LIMIT_DAYS)
        except ValueError:
            age_reason = t("report.age_bad_format")

    category_ok = bool(categories) and all(c in ABUSEIPDB_CATEGORIES for c in categories)

    return {
        "ip_ok": ip_ok,
        "ip_reason": ip_reason,
        "age_ok": age_ok,
        "age_reason": age_reason,
        "category_ok": category_ok,
        "all_passed": ip_ok and age_ok and category_ok,
    }

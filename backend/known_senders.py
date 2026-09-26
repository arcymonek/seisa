"""Well-known mail senders, recognised by the reverse DNS name of the source IP (DMARC tab, "geo" click).

A PTR record is set by whoever owns the IP block, so on its own it proves nothing: an attacker can point the PTR of a
rented server at google.com. A name counts only when it is forward-confirmed, i.e. the name resolves back to the same
address (which the attacker cannot arrange for a domain they do not own)."""
from __future__ import annotations

import socket

# (domain suffix of the PTR name, display name)
KNOWN_SENDERS: list[tuple[str, str]] = [
    ("google.com", "Google (Gmail / Workspace)"),
    ("googlemail.com", "Google (Gmail / Workspace)"),
    ("outlook.com", "Microsoft 365 / Outlook"),
    ("protection.outlook.com", "Microsoft 365 / Outlook"),
    ("hotmail.com", "Microsoft 365 / Outlook"),
    ("amazonses.com", "Amazon SES"),
    ("sendgrid.net", "SendGrid"),
    ("mailgun.org", "Mailgun"),
    ("mcsv.net", "Mailchimp"),
    ("mandrillapp.com", "Mandrill (Mailchimp)"),
    ("mtasv.net", "Postmark"),
    ("sendinblue.com", "Brevo (Sendinblue)"),
    ("brevo.com", "Brevo (Sendinblue)"),
    ("zoho.com", "Zoho Mail"),
    ("messagingengine.com", "Fastmail"),
    ("protonmail.ch", "Proton Mail"),
    ("yahoo.com", "Yahoo Mail"),
    ("yahoodns.net", "Yahoo Mail"),
]


def resolve_host_ips(host: str) -> set[str]:
    """All addresses (IPv4 and IPv6) a host name resolves to; empty when it does not resolve."""
    try:
        return {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError:
        return set()


def match_known_sender(hostname: str | None) -> str | None:
    """Display name of the known sender whose domain the host name belongs to (on a label boundary), else None."""
    if not hostname:
        return None
    name = hostname.lower().rstrip(".")
    for suffix, label in KNOWN_SENDERS:
        if name == suffix or name.endswith("." + suffix):
            return label
    return None

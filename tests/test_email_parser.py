"""backend/email_parser.py: picking the sender's IP from the Received chain and reading the authentication verdicts.

Expected values are derived by hand from the .eml files / strings below using RFC 5321 (Received), RFC 8601
(Authentication-Results: the receiving server prepends its own header, so the TOPMOST one is the trustworthy one)
and the "newest hop first" order of Received headers. They are never copied from the code's own output.

Public stand-ins: 8.8.8.8, 1.1.1.1 and 9.9.9.9 are well-known public DNS resolvers (not "special" for the
application); the documentation ranges are special on purpose, see test_mail_trust.py.
"""
from __future__ import annotations

from email import message_from_string

import pytest

from backend.email_parser import find_boundary_index, parse_email, parse_received_header
from backend.i18n import t
from tests.helpers import load_eml


def build(received: list[str], extra: str = "", date: str = "Mon, 21 Sep 2026 17:00:00 +0000") -> str:
    """A minimal e-mail: `received` is listed newest first, exactly as a mail server leaves the headers."""
    lines = [f"Received: {r}" for r in received]
    if extra.strip("\n"):  # an empty line would end the header block early
        lines.append(extra.strip("\n"))
    return "\n".join(
        [*lines, "From: Sender <sender@example.org>", "To: me@example.net", "Subject: test",
         f"Date: {date}", "Message-ID: <id1@example.org>", "", "body", ""]
    )


def received_of(src: str) -> list[str]:
    return message_from_string(src).get_all("Received") or []


# ---- parse_received_header ----

def test_received_basic_fields():
    hop = parse_received_header("from mail.example.org (mail.example.org [8.8.8.8]) by mx.example.net with ESMTPS id 1; Mon, 1 Jan 2026")
    assert (hop["from_host"], hop["by_host"], hop["ip"]) == ("mail.example.org", "mx.example.net", "8.8.8.8")
    assert hop["is_boundary"] is False


def test_received_folded_header_is_read_like_a_single_line():
    hop = parse_received_header("from a.example.org\n\t(a.example.org [8.8.8.8])\n\tby mx.example.net; x")
    assert (hop["from_host"], hop["by_host"], hop["ip"]) == ("a.example.org", "mx.example.net", "8.8.8.8")


def test_received_public_ip_in_parentheses_beats_loopback_in_brackets():
    # Microsoft EOP style: `[127.0.0.1] (real_ip)` - the real client address is the one in parentheses
    hop = parse_received_header("from [127.0.0.1] (8.8.8.8) by mx.example.net with SMTP; x")
    assert hop["ip"] == "8.8.8.8"
    assert hop["from_host"] == "127.0.0.1"


def test_received_without_from_clause_has_no_host_and_no_ip():
    hop = parse_received_header("by 2002:a05:6a00:1 with SMTP id abc; Mon, 21 Sep 2026 10:00:03 -0700 (PDT)")
    assert hop["from_host"] is None and hop["ip"] is None


def test_received_ipv6_address_in_brackets():
    hop = parse_received_header("from mail.example.org (mail.example.org [2606:4700:4700::1111]) by mx.example.net with ESMTPS; x")
    assert hop["ip"] == "2606:4700:4700::1111"


def test_received_ipv6_literal_with_rfc5321_prefix():
    hop = parse_received_header("from mail.example.org (mail.example.org [IPv6:2606:4700:4700::1111]) by mx.example.net with ESMTPS; x")
    assert hop["ip"] == "2606:4700:4700::1111"


# ---- find_boundary_index ----

def test_boundary_of_an_empty_chain():
    assert find_boundary_index([]) == (None, "low")


def test_boundary_single_external_hop():
    chain = ["from smtp.news.example (smtp.news.example [8.8.8.8]) by mx.recipient.example with ESMTPS; x"]
    assert find_boundary_index(chain) == (0, "high")


def test_boundary_is_the_hop_where_the_receiving_operator_recorded_an_outsider():
    chain = [
        "from relay.recipient.example (relay.recipient.example [10.0.0.2]) by mx.recipient.example with ESMTP; x",  # internal
        "from mail.sender-corp.example (mail.sender-corp.example [8.8.8.8]) by relay.recipient.example with ESMTPS; x",  # outsider
    ]
    assert find_boundary_index(chain) == (1, "high")


def test_forged_older_received_headers_from_an_unknown_relay_do_not_move_the_boundary():
    # The recipient's server recorded 8.8.8.8 (hop 0). Everything below was written by the sender and may claim anything,
    # including that the message passed through 1.1.1.1 or through the recipient's own domain.
    src = build(
        [
            "from evil-host.example.net (evil-host.example.net [8.8.8.8]) by mx.recipient.example with ESMTPS; Mon, 21 Sep 2026 17:00:03 +0000",
            "from mail.bank.example (mail.bank.example [1.1.1.1]) by evil-host.example.net with ESMTP; Mon, 21 Sep 2026 17:00:01 +0000",
            "from relay.recipient.example (relay.recipient.example [9.9.9.9]) by mail.bank.example with ESMTP; Mon, 21 Sep 2026 17:00:00 +0000",
        ]
    )
    parsed = parse_email(src)
    assert parsed["trusted_source_ip"] == "8.8.8.8"
    assert parsed["received_chain"][0]["is_boundary"] is True


# ---- parse_email on the synthetic fixtures (hand-read) ----

def test_fixture_multihop_picks_the_client_behind_the_google_relays():
    # three Received, all inside Google, the oldest recorded the connecting client 176.9.44.107 in parentheses
    parsed = parse_email(load_eml("multihop.eml"))
    assert parsed["trusted_source_ip"] == "176.9.44.107"
    assert parsed["ip_ok"] is True
    assert parsed["ip_confidence"] == "high"
    assert [h["is_boundary"] for h in parsed["received_chain"]] == [False, False, True]
    assert (parsed["spf"], parsed["dkim"], parsed["dmarc"]) == (None, None, None)
    assert parsed["spoofing_suspected"] is False


def test_fixture_newsletter_is_authenticated_and_not_suspicious():
    parsed = parse_email(load_eml("newsletter.eml"))
    assert parsed["trusted_source_ip"] == "192.0.2.10"
    assert (parsed["spf"], parsed["dkim"], parsed["dmarc"]) == ("pass", "pass", "pass")
    assert parsed["spoofing_suspected"] is False
    assert parsed["ip_ok"] is False  # the documentation range is never reportable
    assert parsed["attachments"] == []


def test_fixture_phishing_failed_authentication_is_flagged():
    parsed = parse_email(load_eml("phishing.eml"))
    assert parsed["trusted_source_ip"] == "203.0.113.45"  # hop 0, written by the recipient's own server
    assert parsed["trusted_source_ip"] != "198.51.100.7"  # the X-Originating-IP header is sender-controlled text
    assert (parsed["spf"], parsed["dkim"], parsed["dmarc"]) == ("fail", "none", "fail")
    assert parsed["spoofing_suspected"] is True
    assert [a["filename"] for a in parsed["attachments"]] == ["invoice.pdf.exe"]
    assert parsed["attachments"][0]["apparent_extension"] == "pdf"
    assert parsed["attachments"][0]["declared_extension"] == "exe"


def test_fixture_relay_walks_through_pods_to_the_authenticated_client():
    parsed = parse_email(load_eml("ovh_style_relay.eml"))
    assert parsed["trusted_source_ip"] == "154.16.88.201"
    assert parsed["ip_ok"] is True
    assert [h["is_boundary"] for h in parsed["received_chain"]] == [False, False, False, True]
    assert (parsed["spf"], parsed["dkim"], parsed["dmarc"]) == ("pass", "pass", "pass")
    assert parsed["boundary_auth_corroboration"]["smtp_auth_account"] == "sales@brightfield-consult.example"


# ---- authentication verdicts ----

def test_no_authentication_results_means_no_verdict_and_no_spoofing_flag():
    parsed = parse_email(build(["from a.example.net (a.example.net [8.8.8.8]) by mx.recipient.example; x"]))
    assert (parsed["spf"], parsed["dkim"], parsed["dmarc"]) == (None, None, None)
    assert parsed["spoofing_suspected"] is False


def test_topmost_authentication_results_wins_over_a_planted_one_below():
    extra = (
        "Authentication-Results: mx.recipient.example; spf=fail smtp.mailfrom=example.org; dmarc=fail header.from=example.org\n"
        "Authentication-Results: fake.example; spf=pass; dkim=pass; dmarc=pass"
    )
    parsed = parse_email(build(["from a.example.net (a.example.net [8.8.8.8]) by mx.recipient.example; x"], extra))
    assert (parsed["spf"], parsed["dmarc"]) == ("fail", "fail")
    assert parsed["spoofing_suspected"] is True


def test_spoofing_flag_follows_spf_fail_or_dmarc_fail_only():
    base = ["from a.example.net (a.example.net [8.8.8.8]) by mx.recipient.example; x"]
    softfail = parse_email(build(base, "Authentication-Results: mx.recipient.example; spf=softfail; dkim=none; dmarc=pass"))
    assert softfail["spoofing_suspected"] is False
    dmarc_fail = parse_email(build(base, "Authentication-Results: mx.recipient.example; spf=pass; dmarc=fail"))
    assert dmarc_fail["spoofing_suspected"] is True


def test_verdicts_are_lowercased():
    parsed = parse_email(build(["from a.example.net (a.example.net [8.8.8.8]) by mx.recipient.example; x"],
                               "Authentication-Results: mx.recipient.example; SPF=PASS; DKIM=Pass; DMARC=PASS"))
    assert (parsed["spf"], parsed["dkim"], parsed["dmarc"]) == ("pass", "pass", "pass")


# ---- degenerate input ----

def test_message_without_received_has_no_ip_and_is_not_reportable():
    parsed = parse_email(build([]))
    assert parsed["trusted_source_ip"] is None
    assert parsed["ip_ok"] is False
    assert parsed["ip_confidence"] == "low"
    assert parsed["received_chain"] == []


def test_private_only_chain_is_not_reportable():
    parsed = parse_email(build(["from localhost (localhost [127.0.0.1]) by mx.example.net; x"]))
    assert parsed["ip_ok"] is False


def test_old_message_fails_the_age_check():
    parsed = parse_email(build(["from a.example.net (a.example.net [8.8.8.8]) by mx.recipient.example; x"], date="Mon, 01 Jan 2024 00:00:00 +0000"))
    assert parsed["age_ok"] is False
    assert parsed["age_days"] > 60


def test_unparseable_date_is_not_a_crash():
    parsed = parse_email(build(["from a.example.net (a.example.net [8.8.8.8]) by mx.recipient.example; x"], date="not a date"))
    assert parsed["age_ok"] is False and parsed["date_parsed"] is None


def test_attachment_detection_ignores_plain_body():
    assert parse_email(build(["from a.example.net (a.example.net [8.8.8.8]) by mx.recipient.example; x"]))["attachments"] == []


def test_bitcoin_address_in_body_is_found():
    wallet = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"  # the BIP-173 example address
    src = build(["from a.example.net (a.example.net [8.8.8.8]) by mx.recipient.example; x"]).replace("body", f"send bitcoin to {wallet} now")
    parsed = parse_email(src)
    assert parsed["btc_addresses_found"] == [wallet]
    assert parsed["ransom_keywords_found"] is True


def test_ipv6_literal_with_prefix_is_found_in_a_full_message():
    src = build(["from mail.example.org (mail.example.org [IPv6:2606:4700:4700::1111]) by mx.recipient.example with ESMTPS; x"])
    assert parse_email(src)["trusted_source_ip"] == "2606:4700:4700::1111"


def test_walk_through_a_known_provider_still_reaches_the_client():
    # Exchange-Online style: the recipient's server recorded the provider relay (outlook.com); the provider's own,
    # older line recorded the client that really connected to it
    chain = [
        "from mail-eopbgr.outlook.com (mail-eopbgr.outlook.com [9.9.9.9]) by mx.recipient.example with ESMTPS; x",
        "from CLIENTPC (1.1.1.1) by AM6PR.prod.outlook.com with ESMTPSA; x",
    ]
    assert find_boundary_index(chain) == (1, "medium")  # found through lines the provider wrote: never "high"
    parsed = parse_email(build(chain))
    assert parsed["trusted_source_ip"] == "1.1.1.1"
    assert parsed["ip_from_relay_lines"] is True
    assert "9.9.9.9" in parsed["ip_reasoning"]  # the user is shown what the recipient's own server recorded


@pytest.mark.xfail(
    strict=True,
    reason="KNOWN RESIDUAL LIMIT: an attacker who also forges bare pod-style names with private addresses still gets "
    "through the internal-hop rule. Closing it needs verification the program cannot do offline.",
)
def test_forged_pod_style_hops_can_still_steer_the_ip():
    src = build(
        [
            "from evil-host.example.net (evil-host.example.net [8.8.8.8]) by mx.recipient.example with ESMTPS; x",
            "from fakepod (fakepod [10.0.0.1]) by pod-1 with ESMTP; x",
            "from mail.bank.example (mail.bank.example [1.1.1.1]) by pod-1 with ESMTP; x",
        ]
    )
    assert parse_email(src)["trusted_source_ip"] == "8.8.8.8"


# ---- an address taken from lines written by a relay is never presented as certain ----

def test_direct_boundary_stays_high_and_has_no_relay_warning():
    for name in ("newsletter.eml", "phishing.eml", "multihop.eml"):
        parsed = parse_email(load_eml(name))
        assert parsed["ip_confidence"] == "high", name
        assert parsed["ip_from_relay_lines"] is False, name
        assert "9.9.9.9" not in parsed["ip_reasoning"]


def test_relay_walk_is_capped_at_medium_even_with_an_smtp_auth_bonus():
    # ovh_style_relay.eml has a valid SMTP-AUTH/DKIM pair next to the boundary line, which would normally raise the
    # confidence one step; for an address from relay-written lines that bonus must not reach "high"
    parsed = parse_email(load_eml("ovh_style_relay.eml"))
    assert parsed["boundary_auth_corroboration"] is not None
    assert parsed["ip_confidence"] == "medium"
    assert parsed["ip_from_relay_lines"] is True
    assert "198.51.100.20" in parsed["ip_reasoning"]  # what the recipient's own server recorded (the relay)


def test_forged_pod_style_chain_is_at_least_flagged_as_uncertain():
    src = build(
        [
            "from evil-host.example.net (evil-host.example.net [8.8.8.8]) by mx.recipient.example with ESMTPS; x",
            "from fakepod (fakepod [10.0.0.1]) by pod-1 with ESMTP; x",
            "from mail.bank.example (mail.bank.example [1.1.1.1]) by pod-1 with ESMTP; x",
        ]
    )
    parsed = parse_email(src)
    assert parsed["ip_confidence"] != "high"
    assert parsed["ip_from_relay_lines"] is True
    assert "8.8.8.8" in parsed["ip_reasoning"]


def test_helo_spoofed_provider_with_a_different_verified_name_is_not_believed():
    # The attacker's server (8.8.8.8) introduces itself as an outlook.com host, but the receiving server looked up
    # the real reverse-DNS name and wrote it next to the address: that verified name is what counts.
    src = build(
        [
            "from mail.outlook.com (evil-host.example.net [8.8.8.8]) by mx.recipient.example with ESMTPS; x",
            "from mail.bank.example (mail.bank.example [1.1.1.1]) by AM6PR.prod.outlook.com with ESMTP; x",
        ]
    )
    parsed = parse_email(src)
    assert parsed["trusted_source_ip"] == "8.8.8.8"
    assert parsed["ip_confidence"] == "high"
    assert parsed["ip_from_relay_lines"] is False
    assert parsed["received_chain"][0]["from_host"] == "evil-host.example.net"


@pytest.mark.xfail(
    strict=True,
    reason="KNOWN RESIDUAL LIMIT: when the receiving server wrote NO reverse-DNS name, the HELO claim of a provider "
    "cannot be checked offline; the address is then only flagged as uncertain, not corrected.",
)
def test_helo_spoofed_provider_without_a_verified_name_does_not_move_the_ip():
    src = build(
        [
            "from mail.outlook.com ([8.8.8.8]) by mx.recipient.example with ESMTPS; x",
            "from mail.bank.example (mail.bank.example [1.1.1.1]) by AM6PR.prod.outlook.com with ESMTP; x",
        ]
    )
    assert parse_email(src)["trusted_source_ip"] == "8.8.8.8"


def test_helo_spoofed_provider_without_a_verified_name_is_flagged_as_uncertain():
    src = build(
        [
            "from mail.outlook.com ([8.8.8.8]) by mx.recipient.example with ESMTPS; x",
            "from mail.bank.example (mail.bank.example [1.1.1.1]) by AM6PR.prod.outlook.com with ESMTP; x",
        ]
    )
    parsed = parse_email(src)
    assert parsed["ip_confidence"] != "high"
    assert parsed["ip_from_relay_lines"] is True


# ---- findings from a real-mail corpus (rebuilt here as synthetic messages) ----

def test_address_in_plain_parentheses_after_a_reverse_dns_name():
    # Gmail also writes `(name. 192.0.2.1)` without square brackets
    hop = parse_received_header("from efi.example.net (efi.example.net. 8.8.8.8) by mx.google.com with ESMTPS id 1; x")
    assert hop["ip"] == "8.8.8.8"
    assert hop["from_host"] == "efi.example.net"


def test_gmail_style_chain_with_a_spoofed_google_helo_picks_the_real_connecting_address():
    # The newest Gmail line says HELO docs.google.com, but its verified reverse-DNS name is another organisation:
    # the connection came from 9.9.9.9, not from "inside Google". (Previously this hop was skipped and the older,
    # unbracketed line could not be read at all, so no address was found.)
    chain = [
        "from docs.google.com (customer.example.fr. [9.9.9.9]) by mx.google.com with ESMTPS id a; Mon, 21 Sep 2026 05:26:06 -0700 (PDT)",
        "from sender.example.com (sender.example.com. 8.8.8.8) by mx.google.com with ESMTPS id b; Sun, 20 Sep 2026 05:00:00 -0700 (PDT)",
    ]
    parsed = parse_email(build(chain))
    assert parsed["trusted_source_ip"] == "9.9.9.9"
    assert parsed["received_chain"][0]["is_boundary"] is True


def test_exchange_online_internal_machines_count_as_microsoft():
    # Microsoft's own internal hops use several domains; only the machine that connected from outside is the boundary
    chain = [
        "from PR3P194MB0556.EURP194.PROD.OUTLOOK.COM (2603:10a6:102:39::10) by AS8P194MB1922.EURP194.PROD.OUTLOOK.COM with HTTPS; x",
        "from MN2PR01CA0066.prod.exchangelabs.com (2603:10b6:208:23f::35) by PR3P194MB0556.EURP194.PROD.OUTLOOK.COM (2603:10a6:102:39::10) with Microsoft SMTP Server; x",
        "from BL6PEPF0001AB56.namprd02.prod.outlook.com (2603:10b6:208:23f:cafe::d7) by MN2PR01CA0066.outlook.office365.com (2603:10b6:208:23f::35) with Microsoft SMTP Server; x",
        "from mail-nam.eastus.cloudapp.azure.com (8.8.8.8) by BL6PEPF0001AB56.mail.protection.outlook.com (10.167.241.8) with Microsoft SMTP Server; x",
    ]
    parsed = parse_email(build(chain))
    assert parsed["trusted_source_ip"] == "8.8.8.8"
    assert parsed["ip_confidence"] == "high"


def test_unknown_relay_with_older_lines_is_reported_and_the_reader_is_told_why():
    chain = [
        "from srv01.filter.example (srv01.filter.example [8.8.8.8]) by mx.recipient.example with ESMTPS; x",
        "from [9.9.9.9] (helo=web01.shop.example) by srv01.filter.example with ESMTPS; x",
    ]
    parsed = parse_email(build(chain))
    assert parsed["trusted_source_ip"] == "8.8.8.8"  # the address recorded by the recipient's own server
    assert parsed["ip_from_relay_lines"] is False
    assert t("parser.relay_declined", relay="filter.example") in parsed["ip_reasoning"]  # the reader is told why
    assert "9.9.9.9" not in parsed["ip_reasoning"]

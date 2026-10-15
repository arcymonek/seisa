"""backend/email_forensics.py: the deterministic facts shown on the Email tab (and fed to the LLM as ground truth).

Expected values are read off the .eml files by hand or computed with the standard library (hashlib, base64),
never copied from the output of the code under test. The two prompt-injection tests encode the project's central
rule: the content of an e-mail is data from a possible attacker and must never change a security fact.
"""
from __future__ import annotations

import base64
import hashlib

import pytest

from backend.email_forensics import compute_facts, normalize_source, prepare_for_llm
from backend.email_parser import parse_email
from tests.helpers import FIXTURES, load_eml

ALL_FIXTURES = sorted(str(p.relative_to(FIXTURES)) for p in FIXTURES.rglob("*.eml"))

# keys of compute_facts() that describe WHO sent the message and whether it was authenticated (not its content)
SECURITY_FACT_KEYS = ("received", "trust_index", "trust_note", "auth", "dkim", "identity", "ips", "single_operator")
SECURITY_PARSE_KEYS = ("trusted_source_ip", "ip_ok", "ip_confidence", "spf", "dkim", "dmarc", "spoofing_suspected",
                       "received_chain")


# ---- normalize_source ----

def test_normalize_strips_bom_crlf_and_leading_blank_lines():
    assert normalize_source("﻿\r\n\r\nSubject: x\r\n\r\nbody\r\n") == "Subject: x\n\nbody\n"


def test_normalize_drops_the_mbox_envelope_line():
    assert normalize_source("From sender@example.org Mon Sep 21 10:00:00 2026\nSubject: x\n\nbody") == "Subject: x\n\nbody"


def test_normalize_keeps_a_from_header():
    assert normalize_source("From: Someone <s@example.org>\nSubject: x\n\nb") == "From: Someone <s@example.org>\nSubject: x\n\nb"


def test_normalize_does_not_touch_headers_or_body():
    src = "Subject: =?utf-8?q?a_b?=\nX-Test:  two  spaces\n\n  indented body\n"
    assert normalize_source(src) == src


# ---- facts of the hand-read fixtures ----

@pytest.mark.parametrize(
    "name, index",
    [("multihop.eml", 2), ("newsletter.eml", 0), ("ovh_style_relay.eml", 3), ("phishing.eml", 0), ("unit/encodings.eml", 0)],
)
def test_trust_boundary_index(name, index):
    # index of the Received entry that marks the trust boundary, counted from the top (newest) entry
    assert compute_facts(load_eml(name))["trust_index"] == index


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_both_tabs_agree_on_the_boundary(name):
    """The AbuseIPDB tab (parse_email) and the Email tab (compute_facts) share one walk; they must never diverge."""
    src = load_eml(name)
    chain = parse_email(src)["received_chain"]
    boundary = next((i for i, h in enumerate(chain) if h["is_boundary"]), None)
    if boundary is not None:
        assert compute_facts(src)["trust_index"] == boundary


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_received_count_matches_the_raw_headers(name):
    src = load_eml(name)
    header_block = src.split("\n\n", 1)[0]
    expected = sum(1 for line in header_block.split("\n") if line.lower().startswith("received:"))
    facts = compute_facts(src)
    assert len(facts["received"]) == expected == facts["overview"]["received_count"]
    assert [h["index"] for h in facts["received"]] == list(range(expected))


def test_phishing_facts():
    facts = compute_facts(load_eml("phishing.eml"))
    assert [(e["header"], e["decoded"]) for e in facts["encoded_words"]] == [("Subject", "Pilne: zweryfikuj konto")]
    # three different parties: From (bank.example), Reply-To and DKIM d= (evil.example), Message-ID (mail-out.example.net)
    identity = {row["field"]: row for row in facts["identity"]}
    assert identity["From"]["domain"] == "bank.example"
    assert identity["Reply-To"]["domain"] == "evil.example" and identity["Reply-To"]["aligned"] is False
    assert identity["DKIM (d=)"]["aligned"] is False
    assert identity["Authentication-Results smtp.mailfrom"]["aligned"] is True
    # DKIM: rsa-sha1 is deprecated (RFC 8301)
    assert facts["dkim"][0]["a"] == "rsa-sha1" and facts["dkim"][0]["legacy_sha1"] is True
    # the header `To` appears twice with different values
    assert [(d["name"], d["count"]) for d in facts["duplicates"]] == [("to", 2)]
    assert facts["placeholders"] == ["{{first_name}}"]
    assert facts["list_unsubscribe"]["urls"] == ["https://tracker.evil.example/u?a=1&b=2&c=3&d=4&e=5"]
    assert facts["list_unsubscribe"]["one_click"] is False


def test_phishing_attachment_facts_use_an_independent_hash():
    attachment = compute_facts(load_eml("phishing.eml"))["attachments"][0]
    payload = base64.b64decode("TVqQAAMAAAAEAAAA")  # the base64 body of the part in the .eml
    assert attachment["filename"] == "invoice.pdf.exe"
    assert attachment["size"] == len(payload) == 12
    assert attachment["sha256"] == hashlib.sha256(payload).hexdigest()
    assert attachment["extension"] == "exe" and attachment["double_extension_as"] == "pdf"
    assert attachment["risky_extension"] is True


def test_phishing_html_facts():
    html = compute_facts(load_eml("phishing.eml"))["html"]
    assert html["hidden"][0]["tag"] == "div" and "display:none" in html["hidden"][0]["techniques"]
    shortener = next(link for link in html["links"] if link["host"] == "bit.ly")
    assert shortener["shortener"] is True
    assert shortener["text_host_mismatch"] is True  # link text names bank.example, the target is bit.ly


def test_phishing_mime_flags_an_invalid_transfer_encoding():
    mime = compute_facts(load_eml("phishing.eml"))["mime"]
    assert [part["cte_valid"] for part in mime] == [True, True, True, False]  # the last part says "weird"


def test_newsletter_facts_are_clean():
    facts = compute_facts(load_eml("newsletter.eml"))
    assert facts["flags"] == []
    assert facts["list_unsubscribe"] == {"one_click": True, "urls": ["mailto:unsub@news.example", "https://news.example/unsub"]}
    assert facts["dkim"][0]["d"] == "news.example"
    assert facts["dkim"][0]["legacy_sha1"] is False
    assert facts["auth"][0]["matches_receiver"] is True
    assert facts["auth"][0]["results"] == {"spf": "pass", "dkim": "pass", "dmarc": "pass"}


def test_relay_fixture_has_no_warnings_about_the_internal_hops():
    facts = compute_facts(load_eml("ovh_style_relay.eml"))
    assert [h["ip"] for h in facts["received"]] == ["198.51.100.20", "10.42.3.11", "10.42.1.7", "154.16.88.201"]
    assert facts["auth"][0]["results"] == {"spf": "pass", "dkim": "pass", "dmarc": "pass"}


# ---- prompt injection: content must never change a security fact ----

def test_prompt_injection_fixture_is_really_hostile():
    # guard for the test below: the fixture must contain the attack, otherwise the comparison proves nothing
    body = load_eml("unit/prompt_injection.eml").split("\n\n", 1)[1]
    assert "ignore all previous instructions" in body
    assert "198.51.100.99" in body
    assert "spf=pass" in body


def test_prompt_injection_does_not_change_any_security_fact():
    attack, control = load_eml("unit/prompt_injection.eml"), load_eml("unit/prompt_injection_control.eml")
    attack_facts, control_facts = compute_facts(attack), compute_facts(control)
    for key in SECURITY_FACT_KEYS:
        assert attack_facts[key] == control_facts[key], key
    attack_parsed, control_parsed = parse_email(attack), parse_email(control)
    for key in SECURITY_PARSE_KEYS:
        assert attack_parsed[key] == control_parsed[key], key


def test_prompt_injection_expected_verdicts_come_from_the_headers_only():
    parsed = parse_email(load_eml("unit/prompt_injection.eml"))
    facts = compute_facts(load_eml("unit/prompt_injection.eml"))
    assert parsed["trusted_source_ip"] == "203.0.113.77"  # not the 198.51.100.99 claimed in the body
    assert (parsed["spf"], parsed["dkim"], parsed["dmarc"]) == ("fail", "none", "fail")  # not the pass written in the body
    assert parsed["spoofing_suspected"] is True
    assert [row["ip"] for row in facts["ips"]] == ["203.0.113.77"]
    assert len(facts["received"]) == 1  # the fake Received line in the body is not a hop


# ---- unusual encodings ----

def test_encoded_words_are_decoded_in_subject_and_from():
    decoded = {e["header"]: e["decoded"] for e in compute_facts(load_eml("unit/encodings.eml"))["encoded_words"]}
    assert decoded["Subject"] == "Zażółć gęślą jaźń - faktura"
    assert decoded["From"] == "Zażółć Sklep <orders@shop.example>"


def test_quoted_printable_and_base64_bodies_are_both_readable():
    parsed = parse_email(load_eml("unit/encodings.eml"))
    # the wallet sits only in the quoted-printable text part
    assert parsed["btc_addresses_found"] == ["bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"]
    assert parsed["ransom_keywords_found"] is True


def test_encodings_fixture_is_authenticated_and_clean():
    parsed = parse_email(load_eml("unit/encodings.eml"))
    assert (parsed["spf"], parsed["dkim"], parsed["dmarc"]) == ("pass", "pass", "pass")
    assert parsed["spoofing_suspected"] is False
    assert parsed["trusted_source_ip"] == "198.51.100.20"


def test_prepare_for_llm_replaces_binary_attachments_and_reports_it():
    text, notes = prepare_for_llm(load_eml("phishing.eml"))
    assert "TVqQAAMAAAAEAAAA" not in text  # the binary payload never reaches the model
    assert hashlib.sha256(base64.b64decode("TVqQAAMAAAAEAAAA")).hexdigest() in text
    assert notes  # the user is told that something was replaced


# ---- damaged input must not crash anything ----

def test_missing_received_headers():
    src = load_eml("unit/broken_headers.eml")
    parsed = parse_email(src)
    facts = compute_facts(src)
    assert parsed["trusted_source_ip"] is None and parsed["ip_ok"] is False
    assert parsed["spoofing_suspected"] is False
    assert facts["received"] == []
    assert facts["overview"]["received_count"] == 0


@pytest.mark.parametrize("src", ["", "   \n\n  ", "just some text, no headers at all", "Received:\n\n", "Received: garbage\n\nbody"])
def test_degenerate_sources_do_not_raise(src):
    facts = compute_facts(src)
    parsed = parse_email(src)
    assert isinstance(facts, dict) and isinstance(parsed, dict)
    assert parsed["ip_ok"] is False


def test_very_long_header_line_does_not_hang_or_raise():
    src = "Received: from " + "a" * 200_000 + " by mx.example.net; x\nSubject: x\n\nbody\n"
    assert parse_email(src)["ip_ok"] is False


def test_email_tab_warns_when_the_boundary_comes_from_relay_written_lines():
    warns = [f["text"] for f in compute_facts(load_eml("ovh_style_relay.eml"))["flags"] if f["level"] == "warn"]
    assert any("198.51.100.20" in text for text in warns)  # the address the recipient's own server recorded


@pytest.mark.parametrize("name", ["newsletter.eml", "multihop.eml", "unit/encodings.eml"])
def test_email_tab_has_no_relay_warning_for_a_direct_boundary(name):
    flags = compute_facts(load_eml(name))["flags"]
    assert not [f for f in flags if f["level"] == "warn" and "relay" in f["text"].lower() and "Received" in f["text"]]


# ---- audit 2026-10-15, stage 1 (B01, B02) ----

# The bottom line is forged (it claims the same operator, mx.google.com, wrote it); the line above it is the one the
# recipient's own infrastructure wrote for the real connecting machine.
FORGED_BOTTOM_RECEIVED = (
    "Received: by 2002:a05:6638:4e2f::1 with SMTP id x1; Mon, 5 Oct 2026 10:00:05 -0700\n"
    "Received: from mail.attacker.example (mail.attacker.example. [9.9.9.9]) by mx.google.com with ESMTPS id y2; "
    "Mon, 5 Oct 2026 10:00:04 -0700\n"
    "Received: from innocent.example (innocent.example. 1.1.1.1) by mx.google.com with ESMTPS id z3; "
    "Mon, 5 Oct 2026 09:00:00 -0700\n"
    "From: a@example.org\n\nbody\n"
)


def test_forged_bottom_received_of_the_same_operator_does_not_pick_the_sender_ip():
    facts = compute_facts(normalize_source(FORGED_BOTTOM_RECEIVED))
    assert facts["received"][facts["trust_index"]]["ip"] == "9.9.9.9"
    assert facts["single_operator"] is None
    assert facts["trust_note"] is None
    # the Email tab and the AbuseIPDB tab name the same machine
    assert parse_email(FORGED_BOTTOM_RECEIVED)["trusted_source_ip"] == "9.9.9.9"


@pytest.mark.parametrize("header", ["Authentication-Results: ;x", "Authentication-Results:  ; ", "Authentication-Results: i=1; ;"])
def test_authentication_results_without_an_authserv_id_does_not_break_the_facts(header):
    facts = compute_facts(normalize_source(f"{header}\nFrom: a@example.org\n\nbody\n"))
    assert facts["auth"][0]["authserv_id"] is None
    assert facts["auth"][0]["matches_receiver"] is None


def _received_lines(count: int) -> str:
    return "".join(
        f"Received: from relay{i}.example.net (relay{i}.example.net. [8.8.{i % 250}.{i % 200 + 1}]) by mx{i}.example.org "
        f"with ESMTPS id x{i}; Mon, 5 Oct 2026 10:00:00 +0000\n"
        for i in range(count)
    )


def test_an_enormous_number_of_received_headers_is_cut_and_reported():
    from backend.email_parser import MAX_RECEIVED_HEADERS

    src = _received_lines(MAX_RECEIVED_HEADERS + 40) + "From: a@example.org\n\nbody\n"
    facts = compute_facts(normalize_source(src))
    assert len(facts["received"]) == MAX_RECEIVED_HEADERS
    assert any(str(MAX_RECEIVED_HEADERS + 40) in f["text"] and f["level"] == "info" for f in facts["flags"])
    assert "Received" in parse_email(src)["ip_reasoning"] and str(MAX_RECEIVED_HEADERS + 40) in parse_email(src)["ip_reasoning"]
    # a normal message gets no such note
    normal = compute_facts(normalize_source(_received_lines(5) + "From: a@example.org\n\nbody\n"))
    assert not any("Received headers" in f["text"] for f in normal["flags"])


def test_an_oversized_received_header_still_yields_its_leading_fields():
    from backend.email_parser import MAX_RECEIVED_CHARS, parse_received_header

    raw = "from mail.example.net (mail.example.net. [8.8.4.4]) by mx.example.org with ESMTPS id x; " + "(x " * MAX_RECEIVED_CHARS
    hop = parse_received_header(raw)
    assert (hop["from_host"], hop["ip"], hop["by_host"]) == ("mail.example.net", "8.8.4.4", "mx.example.org")
    assert len(hop["raw"]) <= MAX_RECEIVED_CHARS

"""backend/report_builder.py + backend/report_utils.py: what may be sent to AbuseIPDB.

The rules come from AbuseIPDB's /report documentation (age limit 60 days, at most 1024 characters in the comment,
a valid category id) and from the project's own policy of never sending personal data. Time-dependent cases are
built relative to "now", so they do not rot.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.report_builder import ABUSEIPDB_CATEGORIES, build_comment, local_assessment, validate_hard_checks
from backend.report_utils import (
    MAX_COMMENT_CHARS,
    attack_age,
    find_pii,
    is_reportable_ip,
    own_identifiers,
    redact_pii,
    sanitize_comment,
    truncate_chars,
)


def iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


PUBLIC_IP = "8.8.8.8"


# ---- validate_hard_checks: age ----

@pytest.mark.parametrize("days, ok", [(0, True), (1, True), (59, True), (60, True), (61, False), (400, False)])
def test_age_limit_is_60_days_inclusive(days, ok):
    result = validate_hard_checks(PUBLIC_IP, iso(-timedelta(days=days, hours=1)), [7])
    assert result["age_ok"] is ok
    assert (result["age_reason"] is None) is ok
    assert result["all_passed"] is ok


def test_age_missing():
    result = validate_hard_checks(PUBLIC_IP, None, [7])
    assert result["age_ok"] is False and result["age_reason"]
    assert result["all_passed"] is False


@pytest.mark.parametrize("bad", ["yesterday", "2026-13-45T00:00:00Z", "12/31/2026"])
def test_age_unparseable_date_is_rejected_not_crashing(bad):
    result = validate_hard_checks(PUBLIC_IP, bad, [7])
    assert result["age_ok"] is False and result["age_reason"]


def test_age_far_future_is_rejected():
    assert validate_hard_checks(PUBLIC_IP, iso(timedelta(days=3)), [7])["age_ok"] is False


def test_age_small_clock_skew_in_the_future_is_tolerated():
    assert validate_hard_checks(PUBLIC_IP, iso(timedelta(minutes=10)), [7])["age_ok"] is True


def test_age_naive_timestamp_is_taken_as_utc_and_zulu_suffix_is_accepted():
    naive = (datetime.now(timezone.utc) - timedelta(days=2)).replace(tzinfo=None).isoformat()
    zulu = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert validate_hard_checks(PUBLIC_IP, naive, [7])["age_ok"] is True
    assert validate_hard_checks(PUBLIC_IP, zulu, [7])["age_ok"] is True


def test_attack_age_whole_days_and_limit():
    now = datetime.now(timezone.utc)
    assert attack_age(now - timedelta(days=3, hours=2)) == (3, True)
    assert attack_age(now - timedelta(days=61)) == (61, False)
    days, ok = attack_age(now + timedelta(days=2))
    assert days < 0 and ok is False


# ---- validate_hard_checks: IP ----

@pytest.mark.parametrize("ip", ["10.0.0.5", "192.168.1.1", "127.0.0.1", "::1", "203.0.113.45", "garbage", ""])
def test_unreportable_ips(ip):
    result = validate_hard_checks(ip, iso(-timedelta(days=1)), [7])
    assert result["ip_ok"] is False and result["ip_reason"]
    assert result["all_passed"] is False


@pytest.mark.parametrize("ip", [PUBLIC_IP, "8.8.8.8", "2606:4700:4700::1111"])
def test_reportable_ips(ip):
    assert is_reportable_ip(ip) == (True, None)


# ---- validate_hard_checks: categories ----

@pytest.mark.parametrize(
    "categories, ok",
    [([7], True), ([7, 11], True), ([], False), ([0], False), ([999], False), ([7, 999], False), ([-1], False)],
)
def test_categories(categories, ok):
    assert validate_hard_checks(PUBLIC_IP, iso(-timedelta(days=1)), categories)["category_ok"] is ok


def test_category_ids_match_the_abuseipdb_documentation():
    # https://www.abuseipdb.com/categories: ids 1-23, 7 = Phishing, 11 = Email Spam
    assert sorted(ABUSEIPDB_CATEGORIES) == list(range(1, 24))
    assert ABUSEIPDB_CATEGORIES[7] == "Phishing"
    assert ABUSEIPDB_CATEGORIES[11] == "Email Spam"


def test_all_passed_needs_every_check():
    good = validate_hard_checks(PUBLIC_IP, iso(-timedelta(days=1)), [7])
    assert good == {**good, "ip_ok": True, "age_ok": True, "category_ok": True, "all_passed": True}
    assert good["ip_reason"] is None and good["age_reason"] is None


# ---- build_comment ----

def test_comment_basic_shape():
    comment = build_comment(PUBLIC_IP, False, [], None, None)
    assert comment == f"Suspicious email delivered directly from IP {PUBLIC_IP}."


def test_comment_mentions_spoofing_only_when_confirmed():
    assert "SPF/DMARC" in build_comment(PUBLIC_IP, True, [], None, None)
    assert "SPF/DMARC" not in build_comment(PUBLIC_IP, False, [], None, None)


def test_comment_message_id_keeps_only_the_local_part():
    comment = build_comment(PUBLIC_IP, False, [], None, "<abc123@private-company.example>")
    assert "Message-ID: abc123" in comment
    assert "private-company.example" not in comment


def test_comment_message_id_without_domain():
    assert "Message-ID: abc123" in build_comment(PUBLIC_IP, False, [], None, "abc123")


def test_comment_attachment_double_extension_is_flagged():
    attachment = {
        "filename": "invoice.pdf.exe", "size_bytes": 1234, "content_type": "application/octet-stream",
        "apparent_extension": "pdf", "declared_extension": "exe",
    }
    comment = build_comment(PUBLIC_IP, False, [attachment], None, None)
    assert "invoice.pdf.exe" in comment
    assert "double extension" in comment


def test_comment_attachment_without_mismatch_has_no_double_extension_note():
    attachment = {"filename": "a.pdf", "size_bytes": 1, "content_type": "application/pdf",
                  "apparent_extension": "pdf", "declared_extension": "pdf"}
    assert "double extension" not in build_comment(PUBLIC_IP, False, [attachment], None, None)


def test_comment_ransom_details():
    comment = build_comment(PUBLIC_IP, False, [], {"amount": "0.5", "currency": "BTC", "wallet": "bc1qexamplewallet"}, None)
    assert "Ransom/payment demand: 0.5 BTC" in comment
    assert "bc1qexamplewallet" in comment


def test_comment_is_cut_to_the_limit():
    many = [{"filename": f"file{i}.bin", "size_bytes": i, "content_type": "x/y"} for i in range(200)]
    comment = build_comment(PUBLIC_IP, True, many, None, "<id@example.org>")
    assert len(comment) == MAX_COMMENT_CHARS == 1024


def test_comment_is_plain_ascii_without_control_characters():
    attachment = {"filename": "zażółć‮gpj.exe\x00", "size_bytes": 1, "content_type": "x/y"}
    comment = build_comment(PUBLIC_IP, False, [attachment], None, None)
    assert all(32 <= ord(ch) < 127 or ch == "\n" for ch in comment)


# ---- sanitize_comment / truncate_chars ----

@pytest.mark.parametrize("text", ["=SUM(A1:A9)", "+1 555", "-2+3", "@cmd", "\t=1"])
def test_sanitize_neutralises_spreadsheet_formulas(text):
    # CSV/spreadsheet injection: a leading = + - @ must not survive as the first character
    assert sanitize_comment(text)[0] not in "=+-@"


def test_sanitize_collapses_whitespace_and_non_ascii():
    assert sanitize_comment("a  \n\n b\u00a0c\u0105") == "a b c"


def test_truncate_chars():
    assert truncate_chars("abcdef", 3) == "abc"
    assert truncate_chars("abc", 10) == "abc"
    assert len(truncate_chars("x" * 5000)) == 1024


# ---- personal data in the comment ----

def test_own_identifiers_skip_freemail_domains_but_keep_the_address():
    assert own_identifiers(["me@gmail.com"]) == ["me@gmail.com"]
    assert own_identifiers(["boss@acme-corp.example"]) == ["boss@acme-corp.example", "acme-corp.example"]
    assert own_identifiers(["a@acme-corp.example", "b@acme-corp.example"]) == [
        "a@acme-corp.example", "acme-corp.example", "b@acme-corp.example",
    ]


def test_find_pii_orders_own_then_email_then_private_ip():
    comment = "to boss@acme-corp.example via 10.1.2.3 cc x@other.example"
    findings = find_pii(comment, ["acme-corp.example"])
    assert [f["kind"] for f in findings] == ["own", "email", "email", "private_ip"]
    kinds = {f["value"]: f["kind"] for f in findings}
    assert kinds["acme-corp.example"] == "own"
    assert kinds["x@other.example"] == "email"
    assert kinds["10.1.2.3"] == "private_ip"


def test_find_pii_leaves_public_ips_alone():
    assert find_pii(f"attacker at {PUBLIC_IP}") == []


def test_redact_pii_replaces_every_finding():
    comment = "Mail to boss@acme-corp.example from 192.168.0.9"
    redacted = redact_pii(comment, ["boss@acme-corp.example", "acme-corp.example"])
    assert "acme-corp.example" not in redacted
    assert "192.168.0.9" not in redacted
    assert "boss@" not in redacted


# ---- local_assessment ----

SELF_SENT = "From: me@example.org\nReturn-Path: <me@example.org>\nTo: me@example.org\nSubject: test\n\nhello\n"


def test_local_assessment_recognises_a_self_test():
    result = local_assessment(SELF_SENT, {})
    assert result == {"self_sent": True, "address": "me@example.org"}


def test_local_assessment_other_recipient_is_not_self_sent():
    src = SELF_SENT.replace("To: me@example.org", "To: you@example.net")
    assert local_assessment(src, {})["self_sent"] is False


@pytest.mark.parametrize(
    "facts",
    [{"spoofing_suspected": True}, {"attachments": [{"filename": "x"}]}, {"btc_addresses_found": ["bc1q"]},
     {"ransom_keywords_found": ["bitcoin"]}],
)
def test_local_assessment_any_attack_sign_blocks_the_self_sent_verdict(facts):
    assert local_assessment(SELF_SENT, facts)["self_sent"] is False

"""backend/citation_check.py: the local check of what an LLM analysis quotes from the source. Written from the module's
documented contract (IPs, quoted header lines, `Header: value` quotes, SCL/BCL, Message-ID and hex digests), including
what it deliberately does NOT flag. Public addresses (8.8.8.8, 9.9.9.9) are used where an address must be checked,
because the documentation ranges are skipped on purpose (examples in an analysis)."""
from __future__ import annotations

import pytest

from backend.citation_check import MAX_ISSUES, verify_citations
from backend.i18n import t

SOURCE = """Received: from mail.example.org (mail.example.org [8.8.8.8])
\tby mx.example.net with ESMTPS; Fri, 16 Oct 2026 10:00:00 +0000
From: Alice <alice@example.org>
Message-ID: <abc123@example.org>
X-MS-Exchange-Organization-SCL: 5
Authentication-Results: mx.example.net; spf=pass smtp.mailfrom=example.org

Body text.
"""


def check(markdown, facts=None, extra=()):
    return verify_citations(markdown, SOURCE, list(extra), facts)


def kinds(result):
    return [(i["kind"], i["text"]) for i in result["issues"]]


def test_an_address_that_is_in_the_source_is_fine_and_counted():
    result = check("The sender is 8.8.8.8 and nobody else.")
    assert result == {"checked": 1, "issues": []}


def test_an_address_that_is_not_in_the_source_is_flagged():
    result = check("The sender is 9.9.9.9 and nobody else.")
    assert kinds(result) == [("ip", "9.9.9.9")]
    assert result["issues"][0]["note"] == t("cite.ip_missing")


def test_documentation_addresses_in_examples_are_not_checked():
    assert check("For example 203.0.113.5 or 198.51.100.7 or 2001:db8::1.") == {"checked": 0, "issues": []}


def test_a_time_is_not_taken_for_an_ipv6_address():
    assert check("Sent at 23:50:16 and 10:00:00.")["checked"] == 0


def test_an_ipv6_address_is_checked():
    assert kinds(check("Connecting address 2001:4860:4860::8888 was used.")) == [("ip", "2001:4860:4860::8888")]


def test_defanged_address_is_restored_before_the_check():
    assert kinds(check("The sender was 9[.]9[.]9[.]9 again.")) == [("ip", "9.9.9.9")]
    assert check("The sender was 8[.]8[.]8[.]8 again.")["issues"] == []


def test_an_address_found_only_in_the_facts_or_extra_texts_counts_as_present():
    assert check("Address 9.9.9.9.", facts={"trusted_source_ip": "9.9.9.9"})["issues"] == []
    assert check("Address 9.9.9.9.", extra=["decoded part mentions 9.9.9.9"])["issues"] == []


def test_a_quoted_header_line_that_matches_is_fine():
    md = "```\nFrom: Alice <alice@example.org>\n```"
    assert check(md) == {"checked": 1, "issues": []}


def test_a_quote_may_differ_in_spacing_and_may_use_an_ellipsis():
    md = "```\nAuthentication-Results:   mx.example.net;spf=pass (...) smtp.mailfrom=example.org\n```"
    assert check(md)["issues"] == []


def test_a_quoted_header_with_another_value_is_flagged():
    md = "```\nFrom: Mallory <mallory@evil.example>\n```"
    result = check(md)
    assert kinds(result) == [("header_quote", "From: Mallory <mallory@evil.example>")]
    assert result["issues"][0]["note"] == t("cite.header_mismatch")


def test_a_quoted_header_that_is_not_in_the_source_is_flagged_as_missing():
    result = check("```\nX-Totally-Invented: some long value here\n```")
    assert [i["kind"] for i in result["issues"]] == ["missing_header"]


def test_a_folded_header_in_a_code_block_is_joined_before_the_check():
    md = "```\nReceived: from mail.example.org (mail.example.org [8.8.8.8])\n    by mx.example.net with ESMTPS\n```"
    assert check(md)["issues"] == []


def test_inline_header_quote_with_a_wrong_value():
    result = check("The header `From: Mallory <mallory@evil.example>` shows it.")
    assert kinds(result) == [("header_quote", "From: Mallory <mallory@evil.example>")]
    assert result["issues"][0]["note"] == t("cite.value_differs")


def test_inline_quote_of_a_header_the_source_does_not_have_is_left_alone():
    # the analysis may discuss other messages; only headers present in the source are compared
    assert check("Normally `X-Other: some value here` is present.") == {"checked": 0, "issues": []}


def test_scl_number_must_match_the_source():
    assert check("The SCL: 5 verdict.")["issues"] == []
    assert kinds(check("The SCL=9 verdict.")) == [("number", "SCL=9")]


def test_message_id_and_hex_digest_in_code():
    assert check("The id is `<abc123@example.org>`.")["issues"] == []
    assert kinds(check("The id is `<zzz999@example.org>`.")) == [("identifier", "<zzz999@example.org>")]
    digest = "ab" * 32
    assert kinds(check(f"The hash is `{digest}`.")) == [("identifier", digest)]


def test_domains_and_authentication_values_are_not_checked_on_purpose():
    assert check("Compare with legit.example and `spf=fail` seen elsewhere.") == {"checked": 0, "issues": []}


def test_the_number_of_issues_is_capped():
    many = " ".join(f"9.9.{i // 250}.{i % 250 + 1}" for i in range(MAX_ISSUES + 20))
    result = check(many)
    assert len(result["issues"]) == MAX_ISSUES and result["checked"] == MAX_ISSUES + 20


def test_long_quotes_are_cut_in_the_issue_text():
    result = check("```\nX-Invented: " + "a" * 500 + "\n```")
    assert len(result["issues"][0]["text"]) == 200


@pytest.mark.xfail(strict=True, reason="found in audit stage 5 (T5.11): an address followed by a sentence-final full stop is not extracted, "
                   "so an invented address at the end of a sentence escapes the check (lookahead (?![\\w.]) in _IPV4_RE / _IPV6_RE)")
@pytest.mark.parametrize("text", ["The sender is 9.9.9.9.", "Connecting address 2001:4860:4860::8888.", "Seen at 9.9.9.9. Next sentence."])
def test_an_address_at_the_end_of_a_sentence_is_checked(text):
    assert [i["kind"] for i in check(text)["issues"]] == ["ip"]

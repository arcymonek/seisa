"""backend/mail_trust.py: the building blocks that decide which Received hop is "the sender".

Expected values come from the RFCs (5321/5322/8601 for headers, 1918/3330/4291 for address ranges) and from
reading the inputs by hand, never from running the code under test.
"""
from __future__ import annotations

import pytest

from backend.mail_trust import (
    domains_consistent,
    family,
    hop_specific_auth,
    is_dotless_internal_hop,
    is_special_ip,
    parse_hop_auth,
    parse_ip,
    registrable_domain,
    unfold,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("foo\n bar", "foo bar"),
        ("foo\r\n\tbar", "foo bar"),  # CRLF fold: only the newline plus indentation is collapsed
        ("  padded  ", "padded"),
        ("no fold at all", "no fold at all"),
    ],
)
def test_unfold(value, expected):
    # RFC 5322 section 2.2.3: unfolding removes the CRLF that precedes whitespace; we keep one space
    assert unfold(value).replace("\r", "") == expected


@pytest.mark.parametrize(
    "candidate, expected",
    [
        ("8.8.8.8", "8.8.8.8"),
        ("  8.8.8.8  ", "8.8.8.8"),
        ("2001:DB8::1", "2001:db8::1"),  # RFC 5952: canonical form is lower case
        ("999.1.1.1", None),
        ("example.org", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_ip(candidate, expected):
    assert parse_ip(candidate) == expected


# Only ranges whose status is fixed by an RFC and unchanged across Python versions (the stdlib's treatment of edge
# ranges such as 192.0.0.0/24 or 100.64.0.0/10 has changed between releases, so they are deliberately not pinned).
@pytest.mark.parametrize(
    "ip",
    [
        "10.1.2.3", "172.16.0.1", "192.168.1.1",  # RFC 1918 private
        "127.0.0.1", "::1",  # loopback
        "169.254.10.10", "fe80::1",  # link-local
        "fc00::1",  # RFC 4193 unique local
        "0.0.0.0", "::",  # unspecified
        "224.0.0.1", "ff02::1",  # multicast
        "240.0.0.1",  # reserved
        # documentation ranges (RFC 5737 / 3849): the application treats them as "special" on purpose, which is why
        # the synthetic fixtures can never yield a reportable IP and why real attacker IPs must not be rewritten into them
        "192.0.2.41", "198.51.100.20", "203.0.113.45", "2001:db8::1",
    ],
)
def test_is_special_ip_true(ip):
    assert is_special_ip(ip) is True


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "176.9.44.107", "2606:4700:4700::1111"])
def test_is_special_ip_false_for_public(ip):
    assert is_special_ip(ip) is False


def test_is_special_ip_rejects_garbage():
    with pytest.raises(ValueError):
        is_special_ip("not-an-ip")


@pytest.mark.parametrize(
    "host, expected",
    [
        ("sub.foo.outlook.com", "outlook.com"),
        ("mail.example.org", "example.org"),
        ("Example.COM.", "example.com"),  # case-insensitive, trailing root dot ignored
        ("mail.example.co.uk", "example.co.uk"),  # two-level public suffix keeps one more label
        ("co.uk", "co.uk"),
        ("localhost", "localhost"),
        ("8.8.8.8", None),  # an IP has no registrable domain
        ("2001:db8::1", None),
        ("", None),
        (None, None),
    ],
)
def test_registrable_domain(host, expected):
    assert registrable_domain(host) == expected


def test_registrable_domain_does_not_merge_unrelated_co_uk_organisations():
    assert registrable_domain("a.firm-one.co.uk") != registrable_domain("b.firm-two.co.uk")


@pytest.mark.parametrize(
    "host, ip, expected",
    [
        ("msg-router-59f7c8d4b-q7t3m", None, True),
        ("msg-router-59f7c8d4b-q7t3m", "10.42.1.7", True),
        ("msg-router-59f7c8d4b-q7t3m", "8.8.8.8", False),  # dotless name + public IP is a real external hop
        ("relay.example.org", None, False),  # has a dot: a real host name
        ("127.0.0.1", None, False),  # an IP literal is not a pod name
        ("", None, False),
        (None, None, False),
    ],
)
def test_is_dotless_internal_hop(host, ip, expected):
    assert is_dotless_internal_hop(host, ip) is expected


@pytest.mark.parametrize(
    "domain, expected",
    [
        ("gmail.com", "google"),
        ("googlemail.com", "google"),
        ("outlook.com", "microsoft"),
        ("hotmail.com", "microsoft"),
        ("icloud.com", "apple"),
        ("example.org", "example.org"),  # an unknown domain is its own family
        (None, None),
        ("", None),
    ],
)
def test_family(domain, expected):
    assert family(domain) == expected


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ("example.org", "example.org", True),
        ("mail.example.org", "example.org", True),
        ("example.org", "mail.example.org", True),
        ("EXAMPLE.org.", "example.org", True),
        ("evilexample.org", "example.org", False),  # lookalike: shares a suffix string, not a label boundary
        ("example.org.evil.test", "example.org", False),
        ("example.org", "example.net", False),
        (None, "example.org", False),
        ("example.org", None, False),
        ("", "", False),
    ],
)
def test_domains_consistent(a, b, expected):
    assert domains_consistent(a, b) is expected


def test_parse_hop_auth_full():
    value = "mx.example.org; auth=pass smtp.auth=user@example.org; dkim=pass header.d=example.org"
    assert parse_hop_auth(value) == {"auth": "pass", "smtp_auth_account": "user@example.org", "dkim_domain": "example.org"}


def test_parse_hop_auth_requires_a_plain_auth_verdict():
    # only spf/dkim/dmarc: nothing to correlate with a hop
    assert parse_hop_auth("mx.example.org; spf=pass smtp.mailfrom=example.org; dkim=pass header.d=example.org") is None
    # `smtp.auth=` alone is the account name, not the verdict itself
    assert parse_hop_auth("mx.example.org; smtp.auth=user@example.org") is None


def test_parse_hop_auth_dkim_domain_only_when_dkim_passes():
    result = parse_hop_auth("mx.example.org; auth=pass; dkim=fail header.d=example.org")
    assert result is not None and result["dkim_domain"] is None


def test_parse_hop_auth_verdict_is_lowercased():
    result = parse_hop_auth("mx.example.org; AUTH=PASS")
    assert result is not None and result["auth"] == "pass"


def test_hop_specific_auth_maps_only_the_immediately_following_header():
    headers = [
        ("Received", "from a by b"),  # hop 0
        ("Authentication-Results", "mx; auth=pass smtp.auth=u@example.org"),  # right after hop 0 -> counts
        ("Received", "from c by d"),  # hop 1
        ("Subject", "x"),
        ("Authentication-Results", "mx; auth=pass"),  # separated from hop 1 by another header -> ignored
    ]
    result = hop_specific_auth(headers, hop_count=2)
    assert list(result) == [0]
    assert result[0]["smtp_auth_account"] == "u@example.org"


def test_hop_specific_auth_respects_hop_count_and_header_name_case():
    headers = [
        ("received", "from a by b"),
        ("authentication-results", "mx; auth=pass"),
        ("received", "from c by d"),
        ("authentication-results", "mx; auth=fail"),
    ]
    assert list(hop_specific_auth(headers, hop_count=1)) == [0]
    assert sorted(hop_specific_auth(headers, hop_count=2)) == [0, 1]


def test_hop_specific_auth_ignores_a_forged_header_planted_elsewhere():
    headers = [
        ("Authentication-Results", "attacker.example; auth=pass smtp.auth=boss@example.org"),
        ("Received", "from a by b"),
        ("Subject", "x"),
    ]
    assert hop_specific_auth(headers, hop_count=1) == {}

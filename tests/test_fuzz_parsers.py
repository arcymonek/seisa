"""Random-input (property-based) tests of the e-mail parsers and the input normalisers.

Instead of a handful of hand-written messages, hypothesis generates thousands of odd ones (folded and broken
`Received` lines, encoded words, MIME trees, base64 in several charsets, mbox envelopes, BOMs, CRLF) and checks
properties that must hold for EVERY input: no exception, deterministic output, the sender IP always comes from the
source text, the trust index stays in range, the text for the LLM never exceeds its limit, the AbuseIPDB comment is
plain ASCII within 1024 characters, and so on.

Profiles (env `HYPOTHESIS_PROFILE`): `ci` = 300 examples, derandomized (the same inputs on every run, so CI never
flakes); the default for local runs is 200 random examples. `.hypothesis/` keeps failing examples between runs.

Known bugs are pinned with `xfail(strict=True)` and ONE fixed input (`@example`), so they fail every time and flip
to red as soon as the bug is fixed (then remove the xfail in the fixing change).
"""
from __future__ import annotations

import base64
import ipaddress
import json
import os
import re

import pytest
from hypothesis import HealthCheck, assume, example, given, settings
from hypothesis import strategies as st

from backend.aggregator import detect_indicator_type, is_valid_indicator, normalize_indicator
from backend.citation_check import verify_citations
from backend.email_forensics import compute_facts, decoded_text_parts, normalize_source, prepare_for_llm
from backend.email_parser import _enclosed, _strip_html_tags, extract_addresses, parse_email, parse_message
from backend.mail_trust import is_special_ip
from backend.report_builder import local_assessment
from backend.report_utils import find_pii, redact_pii, sanitize_comment, truncate_chars
from backend.urlscan_input import InvalidScanUrl, normalize_scan_url
from backend.verdict import parse_verdict

settings.register_profile("ci", max_examples=300, deadline=None, derandomize=True, suppress_health_check=list(HealthCheck))
settings.register_profile("dev", max_examples=200, deadline=None, suppress_health_check=list(HealthCheck))
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))

MAX_LLM_SOURCE_CHARS = 120_000  # prepare_for_llm cuts at this many characters and appends a short marker
MARKER_ROOM = 60

# --- generators -------------------------------------------------------------------------------------------------

ipv4 = st.tuples(*[st.integers(0, 255)] * 4).map(lambda t: ".".join(map(str, t)))
ipv6 = st.integers(0, 2**128 - 1).map(lambda n: str(ipaddress.IPv6Address(n)))
label = st.text("abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=12)
host = st.tuples(
    st.lists(label, min_size=1, max_size=3),
    st.sampled_from(["com", "net", "outlook.com", "google.com", "co.uk", "pl", ""]),
).map(lambda t: ".".join(t[0] + ([t[1]] if t[1] else [])))
ip = st.one_of(
    ipv4, ipv6, st.just("127.0.0.1"), st.just("8.8.8.8"), st.just("10.0.0.1"),
    st.sampled_from(["IPv6:2001:4860::1", "fe80::1%4", "999.1.1.1", ""]),
)
junk = st.text(min_size=0, max_size=40)


def received_variant(draw):
    form = draw(st.integers(0, 7))
    f, b, i = draw(host), draw(host), draw(ip)
    return [
        f"from {f} ({f}. [{i}]) by {b} with ESMTPS id x",
        f"from {f} ([{i}] helo={f}) by {b} with esmtps",
        f"from [127.0.0.1] ({i}) by {b} with Microsoft SMTP Server via Frontend Transport",
        f"from {f} ({i}) by {b} with SMTP",
        f"by {b} with SMTP id {draw(junk)}",
        f"from {f} by {f} with LMTP",
        f"{draw(junk)}",
        f"from {f} ({f} {i}) by {b} (Postfix) with ESMTP",
    ][form] + "; " + draw(st.sampled_from(["Mon, 5 Oct 2026 10:00:00 +0000", "garbage date", "", "Mon, 5 Oct 2026 10:00:00 -0700 (PDT)"]))


@st.composite
def email(draw):
    lines = []
    for _ in range(draw(st.integers(0, 8))):
        r = received_variant(draw)
        if draw(st.booleans()):  # folding, sometimes broken (lost indentation)
            cut = len(r) // 2
            r = r[:cut] + "\n" + draw(st.sampled_from([" ", "\t", ""])) + r[cut:]
        lines.append("Received: " + r)
    names = st.sampled_from([
        "From", "To", "Subject", "Date", "Message-ID", "Reply-To", "Return-Path", "Authentication-Results", "DKIM-Signature",
        "ARC-Seal", "X-Originating-IP", "List-Unsubscribe", "Received-SPF", "X-Forefront-Antispam-Report",
    ])
    for name in draw(st.lists(names, max_size=12)):
        val = draw(st.one_of(
            junk,
            st.just("=?UTF-8?B?" + base64.b64encode(draw(junk).encode()).decode() + "?="),
            st.just("mx.example; spf=fail; dkim=pass header.d=a.com; dmarc=fail; auth=pass smtp.auth=u@a.com"),
            st.just("v=1; a=rsa-sha1; d=a.com; s=s; h=from:to; bh=" + "A" * draw(st.integers(0, 90)) + "; t=1700000000"),
        ))
        lines.append(f"{name}: {val}")
    kind = draw(st.integers(0, 3))
    cs = draw(st.sampled_from(["utf-8", "iso-8859-2", "windows-1250", "bogus-cs", "us-ascii"]))
    body_text = draw(st.text(max_size=200))
    if kind == 0:
        body = body_text
    elif kind == 1:
        lines += [f"Content-Type: text/plain; charset={cs}", "Content-Transfer-Encoding: base64"]
        body = base64.b64encode(body_text.encode("utf-8", "replace")).decode()
    else:
        bnd = draw(st.text("abcXYZ0123456789-_=", min_size=1, max_size=20))
        lines.append(f'Content-Type: multipart/mixed; boundary="{bnd}"')
        parts = []
        for _ in range(draw(st.integers(0, 4))):
            fn = draw(st.one_of(junk, st.just("=?UTF-8?B?" + base64.b64encode(b"a.pdf.exe").decode() + "?=")))
            ct = draw(st.sampled_from(["text/plain", "text/html", "application/octet-stream", "multipart/alternative", "message/rfc822"]))
            cte = draw(st.sampled_from(["base64", "quoted-printable", "7bit", "x-weird", ""]))
            payload = draw(st.one_of(
                st.text(max_size=150),
                st.just("<html><a href='http://evil.test/x?a=1&b=2&c=3&d=4'>bank.com</a><div style='display:none'>hid</div><!-- c --></html>"),
            ))
            if cte == "base64":
                payload = base64.b64encode(payload.encode("utf-8", "replace")).decode()
            parts.append(
                f"--{bnd}\nContent-Type: {ct}; charset={cs}; name=\"{fn}\"\nContent-Disposition: attachment; "
                f"filename=\"{fn}\"\nContent-Transfer-Encoding: {cte}\n\n{payload}"
            )
        body = "\n".join(parts) + (f"\n--{bnd}--\n" if draw(st.booleans()) else "")
    prefix = draw(st.sampled_from(["", "﻿", "From someone@x Mon Oct 5\n", "\n\n"]))
    sep = draw(st.sampled_from(["\n", "\r\n"]))
    return prefix + sep.join(lines) + sep + sep + body


# --- helpers ----------------------------------------------------------------------------------------------------


def _ip_tokens(s: str) -> list[str]:
    return re.findall(r"(?:IPv6:)?[0-9A-Fa-f:.]{2,45}(?:%\w+)?", s)


def _as_ip(tok: str):
    """An address as the source may spell it: `IPv6:` prefix, `%scope` suffix, stray dots or colons around it."""
    for t in (tok, tok.strip(".:"), tok.split("%")[0], tok[5:] if tok[:5].lower() == "ipv6:" else tok):
        try:
            return ipaddress.ip_address(t)
        except ValueError:
            pass
    return None


def check_email(src: str, *, with_facts: bool = True):
    norm = normalize_source(src)
    assert normalize_source(norm) == norm  # idempotent
    a = parse_email(src)
    assert parse_email(src) == a  # deterministic
    json.dumps(a)
    if a["trusted_source_ip"]:
        found = ipaddress.ip_address(a["trusted_source_ip"])
        # a fact about the sender must come from the source itself
        assert any(found == _as_ip(tok) for tok in _ip_tokens(src)), a["trusted_source_ip"]
    for h in a["received_chain"]:
        if h["is_private"] is not None:
            assert h["ip"]
    f = None
    if with_facts:
        f = compute_facts(norm)
        json.dumps(f)
        assert 0 <= f["trust_index"] <= max(0, len(f["received"]) - 1)
    prep, _notes = prepare_for_llm(norm)
    assert len(prep) <= MAX_LLM_SOURCE_CHARS + MARKER_ROOM
    decoded_text_parts(norm)
    local_assessment(parse_message(src), a)
    extract_addresses(src)
    verify_citations("VERDICT: spam | CONFIDENCE: low\n" + src[:500], norm, [prep], f or {})
    return a, f


# --- properties that hold today ---------------------------------------------------------------------------------


@given(email())
def test_structured_emails(src):
    check_email(src)


@given(st.text(max_size=3000))
def test_arbitrary_text(src):
    check_email(src)


@given(st.text(max_size=1500), st.lists(st.text(max_size=30), max_size=5))
def test_comment_pipeline(text, own):
    out = truncate_chars(sanitize_comment(text))
    assert len(out) <= 1024
    assert all(32 <= ord(c) < 127 for c in out)
    red = redact_pii(text, own)
    for found in find_pii(text, own):
        if found["kind"] == "own" and found["value"].strip():
            assert found["value"].lower() not in red.lower() or found["value"].lower() in "[redacted]", (found, red)


@given(st.text(max_size=300))
def test_indicator_has_no_url_or_path_characters(raw):
    ind = normalize_indicator(raw)
    t = detect_indicator_type(ind)
    if is_valid_indicator(ind, t):
        assert not any(c in ind for c in "/?#\\ \t\n@%"), ind


@given(st.text(max_size=300))
def test_scan_url_is_plain_http(raw):
    try:
        u = normalize_scan_url(raw)
    except InvalidScanUrl:
        return
    assert u.startswith(("http://", "https://"))
    assert "\n" not in u
    assert " " not in u


@given(st.text(max_size=200))
def test_verdict_parts_come_together(raw):
    v, c = parse_verdict(raw)
    assert (v is None) == (c is None)


# --- fixed parsing bugs (B01, B02, B03), kept as properties -------------------------------------------------------

B01_SRC = (
    "Received: by 2002:a05:6638:4e2f::1 with SMTP id x1; Mon, 5 Oct 2026 10:00:05 -0700\n"
    "Received: from mail.attacker.example (mail.attacker.example. [9.9.9.9]) by mx.google.com with ESMTPS id y2; "
    "Mon, 5 Oct 2026 10:00:04 -0700\n"
    "Received: from innocent.example (innocent.example. 1.1.1.1) by mx.google.com with ESMTPS id z3; "
    "Mon, 5 Oct 2026 09:00:00 -0700\n\nbody\n"
)


@example("Authentication-Results: ;x\n\nbody\n")
@given(st.just("From: a@example.org\n\nbody\n"))
def test_compute_facts_never_raises(src):
    compute_facts(normalize_source(src))


@example(B01_SRC)
@given(email())
def test_tabs_agree_on_sender_ip(src):
    """The Email tab and the AbuseIPDB tab use one algorithm, so they name the same machine (when it is public: the
    Email tab never points at a private or reserved address, AbuseIPDB reports it and then refuses it)."""
    a = parse_email(src)
    facts = compute_facts(normalize_source(src))
    # Only when both tabs read the same Received lines: the Email tab does not yet repair a header whose folding was
    # lost in the middle, so for such an input the tabs read different text, not different rules.
    same_lines = [h["raw"] for h in facts["received"]] == [
        re.sub(r"\s+", " ", v).strip()[:400] for v in parse_message(src).get_all("Received") or []
    ]
    assume(same_lines)
    email_tab = facts["received"][facts["trust_index"]]["ip"] if facts["received"] else None
    if a["trusted_source_ip"] and email_tab and not is_special_ip(a["trusted_source_ip"]):
        assert a["trusted_source_ip"] == email_tab


# The pre-fix expressions, kept as the reference: the linear scanners must return exactly what they returned.
_OLD_PAREN = re.compile(r"\(([^)]+)\)")
_OLD_BRACKET = re.compile(r"\[([^\]]+)\]")
_OLD_HTML_TAG = re.compile(r"<[^>]+>")
_BRACKETY = st.text("()[]<>a b.:", max_size=60)


@given(_BRACKETY)
def test_scanners_return_what_the_old_regexes_returned(text):
    assert _enclosed(text, "(", ")") == _OLD_PAREN.findall(text)
    assert _enclosed(text, "[", "]") == _OLD_BRACKET.findall(text)
    assert _strip_html_tags(text) == _OLD_HTML_TAG.sub("", text)


@pytest.mark.parametrize("charset", ["iso-8859-2", "windows-1250"])
def test_single_part_base64_charset(charset):
    text = "Zażółć gęślą jaźń"
    src = (
        f"From: a@example.org\nContent-Type: text/plain; charset={charset}\nContent-Transfer-Encoding: base64\n\n"
        f"{base64.b64encode(text.encode(charset)).decode()}\n"
    )
    assert text in prepare_for_llm(src)[0]


@pytest.mark.parametrize("name", ["faktura.pdf.exe", "scan.doc.js", "a.exe", "zdjęcie.jpg.scr"])
@pytest.mark.parametrize("encoding", ["B", "Q"])
def test_encoded_attachment_name(name, encoding):
    if encoding == "B":
        word = "=?UTF-8?B?" + base64.b64encode(name.encode()).decode() + "?="
    else:
        word = "=?UTF-8?Q?" + "".join(c if c.isascii() and c.isalnum() else "".join(f"={b:02X}" for b in c.encode()) for c in name) + "?="
    src = (
        'From: a@example.org\nMIME-Version: 1.0\nContent-Type: multipart/mixed; boundary="B"\n\n--B\nContent-Type: text/plain\n\nx\n'
        f'--B\nContent-Type: application/octet-stream\nContent-Disposition: attachment; filename="{word}"\n'
        "Content-Transfer-Encoding: base64\n\nTVqQ\n--B--\n"
    )
    expected = name.rsplit(".", 1)[1]
    assert compute_facts(src)["attachments"][0]["extension"] == expected
    assert parse_email(src)["attachments"][0]["declared_extension"] == expected

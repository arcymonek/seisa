"""Stage 2 of the 2026-10-15 audit: the building blocks both mail tabs share (loading a message, describing an
attachment, reading the receiver's authentication verdicts, the SMTP-AUTH correlation) and the parsing bugs that came
from keeping two copies of them (B04-B09, B26).

Expected values come from RFCs, BIPs and hand-built messages, never from the output of the code under test. The
Bitcoin vectors are the published examples of BIP-173, BIP-350 and the Bitcoin Wiki "Address" page.
"""
from __future__ import annotations

import base64
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from backend.email_forensics import compute_facts, normalize_source, prepare_for_llm
from backend.email_parser import is_valid_btc_address, parse_email
from backend.mail_source import MAX_DECODE_CHARS, attachment_info, decode_words, load_message, refold_headers, unfold
from backend.mail_trust import authserv_id, hop_corroboration, receiver_auth

ROOT = Path(__file__).resolve().parent.parent


def _mime(*parts: str, headers: str = "") -> str:
    return (
        "From: a@example.org\nTo: b@example.org\nSubject: x\nMIME-Version: 1.0\n" + headers
        + 'Content-Type: multipart/mixed; boundary="B"\n\n--B\nContent-Type: text/plain\n\nhi\n'
        + "".join(f"--B\n{p}\n" for p in parts) + "--B--\n"
    )


def _attachment(disposition_params: str) -> str:
    return (
        "Content-Type: application/octet-stream\n"
        f"Content-Disposition: attachment; {disposition_params}\nContent-Transfer-Encoding: base64\n\nTVqQ"
    )


def _b64_word(name: str) -> str:
    return "=?UTF-8?B?" + base64.b64encode(name.encode()).decode() + "?="


def _both_tabs(src: str) -> tuple[dict, dict]:
    """(attachment as the AbuseIPDB tab sees it, attachment as the Email tab sees it)"""
    return parse_email(src)["attachments"][0], compute_facts(normalize_source(src))["attachments"][0]


# ---- B04: attachment names are decoded before the extension is read ----

@pytest.mark.parametrize(
    "disposition",
    [
        f'filename="{_b64_word("faktura.pdf.exe")}"',
        'filename="=?UTF-8?Q?faktura.pdf.exe?="',
        "filename*=UTF-8''faktura.pdf.exe",
        "filename*=UTF-8''" + "faktura.pdf.exe".replace(".", "%2E"),
        f'filename="{_b64_word("faktura.pdf.exe")}"; size=4',
    ],
)
def test_encoded_attachment_name_still_shows_the_exe(disposition):
    abuse, email = _both_tabs(_mime(_attachment(disposition)))
    assert abuse["declared_extension"] == "exe" and abuse["apparent_extension"] == "pdf"
    assert email["extension"] == "exe" and email["double_extension_as"] == "pdf" and email["risky_extension"] is True
    assert abuse["filename"] == email["filename"] == "faktura.pdf.exe"


def test_encoded_attachment_name_raises_the_double_extension_warning():
    src = normalize_source(_mime(_attachment(f'filename="{_b64_word("faktura.pdf.exe")}"')))
    texts = [f["text"] for f in compute_facts(src)["flags"] if f["level"] == "warn"]
    assert any("faktura.pdf.exe" in text for text in texts)


def test_polish_letters_in_an_encoded_attachment_name():
    abuse, email = _both_tabs(_mime(_attachment(f'filename="{_b64_word("zażółć gęślą.doc.js")}"')))
    assert (abuse["declared_extension"], abuse["apparent_extension"]) == ("js", "doc")
    assert (email["extension"], email["double_extension_as"]) == ("js", "doc")
    assert email["filename"] == "zażółć gęślą.doc.js"


def test_right_to_left_override_cannot_hide_the_extension():
    # U+202E reverses the display order: the file is "faktura" + "fdp.exe" for the file system
    abuse, email = _both_tabs(_mime(_attachment(f'filename="{_b64_word("faktura" + chr(0x202E) + "fdp.exe")}"')))
    assert abuse["declared_extension"] == "exe" and email["extension"] == "exe" and email["risky_extension"] is True


def test_trailing_dot_or_space_cannot_hide_the_extension():
    # Windows drops them when the file is saved, so "a.pdf.exe." is "a.pdf.exe"
    for name in ("faktura.pdf.exe.", "faktura.pdf.exe  "):
        abuse, email = _both_tabs(_mime(_attachment(f'filename="{name}"')))
        assert abuse["declared_extension"] == email["extension"] == "exe", name


def test_both_tabs_use_the_same_list_of_innocent_looking_extensions():
    for apparent in ("bmp", "rar", "pdf", "docx"):
        abuse, email = _both_tabs(_mime(_attachment(f'filename="x.{apparent}.exe"')))
        assert abuse["apparent_extension"] == email["double_extension_as"] == apparent


def test_plain_attachment_names_are_unchanged():
    abuse, email = _both_tabs(_mime(_attachment('filename="report.pdf"')))
    assert (abuse["declared_extension"], abuse["apparent_extension"]) == ("pdf", None)
    assert (email["extension"], email["double_extension_as"], email["risky_extension"]) == ("pdf", None, False)
    assert abuse["size_bytes"] == email["size"] == 3 and abuse["content_type"] == email["content_type"] == "application/octet-stream"
    assert email["sha256"] == hashlib.sha256(base64.b64decode("TVqQ")).hexdigest()


# ---- B08: charset of a single-part base64 body ----

@pytest.mark.parametrize("charset", ["iso-8859-2", "windows-1250"])
def test_single_part_base64_uses_the_declared_charset(charset):
    text = "Zażółć gęślą jaźń"
    src = (
        f"From: a@example.org\nContent-Type: text/plain; charset={charset}\nContent-Transfer-Encoding: base64\n\n"
        f"{base64.b64encode(text.encode(charset)).decode()}\n"
    )
    prepared = prepare_for_llm(src)[0]
    assert text in prepared and f"(charset {charset})" in prepared


@pytest.mark.parametrize("charset", ["iso-8859-2", "windows-1250"])
def test_last_part_of_a_multipart_uses_its_own_charset(charset):
    text = "Zażółć gęślą jaźń"
    src = (
        'From: a@example.org\nMIME-Version: 1.0\nContent-Type: multipart/alternative; boundary="B"\n\n'
        f"--B\nContent-Type: text/plain; charset={charset}\nContent-Transfer-Encoding: base64\n\n"
        f"{base64.b64encode(text.encode(charset)).decode()}\n--B--\n"
    )
    assert text in prepare_for_llm(src)[0]


def test_single_part_base64_without_a_charset_is_still_read_as_utf8():
    src = "From: a@example.org\nContent-Type: text/plain\nContent-Transfer-Encoding: base64\n\n" + base64.b64encode("Zażółć".encode()).decode() + "\n"
    assert "Zażółć" in prepare_for_llm(src)[0]


# ---- B05: Bitcoin addresses need a valid checksum, ransom words need to be whole words ----

# published examples: BIP-173 (v0), BIP-350 (v1 and later) and the Bitcoin Wiki "Address" page (legacy)
VALID_BTC = [
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # BIP-173, P2WPKH
    "bc1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3qccfmv3",  # BIP-173, P2WSH
    "bc1pw508d6qejxtdg4y5r3zarvary0c5xw7kw508d6qejxtdg4y5r3zarvary0c5xw7kt5nd6y",  # BIP-350, v1, 40 bytes
    "bc1zw508d6qejxtdg4y5r3zarvaryvaxxpcs",  # BIP-350, v2
    "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0",  # BIP-350, v1 (taproot)
    "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",  # Bitcoin Wiki, P2PKH
    "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # Bitcoin Wiki, P2SH
]


def _mail_with(body: str) -> str:
    return f"From: a@example.org\nSubject: z\n\n{body}\n"


@pytest.mark.parametrize("address", VALID_BTC)
def test_valid_bitcoin_address_is_found(address):
    assert parse_email(_mail_with(f"Send to {address} now"))["btc_addresses_found"] == [address]


def _flip(address: str) -> str:
    """The same address with one letter changed (and so a broken checksum)."""
    i = len(address) // 2
    return address[:i] + ("q" if address[i] != "q" else "p") + address[i + 1:]


@pytest.mark.parametrize("address", VALID_BTC)
def test_address_with_one_changed_letter_is_not_found(address):
    assert parse_email(_mail_with(f"Send to {_flip(address)} now"))["btc_addresses_found"] == []


@pytest.mark.parametrize("lookalike", ["1AbCdEfGhJkLmNpQrStUvWxYz12345", "1Z999AA10123456784XQZ999AA101234567"])
def test_random_text_that_looks_like_an_address_is_not_found(lookalike):
    assert parse_email(_mail_with(f"Your tracking number: {lookalike}"))["btc_addresses_found"] == []


@pytest.mark.parametrize("body", ["Pay the ransom in bitcoin", "send BTC today", "Your WALLET is locked", "files are encrypted, decrypt them",
                                   "ransomware found", "two bitcoins", "decryption key", "payments overdue"])
def test_ransom_words_are_found(body):
    assert parse_email(_mail_with(body))["ransom_keywords_found"] is True


@pytest.mark.parametrize("body", ["subpayment received", "a course in cryptography", "unwalleted", "the btcweb project", "undecrypted"])
def test_ransom_words_inside_other_words_are_not_found(body):
    assert parse_email(_mail_with(body))["ransom_keywords_found"] is False


# ---- B06 + B09: the same loading for both tabs (lost folding, BOM, leading blank lines) ----

LOST_FOLDING = (
    "Received: from mail.attacker.example (mail.attacker.example [8.8.8.8])\n"
    "by mx.example.org with ESMTPS id abc; Mon, 5 Oct 2026 10:00:00 +0000\n"
    "From: x@attacker.example\n"
    "To: me@example.org\n"
    "Subject: hi\n"
    "Date: Mon, 5 Oct 2026 10:00:00 +0000\n"
    "\nbody\n"
)


def test_email_tab_repairs_headers_that_lost_their_indentation():
    facts = compute_facts(normalize_source(LOST_FOLDING))
    assert [(r["ip"], r["by_host"]) for r in facts["received"]] == [("8.8.8.8", "mx.example.org")]
    assert facts["overview"]["subject"] == "hi" and facts["overview"]["from"] == "x@attacker.example"
    assert parse_email(LOST_FOLDING)["trusted_source_ip"] == "8.8.8.8"


def test_email_tab_keeps_showing_the_source_as_it_was_pasted():
    src = normalize_source(LOST_FOLDING)
    assert compute_facts(src)["overview"]["source_chars"] == len(src)


@pytest.mark.parametrize("prefix", ["﻿", "\n\n", "\r\n\r\n", "﻿\n\n"])
def test_abuseipdb_api_reads_a_source_with_a_bom_or_leading_blank_lines(prefix):
    assert parse_email(prefix + LOST_FOLDING) == parse_email(LOST_FOLDING)


# ---- B07: the receiver's verdicts, also when Microsoft 365 omits the authserv-id ----

M365_AUTH = (
    "spf=pass (sender IP is 9.9.9.9) smtp.mailfrom=example.org; dkim=pass (signature was verified) header.d=example.org;"
    " dmarc=pass action=none header.from=example.org;"
)


def _m365(auth_header: str = f"Authentication-Results: {M365_AUTH}", after_received: bool = True) -> str:
    received = (
        "Received: from BL6PEPF0001AB56.namprd02.prod.outlook.com (2603:10b6:208::d7) by MN2PR01CA0066.outlook.office365.com"
        " (2603:10b6:208::35) with Microsoft SMTP Server; Mon, 5 Oct 2026 10:00:03 +0000\n"
    )
    oldest = (
        "Received: from mail-nam.example.net (9.9.9.9) by BL6PEPF0001AB56.mail.protection.outlook.com (10.1.1.1)"
        " with Microsoft SMTP Server; Mon, 5 Oct 2026 10:00:02 +0000\n"
    )
    top = "Received: from AS8P194MB1922.EURP194.PROD.OUTLOOK.COM (2603:10a6::1) by PR3P194MB0556.EURP194.PROD.OUTLOOK.COM with HTTPS; x\n"
    middle = auth_header + "\n" if after_received else ""
    return top + received + middle + oldest + "From: a@example.org\nTo: b@example.org\nSubject: s\nDate: Mon, 5 Oct 2026 10:00:00 +0000\n\nbody\n"


def test_m365_authentication_results_without_an_authserv_id_are_verified():
    facts = compute_facts(normalize_source(_m365()))
    entry = facts["auth"][0]
    assert entry["authserv_id"] is None  # "spf=pass" is a result, not a server name
    assert entry["matches_receiver"] is True
    assert entry["results"]["spf"] == "pass"
    assert facts["auth_summary"] == {
        "spf": "pass", "dkim": "pass", "dmarc": "pass", "verified": True, "authserv_id": None, "header": "Authentication-Results",
    }
    assert parse_email(_m365())["spf"] == "pass"


def test_authentication_results_far_from_any_received_stay_unverified():
    src = _m365(after_received=False).replace("To: b@example.org", f"Authentication-Results: {M365_AUTH}\nTo: b@example.org")
    facts = compute_facts(normalize_source(src))
    assert facts["auth"][0]["matches_receiver"] is None
    assert facts["auth_summary"]["verified"] is False and facts["auth_summary"]["spf"] == "pass"


def test_x_ms_exchange_authentication_results_are_read_by_the_email_tab():
    facts = compute_facts(normalize_source(_m365(f"X-MS-Exchange-Authentication-Results: {M365_AUTH}")))
    assert [a["header"] for a in facts["auth"]] == ["X-MS-Exchange-Authentication-Results"]
    assert facts["auth_summary"]["header"] == "X-MS-Exchange-Authentication-Results"
    assert facts["auth_summary"]["dkim"] == "pass" and facts["auth_summary"]["verified"] is True
    assert parse_email(_m365(f"X-MS-Exchange-Authentication-Results: {M365_AUTH}"))["dmarc"] == "pass"


GMAIL = (
    "Received: by 2002:a05:6a00:1 with SMTP id abc; Mon, 5 Oct 2026 10:00:05 -0700 (PDT)\n"
    "Received: from mail.sender.example (mail.sender.example. [9.9.9.9]) by mx.google.com with ESMTPS id q1; Mon, 5 Oct 2026 10:00:04 -0700\n"
    "Authentication-Results: mx.google.com;\n"
    "       spf=pass smtp.mailfrom=sender.example;\n"
    "       dkim=pass header.d=sender.example;\n"
    "       dmarc=pass header.from=sender.example\n"
    "From: a@sender.example\n\nbody\n"
)


def test_gmail_with_an_authserv_id_is_still_verified():
    summary = compute_facts(normalize_source(GMAIL))["auth_summary"]
    assert summary == {"spf": "pass", "dkim": "pass", "dmarc": "pass", "verified": True, "authserv_id": "mx.google.com", "header": "Authentication-Results"}


def test_a_forged_authentication_results_lower_in_the_headers_cannot_win():
    forged = "Authentication-Results: mx.google.com; spf=pass; dkim=pass; dmarc=pass\n"
    genuine = GMAIL.replace("spf=pass smtp.mailfrom", "spf=fail smtp.mailfrom").replace("dmarc=pass", "dmarc=fail")
    src = genuine.replace("From: a@sender.example", forged + "From: a@sender.example")
    summary = compute_facts(normalize_source(src))["auth_summary"]
    assert (summary["spf"], summary["dmarc"]) == ("fail", "fail")
    facts = parse_email(src)
    assert (facts["spf"], facts["dmarc"], facts["spoofing_suspected"]) == ("fail", "fail", True)


def test_a_message_without_any_verdict_has_an_empty_summary():
    summary = compute_facts(normalize_source("Received: from a.example (a.example [9.9.9.9]) by mx.example.org; x\nFrom: a@example.org\n\nb\n"))["auth_summary"]
    assert summary == {"spf": None, "dkim": None, "dmarc": None, "verified": False, "authserv_id": None, "header": None}


def test_received_spf_fills_in_a_missing_spf_verdict():
    src = GMAIL.replace("       spf=pass smtp.mailfrom=sender.example;\n", "").replace(
        "Authentication-Results:", "Received-SPF: softfail (google.com: domain of a@sender.example does not designate 9.9.9.9)\nAuthentication-Results:"
    )
    assert compute_facts(normalize_source(src))["auth_summary"]["spf"] == "softfail"


# ---- B26: the order of the "duplicated header" findings does not depend on the Python hash seed ----

def test_duplicate_header_findings_are_in_a_fixed_order():
    src = "".join(f"{name}: v{i}\n" for i in (1, 2) for name in ("To", "Subject", "Date", "From", "Message-ID", "Reply-To")) + "\nbody\n"
    names = [d["name"] for d in compute_facts(src)["duplicates"]]
    assert names == sorted(names) and len(names) == 6


def test_facts_are_identical_for_different_hash_seeds():
    script = (
        "import json, sys\nsys.path.insert(0, '.')\nfrom backend.email_forensics import compute_facts\n"
        "src = ''.join(f'{n}: v{i}\\n' for i in (1, 2) for n in ('To', 'Subject', 'Date', 'From', 'Message-ID', 'Reply-To', 'Sender')) + '\\nbody\\n'\n"
        "print(json.dumps(compute_facts(src), sort_keys=True))\n"
    )
    outputs = {
        seed: subprocess.run([sys.executable, "-c", script], cwd=ROOT, env={"PYTHONHASHSEED": seed, "PATH": ""}, capture_output=True, text=True, check=True).stdout
        for seed in ("1", "2", "3")
    }
    assert len(set(outputs.values())) == 1


# ---- the building blocks themselves ----

# BIP-350 lists addresses that must be REJECTED; each fails for the reason in its comment
INVALID_BIP_ADDRESSES = [
    "tc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vq5zuyut",  # wrong human-readable part
    "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqh2y7hd",  # bech32 checksum on a version-1 address
    "BC1S0XLXVLHEMJA6C4DQV22UAPCTQUPFHLXM9H8Z3K2E72Q4K9HCZ7VQ54WELL",  # bech32 checksum on a version-16 address
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kemeawh",  # bech32m checksum on a version-0 address
    "bc1p38j9r5y49hruaue7wxjce0updqjuyyx0kh56v8s25huc6995vvpql3jow4",  # invalid character "o"
    "BC130XLXVLHEMJA6C4DQV22UAPCTQUPFHLXM9H8Z3K2E72Q4K9HCZ7VQ7ZWS8R",  # invalid witness version 17
    "bc1pw5dgrnzv",  # program too short
    "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7v8n0nx0muaewav253zgeav",  # program too long
    "BC1QR508D6QEJXTDG4Y5R3ZARVARYV98GJ9P",  # version 0 with a program of 16 bytes
    "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7v07qwwzcrf",  # more than 4 bits of zero padding
    "bc1gmk9yu",  # empty program
    "Bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # mixed case
]


@pytest.mark.parametrize("address", [*VALID_BTC, "BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4", "BC1SW50QGDZ25J"])
def test_valid_vectors_are_accepted(address):
    assert is_valid_btc_address(address)


@pytest.mark.parametrize("address", INVALID_BIP_ADDRESSES)
def test_invalid_bip_vectors_are_rejected(address):
    assert not is_valid_btc_address(address)


def test_legacy_address_with_extra_leading_ones_or_wrong_version_is_rejected():
    assert not is_valid_btc_address("1" + VALID_BTC[5])  # one more "1" than zero bytes
    assert not is_valid_btc_address("Hz" + "1" * 31)  # not a Bitcoin prefix at all
    assert not is_valid_btc_address("1" * 34)


def test_unfold_joins_continuation_lines():
    assert unfold("a\n\tb\n  c ") == "a b c"


def test_decode_words_decodes_and_survives_garbage():
    assert decode_words("=?UTF-8?Q?z=C5=82o?=") == "zło"
    assert decode_words("=?broken") == "=?broken"
    assert decode_words("x" * (MAX_DECODE_CHARS + 50)) == "x" * MAX_DECODE_CHARS  # the documented cut


def test_refold_headers_restores_lost_indentation_and_removes_wrong_one():
    assert refold_headers("Received: from a\nby b\nSubject: s\n\nbody\nnot a header") == "Received: from a\n by b\nSubject: s\n\nbody\nnot a header"
    assert refold_headers("To: a\n    Subject: s\n\nb") == "To: a\nSubject: s\n\nb"


def test_load_message_applies_normalisation_and_refolding_once():
    msg = load_message("﻿\r\nFrom sender@example.org Mon Sep 21 10:00:00 2026\r\nReceived: from a\r\nby b\r\nSubject: s\r\n\r\nbody")
    assert msg.get("Subject") == "s" and "by b" in msg.get("Received")
    assert load_message(load_message("Subject: s\n\nb").as_string()).get("Subject") == "s"  # idempotent


def test_attachment_info_of_a_part_without_a_name_is_none():
    assert attachment_info(load_message("Content-Type: text/plain\n\nhi")) is None


def test_attachment_info_keys_and_oversized_names():
    part = load_message(f'Content-Type: application/octet-stream; name="{"a" * 5000}.txt"\nContent-Disposition: attachment\n\nTVqQ')
    info = attachment_info(part)
    assert set(info) == {"filename", "extension", "double_extension_as", "risky_extension", "size", "sha256", "content_type"}
    assert len(info["filename"]) == 120
    assert info["risky_extension"] is True  # too long to read reliably: reported as risky, never silently harmless


def test_hop_corroboration_cases():
    assert hop_corroboration(None) is None
    assert hop_corroboration({"auth": "fail", "smtp_auth_account": "u@example.org"}) is None
    assert hop_corroboration({"auth": "pass", "smtp_auth_account": None}) is None
    assert hop_corroboration({"auth": "pass", "smtp_auth_account": "u@mail.example.org", "dkim_domain": "example.org"})["consistent"] is True
    assert hop_corroboration({"auth": "pass", "smtp_auth_account": "u@example.org", "dkim_domain": "other.example"})["consistent"] is False
    assert hop_corroboration({"auth": "pass", "smtp_auth_account": "u@example.org", "dkim_domain": None})["consistent"] is None


@pytest.mark.parametrize(
    "value, expected",
    [
        ("mx.google.com; spf=pass", "mx.google.com"),
        ("i=1; mx.google.com; arc=none", "mx.google.com"),
        ("mx.microsoft.com 1; spf=pass", "mx.microsoft.com"),
        ("spf=pass smtp.mailfrom=example.org; dkim=pass", None),
        ("; spf=pass", None),
        ("", None),
    ],
)
def test_authserv_id(value, expected):
    assert authserv_id(value) == expected


def test_receiver_auth_works_on_plain_header_lists():
    headers = [("Received", "from a by mx.google.com"), ("Authentication-Results", "mx.google.com; spf=pass; dkim=fail")]
    assert receiver_auth(headers, ["mx.google.com"])["dkim"] == "fail"
    assert receiver_auth([], [])["header"] is None


def _base58check(version: int, payload: bytes) -> str:
    """An independent encoder (written from the Bitcoin Wiki description) to build addresses with a VALID checksum."""
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    data = bytes([version]) + payload
    data += hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
    number, out = int.from_bytes(data, "big"), ""
    while number:
        number, rest = divmod(number, 58)
        out = alphabet[rest] + out
    return "1" * (len(data) - len(data.lstrip(b"\0"))) + out


@pytest.mark.parametrize("version, ok", [(0x00, True), (0x05, True), (0x06, False), (0x04, False)])
def test_only_the_two_bitcoin_version_bytes_are_addresses(version, ok):
    address = _base58check(version, bytes([200]) * 20)
    assert address[0] in "123"  # looks like a candidate in every case
    assert is_valid_btc_address(address) is ok

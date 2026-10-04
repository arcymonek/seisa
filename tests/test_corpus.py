"""Optional local corpus: REAL e-mails kept out of the repository (tests/private/ is gitignored).

For every `tests/private/<name>.eml` put a `tests/private/<name>.expected.json` next to it. The expectations must
come from outside the code under test: your own knowledge of the message, an independent reader such as Google's
Messageheader, or the RFCs - never from running Seisa and pasting its answer back. All keys are optional:

    {
      "trusted_source_ip": "203.0.113.45",   # the IP of the machine that really delivered the message to the recipient
      "trust_index": 0,                        # which Received entry (0 = top) is the trust boundary
      "spf": "pass", "dkim": "pass", "dmarc": "pass",
      "spoofing_suspected": false,
      "label": "legitimate"                    # or "phishing": a legitimate message must never look like spoofing
    }

Without the directory or without any pair the whole module is skipped, so a fresh clone or a fork still gets a
green `pytest`. A message without an expectations file is skipped, not silently passed.
"""
from __future__ import annotations

import json

import pytest

from backend.email_forensics import compute_facts
from backend.email_parser import parse_email
from tests.helpers import PRIVATE, load_eml

CASES = sorted(PRIVATE.glob("*.eml")) if PRIVATE.is_dir() else []


@pytest.mark.skipif(not CASES, reason="no private e-mails in tests/private/ (optional, see the module docstring)")
@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
def test_private_message(path):
    expected_file = path.with_suffix(".expected.json")
    if not expected_file.exists():
        pytest.skip(f"{expected_file.name} is missing: nothing to compare with")
    expected = json.loads(expected_file.read_text(encoding="utf-8"))
    src = load_eml(path)
    parsed = parse_email(src)

    for key in ("trusted_source_ip", "spf", "dkim", "dmarc", "spoofing_suspected"):
        if key in expected:
            assert parsed[key] == expected[key], key
    if "trust_index" in expected:
        assert compute_facts(src)["trust_index"] == expected["trust_index"]
    if expected.get("label") == "legitimate":
        assert parsed["spoofing_suspected"] is False, "a legitimate message was flagged as spoofed (false alarm)"
    if expected.get("label") == "phishing":
        assert parsed["trusted_source_ip"] is not None, "no sender IP was found in a message you labelled as phishing"

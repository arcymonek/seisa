"""Optional local corpus: REAL e-mails kept out of the repository (tests/private/ is gitignored).

Sort the messages into two folders, so they never get mixed up:

    tests/private/legit/          messages you know are genuine (newsletters, colleagues, services)
    tests/private/phishing_spam/  messages you know are phishing, spam or scams

The folder alone gives a baseline check for every file: a genuine message must never look spoofed (no false
alarm), and every message must be analysed without an error. A phishing message may legitimately have no sender
address (for example mail sent from an Outlook.com account hides it), so the folder never demands one: put the
address you expect into the .expected.json instead. For exact expectations put a
`<name>.expected.json` next to the message (the same name, in the same folder). The expectations must come from
outside the code under test: your own knowledge of the message, an independent reader such as Google's
Messageheader, or the RFCs - never from running Seisa and pasting its answer back. All keys are optional:

    {
      "trusted_source_ip": "203.0.113.45",   # the IP of the machine that really delivered the message to the recipient
      "trust_index": 0,                        # which Received entry (0 = top) is the trust boundary
      "spf": "pass", "dkim": "pass", "dmarc": "pass",
      "spoofing_suspected": false,
      "auth_verified": true,                   # the Email tab found the verdicts written by the recipient's own server
      "label": "legitimate"                    # or "phishing"; overrides the folder
    }

Without any message the whole module is skipped, so a fresh clone or a fork still gets a green `pytest`.
"""
from __future__ import annotations

import json

import pytest

from backend.email_forensics import compute_facts
from backend.email_parser import parse_email
from tests.helpers import PRIVATE, load_eml

FOLDER_LABELS = {"legit": "legitimate", "phishing_spam": "phishing"}
CASES = sorted(PRIVATE.rglob("*.eml")) if PRIVATE.is_dir() else []


@pytest.mark.skipif(not CASES, reason="no private e-mails in tests/private/ (optional, see the module docstring)")
@pytest.mark.parametrize("path", CASES, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_private_message(path):
    expected_file = path.with_suffix(".expected.json")
    expected = json.loads(expected_file.read_text(encoding="utf-8")) if expected_file.exists() else {}
    label = expected.get("label") or FOLDER_LABELS.get(path.parent.name)
    if not expected and label is None:
        pytest.skip("not in legit/ or phishing_spam/ and no .expected.json: nothing to check")
    src = load_eml(path)
    parsed = parse_email(src)

    for key in ("trusted_source_ip", "spf", "dkim", "dmarc", "spoofing_suspected"):
        if key in expected:
            assert parsed[key] == expected[key], key
    if "trust_index" in expected:
        assert compute_facts(src)["trust_index"] == expected["trust_index"]
    if "auth_verified" in expected:
        assert compute_facts(src)["auth_summary"]["verified"] is expected["auth_verified"]
    if label == "legitimate":
        assert parsed["spoofing_suspected"] is False, "a legitimate message was flagged as spoofed (false alarm)"

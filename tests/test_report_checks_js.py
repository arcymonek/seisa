"""The "Received verified" check of the AbuseIPDB tab (frontend/js/report-checks.js), run through Node.

It used to be green whenever the code had found an address, whatever address the form held and however unsure the code
was. Skipped when Node is missing."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is not installed")
RUNNER = Path(__file__).resolve().parent / "js" / "report_checks_run.mjs"

PICKED = "8.8.8.8"


def facts(confidence="high", relay=False, ip=PICKED, reasoning="Because of the chain."):
    return {"trusted_source_ip": ip, "ip_confidence": confidence, "ip_from_relay_lines": relay, "ip_reasoning": reasoning}


def check(**case):
    done = subprocess.run([NODE, str(RUNNER)], input=json.dumps([case]), capture_output=True, text=True, check=True, timeout=60)
    key, status, note = json.loads(done.stdout)[0]
    assert key == "received_verified"
    return status, note


def test_green_only_for_the_picked_address_with_high_confidence():
    assert check(facts=facts(), llmItem=None, formIp=PICKED)[0] == "pass"
    assert check(facts=facts(), llmItem=None, formIp=" 8.8.8.8 ")[0] == "pass"


def test_another_address_in_the_form_is_not_verified():
    status, note = check(facts=facts(), llmItem=None, formIp="9.9.9.9")
    assert status == "unknown" and "different address" in note
    assert check(facts=facts(), llmItem=None, formIp="")[0] == "unknown"


def test_lower_confidence_is_not_verified_and_explains_why():
    assert check(facts=facts(confidence="medium"), llmItem=None, formIp=PICKED) == ("unknown", "Because of the chain.")
    assert check(facts=facts(confidence="low", reasoning=""), llmItem=None, formIp=PICKED)[0] == "unknown"
    assert check(facts=facts(relay=True), llmItem=None, formIp=PICKED)[0] == "unknown"


def test_the_opinion_of_the_model_counts_for_the_picked_address_only():
    ok = {"status": "pass", "note": "Looks right."}
    assert check(facts=facts(confidence="low"), llmItem=ok, formIp=PICKED) == ("pass", "Looks right.")
    status, note = check(facts=facts(), llmItem=ok, formIp="9.9.9.9")
    assert status == "unknown" and "different address" in note


def test_a_failed_check_of_the_model_keeps_blocking():
    bad = {"status": "fail", "note": "Written by the sender."}
    assert check(facts=facts(), llmItem=bad, formIp=PICKED) == ("fail", "Written by the sender.")
    assert check(facts=facts(), llmItem=bad, formIp="9.9.9.9")[0] == "fail"


def test_without_a_pasted_message_it_stays_manual():
    assert check(facts=None, llmItem=None, formIp="9.9.9.9") == ("unknown", "No e-mail pasted - verify manually.")
    assert check(facts=facts(ip=None), llmItem=None, formIp="9.9.9.9")[0] == "unknown"

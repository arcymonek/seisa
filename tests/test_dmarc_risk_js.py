"""Risk of a source IP in the DMARC tab (frontend/js/dmarc-data.js), run through Node.

The legend promises: HIGH = messages that fail DMARC (neither SPF nor DKIM aligned), MEDIUM = only one of the two methods
fails somewhere, LOW = everything passes. The check counts messages, not totals per source: an IP whose messages each
pass through one of the methods is not HIGH. Skipped when Node is missing."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is not installed")
RUNNER = Path(__file__).resolve().parent / "js" / "dmarc_risk_run.mjs"


def rec(ip, count, spf, dkim, disposition="none"):
    return {"reportIdx": 0, "sourceIp": ip, "count": count, "spfEval": spf, "dkimEval": dkim, "disposition": disposition}


def run(records):
    done = subprocess.run([NODE, str(RUNNER)], input=json.dumps({"records": records}), capture_output=True, text=True, check=True, timeout=60)
    return json.loads(done.stdout)


def test_every_message_passes_one_method_is_not_high():
    # SPF aligned but DKIM not, and the other way round: all 20 messages pass DMARC (audit 2026-10-15, B11)
    out = run([rec("8.8.8.8", 10, "pass", "fail"), rec("8.8.8.8", 10, "fail", "pass")])
    assert out["rows"] == [{"sourceIp": "8.8.8.8", "count": 20, "dmarcFail": 0, "risk": "medium"}]
    assert out["byIp"] == {"8.8.8.8": "medium"}


def test_one_message_failing_both_is_high():
    out = run([rec("9.9.9.9", 10, "pass", "pass"), rec("9.9.9.9", 1, "fail", "fail", "reject")])
    assert out["rows"][0]["dmarcFail"] == 1 and out["rows"][0]["risk"] == "high"
    assert out["byIp"] == {"9.9.9.9": "high"}


def test_everything_passing_is_low():
    out = run([rec("1.1.1.1", 5, "pass", "pass")])
    assert out["rows"][0]["risk"] == "low" and out["byIp"] == {"1.1.1.1": "low"}


def test_a_negative_or_unreadable_count_counts_as_zero():
    # parseInt("-5") used to subtract from the totals
    out = run([rec("8.8.8.8", 10, "pass", "pass"), rec("8.8.8.8", -5, "fail", "fail"), rec("8.8.8.8", None, "fail", "fail")])
    assert out["rows"][0]["count"] == 10 and out["rows"][0]["risk"] == "low"
    assert out["byIp"] == {"8.8.8.8": "low"}

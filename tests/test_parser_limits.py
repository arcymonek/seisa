"""Time limits for hostile input: a message of about 300 KB must not keep the parsers busy for long.

Seisa parses an e-mail inside the server's single event loop, so a message that takes minutes to parse would freeze
every tab. Each case builds a nasty ~300 KB message and runs `parse_email` + `compute_facts` + `prepare_for_llm` in a
fresh child process; the work (not the interpreter start-up) must finish within WORK_BUDGET seconds. The budget is
generous on purpose (a slow CI runner must not flake), a quadratic regex misses it by orders of magnitude.

The child process is also what makes the known-slow cases safe to keep in the suite: it is killed after
KILL_AFTER seconds instead of blocking the run for minutes (there is no `timeout` command on macOS to rely on).

The slow cases found earlier are fixed; this file keeps them from coming back.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

SIZE = 300_000
WORK_BUDGET = 3.0
KILL_AFTER = 8.0

CHILD = """
import sys, time
from backend.email_parser import parse_email
from backend.email_forensics import compute_facts, normalize_source, prepare_for_llm
src = sys.stdin.read()
t = time.perf_counter()
parse_email(src)
s = normalize_source(src)
compute_facts(s)
prepare_for_llm(s)
print(time.perf_counter() - t)
"""

pytestmark = pytest.mark.slow  # about a minute: every case starts its own interpreter


def repeat(unit: str, head: str, tail: str = "\n\nb") -> str:
    return head + unit * ((SIZE - len(head)) // len(unit)) + tail


CASES = {
    "received from-from": lambda: repeat("from ", "Received: ", "by x\n\nb"),
    "received parens": lambda: repeat("(", "Received: from a "),
    "received nested parens": lambda: repeat("((1", "Received: from a ", " by mx.example with SMTP; Mon, 5 Oct 2026 10:00:00 +0000\n\nb"),
    "received brackets": lambda: repeat("[[1", "Received: from a ", " by mx.example with SMTP; Mon, 5 Oct 2026 10:00:00 +0000\n\nb"),
    "received spaces": lambda: repeat(" ", "Received: from a", "x\n\nb"),
    "auth-results": lambda: repeat("spf=", "Authentication-Results: "),
    "dkim tags": lambda: repeat("a=", "DKIM-Signature: "),
    "subject words": lambda: repeat("=?utf-8?q?a ", "Subject: "),
    "html nest": lambda: repeat("<div style='display:none'>", "Content-Type: text/html\n\n", "\n"),
    "html attrs": lambda: repeat("http://", "Content-Type: text/html\n\n<a href='", "'>x</a>"),
    "html tag names": lambda: repeat("<", "Content-Type: text/html\n\n", "\n"),
    "body urls": lambda: repeat("http://a", "\n\n", "\n"),
    "placeholders": lambda: repeat("{{", "\n\n", "\n"),
    "many headers": lambda: "".join(f"X-{i}: v\n" for i in range(SIZE // 10)) + "\nb",
    "email-like": lambda: repeat("a.", "\n\n", "@"),
    "btc": lambda: repeat("1", "\n\n", "\n"),
    "boundary": lambda: repeat("a", "Content-Type: multipart/mixed; boundary=", "\n\n--" + "a" * 1000),
    "many received": lambda: "".join("Received: from a ((1 [[2 by mx.example; Mon, 5 Oct 2026 10:00:00 +0000\n" for _ in range(SIZE // 71)) + "\nb",
    "100 long received": lambda: "".join("Received: from a " + "((1" * 2700 + " by mx.example; Mon, 5 Oct 2026 10:00:00 +0000\n" for _ in range(37)) + "\nb",
    "mbox": lambda: repeat("x ", "From ", "\nA: b\n\nc"),
}


@pytest.mark.parametrize("name", list(CASES))
def test_hostile_input_is_parsed_quickly(name):
    src = CASES[name]()
    assert SIZE * 0.9 <= len(src) <= SIZE * 1.1, len(src)
    try:
        out = subprocess.run([sys.executable, "-c", CHILD], input=src, capture_output=True, text=True, timeout=KILL_AFTER, check=False)
    except subprocess.TimeoutExpired:
        pytest.fail(f"still running after {KILL_AFTER} s")
    assert out.returncode == 0, out.stderr[-500:]
    assert float(out.stdout.strip()) <= WORK_BUDGET

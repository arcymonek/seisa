"""Golden pattern of the e-mail facts: `scripts/dump_facts.py` output for the synthetic fixtures must not drift.

`tests/golden/dump_facts.{pl,en}.txt` were generated from the unchanged `main` of 2026-10-15 (Seisa 2.4.21). Any change
of `compute_facts`, `parse_email` or `prepare_for_llm` that alters a fact, a flag text or a note shows up here as a
unified diff.

Rule: a golden file changes ONLY in a commit that deliberately changes the facts, and the pull request explains every
difference line by line. Regenerate with:

    python3 scripts/dump_facts.py --lang pl > tests/golden/dump_facts.pl.txt   (and --lang en for the other file)

A refactor or a translation change must leave both files byte-for-byte as they are.
"""
from __future__ import annotations

import difflib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = Path(__file__).resolve().parent / "golden"


@pytest.mark.parametrize("lang", ["pl", "en"])
def test_facts_match_the_golden_pattern(lang):
    # A child process: the dump switches the UI language globally and imports the backend fresh, like CI does.
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "dump_facts.py"), "--lang", lang],
        capture_output=True, text=True, check=True, cwd=ROOT,
    ).stdout
    expected = (GOLDEN / f"dump_facts.{lang}.txt").read_text(encoding="utf-8")
    if out != expected:
        diff = "".join(difflib.unified_diff(
            expected.splitlines(keepends=True), out.splitlines(keepends=True), "golden", "current", n=2,
        ))
        pytest.fail(f"facts differ from tests/golden/dump_facts.{lang}.txt:\n{diff[:6000]}")

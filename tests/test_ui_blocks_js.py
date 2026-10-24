"""The shared HTML blocks of frontend/js/ui.js (summary tile, definition list, Explanations card), run through Node.

Their plain-text arguments (captions, labels, terms, explanations) go into innerHTML, so they must come out escaped:
markup in the text is shown, never interpreted. Arguments named ...Html (the values of kvHtml) are already escaped by
the caller and pass through unchanged. Skipped when Node is missing."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is not installed")
RUNNER = Path(__file__).resolve().parent / "js" / "ui_blocks_run.mjs"

PAYLOAD = '<img src=x onerror="window.__xss=1">&'
ESCAPED = "&lt;img src=x onerror=&quot;window.__xss=1&quot;&gt;&amp;"


def blocks() -> dict[str, str]:
    done = subprocess.run([NODE, str(RUNNER)], input=json.dumps(PAYLOAD), capture_output=True, text=True, check=True, timeout=60)
    return json.loads(done.stdout)


def test_plain_text_never_becomes_markup():
    for name, html in blocks().items():
        assert "<img" not in html, name
        assert ESCAPED in html, name


def test_every_text_slot_is_escaped():
    out = blocks()
    assert out["kpi"].count(ESCAPED) == 3  # caption, value, line under it
    assert out["legend"].count(ESCAPED) == 6  # title, two terms, two leads, one folded detail


def test_value_markup_of_a_definition_list_passes_through():
    assert "<dd><b>ok</b></dd>" in blocks()["kv"]

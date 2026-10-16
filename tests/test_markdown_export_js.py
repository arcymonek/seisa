"""The Markdown helpers of the browser exports (frontend/js/markdown-export.js), run through Node.

The frontend has no unit-test framework, so this test starts Node on a tiny runner (tests/js/markdown_export_run.mjs) and
checks the results with a real CommonMark parser, like tests/test_markdown_safety.py does for the Python twins. Skipped
when Node or markdown-it-py is missing."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.markdown_utils import defang_url, fence, md_code, md_text
from tests.helpers import assert_inert_markdown, markdown_tokens

pytest.importorskip("markdown_it")
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is not installed")
RUNNER = Path(__file__).resolve().parent / "js" / "markdown_export_run.mjs"


def run_js(calls: list[list]) -> list:
    done = subprocess.run([NODE, str(RUNNER)], input=json.dumps(calls), capture_output=True, text=True, check=True, timeout=60)
    return json.loads(done.stdout)


# Each of these tries to get an image, a link or HTML out of a text that is only supposed to be read.
HOSTILE = {
    "image": "![x](http://evil.example/p.png)",
    "link": "[click](http://evil.example/a)",
    "html_img": "<img src=x onerror=alert(1)>",
    "html_script": "<script>alert(1)</script> <a href=\"javascript:alert(1)\">x</a>",
    "html_comment": "<!-- hidden http://evil.example/h -->",
    "autolink": "<http://evil.example/b> <someone@evil.example>",
    "bare": "see http://evil.example/c, HTTPS://EVIL.EXAMPLE/d and www.evil.example.",
    "reference": "[a][1] and ![b][1]\n\n[1]: http://evil.example/ref",
    "reference_in_quote": "[a]\n\n> [a]: http://evil.example/q\n\n- [b]: http://evil.example/q2\n\n[b]",
    "reference_multiline": "[a]:\nhttp://evil.example/n\n\n[a]",
    "reference_multiline_label": "[a\nb]: http://evil.example/n\n\n[a b]",
    "nested": "[![alt](http://evil.example/i.png)](http://evil.example/l)",
    "parens": "[click](http://evil.example/(a(b))) [x](<http://evil.example/a b>)",
    "titled": '[click](http://evil.example/a "title") ![i](http://evil.example/i.png \'t\')',
    "javascript": "[a](javascript:alert(1)) ![b](data:image/png;base64,AAAA)",
    "table_backticks": "| ` | ![a](http://evil.example/p.png) | ` |\n|---|---|---|\n| ` | [b](http://evil.example/q) | ` |",
    "escaped_backtick": "\\`![a](http://evil.example/p.png)\\`",
    "fence_info_backtick": "```a`\n![a](http://evil.example/p.png)\n```",
    "fence_in_list": "- x\n  ```\n![a](http://evil.example/p.png)\n```",
    "unclosed_inline": "a ` b\n\n![x](http://evil.example/p.png) \n\n c `",
    "span_across_lines": "`a\n![x](http://evil.example/p.png)\nb`",
    "forged_placeholder": "\ue0000\ue001 ![x](http://evil.example/p.png)",
    "entity": "&lt;img src=x&gt; &#60;b&#62;",
}


@pytest.mark.parametrize("name", sorted(HOSTILE))
def test_safe_markdown_text_is_inert(name):
    (out,) = run_js([["safeMarkdownText", HOSTILE[name]]])
    assert_inert_markdown(out)


def test_safe_markdown_text_keeps_code_and_ordinary_markup():
    text = "## Title\n\n**bold**, _it_ and [Fact] label.\n\n- item\n\n```\ncurl http://ok.example/x\n```\n\n`code http://ok.example` and a | b\n"
    (out,) = run_js([["safeMarkdownText", text]])
    assert "## Title" in out and "**bold**" in out and "[Fact] label" in out and "- item" in out
    assert "curl http://ok.example/x" in out  # code is shown as written
    types = [tok.type for tok in markdown_tokens(out)]
    assert "heading_open" in types and "fence" in types and "code_inline" in types and "bullet_list_open" in types


def test_safe_markdown_text_shows_what_was_removed():
    (out,) = run_js([["safeMarkdownText", "![logo](http://evil.example/p.png) and [click here](http://evil.example/a)"]])
    assert "image: logo" in out and "hxxp://evil[.]example/p[.]png" in out
    assert "click here" in out and "hxxp://evil[.]example/a" in out


MIRROR_SAMPLES = [
    "plain words",
    "Registrar: Example Inc., Ltd (EU) snake_case 3 items - ok",
    "![x](http://evil.example/p.png) <b>hi</b> [a](b) *x* _y_ a|b `c`",
    "# title", "- item", "1. item", "> quote", "=== x", "2) item",
    "see http://evil.example/c, and www.evil.example. ftp://x.example/a|b",
    "line one\nline   two\t\ttabbed",
    "x_y _z_ __w__ end_",
    "",
]


def test_javascript_and_python_helpers_agree():
    calls = []
    for sample in MIRROR_SAMPLES:
        calls += [["mdText", sample], ["mdCode", sample], ["defangForText", sample]]
    for sample in ("plain", "a ``` b", "`````x", ""):
        calls.append(["mdFence", sample])
    results = iter(run_js(calls))
    for sample in MIRROR_SAMPLES:
        assert next(results) == md_text(sample), sample
        assert next(results) == md_code(sample), sample
        assert next(results) == defang_url(sample).replace("\n", "\n"), sample
    for sample in ("plain", "a ``` b", "`````x", ""):
        marker = fence(sample)
        assert next(results) == [marker, sample, marker]


def test_md_cell_keeps_code_spans_and_escapes_the_rest():
    cells = ["`a|b` and x|y", "![i](http://evil.example/p.png)", "plain", "`one` `two`", ""]
    out = run_js([["mdCell", c] for c in cells])
    assert out[0] == "`a\\|b` and x\\|y"
    assert out[2] == "plain" and out[4] == ""
    md = "| a | b | c | d | e |\n|---|---|---|---|---|\n| " + " | ".join(out) + " |\n"
    assert_inert_markdown(md)
    assert len([t for t in markdown_tokens(md) if t.type == "td_open"]) == 5

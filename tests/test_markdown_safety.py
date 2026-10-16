"""Markdown exports (IP tab, URLScan tab) must stay inert when opened outside Seisa (VS Code, Obsidian, GitHub preview).

Everything in a report that came from a remote service or a scanned page is untrusted text: an image would be loaded,
a link would be clickable, raw HTML would be rendered. These tests feed hostile values into every field of both reports
and check the result with a real CommonMark parser (markdown-it-py, present in the dev environment as a dependency of
rich; it is not a requirement of the program)."""
from __future__ import annotations

import pytest

from backend.markdown_report import build_markdown
from backend.markdown_utils import fence, md_cell, md_code, md_text
from backend.models import Identity, IdentityField, IdentityVariant, RiskComponent, RiskScore, ServiceResult
from backend.urlscan_report import build_urlscan_markdown, build_urlscan_summary
from tests.helpers import assert_inert_markdown

markdown_it = pytest.importorskip("markdown_it")

EVIL = (
    "![x](http://evil.example/p.png) <img src=x onerror=alert(1)> [click](http://evil.example/a) "
    "<http://evil.example/b> http://evil.example/c www.evil.example `tick` ``` | pipe\n```\n# head\n- list"
)
ALLOWED_TAGS = frozenset({"details", "summary", "div"})


def parse(md: str):
    return markdown_it.MarkdownIt("commonmark").enable("table").enable("strikethrough").parse(md)


def assert_inert(md: str, allowed_links: tuple[str, ...] = ()):
    """The reports may contain the wrappers Seisa writes itself (details, summary, div) and nothing else."""
    assert_inert_markdown(md, allowed_links, ALLOWED_TAGS)


def hostile_services() -> dict[str, ServiceResult]:
    summary = {
        "comment": EVIL,
        "pulses": [EVIL, {"name": EVIL, "refs": [EVIL]}],
        EVIL: "value",
        "whois_raw": f"Registrar: {EVIL}\nline {EVIL}\nKey: http://evil.example/z",
        "reporter_profile": "https://evil.example/user/1",
    }
    return {
        "abuseipdb": ServiceResult(service="abuseipdb", status="ok", summary=summary, raw={"a": EVIL, "b": ["```", EVIL]}),
        "otx": ServiceResult(service="otx", status="error", error_message=EVIL),
    }


def hostile_score() -> RiskScore:
    comp = RiskComponent(source=EVIL, signal=EVIL, value=EVIL, weight=1, contribution=1, risk=1)
    return RiskScore(level="high", score=90, components=[comp], excluded_sources=[EVIL], sources_used=1, sources_possible=2, notes=[EVIL])


def hostile_identity() -> Identity:
    variants = [IdentityVariant(value=EVIL, sources=["otx"]), IdentityVariant(value=EVIL + "2", sources=["abuseipdb"])]
    field = IdentityField(key="asn", value=EVIL, status="conflict", agree=1, total=2, variants=variants)
    return Identity(fields=[field], notes=[EVIL])


def test_ip_report_is_inert():
    md = build_markdown("203.0.113.9", hostile_score(), hostile_services(), hostile_identity())
    assert_inert(md)


def test_ip_report_keeps_the_known_profile_link_clickable():
    services = {
        "abuseipdb": ServiceResult(
            service="abuseipdb", status="ok", summary={"latest_report": {"reporter_profile": "https://www.abuseipdb.com/user/123"}}
        )
    }
    md = build_markdown("8.8.8.8", hostile_score(), services, None)
    assert "<https://www.abuseipdb.com/user/123>" in md


def test_ip_report_indicator_cannot_break_out_of_the_title():
    md = build_markdown("`x`\n![a](http://evil.example/p.png)", hostile_score(), {}, None)
    assert_inert(md)


def test_raw_json_block_cannot_be_closed_by_its_content():
    raw = {"a": "x\n```\n![i](http://evil.example/p.png)", "b": "~~~"}
    services = {"otx": ServiceResult(service="otx", status="ok", summary={"k": "v"}, raw=raw)}
    md = build_markdown("8.8.8.8", RiskScore(level="low", score=1), services, None)
    fences = [tok for tok in parse(md) if tok.type == "fence"]
    assert len(fences) == 1
    assert "![i](http://evil.example/p.png)" in fences[0].content  # still shown, as inert code
    assert [tok.type for tok in parse(md) if tok.type in ("image", "link_open")] == []


def hostile_urlscan_data():
    return {
        "task": {"url": "http://evil.example/?q=`x`", "time": "2026-10-16"},
        "page": {
            "url": "http://evil.example/final", "title": EVIL, "domain": EVIL, "apexDomain": EVIL, "ip": "8.8.8.8", "asn": "AS1",
            "asnname": EVIL, "country": "XX", "city": EVIL, "ptr": EVIL, "server": EVIL, "status": 200, "mimeType": EVIL,
            "tlsIssuer": EVIL, "tlsValidFrom": EVIL,
        },
        "verdicts": {"overall": {"categories": [EVIL], "brands": [{"name": EVIL, "vertical": [EVIL], "country": [EVIL]}]}},
        "lists": {"ips": ["8.8.8.8"], "domains": [EVIL, "www.evil.example"]},
        "meta": {"processors": {
            "wappa": {"data": [{"app": EVIL, "version": EVIL, "categories": [{"name": EVIL}]}]},
            "geoip": {"data": [{"ip": "8.8.8.8", "country": EVIL}]},
            "asn": {"data": [{"ip": "8.8.8.8", "name": EVIL}]},
        }},
        "data": {"links": [{"href": "http://evil.example/`a`", "text": EVIL}, {"href": EVIL, "text": "t"}], "requests": []},
    }


def hostile_forms():
    return [{"action": EVIL, "method": "post", "fields": [EVIL], "password": True, "external": True, "insecure": True}]


def test_urlscan_report_is_inert():
    uuid = "01234567-89ab-cdef-0123-456789abcdef"
    summary = build_urlscan_summary("http://evil.example/", uuid, hostile_urlscan_data(), hostile_forms())
    md = build_urlscan_markdown(summary, {"raw": EVIL})
    assert_inert(md, allowed_links=(f"https://urlscan.io/result/{uuid}/",))


def test_urlscan_result_link_is_only_trusted_when_it_has_the_expected_shape():
    uuid = "01234567-89ab-cdef-0123-456789abcdef"
    summary = build_urlscan_summary("http://evil.example/", uuid, {}, None)
    summary["result_url"] = "http://evil.example/result/"
    assert_inert(build_urlscan_markdown(summary))


def test_md_code_flattens_and_cannot_be_closed():
    assert md_code("a`b\nc  d") == "`a'b c d`"
    assert md_code(None) == "-"
    assert md_code("   ") == "-"
    assert md_code(0) == "`0`"


def test_md_text_neutralises_markup():
    out = md_text("![x](http://evil.example/p.png) <b>hi</b> [a](b) *x* _y_ a|b `c`")
    assert "<b>" not in out and "`c`" not in out
    assert "\n" not in out
    assert_inert(out)


def test_md_text_leaves_plain_words_readable():
    assert md_text("Registrar: Example Inc., Ltd (EU) snake_case 3 items - ok") == "Registrar: Example Inc., Ltd (EU) snake_case 3 items - ok"


def test_md_text_does_not_start_a_block():
    for text in ("# title", "- item", "1. item", "> quote", "=== x"):
        tokens = [t.type for t in parse(md_text(text))]
        assert tokens == ["paragraph_open", "inline", "paragraph_close"], (text, tokens)


def test_md_cell_cannot_split_a_table_row():
    md = f"| a | b |\n|---|---|\n| {md_cell('x | y')} | {md_cell(EVIL)} |\n"
    rows = [tok for tok in parse(md) if tok.type == "tr_open"]
    assert len(rows) == 2
    cells = [tok for tok in parse(md) if tok.type == "td_open"]
    assert len(cells) == 2
    assert_inert(md)


def test_fence_is_longer_than_any_backtick_run_inside():
    assert fence("plain") == "```"
    assert fence("a ``` b") == "````"
    assert fence("`````x") == "``````"
    md = f"{fence('a ``` b')}\nin ``` here\n{fence('a ``` b')}\n"
    assert [t.type for t in parse(md)] == ["fence"]

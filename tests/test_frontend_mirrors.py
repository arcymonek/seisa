"""Values the frontend repeats from the backend must stay equal to it. The frontend keeps its own copy on purpose: the
History tab draws saved results, which do not carry these values, so they cannot simply come with every answer. A
change on one side only would, for example, colour a score bar differently from the verdict next to it."""
from __future__ import annotations

import re
from pathlib import Path

from backend import markdown_report, report_utils, scoring
from backend.routers import history as history_router
from backend.services import urlscan as urlscan_service

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def js_const(file: str, name: str) -> int:
    match = re.search(rf"^const {name} = (\d+);", (JS / file).read_text(encoding="utf-8"), re.M)
    assert match, f"{name} not found in frontend/js/{file}"
    return int(match.group(1))


def test_risk_thresholds_match_scoring():
    assert js_const("lookup-result.js", "MEDIUM_FROM") == scoring.MEDIUM_FROM
    assert js_const("lookup-result.js", "HIGH_FROM") == scoring.HIGH_FROM
    assert js_const("lookup-result.js", "BENIGN_CAP") == scoring.BENIGN_CAP


def test_report_age_limit_matches_backend():
    assert js_const("report-result.js", "AGE_LIMIT_DAYS") == report_utils.AGE_LIMIT_DAYS


def test_service_names_match_markdown_report():
    text = (JS / "services.js").read_text(encoding="utf-8")
    block = text[text.index("const TITLES = {"):text.index("};", text.index("const TITLES = {"))]
    frontend = dict(re.findall(r'^\s+(\w+): "([^"]+)",', block, re.M))
    # local_heuristics is translated in the frontend ("Seisa (local heuristics)") and only "Seisa" in the report
    backend = {k: v for k, v in markdown_report.SERVICE_TITLES.items() if k != "local_heuristics"}
    assert {k: frontend.get(k) for k in backend} == backend


def js_list(file: str, name: str) -> list[str]:
    match = re.search(rf"^const {name} = \[([^\]]*)\];", (JS / file).read_text(encoding="utf-8"), re.M)
    assert match, f"{name} not found in frontend/js/{file}"
    return re.findall(r'"([^"]*)"', match.group(1))


def test_urlscan_form_options_match_backend():
    assert tuple(js_list("urlscan.js", "VISIBILITIES")) == urlscan_service.VISIBILITIES
    assert tuple(js_list("urlscan.js", "COUNTRIES")) == urlscan_service.COUNTRIES


def test_urlscan_useragent_limit_matches_backend():
    assert js_const("urlscan.js", "MAX_USERAGENT_CHARS") == urlscan_service.MAX_USERAGENT_CHARS


def test_thumbnail_the_frontend_makes_fits_the_backend_limit():
    # the frontend must never produce a thumbnail the backend would then refuse (the History entry would be lost)
    assert js_const("urlscan.js", "THUMB_MAX_CHARS") <= history_router.MAX_THUMBNAIL_CHARS


def test_comment_counter_warns_at_the_backend_limit():
    # report-builder.js turns the character counter to the warning colour at the same length at which the backend
    # (report_utils.truncate_chars) starts cutting the comment
    assert js_const("report-builder.js", "MAX_COMMENT_CHARS") == report_utils.MAX_COMMENT_CHARS
    text = (JS / "report-builder.js").read_text(encoding="utf-8")
    # the counter must use the constant, not a second copy of the number
    assert re.search(r"len >= MAX_COMMENT_CHARS\b", text), "the counter no longer compares with MAX_COMMENT_CHARS"


def test_theme_defaults_match_between_theme_init_and_theme_module():
    # /theme-init.js is a classic script (it must run before the first paint, so it cannot import js/theme.js) and
    # repeats the module's defaults; a difference would flash the wrong colours on every load
    init = (JS.parent / "theme-init.js").read_text(encoding="utf-8")
    module = (JS / "theme.js").read_text(encoding="utf-8")
    assert re.search(r'^const DEFAULT = "light";', module, re.M)
    assert re.search(r'^const RENAMED = \{ dark: "blue" \};', module, re.M)
    assert 'var mode = "light"' in init
    assert 'localStorage.getItem("seisa.theme") || "light"' in init
    assert 'if (mode === "dark") mode = "blue";' in init
    # the dark default of "system" is the same theme on both sides (and the light one is "light")
    assert 'first = base === "dark" ? "sumi-brown" : "light"' in module
    assert '(light ? "light" : "sumi-brown")' in init
    assert 'const STORAGE_KEY = "seisa.theme"' in module

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
    # (report_utils.truncate_chars) starts cutting the comment; the number is still a literal there
    text = (JS / "report-builder.js").read_text(encoding="utf-8")
    match = re.search(r"const len = \$\(\"#rb-comment\"\)\.value\.length;.*?len >= (\d+)", text, re.S)
    assert match, "comment length check not found in frontend/js/report-builder.js"
    assert int(match.group(1)) == report_utils.MAX_COMMENT_CHARS

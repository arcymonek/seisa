"""Size limits on request bodies: absurd bodies are refused by the model before any parsing, while the friendly
"source too large" answer of the Email and AbuseIPDB tabs keeps working for sources between the two ceilings."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.config import MAX_SOURCE_CHARS
from backend.main import app
from backend.routers.abuseipdb_report import RedactRequest, ReportFields
from backend.routers.email_analysis import EmailAnalysisRequest

client = TestClient(app, base_url="http://127.0.0.1")
H = {"X-Seisa-Lang": "en"}


def test_email_request_refuses_more_than_twice_the_source_limit():
    EmailAnalysisRequest(raw_email="a" * (2 * MAX_SOURCE_CHARS))
    with pytest.raises(ValidationError):
        EmailAnalysisRequest(raw_email="a" * (2 * MAX_SOURCE_CHARS + 1))


@pytest.mark.parametrize("path", ["/api/email/find", "/api/email/analyze"])
def test_email_endpoints_answer_422_for_an_absurd_body(path):
    res = client.post(path, json={"raw_email": "a" * (2 * MAX_SOURCE_CHARS + 1), "use_llm": False}, headers=H)
    assert res.status_code == 422
    assert isinstance(res.json()["detail"], list)  # the frontend shows it as text (field: message)


def test_a_source_over_the_limit_still_gets_the_friendly_message():
    res = client.post("/api/email/analyze", json={"raw_email": "a" * (MAX_SOURCE_CHARS + 1), "use_llm": False}, headers=H)
    assert res.status_code == 200
    events = [json.loads(line[6:]) for line in res.text.splitlines() if line.startswith("data: ")]
    assert events[0]["type"] == "error" and str(MAX_SOURCE_CHARS) in events[0]["message"]


def test_report_comment_has_a_ceiling_but_a_long_one_is_still_accepted():
    ReportFields(ip="8.8.8.8", categories=[11], comment="x" * 5000)
    with pytest.raises(ValidationError):
        ReportFields(ip="8.8.8.8", categories=[11], comment="x" * 5001)
    res = client.post("/api/abuseipdb/report/preview", json={"ip": "8.8.8.8", "categories": [11], "comment": "x" * 5001}, headers=H)
    assert res.status_code == 422


@pytest.mark.parametrize("model", [ReportFields, RedactRequest])
def test_own_terms_items_are_limited_to_the_length_of_an_address(model):
    base = {"ip": "8.8.8.8", "categories": [11]} if model is ReportFields else {"comment": "c"}
    model(**base, own_terms=["a" * 242 + "@example.org"])  # 254 characters: the longest address RFC 5321 allows
    with pytest.raises(ValidationError):
        model(**base, own_terms=["a" * 243 + "@example.org"])
    with pytest.raises(ValidationError):
        model(**base, own_terms=["x"] * 21)


def test_abuseipdb_source_over_the_limit_gets_the_friendly_message():
    """The AbuseIPDB tab answers like the Email tab: a readable, translated message instead of a raw validation error."""
    res = client.post("/api/abuseipdb/email/analyze", json={"raw_email": "a" * (MAX_SOURCE_CHARS + 1), "use_llm": False}, headers=H)
    assert res.status_code == 413
    detail = res.json()["detail"]
    assert isinstance(detail, str) and str(MAX_SOURCE_CHARS) in detail and "raw_email" not in detail
    pl = client.post("/api/abuseipdb/email/analyze", json={"raw_email": "a" * (MAX_SOURCE_CHARS + 1), "use_llm": False}, headers={"X-Seisa-Lang": "pl"})
    assert "Źródło jest za duże" in pl.json()["detail"]


def test_abuseipdb_absurd_body_is_still_refused_by_the_model():
    res = client.post("/api/abuseipdb/email/analyze", json={"raw_email": "a" * (2 * MAX_SOURCE_CHARS + 1), "use_llm": False}, headers=H)
    assert res.status_code == 422

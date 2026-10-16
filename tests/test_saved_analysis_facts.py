"""Opening a saved e-mail analysis: the facts are recomputed, and the answer says when they differ from the saved ones.

An analysis saved by an older version carries the facts of that day. Later versions fixed how some facts are read (the
sender address, attachment names, the receiver's verdicts), so the saved ones can be wrong. The file is never changed:
the answer only gains `facts_current` and `facts_changed` (audit 2026-10-15, B14)."""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from backend.analyses import load_analysis, save_analysis
from backend.email_forensics import compute_facts
from backend.main import app
from tests.helpers import load_eml

client = TestClient(app, base_url="http://127.0.0.1")
HEADERS = {"X-Seisa-Lang": "en"}


def save(raw: str, facts: dict) -> str:
    return save_analysis({"raw_email": raw, "facts": facts, "markdown": "VERDICT: legit | CONFIDENCE: high\n\nText.", "subject": "x", "from": "y"})


def fetch(analysis_id: str) -> dict:
    res = client.get(f"/api/email/analyses/{analysis_id}", headers=HEADERS)
    assert res.status_code == 200
    return res.json()


@pytest.fixture
def raw() -> str:
    return load_eml("multihop.eml")


def test_unchanged_facts_add_nothing(raw):
    body = fetch(save(raw, compute_facts(raw)))
    assert "facts_current" not in body and "facts_changed" not in body


def test_a_wrong_sender_address_in_the_saved_facts_is_reported(raw):
    facts = compute_facts(raw)
    saved = copy.deepcopy(facts)
    saved["trust_index"] = 0  # multihop.eml: the sender is a lower hop (index 2), an older version chose the top one
    assert saved["trust_index"] != facts["trust_index"]
    analysis_id = save(raw, saved)
    body = fetch(analysis_id)
    assert body["facts_changed"] is True
    assert body["facts_current"]["trust_index"] == facts["trust_index"]
    assert body["facts"]["trust_index"] == saved["trust_index"]  # the saved facts stay as they were
    assert load_analysis(analysis_id)["facts"]["trust_index"] == saved["trust_index"]  # and so does the file


def test_other_changed_facts_are_reported(raw):
    base = compute_facts(raw)
    for change in (
        lambda f: f["attachments"].append({"filename": "a.pdf.exe", "extension": "exe", "double_extension_as": "pdf", "risky_extension": True}),
        lambda f: f["auth"].append({"header": "Authentication-Results", "results": {"spf": "fail"}, "matches_receiver": True}),
        lambda f: f["flags"].append({"level": "warn", "text": "something"}),
    ):
        saved = copy.deepcopy(base)
        change(saved)
        assert fetch(save(raw, saved)).get("facts_changed") is True


def test_texts_and_info_flags_alone_do_not_count_as_a_change(raw):
    saved = compute_facts(raw)
    saved["flags"].append({"level": "info", "text": "an older wording"})
    saved["overview"]["subject"] = "another wording"
    assert "facts_changed" not in fetch(save(raw, saved))


def test_a_message_that_cannot_be_recomputed_is_still_opened(raw, monkeypatch):
    import backend.routers.email_analysis as router

    def boom(_raw):
        raise RuntimeError("boom")

    monkeypatch.setattr(router, "compute_facts", boom)
    body = fetch(save(raw, compute_facts(raw)))
    assert "facts_changed" not in body and body["facts"]

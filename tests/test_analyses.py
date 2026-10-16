"""backend/analyses.py: the store of saved e-mail analyses (data/analyses/, one JSON file each). Identifiers are
validated so nothing can leave the directory, a damaged file must not break the list or the other analyses, and records
saved by older versions (Polish verdict words, no language field) read as the current codes.

Paths are redirected to a temporary directory (the module copies the constant at import time)."""
from __future__ import annotations

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from backend import analyses
from backend.main import app

client = TestClient(app, base_url="http://127.0.0.1")
H = {"X-Seisa-Lang": "en"}
RAW = "From: a@example.org\nSubject: hi\n\nbody\n"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(analyses, "ANALYSES_DIR", tmp_path / "analyses")
    return tmp_path / "analyses"


def write_raw(store, name, text):
    store.mkdir(parents=True, exist_ok=True)
    (store / name).write_text(text, encoding="utf-8")


@pytest.mark.parametrize("bad", ["", "../etc/passwd", "20261016-100000-abcdefg", "20261016-100000-ABCDEF12", "x", "20261016-100000-abcdef123", "..%2F..", "a/b"])
def test_an_invalid_identifier_is_refused_everywhere(store, bad):
    for call in (analyses.load_analysis, analyses.delete_analysis):
        with pytest.raises(ValueError):
            call(bad)
    with pytest.raises(ValueError):
        analyses.update_analysis(bad, {"x": 1})


def test_save_and_load_roundtrip(store):
    analysis_id = analyses.save_analysis({"raw_email": RAW, "verdict": "phishing", "confidence": "high", "lang": "en"})
    record = analyses.load_analysis(analysis_id)
    assert record["id"] == analysis_id and record["raw_email"] == RAW and record["verdict"] == "phishing"
    assert analyses._ID_RE.match(analysis_id)  # time stamp + 8 hex characters of the source hash
    assert analysis_id.endswith(hashlib.sha256(RAW.encode()).hexdigest()[:8])


def test_an_unknown_identifier_is_none_false_or_file_not_found(store):
    unknown = "20261016-100000-abcdef12"
    assert analyses.load_analysis(unknown) is None
    assert analyses.delete_analysis(unknown) is False
    with pytest.raises(FileNotFoundError):
        analyses.update_analysis(unknown, {"x": 1})


def test_update_changes_only_the_given_fields(store):
    analysis_id = analyses.save_analysis({"raw_email": RAW, "verdict": "spam"})
    analyses.update_analysis(analysis_id, {"truncated": True})
    record = analyses.load_analysis(analysis_id)
    assert record["truncated"] is True and record["verdict"] == "spam" and record["raw_email"] == RAW


def test_delete_removes_the_file(store):
    analysis_id = analyses.save_analysis({"raw_email": RAW})
    assert analyses.delete_analysis(analysis_id) is True
    assert analyses.load_analysis(analysis_id) is None


def test_a_damaged_file_reads_as_missing_and_does_not_break_the_list(store):
    good = analyses.save_analysis({"raw_email": RAW, "subject": "hi", "verdict": "spam"})
    write_raw(store, "20261016-100000-deadbeef.json", "{ this is not json")
    assert analyses.load_analysis("20261016-100000-deadbeef") is None
    assert [item["id"] for item in analyses.list_analyses()] == [good]
    assert analyses.find_by_source(analyses.source_hash(RAW))[0]["id"] == good


@pytest.mark.parametrize("content", ["[]", '"text"', "42", "null"])
def test_a_file_with_valid_json_that_is_not_an_object_does_not_break_anything(store, content):
    good = analyses.save_analysis({"raw_email": RAW, "verdict": "spam"})
    write_raw(store, "20261016-100000-deadbeef.json", content)
    assert analyses.load_analysis("20261016-100000-deadbeef") is None
    assert [item["id"] for item in analyses.list_analyses()] == [good]
    assert [m["id"] for m in analyses.find_by_source(analyses.source_hash(RAW))] == [good]


def test_a_file_that_is_not_utf8_text_is_skipped_too(store):
    good = analyses.save_analysis({"raw_email": RAW, "verdict": "spam"})
    (store / "20261016-100000-deadbeef.json").write_bytes(b"\xff\xfe\x00 not utf-8")
    assert analyses.load_analysis("20261016-100000-deadbeef") is None
    assert [item["id"] for item in analyses.list_analyses()] == [good]


def test_older_records_read_with_the_current_codes_and_a_language(store):
    write_raw(store, "20250101-100000-aaaaaaaa.json", '{"id": "20250101-100000-aaaaaaaa", "raw_email": "x", "verdict": "Oszustwo", "confidence": "WYSOKA"}')
    record = analyses.load_analysis("20250101-100000-aaaaaaaa")
    assert (record["verdict"], record["confidence"], record["lang"]) == ("scam", "high", "pl")
    assert analyses.list_analyses()[0]["verdict"] == "scam"


def test_find_by_source_matches_by_stored_hash_or_by_the_raw_email(store):
    with_hash = analyses.save_analysis({"raw_email": RAW, "source_sha256": analyses.source_hash(RAW), "usage": {"cost": 0.25}})
    write_raw(store, "20250101-100000-aaaaaaaa.json", '{"id": "20250101-100000-aaaaaaaa", "raw_email": ' + json.dumps(RAW) + ', "usage": {"cost": "free"}}')
    analyses.save_analysis({"raw_email": "From: other@example.org\n\nx\n"})
    matches = analyses.find_by_source(analyses.source_hash(RAW))
    assert {m["id"] for m in matches} == {with_hash, "20250101-100000-aaaaaaaa"}
    costs = {m["id"]: m["cost"] for m in matches}
    assert costs[with_hash] == 0.25 and costs["20250101-100000-aaaaaaaa"] is None  # a non-number is not a cost


def test_the_list_is_newest_first_and_has_only_the_listed_fields(store):
    write_raw(store, "20250101-100000-aaaaaaaa.json", '{"id": "old", "raw_email": "x", "secret": "s"}')
    write_raw(store, "20260101-100000-bbbbbbbb.json", '{"id": "new", "raw_email": "x"}')
    items = analyses.list_analyses()
    assert [i["id"] for i in items] == ["new", "old"]
    assert set(items[0]) == {"id", "created_at", "subject", "from", "verdict", "confidence", "truncated", "lang"}


def test_nothing_in_a_missing_directory(store):
    assert analyses.list_analyses() == [] and analyses.find_by_source("0" * 64) == []


def test_api_refuses_a_bad_identifier_with_400_and_an_unknown_one_with_404(store):
    for method in ("get", "delete"):
        assert getattr(client, method)("/api/email/analyses/not-an-id", headers=H).status_code == 400
        assert getattr(client, method)("/api/email/analyses/20261016-100000-abcdef12", headers=H).status_code == 404
    assert client.post("/api/email/analyses/not-an-id/continue", headers=H).status_code == 400

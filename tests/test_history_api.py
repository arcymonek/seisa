"""History endpoints on top of the new storage: same JSON shapes as before, the list is not cut, damage does not give 500,
and the comparison of a lookup with earlier ones reads the index."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import analyses
from backend import history_store as hs
from backend.main import app
from backend.models import HistoryEntry
from backend.routers.lookup import _compare_with_history

client = TestClient(app, base_url="http://127.0.0.1")
H = {"X-Seisa-Lang": "en"}


@pytest.fixture
def store(tmp_path, monkeypatch):
    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setattr(hs, "HISTORY_FILE", root / "history.json")
    monkeypatch.setattr(hs, "HISTORY_DIR", root / "history")
    monkeypatch.setattr(hs, "HISTORY_INDEX_FILE", root / "history" / "index.json")
    monkeypatch.setattr(hs, "HISTORY_ENTRIES_DIR", root / "history" / "entries")
    monkeypatch.setattr(analyses, "ANALYSES_DIR", root / "analyses")
    monkeypatch.setattr("backend.routers.history.load_report_log", list)
    hs._REPORTED.clear()
    return root


def create(label="a.example", **kw):
    res = client.post("/api/history", json={"type": "dmarc", "label": label, "data": {"x": 1}, **kw}, headers=H)
    assert res.status_code == 200
    return res.json()


def test_roundtrip_shapes(store):
    made = create("one", risk_summary="High")
    assert set(made) == {"id", "type", "created_at", "label", "risk_summary", "lang", "pinned", "data"}
    assert client.get(f"/api/history/{made['id']}", headers=H).json() == made
    row = client.get("/api/history", headers=H).json()[0]
    assert set(row) == {"id", "type", "created_at", "label", "risk_summary", "lang", "pinned"}
    assert client.patch(f"/api/history/{made['id']}", json={"pinned": True}, headers=H).json() == {"id": made["id"], "pinned": True}
    assert client.get("/api/history", headers=H).json()[0]["pinned"] is True
    assert client.delete(f"/api/history/{made['id']}", headers=H).json() == {"deleted": made["id"]}
    assert client.get(f"/api/history/{made['id']}", headers=H).status_code == 404
    assert client.delete(f"/api/history/{made['id']}", headers=H).status_code == 404
    assert client.patch("/api/history/nope", json={"pinned": True}, headers=H).status_code == 404


def test_list_shows_every_saved_email_analysis_and_report(store, monkeypatch):
    """Earlier the shared limit of 100 cut e-mail analyses and reports from the view although they were stored."""
    monkeypatch.setattr("backend.routers.history.list_analyses", lambda: [
        {"id": f"20260101-0000{i // 100:02d}-{i % 100:08x}", "created_at": f"2026-02-01T00:{i // 60:02d}:{i % 60:02d}+00:00", "subject": f"s{i}", "from": "f", "lang": "en"}
        for i in range(130)
    ])
    monkeypatch.setattr("backend.routers.history.load_report_log", lambda: [
        {"id": f"r{i}", "success": True, "ip": "8.8.8.8", "categories": [11], "submitted_at": f"2026-03-01T00:{i // 60:02d}:{i % 60:02d}+00:00"}
        for i in range(120)
    ])
    for i in range(3):
        create(f"d{i}")
    items = client.get("/api/history", headers=H).json()
    assert len(items) == 130 + 120 + 3
    assert [i["created_at"] for i in items] == sorted((i["created_at"] for i in items), reverse=True)


def test_damaged_entry_gives_404_not_500(store):
    good, bad = create("good"), create("bad")
    (store / "history" / "entries" / f"{bad['id']}.json").write_text("{broken", encoding="utf-8")
    assert client.get(f"/api/history/{bad['id']}", headers=H).status_code == 404
    assert client.get(f"/api/history/{good['id']}", headers=H).status_code == 200
    assert client.get("/api/history", headers=H).status_code == 200
    assert (store / "history" / "entries" / f"{bad['id']}.json").exists()


def test_row_without_file_gives_404_and_row_is_removed(store):
    made = create("gone")
    (store / "history" / "entries" / f"{made['id']}.json").unlink()
    assert client.get(f"/api/history/{made['id']}", headers=H).status_code == 404
    assert client.get("/api/history", headers=H).json() == []


def test_clear_keeps_pinned(store):
    keep, drop = create("keep"), create("drop")
    client.patch(f"/api/history/{keep['id']}", json={"pinned": True}, headers=H)
    assert client.delete("/api/history", headers=H).json() == {"cleared": True}
    assert [i["id"] for i in client.get("/api/history", headers=H).json()] == [keep["id"]]
    assert client.get(f"/api/history/{drop['id']}", headers=H).status_code == 404


def lookup(label, score, level, risks, queried_at=None, created_at="2026-01-01T00:00:00+00:00"):
    comps = [{"source": s, "risk": r} for s, r in risks.items()]
    data = {"risk_score": {"score": score, "level": level, "components": comps}}
    if queried_at:
        data["queried_at"] = queried_at
    hs.append_history(HistoryEntry(type="lookup", label=label, created_at=created_at, data=data))


def fake_result(score, risks):
    comps = [SimpleNamespace(source=s, risk=r) for s, r in risks.items()]
    return SimpleNamespace(indicator="8.8.8.8", risk_score=SimpleNamespace(score=score, components=comps))


def test_comparison_reads_the_index(store, monkeypatch):
    lookup("8.8.8.8", 20.0, "low", {"otx": 10.0, "vt": 0.0}, queried_at="Q1")
    lookup("9.9.9.9", 99.0, "high", {"otx": 99.0})  # another indicator: ignored
    lookup("8.8.8.8", 30.0, "medium", {"otx": 40.0, "vt": 5.0}, queried_at="Q2")
    monkeypatch.setattr(hs, "_read_entry", lambda _id: pytest.fail("the comparison must not open entry files"))
    cmp = _compare_with_history(fake_result(55.0, {"otx": 70.0, "vt": 6.0, "gn": 30.0}))
    assert cmp.previous.score == 30.0 and cmp.previous.queried_at == "Q2"
    assert cmp.delta == 25.0
    assert [p.queried_at for p in cmp.trend] == ["Q1", "Q2"]  # oldest first
    changes = {c.source: (c.before, c.after) for c in cmp.changes}
    assert changes == {"otx": (40.0, 70.0), "gn": (None, 30.0)}  # vt moved by 1: noise


def test_comparison_without_earlier_scan_is_none(store):
    assert _compare_with_history(fake_result(10.0, {})) is None
    lookup("1.1.1.1", 5.0, "low", {})
    assert _compare_with_history(fake_result(10.0, {})) is None

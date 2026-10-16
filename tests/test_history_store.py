"""History storage (backend/history_store.py): one index + one file per entry in data/history/.

Everything runs in a temporary directory. The migration is tested on SYNTHETIC copies of the old single file; the
real data/ is never touched (tests/conftest.py also fails the run if it changes).
"""
from __future__ import annotations

import json
import os
import stat
import threading
import uuid

import pytest

from backend import history_store as hs
from backend.config import HISTORY_MAX_ENTRIES
from backend.models import HistoryEntry


@pytest.fixture
def store(tmp_path, monkeypatch):
    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setattr(hs, "HISTORY_FILE", root / "history.json")
    monkeypatch.setattr(hs, "HISTORY_DIR", root / "history")
    monkeypatch.setattr(hs, "HISTORY_INDEX_FILE", root / "history" / "index.json")
    monkeypatch.setattr(hs, "HISTORY_ENTRIES_DIR", root / "history" / "entries")
    hs._REPORTED.clear()
    return root


def mk(i: int, type_="lookup", **kw) -> HistoryEntry:
    return HistoryEntry(type=type_, label=f"host{i}.example", created_at=f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00", data={"n": i}, **kw)


def ids(rows) -> list[str]:
    return [r["id"] for r in rows]


def files(root) -> set[str]:
    d = root / "history" / "entries"
    return {p.stem for p in d.glob("*.json")} if d.exists() else set()


def legacy_file(root, entries: list[dict]) -> None:
    (root / "history.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")


def test_append_writes_entry_and_index(store):
    e = mk(1)
    hs.append_history(e)
    assert ids(hs.list_history_rows()) == [e.id]
    assert hs.get_history_entry(e.id).data == {"n": 1}
    assert files(store) == {e.id}


def test_newest_first(store):
    a, b = mk(1), mk(2)
    hs.append_history(a)
    hs.append_history(b)
    assert ids(hs.list_history_rows()) == [b.id, a.id]


def test_retention_keeps_newest_unpinned_and_all_pinned(store):
    pinned = mk(0, pinned=True)
    hs.append_history(pinned)
    made = []
    for i in range(1, HISTORY_MAX_ENTRIES + 6):
        e = mk(i)
        made.append(e)
        hs.append_history(e)
    rows = hs.list_history_rows()
    assert len(rows) == HISTORY_MAX_ENTRIES + 1
    assert pinned.id in ids(rows)
    assert ids(rows)[0] == made[-1].id
    assert made[0].id not in ids(rows)
    assert files(store) == set(ids(rows))  # files of the dropped entries are gone, none left behind


def test_pin_survives_retention_and_clear(store):
    first = mk(1)
    hs.append_history(first)
    assert hs.set_history_pinned(first.id, True)
    assert hs.get_history_entry(first.id).pinned is True
    for i in range(2, HISTORY_MAX_ENTRIES + 5):
        hs.append_history(mk(i))
    assert first.id in ids(hs.list_history_rows())
    hs.clear_history()
    assert ids(hs.list_history_rows()) == [first.id]
    assert files(store) == {first.id}
    assert hs.set_history_pinned(first.id, False)
    assert not hs.set_history_pinned("nope", True)


def test_delete(store):
    a, b = mk(1), mk(2)
    hs.append_history(a)
    hs.append_history(b)
    assert hs.delete_history_entry(a.id)
    assert not hs.delete_history_entry(a.id)
    assert ids(hs.list_history_rows()) == [b.id]
    assert files(store) == {b.id}


def test_risk_summary_is_stored_in_lower_case(store):
    e = mk(1, risk_summary="High")
    hs.append_history(e)
    assert hs.list_history_rows()[0]["risk_summary"] == "high"
    assert hs.get_history_entry(e.id).risk_summary == "high"


def test_unsafe_ids_never_reach_the_filesystem(store):
    hs.append_history(mk(1))
    for bad in ("../index", "..", "a/b", "", "x" * 300, "../../history"):
        assert hs.get_history_entry(bad) is None
        assert not hs.delete_history_entry(bad)
        assert not hs.set_history_pinned(bad, True)
    assert (store / "history" / "index.json").exists()


def test_trend_in_index_for_lookups_only(store):
    look = HistoryEntry(type="lookup", label="x", data={"queried_at": "Q", "risk_score": {"score": 40, "level": "medium", "components": [{"source": "otx", "risk": 12.5}]}})
    other = HistoryEntry(type="dmarc", label="d", data={"risk_score": {"score": 1, "level": "low"}})
    hs.append_history(look)
    hs.append_history(other)
    rows = {r["id"]: r for r in hs.list_history_rows()}
    assert rows[look.id]["trend"] == {"queried_at": "Q", "score": 40, "level": "medium", "risks": {"otx": 12.5}}
    assert "trend" not in rows[other.id]


def test_trend_without_score_has_no_score_keys(store):
    e = HistoryEntry(type="lookup", label="x", data={})
    hs.append_history(e)
    assert hs.list_history_rows()[0]["trend"] == {"queried_at": e.created_at, "risks": {}}


# ---- migration ----------------------------------------------------------------------------------------------

def old_entries(n=130, pinned=5) -> list[dict]:
    types = ["lookup", "dmarc", "urlscan"]
    out = []
    for i in range(n):  # newest first, like the old file
        e = mk(n - i, types[i % 3], pinned=i < pinned)
        out.append(e.model_dump())
    return out


def test_migration_moves_everything_and_keeps_the_old_file(store):
    entries = old_entries()
    legacy_file(store, entries)
    before = (store / "history.json").read_bytes()
    rows = hs.list_history_rows()
    assert ids(rows) == [e["id"] for e in entries]  # same order, nothing dropped (retention applies on the next write)
    assert [r["pinned"] for r in rows].count(True) == 5
    assert files(store) == set(ids(rows))
    assert not (store / "history.json").exists()
    assert (store / "history.json.migrated").read_bytes() == before
    one = entries[7]
    got = hs.get_history_entry(one["id"])
    assert got.model_dump() == one  # id, created_at, pinned and data are kept


def test_migration_is_idempotent(store):
    legacy_file(store, old_entries(10, 1))
    first = hs.list_history_rows()
    second = hs.list_history_rows()
    assert first == second
    assert len(files(store)) == 10


def test_second_legacy_file_does_not_overwrite_the_backup(store):
    legacy_file(store, old_entries(3, 0))
    hs.list_history_rows()
    backup = (store / "history.json.migrated").read_bytes()
    # an old version started again and wrote a new single file; the index exists, so nothing is migrated or overwritten
    legacy_file(store, old_entries(2, 0))
    hs.list_history_rows()
    assert (store / "history.json.migrated").read_bytes() == backup
    assert (store / "history.json").exists()


def test_migration_does_not_overwrite_an_existing_backup(store):
    (store / "history.json.migrated").write_text("older backup", encoding="utf-8")
    legacy_file(store, old_entries(3, 0))
    hs.list_history_rows()
    assert (store / "history.json.migrated").read_text(encoding="utf-8") == "older backup"
    assert (store / "history.json.migrated2").exists()


def test_unreadable_old_file_is_not_migrated_and_not_touched(store):
    (store / "history.json").write_text("{ this is not json", encoding="utf-8")
    assert hs.list_history_rows() == []
    assert (store / "history.json").read_text(encoding="utf-8") == "{ this is not json"
    assert not (store / "history.json.migrated").exists()
    assert not (store / "history").exists()  # nothing was created by a failed migration


def test_migration_skips_invalid_entries_but_keeps_them_in_the_backup(store):
    good = old_entries(3, 0)
    legacy_file(store, [good[0], {"type": "nonsense"}, good[1], {"id": "../evil", "type": "lookup", "label": "x", "data": {}}, good[2]])
    assert ids(hs.list_history_rows()) == [e["id"] for e in good]
    assert "nonsense" in (store / "history.json.migrated").read_text(encoding="utf-8")


def test_migration_drops_repeated_ids(store):
    e = old_entries(1, 0)[0]
    legacy_file(store, [e, e])
    assert ids(hs.list_history_rows()) == [e["id"]]


def test_migration_of_an_empty_old_file(store):
    legacy_file(store, [])
    assert hs.list_history_rows() == []
    assert (store / "history.json.migrated").exists()


def test_migration_files_are_private(store):
    old = os.umask(0o022)
    try:
        legacy_file(store, old_entries(2, 0))
        hs.list_history_rows()
    finally:
        os.umask(old)
    for p in [store / "history" / "index.json", *(store / "history" / "entries").glob("*.json")]:
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert stat.S_IMODE((store / "history").stat().st_mode) == 0o700


# ---- damage -------------------------------------------------------------------------------------------------

def test_unreadable_index_is_rebuilt_from_entry_files(store):
    made = [mk(i) for i in range(1, 6)]
    for e in made:
        hs.append_history(e)
    made[1].pinned = True
    hs.set_history_pinned(made[1].id, True)
    (store / "history" / "index.json").write_text("garbage", encoding="utf-8")
    rows = hs.list_history_rows()
    assert set(ids(rows)) == {e.id for e in made}
    assert ids(rows) == [e.id for e in reversed(made)]  # by created_at, newest first
    assert next(r for r in rows if r["id"] == made[1].id)["pinned"] is True
    assert json.loads((store / "history" / "index.json").read_text(encoding="utf-8"))["entries"]  # repaired on disk


def test_deleted_index_is_rebuilt(store):
    e = mk(1)
    hs.append_history(e)
    (store / "history" / "index.json").unlink()
    assert ids(hs.list_history_rows()) == [e.id]


def test_index_with_a_bad_row_is_rebuilt(store):
    e = mk(1)
    hs.append_history(e)
    (store / "history" / "index.json").write_text(json.dumps({"version": 1, "entries": [{"id": "x"}]}), encoding="utf-8")
    assert ids(hs.list_history_rows()) == [e.id]


def test_entry_file_without_a_row_is_picked_up(store):
    a, b = mk(1), mk(2)
    hs.append_history(a)
    hs._write_entry(b)  # a crash between "entry file" and "index"
    assert set(ids(hs.list_history_rows())) == {a.id, b.id}


def test_damaged_entry_file_is_skipped_and_never_deleted(store):
    good, bad = mk(1), mk(2)
    hs.append_history(good)
    hs.append_history(bad)
    bad_path = store / "history" / "entries" / f"{bad.id}.json"
    bad_path.write_text("{broken", encoding="utf-8")
    (store / "history" / "index.json").write_text("garbage", encoding="utf-8")
    assert ids(hs.list_history_rows()) == [good.id]
    assert bad_path.read_text(encoding="utf-8") == "{broken"
    # later writes and lists leave it alone and do not rebuild again and again
    hs.append_history(mk(3))
    hs.list_history_rows()
    assert bad_path.read_text(encoding="utf-8") == "{broken"


def test_one_damaged_entry_does_not_break_the_list_or_other_entries(store):
    good, bad = mk(1), mk(2)
    hs.append_history(good)
    hs.append_history(bad)
    (store / "history" / "entries" / f"{bad.id}.json").write_text("{broken", encoding="utf-8")
    assert len(hs.list_history_rows()) == 2
    assert hs.get_history_entry(bad.id) is None
    assert hs.get_history_entry(good.id) is not None
    assert not hs.set_history_pinned(bad.id, True)
    assert (store / "history" / "entries" / f"{bad.id}.json").exists()


def test_row_without_a_file_disappears_when_opened(store):
    e = mk(1)
    hs.append_history(e)
    (store / "history" / "entries" / f"{e.id}.json").unlink()
    assert hs.get_history_entry(e.id) is None
    assert hs.list_history_rows() == []


def test_rebuild_does_not_log_entry_content(store, caplog):
    e = HistoryEntry(type="lookup", label="secret-label.example", data={"k": "secret-data"})
    hs.append_history(e)
    (store / "history" / "entries" / f"{e.id}.json").write_text("{broken secret-data", encoding="utf-8")
    (store / "history" / "index.json").write_text("garbage", encoding="utf-8")
    with caplog.at_level("WARNING", logger="app"):
        hs.list_history_rows()
    assert "secret" not in caplog.text


# ---- concurrency --------------------------------------------------------------------------------------------

def test_parallel_writes_lose_nothing(store):
    made = [mk(i) for i in range(40)]
    errors = []

    def work(chunk):
        try:
            for e in chunk:
                hs.append_history(e)
                hs.list_history_rows()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(made[i::8],)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert set(ids(hs.list_history_rows())) == {e.id for e in made}
    assert files(store) == {e.id for e in made}


def test_ids_are_uuids(store):
    e = mk(1)
    assert str(uuid.UUID(e.id)) == e.id

"""Safeguard test: every file Seisa writes into data/ is readable only by its owner (0600), directories with raw
e-mails 0700. The files hold history, raw e-mails and API usage, and the machine may have other users.

Each test runs under the common umask 022 (the default on macOS and most Linux systems): it would leave a plainly
created file at 0644, so a writer that forgets to restrict the mode is caught. Paths are redirected into a temporary
directory (the writers copy the `backend.config` paths at import time, hence the monkeypatching of each module).

The daily logs (logs/*.jsonl) are covered too.
"""
from __future__ import annotations

import logging
import os
import stat

import pytest

from backend import analyses, history_store, storage
from backend.logging_config import DailyJsonlHandler
from backend.models import HistoryEntry


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    old = os.umask(0o022)
    root = tmp_path / "data"
    monkeypatch.setattr(history_store, "HISTORY_FILE", root / "history.json")
    monkeypatch.setattr(history_store, "HISTORY_DIR", root / "history")
    monkeypatch.setattr(history_store, "HISTORY_INDEX_FILE", root / "history" / "index.json")
    monkeypatch.setattr(history_store, "HISTORY_ENTRIES_DIR", root / "history" / "entries")
    monkeypatch.setattr(storage, "REPORT_LOG_FILE", root / "report_log.json")
    monkeypatch.setattr(storage, "VT_USAGE_FILE", root / "vt_usage.json")
    monkeypatch.setattr(storage, "API_USAGE_FILE", root / "api_usage.json")
    monkeypatch.setattr(analyses, "ANALYSES_DIR", root / "analyses")
    yield root
    os.umask(old)


def mode(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_history_files_are_private(data_dir):
    entry = HistoryEntry(type="lookup", label="x", data={})
    history_store.append_history(entry)
    assert mode(data_dir / "history" / "index.json") == 0o600
    assert mode(data_dir / "history" / "entries" / f"{entry.id}.json") == 0o600
    assert mode(data_dir / "history") == 0o700
    assert mode(data_dir / "history" / "entries") == 0o700


def test_report_log_is_private(data_dir):
    storage.append_report_log({"ip": "8.8.8.8", "success": False})
    assert mode(data_dir / "report_log.json") == 0o600


def test_api_usage_is_private(data_dir):
    storage.save_api_usage({"virustotal": {"count": 1}})
    assert mode(data_dir / "api_usage.json") == 0o600


def test_vt_usage_is_private(data_dir):
    storage.save_vt_usage({"date": "2026-10-15", "count": 1})
    assert mode(data_dir / "vt_usage.json") == 0o600


def test_saved_analysis_file_is_private_and_its_directory_closed(data_dir):
    analysis_id = analyses.save_analysis({"raw_email": "From: a@example.org\n\nbody\n"})
    assert mode(data_dir / "analyses" / f"{analysis_id}.json") == 0o600
    assert mode(data_dir / "analyses") == 0o700


def test_analysis_directory_is_closed_even_if_it_already_existed_open(data_dir):
    (data_dir / "analyses").mkdir(parents=True, mode=0o755)
    analyses.save_analysis({"raw_email": "From: a@example.org\n\nbody\n"})
    assert mode(data_dir / "analyses") == 0o700


def _log_one(tmp_path):
    logs = tmp_path / "logs"
    handler = DailyJsonlHandler(logs)
    handler.handle(logging.LogRecord("test", logging.ERROR, __file__, 1, "something failed", None, None))
    return logs, next(logs.glob("*.jsonl"))


def test_daily_log_file_is_private(data_dir, tmp_path):
    _logs, log_file = _log_one(tmp_path)
    assert mode(log_file) == 0o600


def test_logs_directory_is_closed(data_dir, tmp_path):
    logs, _log_file = _log_one(tmp_path)
    assert mode(logs) == 0o700


def test_existing_log_file_and_directory_are_tightened_at_startup(data_dir, tmp_path):
    from backend.logging_config import restrict_modes

    logs = tmp_path / "logs"
    logs.mkdir(mode=0o755)
    old = logs / "2026-10-01.jsonl"
    old.write_text("{}\n")
    old.chmod(0o644)
    restrict_modes(logs)
    assert mode(old) == 0o600
    assert mode(logs) == 0o700


def test_log_file_made_by_an_older_version_is_not_loosened_or_replaced(data_dir, tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir(mode=0o700)
    handler = DailyJsonlHandler(logs)
    handler.handle(logging.LogRecord("test", logging.ERROR, __file__, 1, "first", None, None))
    handler.handle(logging.LogRecord("test", logging.ERROR, __file__, 1, "second", None, None))
    (log_file,) = logs.glob("*.jsonl")
    assert len(log_file.read_text().splitlines()) == 2  # appended, not overwritten
    assert mode(log_file) == 0o600


def test_logs_directory_that_already_exists_open_is_closed_by_the_next_log_line(data_dir, tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir(mode=0o755)
    logs.chmod(0o755)
    handler = DailyJsonlHandler(logs)
    handler.handle(logging.LogRecord("test", logging.ERROR, __file__, 1, "x", None, None))
    assert mode(logs) == 0o700

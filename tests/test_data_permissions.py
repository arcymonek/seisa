"""Safeguard test: every file Seisa writes into data/ is readable only by its owner (0600), directories with raw
e-mails 0700. The files hold history, raw e-mails and API usage, and the machine may have other users.

Each test runs under the common umask 022 (the default on macOS and most Linux systems): it would leave a plainly
created file at 0644, so a writer that forgets to restrict the mode is caught. Paths are redirected into a temporary
directory (the writers copy the `backend.config` paths at import time, hence the monkeypatching of each module).

The daily logs (logs/*.jsonl) are written with the default mode (0644) today: audit 2026-10-15 B17, `xfail(strict=True)`
until stage 5 fixes it.
"""
from __future__ import annotations

import logging
import os
import stat

import pytest

from backend import analyses, storage
from backend.logging_config import DailyJsonlHandler
from backend.models import HistoryEntry


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    old = os.umask(0o022)
    root = tmp_path / "data"
    monkeypatch.setattr(storage, "HISTORY_FILE", root / "history.json")
    monkeypatch.setattr(storage, "REPORT_LOG_FILE", root / "report_log.json")
    monkeypatch.setattr(storage, "VT_USAGE_FILE", root / "vt_usage.json")
    monkeypatch.setattr(storage, "API_USAGE_FILE", root / "api_usage.json")
    monkeypatch.setattr(analyses, "ANALYSES_DIR", root / "analyses")
    yield root
    os.umask(old)


def mode(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_history_file_is_private(data_dir):
    storage.append_history(HistoryEntry(type="lookup", label="x", data={}))
    assert mode(data_dir / "history.json") == 0o600


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


@pytest.mark.xfail(strict=True, reason="audit 2026-10-15 B17: daily log files are created with mode 0644")
def test_daily_log_file_is_private(data_dir, tmp_path):
    _logs, log_file = _log_one(tmp_path)
    assert mode(log_file) == 0o600


@pytest.mark.xfail(strict=True, reason="audit 2026-10-15 B17: the logs directory is created with mode 0755")
def test_logs_directory_is_closed(data_dir, tmp_path):
    logs, _log_file = _log_one(tmp_path)
    assert mode(logs) == 0o700

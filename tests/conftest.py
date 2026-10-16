"""Shared pytest setup.

Two things have to happen before any test module imports the backend:

1. The data/log paths from `backend.config` are pointed at a temporary directory (the same trick as
   `scripts/api_harness.py`), so no test can write into the real `data/` (raw e-mails, 0600) or `logs/`.
   conftest.py is imported before the test modules, and modules that do `from backend.config import X` copy the
   value at import time - that is why the patch is done here, at import time of this file.
2. The UI language is fixed to Polish for every test (the same language as the `dump_facts.py` golden dump).

At the end of the run the real `data/` and `logs/` are compared with their state at the start; any difference
fails the run (`pytest_sessionfinish`), so an isolation leak cannot go unnoticed.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

import backend.config as cfg
from backend.i18n import reset_lang, set_lang

_REAL_DIRS = (cfg.DATA_DIR, cfg.LOGS_DIR)
_TMP = Path(tempfile.mkdtemp(prefix="seisa-tests-"))


def _snapshot(dirs) -> list[tuple[str, int, int]]:
    rows = []
    for base in dirs:
        if base.exists():
            for p in sorted(base.rglob("*")):
                st = p.stat()
                rows.append((str(p), st.st_mtime_ns, st.st_size))
    return rows


_BEFORE = _snapshot(_REAL_DIRS)
REAL_DATA_DIR = cfg.DATA_DIR

cfg.DATA_DIR = _TMP / "data"
cfg.HISTORY_FILE = cfg.DATA_DIR / "history.json"
cfg.HISTORY_DIR = cfg.DATA_DIR / "history"
cfg.HISTORY_INDEX_FILE = cfg.HISTORY_DIR / "index.json"
cfg.HISTORY_ENTRIES_DIR = cfg.HISTORY_DIR / "entries"
cfg.VT_USAGE_FILE = cfg.DATA_DIR / "vt_usage.json"
cfg.REPORT_LOG_FILE = cfg.DATA_DIR / "report_log.json"
cfg.API_USAGE_FILE = cfg.DATA_DIR / "api_usage.json"
cfg.ANALYSES_DIR = cfg.DATA_DIR / "analyses"
cfg.LOGS_DIR = _TMP / "logs"


@pytest.fixture(autouse=True)
def _polish_language():
    token = set_lang("pl")
    yield
    reset_lang(token)


def pytest_collection_modifyitems(items):
    """Mark the end-to-end hook tests (they use the `repo` fixture) as slow, so `pytest -m "not slow"` runs in seconds."""
    for item in items:
        if "repo" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.slow)


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)
    if _snapshot(_REAL_DIRS) != _BEFORE:
        print("\nISOLATION LEAK: the real data/ or logs/ directory changed during the test run")
        session.exitstatus = 1

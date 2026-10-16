from __future__ import annotations

import contextlib
import json
import logging
import os
from datetime import date, datetime, timedelta

from backend.config import LOG_RETENTION_DAYS, LOGS_DIR


def prune_old_logs(directory, today: date, days: int = LOG_RETENTION_DAYS) -> None:
    """Deletes daily log files (YYYY-MM-DD.jsonl) older than `days` days; today counts as day 1. Files with any other
    name are left alone, and a failure on one file never stops the rest."""
    cutoff = today - timedelta(days=days - 1)
    try:
        files = list(directory.glob("*.jsonl"))
    except OSError:
        return
    for path in files:
        try:
            file_date = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if file_date < cutoff:
            with contextlib.suppress(OSError):
                path.unlink()


def restrict_modes(directory) -> None:
    """The logs directory 0700 and the daily files 0600 (the messages can name hosts and addresses; the machine may
    have other users). Fixes files an older version created with the default mode; failures are ignored."""
    with contextlib.suppress(OSError):
        os.chmod(directory, 0o700)
    try:
        files = list(directory.glob("*.jsonl"))
    except OSError:
        return
    for path in files:
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)


class DailyJsonlHandler(logging.Handler):
    """One .jsonl file per day in the logs/ directory. Only WARNING and above gets here at all (the level is set
    on the handler in setup_logging), so normal operation of Seisa leaves no trace on disk."""

    def __init__(self, directory=LOGS_DIR):
        super().__init__()
        self.directory = directory
        self._pruned_on: date | None = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self.directory, 0o700)  # also when the directory already existed with a looser mode
            now = datetime.now().astimezone()
            if self._pruned_on != now.date():  # once per day, also in a Seisa that runs for weeks
                self._pruned_on = now.date()
                prune_old_logs(self.directory, now.date())
            path = self.directory / f"{now.date().isoformat()}.jsonl"
            entry = {
                "time": now.isoformat(),
                "level": record.levelname,
                "service": record.name,
                "message": record.getMessage(),
            }
            # os.open with an explicit mode: the file never exists, even for a moment, readable by other users
            fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            self.handleError(record)


def setup_logging() -> None:
    handler = DailyJsonlHandler()
    restrict_modes(handler.directory)
    prune_old_logs(handler.directory, datetime.now().astimezone().date())
    handler._pruned_on = datetime.now().astimezone().date()
    handler.setLevel(logging.WARNING)
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    root.addHandler(handler)

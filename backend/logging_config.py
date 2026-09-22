from __future__ import annotations

import json
import logging
from datetime import datetime

from backend.config import LOGI_DIR


class DailyJsonlHandler(logging.Handler):
    """Jeden plik .jsonl na dzień w katalogu logi/. Tylko WARNING i wyżej trafia
    tu w ogóle (poziom ustawiany na handlerze w setup_logging), więc zwykła
    praca arcyAnalizer nie zostawia żadnego śladu na dysku."""

    def __init__(self, directory=LOGI_DIR):
        super().__init__()
        self.directory = directory

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            now = datetime.now().astimezone()
            path = self.directory / f"{now.date().isoformat()}.jsonl"
            entry = {
                "time": now.isoformat(),
                "level": record.levelname,
                "service": record.name,
                "message": record.getMessage(),
            }
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            self.handleError(record)


def setup_logging() -> None:
    handler = DailyJsonlHandler()
    handler.setLevel(logging.WARNING)
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    root.addHandler(handler)

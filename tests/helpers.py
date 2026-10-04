"""Small helpers shared by the test modules (kept out of conftest.py, which must only ever be imported by pytest)."""
from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PRIVATE = Path(__file__).resolve().parent / "private"


def load_eml(path: Path | str) -> str:
    """Reads an .eml file and normalises it exactly like the application does for pasted or uploaded sources.
    A relative name is looked up in tests/fixtures."""
    from backend.email_forensics import normalize_source

    p = Path(path)
    if not p.is_absolute():
        p = FIXTURES / p
    return normalize_source(p.read_text(encoding="utf-8"))

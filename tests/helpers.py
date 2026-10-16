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


def markdown_tokens(md: str):
    """Every token of a CommonMark parse (markdown-it-py, a dev-only dependency), inline children included."""
    import markdown_it

    def walk(tokens):
        for tok in tokens:
            yield tok
            if tok.children:
                yield from walk(tok.children)

    return list(walk(markdown_it.MarkdownIt("commonmark").enable("table").enable("strikethrough").parse(md)))


def assert_inert_markdown(md: str, allowed_links: tuple[str, ...] = (), allowed_tags: frozenset[str] = frozenset()):
    """No image, no link except the listed ones, no raw HTML except the listed tags, and no web address left in the
    visible text. Code (spans and fences) is not visible text: it is shown as it is and cannot load or link anything."""
    links = []
    tokens = markdown_tokens(md)
    for tok in tokens:
        assert tok.type != "image", f"image survived: {tok.attrs}"
        if tok.type == "link_open":
            links.append(tok.attrs.get("href"))
        if tok.type in ("html_block", "html_inline"):
            tag = tok.content.strip().lstrip("<").lstrip("/").split(">")[0].split()[0] if tok.content.strip() else ""
            assert tag in allowed_tags, f"raw HTML survived: {tok.content!r}"
    assert sorted(links) == sorted(allowed_links), links
    visible = "".join(tok.content for tok in tokens if tok.type == "text").lower()
    assert "http://" not in visible and "https://" not in visible and "www." not in visible

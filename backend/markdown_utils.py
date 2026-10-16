"""Helpers that keep untrusted text inert inside the Markdown reports (IP and URLScan tabs).

A saved .md file is opened outside Seisa (editors, GitHub preview), where an image is loaded, a link is clickable and raw
HTML is rendered. Whatever came from a remote service or a scanned page therefore goes through one of these functions.
The same rules exist in `frontend/js/markdown-export.js` for the exports built in the browser; `tests/test_markdown_safety.py`
checks that the two stay equal.

- `md_code`: a value shown as code (one line, cannot be closed from inside). For addresses, names and identifiers.
- `md_text`: a value shown as text in a paragraph or list item: markup characters are escaped and web addresses become
  defanged code (`hxxp://evil[.]example`), so nothing is clickable or loaded.
- `md_cell`: the same for a table cell.
- `fence`: a code fence longer than any run of backticks in the content, so the content cannot close it.
"""
from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")
# Web addresses, with or without scheme; the trailing punctuation of a sentence is not part of the address.
_URL = re.compile(r"\b(?:https?|ftp)://[^\s<>\"'`]+|\bwww\.[^\s<>\"'`]+", re.IGNORECASE)
_TRAILING = re.compile(r"[.,;:!?)\]}]+$")
# Characters that start markup anywhere in a line; an underscore only counts at a word edge (snake_case is left alone).
_SPECIAL = re.compile(r"[\\*<>|\[\]]|(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])")
_BLOCK_START = re.compile(r"^(?:[-+](?=\s)|#{1,6}(?=\s|$)|=+(?=\s|$))")
_NUMBER_START = re.compile(r"^(\d{1,9})([.)])(?=\s)")


def flat(value) -> str:
    """The value as one line of text: any run of whitespace (line breaks included) becomes one space."""
    return _WHITESPACE.sub(" ", "" if value is None else str(value)).strip()


def defang_url(url: str) -> str:
    """hxxps://evil[.]example - readable, but not a link in any viewer. Also safe inside a code span and a table cell."""
    out = re.sub(r"^http", "hxxp", url, flags=re.IGNORECASE)
    out = re.sub(r"^ftp", "fxp", out, flags=re.IGNORECASE)
    return out.replace(".", "[.]").replace("`", "'").replace("|", "%7C")


def md_code(value) -> str:
    """One line in a code span. A backtick inside the value becomes an apostrophe, so the span cannot end early."""
    text = flat(value).replace("`", "'")
    return f"`{text}`" if text else "-"


def _inline(text: str) -> str:
    """Escapes markup and turns every web address into a defanged code span (no trimming, no line handling)."""
    out: list[str] = []
    last = 0
    for match in _URL.finditer(text):
        url = _TRAILING.sub("", match.group(0))
        out.append(_SPECIAL.sub(lambda m: "\\" + m.group(0), text[last:match.start()]).replace("`", "'"))
        out.append(f"`{defang_url(url)}`")
        last = match.start() + len(url)
    out.append(_SPECIAL.sub(lambda m: "\\" + m.group(0), text[last:]).replace("`", "'"))
    return "".join(out)


def md_text(value) -> str:
    """Untrusted text as one line of Markdown text that cannot start a block, load an image or become a link."""
    out = _inline(flat(value))
    out = _BLOCK_START.sub(lambda m: "\\" + m.group(0), out)
    return _NUMBER_START.sub(r"\1\\\2", out)


def md_cell(value) -> str:
    """Untrusted text in a table cell (the pipe is escaped by `md_text`)."""
    return md_text(value)


def fence(text: str) -> str:
    """A code fence that the content cannot close: longer than the longest run of backticks inside (at least 3)."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)

"""One place that turns pasted text into a parsed message and describes its parts; shared by the Email and
AbuseIPDB tabs.

The two tabs stay separate tools (see CLAUDE.md), but they used to carry their own copies of these small building
blocks, and the copies drifted apart: one tab repaired headers that lost their indentation, the other did not; one
decoded an encoded attachment name, the other did not. Everything here is a pure function of the message text, with
no network access and no dependence on a tab's wording. This module imports nothing from the rest of the project, so
every other module may import it.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from email import message_from_string
from email.header import decode_header, make_header
from email.message import Message

_HEADER_START_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:")
_INDENTED_HEADER_START_RE = re.compile(r"^\s+[A-Za-z][A-Za-z0-9-]*:(\s|$)")

MAX_DECODE_CHARS = 4000  # the standard-library decoder of encoded words is quadratic on thousands of them
MAX_FILENAME_CHARS = 120  # characters of an attachment name that are kept for display


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def normalize_source(raw: str) -> str:
    """Unifies the source pasted/loaded from a file: BOM, line endings, mbox envelope ("From ..."), leading
    empty lines. Does not change anything inside the headers or the body."""
    text = raw.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    text = text.lstrip("\n")
    lines = text.split("\n", 1)
    if lines and re.match(r"^From \S+", lines[0]) and ":" not in lines[0].split(" ", 1)[0]:
        text = lines[1] if len(lines) > 1 else ""
    return text.lstrip("\n")


def refold_headers(raw_email: str) -> str:
    """Many mail clients/browsers lose the indentation of continuation lines (RFC 5322 folding) of long headers
    when you "show the source" - especially multi-line `Received`. For the stdlib `email` parser a line without
    a leading space that does not look like `Header-Name:` ends the header block, so a pasted e-mail like that
    can stop parsing at the very first header. We restore the missing indentation where it is unambiguous (a
    non-empty line inside the header block that starts neither with `Name:` nor with whitespace). The reverse
    also happens - the next header is wrongly indented (e.g. by a paste tool that keeps nesting) - such a line
    is recognised by the `Name:` pattern despite the indentation and un-indented, so that the stdlib treats it
    as a new header and not as a continuation."""
    lines = raw_email.split("\n")
    out: list[str] = []
    in_headers = True
    for line in lines:
        if in_headers and line.strip() == "":
            in_headers = False
            out.append(line)
            continue
        if in_headers and line.startswith((" ", "\t")):
            indented_header = _INDENTED_HEADER_START_RE.match(line)
            out.append(line.lstrip() if indented_header else line)
        elif in_headers and out and not _HEADER_START_RE.match(line):
            out.append(" " + line)
        else:
            out.append(line)
    return "\n".join(out)


def load_message(raw: str) -> Message:
    """The single way both tabs read a pasted e-mail: normalise the text (BOM, line endings, mbox envelope, leading
    blank lines), repair headers that lost their indentation, then parse. Normalising twice is harmless, so callers
    that already normalised the text may call this directly. The text SHOWN to the user is not changed by this."""
    return message_from_string(refold_headers(normalize_source(raw)))


def unfold(value: str) -> str:
    """Collapses an RFC 5322 folded header value's embedded newline+indentation into a single space, so a regex
    looking for a value that happens to sit right at a fold boundary is not cut short."""
    return re.sub(r"\n[ \t]+", " ", str(value)).strip()


def decode_words(value: str) -> str:
    """RFC 2047 encoded words (`=?utf-8?b?...?=`) decoded to text; the input is cut at MAX_DECODE_CHARS and an
    undecodable value is returned unchanged."""
    try:
        return str(make_header(decode_header(value[:MAX_DECODE_CHARS])))
    except Exception:
        return value


# ---------------------------------------------------------------------------
# attachments
# ---------------------------------------------------------------------------

# Extensions that make a file dangerous to open (programs, scripts, shortcuts, disk images, macro documents, web
# pages, archives that hide any of those).
RISKY_EXTENSIONS = {
    "exe", "scr", "bat", "cmd", "com", "js", "jse", "vbs", "vbe", "wsf", "jar", "lnk", "iso", "img", "hta", "ps1",
    "msi", "dll", "docm", "xlsm", "pptm", "html", "htm", "svg", "one", "zip", "rar", "7z", "ace",
}
# The classic double-extension trick ("invoice.pdf.exe"): the second-to-last segment looks like a harmless document,
# picture or archive, so the real, last extension is easy to overlook.
INNOCENT_LOOKING_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", "jpg", "jpeg", "png", "gif", "bmp", "zip", "rar",
}


def _without_invisible_characters(name: str) -> str:
    """Control and formatting characters (such as U+202E, "right-to-left override") change how a name is displayed
    but not which file it is, so they are dropped before the extension is read."""
    return "".join(ch for ch in name if unicodedata.category(ch) not in ("Cc", "Cf"))


def attachment_info(part: Message) -> dict | None:
    """The one description of an attachment that both tabs build their own report from, or None when the part has
    no file name. The name is decoded (RFC 2231 by the stdlib, RFC 2047 here) BEFORE the extension is read; the
    extension is the last segment of the decoded name with invisible characters and trailing dots/spaces removed
    (Windows ignores those when the file is saved), in lower case.

    Keys: filename (decoded, at most MAX_FILENAME_CHARS), extension, double_extension_as, risky_extension, size,
    sha256 (None for an empty part), content_type."""
    raw_name = part.get_filename()
    if not raw_name:
        return None
    oversized = len(raw_name) > MAX_DECODE_CHARS
    # a name this long cannot be decoded reliably, and nobody sends one on purpose to be useful: treat it as risky
    name = raw_name if oversized or "=?" not in raw_name else decode_words(raw_name)
    try:
        payload = part.get_payload(decode=True) or b""
    except Exception:
        payload = b""
    segments = _without_invisible_characters(name).rstrip(" .").split(".")
    extension = segments[-1].lower() if len(segments) > 1 else ""
    second_last = segments[-2].lower() if len(segments) > 2 else ""
    return {
        "filename": name[:MAX_FILENAME_CHARS],
        "extension": extension,
        "double_extension_as": second_last if second_last in INNOCENT_LOOKING_EXTENSIONS and second_last != extension else None,
        "risky_extension": oversized or extension in RISKY_EXTENSIONS,
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest() if payload else None,
        "content_type": part.get_content_type(),
    }

#!/usr/bin/env python3
"""Checks that the documentation is complete, well-formed and agrees with the code (standard library only).

Usage: python3 scripts/check_docs.py [--external]

The documentation is English first: a file in the project root or in docs/, with its Polish twin in docs/pl/ under the
same name (README.md has README.pl.md next to it). AGENTS.md and CHANGELOG.md have no twin. The lists below
(DOC_PAIRS, REQUIRED_DOCS, PENDING) are the single source of that layout; scripts/hooks/pre-commit reads DOC_PAIRS too.

Errors (exit code 1):
   1. every pair in DOC_PAIRS: both files exist (or neither, while the file is PENDING); the same headings of levels
      1-4 in the same order and levels, and the same number of code blocks, tables, table rows and images
   2. every *.md in the root, docs/ and docs/pl/ is part of a pair or a known exception
   3. relative links, #anchors and src= of images resolve, in every Markdown file of the repository
   4. every image has a non-empty alt text; once nothing is PENDING, every image in docs/images/ is used somewhere
   5. the routes of the FastAPI app are exactly the `METHOD /path` entries of docs/API.md (and its twin)
   6. the fields of `Settings` (backend/config.py) are exactly the keys in .env.example and in the key table of both READMEs
   7. every tab (`data-tab` in frontend/index.html) has its section in docs/USER_GUIDE.md and a row in the tab table of
      both READMEs
   8. every program and script file (backend/**/*.py, frontend/js/*.js, scripts/**) is named in docs/ARCHITECTURE.md
      or docs/DEVELOPMENT.md
   9. FACTS: a number taken from the code (a limit, a retention time) appears in the file that is the home of that fact
  10. no version number ("Seisa 1.2.3") in docs/, no long dash (U+2014), the language switch line on top of every
      file that has a twin
  11. e-mail addresses in the documentation and in frontend/js/about.js only from ALLOWED_EMAILS (or reserved
      example domains)
  12. every file of REQUIRED_DOCS that is not PENDING exists
Warnings (never fail the run):
  13. a paragraph longer than 6 lines or 90 words
  14. a file longer than 150 lines without a table of contents
Manual only (never in CI or the hook):
  15. --external: every external https:// link answers (needs the network)

Rules that read the CONTENT of a document (5-9, 13, 14) skip a file while it is on the PENDING list: a session that
writes a file removes it from PENDING in the same commit, and from then on the file is checked in full. How to add a
document, a tab, a route or a fact: docs/DEVELOPMENT.md.

The code is read with `ast` and regular expressions, never imported: the hook runs this file with the system Python,
which may not have the project's dependencies. tests/test_check_docs.py compares this static view with the real app.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent

# --- the layout of the documentation -----------------------------------------------------------------------------

_DOCS_DIR_FILES = ("USER_GUIDE", "OPERATIONS", "PRIVACY", "COMPLIANCE", "ARCHITECTURE", "API", "DEVELOPMENT")

# (English file, Polish twin). The hook's language-pair rule uses this list as well.
DOC_PAIRS: tuple[tuple[str, str], ...] = (
    ("README.md", "README.pl.md"),
    ("CONTRIBUTING.md", "docs/pl/CONTRIBUTING.md"),
    ("SECURITY.md", "docs/pl/SECURITY.md"),
    ("CODE_OF_CONDUCT.md", "docs/pl/CODE_OF_CONDUCT.md"),
    *((f"docs/{name}.md", f"docs/pl/{name}.md") for name in _DOCS_DIR_FILES),
)
# Markdown files in the root, docs/ and docs/pl/ that have no twin on purpose.
UNPAIRED = ("AGENTS.md", "CHANGELOG.md")
REQUIRED_DOCS: tuple[str, ...] = (*(f for pair in DOC_PAIRS for f in pair), "AGENTS.md", "CHANGELOG.md")

# Files still being written (the documentation rewrite). A missing PENDING file is not an error, and the rules that
# read a document's content skip it. The session that writes a file removes it here in the same commit.
PENDING: frozenset[str] = frozenset({
    *(f"docs/{name}.md" for name in _DOCS_DIR_FILES if name not in ("ARCHITECTURE", "API", "PRIVACY", "COMPLIANCE", "USER_GUIDE", "OPERATIONS", "DEVELOPMENT")),
    *(f"docs/pl/{name}.md" for name in _DOCS_DIR_FILES if name not in ("ARCHITECTURE", "API", "PRIVACY", "COMPLIANCE", "USER_GUIDE", "OPERATIONS", "DEVELOPMENT")),
})

API_DOC = "docs/API.md"
USER_GUIDE = "docs/USER_GUIDE.md"
MODULE_DOCS = ("docs/ARCHITECTURE.md", "docs/DEVELOPMENT.md")
READMES = (("README.md", "en"), ("README.pl.md", "pl"))

# Rule 7: the English heading of each tab's section in USER_GUIDE.md (a leading "5. " is ignored). The Polish twin
# has the same headings in the same order (rule 1), so its section is found at the same position.
USER_GUIDE_SECTIONS = {
    "lookup": "IP tab",
    "urlscan": "URLScan tab",
    "dmarc": "DMARC tab",
    "email": "Email tab",
    "report": "AbuseIPDB tab",
    "history": "History tab",
    "logs": "Logs tab",
    "about": "Info tab",
}

# Rule 8: files that need no mention (empty package markers).
MODULE_EXCEPTIONS = frozenset({"backend/__init__.py", "backend/routers/__init__.py", "backend/services/__init__.py"})


class Fact(NamedTuple):
    """A number from the code that the documentation states. `pattern` finds it in `source` (group 1); `units` are
    word stems (English and Polish) of which one must follow a small number within the same sentence, so that a lone
    "4" somewhere in the text does not count."""
    label: str
    source: str
    pattern: str
    homes: tuple[str, ...]
    units: tuple[str, ...] = ()


# Rule 9. `homes` are English files; the Polish twin must state the same number.
FACTS: tuple[Fact, ...] = (
    Fact("History size", "backend/config.py", r"^HISTORY_MAX_ENTRIES = ([\d_]+)", ("docs/OPERATIONS.md",),
         ("entr", "item", "check", "unpinned", "wpis", "pozycj", "nieprzypi")),
    Fact("Log retention", "backend/config.py", r"^LOG_RETENTION_DAYS = ([\d_]+)", ("docs/OPERATIONS.md", "docs/PRIVACY.md"),
         ("day", "dni", "dzie")),
    Fact("E-mail source limit", "backend/config.py", r"^MAX_SOURCE_CHARS = ([\d_]+)", ("docs/OPERATIONS.md", "docs/API.md")),
    Fact("Characters of the source sent to the model", "backend/email_forensics.py", r"^MAX_LLM_SOURCE_CHARS = ([\d_]+)",
         ("docs/PRIVACY.md",)),
    Fact("Characters of the AbuseIPDB policy sent to the model", "backend/services/llm_analyzer.py",
         r"ABUSEIPDB_POLICY_FILE\.read_text\([^)]*\)\[:([\d_]+)\]", ("docs/COMPLIANCE.md",)),
    Fact("AbuseIPDB comment limit", "backend/report_utils.py", r"^MAX_COMMENT_CHARS = ([\d_]+)", ("docs/COMPLIANCE.md",),
         ("char", "znak")),
    Fact("Maximum age of a reported attack", "backend/report_utils.py", r"^AGE_LIMIT_DAYS = ([\d_]+)", ("docs/COMPLIANCE.md",),
         ("day", "dni", "dzie")),
    Fact("Pause between reports of one IP", "backend/routers/abuseipdb_report.py", r"^REPORT_COOLDOWN_MINUTES = ([\d_]+)",
         ("docs/COMPLIANCE.md",), ("min",)),
    Fact("VirusTotal requests per minute", "backend/ratelimit.py", r"^VT_PER_MINUTE = ([\d_]+)", ("docs/OPERATIONS.md",),
         ("min",)),
    Fact("VirusTotal requests per day", "backend/ratelimit.py", r"^VT_PER_DAY = ([\d_]+)", ("docs/OPERATIONS.md",),
         ("day", "dzie", "dob", "dni")),
    Fact("OpenRouter silence limit", "backend/services/llm_analyzer.py",
         r"^OPENROUTER_TIMEOUT = httpx\.Timeout\([^)]*read=([\d_]+)(?:\.0)?\)", ("docs/OPERATIONS.md",),
         ("s", "sec", "sek")),
)

# Rule 11. Addresses on reserved example domains (RFC 2606, RFC 6761) are allowed in examples.
ALLOWED_EMAILS = frozenset({"contact@seisa.eu"})
EXAMPLE_EMAIL_DOMAIN = re.compile(r"(?:^|\.)(?:example(?:\.(?:org|com|net))?|test|invalid|localhost)$")
EMAIL_SOURCES = ("frontend/js/about.js",)

# Rule 3: directories never scanned for Markdown when there is no git to ask (an exported index has none of them).
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "data", "logs", "reports", "__pycache__", ".pytest_cache",
              ".ruff_cache", ".mypy_cache"}

EM_DASH = "\u2014"
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
TOC_MIN_LINES = 150
PARAGRAPH_MAX_LINES = 6
PARAGRAPH_MAX_WORDS = 90


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []


# --- reading Markdown --------------------------------------------------------------------------------------------

def read(root: Path, rel: str) -> str | None:
    p = root / rel
    return p.read_text(encoding="utf-8") if p.is_file() else None


def strip_code(text: str) -> list[tuple[int, str]]:
    """(line number, text) of the lines outside fenced code blocks."""
    out, fence = [], None
    for n, line in enumerate(text.splitlines(), 1):
        m = re.match(r"\s*(```|~~~)", line)
        if m:
            fence = None if fence == m[1] else (fence or m[1])
            continue
        if fence is None:
            out.append((n, line))
    return out


def headings(text: str) -> list[tuple[int, str]]:
    return [(len(m[1]), m[2].strip()) for _, line in strip_code(text) if (m := re.match(r"(#{1,6})\s+(.*?)\s*#*\s*$", line))]


def code_blocks(text: str) -> int:
    return sum(1 for line in text.splitlines() if re.match(r"\s*(```|~~~)", line)) // 2


def table_rows(text: str) -> list[list[str]]:
    """Tables as lists of row lines (the separator line |---| not counted)."""
    tables, current = [], []
    for _, line in [*strip_code(text), (0, "")]:
        if line.lstrip().startswith("|"):
            if not re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", line):
                current.append(line)
        elif current:
            tables.append(current)
            current = []
    return tables


MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
HTML_IMAGE = re.compile(r"<img\b[^>]*>", re.I)


def images(text: str) -> list[tuple[int, str, str]]:
    """(line, alt, src) of every image, Markdown or <img>."""
    out = []
    for n, line in strip_code(text):
        line = re.sub(r"`[^`]*`", "", line)
        out += [(n, m[1], m[2]) for m in MD_IMAGE.finditer(line)]
        for tag in HTML_IMAGE.findall(line):
            src = re.search(r"""\bsrc=["']([^"']*)["']""", tag)
            alt = re.search(r"""\balt=["']([^"']*)["']""", tag)
            out.append((n, alt[1] if alt else "", src[1] if src else ""))
    return out


def slugify(title: str) -> str:
    """GitHub's anchor rule: lower case, drop punctuation (letters with diacritics, digits, '-' and '_' stay), spaces to '-'."""
    title = re.sub(r"`|\*|<[^>]+>|\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) or "", title)
    return re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")


def anchors(text: str) -> set[str]:
    seen: dict[str, int] = {}
    res = set()
    for _, title in headings(text):
        slug = slugify(title)
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        res.add(slug if n == 0 else f"{slug}-{n}")
    res.update(re.findall(r"""<a\s+(?:name|id)=["']([^"']+)["']""", text))
    return res


def markdown_files(root: Path) -> list[str]:
    """Every Markdown file git tracks (a new document counts once it is added with `git add`; local, untracked notes
    never do). Without git, a directory walk: the hook runs on an export of the index, which holds exactly those files."""
    if (root / ".git").exists():
        p = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "-z", "--cached", "--", "*.md"],
                           cwd=root, capture_output=True, text=True)
        if p.returncode == 0:
            return sorted({f for f in p.stdout.split("\0") if f and (root / f).is_file()})
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not (Path(dirpath) / d).relative_to(root).as_posix().startswith("tests/private")]
        out += [(Path(dirpath) / f).relative_to(root).as_posix() for f in filenames if f.endswith(".md")]
    return sorted(out)


def is_content_checked(rel: str) -> bool:
    return rel not in PENDING


# --- rules -------------------------------------------------------------------------------------------------------

def check_pairs(root: Path, rep: Report) -> None:
    """Rule 1."""
    for en, pl in DOC_PAIRS:
        te, tp = read(root, en), read(root, pl)
        if te is None and tp is None:
            continue
        if te is None or tp is None:
            have, missing = (pl, en) if te is None else (en, pl)
            rep.errors.append(f"{missing} is missing ({have} exists): a document and its twin come together")
            continue
        he = [lvl for lvl, _ in headings(te) if lvl <= 4]
        hp = [lvl for lvl, _ in headings(tp) if lvl <= 4]
        if he != hp:
            rep.errors.append(f"{en} and {pl} have a different heading structure (levels {''.join(map(str, he))} vs {''.join(map(str, hp))})")
        for what, count in (("code blocks", code_blocks), ("tables", lambda t: len(table_rows(t))),
                            ("table rows", lambda t: sum(map(len, table_rows(t)))), ("images", lambda t: len(images(t)))):
            a, b = count(te), count(tp)
            if a != b:
                rep.errors.append(f"{en} and {pl} have a different number of {what} ({a} vs {b})")


def check_unpaired(root: Path, rep: Report, md_files: list[str]) -> None:
    """Rule 2."""
    known = {f for pair in DOC_PAIRS for f in pair} | set(UNPAIRED)
    for rel in md_files:
        if Path(rel).parent.as_posix() in (".", "docs", "docs/pl") and rel not in known:
            rep.errors.append(f"{rel} is not in DOC_PAIRS (scripts/check_docs.py): a document needs its twin in the other language")


def check_links(root: Path, rep: Report, md_files: list[str]) -> None:
    """Rule 3."""
    link = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
    src = re.compile(r"""\b(?:src|href)=["']([^"']+)["']""")
    cache: dict[Path, set[str]] = {}
    for rel in md_files:
        f = root / rel
        for n, line in strip_code(f.read_text(encoding="utf-8")):
            line = re.sub(r"`[^`]*`", "", line)
            for target in link.findall(line) + src.findall(line):
                if re.match(r"[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("//"):
                    continue
                path_part, _, frag = target.partition("#")
                dest = (f.parent / unquote(path_part)).resolve() if path_part else f.resolve()
                if not dest.exists():
                    rep.errors.append(f"{rel}:{n}: dead link {target}")
                    continue
                if frag and dest.suffix == ".md":
                    if dest not in cache:
                        cache[dest] = anchors(dest.read_text(encoding="utf-8"))
                    if unquote(frag).lower() not in cache[dest]:
                        rep.errors.append(f"{rel}:{n}: dead anchor {target}")


def check_images(root: Path, rep: Report, md_files: list[str]) -> None:
    """Rule 4."""
    used: set[Path] = set()
    for rel in md_files:
        f = root / rel
        for n, alt, target in images(f.read_text(encoding="utf-8")):
            if not alt.strip():
                rep.errors.append(f"{rel}:{n}: image {target} has no alt text (describe what it shows)")
            if target and not re.match(r"[a-z][a-z0-9+.-]*:", target, re.I):
                used.add((f.parent / unquote(target.partition("#")[0])).resolve())
    img_dir = root / "docs" / "images"
    if not img_dir.is_dir():
        return
    for img in sorted(img_dir.iterdir()):
        if img.is_file() and img.resolve() not in used:
            msg = f"docs/images/{img.name} is not used by any document"
            (rep.warnings if PENDING else rep.errors).append(msg + (" (an error once PENDING is empty)" if PENDING else ""))


def _call_name(node: ast.AST) -> str:
    return node.attr if isinstance(node, ast.Attribute) else node.id if isinstance(node, ast.Name) else ""


def _str_kw(call: ast.Call, name: str, default: str | None = None) -> str | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value.value if isinstance(kw.value, ast.Constant) else None
    return default


def app_routes(root: Path) -> set[tuple[str, str]]:
    """(METHOD, path) of every route the app serves, read from backend/main.py and backend/routers/*.py."""
    main = ast.parse((root / "backend" / "main.py").read_text(encoding="utf-8"))
    routes: set[tuple[str, str]] = set()
    for node in ast.walk(main):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name == "FastAPI":
            for kw, default in (("openapi_url", "/openapi.json"), ("docs_url", "/docs"), ("redoc_url", "/redoc")):
                given = [k for k in node.keywords if k.arg == kw]
                value = given[0].value.value if given and isinstance(given[0].value, ast.Constant) else (None if given else default)
                if value:
                    routes.add(("GET", value))
                    if kw == "docs_url":
                        routes.add(("GET", value + "/oauth2-redirect"))
        elif name == "include_router" and node.args and isinstance(node.args[0], ast.Attribute):
            module = _call_name(node.args[0].value)
            prefix = _str_kw(node, "prefix", "") or ""
            src = root / "backend" / "routers" / f"{module}.py"
            tree = ast.parse(src.read_text(encoding="utf-8"))
            router_prefix = ""
            for n in ast.walk(tree):
                if isinstance(n, ast.Call) and _call_name(n.func) == "APIRouter":
                    router_prefix = _str_kw(n, "prefix", "") or ""
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for dec in fn.decorator_list:
                    if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                            and dec.func.attr.upper() in HTTP_METHODS and _call_name(dec.func.value) == "router"
                            and dec.args and isinstance(dec.args[0], ast.Constant)):
                        routes.add((dec.func.attr.upper(), prefix + router_prefix + dec.args[0].value))
    return routes


def documented_routes(text: str) -> set[tuple[str, str]]:
    pattern = re.compile(rf"\b({'|'.join(HTTP_METHODS)}) (/[A-Za-z0-9_./{{}}-]*)")
    return {(m[1], m[2]) for m in pattern.finditer(text)}


def check_api(root: Path, rep: Report) -> None:
    """Rule 5."""
    routes = app_routes(root)
    for rel in (API_DOC, _twin(API_DOC)):
        text = read(root, rel)
        if text is None or not is_content_checked(rel):
            continue
        documented = documented_routes(text)
        for method, path in sorted(routes - documented, key=lambda r: (r[1], r[0])):
            rep.errors.append(f"{rel}: route {method} {path} is not documented")
        for method, path in sorted(documented - routes, key=lambda r: (r[1], r[0])):
            rep.errors.append(f"{rel}: documents {method} {path}, which the app does not have")


def settings_keys(root: Path) -> set[str]:
    tree = ast.parse((root / "backend" / "config.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            return {s.target.id.upper() for s in node.body if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
                    and s.target.id != "model_config"}
    return set()


ENV_NAME = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")


def check_env_keys(root: Path, rep: Report) -> None:
    """Rule 6."""
    keys = settings_keys(root)
    example = {m[1] for m in re.finditer(r"^([A-Z][A-Z0-9_]*)=", read(root, ".env.example") or "", re.M)}
    for k in sorted(keys - example):
        rep.errors.append(f".env.example lacks {k} (a field of Settings in backend/config.py)")
    for k in sorted(example - keys):
        rep.errors.append(f".env.example has {k}, which Settings in backend/config.py does not read")
    for rel, _lang in READMES:
        text = read(root, rel)
        if text is None or not is_content_checked(rel):
            continue
        in_tables = {tok for table in table_rows(text) for row in table for tok in re.findall(r"`([^`]+)`", row) if ENV_NAME.match(tok)}
        for k in sorted(keys - in_tables):
            rep.errors.append(f"{rel}: the key table lacks `{k}`")
        for k in sorted(in_tables - keys):
            rep.errors.append(f"{rel}: the key table names `{k}`, which Settings does not read")


def tabs(root: Path) -> list[tuple[str, dict[str, str]]]:
    """(data-tab id, {language: label}) of the tab bar, labels from the catalogs where the button has a key."""
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    cats = {}
    for lang in ("en", "pl"):
        p = root / "frontend" / "i18n" / f"{lang}.json"
        cats[lang] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    out = []
    for m in re.finditer(r"<button\b([^>]*\bdata-tab=\"([\w-]+)\"[^>]*)>(.*?)</button>", html, re.S):
        attrs, tab_id, inner = m[1], m[2], m[3]
        key = re.search(r'data-i18n="([\w.]+)"', attrs) or re.search(r'data-i18n-attr="[^"]*title:([\w.]+)', attrs)
        text = re.sub(r"<[^>]+>", "", inner).strip()
        out.append((tab_id, {lang: (cats[lang].get(key[1]) if key else None) or text for lang in ("en", "pl")}))
    return out


def _plain(cell: str) -> str:
    return re.sub(r"[`*_]|\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) or "", cell).strip()


def check_tabs(root: Path, rep: Report) -> None:
    """Rule 7."""
    tab_list = tabs(root)
    for tab_id, _labels in tab_list:
        if tab_id not in USER_GUIDE_SECTIONS:
            rep.errors.append(f"tab '{tab_id}' has no entry in USER_GUIDE_SECTIONS (scripts/check_docs.py) and no section in {USER_GUIDE}")
    guide = read(root, USER_GUIDE)
    if guide is not None and is_content_checked(USER_GUIDE):
        titles = [re.sub(r"^\d+(\.\d+)*\.?\s+", "", t) for _, t in headings(guide)]
        for tab_id, _labels in tab_list:
            want = USER_GUIDE_SECTIONS.get(tab_id)
            if want and want not in titles:
                rep.errors.append(f"{USER_GUIDE}: no section '{want}' for the tab '{tab_id}'")
    for rel, lang in READMES:
        text = read(root, rel)
        if text is None or not is_content_checked(rel):
            continue
        first_cells = [_plain(row.strip().strip("|").split("|")[0]) for table in table_rows(text) for row in table]
        for tab_id, labels in tab_list:
            label = labels[lang]
            if not any(re.search(rf"(?<!\w){re.escape(label)}(?!\w)", cell) for cell in first_cells):
                rep.errors.append(f"{rel}: the tab table has no row for the tab '{label}' ({tab_id})")


def module_files(root: Path) -> list[str]:
    files = list((root / "backend").rglob("*.py"))
    files += sorted((root / "frontend" / "js").glob("*.js"))
    files += [p for p in (root / "scripts").rglob("*") if p.is_file()]
    rels = sorted({p.relative_to(root).as_posix() for p in files if "__pycache__" not in p.parts and p.suffix != ".pyc"})
    return [r for r in rels if r not in MODULE_EXCEPTIONS]


def _mentioned(rel: str, text: str, all_files: list[str]) -> bool:
    """True when the text names the file by its path or by a shorter tail of it that names no other file."""
    parts = rel.split("/")
    for i in range(len(parts)):
        tail = "/".join(parts[i:])
        if i > 0 and sum(1 for f in all_files if f == tail or f.endswith("/" + tail)) > 1:
            continue
        if re.search(rf"(?<![\w./-]){re.escape(tail)}(?![\w-]|\.\w)", text):
            return True
    return False


def check_modules(root: Path, rep: Report) -> None:
    """Rule 8: an error once both files are written, a warning while one of them is still PENDING."""
    ready = [rel for rel in MODULE_DOCS if is_content_checked(rel) and read(root, rel) is not None]
    if not ready:
        return
    text = "\n".join(read(root, rel) or "" for rel in ready)
    files = module_files(root)
    sink = rep.errors if len(ready) == len(MODULE_DOCS) else rep.warnings
    for rel in files:
        if not _mentioned(rel, text, files):
            sink.append(f"{rel} is not named in {' or '.join(MODULE_DOCS)}")


def fact_value(root: Path, fact: Fact) -> int | None:
    m = re.search(fact.pattern, read(root, fact.source) or "", re.M)
    return int(m[1].replace("_", "")) if m else None


def number_pattern(n: int) -> str:
    """A number as people write it: 3000000, 3 000 000, 3,000,000, 3.000.000 (also with a no-break space)."""
    digits = str(n)
    groups = []
    while digits:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    return r"(?<![\w.,])" + "[ ,.\u00a0\u202f]?".join(groups) + r"(?![\w]|[.,]\d)"


def states_fact(text: str, fact: Fact, value: int) -> bool:
    plain = "\n".join(line for _, line in strip_code(text))
    for m in re.finditer(number_pattern(value), plain):
        if value >= 1000 or not fact.units:
            return True
        after = plain[m.end():m.end() + 30].split("\n")[0].lower()
        if re.match(r"\s*(?:-\s*)?(?:[a-ząćęłńóśźż]+\s+){0,2}?(?:" + "|".join(map(re.escape, fact.units)) + ")", after):
            return True
    return False


def check_facts(root: Path, rep: Report) -> None:
    """Rule 9."""
    for fact in FACTS:
        value = fact_value(root, fact)
        if value is None:
            rep.errors.append(f"FACTS: '{fact.label}' not found in {fact.source} (pattern {fact.pattern!r}); update FACTS in scripts/check_docs.py")
            continue
        for home in fact.homes:
            for rel in (home, _twin(home)):
                text = read(root, rel)
                if text is None or not is_content_checked(rel):
                    continue
                if not states_fact(text, fact, value):
                    rep.errors.append(f"{rel}: does not state '{fact.label}' = {value} (from {fact.source})")


def _twin(rel: str) -> str:
    for en, pl in DOC_PAIRS:
        if rel == en:
            return pl
        if rel == pl:
            return en
    return rel


def switch_line(rel: str) -> str:
    """The expected first line of a paired file: the current language in bold, the other as a link."""
    en_rel = rel if any(rel == en for en, _ in DOC_PAIRS) else _twin(rel)
    pl_rel = _twin(en_rel)
    other = pl_rel if rel == en_rel else en_rel
    link = os.path.relpath(other, Path(rel).parent.as_posix() or ".").replace(os.sep, "/")
    return f"**English** | [Polski]({link})" if rel == en_rel else f"[English]({link}) | **Polski**"


def check_form(root: Path, rep: Report, md_files: list[str]) -> None:
    """Rule 10."""
    for rel in md_files:
        text = (root / rel).read_text(encoding="utf-8")
        if EM_DASH in text:
            n = next(i for i, line in enumerate(text.splitlines(), 1) if EM_DASH in line)
            rep.errors.append(f"{rel}:{n}: long dash (U+2014), use '-'")
        if rel.startswith("docs/") and (m := re.search(r"Seisa \d+\.\d+\.\d+", text)):
            rep.errors.append(f"{rel}: contains a version number ('{m[0]}'); docs/ never carries one")
    for pair in DOC_PAIRS:
        for rel in pair:
            text = read(root, rel)
            if text is None:
                continue
            first = next((line.strip() for line in text.splitlines() if line.strip()), "")
            # the README starts with the centred logo block, and the switch line sits inside it
            ok = switch_line(rel) in text.split("\n# ", 1)[0] if rel.startswith("README") else first == switch_line(rel)
            if not ok:
                rep.errors.append(f"{rel}: the first line must be the language switch: {switch_line(rel)}")


EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")


def check_emails(root: Path, rep: Report, md_files: list[str]) -> None:
    """Rule 11."""
    for rel in [*md_files, *EMAIL_SOURCES]:
        text = read(root, rel)
        if text is None:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for m in EMAIL.finditer(line):
                addr, domain = m[0].lower().rstrip("."), m[1].lower().rstrip(".")
                if addr not in ALLOWED_EMAILS and not EXAMPLE_EMAIL_DOMAIN.search(domain):
                    rep.errors.append(f"{rel}:{n}: e-mail address not on ALLOWED_EMAILS (scripts/check_docs.py); the public contact is contact@seisa.eu")


def check_required(root: Path, rep: Report) -> None:
    """Rule 12."""
    for rel in REQUIRED_DOCS:
        if rel not in PENDING and not (root / rel).is_file():
            rep.errors.append(f"{rel} is missing (REQUIRED_DOCS); if it is still being written, it belongs on PENDING")


def check_readability(root: Path, rep: Report, md_files: list[str]) -> None:
    """Rules 13 and 14 (warnings)."""
    for rel in md_files:
        if rel in PENDING or rel.startswith((".github/", "backend/", "tests/")) or rel in UNPAIRED:
            continue
        text = (root / rel).read_text(encoding="utf-8")
        para: list[tuple[int, str]] = []
        for n, line in [*strip_code(text), (0, "")]:
            s = line.strip()
            if s and not re.match(r"([-*+>|#]|\d+[.)]\s|<)", s):
                para.append((n, s))
                continue
            if len(para) > PARAGRAPH_MAX_LINES or sum(len(t.split()) for _, t in para) > PARAGRAPH_MAX_WORDS:
                rep.warnings.append(f"{rel}:{para[0][0]}: a paragraph of {len(para)} lines / {sum(len(t.split()) for _, t in para)} words; split it or use a list")
            para = []
        lines = text.count("\n") + 1
        has_toc = (any(re.fullmatch(r"(contents|table of contents|spis treści)", t.lower()) for _, t in headings(text))
                   or len(re.findall(r"^\s*[-*]\s+\[[^\]]+\]\(#", text, re.M)) >= 3)
        if lines > TOC_MIN_LINES and not has_toc:
            rep.warnings.append(f"{rel}: {lines} lines and no table of contents")


# Rule 15: hosts that are examples, not links to visit. Loopback and this computer, the names reserved for examples and
# tests (RFC 2606, RFC 6761), the mDNS suffix .local and the placeholder suffix .tld used in examples.
EXAMPLE_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "example.org", "example.com", "example.net"})
EXAMPLE_HOST_SUFFIXES = (".local", ".localhost", ".tld", ".example", ".test", ".invalid", ".example.org", ".example.com", ".example.net")
# A URL ends at white space, quotes, angle or square brackets (a reference link `[text][label]`), a closing parenthesis
# or a backtick; trailing sentence punctuation is not part of it.
_URL = re.compile(r"https?://[^\s()\[\]<>\"'`{}|\\]+")
_TRAILING = ".,;:!?*_"


def external_urls(text: str) -> set[str]:
    """The URLs worth visiting in a Markdown text.

    Skipped: everything in fenced code blocks and `code spans` (commands and sample output, not links); example hosts
    (EXAMPLE_HOSTS, EXAMPLE_HOST_SUFFIXES); and templates, i.e. a URL followed directly by a placeholder such as
    `https://urlscan.io/result/<uuid>` or `.../check/{ip}`. A template is not a page: its stem alone (".../result/")
    usually answers 404, which would be a false alarm, and the real page needs a value only the reader has."""
    found = set()
    for _, line in strip_code(text):
        line = re.sub(r"`[^`]*`", " ", line)
        for m in _URL.finditer(line):
            url = m[0].rstrip(_TRAILING)
            following = line[m.start() + len(url):m.start() + len(url) + 1]
            if following in ("<", "{"):
                continue
            host = (re.match(r"https?://([^/:?#]+)", url) or [None, ""])[1].lower()
            if not host or host in EXAMPLE_HOSTS or host.endswith(EXAMPLE_HOST_SUFFIXES):
                continue
            found.add(url)
    return found


def check_external(root: Path, rep: Report, md_files: list[str]) -> None:
    """Rule 15 (only with --external): every external link of the documentation answers."""
    import urllib.error
    import urllib.request

    urls = sorted({u for rel in md_files for u in external_urls((root / rel).read_text(encoding="utf-8"))})
    for url in urls:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "seisa-check-docs"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                status = r.status
        except urllib.error.HTTPError as e:
            status = e.code
        except Exception as e:  # every failure is reported, none stops the run
            rep.errors.append(f"external link {url}: {type(e).__name__}")
            continue
        if status >= 400 and status not in (403, 405, 429):  # some sites refuse HEAD or robots; that is not a dead link
            rep.errors.append(f"external link {url}: HTTP {status}")


def run(root: Path = ROOT, external: bool = False) -> Report:
    rep = Report()
    md_files = markdown_files(root)
    check_pairs(root, rep)
    check_unpaired(root, rep, md_files)
    check_links(root, rep, md_files)
    check_images(root, rep, md_files)
    check_api(root, rep)
    check_env_keys(root, rep)
    check_tabs(root, rep)
    check_modules(root, rep)
    check_facts(root, rep)
    check_form(root, rep, md_files)
    check_emails(root, rep, md_files)
    check_required(root, rep)
    check_readability(root, rep, md_files)
    if external:
        check_external(root, rep, md_files)
    return rep


def main(argv: list[str]) -> int:
    unknown = [a for a in argv if a != "--external"]
    if unknown:
        print("usage: check_docs.py [--external]", file=sys.stderr)
        return 2
    rep = run(ROOT, external="--external" in argv)
    for w in rep.warnings:
        print("warning:", w)
    for e in rep.errors:
        print("ERROR:", e)
    pending = sorted(f for f in PENDING if f in REQUIRED_DOCS)
    print(f"{len(rep.errors)} error(s), {len(rep.warnings)} warning(s); still PENDING: {len(pending)} file(s)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

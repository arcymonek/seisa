#!/usr/bin/env python3
"""Consistency checks for the PL/EN catalogs (standard library only).

Usage: python3 scripts/check_i18n.py [--strict]

Checks: key parity pl/en, {placeholder} parity, plural-suffix completeness, forbidden characters (HTML, U+2014),
keys used in code but missing from the catalog, unused keys, README heading parity, docs/en <-> docs/pl parity (same files, same heading levels 1-4),
dead relative links and anchors in the Markdown files, the same version in all five places and (with --strict) user-facing
literals with Polish diacritics that bypass t(). Exit code 1 on errors. Warnings never fail the run.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
PAIRS = {
    "frontend": ROOT / "frontend" / "i18n",
    "backend": ROOT / "backend" / "locales",
}
PLURAL_SUFFIXES = ("_zero", "_one", "_two", "_few", "_many", "_other")
PLURALS_REQUIRED = {"pl": {"_one", "_few", "_many", "_other"}, "en": {"_one", "_other"}}
DIACRITICS = re.compile("[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
# Polish words that carry no diacritics (a diacritic-only check missed a literal 'nieznana'); matched as whole words
# in string literals, reported as warnings because a few of them may be legitimate identifiers.
POLISH_WORDS = re.compile(
    r"\b(nieznan\w*|brak|blad|bledy|zapis\w*|wyslij|wysylk\w*|temat|tytul|uzytkownik\w*|wiadomosc|plik\w*|dane|wynik\w*"
    r"|ostrzezeni\w*|szukaj|usun|otworz|zamknij|anuluj|pokaz|ukryj|tak|nie wiem)\b",
    re.IGNORECASE,
)
PLACEHOLDER = re.compile(r"\{(\w+)\}")
EM_DASH = "\u2014"

errors: list[str] = []
warnings: list[str] = []


def load(dir_: Path, lang: str) -> dict[str, str]:
    path = dir_ / f"{lang}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def base_key(key: str) -> str:
    for suffix in PLURAL_SUFFIXES:
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return key


def check_pair(name: str, dir_: Path) -> dict[str, dict[str, str]]:
    cats = {lang: load(dir_, lang) for lang in ("pl", "en")}
    if not cats["pl"] and not cats["en"]:
        return cats
    pl, en = cats["pl"], cats["en"]
    # plural forms differ per language (pl has few/many), so parity is checked on the base key
    pl_keys, en_keys = {base_key(k) for k in pl}, {base_key(k) for k in en}
    for key in sorted(pl_keys - en_keys):
        errors.append(f"[{name}] key missing in en.json: {key}")
    for key in sorted(en_keys - pl_keys):
        errors.append(f"[{name}] key missing in pl.json: {key}")
    for key in sorted(set(pl) & set(en)):
        if set(PLACEHOLDER.findall(pl[key])) != set(PLACEHOLDER.findall(en[key])):
            errors.append(f"[{name}] placeholder mismatch in {key}: pl={PLACEHOLDER.findall(pl[key])} en={PLACEHOLDER.findall(en[key])}")
    for lang, cat in cats.items():
        for key, value in cat.items():
            if not isinstance(value, str):
                errors.append(f"[{name}/{lang}] value of {key} is not a string")
                continue
            if "<" in value and key not in ALLOW_MARKUP:
                errors.append(f"[{name}/{lang}] '<' in {key} (catalogs hold plain text, never HTML)")
            if EM_DASH in value:
                errors.append(f"[{name}/{lang}] long dash (U+2014) in {key}, use '-'")
        groups: dict[str, set[str]] = {}
        for key in cat:
            for suffix in PLURAL_SUFFIXES:
                if key.endswith(suffix):
                    groups.setdefault(key[: -len(suffix)], set()).add(suffix)
        for base, have in groups.items():
            missing = PLURALS_REQUIRED[lang] - have
            if missing:
                errors.append(f"[{name}/{lang}] plural forms of {base} missing: {sorted(missing)}")
    return cats


ALLOW_MARKUP: set[str] = set()

FRONT_USE = re.compile(r"""\bt[n]?\(\s*["'`]([\w.]+)["'`]""")
FRONT_DYN = re.compile(r"""\bt[n]?\(\s*["'`]([\w.]+\.)["'`]\s*\+|\bt[n]?\(\s*`([\w.]+\.)\$\{""")
QUOTED_KEY = re.compile(r"""["'`]([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)["'`]""")
BACK_USE = re.compile(r"""\b(?:t|tn|T)\(\s*["']([\w.]+)["']""")
BACK_DYN = re.compile(r"""\b(?:t|tn|T)\(\s*f["']([\w.]+\.)\{""")


def source_files(sub: str, exts: tuple[str, ...]) -> list[Path]:
    return [p for p in (ROOT / sub).rglob("*") if p.suffix in exts and "vendor" not in p.parts and "__pycache__" not in p.parts]


def check_usage(name: str, cat: dict[str, str], files: list[Path], use_re: re.Pattern, dyn_re: re.Pattern) -> None:
    if not cat:
        return
    used: set[str] = set()
    prefixes: set[str] = set()
    for f in files:
        text = f.read_text(encoding="utf-8")
        for m in use_re.finditer(text):
            key = m.group(1)
            if key.endswith("."):
                continue  # dynamic key prefix, handled through dyn_re
            used.add(key)
            if base_key(key) == key and key not in cat and not any(f"{key}{s}" in cat for s in PLURAL_SUFFIXES):
                errors.append(f"[{name}] key used but not defined: {key} ({f.relative_to(ROOT)})")
        for m in dyn_re.finditer(text):
            prefixes.add(m.group(1) or m.group(2))
        # keys kept as data (e.g. {desc: "md.service.otx"}) count as used
        used.update(k for k in QUOTED_KEY.findall(text) if k in cat or any(f"{k}{sfx}" in cat for sfx in PLURAL_SUFFIXES))
    if name == "frontend":  # static markup: data-i18n="key" and data-i18n-attr="attr:key;attr:key"
        for html in (ROOT / "frontend").glob("*.html"):
            text = html.read_text(encoding="utf-8")
            used.update(re.findall(r'data-i18n="([\w.]+)"', text))
            for attr in re.findall(r'data-i18n-attr="([^"]+)"', text):
                used.update(pair.split(":")[1].strip() for pair in attr.split(";") if ":" in pair)
    for key in sorted(cat):
        if key in used or base_key(key) in used or any(key.startswith(p) for p in prefixes):
            continue
        warnings.append(f"[{name}] key never referenced by literal: {key}")


def check_hardcoded_python() -> None:
    hits = 0
    for f in source_files("backend", (".py",)):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        docs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant):
                    docs.add(id(first.value))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs):
                continue
            if DIACRITICS.search(node.value):
                hits += 1
                errors.append(f"[strict] Polish literal in {f.relative_to(ROOT)}:{node.lineno}: {node.value[:60]!r}")
            elif POLISH_WORDS.search(node.value):
                warnings.append(f"[strict] possible Polish literal in {f.relative_to(ROOT)}:{node.lineno}: {node.value[:60]!r}")
    if not hits:
        print("strict: no Polish literals in backend/ (docstrings excluded)")


def check_hardcoded_js() -> None:
    for f in source_files("frontend/js", (".js",)):
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "i18n-ok" in line:
                continue
            code = line.split("//", 1)[0]
            if DIACRITICS.search(code):
                errors.append(f"[strict] Polish text in {f.relative_to(ROOT)}:{n}: {line.strip()[:70]}")


def check_readme_parity() -> None:
    en, pl = ROOT / "README.md", ROOT / "README.pl.md"
    if not (en.exists() and pl.exists()):
        return

    def headings(p: Path) -> list[str]:
        return [m.group(1) for m in re.finditer(r"^(#{1,3}) ", p.read_text(encoding="utf-8"), re.M)]

    if headings(en) != headings(pl):
        errors.append(f"README.md and README.pl.md have different heading structure ({len(headings(en))} vs {len(headings(pl))} headings)")


MD_LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
MD_SRC = re.compile(r"""\bsrc=["']([^"']+)["']""")
DOC_DIRS = (ROOT / "docs" / "en", ROOT / "docs" / "pl")
LINKED_MD = ("README.md", "README.pl.md", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md")


def md_lines(p: Path) -> list[tuple[int, str]]:
    """(line number, text) of a Markdown file without fenced code blocks."""
    out, in_code = [], False
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            out.append((n, line))
    return out


def md_headings(p: Path) -> list[tuple[int, str]]:
    return [(len(m.group(1)), m.group(2).strip()) for _, line in md_lines(p) if (m := re.match(r"(#{1,6}) (.*)", line))]


def slugify(title: str) -> str:
    """The GitHub/Forgejo anchor rule: lower case, drop punctuation (keep letters incl. diacritics, digits, '-', '_'), spaces to '-'."""
    return re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")


def anchors_of(p: Path) -> set[str]:
    seen: dict[str, int] = {}
    res: set[str] = set()
    for _, title in md_headings(p):
        title = re.sub(r"`|\*|\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) or "", title)
        slug = slugify(title)
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        res.add(slug if n == 0 else f"{slug}-{n}")
    return res


def check_docs_parity() -> None:
    """docs/en and docs/pl: the same file names, the same heading levels (1-4) in every pair, no version number."""
    en_dir, pl_dir = DOC_DIRS
    if not (en_dir.is_dir() and pl_dir.is_dir()):
        return
    en_files = {p.name for p in en_dir.glob("*.md")}
    pl_files = {p.name for p in pl_dir.glob("*.md")}
    for name in sorted(en_files - pl_files):
        errors.append(f"docs/pl/{name} is missing (docs/en/{name} exists)")
    for name in sorted(pl_files - en_files):
        errors.append(f"docs/en/{name} is missing (docs/pl/{name} exists)")
    for name in sorted(en_files & pl_files):
        lv_en = [lvl for lvl, _ in md_headings(en_dir / name) if lvl <= 4]
        lv_pl = [lvl for lvl, _ in md_headings(pl_dir / name) if lvl <= 4]
        if lv_en != lv_pl:
            errors.append(f"docs/en/{name} and docs/pl/{name} have different heading structure ({len(lv_en)} vs {len(lv_pl)} headings)")
    for d in DOC_DIRS:
        for p in sorted(d.glob("*.md")):
            text = p.read_text(encoding="utf-8")
            if re.search(r"Seisa \d+\.\d+\.\d+", text):
                errors.append(f"{p.relative_to(ROOT)} contains a version number (docs must not carry one)")


def check_markdown_links() -> None:
    """Relative links and #anchors in the documentation Markdown files must resolve (external URLs are not fetched)."""
    files = [ROOT / n for n in LINKED_MD if (ROOT / n).exists()]
    for d in DOC_DIRS:
        files += sorted(d.glob("*.md"))
    cache: dict[Path, set[str]] = {}
    for f in files:
        rel_f = f.relative_to(ROOT)
        text = f.read_text(encoding="utf-8")
        if EM_DASH in text:
            errors.append(f"{rel_f}: long dash (U+2014), use '-'")
        for n, line in md_lines(f):
            line = re.sub(r"`[^`]*`", "", line)
            targets = MD_LINK.findall(line) + MD_SRC.findall(line)
            for target in targets:
                if re.match(r"[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("//"):
                    continue
                path_part, _, frag = target.partition("#")
                dest = (f.parent / path_part).resolve() if path_part else f
                if not dest.exists():
                    errors.append(f"{rel_f}:{n}: dead link {target}")
                    continue
                if frag and dest.suffix == ".md":
                    if dest not in cache:
                        cache[dest] = anchors_of(dest)
                    if unquote(frag).lower() not in cache[dest]:
                        errors.append(f"{rel_f}:{n}: dead anchor {target}")


def check_versions() -> None:
    """The visible version must be identical everywhere: 3x index.html (title, header, footer) + 2x README."""
    found: dict[str, str] = {}
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for label, pattern in (
        ("index.html <title>", r"<title>Seisa ([\d.]+)</title>"),
        ("index.html header", r"<small>([\d.]+)</small>"),
        ("index.html footer", r"<footer>Seisa ([\d.]+)"),
    ):
        m = re.search(pattern, html)
        found[label] = m.group(1) if m else "?"
    for name in ("README.md", "README.pl.md"):
        m = re.search(r"<b>Seisa ([\d.]+)</b>", (ROOT / name).read_text(encoding="utf-8"))
        found[name] = m.group(1) if m else "?"
    if len(set(found.values())) != 1:
        errors.append(f"version differs between places: {found}")
    m = re.search(r'<meta name="seisa-release-date" content="(\d{4}-\d{2}-\d{2})"', html)
    if not m:
        errors.append("index.html: missing <meta name=\"seisa-release-date\" content=\"YYYY-MM-DD\">")


def main() -> int:
    strict = "--strict" in sys.argv
    cats = {name: check_pair(name, d) for name, d in PAIRS.items()}
    check_usage("frontend", cats["frontend"]["en"], source_files("frontend/js", (".js",)), FRONT_USE, FRONT_DYN)
    check_usage("backend", cats["backend"]["en"], source_files("backend", (".py",)), BACK_USE, BACK_DYN)
    check_readme_parity()
    check_docs_parity()
    check_markdown_links()
    check_versions()
    if strict:
        check_hardcoded_python()
        check_hardcoded_js()
    for w in warnings:
        print("warning:", w)
    for e in errors:
        print("ERROR:", e)
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Consistency checks for the PL/EN catalogs (standard library only).

Usage: python3 scripts/check_i18n.py [--strict]

Checks: key parity pl/en, {placeholder} parity, plural-suffix completeness, forbidden characters (HTML, U+2014),
keys used in code but missing from the catalog, unused keys, README heading parity and (with --strict) user-facing
literals with Polish diacritics that bypass t(). Exit code 1 on errors. Warnings never fail the run.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAIRS = {
    "frontend": ROOT / "frontend" / "i18n",
    "backend": ROOT / "backend" / "locales",
}
PLURAL_SUFFIXES = ("_zero", "_one", "_two", "_few", "_many", "_other")
PLURALS_REQUIRED = {"pl": {"_one", "_few", "_many", "_other"}, "en": {"_one", "_other"}}
DIACRITICS = re.compile("[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
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
        if name == "frontend":  # keys kept as data (e.g. {desc: "md.service.otx"}) count as used
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
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs and DIACRITICS.search(node.value):
                hits += 1
                errors.append(f"[strict] Polish literal in {f.relative_to(ROOT)}:{node.lineno}: {node.value[:60]!r}")
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


def main() -> int:
    strict = "--strict" in sys.argv
    cats = {name: check_pair(name, d) for name, d in PAIRS.items()}
    check_usage("frontend", cats["frontend"]["en"], source_files("frontend/js", (".js",)), FRONT_USE, FRONT_DYN)
    check_usage("backend", cats["backend"]["en"], source_files("backend", (".py",)), BACK_USE, BACK_DYN)
    check_readme_parity()
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

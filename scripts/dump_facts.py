#!/usr/bin/env python3
"""Dumps compute_facts() and parse_email() of the synthetic fixtures as JSON (used for golden comparisons).

Usage: python3 scripts/dump_facts.py [--lang pl|en] [--root DIR]

`--root` points to another checkout of the code (e.g. an older release exported with `git archive`), which makes
it possible to compare the output of two versions byte for byte: refactors of user-facing texts must not change
the facts in the language they had before.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--lang", default="pl")
ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
args = ap.parse_args()
root = Path(args.root)
sys.path.insert(0, str(root))

try:
    from backend.i18n import set_lang  # absent in releases before 2.0.13
    set_lang(args.lang)
except ImportError:
    pass
from backend.email_forensics import compute_facts, normalize_source, prepare_for_llm
from backend.email_parser import parse_email

fixtures = sorted((Path(__file__).resolve().parent.parent / "tests" / "fixtures").glob("*.eml"))
out = {}
for f in fixtures:
    src = normalize_source(f.read_text(encoding="utf-8"))
    parsed = parse_email(src)
    out[f.name] = {"facts": compute_facts(src), "prepared_notes": prepare_for_llm(src)[1], "parse_email": parsed}
print(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True, default=str))

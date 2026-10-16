#!/usr/bin/env python3
"""Runs the whole local checklist that must pass before a commit, in order, and stops at the first failure.

Usage: python3 scripts/check_all.py [--fast]

Steps: ruff, pytest (everything, including the slow hook and time-limit tests; `--fast` skips those), the end-to-end
harness, the i18n check in strict mode, the documentation check, the facts dump, and the syntax check of every frontend
module. The same steps
run in CI (.github/workflows/ci.yml). Exit code 0 = all passed, 1 = a step failed (its output is shown above the summary).

What it does NOT replace: the manual try in the browser after UI changes (`/?lang=qa`, XSS payloads), and the one test
that is skipped inside a sandbox (the desktop icon test needs `sips`).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
PY = str(VENV_PYTHON if VENV_PYTHON.exists() else sys.executable)


def run(cmd: list[str], **kwargs) -> bool:
    return subprocess.run(cmd, cwd=ROOT, **kwargs).returncode == 0


def check_js_syntax() -> bool:
    """`node --check` treats a .js file as CommonJS, so every module is copied to a .mjs name first."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "x.mjs"
        bad = []
        for path in sorted((ROOT / "frontend" / "js").glob("*.js")):
            target.write_bytes(path.read_bytes())
            if not run(["node", "--check", str(target)]):
                bad.append(path.name)
    if bad:
        print("SYNTAX ERROR in: " + ", ".join(bad))
    return not bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fast", action="store_true", help='skip the slow tests (pytest -m "not slow")')
    args = ap.parse_args()

    pytest_cmd = [PY, "-m", "pytest", "-q"] + (["-m", "not slow"] if args.fast else [])
    steps: list[tuple[str, object]] = [
        ("ruff", lambda: run([PY, "-m", "ruff", "check", "backend", "scripts", "tests"])),
        ("pytest" + (" (fast)" if args.fast else ""), lambda: run(pytest_cmd)),
        ("api_harness", lambda: run([PY, "scripts/api_harness.py"])),
        ("check_i18n --strict", lambda: run([PY, "scripts/check_i18n.py", "--strict"])),
        ("check_docs", lambda: run([PY, "scripts/check_docs.py"])),
        ("dump_facts", lambda: run([PY, "scripts/dump_facts.py", "--lang", "pl"], stdout=subprocess.DEVNULL)),
        ("frontend syntax (node --check)", check_js_syntax),
    ]
    results: list[tuple[str, bool, float]] = []
    for name, step in steps:
        print(f"\n=== {name} ===", flush=True)
        started = time.perf_counter()
        ok = bool(step())
        results.append((name, ok, time.perf_counter() - started))
        if not ok:
            break

    print("\n=== summary ===")
    for name, ok, seconds in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({seconds:.1f} s)")
    skipped = [name for name, _ in steps[len(results):]]
    for name in skipped:
        print(f"SKIP  {name}  (not run, an earlier step failed)")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())

"""Tests for scripts/hooks/pre-commit (the git hook) and its `--range` mode used by CI.

The expected values come from the rules in CLAUDE.md ("Wersjonowanie", "Commit i push"), not from the hook's own
output. The end-to-end tests build a throw-away git repository from a copy of this project (the working tree, so
an uncommitted hook is tested too), stage a change, run the hook and check the exit code and the message. Every
rule of the hook has at least one test that fails when the rule is removed: that is the mutation test CLAUDE.md
asks for, kept permanently.

`SEISA_HOOK_UNDER_TEST=/path/to/mutated-copy` runs the same tests against another copy of the hook; it is how a
mutated hook is shown to turn the matching test red.
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK_SRC = Path(os.environ.get("SEISA_HOOK_UNDER_TEST") or ROOT / "scripts" / "hooks" / "pre-commit")
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.org",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.org",
}


def _load_hook():
    loader = SourceFileLoader("seisa_pre_commit_hook", str(HOOK_SRC))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


hook_mod = _load_hook()


# --- helpers ----------------------------------------------------------------------------------------------------

def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, env=GIT_ENV, capture_output=True, text=True, check=check)


def write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def append(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.write_text(p.read_text(encoding="utf-8") + text, encoding="utf-8")


def run_hook(repo: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "hooks" / "pre-commit"), *args],
        cwd=repo, env={**GIT_ENV, **(env or {})}, capture_output=True, text=True,
    )


def current_version(repo: Path) -> str:
    html = (repo / "frontend" / "index.html").read_text(encoding="utf-8")
    return re.search(r"<title>Seisa ([\d.]+)</title>", html)[1]


# The five places, written out here on purpose (CLAUDE.md "Wersjonowanie"), not taken from the hook's own table.
_PLACES = {
    "frontend/index.html": (r"<title>Seisa [\d.]+</title>", r"<small>[\d.]+</small>", r"<footer>Seisa [\d.]+"),
    "README.md": (r"<b>Seisa [\d.]+</b>",),
    "README.pl.md": (r"<b>Seisa [\d.]+</b>",),
}


def set_version(repo: Path, new: str, files: tuple[str, ...] = tuple(_PLACES)) -> None:
    for rel in files:
        text = (repo / rel).read_text(encoding="utf-8")
        for pattern in _PLACES[rel]:
            text = re.sub(pattern, lambda m: re.sub(r"[\d]+\.[\d]+\.[\d]+", new, m.group(0)), text)
        (repo / rel).write_text(text, encoding="utf-8")


def step(version: str, kind: str) -> str:
    x, y, z = (int(n) for n in version.split("."))
    return {
        "z": f"{x}.{y}.{z + 1}",
        "y": f"{x}.{y + 1}.0",
        "x": f"{x + 1}.0.0",
        "skip": f"{x}.{y}.{z + 2}",
        "bad-y": f"{x}.{y + 1}.1",
        "back": f"{x}.{y}.{z - 1}",
    }[kind]


def stage(repo: Path, *paths: str, force: bool = False) -> None:
    git(repo, "add", *(["-f"] if force else []), "--", *paths)


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


# --- fixtures ---------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def base_repo(tmp_path_factory) -> Path:
    """A git repository with one commit on `main`: a copy of the project (tracked files plus not-yet-committed ones)."""
    d = tmp_path_factory.mktemp("hookbase")
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    for rel in filter(None, listing.split("\0")):
        src = ROOT / rel
        if src.is_file():
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, d / rel)
    shutil.copy2(HOOK_SRC, d / "scripts" / "hooks" / "pre-commit")
    git(d, "init", "-q", "-b", "main")
    commit_all(d, "base")
    return d


@pytest.fixture
def repo(base_repo, tmp_path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(base_repo, dest, symlinks=True)
    return dest


# --- pure functions (the rules written down in CLAUDE.md) -------------------------------------------------------

@pytest.mark.parametrize(("old", "new"), [
    ("2.1.30", "2.1.31"),    # Z+1
    ("2.1.99", "2.1.100"),   # Z has no upper limit
    ("2.1.30", "2.2.0"),     # Y+1, Z back to 0
    ("2.1.30", "3.0.0"),     # X+1, Y and Z back to 0
])
def test_allowed_version_steps(old, new):
    assert hook_mod.is_next_version(old, new)


@pytest.mark.parametrize(("old", "new"), [
    ("2.1.30", "2.1.30"),    # no change is not a step
    ("2.1.30", "2.1.32"),    # skipped one
    ("2.1.30", "2.1.29"),    # backwards
    ("2.1.30", "2.2.1"),     # Y+1 must reset Z
    ("2.1.30", "2.3.0"),     # skipped a minor
    ("2.1.30", "3.0.1"),     # X+1 must reset Y and Z
    ("2.1.30", "3.1.0"),
    ("2.1.30", "?"),
])
def test_disallowed_version_steps(old, new):
    assert not hook_mod.is_next_version(old, new)


@pytest.mark.parametrize(("path", "twin"), [
    ("README.md", "README.pl.md"),
    ("README.pl.md", "README.md"),
    ("docs/en/architecture.md", "docs/pl/architecture.md"),
    ("docs/pl/tabs.md", "docs/en/tabs.md"),
    ("docs/email-analysis-guide.md", None),    # prompt context, not documentation
    ("CHANGELOG.md", None),
    ("backend/main.py", None),
])
def test_language_twin(path, twin):
    assert hook_mod.twin_of(path) == twin


@pytest.mark.parametrize("path", ["CLAUDE.md", ".env", "data/history.json", "logs/seisa.log", "tests/private/a.eml", "reports/audits/x.md"])
def test_forbidden_paths(path):
    assert hook_mod.forbidden_reason(path)


@pytest.mark.parametrize("path", [".env.example", "data/.gitkeep", "logs/.gitkeep", "tests/private/.gitkeep", "backend/main.py", "docs/en/tabs.md"])
def test_allowed_paths(path):
    assert hook_mod.forbidden_reason(path) is None


# --- the hook on one commit -------------------------------------------------------------------------------------

def test_nothing_staged_passes(repo):
    assert run_hook(repo).returncode == 0


def test_a_clean_two_language_change_passes(repo):
    append(repo, "docs/en/architecture.md", "\nAn extra sentence.\n")
    append(repo, "docs/pl/architecture.md", "\nDodatkowe zdanie.\n")
    stage(repo, "docs/en/architecture.md", "docs/pl/architecture.md")
    r = run_hook(repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_forbidden_files_are_rejected_but_gitkeep_is_not(repo):
    forbidden = ["CLAUDE.md", ".env", "data/history.json", "logs/seisa.log", "tests/private/a.eml", "reports/audits/x.md"]
    for rel in forbidden:
        write(repo, rel, "x\n")
    append(repo, "data/.gitkeep", "\n")
    stage(repo, *forbidden, "data/.gitkeep", force=True)
    r = run_hook(repo)
    assert r.returncode == 1
    for rel in forbidden:
        assert f"FORBIDDEN FILE: {rel}" in r.stdout
    assert "data/.gitkeep" not in r.stdout


def test_long_dash_in_an_added_line_is_rejected_but_not_in_vendor_code(repo):
    append(repo, "backend/config.py", "\n# one \u2014 two\n")
    stage(repo, "backend/config.py")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "LONG DASH (U+2014) at backend/config.py:" in r.stdout

    git(repo, "reset", "-q", "--hard")
    append(repo, "frontend/vendor/marked.min.js", "\n/* one \u2014 two */\n")
    stage(repo, "frontend/vendor/marked.min.js")
    r = run_hook(repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_language_pair_must_be_staged_together(repo):
    append(repo, "README.md", "\nAn extra sentence.\n")
    append(repo, "docs/pl/extending.md", "\nDodatkowe zdanie.\n")
    stage(repo, "README.md", "docs/pl/extending.md")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "LANGUAGE PAIR: README.md is staged but README.pl.md is not" in r.stdout
    assert "LANGUAGE PAIR: docs/pl/extending.md is staged but docs/en/extending.md is not" in r.stdout


def test_one_lang_variable_skips_only_the_pair_rule(repo):
    append(repo, "README.md", "\nAn extra sentence.\n")
    stage(repo, "README.md")
    r = run_hook(repo, env={"SEISA_ONE_LANG": "1"})
    assert r.returncode == 0, r.stdout + r.stderr
    write(repo, "CLAUDE.md", "x\n")
    stage(repo, "CLAUDE.md", force=True)
    r = run_hook(repo, env={"SEISA_ONE_LANG": "1"})
    assert r.returncode == 1
    assert "FORBIDDEN FILE: CLAUDE.md" in r.stdout
    assert "LANGUAGE PAIR" not in r.stdout


def test_check_i18n_runs_on_the_index_not_on_the_working_tree(repo):
    original = (repo / "docs" / "en" / "architecture.md").read_text(encoding="utf-8")
    append(repo, "docs/en/architecture.md", "\n## A heading only in English\n")
    append(repo, "docs/pl/architecture.md", "\nDodatkowe zdanie.\n")
    stage(repo, "docs/en/architecture.md", "docs/pl/architecture.md")
    assert run_hook(repo).returncode == 1
    # fix the file on disk without staging the fix: what will be committed is still wrong
    write(repo, "docs/en/architecture.md", original)
    r = run_hook(repo)
    assert r.returncode == 1
    assert "CHECK_I18N failed" in r.stdout and "heading structure" in r.stdout


def test_a_broken_staged_check_i18n_stops_the_commit_with_a_message(repo):
    # the hook takes the five version places from the check_i18n.py that is in the INDEX; a wrong copy must not crash it
    # and, above all, must not let the commit through (a module that calls sys.exit(0) on import is a way to fail open)
    write(repo, "scripts/check_i18n.py", "X = 1\n")
    stage(repo, "scripts/check_i18n.py")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "lacks VERSION_PLACES" in r.stdout and "Traceback" not in r.stdout + r.stderr

    write(repo, "scripts/check_i18n.py", "import sys\nsys.exit(0)\n")
    stage(repo, "scripts/check_i18n.py")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "cannot import scripts/check_i18n.py" in r.stdout


def test_deleting_check_i18n_does_not_switch_the_checks_off(repo):
    git(repo, "rm", "-q", "scripts/check_i18n.py")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "MISSING CHECK: scripts/check_i18n.py" in r.stdout


def test_deleting_only_one_language_of_a_document_is_rejected(repo):
    git(repo, "rm", "-q", "docs/pl/tabs.md")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "docs/pl/tabs.md is missing" in r.stdout


def test_a_bump_of_one_allowed_step_passes(repo):
    set_version(repo, step(current_version(repo), "z"))
    stage(repo, *_PLACES)
    r = run_hook(repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_wrong_version_step_is_rejected(repo):
    # one end-to-end case; the arithmetic of every other wrong step is covered by test_disallowed_version_steps
    set_version(repo, step(current_version(repo), "skip"))
    stage(repo, *_PLACES)
    r = run_hook(repo)
    assert r.returncode == 1
    assert "VERSION STEP" in r.stdout


def test_the_five_places_must_agree(repo):
    set_version(repo, step(current_version(repo), "z"), files=("README.md",))
    stage(repo, "README.md")
    r = run_hook(repo, env={"SEISA_ONE_LANG": "1"})
    assert r.returncode == 1
    assert "version differs between places" in r.stdout


def test_a_branch_cannot_bump_twice(repo):
    git(repo, "switch", "-q", "-c", "feat-x")
    first = step(current_version(repo), "z")
    set_version(repo, first)
    commit_all(repo, "bump once")
    set_version(repo, step(first, "z"))
    stage(repo, *_PLACES)
    r = run_hook(repo)
    assert r.returncode == 1
    assert "VERSION STEP" in r.stdout and "(one bump per branch)" in r.stdout

    git(repo, "reset", "-q", "--hard")    # back to the single bump: further commits on the branch are fine
    append(repo, "docs/en/architecture.md", "\nAn extra sentence.\n")
    append(repo, "docs/pl/architecture.md", "\nDodatkowe zdanie.\n")
    stage(repo, "docs/en/architecture.md", "docs/pl/architecture.md")
    r = run_hook(repo)
    assert r.returncode == 0, r.stdout + r.stderr


# --- `--range main` (the whole branch, used by CI) --------------------------------------------------------------

def _branch_with(repo: Path, *, program: bool = False, bump: str | None = None, message: str = "work") -> None:
    git(repo, "switch", "-q", "-c", "feat-y")
    if program:
        append(repo, "backend/config.py", "\n# an edit\n")
    if bump:
        set_version(repo, step(current_version(repo), bump))
    if not program and not bump:
        append(repo, "docs/en/tabs.md", "\nAn extra sentence.\n")
    commit_all(repo, message)


def test_range_a_program_change_without_a_bump_fails(repo):
    _branch_with(repo, program=True)
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 1
    assert "PROGRAM CHANGED WITHOUT A VERSION BUMP" in r.stdout and "backend/config.py" in r.stdout


def test_range_a_waiver_in_a_commit_message_allows_a_program_change_without_a_bump(repo):
    _branch_with(repo, program=True, message="Reword a comment\n\nNo-version-bump: comments only")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 0, r.stdout + r.stderr


def test_range_an_empty_waiver_does_not_count(repo):
    _branch_with(repo, program=True, message="work\n\nNo-version-bump:")
    assert run_hook(repo, "--range", "main").returncode == 1


def test_range_a_program_change_with_one_bump_passes(repo):
    _branch_with(repo, program=True, bump="z")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 0, r.stdout + r.stderr


def test_range_a_change_outside_the_program_needs_no_bump(repo):
    _branch_with(repo)
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 0, r.stdout + r.stderr


def test_range_a_bump_without_a_program_change_fails(repo):
    _branch_with(repo, bump="z")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 1
    assert "VERSION BUMPED WITHOUT A PROGRAM CHANGE" in r.stdout


def test_range_a_wrong_step_fails_even_with_a_program_change(repo):
    _branch_with(repo, program=True, bump="skip")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 1
    assert "VERSION STEP" in r.stdout


def test_range_a_real_edit_of_index_html_is_a_program_change(repo):
    git(repo, "switch", "-q", "-c", "feat-y")
    append(repo, "frontend/index.html", "\n<!-- an edit -->\n")
    commit_all(repo, "edit the page")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 1
    assert "frontend/index.html" in r.stdout

    set_version(repo, step(current_version(repo), "z"))
    commit_all(repo, "bump")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 0, r.stdout + r.stderr

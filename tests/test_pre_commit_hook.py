"""Tests for scripts/hooks/pre-commit (the git hook) and its `--range` mode used by CI.

The expected values come from the project rules (docs/DEVELOPMENT.md: versioning, commits), not from the hook's own
output. The end-to-end tests build a throw-away git repository from a copy of this project (the working tree, so
an uncommitted hook is tested too), stage a change, run the hook and check the exit code and the message. Every
rule of the hook has at least one test that fails when the rule is removed: that is the mutation test the project
asks for, kept permanently.

Documentation pairs used here exist from the start of the documentation rewrite on: CODE_OF_CONDUCT.md with
docs/pl/CODE_OF_CONDUCT.md, and README.md with README.pl.md.

`SEISA_HOOK_UNDER_TEST=/path/to/mutated-copy` (and `SEISA_COMMITMSG_UNDER_TEST` for the commit-msg wrapper) runs the
same tests against another copy of the hook; it is how a mutated hook is shown to turn the matching test red.
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
COMMIT_MSG_SRC = Path(os.environ.get("SEISA_COMMITMSG_UNDER_TEST") or ROOT / "scripts" / "hooks" / "commit-msg")
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.org",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.org",
    "SEISA_PRIVACY_MARKERS": "/nonexistent/privacy-markers.txt",
}


def _load_check_docs():
    spec = importlib.util.spec_from_file_location("seisa_check_docs_for_hook_tests", ROOT / "scripts" / "check_docs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_hook():
    loader = SourceFileLoader("seisa_pre_commit_hook", str(HOOK_SRC))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


hook_mod = _load_hook()
DOC_PAIRS = _load_check_docs().DOC_PAIRS


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


# The four places, written out here on purpose (docs/DEVELOPMENT.md, versioning), not taken from the hook's own table.
_PLACES = {
    "frontend/index.html": (r"<title>Seisa [\d.]+</title>", r"<footer>Seisa [\d.]+"),
    "README.md": (r"<b>Seisa [\d.]+</b>",),
    "README.pl.md": (r"<b>Seisa [\d.]+</b>",),
}


def set_version(repo: Path, new: str, files: tuple[str, ...] = tuple(_PLACES)) -> None:
    for rel in files:
        text = (repo / rel).read_text(encoding="utf-8")
        for pattern in _PLACES[rel]:
            text = re.sub(pattern, lambda m: re.sub(r"[\d]+\.[\d]+\.[\d]+", new, m.group(0)), text)
        (repo / rel).write_text(text, encoding="utf-8")


RELEASE_DATE = "2031-01-02"


def bump(repo: Path, new: str, *, date: str = RELEASE_DATE) -> None:
    """A complete release: the four places, a CHANGELOG entry and the release date of the Info tab."""
    set_version(repo, new)
    changelog = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    changelog = re.sub(r"^## (\d)", f"## {new} - {date}\n\nA test entry.\n\n## \\1", changelog, count=1, flags=re.MULTILINE)
    (repo / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    html = (repo / "frontend" / "index.html").read_text(encoding="utf-8")
    html = re.sub(r'(<meta name="seisa-release-date" content=")[\d-]+', rf"\g<1>{date}", html)
    (repo / "frontend" / "index.html").write_text(html, encoding="utf-8")


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
    shutil.copy2(COMMIT_MSG_SRC, d / "scripts" / "hooks" / "commit-msg")
    git(d, "init", "-q", "-b", "main")
    # `git commit` may start `gc --auto` in the background, which deletes loose objects while `repo` copies this directory
    git(d, "config", "gc.auto", "0")
    git(d, "config", "maintenance.auto", "false")
    commit_all(d, "base")
    return d


@pytest.fixture
def repo(base_repo, tmp_path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(base_repo, dest, symlinks=True)
    return dest


# --- pure functions (the project rules) -------------------------------------------------------------------------

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
    ("docs/ARCHITECTURE.md", "docs/pl/ARCHITECTURE.md"),
    ("docs/pl/USER_GUIDE.md", "docs/USER_GUIDE.md"),
    ("CONTRIBUTING.md", "docs/pl/CONTRIBUTING.md"),
    ("docs/pl/CODE_OF_CONDUCT.md", "CODE_OF_CONDUCT.md"),
    ("backend/prompts/email-analysis-guide.md", None),    # prompt context, not documentation
    ("CHANGELOG.md", None),
    ("AGENTS.md", None),
    ("backend/main.py", None),
])
def test_language_twin(path, twin):
    assert hook_mod.twin_of(path, DOC_PAIRS) == twin


@pytest.mark.parametrize(("path", "program"), [
    ("backend/prompts/abuseipdb-reporting-policy.md", True),    # prompt context: a change alters the app
    ("backend/prompts/email-analysis-guide.md", True),
    ("seisa.sh", True),
    ("docs/abuseipdb-reporting-policy.md", False),              # the old place is documentation now
    ("README.md", False),
])
def test_program_file(path, program):
    assert hook_mod.is_program_file(path) is program


@pytest.mark.parametrize("path", ["CLAUDE.md", ".env", "data/history.json", "logs/seisa.log", "tests/private/a.eml", "reports/audits/x.md"])
def test_forbidden_paths(path):
    assert hook_mod.forbidden_reason(path)


@pytest.mark.parametrize("path", [".env.example", "data/.gitkeep", "logs/.gitkeep", "tests/private/.gitkeep", "backend/main.py", "docs/USER_GUIDE.md"])
def test_allowed_paths(path):
    assert hook_mod.forbidden_reason(path) is None


# --- the hook on one commit -------------------------------------------------------------------------------------

def test_nothing_staged_passes(repo):
    assert run_hook(repo).returncode == 0


def test_a_clean_two_language_change_passes(repo):
    _both_languages(repo)
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
    append(repo, "docs/pl/CODE_OF_CONDUCT.md", "\nDodatkowe zdanie.\n")
    stage(repo, "README.md", "docs/pl/CODE_OF_CONDUCT.md")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "LANGUAGE PAIR: README.md is staged but README.pl.md is not" in r.stdout
    assert "LANGUAGE PAIR: docs/pl/CODE_OF_CONDUCT.md is staged but CODE_OF_CONDUCT.md is not" in r.stdout


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


def test_the_checks_run_on_the_index_not_on_the_working_tree(repo):
    original = (repo / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    append(repo, "CODE_OF_CONDUCT.md", "\n## A heading only in English\n")
    append(repo, "docs/pl/CODE_OF_CONDUCT.md", "\nDodatkowe zdanie.\n")
    stage(repo, "CODE_OF_CONDUCT.md", "docs/pl/CODE_OF_CONDUCT.md")
    assert run_hook(repo).returncode == 1
    # fix the file on disk without staging the fix: what will be committed is still wrong
    write(repo, "CODE_OF_CONDUCT.md", original)
    r = run_hook(repo)
    assert r.returncode == 1
    assert "CHECK_DOCS failed" in r.stdout and "heading structure" in r.stdout


def test_check_i18n_runs_on_the_index(repo):
    cat = repo / "frontend" / "i18n" / "en.json"
    write(repo, "frontend/i18n/en.json", cat.read_text(encoding="utf-8").replace("{\n", '{\n  "zz.only_in_english": "x",\n', 1))
    stage(repo, "frontend/i18n/en.json")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "CHECK_I18N failed" in r.stdout and "zz.only_in_english" in r.stdout


def test_check_docs_rejects_a_document_without_a_twin(repo):
    write(repo, "docs/NOTES.md", "# Notes\n")
    stage(repo, "docs/NOTES.md")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "CHECK_DOCS failed" in r.stdout and "docs/NOTES.md is not in DOC_PAIRS" in r.stdout


def test_a_broken_staged_check_i18n_stops_the_commit_with_a_message(repo):
    # the hook takes the four version places from the check_i18n.py that is in the INDEX; a wrong copy must not crash it
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


def test_deleting_check_docs_does_not_switch_the_checks_off(repo):
    git(repo, "rm", "-q", "scripts/check_docs.py")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "MISSING CHECK: scripts/check_docs.py" in r.stdout


def test_a_broken_staged_check_docs_stops_the_commit_with_a_message(repo):
    # the hook takes DOC_PAIRS from the check_docs.py in the INDEX; a copy without it, or one that exits on import, must
    # stop the commit instead of switching the pair rule off
    write(repo, "scripts/check_docs.py", "X = 1\n")
    stage(repo, "scripts/check_docs.py")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "lacks DOC_PAIRS" in r.stdout and "Traceback" not in r.stdout + r.stderr

    write(repo, "scripts/check_docs.py", "import sys\nsys.exit(0)\n")
    stage(repo, "scripts/check_docs.py")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "cannot import scripts/check_docs.py" in r.stdout


def test_deleting_only_one_language_of_a_document_is_rejected(repo):
    git(repo, "rm", "-q", "docs/pl/CODE_OF_CONDUCT.md")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "docs/pl/CODE_OF_CONDUCT.md is missing" in r.stdout


def test_hook_messages_do_not_point_to_private_files(repo):
    write(repo, "CLAUDE.md", "x\n")
    stage(repo, "CLAUDE.md", force=True)
    r = run_hook(repo)
    assert r.returncode == 1
    assert "docs/DEVELOPMENT.md" in r.stdout
    assert "(CLAUDE.md)" not in r.stdout


def test_a_bump_of_one_allowed_step_passes(repo):
    bump(repo, step(current_version(repo), "z"))
    stage(repo, *_PLACES, "CHANGELOG.md")
    r = run_hook(repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_wrong_version_step_is_rejected(repo):
    # one end-to-end case; the arithmetic of every other wrong step is covered by test_disallowed_version_steps
    bump(repo, step(current_version(repo), "skip"))
    stage(repo, *_PLACES, "CHANGELOG.md")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "VERSION STEP" in r.stdout


def test_the_four_places_must_agree(repo):
    set_version(repo, step(current_version(repo), "z"), files=("README.md",))
    stage(repo, "README.md")
    r = run_hook(repo, env={"SEISA_ONE_LANG": "1"})
    assert r.returncode == 1
    assert "version differs between places" in r.stdout


def test_a_branch_cannot_bump_twice(repo):
    git(repo, "switch", "-q", "-c", "feat-x")
    first = step(current_version(repo), "z")
    bump(repo, first)
    commit_all(repo, "bump once")
    bump(repo, step(first, "z"))
    stage(repo, *_PLACES, "CHANGELOG.md")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "VERSION STEP" in r.stdout and "(one bump per branch)" in r.stdout

    git(repo, "reset", "-q", "--hard")    # back to the single bump: further commits on the branch are fine
    _both_languages(repo)
    r = run_hook(repo)
    assert r.returncode == 0, r.stdout + r.stderr


def _release_on_the_server(repo: Path, ref: str) -> str:
    """`main` moved on on the server (a merged release, program change and bump) while the local `main` stayed behind;
    returns the version of that release."""
    git(repo, "switch", "-q", "-c", "release")
    append(repo, "backend/config.py", "\n# a released change\n")
    released = step(current_version(repo), "z")
    bump(repo, released, date="2031-01-01")
    commit_all(repo, "Release")
    git(repo, "update-ref", f"refs/remotes/{ref}", "HEAD")
    git(repo, "switch", "-q", "-c", "feat-next")    # a new branch cut from the server's main
    git(repo, "branch", "-q", "-D", "release")
    return released


@pytest.mark.parametrize("ref", ["origin/main", "github/main"])
def test_the_version_step_counts_from_the_newest_main(repo, ref):
    # the local main is still on the old version: comparing with it made a correct bump look like two (F1, F2)
    released = _release_on_the_server(repo, ref)
    bump(repo, step(released, "z"))
    stage(repo, *_PLACES, "CHANGELOG.md")
    r = run_hook(repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_newest_main_still_allows_only_one_bump(repo):
    released = _release_on_the_server(repo, "origin/main")
    bump(repo, step(step(released, "z"), "z"))
    stage(repo, *_PLACES, "CHANGELOG.md")
    r = run_hook(repo)
    assert r.returncode == 1
    assert f"after {released} on main" in r.stdout


# --- `--range main` (the whole branch, used by CI) --------------------------------------------------------------

def _branch_with(repo: Path, *, program: bool = False, bump_kind: str | None = None, message: str = "work") -> None:
    git(repo, "switch", "-q", "-c", "feat-y")
    if program:
        append(repo, "backend/config.py", "\n# an edit\n")
    if bump_kind:
        bump(repo, step(current_version(repo), bump_kind))
    if not program and not bump_kind:
        append(repo, "CODE_OF_CONDUCT.md", "\nAn extra sentence.\n")
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


def test_range_a_change_to_the_launcher_script_counts_as_a_program_change(repo):
    git(repo, "switch", "-q", "-c", "feat-y")
    (repo / "seisa-launcher.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    commit_all(repo, "work")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 1
    assert "PROGRAM CHANGED WITHOUT A VERSION BUMP" in r.stdout and "seisa-launcher.sh" in r.stdout


def test_range_a_program_change_with_one_bump_passes(repo):
    _branch_with(repo, program=True, bump_kind="z")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 0, r.stdout + r.stderr


def test_range_a_change_outside_the_program_needs_no_bump(repo):
    _branch_with(repo)
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 0, r.stdout + r.stderr


def test_range_a_bump_without_a_program_change_fails(repo):
    _branch_with(repo, bump_kind="z")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 1
    assert "VERSION BUMPED WITHOUT A PROGRAM CHANGE" in r.stdout


def test_range_a_wrong_step_fails_even_with_a_program_change(repo):
    _branch_with(repo, program=True, bump_kind="skip")
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

    bump(repo, step(current_version(repo), "z"))
    commit_all(repo, "bump")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 0, r.stdout + r.stderr


# --- release notes: a new version needs its CHANGELOG entry and a matching release date -------------------------

DASH = chr(0x2014)    # built here so that this file itself passes the long dash rule


def test_a_bump_needs_its_changelog_entry(repo):
    set_version(repo, step(current_version(repo), "z"))    # the four places only
    stage(repo, *_PLACES)
    r = run_hook(repo)
    assert r.returncode == 1
    assert "CHANGELOG: no '## " in r.stdout


def test_the_release_date_must_match_the_changelog_entry(repo):
    bump(repo, step(current_version(repo), "z"))
    html = (repo / "frontend" / "index.html").read_text(encoding="utf-8")
    write(repo, "frontend/index.html", re.sub(r'(seisa-release-date" content=")[\d-]+', r"\g<1>2000-01-01", html))
    stage(repo, *_PLACES, "CHANGELOG.md")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "RELEASE DATE: CHANGELOG says" in r.stdout


def test_range_a_bump_needs_its_changelog_entry(repo):
    git(repo, "switch", "-q", "-c", "feat-y")
    append(repo, "backend/config.py", "\n# an edit\n")
    set_version(repo, step(current_version(repo), "z"))
    commit_all(repo, "bump without notes")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 1
    assert "CHANGELOG: no" in r.stdout


# --- `--range` also judges the lines a branch adds: a contributor's fork runs no hooks -----------------------------

def _branch_adding(repo: Path, line: str, message: str = "work") -> None:
    git(repo, "switch", "-q", "-c", "feat-y")
    for rel in PAIR_COC:
        append(repo, rel, f"\n{line}\n")
    commit_all(repo, message)


def test_range_rejects_a_long_dash_the_branch_adds(repo):
    _branch_adding(repo, f"one {DASH} two")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 1
    assert "LONG DASH" in r.stdout and "docs/pl/CODE_OF_CONDUCT.md" in r.stdout


def test_range_runs_the_privacy_scan_on_the_lines_the_branch_adds(repo, tmp_path):
    key, home = "ab" * 40, "/home" + "/someone/x"
    _branch_adding(repo, f"A key {key}, a path {home}.")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 1
    assert "looks like a real API key" in r.stdout and "home directory path" in r.stdout
    assert key not in r.stdout    # the value itself is never printed
    markers = tmp_path / "markers.txt"
    markers.write_text("host.leak.example\n", encoding="utf-8")
    git(repo, "switch", "-q", "main")
    git(repo, "branch", "-q", "-D", "feat-y")
    _branch_adding(repo, "A host host.leak.example.")
    r = run_hook(repo, "--range", "main", env={"SEISA_PRIVACY_MARKERS": str(markers)})
    assert r.returncode == 1
    assert "private names" in r.stdout and "leak.example" not in r.stdout


def test_range_does_not_judge_what_main_already_had(repo):
    git(repo, "switch", "-q", "-c", "feat-y")
    for rel in PAIR_COC:
        append(repo, rel, f"\nold {DASH} text\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--no-verify", "-m", "on main before the rule")    # the repo has no hooks enabled anyway
    git(repo, "switch", "-q", "main")
    git(repo, "merge", "-q", "--ff-only", "feat-y")
    git(repo, "switch", "-q", "-c", "feat-z")
    _both_languages(repo, "readme")
    git(repo, "commit", "-q", "-m", "A clean change")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 0, r.stdout + r.stderr


def test_range_leaves_the_commit_messages_of_a_branch_alone(repo):
    # The message rules are the maintainer's; a contributor's messages and co-author trailers stay as written.
    _branch_adding(repo, "A clean sentence.", message=f"Add a sentence {DASH} by hand\n\nCo-Authored-By: A <a@example.org>")
    r = run_hook(repo, "--range", "main")
    assert r.returncode == 0, r.stdout + r.stderr


def test_range_without_the_version_rule_still_judges_the_added_lines(repo):
    _branch_with(repo, program=True)    # a program change without a bump: what a contributor's pull request looks like
    r = run_hook(repo, "--range", "main", "--no-version-rule")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "version rule skipped" in r.stdout
    append(repo, "backend/config.py", f"\n# one {DASH} two\n")
    commit_all(repo, "more work")
    r = run_hook(repo, "--range", "main", "--no-version-rule")
    assert r.returncode == 1
    assert "LONG DASH" in r.stdout
    assert "VERSION BUMP" not in r.stdout


@pytest.mark.parametrize("args", [("--range",), ("--range", "main", "--other"), ("--range", "main", "--no-version-rule", "x")])
def test_range_rejects_a_wrong_command_line(base_repo, args):
    r = run_hook(base_repo, *args)
    assert r.returncode == 2
    assert "usage" in r.stderr


# --- the commit message (hook `commit-msg`, which calls `pre-commit --commit-msg`) ------------------------------

def _message(tmp_path: Path, text: str) -> str:
    f = tmp_path / "COMMIT_EDITMSG"
    f.write_text(text, encoding="utf-8")
    return str(f)


@pytest.mark.parametrize(("message", "expected"), [
    ("Add a thing\n\nA body.", None),
    (f"Add a thing {DASH} and more", "LONG DASH"),
    ("Add a thing\n\nCo-Authored-By: Claude <noreply@example.org>", "CO-AUTHORED-BY"),
    ("Add a thing\n\nco-authored-by: Someone <someone@example.org>", "CO-AUTHORED-BY"),
    ("Add a thing\n\nGenerated with Claude Code", "ATTRIBUTION"),
    (f"Add a thing\n# a git comment line with a dash {DASH}\n", None),    # '#' lines are git's own comments
    ("Fix " + "ab" * 40, "looks like a real API key"),
    ("Fix sk-or-v1-" + "a1" * 12, "looks like a real API key"),
    ("Fix a path " + "/Users" + "/someone/project", "home directory path"),
    ("Fix a path " + "/Users" + "/you/project", None),    # an obvious placeholder
])
def test_commit_message_rules(base_repo, tmp_path, message, expected):
    r = run_hook(base_repo, "--commit-msg", _message(tmp_path, message))
    if expected is None:
        assert r.returncode == 0, r.stdout + r.stderr
    else:
        assert r.returncode == 1
        assert expected in r.stdout


# Values are built at run time: the test file itself is scanned by the hook when it is committed.
_SECRET = "a1" * 16            # 32 characters with digits, like a real key
_UUID = "-".join(["12345678", "1234", "1234", "1234", "123456789abc"])    # the shape of a urlscan key

@pytest.mark.parametrize("line", [
    "OTX_API_KEY=" + _SECRET,                                     # a .env line
    "VIRUSTOTAL_API_KEY = " + _SECRET,
    'api_key = "' + _SECRET + '"',
    '"apiKey": "' + _SECRET + '"',                                # JSON
    "x-apikey: " + _SECRET,                                       # VirusTotal header
    "X-OTX-API-KEY: " + _SECRET,
    "API-Key: " + _SECRET,                                        # AbuseIPDB / urlscan style
    "Key: " + _SECRET,
    "Authorization: Bearer " + _SECRET,
    "client_secret=" + _SECRET,
    "GREYNOISE_TOKEN: " + _SECRET,
    "API-Key: " + _UUID,
    "api_key: " + "c3" * 32,                                      # 64 hex (VirusTotal, OTX, Cloudflare)
])
def test_secret_assignments_are_blocked_and_the_value_is_never_printed(base_repo, tmp_path, line):
    r = run_hook(base_repo, "--commit-msg", _message(tmp_path, "Fix a thing\n\n" + line))
    assert r.returncode == 1, line
    assert "looks like a real API key" in r.stdout
    assert _SECRET not in r.stdout and "c3" * 32 not in r.stdout and _UUID not in r.stdout


@pytest.mark.parametrize("line", [
    "OTX_API_KEY=",                                               # .env.example: an empty value
    "ABUSEIPDB_API_KEY=your-key-here",                            # a placeholder has no digit
    "api_key = settings.get_virustotal_api_key_value",            # an identifier
    "sha256 of the file: " + "ab" * 32,                           # a bare hash is not a key
    "The key: a plain sentence about something",
    "max_tokens=4096",
    "token = next_token_from_the_stream",
])
def test_harmless_lines_with_key_words_pass(base_repo, tmp_path, line):
    r = run_hook(base_repo, "--commit-msg", _message(tmp_path, "Fix a thing\n\n" + line))
    assert r.returncode == 0, line + "\n" + r.stdout + r.stderr


def test_privacy_markers_come_from_a_file_outside_the_repository(base_repo, tmp_path):
    markers = tmp_path / "markers.txt"
    markers.write_text("# my private names\nhost.leak.example\n!docs.host.leak.example\n", encoding="utf-8")
    env = {"SEISA_PRIVACY_MARKERS": str(markers)}
    r = run_hook(base_repo, "--commit-msg", _message(tmp_path, "Fix a problem on HOST.LEAK.EXAMPLE"), env=env)
    assert r.returncode == 1
    assert "one of your own host, domain or other private names" in r.stdout
    assert "leak.example" not in r.stdout.lower()    # the value itself is never printed
    r = run_hook(base_repo, "--commit-msg", _message(tmp_path, "Mention docs.host.leak.example"), env=env)    # an allowed string
    assert r.returncode == 0, r.stdout + r.stderr
    r = run_hook(base_repo, "--commit-msg", _message(tmp_path, "Fix a problem on host.leak.example"))    # no markers file: nothing to match
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_commit_msg_wrapper_passes_the_verdict_on(base_repo, tmp_path):
    def wrapper(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(base_repo / "scripts" / "hooks" / "commit-msg"), *args],
                              cwd=base_repo, env=GIT_ENV, capture_output=True, text=True)

    assert wrapper(_message(tmp_path, "Add a thing\n")).returncode == 0
    assert wrapper(_message(tmp_path, "Add a thing\n\nCo-Authored-By: X <x@example.org>\n")).returncode == 1
    assert wrapper().returncode != 0


def test_privacy_scan_of_added_lines(repo, tmp_path):
    markers = tmp_path / "markers.txt"
    markers.write_text("host.leak.example\n", encoding="utf-8")
    key, home = "ab" * 40, "/home" + "/someone/x"
    for rel in PAIR_COC:
        append(repo, rel, f"\nA key {key}, a path {home}, a host host.leak.example.\n")
    stage(repo, *PAIR_COC)
    r = run_hook(repo, env={"SEISA_PRIVACY_MARKERS": str(markers)})
    assert r.returncode == 1
    assert "looks like a real API key" in r.stdout and "home directory path" in r.stdout
    assert "private names" in r.stdout
    assert key not in r.stdout and "leak.example" not in r.stdout
    r = run_hook(repo)    # without the markers file only the generic checks run, and a note says so
    assert r.returncode == 1
    assert "private names" not in r.stdout and "no privacy markers file" in r.stdout


# --- real git: the hooks as git calls them (partial commits, -a, --amend, rebase, merge) -------------------------

@pytest.fixture
def hooked(repo) -> Path:
    git(repo, "config", "core.hooksPath", "scripts/hooks")
    return repo


def _head(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def _out(r: subprocess.CompletedProcess) -> str:
    return r.stdout + r.stderr


PAIR_COC = ("CODE_OF_CONDUCT.md", "docs/pl/CODE_OF_CONDUCT.md")
PAIR_README = ("README.md", "README.pl.md")


def _both_languages(repo: Path, name: str = "coc") -> list[str]:
    paths = list(PAIR_COC if name == "coc" else PAIR_README)
    for rel in paths:
        append(repo, rel, "\nAn extra sentence.\n")
    stage(repo, *paths)
    return paths


def test_git_runs_the_pre_commit_hook_and_a_rejected_commit_leaves_no_commit(hooked):
    before = _head(hooked)
    append(hooked, "backend/config.py", f"\n# one {DASH} two\n")
    stage(hooked, "backend/config.py")
    r = git(hooked, "commit", "-q", "-m", "Edit a comment", check=False)
    assert r.returncode != 0
    assert "LONG DASH" in _out(r)
    assert _head(hooked) == before


def test_git_runs_the_commit_msg_hook(hooked):
    before = _head(hooked)
    _both_languages(hooked)
    r = git(hooked, "commit", "-q", "-m", "Add a sentence\n\nCo-Authored-By: Claude <noreply@example.org>", check=False)
    assert r.returncode != 0
    assert "CO-AUTHORED-BY" in _out(r)
    assert _head(hooked) == before
    r = git(hooked, "commit", "-q", "-m", "Add a sentence", check=False)
    assert r.returncode == 0, _out(r)
    assert _head(hooked) != before


def test_a_partial_commit_judges_only_the_listed_paths(hooked):
    append(hooked, "backend/config.py", f"\n# one {DASH} two\n")
    stage(hooked, "backend/config.py")    # staged, but NOT part of the partial commit below
    for rel in PAIR_COC:
        append(hooked, rel, "\nAn extra sentence.\n")
    r = git(hooked, "commit", "-q", "-m", "Add a sentence", "--", *PAIR_COC, check=False)
    assert r.returncode == 0, _out(r)
    assert git(hooked, "show", "--name-only", "--format=", "HEAD").stdout.split() == list(PAIR_COC)
    assert git(hooked, "diff", "--cached", "--name-only").stdout.split() == ["backend/config.py"]
    r = git(hooked, "commit", "-q", "-m", "Edit a comment", "--", "backend/config.py", check=False)
    assert r.returncode != 0
    assert "LONG DASH" in _out(r)


def test_commit_a_judges_the_modified_tracked_files(hooked):
    append(hooked, "backend/config.py", f"\n# one {DASH} two\n")    # modified, not staged
    r = git(hooked, "commit", "-q", "-a", "-m", "Edit a comment", check=False)
    assert r.returncode != 0
    assert "LONG DASH" in _out(r)


def test_amend_is_judged_like_any_other_commit(hooked):
    _both_languages(hooked)
    git(hooked, "commit", "-q", "-m", "Add a sentence")
    first = _head(hooked)
    append(hooked, "backend/config.py", f"\n# one {DASH} two\n")
    stage(hooked, "backend/config.py")
    r = git(hooked, "commit", "-q", "--amend", "--no-edit", check=False)
    assert r.returncode != 0
    assert "LONG DASH" in _out(r)
    assert _head(hooked) == first
    git(hooked, "reset", "-q", "--hard")
    r = git(hooked, "commit", "-q", "--amend", "-m", "A better message", check=False)    # nothing staged, a clean message
    assert r.returncode == 0, _out(r)
    r = git(hooked, "commit", "-q", "--amend", "-m", "A message\n\nCo-Authored-By: C <c@example.org>", check=False)
    assert r.returncode != 0
    assert "CO-AUTHORED-BY" in _out(r)


def test_amending_a_bump_cannot_make_it_a_second_bump(hooked):
    git(hooked, "switch", "-q", "-c", "feat-x")
    first = step(current_version(hooked), "z")
    bump(hooked, first)
    stage(hooked, *_PLACES, "CHANGELOG.md")
    r = git(hooked, "commit", "-q", "-m", "Bump once", check=False)
    assert r.returncode == 0, _out(r)
    r = git(hooked, "commit", "-q", "--amend", "-m", "Bump once, reworded", check=False)
    assert r.returncode == 0, _out(r)
    bump(hooked, step(first, "z"))
    stage(hooked, *_PLACES, "CHANGELOG.md")
    r = git(hooked, "commit", "-q", "--amend", "--no-edit", check=False)
    assert r.returncode != 0
    assert "VERSION STEP" in _out(r)


def test_rebase_and_merge_work_with_the_hooks_enabled(hooked):
    git(hooked, "switch", "-q", "-c", "feat-x")
    _both_languages(hooked, "coc")
    git(hooked, "commit", "-q", "-m", "Edit the code of conduct")
    git(hooked, "switch", "-q", "main")
    _both_languages(hooked, "readme")
    git(hooked, "commit", "-q", "-m", "Edit the README")
    git(hooked, "switch", "-q", "feat-x")
    r = git(hooked, "rebase", "main", check=False)
    assert r.returncode == 0, _out(r)
    git(hooked, "switch", "-q", "main")
    r = git(hooked, "merge", "--no-ff", "-m", "Merge feat-x", "feat-x", check=False)
    assert r.returncode == 0, _out(r)


# --- `--range` on what GitHub checks out for a pull request: a merge commit of the branch into a main that moved on ---

def _pull_request_merge(repo: Path, bump_kind: str | None = None) -> None:
    git(repo, "switch", "-q", "-c", "feat-y")
    append(repo, "backend/config.py", "\n# an edit\n")
    if bump_kind:
        bump(repo, step(current_version(repo), bump_kind))
    commit_all(repo, "The feature")
    git(repo, "switch", "-q", "main")
    _both_languages(repo, "readme")
    git(repo, "commit", "-q", "-m", "Main moves on")
    git(repo, "update-ref", "refs/remotes/origin/main", "main")    # what `actions/checkout` with fetch-depth 0 provides
    git(repo, "switch", "-q", "-c", "pr-merge")
    git(repo, "merge", "--no-ff", "-q", "-m", "Merge pull request", "feat-y")


def test_range_on_a_pull_request_merge_commit_rejects_a_program_change_without_a_bump(repo):
    _pull_request_merge(repo)
    r = run_hook(repo, "--range", "origin/main")
    assert r.returncode == 1
    assert "PROGRAM CHANGED WITHOUT A VERSION BUMP" in r.stdout and "backend/config.py" in r.stdout


def test_range_on_a_pull_request_merge_commit_accepts_a_program_change_with_one_bump(repo):
    _pull_request_merge(repo, bump_kind="z")
    r = run_hook(repo, "--range", "origin/main")
    assert r.returncode == 0, r.stdout + r.stderr


def test_range_judges_the_branch_not_what_main_gained_since_it_was_cut(repo):
    git(repo, "switch", "-q", "-c", "feat-y")
    _both_languages(repo, "coc")
    git(repo, "commit", "-q", "-m", "Edit the code of conduct")    # the branch: documentation only
    git(repo, "switch", "-q", "main")
    append(repo, "backend/config.py", "\n# another release\n")
    bump(repo, step(current_version(repo), "z"))
    commit_all(repo, "Main gained a program change and a release")
    git(repo, "switch", "-q", "feat-y")
    r = run_hook(repo, "--range", "main")    # the branch is behind main: only its own changes count
    assert r.returncode == 0, r.stdout + r.stderr
    assert "program files changed: 0" in r.stdout

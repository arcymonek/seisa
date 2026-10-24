"""Tests for scripts/check_docs.py, the documentation check.

Each rule is tried on a small made-up project in a temporary folder: first in a good state (no error, no warning),
then broken in one place, which must give exactly the expected message. The tests are named after the rule number
(`test_rule05_...`), so the mutation test of a rule runs `-k rule05`: with the rule switched off those tests must fail.
`SEISA_CHECK_DOCS_UNDER_TEST=/path/to/copy` runs the same tests against another copy of the script.

The last group compares the script's static view of the code (it reads the code with `ast`, it never imports it) with
the real application, and runs the whole check on this repository.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = Path(os.environ.get("SEISA_CHECK_DOCS_UNDER_TEST") or ROOT / "scripts" / "check_docs.py")


def _load():
    spec = importlib.util.spec_from_file_location("seisa_check_docs_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cd = _load()


# --- the made-up project ------------------------------------------------------------------------------------------

def w(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def add(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.write_text(p.read_text(encoding="utf-8") + text, encoding="utf-8")


def both(root: Path, en: str, text_en: str, text_pl: str | None = None) -> None:
    """Appends to a document and to its Polish twin (the same text unless given)."""
    add(root, en, text_en)
    add(root, cd._twin(en), text_pl if text_pl is not None else text_en)


TINY_PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")

FACTS = (
    cd.Fact("History size", "backend/config.py", r"^HISTORY_MAX_ENTRIES = ([\d_]+)", ("docs/OPERATIONS.md",), ("entr", "wpis")),
    cd.Fact("E-mail source limit", "backend/config.py", r"^MAX_SOURCE_CHARS = ([\d_]+)", ("docs/API.md",)),
)


@pytest.fixture
def proj(tmp_path, monkeypatch) -> Path:
    """A complete, correct project: every required document, nothing PENDING."""
    monkeypatch.setattr(cd, "PENDING", frozenset())
    monkeypatch.setattr(cd, "FACTS", FACTS)
    r = tmp_path / "p"
    w(r, "backend/__init__.py", "")
    w(r, "backend/routers/__init__.py", "")
    w(r, "backend/main.py", (
        "from fastapi import FastAPI\nfrom backend.routers import items\n"
        'app = FastAPI(title="T", docs_url=None, redoc_url=None)\n'
        'app.include_router(items.router, prefix="/api")\n'
    ))
    w(r, "backend/routers/items.py", (
        "from fastapi import APIRouter\nrouter = APIRouter()\n\n"
        '@router.get("/items")\ndef list_items():\n    return []\n\n'
        '@router.post("/items/{item_id}")\nasync def save(item_id: str):\n    return {}\n'
    ))
    w(r, "backend/config.py", (
        "HISTORY_MAX_ENTRIES = 100\nMAX_SOURCE_CHARS = 3_000_000\n\n"
        "class Settings(BaseSettings):\n    model_config = SettingsConfigDict()\n"
        '    foo_api_key: str = ""\n    foo_model: str = "x"\n'
    ))
    w(r, ".env.example", "# keys\nFOO_API_KEY=\nFOO_MODEL=x\n")
    w(r, "frontend/index.html", (
        '<nav><button class="tab-btn" data-tab="lookup">IP</button>\n'
        '<button class="tab-btn" data-tab="history" data-i18n="tab.history">History</button></nav>\n'
    ))
    w(r, "frontend/i18n/en.json", json.dumps({"tab.history": "History"}))
    w(r, "frontend/i18n/pl.json", json.dumps({"tab.history": "Historia"}))
    w(r, "frontend/js/app.js", "export const x = 1;\n")
    w(r, "frontend/js/about.js", 'const AUTHOR_EMAIL = "github@arkadiuszpolak.pl";\n')
    w(r, "scripts/tool.py", "print(1)\n")
    (r / "docs" / "images").mkdir(parents=True)
    (r / "docs" / "images" / "ip_en.png").write_bytes(TINY_PNG)
    (r / "docs" / "images" / "ip_pl.png").write_bytes(TINY_PNG)
    for en, pl in cd.DOC_PAIRS:
        w(r, en, f"{cd.switch_line(en)}\n\n# {Path(en).stem}\n\nOne sentence.\n")
        w(r, pl, f"{cd.switch_line(pl)}\n\n# {Path(en).stem}\n\nJedno zdanie.\n")
    for rel in ("README.md", "README.pl.md"):
        lang = "en" if rel == "README.md" else "pl"
        w(r, rel, (
            f'<p align="center">\n  <b>Seisa 1.2.3</b><br>\n  {cd.switch_line(rel)}\n</p>\n\n# Seisa\n\n'
            f"![IP tab](docs/images/ip_{lang}.png)\n\n"
            "| Tab | What |\n|---|---|\n"
            f"| IP | x |\n| {'History' if lang == 'en' else 'Historia'} | y |\n\n"
            "| Key | What |\n|---|---|\n| `FOO_API_KEY` | a |\n| `FOO_MODEL` | b |\n"
        ))
    w(r, "AGENTS.md", "# Agents\n")
    w(r, "CHANGELOG.md", "# Changelog\n\nSee [README.md](README.md).\n")
    both(r, "docs/API.md", "\n## Routes\n\n- `GET /api/items`\n- `POST /api/items/{item_id}`\n- `GET /openapi.json`\n\n"
         "A source may have 3 000 000 characters.\n")
    both(r, "docs/USER_GUIDE.md", "\n## 1. IP tab\n\nx\n\n## 2. History tab\n\ny\n", "\n## 1. Zakładka IP\n\nx\n\n## 2. Zakładka Historia\n\ny\n")
    both(r, "docs/OPERATIONS.md", "\nHistory keeps 100 entries.\n", "\nHistoria trzyma 100 wpisów.\n")
    both(r, "docs/ARCHITECTURE.md", "\n- `backend/main.py`, `routers/items.py`, `config.py`\n- `app.js`, `about.js`\n")
    both(r, "docs/DEVELOPMENT.md", "\n- `scripts/tool.py`\n")
    return r


def run(root: Path, **kw):
    return cd.run(root, **kw)


def errors(root: Path) -> list[str]:
    return run(root).errors


def only_error(root: Path, fragment: str) -> None:
    errs = errors(root)
    assert len(errs) == 1 and fragment in errs[0], errs


def test_the_made_up_project_is_clean(proj):
    rep = run(proj)
    assert rep.errors == [] and rep.warnings == []


# --- rule 1: pairs --------------------------------------------------------------------------------------------------

def test_rule01_a_missing_twin(proj):
    (proj / "docs" / "pl" / "SECURITY.md").unlink()
    errs = errors(proj)
    assert "docs/pl/SECURITY.md is missing (SECURITY.md exists): a document and its twin come together" in errs, errs


def test_rule01_a_missing_twin_counts_even_while_pending(proj, monkeypatch):
    monkeypatch.setattr(cd, "PENDING", frozenset({"SECURITY.md", "docs/pl/SECURITY.md"}))
    (proj / "SECURITY.md").unlink()
    errs = errors(proj)
    assert "SECURITY.md is missing (docs/pl/SECURITY.md exists): a document and its twin come together" in errs, errs
    (proj / "docs" / "pl" / "SECURITY.md").unlink()    # neither written yet: fine while pending
    assert errors(proj) == []


@pytest.mark.parametrize(("en", "pl", "what"), [
    ("\n## Extra\n", "\nTekst.\n", "heading structure"),
    ("\n### Level three\n", "\n## Poziom dwa\n", "heading structure"),
    ("\n```bash\nls\n```\n", "\nls\n", "code blocks"),
    ("\n| a |\n|---|\n| 1 |\n", "\n| a |\n|---|\n\n| b |\n|---|\n", "tables"),
    ("\n| a |\n|---|\n| 1 |\n| 2 |\n", "\n| a |\n|---|\n| 1 |\n", "table rows"),
    ("\n![x](docs/images/ip_en.png)\n", "\nx\n", "images"),
])
def test_rule01_the_twins_must_have_the_same_shape(proj, en, pl, what):
    both(proj, "CONTRIBUTING.md", en, pl)
    only_error(proj, f"CONTRIBUTING.md and docs/pl/CONTRIBUTING.md have a different {what}" if what == "heading structure"
               else f"different number of {what}")


def test_rule01_a_heading_inside_a_code_block_is_not_a_heading(proj):
    both(proj, "CONTRIBUTING.md", "\n```bash\n# a comment\n```\n", "\n```bash\n# komentarz\n```\n")
    assert errors(proj) == []


# --- rule 2: every document has a twin -------------------------------------------------------------------------------

@pytest.mark.parametrize("rel", ["NOTES.md", "docs/NOTES.md", "docs/pl/NOTATKI.md"])
def test_rule02_a_document_outside_the_pairs(proj, rel):
    w(proj, rel, "# x\n")
    only_error(proj, f"{rel} is not in DOC_PAIRS")


def test_rule02_files_elsewhere_and_the_exceptions_are_fine(proj):
    w(proj, ".github/pull_request_template.md", "## What\n")
    w(proj, "backend/prompts/guide.md", "# Guide\n")
    assert errors(proj) == []


def test_rule02_only_files_git_tracks_count(proj):
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    subprocess.run(["git", "add", "-A"], cwd=proj, check=True)
    w(proj, "NOTES.local.md", "# local, never added\n\nSee [x](nowhere.md).\n")
    assert errors(proj) == []
    subprocess.run(["git", "add", "NOTES.local.md"], cwd=proj, check=True)
    errs = errors(proj)
    assert any("NOTES.local.md is not in DOC_PAIRS" in e for e in errs), errs


# --- rule 3: links -----------------------------------------------------------------------------------------------------

def test_rule03_a_dead_link(proj):
    both(proj, "docs/API.md", "\nSee [x](missing.md).\n")
    errs = errors(proj)
    assert any("docs/API.md" in e and "dead link missing.md" in e for e in errs), errs


def test_rule03_a_dead_link_in_a_file_without_a_twin(proj):
    add(proj, "CHANGELOG.md", "\nSee [x](docs/NOPE.md).\n")
    only_error(proj, "CHANGELOG.md:5: dead link docs/NOPE.md")


def test_rule03_anchors(proj):
    add(proj, "AGENTS.md", "\n## Zażółć gęślą `jaźń`!\n\n[ok](#zażółć-gęślą-jaźń) [ok2](docs/API.md#routes) [bad](docs/API.md#nope)\n")
    only_error(proj, "dead anchor docs/API.md#nope")


def test_rule03_an_image_src(proj):
    add(proj, "AGENTS.md", '\n<img src="docs/images/none.png" alt="x">\n')
    only_error(proj, "dead link docs/images/none.png")


def test_rule03_external_links_and_code_are_not_checked(proj):
    add(proj, "AGENTS.md", "\n[a](https://example.org/x) `[b](nope.md)`\n\n```\n[c](nope.md)\n```\n")
    assert errors(proj) == []


# --- rule 4: images ---------------------------------------------------------------------------------------------------

def test_rule04_an_image_needs_alt_text(proj):
    add(proj, "AGENTS.md", "\n![](docs/images/ip_en.png)\n")
    only_error(proj, "has no alt text")


def test_rule04_an_html_image_needs_alt_text(proj):
    add(proj, "AGENTS.md", '\n<img src="docs/images/ip_en.png">\n')
    only_error(proj, "has no alt text")


def test_rule04_an_unused_image(proj, monkeypatch):
    (proj / "docs" / "images" / "old.png").write_bytes(TINY_PNG)
    only_error(proj, "docs/images/old.png is not used")
    monkeypatch.setattr(cd, "PENDING", frozenset({"AGENTS.md"}))    # while documents are still being written: a warning
    rep = run(proj)
    assert rep.errors == [] and any("old.png" in x for x in rep.warnings)


# --- rule 5: routes ---------------------------------------------------------------------------------------------------

def test_rule05_a_route_without_documentation(proj):
    add(proj, "backend/routers/items.py", '\n@router.delete("/items/{item_id}")\ndef drop(item_id: str):\n    return {}\n')
    errs = errors(proj)
    assert sorted(errs) == sorted([
        "docs/API.md: route DELETE /api/items/{item_id} is not documented",
        "docs/pl/API.md: route DELETE /api/items/{item_id} is not documented",
    ])


def test_rule05_documentation_of_a_route_that_does_not_exist(proj):
    both(proj, "docs/API.md", "\n- `PUT /api/items`\n")
    assert "docs/API.md: documents PUT /api/items, which the app does not have" in errors(proj)


def test_rule05_the_default_fastapi_pages_count_when_switched_on(proj):
    w(proj, "backend/main.py", (proj / "backend" / "main.py").read_text().replace(", docs_url=None, redoc_url=None", ""))
    errs = errors(proj)
    assert "docs/API.md: route GET /docs is not documented" in errs
    assert "docs/API.md: route GET /redoc is not documented" in errs


def test_rule05_a_router_prefix_counts(proj):
    w(proj, "backend/main.py", (proj / "backend" / "main.py").read_text().replace('prefix="/api"', 'prefix="/api/v"'))
    assert "docs/API.md: route GET /api/v/items is not documented" in errors(proj)


def test_rule05_skips_a_pending_file(proj, monkeypatch):
    monkeypatch.setattr(cd, "PENDING", frozenset({"docs/API.md", "docs/pl/API.md"}))
    add(proj, "backend/routers/items.py", '\n@router.get("/new")\ndef new():\n    return {}\n')
    assert errors(proj) == []


# --- rule 6: .env keys -----------------------------------------------------------------------------------------------

def test_rule06_a_settings_field_missing_in_env_example_and_readmes(proj):
    add(proj, "backend/config.py", '    bar_api_key: str = ""\n')
    errs = errors(proj)
    assert ".env.example lacks BAR_API_KEY (a field of Settings in backend/config.py)" in errs
    assert "README.md: the key table lacks `BAR_API_KEY`" in errs
    assert "README.pl.md: the key table lacks `BAR_API_KEY`" in errs


def test_rule06_a_key_only_in_env_example(proj):
    add(proj, ".env.example", "OLD_KEY=\n")
    only_error(proj, ".env.example has OLD_KEY, which Settings")


def test_rule06_a_key_only_in_the_readme_table(proj):
    for rel in ("README.md", "README.pl.md"):
        add(proj, rel, "| `OLD_API_KEY` | c |\n")
    errs = errors(proj)
    assert "README.md: the key table names `OLD_API_KEY`, which Settings does not read" in errs


# --- rule 7: tabs -----------------------------------------------------------------------------------------------------

def test_rule07_a_tab_without_a_user_guide_section(proj):
    w(proj, "docs/USER_GUIDE.md", (proj / "docs" / "USER_GUIDE.md").read_text().replace("History tab", "Past tab"))
    only_error(proj, "docs/USER_GUIDE.md: no section 'History tab' for the tab 'history'")


def test_rule07_a_tab_without_a_readme_row(proj):
    w(proj, "README.pl.md", (proj / "README.pl.md").read_text().replace("| Historia |", "| Dawne |"))
    only_error(proj, "README.pl.md: the tab table has no row for the tab 'Historia' (history)")


def test_rule07_a_new_tab_must_be_mapped(proj):
    add(proj, "frontend/index.html", '<button class="tab-btn" data-tab="extra">Extra</button>\n')
    errs = errors(proj)
    assert any("tab 'extra' has no entry in USER_GUIDE_SECTIONS" in e for e in errs), errs
    assert "README.md: the tab table has no row for the tab 'Extra' (extra)" in errs


def test_rule07_ip_is_not_found_inside_abuseipdb(proj):
    for rel in ("README.md", "README.pl.md"):
        w(proj, rel, (proj / rel).read_text().replace("| IP | x |", "| AbuseIPDB | x |"))
    assert "README.md: the tab table has no row for the tab 'IP' (lookup)" in errors(proj)


# --- rule 8: modules --------------------------------------------------------------------------------------------------

def test_rule08_an_unnamed_module(proj):
    w(proj, "backend/routers/extra.py", "")
    only_error(proj, "backend/routers/extra.py is not named in docs/ARCHITECTURE.md or docs/DEVELOPMENT.md")


def test_rule08_a_short_name_counts_only_when_it_is_unique(proj):
    w(proj, "scripts/config.py", "")    # now `config.py` in ARCHITECTURE.md no longer says which one
    errs = errors(proj)
    assert "backend/config.py is not named in docs/ARCHITECTURE.md or docs/DEVELOPMENT.md" in errs
    assert "scripts/config.py is not named in docs/ARCHITECTURE.md or docs/DEVELOPMENT.md" in errs


def test_rule08_a_name_inside_a_longer_name_does_not_count(proj):
    w(proj, "frontend/js/app.js", "")
    w(proj, "docs/ARCHITECTURE.md", (proj / "docs" / "ARCHITECTURE.md").read_text().replace("`app.js`", "`webapp.js`"))
    w(proj, "docs/pl/ARCHITECTURE.md", (proj / "docs" / "pl" / "ARCHITECTURE.md").read_text().replace("`app.js`", "`webapp.js`"))
    only_error(proj, "frontend/js/app.js is not named")


def test_rule08_only_a_warning_while_one_of_the_two_files_is_pending(proj, monkeypatch):
    monkeypatch.setattr(cd, "PENDING", frozenset({"docs/DEVELOPMENT.md", "docs/pl/DEVELOPMENT.md"}))
    rep = run(proj)
    assert rep.errors == [] and rep.warnings == ["scripts/tool.py is not named in docs/ARCHITECTURE.md or docs/DEVELOPMENT.md"]


# --- rule 9: facts ----------------------------------------------------------------------------------------------------

def test_rule09_a_changed_limit_without_a_documentation_change(proj):
    w(proj, "backend/config.py", (proj / "backend" / "config.py").read_text().replace("= 100", "= 150"))
    errs = errors(proj)
    assert sorted(errs) == sorted([
        "docs/OPERATIONS.md: does not state 'History size' = 150 (from backend/config.py)",
        "docs/pl/OPERATIONS.md: does not state 'History size' = 150 (from backend/config.py)",
    ])


@pytest.mark.parametrize("written", ["3000000", "3,000,000", "3 000 000", "3\u00a0000\u00a0000"])
def test_rule09_big_numbers_in_any_usual_form(proj, written):
    for rel in ("docs/API.md", "docs/pl/API.md"):
        w(proj, rel, (proj / rel).read_text().replace("3 000 000", written))
    assert errors(proj) == []


def test_rule09_a_bigger_number_does_not_count(proj):
    for rel in ("docs/API.md", "docs/pl/API.md"):
        w(proj, rel, (proj / rel).read_text().replace("3 000 000", "13 000 000"))
    assert len(errors(proj)) == 2


def test_rule09_a_small_number_needs_its_unit(proj):
    w(proj, "docs/pl/OPERATIONS.md", (proj / "docs" / "pl" / "OPERATIONS.md").read_text().replace("100 wpisów", "100 razy"))
    only_error(proj, "docs/pl/OPERATIONS.md: does not state 'History size' = 100")


def test_rule09_a_fact_that_moved_in_the_code(proj):
    w(proj, "backend/config.py", (proj / "backend" / "config.py").read_text().replace("HISTORY_MAX_ENTRIES", "HISTORY_LIMIT"))
    only_error(proj, "FACTS: 'History size' not found in backend/config.py")


# --- rule 10: version, long dash, language switch ----------------------------------------------------------------------

def test_rule10_no_version_in_docs(proj):
    both(proj, "docs/OPERATIONS.md", "\nSince Seisa 2.4.30.\n")
    errs = errors(proj)
    assert any("docs/OPERATIONS.md: contains a version number" in e for e in errs), errs
    assert any("docs/pl/OPERATIONS.md: contains a version number" in e for e in errs), errs


def test_rule10_no_long_dash(proj):
    add(proj, "AGENTS.md", "\none " + chr(0x2014) + " two\n")
    only_error(proj, "AGENTS.md:3: long dash (U+2014)")


@pytest.mark.parametrize("rel", ["docs/pl/SECURITY.md", "CONTRIBUTING.md", "README.md"])
def test_rule10_the_language_switch_line(proj, rel):
    text = (proj / rel).read_text()
    w(proj, rel, text.replace(cd.switch_line(rel), ""))
    only_error(proj, f"{rel}: the first line must be the language switch")


def test_rule10_switch_lines_point_to_the_twin():
    assert cd.switch_line("docs/USER_GUIDE.md") == "**English** | [Polski](pl/USER_GUIDE.md)"
    assert cd.switch_line("docs/pl/USER_GUIDE.md") == "[English](../USER_GUIDE.md) | **Polski**"
    assert cd.switch_line("CONTRIBUTING.md") == "**English** | [Polski](docs/pl/CONTRIBUTING.md)"
    assert cd.switch_line("docs/pl/CONTRIBUTING.md") == "[English](../../CONTRIBUTING.md) | **Polski**"
    assert cd.switch_line("README.pl.md") == "[English](README.md) | **Polski**"


# --- rule 11: e-mail addresses -----------------------------------------------------------------------------------------

def test_rule11_a_private_address(proj):
    add(proj, "AGENTS.md", "\nWrite to someone@private-domain.eu.\n")
    only_error(proj, "AGENTS.md:3: e-mail address not on ALLOWED_EMAILS")


def test_rule11_the_contact_and_example_addresses_are_fine(proj):
    add(proj, "AGENTS.md", "\ngithub@arkadiuszpolak.pl, user@example.org, a@mail.example, b@host.test\n")
    assert errors(proj) == []


def test_rule11_the_info_tab_too(proj):
    w(proj, "frontend/js/about.js", 'const AUTHOR_EMAIL = "me@private-domain.eu";\n')
    only_error(proj, "frontend/js/about.js:1: e-mail address not on ALLOWED_EMAILS")


# --- rule 12: required documents ----------------------------------------------------------------------------------------

def test_rule12_a_required_document_is_missing(proj):
    (proj / "AGENTS.md").unlink()
    only_error(proj, "AGENTS.md is missing (REQUIRED_DOCS)")


def test_rule12_a_pending_document_may_be_missing(proj, monkeypatch):
    monkeypatch.setattr(cd, "PENDING", frozenset({"AGENTS.md"}))
    (proj / "AGENTS.md").unlink()
    assert errors(proj) == []


# --- rules 13 and 14: readability (warnings) ----------------------------------------------------------------------------

def test_rule13_a_wall_of_text_is_a_warning(proj):
    both(proj, "docs/OPERATIONS.md", "\n" + "word " * 95 + "\n")
    rep = run(proj)
    assert rep.errors == []
    assert any("docs/OPERATIONS.md" in x and "a paragraph of 1 lines / 95 words" in x for x in rep.warnings), rep.warnings


def test_rule13_a_list_is_not_a_paragraph(proj):
    both(proj, "docs/OPERATIONS.md", "\n" + "".join(f"- item {i} with a few words\n" for i in range(30)))
    assert run(proj).warnings == []


def test_rule14_a_long_file_needs_a_table_of_contents(proj):
    both(proj, "docs/OPERATIONS.md", "\n" + "\n\n".join(f"Line {i}." for i in range(90)) + "\n")
    rep = run(proj)
    assert any("docs/OPERATIONS.md:" in x and "no table of contents" in x for x in rep.warnings), rep.warnings
    for rel, title in (("docs/OPERATIONS.md", "Contents"), ("docs/pl/OPERATIONS.md", "Spis treści")):
        w(proj, rel, (proj / rel).read_text().replace("# OPERATIONS\n", f"# OPERATIONS\n\n## {title}\n", 1))
    assert not [x for x in run(proj).warnings if "table of contents" in x]


# --- rule 15: external links (only with --external) -----------------------------------------------------------------------

def test_rule15_external_links_only_on_request(proj, monkeypatch):
    add(proj, "AGENTS.md", "\n[a](https://www.virustotal.com/gone) [b](https://www.virustotal.com/ok)\n")
    calls = []

    class Answer:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if req.full_url.endswith("gone"):
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
        return Answer()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert errors(proj) == [] and calls == []    # never without the switch
    rep = run(proj, external=True)
    assert rep.errors == ["external link https://www.virustotal.com/gone: HTTP 404"]


@pytest.mark.parametrize(("text", "expected"), [
    ("See https://example.org/x.", set()),                                        # reserved example domain
    ("Open http://127.0.0.1:54321 or http://localhost:9999/api.", set()),          # this computer
    ("A host like https://host.tld/ or https://seisa.local or https://a.test/x", set()),
    ("Template https://urlscan.io/result/<uuid>/ and https://www.abuseipdb.com/check/{ip}", set()),
    ("In code `https://www.virustotal.com/x` only", set()),
    ("```\ncurl https://www.virustotal.com/api\n```\n", set()),
    ("Read https://www.abuseipdb.com/reporting-policy; then report.", {"https://www.abuseipdb.com/reporting-policy"}),
    ("[FAQ][FAQ]\n\n[FAQ]: https://www.contributor-covenant.org/faq", {"https://www.contributor-covenant.org/faq"}),
    ("[https://www.virustotal.com][vt] in a reference link", {"https://www.virustotal.com"}),
    ("Link [x](https://arkadiuszpolak.pl) and <https://openrouter.ai>.", {"https://arkadiuszpolak.pl", "https://openrouter.ai"}),
    ("A stem without a placeholder https://www.abuseipdb.com/check/ counts", {"https://www.abuseipdb.com/check/"}),
])
def test_rule15_which_addresses_are_visited(text, expected):
    assert cd.external_urls(text) == expected


# --- the command line -------------------------------------------------------------------------------------------------

def test_the_command_line(monkeypatch, capsys):
    assert cd.main(["--nope"]) == 2
    rep = cd.Report()
    monkeypatch.setattr(cd, "run", lambda root, external=False, contributor=False: rep)
    assert cd.main([]) == 0
    rep.errors.append("x")
    assert cd.main([]) == 1
    assert "1 error(s)" in capsys.readouterr().out


# --- the static view against the real application, and this repository --------------------------------------------------

def test_static_routes_are_the_routes_of_the_real_app():
    from backend.main import app

    runtime = {(m.upper(), path) for path, ops in app.openapi()["paths"].items() for m in ops}
    runtime |= {("GET", url) for url in (app.openapi_url, app.docs_url, app.redoc_url) if url}
    if app.docs_url:
        runtime.add(("GET", app.docs_url + "/oauth2-redirect"))
    assert cd.app_routes(ROOT) == runtime


def test_static_settings_are_the_real_settings():
    from backend.config import Settings

    assert cd.settings_keys(ROOT) == {name.upper() for name in Settings.model_fields}


def test_every_fact_is_found_in_the_code():
    import backend.config as config
    import backend.ratelimit as ratelimit
    import backend.report_utils as report_utils

    values = {f.label: cd.fact_value(ROOT, f) for f in cd.FACTS}
    assert None not in values.values(), values
    assert values["History size"] == config.HISTORY_MAX_ENTRIES
    assert values["E-mail source limit"] == config.MAX_SOURCE_CHARS
    assert values["AbuseIPDB comment limit"] == report_utils.MAX_COMMENT_CHARS
    assert values["VirusTotal requests per day"] == ratelimit.VT_PER_DAY


def test_every_tab_is_mapped():
    assert [t for t, _ in cd.tabs(ROOT)] == list(cd.USER_GUIDE_SECTIONS)


def test_pending_names_only_required_documents():
    assert set(cd.REQUIRED_DOCS) >= cd.PENDING


def test_this_repository_passes():
    rep = cd.run(ROOT)
    assert rep.errors == [], "\n".join(rep.errors)


def test_the_hook_and_this_script_agree_on_the_pairs():
    hook = (ROOT / "scripts" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert "DOC_PAIRS" in hook and not re.search(r"docs/\(en\|pl\)", hook)


# --- --contributor: the maintainer's rules become a list, the form rules still fail -----------------------------------
# Expected values come from the rules in the module docstring of scripts/check_docs.py, not from a run of the script.

HEADING = "To be completed by the maintainer"


def contributor_run(root: Path):
    return cd.run(root, contributor=True)


def test_contributor_default_mode_is_unchanged_by_the_new_field(proj):
    (proj / "docs" / "pl" / "SECURITY.md").unlink()
    rep = run(proj)
    assert rep.maintainer == []
    assert "docs/pl/SECURITY.md is missing (SECURITY.md exists): a document and its twin come together" in rep.errors


def test_contributor_a_clean_project_stays_clean(proj):
    rep = contributor_run(proj)
    assert rep.errors == [] and rep.warnings == [] and rep.maintainer == []


@pytest.mark.parametrize("breakage", ["pair", "unpaired", "route", "env", "tab", "module", "fact"])
def test_contributor_consistency_problems_are_listed_not_failed(proj, breakage):
    if breakage == "pair":
        add(proj, "CONTRIBUTING.md", "\n## Extra\n")
        expected = "heading structure"
    elif breakage == "unpaired":
        w(proj, "docs/NOTES.md", "# x\n")
        expected = "docs/NOTES.md is not in DOC_PAIRS"
    elif breakage == "route":
        add(proj, "backend/routers/items.py", '\n@router.delete("/items")\ndef gone():\n    return None\n')
        expected = "DELETE /api/items"
    elif breakage == "env":
        add(proj, ".env.example", "ZZ_NEW=1\n")
        expected = "ZZ_NEW"
    elif breakage == "tab":
        add(proj, "frontend/index.html", '<button data-tab="logs">Logs</button>\n')
        expected = "logs"
    elif breakage == "module":
        w(proj, "scripts/new_tool.py", "print(2)\n")
        expected = "scripts/new_tool.py is not named"
    else:
        w(proj, "backend/config.py", (proj / "backend/config.py").read_text(encoding="utf-8").replace("= 100", "= 250"))
        expected = "History size"
    assert errors(proj), "the strict mode must fail on this breakage"      # the same breakage fails by default ...
    rep = contributor_run(proj)
    assert rep.errors == [], rep.errors                                    # ... and only gets listed for a contributor
    assert any(expected in m for m in rep.maintainer), rep.maintainer


@pytest.mark.parametrize("breakage", ["dead_link", "dead_anchor", "long_dash", "alt", "version", "switch", "email", "required"])
def test_contributor_form_errors_still_fail(proj, breakage):
    if breakage == "dead_link":
        both(proj, "CONTRIBUTING.md", "\nSee [x](nowhere.md).\n")
        expected = "dead link nowhere.md"
    elif breakage == "dead_anchor":
        both(proj, "CONTRIBUTING.md", "\nSee [x](#nothing-here).\n")
        expected = "dead anchor #nothing-here"
    elif breakage == "long_dash":
        add(proj, "CONTRIBUTING.md", "\none \u2014 two\n")
        expected = "long dash (U+2014)"
    elif breakage == "alt":
        both(proj, "CONTRIBUTING.md", "\n![](docs/images/ip_en.png)\n")
        expected = "has no alt text"
    elif breakage == "version":
        both(proj, "docs/API.md", "\nSeisa 9.9.9 does this.\n")
        expected = "contains a version number"
    elif breakage == "switch":
        t = (proj / "SECURITY.md").read_text(encoding="utf-8")
        w(proj, "SECURITY.md", t.replace(cd.switch_line("SECURITY.md"), "English"))
        expected = "the first line must be the language switch"
    elif breakage == "email":
        both(proj, "CONTRIBUTING.md", "\nWrite to someone@gmail.com.\n")
        expected = "e-mail address not on ALLOWED_EMAILS"
    else:
        (proj / "CHANGELOG.md").unlink()
        expected = "CHANGELOG.md is missing (REQUIRED_DOCS)"
    rep = contributor_run(proj)
    assert any(expected in e for e in rep.errors), (rep.errors, rep.maintainer)


def test_contributor_form_errors_fail_next_to_listed_consistency_problems(proj):
    add(proj, "CONTRIBUTING.md", "\n## Extra\n")                  # the maintainer's: listed
    both(proj, "README.md", "\nSee [x](nowhere.md).\n", "\nZob. [x](nowhere.md).\n")   # form: fails
    rep = contributor_run(proj)
    assert [e for e in rep.errors if "dead link" in e] and not [e for e in rep.errors if "heading structure" in e]
    assert any("heading structure" in m for m in rep.maintainer)


def test_contributor_cli_prints_the_heading_and_exits_zero_or_one(proj, tmp_path):
    # the script locates the project from its own path, so a copy of it goes into the made-up project
    shutil_copy = proj / "scripts" / "check_docs.py"
    shutil_copy.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    add(proj, "docs/ARCHITECTURE.md", "\n`scripts/check_docs.py`\n")
    add(proj, "docs/pl/ARCHITECTURE.md", "\n`scripts/check_docs.py`\n")
    add(proj, "CONTRIBUTING.md", "\n## Extra\n")
    strict = subprocess.run(["python3", str(shutil_copy)], capture_output=True, text=True)
    assert strict.returncode == 1 and HEADING not in strict.stdout
    soft = subprocess.run(["python3", str(shutil_copy), "--contributor"], capture_output=True, text=True)
    assert soft.returncode == 0, soft.stdout
    assert HEADING in soft.stdout and "heading structure" in soft.stdout and "ERROR:" not in soft.stdout
    both(proj, "README.md", "\nSee [x](nowhere.md).\n")
    hard = subprocess.run(["python3", str(shutil_copy), "--contributor"], capture_output=True, text=True)
    assert hard.returncode == 1 and "ERROR:" in hard.stdout and "dead link" in hard.stdout


def test_contributor_unknown_flag_is_a_usage_error():
    p = subprocess.run(["python3", str(SCRIPT), "--contributer"], capture_output=True, text=True)
    assert p.returncode == 2 and "usage:" in p.stderr

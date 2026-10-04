# Forking and extending

**English** | [Polski](../pl/extending.md) · [Documentation index](index.md) · [README](../../README.md)

## For developers and forks

Everything you need to decide about a fork and to work on one is in this documentation (this page, [Architecture and design](architecture.md) and [API reference](api.md)); the README is the short entry point. The two files directly in `docs/` are prompt context for the LLM, summarised where they matter (the [AbuseIPDB](tabs.md#abuseipdb) and [Email](tabs.md#email) tabs).

### Should you fork?

| You may | You may not |
|---|---|
| use, copy, modify and distribute Seisa (forks included) for noncommercial purposes: personal, hobby, educational and research use, and use by charitable, educational, public and government organisations | use it commercially: selling it, commercial forks, work for the profit of a company (this needs a separate permission of the author) |
| keep the `LICENSE` file and its "Required Notice" line in your fork | submit code changes upstream: pull requests are not accepted (issues with ideas and bug reports are welcome; see [CONTRIBUTING.md](../../CONTRIBUTING.md)) |

This is a *source-available* license, not an open-source license in the OSI sense. A fork is a reasonable choice if you want to keep a local, dependency-light tool and adapt it: add a threat-intel source, a language, a tab, another LLM provider. It is a poor choice if you need multi-user access, authentication, remote hosting or a database; those are non-goals (see [Design decisions and non-goals](architecture.md#design-decisions-and-non-goals)).

### How to extend

#### Add a threat-intel service

1. `backend/services/<name>.py`: subclass `IntelService` (`backend/services/base.py`) with a `name`, `query_ip` and `query_domain`; use `fetch_json` for HTTP so errors are readable and rate-limit headers are observed.
2. Register it in `SERVICE_REGISTRY` in `backend/aggregator.py`.
3. Add its key to `Settings` in `backend/config.py` and to `.env.example`; show its status in `backend/routers/about.py`.
4. If it should influence the score, add a `CREDIBILITY` entry and a `score_<name>` function in `backend/scoring.py` and register it in `compute_risk_score`.
5. Frontend: the service metadata in `frontend/js/lookup-result.js` and the `ALL_SERVICES` list in `frontend/js/lookup.js`; Markdown: the title and `SERVICE_ORDER` in `backend/markdown_report.py`.
6. Optionally its free-plan limit in `backend/api_limits.py`.
7. i18n keys (`md.service.<name>` and any messages) in both catalogs; a mocked answer in `scripts/api_harness.py`; run the checks below.

#### Add a language

1. Add `frontend/i18n/<xx>.json` and `backend/locales/<xx>.json` with the same keys as the English ones (`scripts/check_i18n.py` compares keys, `{placeholders}` and plural forms; the required plural suffixes per language are in `PLURALS_REQUIRED` there).
2. Add the language to `SUPPORTED` and `LOCALES` in `frontend/js/i18n.js` and to `SUPPORTED` in `backend/i18n.py`.
3. The LLM prompts are single and in English; extend the label table and the language directive in `docs/email-analysis-guide.md` for the new language.
4. Translate the README and `docs/en/` (into `docs/<lang>/`) under the same heading structure.

#### Add a tab

1. A button and a `<section>` in `frontend/index.html`; the panel in `frontend/js/app.js`.
2. One module in `frontend/js/` in the style of the neighbours (ES modules, no framework), with its texts in the catalogs.
3. A router in `backend/routers/` included in `backend/main.py` if it needs a backend; a place in the harness.
4. Follow the shared layout (verdict banner, tiles, collapsible cards) and the action row: the timer, the status and related buttons sit next to the action button.

### Workflow, tests and conventions

- **Verification:** `./.venv/bin/python scripts/api_harness.py` runs every endpoint against mocked services (no keys, no network) and exits with 1 on an unexpected answer, a request that left the mocks, or a failed security probe. `--out file.json` writes the normalised answers and `--root` points at an older checkout (`git archive`): after a refactor the two versions must give the same output. `scripts/dump_facts.py` and the synthetic `tests/fixtures/*.eml` do the same for the deterministic e-mail analysis (after changing texts in `email_forensics.py` the dump in `pl` must stay identical; both scripts read only the flat `tests/fixtures/*.eml`, not the `unit/` subfolder). The interface is checked by hand.
- **Unit tests:** `./.venv/bin/pip install -r requirements-dev.txt`, then `./.venv/bin/python -m pytest -q` (a few seconds, no network, no keys). `tests/conftest.py` points `data/` and `logs/` at a temporary directory and fails the run if the real ones changed. Expected values are worked out from the RFCs and by reading the sample e-mails, never copied from the program's own output; a test that exposes a real defect is marked `xfail(strict=True)` with the reason instead of being bent to match. To add a case, save a SYNTHETIC `.eml` in `tests/fixtures/unit/` (reserved addresses only) and assert what its headers prove. Real messages belong in the gitignored `tests/private/`: put `name.eml` and `name.expected.json` there (format at the top of `tests/test_corpus.py`); without them that test is skipped.
- **Linting:** `ruff check backend scripts tests` (installed by `requirements-dev.txt`, pinned to one minor series so that a new ruff release does not suddenly report new findings in unchanged code; configuration in `pyproject.toml`; a development tool, not a dependency). For a frontend module: `cp file.js $TMPDIR/x.mjs && node --check $TMPDIR/x.mjs`.
- **i18n:** every text visible to the user goes through the catalogs (`t()`/`tn()` in the frontend, `backend/i18n.py` in Python). A new key needs a PL and an EN entry; run `python3 scripts/check_i18n.py` (also checks README and `docs/` heading parity, dead relative links and anchors, and that the version is the same in all five places) and look at the UI in `/?lang=qa`. Catalogs hold plain text; never HTML.
- **Versioning:** every change to the tool raises the version by 0.0.1 (after `X.Y.99` comes `X.(Y+1).0`, for example after 2.0.99 comes 2.1.0). The version is in five places: the `<title>`, the header and the footer of `frontend/index.html`, and under the logo in both READMEs. The release date (`YYYY-MM-DD`) in `<meta name="seisa-release-date">` of `index.html` is updated with every release; the Info tab shows it under the version. Add an entry to [CHANGELOG.md](../../CHANGELOG.md). Version 2.0.0 is the first release under the name Seisa.
- **Documentation:** the short `README.md` (English, the main one) and `README.pl.md` (Polish), and the pages of `docs/en/` and `docs/pl/` (the same file names, the same heading structure) change together; the two files directly in `docs/` are prompt context, not documentation.
- **Language and style:** code, comments, docstrings, log messages and commits are in English; the whole project avoids the long dash (Unicode U+2014), only a plain "-".
- **Action rows:** every tab that runs an action shows the timer (always one decimal, for example `13.1 s`), the status (for example the loaded file) and related buttons in one row next to the action button, during and after the run; in the Email tab the tokens and cost sit there too.
- **OpenRouter:** never guess a model slug or prices; the cost comes from the `usage.cost` that OpenRouter returns (`"usage": {"include": true}`).

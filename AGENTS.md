# AGENTS.md

Instructions for AI coding agents (and a short read for humans) working on this repository. It is written in English
only, on purpose: it is read by tools, not chosen by language. Human-facing documentation exists in English and
Polish; see `CONTRIBUTING.md`.

## What this project is

Seisa is a local tool for looking closely at suspicious things: IP reputation, URL scans, DMARC aggregate reports, an
educational analysis of an e-mail's source and the preparation of AbuseIPDB abuse reports. It is one Python process
(FastAPI) on `127.0.0.1` with a static frontend in plain JavaScript. No login, no database, no build step.

- `backend/`: the application. `routers/` (endpoints), `services/` (clients of external services), the domain logic in
  single-purpose modules (`scoring.py`, `email_forensics.py`, `mail_trust.py`, `report_builder.py`, ...).
- `frontend/`: `index.html`, `js/` (ES modules, no framework), `css/`, `themes/`, `i18n/{pl,en}.json`.
- `backend/locales/{pl,en}.json`: texts produced by the backend.
- `scripts/`: `api_harness.py` (end-to-end test on mocked services), `check_i18n.py`, `dump_facts.py`, `hooks/`.
- `tests/`: pytest. `docs/en/`, `docs/pl/`: documentation. `docs/*.md` (two files directly in `docs/`) are context
  for the LLM prompts, not documentation: do not move or rename them.

Read `docs/en/architecture.md` and `docs/en/extending.md` before a non-trivial change.

## The one priority

Seisa processes untrusted data (the text of e-mails, answers of external services) and can send a report to a public
database. Every change is judged first by one question: can it let untrusted content run code or leave the machine,
or make the tool publish something that is not a real, checked case? Convenience and elegance come second.

## Hard safeguards: never weaken without an explicit decision by the maintainer

If a task seems to require touching one of these, stop and ask instead of working around it. The full list with file
names is in [Security invariants](docs/en/privacy-and-security.md#security-invariants).

- it listens only on `127.0.0.1`: the `Host` check, the origin guard, the Content-Security-Policy, no login;
- security facts (sender IP, the order and origin of `Received` headers, SPF/DKIM/DMARC results, eligibility of a
  report, the score) are worked out by deterministic Python code. A language model may explain them or double-check
  them with a visible warning, but it is never the only source of a fact;
- the checks of an AbuseIPDB report (age, public IP, category) are validated by the backend, and "Send" stays a
  separate, manual click;
- e-mail content is untrusted text: nothing from it is opened or downloaded, links in results are not clickable, and
  it reaches OpenRouter only after an explicit "Analyze";
- everything put into `innerHTML` goes through `escapeHtml`; the i18n catalogs contain plain text, no HTML;
- files with user data are `0600` (the `data/analyses/` directory `0700`) and API keys are never printed or sent to
  the browser.

After you change a safeguard or code next to one, run a mutation check: break the safeguard on purpose and confirm
that `python3 scripts/api_harness.py` turns red. If the harness stays green, nothing guards it: add a case to the
harness first. A refactor or a translation must not change the normalised answers of the harness.

## Never do

- Never perform a real submission to AbuseIPDB, not even "as a test": it publishes data and spends the daily quota.
  Use the mocks in `scripts/api_harness.py` (`--serve PORT` starts the app on them for a try in the browser).
- Never print, log, commit or paste API keys or the contents of `.env`. Tests and docs use artificial keys.
- Never put a real host name, domain, own IP address, home directory path or real e-mail address into code, tests,
  fixtures, docs, issues, pull requests or commit messages. Use reserved data: `203.0.113.0/24`, `198.51.100.0/24`,
  `2001:db8::/32`, `example.org`, `.example`, `.test`. Real e-mails belong only in the gitignored `tests/private/`.
- Never commit the contents of `data/`, `logs/` or `.env`.
- Never bypass the git hooks (`--no-verify`) and never change `.github/` or `scripts/hooks/` casually: they guard the
  rest.

## Commands

```bash
python3 -m pytest -q                       # unit tests (the hook tests are marked `slow`; `-m "not slow"` skips them)
python3 scripts/api_harness.py             # the end-to-end test on mocked services
python3 scripts/check_i18n.py --strict     # catalogs, docs parity, links, version in all places
python3 scripts/dump_facts.py > /dev/null  # the deterministic e-mail facts on synthetic fixtures
ruff check backend scripts tests           # lint (pinned in requirements-dev.txt)
git config core.hooksPath scripts/hooks    # enable the pre-commit and commit-msg hooks once per clone
```

Setup: `python3 -m venv .venv && ./.venv/bin/pip install -r requirements-dev.txt`. Run the app with `./seisa.sh`
(port 54321). CI repeats this set on Linux for every pull request.

## Conventions

- Code, comments, docstrings, log messages, commits, issues and pull requests: English. Match the style of the
  neighbouring code (ES modules, no frameworks); look at `ls backend/*.py` and `ls frontend/js/*.js` before adding a
  module.
- Every text visible to the user goes through the catalogs (`t()`/`tn()` in the frontend, `backend/i18n.py` in Python)
  with an English and a Polish entry in the same commit. If you do not write Polish, a machine translation is fine: it
  will be corrected.
- Explanations in the interface are written for non-specialists: one plain sentence first (an everyday analogy helps),
  technical detail and expanded acronyms after it.
- No long dash (U+2014) in code, UI or docs: a plain "-".
- Documentation exists in English and Polish (`README.md` and `README.pl.md`, `docs/en/X.md` and `docs/pl/X.md`) and
  the pairs change together. This file (`AGENTS.md`) has no Polish twin.
- Do not raise the version and do not write a `CHANGELOG.md` entry: the maintainer does both when merging (the version
  changes only when the program changes, see `docs/en/extending.md`).
- One topic per pull request. Explain in plain language what changed and why, and state what you did not verify: the
  reviewer may not read every line, so the description and the tests carry the argument.
- Work on a branch and never commit directly to `main`; do not merge. Do not run `git push` or open pull requests on
  your own initiative: propose the change and let the person you work for decide.

## Where to look

| Need | File |
|---|---|
| what each tab does | `docs/en/tabs.md` |
| design decisions, modules, data files | `docs/en/architecture.md` |
| the data flow, the threat model, the security invariants | `docs/en/privacy-and-security.md` |
| how to add a service, a language, a theme or a tab; workflow | `docs/en/extending.md` |
| endpoints | `docs/en/api.md` |
| contributor rules for humans | `CONTRIBUTING.md` |
| reporting a vulnerability | `SECURITY.md` |

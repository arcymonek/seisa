**English** | [Polski](pl/DEVELOPMENT.md)

# Development

This guide is for contributors and for anyone who forks Seisa. In one sentence: it tells you how to set up the project, which checks to run before you send a change, and which documents to update when you change something.

## Contents

- [Set up](#set-up)
- [The local checklist](#the-local-checklist)
- [End-to-end harness](#end-to-end-harness)
- [Golden patterns](#golden-patterns)
- [Tests](#tests)
- [Git hooks](#git-hooks)
- [Continuous integration](#continuous-integration)
- [Versioning and changelog](#versioning-and-changelog)
- [Branches and pull requests](#branches-and-pull-requests)
- [How to extend Seisa](#how-to-extend-seisa)
- [If you change X, update Y](#if-you-change-x-update-y)
- [Writing documentation](#writing-documentation)

## Set up

This section gets a working copy onto your computer. You need Python 3.11 or newer and git; you do not need any real API keys.

```bash
git clone https://github.com/arcymonek/seisa.git
cd seisa
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
git config core.hooksPath scripts/hooks
```

- If you work in a fork, clone your fork instead.
- `requirements-dev.txt` includes `requirements.txt` and adds the development tools: pytest, ruff (pinned to the 0.16 series), hypothesis, coverage, pip-audit, pip-licenses and markdown-it-py.
- `requirements.lock` is the exact set of runtime versions that was tested. If something does not work, install it with `pip install -r requirements.lock`.
- Node.js is optional. It runs the syntax check of the frontend and a few frontend tests; without it those tests are skipped.
- The last command enables the git hooks. Do it once per clone (see [Git hooks](#git-hooks)).
- The harness and the tests use fake keys and faked services, so nothing you run here talks to the real services.

How to install and run Seisa as a user is explained in [OPERATIONS.md](OPERATIONS.md).

## The local checklist

This is the set of checks that must pass before you send a change. One command runs all of them:

```bash
python3 scripts/check_all.py
```

`scripts/check_all.py` uses `.venv/bin/python` when it exists. It runs these steps in order and stops at the first failure:

| Step | What it checks |
|---|---|
| `ruff` | Style and common mistakes in `backend`, `scripts` and `tests` (configuration in `pyproject.toml`: line length 140, Python 3.11 target, the git hooks included) |
| `pytest` | All tests, including the slow ones |
| `api_harness` | Every endpoint, end to end, with the outside services faked (see [End-to-end harness](#end-to-end-harness)) |
| `check_i18n --strict` | The language catalogs, and the same version in the title and the footer |
| `check_docs` | The documentation (see [Writing documentation](#writing-documentation)) |
| `dump_facts` | That the facts of the synthetic e-mails can still be computed (see [Golden patterns](#golden-patterns)) |
| `frontend syntax (node --check)` | The syntax of every module in `frontend/js/` |

- `python3 scripts/check_all.py --fast` skips the slow tests. Use it while you work, and the full run before you push.
- The frontend syntax check copies each module to a `.mjs` name first, because `node --check` treats a `.js` file as the older CommonJS format.
- CI runs the same steps (see [Continuous integration](#continuous-integration)).

`scripts/check_i18n.py [--strict]` has several jobs in one:

- key and `{placeholder}` parity between the English and Polish catalogs (frontend and backend);
- the right plural forms, no HTML and no long dash (U+2014) in the catalogs;
- keys used in code but missing from a catalog, and the other way round;
- the same version in the title and the footer;
- with `--strict`, Polish text in code that bypasses `t()`.

`scripts/make_app_icon.py` is not part of the checklist: it is a helper that builds `frontend/app-icon.png` from the logo, and it needs Pillow, which is not a dependency of Seisa.

What the checklist does not replace is a manual try in the browser after a change to the interface. Start the mock server described in the harness section, then open it with `/?lang=qa` (the pseudo language shows every untranslated text as `[[key]]`) and try some script payloads from a hostile page (the counter `window.__xss` must stay 0).

## End-to-end harness

The harness is the one test that exercises the whole application. It calls every endpoint while all outside services are replaced by fakes, so it is safe and needs no network.

```bash
python3 scripts/api_harness.py
```

It exits with 1 on an unexpected status, a request that tried to leave the fakes, or a failed security probe.

- **What it fakes.** It replaces the HTTP client with a mock transport (an unknown host fails), blocks socket connections, fakes WHOIS, DNS and reverse DNS, uses fake keys, and redirects `data/`, `logs/` and the home folder to a temporary folder.
- **Security probes.** A foreign `Host` header, cross-site requests (also to the icon and shutdown endpoints), a CORS preflight, the CSP header, URLScan path injection and screenshot checks.
- **Hostile data.** The faked answers contain HTML and script payloads, so the harness also checks that hostile third-party data stays inert on the server side.
- **`--out FILE`** writes the normalised answers (ids, times and version masked).
- **`--root DIR`** runs against another checkout, for example one exported with `git archive`. A refactor or a translation must give identical answers in both, so you can prove that nothing changed.
- **`--serve PORT`** serves the whole application on `127.0.0.1` with the fakes and temporary data. Use it to try the interface without keys and without real traffic, for example `python3 scripts/api_harness.py --serve 8765`.

Backend modules are imported only after the data paths are redirected, because the storage code binds those paths when it is imported. Keep that order if you edit the harness.

## Golden patterns

A golden pattern is a saved, correct answer that a test compares with the current one. It catches changes you did not mean to make.

- `scripts/dump_facts.py [--lang pl|en] [--root DIR]` prints the computed facts of the synthetic e-mails in `tests/fixtures/*.eml` as JSON.
- `tests/test_dump_facts_golden.py` compares that dump, in both languages, with `tests/golden/dump_facts.en.txt` and `tests/golden/dump_facts.pl.txt`. The age of the message is masked, so the pattern does not depend on today's date.
- A golden file changes only on purpose, and the pull request says why.
- The flat `tests/fixtures/*.eml` files feed both the harness and the golden dump. New synthetic e-mails for unit tests go to `tests/fixtures/unit/`, so the golden patterns stay unchanged.

## Tests

The tests live in `tests/`. Run them all with `python3 -m pytest -q`.

- **Slow tests.** `python3 -m pytest -m "not slow"` skips the tests that build throw-away git repositories (the hook tests) or start child processes (the parser time limits). They take a few minutes.
- **Isolation.** `tests/conftest.py` redirects `data/` and `logs/` to a temporary folder, fixes the language to Polish, and fails the run if the real `data/` or `logs/` changed.
- **Property tests.** `tests/test_fuzz_parsers.py` feeds random input to the e-mail parsers with hypothesis. The `dev` profile uses 200 random examples, the `ci` profile 300 fixed ones; choose with the `HYPOTHESIS_PROFILE` variable.
- **Frontend tests.** Pure frontend functions (API error messages, DMARC risk, Markdown export, the "Received verified" check) are tested through Node: the scripts are in `tests/js/` and pytest runs them.
- **Desktop icon.** The icon tests fake the home folder and need the `sips` tool on macOS; one test is skipped inside a sandbox.
- **Mirrored values.** A few values are repeated in the frontend on purpose (theme defaults, the comment length limit, the URLScan countries). `tests/test_frontend_mirrors.py` keeps them equal.
- **Private corpus.** If you keep real e-mails for your own checks, put them in `tests/private/legit/` and `tests/private/phishing_spam/` (git ignores them), with an optional `<name>.expected.json` next to each. Without such files the module is skipped.

Good practice for tests in this project:

- Take expected values from RFCs or from reading the input file, never from the output of the code under test. A test that copies the code's answer proves nothing.
- Use reserved example data only: `203.0.113.0/24`, `198.51.100.0/24`, `2001:db8::/32`, `example.org`, `.example` and `.test`.
- If a test finds a real bug, mark it `xfail(strict=True)` and report the bug. `strict` makes the run fail as soon as the bug is fixed, so the marker cannot be forgotten. Fix the production code in a separate step, after agreement.
- **Mutation check.** After you change a safeguard (or code next to it), break it on purpose and confirm that the harness or a test turns red. If nothing turns red, nothing guards that safeguard: add the check first, then finish your change.

## Git hooks

The hooks run the checks automatically when you commit. Enable them once per clone with `git config core.hooksPath scripts/hooks`.

The `pre-commit` hook (`scripts/hooks/pre-commit`) checks what is staged, not the working folder:

1. **Forbidden files.** `.env`, `data/`, `logs/`, `tests/private/` and `reports/` (except `.gitkeep`), and any other file that git ignores. Only `git add -f` could stage them.
2. **No long dash (U+2014)** in added lines, except in `frontend/vendor/`.
3. **Language pairs.** A document and its twin (for example `README.md` and `README.pl.md`, or `docs/X.md` and `docs/pl/X.md`) must be staged together. `SEISA_ONE_LANG=1 git commit ...` skips only this rule, for a typo fixed in one language.
4. **`check_i18n.py --strict` and `check_docs.py`**, run on an export of the index.

**Contributor mode.** A contributor does not have to update the documentation; the maintainer does. After `git config seisa.contributor true` the hook skips rule 3 and runs `check_docs.py --contributor` (see [How the documentation checks work](#how-the-documentation-checks-work)): what only the maintainer completes is printed as a list and does not stop the commit. Every other rule stays, including `check_i18n.py --strict` (the interface texts still need an English and a Polish entry; a machine translation of the Polish is fine) and the version step. The hook reads the setting with `git config --bool seisa.contributor` and fails closed: anything but a clean `true` (no setting, `false`, a value git cannot read) means the strict mode. The maintainer leaves the setting off.

5. **The version step** (see [Versioning and changelog](#versioning-and-changelog)).
6. **Privacy scan of added lines.** Strings that look like keys (long hex strings, `sk-or-v1-...`, names such as key, token or secret with a long value, `Bearer`), home folder paths (`/Users/name/`, `/home/name/`) and your own host names.

The `commit-msg` hook (`scripts/hooks/commit-msg`) checks the message: no long dash, no `Co-Authored-By` trailer, no "Generated with Claude Code" footer, and the same privacy scan. These message rules apply to commits made in a clone that has the hooks enabled; CI does not check the messages of a pull request.

- **Your own names.** The privacy scan reads a list of your own host names and domains from a file outside the repository: `~/.config/seisa/privacy-markers.txt`, or the file named in the `SEISA_PRIVACY_MARKERS` variable. One string per line, `#` starts a comment, and a line starting with `!` is a string that is allowed. The file is optional: without it only the generic checks run, and the hook prints a note. A hit never prints the value it found.
- **Whole branches.** `python3 scripts/hooks/pre-commit --range main` checks a whole branch, as CI does. Git does not run hooks on rebase and merge, so this command covers them. With `--no-version-rule` it checks only the added lines (CI uses that for pull requests from forks).
- **No off switch.** The hooks fail towards blocking, and there is deliberately no switch that turns all of them off. `git commit --no-verify` does, so do not use it: fix the cause instead.
- **Testing the hooks.** `tests/test_pre_commit_hook.py` tests them (slow). The variables `SEISA_HOOK_UNDER_TEST` and `SEISA_COMMITMSG_UNDER_TEST` point the tests at a modified copy of a hook, which is how you mutation-check a hook rule.
- **Testing the installer.** `tests/test_install_script.py` runs `install.sh` in a temporary folder, offline, with a hand-made package instead of PyPI (slow). The `install` job in CI runs it for real.
- **Testing the uninstaller.** `tests/test_uninstall_script.py` runs `uninstall.sh` in a temporary folder with HOME in a temporary directory (slow). Fake `uname` and `curl` commands simulate macOS, Linux and a running Seisa, and a pseudo-terminal types the answers, because the script only asks questions in a terminal. The `install` job in CI runs its preview after the installation.

## Continuous integration

CI is GitHub Actions in `.github/workflows/ci.yml`. It runs on pushes to `main` and on pull requests, with read-only permissions and no secrets. `pull_request_target` is deliberately not used, because it would give a fork's code write rights.

There are three jobs:

- **`check`** runs on Ubuntu 24.04 with Python 3.11 and the latest 3.x, with a 15-minute limit. Steps: ruff, pytest, the harness, `check_i18n --strict`, `check_docs`, the frontend syntax check, an informational coverage report (it has no threshold), and the branch rules of the hook.
- **`install`** runs `install.sh` as a new user would, on Ubuntu 24.04 and macOS 15, with the real libraries from PyPI. Then it starts the installed Seisa, waits for it to answer on `127.0.0.1:54321`, and runs the preview of `uninstall.sh`. This is the job that proves that `requirements.lock` installs on both systems.
- **`dependencies`** runs `pip-audit` on `requirements.lock` and checks the licences of the runtime packages against an allow-list (MIT, BSD, Apache, ISC, MPL-2.0 and PSF). If it turns red without a change in the code, the world changed: update the vulnerable library in its own branch, or read the new licence first (it must stay compatible with GPL-3.0-or-later) before extending the list.

The branch rules differ by origin:

- Own pull requests run `pre-commit --range origin/<base>`, version rule included.
- Pull requests from forks run only the added-line rules (`--no-version-rule`), because a contributor does not bump the version.

Other facts:

- The actions are pinned to full commit SHAs. Dependabot updates only them, weekly. Python dependencies are updated by hand, because a change to them is a change to the program.
- A green run does not prove that the tests cover your change, nor how the interface behaves in a browser.
- When a pull request changes `ci.yml`, `scripts/` or the hooks, GitHub runs the workflow from that pull request, which could switch off its own checks. In that case only the full local checklist counts.

## Versioning and changelog

The version answers one question: did the program change? It rises only when the program changes, not with every change in the repository.

- **Program files** (a change raises the version): everything in `backend/` (the prompt files in `backend/prompts/` included) and `frontend/` (the catalogs included), `requirements.txt`, `requirements.lock`, `seisa.sh` and `seisa-launcher.sh`.
- **Not program** (no new version): `README.md`, `README.pl.md`, `docs/`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `install.sh`, `uninstall.sh`, `scripts/`, `tests/`, `.github/`, and changes that touch only comments in the code.

The version has the form `X.Y.Z`:

| Part | Rises when |
|---|---|
| `Z` | A fix or a changed behaviour (a new check, a changed message, status code or validation). There is no upper bound: after 2.0.99 comes 2.0.100. |
| `Y` | A new feature, tab, outside service or `.env` key. `Z` goes back to 0. |
| `X` | Only by the maintainer's decision. |

- **Two places.** The version stands in `<title>` and in the footer of `frontend/index.html`. `check_i18n.py` checks that both match. The READMEs carry no version number: the current one is the top entry of `CHANGELOG.md`. The release date is the `seisa-release-date` meta tag in `frontend/index.html`.
- **One bump per branch**, in its last commit, together with a `## X.Y.Z - YYYY-MM-DD` entry at the top of `CHANGELOG.md` whose date equals the meta tag. The hook enforces both.
- **No bump needed?** A change to the program that really needs none (comments only) says so with a `No-version-bump: <reason>` line in one commit message of the branch.
- **Development notes.** A change without a bump that matters to maintainers (a new check, a new script) gets one dated line under `## Development` at the top of `CHANGELOG.md`.
- **Contributors do not touch the version or `CHANGELOG.md`.** The maintainer does it when merging.
- **Release titles are read by the program.** A release commit is titled `Seisa X.Y.Z: short summary`. The Info tab lists the last 10 such commits among the last 100 under "Recent changes", so keep that format exactly.

## Branches and pull requests

Work happens on a branch whose name starts with its type: `fix-`, `feat-`, `test-`, `ci-` or `docs-`, then a short description (for example `fix-dns-timeout`). The `main` branch changes only when the maintainer merges a reviewed pull request.

- **Commit messages** are in English, in the imperative mood, with a short title (`Fix the DNS timeout`).
- **The pull request description** has four parts: `## What`, `## Why`, `## What changes for users` and `## Checked`. In "Checked", say what you checked and what you did NOT check; that honesty is more useful than a long list.
- **The template** asks what changes for users. A contributor does not update the documentation; the maintainer does, from that answer (see the table below).
- The steps from fork to pull request are in [CONTRIBUTING.md](../CONTRIBUTING.md).

## How to extend Seisa

These recipes list the places you have to touch. Each starts from the usual way to add the thing; the module descriptions are in [ARCHITECTURE.md](ARCHITECTURE.md).

### Add an outside service to the IP tab

A new source of information is a subclass of `IntelService` in `backend/services/base.py` (`name`, `supports_ip`, `supports_domain`, `is_configured`, `query_ip`, `query_domain`; use `fetch_json` for requests) and is registered in `SERVICE_REGISTRY` in `backend/aggregator.py`. These places list services by name and need an entry too:

- `backend/config.py` (the key) and `.env.example`;
- `backend/routers/about.py` (the list of keys) and `backend/api_limits.py` (`SERVICE_ORDER` and the limits);
- `backend/markdown_report.py` (`SERVICE_TITLES` and `SERVICE_ORDER`) and `backend/scoring.py` (`CREDIBILITY`, if the service votes);
- `frontend/js/services.js`, `frontend/js/lookup.js` (`ALL_SERVICES`) and `frontend/js/lookup-result.js` (the link to the service);
- both language catalogs and the mock handler in `scripts/api_harness.py`.

A new `.env` key raises the middle number of the version and has to appear in the [README](../README.md) key table and in the full table of [PRIVACY.md](PRIVACY.md).

### Add a language

Many places know the list of languages:

- backend: `SUPPORTED` and `LANGUAGE_NAMES` with the plural rules in `backend/i18n.py`, and `backend/locales/<lang>.json`;
- frontend: `SUPPORTED` in `frontend/js/i18n.js` and `frontend/i18n/<lang>.json`;
- theme names: `LANGS` in `backend/themes.py`, and the names inside each theme file;
- `scripts/check_i18n.py` (`PLURALS_REQUIRED`);
- the label table in section 0 of `backend/prompts/email-analysis-guide.md`, and `backend/verdict.py` if it has localised tokens.

### Add a theme

Drop `frontend/themes/<id>.json` with every colour key. `tests/test_themes.py` validates the shipped themes and checks their text contrast against the WCAG AA rule (the accessibility standard for readable colours).

### Add a tab

A tab touches both ends:

- `frontend/index.html`: a `data-tab` button and a `<section id="panel-...">`;
- `frontend/js/app.js` (`panels` and the start-up) and a new module `frontend/js/<tab>.js`; larger tabs use `<tab>-<role>.js` for extra modules;
- catalog keys `tab.*` in both languages;
- a router in `backend/routers/`, mounted in `backend/main.py`;
- the harness, the [README](../README.md) tab table and [USER_GUIDE.md](USER_GUIDE.md). `check_docs.py` turns red until the last two exist.

### Change a prompt

The files in `backend/prompts/` are program files: a change needs a version bump. Try the Email lesson and the AbuseIPDB answer on the mock server. The Email guide fixes the structure of the answer that the interface parses (the verdict line, the `## ` parts, the status tags), so keep that structure.

### Conventions

- **Language.** Code, comments, logs and commits are in English. Every visible text goes through the catalogs (`t()` and `tn()`), in both languages in the same commit. Catalogs hold plain text, and a result that goes into `innerHTML` is escaped with `escapeHtml`.
- **Dashes.** No long dash (U+2014) anywhere; use a plain `-`.
- **Style.** Match the neighbouring files: plain ES modules, no framework, no build step.
- **Check before you add.** Before you add a module, look whether one exists (`ls backend/*.py`, `ls frontend/js/*.js`).
- **Times.** A time shown next to an action button has one decimal (`13.1 s`), in the same `.action-row` and `.action-info` area as the status, the token cost and related buttons.
- **Separate tools.** The Email and AbuseIPDB tabs are two different tools. Do not copy a change from one to the other unless that is the point.
- **Plain explanations.** An explanation in the interface starts with one plain sentence (an everyday comparison helps) and only then gives the details, with abbreviations expanded.

## If you change X, update Y

Documentation that is out of date is worse than none, so the maintainer keeps a change and its documentation together. This table is the maintainer's map (and the map of the maintainer's agent): it shows which document belongs to which kind of change. A contributor need not follow it. `check_docs.py` enforces the rows marked "checked" for the maintainer; for pull requests from forks the same findings are only listed (`--contributor`).

| When you change... | Update |
|---|---|
| An endpoint (path, input, output, error) | [API.md](API.md) and its Polish twin (checked), and the harness |
| Anything that sends data out (a new service, key, endpoint or kind of request) | The full table in [PRIVACY.md](PRIVACY.md), the short table and the key table in [README](../README.md), the tab in [USER_GUIDE.md](USER_GUIDE.md), [API.md](API.md), `.env.example` |
| A `.env` key | `backend/config.py`, `.env.example` and the [README](../README.md) key table (checked), and raise the middle number of the version |
| A tab, a button or a visible name | Both catalogs, [USER_GUIDE.md](USER_GUIDE.md) and the [README](../README.md) tab table (checked), and the screenshots if the look changed |
| A limit or a number shown to users (history size, log retention, comment length, timeouts) | The document that owns the number: [OPERATIONS.md](OPERATIONS.md), [PRIVACY.md](PRIVACY.md) or [COMPLIANCE.md](COMPLIANCE.md); `check_docs.py` checks the numbers listed in its `FACTS` table |
| A data file or its permissions | The data section of [PRIVACY.md](PRIVACY.md), the deleting section of [OPERATIONS.md](OPERATIONS.md), and [ARCHITECTURE.md](ARCHITECTURE.md) |
| A safeguard | The safeguards in [PRIVACY.md](PRIVACY.md), and a mutation check (see [Tests](#tests)) |
| The AbuseIPDB rules, hard checks or comment rules | [COMPLIANCE.md](COMPLIANCE.md), and `backend/prompts/abuseipdb-reporting-policy.md` if the model should know |
| A prompt file | A version bump, and [ARCHITECTURE.md](ARCHITECTURE.md) if the role of the prompt changes |
| A module (new, renamed or removed) | The module tables in [ARCHITECTURE.md](ARCHITECTURE.md) (checked) |
| A script, a hook rule or a CI job | This file (checked for scripts), and [CONTRIBUTING.md](../CONTRIBUTING.md) if contributors are affected |
| A dependency | `requirements.txt` and `requirements.lock`, a version bump, and the licences in [COMPLIANCE.md](COMPLIANCE.md) if it is new |
| The version | The title and the footer of `frontend/index.html`, the release date and `CHANGELOG.md` (see [Versioning and changelog](#versioning-and-changelog)) |
| A file in `frontend/vendor/` | The licences in [COMPLIANCE.md](COMPLIANCE.md) |
| A language or a theme | The recipes in [How to extend Seisa](#how-to-extend-seisa), and the settings in [USER_GUIDE.md](USER_GUIDE.md) |
| The start-up messages in `seisa.sh` | The "Install and run" heading in the [README](../README.md), which `seisa.sh` points to |
| The messages or steps of `install.sh` | Section 2 and the "Starting" table in [OPERATIONS.md](OPERATIONS.md#starting), and the quick start in the [README](../README.md) |
| The messages or steps of `uninstall.sh` | Section 8 and the "Starting" table in [OPERATIONS.md](OPERATIONS.md#8-uninstalling) |

The maintainer makes every documentation change in both languages, in the same commit. A contributor who edits a document is welcome to change one language only; the maintainer completes the twin.

## Writing documentation

This section is for everyone who writes or edits the documents of the project. The English text is the source; the Polish text is a faithful, natural translation with the same structure.

### Rules for writing

1. **One plain sentence first, then the details.** The reader is not necessarily a programmer. Expand every abbreviation at its first use in each file, for example "SPF (Sender Policy Framework - a list of the servers allowed to send mail for a domain)".
2. **No walls of text.** A paragraph has at most about four lines (60 words). Three or more parallel items become a list or a table. A file longer than about 150 lines has a table of contents. Every section starts with a sentence that says what it is about.
3. **Interface names literally.** Use the names exactly as the catalogs spell them (`frontend/i18n/en.json` and `pl.json`).
4. **Only true claims.** Every claim must be true in the code. A number comes from one place in the code. When in doubt, look it up in the code or ask; do not guess.
5. **One home per fact.** Each fact has one document where it is explained in full; other documents link to it. Two deliberate exceptions: the short "what leaves your computer" table and the tab table in [README](../README.md).
6. **Keep private things out.** No version numbers in `docs/`, no long dash (U+2014), no real host names, IP addresses or home folder paths. Examples use `203.0.113.0/24`, `198.51.100.0/24`, `2001:db8::/32`, `example.org` and `.example`. The only e-mail address is `github@arkadiuszpolak.pl`.
7. **The top of a file with a twin:** the language switch line, the title, and one or two sentences saying for whom the file is and why it exists.
8. **Natural Polish.** Translate the meaning, not the words; use the terms of the Polish catalog. Headings, tables, code blocks and images are the same in both languages.
9. **Encouraging, but factual.** No marketing and no promises the code does not keep. Say what Seisa does not do, too.

### How the documentation checks work

`python3 scripts/check_docs.py` reads the documentation and the code and compares them. It uses only the standard library and reads the code without running it, so the git hook can run it with any Python. It runs in `check_all.py`, in the pre-commit hook and in CI. Errors block; warnings only inform.

With `--contributor` (CI for pull requests from forks; the hook when `seisa.contributor` is `true`) the checks that compare the documentation with the code or with its twin (Pairs, Known files, Routes, Keys, Tabs, Modules, Numbers) do not fail. Their findings are printed under "To be completed by the maintainer", and the run still ends with exit code 0. The checks of form (Links, Images, Form, Addresses, Presence) still block. Without the flag nothing changes.

| Check | What it requires | Kind |
|---|---|---|
| Pairs | Each English file has its Polish twin with the same headings (levels 1-4), code blocks, tables, table rows and images | Error |
| Known files | Every Markdown file in the root, `docs/` and `docs/pl/` is a pair or a known exception (`AGENTS.md`, `CHANGELOG.md`) | Error |
| Links | Every relative link, `#anchor` and image `src=` in a tracked Markdown file works | Error |
| Images | Every image has a non-empty `alt` text and every image in `docs/images/` is used | Error |
| Routes | The endpoints of the application are exactly the `METHOD /path` entries of `docs/API.md` | Error |
| Keys | The fields of `Settings`, the keys of `.env.example` and the [README](../README.md) key table agree | Error |
| Tabs | Every tab has a section in `docs/USER_GUIDE.md` and a row in the [README](../README.md) tab table | Error |
| Modules | Every file of `backend/`, `frontend/js/` and `scripts/` is named in `docs/ARCHITECTURE.md` or in this file | Error |
| Numbers | Limits from the code (listed in `FACTS` in `check_docs.py`) appear in the document that owns them, in both languages | Error |
| Form | No version number in `docs/`, no U+2014, the language switch line on top of every file with a twin | Error |
| Addresses | E-mail addresses only from an allowed list (`github@arkadiuszpolak.pl`) | Error |
| Presence | Every required document exists | Error |
| Readability | No paragraph longer than 6 lines or 90 words; no file over 150 lines without a table of contents | Warning |
| `--external` | Every external web link answers (run by hand before a release; needs the network, so never in CI or the hook) | Manual |

- New files must be known to git before the checks see them: run `git add <path>` first, because the content checks read tracked files only.
- When a check is red, its message names the file and the line. Fix the document (or the code); do not change the check to make it pass.
- To add a document, put it in `DOC_PAIRS` in `scripts/check_docs.py`. To protect a new number, add it to `FACTS`. `tests/test_check_docs.py` tests each check with a good and a broken case.

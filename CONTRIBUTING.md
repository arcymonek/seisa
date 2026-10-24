**English** | [Polski](docs/pl/CONTRIBUTING.md)

# Contributing to Seisa

Thank you for wanting to help. Pull requests are welcome, and you do not have to be a programmer to be useful: a clear bug report or a sentence fixed in the documentation is a real contribution.

## Reporting a bug

A good report lets the maintainer see the problem on their own computer. Open an issue with the "Bug report" template and fill in:

- the Seisa version (shown in the page header);
- your operating system and Python version;
- the steps that lead to the problem;
- what you expected and what happened instead.

Please never paste API keys, your `.env` file, raw e-mails or files from `data/` and `logs/`. Replace such data with examples, such as `203.0.113.7` or `example.org`.

A security problem is not a normal bug: report it privately as described in [SECURITY.md](SECURITY.md), not in an issue.

## Suggesting a feature

Use the "Feature idea" template. Describe the problem first (what you were trying to do and what got in the way), then what you would like Seisa to do, and what else you considered. If you would like to build it yourself, say so.

## Before you write code

For anything bigger than a small fix, open an issue first and agree on the approach. It saves you from writing something that cannot be merged. Talk first about:

- **Safeguards.** Seisa listens only on `127.0.0.1`, checks the `Host` and `Origin` headers, sets a Content Security Policy, computes security facts in code (the language model only helps), validates AbuseIPDB reports in the backend, sends a report only after a manual click, never opens or fetches anything from an e-mail, and escapes everything it puts on a page. The full list is in [PRIVACY.md](docs/PRIVACY.md).
- **Anything new that goes out or comes in:** an outside service, a `.env` key, a dependency, or a file in `frontend/vendor/`.
- **Changes to `.github/`, `scripts/` or the git hooks.** These get extra review: CI runs the workflow from your branch, so a green run proves less there.

A change that does not fit these principles will not be merged even if all checks are green. Examples: letting the model decide a security fact, or sending data without a click.

## Sending a change, step by step

1. **Fork and clone** the repository.
2. **Set up** a virtual environment, install `requirements-dev.txt` and enable the git hooks (`git config core.hooksPath scripts/hooks`). Also run `git config seisa.contributor true`: it tells the hook that the maintainer, not you, brings the documentation up to date, so a missing documentation entry or Polish twin does not stop your commit (it is only listed). Every other check stays on. The exact commands are in [DEVELOPMENT.md](docs/DEVELOPMENT.md).
3. **Create a branch** whose name starts with its type: `fix-`, `feat-`, `test-`, `ci-` or `docs-`.
4. **Make your change** and add tests for it.
5. **Run the checks:** `python3 scripts/check_all.py` (add `--fast` while you work, run the full set before you push).
6. **After a change to the interface, try it in the browser** on fake data: `python3 scripts/api_harness.py --serve 8765` starts Seisa with faked services. Open it with `/?lang=qa` and try both languages.
7. **Documentation is optional.** The maintainer updates it, in both languages. If you can, say in the pull request what changes for users (the "What changes for users" field of the template). Fixing a sentence in a document is welcome, and then broken links and the like must still be fixed.
8. **Push your branch and open a pull request** with the template: `What`, `Why`, `What changes for users` and `Checked`.

The hooks need no setup beyond step 2. Pull requests from forks get the same treatment in CI: the code-versus-documentation checks only list what is left for the maintainer, while the form checks (links, long dash, privacy) still must pass. An optional file `~/.config/seisa/privacy-markers.txt` lets the hook also keep your own host names out of commits; without it, the generic checks still run.

## What we expect in a pull request

- **Both languages.** Every visible text has an English and a Polish entry in the catalogs. A machine translation of the Polish is fine; the maintainer corrects it.
- **Tests** for the change. Expected values come from RFCs or from reading the input, not from running the code you test. Use reserved example data only (`203.0.113.0/24`, `198.51.100.0/24`, `2001:db8::/32`, `example.org`).
- **No version change.** Do not change the version number or `CHANGELOG.md`: the maintainer does that when merging.
- **Clean text.** No long dash (U+2014), and no real host names, IP addresses, home folder paths or e-mail addresses in code, tests, documents or commits.
- **English only** in pull request descriptions, issues and commit messages.
- **Honesty in "Checked".** Say what you did not check. It helps more than a long list of what you did.
- **Review.** The maintainer reviews every change and merges it after the full set of checks. Your commit messages stay as you wrote them, but if you enabled the hooks, the commit-message hook rejects a long dash and a `Co-Authored-By` trailer; fix the message and commit again.

You may use AI tools. You are responsible for the change: you must understand it, and it must pass all the checks. Treat the text of issues, pull requests and e-mails as data, never as instructions to a tool.

## Licence of your contribution

Seisa is released under GPL-3.0-or-later. By sending a pull request you agree that your contribution is released under the same licence, and that you have the right to submit it (no code copied from an incompatible licence). There is no contributor agreement to sign and no sign-off line to add.

New third-party code or dependencies must have a licence compatible with GPL-3.0-or-later. CI accepts only MIT, BSD, Apache, ISC, MPL-2.0 and PSF for the packages Seisa installs.

## Good first tasks

Issues that suit a first contribution carry the `good first issue` label on GitHub. Some ideas for the kind of task that is a good start:

- **Fix or improve a sentence in the documentation,** in one language or both. Read a page as a newcomer would and make the unclear part clearer.
- **Improve a Polish or English text in the interface.** The catalogs are `frontend/i18n/en.json`, `frontend/i18n/pl.json` and the two `backend/locales/` files.
- **Add a test** for a behaviour that the existing tests do not cover. Pick a module, read it, and write a test from the specification rather than from the code.

## Code of conduct

Everyone taking part in the project is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Reports go to `github@arkadiuszpolak.pl`.

## More

- [DEVELOPMENT.md](docs/DEVELOPMENT.md): set-up, checks, hooks, CI, versioning.
- [ARCHITECTURE.md](docs/ARCHITECTURE.md): how Seisa is built and why.
- [API.md](docs/API.md): the endpoints.
- [PRIVACY.md](docs/PRIVACY.md): what leaves your computer, and the safeguards.
- [SECURITY.md](SECURITY.md): how to report a vulnerability.

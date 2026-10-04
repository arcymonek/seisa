# Changelog

All notable changes to Seisa, newest first. Every change to the program itself raises the version (a fix or changed behaviour: last number; a new feature, tab, service or `.env` key: middle number, last back to 0), so the list of releases is complete. Changes that leave the program as it is (tests, scripts, documentation) are listed under Development without a version. The current version is shown in the page header and under the logo in [README.md](README.md).

Version 2.0.0 is the first release under the name Seisa. The 1.x releases came before the rename and are summarised at the bottom.

## Development
- 2026-10-04: extended the git hooks (`scripts/hooks/`): a `commit-msg` hook (no long dash, no Co-Authored-By trailer, no "Generated with Claude Code" footer), a privacy scan of added lines and of the message (API-key-looking strings, home directory paths, own names from a markers file outside the repository), a `## X.Y.Z - YYYY-MM-DD` CHANGELOG entry matching `seisa-release-date` whenever the version is bumped, and a `slow` pytest marker for the hook tests (`pytest -m "not slow"`). The tests now also run real `git commit` (partial commits, `-a`, `--amend`, rebase, merge) and a simulated pull request merge commit for `--range`. No change to the program.
- 2026-10-04: added a git pre-commit hook (`scripts/hooks/pre-commit`, enabled with `git config core.hooksPath scripts/hooks`): forbidden files, long dash, PL/EN pairs, `check_i18n.py` on the staged files and one allowed version step per branch; its `--range` mode runs in CI on pull requests and requires a version bump exactly when program files changed (a comment-only change declares `No-version-bump: <reason>` in a commit message). `check_i18n.py` now exposes the five version places as `VERSION_PLACES`/`read_versions` (same output as before); `pyproject.toml` makes ruff lint the extensionless hook; `tests/test_pre_commit_hook.py` covers every rule. Also corrected the Versioning and test-time notes in `docs/{en,pl}/extending.md`. No change to the program.
- 2026-10-04: added a pull request template (`.github/pull_request_template.md`: What / Why / Checked) and listed it, together with the CI workflow, in the file tree of `docs/{en,pl}/architecture.md`. No change to the program.
- 2026-10-04: added GitHub Actions CI (`.github/workflows/ci.yml`: ruff, pytest, API harness, i18n check and facts dump on Python 3.11 and the latest 3.x), run on pull requests and on pushes to `main`. No change to the program.
- 2026-10-04: history rewritten before the first push to GitHub (a local-only file removed from all commits, author unified); commit hashes from before this date changed. No change to the program.
- 2026-10-04: added a pytest unit-test suite (`tests/`, `requirements-dev.txt`, run with `python3 -m pytest -q`) covering the mail trust helpers, scoring, the AbuseIPDB report checks, the e-mail parser and forensics, plus a gitignored `tests/private/` for an optional local corpus of real e-mails. No change to the program.
- 2026-10-04: `scripts/api_harness.py --out` no longer crashes after writing the answers (the `.meta.json` file now serialises the raw bytes of the screenshot probe), so the command exits with 0 on success. No change to the program.
- 2026-10-04: `requirements-dev.txt` now also installs `ruff`, pinned to the 0.16 series, so a new ruff release cannot start reporting new findings in unchanged code. No change to the program.

## 2.1.30 - 2026-10-04
- **Fix:** Email tab, Overview panel: the mirrored Checklist and Assessment sections now get glossary tooltips (SPF, DKIM, DMARC, ARC, PTR, SCL, HELO...) on first mention, tracked independently from the main Lesson panel's own cards, so a term already explained in one panel is still explained once in the other instead of never appearing there. (Written on 2026-09-27 as 2.1.23 and left on a side branch; re-applied on top of 2.1.29.)

## 2.1.29 - 2026-10-04
- **Fix:** AbuseIPDB and Email tabs, found by checking real messages: (1) an address written without square brackets after a reverse-DNS name, `(host. 192.0.2.1)` (a Gmail form), is now read; before, such a message could end with "no sender IP found". (2) A hop is now compared with the recipient's operator by family, and Exchange Online's internal domain `exchangelabs.com` belongs to Microsoft; before, a genuine message to a Microsoft mailbox could end with a Microsoft-internal address at high confidence instead of the connecting client. (3) When the receiving server wrote a verified reverse-DNS name that belongs to another operator than the HELO name, the verified name is used, so a sender who introduces itself as a big provider is no longer skipped as "internal". (4) When the older lines of an unknown relay are not used, the reasoning now says so.

## 2.1.28 - 2026-10-04
- **Fix:** AbuseIPDB and Email tabs: when the sender IP is taken from older `Received` lines written by a relay (the walk through a provider or pod-style relay) instead of by the recipient's own server, it is no longer shown with high confidence. The confidence is capped at medium (an SMTP-AUTH/DKIM match no longer raises it back), the reasoning states that the lines may be forged and names the address the recipient's own server recorded, the facts carry a new `ip_from_relay_lines` field, and the Email tab adds the same warning to its findings. The chosen address itself does not change. A sender can still make Seisa pick a forged address (by posing as a known provider in the HELO name or by forging pod-style hops); closing that fully needs checks that cannot be done offline, so it stays flagged as uncertain (see `docs/*/tabs.md`).

## 2.1.27 - 2026-10-04
- **Maintenance:** code cleanup flagged by the current `ruff` (unused imports, import order, `contextlib.suppress` instead of `try`/`except`/`pass`, `zip(strict=True)` in the quota refresh, list literals instead of `str.split`). No change in behaviour: the API harness output and the e-mail facts dumps are byte-identical to 2.1.26.

## 2.1.26 - 2026-10-04
- **Fix:** AbuseIPDB and Email tabs: an IPv6 sender address written the way RFC 5321 prescribes (`[IPv6:2001:db8::1]`, as Postfix does) is now recognised; before, no sender IP was found for such messages.
- **Fix:** AbuseIPDB and Email tabs: the walk through a relay's older `Received` lines is now done only for a well-known provider (Microsoft, Google, ...) or through internal pod-style hops with private addresses (OVH). Before, forged older lines that followed the walk's own `by`/`from` pattern could move the reported IP to an innocent third party with confidence "high". For an unknown relay Seisa now stays at the hop recorded by the recipient's own server. A sender who also forges pod-style names with private addresses can still get through; that needs checks the program cannot do offline (see `docs/*/tabs.md`).

## 2.1.25 - 2026-10-02
- **Fix:** AbuseIPDB tab: the model refused to analyse e-mails whose body is base64 (e.g. phishing sent through an e-mail provider). The tab sent the raw source, so the model saw walls of base64 instead of the message, while the Email tab, which decodes text parts first, worked on the very same file. AbuseIPDB now sends the same prepared source as the Email tab (headers unchanged, base64 text parts decoded, binary parts replaced by a size + sha256 marker), fenced with the `EMAIL-START`/`EMAIL-END` markers as untrusted data. The facts (IP, SPF/DKIM/DMARC) are still computed from the original source. The markers moved to `backend/email_forensics.py` and are shared by both tabs.
- **Fix:** removed the retry without `response_format` added in 2.1.23 (it rested on a wrong diagnosis); an empty non-refusal answer is retried once with the same request again. Model refusals are still recognised and reported (2.1.24), and the extended log line stays.

## 2.1.24 - 2026-10-02
- **Fix:** AbuseIPDB tab: the "invalid response ... start of the response: ''" error was in fact a refusal by the model's own safety filter (`finish_reason=content_filter`, `native_finish_reason=refusal`), not a JSON-format problem as 2.1.23 assumed. Seisa now recognises a refusal, shows a clear message that suggests trying another model in `OPENROUTER_MODEL`, and no longer wastes a second identical request on it.

## 2.1.23 - 2026-10-02
- **Fix:** AbuseIPDB tab: when OpenRouter returned an empty message ("invalid response ... start of the response: ''"), the automatic retry sent the identical request and failed the same way. The retry now drops the strict `response_format: json_object` option (the prompt still demands JSON and the parser tolerates a code fence), and the log line for an unparseable answer now also records `finish_reason`, `native_finish_reason`, any `refusal`, the provider and the token count, so the real cause is visible if it persists.

## 2.1.22 - 2026-09-27
- **UI:** URLScan and AbuseIPDB tabs now end with a collapsible "Explanations" card, matching IP and DMARC - written for non-specialists first (score/scale, engines vs. community, categories/brands, flagged requests, certificate age, Umbrella rank, apex vs. subdomain, form signals, visibility for URLScan; the three check groups, boundary hop, SMTP-AUTH, double extension, the 15-minute rule, PII masking, and eligibility vs. risk score for AbuseIPDB). The same `frontend/js/glossary.js` glossary tooltip now also covers ASN, the engine/community counts, the apex domain, the boundary-hop and SMTP-AUTH badges and a few check labels in both tabs.
- **Docs:** `docs/{en,pl}/tabs.md` and `docs/{en,pl}/architecture.md` updated to describe the new sections and the shared glossary helper.

## 2.1.21 - 2026-09-27
- **UI:** rewrote the IP and DMARC tab "Explanations" text for non-specialists - a plain-language sentence with an everyday analogy first, technical detail (with abbreviations expanded) after - and added a small shared `frontend/js/glossary.js` helper that puts the same contextual glossary tooltip (as already used in the Email tab) on jargon labels such as ASN, reverse DNS, the domain's own SPF/DKIM/DMARC/CAA records, the AbuseIPDB confidence score, and the DMARC report's Policy/Alignment fields.
- **Docs:** README and `docs/{en,pl}/tabs.md` now mention the "Explanations" cards and glossary tooltips as part of the shared tab layout.

## 2.1.20 - 2026-09-27
- **Docs:** README audit - added a table of contents, a literal `git clone` command, where local data lives (`data/`, `logs/`) and how to wipe it, a verification pointer for "local by design"/"no telemetry", and moved the "pull requests are not accepted, issues are welcome" note next to the project description instead of the bottom of the License section; the license badge is now a link to `LICENSE`.
- **Docs:** removed 20 leftover `<!-- Screenshot to add -->` placeholder comments (README x2, `docs/{en,pl}/tabs.md` x8 each) - no `docs/img/` directory ever existed.
- **Docs:** de-duplicated two tables that had drifted out of sync risk - the `.env` keys table is now only in the README (`docs/{en,pl}/configuration.md` links back to it), and the "what leaves your machine" table is now only fully listed in `docs/{en,pl}/privacy-and-security.md` (the README keeps a short excerpt of the most common actions, with a link to the full table). The README's own "Changelog" excerpt now skips maintenance-only entries and stays in sync with the version header.

## 2.1.19 - 2026-09-27
- **Docs:** added the missing changelog entries for 2.1.0-2.1.13.

## 2.1.18 - 2026-09-27
- **Docs:** added the missing changelog entries for 2.1.14-2.1.17 and refreshed the READMEs' release highlights to match; `docs/{en,pl}/tabs.md`, `docs/{en,pl}/architecture.md` and `docs/email-analysis-guide.md` were already updated in those releases themselves.

## 2.1.17 - 2026-09-27
- **AbuseIPDB tab:** every hop in the address card now shows a private/public label and its own SMTP-AUTH/DKIM corroboration badge, not just the boundary hop; `is_reportable_ip`'s private/special-IP check now shares its classification with the rest of the tool instead of a third, separate copy of it.

## 2.1.16 - 2026-09-27
- **Email tab:** the "sender IP" fact and the route diagram now walk through an external relay's own internal hops (the same mechanism as the AbuseIPDB tab) instead of always defaulting to the newest entry, fixing a wrong sender IP for chains that span more than one mail operator.

## 2.1.15 - 2026-09-27
- **Email tab:** trust-boundary detection now recognises internal relay hops named with bare, dotless identifiers (for example Kubernetes pod names) instead of miscounting them as a different operator; every hop's IP is marked private or public and gets an SMTP-AUTH/DKIM corroboration note. Domain/IP/relay-trust logic shared by the Email and AbuseIPDB tabs is consolidated into `backend/mail_trust.py`.

## 2.1.14 - 2026-09-27
- **AbuseIPDB tab:** the reported IP no longer gets stuck on a shared mail relay when its internal hops are named with bare, dotless identifiers (for example OVH's mail-out infrastructure) - the boundary walk now continues through them; added an SMTP-AUTH/DKIM corroboration note and a confidence bump for the selected hop.

## 2.1.13 - 2026-09-26
- **Email tab:** new "Analyze without LLM" button runs only the local deterministic checks (Received route, authentication, domain alignment, timeline, MIME structure, links, hidden content) - nothing is sent to OpenRouter and the result is not saved as an analysis.

## 2.1.12 - 2026-09-26
- Banners lost their fill: only the border carries the meaning (bad = red, warn = yellow, good = green, default = white), the text stays white.
- **Removed:** the IP tab's batch mode and "Force refresh" button (and the 15-minute in-memory result cache behind it - every lookup is queried fresh now), the Email tab's follow-up-question feature (`email-ask.js`), and the Logs tab's auto-refresh.
- **Email tab:** the Received table is wider so its columns no longer crowd the hostnames and notes.
- "Expand all" / "Collapse all" buttons for groups of collapsible cards (`frontend/js/util.js`); assorted wording fixes across the tabs.

## 2.1.11 - 2026-09-26
- Reworded descriptions: the app subtitle, the History tab's second line (pinned entries mentioned before "Clear history", e-mail analyses deleted "manually") and the AbuseIPDB and Email tabs' LLM notices.

## 2.1.10 - 2026-09-26
- **Info tab:** the environment grid no longer shows a tile for WHOIS/rDNS (it needs no API key); a note explains why; small wording fixes to the description.

## 2.1.9 - 2026-09-26
- **Info tab:** service status and API limits are shown as tiles instead of a table, with the environment tile first and the notes below a divider.

## 2.1.8 - 2026-09-26
- **Info tab:** the license link is no longer italic.

## 2.1.7 - 2026-09-26
- **Info tab:** the status and limits table is full-width and column-aligned, without asterisks; a divider sits under the "Refresh limits" row.

## 2.1.6 - 2026-09-26
- **Info tab:** the "limit exceeded" badge moved under the values, labels shortened, and the table is fitted to its content instead of stretching full-width.

## 2.1.5 - 2026-09-26
- **Info tab:** API usage is shown as "used/limit | share" instead of a bar.

## 2.1.4 - 2026-09-26
- **Info tab:** the usage column has a fixed-width number next to a short bar.

## 2.1.3 - 2026-09-26
- **Info tab:** shorter key and source labels; the OpenRouter row no longer names the model.

## 2.1.2 - 2026-09-26
- **Info tab:** the description matches what the tab actually shows; the author's e-mail address changed.

## 2.1.1 - 2026-09-26
- **Info tab:** the status-and-limits table is more compact, the environment fields are laid out in rows, and the hint text is shorter.

## 2.1.0 - 2026-09-26
- **Info tab:** the separate "Service status" and "API limits" cards are merged into one "Status and API limits" card, with a new environment grid (address, whether `.env` is present, OS, Python and FastAPI versions).

## 2.0.92 - 2026-09-26
- **Logs tab:** the sentence about expanding entries is on its own line in the description.

## 2.0.91 - 2026-09-26
- **Logs tab:** the search box placeholder now reads "Search the logs..." ("Szukaj w logach...").

## 2.0.90 - 2026-09-26
- **Logs tab:** the Refresh and Clear logs buttons sit between two rules under the summary tiles; the "Shown: N of N" count moved next to the service chips.

## 2.0.89 - 2026-09-26
- **History tab:** URL scans are listed with the plain address (`https://host.tld/`) instead of the defanged one (`hxxps://host[.]tld/`); older entries are shown the same way. The links stay non-clickable.

## 2.0.88 - 2026-09-26
- **History tab:** new layout. The description is split into two lines; the action buttons (Refresh, Export, Clear history, count) sit between rules under the tiles; the date chips are on the left and the risk chips on the right of one row; the search box is above the list with the compare hint and button beside it.

## 2.0.87 - 2026-09-26
- **History tab:** the description is reworded into shorter sentences (what is stored, what "Clear history" removes, how e-mail analyses and AbuseIPDB reports are handled).

## 2.0.86 - 2026-09-26
- **AbuseIPDB tab:** the optional Attacked port field is removed (the tab is for e-mails only, which do not carry the attacked port). Ports the LLM writes in the comment are still stripped.

## 2.0.85 - 2026-09-26
- **AbuseIPDB tab:** the source port read from `Received` is gone again (it is the sender's random port, not the attacked one). New optional **Attacked port** field: the destination port on the victim side is appended to the comment as "Target port: N.". Ports the LLM writes are still stripped.

## 2.0.84 - 2026-09-26
- **AbuseIPDB tab:** any port the LLM writes in the comment is removed; only the port read from the `Received` header (or none) can reach AbuseIPDB.

## 2.0.83 - 2026-09-26
- **AbuseIPDB tab:** when the `Received` header of the reported hop states the connecting client's port, the comment ends with "Source port: N." (LLM text and fallback alike); when it does not, no port is mentioned.

## 2.0.82 - 2026-09-26
- **AbuseIPDB tab:** the LLM notice and the check-before-sending warning moved from a separate banner into the tab description.

## 2.0.81 - 2026-09-26
- **AbuseIPDB tab:** the check-before-sending warning sits on its own line in the banner; the personal-data hint now asks you to check whether the data is yours and to mask or remove it before sending.

## 2.0.80 - 2026-09-26
- **AbuseIPDB tab:** the banner now says the content goes to an LLM agent (no provider name) and adds a bold warning to always check the proposed report before sending it to AbuseIPDB.

## 2.0.79 - 2026-09-26
- **DMARC tab:** only the IP sources section is open by default; the providers table, the chart, the comparison and the reports are folded cards. The glossary now also explains the risk levels, the tiles (suspicious, pass rate, decisions, overrides), geo/rDNS/known sender, the fix hints and the comparison with the chart.

## 2.0.78 - 2026-09-26
- **DMARC tab:** the uploaded reports come right after the IP sources; the providers table, the chart and the comparison follow.

## 2.0.77 - 2026-09-26
- **DMARC tab:** the IP sources section comes first, right below the summary tiles.

## 2.0.76 - 2026-09-26
- **DMARC tab:** reverse DNS next to the geo data, with a well-known sender named only when its reverse DNS name is forward-confirmed (`backend/known_senders.py`); fix hints per failing source; a bar chart of messages per day; a comparison with the previous import of the same domain (from the History); the list of reports is one folded card when there are several; the banner lists every failing address behind an expandable line.

## 2.0.75 - 2026-09-26
- **DMARC tab:** the results banner shows the headline, the addresses, the policy decisions and the advice on separate lines.

## 2.0.74 - 2026-09-26
- **DMARC tab:** the English description matches the Polish one.

## 2.0.73 - 2026-09-26
- **DMARC tab:** a new description; the glossary is a collapsible card, folded by default.

## 2.0.72 - 2026-09-26
- **URLScan tab:** the History list (earlier scans) and the batch list show full addresses as plain, non-clickable text, like the report.

## 2.0.71 - 2026-09-26
- **URLScan tab:** the input hint moved into the label; the visibility buttons look like the buttons of the other tabs and "Advanced options" sits next to them; the action line reads Scan, Scan again, Save .md, Copy Markdown, History, Compare, Open in urlscan.io (state and time at the end); addresses in the report (title, identity, redirects, contacted domains, links, comparison) are shown in full as plain, non-clickable text - the Markdown export and the copy button stay defanged.

## 2.0.70 - 2026-09-26
- **URLScan tab:** the chosen visibility, scan country and user agent are remembered in the browser; advanced options (scan country, user agent: presets or custom) are sent to urlscan.io only when set; a Cancel button stops waiting for a running scan; "Compare with the previous scan" shows what changed since the newest earlier scan of the domain; a "Check domain" button in the identity card; up to 5 addresses can be scanned at once (a list with the risk level of each); a warning when a Public scan would publish an address with parameters such as `token=` or `user:password@`; the note under "Earlier scans" moved into a "?" tip.

## 2.0.69 - 2026-09-26
- **URLScan tab:** the scan visibility drop-down is replaced by three buttons (unlisted, private, public; the description banner stays). The action line now holds all the buttons - Scan, Earlier scans, Save .md, Copy Markdown, Scan again, Open in urlscan.io - with the state and the time always at its end; the buttons below the report are gone.

## 2.0.68 - 2026-09-26
- **IP tab:** the description is shorter and split into three lines (what it does, the sources for an IP address, the sources for a domain).

## 2.0.67 - 2026-09-26
- **HTTP 429 in the Info tab:** when any service answers "limit exceeded", `backend/api_limits.py` remembers it (with the reset date from `Retry-After` / `X-RateLimit-Reset` or from the message, e.g. GreyNoise "reset on September 29") and the "API limits" card marks the row with a "limit exceeded" badge, fills the counter to the limit (only where the count is Seisa's own or comes from headers) and turns the summary line red. The mark disappears after the next successful answer of that service, or when the reset time has passed. AbuseIPDB is tracked per endpoint (check / report).
- The status of a source that reached its limit reads "limit exceeded" instead of "daily limit exceeded" (GreyNoise's limit is weekly).

## 2.0.66 - 2026-09-26
- **IP tab:** the row of jump links moved between the verdict banner (with the comparison line) and the tiles.

## 2.0.65 - 2026-09-26
- **IP tab:** the row of jump links (Summary, Scores, Identity, sources) has a separating line above it, so it no longer runs into the button row.

## 2.0.64 - 2026-09-26
- **GreyNoise HTTP 429** (search limit of the plan used up) is shown as a plain message with the reset date instead of the raw JSON; the full answer stays in the log. The status is `rate_limited_daily`, so the source is excluded from the score and listed in the "sources without a result" bar.
- **Component scores** are open by default again.
- **Legend** brought up to date: domains (voters, identity fields, DNS/WHOIS terms, dangling NS, popularity), local heuristics, comparison with the previous scan, the collapsed identity card and the failed-sources bar.

## 2.0.63 - 2026-09-26
- **Comparison with the previous scan** (`comparison` in the `/api/lookup` answer, built from the History before the new entry is saved and never stored in it): previous score, difference, sources whose risk moved by 10 or more, and a bar per earlier scan.
- **Batch mode:** duplicates are dropped after normalisation, a summary table sorted by score, and "Save CSV" (spreadsheet-formula safe).
- **IP tab:** sources without a result are one collapsed bar; "Component scores" is collapsed; the service chips carry the service names; a single result has no "Refresh" button (Force refresh does the same); a domain report has "Scan in URLScan".
- **Domains:** a delegation to name servers that do not exist (dangling NS) is reported in the domain identity.

## 2.0.62 - 2026-09-26
- **IP tab, domains:** Cloudflare Radar now uses the ranking endpoint (`/radar/ranking/domain/{domain}`: rank, popularity bucket, categories); the old entity URL answered `HTTP 400 No route for that URI`. WHOIS is joined by DNS records (A, AAAA, NS, MX, CAA, SPF, DMARC, wildcard; new dependency `dnspython`). A **domain identity** card (registrar, dates, age, name servers cross-checked between WHOIS and DNS, addresses with a "check this IP" button, category, popularity), domain tiles, and local heuristics as a low-credibility score source (`backend/domain_heuristics.py`).
- **Input normalisation** (`normalize_indicator`): a pasted URL, a defanged indicator, `ip:port`, `user@host`, upper case and IDN are reduced to the bare host or IP; private, loopback and reserved addresses get 400 with an explanation instead of being sent to the services.
- **UI:** "Force refresh" sits next to "Batch mode"; the copy button reads "Copy IP" / "Copy domain" and has the size of the other buttons; "Open in Talos" ends the button row; the identity card is collapsed (green "sources agree") and opens by itself on a disagreement; the WHOIS / rDNS card lists the identity rows it supplies; the subtitle describes domain scans.
- The harness imports the application only after the data paths are patched (before, an early import made it write to the real `data/`).

## 2.0.61 - 2026-09-26
- **IP tab, single mode accepts domains:** the frontend sends `type: "auto"` and the backend detects an IP address or a host name (as batch mode already did). The domain itself is queried (VirusTotal, OTX, WHOIS and the other services that support domains); it is deliberately not resolved to an IP, because a CDN address would describe the CDN, not the domain.
- Labels and the batch hint say "IP address or domain"; the harness has a `lookup domain auto` case; README and docs updated.

## 2.0.60 - 2026-09-26
- **Origin guard for `/api/`** (`OriginGuardMiddleware` in `backend/main.py`): a request with `Sec-Fetch-Site` other than `same-origin`/`none` (so also `same-site`), or with an `Origin` whose host is not `127.0.0.1`/`localhost` (including `null`), gets 403. Before, a page in another browser tab could fire a plain GET (an `<img>` tag) or a body-less POST at the API without a preflight and use up the urlscan/AbuseIPDB/RDAP quotas or the LLM budget (it could not read the answers). Requests without these headers (curl, scripts, older browsers) still pass, and static files stay open. The log gets at most one warning a minute about blocked requests.
- The harness (`scripts/api_harness.py`) probes the guard (blocked and allowed cases, a preflight, a body-less POST) and asserts that a `text/plain` cross-site POST never reaches a handler.
- The docs now say plainly that there is no authentication: any local process can call the API and read what Seisa stores, and the origin guard is not a defence against it (`docs/{en,pl}/privacy-and-security.md`, README). New troubleshooting entry for the 403.

## 2.0.59 - 2026-09-26
- **DMARC tab:** the "geo" button no longer makes the browser call `ipwho.is`. A new `GET /api/dmarc/geo` (`backend/routers/dmarc.py`) asks RDAP through the same service as the IP tab and returns the registration country, the owner and the network name (only global addresses; private ones get 400). RDAP has no ASN, so it is no longer shown. The button is labelled "geo (RDAP)".
- The Content-Security-Policy is now `connect-src 'self'`: the frontend calls no third-party host. The privacy tables, the tab description and the API list (README, `docs/{en,pl}`) are updated.

## 2.0.58 - 2026-09-26
- **Documentation:** the single-page README (758 lines) split into a short `README.md` / `README.pl.md` (landing, quick start, keys, privacy overview, documentation index) and a documentation set in `docs/en/` and `docs/pl/` (`index`, `tabs`, `configuration`, `privacy-and-security`, `architecture`, `api`, `extending`, `troubleshooting`). This reverses the "everything on one page" decision of 2.0.57. The two prompt-context files directly in `docs/` are unchanged.
- `scripts/check_i18n.py` checks the parity of `docs/en` and `docs/pl` (the same files, the same heading levels) and dead relative links and anchors in the Markdown files.
- The start script message and a code comment point to the current sections.

## 2.0.57 - 2026-09-25
- **Documentation:** `README.md` and `README.pl.md` rebuilt with one structure: a landing section, a quick start, a configuration and limits section, a privacy table ("what leaves your machine", including `rdap.org` and WHOIS lookups that the old text left out), a threat model, an LLM cost table, one section per tab with the details in collapsible blocks, a walkthrough, a guide for developers and forks (design decisions, endpoints, data files, security invariants, how to extend), troubleshooting and a changelog summary.
- The full `CHANGELOG.md` (this file) added. `SECURITY.md` now names `logs/` instead of the pre-2.0.27 `logi/`.

## 2.0.56 - 2026-09-25
- **Info:** new collapsed **API limits** card with the free-plan limits of every service that has a key. VirusTotal, urlscan.io and OpenRouter report their real quota on an explicit "Refresh limits" click; AbuseIPDB and Cloudflare Radar come from rate-limit headers; GreyNoise and OTX are counted by Seisa.
- The VirusTotal tile was removed and the tiles aligned; cards keep their open state; the VirusTotal daily counter now resets at 00:00 UTC.

## 2.0.55 - 2026-09-25
- **Info:** privacy banner removed; cards in the order Service status (collapsed), Author, Name, Recent changes (collapsed), License (collapsed).

## 2.0.54 - 2026-09-25
- **Email:** all Lesson cards start collapsed; a "Show source" button next to "Ask".

## 2.0.53 - 2026-09-25
- **Email:** the Received table in the Facts pane no longer gets huge row heights (six columns, hostnames wrap, the notes columns keep a usable width).

## 2.0.52 - 2026-09-25
- **Email:** card titles and the table of contents follow the streamed headings instead of keeping the first cut-off fragment.

## 2.0.51 - 2026-09-25
- **Info:** redesigned like the other tabs: summary tiles (version, API keys set, LLM model), integration status card (never the keys), collapsible name, license and author cards, recent releases from the git log. New endpoint `GET /api/about`.

## 2.0.50 - 2026-09-25
- **History:** redesigned: clickable summary tiles, risk and date chips, search, cards grouped by day with a pinned group, "earlier rating" marker, Repeat for IP and URL scans, pinning that survives the size limit and "Clear history", comparison of two IP checks, JSON/CSV export, two-click delete.

## 2.0.49 - 2026-09-25
- **Logs:** redesigned: summary tiles, level and service filter chips with counts, message search, collapsible entry cards with copy, auto-refresh, "Clear logs".

## 2.0.48 - 2026-09-25
- **AbuseIPDB:** redesigned: verdict banner, summary tiles, address card with a "Use this address" button on every hop, report card with category hints, personal-data scan and masking, API payload preview, collapsible checks.
- API errors (daily quota, same-IP rule, 422, key) turn into readable messages with the rate-limit headers; log of sent reports with the daily limit, reports listed in History, Markdown export.

## 2.0.47 - 2026-09-25
- **Email:** redesigned: verdict banner, summary tiles, Overview / Facts / Lesson panes with a table of contents, route diagram, fact cards that open on a signal, lesson split into collapsible cards, evidence quotes with a source drawer, glossary tooltips, search, follow-up questions to the LLM, comparison of two analyses, HTML export.

## 2.0.46 - 2026-09-25
- **URLScan:** earlier scans of the same domain; a Forms card read from the scanned page's DOM (a password form posting elsewhere lifts a weak verdict to Medium); a URLScan button next to links in the Email tab.

## 2.0.45 - 2026-09-25
- **URLScan:** redesigned like IP and DMARC: verdict banner, summary tiles, screenshot served by the backend, page identity card with the redirect chain, collapsible detail cards, visibility choice, URL cleaning and validation, History entries with a thumbnail.

## 2.0.44 - 2026-09-25
- **IP:** redesigned: verdict banner, summary tiles, a merged address identity card with per-field source agreement (majority value, RDAP priority on a tie), collapsible source cards that open only on a signal, raw API data only under "Full API response".

## 2.0.43 - 2026-09-25
- **DMARC:** slim one-line drop zone, folded file list (opens on skipped or failed files), even spacing of the action row, aligned summary tiles.

## 2.0.42 - 2026-09-25
- **DMARC:** loaded file names in the drop zone laid out in an aligned two-column grid.

## 2.0.41 - 2026-09-25
- **DMARC:** the tab description mentions `.gz` and `.zip`; loaded file names sit side by side in the compact drop zone.

## 2.0.40 - 2026-09-25
- **DMARC:** `.gz` and `.zip` reports, duplicate skipping, provider table, policy hints, override notes, Markdown export, History reopens the full analysis; fixes for capitalised results and empty auth fields.

## 2.0.39 - 2026-09-25
- **DMARC:** redesigned: verdict banner, summary tiles, expandable reports with every metadata and policy field, filterable sources with expandable per-record details, a glossary of SPF, DKIM and policy terms.

## 2.0.38 - 2026-09-25
- The interface language follows the browser again (English for anything other than `en` and `pl`); the footer switch order is `EN | PL`.

## 2.0.37 - 2026-09-25
- The interface defaults to English regardless of the browser language (reverted in 2.0.38).

## 2.0.36 - 2026-09-25
- The Info button glyph changed from the letter I to a dot-over-stroke icon.

## 2.0.35 - 2026-09-25
- The description is a list of what may leave the machine (threat-intel queries, `ipwho.is`, OpenRouter), in the Info tab and both READMEs; a GitHub profile added to the author details.

## 2.0.34 - 2026-09-25
- Info tab description aligned with the README intro.

## 2.0.33 - 2026-09-25
- License section (PolyForm Noncommercial 1.0.0) in the Info tab.

## 2.0.32 - 2026-09-25
- **Info:** new tab (round info button at the far right of the tab row) with the name and version, a description, the meaning of the name and the author details.

## 2.0.31 - 2026-09-25
- Page header reduced to the graphic logo, the name and the version.

## 2.0.30 - 2026-09-25
- **AbuseIPDB:** the LLM now receives the complete raw message source instead of selected headers and a 2000-character excerpt; the partial-content warning is gone.

## 2.0.29 - 2026-09-25
- **AbuseIPDB:** verdict banner border (green = not eligible, red = eligible, none = unknown), white banner text; the eligibility verdict is the first check and blocks sending when the e-mail does not qualify.

## 2.0.28 - 2026-09-25
- Housekeeping: stray log files removed from the repository.

## 2.0.27 - 2026-09-25
- English names in code and on disk: `analyses.py`, `data/analyses/`, `logs/`, English citation kinds (old codes are still read). There is no migration code: releases before 2.0.27 used `data/analizy/` and `logi/`, so rename them by hand (`mv data/analizy data/analyses`, move the `*.jsonl` files from `logi/` to `logs/`).

## 2.0.26 - 2026-09-25
- **Hardening:** indicator validation before URL paths, UUID check for urlscan results, request size limits, refresh button error handling, `requirements.lock`.
- The API harness `scripts/api_harness.py` (the first automated test).

## 2.0.25 - 2026-09-25
- Duplication removed: shared frontend `util.js`, one relay loop for analyze and continue, `sse.py`, `atomic_write_json`, the message parsed once per request; AbuseIPDB categories served by the backend.

## 2.0.24 - 2026-09-25
- Dead code removed, `ruff` configuration and lint clean-up, module docs for routers and frontend.

## 2.0.23 - 2026-09-25
- i18n and consistency fixes: unknown category and empty subject through the catalogs, one age rule with a 1 h clock tolerance, "Finish the analysis" relays warnings, `check_i18n.py --strict` warns about Polish words without diacritics.

## 2.0.22 - 2026-09-25
- `seisa.sh` detects the system (macOS `open`, Linux `xdg-open`, otherwise it prints the address) and checks for `.venv`; README install notes for macOS and Linux.

## 2.0.21 - 2026-09-25
- Publication hygiene: private references removed, the AbuseIPDB policy summarised in own words, `.gitignore` / `.gitattributes` / `.gitkeep`, `SECURITY.md`, English-first `CONTRIBUTING.md`, the version under the logo, `ipwho.is` documented, the analyses directory forced to 0700, a version consistency check.

## 2.0.20 - 2026-09-25
- **Security:** report HTML sanitised by an allow-list (stored XSS), the DMARC source IP escaped, the history detail rendered as text, a loopback-only `Host` header (DNS rebinding), a Content-Security-Policy.

## 2.0.19 - 2026-09-25
- **AbuseIPDB:** what AbuseIPDB already knows about the IP before reporting, your own earlier reports and the 15-minute cooldown (button disabled, HTTP 409); only the local part of the Message-ID in the fallback comment.

## 2.0.18 - 2026-09-25
- **AbuseIPDB:** no false "qualifies" without an LLM, detection of a test sent to yourself, a three-state Spoofing check, red / green / neutral banners, a timestamp timezone fix (UTC for the API).

## 2.0.17 - 2026-09-25
- **Email:** repeated link findings collapse into one with a count.

## 2.0.16 - 2026-09-25
- Timer, status, tokens and cost and related buttons shown next to the action button in every tab; the Logs default filter is "All".

## 2.0.15 - 2026-09-24
- English `README.md` (the main one) and `README.pl.md`; bilingual conventions; English `.env.example`.

## 2.0.14 - 2026-09-24
- LLM answers in the interface language (English guide and prompts plus a language directive); the language is stored with analyses and history, language badges and a re-analysis notice.

## 2.0.13 - 2026-09-24
- Backend i18n (`X-Seisa-Lang`, `backend/i18n.py`, locales) for messages, forensics, scoring and reports; English comments and logs; synthetic fixtures and the golden dump script.

## 2.0.12 - 2026-09-24
- Email tab and its Markdown export translated (PL/EN).

## 2.0.11 - 2026-09-24
- A language-neutral verdict protocol (`VERDICT` / `CONFIDENCE` codes); legacy Polish tokens are still read.

## 2.0.10 - 2026-09-24
- AbuseIPDB tab translated (PL/EN).

## 2.0.9 - 2026-09-24
- IP, URLScan and DMARC tabs and the report rendering translated (PL/EN).

## 2.0.8 - 2026-09-24
- i18n infrastructure: PL/EN catalogs, the footer language switch, the `X-Seisa-Lang` header, `scripts/check_i18n.py`; History and Logs translated.

## 2.0.7 - 2026-09-24
- `CONTRIBUTING.md` (no external code changes).

## 2.0.6 - 2026-09-24
- License changed from MIT to PolyForm Noncommercial 1.0.0.

## 2.0.1 - 2.0.5 - 2026-09-24
- README fixes; the round logo and favicon with the kanji 査; a MIT license for a single release (replaced in 2.0.6).

## 2.0.0 - 2026-09-24
- The project is renamed **Seisa** (精査): a new logo with the kanji, a path-independent `seisa.sh`, `window.seisaApp`, README and documentation.

## 1.x - before the rename (2026-09-22 to 2026-09-24)

Releases 1.1 to 1.1.18, published under the project's earlier name. In short:

- **1.1 - 1.1.1:** the first version: IP and domain reputation from VirusTotal, OTX, urlscan.io, Cloudflare Radar, AbuseIPDB, GreyNoise and WHOIS/rDNS; a DMARC report viewer; AbuseIPDB report preparation; an optional LLM layer through OpenRouter. The AbuseIPDB workflow was reworked so that the checklist is informational and only the deterministic hard checks gate sending.
- **1.1.2:** source-IP detection in multi-hop `Received` chains (a boundary walk instead of "the first public address"), with an independent LLM cross-check.
- **1.1.3 - 1.1.4:** reports aligned with the real AbuseIPDB API (only `ip` and `categories` are required); automatic detection of double-extension attachments; the report comment written by the LLM in English from the facts and the raw message.
- **1.1.5:** the IP tab limited to IP addresses and a new URLScan tab with live scans.
- **1.1.6:** full RDAP, the GreyNoise `/v3/ip` lookup with a community fallback, DMARC alignment and per-record `auth_results`.
- **1.1.7 - 1.1.8:** a fixed order of services and the noisy-OR aggregate score (thresholds 25 and 60) with richer OTX data.
- **1.1.9 - 1.1.12:** the Email tab: deterministic analysis, streamed LLM analysis, truncation detection with "Finish the analysis", exports, recipient anti-spam filters, duplicate detection and the citation check.
- **1.1.13 - 1.1.18:** the `open_router` log service, `.eml` loading in the AbuseIPDB tab, the History of the last 25 actions, robustness against malformed model JSON, relay walking when choosing the sender IP, ARC and `X-MS` authentication results.

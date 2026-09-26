# Changelog

All notable changes to Seisa, newest first. Every release raises the version by 0.0.1 (after `X.Y.99` comes `X.(Y+1).0`), so the list is complete. The current version is shown in the page header and under the logo in [README.md](README.md).

Version 2.0.0 is the first release under the name Seisa. The 1.x releases came before the rename and are summarised at the bottom.

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

<p align="center"><img src="frontend/logo.png" alt="Seisa" width="120"></p>

# Seisa

**English** | [Polski](README.pl.md)

A local tool for IP reputation analysis, URL scanning (urlscan.io), DMARC reports and preparing AbuseIPDB abuse reports. It runs **locally only** (`127.0.0.1`), with no login and without sending anything out except the explicit queries to the selected threat-intel services.

**Seisa** (精査, *せいさ*, pronounced roughly "say-sah") is a Japanese word meaning a thorough, detailed examination - looking at something closely. 精 (*sei*) = precise, exact, detailed; 査 (*sa*) = to examine, to inspect.

Author: Arkadiusz Polak <kontakt@arkadiuszpolak.pl>

## Features

### IP
You enter an IP address (IP only - URL/domain analysis lives in the separate URLScan tab) and the tool queries in parallel:

| Service | What it provides |
|---|---|
| [VirusTotal](https://www.virustotal.com) | AV engine detections, reputation, ASN, categories, tags, WHOIS |
| [AlienVault OTX](https://otx.alienvault.com) | threat-intel pulses, geolocation, ASN |
| [Cloudflare Radar](https://radar.cloudflare.com) | network/context data - ASN, location, routing (not a verdict) |
| [AbuseIPDB](https://www.abuseipdb.com) | confidence score, number of reports, author of the latest report, ISP |
| [GreyNoise](https://www.greynoise.io) | full IP Lookup (`/v3/ip`) - actor, tags, VPN/Tor, network metadata; falls back to the free community endpoint if the key has no access to the full API; "no information in the service" counts as a contribution of 0.0, not as "unknown" |
| WHOIS / rDNS | reverse DNS (PTR) + full RDAP (RFC 9083, the successor of WHOIS) - network range, owner, abuse/technical contact, registration dates - no API key needed |
| Cisco Talos | no official API - only a button for a manual check |

The result is one **aggregate score** 0-100 (a noisy-OR model: every source - AbuseIPDB, VirusTotal, GreyNoise, OTX - gives a risk of 0-100 on a non-linear scale and has its own credibility; a source without data does not vote, a known good IP lowers the score to 15; thresholds: <25 LOW, 25-59 MEDIUM, ≥60 HIGH; logic in `backend/scoring.py`; Cloudflare Radar is contextual and deliberately excluded from the number) and a full Markdown report with the data of every service - including the raw API response in a collapsible section, for your own analysis.

It supports batch mode (many IP addresses at once, with a visible VirusTotal throttle - 4 requests/min, 500/day) and an in-memory cache (15 min), with an option to force a refresh.

The report can be saved as `.md` (the browser's native save dialog) or copied.

### URLScan
Orders a live scan of the given URL through the [urlscan.io API](https://urlscan.io/docs/api/) (`POST /api/v1/scan/`, then polling `GET /api/v1/result/{uuid}/` every 5 seconds until the result is ready - urlscan.io returns 404 while the scan is running). Every scan is submitted with:

- **`unlisted` visibility** - it does not appear on the urlscan.io front page or in the public search results, but stays visible to verified security researchers in urlscan Pro,
- **the default user agent** (no `customagent`) and **automatic choice of the scan country** (no `country`) - both fields are deliberately left out of the request.

The result shows the API response in as much detail as possible, formatted as readable text: a page summary (final URL after redirects, title, domain, IP, ASN, geolocation, HTTP server, status), the TLS certificate, the urlscan.io verdict (malicious score, categories, detected brands), statistics (number of requests, unique domains/IPs/countries/ASNs, cookies), detected technologies, the list of contacted IP addresses and domains, and the links found on the page. At the end, in a collapsible "Full API response" section, the whole raw response as code with line numbers - the same as in the IP tab.

### DMARC
Drag and drop aggregate DMARC XML reports (from Google, Microsoft etc.) - the tool parses them 100% in the browser (no files are sent anywhere), aggregates by source IP address, shows SPF/DKIM pass/fail, alignment (adkim/aspf) and the policy (p/sp/pct) from every report. The "Records" button next to each IP expands the full detail of every single record - header/envelope from, the reason of a policy override (`policy_evaluated > reason`) and the raw `auth_results` outcome (domain/selector/result for DKIM, domain/scope/result for SPF) - exactly what lets you diagnose *why* alignment failed, not just that it did. From every IP row you can jump straight to a full reputation check (IP tab) or to preparing an AbuseIPDB report.

### Email
An educational analysis of the e-mail source: paste the whole source (headers + body) or load an `.eml` file (UTF-8 or windows-1252, the mbox envelope and line endings are normalised; binary base64 attachments do not go to the model - only their size and sha256 stay, while text base64 parts are decoded).

- **Deterministic analysis (immediately, locally, without an LLM)**: findings about anomalies, the Received route with the role in the chain of trust, authentication (SPF/DKIM/DMARC/ARC, authserv-id, signed and unsigned headers, `bh=` length), domain alignment relative to `From`, a UTC timeline, epoch conversions, the MIME tree, attachments (sha256, double extensions), links (text vs `href`), hidden content, HTML comments, template placeholders, the recipient's anti-spam filters (SCL/BCL/CAT, the Junk target folder, AuthAs, the decoded X-Message-Delivery) and flags set by the sender (X-Message-Flag, Importance, read-receipt requests). When the whole Received chain belongs to one operator (e.g. Microsoft), the table marks the oldest entry as the trust boundary. Identical findings caused by repeated links are reported once with a count, e.g. `(x4)`. The logic is in `backend/email_forensics.py`; nothing from the message is opened or downloaded.
- Below the separator: a **detailed LLM analysis** (OpenRouter, the same key and model as in AbuseIPDB), streamed live, following the guide `docs/email-analysis-guide.md` (mental model, a line-by-line analysis of both the good and the bad elements, a checklist, traps, an assessment, control questions with answers in collapsible sections). The first line of the answer is the verdict with a confidence level.
- The response limit of the model is 64000 tokens (counted together with the hidden reasoning of the model, about 45% of the output; it is a ceiling, you pay for the tokens actually generated). If the analysis is cut off anyway, the tab shows a warning and a **"Finish the analysis"** button (the model receives the text so far and writes the missing parts; token usage and cost add up in the saved analysis).
- **"Save .md"** and **"Copy Markdown"** (the export labels follow the interface language at the moment of export, the text of the LLM analysis stays in the language it was written in) export the whole set: metadata (date, verdict, model, input/output tokens, cost), the whole deterministic analysis (tables) and the LLM analysis.
- **Duplicate detection:** before a paid analysis Seisa checks the fingerprint (sha256 of the normalised source) in `data/analizy/`. If the message was already analysed, it offers to open the saved analysis (with the date, verdict and cost) or to run it again deliberately.
- **Citation check (local, free):** after the analysis the code checks whether the IP addresses, the header lines quoted in code blocks, `Header: value` quotes, SCL/BCL numbers and identifiers given by the model appear in the source or in the deterministic analysis (`backend/citation_check.py`). Discrepancies are listed under the analysis and in the `.md` export; this is information, not proof of an error (an example or a paraphrase may be flagged too). It does not check domains or entries such as `spf=pass`, because the analysis also discusses examples of a legitimate message.
- The LLM analysis does not reproduce the tables visible in the deterministic analysis (timeline, links, Received etc.), it only interprets them, so that you do not pay for repetition; the complete set is in the export.
- The LLM output is rendered safely: raw HTML from the e-mail and links are neutralised (links are shown as non-clickable, defanged text).
- **Analysis language:** the analysis is written in the interface language (a directive in the prompt plus a table of literal headings and tags `[Fakt]`/`[Fact]` for both languages in `docs/email-analysis-guide.md`); the language is stored in the record (`lang`; older records = Polish). "Finish the analysis" uses the language of the stored record, not the current interface language. A saved analysis in a language other than the interface is marked with a PL/EN badge, and opening it shows a banner with a paid re-analysis button (the cost of the previous one is given as a guide); the facts and the text stay in the language they were created in, while the labels and the .md export use the interface language. Duplicate detection (sha256 of the source) does not depend on the language: the banner shows the language of the existing analysis.
- **Verdict protocol:** the first line of the model answer has the form `VERDICT: <legit|phishing|spam|scam|malware|inconclusive> | CONFIDENCE: <high|medium|low>` and always uses these canonical codes, whatever the language of the analysis (`backend/verdict.py`); the interface maps them to labels in the selected language. Analyses saved earlier with Polish tokens (`WERDYKT`/`PEWNOSC`) are read without any file migration.
- The **"Report to AbuseIPDB"** button (visible only when the verdict is not `legit`, i.e. legitimate) pastes the original source into Step 1 of the AbuseIPDB tab (overwriting the field) and takes the user there.
- Every completed analysis is saved together with the raw e-mail in `data/analizy/` (files 0600, gitignored); the list of saved analyses (open/delete) is at the bottom of the tab.

### AbuseIPDB (reporting)
A workflow compliant with the [AbuseIPDB reporting policy](docs/abuseipdb-reporting-policy.md) (60-day limit, no reporting based on the confidence score alone, the 1024-character comment limit etc.):

1. **Paste the raw source of the suspicious e-mail** (headers + body) - optional, you can also start from the IP alone (the "Report to AbuseIPDB" button in the IP/DMARC tab).
2. The backend extracts the facts deterministically: the trusted source IP address (the algorithm goes from the newest `Received` header downwards and looks for the first hop whose "from" host no longer belongs to the same domain as the "by" host of the newest hop - in multi-hop chains of large providers, e.g. Microsoft 365/Outlook.com, the first few hops are internal transfers of the same provider and are skipped, so that their address is not taken instead of the real sender), together with a confidence level (`ip_confidence`) and the full chain of hops for inspection (the expandable list "Received chain - why this IP" in Step 1). In addition: the SPF/DKIM/DMARC result, attachments (with detection of double extensions such as `invoice.pdf.exe`), the Message-ID, BTC address/ransom demand patterns. **The hard checks (age of the attack, whether the IP is private) are always computed in Python and are never delegated to the LLM.**
3. Optionally (if `.env` has `OPENROUTER_API_KEY`) an LLM through **OpenRouter** assesses whether the e-mail qualifies for a report, independently verifies the IP address chosen by the code on the basis of the raw headers (`source_ip_check` - if it disagrees, Step 1 shows a clear warning banner with the model's suggestion, informational only), assesses the fit of the suggested categories and possible PII in the comment - and **writes a ready, detailed report comment in English**, based on the facts, the raw headers (including Subject/Reply-To/spam indicators if present) and an excerpt of the message body (HTML converted to plain text) - see point 4. Without a key the tool works in rule-based mode.
4. **The report comment is an editable field in Step 2, filled with what the LLM wrote** - `comment` is an optional field in the AbuseIPDB API ([`/report`](https://docs.abuseipdb.com/#report-endpoint), only `ip` and `categories` are required), but the AbuseIPDB policy itself expects a detailed, technically justified description - hence the LLM writes the comment (attack mechanism, meaning of SPF/DKIM/DMARC, malicious attachments with a detected double extension such as `invoice.pdf.exe`, a ransom/BTC demand, mass-mailing patterns), within about 900 characters. Without an LLM (or when the analysis fails) a poorer, deterministic fallback built solely from the facts is used. In both cases the text is fully editable before sending, and the backend sanitises/truncates it to 1024 characters right before sending anyway. If you know the port number, add it by hand.
5. A form with a character counter (limit 1024) computed locally, without backend calls at every edit of the comment.
6. **The checklist is informational only**, it does not block sending - the three hard checks (age, IP, category - exactly what the API requires) are always computed by the Python code and only they gate the "Send" button; the five further items (Received, not a spoofed source, Spoofing, category fit, PII redaction) are a hint to read before sending. Received and Spoofing come from the facts of the e-mail; the others from the same LLM analysis of Step 1 (without an LLM they stay as "requires AI analysis"). Spoofing is one of three states, always with a short reason: detected (SPF/DMARC fail), not detected (authentication passed) or cannot be assessed (no or ambiguous SPF/DKIM/DMARC results in the pasted source).
   The verdict banner above the form has a coloured border: red = does not qualify, green = qualifies, no colour = not assessed. Without an LLM the tool never claims that an e-mail qualifies: it only checks the hard criteria (public IP, age) and recognises the obvious case of a test sent from your own account to yourself (sender = envelope sender = recipient, no sign of an attack). The attack timestamp is taken from the `Date` header and shown in the browser's local time; it is sent to AbuseIPDB in UTC (ISO 8601).
7. Sending through the AbuseIPDB API (the backend validates the hard checks anew, independently of the state of the form in the browser) **or** copying the comment for manual pasting on the website.

### History
The last 25 actions: IP lookups, DMARC imports and saved e-mail analyses (reopened in the Email tab), which you can reopen or delete. "Clear history" removes only IP and DMARC entries; e-mail analyses (with the raw messages) are deleted one by one.

### Logs
Errors and warnings (WARNING level and above) from every service - normal, error-free operation of the tool leaves no trace on disk. Filtering by date range (today / 3 days / week / month / all; the default is all) and by service (the default is all). All OpenRouter API errors (Email and AbuseIPDB tabs: limits, insufficient credits, provider errors, timeouts) go to a single `open_router` service; the other application errors go to `app`.

### Interface language (PL/EN)
The `PL | EN` switch is in the footer. The choice is remembered by the browser (`localStorage`, key `seisa.lang`); without a stored choice the browser language is used (`pl` or `en`), and English in all other cases. Changing the language reloads the page (you are asked first if that would lose work in progress). The interface texts live in the catalogs `frontend/i18n/pl.json` and `en.json` (flat keys, `{name}` parameters, plural forms through `Intl.PluralRules`), dates use the `pl-PL` or `en-GB` format. The development mode `/?lang=qa` shows `[[key]]` instead of texts, so places that bypass the translations are visible at once. The frontend sends the selected language in the `X-Seisa-Lang` header (only to its own backend) and the backend translates error messages, the deterministic e-mail analysis, the IP scoring notes and the Markdown reports on its side (catalogs `backend/locales/pl.json` and `en.json`, module `backend/i18n.py`). Analyses and history entries saved earlier keep the language they were created in. The logs (Logs tab) are in English regardless of the interface language. LLM answers (Email and AbuseIPDB tabs) are written in the interface language of the moment of the request; the prompts and guides are single, in English, and the answer language is set by an explicit directive (the AbuseIPDB report comment is always in English - an AbuseIPDB policy requirement). The cost of requests depends on the model, and an English prompt is usually a little shorter (in an A/B test on a synthetic message about 8% fewer input tokens than before).

## Architecture

A single **Python FastAPI** process (`backend/`) serves both the API and the static frontend (`frontend/` - plain JavaScript, ES modules, no framework and no build step) on `127.0.0.1:54321`.

```
seisa/
├── .env                    # API keys (gitignored, see .env.example)
├── seisa.sh                 # start script (alias `seisa` in ~/.zshrc)
├── README.md / README.pl.md  # this documentation in English (the main one on GitHub) and in Polish
├── LICENSE                  # PolyForm Noncommercial 1.0.0 license
├── CONTRIBUTING.md          # contribution rules (no external code changes)
├── backend/
│   ├── main.py               # FastAPI, routing, no-cache and language middleware, error handling
│   ├── config.py             # paths, settings from .env
│   ├── models.py             # Pydantic models
│   ├── aggregator.py         # fan-out to the services, aggregate risk score
│   ├── markdown_report.py    # Markdown report builder
│   ├── ratelimit.py          # VirusTotal throttle
│   ├── cache.py              # in-memory result cache
│   ├── storage.py            # atomic history storage (JSON)
│   ├── logging_config.py     # WARNING+ logs to logi/*.jsonl
│   ├── email_parser.py       # fact extraction from the raw e-mail (AbuseIPDB tab)
│   ├── email_forensics.py    # deterministic analysis of the e-mail source (Email tab)
│   ├── analizy.py            # storage of e-mail analyses in data/analizy/
│   ├── i18n.py               # backend translations: request language (ContextVar), t()/tn(), catalogs in locales/
│   ├── locales/              # backend text catalogs: pl.json, en.json
│   ├── verdict.py            # canonical verdict protocol (EN codes, mapping of the old PL tokens)
│   ├── scoring.py            # aggregate IP reputation score (noisy-OR)
│   ├── report_builder.py     # AbuseIPDB comment builder + policy validation
│   ├── report_utils.py       # text sanitisation, IP checks
│   ├── urlscan_report.py     # Markdown report builder for a urlscan.io scan result
│   ├── routers/               # /api/* endpoints
│   └── services/               # a client for every service (common IntelService interface; urlscan.py separately - submit+poll, not an IntelService)
├── frontend/
│   ├── index.html
│   ├── favicon.ico            # icon: the kanji 査 (16/32/48/64 px)
│   ├── logo.png               # round logo (page header and README)
│   ├── css/style.css          # dark theme
│   ├── i18n/                  # interface text catalogs: pl.json, en.json
│   ├── js/                    # modules: app, i18n, lookup, urlscan, dmarc, email, report-builder, history, logs
│   └── vendor/marked.min.js   # Markdown rendering, bundled locally (no CDN)
├── tests/fixtures/          # SYNTHETIC e-mails (.eml) for comparisons; entirely fictitious data (.example domains, documentation address ranges), no personal data
├── scripts/
│   ├── dump_facts.py          # dumps the deterministic analysis of the fixtures to JSON (compares two code versions byte for byte)
│   └── check_i18n.py          # checks the PL/EN catalogs (keys, parameters, plurals); `--strict` looks for Polish literals in code
├── data/                    # history.json, vt_usage.json, report_log.json, analizy/ (gitignored)
├── logi/                    # error logs, one .jsonl file per day (gitignored)
└── docs/
    ├── abuseipdb-reporting-policy.md   # the full policy + the AbuseIPDB category table (English, LLM prompt context)
    └── email-analysis-guide.md         # e-mail analysis guide loaded into the LLM prompt (Email tab), English, with a PL/EN label table
```

There is no database - all persistence is plain JSON files in `data/` (history limited to 25 entries, the VirusTotal daily limit counter) and logs in `logi/`.

## Installation

Requires Python 3.11+.

```bash
cd seisa
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with real API keys (the keys are described below).

## Running

The simplest way is the terminal shortcut (added to `~/.zshrc`):

```bash
seisa
```

It starts the server and automatically opens the browser at `http://127.0.0.1:54321`.

Manually:

```bash
cd seisa
./.venv/bin/uvicorn backend.main:app --port 54321 --host 127.0.0.1
```

## API keys (`.env`)

| Variable | Required? | Where to get it |
|---|---|---|
| `URLSCAN_API_KEY` | yes, for urlscan.io | [urlscan.io/user/signup](https://urlscan.io/user/signup) |
| `VIRUSTOTAL_API_KEY` | yes, for VirusTotal | [virustotal.com](https://www.virustotal.com) |
| `OTX_API_KEY` | yes, for OTX | [otx.alienvault.com](https://otx.alienvault.com) |
| `CLOUDFLARE_RADAR_API_KEY` | yes, for Cloudflare Radar | [dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens) - **it must be a scoped API Token with Radar read permission, not the old Global API Key** (the latter gives a 401 error) |
| `ABUSEIPDB_API_KEY` | yes, for AbuseIPDB (reading and reports) | [abuseipdb.com](https://www.abuseipdb.com) |
| `GREYNOISE_API_KEY` | yes, for GreyNoise | [greynoise.io](https://www.greynoise.io) |
| `OPENROUTER_API_KEY` | no, optional | [openrouter.ai](https://openrouter.ai) - enables the LLM analysis in the Email tab and the eligibility assessment and draft report comment in the AbuseIPDB tab |
| `OPENROUTER_MODEL` | no | `anthropic/claude-sonnet-4.5` by default - verify the exact slug on the OpenRouter model list |

A missing key for any service does not block the rest of the tool - the service simply shows the status "no API key" and is excluded from the aggregate score.

## Security and privacy

- Everything runs on `127.0.0.1`, without authentication - a single-user tool, do not expose port 54321 to the outside.
- API keys are kept only in `.env` (gitignored), never in the frontend code.
- DMARC XML parsing happens entirely in the browser.
- The content of a pasted e-mail goes to OpenRouter **only** after an explicit click on "Analyze" (not "Analyze without LLM") - the interface says so plainly before sending.
- AbuseIPDB tab: the "Load .eml file" button (also dragging a file onto the field), a timer of the analysis and the tokens and cost after the "Analyze" analysis, shown next to the buttons.
- Detection of the sender IP in the AbuseIPDB tab: when the first hop outside the recipient's domain is only a relay of an operator (e.g. Microsoft Exchange Online), the parser walks through the operator's internal hops to the hop where the address of the connecting sender was recorded. If the message originated inside a shared provider (e.g. a hotmail account) and there is no public sender IP, the IP stays empty (confidence low). Authentication results are also read from `X-MS-Exchange-Authentication-Results` and `ARC-Authentication-Results`. After an analysis with an LLM the tab shows how much of the content the model saw (the first 2000 characters), and the hard checks (IP, age) take precedence over the opinion of the model.
- A report to AbuseIPDB always requires a deliberate click on "Send"; the backend validates the hard checks (age, IP, category, description) anew regardless of the state of the form in the browser - they, not the informational checklist, decide whether sending is possible.
- The Email tab sends the whole source of the message (with personal data) to OpenRouter after a click on "Analyze"; this is a deliberate decision (mostly suspicious messages are analysed).
- History, saved e-mail analyses and logs stay only locally in `data/` and `logi/` (gitignored). The analyses contain raw e-mails, so the files have 0600 permissions.

## Versioning and conventions

- The visible version number (page title, header, footer) is increased by 0.0.1 after every change to the tool; after X.Y.99 the next version is X.(Y+1).0. Version 2.0.0 is the first release under the name Seisa.
- Code, comments, docstrings, log messages and commits are in English. The documentation exists in two versions with the same heading structure: `README.md` (English, the main one on GitHub) and `README.pl.md` (Polish); a change in one means a change in the other (the heading structure is compared by `scripts/check_i18n.py`).
- Every tab that runs an action shows the timer (always one decimal, e.g. `13.1 s`), the status (e.g. the loaded file) and any related buttons in one row next to the action button, both during and after the run; in the Email tab the tokens and cost sit there too.
- Texts visible in the interface go exclusively to the `i18n` catalogs (a new key = a PL and an EN entry in the same commit); before a commit `python3 scripts/check_i18n.py` must finish without errors.
- The whole project (code, UI, documentation) avoids the long dash (Unicode U+2014) - only a plain "-".

## Known open issues

- The exact slug of the OpenRouter model (`OPENROUTER_MODEL`) should be verified on the current OpenRouter model list.
- WHOIS/rDNS has no "open the service website" button - it is a direct protocol query, without a single external service to link to.

## License

Seisa is made available under the [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0) license - the full text is in the [LICENSE](LICENSE) file. The code is public (*source-available*), but **this is not an open-source license in the OSI sense**: you may use, copy, modify and distribute it (including forks) only for noncommercial purposes, among others personal, hobby, educational and research use and use by charitable, educational, public and government organisations. Commercial use (including selling, commercial forks and work for the profit of a company) requires a separate permission of the author.

The bundled `frontend/vendor/marked.min.js` remains under its own MIT license (the header in the file).

Rules for reporting bugs and contributing: [CONTRIBUTING.md](CONTRIBUTING.md) - external code changes (pull requests) are not accepted.

<p align="center"><img src="frontend/logo.png" alt="Seisa" width="120"></p>
<p align="center"><b>Seisa 2.0.45</b></p>

# Seisa

**English** | [Polski](README.pl.md)

A local tool for IP reputation analysis, URL scanning, DMARC reports and preparing AbuseIPDB abuse reports. It runs **locally only** (`127.0.0.1`), with no login and without sending anything out except:

- explicit queries to the selected threat-intel services, once the API keys are provided,
- one IP address sent to [ipwho.is](https://ipwho.is) on an explicit click of the "geo/ASN" button in the DMARC tab,
- explicit analyses performed by an LLM through OpenRouter, once the API key and the model are defined.

**Seisa** (精査, *せいさ*, pronounced roughly "say-sah") is a Japanese word meaning a thorough, detailed examination - looking at something closely. 精 (*sei*) = precise, exact, detailed; 査 (*sa*) = to examine, to inspect.

Author: Arkadiusz Polak ([GitHub: arcymonek](https://github.com/arcymonek), e-mail: kontakt (at) arkadiuszpolak (dot) pl). Security issues: see [SECURITY.md](SECURITY.md).

## Features

### IP
You enter an IP address (batch mode also accepts domain names; scanning a URL lives in the separate URLScan tab) and the tool queries in parallel:

| Service | What it provides |
|---|---|
| [VirusTotal](https://www.virustotal.com) | AV engine detections, reputation, ASN, categories, tags, WHOIS |
| [AlienVault OTX](https://otx.alienvault.com) | threat-intel pulses, geolocation, ASN |
| [Cloudflare Radar](https://radar.cloudflare.com) | network/context data - ASN, location, routing (not a verdict) |
| [AbuseIPDB](https://www.abuseipdb.com) | confidence score, number of reports, author of the latest report, ISP |
| [GreyNoise](https://www.greynoise.io) | full IP Lookup (`/v3/ip`) - actor, tags, VPN/Tor, network metadata; falls back to the free community endpoint if the key has no access to the full API; "no information in the service" counts as a contribution of 0.0, not as "unknown" |
| WHOIS / rDNS | reverse DNS (PTR) + full RDAP (RFC 9083, the successor of WHOIS) - network range, owner, abuse/technical contact, registration dates - no API key needed |
| Cisco Talos | no official API - only a button for a manual check |

The result is one **aggregate score** 0-100 (a noisy-OR model: every source - AbuseIPDB, VirusTotal, GreyNoise, OTX - gives a risk of 0-100 on a non-linear scale and has its own credibility; a source without data does not vote, a known good IP lowers the score to 15; thresholds: <25 LOW, 25-59 MEDIUM, ≥60 HIGH; logic in `backend/scoring.py`; Cloudflare Radar is contextual and deliberately excluded from the number) shown as a report: a verdict banner (colour by level, with the values behind it), summary tiles (abuse confidence, detections, GreyNoise, OTX pulses, country, ASN, IP type), the component-score table and an **address identity** card. The card merges owner, ASN, country, network, reverse DNS, usage type and Tor from all sources that report them, after normalising the values (ASN to a number, country to an ISO code, owner names without legal-form suffixes, RDAP ranges to CIDR). Each field shows how many sources agree; where they disagree, the majority value is shown with an amber badge (a click lists every value with its sources), and on a tie the value of the highest-priority source (RDAP first, as the registry) is shown with a red badge. The registration country (RDAP) and the geolocation country are separate fields, since they legitimately differ for hosting and anycast. This affects the display only, not the score (`backend/identity.py`). Below, every source is a collapsible card with the fields that matter, open only for sources with a signal (source risk ≥ 25); lists (tags, CVEs, ports, pulses) are chips with "show more", and the complete API response of each source (with line numbers) sits in a "Full API response" section. The Markdown export contains the whole report, including the identity table.

It supports batch mode (many IP addresses at once, with a visible VirusTotal throttle - 4 requests/min, 500/day) and an in-memory cache (15 min), with an option to force a refresh.

The report can be saved as `.md` (the browser's native save dialog) or copied.

### URLScan
Orders a live scan of the given URL through the [urlscan.io API](https://urlscan.io/docs/api/) (`POST /api/v1/scan/`, then polling `GET /api/v1/result/{uuid}/` every 5 seconds until the result is ready - urlscan.io returns 404 while the scan is running; a three-step indicator shows the progress). The address is cleaned by the backend first: a defanged link (`hxxps://evil[.]example`) is restored, a missing scheme becomes `https://`, and what urlscan.io can never scan is refused with a clear message (non-HTTP schemes, `localhost`, private and local addresses, intranet names). The scan is submitted with:

- **the visibility you choose** - `unlisted` by default (not on the urlscan.io front page or in public search, but visible to verified security researchers in urlscan Pro), or `private` (only your account) or `public` (anyone; the tab warns about it),
- **the default user agent** (no `customagent`) and **automatic choice of the scan country** (no `country`) - both fields are deliberately left out of the request.

The result is laid out like the IP tab: a verdict banner (colour from the urlscan.io score and the engine and community verdicts; "no verdict" is shown neutrally and explicitly not as "safe"), summary tiles (score, HTTP status, server country, ASN, requests, certificate age with a "new" mark below 7 days, redirects), the page screenshot, a "Page identity" card (submitted and final URL, the redirect chain, title, domain, main IP with a **Check IP** button that only puts the address into the IP tab, location, PTR, server, MIME type, scan time and visibility) and collapsible detail cards - urlscan.io verdict (open only when it signals a risk), TLS certificate, technologies, contacted IP addresses (each with **Check IP**), contacted domains and links - with the whole raw response under "Full API response". The screenshot is fetched by the backend from urlscan.io and served from your own origin, so neither the browser nor the Content-Security-Policy ever touch urlscan.io or the scanned page. Addresses found on the scanned page are shown defanged and are never clickable, also in the Markdown export ("Save .md", "Copy Markdown"). "Scan again" repeats the scan.

Every finished scan is saved in the History tab as a structured summary plus a small JPEG thumbnail of the screenshot (640 px wide, tens of KB); "Reopen" shows it again in this tab, and "Load full report" fetches the complete result from urlscan.io by its identifier.

### DMARC
Drag and drop aggregate DMARC reports (from Google, Microsoft etc.; plain `.xml` as well as `.gz` and `.zip` archives exactly as the providers send them) - the tool unpacks and parses them 100% in the browser (no files are sent anywhere) and shows everything the reports contain. A report loaded twice (the same provider and report ID) is skipped and marked in the file list. At the top: a verdict banner (red when a source fails both SPF and DKIM, amber when only one of them fails, green otherwise; report errors get their own banner) followed by hints on the latest published policy of each domain (`p=none` only monitors, a policy that can probably be tightened, `pct` below 100), summary tiles (messages, unique IPs, suspicious sources, share of messages that pass DMARC, and a bar of the policy decisions reject/quarantine/none) and, with more than one report, a table by provider (reports, messages, share passing DMARC). Each uploaded report is an expandable block with every field of its metadata and published policy: provider, contact and additional contact, report ID and version, period, domain, `p`/`sp`/`pct`/`fo`, alignment (`adkim`/`aspf`, with defaults marked), report errors and any other element the report carries (for example `np`, `testing` or vendor tags). Below, the sources aggregated by IP address, riskiest first, filterable (all / suspicious / passing), with SPF and DKIM pass/fail counts and the policy decisions (an override such as `forwarded` is noted there, so legitimate forwarding is not mistaken for an attack); a click on a row expands every single record - header/envelope from and to, the reason of a policy override (`policy_evaluated > reason`), the raw `auth_results` outcome (domain/selector/result/`human_result` for DKIM, domain/scope/result for SPF) and any extra fields - exactly what lets you diagnose *why* alignment failed, not just that it did. The optional "geo/ASN" button in the expanded row sends that single IP address to the external service [ipwho.is](https://ipwho.is) (from your browser, only on click) and shows the country and ASN; from there you can also jump straight to a full reputation check (IP tab) or to preparing an AbuseIPDB report. A short glossary of SPF, DKIM, the policy terms and the table closes the tab. "Save .md" and "Copy Markdown" export the whole analysis (summary, reports, sources and every record; values from the XML sit in code spans). Every import is saved in the History tab with its records, and "Reopen" restores the full analysis. The risk rating is unchanged: high = SPF and DKIM both failed, medium = one of them failed.

### Email
An educational analysis of the e-mail source: paste the whole source (headers + body) or load an `.eml` file (UTF-8 or windows-1252, the mbox envelope and line endings are normalised; binary base64 attachments do not go to the model - only their size and sha256 stay, while text base64 parts are decoded).

- **Deterministic analysis (immediately, locally, without an LLM)**: findings about anomalies, the Received route with the role in the chain of trust, authentication (SPF/DKIM/DMARC/ARC, authserv-id, signed and unsigned headers, `bh=` length), domain alignment relative to `From`, a UTC timeline, epoch conversions, the MIME tree, attachments (sha256, double extensions), links (text vs `href`), hidden content, HTML comments, template placeholders, the recipient's anti-spam filters (SCL/BCL/CAT, the Junk target folder, AuthAs, the decoded X-Message-Delivery) and flags set by the sender (X-Message-Flag, Importance, read-receipt requests). When the whole Received chain belongs to one operator (e.g. Microsoft), the table marks the oldest entry as the trust boundary. Identical findings caused by repeated links are reported once with a count, e.g. `(x4)`. The logic is in `backend/email_forensics.py`; nothing from the message is opened or downloaded.
- Below the separator: a **detailed LLM analysis** (OpenRouter, the same key and model as in AbuseIPDB), streamed live, following the guide `docs/email-analysis-guide.md` (mental model, a line-by-line analysis of both the good and the bad elements, a checklist, traps, an assessment, control questions with answers in collapsible sections). The first line of the answer is the verdict with a confidence level.
- The response limit of the model is 64000 tokens (counted together with the hidden reasoning of the model, about 45% of the output; it is a ceiling, you pay for the tokens actually generated). If the analysis is cut off anyway, the tab shows a warning and a **"Finish the analysis"** button (the model receives the text so far and writes the missing parts; token usage and cost add up in the saved analysis).
- **"Save .md"** and **"Copy Markdown"** (the export labels follow the interface language at the moment of export, the text of the LLM analysis stays in the language it was written in) export the whole set: metadata (date, verdict, model, input/output tokens, cost), the whole deterministic analysis (tables) and the LLM analysis.
- **Duplicate detection:** before a paid analysis Seisa checks the fingerprint (sha256 of the normalised source) in `data/analyses/`. If the message was already analysed, it offers to open the saved analysis (with the date, verdict and cost) or to run it again deliberately.
- **Citation check (local, free):** after the analysis the code checks whether the IP addresses, the header lines quoted in code blocks, `Header: value` quotes, SCL/BCL numbers and identifiers given by the model appear in the source or in the deterministic analysis (`backend/citation_check.py`). Discrepancies are listed under the analysis and in the `.md` export; this is information, not proof of an error (an example or a paraphrase may be flagged too). It does not check domains or entries such as `spf=pass`, because the analysis also discusses examples of a legitimate message.
- The LLM analysis does not reproduce the tables visible in the deterministic analysis (timeline, links, Received etc.), it only interprets them, so that you do not pay for repetition; the complete set is in the export.
- The LLM output is rendered safely: raw HTML from the e-mail and links are neutralised (links are shown as non-clickable, defanged text).
- **Analysis language:** the analysis is written in the interface language (a directive in the prompt plus a table of literal headings and tags `[Fakt]`/`[Fact]` for both languages in `docs/email-analysis-guide.md`); the language is stored in the record (`lang`; older records = Polish). "Finish the analysis" uses the language of the stored record, not the current interface language. A saved analysis in a language other than the interface is marked with a PL/EN badge, and opening it shows a banner with a paid re-analysis button (the cost of the previous one is given as a guide); the facts and the text stay in the language they were created in, while the labels and the .md export use the interface language. Duplicate detection (sha256 of the source) does not depend on the language: the banner shows the language of the existing analysis.
- **Verdict protocol:** the first line of the model answer has the form `VERDICT: <legit|phishing|spam|scam|malware|inconclusive> | CONFIDENCE: <high|medium|low>` and always uses these canonical codes, whatever the language of the analysis (`backend/verdict.py`); the interface maps them to labels in the selected language. Analyses saved earlier with Polish tokens (`WERDYKT`/`PEWNOSC`) are read without any file migration.
- The **"Report to AbuseIPDB"** button (visible only when the verdict is not `legit`, i.e. legitimate) pastes the original source into Step 1 of the AbuseIPDB tab (overwriting the field) and takes the user there.
- Every completed analysis is saved together with the raw e-mail in `data/analyses/` (files 0600, gitignored); the list of saved analyses (open/delete) is at the bottom of the tab.

### AbuseIPDB (reporting)
A workflow compliant with the [AbuseIPDB reporting policy](docs/abuseipdb-reporting-policy.md) (60-day limit, no reporting based on the confidence score alone, the 1024-character comment limit etc.):

1. **Paste the raw source of the suspicious e-mail** (headers + body) - optional, you can also start from the IP alone (the "Report to AbuseIPDB" button in the IP/DMARC tab).
2. The backend extracts the facts deterministically: the trusted source IP address (the algorithm goes from the newest `Received` header downwards and looks for the first hop whose "from" host no longer belongs to the same domain as the "by" host of the newest hop - in multi-hop chains of large providers, e.g. Microsoft 365/Outlook.com, the first few hops are internal transfers of the same provider and are skipped, so that their address is not taken instead of the real sender), together with a confidence level (`ip_confidence`) and the full chain of hops for inspection (the expandable list "Received chain - why this IP" in Step 1). In addition: the SPF/DKIM/DMARC result, attachments (with detection of double extensions such as `invoice.pdf.exe`), the Message-ID, BTC address/ransom demand patterns. **The hard checks (age of the attack, whether the IP is private) are always computed in Python and are never delegated to the LLM.**
3. Optionally (if `.env` has `OPENROUTER_API_KEY`) an LLM through **OpenRouter** assesses whether the e-mail qualifies for a report, independently verifies the IP address chosen by the code on the basis of the raw headers (`source_ip_check` - if it disagrees, Step 1 shows a clear warning banner with the model's suggestion, informational only), assesses the fit of the suggested categories and possible PII in the comment - and **writes a ready, detailed report comment in English**, based on the facts, the complete raw source of the message (all headers and the whole body, up to the source size limit; Step 1 states how many characters the model saw) - see point 4. Without a key the tool works in rule-based mode.
4. **The report comment is an editable field in Step 2, filled with what the LLM wrote** - `comment` is an optional field in the AbuseIPDB API ([`/report`](https://docs.abuseipdb.com/#report-endpoint), only `ip` and `categories` are required), but the AbuseIPDB policy itself expects a detailed, technically justified description - hence the LLM writes the comment (attack mechanism, meaning of SPF/DKIM/DMARC, malicious attachments with a detected double extension such as `invoice.pdf.exe`, a ransom/BTC demand, mass-mailing patterns), within about 900 characters. Without an LLM (or when the analysis fails) a poorer, deterministic fallback built solely from the facts is used. In both cases the text is fully editable before sending, and the backend sanitises/truncates it to 1024 characters right before sending anyway. If you know the port number, add it by hand.
5. A form with a character counter (limit 1024) computed locally, without backend calls at every edit of the comment.
6. **The checklist is mostly informational** - sending is gated by the eligibility verdict (first item; "not suitable" blocks the button, "in doubt" does not) and the three hard checks (age, IP, category - exactly what the API requires; a date up to one hour in the future counts as "now" to tolerate a clock offset, a further future date fails) are always computed by the Python code and only these gate the "Send" button; the five further items (Received, not a spoofed source, Spoofing, category fit, PII redaction) are a hint to read before sending. Received and Spoofing come from the facts of the e-mail; the others from the same LLM analysis of Step 1 (without an LLM they stay as "requires AI analysis"). Spoofing is one of three states, always with a short reason: detected (SPF/DMARC fail), not detected (authentication passed) or cannot be assessed (no or ambiguous SPF/DKIM/DMARC results in the pasted source).
   The verdict banner above the form has a coloured border (the text is always white): green = does not qualify (nothing to report), red = qualifies (worth reporting), no colour = not assessed. The first checklist item repeats this verdict (suitable / not suitable / in doubt) and a "not suitable" verdict blocks the "Send" button. Without an LLM the tool never claims that an e-mail qualifies: it only checks the hard criteria (public IP, age) and recognises the obvious case of a test sent from your own account to yourself (sender = envelope sender = recipient, no sign of an attack). The attack timestamp is taken from the `Date` header and shown in the browser's local time; it is sent to AbuseIPDB in UTC (ISO 8601).
7. Under the IP field the tab shows what AbuseIPDB already knows about the address (reports, distinct reporters, confidence score and last report in 90 days; one `/check` query per address, only with an API key) and your own earlier reports of it from `data/report_log.json`. AbuseIPDB accepts a repeated report of the same IP from one account only after 15 minutes, so within that time the "Send" button is disabled and the backend refuses the request (HTTP 409) instead of spending a call. The fallback comment (without an LLM) contains only the local part of the `Message-ID`, because the domain after `@` is usually your own.
8. Sending through the AbuseIPDB API (the backend validates the hard checks anew, independently of the state of the form in the browser) **or** copying the comment for manual pasting on the website.

Further details of this tab:

- The "Load .eml file" button (also dragging a file onto the field), a timer of the analysis and the tokens and cost after the "Analyze" analysis, shown next to the buttons.
- Detection of the sender IP: when the first hop outside the recipient's domain is only a relay of an operator (e.g. Microsoft Exchange Online), the parser walks through the operator's internal hops to the hop where the address of the connecting sender was recorded. If the message originated inside a shared provider (e.g. a hotmail account) and there is no public sender IP, the IP stays empty (confidence low). Authentication results are also read from `X-MS-Exchange-Authentication-Results` and `ARC-Authentication-Results`. After an analysis with an LLM the tab shows how much of the content the model saw (the first 2000 characters), and the hard checks (IP, age) take precedence over the opinion of the model.

### History
The last 25 actions: IP lookups, URL scans (reopened in the URLScan tab, with a thumbnail of the screenshot), DMARC imports and saved e-mail analyses (reopened in the Email tab), which you can reopen or delete. "Clear history" removes only IP, URL scan and DMARC entries; e-mail analyses (with the raw messages) are deleted one by one.

### Logs
Errors and warnings (WARNING level and above) from every service - normal, error-free operation of the tool leaves no trace on disk. Filtering by date range (today / 3 days / week / month / all; the default is all) and by service (the default is all). All OpenRouter API errors (Email and AbuseIPDB tabs: limits, insufficient credits, provider errors, timeouts) go to a single `open_router` service; the other application errors go to `app`.

### Info
The round info button (ⓘ) at the far right of the tab row opens the Info tab: the name and the current version (read from the page header), a short description of Seisa, the meaning of the name (精査, *せいさ*), the license (the same summary as in the License section below) and the author's contact details (e-mail, GitHub, website).

### Interface language (PL/EN)
The `EN | PL` switch is in the footer. The choice is remembered by the browser (`localStorage`, key `seisa.lang`); without a stored choice the browser language is used (`en` or `pl`), and English in all other cases. Changing the language reloads the page (you are asked first if that would lose work in progress). The interface texts live in the catalogs `frontend/i18n/pl.json` and `en.json` (flat keys, `{name}` parameters, plural forms through `Intl.PluralRules`), dates use the `pl-PL` or `en-GB` format. The development mode `/?lang=qa` shows `[[key]]` instead of texts, so places that bypass the translations are visible at once. The frontend sends the selected language in the `X-Seisa-Lang` header (only to its own backend) and the backend translates error messages, the deterministic e-mail analysis, the IP scoring notes and the Markdown reports on its side (catalogs `backend/locales/pl.json` and `en.json`, module `backend/i18n.py`). Analyses and history entries saved earlier keep the language they were created in. The logs (Logs tab) are in English regardless of the interface language. LLM answers (Email and AbuseIPDB tabs) are written in the interface language of the moment of the request; the prompts and guides are single, in English, and the answer language is set by an explicit directive (the AbuseIPDB report comment is always in English - an AbuseIPDB policy requirement). The cost of requests depends on the model.

## Architecture

A single **Python FastAPI** process (`backend/`) serves both the API and the static frontend (`frontend/` - plain JavaScript, ES modules, no framework and no build step) on `127.0.0.1:54321`.

```
seisa/
├── .env                    # API keys (gitignored, see .env.example)
├── seisa.sh                 # start script (starts the server and opens the browser)
├── README.md / README.pl.md  # this documentation in English (the main one on GitHub) and in Polish
├── pyproject.toml           # ruff configuration (linter only, not a package)
├── LICENSE                  # PolyForm Noncommercial 1.0.0 license
├── CONTRIBUTING.md          # contribution rules (no external code changes)
├── SECURITY.md              # how to report a vulnerability
├── .github/ISSUE_TEMPLATE/  # bug report template
├── backend/
│   ├── main.py               # FastAPI, routing, no-cache and language middleware, error handling
│   ├── config.py             # paths, settings from .env
│   ├── models.py             # Pydantic models
│   ├── aggregator.py         # fan-out to the services, aggregate risk score
│   ├── markdown_report.py    # Markdown report builder
│   ├── ratelimit.py          # VirusTotal throttle
│   ├── cache.py              # in-memory result cache
│   ├── storage.py            # atomic JSON storage (history, VirusTotal counter, report log)
│   ├── sse.py                # Server-Sent Events framing shared by the streaming endpoints
│   ├── logging_config.py     # WARNING+ logs to logs/*.jsonl
│   ├── email_parser.py       # fact extraction from the raw e-mail (AbuseIPDB tab)
│   ├── email_forensics.py    # deterministic analysis of the e-mail source (Email tab)
│   ├── analyses.py           # storage of e-mail analyses in data/analyses/
│   ├── i18n.py               # backend translations: request language (ContextVar), t()/tn(), catalogs in locales/
│   ├── locales/              # backend text catalogs: pl.json, en.json
│   ├── verdict.py            # canonical verdict protocol (EN codes, mapping of the old PL tokens)
│   ├── scoring.py            # aggregate IP reputation score (noisy-OR)
│   ├── identity.py           # merged address identity (ASN, owner, country, network) with per-field source agreement
│   ├── report_builder.py     # AbuseIPDB comment builder + policy validation
│   ├── report_utils.py       # text sanitisation, IP checks
│   ├── urlscan_report.py     # structured summary + Markdown report of a urlscan.io scan result
│   ├── urlscan_input.py      # cleaning and validation of the URL to scan (refang, scheme, private hosts)
│   ├── routers/               # /api/* endpoints
│   └── services/               # a client for every service (common IntelService interface; urlscan.py separately - submit+poll, not an IntelService)
├── frontend/
│   ├── index.html
│   ├── favicon.ico            # icon: the kanji 査 (16/32/48/64 px)
│   ├── logo.png               # round logo (page header and README)
│   ├── css/style.css          # dark theme
│   ├── i18n/                  # interface text catalogs: pl.json, en.json
│   ├── js/                    # modules: app, i18n, util (shared helpers), lookup (+ lookup-result: the report view), urlscan (+ urlscan-result: the report view), dmarc, archive (unpacking .gz/.zip), email, report-builder, history, logs, about
│   └── vendor/marked.min.js   # Markdown rendering, bundled locally (no CDN)
├── tests/fixtures/          # SYNTHETIC e-mails (.eml) for comparisons; fictitious data (.example domains, documentation address ranges; the header layout of `multihop.eml` imitates a large mail provider), no personal data
├── scripts/
│   ├── api_harness.py         # the only automated test: every API endpoint with all external services mocked (also `--serve PORT` for trying the UI without keys)
│   ├── dump_facts.py          # dumps the deterministic analysis of the fixtures to JSON (compares two code versions byte for byte)
│   └── check_i18n.py          # checks the PL/EN catalogs (keys, parameters, plurals); `--strict` looks for Polish literals in code
├── data/                    # history.json, vt_usage.json, report_log.json, analyses/ (gitignored)
├── logs/                    # error logs, one .jsonl file per day (gitignored)
└── docs/
    ├── abuseipdb-reporting-policy.md   # the full policy + the AbuseIPDB category table (English, LLM prompt context)
    └── email-analysis-guide.md         # e-mail analysis guide loaded into the LLM prompt (Email tab), English, with a PL/EN label table
```

There is no database - all persistence is plain JSON files in `data/` (history limited to 25 entries, the VirusTotal daily limit counter) and logs in `logs/`. Saved e-mail analyses live in `data/analyses/`. Releases before 2.0.27 used `data/analizy/` and `logi/`; Seisa does not migrate them, so rename them by hand before the first start of a newer release (`mv data/analizy data/analyses`, and move the `*.jsonl` files from `logi/` to `logs/`).

## Installation

Requires Python 3.11+ on **macOS** or **Linux**. On Debian/Ubuntu install the venv module first (`sudo apt install python3-venv`). Windows is not supported natively; it works through WSL as Linux.

```bash
cd seisa
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt   # or requirements.lock for the exact tested versions
cp .env.example .env
```

Fill `.env` with real API keys (the keys are described below) and make the file readable only for you: `chmod 600 .env`.

## Running

The simplest way is the start script, which starts the server and opens the browser at `http://127.0.0.1:54321` (macOS: `open`; Linux with a desktop: `xdg-open`; otherwise it only prints the address to open by hand):

```bash
./seisa.sh
```

You can add a shell alias for it (e.g. `alias seisa='~/path/to/seisa/seisa.sh'`). Without the script:

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
- Unpacking and parsing of DMARC reports (.xml, .gz, .zip) happens entirely in the browser. The only call the frontend makes to a third party is the optional "geo/ASN" button, which sends a single IP address to ipwho.is on click.
- The server accepts only loopback `Host` headers (`127.0.0.1`, `localhost`), which blocks DNS-rebinding attacks from other web pages. Every response carries a Content-Security-Policy (scripts only from the tool's own origin).
- Indicators are validated before they reach the URL paths of the intel services (only real IP addresses and host names), scan identifiers must be UUIDs, and request sizes are bounded (e-mail source 3 million characters, 200 indicators per batch).
- Reports contain text from third-party APIs (e.g. comments from other AbuseIPDB users), so the rendered HTML goes through an allow-list: only the tags the reports use survive, links only with `http(s)`, and any other markup is shown as inert text.
- The content of a pasted e-mail goes to OpenRouter **only** after an explicit click on "Analyze" (not "Analyze without LLM") - the interface says so plainly before sending.
- A report to AbuseIPDB always requires a deliberate click on "Send"; the backend validates the hard checks (age, IP, category) anew regardless of the state of the form in the browser - they, not the informational checklist, decide whether sending is possible. The comment is only sanitised and shortened, not judged.
- The Email tab sends the whole source of the message (with personal data) to OpenRouter after a click on "Analyze"; this is a deliberate decision (mostly suspicious messages are analysed).
- History, saved e-mail analyses and logs stay only locally in `data/` and `logs/` (gitignored). The analyses contain raw e-mails, so the files have 0600 permissions.

## Versioning and conventions

- The visible version number (page title, header and footer in `index.html`, and under the logo in both READMEs) is increased by 0.0.1 after every change to the tool; after X.Y.99 the next version is X.(Y+1).0. Version 2.0.0 is the first release under the name Seisa.
- Code, comments, docstrings, log messages and commits are in English. The documentation exists in two versions with the same heading structure: `README.md` (English, the main one on GitHub) and `README.pl.md` (Polish); a change in one means a change in the other (the heading structure is compared by `scripts/check_i18n.py`).
- Every tab that runs an action shows the timer (always one decimal, e.g. `13.1 s`), the status (e.g. the loaded file) and any related buttons in one row next to the action button, both during and after the run; in the Email tab the tokens and cost sit there too.
- Texts visible in the interface go exclusively to the `i18n` catalogs (a new key = a PL and an EN entry in the same commit); before a commit `python3 scripts/check_i18n.py` must finish without errors.
- Verification: `python3 scripts/api_harness.py` runs every endpoint against mocked services (no keys, no network) and fails on unexpected answers; `scripts/dump_facts.py` and `--out` of the harness allow comparing two versions byte for byte after a refactor; the interface is checked by hand.
- Python code is checked with `ruff` (configuration in `pyproject.toml`; a development tool, not a dependency): `ruff check backend scripts`.
- The whole project (code, UI, documentation) avoids the long dash (Unicode U+2014) - only a plain "-".

## Known open issues

- The exact slug of the OpenRouter model (`OPENROUTER_MODEL`) should be verified on the current OpenRouter model list.
- WHOIS/rDNS has no "open the service website" button - it is a direct protocol query, without a single external service to link to.

## License

Seisa is made available under the [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0) license - the full text is in the [LICENSE](LICENSE) file. The code is public (*source-available*), but **this is not an open-source license in the OSI sense**: you may use, copy, modify and distribute it (including forks) only for noncommercial purposes, among others personal, hobby, educational and research use and use by charitable, educational, public and government organisations. Commercial use (including selling, commercial forks and work for the profit of a company) requires a separate permission of the author.

The bundled `frontend/vendor/marked.min.js` remains under its own MIT license (the header in the file).

Rules for reporting bugs and contributing: [CONTRIBUTING.md](CONTRIBUTING.md) - external code changes (pull requests) are not accepted.

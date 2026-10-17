**English** | [Polski](pl/PRIVACY.md)

# Privacy and security

This page is for careful users and reviewers. In one sentence: Seisa runs on your own computer and contacts outside services only when you click a button. This page lists every call that leaves your computer, every file Seisa keeps, and what the safeguards do and do not protect.

## Contents

- [In short](#in-short)
- [What leaves your computer](#what-leaves-your-computer)
- [Identification](#identification)
- [What your browser opens itself](#what-your-browser-opens-itself)
- [What stays on your computer](#what-stays-on-your-computer)
- [How to delete your data](#how-to-delete-your-data)
- [Language model (OpenRouter)](#language-model-openrouter)
- [Safeguards](#safeguards)
- [Threat model](#threat-model)
- [Reporting a vulnerability](#reporting-a-vulnerability)

## In short

- Seisa listens only on `127.0.0.1` (port 54321), so other computers on your network cannot reach it.
- Nothing is sent to an outside service until you click a button that does it (Check, Scan, Analyze, Send via AbuseIPDB API, geo (RDAP), Refresh limits).
- There is one exception: the AbuseIPDB tab looks the address up in AbuseIPDB by itself as soon as an IP is in its form (see the table below).
- Your browser talks only to Seisa. The page is not allowed to contact any other server.
- E-mail contents go to a language model only when you click "Analyze" (not "Analyze without LLM") and only if an OpenRouter key is set.
- A report reaches AbuseIPDB only through the "Send via AbuseIPDB API" button.
- Seisa has no telemetry, no update check and no account. It never contacts its author.

## What leaves your computer

Every call that Seisa makes to the outside world is in this table. Calls are listed by tab and button, using the names from the interface. "Key" is the setting in your `.env` file that the call needs; a service without a key is skipped without any network call.

Two things apply to the whole table:

- **The automatic call.** The `GET /api/v2/check` row of the AbuseIPDB tab is the only call that happens without a click of its own. All other rows need your click or follow directly from one.
- **Nothing for private addresses.** Private, loopback and documentation IPs are refused before anything is sent. If you switch every service off in the IP tab, Seisa asks nobody: it shows "Select at least one service." and the server refuses such a request too.

| Tab and action | What is sent | To whom | When | Key |
|---|---|---|---|---|
| IP, "Check": WHOIS / rDNS (address) | The IP address (`GET /ip/{ip}`) | rdap.org, which forwards to the regional registry (RIPE, ARIN, APNIC, LACNIC or AFRINIC) | Click "Check". Also "Repeat" on a saved IP check in History and the IP buttons of other tabs, which open the IP tab and run it | none |
| IP, "Check": WHOIS / rDNS (address) | A reverse-DNS (PTR) query for the IP | Your system's DNS resolver and whatever it forwards to | Click "Check" | none |
| IP, "Check": WHOIS / rDNS (domain) | The domain name | WHOIS servers on TCP port 43: the server for the domain's ending, possibly also the registrar's server | Click "Check" | none |
| IP, "Check": DNS (domain) | DNS queries for the domain: A, AAAA, NS, MX, CAA, TXT, `_dmarc.<domain>` TXT, an A query for each name server, and one A query for a random name of 16 hexadecimal characters under the domain (a wildcard test) | Your system's DNS resolver; the random name reaches the domain's own name servers | Click "Check" | none |
| IP, "Check": Cloudflare Radar | The IP (`/radar/entities/ip?ip=`) or the domain (`/radar/ranking/domain/{domain}`) | api.cloudflare.com | Click "Check", if the service is selected | `CLOUDFLARE_RADAR_API_KEY` |
| IP, "Check": AlienVault OTX | The IP (`/IPv4/{ip}/general` or `/IPv6/...`) or the domain (`/domain/{d}/general`) | otx.alienvault.com | Click "Check", if the service is selected | `OTX_API_KEY` |
| IP, "Check": AbuseIPDB | The IP (`GET /api/v2/check?ipAddress=&maxAgeInDays=90&verbose`). Domains are not sent | api.abuseipdb.com | Click "Check", if the service is selected | `ABUSEIPDB_API_KEY` |
| IP, "Check": VirusTotal | The IP (`/api/v3/ip_addresses/{ip}`) or the domain (`/api/v3/domains/{d}`). At most 4 a minute and 500 a day; Seisa waits or refuses | www.virustotal.com | Click "Check", if the service is selected | `VIRUSTOTAL_API_KEY` |
| IP, "Check": GreyNoise | The IP (`/v3/ip/{ip}`; if the plan of the key has no access, again to `/v3/community/{ip}`). Domains are not sent | api.greynoise.io | Click "Check", if the service is selected | `GREYNOISE_API_KEY` |
| URLScan, "Scan" | The URL, the scan visibility (default "Unlisted (default)"; "Public" shows the scan to everyone on urlscan.io), optionally a country and a user agent you picked. Up to 5 URLs at once, 1 second apart. urlscan.io then opens the page from its own servers | urlscan.io (`POST /api/v1/scan/`) | Click "Scan". Also the "Repeat" button of a saved scan in History. The URLScan button of the IP tab only fills in the address | `URLSCAN_API_KEY` |
| URLScan, waiting for the result | The scan id (`GET /api/v1/result/{uuid}/`), first after 12 seconds, then every 5 seconds, up to 120 seconds | urlscan.io | Automatically after "Scan"; also "Load full report" for a saved scan | `URLSCAN_API_KEY` |
| URLScan, result | The scan id (`GET /dom/{uuid}/`). Seisa reads the page's HTML only to find forms | urlscan.io | With each finished result | `URLSCAN_API_KEY` |
| URLScan, result | The scan id (`GET /screenshots/{uuid}.png`). Seisa fetches the screenshot, not your browser | urlscan.io | When the result is shown (it retries if the screenshot is not ready) | `URLSCAN_API_KEY` |
| URLScan, "History" (earlier scans of the domain) | A search for the host of the URL (`page.domain:"host"` or `page.ip:"x"`), at most 10 hits. The list holds public scans by other people and scans of your own account | urlscan.io (`/api/v1/search/`) | Click only | `URLSCAN_API_KEY` |
| DMARC, "geo (RDAP)" | The source IP of one row | rdap.org, which forwards to the regional registry | Click "geo (RDAP)" on that row | none |
| DMARC, "geo (RDAP)" | A reverse-DNS (PTR) query for the IP | Your system's DNS resolver | Click "geo (RDAP)" | none |
| DMARC, "geo (RDAP)" | If the PTR name belongs to a known mail sender (Google, Microsoft, Amazon SES and others), a forward lookup of that name (A and AAAA), given at most 5 seconds | Your system's DNS resolver | Click "geo (RDAP)" | none |
| DMARC, loading a report | Nothing. The file is unpacked and read in your browser | Nobody | - | none |
| Email, "Analyze" | The system prompt with the analysis guide (`backend/prompts/email-analysis-guide.md`), the facts computed from the e-mail (JSON), the prepared e-mail source and the model name. The source keeps all headers unchanged, decodes text parts (up to 60 000 characters each), replaces attachments with their size and SHA-256, and is cut at 120 000 characters. The answer streams back (`max_tokens` 64 000) | openrouter.ai (`/api/v1/chat/completions`), which passes it to the model provider | Click "Analyze". "Analyze without LLM" sends nothing | `OPENROUTER_API_KEY` |
| Email, "Finish the analysis" | The same as "Analyze" once more, plus the text written so far and an instruction to continue | openrouter.ai | Click on a truncated analysis | `OPENROUTER_API_KEY` |
| AbuseIPDB, "Analyze" (with LLM) | The facts computed from the e-mail (JSON), the e-mail source prepared for the model (the same preparation as above, cut at 120 000 characters), the first 12 000 characters of the AbuseIPDB policy text (`backend/prompts/abuseipdb-reporting-policy.md`) and the model name. If the answer is not valid JSON, Seisa asks once more | openrouter.ai, then the model provider | Click "Analyze". "Analyze without LLM" sends nothing | `OPENROUTER_API_KEY` |
| AbuseIPDB, report form | The IP in the form (`GET /api/v2/check`, 90 days, verbose) | api.abuseipdb.com | **Automatically**, about 0.4 seconds after the IP field changes: after an analysis, when you type an address, or when another tab hands an address over. Once per address, only for a reportable public IP and only with a key | `ABUSEIPDB_API_KEY` |
| AbuseIPDB, "Send via AbuseIPDB API" | The report: IP, categories, attack time (UTC) and the comment (ASCII, at most 1 024 characters). It is published on AbuseIPDB under your account | api.abuseipdb.com (`POST /api/v2/report`) | Click "Send via AbuseIPDB API" (plus a confirmation if personal data was found) | `ABUSEIPDB_API_KEY` |
| Info, "Refresh limits" | A quota query. The VirusTotal key is part of the address (`/api/v3/users/{key}/overall_quotas`), as VirusTotal requires | www.virustotal.com | Click only | `VIRUSTOTAL_API_KEY` |
| Info, "Refresh limits" | A quota query (`/user/quotas/`) | urlscan.io | Click only | `URLSCAN_API_KEY` |
| Info, "Refresh limits" | A key status query (`/api/v1/key`) | openrouter.ai | Click only | `OPENROUTER_API_KEY` |
| Info, "Add icon" and "Remove icon" | Nothing leaves the computer. Seisa writes files in your home folder and runs local tools (`sips`, `iconutil`, `update-desktop-database`) | Nobody | Click only | none |
| Starting from the desktop icon | A local check `curl http://127.0.0.1:54321/api/about` | Your own computer | When you start Seisa from the icon | none |
| Opening Info, History or Logs; parsing an e-mail; loading a DMARC file | Nothing leaves the computer. Parsing, scoring and the local `git log` for Recent changes all run locally | Nobody | - | none |

About the AbuseIPDB automatic lookup: it asks AbuseIPDB what it already knows about the address, so you can see it before you decide to report. It is the only call that follows no click of its own. Without an AbuseIPDB key it does not happen.

## Identification

This section is about who can see what. Each service sees the address your computer connects from, and the details below explain how Seisa introduces itself.

- **Your IP address.** Every call in the table goes directly from your computer, so each service sees your public IP address. A service with a key also knows your account.
- **No own User-Agent.** Seisa sends no `User-Agent` of its own. HTTP calls carry the library default, `python-httpx/<version>`.
- **DNS wildcard test.** The random name is 16 hexadecimal characters with no reference to Seisa. The domain's name servers see an odd query from your DNS resolver, not which tool sent it.
- **OpenRouter headers.** OpenRouter receives two attribution headers, `HTTP-Referer: https://seisa.local` and `X-Title: Seisa`, so your OpenRouter dashboard shows the calls as "Seisa".
- **URLScan.** A scan can carry a user agent you chose. The urlscan.io servers, not yours, connect to the scanned page.

## What your browser opens itself

These are links that open in a new browser tab when you click them. The page itself never loads anything from other servers (its `connect-src` is `'self'`). What you open is then governed by that site.

| Where | What it opens |
|---|---|
| Info, author card | `github.com/arcymonek/seisa`, `seisa.eu` and `mailto:contact@seisa.eu` |
| Info, license card | `LICENSE` and `CONTRIBUTING.md` on GitHub (they work once the repository is public) |
| IP, source cards | The home page of the service (Cloudflare Radar, AlienVault OTX, AbuseIPDB, VirusTotal, GreyNoise). Nothing about the checked address is in the link |
| AbuseIPDB, "Your reports", "Check" | `https://www.abuseipdb.com/check/<ip>`. Here your browser itself tells AbuseIPDB the address |
| URLScan, "Open in urlscan.io" | `https://urlscan.io/result/<uuid>/` |

Two more facts about links:

- **Exported files.** Exports (.md) contain only two kinds of live links: an AbuseIPDB reporter profile (`https://www.abuseipdb.com/user/<number>`) and a urlscan.io result. Every other address is defanged, for example `hxxp://evil[.]example`. An e-mail address in the text may still become a `mailto:` link in your Markdown viewer.
- **E-mail results.** Links from an e-mail are never clickable in Seisa. They are shown as text with a defanged address.

## What stays on your computer

This table lists every place where Seisa keeps something. Data files are plain JSON, readable only by you (file mode 0600, which means owner read and write). Folders that hold raw e-mails and logs are 0700 (owner only).

| File | What it holds | Permissions | How long |
|---|---|---|---|
| `data/history/index.json` and `data/history/entries/<uuid>.json` | IP checks, DMARC imports and URL scans (a summary and a JPEG thumbnail) | Folders 0700, files 0600 | The newest 100 unpinned entries and all pinned ones; older files are deleted |
| `data/history.json` and `data/history.json.migrated` | The history of versions before 2.4.25, migrated on first use and renamed | As left by the old version | Kept, never deleted |
| `data/analyses/<date-time-hash>.json` | One Email analysis: **the whole raw e-mail**, the facts, the model's text, the model name, token use, cost and language | Folder 0700, file 0600 | Until you delete it |
| `data/report_log.json` | Every AbuseIPDB send attempt, accepted or failed: IP, categories, comment, attack time, API answer, error | 0600 | Grows without limit; the interface has no delete button |
| `data/vt_usage.json` | Today's VirusTotal call count | 0600 | One day |
| `data/api_usage.json` | Quota answers, rate-limit headers, own hourly counters (GreyNoise, OTX) and "limit exceeded" flags | 0600 | Counters 8 days |
| `logs/YYYY-MM-DD.jsonl` | Warnings and errors only: time, level, service and message. Messages can name hosts and addresses | Folder 0700, files 0600 | 30 days (today counts as day 1); "Clear logs" deletes them |
| `logs/launcher.log` | Everything uvicorn prints when Seisa is started from the desktop icon, including request lines | 0600 | Overwritten at every start from the icon; "Clear logs" and the 30-day rule do not remove it |
| Browser `localStorage` | `seisa.lang`, `seisa.theme`, `seisa.shutdownAsk`, `seisa.urlscan.options` (visibility, country, user agent), `seisa.em.pane` and `seisa.em.cards` (which lesson cards are open). No e-mail contents or results | In your browser | Until you clear site data |
| `~/Applications/Seisa.app` (macOS) or `~/.local/share/applications/seisa.desktop` (Linux) | The desktop icon. Written only on "Add icon"; replaced or removed only if it carries Seisa's marker | The launcher script is 0755 | Until "Remove icon" |
| `.env` | Your API keys. Read at start and never shown: Info shows only "set" or "missing" | As you create it (git ignores it) | - |

Some details about this table:

- **The `data/` folder itself** keeps the mode it got from git or from unzipping (often 0755). The files inside are 0600.
- **Request lines in `launcher.log`.** Uvicorn's access log includes the path with its parameters, for example `/api/dmarc/geo?ip=...`. This follows from uvicorn's default behaviour; the file was not read when this page was written.
- **No lines in normal operation.** Normal operation writes no log lines to disk, only warnings and errors.

## How to delete your data

Everything above can be removed by hand, and the buttons that do it are described in [OPERATIONS.md](OPERATIONS.md). In short: deleting the `data/` and `logs/` folders removes what Seisa stored, and "Remove icon" in Info removes the desktop icon.

## Language model (OpenRouter)

This section explains what the optional language model receives. In one sentence: nothing goes to the model unless you click "Analyze" and have set an OpenRouter key.

- **Model.** The default is `anthropic/claude-sonnet-4.5`. The `OPENROUTER_MODEL` setting in `.env` changes it.
- **What it receives.** The facts computed by Seisa, the prepared e-mail source (at most 120 000 characters) and, in the AbuseIPDB tab, the first 12 000 characters of the AbuseIPDB policy text. Details are in the table above.
- **Untrusted data.** The e-mail sits between the markers `===EMAIL-START===` and `===EMAIL-END===`. The same markers inside the e-mail are replaced, and the prompt tells the model never to follow instructions found in the message. This is a precaution, not a guarantee.
- **Facts stay in code.** The model only explains facts that code computed (Email tab) or gives an advisory opinion and a draft comment (AbuseIPDB tab). Details are in [COMPLIANCE.md](COMPLIANCE.md).
- **Cost.** The cost shown is the one OpenRouter reports in its answer. Seisa does not estimate prices.
- **Answer length.** The Email tab limits an answer to 64 000 output tokens. If an answer is cut off, "Finish the analysis" continues it.
- **Time limit.** After 120 seconds without data from OpenRouter the request ends with a plain message. Connecting may take 30 seconds.
- **No double analysis by accident.** Before "Analyze", the Email tab checks locally whether the same source was analysed before and shows the saved result and its cost.
- **Outside Seisa.** What OpenRouter and the model provider do with the data is governed by their own terms, not by Seisa.

## Safeguards

These are the protections that the code enforces. The right column shows what keeps each of them from silently breaking.

| Safeguard | Where in the code | What watches it |
|---|---|---|
| Listens only on `127.0.0.1` | `seisa.sh` (`--host 127.0.0.1`) | No test: it is an argument to the server |
| The `Host` header must be `127.0.0.1` or `localhost` (protection against DNS rebinding) | `backend/main.py` | The harness case "foreign Host header accepted (DNS rebinding)" |
| Cross-site guard on `/api/`: `Sec-Fetch-Site` and `Origin` must be this server (scheme, loopback name and port); otherwise HTTP 403 | `backend/main.py` | The harness guard cases and `tests/test_origin_guard.py` |
| Content-Security-Policy on every response: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'` | `backend/main.py` | The harness case "CSP header on /" |
| Every insertion of untrusted text into the page goes through `escapeHtml`; the language catalogues hold no HTML; the model's Markdown is rendered through an allow-list of tags without attributes and links | `frontend/js/util.js`, `frontend/js/markdown-render.js`, `scripts/check_i18n.py` | A mock answer with `<img onerror>` in the harness; the manual `window.__xss` check (no browser automation) |
| Hard checks of a report (public IP, attack age 0 to 60 days, 1 to 30 known categories) and the 15-minute repeat block are enforced by the backend on every send | `backend/report_builder.py`, `backend/report_utils.py`, `backend/routers/abuseipdb_report.py` | `tests/test_report_builder.py`; the harness report cases |
| Sending is manual. A model's "fail" or a failed hard check keeps the button disabled; personal data in the comment asks for confirmation | `frontend/js/report-builder.js` | `tests/test_report_checks_js.py` (partly), the rest by hand |
| Security facts (sender IP, Received chain, SPF/DKIM/DMARC, report eligibility, score) are computed in Python, never only by the model | `backend/email_parser.py`, `backend/email_forensics.py`, `backend/scoring.py`, `backend/mail_trust.py` | `tests/test_email_parser.py`, `test_mail_trust.py`, `test_scoring.py` and the golden files in `tests/golden/` |
| Data files 0600, folders with raw e-mails and logs 0700; writes are atomic (a temporary file, then a rename) | `backend/storage.py`, `backend/analyses.py`, `backend/history_store.py`, `backend/logging_config.py` | `tests/test_data_permissions.py` |
| API keys are never returned by the API or printed; Info shows only whether a key is set; quota errors are reduced to a status, so the VirusTotal key in the address never reaches a message | `backend/routers/about.py`, `backend/api_limits.py` | The pre-commit hook (key patterns). No test covers an `/api/about` answer without keys |
| Inputs that end up in service addresses are validated: an IP or a plain host name, a URL with http or https and a public host, the shape of a urlscan id, the characters of a search host | `backend/aggregator.py`, `backend/urlscan_input.py`, `backend/routers/urlscan.py` | The harness case "urlscan uuid path injection", `tests/test_fuzz_parsers.py` |
| Size limits on input and parsing: e-mail source 3 000 000 characters (above 6 000 000 refused before parsing), one Received header 8 192 characters, 100 Received headers, 4 000 characters of encoded words, DOM 2 000 000, theme file 8 KB; parsing runs off the main loop | `backend/config.py`, `backend/email_parser.py`, `backend/mail_source.py`, `backend/urlscan_forms.py`, `backend/themes.py` | `tests/test_request_limits.py`, `tests/test_parser_limits.py` (slow) |
| Colour theme files cannot inject CSS: only known colour keys with `#rrggbb` values become CSS | `backend/themes.py` | `tests/test_themes.py` and the harness (hostile theme files) |
| The scanned page is never opened by Seisa or your browser: the screenshot is fetched by the backend and checked to be a PNG under 6 MB, and the DOM is only parsed | `backend/services/urlscan.py`, `backend/urlscan_forms.py` | The harness case "urlscan screenshot", `tests/test_urlscan_service.py` |

## Threat model

This section says honestly what Seisa protects against and what it does not. Seisa is a tool for one person on one computer, and its design assumes that the computer itself is trusted.

Seisa protects against:

- **Other computers on the network.** The server is bound to `127.0.0.1`.
- **Web pages in other tabs.** They cannot read the API (CORS is not enabled and the `Host` is checked), and their background requests are refused.
- **Hostile content.** Text in e-mails, scanned pages, DMARC files and service answers is shown only as text, links are defanged, and nothing is loaded or run.
- **A model talked into a wrong fact.** Facts come from code; if the model disagrees, Seisa only shows a warning.
- **Accidental or malformed reports.** The backend repeats the hard checks, sending is manual, and a personal-data scan runs first.

Seisa does NOT protect against:

- **Other programs and other user accounts on the same computer.** Anything that can open a connection to `127.0.0.1:54321` can use the whole API without a password: read the history and the saved e-mails, or send reports with your key. File permissions do not help while Seisa is running.
- **Malware on your computer.** It can read `.env` and `data/` directly.
- **What the services see and keep.** The IPs, domains, URLs, e-mail contents and reports you send to them are theirs to handle.
- **Missing encryption at rest.** Data files are plain JSON; the protection is file permissions and your disk encryption.
- **A wrong or misled model.** Its text is educational and its opinion is advisory.
- **A public urlscan.io scan.** It publishes the URL, with any secret in it, to everyone.

A note about the cross-site guard: modern browsers send `Sec-Fetch-Site`. Without it, `Origin` must name this server exactly (scheme, `127.0.0.1` or `localhost`, and port), so a page of another local application on a different port is refused. A local program, as opposed to a web page, can still send any header.

## Reporting a vulnerability

If you find a weakness in Seisa, please report it privately. How to do that, and what counts as a vulnerability, is in [SECURITY.md](../SECURITY.md).

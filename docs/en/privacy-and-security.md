# Privacy, threat model and security

**English** | [Polski](../pl/privacy-and-security.md) · [Documentation index](index.md) · [README](../../README.md)

## Privacy and data flow

Seisa listens only on `127.0.0.1` and has no login. Nothing leaves the machine except what is listed here, and every row is triggered by an action of yours. The frontend loads nothing from a CDN, no fonts, no analytics; `marked.min.js` is bundled.

### What leaves your machine

| Action | What is sent | To | When |
|---|---|---|---|
| IP lookup (and batch) | the IP address (in batch mode also a domain name) | VirusTotal, AlienVault OTX, Cloudflare Radar, AbuseIPDB, GreyNoise - only those with a key | when you run the lookup |
| IP lookup, free part | the IP address; a domain name in batch mode | `rdap.org` (an RDAP bootstrap that redirects to the regional registry), your DNS resolver (reverse DNS), and WHOIS servers for domain names (`python-whois`) | when you run the lookup |
| URL scan | the URL and the chosen visibility; the domain in the "Earlier scans" search; the scan id when the result, the screenshot and the DOM are fetched | urlscan.io | when you scan |
| DMARC "geo (RDAP)" | one IP address, from the backend | RDAP (`rdap.org`, then the regional registry), as in the IP tab | only on the click in an expanded row |
| Email: "Analyze" (not "Analyze without LLM"), "Finish the analysis", "Ask" | the whole e-mail source (with personal data), and for "Ask" the question and the fragment | OpenRouter | only on that click; the interface says so before sending |
| AbuseIPDB: "Analyze" | the whole e-mail source | OpenRouter | only on that click |
| AbuseIPDB: address check | the IP | AbuseIPDB (`/check`) | when an IP is entered and a key exists |
| AbuseIPDB: "Send" | the IP, categories, timestamp, comment | AbuseIPDB (`/report`) - **public** | only on a deliberate click |
| Info: "Refresh limits" | your keys' quota requests | VirusTotal, urlscan.io, OpenRouter | only on the click; none of these calls uses quota |
| Cisco Talos | nothing from Seisa; the button only helps you open Talos yourself | - | you click it |

Seisa's requests to OpenRouter identify the application as Seisa. Everything else in the interface (History, Logs, comparisons, exports, the citation check, the duplicate check) is local.

### What stays local

- `data/` holds the history, the counters, the log of sent reports and the saved e-mail analyses (with the raw messages, files `0600`, the directory `0700`); `logs/` holds errors and warnings. Both are gitignored. See [Data files](architecture.md#data-files).
- API keys stay in `.env` (gitignored) and are never sent to the frontend; the Info tab shows only whether a key is set.
- The browser stores only per-viewer conveniences in `localStorage` (the interface language under `seisa.lang`, the chosen pane, which cards you left open).
- There is no telemetry and no update check.

### Threat model

**Seisa defends against:**

- untrusted content (e-mails, DMARC XML, urlscan pages, comments in third-party API answers) running code in the interface or making the tool fetch something: an HTML allow-list, a Content-Security-Policy, non-clickable "defanged" links, and nothing from a message is ever opened or downloaded;
- another web page talking to your local API (a loopback-only `Host` header blocks DNS rebinding; scripts only from Seisa's own origin);
- leaking data by accident: the LLM is called only after an explicit click, the AbuseIPDB comment gets a personal-data scan with masking, and the hard checks are re-computed in the backend.

**Seisa does not defend against:**

- someone with access to your machine or user account: there is no authentication, any local process can call the API, `.env` is plain text;
- exposing port 54321 to a network: it is a single-user tool, do not do that;
- what you send to third parties: once an e-mail reaches OpenRouter or a report reaches AbuseIPDB (which shows comments publicly) it is theirs;
- a wrong LLM answer: the verdict is an aid, the citation check is a hint, not proof.

### LLM cost

Only calls to OpenRouter cost money (per token, depending on the model; the tokens include the model's hidden reasoning). The cost is read from the `usage.cost` that OpenRouter returns and is shown next to the action button; Seisa has no price table.

| Paid (OpenRouter) | Free (local or free-plan APIs) |
|---|---|
| Email: "Analyze", "Finish the analysis", "Ask" | Email: the deterministic analysis, the duplicate check, the citation check, comparison, all exports |
| AbuseIPDB: "Analyze" | AbuseIPDB: the hard checks, the personal-data scan, "Send" (an AbuseIPDB call, no LLM) |
| | IP, URLScan, DMARC, History, Logs, Info |

Before a paid e-mail analysis Seisa checks whether the same message was analysed already and offers to open the saved analysis instead.

## Security invariants

If you change the code, keep these true; each names where it lives.

1. **Loopback-only `Host` header** (`backend/main.py`, `TrustedHostMiddleware`): blocks DNS rebinding.
2. **Content-Security-Policy on every response** (`backend/main.py`): scripts only from the tool's own origin. The frontend calls only its own backend (`connect-src 'self'`); if it ever has to call another host, add it there.
3. **Third-party text is data.** Rendered Markdown goes through an allow-list (`frontend/js/markdown-render.js`: only the tags the reports use, links only with `http(s)`, anything else shown as inert text), and the result of `t()` put into `innerHTML` always goes through `escapeHtml` (`frontend/js/util.js`).
4. **Links from e-mails and scans are never clickable** and are shown defanged; nothing from a message is opened or downloaded; the urlscan screenshot is fetched by the backend.
5. **The LLM is called only after an explicit click**, and the banners that say so must stay (`email.js`, `report-builder.js`).
6. **Hard checks are re-computed in the backend** on every change and when sending (`backend/report_builder.py`, `backend/routers/abuseipdb_report.py`); never move that validation to the frontend only.
7. **Indicators are validated before they reach URL paths** (`is_valid_indicator` in `backend/aggregator.py`: only real IP addresses and host names), urlscan ids must be UUIDs, and request sizes are bounded (`backend/config.py`).
8. **File permissions:** `data/analyses/` is `0700` and its files `0600` (they hold raw e-mails).
9. **Keys stay in the backend** (`.env`); `GET /api/about` exposes only whether a key is set.

To verify: `./.venv/bin/python scripts/api_harness.py` includes security probes (a foreign `Host`, the CSP header, path injection) and its mocked answers contain hostile HTML; in the browser (`--serve`), XSS payloads must leave `window.__xss` at 0.

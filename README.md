<p align="center"><img src="frontend/logo.png" alt="Seisa" width="120"></p>
<p align="center"><b>Seisa 2.1.1</b></p>

# Seisa

**English** | [Polski](README.pl.md)

![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-blue) ![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue) ![Runs locally on 127.0.0.1](https://img.shields.io/badge/runs-locally%20on%20127.0.0.1-green) ![No telemetry](https://img.shields.io/badge/telemetry-none-green)

**Seisa** is a local tool for looking closely at suspicious things without handing them to yet another web service: IP reputation from several sources merged into one explained score, live URL scans, DMARC aggregate reports, an educational analysis of an e-mail's source and the preparation of AbuseIPDB abuse reports. It is one Python process on `127.0.0.1` with no login, no database and no build step.

<!-- Screenshot to add: docs/img/hero-ip.png (the IP tab with a verdict and the address identity card) -->

- **Local by design.** It listens only on `127.0.0.1` and sends nothing anywhere except the actions you start yourself; [what leaves your machine](#what-leaves-your-machine) is one table.
- **Explains instead of only scoring.** Every score shows the sources behind it; the e-mail analysis teaches how to read headers instead of only giving a verdict.
- **Hard checks live in code, not in the LLM.** Whether a report to AbuseIPDB may be sent (age of the attack, public IP, category) is computed in Python and re-checked by the backend; the LLM only advises.
- **Works with what you have.** A missing API key only switches that service off; without an OpenRouter key the LLM layer is off and the deterministic analysis still works.
- **Bilingual.** The whole interface, the backend messages and the reports exist in English and Polish.

**Seisa** (精査, *せいさ*, pronounced roughly "say-sah") is a Japanese word meaning a thorough, detailed examination - looking at something closely. 精 (*sei*) = precise, exact, detailed; 査 (*sa*) = to examine, to inspect.

Author: Arkadiusz Polak ([GitHub: arcymonek](https://github.com/arcymonek), e-mail: kontakt (at) arkadiuszpolak (dot) pl). Security issues: see [SECURITY.md](SECURITY.md).

## What Seisa does

| Tab | What it does | Needs | What it sends out |
|---|---|---|---|
| [IP](docs/en/tabs.md#ip) | Reputation of an IP address or a domain name from VirusTotal, OTX, Cloudflare Radar, AbuseIPDB, GreyNoise and RDAP/reverse DNS, merged into one 0-100 score | a key per service (each optional) | the address, to the services you have keys for, plus the free RDAP/DNS lookups |
| [URLScan](docs/en/tabs.md#urlscan) | A live scan of a URL through urlscan.io with a verdict, a screenshot, redirects, forms and certificates | `URLSCAN_API_KEY` | the URL, to urlscan.io |
| [DMARC](docs/en/tabs.md#dmarc) | Aggregate DMARC reports (`.xml`, `.gz`, `.zip`) unpacked and analysed in the browser | nothing | nothing (an optional button asks the backend for RDAP and reverse DNS data on one IP, like the IP tab) |
| [Email](docs/en/tabs.md#email) | An educational analysis of an e-mail's source: deterministic findings at once, plus an optional streamed LLM lesson | OpenRouter key for the LLM part | the whole source to OpenRouter, only after an explicit click |
| [AbuseIPDB](docs/en/tabs.md#abuseipdb) | Prepares and sends an abuse report: source IP, eligibility, categories, an English comment, hard checks | `ABUSEIPDB_API_KEY` (OpenRouter optional) | the IP and, on "Send", the report, to AbuseIPDB |
| [History](docs/en/tabs.md#history) | Everything Seisa remembers, reopenable, comparable, pinnable | nothing | nothing |
| [Logs](docs/en/tabs.md#logs) | Errors and warnings of every service | nothing | nothing |
| [Info](docs/en/tabs.md#info) | Version, key status, API limits, recent changes, license | nothing | quota requests only on "Refresh limits" |

<!-- Screenshots to add: docs/img/tab-*.png (one per tab, see the Tabs section) -->

Every tab is described in [Tabs](docs/en/tabs.md); an end-to-end example is the [Walkthrough](docs/en/tabs.md#walkthrough-from-a-suspicious-e-mail-to-a-report). All tabs share one layout: a verdict banner, summary tiles, then collapsible cards that open by themselves only when they carry a signal.

## Quick start

### Requirements

- **Python 3.11+** on **macOS** or **Linux**. On Debian/Ubuntu install the venv module first (`sudo apt install python3-venv`). Windows is not supported natively; it works through WSL as Linux.
- A current web browser. `git` is optional (the Info tab reads the release list from `git log` when the directory is a checkout).
- No API key is required to start; see [First steps without any keys](#first-steps-without-any-keys).

### Install and run

Get the code (clone the repository or unpack a release archive) and, in the project directory:

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
./seisa.sh
```

`requirements.lock` holds the exact tested versions (`pip install -r requirements.lock` instead of `requirements.txt`). The start script launches the server and opens the browser at `http://127.0.0.1:54321` (macOS: `open`; Linux with a desktop: `xdg-open`; otherwise it only prints the address to open by hand). If `.venv/` is missing it says so and stops.

Without the script:

```bash
./.venv/bin/uvicorn backend.main:app --port 54321 --host 127.0.0.1
```

To use another port, start `uvicorn` yourself with `--port`. You can add a shell alias for the script (for example `alias seisa='~/path/to/seisa/seisa.sh'`). Restart Seisa after editing `.env`; the keys are read at start.

### First steps without any keys

Try the whole interface on fictitious data, with no keys and no network traffic, by starting the mocked application used by the test harness (all external services are replaced by fixed answers, data goes to a temporary directory):

```bash
./.venv/bin/python scripts/api_harness.py --serve 8765
```

Then open `http://127.0.0.1:8765`. With the real application and no keys:

- **Works:** the [DMARC](docs/en/tabs.md#dmarc) tab completely, the deterministic analysis in the [Email](docs/en/tabs.md#email) tab, WHOIS/rDNS (RDAP and reverse DNS) in the [IP](docs/en/tabs.md#ip) tab, [History](docs/en/tabs.md#history), [Logs](docs/en/tabs.md#logs), [Info](docs/en/tabs.md#info) and the language switch.
- **Switched off, per service:** every service without a key shows "no API key" and is left out of the aggregate score. Without `OPENROUTER_API_KEY` the LLM layer is off (the [AbuseIPDB](docs/en/tabs.md#abuseipdb) tab then runs in rule-based mode and never claims that an e-mail qualifies). Sending a report and the "what AbuseIPDB already knows" card need `ABUSEIPDB_API_KEY`.

## Configuration

### API keys (.env)


Copy `.env.example` to `.env`, fill in the keys you have and make the file readable only for you (`chmod 600 .env`). `.env` is gitignored and the keys never reach the browser.

| Variable | Required? | Where to get it |
|---|---|---|
| `URLSCAN_API_KEY` | yes, for urlscan.io | [urlscan.io/user/signup](https://urlscan.io/user/signup) |
| `VIRUSTOTAL_API_KEY` | yes, for VirusTotal | [virustotal.com](https://www.virustotal.com) |
| `OTX_API_KEY` | yes, for OTX | [otx.alienvault.com](https://otx.alienvault.com) |
| `CLOUDFLARE_RADAR_API_KEY` | yes, for Cloudflare Radar | [dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens) |
| `ABUSEIPDB_API_KEY` | yes, for AbuseIPDB (reading and reports) | [abuseipdb.com](https://www.abuseipdb.com) |
| `GREYNOISE_API_KEY` | yes, for GreyNoise | [greynoise.io](https://www.greynoise.io) |
| `OPENROUTER_API_KEY` | no, optional | [openrouter.ai](https://openrouter.ai) - enables the LLM analysis in the Email tab and the eligibility assessment and draft report comment in the AbuseIPDB tab |
| `OPENROUTER_MODEL` | no | `anthropic/claude-sonnet-4.5` by default - verify the exact slug on the OpenRouter model list |

> **Warning:** the Cloudflare key **must be a scoped API Token with Radar read permission, not the old Global API Key** (the latter gives a 401 error).

A missing key for any service does not block the rest of the tool - the service simply shows the status "no API key" and is excluded from the aggregate score.

Limits, throttling and the free-plan quotas: [Configuration and limits](docs/en/configuration.md).

## Privacy and data flow

Seisa listens only on `127.0.0.1` and has no login. Nothing leaves the machine except what is listed here, and every row is triggered by an action of yours. The frontend loads nothing from a CDN, no fonts, no analytics; `marked.min.js` is bundled.

### What leaves your machine

| Action | What is sent | To | When |
|---|---|---|---|
| IP lookup (and batch) | the IP address or a domain name | VirusTotal, AlienVault OTX, Cloudflare Radar, AbuseIPDB, GreyNoise - only those with a key | when you run the lookup |
| IP lookup, free part | the IP address or a domain name | `rdap.org` (an RDAP bootstrap that redirects to the regional registry), your DNS resolver (reverse DNS; for a domain the A, AAAA, NS, MX, CAA and TXT records, plus one query for a random subdomain to detect wildcard DNS and one A query per name server), and WHOIS servers for domain names (`python-whois`) | when you run the lookup |
| URL scan | the URL, the chosen visibility and, if you set them, the scan country and the user agent; the domain in the "History" search of earlier scans; the scan id when the result, the screenshot and the DOM are fetched | urlscan.io | when you scan |
| DMARC "geo (RDAP)" | one IP address, from the backend | RDAP (`rdap.org`, then the regional registry) and your DNS resolver (reverse and forward lookup), as in the IP tab | only on the click in an expanded row |
| Email: "Analyze" (not "Analyze without LLM"), "Finish the analysis", "Ask" | the whole e-mail source (with personal data), and for "Ask" the question and the fragment | OpenRouter | only on that click; the interface says so before sending |
| AbuseIPDB: "Analyze" | the whole e-mail source | OpenRouter | only on that click |
| AbuseIPDB: address check | the IP | AbuseIPDB (`/check`) | when an IP is entered and a key exists |
| AbuseIPDB: "Send" | the IP, categories, timestamp, comment | AbuseIPDB (`/report`) - **public** | only on a deliberate click |
| Info: "Refresh limits" | your keys' quota requests | VirusTotal, urlscan.io, OpenRouter | only on the click; none of these calls uses quota |
| Cisco Talos | nothing from Seisa; the button only helps you open Talos yourself | - | you click it |

Seisa's requests to OpenRouter identify the application as Seisa. Everything else in the interface (History, Logs, comparisons, exports, the citation check, the duplicate check) is local.

### Threat model

Seisa defends against untrusted content running code in the interface or making the tool fetch something, against another web page talking to your local API through your browser (an origin guard refuses cross-site requests), and against leaking data by accident (the LLM is called only after an explicit click, the AbuseIPDB comment gets a personal-data scan, the hard checks are re-computed in the backend). It does not defend against someone with access to your machine or account (there is no authentication: any local process can call the API and read what Seisa stores, including raw e-mails), against exposing port 54321 to a network, against what you send to third parties, or against a wrong LLM answer. The full model, what stays local, the LLM cost table and the security invariants: [Privacy, threat model and security](docs/en/privacy-and-security.md).

## Documentation

The full documentation is in [`docs/en/`](docs/en/index.md) (Polish: [`docs/pl/`](docs/pl/index.md)):

- [Tabs and walkthrough](docs/en/tabs.md) - every tab in detail, and a walkthrough from a suspicious e-mail to a report;
- [Configuration and limits](docs/en/configuration.md) - the `.env` keys, limits and throttling;
- [Privacy, threat model and security](docs/en/privacy-and-security.md) - the full data flow, the threat model, the LLM cost, the security invariants;
- [Architecture and design](docs/en/architecture.md) - design decisions and non-goals, the stack, the modules, the data files;
- [API reference](docs/en/api.md) - the backend endpoints;
- [Forking and extending](docs/en/extending.md) - should you fork, how to add a service, a language or a tab, workflow, tests and conventions;
- [Troubleshooting](docs/en/troubleshooting.md) - problems and the FAQ.

## Changelog

The latest releases; every release is in [CHANGELOG.md](CHANGELOG.md), and the Info tab lists the recent ones from the git log.

- **2.0.68** - IP tab: single mode now accepts a domain name as well as an IP address (the type is detected by the backend, as in batch mode); no DNS resolution to an IP is done, the domain itself is checked.
- **2.0.60** - an origin guard for `/api/`: requests that the browser marks as cross-site (`Sec-Fetch-Site`) or that carry a foreign `Origin` get 403, so another web page can no longer use up your API quotas or LLM budget; the docs state plainly that a local process is not stopped.
- **2.0.59** - DMARC tab: the geo button asks the backend (RDAP, as in the IP tab) instead of `ipwho.is`; the Content-Security-Policy allows only `connect-src 'self'`. RDAP has no ASN, so none is shown.
- **2.0.58** - the README split into a short README and a documentation set in `docs/en/` and `docs/pl/`; `check_i18n.py` checks the docs parity and dead links.
- **2.0.57** - the README (EN and PL) rebuilt: structure, privacy table, threat model, developer and fork guide, endpoints and data files; the full [CHANGELOG.md](CHANGELOG.md) added.
- **2.0.56** - Info: the collapsed API limits card with the free-plan limits of every keyed service; the VirusTotal daily counter resets at 00:00 UTC.
- **2.0.55** - Info: the privacy banner removed and the cards reordered.
- **2.0.54** - Email: all Lesson cards start collapsed; a "Show source" button next to "Ask".

## License and contributing

Seisa is made available under the [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0) license - the full text is in the [LICENSE](LICENSE) file. The code is public (*source-available*), but **this is not an open-source license in the OSI sense**: you may use, copy, modify and distribute it (including forks) only for noncommercial purposes, among others personal, hobby, educational and research use and use by charitable, educational, public and government organisations. Commercial use (including selling, commercial forks and work for the profit of a company) requires a separate permission of the author.

The bundled `frontend/vendor/marked.min.js` remains under its own MIT license (the header in the file).

Rules for reporting bugs and contributing: [CONTRIBUTING.md](CONTRIBUTING.md) - external code changes (pull requests) are not accepted. Security issues: [SECURITY.md](SECURITY.md).

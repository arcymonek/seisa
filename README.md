<p align="center"><img src="frontend/logo.png" alt="Seisa" width="120"></p>
<p align="center"><b>Seisa 2.1.28</b></p>

# Seisa

**English** | [Polski](README.pl.md)

[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-blue)](LICENSE) ![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue) ![Runs locally on 127.0.0.1](https://img.shields.io/badge/runs-locally%20on%20127.0.0.1-green) ![No telemetry](https://img.shields.io/badge/telemetry-none-green)

[Quick start](#quick-start) · [Configuration](#configuration) · [Privacy and data flow](#privacy-and-data-flow) · [Documentation](#documentation) · [Changelog](#changelog) · [License and contributing](#license-and-contributing)

**Seisa** is a local tool for looking closely at suspicious things without handing them to yet another web service: IP reputation from several sources merged into one explained score, live URL scans, DMARC aggregate reports, an educational analysis of an e-mail's source and the preparation of AbuseIPDB abuse reports. It is one Python process on `127.0.0.1` with no login, no database and no build step.

Bug reports and feature ideas are welcome as issues; code changes (pull requests) are not accepted - see [CONTRIBUTING.md](CONTRIBUTING.md), or [Forking and extending](docs/en/extending.md) if you want to fork and modify Seisa yourself.

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

Every tab is described in [Tabs](docs/en/tabs.md); an end-to-end example is the [Walkthrough](docs/en/tabs.md#walkthrough-from-a-suspicious-e-mail-to-a-report). All tabs share one layout: a verdict banner (no fill, only its border is coloured red, amber or green), summary tiles, then collapsible cards that open by themselves only when they carry a signal; a plain-language "Explanations" card and contextual glossary tooltips (hover or keyboard focus on a dotted-underline term) turn the technical detail into something a non-specialist can read.

## Quick start

### Requirements

- **Python 3.11+** on **macOS** or **Linux**. On Debian/Ubuntu install the venv module first (`sudo apt install python3-venv`). Windows is not supported natively; it works through WSL as Linux.
- A current web browser. `git` is optional (the Info tab reads the release list from `git log` when the directory is a checkout).
- No API key is required to start; see [First steps without any keys](#first-steps-without-any-keys).

### Install and run

Get the code and, in the project directory:

```bash
git clone https://github.arcymonek.eu/arcy/seisa.git
cd seisa
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
| `OPENROUTER_MODEL` | no | `anthropic/claude-sonnet-4.5` by default |

> `OPENROUTER_MODEL` is a model slug on OpenRouter, and OpenRouter renames and retires slugs over time - verify the exact current one on its model list before relying on the default.

> **Warning:** the Cloudflare key **must be a scoped API Token with Radar read permission, not the old Global API Key** (the latter gives a 401 error).

A missing key for any service does not block the rest of the tool - the service simply shows the status "no API key" and is excluded from the aggregate score.

Limits, throttling and the free-plan quotas: [Configuration and limits](docs/en/configuration.md).

## Privacy and data flow

Seisa listens only on `127.0.0.1` and has no login. Nothing leaves the machine except what is listed here, and every row is triggered by an action of yours. The frontend loads nothing from a CDN, no fonts, no analytics; `marked.min.js` is bundled. This is a source-available tool with no build step and no obfuscation - if you would rather verify "local by design" and "no telemetry" yourself than take them on faith, `backend/` is short enough to read, and every outgoing call it makes is the ones listed below.

### What leaves your machine

The most common actions, condensed - the full table of every action, including the rarer ones (DMARC's optional geo lookup, the Info tab's "Refresh limits", the Cisco Talos button), is in [What leaves your machine](docs/en/privacy-and-security.md#what-leaves-your-machine).

| Action | What is sent | To | When |
|---|---|---|---|
| IP lookup | the IP address or a domain name | VirusTotal, AlienVault OTX, Cloudflare Radar, AbuseIPDB, GreyNoise - only those with a key - plus the free RDAP/DNS lookups | when you run the lookup |
| URL scan | the URL and, if you set them, the scan country and the user agent | urlscan.io | when you scan |
| Email: "Analyze" (not "Analyze without LLM"), "Finish the analysis" | the whole e-mail source (with personal data) | OpenRouter | only on that click; the interface says so before sending |
| AbuseIPDB: "Analyze", then "Send" | the whole e-mail source on "Analyze"; the IP, categories, timestamp and comment on "Send" | OpenRouter, then AbuseIPDB (`/report`) - **public** | only on that click; "Send" is a deliberate, separate click |

Seisa's requests to OpenRouter identify the application as Seisa. Everything else in the interface (History, Logs, comparisons, exports, the citation check, the duplicate check) is local.

### What stays on your machine

Everything that is not sent out is kept in two gitignored folders under the project directory: `data/` (history, saved e-mail analyses with the raw messages, the AbuseIPDB report log, usage counters) and `logs/` (errors and warnings) - files `0600`, the `data/analyses/` directory `0700`. There is no authentication, so treat these folders like the raw e-mails they can contain: to wipe everything, delete `data/` and `logs/`, or use "Clear" in the History and Logs tabs for a more selective cleanup. Full list and the reasoning: [What stays local](docs/en/privacy-and-security.md#what-stays-local).

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

Recent feature highlights below; the full list - including maintenance-only releases such as documentation fixes - is in [CHANGELOG.md](CHANGELOG.md), and the Info tab lists the most recent ones from the git log.

- **2.1.22** - URLScan and AbuseIPDB tabs now also end with a plain-language "Explanations" card and glossary tooltips, matching IP and DMARC.
- **2.1.21** - IP and DMARC tabs: the "Explanations" cards were rewritten in plain language for non-specialists, and jargon labels (ASN, reverse DNS, SPF/DKIM/DMARC/CAA records, the AbuseIPDB confidence score...) now carry a contextual glossary tooltip, the same mechanism already used in the Email tab.
- **2.1.20** - Docs: README trimmed and de-duplicated against `docs/` - a table of contents, a literal `git clone` command, where local data lives and how to wipe it; the "what leaves your machine" table is now a short excerpt linking to the full one in `docs/privacy-and-security.md`, and `docs/configuration.md`'s `.env` keys table now links back to the README instead of repeating it.
- **2.1.17** - AbuseIPDB tab: every hop in the address card now shows a private/public label and its own SMTP-AUTH/DKIM corroboration badge, not just the boundary hop; `is_reportable_ip` shares its private/special-IP check with the rest of the tool instead of a third, separate copy of it.
- **2.1.16** - Email tab: the "sender IP" fact and the route diagram now walk through an external relay's own internal hops (the same mechanism as the AbuseIPDB tab), fixing a wrong sender IP for chains that span more than one mail operator.
- **2.1.15** - Email tab: trust-boundary detection now recognises internal relay hops named with bare, dotless identifiers instead of miscounting them as a different operator; every hop's IP is marked private or public and gets an SMTP-AUTH/DKIM corroboration note. Domain/IP/relay-trust logic shared by the Email and AbuseIPDB tabs is consolidated into `backend/mail_trust.py`.

## License and contributing

Seisa is made available under the [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0) license - the full text is in the [LICENSE](LICENSE) file. The code is public (*source-available*), but **this is not an open-source license in the OSI sense**: you may use, copy, modify and distribute it (including forks) only for noncommercial purposes, among others personal, hobby, educational and research use and use by charitable, educational, public and government organisations. Commercial use (including selling, commercial forks and work for the profit of a company) requires a separate permission of the author.

The bundled `frontend/vendor/marked.min.js` remains under its own MIT license (the header in the file).

Rules for reporting bugs and contributing: [CONTRIBUTING.md](CONTRIBUTING.md) - external code changes (pull requests) are not accepted. Security issues: [SECURITY.md](SECURITY.md).

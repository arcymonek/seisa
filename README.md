<p align="center">
  <img src="frontend/logo.png" alt="Seisa logo" width="160"><br>
  <b>Seisa 2.4.30</b>
</p>

**English** | [Polski](README.pl.md)

# Seisa

Seisa (精査, "a careful, detailed examination") is a tool that runs on your own computer and helps you judge whether an IP address, a web link, a DMARC report or an e-mail can be trusted, and report abuse to AbuseIPDB. You do not need to be an IT specialist: every result comes with plain explanations.

## What Seisa does

Pick the tab that matches what you have in your hand. [docs/USER_GUIDE.md](docs/USER_GUIDE.md) describes every tab in detail.

| Tab | What it does | Needs a key? |
|---|---|---|
| IP | Looks up an IP address or a domain in several sources at once and combines them into one 0-100 risk score | Each source has its own key (WHOIS, RDAP and DNS need none) |
| URLScan | Has urlscan.io open a suspicious link for you and returns a report with a screenshot | `URLSCAN_API_KEY` |
| DMARC | Reads DMARC reports of your domain in the browser and shows who sends mail as you | No |
| Email | Explains a suspicious e-mail step by step: local facts, plus an optional lesson from a language model | Only for the lesson |
| AbuseIPDB | Prepares, checks and, on your click, sends an abuse report about the sender of an e-mail | To send |
| History | Your recent checks, scans, imports, analyses and reports in one place | No |
| Logs | Errors and warnings of the services | No |
| Info | Version, key status, limits, language, theme and the application icon | No |

## Principles

- **Local.** Seisa listens only on `127.0.0.1`. It has no account, no telemetry and no update check.
- **Nothing without your click.** Nothing goes to an outside service until you click, with one documented exception (see "What leaves your computer").
- **Facts come from code.** Security facts (the sender's address, the route of the mail, SPF/DKIM/DMARC results) are computed by ordinary program code. The language model only explains them and may give an advisory second opinion.
- **Untrusted by default.** Links in e-mails and scanned pages are never clickable, and nothing in an e-mail is opened or downloaded.
- **Reports by hand.** A report reaches AbuseIPDB only after your click, and only after checks in the backend.

## Screenshots

| IP | URLScan |
|---|---|
| ![The IP tab](docs/images/ip_en.png) | ![The URLScan tab](docs/images/urlscan_en.png) |
| **DMARC** | **Email** |
| ![The DMARC tab](docs/images/dmarc_en.png) | ![The Email tab](docs/images/email_en.png) |

![The AbuseIPDB tab](docs/images/abuseipdb_en.png)

## Requirements

- macOS or Linux. The start scripts are Bash scripts; Windows is not supported directly (it may work through WSL, but this has not been tested).
- Python 3.11 or newer.
- A web browser. Seisa opens at `http://127.0.0.1:54321`, so port 54321 must be free.
- No API key is needed to start. Each key you add switches on one more service.
- Optional: git, to update Seisa and to see "Recent changes" in the Info tab.

## Quick start

### Install and run

```bash
git clone https://github.com/arcymonek/seisa.git
cd seisa
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
./seisa.sh
```

The last command starts Seisa and opens your browser. Keep the terminal window open while you use it; closing it stops Seisa. For the details (a ZIP download, the application icon, updating, troubleshooting), see [docs/OPERATIONS.md](docs/OPERATIONS.md).

### API keys (.env)

An API key is a long code that a service gives you so it knows who is asking. Create an account with the service, copy your key into the `.env` file after the `=` sign, and restart Seisa. A service without a key is simply skipped.

| Key | Service | What it switches on | Where to get it |
|---|---|---|---|
| `URLSCAN_API_KEY` | urlscan.io | The URLScan tab: scans, earlier scans, screenshots | [urlscan.io](https://urlscan.io) |
| `VIRUSTOTAL_API_KEY` | VirusTotal | An IP tab source for IPs and domains (Seisa limits itself to 4 requests a minute and 500 a day) | [virustotal.com](https://www.virustotal.com) |
| `OTX_API_KEY` | AlienVault OTX | An IP tab source for IPs and domains | [otx.alienvault.com](https://otx.alienvault.com) |
| `CLOUDFLARE_RADAR_API_KEY` | Cloudflare Radar | Context in the IP tab: network and place of an IP, ranking of a domain (not part of the score) | [dash.cloudflare.com](https://dash.cloudflare.com) |
| `ABUSEIPDB_API_KEY` | AbuseIPDB | An IP tab source; in the AbuseIPDB tab the history of an address and sending reports | [abuseipdb.com](https://www.abuseipdb.com) |
| `GREYNOISE_API_KEY` | GreyNoise | An IP tab source for IPs | [greynoise.io](https://www.greynoise.io) |
| `OPENROUTER_API_KEY` | OpenRouter | The language model: the Email lesson and the AbuseIPDB assessment and draft comment (paid by use) | [openrouter.ai](https://openrouter.ai) |
| `OPENROUTER_MODEL` | OpenRouter | Which model to use (the default is `anthropic/claude-sonnet-4.5`) | - |

WHOIS, RDAP and DNS lookups need no key and are always on. The Info tab shows whether each key is "set" or "missing", never the key itself. The account pages and prices belong to the services and may change; check them there.

## What leaves your computer

This is a short version of the full table in [docs/PRIVACY.md](docs/PRIVACY.md), which lists every call.

| Action | What is sent | To whom |
|---|---|---|
| IP: "Check" | The IP address or domain | The sources you selected (WHOIS, RDAP and DNS without a key; the others with their keys) |
| URLScan: "Scan" | The URL and your options | urlscan.io, which opens the page itself |
| DMARC: "geo (RDAP)" | One source IP. Loading a report sends nothing | RDAP and DNS |
| Email: "Analyze" | The e-mail (headers, decoded text, attachments only as a size and hash) and the computed facts. "Analyze without LLM" sends nothing | OpenRouter and the model provider |
| AbuseIPDB: "Analyze" | As for Email | OpenRouter and the model provider |
| AbuseIPDB: address in the form | The IP, looked up **automatically** (the only call without a click of its own, and only with a key) | AbuseIPDB |
| AbuseIPDB: "Send via AbuseIPDB API" | The public report: IP, categories, time and comment | AbuseIPDB |
| Info: "Refresh limits" | Quota queries | VirusTotal, urlscan.io, OpenRouter |

## Documentation

- [docs/USER_GUIDE.md](docs/USER_GUIDE.md): every tab, step by step, with an example from a suspicious e-mail to a report.
- [docs/OPERATIONS.md](docs/OPERATIONS.md): installing, starting, updating, limits, your data, uninstalling, troubleshooting.
- [docs/PRIVACY.md](docs/PRIVACY.md): what leaves your computer, what stays on it, the safeguards and the threat model.
- [docs/COMPLIANCE.md](docs/COMPLIANCE.md): how reports follow AbuseIPDB's rules, the role of the model, licences.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how Seisa is built and why.
- [docs/API.md](docs/API.md): the endpoints.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md): set-up, checks, hooks, versioning, writing documentation.
- [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [CHANGELOG.md](CHANGELOG.md).
- [AGENTS.md](AGENTS.md): rules for AI coding agents.

## Contributing

Bug reports, ideas and pull requests are welcome, and you do not have to be a programmer to help. Start with [CONTRIBUTING.md](CONTRIBUTING.md); the developer set-up is in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). Please report security problems privately, as described in [SECURITY.md](SECURITY.md). Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Built with Claude Code

Seisa's code, tests and documentation are written with Claude Code, Anthropic's AI coding assistant, under the author's direction. The author decides, reviews the behaviour and is responsible for the releases.

## License and contact

Copyright (c) 2026 Arkadiusz Polak. Seisa is free software under GPL-3.0-or-later: you may use, study, change and share it, also commercially, and a modified version you pass on must stay under the same licence, with its source. The full text is in [LICENSE](LICENSE). The bundled `marked` library (MIT) renders Markdown; the logo and icons are the author's work under the project licence.

Website: [seisa.eu](https://seisa.eu). Repository: [github.com/arcymonek/seisa](https://github.com/arcymonek/seisa). Contact: `contact@seisa.eu`.

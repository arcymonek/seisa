**English** | [Polski](pl/COMPLIANCE.md)

# Compliance

This page is for people who send reports to AbuseIPDB with Seisa, and for reviewers. In one sentence: you are responsible for every report, and Seisa helps by enforcing the basic rules in code and by never letting a language model decide the facts.

## Contents

- [Reporting to AbuseIPDB](#reporting-to-abuseipdb)
- [Facts in code, the model only helps](#facts-in-code-the-model-only-helps)
- [Third-party services](#third-party-services)
- [Personal data in e-mails](#personal-data-in-e-mails)
- [Licences](#licences)

## Reporting to AbuseIPDB

A report to AbuseIPDB is public and is published under your account. This section lists what Seisa checks for you, what it leaves to you and what the model is told. The binding rules are AbuseIPDB's own reporting policy (`https://www.abuseipdb.com/reporting-policy`); the file Seisa keeps is only a summary in its own words.

### What Seisa enforces before sending

These checks run in the backend on every send, whatever the page shows. If one fails, the report is not sent.

- **Manual only.** A report is sent only through the "Send via AbuseIPDB API" button. There is no automatic or bulk sending.
- **A valid public IP.** Private, loopback, link-local, reserved, multicast, unspecified, documentation and shared carrier-grade NAT (`100.64.0.0/10`) addresses cannot be reported.
- **A recent attack.** The attack time must be given and be 0 to 60 days old. Up to 1 hour in the future counts as now.
- **A known category.** At least one category is required, all from the AbuseIPDB list, at most 30.
- **No repeat within 15 minutes.** The same IP cannot be sent again within 15 minutes of your last accepted report of it. Seisa checks its local log, and AbuseIPDB applies the same rule on its side.
- **A key.** Without `ABUSEIPDB_API_KEY` the report can be prepared but not sent.
- **A clean comment.** The comment is cleaned right before sending: only printable ASCII is kept, white space is collapsed, a leading `=`, `+`, `-` or `@` (which could be read as a spreadsheet formula) gets a `'` in front, and the text is cut to 1 024 characters.
- **Time sent separately.** The attack time goes as ISO 8601 UTC without fractions. It is not written into the comment.
- **A log of every attempt.** Every attempt, accepted or refused, is written to the local report log `data/report_log.json`.

### What Seisa checks but you decide

These checks help you, but the final decision is yours. Some of them live only in the page, because the model's opinion is advisory.

- **The address.** Code picks the address to report from the Received chain: the first hop written by the recipient's own infrastructure. The other public addresses of the chain are offered as alternatives, marked "already reported" when your log has them.
- **"Received verified".** This check is green only for the address that the code picked, with high confidence and not taken from lines a relay wrote, or when the model confirmed it. If you change the address, it becomes "unknown".
- **A disputed check.** If the model marks a check as "fail", the "Send via AbuseIPDB API" button stays disabled. The backend does not know the model's opinion at send time.
- **Personal data.** The comment is scanned for your own addresses and their domains (taken from the recipients, with free-mail domains skipped), any other e-mail address and private IPv4 addresses. If something is found, "Send via AbuseIPDB API" asks for confirmation, and one click replaces the findings with `[redacted]`, `[email removed]` and `[internal IP]`.
- **A preview.** Before sending, you see exactly what goes to the API ("What will be sent to the API").
- **What AbuseIPDB knows.** Before sending, Seisa shows what AbuseIPDB already knows about the address (last 90 days) and your own recent reports of it (7 days). This lookup is automatic; see [PRIVACY.md](PRIVACY.md).
- **No model, no verdict.** Without a model, Seisa never says that a message qualifies. It only recognises a test sent from your own account to yourself. The verdict then stays "in doubt (not assessed)", and this does not block sending: the hard checks still run in the backend.

### What you are still responsible for

Seisa cannot judge whether a report is right. These points stay with you:

- **Public reports.** AbuseIPDB may remove reports or suspend reporting rights.
- **Not by score alone.** Do not report an address because of its AbuseIPDB score alone.
- **No spoofed sources.** Do not report spoofed sources (SYN or UDP floods). A TCP connection may be reported only after a completed handshake.
- **The right category.** The category must describe the actual attack, not "just in case".
- **Unrecognised personal data.** Names, phone numbers, IPv6 addresses and text in other forms are not recognised by the scan. They are your responsibility.

### The comment

The comment is the text people see next to your report. It is always written in English, whatever the interface language.

- **With a model.** With an OpenRouter key, the model drafts a detailed comment (aimed at about 900 characters).
- **Without a model.** Without a key, or when the model fails, Seisa builds a plain comment from the facts. It contains only the sender IP, a spoofing sentence (SPF or DMARC failed), attachments (name, size, type, double extension), a ransom or bitcoin wallet, and the local part of the Message-ID. The domain part of the Message-ID is dropped as personal data.
- **No ports.** Ports are removed from the model's draft (sentences naming a port and `ip:port`), because an e-mail does not say which port was attacked. You may add a port by hand; the text you write is not stripped of ports at send time.
- **Editable.** The draft is editable. Whatever you change, the backend cleans it again before sending.

### Limits and repeated reports

This part is about quotas and what happens when AbuseIPDB refuses a report.

- **Counters.** The AbuseIPDB tab shows how many reports you sent today (UTC) and the last quota that AbuseIPDB reported in its headers.
- **Refusals.** A used-up daily quota gives HTTP 429 with the reset time. The same IP within 15 minutes gives 409. A rejected key gives 401. Rejected data gives 422 with AbuseIPDB's text.
- **Assumed quota.** The Info limit table assumes 5 000 requests per day for each AbuseIPDB endpoint (the free-plan limit) until a header with the real value has been seen.

### What the model is told

The model receives the facts, the prepared e-mail source and the first 12 000 characters of `backend/prompts/abuseipdb-reporting-policy.md`. It is told that its assessment is advisory and that the hard checks are computed in code.

- **What the policy file covers.** The reporting rules (a summary), how to find the real IP in the Received chain (multi-hop providers), the category list, the report fields, the comment and a checklist before sending.
- **What the model answers.** A JSON with `qualifies`, `reasoning`, `suggested_categories`, `report_comment`, `alternatives` and `source_ip_check` (`agrees`, `suggested_ip`, `reasoning`), plus four checks (`received_verified`, `not_spoofed_source`, `category_matches`, `pii_redacted`) with pass, fail or unknown.
- **A different source IP.** If the model suggests another source IP, Seisa shows a warning and a button. The form is never changed automatically.

## Facts in code, the model only helps

This is the central rule of the project: anything that decides about security is computed by ordinary code, and the language model only explains or comments. The reason is simple. An e-mail is written by a possible attacker, and a model cannot reliably tell the data it analyses from instructions hidden in it (this is called prompt injection, number LLM01 in the OWASP list of risks for language-model applications). Code cannot be talked into a different answer, and it can be tested.

- **What code computes.** The sender IP and the Received chain, the SPF, DKIM and DMARC results, report eligibility (the hard checks) and the IP risk score.
- **What the model does.** It explains facts that were already computed (the lesson in the Email tab) and gives an independent second opinion. When it disagrees, Seisa shows a warning instead of replacing the fact.
- **Citation check.** A local check, with no model and no cost, flags IP addresses, quoted headers, SCL and BCL numbers, Message-IDs and hashes in the model's text that do not appear in the source.
- **Old analyses.** A saved analysis whose facts would be read differently by today's code shows a banner and both versions. The lesson itself is not changed.

How this is built is described in [ARCHITECTURE.md](ARCHITECTURE.md); what it protects against is in [PRIVACY.md](PRIVACY.md).

## Third-party services

Seisa uses outside services only with your own keys, under your own accounts and their terms. Seisa ships no keys. WHOIS, RDAP (rdap.org) and DNS need no key. For the binding terms of each service, see its own website (openrouter.ai, urlscan.io, www.virustotal.com, www.greynoise.io, otx.alienvault.com, radar.cloudflare.com and www.abuseipdb.com).

| Service | Key in `.env` | What Seisa assumes about the free plan |
|---|---|---|
| AbuseIPDB | `ABUSEIPDB_API_KEY` | 5 000 requests per day for each endpoint, if no header has been seen yet |
| VirusTotal | `VIRUSTOTAL_API_KEY` | Seisa itself throttles to 4 per minute and 500 per day |
| GreyNoise | `GREYNOISE_API_KEY` | 50 searches per week |
| AlienVault OTX | `OTX_API_KEY` | 10 000 per hour |
| Cloudflare Radar | `CLOUDFLARE_RADAR_API_KEY` | 1 200 per 5 minutes |
| URLScan | `URLSCAN_API_KEY` | Seisa asks the service for your quota ("Refresh limits" in Info) |
| OpenRouter | `OPENROUTER_API_KEY` | Seisa asks the service for your key status ("Refresh limits" in Info) |

Some notes on the table:

- **Assumptions.** The numbers are what Seisa assumes when the service does not report its limits. They were not checked against the services' current price lists and may be out of date.
- **Own counters.** The GreyNoise and OTX counts are Seisa's own and a lower bound, because requests made elsewhere are not seen.
- **URLScan visibility.** A URLScan scan is "Unlisted (default)" unless you choose otherwise; "Public" publishes it on urlscan.io.

## Personal data in e-mails

E-mails you analyse usually contain personal data, yours and other people's. This section says where Seisa keeps and sends that data. It is not legal advice.

- **Stored.** Seisa stores the raw e-mail of every Email-tab analysis in `data/analyses/` until you delete it.
- **Sent to the model.** With "Analyze", the whole header block of the e-mail goes to OpenRouter and the model provider (see [PRIVACY.md](PRIVACY.md)).
- **AbuseIPDB tab.** It does not save the e-mail. Only the report log is kept.
- **GDPR.** E-mails contain personal data of other people, and depending on where you live, rules such as the GDPR may apply to it. Sending an e-mail to OpenRouter is your decision. Seisa is a tool you run for yourself and gives no legal advice.
- **Asking for help.** The issue and pull request templates ask you not to paste keys, `.env`, raw e-mails or files from `data/` and `logs/`.

## Licences

This section lists the licences of Seisa and the things it contains.

- **Seisa.** GPL-3.0-or-later. The `LICENSE` file holds the plain GPL version 3 text without a preamble, so that GitHub recognises it.
- **Bundled code.** The only third-party code that ships with Seisa is `frontend/vendor/marked.min.js`: marked v15.0.12, MIT licence, copyright 2011-2025 Christopher Jeffrey.
- **Python dependencies.** The runtime dependencies are pinned in `requirements.lock`. CI allows only MIT, BSD, Apache, ISC, MPL-2.0 and PSF licences there, so a GPL package cannot get in by accident, and it runs `pip-audit` to look for known vulnerabilities.
- **Graphics.** The logo and icons (`frontend/logo.png`, `logo-mask.png`, `app-icon.png`, `favicon.ico`) are the author's own work under the project licence.
- **Development tools.** pytest, ruff, hypothesis, coverage, pip-audit, pip-licenses and markdown-it-py are not shipped and are not part of the program.
- **Contributions.** They are accepted under the project licence ("inbound equals outbound"), without a DCO or a CLA. [CONTRIBUTING.md](../CONTRIBUTING.md) has the details.

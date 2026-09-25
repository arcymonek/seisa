<p align="center"><img src="frontend/logo.png" alt="Seisa" width="120"></p>
<p align="center"><b>Seisa 2.0.55</b></p>

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

- **the visibility you choose** - `unlisted` by default (not on the urlscan.io front page or in public search, but visible to verified security researchers in urlscan Pro), or `private` (only your account) or `public` (anyone; the tab warns about it). **Earlier scans** first searches urlscan.io for earlier scans of the same domain (public ones plus those of your account; a hit is marked when it is the very same URL) so that a recent report can be opened instead of ordering a new scan,
- **the default user agent** (no `customagent`) and **automatic choice of the scan country** (no `country`) - both fields are deliberately left out of the request.

The result is laid out like the IP tab: a verdict banner (colour from the urlscan.io score and the engine and community verdicts; "no verdict" is shown neutrally and explicitly not as "safe"), summary tiles (score, HTTP status, server country, ASN, requests, certificate age with a "new" mark below 7 days, redirects), the page screenshot, a "Page identity" card (submitted and final URL, the redirect chain, title, domain, main IP with a **Check IP** button that only puts the address into the IP tab, location, PTR, server, MIME type, scan time and visibility) and collapsible detail cards - urlscan.io verdict (open only when it signals a risk), forms, TLS certificate, technologies, contacted IP addresses (each with **Check IP**), contacted domains and links - with the whole raw response under "Full API response". The screenshot is fetched by the backend from urlscan.io and served from your own origin, so neither the browser nor the Content-Security-Policy ever touch urlscan.io or the scanned page. Addresses found on the scanned page are shown defanged and are never clickable, also in the Markdown export ("Save .md", "Copy Markdown"). The **Forms** card reads the rendered DOM that urlscan.io keeps (structure only - nothing from the page is loaded): where each form posts, its method and fields; a password field that posts to another domain or over plain HTTP is the classic phishing kit and lifts a "low" or missing urlscan.io verdict to Medium (with a note). "Scan again" repeats the scan.

Every finished scan is saved in the History tab as a structured summary plus a small JPEG thumbnail of the screenshot (640 px wide, tens of KB); "Reopen" shows it again in this tab, and "Load full report" fetches the complete result from urlscan.io by its identifier.

### DMARC
Drag and drop aggregate DMARC reports (from Google, Microsoft etc.; plain `.xml` as well as `.gz` and `.zip` archives exactly as the providers send them) - the tool unpacks and parses them 100% in the browser (no files are sent anywhere) and shows everything the reports contain. A report loaded twice (the same provider and report ID) is skipped and marked in the file list. At the top: a verdict banner (red when a source fails both SPF and DKIM, amber when only one of them fails, green otherwise; report errors get their own banner) followed by hints on the latest published policy of each domain (`p=none` only monitors, a policy that can probably be tightened, `pct` below 100), summary tiles (messages, unique IPs, suspicious sources, share of messages that pass DMARC, and a bar of the policy decisions reject/quarantine/none) and, with more than one report, a table by provider (reports, messages, share passing DMARC). Each uploaded report is an expandable block with every field of its metadata and published policy: provider, contact and additional contact, report ID and version, period, domain, `p`/`sp`/`pct`/`fo`, alignment (`adkim`/`aspf`, with defaults marked), report errors and any other element the report carries (for example `np`, `testing` or vendor tags). Below, the sources aggregated by IP address, riskiest first, filterable (all / suspicious / passing), with SPF and DKIM pass/fail counts and the policy decisions (an override such as `forwarded` is noted there, so legitimate forwarding is not mistaken for an attack); a click on a row expands every single record - header/envelope from and to, the reason of a policy override (`policy_evaluated > reason`), the raw `auth_results` outcome (domain/selector/result/`human_result` for DKIM, domain/scope/result for SPF) and any extra fields - exactly what lets you diagnose *why* alignment failed, not just that it did. The optional "geo/ASN" button in the expanded row sends that single IP address to the external service [ipwho.is](https://ipwho.is) (from your browser, only on click) and shows the country and ASN; from there you can also jump straight to a full reputation check (IP tab) or to preparing an AbuseIPDB report. A short glossary of SPF, DKIM, the policy terms and the table closes the tab. "Save .md" and "Copy Markdown" export the whole analysis (summary, reports, sources and every record; values from the XML sit in code spans). Every import is saved in the History tab with its records, and "Reopen" restores the full analysis. The risk rating is unchanged: high = SPF and DKIM both failed, medium = one of them failed.

### Email
An educational analysis of the e-mail source: paste the whole source (headers + body) or load an `.eml` file (UTF-8 or windows-1252, the mbox envelope and line endings are normalised; binary base64 attachments do not go to the model - only their size and sha256 stay, while text base64 parts are decoded).

- **Deterministic analysis (immediately, locally, without an LLM)**: findings about anomalies, the Received route with the role in the chain of trust, authentication (SPF/DKIM/DMARC/ARC, authserv-id, signed and unsigned headers, `bh=` length), domain alignment relative to `From`, a UTC timeline, epoch conversions, the MIME tree, attachments (sha256, double extensions), links (text vs `href`), hidden content, HTML comments, template placeholders, the recipient's anti-spam filters (SCL/BCL/CAT, the Junk target folder, AuthAs, the decoded X-Message-Delivery) and flags set by the sender (X-Message-Flag, Importance, read-receipt requests). When the whole Received chain belongs to one operator (e.g. Microsoft), the table marks the oldest entry as the trust boundary. Identical findings caused by repeated links are reported once with a count, e.g. `(x4)`. The logic is in `backend/email_forensics.py`; nothing from the message is opened or downloaded.
- **Layout of the result** (like the IP, DMARC and URLScan tabs): a verdict banner on top (verdict, confidence, the summary of the analysis, the citation check status and the actions: report, save/copy, finish a truncated analysis), a row of tiles (warnings, SPF/DKIM/DMARC as written by the recipient's server, sender identity alignment, the IP at the trust boundary with a button that puts it into the IP tab, links/attachments/hidden content, the recipient's filter, delivery time), then three panes with a table of contents on the left: **Overview** (the route of the message as a diagram with the trust boundary, the warnings, the checklist and the "what to do" part of the analysis, the citation check), **Facts** (the deterministic analysis as collapsible cards; a card opens by itself only when it carries a signal, and shows a one-line state in its header) and **Lesson** (the whole LLM analysis, below). The source collapses to a one-line bar after the analysis ("Edit source" brings the field back). The tab remembers the chosen pane.
- Below: a **detailed LLM analysis** (OpenRouter, the same key and model as in AbuseIPDB), streamed live, following the guide `docs/email-analysis-guide.md` (mental model, a line-by-line analysis of both the good and the bad elements, a checklist, traps, an assessment, control questions with answers in collapsible sections). The first line of the answer is the verdict with a confidence level. The text is split at its `##` headings into collapsible cards (all cards start collapsed; the state you choose is remembered; "Expand all" / "Collapse all"; the sub-blocks of the line-by-line part are collapsible too); if the model breaks the structure, the text is shown as one block. Quotes from the message become **evidence cards** with the line numbers and a "Show in source" button that opens the **source drawer** (the message with line numbers, the quoted lines highlighted, several hits can be stepped through); a quote that is not literally in the source is marked as a diagram or example. Inline code found in the source is clickable in the same way. Technical terms (SPF, DKIM, DMARC, ARC, PTR, SCL, HELO...) get a dotted underline and a short explanation on hover, once in the whole analysis. The lesson can be searched (hits open the collapsed cards).
- The response limit of the model is 64000 tokens (counted together with the hidden reasoning of the model, about 45% of the output; it is a ceiling, you pay for the tokens actually generated). If the analysis is cut off anyway, the tab shows a warning and a **"Finish the analysis"** button (the model receives the text so far and writes the missing parts; token usage and cost add up in the saved analysis).
- **"Save .md"**, **"Copy Markdown"** and **"Save .html"** (the export labels follow the interface language at the moment of export, the text of the LLM analysis stays in the language it was written in) export the whole set: metadata (date, verdict, model, input/output tokens, cost), the whole deterministic analysis (tables), the LLM analysis and the follow-up questions; the HTML file is a self-contained copy of the result with all cards expanded (no scripts, a Content-Security-Policy forbids everything but inline styles).
- **Duplicate detection:** before a paid analysis Seisa checks the fingerprint (sha256 of the normalised source) in `data/analyses/`. If the message was already analysed, it offers to open the saved analysis (with the date, verdict and cost) or to run it again deliberately.
- **Citation check (local, free):** after the analysis the code checks whether the IP addresses, the header lines quoted in code blocks, `Header: value` quotes, SCL/BCL numbers and identifiers given by the model appear in the source or in the deterministic analysis (`backend/citation_check.py`). The banner shows the result ("quotes verified" or a warning that jumps to the details in the Overview pane); discrepancies are also in the `.md` export. This is information, not proof of an error (an example or a paraphrase may be flagged too). It does not check domains or entries such as `spf=pass`, because the analysis also discusses examples of a legitimate message.
- The LLM analysis does not reproduce the tables visible in the deterministic analysis (timeline, links, Received etc.), it only interprets them, so that you do not pay for repetition; the complete set is in the export.
- The LLM output is rendered safely: raw HTML from the e-mail and links are neutralised (links are shown as non-clickable, defanged text).
- Next to every link of the deterministic analysis (links, plain URLs, List-Unsubscribe) there is a **URLScan** button, and next to public IP addresses an **IP** button; they only put the address into the URLScan / IP tab - nothing is opened, scanned or looked up until you click the action there. Rows of the Received and authentication tables have a "source" button that highlights the header in the source drawer.
- **Analysis language:** the analysis is written in the interface language (a directive in the prompt plus a table of literal headings and tags `[Fakt]`/`[Fact]` for both languages in `docs/email-analysis-guide.md`); the language is stored in the record (`lang`; older records = Polish). "Finish the analysis" uses the language of the stored record, not the current interface language. A saved analysis in a language other than the interface is marked with a PL/EN badge, and opening it shows a banner with a paid re-analysis button (the cost of the previous one is given as a guide); the facts and the text stay in the language they were created in, while the labels and the .md export use the interface language. Duplicate detection (sha256 of the source) does not depend on the language: the banner shows the language of the existing analysis.
- **Verdict protocol:** the first line of the model answer has the form `VERDICT: <legit|phishing|spam|scam|malware|inconclusive> | CONFIDENCE: <high|medium|low>` and always uses these canonical codes, whatever the language of the analysis (`backend/verdict.py`); the interface maps them to labels in the selected language. Analyses saved earlier with Polish tokens (`WERDYKT`/`PEWNOSC`) are read without any file migration.
- The **"Report to AbuseIPDB"** button (visible only when the verdict is not `legit`, i.e. legitimate) pastes the original source into the e-mail field of the AbuseIPDB tab (overwriting the field) and takes the user there.
- **Ask about this message** (a card at the end of the Lesson pane): a follow-up question about a saved analysis, optionally with a fragment of the source (select text in the source drawer and click "Ask about the selection"; the "Show source" button next to "Ask" opens the drawer). Every question is an explicit, paid click that sends the whole source, the question and the fragment to OpenRouter; the answer is streamed, rendered safely and saved together with the analysis (`questions` in the record; endpoint `POST /api/email/analyses/{id}/ask`, question up to 600 and fragment up to 2000 characters). The questions are part of the exports.
- **Comparison:** tick two saved analyses and click "Compare selected" to see their facts side by side (verdict, SPF/DKIM/DMARC, sender IP, domains, IPs, hosts of links, attachment hashes) with the shared items highlighted - a local operation, nothing is sent.
- Every completed analysis is saved together with the raw e-mail in `data/analyses/` (files 0600, gitignored); the list of saved analyses (open/delete/compare) is at the bottom of the tab.

### AbuseIPDB (reporting)
A workflow compliant with the [AbuseIPDB reporting policy](docs/abuseipdb-reporting-policy.md) (60-day limit, no reporting based on the confidence score alone, the 1024-character comment limit etc.):

1. **Paste the raw source of the suspicious e-mail** (headers + body) - optional, you can also start from the IP alone (the "Report to AbuseIPDB" button in the IP/DMARC tab, or "Use as draft" on an earlier report).
2. The backend extracts the facts deterministically: the trusted source IP address (the algorithm goes from the newest `Received` header downwards and looks for the first hop whose "from" host no longer belongs to the same domain as the "by" host of the newest hop - in multi-hop chains of large providers, e.g. Microsoft 365/Outlook.com, the first few hops are internal transfers of the same provider and are skipped, so that their address is not taken instead of the real sender), together with a confidence level (`ip_confidence`) and the full chain of hops. In addition: the SPF/DKIM/DMARC result, attachments (with detection of double extensions such as `invoice.pdf.exe`), the Message-ID, BTC address/ransom demand patterns. **The hard checks (age of the attack, whether the IP is private) are always computed in Python and are never delegated to the LLM.**
3. Optionally (if `.env` has `OPENROUTER_API_KEY`) an LLM through **OpenRouter** assesses whether the e-mail qualifies for a report, independently verifies the IP address chosen by the code on the basis of the raw headers (`source_ip_check` - if it disagrees, the address card shows a warning with the model's suggestion and a button to use it), assesses the fit of the suggested categories and possible PII in the comment - and **writes a ready, detailed report comment in English**, based on the facts and the complete raw source of the message (all headers and the whole body, up to the source size limit; the address card states how many characters the model saw) - see point 6. Without a key the tool works in rule-based mode.
4. **The result is laid out like the IP, DMARC and URLScan tabs.** A verdict banner (green = eligible, red = not eligible and sending blocked, blue = not assessed; the text is always white) with the reasoning and alternatives, then summary tiles (source IP with its confidence, age of the e-mail against the 60-day limit, SPF/DKIM/DMARC, attachments, and the AbuseIPDB score of the address once `/check` answers) and the **address card**: the `Received` chain with the boundary hop marked and, on every hop with a public address, a "Use this address" button (also for the address the model suggests instead). An address you have already reported is marked. Only the boundary hop is the real sender - the other hops are usually the recipient's or the provider's own servers (the tooltip says so) - so after a report the tab offers the remaining non-relay addresses of the same e-mail one by one. Attachments sit in a collapsible card that opens by itself when a double extension is found. Without an LLM the tool never claims that an e-mail qualifies: it only checks the hard criteria (public IP, age) and recognises the obvious case of a test sent from your own account to yourself (sender = envelope sender = recipient, no sign of an attack).
5. **The report card** holds the IP, the categories, the attack timestamp and the comment. The category chips carry a short description on hover, and notes appear under them where a choice is usually wrong or incomplete (`20 Exploited Host`, `22 SSH` and `13 VPN IP` alone; `23 IoT Targeted` without a device type in the comment; `17 Spoofing` when SPF/DMARC passed). The timestamp is taken from the `Date` header and shown in the browser's local time; it is sent in UTC (ISO 8601). The comment field has a character counter (limit 1024) and a **personal-data scan**: your own addresses (recipients of the message and their domains, except freemail domains), any other e-mail address and internal IP addresses are listed, and "Mask them" replaces them with placeholders (AbuseIPDB shows comments publicly and, per its documentation, is not responsible for PII you reveal); sending with findings left asks for confirmation. The "What will be sent to the API" block shows the exact request the backend will make (categories without duplicates, the comment after cleaning: ASCII only, at most 1024 characters, formula prefixes neutralised).
6. **The comment is filled with what the LLM wrote** - `comment` is an optional field in the AbuseIPDB API ([`/report`](https://docs.abuseipdb.com/#report-endpoint), only `ip` and `categories` are required), but the AbuseIPDB policy itself expects a detailed, technically justified description - hence the LLM writes the comment (attack mechanism, meaning of SPF/DKIM/DMARC, malicious attachments with a detected double extension such as `invoice.pdf.exe`, a ransom/BTC demand, mass-mailing patterns), within about 900 characters. Without an LLM (or when the analysis fails) a poorer, deterministic fallback built solely from the facts is used (with only the local part of the `Message-ID`, because the domain after `@` is usually your own). In both cases the text is fully editable before sending. If you know the port number, add it by hand.
7. **Checks before sending** is a collapsible card (open by itself when something blocks) with a state on its header. *Required* (age of the attack, public IP, category selected, the 15-minute rule, the eligibility verdict) and the two *blocking* items judged by the LLM (`Received` verified, the source is not spoofed - only a "fail" blocks) gate the "Send" button; a date up to one hour in the future counts as "now" to tolerate a clock offset, a further future date fails. The *informational* items (Spoofing, category fit, the local PII scan, the model's PII opinion) are a hint to read before sending. Spoofing is one of three states, always with a short reason: detected (SPF/DMARC fail), not detected (authentication passed) or cannot be assessed (no or ambiguous SPF/DKIM/DMARC results in the pasted source). The backend recomputes the hard checks on every change and again when sending, independently of the state of the form.
8. **What AbuseIPDB already knows** appears under the IP field (reports, distinct reporters, confidence score and last report in 90 days; one `/check` query per address, only with an API key). It warns when the address is whitelisted and when it already has reports in one of your chosen categories from the last 7 days (a new one probably only adds noise - the policy also forbids reporting on the score alone). Your own earlier reports of the address come from `data/report_log.json`.
9. **The API contract** ([docs.abuseipdb.com](https://docs.abuseipdb.com/#report-endpoint)): a form-encoded `POST /report` with the `Key` header and `ip`, `categories` (comma-separated, at most 30, no duplicates), `comment` (at most 1024 characters) and `timestamp` (ISO 8601). AbuseIPDB accepts a repeated report of the same IP from one account only after 15 minutes, so within that time the "Send" button is disabled and the backend refuses the request (HTTP 409) instead of spending a call. The API's own answers are turned into readable errors: 429 with no requests left = the daily limit is used up (with the limit and the time it resets, from `X-RateLimit-Limit` and `X-RateLimit-Reset`), 429 otherwise = the same-IP rule (report sent from elsewhere), 422 = the refused field with the API's own detail, 401/403 = the API key, anything else = an API error. After a success the tab shows the confidence score the API returns and the daily limit left (`X-RateLimit-Remaining`); every attempt, failed ones included, goes to the local log with the last known limit.
10. **Your reports** (a card at the bottom): sent today (UTC), the daily limit left, the number of accepted reports and a table of every attempt with its result; "Use as draft" loads an earlier report into the form. Accepted reports are also listed in the History tab (they open as a draft and cannot be deleted from there - the log is an audit trail). "Save .md" exports the prepared report (address, categories, timestamp, verdict, the address chain, the checks and the comment) for your own archive. You can also copy the comment for manual pasting on the website.

Further details of this tab:

- The "Load .eml file" button (also dragging a file onto the field), a timer of the analysis and the tokens and cost after the "Analyze" analysis, shown next to the buttons.
- Detection of the sender IP: when the first hop outside the recipient's domain is only a relay of an operator (e.g. Microsoft Exchange Online), the parser walks through the operator's internal hops to the hop where the address of the connecting sender was recorded. If the message originated inside a shared provider (e.g. a hotmail account) and there is no public sender IP, the IP stays empty (confidence low). Authentication results are also read from `X-MS-Exchange-Authentication-Results` and `ARC-Authentication-Results`. After an analysis with an LLM the tab shows how much of the content the model saw (the first 2000 characters), and the hard checks (IP, age) take precedence over the opinion of the model.

### History
Everything Seisa remembers: IP lookups, URL scans (reopened in the URLScan tab, with a thumbnail of the screenshot), DMARC imports, saved e-mail analyses (reopened in the Email tab) and accepted AbuseIPDB reports (reopened as a draft in the AbuseIPDB tab). At the top, summary tiles - the total and one per type, plus the number of high-risk entries - which also work as filters (a click filters the list, a second click on "High risk" removes the filter); below them chips for the date range and the risk, and a search box over the labels. The list shows the newest 25 entries that are not pinned. Entries are cards grouped by day (pinned ones first): type, label, risk, the language of the entry when it differs from the interface, and how long ago it was made (the exact time is in the tooltip). When the same IP, URL or domain was rated differently earlier, the card says so ("Earlier: Low"). Each card has "Reopen" (an IP check unfolds inside the card, the others open in their own tab), "Repeat" (IP and URL scan: runs the check again in its tab, for the IP with the cache skipped), "Pin" / "Unpin" (IP, URL scan and DMARC: a pinned entry never falls out of the size limit and survives "Clear history") and "Delete" (two clicks; not for reports - the local report log is an audit trail). Tick two IP checks and "Compare the selected" shows what changed between them: risk level and score, the sources used, the address identity and what every source reported. "Export JSON" and "Export CSV" save the metadata of the list as filtered on screen (id, type, time, label, risk, pinned). "Clear history" (two clicks) removes only unpinned IP checks, URL scans and DMARC reports; e-mail analyses (with the raw messages) are deleted one by one; the report log stays.

### Logs
Errors and warnings (WARNING level and above) from every service - normal, error-free operation of the tool leaves no trace on disk. At the top: summary tiles (errors, warnings, the service with the most entries, the last entry) or, when there is nothing to show, a green banner. Below: filter chips for the date range (today / 3 days / week / month / all; the default is all), the level (all / errors / warnings) and the service (built from the entries, each with a count), and a search box over the messages; the tiles and chip counts always describe the whole date range, the level, service and search only narrow the list. Every entry is a collapsible card (time, level, service and the first line of the message; the full text, for example a whole API error, opens on a click and can be copied); the cards you opened stay open across refreshes. "Refresh every 10 s" reloads the list on its own while the tab is open, and "Clear logs" (two clicks, the second one confirms) deletes all log files. Up to the newest 500 entries are shown (a banner says so when older ones are cut off). All OpenRouter API errors (Email and AbuseIPDB tabs: limits, insufficient credits, provider errors, timeouts) go to a single `open_router` service; the other application errors go to `app`.

### Info
The round info button (ⓘ) at the far right of the tab row opens the Info tab: a short description of Seisa, summary tiles (the current version read from the page header, how many services have an API key set, the LLM model or "off", today's VirusTotal requests against the daily limit), and collapsible cards in this order: the status of every integration (collapsed; only whether a key is set - the keys are never shown or sent to the browser), the author's contact details (e-mail, GitHub, website), the meaning of the name (精査, *せいさ*), the recent releases from the git log of the directory Seisa runs from (collapsed; the card says so when it is not a git checkout) and the license (collapsed; the same summary as in the License section below).

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
│   ├── report_utils.py       # text sanitisation, IP checks, personal-data scan and masking
│   ├── urlscan_report.py     # structured summary + Markdown report of a urlscan.io scan result
│   ├── urlscan_input.py      # cleaning and validation of the URL to scan (refang, scheme, private hosts)
│   ├── urlscan_forms.py      # forms of a scanned page (from its DOM): action, method, fields, password/external flags
│   ├── routers/               # /api/* endpoints
│   └── services/               # a client for every service (common IntelService interface; urlscan.py separately - submit+poll, not an IntelService)
├── frontend/
│   ├── index.html
│   ├── favicon.ico            # icon: the kanji 査 (16/32/48/64 px)
│   ├── logo.png               # round logo (page header and README)
│   ├── css/style.css          # dark theme
│   ├── i18n/                  # interface text catalogs: pl.json, en.json
│   ├── js/                    # modules: app, i18n, util (shared helpers), lookup (+ lookup-result: the report view), urlscan (+ urlscan-result: the report view), dmarc, archive (unpacking .gz/.zip), email (+ email-facts, email-lesson, email-source, email-glossary, email-ask, email-compare, email-export: the deterministic facts, the lesson cards, the source drawer, glossary tooltips, follow-up questions, comparison and exports), report-builder (+ report-result, report-history, report-export: the analysis view, the log of sent reports and the Markdown export), history (+ history-compare: comparison of two IP checks), logs, about
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

There is no database - all persistence is plain JSON files in `data/` (history limited to 25 unpinned entries, the VirusTotal daily limit counter) and logs in `logs/`. Saved e-mail analyses live in `data/analyses/`. Releases before 2.0.27 used `data/analizy/` and `logi/`; Seisa does not migrate them, so rename them by hand before the first start of a newer release (`mv data/analizy data/analyses`, and move the `*.jsonl` files from `logi/` to `logs/`).

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
- A report to AbuseIPDB always requires a deliberate click on "Send"; the backend validates the hard checks (age, IP, category) anew regardless of the state of the form in the browser - they, not the informational checklist, decide whether sending is possible. The comment is only sanitised and shortened, not judged; the personal-data scan is a warning that asks for confirmation, it does not block.
- The Email tab sends the whole source of the message (with personal data) to OpenRouter after a click on "Analyze" (and, for every follow-up question of the Email tab, after a click on "Ask"); this is a deliberate decision (mostly suspicious messages are analysed).
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

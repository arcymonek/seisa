**English** | [Polski](pl/USER_GUIDE.md)

# User guide

This guide is for people who use Seisa, not for programmers. In one sentence: it explains what every tab does, what it needs, how to use it step by step, and how to read what it shows you.

## Contents

- [1. Before you start](#1-before-you-start)
- [2. The screen at a glance](#2-the-screen-at-a-glance)
  - [Tooltips and the Explanations section](#tooltips-and-the-explanations-section)
  - [What is sent where, and when](#what-is-sent-where-and-when)
- [3. Which tab do I need?](#3-which-tab-do-i-need)
- [4. API keys: what works without them](#4-api-keys-what-works-without-them)
- [5. IP tab](#5-ip-tab)
- [6. URLScan tab](#6-urlscan-tab)
- [7. DMARC tab](#7-dmarc-tab)
- [10. History tab](#10-history-tab)
- [11. Logs tab](#11-logs-tab)
- [12. Info tab](#12-info-tab)
- [13. Language and colour themes](#13-language-and-colour-themes)

## 1. Before you start

Seisa is a tool that runs on your own computer and opens in your web browser. It helps you judge whether an IP address, a web link, a mail-security report or a suspicious e-mail is dangerous, and it helps you report abusive senders to AbuseIPDB (a public database of abusive addresses).

- It opens at `http://127.0.0.1:54321`. That address means "this computer only", so nobody else can reach it and it needs no login.
- It has eight tabs: IP, URLScan, DMARC, Email, AbuseIPDB, History, Logs and Info (the Info tab is the slider icon on the right of the tab bar).
- Every tab starts empty and sends nothing until you click its action button (Check, Scan, Analyze and so on).
- Your browser talks only to Seisa. Seisa's own server contacts the outside services for you.
- Seisa never opens links, images or attachments from an e-mail or a scanned page. Addresses in results are shown as text that cannot be clicked.

What Seisa does not do: it does not decide for you. The facts that matter for security (the sender's IP address, the order of the mail servers, the SPF/DKIM/DMARC results, the report checks, the IP score) are worked out by Seisa's own program code. A language model (LLM, the AI service you can switch on with an OpenRouter key) only explains them and double-checks them. An AbuseIPDB report is always your responsibility, and the tab tells you so before sending. The reasons are in [COMPLIANCE.md](COMPLIANCE.md).

You need a running Seisa to follow this guide. How to install, start and update it is in OPERATIONS.md. For the full list of what leaves your computer, see [PRIVACY.md](PRIVACY.md).

## 2. The screen at a glance

All tabs look alike, so once you know one, you know them all. At the top you see the name and a short description. Below it is the tab bar, then the tab itself. The footer shows the version and the "Shut down Seisa" button.

Inside a tab, the same pattern repeats:

- **Input and action row.** A field, the action buttons (Check, Scan, Analyze...) and, next to them, how long the last action took with one decimal place (for example "Checked: 8.6 s"). After an LLM run the same row also shows the tokens used and the cost.
- **"Clear" button.** It appears only when there is something to clear (typed text or a result) and returns the tab to its starting state.
- **Verdict banner.** A coloured bar with the overall level: High, Medium or Low, or an e-mail verdict.
- **Tiles.** A row of small summary boxes under the banner.
- **Foldable cards.** The details. Every card starts folded. Seisa remembers which cards you opened or closed until you close the page (nothing is written to disk). Cards with many sections have "Expand all" and "Collapse all".
- **Explanations.** The last section of each result, described below.

Moving data between tabs is done with buttons such as "Report to AbuseIPDB", "Check in the IP tab" or "Scan in URLScan". They only fill in the other tab's field. They do not start anything, so you stay in control. The one exception is "Repeat" in History (see the History tab).

Results can be saved as a Markdown file ("Save .md") or copied ("Copy Markdown"). In these exports, web addresses and IP addresses are made harmless (for example `hxxp://evil[.]example`) and are never turned into live links or images.

If you switch the language or shut Seisa down while an analysis is running or text is typed in, Seisa asks first, because the page reloads and that work would be lost.

### Tooltips and the Explanations section

Technical terms with a dotted underline show a short explanation when you point at them with the mouse or reach them with the keyboard (Tab key). In the Email tab the first use of terms such as SPF, DKIM, DMARC or Received in the AI lesson gets such a tooltip too.

Each result also ends with an "Explanations" section. It describes the result in plain language, one simple sentence first, and has a "Details" link for more.

### What is sent where, and when

Nothing leaves your computer until you click a button that does it. The short version:

| You click | It contacts |
|---|---|
| "Check" in the IP tab | The services you left selected under "Services" (VirusTotal, AlienVault OTX, Cloudflare Radar, AbuseIPDB, GreyNoise, WHOIS / rDNS and DNS) |
| "Scan" or "History" in the URLScan tab | urlscan.io |
| "geo (RDAP)" in the DMARC tab | A public registration database (RDAP) and DNS |
| "Analyze" in the Email tab | OpenRouter (the AI service), only if a key is set |
| "Analyze" in the AbuseIPDB tab | OpenRouter, only if a key is set |
| "Send via AbuseIPDB API" | AbuseIPDB |
| "Refresh limits" in the Info tab | VirusTotal, urlscan.io and OpenRouter |

The tabs History, Logs and the rest of Info only read from Seisa's own files, and loading a DMARC file only happens in your browser.

There is one exception to "nothing without a click": the AbuseIPDB tab looks the address up in AbuseIPDB by itself as soon as an IP address appears in its form, and only if an AbuseIPDB key is set. The details and the complete table are in [PRIVACY.md](PRIVACY.md).

## 3. Which tab do I need?

Start from what you have in your hand:

| I have... | Use the tab | What you get |
|---|---|---|
| An IP address or a domain I do not trust | IP | One risk score from several independent sources |
| A suspicious web link | URLScan | A safe preview and a report of the page, without opening it yourself |
| A DMARC report (an .xml, .gz or .zip file from a mail provider) | DMARC | Which servers send mail as your domain and whether they pass the checks |
| A suspicious e-mail I want to understand | Email | The facts and a step-by-step lesson on how to read the message |
| A spam or phishing e-mail I want to report | AbuseIPDB | A checked, ready-to-send report |
| Something I did earlier | History | Your recent checks, scans, imports and reports in one list |
| A message that something failed | Logs | The errors and warnings Seisa recorded |
| A question about keys, limits or settings | Info | Version, key status, limits, language, theme |

## 4. API keys: what works without them

An API key is a long code from a service, like a membership card: it tells the service who is asking, so it can count your requests. You put your keys in the `.env` file. The table of all keys and how to get them is in the README. This table only says what happens when a key is missing.

| Tab or function | Key it needs | Without the key |
|---|---|---|
| IP tab | One key per source: `VIRUSTOTAL_API_KEY`, `OTX_API_KEY`, `CLOUDFLARE_RADAR_API_KEY`, `ABUSEIPDB_API_KEY`, `GREYNOISE_API_KEY`. WHOIS / rDNS needs none | The source shows "no API key" and is left out of the score. The check still works with the rest |
| URLScan tab | `URLSCAN_API_KEY` | "Scan" and "History" answer "no API key (URLSCAN_API_KEY)" |
| DMARC tab | None | Works fully. Only the optional "geo (RDAP)" button asks Seisa's server, which uses free public sources |
| Email tab | `OPENROUTER_API_KEY`, only for the AI lesson | "Analyze" shows the local analysis and a note that the key is missing. That analysis is not saved |
| AbuseIPDB tab | `OPENROUTER_API_KEY` for the AI assessment; `ABUSEIPDB_API_KEY` for the address history and for sending | You can still prepare a report from the facts and a comment built from them. Sending and the address history need the AbuseIPDB key |
| History, Logs | None | Work fully |
| Info tab | None | Shows only whether each key is "set" or "missing". The keys themselves are never shown |

## 5. IP tab

### What it is for

The IP tab checks the reputation of one IP address or one domain in several independent sources at once, and combines the answers into a single risk score from 0 to 100. An IP address is the number that identifies a computer on the internet (for example `203.0.113.7`). A domain is the name of a website (for example `example.org`).

- For an IP address it asks VirusTotal, AlienVault OTX, Cloudflare Radar, AbuseIPDB, GreyNoise and WHOIS / rDNS.
- For a domain it asks VirusTotal, AlienVault OTX, Cloudflare Radar, WHOIS / DNS and Seisa's own local heuristics. AbuseIPDB and GreyNoise do not support domains, so they show "not applicable".

### What you need

No key is required: WHOIS / rDNS works without one. Every other source needs its own key and is shown as "no API key" and left out of the score when the key is missing. See section 4.

### How to use it

1. Type or paste an IP address or a domain into "IP address or domain". You can paste messy forms too: a whole link, a port, `user@host`, brackets, upper case, or text made harmless such as `hxxps://evil[.]example` or `1[.]2[.]3[.]4`. Seisa cleans them up.
2. Under "Services", click a source to switch it off or on. All are on by default.
3. Click "Check" (or press Enter in the field).
4. Read the result (below). Click "Clear" to start over.

Seisa refuses private, loopback, reserved and documentation addresses (such as `192.168.x.x`) before anything is sent, because no service knows anything about them. If you switch every source off, Check only shows "Select at least one service." and sends nothing.

### What is sent and when

Only when you click "Check" (or "Repeat" in History, or an IP button in another tab that opens this one and runs it). The address or domain goes to the sources you left selected. Seisa keeps no cache, so every Check asks again and uses the services' quotas each time. VirusTotal is limited by Seisa to 4 requests per minute (extra requests wait) and 500 per day, counted to 00:00 UTC. Over the daily limit, its card says "limit exceeded". The full table is in [PRIVACY.md](PRIVACY.md).

### Reading the result

The result opens with a verdict banner, for example "HIGH - 89.7/100", and "Based on N of M sources". Under it you see the tiles and these cards:

| Part | What it tells you |
|---|---|
| Tiles | Quick facts such as "Abuse confidence", "VirusTotal detections", "OTX pulses", "Country" and "IP type". For a domain: "Domain age", "Registrar", "Expires in", "Popularity (Cloudflare)", "Category", "Name servers" and "IP addresses" |
| Component scores | The risk each source gave (0-100) and its "Credibility", the weight Seisa gives it |
| Address identity (or Domain identity) | Network number (ASN), owner, country, network, reverse DNS name, abuse contact and usage type, merged from all sources. A mark shows whether sources agree (✓ n/n), mostly agree (≈) or conflict. For a domain it also shows MX, SPF, DMARC and CAA records |
| Sources | One card per source, each with "Full API response" holding the service's raw answer |

How the score is decided:

- The levels are Low below 25, Medium from 25 and High from 60.
- The sources are combined so that one strong signal is not averaged away, and a source with no data does not vote. No information is not proof of innocence.
- Sources have different weights ("Credibility"): AbuseIPDB 0.9, VirusTotal 0.8, GreyNoise 0.7, AlienVault OTX 0.5, local heuristics 0.4.
- Cloudflare Radar and WHOIS / rDNS give context (network, owner, location), not a verdict, so they are listed under "Excluded from the score".
- An address known to be good (on the AbuseIPDB whitelist, GreyNoise benign/RIOT or confirmed by OTX) has its score capped at 15, unless another source reports a strong contrary signal (65 or more).
- If a source fails, the check goes on. Its card shows "error" with the service's message (in English), and the error is written to the Logs tab.
- If you checked the same address before, the report shows the previous score, what changed (sources that moved by 10 points or more) and a trend of up to 10 earlier checks. Nothing is asked again for this comparison.

Every check is saved in History automatically, without the raw service answers.

### Buttons

| Button | What it does |
|---|---|
| Check | Runs the check |
| Clear | Empties the field and the result and switches all sources back on |
| Save .md / Copy Markdown | Saves or copies the report as Markdown |
| Report to AbuseIPDB | For an IP address: opens the AbuseIPDB tab with the address filled in (nothing is sent) |
| Scan in URLScan | For a domain: opens the URLScan tab with `https://<domain>/` filled in (nothing is sent) |

## 6. URLScan tab

### What it is for

The URLScan tab asks the service urlscan.io to open a suspicious link in its own browser and to report what it finds, so you never open the link yourself. You get a screenshot, the page's details and a verdict.

### What you need

A `URLSCAN_API_KEY`. Without it, "Scan" and "History" answer "no API key (URLSCAN_API_KEY)".

### How to use it

1. Paste the link into "URL to scan". Only `http://` and `https://` addresses of public sites are accepted, up to 2048 characters. To scan several, separate up to 5 addresses with a space or a new line.
2. Choose "Scan visibility" (see below).
3. Optional: open "Advanced options (scan country, user agent)".
4. Click "Scan". Seisa submits the scan, waits 12 seconds, then checks every 5 seconds. After 2 minutes it stops waiting and says to check manually (the scan goes on at urlscan.io). "Cancel" stops the waiting, not the scan.
5. Read the result (below).

Scan visibility has three choices:

| Choice | Who can see the scan |
|---|---|
| Unlisted (default) | Hidden from urlscan.io's front page and public search, but visible to verified security researchers |
| Private | Only your urlscan.io account; counts against a separate quota |
| Public | Anyone, together with the address |

If the link contains parts that often carry secrets (such as `token=`, `password=`, `email=` or `user:pass@`), Seisa warns you not to use Public.

"Advanced options" set the scan country (automatic or one of 12) and the user agent, which is the browser identity the page sees (default, Chrome on Windows, Chrome on Android, Safari on iPhone, or your own text of up to 250 characters). Your choices are remembered in this browser for next time.

When you paste several addresses, Seisa submits them one second apart and shows a progress list.

### What is sent and when

When you click "Scan", the address, the visibility and your options go to urlscan.io, and urlscan.io opens the page from its own servers. Your browser and Seisa never visit the page. Seisa then asks urlscan.io for the result, the page's form data and the screenshot. "History" sends the address's host name to urlscan.io to search. The full table is in [PRIVACY.md](PRIVACY.md).

### Reading the result

The banner uses urlscan.io's score (scale -100 to 100). A password form that sends data to another domain or over plain HTTP raises the level even when urlscan.io has no verdict. The result then shows:

| Part | What it tells you |
|---|---|
| Tiles | "urlscan score", "HTTP status", "Server country", ASN, "Requests", "Certificate age" and "Redirects" |
| Screenshot | Fetched by Seisa's server and shown in the page; click it to enlarge. Your browser did not visit the scanned page |
| Page identity | Submitted and final URL, redirect chain, page title, domain, main IP, server and more |
| Details | "urlscan.io verdict", "Forms", "TLS certificate", "Technologies", "Contacted IP addresses", "Contacted domains", "Links on the page" and "Full API response" |

Every finished scan is saved in History with a small thumbnail of the screenshot.

### Buttons

| Button | What it does |
|---|---|
| Scan | Submits the scan |
| Cancel | Stops waiting (the scan itself goes on at urlscan.io) |
| Clear | Empties the field and the result |
| History | Lists earlier scans of the same domain at urlscan.io (public scans by anyone plus your own, newest first, up to 10), so you can open a recent one instead of ordering a new scan. It works for one address at a time. Not the same as the History tab |
| Compare | Compares the result with the previous scan of the same domain saved in Seisa's History. Nothing is scanned again |
| Open in urlscan.io | Opens the report page at urlscan.io in a new browser tab (your browser contacts urlscan.io, not the scanned site) |
| Save .md / Copy Markdown | Saves or copies the report as Markdown |
| Check IP | Next to an address in the result: fills the IP tab with it (nothing is sent) |

## 7. DMARC tab

### What it is for

The DMARC tab reads the reports that mail providers send to the owner of a domain and shows which servers send mail as your domain, and whether those messages pass the checks. DMARC is a rule a domain owner publishes that tells receivers what to do with mail that fails two checks: SPF (a list of servers allowed to send mail for the domain) and DKIM (a digital signature on each message). These reports are called aggregate reports.

### What you need

No key. The report is read in your browser. Only the optional "geo (RDAP)" button asks Seisa's server.

### How to use it

1. Click the drop area ("Click to choose files") or drag files onto it ("or drag them here"). `.xml`, `.gz` and `.zip` files are accepted, several at once.
2. Wait a moment. The files are unpacked and read entirely in your browser; nothing is uploaded. One unpacked report may be at most 100 MB (a protection against "zip bombs").
3. Read the result (below). A report loaded twice (same provider and report ID) is skipped and listed as skipped.
4. Click a source's IP address to open its details.

### What is sent and when

Loading and reading the files sends nothing. Only "geo (RDAP)" on one row contacts anything, and only when you click it. See [PRIVACY.md](PRIVACY.md).

### Reading the result

The result shows a banner (for example "All sources pass both SPF and DKIM."), tiles ("Messages", "Unique IPs", "Suspicious", "DMARC pass", "Policy decisions"), the list of "IP sources" with the filters "All", "Suspicious" and "Passing", and the "Uploaded reports".

How the risk of a source is decided:

| Risk | When |
|---|---|
| High | At least one message failed DMARC (neither SPF nor DKIM lined up with your domain) |
| Medium | None failed DMARC, but some failed SPF or DKIM |
| Low | Everything passed |

This measures authentication, not whether the sender is malicious. The table counts SPF and DKIM after the alignment check (does the checked domain match your domain?), so a source can look unaligned although the raw SPF said "pass" for another domain. This is common for forwarded mail.

For a domain with a policy of `p=none` or `p=quarantine` (or `pct` below 100), Seisa adds a hint whether the policy can be tightened.

Clicking a source's IP address opens its details:

- **"geo (RDAP)".** Asks Seisa's server for the registration data of the address block (country, owner, network name) and the reverse DNS name. A "known sender" label (for example Google, Microsoft 365 or Amazon SES) appears only when that name points back to the same address.
- **"What to fix if this is a legitimate sender".** Concrete SPF and DKIM fixes derived from that source's own records. If you do not recognise the source, fix nothing for it.
- **Raw records** of that source.

Each import is saved in History. The next import of the same domain is compared with it (new sources, gone sources, worse sources, pass rate), and a daily chart of messages shows the failed part in red. An import with no loaded report is not saved.

### Buttons

| Button | What it does |
|---|---|
| Click to choose files / or drag them here | Loads reports |
| Clear | Empties the tab |
| All / Suspicious / Passing | Filters the list of sources |
| geo (RDAP) | Looks up registration data and reverse DNS of one address |
| Check in the IP tab | Fills the IP tab with the address (nothing is sent) |
| Report to AbuseIPDB | Fills the AbuseIPDB tab with the address (nothing is sent) |
| Save .md / Copy Markdown | Saves or copies the result as Markdown |

## 10. History tab

### What it is for

History collects your recent work in one place: IP checks, URL scans, DMARC imports, saved e-mail analyses and accepted AbuseIPDB reports.

### What you need

No key.

### How to use it

1. Open the tab. The tiles at the top count all entries per type ("All entries", IP, URLScan, DMARC, Email, AbuseIPDB and "High risk") and work as filters.
2. Narrow the list with the date range (Today, Last 3 days, Week, Month, All), the risk ("Any risk", High, Medium, Low) and the search box ("Search the labels..."). Entries are grouped by day.
3. Use the buttons on an entry (below).

IP checks, URL scans and DMARC imports are kept up to 100 unpinned entries. Older ones are deleted automatically. Pinned entries are never deleted by this limit. E-mail analyses and AbuseIPDB reports are not counted; they live in separate files. An entry shows the language it was made in; for e-mails the risk is taken from the verdict (legitimate = Low, inconclusive = Medium, all others = High).

### What is sent and when

Nothing. History only reads Seisa's own files, with one exception: "Repeat" runs a new check right away (see below).

### Reading the result

Each entry shows its type, its label, its risk and the time. Reopening an IP check unfolds the saved report inside the card (the raw service answers are not stored). Other types open in their own tab, and an AbuseIPDB report opens as a draft.

### Buttons

| Button | What it does |
|---|---|
| Refresh | Reloads the list |
| Reopen | Opens the entry (all types) |
| Repeat | For IP checks and URL scans: runs the check again right away, so it contacts the services |
| Pin / Unpin | Keeps an entry out of the 100-entry limit (IP checks, URL scans, DMARC imports) |
| Delete | Deletes the entry; click twice to confirm (not available for AbuseIPDB reports) |
| Compare | Tick box on IP checks. "Compare the selected" shows two ticked checks side by side; nothing is queried again |
| Clear history | Removes only unpinned IP checks, URL scans and DMARC imports (click twice). E-mail analyses are deleted one by one, and AbuseIPDB reports stay in the local log |
| Export JSON / Export CSV | Saves the visible list. The CSV is protected against formulas being run by spreadsheet programs |
| Open in the IP tab | In a reopened IP check: shows the report in the IP tab |

## 11. Logs tab

### What it is for

Logs shows the errors and warnings that Seisa and its services recorded. Normal, error-free use leaves nothing here, so an empty list is good news.

### What you need

No key.

### How to use it

1. Open the tab. The tiles show "Errors", "Warnings", "Most entries from" and "Last entry".
2. Filter by date range, level ("All levels", "Errors", "Warnings"), service ("All services") and the search box ("Search the logs...").
3. Click an entry to expand its full text. You can copy it to report a problem.

### What is sent and when

Nothing.

### Reading the result

Service names are the same as in the other tabs; Seisa's own messages are labelled "Seisa". At most the 500 newest entries are shown, and a notice asks you to narrow the date range when there are more. Log files older than 30 days are deleted automatically (today counts as day 1).

### Buttons

| Button | What it does |
|---|---|
| Refresh | Reloads the list |
| Expand all / Collapse all | Opens or folds every entry |
| Clear logs | Deletes all log files now (click twice to confirm) |

## 12. Info tab

### What it is for

Info is the slider icon on the right of the tab bar. It shows the version and release date, how many services have a key, which LLM model is on, the author, the meaning of the name, your settings, the service limits, recent changes and the license.

### What you need

No key. It shows only whether each key is "set" or "missing". The keys themselves are never shown or sent to the browser.

### How to use it

Open the tab and read. Change the language, the colour theme, the application icon or the server behaviour under "Settings". Click "Refresh limits" to update the usage figures.

### What is sent and when

Opening the tab sends nothing. "Refresh limits" is the only action that contacts services: it asks VirusTotal, urlscan.io and OpenRouter for their quotas. These requests do not use up quota.

### Reading the result

**Settings.** The language, the colour theme, the "Application icon" (with "Add icon" and "Remove icon"), and the "Server": "Shut down Seisa" and "Ask before shutting down". The icon is explained in OPERATIONS.md.

**Status and API limits.** The "Environment" (address, whether the ".env file" is present, system, Python and FastAPI versions), and one card per service with the key status and usage against the free-plan limits. When a service answers "limit exceeded" (HTTP 429), its card gets that badge until the next successful answer.

**Recent changes.** The 10 most recent releases from the git log. The list is empty when Seisa does not run from a git checkout (for example after a ZIP download).

**The name** and **About the colours** explain where the name comes from and the traditional Japanese colours behind each theme.

**Author and License.** The author card links to `contact@seisa.eu`, the GitHub repository and seisa.eu; they open in a new browser tab.

### Buttons

| Button | What it does |
|---|---|
| EN / PL | Switches the interface language (see section 13) |
| Add icon / Remove icon | Adds or removes the desktop icon |
| Shut down Seisa | Stops Seisa |
| Refresh limits | Asks the services for their current quotas |

## 13. Language and colour themes

### What it is for

Seisa speaks English and Polish and has four colour themes. Both choices are in Info, under "Settings".

### Language

On the first visit Seisa follows your browser's language (English if it is neither). Switch with EN / PL. The choice is stored in this browser, and changing it reloads the page, so Seisa asks first if work would be lost.

Service messages and AI analyses follow the interface language. The comments you send to AbuseIPDB are always in English, because they are public.

### Colour themes

| Theme | Look |
|---|---|
| Light Washi (default) | Light |
| Brown Sumi | Dark, brown |
| Blue Sumi | Dark, blue |
| Red-and-white Kōhaku | Light, red and white |
| System | Follows the light/dark setting of your computer (Light Washi or Brown Sumi) |

The choice is stored in this browser and applied before the page is drawn. The traditional Japanese colours behind each theme are explained in Info under "About the colours".

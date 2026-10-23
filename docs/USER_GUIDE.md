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
- [8. Email tab](#8-email-tab)
- [9. AbuseIPDB tab](#9-abuseipdb-tab)
- [10. History tab](#10-history-tab)
- [11. Logs tab](#11-logs-tab)
- [12. Info tab](#12-info-tab)
- [13. Language and colour themes](#13-language-and-colour-themes)
- [14. Example: from a suspicious e-mail to a report](#14-example-from-a-suspicious-e-mail-to-a-report)
- [15. Shutting Seisa down](#15-shutting-seisa-down)

## 1. Before you start

Seisa is a tool that runs on your own computer and opens in your web browser. It helps you judge whether an IP address, a web link, a mail-security report or a suspicious e-mail is dangerous, and it helps you report abusive senders to AbuseIPDB (a public database of abusive addresses).

- It opens at `http://127.0.0.1:54321`. That address means "this computer only", so nobody else can reach it and it needs no login.
- It has eight tabs: IP, URLScan, DMARC, Email, AbuseIPDB, History, Logs and Info (the Info tab is the slider icon on the right of the tab bar).
- Every tab starts empty and sends nothing until you click its action button (Check, Scan, Analyze and so on).
- Your browser talks only to Seisa. Seisa's own server contacts the outside services for you.
- Seisa never opens links, images or attachments from an e-mail or a scanned page. Addresses in results are shown as text that cannot be clicked.

What Seisa does not do: it does not decide for you. The facts that matter for security (the sender's IP address, the order of the mail servers, the SPF/DKIM/DMARC results, the report checks, the IP score) are worked out by Seisa's own program code. A language model (LLM, the AI service you can switch on with an OpenRouter key) only explains them and double-checks them. An AbuseIPDB report is always your responsibility, and the tab tells you so before sending. The reasons are in [COMPLIANCE.md](COMPLIANCE.md).

You need a running Seisa to follow this guide. How to install, start and update it is in [OPERATIONS.md](OPERATIONS.md). For the full list of what leaves your computer, see [PRIVACY.md](PRIVACY.md).

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

An API key is a long code from a service, like a membership card: it tells the service who is asking, so it can count your requests. You enter your keys in Info, in the "API keys" card (or paste them into the `.env` file yourself). The table of all keys and how to get them is in the [README](../README.md). This table only says what happens when a key is missing.

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

![The IP tab: a risk verdict, summary tiles and one card per source](images/ip_en.png)

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

Only when you click "Check" (or "Repeat" in History). An IP button in another tab only opens this tab with the address filled in. The address or domain goes to the sources you left selected. Seisa keeps no cache, so every Check asks again and uses the services' quotas each time. VirusTotal is limited by Seisa to 4 requests per minute (extra requests wait) and 500 per day, counted to 00:00 UTC. Over the daily limit, its card says "limit exceeded". The full table is in [PRIVACY.md](PRIVACY.md).

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

![The URLScan tab: a scan report with a screenshot, summary tiles and page details](images/urlscan_en.png)

The URLScan tab asks the service urlscan.io to open a suspicious link in its own browser and to report what it finds, so you never open the link yourself. You get a screenshot, the page's details and a verdict.

### What you need

A `URLSCAN_API_KEY`. Without it, "Scan" and "History" answer "no API key (URLSCAN_API_KEY)".

### How to use it

1. Paste the link into "URL to scan". Only `http://` and `https://` addresses of public sites are accepted, up to 2,048 characters. To scan several, separate up to 5 addresses with a space or a new line.
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

![The DMARC tab: a report summary with the list of IP sources and their risk](images/dmarc_en.png)

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

## 8. Email tab

### What it is for

![The Email tab with a finished analysis: verdict, summary tiles and the Overview, Facts and Lesson panes](images/email_en.png)

The Email tab teaches you to read a suspicious e-mail. You paste its full source or load an `.eml` file, and Seisa shows what it finds and explains it step by step. The source is the whole message as the mail system sees it: the headers (the technical lines at the top, like the postmarks and the envelope of a paper letter) and the body (the letter itself).

**Nothing is reported from this tab. It only explains.** To report a sender, use the AbuseIPDB tab (section 9). It is a different tool with a different job.

### What you need

No key for the local facts. An `OPENROUTER_API_KEY` is needed only for the step-by-step lesson written by the AI. Without it, "Analyze" shows the local analysis and a note that the key is missing, and that analysis is not saved.

### How to get the source of an e-mail

Seisa needs the whole source, not just what you see on screen. Where to find it depends on your mail program. The menu names below are typical and may differ in your version or language:

| Program | Typical way |
|---|---|
| Gmail (in the browser) | Open the message, click the three-dot menu next to "Reply", choose "Show original", then copy the text (or download the original as an `.eml` file) |
| Outlook on the web | Open the message, open the three-dot menu, then "View" and "View message source", and copy the text |
| Outlook for desktop | It shows only the headers (File, then Properties), which is not enough. Open the message in Outlook on the web instead |
| Thunderbird | Select the message, then "View" and "Message Source", and copy the text. "File", then "Save As" saves an `.eml` file |
| Apple Mail | Select the message, then "View", "Message" and "Raw Source", and copy the text. "File", then "Save As" with the format "Raw Message Source" saves a file |

Forwarding a message in the usual way does not work: it creates a new message and loses the original headers.

### How to use it

1. Paste the source into the large text field, or click "Load .eml file".
2. Click "Analyze" for the full lesson, or "Analyze without LLM" if you only want the local facts. "Cancel" stops a running analysis.
3. If you analysed the same message before, Seisa offers "Open the saved analysis" or "Analyze again (paid)" before spending anything.
4. Read the result (below). "Show source" and "Edit source" let you look at or change the pasted text.

### What is sent and when

Only your click on "Analyze" sends anything. Without a click, and with "Analyze without LLM", the message stays on your computer.

| You click | What happens |
|---|---|
| Analyze | Seisa first computes the facts locally. Then the whole message, headers and body, goes to OpenRouter (the AI service) for the lesson. The banner above the buttons says so |
| Analyze without LLM | Only the local facts are computed. Nothing is sent off your computer |

Good to know:

- **Attachments.** Binary attachments are not sent. Seisa replaces each with its size and its SHA-256 fingerprint (a short code that identifies a file). Text parts are decoded. The model gets at most 120,000 characters of the source.
- **Size.** The pasted source may have at most 3,000,000 characters. A larger one is refused with a message.
- **Time.** If OpenRouter sends nothing for 120 seconds, Seisa gives up with a plain message.
- **Language and cost.** The lesson is written in the interface language. The model is set by `OPENROUTER_MODEL` (default `anthropic/claude-sonnet-4.5`). The cost shown next to the buttons comes from OpenRouter itself.
- **Other people's data.** An e-mail usually contains personal data of other people. Sending it to OpenRouter is your decision. See [COMPLIANCE.md](COMPLIANCE.md).
- **Links.** Seisa never opens links, images or attachments. The full table of what leaves your computer is in [PRIVACY.md](PRIVACY.md).

### Reading the result

The result opens with a verdict (legitimate, phishing, spam, scam, malware or inconclusive) with a confidence, then these tiles:

| Tile | What it tells you |
|---|---|
| Warnings | How many findings Seisa detected automatically, and how many are only informational |
| Authentication | Whether the message passed the sender checks (SPF, DKIM, DMARC, ARC), and who wrote that result |
| Sender identity | Whether the sender's domains match the address in "From" |
| Sender IP | The address the message really came from, and the "trust boundary" it was found at |
| Content | Number of links and attachments, hidden content and forms |
| Recipient's filter | What the recipient's anti-spam filter decided (for example "Junk folder"). Shown only when the headers contain it |
| Delivery time | How long the message travelled, and whether the timestamps are in the wrong order |

Below the tiles there are three panes:

- **Overview.** A summary.
- **Facts.** What Seisa computed with its own code, no AI involved: the route of the message, authentication, domain match, the recipient's filter, timeline, structure, attachments (including double and risky file extensions), HTML content (links, hidden content, forms) and other observations.
- **Lesson.** The AI's step-by-step analysis, split into cards with a table of contents. Quotes from the message link to the "Message source" drawer, which highlights the quoted lines.

A few terms you will meet in the Facts pane, each in one sentence:

| Term | In plain words |
|---|---|
| Received headers | Every mail server that handles a message stamps it, like a post office stamping a letter. The stamps show the route, and the newest is on top |
| Trust boundary | The stamp written by the recipient's own server. Everything above it you can trust. Everything below it was written by others and may be forged |
| SPF | A list of the servers that may send mail for a domain |
| DKIM | A digital signature that shows a message was not changed on the way |
| DMARC | A rule that tells receivers what to do when SPF and DKIM do not match the sender's domain |
| ARC | A seal that forwarding servers add so that the original checks are not lost |

Two rules decide what counts as proof:

- Only an "Authentication-Results" header written by the recipient's own server counts. A result written by anyone else is just a claim.
- For Microsoft 365, where the header carries no server name, the result counts when it stands right next to the recipient's own Received line (the tile says "next to the recipient's own Received line").

The sender IP tile and the route use the same method as the AbuseIPDB tab. They come from Seisa's code, not from the AI.

Links in the results cannot be clicked. Next to an address you get "IP" (fills the IP tab) or "URLScan" (fills the URLScan tab). Nothing is checked until you click there.

A free local "citation check" confirms that the IP addresses, quoted headers and identifiers in the lesson really appear in the message, and marks those that do not. A mismatch is not always a mistake: it may be an example or a paraphrase.

If the lesson was cut off by the length limit, a banner says so and "Finish the analysis" asks the model for the missing parts (paid). A message with more than 100 Received headers gets a warning that only the newest 100 were analysed.

#### Saved analyses

Every finished AI analysis is saved automatically, together with the raw e-mail, in `data/analyses/`. "Analyze without LLM" and an analysis stopped with "Cancel" are not saved. The "Saved analyses" list lets you:

- open an analysis;
- delete it (click twice; this deletes the analysis and the saved e-mail);
- tick two and click "Compare selected (2)" to see shared IP addresses, domains, link hosts and attachments (same campaign? same infrastructure?).

A saved analysis written in the other language shows a notice, and "Analyze again in {language} (paid)" makes a new one. An analysis saved by an older Seisa version may show a banner when today's code reads the facts differently. You can switch between "Show the facts from the day of saving" and "Show the current facts". The saved file is not changed.

### Buttons

| Button | What it does |
|---|---|
| Analyze | Local facts, then the AI lesson (sends the message to OpenRouter) |
| Analyze without LLM | Local facts only (sends nothing) |
| Load .eml file | Reads an `.eml` file into the field |
| Cancel | Stops a running analysis (it is not saved) |
| Clear | Empties the tab |
| Show source / Edit source / Collapse source | Shows, edits or hides the pasted text |
| Save .md / Copy Markdown / Save .html | Saves or copies the result |
| IP / URLScan | Next to an address: fills the other tab (nothing is sent) |
| Open the saved analysis / Analyze again (paid) | Offered when the same message was analysed before |
| Finish the analysis | Asks the model for the missing parts of a cut-off lesson (paid) |
| Open / Delete / Compare selected (2) | In "Saved analyses" |

## 9. AbuseIPDB tab

### What it is for

![The AbuseIPDB tab with a prepared report: verdict, summary tiles and the Received chain](images/abuseipdb_en.png)

AbuseIPDB is a public database where people report IP addresses that send spam, phishing and other abuse. This tab prepares such a report from a spam or phishing e-mail, checks it, and, after your click, sends it.

It is a different tool from the Email tab. Email teaches you to read a message and reports nothing. AbuseIPDB prepares a public report. Both can use the AI on the same e-mail, but they do not share anything: you paste the source in each.

The checks that decide whether you may send are worked out by Seisa's own code. The AI only gives an opinion and drafts the comment. Whatever you send, you are responsible for it, and the tab says so above the field.

### What you need

- Nothing, to prepare a report from the facts and a comment built from them.
- `OPENROUTER_API_KEY` for the AI assessment.
- `ABUSEIPDB_API_KEY` for what AbuseIPDB already knows about the address, and for sending.

### How to use it

1. Get the source of the e-mail (see "How to get the source of an e-mail" in section 8) and paste it into "E-mail source (with headers)", or click "Load .eml file".
2. Click "Analyze", or "Analyze without LLM".
3. Read the verdict, the tiles and "Where the IP comes from". If Seisa picked the wrong address, click "Use this address" on the right line.
4. In the "Report" form, check the IP address, the categories, the attack timestamp and the comment.
5. Open "Checks before sending" and fix what fails. If the personal-data warning appears, click "Mask them".
6. Look at "What will be sent to the API". It shows exactly what goes out.
7. Click "Send via AbuseIPDB API". The button stays disabled while a required check fails.

### What is sent and when

| What | When |
|---|---|
| The whole message, to OpenRouter | Only when you click "Analyze" and a key is set. "Analyze without LLM" sends nothing |
| The source IP address, to AbuseIPDB | **By itself**, without a click, as soon as a public IP address is in the form and an AbuseIPDB key is set. Only the address is sent, never the e-mail. It shows what AbuseIPDB already knows about it |
| The report (IP, categories, time, comment), to AbuseIPDB | Only when you click "Send via AbuseIPDB API". AbuseIPDB shows comments publicly |

The automatic address lookup is the one exception to "nothing without a click" in Seisa. The complete table is in [PRIVACY.md](PRIVACY.md).

The pasted source may have at most 3,000,000 characters. A larger one is refused with "The source is too large ({size} characters, limit {limit})."

### Reading the result

The result starts with a verdict: "The e-mail looks eligible for a report." or "This e-mail most likely does NOT qualify for a report." Then come the tiles "Source IP", "Age", "Authentication", "Attachments" and "AbuseIPDB score".

**Where the IP comes from.** The source IP is the one at the trust boundary of the Received chain (see section 8): the stamp written by your own provider's server, recording who connected to it. Stamps below it could be forged. Seisa's code finds this address. If the AI suggests a different one, Seisa shows both and never swaps them by itself: you choose with "Use this address".

**The form.** "Report" holds the IP address, the categories, the attack timestamp and the comment:

- Categories are chips. AbuseIPDB has 23, and "7. Phishing" and "11. Email Spam" are typical for e-mail.
- The comment is in English, because it is public. You can edit it. It may have at most 1,024 characters (a counter is shown), and before sending it is cleaned to plain ASCII (other characters become spaces).
- Seisa scans the comment for personal data: your own address from the message, other e-mail addresses and internal IP addresses. It offers "Mask them". Sending with such data left in asks for confirmation.

**Checks before sending.** Three groups:

| Group | What it holds |
|---|---|
| Required (API and backend) | Attack at most 60 days old, public IP, at least one category, the 15-minute rule for the same IP, and report eligibility. Seisa's server repeats the first four itself; the eligibility verdict is checked in the page only, because it is advisory |
| Blocking, judged by the AI | "Verified from the Received header" and "The source is trustworthy" |
| Informational | Spoofing (forged sender), category matches the real mechanism, no personal data |

AbuseIPDB accepts a repeat report of the same IP from one account only after 15 minutes, and Seisa blocks it earlier using its own local log. A message that looks like a test sent from your own account to yourself is marked as most likely not qualifying.

**Without the AI.** The verdict is then "in doubt (not assessed)". Only the hard criteria are checked (public IP, age up to 60 days). That does not block sending, because the hard checks still run in Seisa's code, but it is also not enough to say the e-mail deserves a report. Decide yourself. "Received verified" is green only for an address Seisa picked itself with high confidence. If you type another address, it becomes "not assessed".

**What AbuseIPDB already knows.** With a key set, the form shows the reports of the last 90 days for the address. It warns when the address is on the AbuseIPDB whitelist or was already reported in the chosen categories in the last 7 days.

**After sending.** Seisa shows the address's new AbuseIPDB score, the daily limit left and buttons to report other addresses from the same e-mail. Errors from AbuseIPDB are explained: daily limit used up (with the reset time), repeat of the same IP, rejected data and rejected key.

**Your reports.** Lists the last 100 attempts from the local log, accepted and failed, with the tiles "Sent today" (counted by UTC day), "Daily limit left" and "Accepted". Accepted reports also appear in the History tab.

### Buttons

| Button | What it does |
|---|---|
| Analyze / Analyze without LLM | Prepares the report (the first sends the message to OpenRouter) |
| Load .eml file / Clear | Loads a file / empties the tab |
| Use this address | Takes another address from the Received chain as the source IP |
| Mask them | Masks personal data in the comment |
| Copy comment / Save .md | Copies the comment / saves the prepared report |
| Send via AbuseIPDB API | Sends the report to AbuseIPDB |
| Use as draft | In "Your reports": loads an earlier attempt into the form |
| Check | In "Your reports": opens the address's public AbuseIPDB page in a new tab (your browser contacts abuseipdb.com) |

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

**Settings.** The language, the colour theme, the "Application icon" (with "Add icon" and "Remove icon"), and the "Server": "Shut down Seisa" and "Ask before shutting down". The icon is explained in [OPERATIONS.md](OPERATIONS.md).

**API keys.** A separate card above "Status and API limits", closed until you open it. One row per service; the "Open <service>" button opens the service's home page in a new tab, where you can create an account and generate a key. Each row shows its state: "set", "not set" or "set by an environment variable" (then change it where it is exported; the file cannot override it). Paste a key into the field and click "Save keys"; an empty field keeps what is set, "Remove" deletes one key and "Remove all" (click twice to confirm) deletes every key at once, except those set by an environment variable. The keys go into the `.env` file in the Seisa folder, readable only by you, and take effect at once without a restart. The fields stay empty on purpose: Seisa never shows a key again. A key may contain only letters, digits and `. _ ~ + / = : -`. The "OpenRouter model" row is the one setting that is shown, because it is not a secret. After saving, "Refresh limits" checks the VirusTotal, URLScan and OpenRouter keys.

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

## 14. Example: from a suspicious e-mail to a report

This walk-through follows one made-up case from the first doubt to a sent report. All addresses are fictional: the sender is `203.0.113.45` and its domain is `mail.example`. These are reserved example addresses, so with them the "IP" button does not appear and the report cannot be sent. With a real public address every step works as described.

You get a message that claims to be from your bank and asks you to "confirm your account". Something is off.

1. **Get the source.** Copy the whole source of the message (see "How to get the source of an e-mail" in section 8). Do not click anything in the message itself.
2. **Understand it in the Email tab.** Paste the source and click "Analyze" (or "Analyze without LLM" if you do not want to send it to OpenRouter). Read the verdict, for example "phishing" with a confidence, then the "Sender IP" tile (here `203.0.113.45`) and the "Authentication" tile. The "Lesson" pane explains what is wrong, step by step.
3. **Optional: check the sender.** Click "IP" next to the sender IP. The IP tab opens with the address filled in. Nothing is sent yet: click "Check" to see the address's reputation. With a reserved example address like ours the "IP" button does not appear; a real public address gets a score.
4. **Prepare the report.** Open the AbuseIPDB tab. There is no button that moves the e-mail across, so paste the source again and click "Analyze". Check the verdict, "Where the IP comes from", the categories (for this case "7. Phishing" and perhaps "11. Email Spam"), the time and the comment.
5. **Check before you send.** Open "Checks before sending". Fix what fails. Click "Mask them" if the personal-data warning appears, then look at "What will be sent to the API". Remember that the comment is public.
6. **Send.** Click "Send via AbuseIPDB API". Seisa shows the address's new score and the daily limit left.
7. **Find it again.** The report appears in "Your reports" in the same tab and in the History tab.

If the tab says the e-mail does not qualify (for example, it is older than 60 days), do not send it. AbuseIPDB would refuse it or it would only add noise.

## 15. Shutting Seisa down

When you are done, click "Shut down Seisa" in the footer, or in the Info tab under "Settings". The server stops and the page is replaced by "Seisa has been stopped". Your browser may ask you to close the tab yourself.

Seisa asks for confirmation first. Tick "Do not ask again" to stop the question, and switch it back on with "Ask before shutting down" in Info, under "Settings". It always asks when work would be lost, for example a running analysis or pasted text. To start Seisa again, see [OPERATIONS.md](OPERATIONS.md).

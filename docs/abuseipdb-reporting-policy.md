# AbuseIPDB reporting rules

This file describes the rules of reporting to the AbuseIPDB service - https://www.abuseipdb.com. The wording below is our own summary, not a copy of the AbuseIPDB texts.

## Reporting rules (summary)

This is a summary in our own words of the rules published by AbuseIPDB at https://www.abuseipdb.com/reporting-policy
(last checked against the source version dated 2022-06-23). It is not a copy of that page - the binding text is the
one on the AbuseIPDB website, and the rules apply to the API (`report`, `report-bulk`) and to the web forms alike.

"Attack" always means a cybersecurity attack. The words MUST / SHOULD / MAY below carry their usual RFC 2119 weight.

- The reported activity MUST be no older than 60 days.
- The report MUST describe the activity in detail. Useful details: port, payload, timestamp.
- The report SHOULD carry the time of the event. Without a timestamp in the comment, the time of submission is
  taken as the time of the attack.
- Do NOT report activity whose source address is probably forged (SYN or UDP floods). A TCP connection may be
  reported only if the three-way handshake was completed; UDP traffic cannot be reported.
- Do NOT report an address just because of its AbuseIPDB confidence score - that would be circular reasoning.
- One report MAY summarise several log entries that belong to the same attack.

Reports with an identical comment and identical categories submitted within 24 hours are merged. AbuseIPDB may
remove reports and may suspend the reporting rights of a user at its own discretion.

## Identifying the real IP address in the Received chain

`Received` headers are prepended at every hop - the newest one (the last delivery) comes first in the headers of
the e-mail, the oldest one (the first entry into the network) comes last. In the simple case (a direct SMTP
connection to your own server) the last/oldest Received header is the only and sufficient evidence - it is written
by the recipient's own, unforgeable infrastructure.

**Beware of multi-hop chains of large providers** (Microsoft 365/Outlook.com, Google Workspace and similar): the
first few Received headers from the top are usually INTERNAL transfers between servers of the same provider. They
have formally "public" IP addresses (not private/loopback), but that is NOT the address of the attacker - it is the
mail infrastructure of the provider itself. A typical, recognisable pattern of the boundary (the place where the
provider records the actual address of the connecting sender) is:

```
Received: from [127.0.0.1] (REAL_IP) by <gateway>.mail.protection.outlook.com
  ... via Frontend Transport; ...
```

i.e. the "from" host is a loopback placeholder `[127.0.0.1]` (or similar) and the real external address is written
in the parentheses next to it. The general rule: go from the newest Received header downwards and compare the domain
of the "from" host with the domain of the "by" host of the first (newest) hop - as long as they match, it is an
internal hop of the same provider. The first hop where the "from" domain no longer matches (or "from" is just an
IP/loopback without a domain of its own) is the boundary hop, and its IP is the one that qualifies for a report, not
the IP of the earlier (newer) hops.

## AbuseIPDB categories

The IDs and names are those of the AbuseIPDB API; the descriptions are our own short paraphrases.

| ID | Name | Description |
|----|------|-------------|
| 1 | DNS Compromise | Tampering with DNS records so that traffic is redirected. |
| 2 | DNS Poisoning | Planting forged data in a DNS server's cache. |
| 3 | Fraud Orders | Orders placed fraudulently. |
| 4 | DDoS Attack | Taking part in a distributed denial-of-service attack, typically as a botnet member. |
| 5 | FTP Brute-Force | Password guessing against FTP. |
| 6 | Ping of Death | Oversized IP packets sent to crash a target. |
| 7 | Phishing | Phishing sites or phishing e-mails. |
| 8 | Fraud VoIP | Fraud involving VoIP services. |
| 9 | Open Proxy | An open proxy, an open relay or a Tor exit node. |
| 10 | Web Spam | Comment or forum spam, referer spam and other CMS spam. |
| 11 | Email Spam | Spam in the message body, infected attachments and phishing e-mails. Keep the comment to relevant facts (no log dumps) and strip personal data if you want to stay anonymous. |
| 12 | Blog Spam | Spam comments on blogs and CMS sites. |
| 13 | VPN IP | A combined category for addresses of VPN services. |
| 14 | Port Scan | Probing for open ports and vulnerable services. |
| 15 | Hacking | General intrusion attempts. |
| 16 | SQL Injection | Attempts at SQL injection. |
| 17 | Spoofing | Forging the identity of an e-mail sender. |
| 18 | Brute-Force | Password guessing against websites and services such as SSH, FTP, SIP, SMTP or RDP; separate from DDoS. |
| 19 | Bad Web Bot | Scrapers and crawlers that ignore robots.txt, excessive requests, user-agent spoofing. |
| 20 | Exploited Host | A host that is probably infected and used to attack others or serve malicious content; the owner may not know. Often combined with other categories. |
| 21 | Web App Attack | Probing or exploiting web applications (CMS, shops, forums, phpMyAdmin, plugins). |
| 22 | SSH | Abuse of Secure Shell; combine with a more specific category. |
| 23 | IoT Targeted | An attack aimed at an Internet-of-Things device; the comment should name the device type. |

## AbuseIPDB report template

### Report data (fields sent to `/report`)

| API field | Required? | Value in Seisa |
|---|---|---|
| **ip** | yes | the IP address (Step 2) |
| **categories** | yes, at least 1 | the selected categories (Step 2) |
| **timestamp** | no (default "now") | The attack timestamp - a separate field, it does NOT go into the comment text |
| **comment** | no (but AbuseIPDB recommends a detailed description - see the "Reporting rules" section above) | written by the LLM in Step 1, editable in Step 2 - see below |

Seisa has no separate field for the port number - if it is known, add it to the comment manually before sending.

---

## Comment text - written by the LLM, with a deterministic fallback

Although `comment` is an optional field in the AbuseIPDB API, the AbuseIPDB policy itself (above) expressly expects a
detailed, technically justified description of the attack. Seisa does this differently than through a manually filled
form field: when `OPENROUTER_API_KEY` is configured, during the analysis in Step 1 (`analyze_email`) the model
receives the facts extracted from the e-mail, the complete raw source of the message (all headers and the whole body) - and on that basis writes a
ready, detailed comment in English (the `report_comment` field) covering the attack mechanism, the meaning of
SPF/DKIM/DMARC, malicious attachments (with a detected double extension), a ransom/BTC demand, mass-mailing patterns -
anything relevant visible in the provided data, within about 900 characters (the hard API limit is 1024).

This text goes straight into the editable "Report comment" field in Step 2 - the user can freely correct it before
sending (e.g. add the port number). The backend sanitises/truncates the final text right before sending anyway
(`sanitize_comment`/`truncate_chars` - ASCII, protection against formula injection, a hard limit of 1024
characters), regardless of who wrote it.

**Without an OpenRouter key (or when the LLM analysis fails)** - the comment is built deterministically, solely from
the facts extracted from the headers/MIME (without an LLM):

```
Suspicious email delivered directly from IP [X.X.X.X].

[If applicable - spoofing confirmed technically:]
SPF/DMARC check failed for the spoofed sender domain, confirming the message
did not originate from an authorized mail server for that domain.

[If there are attachments - one block per attachment, detected automatically from MIME:]
Attachment: [file name], [size in bytes], Content-Type: [type].
Filename displays as .[apparent extension] but actual extension is .[real extension] (double extension).

[If applicable - ransom/payment demand:]
Ransom/payment demand: [amount + currency]
BTC/crypto wallet: [address]

[If applicable - identifiers for correlation:]
Message-ID: [identifier]
```

This text is editable too - it is only a rarer, poorer starting point when the LLM is unavailable.

---

## Checklist before sending

- [ ] The attack is not older than 60 days
- [ ] The IP address is verified from the `Received` header (not from `From`/the body - those can be forged)
- [ ] The source is not spoofed (SYN/UDP flood -> do NOT report; TCP with a completed handshake -> may be reported)
- [ ] The category matches the actual attack mechanism, not "just in case"
- [ ] If spoofing is confirmed by an SPF/DMARC failure - one confirming sentence is added (Seisa does this automatically)
- [ ] The timestamp is **not** in the comment text - only in the separate form field
- [ ] The comment (preview in Step 2) contains no own e-mail address/domain/other PII beyond what is needed to describe the attack mechanism

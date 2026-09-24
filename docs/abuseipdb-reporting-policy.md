# AbuseIPDB reporting rules

This file describes the rules of reporting to the AbuseIPDB service - https://www.abuseipdb.com

## Reporting Policy

These rules apply to use of the report and report-bulk API endpoints, as well as the respective web forms.

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

Attack here and elsewhere on the site refers to a cybersecurity attack. If you were physically assaulted or abused, please call your local police.

- Report MUST be of an attack no older than 60 days.
- Report MUST contain a detailed description of the attack. Recommended details to include are: port number, payload, and timestamp.
- Report SHOULD include a timestamp of the attack. If no timestamp is included in the comment, the time of report is assumed to be the time of attack.
- Report MUST NOT be of an attack where the source address is likely spoofed i.e. SYN floods and UDP floods. TCP connections can only be reported if they complete the three-way handshake. UDP connections cannot be reported.
- Report MUST NOT be on the basis of an AbuseIPDB confidence of abuse score. This is circular logic.
- Report MAY be an aggregation of multiple logs related to a single attack.

Reports with the same comment and categories within a 24 hour window will be merged.

AbuseIPDB reserves the right to remove reports at its discretion. AbuseIPDB reserves the right to suspend any user's ability to report.

Last Modified 2022-06-23

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

| ID | Name | Description |
|----|------|-------------|
| 1 | DNS Compromise | Altering DNS records resulting in improper redirection. |
| 2 | DNS Poisoning | Falsifying the cache of a DNS server (cache poisoning). |
| 3 | Fraud Orders | Fraudulent orders. |
| 4 | DDoS Attack | Participating in a distributed denial-of-service attack (usually part of a botnet). |
| 5 | FTP Brute-Force | - |
| 6 | Ping of Death | An oversized IP packet. |
| 7 | Phishing | Phishing websites and/or phishing e-mails. |
| 8 | Fraud VoIP | - |
| 9 | Open Proxy | An open proxy, open relay or Tor exit node. |
| 10 | Web Spam | Comment/forum spam, HTTP referer spam or other CMS spam. |
| 11 | Email Spam | Spam in the e-mail body, infected attachments and phishing e-mails. Note: keep comments to relevant information only (instead of log dumps) and remove PII if you want to stay anonymous. |
| 12 | Blog Spam | CMS blog comment spam. |
| 13 | VPN IP | A conjunctive (combined) category. |
| 14 | Port Scan | Scanning for open ports and vulnerable services. |
| 15 | Hacking | - |
| 16 | SQL Injection | SQL injection attempts. |
| 17 | Spoofing | Impersonating the sender of an e-mail. |
| 18 | Brute-Force | Brute-force attacks on credentials of websites and services such as SSH, FTP, SIP, SMTP, RDP etc. A category separate from DDoS attacks. |
| 19 | Bad Web Bot | Web scraping (e-mail addresses, content etc.) and crawlers that do not respect robots.txt. Excessive requests and user-agent spoofing can be reported here too. |
| 20 | Exploited Host | A host probably infected with malware and used for other attacks or to host malicious content. The owner of the host may be unaware of the compromise. The category is often used together with other attack categories. |
| 21 | Web App Attack | Attempts to probe or exploit installed web applications, e.g. CMS (WordPress/Drupal), e-commerce solutions, forum software, phpMyAdmin and other plugins/solutions. |
| 22 | SSH | Abuse related to Secure Shell (SSH). Use together with more specific categories. |
| 23 | IoT Targeted | An attack aimed at an "Internet of Things" device. The comments should state the type of the attacked device. |

## AbuseIPDB report template

### Report data (fields sent to `/report`)

| API field | Required? | Value in Seisa |
|---|---|---|
| **ip** | yes | the IP address (Step 2) |
| **categories** | yes, at least 1 | the selected categories (Step 2) |
| **timestamp** | no (default "now") | The attack timestamp - a separate field, it does NOT go into the comment text |
| **comment** | no (but AbuseIPDB recommends a detailed description - see the "Reporting Policy" above) | written by the LLM in Step 1, editable in Step 2 - see below |

Seisa has no separate field for the port number - if it is known, add it to the comment manually before sending.

---

## Comment text - written by the LLM, with a deterministic fallback

Although `comment` is an optional field in the AbuseIPDB API, the AbuseIPDB policy itself (above) expressly expects a
detailed, technically justified description of the attack. Seisa does this differently than through a manually filled
form field: when `OPENROUTER_API_KEY` is configured, during the analysis in Step 1 (`analyze_email`) the model
receives the facts extracted from the e-mail, the raw headers (Received/authentication/Subject/Reply-To/spam
indicators if present) and an excerpt of the message body (HTML converted to plain text) - and on that basis writes a
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

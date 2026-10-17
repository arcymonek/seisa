**English** | [Polski](pl/API.md)

# Seisa API

Seisa's web page does all its work by calling a small API on your own computer. This page lists every endpoint, for contributors and for people who want to call Seisa from a script. It is an internal API and may change between versions: there is no API version number and no promise of stability.

## Contents

- [Before you start](#before-you-start)
- [Conventions](#conventions)
- [Machine-readable schema](#machine-readable-schema)
- [IP lookup](#ip-lookup)
- [History](#history)
- [E-mail analysis (Email tab)](#e-mail-analysis-email-tab)
- [AbuseIPDB reports](#abuseipdb-reports)
- [URL scans (URLScan tab)](#url-scans-urlscan-tab)
- [DMARC](#dmarc)
- [Logs](#logs)
- [Info, settings and limits](#info-settings-and-limits)
- [Themes](#themes)
- [Static files](#static-files)
- [Which tab calls what](#which-tab-calls-what)

## Before you start

The API lives under `/api` on the same address as the interface, `http://127.0.0.1:54321`. There is no login and no API key for Seisa itself.

Three rules decide who may call it:

- A request whose `Host` header is not `127.0.0.1` or `localhost` is refused with HTTP 400. This protects against DNS rebinding.
- A request to `/api/` that a browser marks as coming from another page gets HTTP 403 with `{"detail": "request from another web page blocked"}`. That means `Sec-Fetch-Site` is anything but `same-origin` or `none`, or `Origin` is not this server (scheme, `127.0.0.1` or `localhost`, and port must all match).
- A request with neither `Sec-Fetch-Site` nor `Origin` (curl, a script) is allowed. This guard is not authentication: any program on your computer can call the API.

Example from a script:

```bash
curl -s "http://127.0.0.1:54321/api/abuseipdb/ip-info?ip=203.0.113.7"
```

## Conventions

These rules are the same for every endpoint, so they are written once here.

- **Format:** requests and answers are JSON, apart from the two streams, the screenshot and the generated CSS.
- **Errors:** an error is JSON `{"detail": ...}`. Usually `detail` is a translated text. For validation errors (HTTP 422) it is a list of `{loc, msg, ...}`. For a report refused by the hard checks it is an object `{message, checks}`.
- **Unexpected errors:** HTTP 500 with a generic translated message. The details go only to the log.
- **Status codes used:** 400, 401, 403, 404, 409, 413, 422, 429, 500 and 502.
- **Language:** texts in answers follow the `X-Seisa-Lang` header (`en` or `pl`, first two letters). Anything else means English.
- **Streams:** two endpoints send Server-Sent Events (`text/event-stream`). Each message is one `data: <JSON>` line followed by a blank line.
- **Headers on answers:** every answer carries the Content-Security-Policy header. Files outside `/api/` also get `Cache-Control: no-cache, no-store, must-revalidate`.
- **Rate limits:** the local API has none. Only VirusTotal calls are throttled (4 a minute, 500 a day), and AbuseIPDB reports of the same IP are refused for 15 minutes.

Size limits:

| What | Limit |
|---|---|
| Lookup indicator | 253 characters |
| E-mail source (both e-mail tabs) | Refused outright above 6 000 000 characters (HTTP 422). A friendly "too large" message appears above 3 000 000 characters: in the Email tab after normalisation, as an `error` event; in the AbuseIPDB tab as HTTP 413 |
| History label | 1 000 characters |
| History risk summary | 50 characters |
| History data | 10 000 000 characters as JSON |
| Report comment | 5 000 accepted, 1 024 sent |
| Own identifiers of a report | Up to 20, each up to 254 characters |

## Machine-readable schema

`GET /openapi.json` returns the full machine-readable description of all routes. It is guarded like every other path.

FastAPI's interactive documentation pages are switched off (they answer 404), because the Content-Security-Policy would block the scripts they load from a CDN. Use the schema with a viewer of your choice.

## IP lookup

One endpoint checks an IP address or a domain with the selected services.

### `POST /api/lookup`

| Item | Detail |
|---|---|
| Input | JSON `{indicator, type, services}`. `indicator` is text up to 253 characters. `type` is `auto` (default), `ip` or `domain`. `services` is a list of service names, or `null` for all |
| Output | `LookupResult`: `indicator`, `indicator_type`, `risk_score`, `services` (a result per service), `markdown`, `identity`, `comparison` |
| Limits and errors | 400 for an invalid indicator, a non-public IP, or a `services` list with no known service (`null` means all services, an empty list is refused). The result is saved to History |
| Sends to the internet | Yes, to the selected services (see PRIVACY.md) |
| Called by | `frontend/js/lookup.js` |

## History

History endpoints store and read the entries of the IP, DMARC and URLScan tabs. The list also shows saved e-mail analyses and accepted reports.

### `GET /api/history`

| Item | Detail |
|---|---|
| Input | none |
| Output | List of rows `{id, type, created_at, label, risk_summary, lang, pinned}` for lookups, DMARC and URLScan, plus saved e-mail analyses (`type: "email"`) and accepted AbuseIPDB reports (`type: "report"`). Newest first, not cut |
| Limits and errors | none |
| Sends to the internet | No |
| Called by | `frontend/js/history.js`, `frontend/js/dmarc.js` |

### `GET /api/history/{entry_id}`

| Item | Detail |
|---|---|
| Input | `entry_id` in the path |
| Output | The full entry, with its `data` |
| Limits and errors | 404 when the entry does not exist |
| Sends to the internet | No |
| Called by | `frontend/js/history.js`, `frontend/js/dmarc.js` |

### `POST /api/history`

| Item | Detail |
|---|---|
| Input | JSON `{type, label, risk_summary, data}`. `type` is `lookup`, `dmarc` or `urlscan`. `label` is up to 1 000 characters, `risk_summary` up to 50 or `null`, `data` an object |
| Output | The stored entry |
| Limits and errors | 400 for an invalid type; 413 when `data` is above 10 000 000 characters as JSON. For `urlscan`, `data.summary` must be an object and `data.thumbnail` only `data:image/jpeg;base64,...` up to 200 000 characters (otherwise 400) |
| Sends to the internet | No |
| Called by | `frontend/js/dmarc.js`, `frontend/js/urlscan.js` |

### `PATCH /api/history/{entry_id}`

| Item | Detail |
|---|---|
| Input | JSON `{pinned: true or false}` |
| Output | `{id, pinned}` |
| Limits and errors | 404 when the entry does not exist |
| Sends to the internet | No |
| Called by | `frontend/js/history.js` |

### `DELETE /api/history/{entry_id}`

| Item | Detail |
|---|---|
| Input | `entry_id` in the path |
| Output | `{deleted: <id>}` |
| Limits and errors | 404 when the entry does not exist |
| Sends to the internet | No |
| Called by | `frontend/js/history.js` |

### `DELETE /api/history`

| Item | Detail |
|---|---|
| Input | none |
| Output | `{cleared: true}` |
| Limits and errors | Removes every entry that is not pinned (lookups, DMARC, URLScan). E-mail analyses and the report log stay |
| Sends to the internet | No |
| Called by | `frontend/js/history.js` |

## E-mail analysis (Email tab)

The Email tab sends the pasted message source to the backend. Two endpoints stream their answer as Server-Sent Events.

The events are:

- `facts {facts, prep_notes, llm_configured}`: the local, deterministic facts. `facts.auth_summary` is `{spf, dkim, dmarc, verified, authserv_id, header}`. The full `facts` object is large; see `/openapi.json` and `tests/golden/dump_facts.en.txt` for an example.
- `delta {text}`: a chunk of the model's text (repeated).
- `warning {message}`: an optional notice.
- `done {llm, analysis_id, lang, verdict, confidence, usage, truncated, model, citation_check}`: the end. Without the model it is `done {llm: false}`, with `skipped: true` when the request set `use_llm` to false.
- `error {message, phase}`: a failure (`phase` is optional).

### `POST /api/email/find`

| Item | Detail |
|---|---|
| Input | JSON `{raw_email, use_llm}`. `raw_email` is up to 6 000 000 characters |
| Output | `{sha256, matches}`: saved analyses of the same message, each `{id, created_at, verdict, confidence, truncated, lang, cost}` |
| Limits and errors | 422 above 6 000 000 characters |
| Sends to the internet | No |
| Called by | `frontend/js/email.js` |

### `POST /api/email/analyze`

| Item | Detail |
|---|---|
| Input | JSON `{raw_email, use_llm}`. `use_llm` defaults to `true` |
| Output | A stream of events: `facts`, then `delta` (many), then optionally `warning`, then `done`; or `error` |
| Limits and errors | An empty source, a source above 3 000 000 characters after normalisation, or a parser failure arrive as `error` events. 422 above 6 000 000 characters |
| Sends to the internet | Yes, to OpenRouter, only when `use_llm` is true and a key is set (see PRIVACY.md) |
| Called by | `frontend/js/email.js` |

### `POST /api/email/analyses/{analysis_id}/continue`

| Item | Detail |
|---|---|
| Input | `analysis_id` in the path (`YYYYMMDD-HHMMSS-xxxxxxxx`), body `{}` |
| Output | A stream of `delta`, `warning`, `error` and `done` events, as above. It finishes an answer that was cut off |
| Limits and errors | 400 for an invalid id, an analysis that was not truncated, or no key; 404 when not found |
| Sends to the internet | Yes, to OpenRouter (see PRIVACY.md) |
| Called by | `frontend/js/email.js` |

### `GET /api/email/analyses`

| Item | Detail |
|---|---|
| Input | none |
| Output | List of `{id, created_at, subject, from, verdict, confidence, truncated, lang}`, newest first |
| Limits and errors | Unreadable files are skipped |
| Sends to the internet | No |
| Called by | `frontend/js/email.js` |

### `GET /api/email/analyses/{analysis_id}`

| Item | Detail |
|---|---|
| Input | `analysis_id` in the path |
| Output | The saved record. If the facts recomputed today differ in what matters (sender hop, attachments, receiver verdicts, number of warnings), it also has `facts_current` and `facts_changed: true` |
| Limits and errors | 400 for an invalid id; 404 when not found |
| Sends to the internet | No |
| Called by | `frontend/js/email.js` |

### `DELETE /api/email/analyses/{analysis_id}`

| Item | Detail |
|---|---|
| Input | `analysis_id` in the path |
| Output | `{deleted: true}` |
| Limits and errors | 400 for an invalid id; 404 when not found |
| Sends to the internet | No |
| Called by | `frontend/js/email.js`, `frontend/js/history.js` |

## AbuseIPDB reports

The AbuseIPDB tab prepares and sends one abuse report. The backend always repeats the hard checks itself: age, IP and category.

### `POST /api/abuseipdb/email/analyze`

| Item | Detail |
|---|---|
| Input | JSON `{raw_email, use_llm}`. `raw_email` is up to 6 000 000 characters, `use_llm` defaults to `true` |
| Output | `{facts, ip_candidates, own_terms, local_assessment, categories, llm_configured, llm_analysis, usage, llm_input, report_comment}`. Each candidate is `{ip, role, host, reported}` with `role` one of `boundary`, `hop`, `llm` |
| Limits and errors | 413 above 3 000 000 characters, with a translated message; 422 above 6 000 000 characters |
| Sends to the internet | Yes, to OpenRouter, only when `use_llm` is true and a key is set (see PRIVACY.md) |
| Called by | `frontend/js/report-builder.js` |

### `GET /api/abuseipdb/categories`

| Item | Detail |
|---|---|
| Input | none |
| Output | `{id: name}` for the 23 AbuseIPDB categories |
| Limits and errors | none |
| Sends to the internet | No |
| Called by | `frontend/js/report-builder.js` |

### `POST /api/abuseipdb/report/preview`

| Item | Detail |
|---|---|
| Input | `ReportFields`: `ip`, `categories` (list of numbers), `attack_timestamp` (text or `null`), `comment` (up to 5 000 characters), `own_terms` (up to 20 texts of up to 254 characters) |
| Output | `{checks, previous, pii, payload}`. `checks` has `ip_ok`, `ip_reason`, `age_ok`, `age_reason`, `category_ok`, `all_passed`. `previous` has `count`, `last_submitted_at`, `cooldown_left_minutes`. `pii` is a list of `{kind, value}`. `payload` is what would be sent |
| Limits and errors | none |
| Sends to the internet | No |
| Called by | `frontend/js/report-builder.js` |

### `POST /api/abuseipdb/report/redact`

| Item | Detail |
|---|---|
| Input | JSON `{comment, own_terms}`. `comment` is up to 5 000 characters |
| Output | `{comment}` with placeholders `[redacted]`, `[email removed]` and `[internal IP]` |
| Limits and errors | none |
| Sends to the internet | No |
| Called by | `frontend/js/report-builder.js` |

### `GET /api/abuseipdb/report/history`

| Item | Detail |
|---|---|
| Input | Query `limit` (default 100, clamped to 1-500) |
| Output | `{entries, sent_today, rate_limit}`. `sent_today` counts reports since midnight UTC |
| Limits and errors | none |
| Sends to the internet | No |
| Called by | `frontend/js/report-history.js` |

### `GET /api/abuseipdb/ip-info`

| Item | Detail |
|---|---|
| Input | Query `ip`, for example `?ip=203.0.113.7` |
| Output | `{status: "ok", total_reports, num_distinct_users, abuse_confidence_score, last_reported_at, is_whitelisted, isp, usage_type, country_code, recent_reports, recent_days: 7}`, or `{status: "unavailable"}` |
| Limits and errors | An IP that cannot be reported, or a missing key, gives `unavailable` without any network call |
| Sends to the internet | Yes, to AbuseIPDB (see PRIVACY.md) |
| Called by | `frontend/js/report-builder.js` |

### `POST /api/abuseipdb/report/submit`

| Item | Detail |
|---|---|
| Input | `ReportFields`, as for the preview |
| Output | `{success: true, result, rate_limit}` |
| Limits and errors | 400 when a hard check fails (`detail` is `{message, checks}`) or no key is set; 409 for the 15-minute pause on the same IP or the service's own same-IP rule; 429 when the daily quota is used (the text names the reset time); 401 when the key is rejected; 422 when the service refuses the data; 502 for other service errors |
| Sends to the internet | Yes, to AbuseIPDB (see PRIVACY.md) |
| Called by | `frontend/js/report-builder.js` |

## URL scans (URLScan tab)

The URLScan tab asks urlscan.io to scan a page. Seisa never loads the scanned page itself.

### `POST /api/urlscan/scan`

| Item | Detail |
|---|---|
| Input | JSON `{url, visibility, country, useragent}`. `visibility` is `unlisted` (default), `private` or `public`. `country` is one of 12 or `null`. `useragent` is up to 250 printable characters or `null` |
| Output | `{uuid, url, visibility, result_page_url}` |
| Limits and errors | 400 for no key, an invalid visibility, country or user agent, or an invalid URL (empty, above 2 048 characters, with whitespace, a non-HTTP scheme, or a private or local host); 502 when urlscan.io refuses |
| Sends to the internet | Yes, to urlscan.io (see PRIVACY.md) |
| Called by | `frontend/js/urlscan.js` |

### `GET /api/urlscan/result/{uuid}`

| Item | Detail |
|---|---|
| Input | `uuid` in the path (36 characters: hex digits and dashes) |
| Output | `{status: "pending"}`, or `{status: "done", summary, markdown, raw}` |
| Limits and errors | 400 for an invalid uuid; 502 when the fetch fails |
| Sends to the internet | Yes, to urlscan.io (see PRIVACY.md) |
| Called by | `frontend/js/urlscan.js` |

### `GET /api/urlscan/screenshot/{uuid}`

| Item | Detail |
|---|---|
| Input | `uuid` in the path |
| Output | A PNG image with `Cache-Control: private, max-age=3600` and `nosniff` |
| Limits and errors | 400 for an invalid uuid; 404 when there is no screenshot yet; 502 on failure, also when the file is not a PNG or is larger than 6 000 000 bytes |
| Sends to the internet | Yes, to urlscan.io (see PRIVACY.md) |
| Called by | An `<img>` element in `frontend/js/urlscan.js` |

### `GET /api/urlscan/search`

| Item | Detail |
|---|---|
| Input | Query `url` |
| Output | `{host, url, results}`: at most 10 earlier scans, each `{uuid, time, url, ip, country, visibility, level, exact}` |
| Limits and errors | 400 for no key or an invalid URL; 502 when the search fails |
| Sends to the internet | Yes, to urlscan.io (see PRIVACY.md) |
| Called by | `frontend/js/urlscan.js` |

## DMARC

DMARC reports are read in the browser. The backend is asked only for the optional "geo (RDAP)" lookup of one source IP.

### `GET /api/dmarc/geo`

| Item | Detail |
|---|---|
| Input | Query `ip`, for example `?ip=198.51.100.4` |
| Output | `{status: "ok", country, organization, network_name, reverse_dns, known_sender}`, or `{status: "unavailable"}` |
| Limits and errors | 400 for an invalid or non-public IP (the message says "invalid") |
| Sends to the internet | Yes, DNS and RDAP queries (see PRIVACY.md) |
| Called by | `frontend/js/dmarc.js` |

## Logs

The Logs tab reads the daily log files that Seisa keeps.

### `GET /api/logs`

| Item | Detail |
|---|---|
| Input | Query `range`: `today` (default), `3d`, `week`, `month` or `all`. Query `service`: `all` or a service name |
| Output | List of `{time, level, service, message}`, newest first, at most 500 |
| Limits and errors | An unknown range means `today` |
| Sends to the internet | No |
| Called by | `frontend/js/logs.js` |

### `DELETE /api/logs`

| Item | Detail |
|---|---|
| Input | none |
| Output | `{deleted: n}` |
| Limits and errors | Deletes every `logs/*.jsonl` file, but not `launcher.log` |
| Sends to the internet | No |
| Called by | `frontend/js/logs.js` |

## Info, settings and limits

The Info tab shows what is configured, the API limits and the desktop icon, and it can stop the server.

### `GET /api/about`

| Item | Detail |
|---|---|
| Input | none |
| Output | `{services, llm, limits, changes, environment}`. `services` is a list of `{id, configured}` (never the key values). `llm` is `{configured, model}`. `changes` is a list of `{version, summary}`. `environment` is `{host, port, dotenv, os, python, fastapi}` |
| Limits and errors | `changes` is empty when git is not available |
| Sends to the internet | No (it runs `git log` locally) |
| Called by | `frontend/js/about.js` |

### `GET /api/about/icon`

| Item | Detail |
|---|---|
| Input | none |
| Output | The status of the desktop icon |
| Limits and errors | none |
| Sends to the internet | No |
| Called by | `frontend/js/about.js` |

### `POST /api/about/icon`

| Item | Detail |
|---|---|
| Input | none |
| Output | The result of installing the icon |
| Limits and errors | A refused install gives its own status (400 by default) and a translated message |
| Sends to the internet | No (it writes in your home folder) |
| Called by | `frontend/js/about.js` |

### `DELETE /api/about/icon`

| Item | Detail |
|---|---|
| Input | none |
| Output | The result of removing the icon |
| Limits and errors | As for installing |
| Sends to the internet | No |
| Called by | `frontend/js/about.js` |

### `POST /api/about/shutdown`

| Item | Detail |
|---|---|
| Input | none |
| Output | `{ok: true}`, then the server stops: a stop signal after 0.3 s and a hard exit 3 s later |
| Limits and errors | none |
| Sends to the internet | No |
| Called by | `frontend/js/shutdown.js` |

### `POST /api/about/limits/refresh`

| Item | Detail |
|---|---|
| Input | none |
| Output | `{limits, errors}`. `errors` maps a service to a short text: only a status or an exception type |
| Limits and errors | none |
| Sends to the internet | Yes, to the services that report their usage (see PRIVACY.md) |
| Called by | `frontend/js/about.js` |

## Themes

The colour themes are served to the page by two endpoints.

### `GET /api/themes`

| Item | Detail |
|---|---|
| Input | none |
| Output | List of themes `{id, name, base, order, ...}`, where `name` has `en` and `pl` |
| Limits and errors | none |
| Sends to the internet | No |
| Called by | `frontend/js/theme.js` |

### `GET /api/themes.css`

| Item | Detail |
|---|---|
| Input | none |
| Output | Generated CSS (`text/css`) |
| Limits and errors | Invalid theme files are skipped and logged |
| Sends to the internet | No |
| Called by | `frontend/index.html`, as a stylesheet |

## Static files

Everything outside `/api` is the web page itself. It is served from `frontend/`, with `index.html` for `/`. A missing file gives 404, and static files are never cached by the browser.

## Which tab calls what

Every call goes through `frontend/js/api.js`, which has one function per endpoint and sends `X-Seisa-Lang` and `Content-Type: application/json`. There are three direct exceptions: the theme list, the stylesheet `/api/themes.css` and the screenshot image. Besides the API, the browser loads `/i18n/<lang>.json` and, for the Email export, `/css/style.css`.

| Tab | Endpoints it uses |
|---|---|
| IP | `/api/lookup` |
| URLScan | `/api/urlscan/scan`, `/api/urlscan/result/{uuid}`, `/api/urlscan/screenshot/{uuid}`, `/api/urlscan/search`, `/api/history` |
| DMARC | `/api/dmarc/geo`, `/api/history` |
| Email | `/api/email/find`, `/api/email/analyze`, `/api/email/analyses` and its sub-paths |
| AbuseIPDB | `/api/abuseipdb/...` (all seven) |
| History | `/api/history` and its sub-paths, `/api/email/analyses/{analysis_id}` |
| Logs | `/api/logs` |
| Info | `/api/about` and its sub-paths |
| All tabs | `/api/themes`, `/api/themes.css` |

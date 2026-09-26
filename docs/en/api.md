# API reference

**English** | [Polski](../pl/api.md) · [Documentation index](index.md) · [README](../../README.md)

## API endpoints

All routes are under `/api`, answer JSON (errors as `{"detail": "..."}`) and read the language from the `X-Seisa-Lang` header. Routes marked SSE stream Server-Sent Events. The frontend is served from `/`.

| Method and path | Purpose | Calls out? |
|---|---|---|
| `POST /api/lookup` | reputation of one IP (or domain); the input is normalised first (URL, defanged form, `ip:port`), non-public addresses get 400 | intel services, DNS, WHOIS; the answer has `comparison` (earlier scans of the same indicator from the History) |
| `POST /api/lookup/batch` (SSE) | many indicators (normalised, duplicates dropped), with the VirusTotal throttle visible | intel services |
| `POST /api/urlscan/scan` | submit a URL scan (`url`, `visibility`, optional `country`, `useragent`) | urlscan.io |
| `GET /api/urlscan/result/{uuid}` | poll the result (`pending` or `done`) | urlscan.io |
| `GET /api/urlscan/screenshot/{uuid}` | the screenshot, served from your origin | urlscan.io |
| `GET /api/urlscan/search` | earlier scans of a domain | urlscan.io |
| `POST /api/email/find` | duplicate check by fingerprint | no (local) |
| `POST /api/email/analyze` (SSE) | streamed LLM analysis | OpenRouter (paid) |
| `POST /api/email/analyses/{id}/continue` (SSE) | finish a truncated analysis | OpenRouter (paid) |
| `POST /api/email/analyses/{id}/ask` (SSE) | a follow-up question | OpenRouter (paid) |
| `GET /api/email/analyses`, `GET` / `DELETE /api/email/analyses/{id}` | saved analyses | no (local) |
| `POST /api/abuseipdb/email/analyze` | facts, eligibility and the drafted comment | OpenRouter (optional, paid) |
| `GET /api/abuseipdb/categories` | the category table | no |
| `POST /api/abuseipdb/report/preview` | recompute the hard checks | no |
| `POST /api/abuseipdb/report/redact` | mask personal data in the comment | no |
| `GET /api/dmarc/geo` | RDAP country, owner and network name, reverse DNS name and (forward-confirmed) known sender of a source IP (DMARC tab, on click) | RDAP, DNS |
| `GET /api/abuseipdb/ip-info` | what AbuseIPDB already knows about an IP | AbuseIPDB |
| `POST /api/abuseipdb/report/submit` | send the report (re-validated, 409 within the 15-minute rule) | AbuseIPDB |
| `GET /api/abuseipdb/report/history` | the local log of sent reports | no |
| `GET /api/history`, `GET` / `PATCH` / `DELETE /api/history/{id}`, `POST /api/history`, `DELETE /api/history` | history (pin, delete, clear) | no |
| `GET /api/logs`, `DELETE /api/logs` | logs | no |
| `GET /api/about`, `POST /api/about/limits/refresh` | the Info tab, quota refresh | quota endpoints (on refresh) |

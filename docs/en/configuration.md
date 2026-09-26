# Configuration and limits

**English** | [Polski](../pl/configuration.md) · [Documentation index](index.md) · [README](../../README.md)

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
| `OPENROUTER_MODEL` | no | `anthropic/claude-sonnet-4.5` by default - verify the exact slug on the OpenRouter model list |

> **Warning:** the Cloudflare key **must be a scoped API Token with Radar read permission, not the old Global API Key** (the latter gives a 401 error).

A missing key for any service does not block the rest of the tool - the service simply shows the status "no API key" and is excluded from the aggregate score.

### Limits and throttling

| What | Limit | Notes |
|---|---|---|
| VirusTotal | 4 requests/min, 500/day | the daily counter (`data/vt_usage.json`) resets at 00:00 UTC |
| E-mail source | 3 million characters | |
| LLM answer | 64000 tokens | a ceiling that includes the model's hidden reasoning (about 45% of the output); you pay only for what is generated |
| AbuseIPDB report | one per IP per 15 minutes, comment up to 1024 characters, up to 30 categories | the 15-minute rule is enforced (HTTP 409) before a call is spent |
| History | 25 unpinned entries | pinned entries never fall out |
| Logs shown | newest 500 entries | |

The free-plan quotas of every keyed service (used / limit / reset) are in the [Info](tabs.md#info) tab, in the "API limits" card.

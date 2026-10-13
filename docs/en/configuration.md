# Configuration and limits

**English** | [Polski](../pl/configuration.md) · [Documentation index](index.md) · [README](../../README.md)

## Configuration

### API keys (.env)

The full `.env` keys table (every variable, whether it is required, where to get it), the Cloudflare Radar warning and what happens with a missing key are in the README's [API keys (.env)](../../README.md#api-keys-env) section - kept there as the single source of truth, since it is also what a first-time install needs to see before anything else. This page adds the limits each key is subject to, below.

### Limits and throttling

| What | Limit | Notes |
|---|---|---|
| VirusTotal | 4 requests/min, 500/day | the daily counter (`data/vt_usage.json`) resets at 00:00 UTC |
| E-mail source | 3 million characters | |
| LLM answer | 64000 tokens | a ceiling that includes the model's hidden reasoning (about 45% of the output); you pay only for what is generated |
| AbuseIPDB report | one per IP per 15 minutes, comment up to 1024 characters, up to 30 categories | the 15-minute rule is enforced (HTTP 409) before a call is spent |
| History | 100 unpinned entries | pinned entries never fall out |
| Logs shown | newest 500 entries | log files older than 30 days are deleted automatically |

The free-plan quotas of every keyed service (used / limit / reset) are in the [Info](tabs.md#info) tab, in the "API limits" card.

### Desktop icon (optional)

The "Add icon" button (Info > Settings) needs a graphical session: macOS with its own tools `sips` and `iconutil` (both ship with the system), or a Linux desktop (`DISPLAY` or `WAYLAND_DISPLAY` set in the environment Seisa runs in) and `curl` for the launcher. The icon starts Seisa on port 54321 only. The output of a server started by the icon goes to `logs/launcher.log`. See [Info](tabs.md#info).

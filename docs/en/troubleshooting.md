# Troubleshooting

**English** | [Polski](../pl/troubleshooting.md) · [Documentation index](index.md) · [README](../../README.md)

## Troubleshooting and FAQ

**A service shows "no API key".** The key is missing or misspelled in `.env`. Restart Seisa after editing it. The Info tab shows which keys are set (never their values).

**Cloudflare Radar answers 401.** The key is probably the old Global API Key. Create a scoped API Token with Radar read permission.

**An OpenRouter call fails.** Open the [Logs](tabs.md#logs) tab and look at the `open_router` entries (limits, insufficient credits, provider errors, timeouts). Also verify the exact model slug (`OPENROUTER_MODEL`) on the current OpenRouter model list.

**The LLM analysis stops in the middle.** The response limit was reached. Click "Finish the analysis": the model gets the text so far and writes the missing parts.

**A batch lookup is slow.** VirusTotal's free plan allows 4 requests a minute; the throttle is visible in the batch progress.

**The browser shows "Invalid host header".** Seisa accepts only `127.0.0.1` and `localhost` as the host name (protection against DNS rebinding). Open `http://127.0.0.1:54321`.

**An API call answers 403 "request from another web page blocked".** The origin guard refuses `/api/` requests that carry `Sec-Fetch-Site: cross-site`/`same-site` or an `Origin` that is not `127.0.0.1`/`localhost`, for example from a browser extension or a page served from another port. Use the Seisa page itself, or call the API from a script that sends no `Origin` header (curl).

**Port 54321 is already in use.** Start `uvicorn` yourself with another `--port` (see [Install and run](../../README.md#install-and-run)).

**The browser did not open (Linux without a desktop).** The start script then only prints the address; open it by hand.

**`seisa.sh` says `.venv/` is missing.** Run the install steps in [Install and run](../../README.md#install-and-run) first.

**Saved analyses and logs vanished after an upgrade from a release before 2.0.27.** The directories were renamed; see [Data files](architecture.md#data-files).

**Why is there no "open the service website" button for WHOIS/rDNS?** It is a direct protocol query without a single external service to link to.

**Does Seisa run on Windows?** Not natively; it works through WSL as Linux.

**Where are my data and how do I reset Seisa?** In `data/` and `logs/` (see [Data files](architecture.md#data-files)); stop Seisa and delete their contents.

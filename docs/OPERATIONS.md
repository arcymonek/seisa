**English** | [Polski](pl/OPERATIONS.md)

# Installing and running Seisa

This guide is for the person who installs Seisa and keeps it running, even if you have never installed a program from the terminal before. In one sentence: Seisa runs only on your own computer, so "installing" means putting its folder on your disk and starting it with one command.

## Contents

- [1. Requirements](#1-requirements)
- [2. Installation step by step](#2-installation-step-by-step)
  - [With the installer](#with-the-installer)
  - [By hand](#by-hand)
  - [Exact tested versions](#exact-tested-versions)
  - [API keys](#api-keys)
- [3. Starting Seisa](#3-starting-seisa)
  - [The application icon](#the-application-icon)
- [4. Stopping Seisa](#4-stopping-seisa)
- [5. Updating](#5-updating)
- [6. Limits and throttling](#6-limits-and-throttling)
- [7. Where your data is](#7-where-your-data-is)
  - [Backing up](#backing-up)
  - [Deleting data](#deleting-data)
  - [History migration](#history-migration)
- [8. Uninstalling](#8-uninstalling)
- [9. Troubleshooting and FAQ](#9-troubleshooting-and-faq)
  - [Starting](#starting)
  - [Keys and services](#keys-and-services)
  - [IP, URLScan and DMARC tabs](#ip-urlscan-and-dmarc-tabs)
  - [Email and AbuseIPDB tabs](#email-and-abuseipdb-tabs)
  - [Icon, Info and History](#icon-info-and-history)
  - [Common questions](#common-questions)

## 1. Requirements

This section lists what your computer needs before you start. A "terminal" is the text window where you type commands (on macOS the Terminal app, on Linux your terminal program).

- **System:** macOS or Linux. The start scripts are Bash scripts. Windows is not supported directly; it may work through WSL (the Windows Subsystem for Linux, a Linux inside Windows), but this has not been tested.
- **Python 3.11 or newer.** Seisa is tested on Python 3.11 and on the newest 3.x. Check yours with `python3 --version`. If it is older or missing, install a current Python: on macOS with the installer from python.org (the Python that comes with Apple's developer tools has been 3.9, which is too old), on Linux with your package manager. Debian 12 and Ubuntu 24.04 already have a new enough one; Ubuntu 22.04 has 3.10, which is too old. On Debian and Ubuntu you also need the package `python3-venv`. The installer in section 2 stops with this advice when it finds no suitable Python.
- **A modern web browser.** The DMARC tab unpacks `.gz` and `.zip` reports with the browser's own built-in tools.
- **Git (optional).** It is the easiest way to download and later update Seisa. Without it you can download a ZIP file.
- **Port 54321 free.** Seisa listens on `127.0.0.1` (this computer only), port 54321. The port is fixed in the start scripts.

Seisa needs no server, no database and no account. Its Python packages are FastAPI, Uvicorn, Pydantic, pydantic-settings, httpx, python-whois and dnspython; the installation below fetches them for you.

## 2. Installation step by step

You do the installation once. There are two ways: the installer, which does all the steps for you (recommended), and the same steps by hand.

### With the installer

Run each command in the terminal, one at a time, and wait for it to finish before you type the next one.

1. Download Seisa. This copies the project into a new folder named `seisa`:

   ```bash
   git clone https://github.com/arcymonek/seisa.git
   ```

   Without Git, download the ZIP file from the same page on GitHub and unpack it instead.

2. Go into the Seisa folder (for a ZIP, the unpacked folder). All the following commands are run from here:

   ```bash
   cd seisa
   ```

3. Run the installer:

   ```bash
   bash install.sh
   ```

4. Start Seisa (see [3. Starting Seisa](#3-starting-seisa)):

   ```bash
   ./seisa.sh
   ```

If step 4 answers "permission denied" (a ZIP download may lose the "executable" mark), start it with `bash seisa.sh` instead.

The installer does these things:

- It looks for Python 3.11 or newer on your `PATH` (the list of folders where the terminal looks for programs), preferring the versions that the libraries support best (3.13 and 3.12). If it finds none, it changes nothing and tells you what to install. Install it, open a new terminal window and run the installer again. To use a Python that is not on the `PATH`, run `SEISA_PYTHON=/path/to/python3 bash install.sh`.
- It creates the `.venv` folder and installs `requirements.lock` into it. If that exact set does not install, it tries `requirements.txt`.
- It creates `.env` from the template, readable by your user account only, or keeps the `.env` you already have.
- It asks whether to add the application icon (see [The application icon](#the-application-icon)), but only in a terminal where you can answer. `--icon` says yes and `--no-icon` says no, without asking.
- It never uses `sudo`, refuses to run with it (everything it makes must belong to you), and downloads nothing except the libraries, which `pip` fetches from the Python Package Index (PyPI).

It is safe to run again: it keeps your `.env` and `data/` and brings the libraries up to date.

After the first start, enter your API keys in the Info tab, in the "API keys" card (see [API keys](#api-keys)).

### By hand

These are the steps that the installer performs. Use them if you want to see each step yourself, or if the installer does not work on your computer. Run each command in the terminal, one at a time, and wait for it to finish before you type the next one.

1. Download Seisa. This copies the project into a new folder named `seisa`:

   ```bash
   git clone https://github.com/arcymonek/seisa.git
   ```

   Without Git, download the ZIP file from the same page on GitHub and unpack it instead.

2. Go into the Seisa folder. All the following commands are run from here:

   ```bash
   cd seisa
   ```

3. Create a private Python environment in the `.venv` folder. It keeps Seisa's packages apart from the rest of your system:

   ```bash
   python3 -m venv .venv
   ```

4. Install Seisa's packages into that environment:

   ```bash
   .venv/bin/pip install -r requirements.txt
   ```

5. Create your settings file from the template. The copy is named `.env`, and you fill it with your API keys later. The second command makes the file readable only by your user account, because it will hold your keys:

   ```bash
   cp .env.example .env
   chmod 600 .env
   ```

6. Start Seisa (see [3. Starting Seisa](#3-starting-seisa)):

   ```bash
   ./seisa.sh
   ```

If step 6 answers "permission denied" (a ZIP download may lose the "executable" mark), start it with `bash seisa.sh` instead.

The scripts look for `.venv/bin/uvicorn`. If the `.venv` folder is missing, they stop and tell you that Seisa is not installed yet.

The `.env` file, the `data/` folder and the `logs/` folder are excluded from git, so your keys and your data never end up in a commit.

### Exact tested versions

`requirements.txt` gives only minimum versions of the packages. `requirements.lock` is the exact set that the release was tested with. The installer tries it first and falls back to `requirements.txt`. By hand, `requirements.txt` is the normal choice; if something does not work with it, use the exact set instead:

```bash
.venv/bin/pip install -r requirements.lock
```

### API keys

An API key is a long password that a service gives you so it knows who is asking. Seisa works without any key, but each key switches on one more source. The full table of keys (name, where to get it, what it enables) is in the [README](../README.md); what works without which key is in [USER_GUIDE.md](USER_GUIDE.md#4-api-keys-what-works-without-them).

- The easiest way: start Seisa, open the Info tab and paste each key in the "API keys" card, then click "Save keys". Seisa writes the keys into `.env` for you (readable only by your user account) and uses them at once. A key can also be removed there.
- Or open the `.env` file in any text editor and paste each value after the `=` sign. Leave a key empty if you do not use that service.
- Seisa reads `.env` when it starts. After you change the file by hand, stop Seisa and start it again. Changes made in the Info tab need no restart.
- A setting that is also exported in your shell (for example `export OTX_API_KEY=...`) wins over the file; the Info tab then says so and does not change it.
- Without a `.env` file Seisa still starts. The Info tab then shows ".env file: missing (integrations with keys are off)".
- `OPENROUTER_MODEL` chooses the language model (the default is `anthropic/claude-sonnet-4.5`). Seisa does not check the model name; OpenRouter does.

## 3. Starting Seisa

Starting means running one script and leaving its terminal window open. From the Seisa folder:

```bash
./seisa.sh
```

- The script starts the server and, about 1.5 seconds later, opens `http://127.0.0.1:54321` in your browser (on macOS with `open`, on Linux with a desktop with `xdg-open`). If it cannot open a browser, it prints the address; type it into your browser yourself.
- The terminal window stays busy for as long as Seisa runs. Closing it, or pressing Ctrl+C in it, stops Seisa.
- Seisa has no login, because only your own computer can reach it.

### The application icon

If you do not want to open a terminal every time, Seisa can make a clickable icon. Nothing is created until you ask for it.

1. Open the Info tab and find the "Application icon" row in "Settings".
2. Click "Add icon". The row shows "Icon added."
3. Click the new icon to open Seisa. If Seisa is already running, the icon only opens it in the browser. If not, the icon starts it in the background first.

You can do the same from the terminal, in the Seisa folder:

```bash
.venv/bin/python -m backend.desktop_icon install
```

The other two words are `status` (shows the state) and `remove` (takes the icon away).

- **macOS:** the icon is a small app named `Seisa.app` in your `~/Applications` folder. It needs the system tools `sips` and `iconutil`.
- **Linux:** the icon is a menu entry named `seisa.desktop` in `~/.local/share/applications`. It needs a graphical session.
- **Dock or panel:** pinning the icon there is up to you. Seisa never changes the Dock or the panel; the Info tab shows how.
- **Log:** when the icon starts Seisa, the output goes to `logs/launcher.log`. The file is overwritten at each such start.
- **Start problems:** if the icon cannot start Seisa (for example `.venv` is missing), it shows a dialog on macOS or a notification on Linux with the reason.

The row in Settings can show these states:

| State | What it means | What to do |
|---|---|---|
| not added | No icon yet. | Click "Add icon" if you want one. |
| added | The icon exists and points to this Seisa folder. | Nothing. |
| made for a different Seisa folder or its launcher is gone | You moved or renamed the Seisa folder. | Click "Add icon" again. |
| a file with this name that Seisa did not make already exists | Another file occupies the name. | Seisa leaves it untouched. Remove or rename that file yourself. |
| not available here | The system is not macOS or Linux, or there is no graphical session. | Start Seisa with `./seisa.sh`. |

Seisa only replaces or removes an icon that carries its own marker, so a `Seisa.app` or `seisa.desktop` that you made yourself is never touched.

## 4. Stopping Seisa

You can stop Seisa in three ways, and all of them are safe for your data.

- **"Shut down Seisa"** in the footer or in the Info tab (Settings, "Server"). Seisa asks first unless you ticked "Do not ask again". You can turn the question back on with "Ask before shutting down". The tab shows "Seisa has been stopped" and you can close it.
- **Ctrl+C** in the terminal where `./seisa.sh` runs.
- **Closing that terminal window.**

A running analysis is cut after a few seconds at most, and what you typed but did not save is lost. Data files are never left half-written, because Seisa writes each file to a temporary name first and renames it afterwards.

To start again, use the icon or `./seisa.sh`.

## 5. Updating

Seisa has no automatic update and never checks for new versions. You update it by hand, and your data is kept.

1. Stop Seisa (section 4).
2. In the Seisa folder, download the newest version:

   ```bash
   git pull
   ```

3. Run the installer again. It keeps your `.env` and `data/` and installs the packages of the new version (`--no-icon` skips the question about the icon):

   ```bash
   bash install.sh --no-icon
   ```

4. Start Seisa again. A normal reload of the page shows the new interface, because Seisa tells the browser not to keep old copies of its files.

If you downloaded a ZIP, download the new ZIP, unpack it, and copy your `.env` file and your `data/` folder into the new Seisa folder. Then repeat steps 3 and 4 there; the installer builds a new `.venv` for the new folder. If you used the application icon, click "Add icon" again, because the old icon points to the old folder.

- The Info tab shows the version you are running and, in a git checkout, the 10 most recent releases under "Recent changes". After a ZIP install that card is empty: "The change log is available only when Seisa runs from a git checkout."
- Data from older versions is kept. An e-mail analysis saved by an older version still opens; if today's code reads its facts differently, the tab says so.

## 6. Limits and throttling

This section lists the limits that apply while you work. Some are rules of the outside services, some are Seisa's own.

| Where | Limit |
|---|---|
| VirusTotal | Seisa allows 4 requests per minute (extra requests wait) and 500 per day (the day resets at 00:00 UTC). These are the free public limits. |
| AbuseIPDB, reports | The same IP can be reported again only after 15 minutes. The daily report limit comes from AbuseIPDB and appears after the first report. |
| AbuseIPDB, content | Activity at most 60 days old, at most 30 categories, a comment of at most 1,024 characters. |
| Other services | Seisa does not throttle them. The Info tab compares your use with assumed free-plan limits: AbuseIPDB 5,000 a day, GreyNoise 50 a week, AlienVault OTX 10,000 an hour, Cloudflare 1,200 per 5 minutes. |
| E-mail source | Up to 3,000,000 characters. The language model receives at most 120,000 of them. |
| IP or domain | Up to 253 characters. |
| URL to scan | Up to 2,048 characters, up to 5 URLs at once, a custom user agent up to 250 characters. |
| History | 100 unpinned IP checks, URL scans and DMARC imports. Saved e-mail analyses and AbuseIPDB reports are not counted. |
| Logs | Kept for 30 days. |

The Info tab shows how much of each service's quota you have used. VirusTotal, urlscan.io and OpenRouter report their real quota when you click "Refresh limits". AbuseIPDB and Cloudflare are read from the answers Seisa already received. GreyNoise and AlienVault OTX are counted by Seisa, so requests made outside Seisa are not seen there. Free-plan limits of the services can change; treat the numbers for other services as Seisa's assumptions.

How long Seisa waits:

| Service | Waiting time |
|---|---|
| Most services | 20 seconds per request |
| AbuseIPDB | 30 seconds |
| WHOIS | 15 seconds |
| DNS | 5 seconds |
| OpenRouter | Up to 120 s without any answer, then Seisa stops waiting |
| A URL scan result | Up to 2 minutes |

## 7. Where your data is

Everything Seisa keeps lives in two folders inside the Seisa folder, `data/` and `logs/`. Besides them there are the application icon (outside the folder) and a few small settings in your browser. Nothing is sent to the author.

| Where | What it holds | How long it stays | Delete it from the interface |
|---|---|---|---|
| `data/history/` | History: `index.json` (the list) and `entries/<id>.json` (one file per IP check, URL scan or DMARC import) | Until you delete it; the unpinned part is capped at 100 entries | Yes ("Delete", "Clear history") |
| `data/analyses/` | Saved e-mail analyses, one file each, together with the raw e-mail (personal data) | Until you delete them | Yes (each analysis with its e-mail) |
| `data/report_log.json` | Every AbuseIPDB report attempt, accepted and failed | Without a limit | No |
| `data/vt_usage.json` | Today's VirusTotal request count | Today | No |
| `data/api_usage.json` | API usage counters (8 days) and the latest rate-limit answers | Cleans itself after 8 days | No |
| `logs/YYYY-MM-DD.jsonl` | One day of errors and warnings | 30 days | Yes ("Clear logs") |
| `logs/launcher.log` | Output of the last start from the icon, including the server's request lines, which name looked-up addresses | Until the next start from the icon | No |
| Your browser | Language, theme, "ask before shutting down", URLScan options, the open Email pane, lesson cards | Until you clear this site's data | - |

- Files are readable only by your own user account: data files have mode 0600, and the `history`, `analyses` and `logs` folders mode 0700.
- Every file is written to a temporary file first and then renamed, so a crash never leaves a half-written file.
- The browser settings belong to the address `127.0.0.1`; deleting that site's data in your browser clears them.
- The privacy side of this table (what could leak and what protects it) is in [PRIVACY.md](PRIVACY.md).

### Backing up

A backup is a copy of your data that you keep somewhere else. Stop Seisa first, then copy the `data/` folder and, if you want to keep your keys, the `.env` file. `logs/` is optional.

```bash
cp -R data ~/seisa-data-backup
```

This copies the `data/` folder into a new folder in your home directory; change the name and place as you like. Keep in mind that the copy holds raw e-mails and, with `.env`, your keys, so store it somewhere private.

To restore, stop Seisa and copy the saved folder back in the same way.

### Deleting data

From the interface you can delete: single History entries and the whole unpinned History, each saved e-mail analysis (together with its e-mail), and all daily log files. The buttons are described in [USER_GUIDE.md](USER_GUIDE.md).

Three things cannot be deleted from the interface: the AbuseIPDB report log, the API usage counters and `logs/launcher.log`. Stop Seisa and delete the files by hand, in the Seisa folder:

```bash
rm logs/launcher.log
```

This removes the launcher log. The same pattern works for `data/report_log.json`, but read this first: deleting it also removes Seisa's own protection against reporting the same IP twice within 15 minutes, and the "already reported" hints. The usage counters clean themselves after 8 days, so you do not need to remove them.

### History migration

Older versions kept History in one file, `data/history.json`. On first use Seisa moves its entries into the `data/history/` folder and renames the old file to `history.json.migrated`. It never deletes it. If the migration fails, the old file stays untouched and the Logs tab says so (see [9. Troubleshooting and FAQ](#icon-info-and-history)).

## 8. Uninstalling

Removing Seisa means deleting its folder, but the icon lives outside it, so take that away first.

1. Remove the application icon: Info, Settings, "Remove icon" (or `.venv/bin/python -m backend.desktop_icon remove` in the Seisa folder).
2. Stop Seisa (section 4).
3. Make a backup if you want to keep anything (section 7). The next step erases the program, `.venv`, `.env`, `data/` and `logs/`.
4. Delete the Seisa folder. Do it in your file manager, or from the folder above it:

   ```bash
   rm -r seisa
   ```

5. Optionally clear the site data of `127.0.0.1` in your browser to remove the small settings Seisa kept there.

## 9. Troubleshooting and FAQ

Each table below follows the same order: what you see, why it happens, what to do. Messages are quoted as Seisa shows them in English. `{x}` stands for a value that Seisa fills in (in the limit messages, {limit} is a number such as 15). The messages of the start script and of the installer are in English only. Errors from the services also appear in the Logs tab.

### Starting

| What you see | Why | What to do |
|---|---|---|
| "Seisa is not installed yet: .venv/ is missing." | You started Seisa (script or icon) before installing it, or from the wrong folder. | Do the installation (section 2) in the Seisa folder, then start again. |
| An error about the address being already in use (the exact words come from Uvicorn) | Port 54321 is taken, often because Seisa is already running. | Open `http://127.0.0.1:54321`. If another program holds the port, close it. |
| `./seisa.sh` says "permission denied" | The file lost its "executable" mark, for example after a ZIP download. | Run `bash seisa.sh`. |
| The browser did not open | No desktop session, or no browser tool found. | Type `http://127.0.0.1:54321` into your browser. |
| The installer says "It needs Python 3.11 or newer, and none was found on this computer." | No Python, or only an older one, is on your `PATH`. | Install Python as the message says, open a new terminal window and run `bash install.sh` again. For a Python outside the `PATH`: `SEISA_PYTHON=/path/to/python3 bash install.sh`. |
| The installer says "Do not run the installer with sudo or as root." | You started it with `sudo` or as the root user. | Run `bash install.sh` as your own user, without `sudo`. |
| The installer says "could not create a virtual environment" | On Debian and Ubuntu the package `python3-venv` is usually missing. | Run `sudo apt install python3-venv`, then `bash install.sh` again. |
| The installer says ".venv exists but holds no working Python 3.11 or newer." | An old or broken `.venv`, for example after a Python upgrade. | Rename or delete the folder `.venv` and run `bash install.sh` again. Your `.env` and `data/` are not touched. |
| The installer says "The libraries could not be installed." | No internet connection, a proxy or firewall blocks PyPI, or your Python is so new that the libraries have no ready-made files for it yet (the messages then mention compiling). | Check the connection and run `bash install.sh` again. For a too-new Python, delete the folder `.venv` and use an older one: `SEISA_PYTHON=/path/to/python3.12 bash install.sh`. |

### Keys and services

| What you see | Why | What to do |
|---|---|---|
| "no API key" on a service card | The key for that service is missing. | Add the key in the Info tab ("API keys") or in `.env`; after a change in `.env` restart Seisa. |
| "no API key (URLSCAN_API_KEY)" | You clicked "Scan" or the History search in URLScan without a key. | Add `URLSCAN_API_KEY` in the Info tab or in `.env` (restart Seisa after a change in the file). |
| "error" with "HTTP 401: ..." on a service card | The service refused the key: it is wrong, expired, or lacks permission. For Cloudflare Radar, check that the token may read Radar data (general knowledge about the service, not checked by Seisa). | Check the key in the service's own dashboard. |
| "VirusTotal daily limit exceeded (500/day)" | The 500 requests of the UTC day are used. | Wait until 00:00 UTC. The other sources keep working. |
| "GreyNoise search limit of your plan is used up - it resets on {date}. The score is computed without this source." | The weekly GreyNoise limit is used. | Wait for the date. The result is computed without GreyNoise. |
| "limit exceeded" badge in Info | The service answered with HTTP 429. | Wait until the reset time shown in the badge's tooltip. The badge disappears after the next successful answer. |

### IP, URLScan and DMARC tabs

| What you see | Why | What to do |
|---|---|---|
| "Select at least one service." | Every service is switched off in the IP tab. | Tick at least one. |
| "{indicator} is not a public IP address (private, loopback, reserved or documentation range) - the reputation services know nothing about it" | You entered a private or reserved address. | Nothing is wrong: public services know nothing about such addresses. |
| "not a valid IP address or domain name: {indicator}" | A typo or forbidden characters. | Correct the entry. |
| "only http:// and https:// addresses can be scanned" | The URL starts with something else. | Use an `http://` or `https://` address. |
| "urlscan.io scans only public internet hosts; "{host}" is a local or private address" | The URL points to your own network. | Scan only public addresses. |
| "the URL is too long (the limit is {limit} characters)" | The URL is longer than 2,048 characters. | Shorten it. |
| "The scan is still running after {time} - check manually" | urlscan.io did not finish within 2 minutes. | Use "Open in urlscan.io", or "Load full report" later. |
| "this browser cannot unpack archives - unpack the file and load the .xml" | An old browser cannot open `.gz` or `.zip`. | Unpack the file yourself and load the `.xml`. |
| "the unpacked report is too large" | The archive expands to far more than a normal report. | Check the file. Do not load files you do not trust. |
| "no .xml report inside the archive" | The archive holds no `.xml` file. | Check that it is a DMARC report. |

### Email and AbuseIPDB tabs

| What you see | Why | What to do |
|---|---|---|
| "No OpenRouter key (OPENROUTER_API_KEY in .env) - showing the deterministic analysis only." | There is no OpenRouter key. | Add the key in the Info tab or in `.env` (restart Seisa after a change in the file), or use the analysis without the model. |
| "invalid OpenRouter API key" | OpenRouter refused the key (HTTP 401). | Check the key. |
| "insufficient OpenRouter credits or the credit limit was exceeded" | The OpenRouter account has no credit (HTTP 402). | Top up the credit. |
| "rate limit reached" | OpenRouter limits you (HTTP 429). | Wait and try again. |
| "the model or provider is unavailable" / "no provider available for the model" | HTTP 502 or 503 from OpenRouter. | Try later, or change `OPENROUTER_MODEL`. |
| "OpenRouter sent nothing for 120 s, so Seisa stopped waiting ..." | The model is very slow or the service is overloaded. | Try again, or choose a faster model in `OPENROUTER_MODEL`. |
| "the model refused to analyse this message (its safety filter blocked the answer ...)" | The model's own safety filter. It is not a Seisa error. | Retrying does not help; try another model in `OPENROUTER_MODEL`. |
| "The analysis was cut off by the response length limit - its final parts are missing." | The model's answer was truncated. | Click "Finish the analysis" (paid). |
| "The source is too large ({size} characters, limit {limit})." | The e-mail is over 3,000,000 characters, in the Email or AbuseIPDB tab. | Remove large attachments from the source. |
| "the AbuseIPDB daily report limit ({limit}) is used up - reports are accepted again from {when}" | The daily limit of reports is used. | Wait until the given time. |
| "this IP was reported less than {limit} minutes ago ..." or "AbuseIPDB refused the report: the same IP can be reported by one account only once in {limit} minutes ..." | The 15-minute rule. | Wait. |
| "AbuseIPDB rejected the API key (missing, wrong or without the right to report) - check ABUSEIPDB_API_KEY in .env" | The key is wrong or may not report. | Correct the key in the Info tab or in `.env` (restart Seisa after a change in the file). |
| "AbuseIPDB rejected the report data: {message}" | AbuseIPDB refused the content (HTTP 422). | Read the message and fix the form. |
| "the attack is {days} days old (limit 60)" or "the attack date is in the future" | The attack time is outside the allowed range. | A report older than 60 days is impossible; otherwise correct the date. |

### Icon, Info and History

| What you see | Why | What to do |
|---|---|---|
| "an application icon is supported on macOS and Linux only" | Another system. | Start Seisa with `./seisa.sh`. |
| "no graphical session found (DISPLAY / WAYLAND_DISPLAY is not set), so there is no menu to put an icon in" | Linux without a desktop session. | Make the icon from a desktop session, or use `./seisa.sh`. |
| "the macOS tools sips and iconutil are missing, so the icon cannot be made" | The system tools are missing. | Use `./seisa.sh`. |
| "{path} already exists and was not made by Seisa, so it was left untouched" | A foreign file has the name. | Remove or rename that file yourself, then click "Add icon". |
| Recent changes is empty | Seisa runs from a ZIP download, not from git. | Normal. |
| Old History entries are missing after an update | The migration of `history.json` failed. | Look in the Logs tab for "history.json could not be read". The old file `data/history.json` stays untouched. |
| Entries from "OpenRouter", "WHOIS" or "DNS" in Logs | A service failed. | Usually temporary; try again later. |
| "request from another web page blocked" | Another web page tried to call Seisa; Seisa's protection stopped it. | Use Seisa only from its own tab. |
| "internal Seisa error" | An unexpected error inside Seisa. | Look in the Logs tab and report it as described in [CONTRIBUTING.md](../CONTRIBUTING.md). |

### Common questions

| Question | Answer |
|---|---|
| Does Seisa work without any key? | Yes. Some sources need no key, and "Analyze without LLM" sends nothing off your computer. See [USER_GUIDE.md](USER_GUIDE.md#4-api-keys-what-works-without-them). |
| Does Seisa update itself? | No. You update it by hand (section 5). |
| What leaves my computer? | Only what you trigger by a click, with one exception: the AbuseIPDB tab looks up the address in its form by itself. The full list is in [PRIVACY.md](PRIVACY.md). |
| Can I move Seisa to another computer? | Install it there, then copy your `data/` folder and `.env` file into the new Seisa folder. |
| Can I change the port? | Not by a setting. The port is written in `seisa.sh` and `seisa-launcher.sh`; changing it means editing both scripts. |
| I think I found a bug. | Look in the Logs tab and see [CONTRIBUTING.md](../CONTRIBUTING.md). For a security problem use [SECURITY.md](../SECURITY.md). |

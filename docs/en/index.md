# Seisa documentation

**English** | [Polski](../pl/index.md) · [Documentation index](index.md) · [README](../../README.md)

This is the full documentation of Seisa; the [README](../../README.md) is the short entry point (what Seisa is, quick start, keys, privacy overview).

## Contents

- [Tabs and walkthrough](tabs.md) - every tab in detail (IP, URLScan, DMARC, Email, AbuseIPDB, History, Logs, Info, interface language) and a walkthrough from a suspicious e-mail to a report
- [Configuration and limits](configuration.md) - the `.env` keys and where to get them, limits and throttling
- [Privacy, threat model and security](privacy-and-security.md) - the full data flow (what leaves the machine, what stays local), the threat model, the LLM cost, the security invariants
- [Architecture and design](architecture.md) - design decisions and non-goals, the stack, the architecture and the file tree, the data files
- [API reference](api.md) - the backend endpoints
- [Forking and extending](extending.md) - should you fork, how to add a threat-intel service, a language or a tab, workflow, tests and conventions
- [Troubleshooting](troubleshooting.md) - common problems and the FAQ

## Prompt context files

The two files directly in `docs/` are **not documentation**: [abuseipdb-reporting-policy.md](../abuseipdb-reporting-policy.md) and [email-analysis-guide.md](../email-analysis-guide.md) are English prompt context loaded into the LLM by name (`backend/config.py`). Do not move or rename them.

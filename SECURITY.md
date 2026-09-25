# Security policy

Seisa is a local, single-user tool: it listens only on `127.0.0.1`, has no login and is not meant to be exposed to a network. Vulnerabilities that matter here are, for example, ways for a web page, an e-mail, a DMARC report or a response of a third-party API to run code in the interface, to read or change local data (`data/`, `logs/`, `.env`) or to make the tool send requests the user did not ask for.

## Reporting a vulnerability

Please report it **privately**, not as a public issue:

- use GitHub's private vulnerability reporting (the **Security** tab of the repository, "Report a vulnerability"), or
- write to the author: kontakt (at) arkadiuszpolak (dot) pl.

Describe what you found, how to reproduce it and which Seisa version it affects (shown in the page header). Do not include real API keys, the contents of `.env` or private e-mails; anonymised examples are enough. I will answer as soon as I can and credit you in the fix if you wish.

## Supported versions

Only the latest release is supported.

**English** | [Polski](docs/pl/SECURITY.md)

# Security policy

If you find a security weakness in Seisa, please tell us privately first, so it can be fixed before it is public. This page explains how to report it, what to include and what to expect.

## Reporting a vulnerability

Please do not open a public issue for a vulnerability. Use one of these ways instead:

- **GitHub.** Use "Report a vulnerability" on the Security tab of the repository (`https://github.com/arcymonek/seisa/security/advisories/new`). Only you and the maintainer can see the report.
- **E-mail.** Write to `github@arkadiuszpolak.pl`.

The issue templates of the repository point security reports to this page.

## What to include

A short, clear report is enough. It helps to include:

- what you found and why it matters;
- the steps to reproduce it, and the Seisa version shown in the Info tab;
- what you expected and what happened instead.

Please do not include real API keys, your `.env` file, raw e-mails or files from `data/` or `logs/`. Use reserved example data instead, such as `203.0.113.7`, `198.51.100.0/24`, `2001:db8::1` and `example.org`.

## Response

You will get a first answer within 7 days. If a fix is needed, we will tell you when to expect it. If you wish, we will credit you in the `CHANGELOG.md` entry of the release that contains the fix. If you prefer not to be named, say so.

## Supported versions

Only the latest version on the `main` branch gets fixes. There are no maintained release branches, so please check that the problem still exists on the current `main` before you report it.

## What is not a vulnerability

Seisa is a local tool for one person, and some things are deliberate. These are not treated as vulnerabilities:

- **Anything that needs access to your computer or user account.** Other local programs and users can call the API on `127.0.0.1` without a password, and can read `.env` and `data/`.
- **Requests without `Origin` and `Sec-Fetch-Site`.** Tools such as curl and scripts are accepted. The cross-site guard protects against web pages, it is not a login.
- **Data you chose to send to a service** being visible to that service.
- **A language model giving a wrong or manipulated explanation**, as long as it does not change a security fact, the form or a report.
- **`style-src 'unsafe-inline'` in the Content-Security-Policy.** The interface uses `style=` attributes. Scripts are still allowed from `'self'` only.
- **No HTTPS on `127.0.0.1`.** The traffic never leaves your computer.

These are in scope, and we want to hear about them:

- a way for another web page to read or change Seisa's data, or to trigger an outgoing request;
- script execution caused by e-mail, DMARC, scan or service content;
- a report sent without the hard checks or without the user's click;
- a key leaking into a response, a log or an export;
- writing outside `data/`, `logs/` or the desktop icon paths;
- a language model changing a security fact, the form or a send.

## Security design

How Seisa protects itself, and what it does not protect against, is described in [PRIVACY.md](docs/PRIVACY.md) (sections "Safeguards" and "Threat model").

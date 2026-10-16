#!/usr/bin/env python3
"""API harness: exercises every endpoint of Seisa with ALL external services mocked, and checks the results.

Usage: python3 scripts/api_harness.py [--root DIR] [--out FILE] [--serve PORT]

- httpx.AsyncClient is forced onto an httpx.MockTransport; any unknown host raises (proof nothing leaves the box).
- socket connect / reverse DNS / whois are patched; the real network is never touched.
- API keys come from the environment (fake values) - they take precedence over the real .env in pydantic-settings.
- data/ and logs/ paths are redirected to a temp dir, the user's data is not touched.
- The mock API answers contain HTML/script payloads, so the harness also proves that the server side stays
  well-behaved with hostile third-party data (the browser side is checked by hand: window.__xss must stay 0).

`--serve PORT` does not run the checks but serves the whole application on 127.0.0.1:PORT with the same mocks and a
temporary data directory - for trying the interface by hand without real API keys or traffic.

It exits with 1 when an endpoint answers with an unexpected status, when a request left the mocks, or when a
security probe (foreign Host header, cross-site requests, CSP header, path injection) fails. `--out` writes the normalised answers
(ids, timestamps and the version number masked), so two versions of the code can be compared with `--root` pointing at
an older checkout (`git archive`) and `diff`: refactors must not change the answers.
"""
import argparse
import atexit
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import time
from datetime import timedelta, timezone
from pathlib import Path

_ap = argparse.ArgumentParser()
_ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent), help="checkout to test (default: this one)")
_ap.add_argument("--out", default=None, help="write the normalised answers to this JSON file")
_ap.add_argument("--serve", type=int, default=None, help="serve the mocked application on this port instead of testing")
_args = _ap.parse_args()
ROOT = Path(_args.root).resolve()
OUT = Path(_args.out) if _args.out else None
sys.path.insert(0, str(ROOT))

for k in ("URLSCAN", "VIRUSTOTAL", "OTX", "CLOUDFLARE_RADAR", "ABUSEIPDB", "GREYNOISE", "OPENROUTER"):
    os.environ[f"{k}_API_KEY"] = f"FAKE-{k}"
os.environ["OPENROUTER_MODEL"] = "mock/model"


def _png(width=1280, height=800):
    """A valid gradient PNG (the screenshot mock, so that the browser can decode it and build a thumbnail)."""
    import struct
    import zlib

    rows = b"".join(b"\x00" + bytes(v for x in range(width) for v in (x * 255 // width, y * 255 // height, 160)) for y in range(height))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def _no_connect(*a, **kw):
    raise RuntimeError(f"HARNESS: real socket connect attempted: {a!r}")


socket.socket.connect = _no_connect
socket.create_connection = _no_connect
NO_PTR_IP = "185.220.101.99"  # the address without a PTR record


def _gethostbyaddr(ip):
    if ip == NO_PTR_IP:
        raise socket.herror(1, "Unknown host")
    return (f"rdns-{ip.replace('.', '-')}.example", [], [ip])


socket.gethostbyaddr = _gethostbyaddr  # checkouts before 2.4.26 look the name up this way

import urllib.parse  # noqa: E402

import httpx  # noqa: E402

XSS = '<img src=x onerror="window.__xss=1">'
CALLS: list[str] = []
SCANS: list[dict] = []
SEARCHES: list[str] = []
UNHANDLED: list[str] = []
REPORT_POSTS: list[dict] = []  # what the mocked AbuseIPDB /report received: form fields and the headers that matter

# Mocked AbuseIPDB /report answers by the last octet of the address (the documented shapes: https://docs.abuseipdb.com)
_RATE = {"X-RateLimit-Limit": "1000", "X-RateLimit-Remaining": "998"}
_REPORT_ERRORS = {
    20: (422, {"errors": [{"detail": "The categories field is required.", "status": 422, "source": {"parameter": "categories"}}]}, _RATE),
    21: (429, {"errors": [{"detail": "Daily rate limit of 1000 requests exceeded for this endpoint. See headers to determine when you can try again.", "status": 429}]},
         {"X-RateLimit-Limit": "1000", "X-RateLimit-Remaining": "0", "Retry-After": "3600", "X-RateLimit-Reset": "1893456000"}),
    22: (429, {"errors": [{"detail": "You can only report the same IP address (`185.220.101.22`) once in 15 minutes.", "status": 429}]}, {"X-RateLimit-Limit": "1000", "X-RateLimit-Remaining": "997"}),
    23: (401, {"errors": [{"detail": "Authentication failed. Your API key is either missing, incorrect, or revoked.", "status": 401}]}, {}),
    24: (500, None, {}),
}


def _sse(chunks, finish, usage):
    lines = [": OPENROUTER PROCESSING", ""]
    for c in chunks:
        lines.append("data: " + json.dumps({"choices": [{"delta": {"content": c}}]}))
        lines.append("")
    lines.append("data: " + json.dumps({"choices": [{"delta": {}, "finish_reason": finish}], "usage": usage}))
    lines.append("")
    lines.append("data: [DONE]")
    lines.append("")
    return "\n".join(lines).encode()


STREAM_COUNT = {"n": 0}
LLM_PROMPTS: list[tuple[bool, str]] = []  # (streamed?, the text of all messages) of every OpenRouter call


def handler(request: httpx.Request) -> httpx.Response:
    host, path = request.url.host, request.url.path
    CALLS.append(f"{request.method} {host}{path}")
    if host == "www.virustotal.com" and path.endswith("/overall_quotas"):
        return httpx.Response(200, json={"data": {"api_requests_hourly": {"user": {"allowed": 240, "used": 1}},
                                                  "api_requests_daily": {"user": {"allowed": 500, "used": 8}},
                                                  "api_requests_monthly": {"user": {"allowed": 15500, "used": 32}},
                                                  "private_scans_monthly": {"user": {"allowed": 0, "used": 0}}}})
    if host == "urlscan.io" and path == "/user/quotas/":
        day = {"limit": 1000, "used": 3, "remaining": 997, "reset": "2026-09-26T00:00:00.000Z"}
        return httpx.Response(200, json={"limits": {a: {"day": dict(day), "hour": dict(day), "minute": dict(day)}
                                                    for a in ("public", "unlisted", "private", "search", "retrieve", "files.public")}})
    if host == "openrouter.ai" and path == "/api/v1/key":
        return httpx.Response(200, json={"data": {"label": "sk-or-v1-abc...xyz", "limit": 25, "limit_remaining": 20.5, "limit_reset": None,
                                                  "usage": 4.5, "is_free_tier": False,
                                                  "free_model_daily_requests": {"used": 0, "limit": 1000, "remaining": 1000}}})
    if host == "api.abuseipdb.com" and path.endswith("/check"):
        return httpx.Response(200, headers={"X-RateLimit-Limit": "5000", "X-RateLimit-Remaining": "4982", "X-RateLimit-Reset": str(int(time.time()) + 3600)}, json={"data": {
            "ipAddress": request.url.params.get("ipAddress"), "abuseConfidenceScore": 42, "totalReports": 7,
            "numDistinctUsers": 3, "isWhitelisted": False, "isTor": False, "isPublic": True, "countryCode": "NL",
            "domain": "example.net", "hostnames": [], "isp": "Example ISP", "usageType": "Data Center",
            "lastReportedAt": "2026-09-20T10:00:00+00:00",
            "reports": [{"reportedAt": "2026-09-20T10:00:00+00:00", "comment": "spam " + XSS,
                         "categories": [11, 99], "reporterId": 1, "reporterCountryName": "Poland"}]}})
    if host == "api.abuseipdb.com" and path.endswith("/report"):
        form = {k: v[0] for k, v in urllib.parse.parse_qs(request.content.decode()).items()}
        REPORT_POSTS.append({"form": form, "key": request.headers.get("Key"), "accept": request.headers.get("Accept"),
                             "content_type": request.headers.get("Content-Type", "")})
        error = _REPORT_ERRORS.get(int(form["ip"].rsplit(".", 1)[-1])) if form.get("ip", "").startswith("185.220.101.") else None
        if error:
            status, body, headers = error
            return httpx.Response(status, json=body, headers=headers) if body else httpx.Response(status, text="<html>Bad gateway</html>")
        return httpx.Response(200, json={"data": {"ipAddress": form["ip"], "abuseConfidenceScore": 43}}, headers=_RATE)
    if host == "www.virustotal.com":
        return httpx.Response(200, json={"data": {"attributes": {
            "last_analysis_stats": {"malicious": 3, "suspicious": 1, "harmless": 60, "undetected": 20},
            "reputation": -5, "as_owner": "Example AS", "asn": 64500, "country": "NL", "whois": "NetName: X\nDescr: " + XSS}}})
    if host == "otx.alienvault.com":
        return httpx.Response(200, json={"indicator": "x", "type_title": "IPv4", "pulse_info": {"count": 2, "pulses": [
            {"name": "Pulse " + XSS, "modified": "2026-09-01T00:00:00", "tags": ["phishing"], "adversary": "APT-X",
             "indicator_type_counts": {"IPv4": 10}},
            {"name": "Bulk list", "created": "2024-01-01T00:00:00", "indicator_type_counts": {"IPv4": 500}}]},
            "country_name": "Netherlands", "country_code": "NL", "asn": "AS64500"})
    if host == "api.cloudflare.com" and "/ranking/domain/" in path:
        return httpx.Response(200, json={"success": True, "result": {"details_0": {"rank": None, "bucket": "200000", "categories": [{"id": 1, "name": "Business"}]}}})
    if host == "api.cloudflare.com":
        return httpx.Response(200, headers={"ratelimit": '"default";r=1190;t=300', "ratelimit-policy": '"default";q=1200;w=300'},
                              json={"success": True, "result": {"ip": {"asn": 64500, "location": "DE", "asnName": "EXAMPLE-AS"}}})
    if host == "api.greynoise.io" and path.endswith("/185.220.101.77"):
        return httpx.Response(429, json={"error": "We love that you love GreyNoise! Your searches will reset on September 29. Request a free trial."})
    if host == "api.greynoise.io":
        return httpx.Response(200, json={"internet_scanner_intelligence": {
            "found": True, "classification": "malicious", "actor": "unknown", "tags": [{"name": "SSH Bruteforcer"}],
            "cves": ["CVE-2024-0001"], "metadata": {"organization": "Org", "asn": "AS64500", "source_country": "Netherlands", "source_country_code": "NL"},
            "raw_data": {"scan": [{"port": 22, "protocol": "TCP"}]}}, "business_service_intelligence": {"found": False}})
    if host == "rdap.org":
        return httpx.Response(200, json={"handle": "NET-1", "name": "EXAMPLE-NET", "startAddress": "185.220.101.0",
                                         "endAddress": "185.220.101.255", "country": "NL", "entities": [
            {"roles": ["abuse"], "vcardArray": ["vcard", [["fn", {}, "text", "Abuse"], ["email", {}, "text", "abuse@example.net"]]]}],
            "events": [{"eventAction": "registration", "eventDate": "2020-01-01"}]})
    if host == "urlscan.io" and "/scan/" in path:
        SCANS.append(json.loads(request.content))
        return httpx.Response(200, json={"uuid": "11111111-2222-3333-4444-555555555555", "result": "https://urlscan.io/result/1/"})
    if host == "urlscan.io" and "/dom/" in path:
        return httpx.Response(200, text='<html><body><form action="https://collect.evil.example/post" method="POST"><input type="text" name="user">'
                                        '<input type="password" name="pw"><input type="hidden" name="t" value="1"></form>'
                                        '<form action="/search"><input name="q"></form></body></html>')
    if host == "urlscan.io" and "/search/" in path:
        SEARCHES.append(str(request.url))
        return httpx.Response(200, json={"results": [
            {"_id": "aaaaaaaa-2222-3333-4444-555555555555", "task": {"time": "2026-09-20T10:00:00.000Z", "url": "https://phish.example/login", "visibility": "public"},
             "page": {"url": "https://phish.example/login", "ip": "198.51.100.9", "country": "NL"}, "verdicts": {"overall": {"score": 100, "malicious": True, "hasVerdicts": True}}},
            {"_id": "not-a-uuid", "task": {"url": "https://x.example/"}, "page": {}}]})
    if host == "urlscan.io" and "/screenshots/" in path:
        return httpx.Response(200, content=_png(), headers={"Content-Type": "image/png"})
    if host == "urlscan.io" and "/result/" in path:
        return httpx.Response(200, json={"task": {"url": "http://phish.example/", "time": "2026-09-25T10:00:00.000Z", "visibility": "unlisted"},
                                         "page": {"url": "https://phish.example/login", "title": "Login " + XSS, "domain": "phish.example",
                                                  "apexDomain": "phish.example", "ip": "198.51.100.9", "country": "NL", "asn": "AS64500",
                                                  "asnname": "EXAMPLE-AS", "status": "200", "server": "nginx", "mimeType": "text/html",
                                                  "tlsIssuer": "R3", "tlsValidFrom": "2026-09-24T00:00:00.000Z", "tlsValidDays": 90, "tlsAgeDays": 1},
                                         "verdicts": {"overall": {"score": 100, "malicious": True, "hasVerdicts": True, "categories": ["phishing"],
                                                                  "brands": ["Contoso"]},
                                                      "urlscan": {"score": 100, "categories": ["phishing"], "brands": [{"name": "Contoso", "vertical": ["email"], "country": ["US"]}]},
                                                      "engines": {"maliciousTotal": 3, "benignTotal": 60},
                                                      "community": {"votesTotal": 2, "votesMalicious": 2}},
                                         "stats": {"malicious": 1},
                                         "lists": {"ips": ["198.51.100.9"], "domains": ["phish.example"], "countries": ["NL"], "asns": ["AS64500"]},
                                         "meta": {"processors": {"wappa": {"data": [{"app": "nginx", "version": "1.24", "categories": [{"name": "Web servers"}]}]}}},
                                         "data": {"requests": [{"request": {"request": {"url": "http://phish.example/"}}, "response": {"dataLength": 1000}},
                                                               {"request": {"request": {"url": "https://phish.example/login"},
                                                                            "redirectResponse": {"url": "http://phish.example/", "status": 301}},
                                                                "response": {"dataLength": 2048}}],
                                                  "cookies": [{"name": "a"}],
                                                  "links": [{"href": "https://x.example/", "text": "click " + XSS}]}})
    if host == "openrouter.ai":
        payload = json.loads(request.content)
        LLM_PROMPTS.append((bool(payload.get("stream")), "\n".join(m["content"] for m in payload["messages"])))
        usage = {"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200, "cost": 0.0123}
        if payload.get("stream"):
            STREAM_COUNT["n"] += 1
            if len(payload["messages"]) > 2:  # continuation
                return httpx.Response(200, content=_sse(["\n\n## Part 6: Assessment\nRest \u2014 done. Do not click; report `203.0.113.45`.\n\n",
                                                         "## Control questions\n1. Why is SPF fail not enough?\n\n<details><summary>Answer</summary>\n\n",
                                                         "Because DMARC decides.\n\n</details>\n"], "stop", usage),
                                      headers={"content-type": "text/event-stream"})
            return httpx.Response(200, content=_sse(
                ["VERDICT: phishing | CONFIDENCE: high\n\n# Analysis: a fake bank message\nA phishing message: SPF failed, Reply-To points elsewhere. ",
                 "IP 203.0.113.45 and 192.0.2.99 \u2014 ", "`Received-SPF: fail`\n\n",
                 "## Part 1: Mental model\nEnvelope vs letter, see `X-Originating-IP: [198.51.100.7]`.\n\n```\nsender -> mx.recipient.example -> mailbox\n```\n\n",
                 "## Part 2: Line by line\n### A. Headers of the recipient's server\n```\nReceived-SPF: fail (bank.example: domain does not designate 203.0.113.45 as permitted sender) client-ip=203.0.113.45;\n```\n",
                 "Trusted by nobody. `Return-Path` is missing.\n\n### B. Authentication\n```\nAuthentication-Results: mx.recipient.example; spf=fail smtp.mailfrom=bank.example; (...) dmarc=fail\n```\n```\nX-Fake-Header: nothing\n```\n\n",
                 "## Part 3: Checklist\n| # | Check | Result | Rating |\n|---|---|---|---|\n| 1 | Context | unexpected | \u26a0 |\n| 2 | SPF | fail | \u2717 |\n| 3 | Times | consistent | \u2713 |\n\n",
                 "## Part 4: Legitimate vs hostile\nSCL=9 <b>bold</b> [link](https://evil.example/)\n\n## Part 5: Traps\nDo not trust display names."],
                "length", usage), headers={"content-type": "text/event-stream"})
        content = json.dumps({"qualifies": True, "reasoning": "r " + XSS, "suggested_categories": [7, 11],
                              "report_comment": "Phishing from 203.0.113.45 \u2014 test", "alternatives": "",
                              "source_ip_check": {"agrees": False, "suggested_ip": "198.51.100.7", "reasoning": "x \u2014 y"},
                              "received_verified": {"status": "pass", "note": "n"},
                              "not_spoofed_source": {"status": "pass", "note": "n"},
                              "category_matches": {"status": "pass", "note": "n \u2014 ok"},
                              "pii_redacted": {"status": "pass", "note": "n"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "```json\n" + content + "\n```"}, "finish_reason": "stop"}], "usage": usage})
    UNHANDLED.append(f"{request.method} {request.url}")
    raise RuntimeError(f"HARNESS: unmocked request {request.url}")


_OrigAsync = httpx.AsyncClient


class MockAsyncClient(_OrigAsync):
    def __init__(self, *a, **kw):
        kw["transport"] = httpx.MockTransport(handler)
        super().__init__(*a, **kw)


httpx.AsyncClient = MockAsyncClient

import whois  # noqa: E402

whois.whois = lambda domain: {"registrar": "Example Registrar", "creation_date": ["2001-01-01"], "name_servers": ["ns1.example"],
                              "status": "ok", "emails": ["abuse@example.com"]}

TMP = Path(tempfile.mkdtemp(prefix="seisa-harness-"))
atexit.register(shutil.rmtree, TMP, ignore_errors=True)
# The desktop icon writes into the home directory: point it at a temporary one and fake a Linux desktop, so that the
# harness never touches the real Applications folder / menu and its result does not depend on the machine running it.
os.environ["HOME"] = str(TMP / "home")
os.environ["DISPLAY"] = ":0"
os.environ.pop("WAYLAND_DISPLAY", None)
import backend.config as cfg  # noqa: E402

cfg.DATA_DIR = TMP / "data"
cfg.HISTORY_FILE = cfg.DATA_DIR / "history.json"
cfg.HISTORY_DIR = cfg.DATA_DIR / "history"
cfg.HISTORY_INDEX_FILE = cfg.HISTORY_DIR / "index.json"
cfg.HISTORY_ENTRIES_DIR = cfg.HISTORY_DIR / "entries"
cfg.VT_USAGE_FILE = cfg.DATA_DIR / "vt_usage.json"
cfg.REPORT_LOG_FILE = cfg.DATA_DIR / "report_log.json"
cfg.API_USAGE_FILE = cfg.DATA_DIR / "api_usage.json"
# the directory constants were renamed in 2.0.27 (ANALIZY_DIR / LOGI_DIR): patch whichever exists, so that `--root`
# can point at an older checkout
for names, val in ((("ANALYSES_DIR", "ANALIZY_DIR"), cfg.DATA_DIR / "analyses"), (("LOGS_DIR", "LOGI_DIR"), TMP / "logs")):
    for name in names:
        if hasattr(cfg, name):
            setattr(cfg, name, val)

# Imported only here, after the data paths above are patched: storage.py binds them at import time, so an earlier import of
# anything that reaches it would make the harness read and write the real data/ directory.
try:
    import backend.services.whois_dns as _whois_dns

    async def _fake_dns(domain):
        return {"exists": True, "a": ["93.184.216.34"], "ns": ["ns1.example"], "mx": ["mail.example"], "spf": "v=spf1 -all",
                **({"ns_missing": ["ns9.gone.example"]} if domain == "dangling.example" else {})}

    _whois_dns.resolve_domain = _fake_dns

    async def _fake_ptr(ip):  # reverse DNS goes through dnspython since 2.4.26; older checkouts use socket.gethostbyaddr above
        return None if ip == NO_PTR_IP else f"rdns-{ip.replace('.', '-')}.example"

    _whois_dns.reverse_lookup = _fake_ptr
except ImportError:  # `--root` points at a checkout from before the DNS records existed
    pass

from fastapi.testclient import TestClient  # noqa: E402

import backend.main as main  # noqa: E402
from backend.ratelimit import vt_rate_limiter  # noqa: E402

vt_rate_limiter._minute_limiter.max_calls = 10_000

# the Info tab reads the release list from `git log`; the harness serves a fixed one (with an XSS probe) instead
try:
    from backend import desktop_icon as _di_mod
    from backend.routers import about as _about_router  # absent in checkouts older than 2.0.51 (`--root`)

    _di_mod._system = lambda: "Linux"
    _SERVER_STOPS: list[int] = []
    _about_router._schedule_stop = lambda: _SERVER_STOPS.append(1)  # the real one would end the harness process
    _about_router._recent_changes = lambda: [{"version": "9.9.9", "summary": "mock <img src=x onerror=window.__xss=1>"}]
except ImportError:
    pass

if _args.serve:
    import uvicorn

    print(f"Seisa with mocked services on http://127.0.0.1:{_args.serve} (data in {TMP})")
    uvicorn.run(main.app, host="127.0.0.1", port=_args.serve, log_level="warning")
    sys.exit(0)

client = TestClient(main.app, base_url="http://127.0.0.1")
RESULTS: list[dict] = []

VOLATILE_KEYS = {"id", "queried_at", "created_at", "submitted_at", "last_submitted_at", "analysis_id", "time",
                 "age_days", "age_ok", "age_reason", "all_passed", "cooldown_left_minutes", "delta_s"}
# The attack time of the test reports is computed from the clock, never written down: the age check (60 days) of the
# hard checks would otherwise start rejecting them as time passes. Two days back, a full hour, UTC. The clock is the one
# of the code under test (backend.report_utils), so a test can move that clock and the harness follows it.
from backend import report_utils  # noqa: E402

ATTACK_UTC = (report_utils.datetime.now(timezone.utc) - timedelta(days=2)).replace(minute=0, second=0, microsecond=0)
ISO_RE = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?([+-]\d\d:\d\d|Z)?")
VERSION_RE = re.compile(r"Seisa \d+\.\d+\.\d+")
ID_RE = re.compile(r"\b\d{8}-\d{6}-[0-9a-f]{8}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")


def norm(v):
    if isinstance(v, dict):
        return {k: ("<volatile>" if k in VOLATILE_KEYS else norm(x)) for k, x in v.items()}
    if isinstance(v, list):
        return [norm(x) for x in v]
    if isinstance(v, str):
        return VERSION_RE.sub("Seisa <version>", ID_RE.sub("<id>", ISO_RE.sub("<ts>", v)))
    return v


def rec(name, resp, sse=False):
    body = resp.text
    if sse:
        events = [json.loads(line[6:]) for line in body.split("\n") if line.startswith("data: ")]
        data = events
    else:
        try:
            data = resp.json()
        except ValueError:
            data = body[:200]
    RESULTS.append({"name": name, "status": resp.status_code, "body": norm(data)})
    return data


FIX = {p.stem: p.read_text(encoding="utf-8") for p in sorted((ROOT / "tests/fixtures").glob("*.eml"))}
PUBLIC_IP = "185.220.101.1"

for lang in ("pl", "en"):
    H = {"X-Seisa-Lang": lang}
    p = f"[{lang}] "
    rec(p + "lookup ip", client.post("/api/lookup", json={"indicator": PUBLIC_IP, "type": "ip"}, headers=H))
    rec(p + "lookup domain", client.post("/api/lookup", json={"indicator": "example.com", "type": "domain"}, headers=H))
    rec(p + "lookup domain auto", client.post("/api/lookup", json={"indicator": "example.com"}, headers=H))
    rec(p + "lookup domain url", client.post("/api/lookup", json={"indicator": "HTTPS://Example.COM:8080/a/b?x=1#f"}, headers=H))
    rec(p + "lookup defanged ip", client.post("/api/lookup", json={"indicator": "185[.]220[.]101[.]1:443"}, headers=H))
    rec(p + "lookup private ip", client.post("/api/lookup", json={"indicator": "192.168.1.10"}, headers=H))
    rec(p + "lookup domain dangling", client.post("/api/lookup", json={"indicator": "dangling.example"}, headers=H))
    rec(p + "lookup greynoise limit", client.post("/api/lookup", json={"indicator": "185.220.101.77"}, headers=H))
    rec(p + "lookup no ptr", client.post("/api/lookup", json={"indicator": NO_PTR_IP, "type": "ip"}, headers=H))
    rec(p + "lookup invalid", client.post("/api/lookup", json={"indicator": "a/../../x", "type": "domain"}, headers=H))
    rec(p + "lookup invalid ip", client.post("/api/lookup", json={"indicator": "not-an-ip", "type": "ip"}, headers=H))
    rec(p + "urlscan scan", client.post("/api/urlscan/scan", json={"url": "https://phish.example/login"}, headers=H))
    rec(p + "urlscan result", client.get("/api/urlscan/result/11111111-2222-3333-4444-555555555555", headers=H))
    rec(p + "urlscan result bad uuid", client.get("/api/urlscan/result/not-a-uuid", headers=H))
    rec(p + "urlscan scan defanged", client.post("/api/urlscan/scan", json={"url": "hxxps://phish[.]example/login", "visibility": "private"}, headers=H))
    rec(p + "urlscan scan private host", client.post("/api/urlscan/scan", json={"url": "http://192.168.1.10/admin"}, headers=H))
    rec(p + "urlscan scan bad scheme", client.post("/api/urlscan/scan", json={"url": "javascript:alert(1)"}, headers=H))
    rec(p + "urlscan scan bad visibility", client.post("/api/urlscan/scan", json={"url": "https://phish.example/", "visibility": "everyone"}, headers=H))
    rec(p + "urlscan scan options", client.post("/api/urlscan/scan", json={"url": "https://phish.example/login", "country": "PL", "useragent": "Mozilla/5.0 (Test)"}, headers=H))
    rec(p + "urlscan scan bad country", client.post("/api/urlscan/scan", json={"url": "https://phish.example/", "country": "xx"}, headers=H))
    rec(p + "urlscan scan bad useragent", client.post("/api/urlscan/scan", json={"url": "https://phish.example/", "useragent": "bad\nagent"}, headers=H))
    rec(p + "urlscan search", client.get("/api/urlscan/search", params={"url": "hxxps://phish[.]example/login"}, headers=H))
    rec(p + "urlscan search bad url", client.get("/api/urlscan/search", params={"url": "http://10.0.0.1/"}, headers=H))
    rec(p + "urlscan search injection", client.get("/api/urlscan/search", params={"url": 'https://a.example" OR page.domain:"b/'}, headers=H))
    rec(p + "urlscan screenshot bad uuid", client.get("/api/urlscan/screenshot/not-a-uuid", headers=H))
    shot = client.get("/api/urlscan/screenshot/11111111-2222-3333-4444-555555555555", headers=H)
    SHOT_PROBE = (shot.status_code, shot.headers.get("content-type"), shot.content[:4])
    for name, src in FIX.items():
        rec(p + f"abuseipdb analyze {name} no-llm", client.post("/api/abuseipdb/email/analyze", json={"raw_email": src, "use_llm": False}, headers=H))
        rec(p + f"abuseipdb analyze {name} llm", client.post("/api/abuseipdb/email/analyze", json={"raw_email": src, "use_llm": True}, headers=H))
    fields = {"ip": PUBLIC_IP, "categories": [11], "attack_timestamp": ATTACK_UTC.strftime("%Y-%m-%dT%H:%M:%SZ"), "comment": "=test \u2014 comment"}
    rec(p + "report preview", client.post("/api/abuseipdb/report/preview", json=fields, headers=H))
    rec(p + "report preview private ip", client.post("/api/abuseipdb/report/preview", json={**fields, "ip": "10.0.0.1"}, headers=H))
    rec(p + "dmarc geo", client.get(f"/api/dmarc/geo?ip={PUBLIC_IP}", headers=H))
    rec(p + "dmarc geo no ptr", client.get(f"/api/dmarc/geo?ip={NO_PTR_IP}", headers=H))
    rec(p + "dmarc geo private", client.get("/api/dmarc/geo?ip=10.0.0.1", headers=H))
    rec(p + "dmarc geo invalid", client.get("/api/dmarc/geo?ip=x/../y", headers=H))
    rec(p + "ip-info", client.get(f"/api/abuseipdb/ip-info?ip={PUBLIC_IP}", headers=H))
    rec(p + "ip-info private", client.get("/api/abuseipdb/ip-info?ip=10.0.0.1", headers=H))
    rec(p + "report submit bad", client.post("/api/abuseipdb/report/submit", json={**fields, "categories": []}, headers=H))
    ip_lang = PUBLIC_IP if lang == "pl" else "185.220.101.2"
    rec(p + "report submit ok", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": ip_lang}, headers=H))
    rec(p + "report submit cooldown", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": ip_lang}, headers=H))
    # the API's own answers (quota, repeat rule, refused data, key, outage) become distinct, readable errors
    rec(p + "report submit 422", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": "185.220.101.20"}, headers=H))
    rec(p + "report submit daily limit", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": "185.220.101.21"}, headers=H))
    rec(p + "report submit repeat at api", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": "185.220.101.22"}, headers=H))
    rec(p + "report submit bad key", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": "185.220.101.23"}, headers=H))
    rec(p + "report submit outage", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": "185.220.101.24"}, headers=H))
    # what goes over the wire: duplicated categories collapse, the comment is ASCII and at most 1024 characters
    rec(p + "report submit wire", client.post("/api/abuseipdb/report/submit", json={
        "ip": "185.220.101.3" + ("0" if lang == "pl" else "1"), "categories": [11, 11, 7], "attack_timestamp": (ATTACK_UTC + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S+02:00"),
        "comment": "za\u017c\u00f3\u0142\u0107 " + "x" * 2000}, headers=H))
    rec(p + "report submit old", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": "185.220.101.40", "attack_timestamp": "2020-01-01T00:00:00Z"}, headers=H))
    rec(p + "report submit future", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": "185.220.101.41", "attack_timestamp": "2099-01-01T00:00:00Z"}, headers=H))
    rec(p + "report submit no timestamp", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": "185.220.101.42", "attack_timestamp": None}, headers=H))
    rec(p + "report submit unknown category", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": "185.220.101.43", "categories": [11, 99]}, headers=H))
    rec(p + "report submit private ip", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": "10.0.0.1"}, headers=H))
    pii_comment = "Mail to victim@corp.example from spam@bad.example via 10.1.2.3 and 185.220.101.1 corp.example"
    rec(p + "report preview pii", client.post("/api/abuseipdb/report/preview", json={**fields, "comment": pii_comment, "own_terms": ["victim@corp.example", "corp.example"]}, headers=H))
    rec(p + "report redact", client.post("/api/abuseipdb/report/redact", json={"comment": pii_comment, "own_terms": ["victim@corp.example", "corp.example"]}, headers=H))
    rec(p + "report history", client.get("/api/abuseipdb/report/history", headers=H))
    for name, src in FIX.items():
        rec(p + f"email find {name}", client.post("/api/email/find", json={"raw_email": src}, headers=H))
    ev = rec(p + "email analyze phishing", client.post("/api/email/analyze", json={"raw_email": FIX["phishing"]}, headers=H), sse=True)
    rec(p + "email analyze phishing no-llm", client.post("/api/email/analyze", json={"raw_email": FIX["phishing"], "use_llm": False}, headers=H), sse=True)
    rec(p + "email analyze empty", client.post("/api/email/analyze", json={"raw_email": "  "}, headers=H), sse=True)
    aid = next((e.get("analysis_id") for e in ev if e.get("type") == "done"), None)
    rec(p + "email analyses", client.get("/api/email/analyses", headers=H))
    if aid:
        rec(p + "email analysis get", client.get(f"/api/email/analyses/{aid}", headers=H))
        # an analysis saved by an older version: the saved sender hop differs from the one computed today
        saved_file = (getattr(cfg, "ANALYSES_DIR", None) or cfg.ANALIZY_DIR) / f"{aid}.json"
        original = saved_file.read_text(encoding="utf-8")
        saved = json.loads(original)
        saved["facts"]["trust_index"] = 2
        saved_file.write_text(json.dumps(saved), encoding="utf-8")
        rec(p + "email analysis get (older facts)", client.get(f"/api/email/analyses/{aid}", headers=H))
        saved_file.write_text(original, encoding="utf-8")
        rec(p + "email continue", client.post(f"/api/email/analyses/{aid}/continue", headers=H), sse=True)
        rec(p + "email continue again (not truncated)", client.post(f"/api/email/analyses/{aid}/continue", headers=H))
    rec(p + "email bad id", client.get("/api/email/analyses/..%2F..%2Fetc", headers=H))
    rec(p + "email bad id2", client.get("/api/email/analyses/bad-id", headers=H))
    rec(p + "history create dmarc", client.post("/api/history", json={"type": "dmarc", "label": "d", "data": {"x": XSS}}, headers=H))
    thumb = "data:image/jpeg;base64," + "/9j/4AAQ"
    summary_stub = client.get("/api/urlscan/result/11111111-2222-3333-4444-555555555555", headers=H).json()["summary"]
    rec(p + "history create urlscan", client.post("/api/history", json={"type": "urlscan", "label": "hxxps://phish[.]example", "risk_summary": "High", "data": {"summary": summary_stub, "thumbnail": thumb}}, headers=H))
    rec(p + "history create urlscan bad thumbnail", client.post("/api/history", json={"type": "urlscan", "label": "x", "data": {"summary": summary_stub, "thumbnail": "data:image/svg+xml;base64,PHN2Zz4="}}, headers=H))
    rec(p + "history create urlscan no summary", client.post("/api/history", json={"type": "urlscan", "label": "x", "data": {"thumbnail": thumb}}, headers=H))
    rec(p + "history create bad", client.post("/api/history", json={"type": "evil", "label": "d", "data": {}}, headers=H))
    hist = rec(p + "history list", client.get("/api/history", headers=H))
    lookup_entry = next((h for h in hist if h["type"] == "lookup"), None)
    if lookup_entry:
        rec(p + "history entry", client.get(f"/api/history/{lookup_entry['id']}", headers=H))
    rec(p + "history entry missing", client.get("/api/history/nope", headers=H))
    if lookup_entry:
        rec(p + "history pin", client.patch(f"/api/history/{lookup_entry['id']}", json={"pinned": True}, headers=H))
    rec(p + "history pin missing", client.patch("/api/history/nope", json={"pinned": True}, headers=H))
    rec(p + "logs all", client.get("/api/logs?range=all&service=all", headers=H))
    rec(p + "logs today abuseipdb", client.get("/api/logs?range=today&service=abuseipdb", headers=H))
    rec(p + "about", client.get("/api/about", headers=H))
    # last GreyNoise answer before the Info tab is read must be the 429 (a later 200 clears the flag)
    rec(p + "lookup greynoise limit late", client.post("/api/lookup", json={"indicator": "185.220.101.77"}, headers=H))
    rec(p + "limits refresh", client.post("/api/about/limits/refresh", headers=H))
    rec(p + "about after refresh", client.get("/api/about", headers=H))
    rec(p + "icon status", client.get("/api/about/icon", headers=H))
    rec(p + "icon install", client.post("/api/about/icon", headers=H))
    rec(p + "icon status after install", client.get("/api/about/icon", headers=H))
    rec(p + "icon remove", client.delete("/api/about/icon", headers=H))
    rec(p + "icon status after remove", client.get("/api/about/icon", headers=H))
    rec(p + "logs clear", client.delete("/api/logs", headers=H))
    rec(p + "logs after clear", client.get("/api/logs?range=all", headers=H))
    if aid:
        rec(p + "email delete", client.delete(f"/api/email/analyses/{aid}", headers=H))
    rec(p + "history clear", client.delete("/api/history", headers=H))
    rec(p + "history after clear", client.get("/api/history", headers=H))

rec("static index", client.get("/"))
rec("i18n catalog", client.get("/i18n/en.json"))
_themes_resp = client.get("/api/themes")
rec("themes list", _themes_resp)
_themes_css = client.get("/api/themes.css")
rec("themes css", _themes_css)

# --- security probes (not part of the golden comparison) ---
probes = {}
probes["foreign Host header accepted (DNS rebinding)"] = client.get("/api/history", headers={"Host": "attacker.example"}).status_code
r = client.post("/api/abuseipdb/report/preview", content=json.dumps(fields), headers={"Content-Type": "text/plain", "Origin": "https://attacker.example"})
probes["text/plain cross-site POST (CSRF without preflight)"] = r.status_code
r = client.options("/api/abuseipdb/report/submit", headers={"Origin": "https://attacker.example", "Access-Control-Request-Method": "POST"})
probes["CORS preflight status"] = r.status_code
probes["CORS allow-origin header"] = r.headers.get("access-control-allow-origin")
_XSITE_GET = "/api/urlscan/search?url=https://phish.example/"
for _name, _hdr in {
    "Sec-Fetch-Site cross-site": {"Sec-Fetch-Site": "cross-site"},
    "Sec-Fetch-Site same-site": {"Sec-Fetch-Site": "same-site"},
    "foreign Origin": {"Origin": "https://attacker.example"},
    "Origin null": {"Origin": "null"},
    "Sec-Fetch-Site same-origin": {"Sec-Fetch-Site": "same-origin"},
    "Sec-Fetch-Site none": {"Sec-Fetch-Site": "none"},
    "loopback Origin": {"Origin": "http://localhost:54321"},
    "no fetch metadata": {},
}.items():
    probes[f"guard GET {_name}"] = client.get(_XSITE_GET, headers=_hdr).status_code
probes["guard GET dmarc geo cross-site"] = client.get("/api/dmarc/geo?ip=8.8.8.8", headers={"Sec-Fetch-Site": "cross-site"}).status_code
probes["guard body-less POST cross-site"] = client.post("/api/about/limits/refresh", headers={"Sec-Fetch-Site": "cross-site"}).status_code
_XS = {"Sec-Fetch-Site": "cross-site"}
_icon_entry = TMP / "home" / ".local" / "share" / "applications" / "seisa.desktop"
probes["guard icon POST cross-site"] = client.post("/api/about/icon", headers=_XS).status_code
probes["icon entry after cross-site POST"] = _icon_entry.exists()
client.post("/api/about/icon")
probes["guard icon DELETE cross-site"] = client.delete("/api/about/icon", headers=_XS).status_code
probes["icon entry after cross-site DELETE"] = _icon_entry.exists()
client.delete("/api/about/icon")
probes["icon entry after the real remove"] = _icon_entry.exists()
probes["guard shutdown POST cross-site"] = client.post("/api/about/shutdown", headers=_XS).status_code
probes["shutdown calls after cross-site"] = len(_SERVER_STOPS)
probes["shutdown POST same-origin"] = client.post("/api/about/shutdown").status_code
probes["shutdown calls after same-origin"] = len(_SERVER_STOPS)
probes["guard themes.css cross-site"] = client.get("/api/themes.css", headers={"Sec-Fetch-Site": "cross-site"}).status_code
probes["guard static index cross-site"] = client.get("/", headers={"Sec-Fetch-Site": "cross-site"}).status_code
probes["guard preflight foreign Origin"] = client.options("/api/history", headers={"Origin": "https://attacker.example", "Access-Control-Request-Method": "DELETE"}).status_code
probes["CSP header on /"] = client.get("/").headers.get("content-security-policy")
probes["urlscan uuid path injection"] = client.get("/api/urlscan/result/..%2F..%2Fuser%2Fquotas").status_code
probes["urlscan screenshot"] = SHOT_PROBE

# --- checks ---
EXPECTED_STATUS = {
    "lookup ip": 200, "lookup domain url": 200, "lookup defanged ip": 200, "lookup private ip": 400, "lookup domain": 200, "lookup greynoise limit": 200, "lookup no ptr": 200, "lookup domain dangling": 200, "lookup domain auto": 200, "lookup invalid": 400, "lookup invalid ip": 400,
    "urlscan scan": 200, "urlscan result": 200, "urlscan result bad uuid": 400,
    "urlscan scan defanged": 200, "urlscan scan private host": 400, "urlscan scan bad scheme": 400, "urlscan scan bad visibility": 400,
    "urlscan screenshot bad uuid": 400, "urlscan search": 200, "urlscan search bad url": 400, "urlscan search injection": 400, "history create urlscan": 200, "history create urlscan bad thumbnail": 400,
    "history create urlscan no summary": 400,
    "report preview": 200, "dmarc geo": 200, "dmarc geo no ptr": 200, "dmarc geo private": 400, "dmarc geo invalid": 400, "ip-info": 200, "report submit bad": 400, "report submit ok": 200,
    "report submit cooldown": 409, "report submit 422": 422, "report submit daily limit": 429, "report submit repeat at api": 409,
    "report submit bad key": 401, "report submit outage": 502, "report submit wire": 200, "report submit old": 400,
    "report submit future": 400, "report submit no timestamp": 400, "report submit unknown category": 400,
    "report submit private ip": 400, "report preview pii": 200, "report redact": 200, "report history": 200,
    "email analyze phishing": 200, "email bad id": 404, "email bad id2": 400,
    "email continue again (not truncated)": 400, "history create dmarc": 200, "history create bad": 400,
    "history entry missing": 404, "static index": 200, "themes list": 200, "themes css": 200,
}
failures = []
for r in RESULTS:
    want = EXPECTED_STATUS.get(r["name"].split("] ", 1)[-1])
    if want is not None and r["status"] != want:
        failures.append(f"{r['name']}: status {r['status']}, expected {want}")
# domain lookup: URL normalised, identity of the domain, Cloudflare ranking instead of the IP entity endpoint
_dom = next((r["body"] for r in RESULTS if r["name"].endswith("lookup domain url")), None)
if isinstance(_dom, dict) and "identity" in _dom:
    if _dom.get("indicator") != "example.com":
        failures.append(f"lookup domain url: indicator not normalised: {_dom.get('indicator')}")
    if not any(f["key"] == "registrar" for f in (_dom.get("identity") or {}).get("fields", [])):
        failures.append("lookup domain: identity has no registrar")
    if _dom["services"]["cloudflare_radar"]["status"] != "ok":
        failures.append(f"lookup domain: Cloudflare Radar failed: {_dom['services']['cloudflare_radar']}")
_auto = next((r["body"] for r in RESULTS if r["name"].endswith("] lookup domain auto")), None)
if isinstance(_auto, dict) and "identity" in _auto:
    _cmp = _auto.get("comparison")
    if not (_cmp and _cmp["previous"]["level"] and "delta" in _cmp and _cmp["trend"]):
        failures.append(f"lookup domain auto: no comparison with the earlier scan of the same domain: {_cmp}")
_dang = next((r["body"] for r in RESULTS if r["name"].endswith("[en] lookup domain dangling")), None)
if isinstance(_dang, dict) and "identity" in _dang and not any("ns9.gone.example" in n for n in _dang["identity"]["notes"]):
    failures.append("lookup domain dangling: the dangling NS is not reported in the identity notes")
_gn = next((r["body"] for r in RESULTS if r["name"] == "[en] lookup greynoise limit"), None)
if isinstance(_gn, dict) and "services" in _gn:
    _g = _gn["services"]["greynoise"]
    if _g["status"] != "rate_limited_daily" or "HTTP 429" in (_g.get("error_message") or "") or "September 29" not in (_g.get("error_message") or ""):
        failures.append(f"greynoise 429: not turned into a friendly limit message: {_g}")
# no PTR record: stored as null (not as translated text), no "rdns" row in the identity, and the DMARC geo answer says null too
_nop = next((r["body"] for r in RESULTS if r["name"] == "[en] lookup no ptr"), None)
if isinstance(_nop, dict) and "services" in _nop and "identity" in _nop:
    if _nop["services"]["whois_rdns"]["summary"].get("reverse_dns") not in (None, "no PTR record"):
        failures.append(f"lookup no ptr: unexpected reverse_dns {_nop['services']['whois_rdns']['summary'].get('reverse_dns')!r}")
    if any(f["key"] == "rdns" for f in _nop["identity"]["fields"]):
        failures.append("lookup no ptr: the missing PTR record leaked into the identity as a host name")
_geo = next((r["body"] for r in RESULTS if r["name"] == "[en] dmarc geo no ptr"), None)
if isinstance(_geo, dict) and _geo.get("reverse_dns") is not None:
    failures.append(f"dmarc geo no ptr: expected no reverse DNS name, got {_geo.get('reverse_dns')!r}")
# the long dash never reaches the screen from the model's JSON answer (the report comment is cleaned by its own sanitizer)
for _r in RESULTS:
    if "abuseipdb analyze" in _r["name"] and _r["name"].endswith(" llm") and isinstance(_r["body"], dict):
        _llm = dict(_r["body"].get("llm_analysis") or {})
        _llm.pop("report_comment", None)
        if "\u2014" in json.dumps(_llm, ensure_ascii=False):
            failures.append(f"{_r['name']}: a long dash is left in the descriptive fields of the model answer")
_ip = next((r["body"] for r in RESULTS if r["name"].endswith("lookup defanged ip")), None)
if isinstance(_ip, dict) and _ip.get("indicator") != PUBLIC_IP:
    failures.append(f"lookup defanged ip: not normalised: {_ip.get('indicator')}")
# identity merging (backend/identity.py): tie-break by source priority, normalisation, no false conflicts
try:
    from backend.identity import build_identity
except ImportError:  # `--root` points at a checkout from before the module existed
    build_identity = None

if build_identity:
    from backend.models import ServiceResult as _SR

    def _res(**summaries):
        return {name: _SR(service=name, status="ok", summary=summary) for name, summary in summaries.items()}

    def _field(identity, key):
        return next((f for f in identity.fields if f.key == key), None)

    ident = build_identity(_res(
        whois_rdns={"organization": "TC Datacenter Ltd.", "reverse_dns": "no PTR record", "network_range": "10.0.0.0 - 10.0.0.255", "country": "NL"},
        virustotal={"as_owner": "TC DATACENTER LIMITED", "asn": 64500, "network": "10.0.0.0/16", "country": "PL"},
        greynoise={"organization": "Other Corp", "asn": "AS64501", "country_code": "DE", "tor": False},
        abuseipdb={"isp": "Third Party", "country_code": "FR", "is_tor": False},
        otx={"asn": "AS64500 tc datacenter"},
    ))
    org, asn, loc, net = (_field(ident, k) for k in ("organization", "asn", "country_location", "network"))
    if not (org and org.status == "majority" and org.agree == 2 and org.value == "TC Datacenter Ltd."):
        failures.append(f"identity: owner spelling variants are not grouped: {org}")
    if not (asn and asn.status == "majority" and asn.value == "AS64500" and asn.agree == 2):
        failures.append(f"identity: ASN majority is wrong: {asn}")
    if not (loc and loc.status == "conflict" and loc.value == "FR"):
        failures.append(f"identity: a country tie must be flagged and resolved by source priority: {loc}")
    if not (net and net.status == "agree" and net.value == "10.0.0.0/24"):
        failures.append(f"identity: a network reported at another granularity is not a disagreement: {net}")
    if _field(ident, "rdns") or _field(ident, "tor"):
        failures.append("identity: the 'no PTR' placeholder or an all-'no' Tor flag leaked into the card")
    if not ident.notes:
        failures.append("identity: registration vs geolocation country note missing")
    tor = _field(build_identity(_res(greynoise={"tor": True}, abuseipdb={"is_tor": False})), "tor")
    if not (tor and tor.status == "conflict"):
        failures.append("identity: a Tor disagreement must be flagged")
    if build_identity({}).fields:
        failures.append("identity: no sources must give no fields")
# --- AbuseIPDB /report contract (https://docs.abuseipdb.com/#report-endpoint) ---
def _result(name):
    return next(r for r in RESULTS if r["name"] == name)


_wire = [x for x in REPORT_POSTS if x["form"]["ip"].startswith("185.220.101.3")]
if len(_wire) != 2:
    failures.append(f"report wire: expected 2 posts of the wire test, got {len(_wire)}")
for post in _wire:
    form = post["form"]
    if set(form) != {"ip", "categories", "comment", "timestamp"}:
        failures.append(f"report wire: unexpected fields {sorted(form)}")
    if form["categories"] != "7,11":
        failures.append(f"report wire: categories must be a comma-separated list without duplicates, got {form['categories']!r}")
    if len(form["comment"]) > 1024 or not form["comment"].isascii():
        failures.append("report wire: the comment is over 1024 characters or not ASCII")
    if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00", form["timestamp"]) or form["timestamp"] != ATTACK_UTC.strftime("%Y-%m-%dT%H:%M:%S+00:00"):
        failures.append(f"report wire: timestamp is not ISO 8601 in UTC of the attack: {form['timestamp']!r}")
    if not post["key"] or post["accept"] != "application/json" or "x-www-form-urlencoded" not in post["content_type"]:
        failures.append(f"report wire: headers wrong (Key set: {bool(post['key'])}, Accept: {post['accept']}, {post['content_type']})")
if any(x["form"]["ip"] in ("10.0.0.1", "185.220.101.40", "185.220.101.41", "185.220.101.42", "185.220.101.43") for x in REPORT_POSTS):
    failures.append("report: a report that fails the hard checks (private IP, age, no date, unknown category) reached the API")
for _lang, _needle in (("pl", "dzienny limit"), ("en", "daily report limit")):
    if _needle not in _result(f"[{_lang}] report submit daily limit")["body"]["detail"]:
        failures.append(f"report: the daily quota answer is not explained ({_lang})")
    if "1000" not in _result(f"[{_lang}] report submit daily limit")["body"]["detail"]:
        failures.append(f"report: the daily limit value is missing from the message ({_lang})")
    if "categories field is required" not in _result(f"[{_lang}] report submit 422")["body"]["detail"]:
        failures.append(f"report: the API's 422 detail is not passed on ({_lang})")
_pii = _result("[en] report preview pii")["body"]["pii"]
if [f["kind"] for f in _pii] != ["own", "own", "email", "private_ip"] or any(f["value"] == "185.220.101.1" for f in _pii):
    failures.append(f"report pii scan: {_pii}")
_red = _result("[en] report redact")["body"]["comment"]
if any(x in _red for x in ("victim@corp.example", "spam@bad.example", "10.1.2.3", "corp.example")) or "185.220.101.1" not in _red:
    failures.append(f"report redact left personal data or removed the reported address: {_red!r}")
_hist = _result("[pl] report history")["body"]
if _hist["rate_limit"] != {"limit": 1000, "remaining": 998} and _hist["rate_limit"] is not None:
    failures.append(f"report history: rate limit not taken from the answer headers: {_hist['rate_limit']}")
if not _hist["entries"] or not any(not e["success"] and e.get("error") for e in _hist["entries"]):
    failures.append("report history: failed attempts are not logged")
if not any(e["success"] and e.get("abuse_confidence_score") == 43 for e in _hist["entries"]):
    failures.append("report history: the score returned by the API is not stored")
_cand = _result("[en] abuseipdb analyze phishing no-llm")["body"]
if "ip_candidates" not in _cand or "own_terms" not in _cand:
    failures.append("analysis result lacks ip_candidates / own_terms")
_hist_types = {h["type"] for h in _result("[en] history list")["body"]}
if "report" not in _hist_types:
    failures.append(f"the History tab does not list accepted reports: {_hist_types}")
_after_clear = _result("[en] history after clear")["body"]
_about_body = _result("[en] about")["body"]
if "FAKE-" in json.dumps(_about_body) or sum(1 for x in _about_body["services"] if x["configured"]) != 6:
    failures.append(f"the Info endpoint leaks an API key or misreports the configuration: {_about_body}")
_env = _about_body.get("environment") or {}
if not all(_env.get(k) for k in ("os", "python", "fastapi")) or not isinstance(_env.get("dotenv"), bool) or "FAKE-" in json.dumps(_env):
    failures.append(f"the Info endpoint misreports the environment: {_env}")
_lim = _result("[en] about after refresh")["body"]["limits"]["rows"]
_lim_by = {(r["service"], r["scope"], r["window"]): r for r in _lim}
if _lim_by.get(("abuseipdb", "check", "day"), {}).get("used") != 18 or _lim_by[("abuseipdb", "check", "day")]["source"] != "headers":
    failures.append(f"limits: AbuseIPDB usage not taken from the rate-limit headers: {_lim_by.get(('abuseipdb', 'check', 'day'))}")
if _lim_by.get(("virustotal", "requests", "month"), {}).get("limit") != 15500 or _lim_by[("virustotal", "requests", "day")]["source"] != "api":
    failures.append("limits: VirusTotal quotas not read from the quota endpoint")
if _lim_by.get(("cloudflare_radar", "requests", "5min"), {}).get("used") != 10:
    failures.append(f"limits: Cloudflare usage not taken from the Ratelimit headers: {_lim_by.get(('cloudflare_radar', 'requests', '5min'))}")
if ("urlscan", "scan_private", "day") not in _lim_by or ("openrouter", "credits", "total") not in _lim_by or ("openrouter", "free_models", "day") not in _lim_by:
    failures.append(f"limits: urlscan / OpenRouter rows missing: {sorted(_lim_by)}")
_g = _lim_by.get(("greynoise", "searches", "week"), {})
if not _g or _g["source"] != "local" or _g["limit"] != 50 or not _g["used"]:
    failures.append(f"limits: GreyNoise searches are not counted locally: {_g}")
if not (_g.get("exceeded") and _g["exceeded"].get("reset_text") == "September 29" and _g["used"] == _g["limit"]):
    failures.append(f"limits: the HTTP 429 of GreyNoise is not shown in the Info tab: {_g}")
if any(r.get("exceeded") for r in _lim if r["service"] != "greynoise"):
    failures.append("limits: another service is marked as exceeded")
_o = _lim_by.get(("otx", "requests", "hour"), {})
if not _o or not _o["used"]:
    failures.append(f"limits: OTX requests are not counted locally: {_o}")
if "sk-or-v1" in json.dumps(_result("[en] limits refresh")["body"]):
    failures.append("limits: a key label leaked into the answer")
_kept = [h for h in _after_clear if h["type"] in ("lookup", "urlscan", "dmarc")]
if not _kept or not all(h["pinned"] for h in _kept):
    failures.append(f"History clear must keep exactly the pinned entries: {_after_clear}")
if UNHANDLED:
    failures.append(f"{len(UNHANDLED)} request(s) left the mocks: {UNHANDLED[:3]}")
if probes["foreign Host header accepted (DNS rebinding)"] != 400:
    failures.append("a foreign Host header is not rejected")
if not (probes["CSP header on /"] or "").startswith("default-src 'self'"):
    failures.append("the Content-Security-Policy header is missing")
if probes["urlscan uuid path injection"] not in (400, 404):
    failures.append("urlscan result accepts a path-traversal identifier")
if probes["urlscan screenshot"] != (200, "image/png", b"\x89PNG"):
    failures.append(f"urlscan screenshot proxy answered {probes['urlscan screenshot']}")
_defanged = [x for x in SCANS if x["url"] == "https://phish.example/login" and x["visibility"] == "private"]
if len(_defanged) != 2 or any(x["url"].startswith("hxxp") for x in SCANS) or any(x["visibility"] not in ("unlisted", "private", "public") for x in SCANS):
    failures.append(f"urlscan submissions were not normalised (defanged URL, visibility): {SCANS}")
if any("192.168" in x["url"] or x["url"].startswith("javascript") for x in SCANS):
    failures.append("urlscan accepted a private host or a non-HTTP scheme")
_opts = [x for x in SCANS if "country" in x or "customagent" in x]
if not _opts or any(x.get("country") != "pl" or x.get("customagent") != "Mozilla/5.0 (Test)" for x in _opts):
    failures.append(f"urlscan scan options (country, custom user agent) were not passed on correctly: {_opts}")
if not SEARCHES or any('page.domain:"phish.example"' not in q.replace("%22", '"').replace("%3A", ":") for q in SEARCHES):
    failures.append(f"urlscan search query was not the plain domain query: {SEARCHES[:2]}")
_summary = summary_stub
_forms = _summary.get("forms") or []
if not (len(_forms) == 2 and _forms[0]["password"] and _forms[0]["external"] and not _forms[1]["external"] and _forms[0]["fields"] == ["text:user", "password:pw"]):
    failures.append(f"urlscan form extraction is wrong: {_forms}")
if not (_summary["verdict"]["level"] == "high" and len(_summary["redirects"]) == 2 and _summary["tls"]["age_days"] == 1 and _summary["verdict"]["brands"]):
    failures.append(f"urlscan summary is wrong: {_summary['verdict']}, redirects={_summary['redirects']}")
if probes["text/plain cross-site POST (CSRF without preflight)"] not in (403, 422):
    failures.append("a text/plain cross-site POST reached the handler")
_themes = _themes_resp.json()
if [th["id"] for th in _themes] != ["light", "sumi-brown", "blue", "kohaku"] or any("colors" in th for th in _themes):
    failures.append(f"theme list is wrong (shipped themes light, sumi-brown, blue and kohaku, no colours in the list): {_themes}")
if not re.fullmatch(r'(:root\[data-theme="[a-z0-9-]+"\]\{color-scheme:(?:dark|light);--logo-dark-display:(?:inline|none);--logo-light-display:(?:inline|none);(?:--[a-z-]+:#[0-9a-f]{6};)+\}\n)+', _themes_css.text) \
        or not _themes_css.headers.get("content-type", "").startswith("text/css"):
    failures.append("themes.css holds something other than whitelisted colour variables")
# hostile themes dropped into the folder must never reach the stylesheet: the validator whitelists every piece of them
import backend.themes as _themes_mod  # noqa: E402

_theme_dir = Path(tempfile.mkdtemp(prefix="seisa-themes-"))
_theme_base = {"name": {"en": "X", "pl": "X"}, "base": "light", "order": 40,
               "colors": dict.fromkeys(_themes_mod.COLOR_KEYS, "#123456")}
_theme_cases = {
    "okcopy": {},  # control: valid, so the folder switch itself works
    "badstripe": {"stripe": {"top": "#abcdef", "bottom": "#123456"}},  # a key no theme may have (the header stripe was removed)
    "badinfo": {"colors": {**_theme_base["colors"], "info": "#123456;}body{display:none"}},
    "badtop": {"x-rule": "body{display:none}"},
    "okmask": {"logo": "mask"},  # control: the one allowed non-default logo word works
    "badlogo": {"logo": "url(https://attacker.example/x)"},
    "badlogotype": {"logo": ["mask"]},
}
for _tid, _over in _theme_cases.items():
    (_theme_dir / f"{_tid}.json").write_text(json.dumps({**_theme_base, "id": _tid, **_over}), encoding="utf-8")
_real_theme_dir = _themes_mod.THEMES_DIR
_themes_mod.THEMES_DIR = _theme_dir
try:
    _hostile_list = client.get("/api/themes").json()
    _hostile_css = client.get("/api/themes.css").text
finally:
    _themes_mod.THEMES_DIR = _real_theme_dir
    shutil.rmtree(_theme_dir, ignore_errors=True)
if [th["id"] for th in _hostile_list] != ["okcopy", "okmask"] or "attacker" in _hostile_css or "body{" in _hostile_css or "extra" in _hostile_css:
    failures.append(f"a hostile theme file got through the theme validator: {[th['id'] for th in _hostile_list]}")
_blocked = ["guard GET Sec-Fetch-Site cross-site", "guard themes.css cross-site", "guard GET Sec-Fetch-Site same-site", "guard GET foreign Origin", "guard GET Origin null",
            "guard GET dmarc geo cross-site", "guard body-less POST cross-site", "guard preflight foreign Origin",
            "guard icon POST cross-site", "guard icon DELETE cross-site", "guard shutdown POST cross-site"]
_allowed = ["guard GET Sec-Fetch-Site same-origin", "guard GET Sec-Fetch-Site none", "guard GET loopback Origin", "guard GET no fetch metadata",
            "guard static index cross-site"]
for _k in _blocked:
    if probes[_k] != 403:
        failures.append(f"the origin guard let through: {_k} -> {probes[_k]}")
if probes["icon entry after cross-site POST"] or not probes["icon entry after cross-site DELETE"] or probes["icon entry after the real remove"]:
    failures.append(f"the desktop icon was changed by a cross-site request, or a same-origin one did not work: {[probes[k] for k in probes if k.startswith('icon entry')]}")
if (probes["shutdown calls after cross-site"], probes["shutdown POST same-origin"], probes["shutdown calls after same-origin"]) != (0, 200, 1):
    failures.append(f"the shutdown endpoint: a cross-site request must not stop the server, a same-origin one must (once): {[probes[k] for k in probes if k.startswith('shutdown')]}")
_icon_states = [_result(f"[en] {n}")["body"]["status"] for n in ("icon status", "icon install", "icon status after install", "icon remove", "icon status after remove")]
if _icon_states != ["absent", "installed", "installed", "absent", "absent"]:
    failures.append(f"the desktop icon endpoints report {_icon_states}")
for _k in _allowed:
    if probes[_k] != 200:
        failures.append(f"the origin guard blocked a legitimate request: {_k} -> {probes[_k]}")
if probes["CORS allow-origin header"]:
    failures.append("a cross-origin preflight is allowed")

# The two prompt files (backend/prompts/) must reach the model: a wrong path is not an error in the app, it only sends an
# empty guide or policy. Every Email analysis carries the guide, every AbuseIPDB assessment the policy excerpt.
_streams = [text for streamed, text in LLM_PROMPTS if streamed]
_assessments = [text for streamed, text in LLM_PROMPTS if not streamed and "Excerpt of the AbuseIPDB policy" in text]
if not _streams or not all("# E-mail source analysis guide" in text for text in _streams):
    failures.append(f"the Email analysis prompt lacks the guide from backend/prompts/ ({len(_streams)} streamed call(s))")
if not _assessments or not all("# AbuseIPDB reporting rules" in text for text in _assessments):
    failures.append(f"the AbuseIPDB prompt lacks the policy from backend/prompts/ ({len(_assessments)} assessment call(s))")

# Markdown reports (IP and URLScan tabs) hold hostile third-party text (the XSS payload sits in OTX pulses, the page title,
# link texts ...): outside code it must never be live markup. The raw API response in the collapsible block is code.
for _r in RESULTS:
    _body = _r["body"] if isinstance(_r["body"], dict) else {}
    _md = _body.get("markdown") if ("indicator_type" in _body or "summary" in _body) else None  # not the LLM text of an analysis
    if isinstance(_md, str):
        _md = re.sub(r"<details>.*?</details>", "", _md, flags=re.S)
        _md = re.sub(r"`[^`\n]*`", "", _md)
        _md = _md.replace("](<https://urlscan.io/result/", "")  # the one link Seisa builds itself
        if re.search(r"(?<!\\)<img|\]\(\s*<?https?:", _md, re.I):
            failures.append(f"{_r['name']}: the Markdown report holds live markup from a remote source")

if OUT:
    OUT.write_text(json.dumps({"results": RESULTS}, ensure_ascii=False, indent=1, sort_keys=True))
    OUT.with_suffix(".meta.json").write_text(json.dumps(
        {"calls": sorted(set(CALLS)), "unhandled": UNHANDLED, "probes": probes, "stream_calls": STREAM_COUNT["n"]},
        ensure_ascii=False, indent=1, default=lambda o: o.hex() if isinstance(o, bytes) else str(o)))  # probes hold raw bytes
print(f"{len(RESULTS)} endpoint results, {len(UNHANDLED)} unhandled external requests, {len(failures)} failure(s)")
for f in failures:
    print("FAIL:", f)
sys.exit(1 if failures else 0)

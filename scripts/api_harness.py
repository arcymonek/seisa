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
security probe (foreign Host header, CSP header, path injection) fails. `--out` writes the normalised answers
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
socket.gethostbyaddr = lambda ip: (f"rdns-{ip.replace('.', '-')}.example", [], [ip])

import httpx  # noqa: E402

XSS = '<img src=x onerror="window.__xss=1">'
CALLS: list[str] = []
SCANS: list[dict] = []
UNHANDLED: list[str] = []


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


def handler(request: httpx.Request) -> httpx.Response:
    host, path = request.url.host, request.url.path
    CALLS.append(f"{request.method} {host}{path}")
    if host == "api.abuseipdb.com" and path.endswith("/check"):
        return httpx.Response(200, json={"data": {
            "ipAddress": request.url.params.get("ipAddress"), "abuseConfidenceScore": 42, "totalReports": 7,
            "numDistinctUsers": 3, "isWhitelisted": False, "isTor": False, "isPublic": True, "countryCode": "NL",
            "domain": "example.net", "hostnames": [], "isp": "Example ISP", "usageType": "Data Center",
            "lastReportedAt": "2026-09-20T10:00:00+00:00",
            "reports": [{"reportedAt": "2026-09-20T10:00:00+00:00", "comment": "spam " + XSS,
                         "categories": [11, 99], "reporterId": 1, "reporterCountryName": "Poland"}]}})
    if host == "api.abuseipdb.com" and path.endswith("/report"):
        return httpx.Response(200, json={"data": {"ipAddress": "x", "abuseConfidenceScore": 43}})
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
    if host == "api.cloudflare.com":
        return httpx.Response(200, json={"success": True, "result": {"ip": {"asn": 64500, "location": "DE", "asnName": "EXAMPLE-AS"}}})
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
        usage = {"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200, "cost": 0.0123}
        if payload.get("stream"):
            STREAM_COUNT["n"] += 1
            if len(payload["messages"]) > 2:  # continuation
                return httpx.Response(200, content=_sse(["\n\n## Part 6\nRest \u2014 done."], "stop", usage),
                                      headers={"content-type": "text/event-stream"})
            return httpx.Response(200, content=_sse(
                ["VERDICT: phishing | CONFIDENCE: high\n\n# Analysis\n", "IP 203.0.113.45 and 192.0.2.99 \u2014 ",
                 "`Received-SPF: fail`\n\n```\nX-Fake-Header: nothing\n```\n", "SCL=9 <b>bold</b> [link](https://evil.example/)"],
                "length", usage), headers={"content-type": "text/event-stream"})
        content = json.dumps({"qualifies": True, "reasoning": "r " + XSS, "suggested_categories": [7, 11],
                              "report_comment": "Phishing from 203.0.113.45 \u2014 test", "alternatives": "",
                              "source_ip_check": {"agrees": False, "suggested_ip": "198.51.100.7", "reasoning": "x"},
                              "received_verified": {"status": "pass", "note": "n"},
                              "not_spoofed_source": {"status": "pass", "note": "n"},
                              "category_matches": {"status": "pass", "note": "n"},
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
import backend.config as cfg  # noqa: E402

cfg.DATA_DIR = TMP / "data"
cfg.HISTORY_FILE = cfg.DATA_DIR / "history.json"
cfg.VT_USAGE_FILE = cfg.DATA_DIR / "vt_usage.json"
cfg.REPORT_LOG_FILE = cfg.DATA_DIR / "report_log.json"
# the directory constants were renamed in 2.0.27 (ANALIZY_DIR / LOGI_DIR): patch whichever exists, so that `--root`
# can point at an older checkout
for names, val in ((("ANALYSES_DIR", "ANALIZY_DIR"), cfg.DATA_DIR / "analyses"), (("LOGS_DIR", "LOGI_DIR"), TMP / "logs")):
    for name in names:
        if hasattr(cfg, name):
            setattr(cfg, name, val)

from fastapi.testclient import TestClient  # noqa: E402

import backend.main as main  # noqa: E402
from backend.ratelimit import vt_rate_limiter  # noqa: E402

vt_rate_limiter._minute_limiter.max_calls = 10_000

if _args.serve:
    import uvicorn

    print(f"Seisa with mocked services on http://127.0.0.1:{_args.serve} (data in {TMP})")
    uvicorn.run(main.app, host="127.0.0.1", port=_args.serve, log_level="warning")
    sys.exit(0)

client = TestClient(main.app, base_url="http://127.0.0.1")
RESULTS: list[dict] = []

VOLATILE_KEYS = {"id", "queried_at", "created_at", "submitted_at", "last_submitted_at", "analysis_id", "time",
                 "age_days", "age_ok", "age_reason", "all_passed", "cooldown_left_minutes", "delta_s"}
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
    rec(p + "lookup ip", client.post("/api/lookup", json={"indicator": PUBLIC_IP, "type": "ip", "force_refresh": True}, headers=H))
    rec(p + "lookup domain", client.post("/api/lookup", json={"indicator": "example.com", "type": "domain", "force_refresh": True}, headers=H))
    rec(p + "lookup invalid", client.post("/api/lookup", json={"indicator": "a/../../x", "type": "domain"}, headers=H))
    rec(p + "lookup invalid ip", client.post("/api/lookup", json={"indicator": "not-an-ip", "type": "ip"}, headers=H))
    rec(p + "lookup batch", client.post("/api/lookup/batch", json={"indicators": [PUBLIC_IP, "example.com", " ", "a/../../x"], "force_refresh": True}, headers=H), sse=True)
    rec(p + "lookup batch too many", client.post("/api/lookup/batch", json={"indicators": ["1.1.1.1"] * 201}, headers=H))
    rec(p + "urlscan scan", client.post("/api/urlscan/scan", json={"url": "https://phish.example/login"}, headers=H))
    rec(p + "urlscan result", client.get("/api/urlscan/result/11111111-2222-3333-4444-555555555555", headers=H))
    rec(p + "urlscan result bad uuid", client.get("/api/urlscan/result/not-a-uuid", headers=H))
    rec(p + "urlscan scan defanged", client.post("/api/urlscan/scan", json={"url": "hxxps://phish[.]example/login", "visibility": "private"}, headers=H))
    rec(p + "urlscan scan private host", client.post("/api/urlscan/scan", json={"url": "http://192.168.1.10/admin"}, headers=H))
    rec(p + "urlscan scan bad scheme", client.post("/api/urlscan/scan", json={"url": "javascript:alert(1)"}, headers=H))
    rec(p + "urlscan scan bad visibility", client.post("/api/urlscan/scan", json={"url": "https://phish.example/", "visibility": "everyone"}, headers=H))
    rec(p + "urlscan screenshot bad uuid", client.get("/api/urlscan/screenshot/not-a-uuid", headers=H))
    shot = client.get("/api/urlscan/screenshot/11111111-2222-3333-4444-555555555555", headers=H)
    SHOT_PROBE = (shot.status_code, shot.headers.get("content-type"), shot.content[:4])
    for name, src in FIX.items():
        rec(p + f"abuseipdb analyze {name} no-llm", client.post("/api/abuseipdb/email/analyze", json={"raw_email": src, "use_llm": False}, headers=H))
        rec(p + f"abuseipdb analyze {name} llm", client.post("/api/abuseipdb/email/analyze", json={"raw_email": src, "use_llm": True}, headers=H))
    fields = {"ip": PUBLIC_IP, "categories": [11], "attack_timestamp": "2026-09-24T10:00:00Z", "comment": "=test \u2014 comment"}
    rec(p + "report preview", client.post("/api/abuseipdb/report/preview", json=fields, headers=H))
    rec(p + "report preview private ip", client.post("/api/abuseipdb/report/preview", json={**fields, "ip": "10.0.0.1"}, headers=H))
    rec(p + "ip-info", client.get(f"/api/abuseipdb/ip-info?ip={PUBLIC_IP}", headers=H))
    rec(p + "ip-info private", client.get("/api/abuseipdb/ip-info?ip=10.0.0.1", headers=H))
    rec(p + "report submit bad", client.post("/api/abuseipdb/report/submit", json={**fields, "categories": []}, headers=H))
    ip_lang = PUBLIC_IP if lang == "pl" else "185.220.101.2"
    rec(p + "report submit ok", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": ip_lang}, headers=H))
    rec(p + "report submit cooldown", client.post("/api/abuseipdb/report/submit", json={**fields, "ip": ip_lang}, headers=H))
    for name, src in FIX.items():
        rec(p + f"email find {name}", client.post("/api/email/find", json={"raw_email": src}, headers=H))
    ev = rec(p + "email analyze phishing", client.post("/api/email/analyze", json={"raw_email": FIX["phishing"]}, headers=H), sse=True)
    rec(p + "email analyze empty", client.post("/api/email/analyze", json={"raw_email": "  "}, headers=H), sse=True)
    aid = next((e.get("analysis_id") for e in ev if e.get("type") == "done"), None)
    rec(p + "email analyses", client.get("/api/email/analyses", headers=H))
    if aid:
        rec(p + "email analysis get", client.get(f"/api/email/analyses/{aid}", headers=H))
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
    rec(p + "logs all", client.get("/api/logs?range=all&service=all", headers=H))
    rec(p + "logs today abuseipdb", client.get("/api/logs?range=today&service=abuseipdb", headers=H))
    if aid:
        rec(p + "email delete", client.delete(f"/api/email/analyses/{aid}", headers=H))
    rec(p + "history clear", client.delete("/api/history", headers=H))

rec("static index", client.get("/"))
rec("i18n catalog", client.get("/i18n/en.json"))

# --- security probes (not part of the golden comparison) ---
probes = {}
probes["foreign Host header accepted (DNS rebinding)"] = client.get("/api/history", headers={"Host": "attacker.example"}).status_code
r = client.post("/api/abuseipdb/report/preview", content=json.dumps(fields), headers={"Content-Type": "text/plain", "Origin": "https://attacker.example"})
probes["text/plain cross-site POST (CSRF without preflight)"] = r.status_code
r = client.options("/api/abuseipdb/report/submit", headers={"Origin": "https://attacker.example", "Access-Control-Request-Method": "POST"})
probes["CORS preflight status"] = r.status_code
probes["CORS allow-origin header"] = r.headers.get("access-control-allow-origin")
probes["CSP header on /"] = client.get("/").headers.get("content-security-policy")
probes["urlscan uuid path injection"] = client.get("/api/urlscan/result/..%2F..%2Fuser%2Fquotas").status_code
probes["urlscan screenshot"] = SHOT_PROBE

# --- checks ---
EXPECTED_STATUS = {
    "lookup ip": 200, "lookup domain": 200, "lookup invalid": 400, "lookup invalid ip": 400, "lookup batch": 200,
    "lookup batch too many": 422, "urlscan scan": 200, "urlscan result": 200, "urlscan result bad uuid": 400,
    "urlscan scan defanged": 200, "urlscan scan private host": 400, "urlscan scan bad scheme": 400, "urlscan scan bad visibility": 400,
    "urlscan screenshot bad uuid": 400, "history create urlscan": 200, "history create urlscan bad thumbnail": 400,
    "history create urlscan no summary": 400,
    "report preview": 200, "ip-info": 200, "report submit bad": 400, "report submit ok": 200,
    "report submit cooldown": 409, "email analyze phishing": 200, "email bad id": 404, "email bad id2": 400,
    "email continue again (not truncated)": 400, "history create dmarc": 200, "history create bad": 400,
    "history entry missing": 404, "static index": 200,
}
failures = []
for r in RESULTS:
    want = EXPECTED_STATUS.get(r["name"].split("] ", 1)[-1])
    if want is not None and r["status"] != want:
        failures.append(f"{r['name']}: status {r['status']}, expected {want}")
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
_summary = summary_stub
if not (_summary["verdict"]["level"] == "high" and len(_summary["redirects"]) == 2 and _summary["tls"]["age_days"] == 1 and _summary["verdict"]["brands"]):
    failures.append(f"urlscan summary is wrong: {_summary['verdict']}, redirects={_summary['redirects']}")
if probes["CORS allow-origin header"]:
    failures.append("a cross-origin preflight is allowed")

if OUT:
    OUT.write_text(json.dumps({"results": RESULTS}, ensure_ascii=False, indent=1, sort_keys=True))
    OUT.with_suffix(".meta.json").write_text(json.dumps(
        {"calls": sorted(set(CALLS)), "unhandled": UNHANDLED, "probes": probes, "stream_calls": STREAM_COUNT["n"]},
        ensure_ascii=False, indent=1))
print(f"{len(RESULTS)} endpoint results, {len(UNHANDLED)} unhandled external requests, {len(failures)} failure(s)")
for f in failures:
    print("FAIL:", f)
sys.exit(1 if failures else 0)

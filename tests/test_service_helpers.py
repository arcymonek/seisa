"""The shared HTTP helper of the services (`fetch_json` with a status map), GreyNoise on top of it, `int_header`, the
form check of urlscan, the OTX address-family path, the WHOIS / reverse-DNS service (no PTR, one-line log, time limits)
and the known-sender check of the DMARC "geo" answer. No network: every request goes to an httpx.MockTransport, DNS and
WHOIS are replaced by functions.

Expected values come from the documentation of the services: GreyNoise answers 404 for an address it has no data about
and 429 for an exhausted quota (https://docs.greynoise.io), OTX names the path by address family
(https://otx.alienvault.com/api), reverse names follow RFC 1035 (IPv4) and RFC 3596 (IPv6)."""
from __future__ import annotations

import asyncio
import logging
import time

import httpx
import pytest
from fastapi.testclient import TestClient

import backend.routers.dmarc as dmarc_router
import backend.services.dns_records as dns_records
import backend.services.whois_dns as whois_dns
from backend.aggregator import SERVICE_REGISTRY
from backend.api_limits import RESET_DATE_RE, int_header
from backend.config import settings
from backend.i18n import t
from backend.identity import build_identity
from backend.main import app
from backend.markdown_report import build_markdown
from backend.models import RiskScore, ServiceResult
from backend.services.base import IntelService
from backend.services.greynoise import GreyNoiseService
from backend.services.otx import OtxService
from backend.urlscan_forms import extract_forms

client = TestClient(app, base_url="http://127.0.0.1")


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def http(monkeypatch):
    """Every httpx request goes to `state["answer"]` (set by the test); the requests are recorded."""
    state = {"answer": lambda request: httpx.Response(200, json={}), "requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        return state["answer"](request)

    real = httpx.AsyncClient

    def make(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", make)
    monkeypatch.setattr(settings, "greynoise_api_key", "test-key")
    monkeypatch.setattr(settings, "otx_api_key", "test-key")
    return state


# ---- fetch_json with a status map ----

class _Probe(IntelService):
    name = "probe"

    async def query_ip(self, ip):  # pragma: no cover - abstract members only
        raise NotImplementedError

    async def query_domain(self, domain):  # pragma: no cover
        raise NotImplementedError


def test_fetch_json_without_a_map_keeps_its_old_contract(http):
    http["answer"] = lambda r: httpx.Response(200, json={"a": 1})
    assert run(_Probe().fetch_json("GET", "https://example.org/x")) == ({"a": 1}, None)
    http["answer"] = lambda r: httpx.Response(404, text="nope")
    data, err = run(_Probe().fetch_json("GET", "https://example.org/x"))
    assert data is None and err.status == "error" and "HTTP 404" in err.error_message
    http["answer"] = lambda r: httpx.Response(200, text="<html>")
    data, err = run(_Probe().fetch_json("GET", "https://example.org/x"))
    assert data is None and "not JSON" in err.error_message


def test_fetch_json_status_map_takes_a_plain_or_an_async_handler(http):
    probe = _Probe()
    sync_result = ServiceResult(service="probe", status="ok", summary={"via": "sync"})

    async def later(resp):
        return ServiceResult(service="probe", status="ok", summary={"via": "async", "code": resp.status_code})

    http["answer"] = lambda r: httpx.Response(404)
    assert run(probe.fetch_json("GET", "https://example.org/x", special={404: lambda resp: sync_result})) == (None, sync_result)
    http["answer"] = lambda r: httpx.Response(403)
    data, result = run(probe.fetch_json("GET", "https://example.org/x", special={403: later}))
    assert data is None and result.summary == {"via": "async", "code": 403}
    # a status that is not in the map still goes the usual way
    http["answer"] = lambda r: httpx.Response(500, text="boom")
    data, err = run(probe.fetch_json("GET", "https://example.org/x", special={404: lambda resp: sync_result}))
    assert data is None and "HTTP 500" in err.error_message


# ---- int_header and the reset date ----

def test_int_header_reads_numbers_and_ignores_everything_else():
    headers = {"X-RateLimit-Limit": "1000", "Retry-After": "soon", "Empty": ""}
    assert int_header(headers, "X-RateLimit-Limit") == 1000
    assert int_header(headers, "Retry-After") is None
    assert int_header(headers, "Empty") is None
    assert int_header(headers, "Missing") is None


def test_reset_date_regex_finds_the_date_greynoise_names():
    assert RESET_DATE_RE.search("You have reached your daily limit. Your searches will reset on September 29").group(1) == "September 29"
    assert RESET_DATE_RE.search("no date here") is None


# ---- GreyNoise (the 404/429/403 answers are documented behaviour) ----

IP = "8.8.8.8"


def test_greynoise_full_lookup(http):
    http["answer"] = lambda r: httpx.Response(200, json={
        "ip": IP,
        "business_service_intelligence": {"found": False},
        "internet_scanner_intelligence": {
            "found": True, "classification": "malicious", "actor": "unknown", "tor": False,
            "tags": [{"name": "SSH Scanner"}, {"name": ""}],
            "metadata": {"organization": "Example Org", "asn": "AS64500", "source_country_code": "NL"},
        },
    })
    result = run(GreyNoiseService().query_ip(IP))
    assert result.status == "ok"
    assert result.summary["classification"] == "malicious"
    assert result.summary["tags"] == ["SSH Scanner"]
    assert result.summary["organization"] == "Example Org"
    assert http["requests"][0].headers["key"] == "test-key"
    assert str(http["requests"][0].url) == f"https://api.greynoise.io/v3/ip/{IP}"


def test_greynoise_404_means_no_data_not_an_error(http):
    http["answer"] = lambda r: httpx.Response(404, json={"message": "IP not found"})
    result = run(GreyNoiseService().query_ip(IP))
    assert result.status == "ok"
    assert result.summary == {"has_data": False, "message": t("svc.greynoise_no_data_message")}


def test_greynoise_429_names_the_reset_date(http):
    http["answer"] = lambda r: httpx.Response(429, text="Daily limit reached. Your searches will reset on September 29")
    result = run(GreyNoiseService().query_ip(IP))
    assert result.status == "rate_limited_daily"
    assert result.error_message == t("svc.greynoise_limit_reset", date="September 29")


def test_greynoise_429_without_a_date(http):
    http["answer"] = lambda r: httpx.Response(429, text="slow down")
    assert run(GreyNoiseService().query_ip(IP)).error_message == t("svc.greynoise_limit")


def test_greynoise_403_falls_back_to_the_community_endpoint(http):
    def answer(request):
        if request.url.path.startswith("/v3/community/"):
            return httpx.Response(200, json={"ip": IP, "noise": True, "riot": False, "classification": "benign", "name": "Example", "link": "https://viz.greynoise.io/ip/8.8.8.8", "last_seen": "2026-10-01"})
        return httpx.Response(403, json={"message": "forbidden"})

    http["answer"] = answer
    result = run(GreyNoiseService().query_ip(IP))
    assert [r.url.path for r in http["requests"]] == [f"/v3/ip/{IP}", f"/v3/community/{IP}"]
    assert result.status == "ok"
    assert result.summary["source"] == t("svc.greynoise_community")
    assert result.summary["classification"] == "benign" and result.summary["noise"] is True


@pytest.mark.parametrize(("community_status", "body", "expected_status"), [(404, "", "ok"), (429, "Your searches will reset on October 3", "rate_limited_daily"), (500, "boom", "error")])
def test_greynoise_community_answers(http, community_status, body, expected_status):
    http["answer"] = lambda r: httpx.Response(403) if r.url.path.startswith("/v3/ip/") else httpx.Response(community_status, text=body)
    result = run(GreyNoiseService().query_ip(IP))
    assert result.status == expected_status
    if community_status == 404:
        assert result.summary["has_data"] is False


def test_greynoise_server_error_and_bad_json_are_errors(http):
    http["answer"] = lambda r: httpx.Response(500, text="boom")
    assert run(GreyNoiseService().query_ip(IP)).status == "error"
    http["answer"] = lambda r: httpx.Response(200, text="not json")
    assert "not JSON" in run(GreyNoiseService().query_ip(IP)).error_message


def test_greynoise_without_a_key_sends_nothing(http, monkeypatch):
    monkeypatch.setattr(settings, "greynoise_api_key", "")
    assert run(GreyNoiseService().query_ip(IP)).status == "no_key"
    assert http["requests"] == []


# ---- the forms of a scanned page (urlscan_forms) ----

def _form_to(action: str) -> str:
    return f'<form method="post" action="{action}"><input type="password" name="p"></form>'


@pytest.mark.parametrize(("page", "action", "external"), [
    ("https://login.bank.example/", "https://bank.example/auth", False),       # the page is a sub-domain of the target
    ("https://bank.example/", "https://login.bank.example/auth", False),       # the target is a sub-domain of the page
    ("https://bank.example/", "https://bank.example.evil.test/auth", True),    # a look-alike that only STARTS with it
    ("https://bank.example/", "https://evilbank.example/auth", True),          # shares the end, not the label boundary
    ("https://bank.example/", "/relative/path", False),
    ("https://bank.example/", "https://other.test/", True),
])
def test_form_target_is_external_by_label_boundary(page, action, external):
    forms = extract_forms(_form_to(action), page, None)
    assert forms[0]["external"] is external


def test_form_check_uses_the_domain_urlscan_reports_when_given():
    forms = extract_forms(_form_to("https://bank.example.evil.test/a"), "https://login.bank.example/", "bank.example")
    assert forms[0]["external"] is True
    assert extract_forms(_form_to("https://login.bank.example/a"), "https://x.test/", "bank.example")[0]["external"] is False


# ---- OTX path by address family ----

@pytest.mark.parametrize(("ip", "family"), [("8.8.8.8", "IPv4"), ("2001:4860:4860::8888", "IPv6")])
def test_otx_path_names_the_address_family(http, ip, family):
    http["answer"] = lambda r: httpx.Response(200, json={"indicator": ip, "pulse_info": {"count": 0, "pulses": []}})
    run(OtxService().query_ip(ip))
    assert http["requests"][0].url.path == f"/api/v1/indicators/{family}/{ip}/general"


def test_otx_domain_path(http):
    http["answer"] = lambda r: httpx.Response(200, json={"pulse_info": {"count": 0, "pulses": []}})
    run(OtxService().query_domain("example.org"))
    assert http["requests"][0].url.path == "/api/v1/indicators/domain/example.org/general"


# ---- reverse DNS through dnspython ----

def test_reverse_lookup_asks_for_the_ptr_of_the_reverse_name(monkeypatch):
    asked = []

    async def fake_query(name, rdtype):
        asked.append((name, rdtype))
        return ["dns.google."], False

    monkeypatch.setattr(dns_records, "_query", fake_query)
    assert run(dns_records.reverse_lookup("8.8.8.8")) == "dns.google"  # without the trailing dot
    assert run(dns_records.reverse_lookup("2001:4860:4860::8888")) == "dns.google"
    assert asked[0] == ("8.8.8.8.in-addr.arpa.", "PTR")  # RFC 1035 section 3.5
    # RFC 3596 section 2.5: 2001:4860:4860:0000:0000:0000:0000:8888 written as 32 nibbles, last one first
    expected = "8.8.8.8." + "0." * 16 + "0.6.8.4." + "0.6.8.4." + "1.0.0.2." + "ip6.arpa."
    assert asked[1] == (expected, "PTR")


def test_reverse_lookup_without_a_record_or_with_a_bad_address(monkeypatch):
    async def none(name, rdtype):
        return [], True

    monkeypatch.setattr(dns_records, "_query", none)
    assert run(dns_records.reverse_lookup("8.8.8.8")) is None
    assert run(dns_records.reverse_lookup("not an address")) is None


def test_reverse_lookup_has_the_resolver_time_limit():
    resolver = dns_records._resolver()
    assert resolver.lifetime == dns_records.QUERY_TIMEOUT and resolver.timeout == dns_records.QUERY_TIMEOUT


RDAP_OK = {"handle": "NET-8-8-8-0-1", "name": "LVLT-GOGL", "country": "US", "startAddress": "8.8.8.0", "endAddress": "8.8.8.255", "ipVersion": "v4"}


def test_ip_summary_has_none_for_a_missing_ptr_and_the_name_otherwise(http, monkeypatch):
    http["answer"] = lambda r: httpx.Response(200, json=RDAP_OK)

    async def no_ptr(ip):
        return None

    async def ptr(ip):
        return "dns.google"

    monkeypatch.setattr(whois_dns, "reverse_lookup", no_ptr)
    assert run(whois_dns.WhoisDnsService().query_ip("8.8.8.8")).summary["reverse_dns"] is None
    monkeypatch.setattr(whois_dns, "reverse_lookup", ptr)
    assert run(whois_dns.WhoisDnsService().query_ip("8.8.8.8")).summary["reverse_dns"] == "dns.google"


def test_a_failing_reverse_lookup_does_not_stop_the_rdap_part(http, monkeypatch, caplog):
    http["answer"] = lambda r: httpx.Response(200, json=RDAP_OK)

    async def broken(ip):
        raise RuntimeError("resolver exploded")

    monkeypatch.setattr(whois_dns, "reverse_lookup", broken)
    with caplog.at_level(logging.ERROR, logger="whois_rdns"):
        result = run(whois_dns.WhoisDnsService().query_ip("8.8.8.8"))
    assert result.status == "ok" and result.summary["network_name"] == "LVLT-GOGL"
    assert any("reverse DNS failed" in r.getMessage() for r in caplog.records)


def test_dmarc_geo_passes_a_missing_ptr_on_as_none(monkeypatch):
    async def fake(ip):
        return ServiceResult(service="whois_rdns", status="ok", summary={"reverse_dns": None, "country": "US", "organization": "Example Org", "network_name": "EX-NET"})

    monkeypatch.setattr(SERVICE_REGISTRY["whois_rdns"], "query_ip", fake)
    body = client.get("/api/dmarc/geo?ip=8.8.8.8", headers={"X-Seisa-Lang": "en"}).json()
    assert body["status"] == "ok" and body["reverse_dns"] is None and body["known_sender"] is None


def test_markdown_report_says_no_ptr_in_the_language_of_the_reader():
    services = {"whois_rdns": ServiceResult(service="whois_rdns", status="ok", summary={"reverse_dns": None, "country": "US"})}
    md = build_markdown("8.8.8.8", RiskScore(level="low", score=1), services, None)
    assert f"- **reverse_dns**: {t('svc.no_ptr')}" in md
    assert "brak rekordu PTR" in md  # the tests run in Polish
    services = {"whois_rdns": ServiceResult(service="whois_rdns", status="ok", summary={"reverse_dns": "dns.google"})}
    assert "- **reverse_dns**: dns.google" in build_markdown("8.8.8.8", RiskScore(level="low", score=1), services, None)


@pytest.mark.parametrize("stored", [None, "no PTR record", "brak rekordu PTR"])
def test_identity_ignores_a_missing_ptr_whatever_form_a_saved_entry_has(stored):
    """History entries saved before 2.4.26 hold the translated placeholder, newer ones hold null: neither is a host."""
    services = {"whois_rdns": ServiceResult(service="whois_rdns", status="ok", summary={"reverse_dns": stored, "organization": "Example Org"})}
    identity = build_identity(services)
    assert "rdns" not in {f.key for f in identity.fields}


def test_identity_keeps_a_real_ptr_name():
    services = {"whois_rdns": ServiceResult(service="whois_rdns", status="ok", summary={"reverse_dns": "dns.google"})}
    fields = {f.key: f for f in build_identity(services).fields}
    assert fields["rdns"].value == "dns.google"


# ---- WHOIS of a domain ----

REGISTRY_NOTICE = 'No match for "EXAMPLE-NOT-REGISTERED.COM".\n>>> Last update of whois database: 2026-10-16 <<<\n' + "NOTICE: terms of use. " * 150


@pytest.fixture
def dns_ok(monkeypatch):
    async def resolved(domain):
        return {"exists": True, "a": ["93.184.216.34"]}

    monkeypatch.setattr(whois_dns, "resolve_domain", resolved)


def test_failed_whois_with_working_dns_logs_one_short_warning(monkeypatch, caplog, dns_ok):
    def fail(domain):
        raise RuntimeError(REGISTRY_NOTICE)

    monkeypatch.setattr(whois_dns.whois, "whois", fail)
    with caplog.at_level(logging.DEBUG, logger="whois_rdns"):
        result = run(whois_dns.WhoisDnsService().query_domain("example-not-registered.test"))
    assert result.status == "ok" and result.summary["dns"]["a"] == ["93.184.216.34"]
    records = [r for r in caplog.records if r.name == "whois_rdns"]
    assert [r.levelno for r in records] == [logging.WARNING]
    message = records[0].getMessage()
    assert "\n" not in message and len(message) <= 200 + len("WHOIS failed: ")
    assert message.startswith('WHOIS failed: No match for "EXAMPLE-NOT-REGISTERED.COM".')


def test_failed_whois_and_dns_is_an_error_result(monkeypatch):
    def fail(domain):
        raise RuntimeError("whois down")

    async def no_dns(domain):
        raise RuntimeError("dns down")

    monkeypatch.setattr(whois_dns.whois, "whois", fail)
    monkeypatch.setattr(whois_dns, "resolve_domain", no_dns)
    result = run(whois_dns.WhoisDnsService().query_domain("example.test"))
    assert result.status == "error" and result.error_message == "whois down"


def test_whois_that_never_answers_is_cut_off_and_dns_still_counts(monkeypatch, caplog, dns_ok):
    monkeypatch.setattr(whois_dns, "WHOIS_TIMEOUT", 0.05)
    monkeypatch.setattr(whois_dns.whois, "whois", lambda domain: time.sleep(0.4))
    started = time.monotonic()
    with caplog.at_level(logging.WARNING, logger="whois_rdns"):
        result = run(whois_dns.WhoisDnsService().query_domain("example.test"))
    assert result.status == "ok" and result.summary["registrar"] is None and result.summary["dns"]["exists"] is True
    assert time.monotonic() - started < 2
    assert any("TimeoutError" in r.getMessage() for r in caplog.records)


def test_whois_timeout_without_dns_gives_a_readable_error(monkeypatch):
    async def no_dns(domain):
        raise RuntimeError("dns down")

    monkeypatch.setattr(whois_dns, "WHOIS_TIMEOUT", 0.05)
    monkeypatch.setattr(whois_dns.whois, "whois", lambda domain: time.sleep(0.4))
    monkeypatch.setattr(whois_dns, "resolve_domain", no_dns)
    result = run(whois_dns.WhoisDnsService().query_domain("example.test"))
    assert result.status == "error" and "TimeoutError" in result.error_message


def test_first_line_cuts_to_the_limit():
    assert whois_dns._first_line("a" * 500 + "\nsecond") == "a" * 200
    assert whois_dns._first_line("   \n") == ""


# ---- DMARC "geo": a well-known sender only when its reverse DNS name resolves back to the same address ----

GOOGLE_PTR = "mail-sor-f41.google.com"


def _geo_with_ptr(monkeypatch, ptr):
    async def fake(ip):
        return ServiceResult(service="whois_rdns", status="ok", summary={"reverse_dns": ptr, "country": "US", "organization": "Example Org", "network_name": "EX-NET"})

    monkeypatch.setattr(SERVICE_REGISTRY["whois_rdns"], "query_ip", fake)


def test_dmarc_geo_names_a_forward_confirmed_known_sender(monkeypatch):
    _geo_with_ptr(monkeypatch, GOOGLE_PTR)
    monkeypatch.setattr(dmarc_router, "resolve_host_ips", lambda host: {"8.8.4.4"} if host == GOOGLE_PTR else set())
    body = client.get("/api/dmarc/geo?ip=8.8.4.4", headers={"X-Seisa-Lang": "en"}).json()
    assert body["known_sender"] == "Google (Gmail / Workspace)"


def test_dmarc_geo_ignores_a_ptr_that_does_not_resolve_back(monkeypatch):
    """Anyone can point the PTR of a rented server at google.com; without the forward match it proves nothing."""
    _geo_with_ptr(monkeypatch, GOOGLE_PTR)
    monkeypatch.setattr(dmarc_router, "resolve_host_ips", lambda host: {"142.250.0.1"})
    body = client.get("/api/dmarc/geo?ip=8.8.4.4", headers={"X-Seisa-Lang": "en"}).json()
    assert body["status"] == "ok" and body["reverse_dns"] == GOOGLE_PTR and body["known_sender"] is None


def test_dmarc_geo_does_not_wait_for_a_silent_resolver(monkeypatch):
    _geo_with_ptr(monkeypatch, GOOGLE_PTR)
    monkeypatch.setattr(dmarc_router, "FORWARD_LOOKUP_TIMEOUT", 0.2)

    def stuck(host):
        time.sleep(2)
        return {"8.8.4.4"}

    monkeypatch.setattr(dmarc_router, "resolve_host_ips", stuck)
    # one event loop for the whole block, as in the real server: a client per request would close its loop after the
    # answer and wait there for the abandoned thread
    with TestClient(app, base_url="http://127.0.0.1") as live:
        started = time.monotonic()
        body = live.get("/api/dmarc/geo?ip=8.8.4.4", headers={"X-Seisa-Lang": "en"}).json()
        elapsed = time.monotonic() - started
    assert elapsed < 1.5
    assert body["status"] == "ok" and body["known_sender"] is None

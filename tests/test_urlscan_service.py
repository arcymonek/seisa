"""backend/services/urlscan.py: what each call does with the answers of urlscan.io, including the paths the harness
does not reach (scan still running, server errors, a broken screenshot). urlscan.io answers 404 for a result, screenshot
or DOM that is not ready yet (documented behaviour of its API), which is not an error. No network: every request goes
to an httpx.MockTransport."""
from __future__ import annotations

import asyncio
import logging

import httpx
import pytest

import backend.services.urlscan as us
from backend.config import settings

UUID = "11111111-2222-3333-4444-555555555555"
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 16


@pytest.fixture
def urlscan(monkeypatch):
    """Routes every httpx request to `answer` (set by the test) and records the requests."""
    state = {"answer": lambda request: httpx.Response(200, json={}), "requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        return state["answer"](request)

    real = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    monkeypatch.setattr(settings, "urlscan_api_key", "test-key")
    return state


def run(coro):
    return asyncio.run(coro)


def test_submit_sends_url_visibility_and_key(urlscan):
    urlscan["answer"] = lambda r: httpx.Response(200, json={"uuid": UUID})
    assert run(us.submit_scan("https://example.org/", "private", country="de", useragent="UA")) == {"uuid": UUID}
    req = urlscan["requests"][0]
    assert req.method == "POST" and str(req.url) == us.SCAN_URL
    assert req.headers["API-Key"] == "test-key"
    assert req.read() == b'{"url":"https://example.org/","visibility":"private","country":"de","customagent":"UA"}'


def test_submit_leaves_out_empty_options(urlscan):
    run(us.submit_scan("https://example.org/"))
    assert urlscan["requests"][0].read() == b'{"url":"https://example.org/","visibility":"unlisted"}'


def test_submit_http_error_is_logged_and_raised(urlscan, caplog):
    urlscan["answer"] = lambda r: httpx.Response(429, json={"message": "slow down"})
    with caplog.at_level(logging.ERROR, logger="urlscan"), pytest.raises(us.UrlscanError) as exc:
        run(us.submit_scan("https://example.org/"))
    assert "429" in exc.value.message
    assert any(rec.levelno == logging.ERROR and rec.getMessage().startswith("scan submission failed: ") for rec in caplog.records)


def test_submit_without_key_or_with_bad_visibility_sends_nothing(urlscan, monkeypatch):
    with pytest.raises(us.UrlscanError):
        run(us.submit_scan("https://example.org/", "everyone"))
    monkeypatch.setattr(settings, "urlscan_api_key", "")
    with pytest.raises(us.UrlscanError):
        run(us.submit_scan("https://example.org/"))
    assert urlscan["requests"] == []


def test_result_pending_is_none_and_ready_is_json(urlscan):
    urlscan["answer"] = lambda r: httpx.Response(404, json={"message": "not found"})
    assert run(us.fetch_result(UUID)) is None
    urlscan["answer"] = lambda r: httpx.Response(200, json={"task": {"uuid": UUID}})
    assert run(us.fetch_result(UUID)) == {"task": {"uuid": UUID}}
    assert str(urlscan["requests"][-1].url) == us.RESULT_URL.format(uuid=UUID)


def test_result_server_error_is_logged_and_raised(urlscan, caplog):
    urlscan["answer"] = lambda r: httpx.Response(500, text="oops")
    with caplog.at_level(logging.ERROR, logger="urlscan"), pytest.raises(us.UrlscanError):
        run(us.fetch_result(UUID))
    assert any(rec.getMessage().startswith("fetching the scan result failed: ") for rec in caplog.records)


def test_screenshot_ready_missing_and_rejected(urlscan, caplog):
    urlscan["answer"] = lambda r: httpx.Response(200, content=PNG)
    assert run(us.fetch_screenshot(UUID)) == PNG
    req = urlscan["requests"][-1]
    assert str(req.url) == us.SCREENSHOT_URL.format(uuid=UUID) and req.headers["API-Key"] == "test-key"
    urlscan["answer"] = lambda r: httpx.Response(404)
    assert run(us.fetch_screenshot(UUID)) is None
    urlscan["answer"] = lambda r: httpx.Response(200, content=b"<html>not an image</html>")
    with pytest.raises(us.UrlscanError):
        run(us.fetch_screenshot(UUID))
    urlscan["answer"] = lambda r: httpx.Response(503)
    with caplog.at_level(logging.ERROR, logger="urlscan"), pytest.raises(us.UrlscanError):
        run(us.fetch_screenshot(UUID))
    assert any(rec.getMessage().startswith("fetching the screenshot failed: ") for rec in caplog.records)


def test_dom_is_text_and_failures_are_only_a_warning(urlscan, caplog):
    urlscan["answer"] = lambda r: httpx.Response(200, text="<html><form></form></html>")
    assert run(us.fetch_dom(UUID)) == "<html><form></form></html>"
    urlscan["answer"] = lambda r: httpx.Response(404)
    assert run(us.fetch_dom(UUID)) is None
    urlscan["answer"] = lambda r: httpx.Response(500)
    with caplog.at_level(logging.WARNING, logger="urlscan"):
        assert run(us.fetch_dom(UUID)) is None
    failures = [rec for rec in caplog.records if rec.getMessage().startswith("fetching the DOM failed: ")]
    assert failures and all(rec.levelno == logging.WARNING for rec in failures)


def test_search_returns_results_and_raises_on_error(urlscan, caplog):
    urlscan["answer"] = lambda r: httpx.Response(200, json={"results": [{"task": {"uuid": UUID}}]})
    assert run(us.search_scans("page.domain:example.org")) == [{"task": {"uuid": UUID}}]
    req = urlscan["requests"][-1]
    assert req.url.params["q"] == "page.domain:example.org" and req.url.params["size"] == str(us.SEARCH_SIZE)
    urlscan["answer"] = lambda r: httpx.Response(200, json={})
    assert run(us.search_scans("x")) == []
    urlscan["answer"] = lambda r: httpx.Response(401, json={"message": "bad key"})
    with caplog.at_level(logging.ERROR, logger="urlscan"), pytest.raises(us.UrlscanError):
        run(us.search_scans("x"))
    assert any(rec.getMessage().startswith("search failed: ") for rec in caplog.records)

"""OriginGuardMiddleware (backend/main.py): an /api/ request that carries an Origin header must come from the page Seisa
itself served, i.e. the same scheme, a loopback name and the same port as the request. Another port on this machine is
another application (RFC 6454: the port is part of the origin), even when the browser sends no Sec-Fetch-Site."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app, base_url="http://127.0.0.1:54321")
PATH = "/api/abuseipdb/categories"  # read-only, no network, no data files


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:54321",
        "http://localhost:54321",  # the page opened under the other loopback name
    ],
)
def test_the_page_of_this_server_passes(origin):
    assert client.get(PATH, headers={"Origin": origin}).status_code == 200


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:9999",  # another local application
        "http://127.0.0.1:8080",
        "http://127.0.0.1",  # no port = port 80
        "https://127.0.0.1:54321",  # another scheme is another origin
        "http://attacker.example:54321",
        "null",
    ],
)
def test_any_other_origin_is_refused_without_fetch_metadata(origin):
    assert client.get(PATH, headers={"Origin": origin}).status_code == 403


def test_default_port_on_both_sides_matches():
    plain = TestClient(app, base_url="http://127.0.0.1")
    assert plain.get(PATH, headers={"Origin": "http://127.0.0.1"}).status_code == 200
    assert plain.get(PATH, headers={"Origin": "http://127.0.0.1:54321"}).status_code == 403


def test_requests_without_origin_still_pass():
    assert client.get(PATH).status_code == 200

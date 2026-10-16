"""FastAPI's /docs and /redoc pages are switched off (audit A2-B3): they load their scripts from a CDN, which the
Content-Security-Policy blocks, so they could only ever show an empty page. The machine-readable /openapi.json stays."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app, base_url="http://127.0.0.1")


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/docs/oauth2-redirect"])
def test_the_interactive_docs_pages_are_gone(path):
    assert client.get(path).status_code == 404


def test_the_openapi_description_stays():
    res = client.get("/openapi.json")
    assert res.status_code == 200 and "/api/lookup" in res.json()["paths"]

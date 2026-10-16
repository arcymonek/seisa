"""IP tab: which services a lookup asks (audit A2-B1). No service field means all of them; a list means exactly those,
so a list with no known service (every chip switched off) is refused and nothing leaves the machine."""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend import aggregator
from backend.main import app
from backend.models import ServiceResult
from backend.routers import lookup as lookup_router

client = TestClient(app, base_url="http://127.0.0.1")
H = {"X-Seisa-Lang": "en"}


class FakeService:
    supports_ip = True
    supports_domain = True

    def __init__(self, name, asked):
        self.name = name
        self.asked = asked

    async def query_ip(self, indicator):
        self.asked.append(self.name)
        return ServiceResult(service=self.name, status="ok")

    query_domain = query_ip


@pytest.fixture
def asked(monkeypatch):
    calls: list[str] = []
    registry = {name: FakeService(name, calls) for name in aggregator.SERVICE_REGISTRY}
    monkeypatch.setattr(aggregator, "SERVICE_REGISTRY", registry)
    return calls


@pytest.mark.parametrize("services", [[], ["no_such_service"]])
def test_a_lookup_with_no_known_service_is_refused(asked, services):
    res = client.post("/api/lookup", json={"indicator": "185.220.101.1", "services": services}, headers=H)
    assert res.status_code == 400
    assert "service" in res.json()["detail"].lower()
    assert asked == []


def test_the_refusal_is_translated(asked):
    res = client.post("/api/lookup", json={"indicator": "185.220.101.1", "services": []}, headers={"X-Seisa-Lang": "pl"})
    assert res.status_code == 400 and "usług" in res.json()["detail"]


def test_run_lookup_with_an_empty_list_asks_nobody(asked):
    asyncio.run(aggregator.run_lookup("185.220.101.1", "ip", []))
    assert asked == []


def test_run_lookup_without_a_list_asks_every_service(asked):
    asyncio.run(aggregator.run_lookup("185.220.101.1", "ip", None))
    assert sorted(asked) == sorted(aggregator.SERVICE_REGISTRY)


def test_run_lookup_asks_only_the_chosen_services(asked):
    asyncio.run(aggregator.run_lookup("185.220.101.1", "ip", ["otx", "no_such_service"]))
    assert asked == ["otx"]


def test_the_router_passes_the_chosen_services_on(monkeypatch):
    seen = {}

    async def fake_run_lookup(indicator, indicator_type, services):
        seen["services"] = services
        raise RuntimeError("stop here")

    monkeypatch.setattr(lookup_router, "run_lookup", fake_run_lookup)
    with pytest.raises(RuntimeError):
        client.post("/api/lookup", json={"indicator": "185.220.101.1", "services": ["otx"]}, headers=H)
    assert seen["services"] == ["otx"]

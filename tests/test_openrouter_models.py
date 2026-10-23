"""backend/services/openrouter_models.py and POST /api/about/models: what is kept from the public OpenRouter model list,
that no key is sent with the request and how failures are reported. No network: requests go to an httpx.MockTransport.

The list shape follows https://openrouter.ai/docs/api-reference/list-available-models (checked against the real answer
on 2026-10-23): prices are USD per token as text, "-1" means a price that depends on the routing."""
from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app
from backend.services import openrouter_models as om


def model(model_id="vendor/model", **over):
    base = {
        "id": model_id,
        "name": "Vendor: Model",
        "pricing": {"prompt": "0.000003", "completion": "0.000015"},
        "context_length": 200000,
        "architecture": {"output_modalities": ["text"]},
        "top_provider": {"max_completion_tokens": 64000},
        "supported_parameters": ["max_tokens", "response_format"],
    }
    base.update(over)
    return base


def test_prices_are_converted_from_per_token_to_per_million():
    kept = om.compact([model()])[0]
    assert kept["prompt_per_million"] == 3.0
    assert kept["completion_per_million"] == 15.0
    assert om.compact([model(pricing={"prompt": "0", "completion": "0.0000004"})])[0]["completion_per_million"] == 0.4


@pytest.mark.parametrize("pricing", [{"prompt": "-1", "completion": "-1"}, {}, {"prompt": "abc", "completion": None}])
def test_a_price_that_is_negative_missing_or_unreadable_becomes_none(pricing):
    kept = om.compact([model(pricing=pricing)])[0]
    assert kept["prompt_per_million"] is None and kept["completion_per_million"] is None


@pytest.mark.parametrize("bad_id", ["a b/c", "vendor/$HOME", "x\ny", "", "a" * 513, 5, None])
def test_an_id_that_cannot_be_saved_in_the_env_file_is_dropped(bad_id):
    assert om.compact([model(bad_id)]) == []


def test_only_text_only_models_are_kept():
    items = [model("a/text"), model("a/image", architecture={"output_modalities": ["image", "text"]}),
             model("a/audio", architecture={"output_modalities": ["text", "audio"]}), model("a/none", architecture={})]
    assert [m["id"] for m in om.compact(items)] == ["a/text"]


def test_json_mode_and_the_output_limit_come_from_the_list():
    plain = om.compact([model(supported_parameters=["max_tokens"], top_provider={"max_completion_tokens": 8192})])[0]
    assert plain["json_mode"] is False and plain["max_completion_tokens"] == 8192
    unknown = om.compact([model(top_provider={}, supported_parameters=None)])[0]
    assert unknown["json_mode"] is False and unknown["max_completion_tokens"] is None


def test_a_long_name_is_cut_and_a_missing_name_falls_back_to_the_id():
    assert len(om.compact([model(name="x" * 500)])[0]["name"]) == om.NAME_LIMIT
    assert om.compact([model(name=None)])[0]["name"] == "vendor/model"


def test_items_of_the_wrong_shape_are_skipped_not_fatal():
    assert [m["id"] for m in om.compact(["x", 3, None, model("a/ok")])] == ["a/ok"]
    assert om.compact({"not": "a list"}) == []


@pytest.fixture
def served(monkeypatch):
    state = {"answer": lambda r: httpx.Response(200, json={"data": [model()]}), "requests": []}

    def handler(request):
        state["requests"].append(request)
        return state["answer"](request)

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: real(*a, **{**kw, "transport": httpx.MockTransport(handler)}))
    monkeypatch.setattr(settings, "openrouter_api_key", "SECRET-OR-KEY")
    return state


client = TestClient(app, base_url="http://127.0.0.1:54321")


def test_the_request_carries_no_key_and_goes_to_the_public_list(served):
    result = asyncio.run(om.fetch_models())
    request = served["requests"][0]
    assert str(request.url) == "https://openrouter.ai/api/v1/models" and request.method == "GET"
    assert "authorization" not in request.headers and "SECRET-OR-KEY" not in str(request.headers)
    assert [m["id"] for m in result["models"]] == ["vendor/model"]
    assert result["email_max_tokens"] == 64000 and result["fetched_at"]


def test_the_endpoint_answers_with_the_reduced_list(served):
    res = client.post("/api/about/models")
    assert res.status_code == 200 and res.json()["models"][0]["id"] == "vendor/model"


@pytest.mark.parametrize("answer", [
    lambda r: httpx.Response(500, text="boom SECRET-OR-KEY"),
    lambda r: httpx.Response(200, text="<html>not json</html>"),
    lambda r: httpx.Response(200, json={"nope": 1}),
    lambda r: httpx.Response(200, content=b"x" * (om.MAX_BYTES + 1)),
])
def test_a_failure_becomes_a_502_without_the_answer_body(served, answer):
    served["answer"] = answer
    res = client.post("/api/about/models")
    assert res.status_code == 502 and "SECRET-OR-KEY" not in res.text and "boom" not in res.text


def test_a_connection_error_becomes_a_502(served):
    def fail(request):
        raise httpx.ConnectError("no route")

    served["answer"] = fail
    res = client.post("/api/about/models")
    assert res.status_code == 502 and "ConnectError" in res.json()["detail"]

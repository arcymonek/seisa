"""backend/services/llm_analyzer.py: how the OpenRouter answers are read (fenced JSON, truncated JSON, refusals, an error
inside a 200 answer, one retry), what is shared by the two call paths (headers, time limit, language names, the plain
hyphen instead of the long dash) and what is not touched. No network: every request goes to an httpx.MockTransport.

The shapes follow the OpenRouter documentation (https://openrouter.ai/docs): `choices[0].message.content`,
`finish_reason` ("stop", "length", "content_filter"), an `error` object either as the body of an HTTP error or inside a
200 answer, and server-sent events (`data: {...}` lines, `: OPENROUTER PROCESSING` comments, `data: [DONE]`)."""
from __future__ import annotations

import asyncio
import json
import logging

import httpx
import pytest

from backend import i18n
from backend.config import settings
from backend.i18n import t
from backend.routers import email_analysis
from backend.services import llm_analyzer as llm

analyzer = llm.llm_analyzer


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def router(monkeypatch):
    """Requests go to `state["answers"]` (a list of functions, the last one repeats); AsyncClient kwargs are recorded."""
    state = {"answers": [lambda r: httpx.Response(200, json=reply("{}"))], "requests": [], "client_kwargs": []}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        index = min(len(state["requests"]) - 1, len(state["answers"]) - 1)
        return state["answers"][index](request)

    real = httpx.AsyncClient

    def make(*args, **kwargs):
        state["client_kwargs"].append(dict(kwargs))
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", make)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "openrouter_model", "test/model")
    return state


def reply(content, finish="stop", **extra):
    choice = {"message": {"content": content}, "finish_reason": finish, **extra}
    return {"choices": [choice], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001}}


def answering(*bodies, status=200):
    return [lambda r, b=b: httpx.Response(status, json=b) for b in bodies]


def chat():
    return run(analyzer._chat_json("system", "user"))


# ---- reading the answer ----

def test_plain_json_answer_with_usage(router):
    router["answers"] = answering(reply('{"qualifies": true, "reasoning": "ok"}'))
    result = chat()
    assert result["qualifies"] is True and result["_usage"]["cost"] == 0.001
    assert len(router["requests"]) == 1


def test_json_inside_a_markdown_fence(router):
    router["answers"] = answering(reply('```json\n{"qualifies": false}\n```'))
    assert chat()["qualifies"] is False


def test_json_with_text_before_and_after(router):
    router["answers"] = answering(reply('Here is the answer:\n{"qualifies": true}\nHope it helps.'))
    assert chat()["qualifies"] is True


def test_truncated_json_is_retried_once_and_the_second_answer_is_used(router, caplog):
    router["answers"] = answering(reply('{"qualifies": tru', finish="length"), reply('{"qualifies": true}'))
    with caplog.at_level(logging.WARNING, logger="open_router"):
        result = chat()
    assert result["qualifies"] is True and "_retryable" not in result and "error" not in result
    assert len(router["requests"]) == 2
    assert any("retrying" in r.getMessage() for r in caplog.records)


def test_two_broken_answers_end_in_an_error_and_never_a_third_request(router):
    router["answers"] = answering(reply("not json at all"), reply("{broken"))
    result = chat()
    assert result["error"].startswith(t("or.invalid_response", detail="").split("(")[0])
    assert "_retryable" not in result
    assert len(router["requests"]) == 2


def test_model_refusal_is_reported_and_not_retried(router):
    router["answers"] = answering(reply("", finish="content_filter"))
    result = chat()
    assert result == {"error": t("or.refusal", reason="content_filter")}
    assert len(router["requests"]) == 1


def test_native_refusal_is_reported_with_its_reason(router):
    router["answers"] = answering(reply("I cannot help with that.", finish="stop", native_finish_reason="refusal"))
    assert chat() == {"error": t("or.refusal", reason="refusal")}


def test_error_inside_a_200_answer(router):
    router["answers"] = answering({"error": {"code": 502, "message": "Provider disconnected"}})
    result = chat()
    assert "Provider disconnected" in result["error"] and "HTTP 502" in result["error"]
    assert len(router["requests"]) == 1


def test_error_inside_the_choice(router):
    router["answers"] = answering({"choices": [{"error": {"code": 500, "message": "upstream died"}}]})
    assert "upstream died" in chat()["error"]


def test_http_error_gets_the_hint_of_its_status(router):
    router["answers"] = answering({"error": {"message": "Insufficient credits"}}, status=402)
    result = chat()
    assert t("or.hint.402") in result["error"] and "Insufficient credits" in result["error"] and "HTTP 402" in result["error"]
    assert len(router["requests"]) == 1


def test_answer_without_choices_is_an_invalid_response(router):
    router["answers"] = answering({"id": "x"})
    assert "error" in chat()


def test_connection_error_is_returned_as_an_error(router):
    def refuse(request):
        raise httpx.ConnectError("no route")

    router["answers"] = [refuse]
    assert "no route" in chat()["error"]


# ---- what both call paths share ----

def test_one_set_of_headers_for_json_and_stream(router):
    router["answers"] = answering(reply("{}"))
    chat()
    router["answers"] = [lambda r: httpx.Response(200, content=b"data: [DONE]\n\n")]
    run(_collect(analyzer.stream_chat("system", "user")))
    first, second = router["requests"][0].headers, router["requests"][1].headers
    for headers in (first, second):
        assert headers["authorization"] == "Bearer test-key"
        assert headers["x-title"] == "Seisa" and headers["http-referer"] == "https://seisa.local"
        assert headers["content-type"] == "application/json"
    assert llm.openrouter_headers()["X-Title"] == "Seisa"


def test_json_and_stream_use_the_same_time_limit(router):
    router["answers"] = answering(reply("{}"))
    chat()
    router["answers"] = [lambda r: httpx.Response(200, content=b"data: [DONE]\n\n")]
    run(_collect(analyzer.stream_chat("system", "user")))
    timeouts = [kw["timeout"] for kw in router["client_kwargs"]]
    assert timeouts[0] is timeouts[1] is llm.OPENROUTER_TIMEOUT
    assert timeouts[0].connect == 30.0 and timeouts[0].read == 120.0


def test_language_names_live_in_one_place():
    assert llm.LANGUAGE_NAMES is i18n.LANGUAGE_NAMES is email_analysis.LANGUAGE_NAMES
    assert i18n.LANGUAGE_NAMES == {"pl": "Polish", "en": "English"}
    assert "in Polish." in llm._system_prompt("pl") and "in English." in llm._system_prompt("en")
    assert "in English." in llm._system_prompt("de")  # an unknown language falls back to English


# ---- the long dash ----

async def _collect(stream):
    return [event async for event in stream]


def _sse_body(*deltas, finish="stop"):
    lines = [": OPENROUTER PROCESSING", ""]
    for d in deltas:
        lines += ["data: " + json.dumps({"choices": [{"delta": {"content": d}}]}), ""]
    lines += ["data: " + json.dumps({"choices": [{"delta": {}, "finish_reason": finish}], "usage": {"cost": 0.5}}), "", "data: [DONE]", ""]
    return "\n".join(lines).encode()


def test_stream_deltas_get_a_hyphen_for_the_long_dash(router):
    router["answers"] = [lambda r: httpx.Response(200, content=_sse_body("Part 1 \u2014 intro", " and \u2014 more"))]
    events = run(_collect(analyzer.stream_chat("system", "user")))
    assert [p for k, p in events if k == "delta"] == ["Part 1 - intro", " and - more"]
    assert ("usage", {"cost": 0.5}) in events and ("finish", "stop") in events


def test_json_descriptive_fields_get_a_hyphen_but_the_report_comment_is_left_as_it_is(router):
    body = {
        "qualifies": True,
        "reasoning": "fake bank \u2014 login page",
        "alternatives": "",
        "report_comment": "Phishing from 8.8.8.8 \u2014 test",
        "source_ip_check": {"agrees": True, "suggested_ip": None, "reasoning": "one hop \u2014 clear"},
        "received_verified": {"status": "pass", "note": "written by the trusted server \u2014 yes"},
        "suggested_categories": [7, 10],
    }
    router["answers"] = answering(reply(json.dumps(body, ensure_ascii=False)))
    result = chat()
    assert result["reasoning"] == "fake bank - login page"
    assert result["source_ip_check"]["reasoning"] == "one hop - clear"
    assert result["received_verified"]["note"] == "written by the trusted server - yes"
    assert result["suggested_categories"] == [7, 10] and result["qualifies"] is True
    # sanitize_comment() decides what happens to non-ASCII characters of the comment, so it must see them
    assert result["report_comment"] == "Phishing from 8.8.8.8 \u2014 test"


def test_no_em_dash_helper():
    assert llm.no_em_dash("a \u2014 b \u2014 c") == "a - b - c"
    assert llm.no_em_dash("plain - text") == "plain - text"

"""frontend/js/api.js through Node: the message of a failed request is the backend's `detail` for plain requests AND for
the streamed ones (audit 2026-10-15, B20: a refused stream used to show only "HTTP 422"), and history ids are encoded in
every URL. Skipped when Node is missing."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is not installed")
RUNNER = Path(__file__).resolve().parent / "js" / "api_errors_run.mjs"


def run(*cases):
    done = subprocess.run([NODE, str(RUNNER)], input=json.dumps(list(cases)), capture_output=True, text=True, check=True, timeout=60)
    return json.loads(done.stdout)


def failing(call, status, body=None, status_text="", args=None):
    case = {"call": call, "args": args or [{}], "status": status, "statusText": status_text}
    if body is not None:
        case["body"] = body
    return case


@pytest.mark.parametrize("call", ["emailFind", "emailAnalyzeStream"])
def test_a_text_detail_is_shown_for_plain_and_streamed_requests(call):
    assert run(failing(call, 400, {"detail": "Source too large"}))[0]["error"] == "Source too large"


def test_a_validation_error_shows_the_field_and_the_message_but_not_the_echoed_input():
    detail = [{"type": "string_too_long", "loc": ["body", "raw_email"], "msg": "String should have at most 6000000 characters", "input": "a" * 100000}]
    error = run(failing("emailAnalyzeStream", 422, {"detail": detail}))[0]["error"]
    assert error == "raw_email: String should have at most 6000000 characters"
    assert run(failing("emailFind", 422, {"detail": [{"foo": 1}]}))[0]["error"] == '{"foo":1}'


@pytest.mark.parametrize("call", ["emailFind", "emailAnalyzeStream"])
def test_without_a_json_body_the_status_text_or_code_is_shown(call):
    assert run(failing(call, 502, status_text="Bad Gateway"))[0]["error"] == "Bad Gateway"
    assert run(failing(call, 500))[0]["error"] == "HTTP 500"
    assert run(failing(call, 400, {}))[0]["error"] == "HTTP 400"


def test_history_ids_are_encoded_in_every_url():
    results = run(
        {"call": "historyEntry", "args": ["a/b c?"], "status": 200, "body": {}},
        {"call": "historyPin", "args": ["a/b c?", True], "status": 200, "body": {}},
        {"call": "historyDelete", "args": ["a/b c?"], "status": 200, "body": {}},
    )
    assert [r["url"] for r in results] == ["/api/history/a%2Fb%20c%3F"] * 3

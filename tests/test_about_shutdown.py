"""The shutdown endpoint ends the process only after answering, with SIGTERM first (a graceful uvicorn stop) and a hard
exit as the fallback for a stream that would keep the server waiting. os.kill/os._exit/sleep are replaced here: the
real ones would end the test run."""
from __future__ import annotations

import os
import signal

from backend.routers import about


def test_stop_server_sends_sigterm_to_itself_then_exits_hard(monkeypatch):
    calls = []
    monkeypatch.setattr(about.time, "sleep", lambda s: calls.append(("sleep", s)))
    monkeypatch.setattr(about.os, "kill", lambda pid, sig: calls.append(("kill", pid, sig)))
    monkeypatch.setattr(about.os, "_exit", lambda code: calls.append(("exit", code)))
    about._stop_server()
    kinds = [c[0] for c in calls]
    assert ("kill", os.getpid(), signal.SIGTERM) in calls
    assert kinds.index("kill") < kinds.index("exit")  # graceful first
    assert calls[-1] == ("exit", 0)
    assert kinds.index("sleep") < kinds.index("kill")  # the answer is sent before the signal


def test_schedule_stop_starts_a_daemon_thread_running_stop_server(monkeypatch):
    started = []

    class FakeThread:
        def __init__(self, target, daemon):
            started.append((target, daemon))

        def start(self):
            started.append("start")

    monkeypatch.setattr(about.threading, "Thread", FakeThread)
    about._schedule_stop()
    assert started == [(about._stop_server, True), "start"]  # daemon: uvicorn must not wait for it


def test_endpoint_answers_and_schedules_the_stop(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.main import app

    stops = []
    monkeypatch.setattr(about, "_schedule_stop", lambda: stops.append(1))
    res = TestClient(app, base_url="http://127.0.0.1").post("/api/about/shutdown")
    assert res.status_code == 200 and res.json() == {"ok": True}
    assert stops == [1]

"""Info tab: which integrations have an API key (never the keys themselves), the environment Seisa runs in, the usage of
their API limits and the
recent releases from the git log (empty when Seisa does not run from a git checkout)."""
from __future__ import annotations

import os
import platform
import re
import signal
import subprocess
import threading
import time

import fastapi
from fastapi import APIRouter, HTTPException, Request

from backend import desktop_icon
from backend.api_limits import limits_snapshot, refresh_live
from backend.config import BASE_DIR, settings

router = APIRouter()

CHANGES_LIMIT = 10
SCAN_LIMIT = 100  # commits looked through to find CHANGES_LIMIT release commits
_RELEASE = re.compile(r"^Seisa (\d+\.\d+\.\d+): (.+)$")


def _recent_changes() -> list[dict]:
    try:
        out = subprocess.run(
            ["git", "log", "-n", str(SCAN_LIMIT), "--format=%s"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=3, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = (_RELEASE.match(line) for line in out.splitlines())
    return [{"version": m.group(1), "summary": m.group(2)} for m in found if m][:CHANGES_LIMIT]


def _environment(request: Request) -> dict:
    """Where and on what Seisa runs (no secrets: the .env is only checked for existence, never read)."""
    host, port = request.scope.get("server") or (None, None)
    return {
        "host": host,
        "port": port,
        "dotenv": (BASE_DIR / ".env").is_file(),
        "os": platform.platform(),
        "python": platform.python_version(),
        "fastapi": fastapi.__version__,
    }


@router.get("/about")
def about(request: Request):
    keyed = {
        "virustotal": settings.virustotal_api_key,
        "otx": settings.otx_api_key,
        "cloudflare_radar": settings.cloudflare_radar_api_key,
        "abuseipdb": settings.abuseipdb_api_key,
        "greynoise": settings.greynoise_api_key,
        "urlscan": settings.urlscan_api_key,
    }
    llm_on = bool(settings.openrouter_api_key)
    return {
        "services": [{"id": name, "configured": bool(key)} for name, key in keyed.items()]
        + [{"id": "whois_rdns", "configured": None}],
        "llm": {"configured": llm_on, "model": settings.openrouter_model if llm_on else None},
        "limits": limits_snapshot(),
        "changes": _recent_changes(),
        "environment": _environment(request),
    }


@router.get("/about/icon")
def icon_status():
    return desktop_icon.status()


@router.post("/about/icon")
def icon_install():
    """Makes the desktop icon (macOS app / Linux menu entry); fixed targets in the home directory, no client input."""
    return _icon_call(desktop_icon.install)


@router.delete("/about/icon")
def icon_remove():
    return _icon_call(desktop_icon.remove)


def _icon_call(action):
    try:
        return action()
    except desktop_icon.IconError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _stop_server() -> None:
    """Ends this process. The short wait lets the answer reach the browser first. SIGTERM lets uvicorn finish
    gracefully; an analysis stream that is still open would keep it waiting, so after a few seconds the process ends
    regardless (all data files are written atomically)."""
    time.sleep(0.3)
    os.kill(os.getpid(), signal.SIGTERM)
    time.sleep(3)
    os._exit(0)


def _schedule_stop() -> None:
    # A daemon thread, not a Starlette background task: uvicorn waits for background tasks when it shuts down.
    threading.Thread(target=_stop_server, daemon=True).start()


@router.post("/about/shutdown")
def shutdown():
    """Stops the Seisa server on an explicit click ("Shut down Seisa"); no input from the client."""
    _schedule_stop()
    return {"ok": True}


@router.post("/about/limits/refresh")
async def refresh_limits():
    """Asks the services that report their quota (VirusTotal, urlscan, OpenRouter) - only on an explicit click."""
    errors = await refresh_live()
    return {"limits": limits_snapshot(), "errors": errors}

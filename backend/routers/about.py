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

from backend import desktop_icon, env_file
from backend.api_limits import limits_snapshot, refresh_live
from backend.config import BASE_DIR, settings
from backend.i18n import t

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
        "keys": env_file.keys_status(),
        "limits": limits_snapshot(),
        "changes": _recent_changes(),
        "environment": _environment(request),
    }


def _require_json(request: Request) -> None:
    """415 unless the body type is JSON. A page on another site cannot send that type without a CORS preflight, which
    Seisa never approves - together with the Origin guard this keeps other pages from touching the keys."""
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise HTTPException(status_code=415, detail=t("settings.json_required"))


def _change_keys(updates: dict[str, str | None]) -> dict:
    try:
        env_file.write(updates)
    except env_file.EnvFileError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return {"keys": env_file.keys_status()}


@router.put("/about/keys")
async def keys_save(request: Request):
    """Sets API keys (and the model name) in the .env file. The body is checked by hand, not by a Pydantic model:
    FastAPI's default validation error would send the refused value back. An empty value means "no change"."""
    _require_json(request)
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict) or not all(isinstance(v, str) for v in body.values()):
        raise HTTPException(status_code=400, detail=t("settings.bad_body"))
    return _change_keys({field: value for field, value in body.items() if value})


@router.delete("/about/keys")
def keys_remove_all(request: Request):
    """Removes every API key that is set in the .env file. Keys that an environment variable provides cannot be
    changed here and are left alone, and so is the model name (it is not a key)."""
    _require_json(request)
    rows = env_file.keys_status()
    return _change_keys({r["field"]: None for r in rows if r["secret"] and r["set"] and not r["from_env"]})


@router.delete("/about/keys/{field}")
def key_remove(field: str, request: Request):
    """Removes one key from the .env file (the model name goes back to its default)."""
    _require_json(request)
    return _change_keys({field: None})


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

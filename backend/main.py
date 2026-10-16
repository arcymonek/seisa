"""FastAPI application entry point: builds the app, installs the security middleware (Host check against DNS
rebinding, Origin/Sec-Fetch-Site guard, Content-Security-Policy, no-cache for static files, language header),
mounts the routers under /api and serves the static frontend. Seisa listens on 127.0.0.1 only and has no login.
"""
from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.config import FRONTEND_DIR
from backend.i18n import reset_lang, set_lang, t
from backend.logging_config import setup_logging
from backend.routers import about, abuseipdb_report, dmarc, email_analysis, history, logs, lookup, themes, urlscan

setup_logging()
app_logger = logging.getLogger("app")

app = FastAPI(title="Seisa")


# Second line of defence next to the HTML sanitising in the frontend: scripts only from our own origin, no plugins,
# no framing. style-src needs 'unsafe-inline' because the UI uses style= attributes; the frontend talks only to
# its own backend (connect-src 'self').
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
)


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    """Single-user local tool: the browser should not keep old HTML/JS/CSS between our changes.

    Also sets the Content-Security-Policy on every response.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        return response


class LanguageMiddleware(BaseHTTPMiddleware):
    """Stores the UI language sent by the frontend (X-Seisa-Lang) for the duration of the request."""

    async def dispatch(self, request: Request, call_next):
        token = set_lang(request.headers.get("x-seisa-lang"))
        try:
            return await call_next(request)
        finally:
            reset_lang(token)


LOOPBACK_HOSTS = {"127.0.0.1", "localhost"}
SAME_ORIGIN_FETCH_SITES = {"same-origin", "none"}
_last_block_log = 0.0


class OriginGuardMiddleware(BaseHTTPMiddleware):
    """Refuses /api/ requests that another web page makes through the user's browser.

    The Host check stops DNS rebinding, but a page in another tab can still fire a plain GET (an <img> tag) or a
    body-less POST at 127.0.0.1 without a preflight and burn the API quotas. Browsers label such requests with
    Sec-Fetch-Site (anything but same-origin/none, so same-site too: another port on this host is another application)
    and Origin. Requests without either header (curl, scripts, older browsers) pass: this is not authentication, a
    local process can send any header. Static files stay open so that a link to the tool does not give a 403.
    """

    async def dispatch(self, request: Request, call_next):
        global _last_block_log
        if request.url.path.startswith("/api/"):
            site = request.headers.get("sec-fetch-site")
            origin = request.headers.get("origin")
            foreign = (site is not None and site not in SAME_ORIGIN_FETCH_SITES) or (
                origin is not None and urlsplit(origin).hostname not in LOOPBACK_HOSTS
            )
            if foreign:
                now = time.monotonic()
                if now - _last_block_log > 60:  # a hostile page could otherwise flood the log
                    _last_block_log = now
                    app_logger.warning(f"blocked a cross-site request to {request.url.path}")
                return JSONResponse(status_code=403, content={"detail": t("error.cross_site_blocked")})
        return await call_next(request)


app.add_middleware(NoCacheStaticMiddleware)
app.add_middleware(OriginGuardMiddleware)
app.add_middleware(LanguageMiddleware)
# Only loopback names are accepted in the Host header: a page on another domain that was re-pointed (DNS rebinding)
# to 127.0.0.1 would otherwise be treated as the same origin and could read the whole API.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    app_logger.error(f"{request.method} {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": t("error.internal")})


app.include_router(lookup.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(about.router, prefix="/api")
app.include_router(themes.router, prefix="/api")
app.include_router(abuseipdb_report.router, prefix="/api/abuseipdb")
app.include_router(dmarc.router, prefix="/api/dmarc")
app.include_router(urlscan.router, prefix="/api/urlscan")
app.include_router(email_analysis.router, prefix="/api/email")

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

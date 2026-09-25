from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.config import FRONTEND_DIR
from backend.i18n import reset_lang, set_lang, t
from backend.logging_config import setup_logging
from backend.routers import abuseipdb_report, email_analysis, history, logs, lookup, urlscan

setup_logging()
app_logger = logging.getLogger("app")

app = FastAPI(title="Seisa")


# Second line of defence next to the HTML sanitising in the frontend: scripts only from our own origin, no plugins,
# no framing. style-src needs 'unsafe-inline' because the UI uses style= attributes; connect-src lists the one
# external host the frontend calls itself (geo/ASN lookup in the DMARC tab).
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self' https://ipwho.is; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
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


app.add_middleware(NoCacheStaticMiddleware)
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
app.include_router(abuseipdb_report.router, prefix="/api/abuseipdb")
app.include_router(urlscan.router, prefix="/api/urlscan")
app.include_router(email_analysis.router, prefix="/api/email")

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

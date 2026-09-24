from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import FRONTEND_DIR
from backend.i18n import reset_lang, set_lang, t
from backend.logging_config import setup_logging
from backend.routers import abuseipdb_report, email_analysis, history, logs, lookup, urlscan

setup_logging()
app_logger = logging.getLogger("app")

app = FastAPI(title="Seisa")


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    """Single-user local tool: the browser should not keep old HTML/JS/CSS between our changes."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
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

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import FRONTEND_DIR
from backend.logging_config import setup_logging
from backend.routers import abuseipdb_report, email_analysis, history, logs, lookup, urlscan

setup_logging()
app_logger = logging.getLogger("app")

app = FastAPI(title="Seisa")


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    """Narzędzie deweloperskie na jednego użytkownika - przeglądarka nie
    powinna sama trzymać starych wersji HTML/JS/CSS między naszymi zmianami."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response


app.add_middleware(NoCacheStaticMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    app_logger.error(f"{request.method} {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "wewnętrzny błąd Seisy"})


app.include_router(lookup.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(abuseipdb_report.router, prefix="/api/abuseipdb")
app.include_router(urlscan.router, prefix="/api/urlscan")
app.include_router(email_analysis.router, prefix="/api/email")

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

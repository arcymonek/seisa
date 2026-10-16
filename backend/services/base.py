"""Common base for the IP/domain intelligence services: IntelService with the standard not-configured,
not-applicable and error results and a shared JSON fetch with uniform error handling, plus helpers that turn
exceptions into short readable messages. Concrete clients in this package subclass it.
"""
from __future__ import annotations

import inspect
import logging
from abc import ABC, abstractmethod

import httpx

from backend.api_limits import observe
from backend.i18n import t
from backend.models import ServiceResult


def describe_exception(exc: BaseException) -> str:
    """str(exc) is sometimes empty (e.g. httpx.ReadTimeout() without arguments) - then we show at least the
    exception type, so that the log line is not empty."""
    text = str(exc)
    if text:
        return f"{type(exc).__name__}: {text}"
    return f"{type(exc).__name__} (no error text - probably a connection timeout)"


def http_error_text(exc: httpx.HTTPError) -> str:
    """One-line description of an httpx failure: an error status with the start of the response body (so that e.g. a
    401 can be diagnosed without guessing), anything else through describe_exception."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
    return describe_exception(exc)


class IntelService(ABC):
    name: str
    supports_ip: bool = True
    supports_domain: bool = True

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(self.name)

    def is_configured(self) -> bool:
        return True

    def not_configured_result(self) -> ServiceResult:
        return ServiceResult(
            service=self.name,
            status="no_key",
            summary={"message": t("svc.no_key")},
        )

    def not_applicable_result(self) -> ServiceResult:
        return ServiceResult(
            service=self.name,
            status="not_applicable",
            summary={"message": t("svc.not_applicable")},
        )

    def error_result(self, message: str) -> ServiceResult:
        message = message or "unknown error (exception without a message)"
        self.logger.error(message)
        return ServiceResult(service=self.name, status="error", error_message=message)

    async def fetch_json(self, method: str, url: str, *, special: dict | None = None, **kwargs) -> tuple[dict | None, ServiceResult | None]:
        """Common fetch+parse with a rich error message (HTTP code + the server response body, not only a generic
        exception) - so that e.g. a 401 can be diagnosed without guessing.

        `special` maps an HTTP status to a handler `handler(response) -> ServiceResult` (plain or async function) for
        the statuses a service treats as a normal answer (GreyNoise: 404 = no data, 429 = quota). When the status is
        in the map the handler decides and the usual error handling is skipped."""
        handler = None
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.request(method, url, **kwargs)
            observe(self.name, resp)
            handler = (special or {}).get(resp.status_code)
            if handler is None:
                resp.raise_for_status()
                return resp.json(), None
        except httpx.HTTPError as exc:
            return None, self.error_result(http_error_text(exc))
        except ValueError as exc:
            return None, self.error_result(f"invalid response (not JSON): {describe_exception(exc)}")
        result = handler(resp)
        if inspect.isawaitable(result):
            result = await result
        return None, result

    @abstractmethod
    async def query_ip(self, ip: str) -> ServiceResult: ...

    @abstractmethod
    async def query_domain(self, domain: str) -> ServiceResult: ...

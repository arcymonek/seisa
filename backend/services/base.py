from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from backend.models import ServiceResult


def describe_exception(exc: BaseException) -> str:
    """str(exc) bywa puste (np. httpx.ReadTimeout() bez argumentów) - wtedy
    pokazujemy przynajmniej typ wyjątku, żeby log nie był pustą linią."""
    text = str(exc)
    if text:
        return f"{type(exc).__name__}: {text}"
    return f"{type(exc).__name__} (brak treści błędu - prawdopodobnie timeout połączenia)"


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
            summary={"message": "brak klucza API"},
        )

    def not_applicable_result(self) -> ServiceResult:
        return ServiceResult(
            service=self.name,
            status="not_applicable",
            summary={"message": "usługa nie obsługuje tego typu wskaźnika"},
        )

    def error_result(self, message: str) -> ServiceResult:
        message = message or "nieznany błąd (wyjątek bez treści)"
        self.logger.error(message)
        return ServiceResult(service=self.name, status="error", error_message=message)

    async def fetch_json(self, method: str, url: str, **kwargs) -> tuple[dict | None, ServiceResult | None]:
        """Wspólny fetch+parse z bogatym komunikatem błędu (kod HTTP + treść
        odpowiedzi serwera, nie tylko generyczny wyjątek) - żeby dało się
        zdiagnozować np. 401 bez zgadywania."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp.json(), None
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            return None, self.error_result(f"HTTP {exc.response.status_code}: {body}")
        except httpx.HTTPError as exc:
            # httpx potrafi rzucić np. ReadTimeout() bez żadnej treści -
            # str(exc) bywa wtedy pustym stringiem, więc dokładamy typ wyjątku.
            return None, self.error_result(describe_exception(exc))
        except ValueError as exc:
            return None, self.error_result(f"nieprawidłowa odpowiedź (nie JSON): {describe_exception(exc)}")

    @abstractmethod
    async def query_ip(self, ip: str) -> ServiceResult: ...

    @abstractmethod
    async def query_domain(self, domain: str) -> ServiceResult: ...

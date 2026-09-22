from __future__ import annotations

import asyncio
import socket

import whois

from backend.models import ServiceResult
from backend.services.base import IntelService


class WhoisDnsService(IntelService):
    name = "whois_rdns"

    def is_configured(self) -> bool:
        return True

    async def query_ip(self, ip: str) -> ServiceResult:
        try:
            rdns = await asyncio.to_thread(self._reverse_dns, ip)
        except Exception as exc:
            return self.error_result(str(exc))
        return ServiceResult(
            service=self.name,
            status="ok",
            summary={"reverse_dns": rdns or "brak rekordu PTR"},
        )

    async def query_domain(self, domain: str) -> ServiceResult:
        try:
            data = await asyncio.to_thread(whois.whois, domain)
        except Exception as exc:
            return self.error_result(str(exc))
        summary = {
            "registrar": _first(data.get("registrar")),
            "creation_date": _stringify(_first(data.get("creation_date"))),
            "expiration_date": _stringify(_first(data.get("expiration_date"))),
            "name_servers": data.get("name_servers"),
            "status": data.get("status"),
            "emails": data.get("emails"),
        }
        return ServiceResult(service=self.name, status="ok", summary=summary, raw=dict(data))

    @staticmethod
    def _reverse_dns(ip: str) -> str | None:
        try:
            return socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror):
            return None


def _first(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _stringify(value):
    return str(value) if value is not None else None

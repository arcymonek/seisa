from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

ServiceStatus = Literal["ok", "error", "no_key", "not_applicable", "rate_limited_daily"]
IndicatorType = Literal["ip", "domain"]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ServiceResult(BaseModel):
    service: str
    status: ServiceStatus
    summary: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] | None = None
    error_message: str | None = None
    queried_at: str = Field(default_factory=utcnow_iso)

    def without_raw(self) -> "ServiceResult":
        return self.model_copy(update={"raw": None})


class RiskComponent(BaseModel):
    source: str
    signal: str
    value: str
    weight: float
    contribution: float


class RiskScore(BaseModel):
    level: Literal["low", "medium", "high"]
    score: float
    components: list[RiskComponent] = Field(default_factory=list)
    excluded_sources: list[str] = Field(default_factory=list)


class LookupResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    indicator: str
    indicator_type: IndicatorType
    queried_at: str = Field(default_factory=utcnow_iso)
    risk_score: RiskScore
    services: dict[str, ServiceResult] = Field(default_factory=dict)
    talos_url: str
    markdown: str

    def stripped_for_history(self) -> "LookupResult":
        return self.model_copy(
            update={"services": {k: v.without_raw() for k, v in self.services.items()}}
        )


class HistoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: Literal["lookup", "dmarc"]
    created_at: str = Field(default_factory=utcnow_iso)
    label: str
    risk_summary: str | None = None
    data: dict[str, Any]

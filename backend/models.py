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

    def without_raw(self) -> ServiceResult:
        return self.model_copy(update={"raw": None})


class RiskComponent(BaseModel):
    source: str
    signal: str
    value: str
    weight: float  # credibility of the source (cap of its vote)
    contribution: float  # c * r - the maximum "vote" of the source in the noisy-OR model
    risk: float = 0.0  # source risk 0-100


class RiskScore(BaseModel):
    level: Literal["low", "medium", "high"]
    score: float
    components: list[RiskComponent] = Field(default_factory=list)
    excluded_sources: list[str] = Field(default_factory=list)
    sources_used: int = 0
    sources_possible: int = 0
    notes: list[str] = Field(default_factory=list)


class IdentityVariant(BaseModel):
    value: str
    sources: list[str]  # service ids that reported this value, best-priority source first


class IdentityField(BaseModel):
    key: str
    value: str  # the value shown: the majority value, or (on a tie) the one from the highest-priority source
    status: Literal["agree", "majority", "conflict", "single"]
    agree: int  # number of sources behind the shown value
    total: int  # number of sources that reported this field at all
    variants: list[IdentityVariant] = Field(default_factory=list)  # every distinct value, the shown one first


class Identity(BaseModel):
    """Who the address belongs to (ASN, owner, country, network), merged from every source that reports it."""

    fields: list[IdentityField] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class LookupResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    indicator: str
    indicator_type: IndicatorType
    queried_at: str = Field(default_factory=utcnow_iso)
    risk_score: RiskScore
    services: dict[str, ServiceResult] = Field(default_factory=dict)
    talos_url: str
    markdown: str
    identity: Identity | None = None  # IP lookups only

    def stripped_for_history(self) -> LookupResult:
        return self.model_copy(
            update={"services": {k: v.without_raw() for k, v in self.services.items()}}
        )


class HistoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: Literal["lookup", "dmarc", "urlscan"]
    created_at: str = Field(default_factory=utcnow_iso)
    label: str
    risk_summary: str | None = None
    lang: str = "pl"  # UI language the entry was created in (entries saved before this field are Polish)
    data: dict[str, Any]

"""IP tab: reputation lookup of one indicator (/lookup)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.aggregator import detect_indicator_type, is_public_ip, is_valid_indicator, normalize_indicator, run_lookup
from backend.history_store import append_history, list_history_rows
from backend.i18n import current_lang, t
from backend.models import Comparison, HistoryEntry, IndicatorType, ScorePoint, SourceChange

router = APIRouter()


class LookupRequest(BaseModel):
    indicator: str = Field(max_length=253)
    type: str = "auto"
    services: list[str] | None = None


def _rejection(indicator: str, indicator_type: IndicatorType) -> str | None:
    """Why the indicator cannot be checked (message for the user), or None when it can."""
    if not is_valid_indicator(indicator, indicator_type):
        return t("lookup.invalid_indicator", indicator=indicator[:80])
    if indicator_type == "ip" and not is_public_ip(indicator):
        return t("lookup.non_public_ip", indicator=indicator)
    return None


def _resolve_type(indicator: str, requested: str) -> IndicatorType:
    if requested in ("ip", "domain"):
        return requested  # type: ignore[return-value]
    return detect_indicator_type(indicator)


TREND_POINTS = 10
CHANGE_MIN = 10.0  # a source risk that moved by less is noise, not a change


def _compare_with_history(result) -> Comparison | None:
    """Earlier scans of the same indicator (newest first in the History): the score difference, the sources whose risk
    moved and the trend. Called before the current scan is saved."""
    earlier = [r["trend"] for r in list_history_rows() if r["type"] == "lookup" and r["label"] == result.indicator and "trend" in r]
    if not earlier:
        return None
    points = [
        ScorePoint(queried_at=tr["queried_at"], score=tr["score"], level=tr["level"])
        for tr in earlier[:TREND_POINTS]
        if "score" in tr and "level" in tr
    ]
    if not points:
        return None
    before = earlier[0]["risks"]
    after = {c.source: c.risk for c in result.risk_score.components}
    changes = [
        SourceChange(source=src, before=before.get(src), after=after.get(src))
        for src in list(after) + [s for s in before if s not in after]
        if abs((after.get(src) or 0.0) - (before.get(src) or 0.0)) >= CHANGE_MIN
    ]
    return Comparison(
        previous=points[0], delta=round(result.risk_score.score - points[0].score, 1), changes=changes, trend=list(reversed(points))
    )


def _save_to_history(result) -> None:
    entry = HistoryEntry(
        type="lookup",
        label=result.indicator,
        risk_summary=result.risk_score.level,
        lang=current_lang(),
        data=result.stripped_for_history().model_dump(),
    )
    append_history(entry)


@router.post("/lookup")
async def lookup(req: LookupRequest):
    indicator = normalize_indicator(req.indicator)
    indicator_type = _resolve_type(indicator, req.type)
    reason = _rejection(indicator, indicator_type)
    if reason:
        raise HTTPException(status_code=400, detail=reason)
    result = await run_lookup(indicator, indicator_type, req.services)
    result.comparison = _compare_with_history(result)
    _save_to_history(result)
    return result


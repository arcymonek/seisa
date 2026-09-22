from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.aggregator import detect_indicator_type, run_lookup
from backend.models import HistoryEntry, IndicatorType
from backend.storage import append_history

router = APIRouter()


class LookupRequest(BaseModel):
    indicator: str
    type: str = "auto"
    services: list[str] | None = None
    force_refresh: bool = False


class BatchLookupRequest(BaseModel):
    indicators: list[str]
    services: list[str] | None = None
    force_refresh: bool = False


def _resolve_type(indicator: str, requested: str) -> IndicatorType:
    if requested in ("ip", "domain"):
        return requested  # type: ignore[return-value]
    return detect_indicator_type(indicator)


def _save_to_history(result) -> None:
    entry = HistoryEntry(
        type="lookup",
        label=result.indicator,
        risk_summary=result.risk_score.level,
        data=result.stripped_for_history().model_dump(),
    )
    append_history(entry)


@router.post("/lookup")
async def lookup(req: LookupRequest):
    indicator_type = _resolve_type(req.indicator, req.type)
    result = await run_lookup(req.indicator, indicator_type, req.services, req.force_refresh)
    _save_to_history(result)
    return result


@router.post("/lookup/batch")
async def lookup_batch(req: BatchLookupRequest):
    async def event_stream():
        total = len(req.indicators)
        for i, indicator in enumerate(req.indicators, start=1):
            indicator = indicator.strip()
            if not indicator:
                continue
            yield _sse({"type": "progress", "completed": i - 1, "total": total, "current": indicator})
            indicator_type = detect_indicator_type(indicator)

            wait_queue: asyncio.Queue[str] = asyncio.Queue()

            def progress_cb(message: str, q=wait_queue) -> None:
                q.put_nowait(message)

            task = asyncio.create_task(
                run_lookup(indicator, indicator_type, req.services, req.force_refresh, progress_cb)
            )
            while not task.done():
                try:
                    message = await asyncio.wait_for(wait_queue.get(), timeout=0.5)
                    yield _sse({"type": "wait", "current": indicator, "message": message})
                except asyncio.TimeoutError:
                    continue
            result = await task
            _save_to_history(result)
            yield _sse({"type": "result", "indicator": indicator, "result": result.model_dump()})
        yield _sse({"type": "done"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

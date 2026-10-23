"""The public OpenRouter model list for the model search in the Info settings: one GET without a key, and a reduction of
the answer to the few fields the page shows. Nothing is guessed - prices, limits and features are OpenRouter's own
values (prices only converted from "per token" to "per million tokens"). Called only on an explicit click.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx

from backend.env_file import VALUE_RE
from backend.i18n import t
from backend.services.base import describe_exception
from backend.services.llm_analyzer import OPENROUTER_APP_HEADERS, STREAM_MAX_TOKENS

MODELS_URL = "https://openrouter.ai/api/v1/models"
MAX_BYTES = 5_000_000  # the real list is about 0.8 MB; a much larger answer is not the list
NAME_LIMIT = 120

logger = logging.getLogger("open_router")


class ModelsError(Exception):
    """The list could not be fetched; `message` is readable and holds no key (none is sent)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _per_million(value) -> float | None:
    """OpenRouter gives USD per token as text ("0.000003"). Negative ("-1" = price depends on the routing), missing or
    unreadable values become None."""
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not price.is_finite() or price < 0:
        return None
    return float(round(price * 1_000_000, 4))


def _count(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def compact(data) -> list[dict]:
    """Keeps text-only models whose id can be saved in the .env file, with the fields the page needs. Anything that does
    not look like the documented shape is skipped instead of failing the whole list."""
    if not isinstance(data, list):
        return []
    models = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if not isinstance(model_id, str) or not VALUE_RE.fullmatch(model_id):
            continue
        arch = item.get("architecture") if isinstance(item.get("architecture"), dict) else {}
        if arch.get("output_modalities") != ["text"]:
            continue
        pricing = item.get("pricing") if isinstance(item.get("pricing"), dict) else {}
        top = item.get("top_provider") if isinstance(item.get("top_provider"), dict) else {}
        params = item.get("supported_parameters")
        name = item.get("name")
        models.append({
            "id": model_id,
            "name": name[:NAME_LIMIT] if isinstance(name, str) else model_id,
            "prompt_per_million": _per_million(pricing.get("prompt")),
            "completion_per_million": _per_million(pricing.get("completion")),
            "context_length": _count(item.get("context_length")),
            "max_completion_tokens": _count(top.get("max_completion_tokens")),
            "json_mode": isinstance(params, list) and "response_format" in params,
        })
    return models


async def fetch_models() -> dict:
    """GET of the public list, no Authorization header (the endpoint needs no key, so none leaves the computer)."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            async with client.stream("GET", MODELS_URL, headers={**OPENROUTER_APP_HEADERS, "Accept": "application/json"}) as resp:
                resp.raise_for_status()
                body = b""
                async for chunk in resp.aiter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise ModelsError(t("models.too_large"))
        data = httpx.Response(200, content=body).json()["data"]
    except httpx.HTTPStatusError as exc:
        logger.error(f"model list: HTTP {exc.response.status_code}")
        raise ModelsError(f"HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        logger.error(f"model list: {describe_exception(exc)}")
        raise ModelsError(type(exc).__name__) from exc
    except (ValueError, KeyError, TypeError) as exc:
        logger.error(f"model list: unexpected answer ({type(exc).__name__})")
        raise ModelsError(t("models.bad_answer")) from exc
    return {"models": compact(data), "email_max_tokens": STREAM_MAX_TOKENS, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}

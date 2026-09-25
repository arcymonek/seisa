"""Server-Sent Events framing shared by the streaming endpoints."""
from __future__ import annotations

import json


def sse(data: dict) -> str:
    """One SSE message: a JSON payload on a `data:` line."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

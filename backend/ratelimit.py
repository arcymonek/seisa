from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import datetime, timezone

from backend.storage import load_vt_usage, save_vt_usage

VT_PER_MINUTE = 4
VT_PER_DAY = 500


class RateLimitedDaily(Exception):
    pass


class SlidingWindowLimiter:
    def __init__(self, max_calls: int, window_seconds: float):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        """Zwraca liczbę sekund oczekiwania, jakie faktycznie minęły."""
        async with self._lock:
            waited = 0.0
            while True:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.window_seconds:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return waited
                sleep_for = self.window_seconds - (now - self._calls[0]) + 0.05
                waited += sleep_for
                await asyncio.sleep(sleep_for)


class VirusTotalRateLimiter:
    def __init__(self):
        self._minute_limiter = SlidingWindowLimiter(VT_PER_MINUTE, 60.0)

    def _today(self) -> str:
        return datetime.now(timezone.utc).astimezone().date().isoformat()

    def daily_count(self) -> int:
        usage = load_vt_usage()
        if usage.get("date") != self._today():
            return 0
        return usage.get("count", 0)

    def _increment_daily(self) -> None:
        today = self._today()
        usage = load_vt_usage()
        if usage.get("date") != today:
            usage = {"date": today, "count": 0}
        usage["count"] = usage.get("count", 0) + 1
        save_vt_usage(usage)

    async def acquire(self, on_wait=None) -> None:
        if self.daily_count() >= VT_PER_DAY:
            raise RateLimitedDaily()
        waited = await self._minute_limiter.acquire()
        if waited and on_wait:
            on_wait(waited)
        self._increment_daily()


vt_rate_limiter = VirusTotalRateLimiter()

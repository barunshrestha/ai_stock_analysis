"""Per-user rate limiting for expensive endpoints (Gemini / Ollama generation).

In-memory and per-process: with more than one API worker each keeps its own counts,
so move this to Redis before scaling out.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Depends, HTTPException

from backend import config
from backend.auth import CurrentUser, get_current_user


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def try_acquire(self, key: str) -> float | None:
        """Record a hit and return None, or return seconds until the next slot frees up."""
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_seconds:
                hits.popleft()
            if len(hits) >= self.limit:
                return self.window_seconds - (now - hits[0])
            hits.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


ai_generation_limiter = SlidingWindowLimiter(limit=config.AI_RATE_LIMIT_PER_HOUR, window_seconds=3600)


def enforce_ai_rate_limit(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """FastAPI dependency: signed-in user under their hourly AI generation budget, else 429."""
    retry_after = ai_generation_limiter.try_acquire(user.id)
    if retry_after is not None:
        minutes = max(1, round(retry_after / 60))
        raise HTTPException(
            status_code=429,
            detail=f"AI generation limit reached ({ai_generation_limiter.limit}/hour). Try again in about {minutes} min.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )
    return user

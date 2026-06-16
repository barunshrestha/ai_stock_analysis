"""In-process TTL cache.

The PRD requires caching to be transparent to users (no cache toggle).
This is a simple per-function TTL memoizer; entries are keyed by call
arguments. Sufficient for a single-process API server. If the backend is
ever scaled to multiple workers, swap for Redis without changing call sites.
"""

from __future__ import annotations

import functools
import threading
import time
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def ttl_cache(seconds: float) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        store: dict[Any, tuple[float, Any]] = {}
        lock = threading.Lock()

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            with lock:
                hit = store.get(key)
                if hit is not None and (now - hit[0]) < seconds:
                    return hit[1]
            value = fn(*args, **kwargs)
            with lock:
                store[key] = (now, value)
                # Opportunistic cleanup to bound memory.
                if len(store) > 512:
                    expired = [k for k, (ts, _) in store.items() if (now - ts) >= seconds]
                    for k in expired:
                        store.pop(k, None)
            return value

        return wrapper  # type: ignore[return-value]

    return decorator

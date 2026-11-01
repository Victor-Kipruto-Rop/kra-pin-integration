from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    """Sliding-window limiter. In-memory, so per-process: use a shared store
    (e.g. Redis) or your gateway's limiter if you run several instances."""

    def __init__(self, limit: int, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, identity: str) -> bool:
        if self.limit <= 0:
            return True
        now = self._clock()
        hits = self._hits[identity]
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

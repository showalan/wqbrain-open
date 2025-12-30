from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, min_interval_seconds: float):
        self._min_interval_seconds = max(0.0, float(min_interval_seconds))
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        if self._min_interval_seconds <= 0:
            return
        with self._lock:
            now = time.monotonic()
            if now < self._next_allowed:
                time.sleep(self._next_allowed - now)
                now = time.monotonic()
            self._next_allowed = now + self._min_interval_seconds

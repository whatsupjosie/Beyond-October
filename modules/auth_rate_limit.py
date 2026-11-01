"""Small bounded sliding-window limiter for setup/login endpoints."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Tuple


@dataclass(frozen=True)
class LimitResult:
    allowed: bool
    retry_after: int
    remaining: int


class SlidingWindowLimiter:
    def __init__(self, *, limit: int, window_seconds: int, max_keys: int = 2048) -> None:
        if limit < 1 or window_seconds < 1 or max_keys < 1:
            raise ValueError("limit, window_seconds, and max_keys must be positive")
        self.limit = int(limit)
        self.window_seconds = int(window_seconds)
        self.max_keys = int(max_keys)
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._last_seen: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _prune_key(self, key: str, now: float) -> Deque[float]:
        q = self._events[key]
        cutoff = now - self.window_seconds
        while q and q[0] <= cutoff:
            q.popleft()
        if not q:
            self._events.pop(key, None)
            self._last_seen.pop(key, None)
            return deque()
        return q

    def _bound_storage(self) -> None:
        overflow = len(self._last_seen) - self.max_keys
        if overflow <= 0:
            return
        for key, _ in sorted(self._last_seen.items(), key=lambda item: item[1])[:overflow]:
            self._last_seen.pop(key, None)
            self._events.pop(key, None)

    def allow(self, key: str) -> LimitResult:
        normalized = (key or "unknown")[:512]
        now = time.monotonic()
        with self._lock:
            q = self._events.get(normalized, deque())
            cutoff = now - self.window_seconds
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.limit:
                retry = max(1, int(round((q[0] + self.window_seconds) - now)))
                self._events[normalized] = q
                self._last_seen[normalized] = now
                return LimitResult(False, retry, 0)
            q.append(now)
            self._events[normalized] = q
            self._last_seen[normalized] = now
            self._bound_storage()
            return LimitResult(True, 0, self.limit - len(q))

    def clear(self, key: str) -> None:
        normalized = (key or "unknown")[:512]
        with self._lock:
            self._events.pop(normalized, None)
            self._last_seen.pop(normalized, None)

    def snapshot(self) -> Tuple[int, int]:
        with self._lock:
            return len(self._events), sum(len(q) for q in self._events.values())

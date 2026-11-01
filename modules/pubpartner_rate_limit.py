"""PubPartner local boundary rate limiter.

Small dependency-free token bucket. It is intentionally gentle in this local
prototype: the point is to prevent runaway UI/provider loops without making
normal testing painful. Swap storage to Redis if the app becomes multi-worker.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class RateLimiter:
    def __init__(self, capacity: int = 120, refill_per_sec: float = 4.0):
        self.capacity = int(capacity)
        self.refill_per_sec = float(refill_per_sec)
        self._buckets: Dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, identity: str) -> Tuple[bool, float]:
        now = time.monotonic()
        identity = str(identity or "anon")[:160]
        with self._lock:
            bucket = self._buckets.get(identity)
            if bucket is None:
                bucket = _Bucket(tokens=float(self.capacity), last_refill=now)
                self._buckets[identity] = bucket
            elapsed = max(0.0, now - bucket.last_refill)
            bucket.tokens = min(float(self.capacity), bucket.tokens + elapsed * self.refill_per_sec)
            bucket.last_refill = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, 0.0
            retry_after = (1.0 - bucket.tokens) / self.refill_per_sec if self.refill_per_sec > 0 else 1.0
            return False, round(retry_after, 2)

    def snapshot(self) -> Dict[str, float]:
        with self._lock:
            return {k: round(v.tokens, 2) for k, v in self._buckets.items()}

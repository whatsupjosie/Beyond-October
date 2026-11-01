"""Small, dependency-free event bus for EVO semantic events.

Design goals:
- typed envelopes only
- deterministic subscriber order
- bounded recursion / causal fan-out
- duplicate-event suppression
- failure isolation with observable dispatch results
- thread-safe subscription and dispatch bookkeeping
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import inspect
from threading import RLock, local
from typing import Callable
from uuid import uuid4

from .semantic_events import EventEnvelope

EventHandler = Callable[[EventEnvelope], None]


@dataclass(frozen=True, slots=True)
class DispatchFailure:
    subscription_id: str
    event_id: str
    event_type: str
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class DispatchResult:
    event_id: str
    delivered: int
    duplicate: bool = False
    failures: tuple[DispatchFailure, ...] = ()


@dataclass(frozen=True, slots=True)
class _Subscription:
    subscription_id: str
    event_type: str
    handler: EventHandler


class EventBus:
    """In-process typed event router with recursion and duplicate guards."""

    WILDCARD = "*"

    def __init__(self, *, max_dispatch_depth: int = 8, seen_capacity: int = 4096) -> None:
        if max_dispatch_depth < 1:
            raise ValueError("max_dispatch_depth must be at least 1")
        if seen_capacity < 1:
            raise ValueError("seen_capacity must be at least 1")
        self._max_dispatch_depth = max_dispatch_depth
        self._seen_capacity = seen_capacity
        self._subscriptions: list[_Subscription] = []
        self._seen_order: deque[str] = deque()
        self._seen: set[str] = set()
        self._lock = RLock()
        self._local = local()

    def subscribe(self, event_type: str, handler: EventHandler) -> str:
        if not event_type.strip():
            raise ValueError("event_type must be non-empty")
        if not callable(handler):
            raise TypeError("handler must be callable")
        if inspect.iscoroutinefunction(handler) or inspect.iscoroutinefunction(getattr(handler, "__call__", None)):
            raise TypeError("EventBus handlers must be synchronous")
        subscription = _Subscription(uuid4().hex, event_type, handler)
        with self._lock:
            self._subscriptions.append(subscription)
        return subscription.subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        with self._lock:
            for index, subscription in enumerate(self._subscriptions):
                if subscription.subscription_id == subscription_id:
                    del self._subscriptions[index]
                    return True
        return False

    def publish(self, event: EventEnvelope, *, fail_fast: bool = False) -> DispatchResult:
        if not isinstance(event, EventEnvelope):
            raise TypeError("EventBus accepts EventEnvelope instances only")

        depth = getattr(self._local, "dispatch_depth", 0)
        if depth >= self._max_dispatch_depth:
            raise RuntimeError("event dispatch recursion limit reached")

        with self._lock:
            if event.event_id in self._seen:
                return DispatchResult(event_id=event.event_id, delivered=0, duplicate=True)
            self._remember(event.event_id)
            subscribers = tuple(
                sub for sub in self._subscriptions
                if sub.event_type in (event.event_type, self.WILDCARD)
            )

        failures: list[DispatchFailure] = []
        delivered = 0
        self._local.dispatch_depth = depth + 1
        try:
            for subscription in subscribers:
                try:
                    result = subscription.handler(event)
                    if inspect.isawaitable(result):
                        if inspect.iscoroutine(result):
                            result.close()
                        raise TypeError("EventBus handlers must be synchronous")
                    delivered += 1
                except Exception as exc:
                    failure = DispatchFailure(
                        subscription_id=subscription.subscription_id,
                        event_id=event.event_id,
                        event_type=event.event_type,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                    failures.append(failure)
                    if fail_fast:
                        raise
        finally:
            self._local.dispatch_depth = depth

        return DispatchResult(
            event_id=event.event_id,
            delivered=delivered,
            failures=tuple(failures),
        )

    def _remember(self, event_id: str) -> None:
        self._seen.add(event_id)
        self._seen_order.append(event_id)
        while len(self._seen_order) > self._seen_capacity:
            expired = self._seen_order.popleft()
            self._seen.discard(expired)

    @property
    def subscription_count(self) -> int:
        with self._lock:
            return len(self._subscriptions)

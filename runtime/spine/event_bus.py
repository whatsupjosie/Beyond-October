from __future__ import annotations

import asyncio
import inspect
import time
import uuid
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Callable, Dict, List, Mapping, Tuple

EventHandler = Callable[[Mapping[str, Any]], Any]


def _immutable_event(event_type: str, data: Dict[str, Any], source: str) -> Mapping[str, Any]:
    payload = {
        "event_type": str(event_type),
        "data": deepcopy(data or {}),
        "source": str(source or "unknown"),
        "timestamp": time.time(),
    }
    return MappingProxyType(payload)


class EventBus:
    """Canonical event routing for PubCast runtime."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, Dict[str, EventHandler]] = {}
        self._tokens: Dict[str, Tuple[str, str]] = {}
        self.history: List[Dict[str, Any]] = []
        self.max_history = 512

    def subscribe(self, event_type: str, handler: EventHandler) -> str:
        if not callable(handler):
            raise TypeError("handler must be callable")
        event_type = str(event_type)
        token = uuid.uuid4().hex
        self._subscribers.setdefault(event_type, {})[token] = handler
        self._tokens[token] = (event_type, token)
        return token

    def unsubscribe(self, token: str) -> None:
        item = self._tokens.pop(token, None)
        if not item:
            return
        event_type, sub_token = item
        subscribers = self._subscribers.get(event_type)
        if subscribers:
            subscribers.pop(sub_token, None)
            if not subscribers:
                self._subscribers.pop(event_type, None)

    def emit(self, event_type: str, data: Dict[str, Any] | None = None, source: str = "runtime") -> Mapping[str, Any]:
        event = _immutable_event(event_type, data or {}, source)
        self._record(event)
        for handler in list(self._subscribers.get(str(event_type), {}).values()):
            result = handler(event)
            if inspect.isawaitable(result):
                self._schedule(result)
        return event

    async def emit_async(self, event_type: str, data: Dict[str, Any] | None = None, source: str = "runtime") -> Mapping[str, Any]:
        event = _immutable_event(event_type, data or {}, source)
        self._record(event)
        pending = []
        for handler in list(self._subscribers.get(str(event_type), {}).values()):
            result = handler(event)
            if inspect.isawaitable(result):
                pending.append(result)
        if pending:
            await asyncio.gather(*pending)
        return event

    def clear(self) -> None:
        self._subscribers.clear()
        self._tokens.clear()
        self.history.clear()

    def _record(self, event: Mapping[str, Any]) -> None:
        self.history.append({"event_type": event["event_type"], "data": deepcopy(event["data"]), "source": event["source"], "timestamp": event["timestamp"]})
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def _schedule(self, awaitable: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(awaitable)
            return
        loop.create_task(awaitable)
from unittest.mock import AsyncMock
import pytest
from modules.evo.event_bus import EventBus
from modules.evo.semantic_events import EventEnvelope


def test_sync_bus_rejects_async_subscriber_instead_of_silently_losing_it():
    bus = EventBus()
    with pytest.raises(TypeError, match="synchronous"):
        bus.subscribe("tick", AsyncMock())


def test_wrapped_awaitable_is_a_visible_dispatch_failure_without_unawaited_coroutine():
    bus = EventBus()
    async def deferred():
        raise AssertionError("A sync bus must not pretend this ran")
    bus.subscribe("tick", lambda _: deferred())
    seen = []
    bus.subscribe("tick", seen.append)
    result = bus.publish(EventEnvelope(source="test", role="system", event_type="tick"))
    assert result.delivered == 1
    assert len(result.failures) == 1
    assert result.failures[0].error_type == "TypeError"
    assert len(seen) == 1

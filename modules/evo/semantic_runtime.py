"""Transactional coordinator for EVO semantic state.

This is the narrow write boundary for canonical runtime truth. Producers submit
proposals; arbitration resolves them; the store commits one immutable snapshot;
and a typed event announces the committed revision.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Iterable

from .arbitration import ArbitrationEngine
from .event_bus import DispatchResult, EventBus
from .mutation import StateMutationRequest
from .semantic_events import EventEnvelope
from .semantic_field import SemanticField, SemanticStore


@dataclass(frozen=True, slots=True)
class SemanticCommit:
    state: SemanticField
    changed: bool
    changed_paths: tuple[str, ...] = ()
    dispatch: DispatchResult | None = None


class SemanticRuntime:
    """Own the only supported proposal -> arbitration -> commit transition."""

    def __init__(
        self,
        *,
        store: SemanticStore | None = None,
        arbitrator: ArbitrationEngine | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.store = store or SemanticStore()
        self.arbitrator = arbitrator or ArbitrationEngine()
        self.event_bus = event_bus or EventBus()

    def snapshot(self) -> SemanticField:
        return self.store.read()

    def apply(self, proposals: Iterable[StateMutationRequest]) -> SemanticCommit:
        """Resolve and atomically commit one proposal batch.

        The current revision is used as an optimistic-concurrency lease. A stale
        concurrent writer therefore fails rather than silently overwriting state.
        No-op proposal batches do not increment the revision or emit an event.
        """
        before = self.store.read()
        after = self.arbitrator.resolve(before, tuple(proposals))
        changed_paths = self._changed_paths(before, after)

        if not changed_paths:
            return SemanticCommit(state=before, changed=False)

        committed = self.store.commit(after, expected_revision=before.revision)
        event = EventEnvelope(
            source="semantic_runtime",
            role="system",
            event_type="semantic.updated",
            payload={
                "revision": committed.revision,
                "previous_revision": before.revision,
                "changed_paths": changed_paths,
            },
            priority=100,
        )
        dispatch = self.event_bus.publish(event)
        return SemanticCommit(
            state=committed,
            changed=True,
            changed_paths=changed_paths,
            dispatch=dispatch,
        )

    @classmethod
    def _changed_paths(cls, before: object, after: object, prefix: str = "") -> tuple[str, ...]:
        if type(before) is not type(after):
            return (prefix.rstrip("."),) if prefix else ("root",)

        if is_dataclass(before) and is_dataclass(after):
            changed: list[str] = []
            for descriptor in fields(before):
                # revision/timestamp are commit metadata, not semantic content.
                if not prefix and descriptor.name in {"revision", "timestamp"}:
                    continue
                child_prefix = f"{prefix}{descriptor.name}"
                changed.extend(
                    cls._changed_paths(
                        getattr(before, descriptor.name),
                        getattr(after, descriptor.name),
                        child_prefix + ".",
                    )
                )
            return tuple(changed)

        if before != after:
            return (prefix.rstrip("."),)
        return ()

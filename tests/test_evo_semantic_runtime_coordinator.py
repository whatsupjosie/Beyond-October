from modules.evo.event_bus import EventBus
from modules.evo.mutation import StateMutationRequest
from modules.evo.semantic_runtime import SemanticRuntime


def test_runtime_commits_one_revision_and_emits_changed_paths():
    bus = EventBus()
    events = []
    bus.subscribe("semantic.updated", events.append)
    runtime = SemanticRuntime(event_bus=bus)

    commit = runtime.apply(
        [
            StateMutationRequest(
                source="vdi_engine",
                role="system",
                path="audience.engagement",
                value=0.8,
                priority=50,
            ),
            StateMutationRequest(
                source="director",
                role="director",
                path="scene.pacing",
                value=0.7,
                priority=20,
            ),
        ]
    )

    assert commit.changed is True
    assert commit.state.revision == 1
    assert commit.changed_paths == ("audience.engagement", "scene.pacing")
    assert commit.dispatch is not None
    assert commit.dispatch.delivered == 1
    assert len(events) == 1
    assert events[0].payload["revision"] == 1
    assert events[0].payload["changed_paths"] == commit.changed_paths


def test_runtime_does_not_commit_or_emit_for_noop_batch():
    bus = EventBus()
    events = []
    bus.subscribe("semantic.updated", events.append)
    runtime = SemanticRuntime(event_bus=bus)

    commit = runtime.apply(
        [
            StateMutationRequest(
                source="jeremy",
                role="observer",
                path="scene.tension",
                value=0.9,
                priority=100,
            )
        ]
    )

    assert commit.changed is False
    assert commit.state.revision == 0
    assert commit.dispatch is None
    assert events == []


def test_competing_writers_have_one_commit_and_one_event_without_lost_update():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from modules.evo.arbitration import ArbitrationEngine

    rendezvous = Barrier(2)
    class ConcurrentArbitrator(ArbitrationEngine):
        def resolve(self, state, proposals):
            resolved = super().resolve(state, proposals)
            rendezvous.wait(timeout=5)
            return resolved

    runtime = SemanticRuntime(arbitrator=ConcurrentArbitrator())
    events = []
    runtime.event_bus.subscribe("semantic.updated", events.append)
    def write(value):
        try:
            return runtime.apply([StateMutationRequest(source="test-writer", role="system",
                path="audience.engagement", value=value)])
        except RuntimeError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(write, value) for value in (0.2, 0.8)]
        results = [future.result(timeout=10) for future in futures]
    commits = [result for result in results if not isinstance(result, Exception)]
    conflicts = [result for result in results if isinstance(result, RuntimeError)]
    assert len(commits) == len(conflicts) == len(events) == 1
    assert "revision conflict" in str(conflicts[0])
    assert runtime.snapshot() is commits[0].state
    assert runtime.snapshot().revision == events[0].payload["revision"] == 1
    assert runtime.snapshot().audience.engagement in (0.2, 0.8)

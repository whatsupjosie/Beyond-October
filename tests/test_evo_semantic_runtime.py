from modules.evo.arbitration import ArbitrationEngine
from modules.evo.mutation import StateMutationRequest
from modules.evo.semantic_field import EmotionState, SemanticField, SemanticStore


def test_arbitration_prefers_priority_and_allows_one_write_per_path():
    engine = ArbitrationEngine()
    state = SemanticField()

    result = engine.resolve(
        state,
        [
            StateMutationRequest(
                source="performer-a",
                role="performer",
                path="emotion.intensity",
                value=0.4,
                priority=5,
                confidence=1.0,
            ),
            StateMutationRequest(
                source="anchor",
                role="anchor",
                path="emotion.intensity",
                value=0.2,
                priority=10,
                confidence=1.0,
            ),
        ],
    )

    assert result.emotion.intensity == 0.2


def test_observer_cannot_mutate_shared_state():
    engine = ArbitrationEngine()
    state = SemanticField()

    result = engine.resolve(
        state,
        [
            StateMutationRequest(
                source="jeremy",
                role="observer",
                path="scene.tension",
                value=0.9,
                priority=100,
                confidence=1.0,
            )
        ],
    )

    assert result == state


def test_semantic_values_are_normalized():
    engine = ArbitrationEngine()
    state = SemanticField()

    result = engine.resolve(
        state,
        [
            StateMutationRequest(
                source="director",
                role="director",
                path="scene.pacing",
                value=5.0,
            )
        ],
    )

    assert result.scene.pacing == 1.0


def test_store_uses_optimistic_revision_guard():
    store = SemanticStore()
    initial = store.read()
    committed = store.commit(initial, expected_revision=0)

    assert committed.revision == 1

    try:
        store.commit(initial, expected_revision=0)
    except RuntimeError as exc:
        assert "revision conflict" in str(exc)
    else:
        raise AssertionError("expected revision conflict")


def test_explicit_empty_permissions_deny_all_writes():
    initial = SemanticField()
    engine = ArbitrationEngine(permissions={})
    result = engine.resolve(initial, [StateMutationRequest(
        source="system", role="system", path="emotion.intensity", value=0.9)])
    assert result == initial


def test_permissions_are_owned_by_arbitrator_not_aliased_to_caller():
    permissions = {"observer": ()}
    engine = ArbitrationEngine(permissions=permissions)
    permissions["observer"] = ("emotion",)
    mutation = StateMutationRequest(source="observer", role="observer",
        path="emotion.intensity", value=0.9)
    assert not engine.is_allowed(mutation)


def test_lower_priority_parent_cannot_overwrite_accepted_child():
    engine = ArbitrationEngine()
    mutations = [StateMutationRequest(source="anchor", role="anchor",
        path="emotion.intensity", value=0.2, priority=100),
        StateMutationRequest(source="performer", role="performer", path="emotion",
            value=EmotionState(intensity=0.9), priority=1)]
    for batch in (mutations, list(reversed(mutations))):
        assert engine.resolve(SemanticField(), batch).emotion.intensity == 0.2


def test_lower_priority_child_cannot_overwrite_accepted_parent():
    engine = ArbitrationEngine()
    result = engine.resolve(SemanticField(), [
        StateMutationRequest(source="system", role="system", path="emotion",
            value=EmotionState(intensity=0.2), priority=100),
        StateMutationRequest(source="performer", role="performer",
            path="emotion.intensity", value=0.9, priority=1)])
    assert result.emotion.intensity == 0.2

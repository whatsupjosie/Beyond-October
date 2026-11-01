"""Semantic snapshot consumption through October's actual async EVO tick."""
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from modules.evo.evo_integration import EVOOrchestrator
from modules.evo.mutation import StateMutationRequest
from modules.evo.prosody_engine import EmotionalState
from modules.evo.semantic_runtime import SemanticRuntime
from modules.evo.vdi_engine import VDIReport, VDISignals
from modules.evo.voice_characters import get_character_profile


def _performer(orchestrator):
    state = EmotionalState(valence=0.9, arousal=0.2, tension_score=0.4)
    orchestrator.facial_orchestrator.tick = Mock(return_value=SimpleNamespace(
        performer_state=state,
        audience_signals=VDISignals(audience_valence=0.1, audience_arousal=0.9),
    ))
    return state


@pytest.mark.asyncio
async def test_default_tick_reads_committed_snapshot_and_emits_provenanced_instructions():
    orchestrator = EVOOrchestrator()
    performer = _performer(orchestrator)
    before = asdict(performer)
    generate = Mock(wraps=orchestrator.prosody_engine.get_synthesis_params)
    orchestrator.prosody_engine.get_synthesis_params = generate
    events = []
    orchestrator.semantic_runtime.event_bus.subscribe("semantic.updated", events.append)
    result = await orchestrator.tick("A real local tick.", performer_frame=object())
    delivered = generate.call_args.kwargs["emotional_state"]
    assert delivered is not performer
    assert delivered.valence < performer.valence
    assert delivered.arousal > performer.arousal
    assert asdict(performer) == before
    assert result.synthesis_params.semantic_revision == result.semantic_state.revision == 1
    assert len(events) == 1  # voice conditioning does not write another revision
    assert orchestrator.semantic_runtime.snapshot() is result.semantic_state
    assert "<speak>" in result.ssml_text


@pytest.mark.asyncio
async def test_prosody_consumes_tick_snapshot_even_if_observer_commits_later_revision():
    runtime = SemanticRuntime()
    def newer(event):
        if event.payload["revision"] == 1:
            runtime.apply([StateMutationRequest(source="test-director", role="system",
                path="emotion.valence", value=1.0)])
    runtime.event_bus.subscribe("semantic.updated", newer)
    orchestrator = EVOOrchestrator(semantic_runtime=runtime)
    _performer(orchestrator)
    condition = Mock(wraps=orchestrator.prosody_semantic_adapter.condition)
    orchestrator.prosody_semantic_adapter.condition = condition
    result = await orchestrator.tick("Use this tick's version.", performer_frame=object())
    assert runtime.snapshot().revision == 2
    assert result.semantic_state.revision == 1
    assert condition.call_args.args[1] is result.semantic_state
    assert result.synthesis_params.semantic_revision == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("options", [dict(semantic_enabled=False), dict(semantic_prosody_enabled=False)])
async def test_legacy_switches_skip_conditioning_and_do_not_claim_semantic_delivery(options):
    orchestrator = EVOOrchestrator(**options)
    performer = _performer(orchestrator)
    orchestrator.prosody_semantic_adapter.condition = Mock(side_effect=AssertionError("must bypass"))
    generate = Mock(wraps=orchestrator.prosody_engine.get_synthesis_params)
    orchestrator.prosody_engine.get_synthesis_params = generate
    result = await orchestrator.tick("Keep original delivery.", performer_frame=object())
    assert generate.call_args.kwargs["emotional_state"] is performer
    assert result.synthesis_params.semantic_revision is None


@pytest.mark.asyncio
async def test_zero_room_weight_preserves_delivery_but_records_snapshot_consumption():
    orchestrator = EVOOrchestrator(semantic_room_weight=0)
    performer = _performer(orchestrator)
    generate = Mock(wraps=orchestrator.prosody_engine.get_synthesis_params)
    orchestrator.prosody_engine.get_synthesis_params = generate
    result = await orchestrator.tick("Performer only.", performer_frame=object())
    assert asdict(generate.call_args.kwargs["emotional_state"]) == asdict(performer)
    assert result.synthesis_params.semantic_revision == result.semantic_state.revision


@pytest.mark.asyncio
@pytest.mark.parametrize("character", ["pete", "pete_enhanced"])
async def test_character_constraints_remain_final_and_provider_schemas_exclude_metadata(character):
    orchestrator = EVOOrchestrator(active_character=character)
    _performer(orchestrator)
    result = await orchestrator.tick("Keep the character.", performer_frame=object())
    profile = get_character_profile(orchestrator.active_character)
    assert result.synthesis_params.style_exaggeration <= profile.max_expressiveness
    assert result.synthesis_params.stability >= profile.min_stability
    if not profile.crack_allowed:
        assert result.synthesis_params.crack_permission is False
        assert result.synthesis_params.crack_probability == 0
    assert "semantic_revision" not in result.synthesis_params.to_elevenlabs()
    assert "semantic_revision" not in result.synthesis_params.to_cartesia()


@pytest.mark.asyncio
async def test_conditioning_changes_voice_delivery_without_changing_vdi_or_render_priorities():
    semantic = EVOOrchestrator()
    legacy = EVOOrchestrator(semantic_prosody_enabled=False)
    _performer(semantic)
    _performer(legacy)
    current = await semantic.tick("The same sentence.", performer_frame=object())
    original = await legacy.tick("The same sentence.", performer_frame=object())
    def without_timestamp(value):
        return {k: v for k, v in asdict(value).items() if k != "timestamp"}
    assert without_timestamp(current.vdi_report) == without_timestamp(original.vdi_report)
    assert without_timestamp(current.priority_vector) == without_timestamp(original.priority_vector)
    assert current.synthesis_params.pitch_shift_st != original.synthesis_params.pitch_shift_st
    assert current.synthesis_params.speech_rate != original.synthesis_params.speech_rate
    assert semantic.get_current_state()["tick_count"] == 1


@pytest.mark.asyncio
async def test_noop_tick_reuses_committed_revision_without_duplicate_event():
    orchestrator = EVOOrchestrator()
    orchestrator.vdi_engine.update = Mock(return_value=VDIReport())
    events = []
    orchestrator.semantic_runtime.event_bus.subscribe("semantic.updated", events.append)
    first = await orchestrator.tick("First sentence.")
    second = await orchestrator.tick("Second sentence.")
    assert second.semantic_state is first.semantic_state
    assert second.synthesis_params.semantic_revision == first.synthesis_params.semantic_revision
    assert len(events) == 1
    assert orchestrator.get_current_state()["tick_count"] == 2


@pytest.mark.asyncio
async def test_semantic_prosody_can_be_disabled_between_ticks():
    orchestrator = EVOOrchestrator()
    _performer(orchestrator)
    first = await orchestrator.tick("Use room context.", performer_frame=object())
    orchestrator.semantic_prosody_enabled = False
    orchestrator.prosody_semantic_adapter.condition = Mock(side_effect=AssertionError("must bypass"))
    second = await orchestrator.tick("Use the compatibility path.", performer_frame=object())
    assert first.synthesis_params.semantic_revision is not None
    assert second.semantic_state is not None
    assert second.synthesis_params.semantic_revision is None


@pytest.mark.parametrize("weight", [-0.01, 1.01, float("nan")])
def test_orchestrator_rejects_invalid_room_weight(weight):
    with pytest.raises(ValueError, match="room_weight"):
        EVOOrchestrator(semantic_room_weight=weight)

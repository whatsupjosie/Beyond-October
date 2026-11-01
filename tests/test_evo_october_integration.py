"""Exercise October's real EVO tick, retaining the legacy output contracts."""
from dataclasses import FrozenInstanceError, asdict
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from modules.evo import EVOOrchestrator, EVOTick, SemanticRuntime
from modules.evo.prosody_engine import EmotionalState, SynthesisParams
from modules.evo.semantic_field import SafetyState, SemanticField
from modules.evo.vdi_engine import VDIReport, VDISignals


def _without_timing(value):
    if isinstance(value, dict):
        return {k: _without_timing(v) for k, v in value.items()
                if k not in {"timestamp", "total_ms"}}
    if isinstance(value, list):
        return [_without_timing(v) for v in value]
    return value


def _legacy_outputs(tick):
    return _without_timing({
        "vdi": asdict(tick.vdi_report),
        "synthesis": asdict(tick.synthesis_params),
        "ssml": tick.ssml_text,
        "priority": asdict(tick.priority_vector),
    })


@pytest.mark.asyncio
async def test_real_tick_commits_before_event_and_retains_voice_render_outputs():
    runtime = SemanticRuntime()
    orchestrator = EVOOrchestrator(semantic_runtime=runtime, semantic_prosody_enabled=False)
    compatibility = EVOOrchestrator(semantic_enabled=False)
    observed = []

    def observe(event):
        state = runtime.snapshot()
        assert event.payload["revision"] == state.revision
        observed.append(state)

    runtime.event_bus.subscribe("semantic.updated", observe)
    for engagement in (0.8, 0.3, 0.9):
        signals = VDISignals(audience_engagement=engagement, audience_attention=0.85)
        tick = await orchestrator.tick("Test the local EVO path.", additional_signals=signals)
        old = await compatibility.tick("Test the local EVO path.", additional_signals=signals)
        assert _legacy_outputs(tick) == _legacy_outputs(old)
        assert tick.semantic_state is observed[-1]
        assert tick.semantic_state is orchestrator.get_semantic_state()
        # Existing merge semantics are deliberately retained.
        assert tick.semantic_state.audience.engagement == pytest.approx((0.5 + engagement) / 2)
        assert tick.to_pete_shoulder()["semantic_revision"] == tick.semantic_state.revision
    assert len(observed) == 3
    assert orchestrator.get_current_state()["tick_count"] == 3
    json.dumps(orchestrator.get_current_state())


@pytest.mark.asyncio
async def test_disabled_semantics_bypasses_adapter_and_keeps_legacy_state_shape():
    orchestrator = EVOOrchestrator(semantic_enabled=False)
    orchestrator.vdi_semantic_adapter.propose = Mock(side_effect=AssertionError("must bypass"))
    events = []
    orchestrator.semantic_runtime.event_bus.subscribe("*", events.append)
    injected = orchestrator.inject_signals(VDISignals(audience_engagement=0.9))
    tick = await orchestrator.tick("Compatibility output.")
    assert isinstance(injected, VDIReport)
    assert tick.semantic_state is None
    assert "semantic_revision" not in tick.to_pete_shoulder()
    assert "semantic" not in orchestrator.get_current_state()
    assert orchestrator.get_semantic_state().revision == 0
    assert events == []


@pytest.mark.asyncio
async def test_camera_analysis_boundary_and_engine_lifecycle_without_devices():
    orchestrator = EVOOrchestrator(semantic_prosody_enabled=False)
    performer = EmotionalState(valence=0.8, arousal=0.4)
    facial = SimpleNamespace(
        performer_state=performer,
        audience_signals=VDISignals(audience_engagement=0.72, confusion_intensity=0.18),
    )
    orchestrator.facial_orchestrator.tick = Mock(return_value=facial)
    engine = SimpleNamespace(irm=SimpleNamespace(set_batch_size=Mock()), config=SimpleNamespace(quality_level=None))
    camera = SimpleNamespace(auto_switching_enabled=True, _switchblade_vector=None)
    await orchestrator.start(engine, camera)
    worker = orchestrator.epete._worker_task
    try:
        tick = await orchestrator.tick("A synthetic frame.", performer_frame=object())
        assert tick.facial_tick is facial
        assert tick.semantic_state.audience.engagement == 0.72
        assert tick.semantic_state.audience.confusion == 0.18
        assert performer.valence == 0.8  # no semantic prosody conditioning in this slice
        engine.irm.set_batch_size.assert_called_once()
        assert camera._switchblade_vector is tick.priority_vector
        assert orchestrator._running is True
    finally:
        await orchestrator.stop()
    assert worker.done()
    assert orchestrator._running is False


@pytest.mark.asyncio
async def test_subscriber_failure_does_not_break_tick_or_other_subscribers():
    orchestrator = EVOOrchestrator()
    def broken(_event):
        raise RuntimeError("isolated observer failure")
    healthy = []
    orchestrator.semantic_runtime.event_bus.subscribe("semantic.updated", broken)
    orchestrator.semantic_runtime.event_bus.subscribe("semantic.updated", healthy.append)
    tick = await orchestrator.tick("Keep processing.")
    assert tick.semantic_state.revision == 1
    assert healthy[0].payload["revision"] == 1
    assert tick.ssml_text


def test_instances_do_not_share_semantic_state_and_injection_returns_legacy_report():
    first, second = EVOOrchestrator(), EVOOrchestrator()
    report = first.inject_signals(VDISignals(audience_engagement=0.9))
    assert report is first.vdi_engine.get_current_report()
    assert first.get_semantic_state().revision == 1
    assert second.get_semantic_state().revision == 0


def test_safety_flags_are_detached_and_snapshot_exports_are_mutable_copies():
    original = {"paused": False}
    state = SemanticField(safety=SafetyState(flags=original))
    original["paused"] = True
    assert state.safety.flags["paused"] is False
    with pytest.raises(TypeError):
        state.safety.flags["paused"] = True
    with pytest.raises(FrozenInstanceError):
        state.audience.engagement = 0.1
    exported = state.snapshot()
    exported["safety"]["flags"]["paused"] = True
    exported["audience"]["engagement"] = 0.1
    assert state.safety.flags["paused"] is False
    assert state.audience.engagement == 0.5
    json.dumps(exported)


def test_evo_tick_old_positional_constructor_order_is_unchanged():
    report, params = VDIReport(), SynthesisParams()
    tick = EVOTick(report, params, "ssml", None, None, 12.5, 123.0)
    assert tick.total_ms == 12.5
    assert tick.timestamp == 123.0
    assert tick.semantic_state is None

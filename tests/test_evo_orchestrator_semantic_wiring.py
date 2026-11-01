from modules.evo.evo_integration import EVOOrchestrator, EVOTick
from modules.evo.prosody_engine import SynthesisParams
from modules.evo.semantic_field import SemanticField
from modules.evo.semantic_runtime import SemanticRuntime
from modules.evo.vdi_engine import VDIEngine, VDIReport, VDISignals
from modules.evo.vdi_semantic_adapter import VDISemanticAdapter


def _orchestrator_for_signal_injection() -> EVOOrchestrator:
    """Build only the dependencies exercised by inject_signals.

    This deliberately bypasses the heavyweight camera/E-Pete construction so the
    semantic write boundary can be tested as a fast unit.
    """
    orchestrator = EVOOrchestrator.__new__(EVOOrchestrator)
    orchestrator.vdi_engine = VDIEngine(smoothing_window=1, mode_hysteresis=0.0)
    orchestrator.vdi_semantic_adapter = VDISemanticAdapter()
    orchestrator.semantic_runtime = SemanticRuntime()
    orchestrator.semantic_enabled = True
    return orchestrator


def test_injected_vdi_signals_commit_through_semantic_runtime():
    orchestrator = _orchestrator_for_signal_injection()
    signals = VDISignals(
        audience_engagement=0.82,
        audience_valence=0.75,
        audience_arousal=0.68,
        audience_attention=0.91,
        confusion_intensity=0.14,
    )

    report = orchestrator.inject_signals(signals)
    state = orchestrator.get_semantic_state()

    assert report is orchestrator.vdi_engine.get_current_report()
    assert state.revision == 1
    assert state.audience.engagement == 0.82
    assert state.audience.attention == 0.91
    assert state.audience.confusion == 0.14
    assert state.emotion.valence == 0.5


def test_every_signal_injection_uses_canonical_revision_boundary():
    orchestrator = _orchestrator_for_signal_injection()

    orchestrator.inject_signals(VDISignals(audience_engagement=0.65))
    first = orchestrator.get_semantic_state()
    orchestrator.inject_signals(VDISignals(audience_engagement=0.85))
    second = orchestrator.get_semantic_state()

    assert first.revision == 1
    assert second.revision == 2
    assert first is not second
    assert first.audience.engagement == 0.65
    assert second.audience.engagement == 0.85


def test_evo_tick_exposes_semantic_revision_to_pete_shoulder_context():
    state = SemanticField(revision=7)
    tick = EVOTick(
        vdi_report=VDIReport(),
        synthesis_params=SynthesisParams(),
        semantic_state=state,
    )

    shoulder = tick.to_pete_shoulder()

    assert shoulder["semantic_revision"] == 7

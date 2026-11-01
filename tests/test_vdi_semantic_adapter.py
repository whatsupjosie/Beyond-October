from modules.evo.arbitration import ArbitrationEngine
from modules.evo.semantic_field import SemanticField
from modules.evo.vdi_engine import VDIEngine, VDISignals
from modules.evo.vdi_semantic_adapter import VDISemanticAdapter


def test_vdi_adapter_emits_arbitration_ready_observations():
    signals = VDISignals(
        audience_engagement=0.82,
        audience_valence=0.75,
        audience_arousal=0.68,
        audience_attention=0.91,
        confusion_intensity=0.12,
    )
    report = VDIEngine(smoothing_window=1, mode_hysteresis=0.0).update(signals)
    proposals = VDISemanticAdapter().propose(signals, report)

    assert {proposal.path for proposal in proposals} == {
        "audience.engagement",
        "audience.confusion",
        "audience.attention",
        "emotion.valence",
        "emotion.intensity",
    }
    assert all(proposal.role == "system" for proposal in proposals)
    assert all(proposal.source == "vdi_engine" for proposal in proposals)

    resolved = ArbitrationEngine().resolve(SemanticField(), proposals)

    assert resolved.audience.engagement == 0.82
    assert resolved.audience.attention == 0.91
    assert resolved.audience.confusion == 0.12
    assert resolved.emotion.valence == 0.5
    assert 0.0 <= resolved.emotion.intensity <= 1.0


def test_vdi_adapter_values_are_normalized_by_arbitration():
    signals = VDISignals(
        audience_engagement=5.0,
        audience_valence=-2.0,
        audience_arousal=4.0,
        audience_attention=-1.0,
        confusion_intensity=3.0,
    )
    report = VDIEngine(smoothing_window=1, mode_hysteresis=0.0).update(signals)
    proposals = VDISemanticAdapter().propose(signals, report)
    resolved = ArbitrationEngine().resolve(SemanticField(), proposals)

    assert resolved.audience.engagement == 1.0
    assert resolved.audience.attention == 0.0
    assert resolved.audience.confusion == 1.0
    assert resolved.emotion.valence == -1.0
    assert resolved.emotion.intensity == 1.0

import pytest

from modules.evo.prosody_engine import EmotionalState
from modules.evo.prosody_semantic_adapter import ProsodySemanticAdapter
from modules.evo.semantic_field import EmotionState, SemanticField


def test_semantic_conditioning_returns_new_state_without_mutating_inputs():
    performer = EmotionalState(valence=0.8, arousal=0.4, tension_score=0.2)
    semantic = SemanticField(
        emotion=EmotionState(valence=-0.6, intensity=0.9, stability=0.4)
    )
    adapter = ProsodySemanticAdapter(room_weight=0.25)

    conditioned = adapter.condition(performer, semantic)

    assert conditioned is not performer
    assert performer.valence == 0.8
    assert performer.arousal == 0.4
    assert performer.tension_score == 0.2
    assert semantic.emotion.valence == -0.6
    assert conditioned.valence == pytest.approx(0.65)
    assert conditioned.arousal == pytest.approx(0.525)
    assert conditioned.tension_score == pytest.approx(0.3)


def test_zero_room_weight_preserves_performer_delivery_state():
    performer = EmotionalState(valence=0.2, arousal=0.3, tension_score=0.4)
    semantic = SemanticField(
        emotion=EmotionState(valence=1.0, intensity=1.0, stability=0.0)
    )

    conditioned = ProsodySemanticAdapter(room_weight=0.0).condition(performer, semantic)

    assert conditioned.valence == performer.valence
    assert conditioned.arousal == performer.arousal
    assert conditioned.tension_score == performer.tension_score


def test_room_weight_is_validated():
    try:
        ProsodySemanticAdapter(room_weight=1.01)
    except ValueError as exc:
        assert "room_weight" in str(exc)
    else:
        raise AssertionError("expected invalid room_weight to raise ValueError")

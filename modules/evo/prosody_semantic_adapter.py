"""Read-only bridge from canonical semantic state into performer prosody state.

The adapter keeps ProsodyEngine independent of shared-state ownership. It consumes
an immutable SemanticField snapshot and returns a new EmotionalState, leaving both
inputs untouched. That lets voice delivery react to the room without giving the
voice layer permission to mutate canonical truth.
"""
from __future__ import annotations

from dataclasses import replace

from .prosody_engine import EmotionalState
from .semantic_field import SemanticField


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class ProsodySemanticAdapter:
    """Condition performer emotion with room-level semantic context."""

    def __init__(self, room_weight: float = 0.25) -> None:
        if not 0.0 <= room_weight <= 1.0:
            raise ValueError("room_weight must be between 0.0 and 1.0")
        self.room_weight = float(room_weight)

    def condition(
        self,
        performer: EmotionalState,
        semantic: SemanticField,
    ) -> EmotionalState:
        """Return a new prosody state informed by the canonical snapshot.

        Performer expression remains dominant by default (75%). The room-level
        field contributes valence/arousal/tension gently enough to avoid feedback
        oscillation while still giving every performer the same emotional reality.
        """
        room = self.room_weight
        performer_weight = 1.0 - room
        room_valence = _clamp01((semantic.emotion.valence + 1.0) / 2.0)
        room_tension = _clamp01(1.0 - semantic.emotion.stability)

        return replace(
            performer,
            valence=_clamp01(
                performer.valence * performer_weight + room_valence * room
            ),
            arousal=_clamp01(
                performer.arousal * performer_weight + semantic.emotion.intensity * room
            ),
            tension_score=_clamp01(
                performer.tension_score * performer_weight + room_tension * room
            ),
        )

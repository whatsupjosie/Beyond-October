"""Compatibility adapter from the existing VDI engine into SemanticField proposals.

VDI remains a calculation engine. This adapter translates its sensor inputs and
report into state-change proposals, preserving the rule that cognition and sensing
never mutate the canonical semantic snapshot directly.
"""
from __future__ import annotations

from .mutation import StateMutationRequest
from .vdi_engine import VDIReport, VDISignals


class VDISemanticAdapter:
    """Translate VDI observations into arbitration-ready semantic proposals."""

    SOURCE = "vdi_engine"

    def propose(
        self,
        signals: VDISignals,
        report: VDIReport,
    ) -> tuple[StateMutationRequest, ...]:
        confidence = max(0.0, min(1.0, float(report.confidence)))
        audience_valence = max(-1.0, min(1.0, (float(signals.audience_valence) * 2.0) - 1.0))

        # Emotional intensity is intentionally derived from both sensed arousal and
        # the fused VDI score. This keeps one noisy channel from dominating the field.
        emotional_intensity = max(
            0.0,
            min(1.0, float(signals.audience_arousal) * 0.55 + float(report.vdi_score) * 0.45),
        )

        return (
            StateMutationRequest(
                source=self.SOURCE,
                role="system",
                path="audience.engagement",
                value=float(signals.audience_engagement),
                priority=50,
                confidence=confidence,
                reason="VDI audience engagement observation",
            ),
            StateMutationRequest(
                source=self.SOURCE,
                role="system",
                path="audience.confusion",
                value=float(signals.confusion_intensity),
                priority=50,
                confidence=confidence,
                reason="VDI audience confusion observation",
            ),
            StateMutationRequest(
                source=self.SOURCE,
                role="system",
                path="audience.attention",
                value=float(signals.audience_attention),
                priority=50,
                confidence=confidence,
                reason="VDI audience attention observation",
            ),
            StateMutationRequest(
                source=self.SOURCE,
                role="system",
                path="emotion.valence",
                value=audience_valence,
                priority=40,
                confidence=confidence,
                reason="VDI normalized audience valence",
            ),
            StateMutationRequest(
                source=self.SOURCE,
                role="system",
                path="emotion.intensity",
                value=emotional_intensity,
                priority=40,
                confidence=confidence,
                reason="VDI fused audience emotional intensity",
            ),
        )

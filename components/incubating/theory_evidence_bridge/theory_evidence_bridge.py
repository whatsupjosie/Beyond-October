"""
modules/theory_evidence_bridge.py — Wires evidence_layer, contradiction_engine,
and theory_graph into one tick()/distill() surface for EVOOrchestrator.

WHY THIS FILE EXISTS

    All three modules already document their own EVOOrchestrator integration
    point in their own factory docstrings:

        evidence_layer.create_evidence_layer()   → "Call from EVOOrchestrator.tick()"
        theory_graph.create_theory_graph()        → "graph.propagate(...) after evidence
                                                       layer propagates a theory change"
        contradiction_engine (no factory function — constructed directly)

    But nothing actually calls any of them from evo_integration.py — confirmed
    by reading EVOOrchestrator.__init__ and tick() directly; neither is
    imported and tick()'s seven real steps never reference them. This bridge
    is the thing that was missing: it composes the three per their own
    documented contracts and exposes ONE tick()/distill() pair for
    EVOOrchestrator to call, instead of three separately.

WHAT'S WIRED EXACTLY AS DOCUMENTED, AND WHAT'S NEW GLUE

    - EvidenceLayer + SignalAdapter: wired exactly per create_evidence_layer()'s
      own docstring (adapter.process_tick(vdi_report, emotional_state, topic)).
    - ContradictionEngine.ingest_marker(marker): wired exactly per its own
      docstring ("from the EvidenceLayer marker stream").
    - TheoryGraph.register_theories(evidence._active_theories): wired exactly
      per theory_graph.py's own comment ("graph.register_theories(evidence_layer._active_theories)").
    - Contradiction instability → theory confidence: contradiction_engine's
      own docstring says get_instability_signals() is "Used by TheoryGraph to
      influence theory confidence," but no call site for that exists in any
      of the three files as uploaded. The propagate() call below is this
      bridge's own reasonable implementation of that stated intent, NOT
      something recovered from existing code — flagged here so it's not
      mistaken for verified original wiring.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple

from modules.evidence_layer import EvidenceLayer, SignalAdapter, create_evidence_layer, DB_PATH as EVIDENCE_DB_PATH
from modules.contradiction_engine import ContradictionEngine, InstabilityLevel
from modules.theory_graph import TheoryGraph, PresenceModeEngine, create_theory_graph

logger = logging.getLogger("pubcast.theory_bridge")

# Instability level → propagation delta applied to the matching theory's
# confidence, per contradiction_engine's stated intent. New weighting,
# documented here rather than presented as recovered from elsewhere.
_INSTABILITY_TO_DELTA = {
    InstabilityLevel.NOTED:     0.00,   # single contradiction — not yet a graph-level signal
    InstabilityLevel.RECURRING: -0.05,
    InstabilityLevel.VOLATILE:  -0.12,
    InstabilityLevel.CORE:      -0.20,
}


class TheoryEvidenceBridge:
    """
    One object EVOOrchestrator can hold and call per tick, instead of three.
    """

    def __init__(
        self,
        session_id: str,
        db_path: Path = EVIDENCE_DB_PATH,
    ):
        self.session_id = session_id
        self.evidence, self.signal_adapter = create_evidence_layer(session_id, db_path)
        self.contradiction = ContradictionEngine(db_path=db_path, session_id=session_id)
        self.graph, self.presence_engine = create_theory_graph(session_id, db_path)
        logger.info(f"[TheoryBridge] Initialized — session {session_id}")

    def tick(
        self,
        vdi_report: Any,
        emotional_state: Any,
        current_topic: str = "",
        audience_size: int = 0,
        is_live_broadcast: bool = False,
        identity_moment_active: bool = False,
    ) -> dict:
        """
        Call once per EVOOrchestrator.tick(), after VDI update — same point
        evidence_layer.py and theory_graph.py both independently document.
        """
        # 1. Evidence markers from this tick's VDI/prosody signals
        markers = self.signal_adapter.process_tick(vdi_report, emotional_state, current_topic)

        # 2. Feed each marker to the contradiction engine
        new_contradictions = []
        for marker in markers:
            new_contradictions.extend(self.contradiction.ingest_marker(marker))

        # 3. Keep the graph's theory set in sync with what evidence_layer is tracking
        if self.evidence._active_theories:
            self.graph.register_theories(self.evidence._active_theories)

        # 4. Bridge instability → theory confidence (this file's own glue,
        #    see module docstring — not verified pre-existing wiring)
        for signal in self.contradiction.get_instability_signals(min_level=InstabilityLevel.RECURRING):
            delta = _INSTABILITY_TO_DELTA.get(signal.instability_level, 0.0)
            if delta != 0.0 and signal.topic_cluster in self.evidence._active_theories:
                self.graph.propagate(signal.topic_cluster, delta)

        # 5. Presence mode for this tick
        presence_mode = self.presence_engine.compute(
            audience_size=audience_size,
            vdi_score=getattr(vdi_report, "vdi_score", 0.5),
            voice_mode=str(getattr(vdi_report, "voice_mode", "mixed")),
            is_live_broadcast=is_live_broadcast,
            identity_moment_active=identity_moment_active,
        )

        return {
            "markers_emitted": len(markers),
            "new_contradictions": len(new_contradictions),
            "presence_mode": presence_mode,
        }

    def get_briefing(self) -> str:
        """Combined theory + contradiction briefing for Pete's context, at current presence mode."""
        parts = []
        theory_briefing = self.graph.get_briefing(self.presence_engine.current)
        if theory_briefing:
            parts.append(theory_briefing)
        contradiction_briefing = self.contradiction.get_contradiction_briefing()
        if contradiction_briefing:
            parts.append(contradiction_briefing)
        return "\n\n".join(parts)

    def distill(self) -> None:
        """Session-end maintenance for all three systems, in dependency order."""
        self.evidence.distill_evidence()
        self.contradiction.distill()
        self.graph.distill(self.session_id)
        logger.info(f"[TheoryBridge] Distilled session {self.session_id}")


def create_theory_evidence_bridge(
    session_id: str,
    db_path: Path = EVIDENCE_DB_PATH,
) -> TheoryEvidenceBridge:
    return TheoryEvidenceBridge(session_id=session_id, db_path=db_path)


__all__ = ["TheoryEvidenceBridge", "create_theory_evidence_bridge"]

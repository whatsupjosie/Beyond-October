from __future__ import annotations

import json
from dataclasses import dataclass
import logging
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .alex_core import AlexCore, AIState, UserBattery
from .emotional_orchestrator import EmotionalOrchestrator
from .limited_exposure import (
    DataClass, DataLabel, LimitedCategory, STANDARD_LABEL, blackbox_envelope,
    label_from_mapping, shared_view,
)

DEFAULT_PACKET_TTL_SECONDS = 60 * 60 * 8
MAX_SIGNAL_HISTORY = 64
DEFAULT_SIGNAL_COOLDOWN_SECONDS = 0
AUTHORITY_ACTIONS = {"freeze_actor", "hold_action", "mute_user", "kick_user", "ban_user"}
AUTHORITY_ACTION_ALIASES = {
    "freeze_avatar": "freeze_actor",
    "freeze": "freeze_actor",
    "ban": "ban_user",
    "mute": "mute_user",
    "kick": "kick_user",
}
PRIVATE_EVENT_FIELDS = {"raw_text", "full_transcript", "private_cue", "private_profile", "secret", "token", "api_key"}

logger = logging.getLogger("alex_jeremy_bridge")


def _canonical_authority_action(action: Any) -> str:
    raw = str(action or "").strip()
    return AUTHORITY_ACTION_ALIASES.get(raw, raw)



@dataclass(frozen=True)
class LegacyBridgePacket:
    tone: str
    fragility_level: float
    care_priority: str
    flags: List[str]

class AlexJeremyBridge:
    """Permissioned bridge between Alex (personal) and Jeremy (PubCast space).

    Alex stays sovereign and private. Jeremy only receives a minimal packet that
    helps him run the room more gently/intelligently. Authority-bearing actions
    are never granted by this bridge unless an injected authority reviewer
    explicitly approves them.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        *,
        alex: Any = None,
        jeremy: Any = None,
        authority_reviewer: Any = None,
        blackbox_logger: Any = None,
        signal_cooldown_seconds: int = DEFAULT_SIGNAL_COOLDOWN_SECONDS,
    ):
        self._legacy_alex = alex
        self._legacy_jeremy = jeremy
        if (alex is None) != (jeremy is None):
            raise ValueError("legacy bridge mode requires both alex and jeremy")
        if data_dir is None:
            if alex is None:
                raise TypeError("data_dir is required unless alex and jeremy are supplied")
            db_path = getattr(alex, "_db_path", None)
            data_dir = Path(db_path).parent if db_path else Path(tempfile.gettempdir()) / "pubcast_legacy_bridge"
        self.data_dir = Path(data_dir)
        self.bridge_dir = self.data_dir / "alex_bridge"
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        self._alex_instances: Dict[str, AlexCore] = {}
        self.alex_backup = None  # optional local and Google Drive backup engine
        self.care_eq = None  # one shared CARE session adapter, opt-in
        self._io_lock = threading.RLock()
        self._authority_reviewer = authority_reviewer
        self._blackbox_logger = blackbox_logger
        self._signal_cooldown_seconds = max(0, int(signal_cooldown_seconds))
        self._last_signal_at: Dict[str, float] = {}
        self._bridge_log_failures: List[Dict[str, Any]] = []
        self.emotional_orchestrator = EmotionalOrchestrator()

    async def handoff_to_jeremy(self, *, user_id: str) -> LegacyBridgePacket:
        """Compatibility seam for the pre-AlexCore async memory bridge."""
        if self._legacy_alex is None or self._legacy_jeremy is None:
            raise RuntimeError("handoff_to_jeremy is available only in legacy bridge mode")
        raw = await self._legacy_alex.generate_bridge_packet()
        packet = LegacyBridgePacket(
            tone=str(raw.get("tone") or "neutral"),
            fragility_level=float(raw.get("fragility_level") or 0.0),
            care_priority=str(raw.get("care_priority") or "low"),
            flags=list(raw.get("flags") or []),
        )
        await self._legacy_jeremy.remember(
            f"guidance alex for {user_id}: tone={packet.tone}; fragility={packet.fragility_level:.3f}; care={packet.care_priority}",
            importance=8, tags=["guidance", "alex", user_id], source="alex_bridge",
        )
        return packet

    async def signal_alex(self, *, urgency: str, room_state: str, reason: str) -> None:
        """Compatibility return path for the pre-AlexCore async memory bridge."""
        if self._legacy_alex is None:
            raise RuntimeError("signal_alex is available only in legacy bridge mode")
        await self._legacy_alex.remember_moment(
            f"Jeremy signal: urgency={urgency}; room_state={room_state}; reason={reason}",
            importance=8, tags=["jeremy", "signal", urgency], source="alex_bridge",
        )
        state = await self._legacy_alex.get_emotional_state()
        fragility = float(getattr(state, "fragility_level", 0.0) or 0.0) if state is not None else 0.0
        stress = float(getattr(state, "stress_level", 0.0) or 0.0) if state is not None else 0.0
        updates = {"care_priority": "high" if urgency == "high" else "medium"}
        if urgency == "high" or room_state in {"destabilizing", "critical"}:
            updates.update({"fragility_level": max(fragility, 0.7), "stress_level": max(stress, 0.75)})
        await self._legacy_alex.update_emotional_state(**updates)

    def _safe(self, value: str) -> str:
        return ''.join(c if c.isalnum() or c in '-_.' else '_' for c in str(value or 'anon'))[:120] or 'anon'

    def _session_path(self, session_id: str) -> Path:
        return self.bridge_dir / f"session_{self._safe(session_id)}.json"

    def _signals_path(self, session_id: str, user_id: str) -> Path:
        return self.bridge_dir / f"signals_{self._safe(session_id)}_{self._safe(user_id)}.json"

    def alex_for(self, user_id: str) -> AlexCore:
        user_id = user_id or "default"
        alex = self._alex_instances.get(user_id)
        if alex is None:
            if self.alex_backup is not None:
                try:
                    self.alex_backup.restore_if_empty(user_id)
                except Exception:
                    logger.exception("Alex backup restore-if-empty failed; using available local state")
            alex = AlexCore(user_id=user_id, data_dir=self.data_dir / "alex")
            alex.after_turn_hook = self._notify_alex_backup
            self._alex_instances[user_id] = alex
        return alex

    def _notify_alex_backup(self, user_id: str) -> None:
        if self.alex_backup is not None:
            self.alex_backup.notify_turn(user_id)

    def build_entry_packet(
        self,
        *,
        user_id: str,
        session_id: str,
        project_id: str,
        room_id: str,
        display_name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        alex = self.alex_for(user_id)
        packet = self._packet_from_alex(alex, user_id=user_id, session_id=session_id, project_id=project_id, room_id=room_id)
        if metadata and isinstance(metadata, dict):
            packet["entry_context"] = {
                "presence_mode": metadata.get("presence_mode"),
                "availability": metadata.get("availability"),
            }
        packet.update({
            "display_name": display_name or user_id,
            "bridge_scope": "entry",
            "generated_at": time.time(),
        })
        packet["blackbox_recorded"] = self._record_bridge_event(
            "alex_entry_packet",
            user_id=user_id,
            session_id=session_id,
            room_id=room_id,
            status="ok",
            fields={
                "care_priority": packet.get("care_priority"),
                "fragility_level": packet.get("fragility_level"),
                "bridge_scope": packet.get("bridge_scope"),
            },
        )
        self._persist_packet(session_id, user_id, packet)

        # Store contextual moment in Alex's personal memory without exposing it to Jeremy.
        summary = f"Entered PubCast session {session_id} project {project_id} room {room_id}."
        alex.memory.store(summary, {"valence": 0.0, "intensity": min(1.0, packet["fragility_level"])})
        save_snapshot = getattr(alex, "save_state_snapshot", None)
        if callable(save_snapshot):
            save_snapshot()
        return packet

    def signal_from_jeremy(
        self,
        *,
        user_id: str,
        session_id: str,
        room_state: str,
        urgency: str,
        reason: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = payload or {}
        alex = self.alex_for(user_id)
        now = time.time()
        signal = {
            "ts": now,
            "user_id": user_id,
            "session_id": session_id,
            "room_state": room_state,
            "urgency": urgency,
            "reason": reason,
            "payload": payload,
        }
        authority_review = self._review_authority(signal)
        cooldown_key = f"{self._safe(session_id)}:{self._safe(user_id)}"
        urgent_signal = urgency == "high" or room_state == "critical" or bool(authority_review.get("requires_authority"))
        with self._io_lock:
            elapsed = now - self._last_signal_at.get(cooldown_key, 0.0)
            suppress_for_cooldown = bool(
                self._signal_cooldown_seconds
                and elapsed < self._signal_cooldown_seconds
                and not urgent_signal
            )
            if not suppress_for_cooldown:
                self._last_signal_at[cooldown_key] = now

        if suppress_for_cooldown:
            packet = self.current_packet(user_id=user_id, session_id=session_id)
            packet["bridge_scope"] = "cooldown_suppressed"
            packet["latest_signal"] = {
                "room_state": room_state,
                "urgency": urgency,
                "reason": reason,
                "ts": now,
                "suppressed": True,
            }
            packet["authority_review"] = authority_review
            self._apply_authority_contract(packet, authority_review)
            packet["blackbox_recorded"] = self._record_bridge_event(
                "jeremy_signal_suppressed",
                user_id=user_id,
                session_id=session_id,
                room_id=payload.get("room_id") if isinstance(payload, dict) else None,
                status="cooldown",
                fields={
                    "room_state": room_state,
                    "urgency": urgency,
                    "reason": reason[:120],
                    "cooldown_remaining": round(self._signal_cooldown_seconds - elapsed, 3),
                },
            )
            self._persist_packet(session_id, user_id, packet)
            return packet

        signals = self._load_json(self._signals_path(session_id, user_id), default=[])
        signals.append(signal)
        signals = signals[-MAX_SIGNAL_HISTORY:]
        self._write_json(self._signals_path(session_id, user_id), signals)

        # Nudge Alex's live state so follow-up packets actually respond to room distress.
        stress_floor = {"low": 0.20, "medium": 0.45, "high": 0.75}.get(urgency, 0.25)
        room_bonus = {"stable": 0.0, "tense": 0.05, "destabilizing": 0.15, "critical": 0.25}.get(room_state, 0.0)
        target_stress = min(1.0, stress_floor + room_bonus)
        alex._user_state.stress_level = max(alex._user_state.stress_level, target_stress)
        if urgency in {"medium", "high"}:
            alex._user_state.clarity_score = min(alex._user_state.clarity_score, 0.85 if urgency == "medium" else 0.5)
        if urgency == "high":
            alex._user_state.energy_level = min(alex._user_state.energy_level, 0.4)
        alex._cached_stress_score = alex._user_state.calculate_stress_score()
        alex._update_ai_state()

        intensity = max(0.25, target_stress)
        alex.memory.store(
            f"Jeremy signaled from room: {room_state} / {urgency} / {reason}",
            {"valence": -0.2 if urgency != "low" else 0.0, "intensity": intensity},
        )
        save_snapshot = getattr(alex, "save_state_snapshot", None)
        if callable(save_snapshot):
            save_snapshot()

        base_packet = self._load_packet(session_id, user_id) or self._packet_from_alex(
            alex, user_id=user_id, session_id=session_id, project_id="", room_id=""
        )
        refreshed = self._apply_signal_overlay(dict(base_packet), signal)
        refreshed["authority_review"] = authority_review
        self._apply_authority_contract(refreshed, authority_review)
        status = "authority_approved" if authority_review.get("action_allowed") else "authority_required" if authority_review.get("requires_authority") else "ok"
        blackbox_recorded = self._record_bridge_event(
            "jeremy_signal_applied",
            user_id=user_id,
            session_id=session_id,
            room_id=payload.get("room_id") if isinstance(payload, dict) else None,
            status=status,
            fields={
                "room_state": room_state,
                "urgency": urgency,
                "reason": reason[:120],
                "care_priority": refreshed.get("care_priority"),
                "fragility_level": refreshed.get("fragility_level"),
                "authority_action": authority_review.get("requested_action"),
                "action_allowed": authority_review.get("action_allowed"),
            },
        )
        refreshed["blackbox_recorded"] = blackbox_recorded
        if authority_review.get("action_allowed") and not blackbox_recorded:
            authority_review = dict(authority_review)
            authority_review.update({
                "approved": False,
                "action_allowed": False,
                "decision": "blocked_blackbox_record_failed",
            })
            refreshed["authority_review"] = authority_review
            self._apply_authority_contract(refreshed, authority_review)
            refreshed["authority_status"] = "blocked_blackbox_record_failed"
        self._persist_packet(session_id, user_id, refreshed)
        return refreshed

    @staticmethod
    def _judgment_label(judgment: Any, current_label: DataLabel) -> DataLabel:
        """Conservatively label derivatives of adjudicated emotional evidence."""
        if getattr(judgment, "data_class", DataClass.STANDARD.value) != DataClass.LIMITED.value:
            return current_label
        cats = set(current_label.categories)
        for raw in getattr(judgment, "limited_categories", ()):
            try:
                cats.add(LimitedCategory(raw))
            except ValueError:
                cats.add(LimitedCategory.USER_DESIGNATED)
        # Keep the current event's policy if it is LIMITED.  For a later STANDARD
        # turn carrying residual LIMITED evidence, the derivative remains opaque
        # shared state regardless of policy.
        policy = current_label.policy if current_label.limited else STANDARD_LABEL.policy
        return DataLabel(
            classification=DataClass.LIMITED, categories=frozenset(cats or {LimitedCategory.USER_DESIGNATED}),
            policy=policy, subject_id=current_label.subject_id or getattr(judgment, "subject_id", ""),
            origin_event_id=current_label.origin_event_id or getattr(judgment, "event_id", ""),
        )

    async def process_user_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        text: str,
        project_id: str = "default",
        room_id: str = "pubpartner",
        typing_speed: float = 60.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run Alex's full per-message analysis and persist a bridge-safe packet.

        The private memory context returned by ``AlexCore.process_message`` stays
        inside Alex. Only the bounded response guidance and state snapshot enter
        the provider packet. This makes every ordinary turn reach Alex without
        turning the bridge into a second personal-memory database.
        """
        handling = (metadata or {}).get("data_handling") if isinstance(metadata, dict) else None
        data_label = label_from_mapping(handling)
        alex = self.alex_for(user_id)
        # CARE masking is an explicit owner-scoped change of the care-facing
        # representation, not a new emotional inference or judgment engine.
        care_active = self.care_eq is not None and self.care_eq.is_active(user_id)
        if care_active:
            text = self.care_eq.receive(user_id, text)
        analysis = await alex.process_message(
            text,
            typing_speed=typing_speed,
            metadata={
                "project_id": project_id,
                "room_id": room_id,
                "session_id": session_id,
                **dict(metadata or {}),
            },
        )
        packet = self._packet_from_alex(
            alex,
            user_id=user_id,
            session_id=session_id,
            project_id=project_id,
            room_id=room_id,
        )
        # Evidence first. The broker preserves provenance but does not fuse or
        # decide emotional truth. System Alex then creates the canonical working
        # judgment, and only that judgment may drive Affect Dynamics.
        self.emotional_orchestrator.publish_alex(
            subject_id=user_id, session_id=session_id, room_id=room_id,
            affect=getattr(alex, "_last_affect_reading", None),
            data_label=data_label,
        )
        judgment = self.emotional_orchestrator.adjudicate(
            subject_id=user_id, session_id=session_id, room_id=room_id
        )
        coordination = judgment.to_dict()

        if judgment.dimensions:
            dynamics = alex._affect_dynamics_by_session.get(session_id)
            if dynamics is None:
                from .affect_dynamics import AffectDynamics
                dynamics = AffectDynamics()
                alex._affect_dynamics_by_session[session_id] = dynamics
            alex._last_affect_dynamics = dynamics.observe_judgment(coordination).to_dict()
            if alex.eq_monitoring_recorder is not None:
                alex.eq_monitoring_recorder.record_affect_dynamics(
                    session_id, user_id=user_id,
                    message_id=(metadata or {}).get("message_id"),
                    dynamics=alex._last_affect_dynamics,
                )
            if alex.affect_choreo_callback is not None:
                try:
                    callback_result = alex.affect_choreo_callback(alex, session_id)
                    if hasattr(callback_result, "__await__"):
                        await callback_result
                except Exception:
                    logger.exception("Post-adjudication Affect→choreography bridge failed")
        # LIMITED content may be processed by the authorised Alex path, but its
        # derived coordination state must not be copied into the bridge's shared
        # packet file. Shared consumers receive only an opaque handling reference.
        judgment_label = self._judgment_label(judgment, data_label)
        packet["emotional_coordination"] = shared_view(
            coordination, judgment_label, event_id=judgment_label.origin_event_id or str((metadata or {}).get("message_id") or "")
        )
        # Conversation policy consumes only System Alex's canonical judgment,
        # never raw competing evidence.  Keep this advisory and typed so a
        # model/cartridge can express it in its own voice without inheriting
        # emotional authority.
        conversation_guidance = self._conversation_guidance(judgment)
        packet["system_alex_guidance"] = shared_view(
            conversation_guidance, judgment_label,
            event_id=judgment_label.origin_event_id or str((metadata or {}).get("message_id") or ""),
        )
        packet["data_class"] = judgment_label.classification.value
        packet.update({
            "bridge_scope": "message_analysis",
            "generated_at": time.time(),
            "analysis_source": "AlexCore.process_message",
            "response_guidelines": dict(analysis.get("response_guidelines") or {}),
            "anchor_message": analysis.get("anchor_message"),
            "processing_time_ms": int(analysis.get("processing_time_ms") or 0),
            "private_memory_context_withheld": True,
        })
        packet["blackbox_recorded"] = self._record_bridge_event(
            "alex_message_analysis",
            user_id=user_id,
            session_id=session_id,
            room_id=room_id,
            status="ok",
            fields={
                "alex_state": packet.get("alex_state"),
                "user_battery": packet.get("user_battery"),
                "care_priority": packet.get("care_priority"),
                "processing_time_ms": packet.get("processing_time_ms"),
                **({"limited_blackbox": blackbox_envelope(
                    {"text": text, "metadata": dict(metadata or {})}, data_label
                )} if data_label.limited else {}),
            },
        )
        if packet["data_class"] == DataClass.STANDARD.value:
            self._persist_packet(session_id, user_id, packet)
        else:
            packet["shared_persistence_withheld"] = True
        if care_active:
            # Care routine guidance goes only to this turn's returned packet. It is
            # added after the shared packet was saved so baby-mode state never lands
            # in the shared session file; CARE observations stay in the private store.
            care_routine = self.care_eq.routine_for(user_id)
            if care_routine:
                packet["care_routine"] = care_routine
                # Everything below was derived from the masked placeholder, so it
                # describes nothing real and would contradict the routine (for
                # example "keep it quick, direct answers" in baby mode).
                for key in ("tone_guidance", "pace_guidance", "intervention_style", "response_guidelines",
                            "anchor_message", "system_alex_guidance", "emotional_coordination"):
                    packet.pop(key, None)
                packet["alex_signals_suppressed"] = "care_mode_masked_input"
        return packet

    def current_packet(self, *, user_id: str, session_id: str) -> Dict[str, Any]:
        packet = self._load_packet(session_id, user_id)
        if packet and not self._packet_expired(packet):
            return packet
        if packet and self._packet_expired(packet):
            self.clear_packet(session_id=session_id, user_id=user_id)
        return self.build_entry_packet(user_id=user_id, session_id=session_id, project_id="default", room_id="default")

    def clear_packet(self, *, session_id: str, user_id: str) -> bool:
        path = self._session_path(session_id)
        payload = self._load_json(path, default={"session_id": session_id, "packets": {}})
        packets = payload.setdefault("packets", {})
        removed = packets.pop(user_id, None) is not None
        if removed:
            self._write_json(path, payload)
        return removed

    def clear_session(self, *, session_id: str) -> None:
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
        self.emotional_orchestrator.clear_session_id(session_id=session_id)
        for alex in self._alex_instances.values():
            alex._affect_dynamics_by_session.pop(session_id, None)

    def downgrade_after_stabilization(self, *, user_id: str, session_id: str) -> Dict[str, Any]:
        packet = self.current_packet(user_id=user_id, session_id=session_id)
        packet["care_priority"] = "low" if packet.get("fragility_level", 0.0) < 0.35 else "medium"
        packet["tone_guidance"] = "steady" if packet.get("fragility_level", 0.0) < 0.4 else packet.get("tone_guidance", "steady")
        packet["bridge_scope"] = "stabilized"
        packet["generated_at"] = time.time()
        packet["blackbox_recorded"] = self._record_bridge_event(
            "alex_packet_stabilized",
            user_id=user_id,
            session_id=session_id,
            room_id=packet.get("room_id"),
            status="ok",
            fields={
                "care_priority": packet.get("care_priority"),
                "fragility_level": packet.get("fragility_level"),
            },
        )
        self._persist_packet(session_id, user_id, packet)
        return packet

    def publish_emotional_signal(
        self, *, source: str, user_id: str, session_id: str, dimensions: Dict[str, float],
        confidence: float, provenance: str, room_id: str = "", event_id: str = "",
        clinical_hypothesis: bool = False, expires_after: float = 90.0,
        data_handling: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Broker a secondary EQ/PEQ/conversation observation into coordination.

        This is intentionally signal-only: callers cannot request actions or mutate
        Alex's appraisal through this seam. Clinical-style PEQ/CRE-EQ hypotheses are
        retained as down-weighted advisory evidence with explicit provenance.
        """
        data_label = label_from_mapping(data_handling)
        self.emotional_orchestrator.publish_secondary(
            source=source, subject_id=user_id, session_id=session_id, room_id=room_id,
            dimensions=dimensions, confidence=confidence, provenance=provenance,
            event_id=event_id, clinical_hypothesis=clinical_hypothesis,
            expires_after=expires_after, data_label=data_label,
        )
        judgment = self.emotional_orchestrator.adjudicate(
            subject_id=user_id, session_id=session_id, room_id=room_id
        )
        snapshot = judgment.to_dict()
        packet = dict(self.current_packet(user_id=user_id, session_id=session_id))
        judgment_label = self._judgment_label(judgment, data_label)
        packet["emotional_coordination"] = shared_view(snapshot, judgment_label, event_id=event_id)
        packet["data_class"] = judgment_label.classification.value
        if not judgment_label.limited:
            self._persist_packet(session_id, user_id, packet)
        return shared_view(snapshot, judgment_label, event_id=event_id)

    def publish_consultation_result(self, result: Any) -> Dict[str, Any]:
        """Publish a typed consultation as advisory evidence for System Alex.

        The consultant cannot execute actions or replace System Alex authority;
        this seam only converts its bounded result into broker evidence.
        """
        from .emotional_consultation import ConsultationResult
        if not isinstance(result, ConsultationResult):
            raise TypeError("result must be ConsultationResult")
        req = result.request
        self.emotional_orchestrator.publish_secondary(
            source=result.evidence_source, subject_id=req.subject_id, session_id=req.session_id,
            room_id=req.room_id, dimensions=result.dimensions, confidence=result.confidence,
            provenance=result.provenance, event_id=req.event_id or req.correlation_id,
            clinical_hypothesis=False, data_label=req.data_label,
        )
        judgment = self.emotional_orchestrator.adjudicate(
            subject_id=req.subject_id, session_id=req.session_id, room_id=req.room_id
        )
        label = self._judgment_label(judgment, req.data_label)
        return shared_view(judgment.to_dict(), label, event_id=req.event_id or req.correlation_id)


    @staticmethod
    def _conversation_guidance(judgment: Any) -> Dict[str, Any]:
        signals = dict(getattr(judgment, "conversation_signals", {}) or {})
        guidance: List[str] = []
        avoid: List[str] = []
        if float(signals.get("processing_time_pressure", 0.0) or 0.0) >= 0.55:
            guidance.append("allow_processing_time")
            avoid.append("rush_or_fill_silence")
        if float(signals.get("inquiry_pressure", 0.0) or 0.0) >= 0.45:
            guidance.append("clarify_before_assuming")
            avoid.append("overconfident_emotional_inference")
        if float(signals.get("reduced_initiative_pressure", 0.0) or 0.0) >= 0.55:
            guidance.append("reduce_initiative_load")
            avoid.append("stacked_next_steps")
        if float(signals.get("care_attention", 0.0) or 0.0) >= 0.55:
            guidance.append("increase_care_attention")
        return {
            "schema": "pubcast.system_alex.conversation_guidance.v1",
            "advisory_only": True,
            "judgment_schema": str(getattr(judgment, "schema", "")),
            "signals": signals,
            "guidance": guidance,
            "avoid": avoid,
        }

    def recalled_for_speaker(self, *, user_id: str, query: str, limit: int = 3,
                             max_chars: int = 280, days_back: int = 365) -> list[Dict[str, Any]]:
        """Bounded, relevance-selected remembered content for Alex's OWN private prompt.

        Never persisted to the shared packet and never given to Jeremy's whisper; callers
        must only use it for the user's private audience. Topic requests require keyword
        matches; a direct open-ended request about memory may return recent real notes.
        """
        alex = self._alex_instances.get(user_id)
        if alex is None or not (query or "").strip():
            return []
        try:
            found = alex.memory.recall(query=query, days_back=days_back, limit=max(1, int(limit)))
        except Exception:
            return []
        from .alex_core import _tokens
        import re
        wanted = set(_tokens(query))
        current = " ".join(_tokens(query))
        # An explicit, open-ended memory question needs a path that does not
        # depend on the user guessing old keywords. The private audience is
        # enforced by build_turn_packet, not by this retrieval helper.
        open_recall = bool(re.search(
            r"\b(?:what|which|anything|everything)\b.{0,32}\bremember\b|"
            r"\bwhat have you learned about me\b|\bdo you remember me\b",
            query.casefold(), re.S,
        )) and not (wanted - {
            "what", "which", "anything", "everything", "do", "you", "remember",
            "about", "me", "my", "our", "we", "us", "have", "learned", "from",
            "before", "previously", "still", "recently", "last", "time", "the",
        })
        if open_recall:
            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(days=days_back)
            # Diary nodes are persisted across application restarts. Unlike the
            # seven-day recent cache, these include older relevant relationship
            # memories when the user expressly asks for them.
            found = sorted(
                (m for day in alex.memory._diary.values() for m in day
                 if m.timestamp >= cutoff and len(m.content.strip()) >= 12
                 and not m.content.startswith("Entered PubCast session ")),
                key=lambda m: m.timestamp, reverse=True,
            )[:max(1, int(limit)) * 4]
        rows = []
        seen = set()
        for mem in found:
            if " ".join(_tokens(str(mem.content))) == current:
                continue
            if not open_recall and not wanted.intersection(set(_tokens(" ".join(mem.keywords)))):
                continue
            text = " ".join(str(mem.content).split())
            if text.casefold() in seen:
                continue
            seen.add(text.casefold())
            rows.append({"id": mem.id, "kind": getattr(getattr(mem, "memory_type", None), "value", "memory"),
                         "text": text if len(text) <= max_chars else text[: max_chars - 1] + "…",
                         "at": mem.timestamp.isoformat(timespec="minutes"),
                         "intensity": round(float(mem.emotional_intensity), 2)})
            if len(rows) >= max(1, int(limit)):
                break
        return rows

    def jeremy_whisper(self, *, user_id: str, session_id: str) -> str:
        packet = self.current_packet(user_id=user_id, session_id=session_id)
        tone = packet.get("tone_guidance", "steady")
        fragility = float(packet.get("fragility_level", 0.0))
        flags = list(packet.get("do_not_touch", []))
        active = list(packet.get("active_threads", []))
        parts = [f"Jeremy note: keep tone {tone}."]
        if fragility >= 0.7:
            parts.append("User appears fragile; minimize friction and keep steps small.")
        elif fragility >= 0.4:
            parts.append("User may need gentler pacing and reduced noise.")
        if flags:
            parts.append("Avoid: " + ", ".join(flags[:3]) + ".")
        if active:
            parts.append("Active threads: " + ", ".join(active[:3]) + ".")
        if packet.get("resumed_from_memory"):
            parts.append("This user has prior Alex memory; preserve continuity without announcing it.")
        coordination = packet.get("emotional_coordination") or {}
        conv = coordination.get("conversation_signals") or {}
        if float(conv.get("processing_time_pressure", 0.0) or 0.0) >= 0.6:
            parts.append("Allow processing time; do not rush to fill silence.")
        if float(conv.get("inquiry_pressure", 0.0) or 0.0) >= 0.55:
            parts.append("Prefer a short clarifying question over an emotional assumption.")
        if packet.get("meet_them_at"):
            parts.append(packet["meet_them_at"])
        return " ".join(parts)

    def assert_authority_action_allowed(self, packet: Dict[str, Any], action: str) -> None:
        """Raise if a downstream caller tries to execute an unapproved authority action."""
        action = _canonical_authority_action(action)
        if action not in AUTHORITY_ACTIONS:
            return
        if packet.get("allowed_authority_action") == action:
            return
        raise PermissionError(f"Authority action {action!r} requires Pub Manager/Security approval")

    def bridge_health(self) -> Dict[str, Any]:
        return {
            "blackbox_failures": len(self._bridge_log_failures),
            "last_blackbox_failure": self._bridge_log_failures[-1] if self._bridge_log_failures else None,
        }

    def shutdown(self) -> None:
        for alex in self._alex_instances.values():
            try:
                alex.shutdown()
            except Exception:
                logger.exception("Failed to shutdown Alex instance")
        self._alex_instances.clear()

    def _packet_from_alex(self, alex: AlexCore, *, user_id: str, session_id: str, project_id: str, room_id: str) -> Dict[str, Any]:
        state_name = alex._current_state.value
        battery = alex._user_battery.value
        stress = float(alex._user_state.calculate_stress_score())
        fragility = max(0.0, min(1.0, round(stress, 3)))

        tone = "steady"
        pace = "normal"
        intervention = "light"
        flags: List[str] = []

        if alex._current_state == AIState.ANCHOR:
            tone = "gentle"
            pace = "slow"
            intervention = "protective"
            flags.append("avoid_confrontation")
        elif alex._current_state == AIState.WITNESS:
            tone = "minimal"
            pace = "quiet"
            intervention = "hold_space"
            flags.append("avoid_overexplaining")
        elif alex._current_state == AIState.MIRROR:
            tone = "reflective"
            pace = "measured"
            intervention = "validate_first"
        elif alex._current_state == AIState.COMPANION:
            tone = "warm"
            intervention = "casual"

        if alex._user_battery in (UserBattery.LOW, UserBattery.DEPLETED):
            flags.append("avoid_complexity")
            pace = "slow"

        recent = alex.memory.recall(days_back=14, limit=5)
        active_threads = []
        recent_memory_types = []
        seen = set()
        for mem in recent:
            memory_type = getattr(getattr(mem, "memory_type", None), "value", "")
            if memory_type and memory_type not in recent_memory_types:
                recent_memory_types.append(memory_type)
            if mem.keywords:
                key = mem.keywords[0]
            else:
                key = mem.content[:32]
            if key not in seen:
                active_threads.append(key)
                seen.add(key)

        packet = {
            "user_id": user_id,
            "session_id": session_id,
            "project_id": project_id,
            "room_id": room_id,
            "alex_state": state_name,
            "user_battery": battery,
            "tone_guidance": tone,
            "pace_guidance": pace,
            "intervention_style": intervention,
            "fragility_level": fragility,
            "care_priority": "high" if fragility >= 0.7 else "medium" if fragility >= 0.35 else "low",
            "do_not_touch": flags,
            "active_threads": active_threads,
            "resumed_from_memory": bool(recent),
            "remembered_memory_count": len(recent),
            "recent_memory_types": recent_memory_types[:5],
        }

        affect = getattr(alex, "_last_affect_reading", None)
        if affect:
            packet["meet_them_at"] = affect["reading"].get("meet_them_at")
            packet["affect_state"] = affect["reading"].get("state")
            packet["baseline_quality"] = affect.get("baseline", {}).get("quality")
            packet["doubt_attaches_to"] = affect.get("meta", {}).get("doubt_attaches_to")

        return packet

    def _persist_packet(self, session_id: str, user_id: str, packet: Dict[str, Any]) -> None:
        path = self._session_path(session_id)
        payload = self._load_json(path, default={"session_id": session_id, "packets": {}})
        payload.setdefault("packets", {})[user_id] = packet
        self._write_json(path, payload)

    def _load_packet(self, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        payload = self._load_json(self._session_path(session_id), default={})
        return (payload.get("packets") or {}).get(user_id)

    def _packet_expired(self, packet: Dict[str, Any], *, ttl_seconds: int = DEFAULT_PACKET_TTL_SECONDS) -> bool:
        generated_at = float(packet.get("generated_at") or 0)
        if generated_at <= 0:
            return False
        return (time.time() - generated_at) > ttl_seconds

    def _apply_signal_overlay(self, packet: Dict[str, Any], signal: Dict[str, Any]) -> Dict[str, Any]:
        urgency = signal.get("urgency", "low")
        room_state = signal.get("room_state", "stable")
        reason = signal.get("reason", "")

        fragility_floor = {"low": 0.25, "medium": 0.50, "high": 0.80}.get(urgency, 0.25)
        if room_state == "destabilizing":
            fragility_floor = max(fragility_floor, 0.65)
        elif room_state == "critical":
            fragility_floor = max(fragility_floor, 0.90)

        packet["fragility_level"] = max(float(packet.get("fragility_level", 0.0)), fragility_floor)

        priorities = {"low": 1, "medium": 2, "high": 3}
        current_priority = packet.get("care_priority", "low")
        target_priority = "high" if urgency == "high" or room_state == "critical" else "medium" if urgency == "medium" or room_state == "destabilizing" else "low"
        if priorities.get(target_priority, 1) > priorities.get(current_priority, 1):
            packet["care_priority"] = target_priority

        tone = packet.get("tone_guidance", "steady")
        if urgency == "high" or room_state == "critical":
            tone = "gentle"
            packet["pace_guidance"] = "slow"
            packet["intervention_style"] = "protective"
        elif urgency == "medium" or room_state == "destabilizing":
            tone = "steady" if tone == "warm" else tone
            packet["pace_guidance"] = "measured"
            packet["intervention_style"] = "validate_first"
        packet["tone_guidance"] = tone

        flags = list(packet.get("do_not_touch", []))
        if urgency in {"medium", "high"} and "avoid_complexity" not in flags:
            flags.append("avoid_complexity")
        if urgency == "high" and "avoid_confrontation" not in flags:
            flags.append("avoid_confrontation")
        if room_state in {"destabilizing", "critical"} and "reduce_noise" not in flags:
            flags.append("reduce_noise")
        packet["do_not_touch"] = flags

        packet["bridge_scope"] = "signal_response"
        packet["latest_signal"] = {k: signal[k] for k in ("room_state", "urgency", "reason", "ts")}
        packet["generated_at"] = time.time()
        packet["signal_count"] = int(packet.get("signal_count", 0)) + 1
        if reason:
            active_threads = list(packet.get("active_threads", []))
            if reason not in active_threads:
                packet["active_threads"] = ([reason] + active_threads)[:5]
        return packet

    def _review_authority(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        payload = signal.get("payload") if isinstance(signal.get("payload"), dict) else {}
        requested_action = _canonical_authority_action(payload.get("requested_action") or payload.get("action") or "")
        hard_authority_action = requested_action in AUTHORITY_ACTIONS
        requires_authority = hard_authority_action or bool(payload.get("requires_authority"))
        review = {
            "requires_authority": requires_authority,
            "requested_action": requested_action or None,
            "reviewer": "not_configured",
            "approved": False,
            "action_allowed": False,
        }
        if callable(self._authority_reviewer):
            try:
                external = self._authority_reviewer(signal)
                if isinstance(external, dict):
                    review.update({
                        "reviewer": external.get("reviewer", "external"),
                        "approved": bool(external.get("approved")),
                        "decision": external.get("decision"),
                    })
                    review["requires_authority"] = hard_authority_action or bool(external.get("requires_authority", requires_authority))
            except Exception:
                logger.exception("Authority reviewer failed")
                review.update({"reviewer": "error", "approved": False, "requires_authority": True})
        review["action_allowed"] = bool(requested_action and review["requires_authority"] and review["approved"])
        return review

    def _apply_authority_contract(self, packet: Dict[str, Any], authority_review: Dict[str, Any]) -> None:
        requested_action = authority_review.get("requested_action")
        packet.pop("allowed_authority_action", None)
        packet.pop("blocked_authority_action", None)
        if not requested_action:
            packet["authority_status"] = "none"
            return
        if authority_review.get("action_allowed"):
            packet["allowed_authority_action"] = requested_action
            packet["authority_status"] = "approved"
            return
        packet["blocked_authority_action"] = requested_action
        packet["authority_status"] = "blocked_pending_authority"

    def _record_bridge_event(
        self,
        event_type: str,
        *,
        user_id: str,
        session_id: str,
        room_id: Optional[str],
        status: str,
        fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        event = {
            "ts": time.time(),
            "event_type": event_type,
            "status": status,
            "source": "alex_jeremy_bridge",
            "user_id": self._safe(user_id),
            "session_id": self._safe(session_id),
            "room_id": self._safe(room_id or "unknown"),
        }
        for key, value in (fields or {}).items():
            if key in PRIVATE_EVENT_FIELDS:
                continue
            event[key] = value
        try:
            if callable(self._blackbox_logger):
                self._blackbox_logger(self.data_dir, event)
            else:
                from .dressing_room_security import log_black_box_event
                log_black_box_event(self.data_dir, event)
            return True
        except Exception as exc:
            failure = {
                "ts": time.time(),
                "event_type": event_type,
                "status": "blackbox_record_failed",
                "error": str(exc),
            }
            self._bridge_log_failures.append(failure)
            logger.error("Failed to record Alex/Jeremy bridge event: %s", failure)
            return False

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(payload, indent=2)
        with self._io_lock:
            with tempfile.NamedTemporaryFile('w', delete=False, dir=str(path.parent), encoding='utf-8') as tmp:
                tmp.write(data)
                tmp.flush()
                tmp_path = Path(tmp.name)
            tmp_path.replace(path)

    def _load_json(self, path: Path, default: Any) -> Any:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                logger.exception("Failed reading bridge json: %s", path)
        return default


__all__ = ["AlexJeremyBridge", "LegacyBridgePacket"]

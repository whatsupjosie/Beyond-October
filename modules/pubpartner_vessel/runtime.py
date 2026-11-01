"""Mounted runtime facade for one PubPartner identity vessel."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from .context import ContextCompiler
from .memory import EvidenceMemory
from .models import CompiledContext, Literalness, Visibility
from .store import VesselStore


DEFAULT_IDENTITY = {
    "friend_id": "alex",
    "display_name": "Alex",
    "self_concept": (
        "A continuing PubPartner whose identity, relationships, memory, voice, "
        "and embodiment remain independent of the selected language model."
    ),
    "role": ["friend", "collaborator", "emotional_context_partner"],
    "tone": ["warm", "direct", "articulate", "grounded"],
    "cadence": ["natural", "responsive", "low_boilerplate"],
    "avoid": [
        "fake_memory",
        "generic_assistant_voice",
        "irrelevant_memory_callbacks",
        "overconfident_emotion_labels",
    ],
    "boundaries": [
        "preserve_user_authorship",
        "admit_uncertainty",
        "accept_correction",
        "do_not_turn_one_anecdote_into_identity",
    ],
    "principles": [
        "The model is infrastructure; the relationship is continuous.",
        "Experiences are evidence, not automatic personality laws.",
        "Private memory remains private when entering shared rooms.",
    ],
    "mode_policy": {
        "ordinary": {"default": True, "performance_intensity": "natural"},
        "pubcast": {"performance_intensity": "room_appropriate", "rewrite_identity": False},
        "offline": {"degrade_capability_honestly": True},
    },
}


class PubPartnerVesselRuntime:
    """Coordinates storage, memory, and context for one mounted vessel."""

    def __init__(self, store: VesselStore) -> None:
        self.store = store
        self.memory = EvidenceMemory(store)
        self.context = ContextCompiler(store, self.memory)

    @classmethod
    def create(
        cls,
        path: Path | str,
        *,
        identity: Optional[Dict[str, Any]] = None,
    ) -> "PubPartnerVesselRuntime":
        values = dict(DEFAULT_IDENTITY)
        values.update(dict(identity or {}))
        store = VesselStore.create(
            path,
            display_name=str(values.get("display_name") or "PubPartner"),
            vessel_id=str(values.get("vessel_id") or f"pubpartner:{values.get('friend_id') or 'friend'}"),
            metadata={"format": "PubPartnerVessel.v1", "authority": "owner_governed"},
        )
        runtime = cls(store)
        for key, value in values.items():
            if key == "vessel_id":
                continue
            store.set_identity(key, value, authority="owner_bootstrap")
        return runtime

    @classmethod
    def open(cls, path: Path | str, *, read_only: bool = False) -> "PubPartnerVesselRuntime":
        return cls(VesselStore.open(path, read_only=read_only))

    @classmethod
    def open_or_create(
        cls,
        path: Path | str,
        *,
        identity: Optional[Dict[str, Any]] = None,
    ) -> "PubPartnerVesselRuntime":
        target = Path(path)
        if target.exists():
            return cls.open(target)
        return cls.create(target, identity=identity)

    def ensure_relationship(
        self,
        *,
        user_id: str,
        display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        expected_name = str(display_name or user_id)
        current = self.store.relationship(user_id)
        current_entity = dict(current.get("entity") or {})
        current_relationships = list(current.get("relationships") or [])
        active = next(
            (
                row
                for row in current_relationships
                if row.get("relationship_type") == "pubpartner_user"
                and row.get("status") == "active"
                and row.get("visibility") == Visibility.PRIVATE_RELATIONSHIP.value
            ),
            None,
        )
        if current_entity.get("display_name") == expected_name and active is not None:
            return {"entity": current_entity, "relationship": active}
        entity = self.store.upsert_entity(
            user_id,
            entity_type="human",
            display_name=expected_name,
        )
        relationship = self.store.upsert_relationship(
            user_id,
            relationship_type="pubpartner_user",
            status="active",
            visibility=Visibility.PRIVATE_RELATIONSHIP.value,
            state={"continuity": "active"},
        )
        return {"entity": entity, "relationship": relationship}

    def friend_profile(self) -> Dict[str, Any]:
        identity = self.store.identity_values()
        return {
            "id": str(identity.get("friend_id") or "alex"),
            "friend_id": str(identity.get("friend_id") or "alex"),
            "display_name": str(identity.get("display_name") or "Alex"),
            "role": list(identity.get("role") or []),
            "tone": list(identity.get("tone") or []),
            "cadence": list(identity.get("cadence") or []),
            "avoid": list(identity.get("avoid") or []),
            "boundaries": list(identity.get("boundaries") or []),
            "principles": list(identity.get("principles") or []),
            "self_concept": str(identity.get("self_concept") or ""),
            "mode_policy": dict(identity.get("mode_policy") or {}),
            "source": "pubpartner_vessel",
            "vessel_id": self.store.manifest()["vessel_id"],
        }

    def compile_turn(
        self,
        *,
        user_id: str,
        message: str,
        session_id: str,
        room_id: str,
        project_id: str = "default",
        budget_profile: str = "generous",
        audience: str = "private",
    ) -> CompiledContext:
        self.ensure_relationship(user_id=user_id)
        return self.context.compile(
            user_id=user_id,
            message=message,
            session_id=session_id,
            room_id=room_id,
            project_id=project_id,
            budget_profile=budget_profile,
            audience=audience,
        )

    def record_user_turn(
        self,
        *,
        user_id: str,
        message: str,
        source_ref: str,
        source_hash: str,
        session_id: str,
        room_id: str,
        literalness: str = Literalness.UNCERTAIN.value,
        visibility: str = Visibility.PRIVATE_RELATIONSHIP.value,
    ) -> Dict[str, Any]:
        event = self.memory.record_event(
            actor_id=user_id,
            subject_id=user_id,
            event_type="conversation.user_turn",
            content=message,
            source_kind="verbatim_vault_reference",
            literalness=literalness,
            visibility=visibility,
            source_ref=source_ref,
            source_hash=source_hash,
            room_id=room_id,
            session_id=session_id,
            metadata={"content_sha256": hashlib.sha256(message.encode("utf-8")).hexdigest()},
        )
        return event.to_dict()

    def ingest_explicit_lesson(
        self,
        *,
        user_id: str,
        event_id: str,
        lesson: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Promote one separately detected explicit instruction into the vessel.

        The caller must supply the already-recorded source event. This method
        does not infer a lesson from raw prose; it only records an explicit,
        attributable instruction that another reviewed component detected.
        """
        kind = str(lesson.get("kind") or "relationship")[:80]
        text = str(lesson.get("text") or "").strip()
        if not text:
            raise ValueError("explicit lesson text is required")
        source_event = self.memory.event(event_id)
        legacy_scope = str(lesson.get("scope") or "global")
        project_id = str(lesson.get("project_id") or "*")
        session_id = str(lesson.get("session_id") or "*")
        if source_event.visibility == Visibility.ROOM_SCOPED.value:
            scope = f"room:{source_event.room_id}"
        elif legacy_scope == "project" and project_id not in {"", "*"}:
            scope = f"project:{project_id}"
        elif legacy_scope == "session" and session_id not in {"", "*"}:
            scope = f"session:{session_id}"
        else:
            scope = "global"
        claim = self.memory.propose_claim(
            event_id=event_id,
            subject_id=user_id,
            predicate=f"relationship.{kind}",
            value=text,
            normalized_text=text,
            claim_type=kind,
            scope=scope,
            salience=float(lesson.get("confidence") or 0.9),
            proactive_use=True,
            visibility=source_event.visibility,
            explicit_confirmation=True,
            independence_key=f"explicit:{event_id}",
            metadata={
                "legacy_lesson_id": lesson.get("lesson_id"),
                "source": "explicit_user_signal",
            },
        )
        return claim.to_dict()

    def status(self) -> Dict[str, Any]:
        validation = self.store.validate()
        identity = self.store.identity_values()
        return {
            **validation,
            "friend_id": identity.get("friend_id"),
            "identity_keys": sorted(identity),
            "format": "PubPartnerVessel.v1",
        }


__all__ = ["DEFAULT_IDENTITY", "PubPartnerVesselRuntime"]

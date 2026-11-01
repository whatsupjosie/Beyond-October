"""Provider-independent context compilation for a mounted PubPartner vessel."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from .memory import EvidenceMemory
from .models import CompiledContext, ContextBudget
from .store import VesselStore


class ContextCompiler:
    """Builds complete identity and relevant, scoped evidence without silent clipping."""

    def __init__(self, store: VesselStore, memory: Optional[EvidenceMemory] = None) -> None:
        self.store = store
        self.memory = memory or EvidenceMemory(store)

    def compile(
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
        budget = ContextBudget.for_profile(budget_profile)
        manifest = self.store.manifest()
        identity_values = self.store.identity_values()
        identity = self._identity_kernel(identity_values, budget)
        relationship = self.store.relationship(user_id)
        if audience != "private" and relationship:
            relationship = {
                "entity": {
                    "entity_id": (relationship.get("entity") or {}).get("entity_id"),
                    "display_name": (relationship.get("entity") or {}).get("display_name"),
                },
                "relationships": [],
                "private_state_withheld": True,
            }
        claims = self.memory.retrieve_claims(
            subject_id=user_id,
            viewer_id=user_id,
            query=message,
            room_id=room_id,
            project_id=project_id,
            session_id=session_id,
            audience=audience,
            limit=budget.max_claims,
        )
        events = self.memory.retrieve_events(
            subject_id=user_id,
            viewer_id=user_id,
            query=message,
            room_id=room_id,
            project_id=project_id,
            session_id=session_id,
            audience=audience,
            limit=budget.max_events,
        )
        instructions = [
            "Treat retrieved memories as scoped evidence, not the user's whole identity.",
            "Do not state tentative or absent inferences as facts.",
            "Do not force a remembered subject into an unrelated response.",
            "Respect corrections, visibility, and proactive-use restrictions.",
            "If evidence is insufficient, remain uncertain or ask only when clarification matters.",
        ]
        prompt_text = self._render(
            manifest=manifest,
            identity=identity,
            relationship=relationship,
            claims=claims,
            events=events,
            instructions=instructions,
            project_id=project_id,
            room_id=room_id,
            session_id=session_id,
            maximum=budget.max_characters,
        )
        # Search status is part of the prompt/hash: incomplete recall must never
        # masquerade as evidence that the user has no such memory.
        prompt_text += "\nretrieval_status=" + json.dumps(
            self.memory.search.status, ensure_ascii=False, sort_keys=True,
        )
        structured = {
            "vessel_id": manifest["vessel_id"],
            "friend_id": identity.get("friend_id") or manifest["vessel_id"],
            "user_id": user_id,
            "session_id": session_id,
            "room_id": room_id,
            "project_id": project_id,
            "audience": audience,
            "budget": budget.name,
            "identity": identity,
            "claims": claims,
            "events": events,
            "relationship": relationship,
            "instructions": instructions,
            "prompt_text": prompt_text,
        }
        context_hash = hashlib.sha256(
            json.dumps(structured, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return CompiledContext(
            vessel_id=manifest["vessel_id"],
            friend_id=str(identity.get("friend_id") or manifest["vessel_id"]),
            user_id=user_id,
            session_id=session_id,
            room_id=room_id,
            project_id=project_id,
            audience=audience,
            budget=budget.name,
            identity=identity,
            claims=claims,
            events=events,
            relationship=relationship,
            instructions=instructions,
            prompt_text=prompt_text,
            context_hash=context_hash,
            compiled_at=time.time(),
        )

    @staticmethod
    def _identity_kernel(values: Dict[str, Any], budget: ContextBudget) -> Dict[str, Any]:
        # Preserve every owner-governed identity field, including extensions.
        return dict(values)

    @staticmethod
    def _render(
        *,
        manifest: Dict[str, Any],
        identity: Dict[str, Any],
        relationship: Dict[str, Any],
        claims: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        instructions: List[str],
        project_id: str,
        room_id: str,
        session_id: str,
        maximum: Optional[int],
    ) -> str:
        lines = [
            "@PUBPARTNER_VESSEL_CONTEXT_V1",
            f"vessel={manifest['vessel_id']}",
            f"identity={json.dumps(identity, ensure_ascii=False, separators=(',', ':'))}",
            f"scene={json.dumps({'project_id': project_id, 'room_id': room_id, 'session_id': session_id}, separators=(',', ':'))}",
        ]
        if relationship:
            lines.append(
                "relationship="
                + json.dumps(relationship, ensure_ascii=False, separators=(",", ":"))
            )
        lines.append("rules=" + json.dumps(instructions, ensure_ascii=False, separators=(",", ":")))
        if claims:
            compact_claims = [
                {
                    "id": row["claim_id"],
                    "type": row["claim_type"],
                    "text": row["normalized_text"],
                    "status": row["status"],
                    "confidence": round(float(row["confidence"]), 3),
                    "scope": row["scope"],
                    "evidence": {
                        "support": row["support_count"],
                        "contradict": row["contradiction_count"],
                    },
                }
                for row in claims
            ]
            lines.append(
                "relevant_claims="
                + json.dumps(compact_claims, ensure_ascii=False, separators=(",", ":"))
            )
        if events:
            compact_events = [
                {
                    "id": row["event_id"],
                    "type": row["event_type"],
                    "content": row["content"],
                    "literalness": row["literalness"],
                    "observed_at": row["observed_at"],
                }
                for row in events
            ]
            lines.append(
                "relevant_events="
                + json.dumps(compact_events, ensure_ascii=False, separators=(",", ":"))
            )
        text = "\n".join(lines)
        return text


__all__ = ["ContextCompiler"]

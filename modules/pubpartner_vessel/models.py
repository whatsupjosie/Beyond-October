"""Typed model objects for the PubPartner identity vessel."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Literalness(str, Enum):
    LITERAL = "literal"
    JOKING = "joking"
    SARCASTIC = "sarcastic"
    QUOTED = "quoted"
    FICTIONAL = "fictional"
    HYPOTHETICAL = "hypothetical"
    UNCERTAIN = "uncertain"


class Visibility(str, Enum):
    PRIVATE_OWNER = "private_owner"
    PRIVATE_RELATIONSHIP = "private_relationship"
    ROOM_SCOPED = "room_scoped"
    PUBLIC = "public"


class ClaimStatus(str, Enum):
    TENTATIVE = "tentative"
    CORROBORATED = "corroborated"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class EvidencePolarity(str, Enum):
    SUPPORT = "support"
    CONTRADICT = "contradict"


@dataclass(frozen=True)
class MemoryEvent:
    event_id: str
    observed_at: float
    actor_id: str
    subject_id: str
    event_type: str
    content: str
    source_kind: str
    literalness: str
    visibility: str
    sensitivity: str
    source_ref: str
    source_hash: str
    room_id: str = ""
    session_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryClaim:
    claim_id: str
    subject_id: str
    predicate: str
    value: Any
    normalized_text: str
    claim_type: str
    status: str
    confidence: float
    scope: str
    salience: float
    proactive_use: bool
    visibility: str
    sensitivity: str
    created_at: float
    updated_at: float
    last_supported_at: Optional[float]
    expires_at: Optional[float]
    version: int
    support_count: int = 0
    contradiction_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextBudget:
    name: str
    max_characters: Optional[int]
    max_claims: Optional[int]
    max_events: Optional[int]
    max_identity_items: Optional[int]

    @classmethod
    def for_profile(cls, profile: str) -> "ContextBudget":
        # Legacy profile names remain accepted, but never silently ration Alex.
        # Actual model capacity belongs to the provider boundary.
        return cls("generous", None, 40, 20, None)


@dataclass(frozen=True)
class CompiledContext:
    vessel_id: str
    friend_id: str
    user_id: str
    session_id: str
    room_id: str
    project_id: str
    audience: str
    budget: str
    identity: Dict[str, Any]
    claims: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    relationship: Dict[str, Any]
    instructions: List[str]
    prompt_text: str
    context_hash: str
    compiled_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

"""Typed, bounded consultation contracts for PubCast emotional adjudication.

Consultations are evidence requests, never authority transfers.  They carry a
correlation ID and bounded depth so System Alex, Jeremy and model-backed
participants cannot recursively consult one another forever.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import secrets
import time
from typing import Mapping, Optional

from .limited_exposure import DataLabel, STANDARD_LABEL


class ConsultationKind(str, Enum):
    PARTICIPANT_REACTION = "participant_reaction"
    MEANING_INTERPRETATION = "meaning_interpretation"
    CONTEXT_CHECK = "context_check"


_SOURCE_BY_KIND = {
    ConsultationKind.PARTICIPANT_REACTION: "participant_self_report",
    ConsultationKind.MEANING_INTERPRETATION: "meaning",
    ConsultationKind.CONTEXT_CHECK: "context",
}


@dataclass(frozen=True)
class ConsultationRequest:
    kind: ConsultationKind
    subject_id: str
    session_id: str
    requester: str
    consultant: str
    question: str
    room_id: str = ""
    event_id: str = ""
    correlation_id: str = ""
    depth: int = 0
    max_depth: int = 2
    data_label: DataLabel = STANDARD_LABEL
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not all((self.subject_id, self.session_id, self.requester, self.consultant, self.question.strip())):
            raise ValueError("consultation requires subject/session/requester/consultant/question")
        if self.depth < 0 or self.max_depth < 0 or self.depth > self.max_depth:
            raise ValueError("consultation depth exceeds bounded recursion limit")
        if self.requester == self.consultant:
            raise ValueError("consultation requester and consultant must differ")
        if not self.correlation_id:
            object.__setattr__(self, "correlation_id", secrets.token_urlsafe(18))

    def child(self, *, requester: str, consultant: str, question: str) -> "ConsultationRequest":
        if self.depth >= self.max_depth:
            raise RecursionError("emotional consultation depth limit reached")
        return ConsultationRequest(
            kind=self.kind, subject_id=self.subject_id, session_id=self.session_id,
            requester=requester, consultant=consultant, question=question,
            room_id=self.room_id, event_id=self.event_id,
            correlation_id=self.correlation_id, depth=self.depth + 1,
            max_depth=self.max_depth, data_label=self.data_label.inherited(),
        )


@dataclass(frozen=True)
class ConsultationResult:
    request: ConsultationRequest
    dimensions: Mapping[str, float]
    confidence: float
    rationale: str = ""

    @property
    def evidence_source(self) -> str:
        return _SOURCE_BY_KIND[self.request.kind]

    @property
    def provenance(self) -> str:
        # Do not put private rationale into shared provenance. The broker will
        # redact LIMITED provenance as an additional boundary.
        return f"consultation:{self.request.kind.value}:{self.request.consultant}:{self.request.correlation_id}"

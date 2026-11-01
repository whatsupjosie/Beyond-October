"""Limited Exposure data handling for PubCast.

LIMITED is a propagation classification, not an importance label. Limited data
may be used only by explicitly authorised consumers/purposes and must not be
copied into broadly consumed context, indexes, shared intermediate files, or
telemetry. BlackBox capture is intentionally outside this propagation policy:
the authoritative event recorder receives the original event plus its label.

Derived data inherits LIMITED unless it has been deliberately declassified by
an authorised policy decision. This module does not provide declassification.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Iterable, Mapping, MutableMapping, Optional
import hashlib
import json


class DataClass(str, Enum):
    STANDARD = "STANDARD"
    LIMITED = "LIMITED"


class LimitedCategory(str, Enum):
    IDENTITY = "IDENTITY"
    CONTACT_LOCATION = "CONTACT_LOCATION"
    HEALTH = "HEALTH"
    FINANCIAL = "FINANCIAL"
    CREDENTIAL = "CREDENTIAL"
    PERSONAL_HISTORY = "PERSONAL_HISTORY"
    EMOTIONAL = "EMOTIONAL"
    RELATIONSHIP = "RELATIONSHIP"
    LEGAL = "LEGAL"
    USER_DESIGNATED = "USER_DESIGNATED"


class ExposurePurpose(str, Enum):
    DIRECT_CONVERSATION = "DIRECT_CONVERSATION"
    EMOTIONAL_ADJUDICATION = "EMOTIONAL_ADJUDICATION"
    CONTEXT_RETRIEVAL = "CONTEXT_RETRIEVAL"
    AI_ASSIST = "AI_ASSIST"
    BLACKBOX_CAPTURE = "BLACKBOX_CAPTURE"


@dataclass(frozen=True)
class LimitedExposurePolicy:
    """Explicit allow-list. Empty sets mean no non-BlackBox disclosure."""
    allowed_consumers: frozenset[str] = field(default_factory=frozenset)
    allowed_purposes: frozenset[ExposurePurpose] = field(default_factory=frozenset)
    allow_summary: bool = False
    allow_embedding: bool = False
    allow_persistent_memory: bool = False
    allow_shared_intermediate: bool = False

    def permits(self, consumer: str, purpose: ExposurePurpose) -> bool:
        if purpose is ExposurePurpose.BLACKBOX_CAPTURE:
            return True
        return consumer in self.allowed_consumers and purpose in self.allowed_purposes


@dataclass(frozen=True)
class DataLabel:
    classification: DataClass = DataClass.STANDARD
    categories: frozenset[LimitedCategory] = field(default_factory=frozenset)
    policy: LimitedExposurePolicy = field(default_factory=LimitedExposurePolicy)
    subject_id: str = ""
    origin_event_id: str = ""

    @property
    def limited(self) -> bool:
        return self.classification is DataClass.LIMITED

    def inherited(self, *, origin_event_id: Optional[str] = None) -> "DataLabel":
        """Derivatives retain the original classification and restrictions."""
        return replace(self, origin_event_id=origin_event_id or self.origin_event_id)


STANDARD_LABEL = DataLabel()


@dataclass(frozen=True)
class LimitedContextRef:
    """Opaque reference safe to place in shared coordination state."""
    ref_id: str
    categories: tuple[str, ...]
    subject_id: str = ""
    details_withheld: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref_id": self.ref_id,
            "classification": DataClass.LIMITED.value,
            "categories": list(self.categories),
            "subject_id": self.subject_id,
            "details_withheld": self.details_withheld,
        }


def make_ref(label: DataLabel, *, event_id: str, namespace: str = "limited") -> LimitedContextRef:
    if not label.limited:
        raise ValueError("LimitedContextRef requires a LIMITED label")
    raw = f"{namespace}:{event_id}:{label.subject_id}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:24]
    return LimitedContextRef(
        ref_id=f"{namespace}:{digest}",
        categories=tuple(sorted(c.value for c in label.categories)),
        subject_id=label.subject_id,
    )


def may_expose(label: DataLabel, *, consumer: str, purpose: ExposurePurpose) -> bool:
    return not label.limited or label.policy.permits(consumer, purpose)


def require_exposure(label: DataLabel, *, consumer: str, purpose: ExposurePurpose) -> None:
    if not may_expose(label, consumer=consumer, purpose=purpose):
        raise PermissionError(
            f"LIMITED context not authorised for consumer={consumer!r} purpose={purpose.value!r}"
        )


def shared_view(value: Any, label: DataLabel, *, event_id: str = "") -> Any:
    """Return data safe for broadly consumed/shared intermediate state.

    STANDARD data passes through. LIMITED data never does: callers receive only
    an opaque reference carrying non-secret handling metadata.
    """
    if not label.limited:
        return value
    return make_ref(label, event_id=event_id or label.origin_event_id or "unknown").to_dict()


def blackbox_envelope(payload: Mapping[str, Any], label: DataLabel) -> dict[str, Any]:
    """Wrap the *unaltered* payload for the authoritative BlackBox sink."""
    return {
        "data_handling": {
            "classification": label.classification.value,
            "categories": sorted(c.value for c in label.categories),
            "subject_id": label.subject_id,
            "origin_event_id": label.origin_event_id,
        },
        "payload": dict(payload),
    }


def label_from_mapping(value: Optional[Mapping[str, Any]]) -> DataLabel:
    """Strict parser for API/event boundaries; unknown values fail closed."""
    if not value:
        return STANDARD_LABEL
    raw_class = str(value.get("classification") or DataClass.STANDARD.value).upper()
    try:
        classification = DataClass(raw_class)
    except ValueError as exc:
        raise ValueError(f"unknown data classification: {raw_class!r}") from exc
    categories = frozenset(LimitedCategory(str(x).upper()) for x in (value.get("categories") or ()))
    access = value.get("access") or {}
    handling = value.get("handling") or {}
    purposes = frozenset(ExposurePurpose(str(x).upper()) for x in (access.get("allowed_purposes") or ()))
    policy = LimitedExposurePolicy(
        allowed_consumers=frozenset(str(x) for x in (access.get("allowed_consumers") or ())),
        allowed_purposes=purposes,
        allow_summary=bool(handling.get("allow_summary", False)),
        allow_embedding=bool(handling.get("allow_embedding", False)),
        allow_persistent_memory=bool(handling.get("allow_persistent_memory", False)),
        allow_shared_intermediate=bool(handling.get("allow_shared_intermediate", False)),
    )
    if classification is DataClass.LIMITED and not categories:
        categories = frozenset({LimitedCategory.USER_DESIGNATED})
    return DataLabel(
        classification=classification,
        categories=categories,
        policy=policy,
        subject_id=str(value.get("subject_id") or ""),
        origin_event_id=str(value.get("origin_event_id") or ""),
    )


def label_for_audience(*, participant_ids: Iterable[str], restricted: bool,
                       subject_id: str = "", origin_event_id: str = "") -> DataLabel:
    """Classify deliberately audience-restricted conversations as LIMITED.

    Privacy follows the social boundary established by the conversation, not
    merely the semantic sensitivity of its words. Participant access is scoped
    to direct conversation; other purposes require an explicit policy.
    """
    participants = frozenset(str(x) for x in participant_ids if str(x))
    if not restricted:
        return DataLabel(subject_id=subject_id, origin_event_id=origin_event_id)
    return DataLabel(
        classification=DataClass.LIMITED,
        categories=frozenset({LimitedCategory.USER_DESIGNATED}),
        policy=LimitedExposurePolicy(
            allowed_consumers=participants,
            allowed_purposes=frozenset({ExposurePurpose.DIRECT_CONVERSATION}),
        ),
        subject_id=subject_id,
        origin_event_id=origin_event_id,
    )

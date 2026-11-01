"""PubCast security authority and classified-data access gate.

The licensed PubCast instance Owner is the root administrative/custodial
principal for that instance. Host authority is delegated by the Owner and is
never implied by merely running an event. Classified payloads are released only
through SecurityGate. Every classified access attempt is audited; Owner access
requires an acknowledgement before disclosure and does not declassify data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Optional
import time

from .limited_exposure import DataClass, DataLabel, ExposurePurpose


class PrincipalRole(str, Enum):
    OWNER = "OWNER"
    HOST = "HOST"
    PARTICIPANT = "PARTICIPANT"
    AI = "AI"
    SYSTEM = "SYSTEM"


class SecurityOperation(str, Enum):
    READ = "READ"
    RESOLVE = "RESOLVE"
    SEARCH = "SEARCH"
    COPY = "COPY"
    DERIVE = "DERIVE"
    SUMMARIZE = "SUMMARIZE"
    TRANSFORM = "TRANSFORM"
    HANDOFF = "HANDOFF"
    EXPORT = "EXPORT"
    PERSIST = "PERSIST"
    RECLASSIFY = "RECLASSIFY"
    AI_ASSIST = "AI_ASSIST"


@dataclass(frozen=True)
class SecurityPrincipal:
    principal_id: str
    role: PrincipalRole
    instance_id: str
    authenticated: bool = True
    delegated_operations: frozenset[SecurityOperation] = field(default_factory=frozenset)


@dataclass(frozen=True)
class ProtectedResource:
    resource_id: str
    origin_instance_id: str
    owner_authority_id: str
    label: DataLabel


@dataclass(frozen=True)
class OwnerAcknowledgement:
    principal_id: str
    resource_id: str
    operation: SecurityOperation
    acknowledged: bool


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str
    warning_required: bool = False


class ClassifiedAccessDenied(PermissionError):
    pass


class OwnerAcknowledgementRequired(ClassifiedAccessDenied):
    pass


class SecurityGate:
    """Fail-closed gate for classified PubCast resources.

    ``audit_sink`` receives metadata only, never the protected payload. It is
    called for every classified attempt, including denied and warning-required
    attempts. Standard data bypasses classified auditing by design.
    """

    def __init__(self, audit_sink: Optional[Callable[[Mapping[str, Any]], None]] = None):
        self._audit_sink = audit_sink

    def _audit(self, *, principal: SecurityPrincipal, resource: ProtectedResource,
               operation: SecurityOperation, outcome: str, reason: str) -> None:
        if not resource.label.limited:
            return
        event = {
            "event_type": "security.classified_access",
            "timestamp_ns": time.time_ns(),
            "principal_id": principal.principal_id,
            "principal_role": principal.role.value,
            "principal_instance_id": principal.instance_id,
            "resource_id": resource.resource_id,
            "origin_instance_id": resource.origin_instance_id,
            "owner_authority_id": resource.owner_authority_id,
            "classification": resource.label.classification.value,
            "categories": sorted(c.value for c in resource.label.categories),
            "operation": operation.value,
            "outcome": outcome,
            "reason": reason,
        }
        if self._audit_sink is not None:
            self._audit_sink(event)

    def decide(self, *, principal: SecurityPrincipal, resource: ProtectedResource,
               operation: SecurityOperation, purpose: ExposurePurpose,
               acknowledgement: Optional[OwnerAcknowledgement] = None) -> AccessDecision:
        if not resource.label.limited:
            return AccessDecision(True, "standard_data")
        if not principal.authenticated:
            return AccessDecision(False, "principal_not_authenticated")
        if principal.instance_id != resource.origin_instance_id:
            return AccessDecision(False, "wrong_instance")

        if principal.role is PrincipalRole.OWNER:
            if principal.principal_id != resource.owner_authority_id:
                return AccessDecision(False, "not_origin_instance_owner")
            ack_ok = (
                acknowledgement is not None
                and acknowledgement.acknowledged
                and acknowledgement.principal_id == principal.principal_id
                and acknowledgement.resource_id == resource.resource_id
                and acknowledgement.operation is operation
            )
            if not ack_ok:
                return AccessDecision(False, "owner_warning_acknowledgement_required", True)
            return AccessDecision(True, "owner_custodial_authority")

        if principal.role is PrincipalRole.HOST and operation not in principal.delegated_operations:
            return AccessDecision(False, "host_operation_not_delegated")

        if principal.principal_id not in resource.label.policy.allowed_consumers:
            return AccessDecision(False, "consumer_not_authorized")
        if purpose not in resource.label.policy.allowed_purposes:
            return AccessDecision(False, "purpose_not_authorized")
        return AccessDecision(True, "explicit_scoped_authorization")

    def authorize(self, *, principal: SecurityPrincipal, resource: ProtectedResource,
                  operation: SecurityOperation, purpose: ExposurePurpose,
                  acknowledgement: Optional[OwnerAcknowledgement] = None) -> None:
        decision = self.decide(
            principal=principal, resource=resource, operation=operation,
            purpose=purpose, acknowledgement=acknowledgement,
        )
        self._audit(
            principal=principal, resource=resource, operation=operation,
            outcome="ALLOW" if decision.allowed else ("WARNING_REQUIRED" if decision.warning_required else "DENY"),
            reason=decision.reason,
        )
        if decision.allowed:
            return
        if decision.warning_required:
            raise OwnerAcknowledgementRequired(decision.reason)
        raise ClassifiedAccessDenied(decision.reason)

    def release(self, payload: Any, *, principal: SecurityPrincipal,
                resource: ProtectedResource, operation: SecurityOperation,
                purpose: ExposurePurpose,
                acknowledgement: Optional[OwnerAcknowledgement] = None) -> Any:
        """Release payload only after authorization. No payload enters audit events."""
        self.authorize(
            principal=principal, resource=resource, operation=operation,
            purpose=purpose, acknowledgement=acknowledgement,
        )
        return payload


def delegated_host(*, principal_id: str, instance_id: str,
                   operations: frozenset[SecurityOperation]) -> SecurityPrincipal:
    """Construct a Host principal carrying explicit Owner-delegated operations."""
    return SecurityPrincipal(
        principal_id=principal_id,
        role=PrincipalRole.HOST,
        instance_id=instance_id,
        delegated_operations=operations,
    )


__all__ = [
    "AccessDecision", "ClassifiedAccessDenied", "OwnerAcknowledgement",
    "OwnerAcknowledgementRequired", "PrincipalRole", "ProtectedResource",
    "SecurityGate", "SecurityOperation", "SecurityPrincipal", "delegated_host",
]

"""Protected action gatekeeper for Iteration Wallet."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from iteration_wallet.identity import ActorIdentity
from iteration_wallet.notification_manager import ActorKind, NotificationManager


class ProtectedActionError(RuntimeError):
    """Raised when a protected custody action is unknown or denied."""


@dataclass(frozen=True)
class ProtectedActionPolicy:
    action_key: str
    label: str
    requires_human: bool = True
    requires_vault_open: bool = True
    requires_cradle_unlock: bool = False
    allows_bot_direct_access: bool = False
    blackbox_event_type: str = "PROTECTED_ACTION_ATTEMPT"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


PROTECTED_ACTIONS: Dict[str, ProtectedActionPolicy] = {
    "remove_from_active": ProtectedActionPolicy("remove_from_active", "remove from active use", blackbox_event_type="REMOVE_FROM_ACTIVE_REQUESTED"),
    "restore_to_active": ProtectedActionPolicy("restore_to_active", "restore to active use", blackbox_event_type="RESTORE_TO_ACTIVE_REQUESTED"),
    "release_from_custody": ProtectedActionPolicy("release_from_custody", "release from custody", blackbox_event_type="RELEASE_FROM_CUSTODY_REQUESTED"),
    "quarantine": ProtectedActionPolicy("quarantine", "quarantine file", blackbox_event_type="QUARANTINE_REQUESTED"),
    "promote_candidate_to_prime": ProtectedActionPolicy("promote_candidate_to_prime", "promote Candidate to Prime", requires_cradle_unlock=True, blackbox_event_type="PROMOTE_CANDIDATE_TO_PRIME_REQUESTED"),
    "export_working_copy": ProtectedActionPolicy("export_working_copy", "export working copy", blackbox_event_type="EXPORT_WORKING_COPY_REQUESTED"),
    "open_vault": ProtectedActionPolicy("open_vault", "open Vault", requires_vault_open=False, blackbox_event_type="OPEN_VAULT_REQUESTED"),
    "open_cradle": ProtectedActionPolicy("open_cradle", "open Cradle", requires_cradle_unlock=False, blackbox_event_type="OPEN_CRADLE_REQUESTED"),
}


def get_protected_action_policy(action_key: str) -> ProtectedActionPolicy:
    try:
        return PROTECTED_ACTIONS[action_key]
    except KeyError as exc:
        raise ProtectedActionError(f"Protected action is not registered: {action_key!r}") from exc


def list_protected_action_policies() -> Dict[str, Dict[str, Any]]:
    return {key: policy.to_dict() for key, policy in PROTECTED_ACTIONS.items()}


def evaluate_protected_action(action_key: str, actor_kind: ActorKind | str | None, *, actor_identity: Optional[ActorIdentity] = None, human_ceremony_passed: bool = False, vault_open: Optional[bool] = None, cradle_unlocked: Optional[bool] = None, gate: Optional[NotificationManager] = None) -> Dict[str, Any]:
    policy = get_protected_action_policy(action_key)
    if policy.requires_vault_open and vault_open is False:
        return {"allowed": False, "reason": "Vault must be open.", "action_key": action_key, "policy": policy.to_dict()}
    if policy.requires_cradle_unlock and cradle_unlocked is False:
        return {"allowed": False, "reason": "Cradle must be unlocked.", "action_key": action_key, "policy": policy.to_dict()}
    if actor_identity is not None:
        actor_kind = actor_identity.actor_kind
        human_ceremony_passed = bool(human_ceremony_passed or actor_identity.has_human_intent_proof())
    if gate is not None:
        decision = gate.evaluate_direct_access(actor_kind, policy.label, protected=policy.requires_human, human_ceremony_passed=human_ceremony_passed, actor_identity=actor_identity)
    else:
        kind = NotificationManager.coerce_actor_kind(actor_kind)
        if policy.requires_human and kind != ActorKind.HUMAN:
            decision = {"allowed": False, "reason": "AI/tools stay outside the yard; human approval is required."}
        elif policy.requires_human and not human_ceremony_passed:
            decision = {"allowed": False, "reason": "Protected custody requires verified human intent."}
        else:
            decision = {"allowed": True, "reason": "registered human-intent policy passed"}
    decision.update({"action_key": action_key, "action": policy.label, "policy": policy.to_dict(), "blackbox_event_type": policy.blackbox_event_type})
    return decision


def require_protected_action(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    decision = evaluate_protected_action(*args, **kwargs)
    if not decision.get("allowed"):
        raise ProtectedActionError(str(decision.get("reason", "protected action denied")))
    return decision


__all__ = ["PROTECTED_ACTIONS", "ProtectedActionError", "ProtectedActionPolicy", "evaluate_protected_action", "get_protected_action_policy", "list_protected_action_policies", "require_protected_action"]

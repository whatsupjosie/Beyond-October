"""Compatibility guard surface for protected-action policy.

Authoritative gate ownership lives in iteration_wallet.gatekeeper. This file is
a thin import surface only; it must not grow separate custody rules.
"""

from iteration_wallet.gatekeeper import (
    PROTECTED_ACTIONS,
    ProtectedActionError,
    ProtectedActionPolicy,
    evaluate_protected_action,
    get_protected_action_policy,
    list_protected_action_policies,
    require_protected_action,
)

__all__ = [
    "PROTECTED_ACTIONS",
    "ProtectedActionError",
    "ProtectedActionPolicy",
    "evaluate_protected_action",
    "get_protected_action_policy",
    "list_protected_action_policies",
    "require_protected_action",
]

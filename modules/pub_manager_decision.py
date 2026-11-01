"""Deterministic Pub Manager decision policy.

The Pub Manager is an operational authority, not an LLM.  It evaluates current
verified evidence, urgency, reversibility, time pressure, and bounded owner
preferences.  AI advice may be attached as evidence but can never grant
permission by itself.

The policy is intentionally conservative:
* Class A engineering protection may run automatically when evidence supports it.
* Class B reversible safety actions may run automatically only under time pressure,
  above a risk threshold, and inside a short rollback lease.
* Class C operational judgement may use reviewed conditional preferences.
* Class D permanent/destructive/public actions always require a human decision.
"""
from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .persistence import read_json, write_json

SCHEMA_VERSION = "PubManagerDecision.v1"


@dataclass(frozen=True)
class ActionPolicy:
    action: str
    authority_class: str
    description: str
    reversible: bool
    auto_eligible: bool
    human_required: bool
    risk_threshold: float
    auto_urgencies: Tuple[str, ...]
    max_auto_duration_seconds: Optional[float] = None
    default_auto_duration_seconds: Optional[float] = None
    rollback_action: Optional[str] = None


ACTION_POLICIES: Dict[str, ActionPolicy] = {
    # Class A: engineering protection.  These preserve work or reduce load.
    "emergency_save": ActionPolicy(
        "emergency_save", "A", "Preserve current work before a likely failure.",
        True, True, False, 0.30, ("medium", "high", "critical"), None, None, None,
    ),
    "reduce_performance": ActionPolicy(
        "reduce_performance", "A", "Move runtime to the low/stability profile.",
        True, True, False, 0.35, ("medium", "high", "critical"), None, None, "restore_performance",
    ),
    "stop_recording": ActionPolicy(
        "stop_recording", "A", "Stop active recording to prevent corruption or disk exhaustion.",
        True, True, False, 0.45, ("high", "critical"), None, None, None,
    ),
    # Class B: short, reversible containment.
    "hold_action": ActionPolicy(
        "hold_action", "B", "Temporarily hold a pending operation.",
        True, True, False, 0.62, ("high", "critical"), 120.0, 30.0, "release_hold",
    ),
    "mute_user": ActionPolicy(
        "mute_user", "B", "Temporarily mute a participant.",
        True, True, False, 0.68, ("high", "critical"), 300.0, 60.0, "unmute_user",
    ),
    "freeze_actor": ActionPolicy(
        "freeze_actor", "B", "Temporarily freeze avatar control.",
        True, True, False, 0.72, ("high", "critical"), 300.0, 60.0, "unfreeze_actor",
    ),
    # Class C: operational choices can eventually use reviewed preferences, but
    # none are auto-enabled until a concrete executor is wired.
    "select_recovery_path": ActionPolicy(
        "select_recovery_path", "C", "Choose among safe recovery paths.",
        True, False, False, 0.55, ("medium", "high", "critical"), None, None, None,
    ),
    # Class D: permanent/person-affecting actions always require a human.
    "kick_user": ActionPolicy(
        "kick_user", "D", "Remove a participant from the current session.",
        False, False, True, 1.0, tuple(), None, None, None,
    ),
    "ban_user": ActionPolicy(
        "ban_user", "D", "Ban a participant.",
        False, False, True, 1.0, tuple(), None, None, None,
    ),
}

_URGENCY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def canonical_urgency(value: Any) -> str:
    raw = str(value or "medium").strip().lower()
    aliases = {"urgent": "high", "emergency": "critical", "normal": "medium"}
    raw = aliases.get(raw, raw)
    return raw if raw in _URGENCY_ORDER else "medium"


def _unit(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return max(0.0, min(1.0, number))


def _safe_number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def evidence_score(evidence: Mapping[str, Any] | None) -> Tuple[float, List[str]]:
    """Return a deterministic 0..1 risk score and human-readable reasons."""
    e = dict(evidence or {})
    severity = _unit(e.get("severity"), 0.0)
    confidence = _unit(e.get("confidence"), 0.5 if e else 0.0)
    score = severity * 0.55 + confidence * 0.20
    reasons: List[str] = []

    flag_weights = {
        "active_failure": 0.15,
        "data_loss_risk": 0.20,
        "security_risk": 0.18,
        "privacy_risk": 0.18,
        "runaway_process": 0.15,
        "disk_critical": 0.20,
        "recording_corruption_risk": 0.16,
        "repeated_violation": 0.10,
    }
    for key, weight in flag_weights.items():
        if bool(e.get(key)):
            score += weight
            reasons.append(key)

    health = str(e.get("system_health") or "").strip().lower()
    if health in {"failed", "offline", "critical"}:
        score += 0.18
        reasons.append(f"system_health={health}")
    elif health in {"degraded", "warning"}:
        score += 0.08
        reasons.append(f"system_health={health}")

    repeat_count = max(0.0, _safe_number(e.get("repeat_count"), 0.0))
    if repeat_count >= 5:
        score += 0.12
        reasons.append("repeat_count>=5")
    elif repeat_count >= 2:
        score += 0.06
        reasons.append("repeat_count>=2")

    if severity:
        reasons.insert(0, f"severity={severity:.2f}")
    if e:
        reasons.insert(1 if severity else 0, f"confidence={confidence:.2f}")
    return round(max(0.0, min(1.0, score)), 4), reasons


def preference_context(evidence: Mapping[str, Any] | None, metadata: Mapping[str, Any] | None = None) -> Dict[str, str]:
    """Keep only stable conditional dimensions; never profile inferred motives."""
    source: Dict[str, Any] = {}
    source.update(dict(metadata or {}))
    source.update(dict(evidence or {}))
    allowed = ("incident_type", "subsystem", "failure_mode", "room_kind", "project_kind")
    out: Dict[str, str] = {}
    for key in allowed:
        value = str(source.get(key) or "").strip().lower()
        if value:
            out[key] = value[:120]
    return out


class ConditionalPreferenceModel:
    """Reviewed, conditional owner preferences.

    This is deliberately not a raw global approval percentage.  A preference is
    scoped to action + concrete context, requires at least three reviewed human
    decisions, and can never elevate a Class D action or override a hard policy.
    """

    def __init__(self, data_dir: Path | str) -> None:
        self.path = Path(data_dir) / "pub_manager" / "preferences.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": SCHEMA_VERSION, "records": {}}
        try:
            payload = read_json(self.path)
            return payload if isinstance(payload, dict) else {"schema_version": SCHEMA_VERSION, "records": {}}
        except Exception:
            return {"schema_version": SCHEMA_VERSION, "records": {}}

    def _key(self, action: str, context: Mapping[str, Any]) -> str:
        return json.dumps({"action": action, "context": dict(sorted(context.items()))}, sort_keys=True, separators=(",", ":"))

    def record_human_review(
        self,
        *,
        action: str,
        approved: bool,
        evidence: Mapping[str, Any] | None,
        metadata: Mapping[str, Any] | None,
        reviewer: str,
        corrected_automatic_decision: bool = False,
    ) -> Dict[str, Any]:
        context = preference_context(evidence, metadata)
        key = self._key(action, context)
        with self._lock:
            payload = self._load()
            records = payload.setdefault("records", {})
            row = records.setdefault(key, {
                "action": action,
                "context": context,
                "approved_count": 0,
                "denied_count": 0,
                "correction_count": 0,
                "review_count": 0,
                "last_reviewer": "",
                "updated_at": 0.0,
            })
            row["review_count"] = int(row.get("review_count", 0)) + 1
            row["approved_count" if approved else "denied_count"] = int(row.get("approved_count" if approved else "denied_count", 0)) + 1
            if corrected_automatic_decision:
                row["correction_count"] = int(row.get("correction_count", 0)) + 1
            row["last_reviewer"] = str(reviewer or "unknown")[:160]
            row["updated_at"] = time.time()
            total = max(1, int(row["review_count"]))
            dominant = max(int(row.get("approved_count", 0)), int(row.get("denied_count", 0)))
            consistency = dominant / total
            evidence_factor = min(1.0, total / 4.0)
            correction_penalty = min(0.5, int(row.get("correction_count", 0)) * 0.1)
            row["confidence"] = round(max(0.0, consistency * evidence_factor - correction_penalty), 4)
            row["preferred"] = "approve" if int(row.get("approved_count", 0)) > int(row.get("denied_count", 0)) else "deny"
            write_json(self.path, payload)
            return dict(row)

    def suggestion(self, *, action: str, evidence: Mapping[str, Any] | None, metadata: Mapping[str, Any] | None) -> Optional[Dict[str, Any]]:
        context = preference_context(evidence, metadata)
        payload = self._load()
        row = (payload.get("records") or {}).get(self._key(action, context))
        if not isinstance(row, dict):
            return None
        if int(row.get("review_count", 0)) < 3 or float(row.get("confidence", 0.0)) < 0.72:
            return None
        return dict(row)

    def snapshot(self) -> Dict[str, Any]:
        return self._load()


class PubManagerDecisionEngine:
    def __init__(self, data_dir: Path | str) -> None:
        self.preferences = ConditionalPreferenceModel(data_dir)

    def policy_snapshot(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "principle": "Autonomy scales with urgency and reversibility, never model confidence alone.",
            "actions": {name: asdict(policy) for name, policy in ACTION_POLICIES.items()},
        }

    def evaluate(
        self,
        *,
        action: str,
        urgency: Any = "medium",
        evidence: Mapping[str, Any] | None = None,
        deadline_seconds: Any = None,
        requested_duration_seconds: Any = None,
        metadata: Mapping[str, Any] | None = None,
        ai_advisory: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        action = str(action or "").strip()
        policy = ACTION_POLICIES.get(action)
        if policy is None:
            raise ValueError(f"unsupported Pub Manager action: {action}")

        urgency_name = canonical_urgency(urgency)
        score, reasons = evidence_score(evidence)
        deadline = None if deadline_seconds in (None, "") else max(0.0, _safe_number(deadline_seconds, 0.0))
        requested_duration = None if requested_duration_seconds in (None, "") else max(0.0, _safe_number(requested_duration_seconds, 0.0))
        default_duration = policy.default_auto_duration_seconds
        effective_duration = requested_duration if requested_duration is not None else default_duration
        preference = self.preferences.suggestion(action=action, evidence=evidence, metadata=metadata)

        base = {
            "schema_version": SCHEMA_VERSION,
            "action": action,
            "authority_class": policy.authority_class,
            "urgency": urgency_name,
            "risk_score": score,
            "risk_reasons": reasons,
            "reversible": policy.reversible,
            "deadline_seconds": deadline,
            "requested_duration_seconds": requested_duration,
            "effective_duration_seconds": effective_duration,
            "max_auto_duration_seconds": policy.max_auto_duration_seconds,
            "rollback_action": policy.rollback_action,
            "preference_considered": preference,
            "ai_advisory_recorded": bool(ai_advisory),
            "ai_advisory_decisive": False,
            "evaluated_at": time.time(),
        }

        if policy.human_required or policy.authority_class == "D":
            return {
                **base,
                "approved": False,
                "status": "human_required",
                "decision_source": "hard_policy",
                "reason": "Permanent or high-impact action requires explicit human authorization.",
            }

        duration_too_long = bool(
            policy.max_auto_duration_seconds is not None
            and effective_duration is not None
            and effective_duration > policy.max_auto_duration_seconds
        )
        if duration_too_long:
            return {
                **base,
                "approved": False,
                "status": "pending_human",
                "decision_source": "hard_policy",
                "reason": "Requested containment duration exceeds the automatic rollback lease.",
            }

        urgency_ok = urgency_name in policy.auto_urgencies
        risk_ok = score >= policy.risk_threshold

        if policy.auto_eligible and urgency_ok and risk_ok:
            return {
                **base,
                "approved": True,
                "status": "auto_approved",
                "decision_source": "deterministic_policy",
                "reason": (
                    f"Evidence score {score:.2f} met {policy.risk_threshold:.2f}; "
                    f"{urgency_name} urgency permits the minimum reversible action."
                ),
            }

        # Reviewed preferences may inform Class C choices only. They never grant
        # protected Class B or permanent Class D authority.
        if policy.authority_class == "C" and preference and preference.get("preferred") == "approve":
            return {
                **base,
                "approved": False,
                "status": "pending_human",
                "decision_source": "reviewed_preference_advisory",
                "reason": "A reviewed owner preference favors this path, but no automatic executor is enabled.",
            }

        missing: List[str] = []
        if not urgency_ok:
            missing.append(f"urgency must be one of {', '.join(policy.auto_urgencies) or 'human-only'}")
        if not risk_ok:
            missing.append(f"risk score {score:.2f} is below {policy.risk_threshold:.2f}")
        return {
            **base,
            "approved": False,
            "status": "pending_human",
            "decision_source": "insufficient_automatic_authority",
            "reason": "; ".join(missing) or "Human review requested.",
        }


__all__ = [
    "ACTION_POLICIES",
    "ActionPolicy",
    "ConditionalPreferenceModel",
    "PubManagerDecisionEngine",
    "SCHEMA_VERSION",
    "canonical_urgency",
    "evidence_score",
    "preference_context",
]

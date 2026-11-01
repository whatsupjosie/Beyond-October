"""Pub Manager authority and operational decision control plane.

Alex, Jeremy, and interchangeable language models may request or advise.  They
never grant themselves authority.  Pub Manager evaluates current evidence with a
deterministic policy, can automatically approve only bounded/reversible actions,
asks a human when time allows, and requires a human for permanent actions.

Every approval is tied to one exact request and is consumed once.  A successful
BlackBox write is required before automatic or human approval becomes executable.
"""
from __future__ import annotations

import inspect
import json
import logging
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from .alex_jeremy_bridge import AUTHORITY_ACTIONS, _canonical_authority_action
from .pub_manager_decision import ACTION_POLICIES, PubManagerDecisionEngine
from .route_security import bound_actor, require_role

logger = logging.getLogger("pubcast.pub_manager")
SCHEMA_VERSION = "PubManagerAuthority.v2"
_APPROVED_STATUSES = {"auto_approved", "human_approved"}
_TERMINAL_STATUSES = {"executed", "execution_failed", "denied", "expired", "revoked"}


def _safe(value: str, fallback: str = "unknown") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or fallback)).strip("._-")
    return (cleaned or fallback)[:160]


def _atomic_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


class PubManagerAuthorityStore:
    def __init__(
        self,
        data_dir: Path | str,
        *,
        ttl_seconds: int = 900,
        blackbox_logger: Any = None,
        executor: Optional[Callable[[Dict[str, Any]], Any]] = None,
        decision_engine: Optional[PubManagerDecisionEngine] = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.root = self.data_dir / "pub_manager" / "authority"
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = max(60, int(ttl_seconds))
        self._lock = threading.RLock()
        self._blackbox_logger = blackbox_logger
        self._executor = executor
        self.engine = decision_engine or PubManagerDecisionEngine(self.data_dir)
        self._audit_failures: List[Dict[str, Any]] = []

    def _path(self, request_id: str) -> Path:
        return self.root / f"{_safe(request_id)}.json"

    def _record_event(self, event_type: str, row: Mapping[str, Any], **extra: Any) -> bool:
        event = {
            "ts": time.time(),
            "event_type": event_type,
            "status": str(extra.pop("status", row.get("status", "unknown"))),
            "request_id": row.get("request_id"),
            "action": row.get("action"),
            "target_user_id": row.get("target_user_id"),
            "session_id": row.get("session_id"),
            "decision_source": row.get("decision_source"),
            "risk_score": (row.get("decision") or {}).get("risk_score") if isinstance(row.get("decision"), dict) else None,
            **extra,
        }
        try:
            if self._blackbox_logger is None:
                # Local tests and isolated components may omit a logger.  Record a
                # dedicated local audit file rather than pretending nothing happened.
                audit = self.data_dir / "pub_manager" / "decision_audit.jsonl"
                audit.parent.mkdir(parents=True, exist_ok=True)
                with audit.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            else:
                self._blackbox_logger(self.data_dir, event)
            return True
        except Exception as exc:  # fail closed for approvals
            failure = {"ts": time.time(), "event_type": event_type, "request_id": row.get("request_id"), "error": str(exc)}
            self._audit_failures.append(failure)
            logger.exception("Pub Manager BlackBox write failed")
            return False

    def _evaluate_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        decision = self.engine.evaluate(
            action=row["action"],
            urgency=row.get("urgency"),
            evidence=row.get("evidence"),
            deadline_seconds=row.get("deadline_seconds"),
            requested_duration_seconds=row.get("requested_duration_seconds"),
            metadata=row.get("metadata"),
            ai_advisory=row.get("ai_advisory"),
        )
        row["decision"] = decision
        row["decision_source"] = decision.get("decision_source")
        row["approved"] = bool(decision.get("approved"))
        row["status"] = str(decision.get("status") or "pending_human")
        row["rollback_action"] = decision.get("rollback_action")
        row["effective_duration_seconds"] = decision.get("effective_duration_seconds")
        row["max_auto_duration_seconds"] = decision.get("max_auto_duration_seconds")
        row["updated_at"] = time.time()

        if row["approved"]:
            audit_ok = self._record_event("pub_manager_auto_decision", row, status=row["status"], reason=decision.get("reason"))
            row["audit_recorded"] = audit_ok
            if not audit_ok:
                row["approved"] = False
                row["status"] = "blocked_audit_failure"
                row["decision_source"] = "fail_closed"
                row["decision"] = {**decision, "approved": False, "status": "blocked_audit_failure", "reason": "BlackBox recording failed; action blocked."}
        else:
            row["audit_recorded"] = bool(row.get("audit_recorded", False))
        return row

    def create_request(
        self,
        *,
        action: str,
        target_user_id: str = "",
        session_id: str = "",
        packet_user_id: str = "",
        requested_by: str,
        reason: str = "",
        room_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        urgency: str = "medium",
        evidence: Optional[Dict[str, Any]] = None,
        deadline_seconds: Any = None,
        requested_duration_seconds: Any = None,
        ai_advisory: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        canonical = _canonical_authority_action(action)
        action = canonical if canonical in AUTHORITY_ACTIONS else str(action or "").strip()
        if action not in ACTION_POLICIES:
            raise ValueError(f"unsupported Pub Manager action: {action}")
        now = time.time()
        row = {
            "schema_version": SCHEMA_VERSION,
            "request_id": f"pmreq_{int(now * 1000)}_{uuid.uuid4().hex[:10]}",
            "action": action,
            "target_user_id": str(target_user_id or "")[:160],
            "session_id": str(session_id or "")[:160],
            "packet_user_id": str(packet_user_id or target_user_id or "")[:160],
            "requested_by": str(requested_by or "unknown")[:160],
            "reason": str(reason or "")[:1000],
            "room_id": str(room_id or "")[:160],
            "urgency": str(urgency or "medium")[:40],
            "evidence": _dict(evidence),
            "deadline_seconds": deadline_seconds,
            "requested_duration_seconds": requested_duration_seconds,
            "ai_advisory": _dict(ai_advisory),
            "metadata": _dict(metadata),
            "status": "pending_human",
            "approved": False,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + self.ttl_seconds,
            "decided_at": None,
            "decided_by": None,
            "decision_reason": "",
            "audit_recorded": False,
            "consumed_at": None,
            "consumed_by": None,
            "executed_at": None,
            "execution": None,
        }
        self._evaluate_row(row)
        with self._lock:
            _atomic_write(self._path(row["request_id"]), row)
        return row

    def get(self, request_id: str) -> Optional[Dict[str, Any]]:
        path = self._path(request_id)
        if not path.exists():
            return None
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(row, dict):
                return None
        except Exception:
            return None
        if row.get("status") not in _TERMINAL_STATUSES and row.get("status") != "consumed" and float(row.get("expires_at") or 0) < time.time():
            row["status"] = "expired"
            row["approved"] = False
            row["updated_at"] = time.time()
            with self._lock:
                _atomic_write(path, row)
        return row

    def decide(self, request_id: str, *, approved: bool, reviewer: str, reason: str = "") -> Dict[str, Any]:
        with self._lock:
            row = self.get(request_id)
            if not row:
                raise FileNotFoundError(request_id)
            if row.get("status") in {"executed", "execution_failed"}:
                raise ValueError(f"request cannot be decided from status {row.get('status')}")
            if float(row.get("expires_at") or 0) < time.time():
                row["status"] = "expired"
                row["approved"] = False
                _atomic_write(self._path(request_id), row)
                raise ValueError("authority request expired")

            previous_status = str(row.get("status") or "")
            if approved:
                proposed = {**row, "status": "human_approved", "decision_source": "human_review"}
                audit_ok = self._record_event("pub_manager_human_decision", proposed, status="human_approved", reviewer=reviewer, reason=reason)
                if not audit_ok:
                    row["approved"] = False
                    row["status"] = "blocked_audit_failure"
                    row["decision_source"] = "fail_closed"
                    row["decision_reason"] = "BlackBox recording failed; approval was not granted."
                    row["updated_at"] = time.time()
                    _atomic_write(self._path(request_id), row)
                    raise RuntimeError("BlackBox recording failed; approval blocked")
                row["approved"] = True
                row["status"] = "human_approved"
                row["audit_recorded"] = True
            else:
                self._record_event("pub_manager_human_decision", row, status="denied", reviewer=reviewer, reason=reason)
                row["approved"] = False
                row["status"] = "denied"

            row["decision_source"] = "human_review"
            row["decided_at"] = time.time()
            row["decided_by"] = str(reviewer or "unknown")[:160]
            row["decision_reason"] = str(reason or "")[:1000]
            row["updated_at"] = time.time()
            row["decision"] = {
                **_dict(row.get("decision")),
                "approved": bool(approved),
                "status": row["status"],
                "decision_source": "human_review",
                "reason": row["decision_reason"] or ("Human approved." if approved else "Human denied."),
            }
            self.engine.preferences.record_human_review(
                action=row["action"],
                approved=approved,
                evidence=row.get("evidence"),
                metadata=row.get("metadata"),
                reviewer=reviewer,
                corrected_automatic_decision=previous_status == "auto_approved" and not approved,
            )
            _atomic_write(self._path(request_id), row)
            return row

    def add_evidence(self, request_id: str, *, evidence: Dict[str, Any], replace: bool = False, submitted_by: str = "system") -> Dict[str, Any]:
        with self._lock:
            row = self.get(request_id)
            if not row:
                raise FileNotFoundError(request_id)
            if row.get("status") in _TERMINAL_STATUSES or row.get("consumed_at"):
                raise ValueError(f"request cannot be reevaluated from status {row.get('status')}")
            previous = str(row.get("status") or "")
            row["evidence"] = _dict(evidence) if replace else {**_dict(row.get("evidence")), **_dict(evidence)}
            row.setdefault("evidence_history", []).append({
                "ts": time.time(), "submitted_by": str(submitted_by)[:160], "replace": bool(replace), "evidence": _dict(evidence),
            })
            # Human approval is not silently overridden by an automated reevaluation.
            if previous != "human_approved":
                self._evaluate_row(row)
                if previous == "auto_approved" and row.get("status") != "auto_approved":
                    self._record_event("pub_manager_auto_approval_revoked", row, status="revoked_by_new_evidence")
            row["updated_at"] = time.time()
            _atomic_write(self._path(request_id), row)
            return row

    def list(self, *, status: str = "all", limit: int = 100) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for path in self.root.glob("pmreq_*.json"):
            row = self.get(path.stem)
            if not row:
                continue
            if status != "all" and row.get("status") != status:
                continue
            rows.append(row)
        # Backward compatibility with RC1 authreq ids.
        for path in self.root.glob("authreq_*.json"):
            row = self.get(path.stem)
            if row and (status == "all" or row.get("status") == status):
                rows.append(row)
        rows.sort(key=lambda r: float(r.get("created_at") or 0), reverse=True)
        return rows[: max(1, min(1000, int(limit)))]

    def reviewer(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """AlexJeremyBridge callback. Fail closed unless exact approval is live."""
        payload = signal.get("payload") if isinstance(signal.get("payload"), dict) else {}
        request_id = str(payload.get("authority_request_id") or "").strip()
        requested_action = _canonical_authority_action(payload.get("requested_action") or payload.get("action") or "")
        if not request_id:
            return {
                "reviewer": "pub_manager",
                "approved": False,
                "requires_authority": requested_action in AUTHORITY_ACTIONS,
                "decision": "pending_pub_manager_decision",
            }
        row = self.get(request_id)
        if not row:
            return {"reviewer": "pub_manager", "approved": False, "requires_authority": True, "decision": "request_not_found"}
        exact_match = all([
            row.get("action") == requested_action,
            str(row.get("session_id")) == str(signal.get("session_id")),
            str(row.get("packet_user_id")) == str(signal.get("user_id")),
        ])
        executable = bool(
            row.get("approved")
            and row.get("status") in _APPROVED_STATUSES
            and row.get("audit_recorded")
            and not row.get("consumed_at")
            and exact_match
        )
        return {
            "reviewer": str(row.get("decided_by") or row.get("decision_source") or "pub_manager"),
            "approved": executable,
            "requires_authority": True,
            "decision": "approved_exact_request" if executable else "blocked_request_mismatch_consumed_or_not_approved",
            "authority_request_id": request_id,
            "decision_source": row.get("decision_source"),
        }

    def validate_authorization(
        self,
        request_id: str,
        *,
        action: str,
        target_user_id: str,
        session_id: str,
        packet_user_id: str,
        requested_duration_seconds: Any = None,
    ) -> Dict[str, Any]:
        row = self.get(request_id)
        if not row:
            raise FileNotFoundError(request_id)
        action = _canonical_authority_action(action)
        exact = all([
            row.get("action") == action,
            str(row.get("target_user_id")) == str(target_user_id),
            str(row.get("session_id")) == str(session_id),
            str(row.get("packet_user_id")) == str(packet_user_id),
        ])
        if not exact:
            raise PermissionError("authority request does not match action, target, user, and session")
        if row.get("status") not in _APPROVED_STATUSES or not row.get("approved"):
            raise PermissionError(f"authority request is not approved (status={row.get('status')})")
        if not row.get("audit_recorded"):
            raise PermissionError("authority decision has no successful BlackBox record")
        if row.get("consumed_at"):
            raise PermissionError("authority request has already been consumed")
        if float(row.get("expires_at") or 0) < time.time():
            raise PermissionError("authority request expired")
        if row.get("decision_source") == "deterministic_policy":
            maximum = row.get("max_auto_duration_seconds")
            approved_duration = row.get("effective_duration_seconds")
            supplied = requested_duration_seconds
            if maximum is not None:
                try:
                    actual = float(supplied if supplied not in (None, "") else approved_duration)
                except (TypeError, ValueError):
                    raise PermissionError("automatic containment requires a bounded duration")
                if actual <= 0 or actual > float(maximum):
                    raise PermissionError(f"automatic containment duration must be >0 and <= {maximum:g}s")
                if approved_duration is not None and actual > float(approved_duration):
                    raise PermissionError("requested duration exceeds the approved automatic lease")
        return row

    def consume_authorization(self, request_id: str, *, consumed_by: str) -> Dict[str, Any]:
        with self._lock:
            row = self.get(request_id)
            if not row:
                raise FileNotFoundError(request_id)
            if row.get("consumed_at"):
                raise PermissionError("authority request has already been consumed")
            if row.get("status") not in _APPROVED_STATUSES or not row.get("approved"):
                raise PermissionError("authority request is not executable")
            proposed = {**row, "status": "consumed", "consumed_by": str(consumed_by or "unknown")[:160]}
            if not self._record_event("pub_manager_authority_consumed", proposed, status="consumed", consumed_by=proposed["consumed_by"]):
                raise PermissionError("BlackBox recording failed; authority consumption blocked")
            row["consumed_at"] = time.time()
            row["consumed_by"] = proposed["consumed_by"]
            row["status"] = "consumed"
            row["updated_at"] = time.time()
            _atomic_write(self._path(request_id), row)
            return row

    def mark_execution_result(self, request_id: str, *, ok: bool, result: Any = None, error: str = "") -> Dict[str, Any]:
        with self._lock:
            row = self.get(request_id)
            if not row:
                raise FileNotFoundError(request_id)
            row["status"] = "executed" if ok else "execution_failed"
            row["executed_at"] = time.time()
            row["execution"] = {"ok": bool(ok), "result": result if ok else None, "error": str(error or "")[:1000]}
            row["updated_at"] = time.time()
            self._record_event("pub_manager_execution_result", row, status=row["status"], error=str(error or "")[:500])
            _atomic_write(self._path(request_id), row)
            return row

    async def execute_decision(self, request_id: str, *, actor: str = "pub_manager") -> Dict[str, Any]:
        row = self.get(request_id)
        if not row:
            raise FileNotFoundError(request_id)
        if row.get("action") in AUTHORITY_ACTIONS:
            raise ValueError("governance actions execute through governance routes")
        self.validate_authorization(
            request_id,
            action=row["action"],
            target_user_id=row.get("target_user_id", ""),
            session_id=row.get("session_id", ""),
            packet_user_id=row.get("packet_user_id", ""),
            requested_duration_seconds=row.get("requested_duration_seconds"),
        )
        self.consume_authorization(request_id, consumed_by=actor)
        if self._executor is None:
            return self.mark_execution_result(request_id, ok=False, error="no executor registered")
        try:
            result = self._executor(row)
            if inspect.isawaitable(result):
                result = await result
            return self.mark_execution_result(request_id, ok=True, result=result)
        except Exception as exc:
            self.mark_execution_result(request_id, ok=False, error=str(exc))
            raise

    def health(self) -> Dict[str, Any]:
        rows = self.list(limit=1000)
        counts: Dict[str, int] = {}
        for row in rows:
            counts[str(row.get("status") or "unknown")] = counts.get(str(row.get("status") or "unknown"), 0) + 1
        return {
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "counts": counts,
            "audit_failures": len(self._audit_failures),
            "last_audit_failure": self._audit_failures[-1] if self._audit_failures else None,
            "policy_actions": sorted(ACTION_POLICIES),
        }


def _request_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "action": str(body.get("action") or ""),
        "target_user_id": str(body.get("target_user_id") or body.get("user_id") or ""),
        "session_id": str(body.get("session_id") or ""),
        "packet_user_id": str(body.get("packet_user_id") or body.get("target_user_id") or body.get("user_id") or ""),
        "requested_by": str(body.get("requested_by") or "jeremy"),
        "reason": str(body.get("reason") or ""),
        "room_id": str(body.get("room_id") or ""),
        "metadata": _dict(body.get("metadata")),
        "urgency": str(body.get("urgency") or "medium"),
        "evidence": _dict(body.get("evidence")),
        "deadline_seconds": body.get("deadline_seconds"),
        "requested_duration_seconds": body.get("requested_duration_seconds", body.get("duration_seconds")),
        "ai_advisory": _dict(body.get("ai_advisory")),
    }


def create_pub_manager_authority_router(store: PubManagerAuthorityStore, bridge: Any) -> APIRouter:
    router = APIRouter(prefix="/api/pubmanager/authority", tags=["Pub Manager Authority"])

    async def _body(request: Request) -> Dict[str, Any]:
        try:
            value = await request.json()
        except Exception:
            value = {}
        if not isinstance(value, dict):
            raise HTTPException(400, "JSON body must be an object")
        return value

    def _signal(row: Dict[str, Any], body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if bridge is None or row.get("action") not in AUTHORITY_ACTIONS:
            return None
        return bridge.signal_from_jeremy(
            user_id=row["packet_user_id"],
            session_id=row["session_id"],
            room_state=str(body.get("room_state") or ("critical" if row.get("approved") else "tense")),
            urgency=str(row.get("urgency") or body.get("urgency") or "medium"),
            reason=row.get("decision_reason") or row.get("reason") or f"{row['action']} requested",
            payload={
                "requested_action": row["action"],
                "authority_request_id": row["request_id"],
                "target_user_id": row["target_user_id"],
                "room_id": row["room_id"],
            },
        )

    @router.get("/requests")
    async def list_requests(status: str = "all", limit: int = 100, identity: Dict[str, Any] = Depends(require_role("mod"))):
        return {"ok": True, "requests": store.list(status=status[:40], limit=limit)}

    @router.get("/requests/{request_id}")
    async def get_request(request_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        row = store.get(request_id)
        if not row:
            raise HTTPException(404, "authority request not found")
        return {"ok": True, "request": row}

    @router.post("/requests")
    async def request_authority(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _body(request)
        payload = _request_payload(body)
        payload["requested_by"] = bound_actor(
            request=request,
            identity=identity,
            explicit_value=body.get("requested_by"),
            field_name="requested_by",
        )
        try:
            row = store.create_request(**payload)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return {"ok": True, "request": row, "bridge_packet": _signal(row, body)}

    async def _decide(request_id: str, request: Request, approved: bool, identity: Dict[str, Any]) -> Dict[str, Any]:
        body = await _body(request)
        reviewer = bound_actor(request=request, identity=identity, explicit_value=body.get("reviewed_by"), field_name="reviewed_by")
        try:
            row = store.decide(request_id, approved=approved, reviewer=reviewer, reason=str(body.get("reason") or ""))
        except FileNotFoundError:
            raise HTTPException(404, "authority request not found")
        except RuntimeError as exc:
            raise HTTPException(503, str(exc))
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        return {"ok": True, "request": row, "bridge_packet": _signal(row, body)}

    @router.post("/requests/{request_id}/approve")
    async def approve_request(request_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        return await _decide(request_id, request, True, identity)

    @router.post("/requests/{request_id}/deny")
    async def deny_request(request_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        return await _decide(request_id, request, False, identity)

    @router.post("/requests/{request_id}/evidence")
    async def submit_evidence(request_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _body(request)
        submitted_by = bound_actor(request=request, identity=identity, explicit_value=body.get("submitted_by"), field_name="submitted_by")
        try:
            row = store.add_evidence(request_id, evidence=_dict(body.get("evidence")), replace=bool(body.get("replace", False)), submitted_by=submitted_by)
        except FileNotFoundError:
            raise HTTPException(404, "authority request not found")
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        return {"ok": True, "request": row, "bridge_packet": _signal(row, body)}

    @router.get("/health")
    async def health(identity: Dict[str, Any] = Depends(require_role("mod"))):
        return {**store.health(), "bridge": bridge.bridge_health() if bridge is not None else {"available": False}}

    return router


def create_pub_manager_control_router(store: PubManagerAuthorityStore, bridge: Any = None) -> APIRouter:
    """General engineering-control routes.  Safe actions can execute automatically."""
    router = APIRouter(prefix="/api/pubmanager", tags=["Pub Manager Control"])

    async def _body(request: Request) -> Dict[str, Any]:
        try:
            value = await request.json()
        except Exception:
            value = {}
        if not isinstance(value, dict):
            raise HTTPException(400, "JSON body must be an object")
        return value

    @router.get("/policy")
    async def policy(identity: Dict[str, Any] = Depends(require_role("mod"))):
        return {"ok": True, "policy": store.engine.policy_snapshot()}

    @router.get("/preferences")
    async def preferences(identity: Dict[str, Any] = Depends(require_role("mod"))):
        return {"ok": True, "preferences": store.engine.preferences.snapshot()}

    @router.get("/decisions")
    async def decisions(status: str = "all", limit: int = 100, identity: Dict[str, Any] = Depends(require_role("mod"))):
        return {"ok": True, "decisions": store.list(status=status[:40], limit=limit)}

    @router.post("/decisions")
    async def create_decision(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _body(request)
        payload = _request_payload(body)
        payload["requested_by"] = bound_actor(
            request=request,
            identity=identity,
            explicit_value=body.get("requested_by"),
            field_name="requested_by",
        )
        try:
            row = store.create_request(**payload)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        executed = None
        if bool(body.get("execute_immediately")) and row.get("approved") and row.get("action") not in AUTHORITY_ACTIONS:
            try:
                executed = await store.execute_decision(row["request_id"], actor=str(body.get("requested_by") or "pub_manager"))
                row = executed
            except Exception as exc:
                raise HTTPException(503, f"decision approved but execution failed: {exc}")
        return {"ok": True, "decision": row, "executed": executed is not None}

    @router.post("/decisions/{request_id}/evidence")
    async def add_decision_evidence(request_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _body(request)
        submitted_by = bound_actor(request=request, identity=identity, explicit_value=body.get("submitted_by"), field_name="submitted_by")
        try:
            row = store.add_evidence(request_id, evidence=_dict(body.get("evidence")), replace=bool(body.get("replace", False)), submitted_by=submitted_by)
        except FileNotFoundError:
            raise HTTPException(404, "decision not found")
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        return {"ok": True, "decision": row}

    @router.post("/decisions/{request_id}/execute")
    async def execute_decision(request_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _body(request)
        actor = bound_actor(request=request, identity=identity, explicit_value=body.get("executed_by"), field_name="executed_by")
        try:
            row = await store.execute_decision(request_id, actor=actor)
        except FileNotFoundError:
            raise HTTPException(404, "decision not found")
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        except Exception as exc:
            raise HTTPException(503, str(exc))
        return {"ok": True, "decision": row}

    @router.get("/health")
    async def health():
        # Aggregate runtime health is intentionally non-sensitive so the local
        # living UI can report truth before owner authentication is configured.
        return store.health()

    return router


__all__ = [
    "PubManagerAuthorityStore",
    "create_pub_manager_authority_router",
    "create_pub_manager_control_router",
    "SCHEMA_VERSION",
]

"""
modules/governance_routes.py — Governance REST API
═══════════════════════════════════════════════════
FastAPI router for moderation, consent, waiting room, AI disclosure.

Usage in main.py:
    from modules.governance import GovernanceEngine
    from modules.governance_routes import create_governance_router
    gov = GovernanceEngine(DATA_DIR)
    app.include_router(create_governance_router(gov, hub))

Rear View Foresight LLC — Feic Mo Chroí — 2026-03-24T09:30Z
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from modules.governance import (
    GovernanceEngine, BanType, ConsentType, EntryStatus,
)
from modules.route_security import bound_actor, require_role

logger = logging.getLogger("pubcast.governance_routes")


async def _json_dict(request: Request) -> Dict[str, Any]:
    """Parse a request body as a JSON object with clean 400s."""
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Malformed JSON body: {exc.msg}")
    except Exception as exc:
        raise HTTPException(400, f"Invalid JSON body: {exc}")
    if not isinstance(body, dict):
        raise HTTPException(400, "JSON body must be an object")
    return body


def _string_field(body: Dict[str, Any], key: str, *, default: str = "", required: bool = False,
                  max_length: int = 256) -> str:
    value = body.get(key, default)
    if value is None:
        value = default
    if not isinstance(value, str):
        raise HTTPException(400, f"{key} must be a string")
    value = value.strip()
    if required and not value:
        raise HTTPException(400, f"{key} required")
    if len(value) > max_length:
        raise HTTPException(400, f"{key} must be <= {max_length} characters")
    return value


def _optional_non_negative_number(body: Dict[str, Any], key: str) -> float | None:
    value = body.get(key, None)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HTTPException(400, f"{key} must be a non-negative number")
    if value < 0:
        raise HTTPException(400, f"{key} must be non-negative")
    return float(value)


def _bool_field(body: Dict[str, Any], key: str, *, default: bool = False) -> bool:
    value = body.get(key, default)
    if not isinstance(value, bool):
        raise HTTPException(400, f"{key} must be a boolean")
    return value


AI_AUTHORITY_ACTORS = {"alex", "alex_jeremy_bridge", "ai", "ai_delegate", "jeremy", "jeremy_cricket", "pubcast_ai"}


def _normalized_actor(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", "_").split())


def _actor_requires_bridge_authority(actor_id: str) -> bool:
    return _normalized_actor(actor_id) in AI_AUTHORITY_ACTORS


def _authority_requested(body: Dict[str, Any], actor_id: str) -> bool:
    return (
        "authority_source" in body
        or "authority_session_id" in body
        or "authority_user_id" in body
        or "authority_packet" in body
        or "bridge_packet" in body
        or _actor_requires_bridge_authority(actor_id)
    )


def _authority_string(body: Dict[str, Any], key: str) -> str:
    value = body.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise HTTPException(400, f"{key} must be a string")
    return value.strip()


def _require_bridge_authority(
    *,
    body: Dict[str, Any],
    authority_bridge: Any,
    authority_store: Any,
    action: str,
    target_user_id: str,
    actor_id: str,
    requested_duration_seconds: Any = None,
) -> Dict[str, Any] | None:
    """Validate and consume one exact AI/Pub Manager authority grant.

    Human moderators acting directly do not need a Pub Manager request.  AI or
    delegated actions do.  When the v2 authority store is wired, the approval is
    one-use and exact-match; the bridge remains a second independent guard.
    """
    if not _authority_requested(body, actor_id):
        return None
    if "authority_packet" in body or "bridge_packet" in body:
        raise HTTPException(400, "authority packets must be loaded server-side; provide authority_request_id and authority_session_id")
    if authority_bridge is None:
        raise HTTPException(503, "Alex/Jeremy authority bridge is unavailable")

    session_id = _authority_string(body, "authority_session_id") or _authority_string(body, "session_id")
    if not session_id:
        raise HTTPException(400, "authority_session_id required for AI-requested governance actions")
    packet_user_id = _authority_string(body, "authority_user_id") or target_user_id
    request_id = _authority_string(body, "authority_request_id")

    try:
        row = None
        if authority_store is not None:
            if not request_id:
                raise HTTPException(400, "authority_request_id required for AI-requested governance actions")
            row = authority_store.validate_authorization(
                request_id,
                action=action,
                target_user_id=target_user_id,
                session_id=session_id,
                packet_user_id=packet_user_id,
                requested_duration_seconds=requested_duration_seconds,
            )

        packet = authority_bridge.current_packet(user_id=packet_user_id, session_id=session_id)
        authority_bridge.assert_authority_action_allowed(packet, action)

        if authority_store is not None:
            # Consume before mutation so a concurrent/replayed request cannot use
            # the same grant twice.  A failed mutation is recorded as a failed
            # execution and requires a fresh decision to retry.
            authority_store.consume_authorization(request_id, consumed_by=actor_id)
            return {"request": row, "packet": packet, "request_id": request_id}
        return {"packet": packet}
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, "authority request not found") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Bridge authority check failed for %s on %s", action, target_user_id)
        raise HTTPException(503, "Authority bridge check failed") from exc


def create_governance_router(gov: GovernanceEngine, hub: Any = None, authority_bridge: Any = None, authority_store: Any = None) -> APIRouter:
    router = APIRouter(prefix="/api/governance", tags=["Governance"])

    # ═══ CONSENT & ENTRY ═══════════════════════════════════════════════════

    @router.get("/terms")
    async def get_terms():
        return {"terms": gov.get_terms_of_service()}

    @router.get("/ai-disclosure")
    async def get_ai_disclosure():
        # Pull bot names from hub if available
        bot_names = ["Pete", "Sir Purfluous", "Jeremy Cricket"]
        return {"disclosure": gov.get_ai_disclosure(bot_names)}

    @router.post("/consent")
    async def record_consent(request: Request):
        body = await _json_dict(request)
        user_id = _string_field(body, "user_id", required=True, max_length=128)
        consent_type = _string_field(body, "consent_type", required=True, max_length=64)
        granted = _bool_field(body, "granted", default=False)
        try:
            ct = ConsentType(consent_type)
        except ValueError:
            raise HTTPException(400, f"Invalid consent type: {consent_type}")
        record = gov.record_consent(user_id, ct, granted)
        return {"ok": True, "consent_type": ct.value, "granted": granted}

    @router.get("/consent/{user_id}")
    async def get_consents(user_id: str):
        return gov.get_all_consents(user_id)

    @router.get("/consent/{user_id}/check")
    async def check_entry(user_id: str):
        allowed, msg = gov.can_enter(user_id)
        missing = gov.get_missing_consents(user_id)
        return {
            "allowed": allowed,
            "message": msg,
            "missing_consents": [c.value for c in missing],
        }

    # ═══ WAITING ROOM ══════════════════════════════════════════════════════

    @router.post("/waiting-room/request")
    async def request_entry(request: Request):
        body = await _json_dict(request)
        user_id = _string_field(body, "user_id", required=True, max_length=128)
        display_name = _string_field(body, "display_name", default="Guest", max_length=128) or "Guest"
        target_room = _string_field(body, "target_room", default="studio", max_length=128) or "studio"
        consents = body.get("consents", {})
        if not isinstance(consents, dict):
            raise HTTPException(400, "consents must be an object")
        entry = gov.request_entry(user_id, display_name, target_room, consents)
        # Notify host via WebSocket
        if hub:
            import asyncio
            asyncio.create_task(hub.broadcast_system_event({
                "type": "waiting_room_request",
                "payload": {
                    "entry_id": entry.entry_id,
                    "user_id": user_id,
                    "display_name": display_name,
                    "target_room": target_room,
                },
            }))
        return {"ok": True, "entry_id": entry.entry_id, "status": entry.status.value}

    @router.get("/waiting-room")
    async def list_waiting(room: str | None = Query(None, max_length=128)):
        entries = gov.list_waiting(room)
        return {
            "waiting": [
                {
                    "entry_id": e.entry_id,
                    "user_id": e.user_id,
                    "display_name": e.display_name,
                    "target_room": e.target_room,
                    "requested_at": e.requested_at,
                }
                for e in entries
            ]
        }

    @router.post("/waiting-room/{entry_id}/approve")
    async def approve_entry(entry_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        approved_by = bound_actor(request=request, identity=identity, explicit_value=body.get("approved_by"), field_name="approved_by")
        entry = gov.approve_entry(entry_id, approved_by)
        if not entry:
            raise HTTPException(404, "Entry not found or already resolved")
        if hub:
            import asyncio
            asyncio.create_task(hub.broadcast_system_event({
                "type": "entry_approved",
                "payload": {"entry_id": entry_id, "user_id": entry.user_id,
                            "target_room": entry.target_room},
            }))
        return {"ok": True, "status": entry.status.value}

    @router.post("/waiting-room/{entry_id}/deny")
    async def deny_entry(entry_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        denied_by = bound_actor(request=request, identity=identity, explicit_value=body.get("denied_by"), field_name="denied_by")
        reason = _string_field(body, "reason", default="", max_length=512)
        entry = gov.deny_entry(entry_id, denied_by, reason)
        if not entry:
            raise HTTPException(404, "Entry not found or already resolved")
        return {"ok": True, "status": entry.status.value}

    # ═══ MODERATION ════════════════════════════════════════════════════════

    @router.post("/ban")
    async def ban_user(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        user_id = _string_field(body, "user_id", required=True, max_length=128)
        reason = _string_field(body, "reason", default="No reason given", max_length=512) or "No reason given"
        issued_by = bound_actor(request=request, identity=identity, explicit_value=body.get("issued_by"), field_name="issued_by")
        duration = _optional_non_negative_number(body, "duration_hours")
        try:
            ban_type = BanType(_string_field(body, "ban_type", default="session", max_length=64) or "session")
        except ValueError:
            raise HTTPException(400, f"Invalid ban type: {body.get('ban_type', 'session')}")
        authority_context = _require_bridge_authority(
            body=body,
            authority_bridge=authority_bridge,
            authority_store=authority_store,
            action="ban_user",
            target_user_id=user_id,
            actor_id=issued_by,
        )
        try:
            ban = gov.ban_user(user_id, reason, issued_by, ban_type, duration)
            if authority_context and authority_store is not None:
                authority_store.mark_execution_result(authority_context["request_id"], ok=True, result={"ban_id": ban.ban_id})
        except Exception as exc:
            if authority_context and authority_store is not None:
                authority_store.mark_execution_result(authority_context["request_id"], ok=False, error=str(exc))
            raise
        if hub:
            import asyncio
            asyncio.create_task(hub.broadcast_system_event({
                "type": "user_banned",
                "payload": {"user_id": user_id, "reason": reason},
            }))
        return {"ok": True, "ban_id": ban.ban_id}

    @router.post("/unban")
    async def unban_user(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        user_id = _string_field(body, "user_id", required=True, max_length=128)
        lifted_by = bound_actor(request=request, identity=identity, explicit_value=body.get("lifted_by"), field_name="lifted_by")
        if not gov.unban_user(user_id, lifted_by):
            raise HTTPException(404, "No active ban found")
        return {"ok": True}

    @router.post("/freeze")
    async def freeze_avatar(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        user_id = _string_field(body, "user_id", required=True, max_length=128)
        frozen_by = bound_actor(request=request, identity=identity, explicit_value=body.get("frozen_by"), field_name="frozen_by")
        reason = _string_field(body, "reason", default="", max_length=512)
        pose = body.get("pose_override", None)
        duration_seconds = _optional_non_negative_number(body, "duration_seconds")
        authority_context = _require_bridge_authority(
            body=body,
            authority_bridge=authority_bridge,
            authority_store=authority_store,
            action="freeze_actor",
            target_user_id=user_id,
            actor_id=frozen_by,
            requested_duration_seconds=duration_seconds,
        )
        try:
            state = gov.freeze_avatar(user_id, frozen_by, reason, pose)
            if authority_context and authority_store is not None:
                authority_store.mark_execution_result(authority_context["request_id"], ok=True, result={"frozen": True, "duration_seconds": duration_seconds})
        except Exception as exc:
            if authority_context and authority_store is not None:
                authority_store.mark_execution_result(authority_context["request_id"], ok=False, error=str(exc))
            raise
        if authority_context and duration_seconds and duration_seconds > 0:
            import asyncio
            async def _auto_release_freeze() -> None:
                await asyncio.sleep(duration_seconds)
                if gov.unfreeze_avatar(user_id, "pub_manager_auto_release") and hub:
                    await hub.broadcast_system_event({
                        "type": "avatar_unfrozen",
                        "payload": {"user_id": user_id, "unfrozen_by": "pub_manager_auto_release", "automatic": True},
                    })
            asyncio.create_task(_auto_release_freeze())
        if hub:
            import asyncio
            asyncio.create_task(hub.broadcast_system_event({
                "type": "avatar_frozen",
                "payload": {"user_id": user_id, "frozen_by": frozen_by, "reason": reason},
            }))
        return {"ok": True}

    @router.post("/unfreeze")
    async def unfreeze_avatar(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        user_id = _string_field(body, "user_id", required=True, max_length=128)
        unfrozen_by = bound_actor(request=request, identity=identity, explicit_value=body.get("unfrozen_by"), field_name="unfrozen_by")
        if not gov.unfreeze_avatar(user_id, unfrozen_by):
            raise HTTPException(404, "User not frozen")
        return {"ok": True}

    @router.post("/mute")
    async def mute_user(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        user_id = _string_field(body, "user_id", required=True, max_length=128)
        muted_by = bound_actor(request=request, identity=identity, explicit_value=body.get("muted_by"), field_name="muted_by")
        duration = _optional_non_negative_number(body, "duration_seconds") or 0
        authority_context = _require_bridge_authority(
            body=body,
            authority_bridge=authority_bridge,
            authority_store=authority_store,
            action="mute_user",
            target_user_id=user_id,
            actor_id=muted_by,
            requested_duration_seconds=duration,
        )
        try:
            gov.mute_user(user_id, muted_by, duration)
            if authority_context and authority_store is not None:
                authority_store.mark_execution_result(authority_context["request_id"], ok=True, result={"muted": True, "duration_seconds": duration})
        except Exception as exc:
            if authority_context and authority_store is not None:
                authority_store.mark_execution_result(authority_context["request_id"], ok=False, error=str(exc))
            raise
        return {"ok": True}

    @router.post("/unmute")
    async def unmute_user(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        user_id = _string_field(body, "user_id", required=True, max_length=128)
        unmuted_by = bound_actor(request=request, identity=identity, explicit_value=body.get("unmuted_by"), field_name="unmuted_by")
        gov.unmute_user(user_id, unmuted_by)
        return {"ok": True}

    @router.post("/kick")
    async def kick_user(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        user_id = _string_field(body, "user_id", required=True, max_length=128)
        kicked_by = bound_actor(request=request, identity=identity, explicit_value=body.get("kicked_by"), field_name="kicked_by")
        reason = _string_field(body, "reason", default="", max_length=512)
        authority_context = _require_bridge_authority(
            body=body,
            authority_bridge=authority_bridge,
            authority_store=authority_store,
            action="kick_user",
            target_user_id=user_id,
            actor_id=kicked_by,
        )
        try:
            kick_ban = gov.ban_user(user_id, reason or "Kicked", kicked_by, BanType.SESSION)
            if authority_context and authority_store is not None:
                authority_store.mark_execution_result(authority_context["request_id"], ok=True, result={"ban_id": kick_ban.ban_id, "session_kick": True})
        except Exception as exc:
            if authority_context and authority_store is not None:
                authority_store.mark_execution_result(authority_context["request_id"], ok=False, error=str(exc))
            raise
        if hub:
            import asyncio
            asyncio.create_task(hub.broadcast_system_event({
                "type": "user_kicked",
                "payload": {"user_id": user_id, "reason": reason},
            }))
        return {"ok": True}

    # ═══ AUDIT ═════════════════════════════════════════════════════════════

    @router.get("/audit")
    async def get_audit_log(
        limit: int = Query(100, ge=1, le=1000),
        identity: Dict[str, Any] = Depends(require_role("mod")),
    ):
        return gov.get_audit_log(limit)

    @router.get("/audit/{user_id}")
    async def get_user_audit(
        user_id: str,
        identity: Dict[str, Any] = Depends(require_role("mod")),
    ):
        return gov.get_user_history(user_id)

    @router.get("/status")
    async def governance_status():
        return {
            "active_bans": len(gov.list_active_bans()),
            "frozen_avatars": len(gov.list_frozen_avatars()),
            "muted_users": len(gov.list_muted_users()),
            "waiting_room": len(gov.list_waiting()),
        }

    return router

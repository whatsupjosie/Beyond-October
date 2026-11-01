# PubCast AI — alex_routes.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rear View Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart

"""
Alex Core API Routes
Provides endpoints for interacting with Alex AI companion
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from .route_security import current_identity, require_role
from modules.auth import role_gte

router = APIRouter(prefix="/api/alex", tags=["alex"])


class MessageRequest(BaseModel):
    """Request to send message to Alex."""
    message: str = Field(..., min_length=1, max_length=10000)
    user_id: Optional[str] = Field(None, min_length=1, max_length=128)
    context: Optional[Dict[str, Any]] = None
    typing_speed: Optional[float] = Field(60.0, ge=0.0, le=1000.0)


class StateResponse(BaseModel):
    """Alex's current state."""
    state: str
    battery: str
    engagement_score: float


def _normalize_recent_memories(memories: Any) -> List[Dict[str, Any]]:
    """Normalize Alex memory payloads for API responses across implementations."""
    normalized: List[Dict[str, Any]] = []
    for memory in memories or []:
        if isinstance(memory, dict):
            normalized.append(memory)
            continue
        normalized.append({
            "id": getattr(memory, "id", ""),
            "content": getattr(memory, "content", ""),
            "memory_type": getattr(getattr(memory, "memory_type", None), "value", str(getattr(memory, "memory_type", ""))),
            "timestamp": getattr(getattr(memory, "timestamp", None), "isoformat", lambda: "")(),
            "emotional_tags": getattr(memory, "emotional_tags", getattr(memory, "tags", [])),
        })
    return normalized


# Global alex instance/provider - will be set by main.py
_alex_core = None
_alex_provider = None
_choreo_hook = None

logger = logging.getLogger("pubcast.alex_routes")


def set_choreo_hook(hook):
    """
    Register an async callable(alex, user_id) invoked after each processed
    message. Used to drive affect→choreography modulation without alex_routes
    needing to import main (which would be circular).
    """
    global _choreo_hook
    _choreo_hook = hook


def set_alex_instance(alex_instance):
    """Set the fallback Alex instance (called from main.py)."""
    global _alex_core
    _alex_core = alex_instance


def set_alex_provider(provider):
    """Set a user-aware Alex provider, e.g. AlexJeremyBridge.alex_for."""
    global _alex_provider
    _alex_provider = provider


_alex_backup = None


def set_alex_backup(backup):
    """Attach Alex's backup engine to the existing Alex endpoints."""
    global _alex_backup
    _alex_backup = backup


def _authorized_memory_user(identity: Dict[str, Any], user_id: Optional[str] = None, *, privileged=False) -> str:
    """Backup contents must never be readable through dev-mode anonymous headers."""
    if not identity.get("authenticated"):
        raise HTTPException(401, "Authenticated identity required for memory backup")
    actor = str(identity.get("user_id") or "").strip()
    if not actor:
        raise HTTPException(401, "Authenticated user identity required")
    target = user_id or actor
    if target != actor and not role_gte(str(identity.get("role") or "guest"), "mod"):
        raise HTTPException(403, "Cannot access another user's memories")
    if privileged and not role_gte(str(identity.get("role") or "guest"), "mod"):
        raise HTTPException(403, "Moderator role required")
    return target


def _authorized_alex_user(identity: Dict[str, Any], user_id: Optional[str] = None,
                          *, allow_owner_read: bool = False) -> str:
    """Private Alex Core / memory access always requires a verified identity.

    Never interpret the old shared 'default' user as a public memory bucket.
    The owner may inspect other profiles only on read-only endpoints.
    """
    if not isinstance(identity, dict) or not identity.get('authenticated'):
        raise HTTPException(401, 'Authenticated identity required for Alex')
    actor = str(identity.get('user_id') or '').strip()
    if not actor:
        raise HTTPException(401, 'Authenticated user ID required')
    target = user_id or actor
    if target != actor and not (allow_owner_read and role_gte(str(identity.get('role') or 'guest'), 'owner')):
        raise HTTPException(403, 'Cannot access another user’s Alex session')
    return target


_care_eq = None


def set_care_eq(care):
    """Share one CARE coordinator with Alex routes and the Alex/Jeremy Bridge."""
    global _care_eq
    _care_eq = care


def _own_care_identity(identity: Dict[str, Any], user_id: Optional[str] = None,
                       *, require_owner: bool = False) -> str:
    if not isinstance(identity, dict) or not identity.get("authenticated"):
        raise HTTPException(401, "Authenticated identity required for CARE")
    actor = str(identity.get("user_id") or "").strip()
    if not actor or (user_id is not None and user_id != actor):
        raise HTTPException(403, "CARE scope must match authenticated owner")
    if require_owner and not role_gte(str(identity.get("role") or "guest"), "owner"):
        raise HTTPException(403, "Only the PubCast owner can activate Little Mode")
    return actor


class CareObservationRequest(BaseModel):
    kind: str = Field(..., min_length=1, max_length=64)
    observed: Dict[str, Any] = Field(default_factory=dict)
    hypothesis: Optional[str] = Field(None, max_length=400)
    alternatives: List[str] = Field(default_factory=list, max_length=8)
    outcome: Optional[str] = Field(None, max_length=400)


class CareRoutineSettingsRequest(BaseModel):
    change_talk: Optional[bool] = None
    bottle_talk: Optional[bool] = None
    address_terms: Optional[List[str]] = Field(None, max_length=6)


@router.get("/care/routines")
async def get_care_routines(identity: Dict[str, Any] = Depends(current_identity)):
    owner = _own_care_identity(identity)
    if _care_eq is None:
        raise HTTPException(503, "CARE adapter is not configured")
    return _care_eq.routine_settings(owner)


@router.post("/care/routines")
async def set_care_routines(request: CareRoutineSettingsRequest,
                            identity: Dict[str, Any] = Depends(current_identity)):
    """Owner-only. Turning on change_talk is the owner's standing yes to diaper-change
    talk while in baby mode; it is off by default and can be turned off at any time."""
    owner = _own_care_identity(identity, require_owner=True)
    if _care_eq is None:
        raise HTTPException(503, "CARE adapter is not configured")
    return _care_eq.set_routine_settings(
        owner, change_talk=request.change_talk, bottle_talk=request.bottle_talk,
        address_terms=request.address_terms)


@router.post("/care/activate")
async def activate_care(identity: Dict[str, Any] = Depends(current_identity)):
    user_id = _own_care_identity(identity, require_owner=True)
    if _care_eq is None:
        raise HTTPException(503, "CARE adapter is not configured")
    return _care_eq.activate(user_id)


@router.post("/care/deactivate")
async def deactivate_care(identity: Dict[str, Any] = Depends(current_identity)):
    user_id = _own_care_identity(identity)
    if _care_eq is None:
        raise HTTPException(503, "CARE adapter is not configured")
    return _care_eq.deactivate(user_id)


@router.get("/care/status")
async def care_status(identity: Dict[str, Any] = Depends(current_identity)):
    user_id = _own_care_identity(identity)
    if _care_eq is None:
        raise HTTPException(503, "CARE adapter is not configured")
    return _care_eq.status(user_id)


@router.get("/care/events")
async def care_events(user_id: Optional[str] = Query(None, min_length=1, max_length=128),
                      identity: Dict[str, Any] = Depends(current_identity)):
    owner = _own_care_identity(identity, user_id=user_id)
    if _care_eq is None:
        raise HTTPException(503, "CARE adapter is not configured")
    return _care_eq.export(owner)


@router.post("/care/observe")
async def care_observe(request: CareObservationRequest,
                       identity: Dict[str, Any] = Depends(current_identity)):
    owner = _own_care_identity(identity)
    if _care_eq is None:
        raise HTTPException(503, "CARE adapter is not configured")
    return _care_eq.observe(owner, request.kind, request.observed,
                            request.hypothesis, request.alternatives, request.outcome)


def _resolve_alex(user_id: Optional[str] = None):
    if _alex_provider is not None:
        return _alex_provider(user_id or "default")
    return _alex_core


@router.post("/message")
async def send_message(request: MessageRequest, identity: Dict[str, Any] = Depends(current_identity)):
    """Send a message to Alex and get response."""
    user_id = _authorized_alex_user(identity, request.user_id)
    alex = _resolve_alex(user_id)
    if not alex:
        raise HTTPException(503, "Alex Core not initialized")
    
    try:
        metadata = dict(request.context or {})
        care_facing_text = request.message
        if _care_eq is not None and _care_eq.is_active(user_id):
            owner_id = _own_care_identity(identity, user_id=user_id)
            care_facing_text = _care_eq.receive(owner_id, request.message)
            metadata["care_mode"] = "baby_masked"
        response = await alex.process_message(
            care_facing_text,
            typing_speed=float(request.typing_speed or 60.0),
            metadata=metadata,
            user_id=user_id,
        )

        # Affect → choreography. Best-effort and fully isolated: a failure here
        # must never break the chat response the user is waiting on.
        if _choreo_hook is not None:
            try:
                await _choreo_hook(alex, user_id)
            except Exception as hook_exc:  # noqa: BLE001 - deliberate catch-all
                logger.warning("affect→choreo hook failed (non-fatal): %s", hook_exc)

        return {"response": response, "status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Alex processing error: {e}")


@router.get("/state")
async def get_state(user_id: Optional[str] = Query(None, min_length=1, max_length=128),
                    identity: Dict[str, Any] = Depends(current_identity)):
    """Get an authorized Alex state."""
    target = _authorized_alex_user(identity, user_id, allow_owner_read=True)
    alex = _resolve_alex(target)
    if not alex:
        raise HTTPException(503, "Alex Core not initialized")
    
    try:
        state = alex.get_state()
        return state
    except Exception as e:
        raise HTTPException(500, f"State retrieval error: {e}")


@router.post("/grounding")
async def trigger_grounding(
    user_id: Optional[str] = Query(None, min_length=1, max_length=128),
    identity: Dict[str, Any] = Depends(current_identity),
):
    """Trigger a grounding exercise for the authenticated actor."""
    target = _authorized_alex_user(identity, user_id)
    alex = _resolve_alex(target)
    if not alex:
        raise HTTPException(503, "Alex Core not initialized")
    
    try:
        result = await alex.grounding_check()
        return {"grounding": result, "status": "ok"}
    except Exception as e:
        raise HTTPException(500, f"Grounding error: {e}")


@router.get("/memory/recent")
async def get_recent_memory(limit: int = Query(10, ge=1, le=200),
                            user_id: Optional[str] = Query(None, min_length=1, max_length=128),
                            identity: Dict[str, Any] = Depends(current_identity)):
    """Get authorized recent conversation memory."""
    target = _authorized_alex_user(identity, user_id, allow_owner_read=True)
    alex = _resolve_alex(target)
    if not alex:
        raise HTTPException(503, "Alex Core not initialized")
    
    try:
        memories = alex.get_recent_memories(limit)
        normalized = _normalize_recent_memories(memories)
        return {"memories": normalized, "count": len(normalized)}
    except Exception as e:
        raise HTTPException(500, f"Memory retrieval error: {e}")


@router.get("/backup/status")
async def backup_status(identity: Dict[str, Any] = Depends(current_identity)):
    _authorized_memory_user(identity)
    if _alex_backup is None:
        return {"configured": False}
    return {"configured": True, **_alex_backup.status()}


@router.post("/backup/run")
async def backup_run(user_id: Optional[str] = Query(None, min_length=1, max_length=128),
                     identity: Dict[str, Any] = Depends(current_identity)):
    target = _authorized_memory_user(identity, user_id, privileged=True)
    if _alex_backup is None:
        raise HTTPException(503, "Alex backup is not configured")
    return _alex_backup.backup(target)


@router.get("/backup/search")
async def backup_search(q: str = Query(..., min_length=1, max_length=200),
                        user_id: Optional[str] = Query(None, min_length=1, max_length=128),
                        limit: int = Query(5, ge=1, le=25),
                        identity: Dict[str, Any] = Depends(current_identity)):
    target = _authorized_memory_user(identity, user_id)
    if _alex_backup is None:
        raise HTTPException(503, "Alex backup is not configured")
    return {"results": _alex_backup.search(target, q, limit=limit)}


@router.post("/reset")
async def reset_alex(
    user_id: Optional[str] = Query(None, min_length=1, max_length=128),
    identity: Dict[str, Any] = Depends(require_role("mod")),
):
    """Reset Alex to initial state; never by anonymous dev-mode header."""
    target = _authorized_alex_user(identity, user_id, allow_owner_read=True)
    if not role_gte(str(identity.get('role') or 'guest'), 'mod'):
        raise HTTPException(403, 'Moderator role required')
    alex = _resolve_alex(target)
    if not alex:
        raise HTTPException(503, "Alex Core not initialized")
    
    try:
        alex.reset()
        return {"status": "reset", "message": "Alex has been reset"}
    except Exception as e:
        raise HTTPException(500, f"Reset error: {e}")

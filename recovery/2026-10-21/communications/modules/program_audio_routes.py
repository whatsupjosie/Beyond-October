"""Program audio runtime routes for studio playback state.

This is the server contract for dialogue, music, SFX, UI clicks, VTR, and room
sound state. It does not play audio by itself; browser/runtime clients consume
validated events and this state gives menus and recovery tools a stable truth.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from .program_audio import ProgramAudioState, apply_audio_event, issue_recovery_actions, validate_audio_event
from .route_security import require_role, current_identity
from .auth import role_gte


async def _json_dict(request: Request) -> Dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


def create_program_audio_router(state: Optional[ProgramAudioState] = None, *, blackbox: Any = None, hub: Any = None) -> APIRouter:
    audio_state = state or ProgramAudioState()
    router = APIRouter(prefix="/api/program-audio", tags=["Program Audio"])

    def _record(action: str, actor: str, payload: Dict[str, Any]) -> None:
        if blackbox is not None:
            blackbox.record_event("audio.state", source="system", actor=actor, data={"action": action, **payload})

    @router.get('/events')
    async def audio_events(after: int = -1, identity=Depends(current_identity)):
        if not identity.get('authenticated'):
            raise HTTPException(401, 'Sign in to receive program audio commands')
        result = audio_state.events_after(after)
        from .chat_rooms import role_can_access
        aliases = {'control': 'controlroom', 'waiting_room': 'waitingroom'}
        result['events'] = [event for event in result['events'] if not event.get('room') or
            role_can_access(identity.get('role', 'guest'), aliases.get(event['room'], event['room'])) or
            (role_gte(identity.get('role', 'guest'), 'mod') and not str(event['room']).startswith(('dm____','dmv2_')))]
        return result

    @router.get("/status")
    async def program_audio_status(identity: Dict[str, Any] = Depends(require_role("mod"))):
        status = audio_state.status()
        _record("status", str(identity.get("user_id") or "director"), {"dialogue_active": status["dialogue_active"]})
        return {"ok": True, "status": status, "recovery_actions": issue_recovery_actions()}

    @router.post("/event")
    async def program_audio_event(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        try:
            event = validate_audio_event(body)
            event['authorized_director'] = bool(identity.get('authenticated') and role_gte(identity.get('role', 'guest'), 'mod'))
            if event.get('director_announcement') and not event['authorized_director']:
                raise HTTPException(403, 'Authenticated director required for announcements')
            event['authorized_director'] = bool(event.get('director_announcement') and event['authorized_director'])
            if event.get('room') == 'dressing' and event['action'] == 'play' and not event['authorized_director']:
                raise HTTPException(403, 'Dressing room permits direct director announcements only')
            status = apply_audio_event(audio_state, event)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        _record(
            str(event.get("action") or "status"),
            str(identity.get("user_id") or "director"),
            {
                "bus": str(event.get("bus") or ""),
                "volume": event.get("volume", ""),
                "dialogue_active": status["dialogue_active"],
            },
        )
        event = audio_state.publish(event)
        return {"ok": True, "event": event, "status": status, "delivery": "queued_for_players"}

    @router.post("/recovery/{action_id}")
    async def program_audio_recovery(action_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        if action_id == "program_audio.stop_all":
            status = apply_audio_event(audio_state, {"action": "stop_all"})
        elif action_id == "program_audio.clear_dialogue":
            audio_state.dialogue_active = 0
            audio_state.active_sources["dialogue"] = 0
            status = audio_state.status()
        elif action_id == "program_audio.disable_tts_autoplay":
            status = audio_state.status()
        else:
            raise HTTPException(404, f"Unknown audio recovery action: {action_id}")
        recovery_event = {'action': 'stop_all'} if action_id == 'program_audio.stop_all' else (
            {'action': 'stop', 'bus': 'dialogue'} if action_id == 'program_audio.clear_dialogue' else
            {'action': 'disable_tts_autoplay'})
        audio_state.publish(recovery_event)
        _record("recovery", str(identity.get("user_id") or "director"), {"action_id": action_id, "dialogue_active": status["dialogue_active"]})
        return {"ok": True, "action_id": action_id, "status": status}

    router.state = audio_state  # test/introspection convenience; FastAPI ignores this attr.
    return router


__all__ = ["create_program_audio_router"]

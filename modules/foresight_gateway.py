"""One-origin Foresight adapter for the existing PubCast and optional 2i systems.

The browser never calls a separate localhost port. Characters are served by the
canonical BotManager. Only the distinct legacy 2i utilities are forwarded to an
optional loopback-only sidecar; there is no duplicate character implementation.
"""
from __future__ import annotations

import os
from typing import Callable, Any
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from .character_service import speak_to_character, character_history
from .route_security import current_identity, bound_actor


# The sidecar address is owned by the launcher, not supplied by a user or URL.
def _sidecar_url() -> str | None:
    value = os.environ.get('PUBCAST_2I_BRIDGE_URL', '').strip().rstrip('/')
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        return None
    return value


# Explicit allowlist; an arbitrary host/path proxy would expose internal APIs.
_LEGACY_UTILITIES = {
    ('GET', 'api/thesaurus'),
    ('POST', 'api/claude'),
    ('POST', 'api/manuscript/commit'),
    ('GET', 'api/messages'),
    ('DELETE', 'api/messages/clear'),
}


def _credential_ready(manager, cfg):
    """Only a presence flag; never expose host BYOK secrets to browser clients."""
    if cfg.provider.value == 'ollama':
        return None  # Reachability requires an actual inference attempt.
    get_key = getattr(manager, '_get_api_key', None)
    if not callable(get_key):
        return None
    try:
        return bool(get_key(cfg))
    except Exception:
        return False


def create_foresight_gateway(get_manager: Callable[[], Any], get_hub: Callable[[], Any]) -> APIRouter:
    router = APIRouter(prefix='/api/foresight/bridge', tags=['Foresight integration'])

    @router.get('/health')
    async def health():
        manager = get_manager()
        if manager is None:
            raise HTTPException(503, 'PubCast character bridge not initialized')
        # A normal running Reach host provides the character bridge even if the
        # optional Node utilities were not installed or started.
        status = 'healthy' if manager is not None else 'unavailable'
        legacy = 'disabled'
        base = _sidecar_url()
        if base:
            try:
                async with httpx.AsyncClient(timeout=1.0, trust_env=False) as client:
                    response = await client.get(base + '/health')
                legacy = 'running' if response.is_success else 'unavailable'
            except httpx.HTTPError:
                legacy = 'unavailable'
        return {
            'status': status, 'service': 'Foresight character bridge',
            'uptime': None, 'services': {'character_count': len(manager.list_configs()) if manager else 0,
                                         'legacy_2i_utilities': legacy},
            'environment': {}, 'ok': manager is not None,
        }

    @router.get('/api/chat/characters')
    async def characters(identity=Depends(current_identity)):
        manager = get_manager()
        if manager is None:
            raise HTTPException(503, 'PubCast bot manager not started')
        return {'ok': True, 'characters': [
            {'id': cfg.bot_id, 'name': cfg.name, 'provider': cfg.provider.value,
             'model': cfg.model, 'rooms': list(cfg.rooms),
             'credential_ready': _credential_ready(manager, cfg)}
            for cfg in manager.list_configs()
        ]}

    @router.post('/api/chat/character')
    async def chat(request: Request, identity=Depends(current_identity)):
        if not identity.get('authenticated'):
            raise HTTPException(401, 'Sign in to use private character chat')
        try:
            body = await request.json()
        except (ValueError, TypeError):
            raise HTTPException(400, 'JSON body required')
        if not isinstance(body, dict):
            raise HTTPException(400, 'Object body required')
        bot_id = body.get('character_id')
        message = body.get('message')
        if not isinstance(bot_id, str) or not bot_id or len(bot_id) > 128:
            raise HTTPException(400, 'character_id is required')
        if not isinstance(message, str) or not message.strip() or len(message) > 10000:
            raise HTTPException(400, 'nonempty message required (maximum 10000 characters)')
        room = body.get('room_id', 'studio')
        if not isinstance(room, str) or not room or len(room) > 128:
            raise HTTPException(400, 'invalid room_id')
        user = bound_actor(request=request, identity=identity,
                           explicit_value=body.get('user_id'), field_name='user_id',
                           allow_privileged_override=False)
        result = await speak_to_character(get_manager(), get_hub(), bot_id=bot_id,
                                         message=message, room_id=room, user_id=user)
        return {'ok': True, 'character_id': bot_id,
                'character_name': result['bot_name'], 'provider': result['provider'],
                'model': result['model'], 'room_id': room,
                'message': message, 'reply': result['reply']}

    @router.get('/api/chat/history')
    async def direct_chat_history(character_id: str, room_id: str = 'studio',
                                  identity=Depends(current_identity)):
        # No body/header user selection: authenticated caller owns this archive.
        if not identity.get('authenticated'):
            raise HTTPException(401, 'Sign in to view a private conversation')
        records = await character_history(get_manager(), get_hub(), bot_id=character_id,
                                          room_id=room_id, user_id=identity['user_id'])
        return {'ok': True, 'character_id': character_id, 'messages': records}

    @router.api_route('/{legacy_path:path}', methods=['GET', 'POST', 'DELETE'])
    async def distinct_2i_utilities(legacy_path: str, request: Request,
                                   identity=Depends(current_identity)):
        if (request.method, legacy_path) not in _LEGACY_UTILITIES:
            raise HTTPException(404, 'Unknown 2i operation')
        # Never allow a dev-auth anonymous caller to retrieve messages or
        # initiate provider operations through a privileged localhost proxy.
        if not identity.get('authenticated'):
            raise HTTPException(401, 'Sign in to use 2i utilities')
        # Legacy messages are global, not partitioned by user. Do not offer
        # them to ordinary authenticated guests as if they were private.
        privileged_paths = {'api/messages', 'api/messages/clear',
                            'api/manuscript/commit', 'api/claude'}
        if legacy_path in privileged_paths and identity.get('role') not in ('owner', 'admin'):
            raise HTTPException(403, 'Owner/admin required for legacy utility')
        base = _sidecar_url()
        if not base:
            raise HTTPException(503, 'Optional legacy 2i utilities are not running')
        content = await request.body()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(413, 'Request too large')
        headers = {'Authorization': request.headers.get('authorization', ''),
                   'Content-Type': request.headers.get('content-type', 'application/json')}
        # Never forward cookies, untrusted forwarded headers, or browser origins.
        if request.headers.get('x-admin-key') and request.method == 'DELETE':
            headers['X-Admin-Key'] = request.headers['x-admin-key']
        try:
            async with httpx.AsyncClient(timeout=35, trust_env=False) as client:
                reply = await client.request(request.method, base + '/' + legacy_path,
                                             params=request.query_params, content=content,
                                             headers=headers)
        except httpx.HTTPError as exc:
            raise HTTPException(503, '2i utility service unavailable') from exc
        return Response(content=reply.content, status_code=reply.status_code,
                        media_type=reply.headers.get('content-type', 'application/json'))

    return router

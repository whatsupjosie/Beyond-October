"""Own-copy signing and invited guest admission using existing host governance."""
import asyncio
import json
import math
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from . import auth, userdb
from .auth_routes import _set_ws_session_cookie
from .guest_identity import sign_visit, digest
from .route_security import current_identity


async def _body(request):
    async def receive():
        data = bytearray()
        async for block in request.stream():
            if len(block) > 65536 - len(data):
                raise HTTPException(413, 'Keep visiting requests under 64 KB')
            data.extend(block)
        try:
            result = json.loads(data)
        except (ValueError, UnicodeError):
            raise HTTPException(400, 'A JSON object is required') from None
        if not isinstance(result, dict):
            raise HTTPException(400, 'A JSON object is required')
        return result
    try:
        return await asyncio.wait_for(receive(), 10)
    except asyncio.TimeoutError:
        raise HTTPException(408, 'Visiting request timed out') from None


def create_guest_identity_router(admission, vault):
    router = APIRouter(prefix='/api/guests', tags=['human-visitors'])

    async def owner(identity=Depends(current_identity)):
        profile = await userdb.get_profile_by_username(identity['user_id']) if identity['authenticated'] else None
        if not profile or profile.get('visiting') or profile['role'] != 'owner' or identity['role'] != 'owner':
            raise HTTPException(403, 'The owner of this PubCast copy controls guest admission')
        return profile

    async def call(function, *args):
        try:
            return await run_in_threadpool(function, *args)
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post('/sign')
    async def sign(request: Request, response: Response, profile=Depends(owner)):
        if vault is None:
            raise HTTPException(503, 'The encrypted credential store is unavailable')
        body = await _body(request)
        proof = await call(sign_visit, vault, profile, body.get('challenge'), body.get('consents'))
        response.headers['X-PubCast-Identity-Fingerprint'] = digest(proof['payload']['card']['public_key'])
        return proof

    @router.post('/invites', status_code=201)
    async def invite(request: Request, profile=Depends(owner)):
        body = await _body(request)
        code = await call(admission.invite, body.get('room', 'studio'), body.get('duration', 3600), body.get('max_uses', 1))
        admission.governance._audit('GUEST_INVITE', profile['user_id'], None, 'room=' + body.get('room', 'studio'))
        return {'invite_code': code}

    @router.post('/door')
    async def door(request: Request, profile=Depends(owner)):
        body = await _body(request)
        await call(admission.set_locked, body.get('locked'))
        admission.governance._audit('GUEST_DOOR', profile['user_id'], None, 'locked=' + str(body.get('locked')))
        return {'locked': body['locked']}

    @router.get('/settings')
    async def settings(profile=Depends(owner)):
        return await call(admission.settings)

    @router.post('/challenge')
    async def challenge(request: Request):
        body = await _body(request)
        code = body.get('invite_code')
        if not isinstance(code, str) or len(code) > 128:
            raise HTTPException(400, 'A valid invitation is required')
        return await call(admission.challenge, code, str(request.base_url).rstrip('/'))

    @router.post('/request', status_code=201)
    async def request_entry(request: Request):
        body = await _body(request)
        locals_ = [p['user_id'] for p in await userdb.list_profiles() if not p.get('visiting')]
        entry = await call(admission.submit, body, locals_)
        current = await call(admission.governance.get_waiting_entry, entry)
        return {'entry_id': entry, 'status': current.status.value}

    @router.post('/status')
    async def status(request: Request, response: Response):
        body = await _body(request)
        ticket = body.get('poll_token')
        if not isinstance(ticket, str) or len(ticket) != 43:
            raise HTTPException(400, 'A valid waiting ticket is required')
        result = await call(admission.status, ticket)
        if 'card' not in result:
            return result
        claims = {'sub': result['user_id'], 'role': 'guest', 'guest_host': admission.host_id, 'guest_entry': result['entry_id']}
        if not await call(admission.validate_claims, claims):
            raise HTTPException(403, 'This guest admission is no longer authorized')
        await run_in_threadpool(userdb._sync_save_visiting_profile, result['card'], result['card_at'])
        token = auth.create_access_token(claims, expires_minutes=math.ceil(max(1, result['expires'] - time.time()) / 60))
        _set_ws_session_cookie(response, request, token)
        admission.governance.mark_entered(result['entry_id'])
        return dict(result, access_token=token, username=result['user_id'], role='guest', token_type='bearer')

    @router.get('/pending')
    async def pending(profile=Depends(owner)):
        return {'pending': await call(admission.pending)}

    @router.post('/entries/{entry_id}/approve')
    async def approve(entry_id: str, request: Request, profile=Depends(owner)):
        body = await _body(request)
        pending = {p['entry_id']: p for p in await call(admission.pending)}
        if entry_id not in pending:
            raise HTTPException(404, 'No verified waiting request')
        if body.get('fingerprint') != pending[entry_id]['fingerprint']:
            raise HTTPException(409, 'Review the visitor identity key before approval')
        result = await call(admission.governance.approve_entry, entry_id, profile['user_id'])
        if result is None:
            raise HTTPException(409, 'This request was already decided')
        return {'status': result.status.value}

    @router.post('/entries/{entry_id}/deny')
    async def deny(entry_id: str, profile=Depends(owner)):
        result = await call(admission.governance.deny_entry, entry_id, profile['user_id'])
        if result is None:
            raise HTTPException(404, 'No pending request')
        return {'status': result.status.value}

    @router.post('/entries/{entry_id}/revoke')
    async def revoke(entry_id: str, profile=Depends(owner)):
        await call(admission.revoke, entry_id)
        admission.governance._audit('GUEST_REVOKE', profile['user_id'], None, 'entry=' + entry_id)
        return {'revoked': True}

    return router

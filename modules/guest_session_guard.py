"""Recheck a visiting lease before each live socket frame, including idle receivers.

Route-level identity checks still own room/role policy. This transport fence only
ensures a revoked or expired visiting lease cannot keep receiving or publishing
through a socket it opened earlier. Local owner sessions retain existing policy.
"""
import json
from http.cookies import SimpleCookie
from urllib.parse import parse_qs

from starlette.websockets import WebSocketDisconnect

from . import auth


class GuestSessionGuardMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'websocket':
            return await self.app(scope, receive, send)
        guest_token = None
        closed = False

        def observe(token):
            nonlocal guest_token
            if not isinstance(token, str) or not token:
                return
            try:
                claims = auth._jwt_decode(token, auth._SECRET_KEY)
            except Exception:
                return  # The route will reject an invalid authentication attempt.
            if 'guest_entry' in claims or 'guest_host' in claims:
                guest_token = token

        headers = dict(scope.get('headers', []))
        header = headers.get(b'authorization', b'').decode('latin1')
        if header.lower().startswith('bearer '):
            observe(header[7:].strip())
        cookies = SimpleCookie()
        try:
            cookies.load(headers.get(b'cookie', b'').decode('latin1'))
        except Exception:
            pass
        if auth.WS_SESSION_COOKIE in cookies:
            observe(cookies[auth.WS_SESSION_COOKIE].value)
        for token in parse_qs(scope.get('query_string', b'').decode('latin1')).get('token', []):
            observe(token)  # Routes still reject this transport unless explicitly enabled.

        async def close():
            nonlocal closed
            if not closed:
                closed = True
                await send({'type': 'websocket.close', 'code': 1008, 'reason': 'Guest admission expired or revoked'})

        async def guarded_receive():
            event = await receive()
            if event['type'] == 'websocket.receive':
                # The walker has a first-message authentication transport too.
                text = event.get('text')
                if guest_token is None and isinstance(text, str) and len(text) <= 16384:
                    try:
                        data = json.loads(text)
                        if isinstance(data, dict):
                            observe(data.get('token'))
                    except ValueError:
                        pass
                if guest_token is not None and auth.decode_access_token(guest_token) is None:
                    await close()
                    return {'type': 'websocket.disconnect', 'code': 1008}
            return event

        async def guarded_send(event):
            if event['type'] in {'websocket.accept', 'websocket.send'} and guest_token is not None:
                if closed or auth.decode_access_token(guest_token) is None:
                    await close()
                    raise WebSocketDisconnect(code=1008)
            await send(event)

        try:
            await self.app(scope, guarded_receive, guarded_send)
        except WebSocketDisconnect:
            if not closed:
                raise

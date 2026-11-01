"""Reject JSON request bodies that cannot be stored as UTF-8.

A JSON string may legally contain an unpaired surrogate escape such as ``"\\ud800"``.
It decodes to a Python ``str`` that can never be encoded as UTF-8, so it detonates
later - when a store writes it, or when FastAPI echoes it back inside a 422 body -
and the caller sees an opaque 500. Roughly fifty routes did exactly that.

This pure-ASGI guard turns that into one clear 400 at the door. It looks only at
JSON request bodies, buffers at most ``MAX_INSPECT`` bytes, and replays the stream
untouched to the application, so it never changes a valid request.
"""
from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

MAX_INSPECT = 4 * 1024 * 1024
_ESCAPE = re.compile(r"\\(?:u([0-9a-fA-F]{4})|.)", re.DOTALL)
_DETAIL = b'{"detail":"text contains invalid Unicode (unpaired surrogate or invalid UTF-8)"}'


def body_has_invalid_unicode(body: bytes) -> bool:
    """True if ``body`` is not valid UTF-8 or holds an unpaired surrogate escape."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return True
    if "\\" not in text:
        return False
    pending = False
    prev_end = -1
    for match in _ESCAPE.finditer(text):
        if pending and match.start() != prev_end:
            return True
        hex4 = match.group(1)
        if hex4:
            code = int(hex4, 16)
            if 0xD800 <= code <= 0xDBFF:
                if pending:
                    return True
                pending = True
            elif 0xDC00 <= code <= 0xDFFF:
                if not pending:
                    return True
                pending = False
            elif pending:
                return True
        elif pending:
            return True
        prev_end = match.end()
    return pending


class UnicodeGuardMiddleware:
    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http" or not _is_json(scope):
            await self.app(scope, receive, send)
            return
        buffered: list[dict[str, Any]] = []
        chunks: list[bytes] = []
        total = 0
        complete = False
        while total <= MAX_INSPECT:
            message = await receive()
            buffered.append(message)
            if message["type"] != "http.request":
                break
            chunk = message.get("body", b"")
            chunks.append(chunk)
            total += len(chunk)
            if not message.get("more_body", False):
                complete = True
                break
        if complete and body_has_invalid_unicode(b"".join(chunks)):
            await send({"type": "http.response.start", "status": 400,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"content-length", str(len(_DETAIL)).encode())]})
            await send({"type": "http.response.body", "body": _DETAIL})
            return

        async def replay() -> dict[str, Any]:
            if buffered:
                return buffered.pop(0)
            return await receive()

        await self.app(scope, replay, send)


def _is_json(scope: dict) -> bool:
    for name, value in scope.get("headers", ()):
        if name == b"content-type":
            return b"json" in value.lower()
    return False

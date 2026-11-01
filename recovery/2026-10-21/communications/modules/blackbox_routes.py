"""Operator-only BlackBox status routes.

These routes do not expose record contents. They let the operator confirm the
external BlackBox witness is alive and verify the hash chain from outside the
player menu surface.
"""
from __future__ import annotations

from typing import Any, Dict

import asyncio
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from .route_security import current_identity, authorize_websocket
from .auth import role_gte

from .blackbox_runtime import BlackBoxRuntimeWitness
from .route_security import require_role


class PreserveRequest(BaseModel):
    capture_id: str = Field(min_length=32, max_length=32, pattern=r'^[a-f0-9]+$')
    start_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    end_seconds: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    start_at: datetime | None = None
    end_at: datetime | None = None

    @model_validator(mode='after')
    def unambiguous_range(self):
        samples = self.start_seconds is not None and self.end_seconds is not None
        clock = self.start_at is not None and self.end_at is not None
        if samples == clock or (samples and (self.start_at is not None or self.end_at is not None)) or (clock and (self.start_seconds is not None or self.end_seconds is not None)):
            raise ValueError('Specify either start/end seconds or complete start/end datetimes')
        if clock and (self.start_at.utcoffset() is None or self.end_at.utcoffset() is None):
            raise ValueError('Both datetimes require explicit timezone offsets')
        return self


async def capture_operator(identity=Depends(current_identity)):
    # This transport is never an anonymous dev upload surface, including when
    # the older compatibility routes run with relaxed authentication.
    if not identity.get('authenticated') or not role_gte(identity.get('role', 'guest'), 'mod'):
        raise HTTPException(403, 'Authenticated control-room operator required')
    return identity


def create_blackbox_router(witness: BlackBoxRuntimeWitness) -> APIRouter:
    router = APIRouter(prefix="/api/operator/blackbox", tags=["BlackBox Operator Boundary"])

    @router.get('/health')
    async def health(identity=Depends(current_identity)):
        if not identity.get('authenticated'):
            raise HTTPException(401, 'Sign in to inspect Blackbox health')
        return witness.health()

    @router.post('/save')
    async def save(identity=Depends(capture_operator)):
        command_id = uuid.uuid4().hex
        try:
            result = await asyncio.to_thread(witness.media.save)
            if not witness.record_event('blackbox.saved', actor=identity['user_id'], data={'command_id': command_id}):
                raise OSError('Save audit receipt could not be committed')
            return {**result, 'command_id': command_id}
        except (OSError, ValueError) as exc:
            raise HTTPException(503, 'Blackbox save failed') from exc

    @router.post('/preserve')
    async def preserve(body: PreserveRequest, identity=Depends(capture_operator)):
        command_id = uuid.uuid4().hex
        try:
            start, end = body.start_seconds, body.end_seconds
            if body.start_at is not None:
                sink = witness.media.captures.get(body.capture_id)
                if sink is None:
                    raise ValueError('Unknown capture_id')
                start = body.start_at.timestamp() - sink.started_at
                end = body.end_at.timestamp() - sink.started_at
            result = await asyncio.to_thread(witness.media.preserve, body.capture_id, start, end)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(503, 'Blackbox preservation failed') from exc
        if not witness.record_event('blackbox.preserved', actor=identity['user_id'], data={**result, 'command_id': command_id}):
            raise HTTPException(503, 'Copy created but audit receipt could not be committed')
        return {**result, 'command_id': command_id}

    @router.websocket('/capture')
    async def capture(ws: WebSocket):
        identity = await authorize_websocket(ws, 'guest')
        if identity is None:
            return
        if not identity.get('authenticated') or not role_gte(identity.get('role', 'guest'), 'mod'):
            await ws.close(code=1008, reason='Authenticated control-room source required')
            return
        origin = ws.headers.get('origin')
        if origin and origin not in {f"http://{ws.headers.get('host')}", f"https://{ws.headers.get('host')}"}:
            await ws.close(code=1008, reason='Same-origin capture required')
            return
        await ws.accept()
        sink = None
        clean = False
        try:
            config = await asyncio.wait_for(ws.receive_json(), timeout=10)
            if config.get('source') != 'control-room-mix' or config.get('encoding') != 'pcm-s16le':
                raise ValueError('Only live control-room PCM capture is accepted')
            if not witness.enabled or witness._closed:
                raise ValueError('Blackbox is inactive')
            sink = await asyncio.to_thread(witness.media.start, int(config.get('sample_rate', 0)), int(config.get('channels', 0)))
            witness.record_event('capture.started', actor=identity['user_id'], data=sink.status())
            await ws.send_json({'ok': True, 'capture_id': sink.id})
            while True:
                packet = await asyncio.wait_for(ws.receive(), timeout=10)
                if packet['type'] == 'websocket.disconnect':
                    break
                if packet.get('text') == 'stop':
                    clean = True
                    break
                data = packet.get('bytes')
                if data is None:
                    raise ValueError('Expected PCM audio packet')
                projected = (sink.frames + len(data) / (sink.channels * 2)) / sink.rate
                elapsed = time.time() - sink.started_at
                if projected > elapsed + 2 or elapsed - projected > 3:
                    raise ValueError('Capture lost its live sample clock')
                frames = await asyncio.to_thread(sink.append, data)
                await ws.send_json({'ok': True, 'capture_id': sink.id, 'frames': frames})
        except WebSocketDisconnect:
            pass
        except (ValueError, TypeError, OSError, asyncio.TimeoutError):
            if sink is not None:
                sink.error = 'Capture transport failed'
            try:
                await ws.close(code=1011, reason='Capture failed; committed audio retained')
            except RuntimeError:
                pass
        finally:
            if sink is not None:
                if not clean:
                    sink.error = sink.error or 'Capture disconnected without final stop'
                await asyncio.to_thread(sink.close)
                witness.record_event('capture.stopped', actor=identity['user_id'], data={**sink.status(), 'clean': clean})
            try:
                await ws.close()
            except RuntimeError:
                pass

    @router.get("/status")
    async def blackbox_status(identity: Dict[str, Any] = Depends(require_role("mod"))):
        actor = str(identity.get("user_id") or "operator")
        witness.access(actor=actor, access="status", scope=witness.session_id, reason="status_check")
        status = witness.status()
        return {
            "enabled": status.enabled,
            "session_id": status.session_id,
            "path": status.path,
            "next_seq": status.next_seq,
            "previous_hash": status.previous_hash,
            "compute_budget_percent": status.compute_budget_percent,
            "player_menu_exposed": False,
            "record_contents_exposed": False,
        }

    @router.get("/verify")
    async def blackbox_verify(identity: Dict[str, Any] = Depends(require_role("mod"))):
        actor = str(identity.get("user_id") or "operator")
        witness.access(actor=actor, access="verify", scope=witness.session_id, reason="hash_chain_verify")
        result = witness.verify()
        return {"ok": result.ok, "checked": result.checked, "errors": result.errors}

    return router


__all__ = ["create_blackbox_router"]

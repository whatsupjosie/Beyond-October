"""Explicit one-way participant audio into the canonical browser program mixer.

Authenticated same-origin WebSockets relay bounded, ordered mono PCM frames.
Invitations and per-browser capabilities are ephemeral; no private-room capture.
Single application worker, matching the existing camera manager architecture.
"""
from __future__ import annotations
import asyncio
import json
import secrets
import struct
import time
from dataclasses import dataclass, field
from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from .auth import role_gte
from .route_security import current_identity, authorize_websocket


class Join(BaseModel):
    consent: bool


@dataclass
class Peer:
    actor: str
    key: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    seen: float = field(default_factory=time.monotonic)
    socket: WebSocket | None = None


@dataclass
class Room:
    host: str
    peers: dict[str, Peer]
    sample_rate: int = 0
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def create_participant_audio_router(*, clock=time.monotonic):
    router = APIRouter(prefix='/api/participant-audio', tags=['Participant Audio'])
    rooms: dict[str, Room] = {}
    lease = 20

    def prune():
        for rid, room in list(rooms.items()):
            if clock() - room.peers[room.host].seen > lease:
                del rooms[rid]
            # Connected sockets manage their own receive deadlines. Unused
            # reservations expire; an abandoned invitation cannot fill the desk.
            else:
                for pid, peer in list(room.peers.items()):
                    if pid != room.host and peer.socket is None and clock() - peer.seen > lease:
                        del room.peers[pid]

    def authenticated(identity):
        if not identity.get('authenticated'):
            raise HTTPException(401, 'Sign in to contribute production audio')

    def get_room(rid):
        prune()
        if rid not in rooms:
            raise HTTPException(404, 'Audio desk closed or invitation expired')
        return rooms[rid]

    def authorize(room, pid, key, identity):
        authenticated(identity)
        peer = room.peers.get(pid)
        if not peer or peer.actor != identity['user_id'] or not secrets.compare_digest(peer.key, key):
            raise HTTPException(404, 'Audio connection not found')
        peer.seen = clock()
        return peer

    def reservation(rid, pid, peer):
        return {'room': rid, 'peer': pid, 'key': peer.key, 'lease_seconds': lease}

    async def to_host(room, message):
        host = room.peers[room.host].socket
        if host is None:
            raise ValueError('Audio desk is not listening')
        async with room.send_lock:
            if isinstance(message, bytes):
                await asyncio.wait_for(host.send_bytes(message), 1)
            else:
                await asyncio.wait_for(host.send_json(message), 1)

    async def close_room(rid):
        room = rooms.pop(rid, None)
        if room:
            for peer in list(room.peers.values()):
                if peer.socket:
                    try:
                        await asyncio.wait_for(peer.socket.close(code=1000), 1)
                    except (Exception, asyncio.CancelledError):
                        pass

    @router.post('/rooms', status_code=201)
    async def open_desk(identity=Depends(current_identity)):
        authenticated(identity)
        if not role_gte(identity['role'], 'mod'):
            raise HTTPException(403, 'Director role required to receive production audio')
        prune()
        if len(rooms) >= 16:
            raise HTTPException(429, 'Audio desk capacity reached')
        rid, pid = secrets.token_urlsafe(24), secrets.token_hex(16)
        peer = Peer(str(identity['user_id']), seen=clock())
        rooms[rid] = Room(pid, {pid: peer})
        return reservation(rid, pid, peer)

    @router.post('/rooms/{rid}/peers', status_code=201)
    async def join(rid: str, body: Join, identity=Depends(current_identity)):
        authenticated(identity)
        if not body.consent:
            raise HTTPException(400, 'Consent to send and record microphone audio is required')
        room = get_room(rid)
        if not room.sample_rate or room.peers[room.host].socket is None:
            raise HTTPException(409, 'Audio desk is not ready to receive microphones')
        if len(room.peers) >= 9:
            raise HTTPException(429, 'Eight participant audio inputs are already connected')
        pid = secrets.token_hex(16)
        peer = Peer(str(identity['user_id']), seen=clock())
        room.peers[pid] = peer
        return {**reservation(rid, pid, peer), 'host': room.host, 'sample_rate': room.sample_rate}

    @router.delete('/rooms/{rid}/peers/{pid}')
    async def leave(rid: str, pid: str, x_audio_key: str = Header(default=''), identity=Depends(current_identity)):
        room = get_room(rid)
        peer = authorize(room, pid, x_audio_key, identity)
        if pid == room.host:
            await close_room(rid)
        elif peer.socket:
            await peer.socket.close(code=1000)
        else:
            del room.peers[pid]
        return {'ok': True}

    @router.websocket('/rooms/{rid}/peers/{pid}/media')
    async def media(ws: WebSocket, rid: str, pid: str):
        identity = await authorize_websocket(ws)
        if not identity or not identity.get('authenticated'):
            if identity:
                await ws.close(code=1008)
            return
        if ws.headers.get('origin') not in {f'http://{ws.headers.get("host")}', f'https://{ws.headers.get("host")}'}:
            await ws.close(code=1008, reason='Same-origin contribution required')
            return
        await ws.accept()
        room = peer = None
        try:
            hello_text = await asyncio.wait_for(ws.receive_text(), 5)
            if len(hello_text) > 2048:
                raise ValueError('Audio capability message is too large')
            hello = json.loads(hello_text)
            if not isinstance(hello, dict):
                raise ValueError('Invalid audio capability message')
            room = get_room(rid)
            peer = authorize(room, pid, str(hello.get('key', ''))[:128], identity)
            if peer.socket is not None:
                raise ValueError('This audio connection is already in use')
            rate = hello.get('sample_rate', 0)
            if type(rate) is not int or rate not in (8000,16000,22050,24000,32000,44100,48000,88200,96000,192000):
                raise ValueError('Unsupported microphone sample rate')
            if pid == room.host:
                room.sample_rate = rate
            elif rate != room.sample_rate:
                raise ValueError('Microphone clock does not match production sample rate')
            peer.socket = ws
            if pid != room.host:
                await to_host(room, {'type':'source', 'peer':pid, 'actor':peer.actor, 'sample_rate':rate})
            await ws.send_json({'ok':True})
            sequence = 0
            window, count = clock(), 0
            while True:
                packet = await asyncio.wait_for(ws.receive(), lease)
                if packet['type'] == 'websocket.disconnect':
                    break
                if rooms.get(rid) is not room:
                    raise ValueError('Audio desk closed')
                peer.seen = clock()
                if packet.get('text') == 'ping':
                    continue
                if pid == room.host and packet.get('text') and len(packet['text']) <= 100:
                    control = json.loads(packet['text'])
                    if not isinstance(control, dict):
                        raise ValueError('Invalid audio control message')
                    target = room.peers.get(control.get('drop'))
                    if target and target is not peer and target.socket:
                        await asyncio.wait_for(target.socket.close(code=1000), 1)
                        continue
                    raise ValueError('Invalid source disconnect')
                data = packet.get('bytes')
                if pid == room.host or not data or not 6 <= len(data) <= 16388 or (len(data)-4)%2:
                    raise ValueError('Invalid microphone frame')
                if struct.unpack_from('<I',data)[0] != sequence:
                    raise ValueError('Microphone frame sequence lost')
                sequence += 1
                if clock()-window >= 1:
                    window, count = clock(), 0
                count += len(data)
                if count > rate*2*1.2+32768:
                    raise ValueError('Microphone rate exceeds its bound')
                await to_host(room, bytes.fromhex(pid)+data)
        except (WebSocketDisconnect, asyncio.TimeoutError, HTTPException, ValueError, RuntimeError, KeyError, TypeError):
            pass
        finally:
            # A rejected duplicate must not remove the first connection.
            if room and peer and peer.socket is ws:
                peer.socket = None
                if pid == room.host:
                    await close_room(rid)
                else:
                    room.peers.pop(pid, None)
                    try:
                        await to_host(room, {'type':'left','peer':pid})
                    except (Exception, asyncio.CancelledError):
                        pass
            try:
                await ws.close(code=1000)
            except RuntimeError:
                pass
    return router

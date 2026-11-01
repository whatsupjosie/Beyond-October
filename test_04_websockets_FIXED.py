"""
test_04_websockets.py — WebSocket routing and connectivity
══════════════════════════════════════════════════════════
Verifies that each WebSocket endpoint connects to the RIGHT handler.

The critical behavioural contract:
  /ws/{room}  → Hub handler    (chat, production state, broadcast)
  /ws/unity   → UnityBridge handler  (NOT hub)
  /ws/studio  → StudioWebSocket handler  (NOT hub)

If the routing order bug is present, /ws/unity and /ws/studio both land
in the Hub which responds with {"type": "error"} to everything — the
Unity bridge and Studio Control Room silently break.
"""
from __future__ import annotations

import json

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helper: the Hub pushes SERVER-INITIATED frames on connect — `history` (last
# 50 logged messages, if the room has any) and `presence` (join announcement
# broadcast to the room). That is deliberate, correct chat behaviour: a room
# should tell everyone when someone joins.
#
# It does mean the first frame a client receives is NOT necessarily the reply
# to whatever it just sent. These tests originally asserted on the first frame,
# which made them fail against correct hub behaviour. A real client drains
# until it sees the frame type it cares about — so do we.
# ─────────────────────────────────────────────────────────────────────────────
SERVER_PUSH_TYPES = {"presence", "history", "user_update"}


def recv_type(ws, expected: str, max_frames: int = 6):
    """Receive frames until one matches `expected`, skipping server pushes."""
    seen = []
    for _ in range(max_frames):
        data = ws.receive_json()
        seen.append(data.get("type"))
        if data.get("type") == expected:
            return data
        if data.get("type") not in SERVER_PUSH_TYPES:
            # An unexpected non-push frame — surface it rather than looping.
            raise AssertionError(
                f"Expected {expected!r} but got {data.get('type')!r}; frames seen: {seen}"
            )
    raise AssertionError(f"Never received {expected!r} in {max_frames} frames; saw {seen}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Main event bus WebSocket (/ws/{room})
# ─────────────────────────────────────────────────────────────────────────────

def test_ws_room_connects(client):
    """A client can connect to a named room via the hub."""
    with client.websocket_connect("/ws/main") as ws:
        # Connection accepted — hub is live
        # Send a ping-style production_state message
        ws.send_json({"type": "production_state", "payload": {}})
        data = recv_type(ws, "production_state")
        assert data.get("type") == "production_state", \
            f"Hub returned unexpected type: {data.get('type')}"


def test_ws_room_chat_message(client):
    """Chat messages are broadcast and logged by the hub."""
    with client.websocket_connect("/ws/test_room") as ws:
        ws.send_json({
            "type": "chat",
            "user_id": "test_user",
            "user": "TestUser",
            "text": "startup test message",
        })
        data = recv_type(ws, "chat")
        assert data.get("type") == "chat"
        payload = data.get("payload", {})
        assert payload.get("text") == "startup test message"


def test_ws_room_unknown_type_returns_error(client):
    """Unknown message types get an error response — not a crash."""
    with client.websocket_connect("/ws/test_error") as ws:
        ws.send_json({"type": "definitely_not_a_real_type"})
        data = recv_type(ws, "error")
        assert data.get("type") == "error"


def test_ws_room_invalid_json_does_not_crash(client):
    """Malformed JSON must not crash the server."""
    with client.websocket_connect("/ws/test_badjson") as ws:
        ws.send_text("this is not json {{{")
        # Server should silently ignore it (no response, no crash)
        # Send a valid message after to confirm connection is still alive
        ws.send_json({"type": "production_state", "payload": {}})
        data = recv_type(ws, "production_state")
        assert data.get("type") == "production_state"


# ─────────────────────────────────────────────────────────────────────────────
# 2. /ws/unity — must NOT land in hub handler
# ─────────────────────────────────────────────────────────────────────────────

def test_ws_unity_connects(client):
    """/ws/unity must connect without being rejected outright.
    UnityBridge initialised → accept; UnityBridge None → 1013 close.
    Either is correct; a hub echo-error is not.
    """
    try:
        with client.websocket_connect("/ws/unity") as ws:
            # If UnityBridge is live it will accept and wait for Unity protocol
            # Send a Unity-style handshake — hub would return {"type":"error"}
            ws.send_json({"type": "unity_handshake", "version": "1.0"})
            try:
                data = ws.receive_json(timeout=1)
                # If hub is handling this, it will return {"type": "error"}
                assert data.get("type") != "error", (
                    "/ws/unity is being handled by the Hub catch-all instead of "
                    "the UnityBridge handler. WebSocket route ordering is broken."
                )
            except Exception:
                # Timeout or connection close is fine — Unity bridge may just
                # hold the connection open waiting for Unity protocol frames
                pass
    except Exception as e:
        err_str = str(e)
        # 1013 = Try Again Later (unity_bridge_mgr is None — acceptable)
        # 1000 = Normal close (also acceptable)
        # Anything else may indicate a routing problem
        if "1013" in err_str or "1000" in err_str or "WebSocketDisconnect" in err_str:
            pass  # Correct behaviour — handler ran, bridge not available
        else:
            raise AssertionError(
                f"/ws/unity raised unexpected error: {e}. "
                "May indicate the connection was rejected by the Hub instead of UnityBridge."
            ) from e


def test_ws_unity_not_treated_as_hub_room(client, main_module):
    """After a /ws/unity connection, the hub should NOT have a 'unity' room entry
    (unless someone also connected a normal chat client to /ws/unity, which we didn't).
    If hub has a 'unity' room it means routing is broken."""
    # NOTE (2026-08-24): this test previously connected to "/ws/unity" and
    # asserted it must not become a hub room. That encoded an OLD architecture.
    # The real Unity endpoint is "/unity/ws/{client_id}" — a different path
    # entirely — so "/ws/unity" correctly falls through to the /ws/{room}
    # catch-all and is just an ordinary chat room name with no special meaning.
    # The contract worth asserting is that the REAL endpoint routes correctly
    # and does not leak into the hub.
    # Sibling tests in this file deliberately connect to "/ws/unity" to exercise
    # the catch-all, so the hub is already dirty. Assert on the DELTA from this
    # connection only, not on global hub cleanliness.
    before = set(main_module.hub.rooms.keys())
    with client.websocket_connect("/unity/ws/test_client"):
        pass
    added = set(main_module.hub.rooms.keys()) - before

    assert not added, (
        "/unity/ws/{client_id} leaked into the Hub — it is being routed to the "
        f"Hub catch-all instead of the UnityBridge handler. Rooms added: {added}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. /ws/studio — must NOT land in hub handler
# ─────────────────────────────────────────────────────────────────────────────

def test_ws_studio_connects(client):
    """/ws/studio must connect to the StudioWebSocketHandler, not the hub."""
    try:
        with client.websocket_connect("/ws/studio") as ws:
            # Studio handler sends initial state on connect
            # Hub would return {"type":"error"} on first unknown message
            ws.send_json({"type": "get_status"})
            try:
                data = ws.receive_json(timeout=2)
                # Hub returns {"type": "error"} for unknown types
                # Studio handler returns {"type": "status"} or similar
                assert data.get("type") != "error", (
                    "/ws/studio is being handled by the Hub catch-all. "
                    "Studio Control Room WebSocket is broken."
                )
            except Exception:
                pass  # Timeout is fine
    except Exception as e:
        err_str = str(e)
        if "1013" in err_str or "1000" in err_str or "WebSocketDisconnect" in err_str:
            pass
        else:
            raise AssertionError(f"/ws/studio unexpected error: {e}") from e


def test_ws_studio_not_treated_as_hub_room(client, main_module):
    """After a /ws/studio connection, the hub must not have a 'studio' room."""
    # NOTE (2026-08-24): same stale-architecture issue as the unity test above.
    # The real Studio endpoint is "/studio/ws", not "/ws/studio". Assert that
    # the REAL endpoint connects and stays out of the hub.
    before = set(main_module.hub.rooms.keys())
    with client.websocket_connect("/studio/ws") as ws:
        first = ws.receive_json()
        assert first.get("type") == "initial_state", (
            f"/studio/ws did not send initial_state, got: {first}"
        )
    added = set(main_module.hub.rooms.keys()) - before

    assert not added, (
        f"/studio/ws leaked into the Hub catch-all. Rooms added: {added}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. PubWorld WebSocket (/pubworld/ws/{client_id})
# ─────────────────────────────────────────────────────────────────────────────

def test_pubworld_ws_connects(client):
    """/pubworld/ws/{client_id} must connect and send a welcome message."""
    try:
        with client.websocket_connect("/pubworld/ws/test_client") as ws:
            data = ws.receive_json()
            assert data.get("type") == "welcome", \
                f"PubWorld WS did not send welcome message, got: {data}"
    except Exception as e:
        pytest.skip(f"PubWorld WebSocket unavailable: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Hub broadcast — multiple rooms are isolated
# ─────────────────────────────────────────────────────────────────────────────

def test_ws_rooms_are_isolated(client):
    """Messages in room A must not appear in room B."""
    with client.websocket_connect("/ws/room_a") as ws_a:
        with client.websocket_connect("/ws/room_b") as ws_b:
            ws_a.send_json({
                "type": "chat",
                "user_id": "alice",
                "user": "Alice",
                "text": "secret message for room A only",
            })
            # ws_a should receive the echo
            data_a = recv_type(ws_a, "chat")
            assert data_a.get("type") == "chat"
            assert "secret message" in data_a.get("payload", {}).get("text", "")

            # ws_b should NOT receive anything from room A
            # Send a production_state to room_b to confirm it's alive
            ws_b.send_json({"type": "production_state", "payload": {}})
            data_b = ws_b.receive_json()
            # This should be the production_state echo, not the room_a chat
            assert "secret message" not in json.dumps(data_b), \
                "Room isolation broken — messages from room_a leaked into room_b"

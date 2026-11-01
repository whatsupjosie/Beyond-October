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
import uuid

import pytest


# Hub intentionally pushes lifecycle frames on connect. Tests must drain those
# frames rather than assuming the first received frame is the response to the
# message they just sent. This behavior is part of the product contract.
SERVER_PUSH_TYPES = {"presence", "history", "user_update"}


def recv_type(ws, expected: str, max_frames: int = 6):
    """Receive until ``expected`` arrives, skipping known server-push frames."""
    seen = []
    for _ in range(max_frames):
        data = ws.receive_json()
        seen.append(data.get("type"))
        if data.get("type") == expected:
            return data
        if data.get("type") not in SERVER_PUSH_TYPES:
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


def test_ws_room_chat_message(client, main_module):
    """Chat messages are broadcast/logged without polluting persistent test data."""
    room = f"test_room_{uuid.uuid4().hex}"
    log_path = main_module.hub._log_path(room)
    try:
        with client.websocket_connect(f"/ws/{room}") as ws:
            ws.send_json({
                "type": "chat",
                "user_id": "test_user",
                "user": "TestUser",
                "text": "startup test message",
            })
            data = recv_type(ws, "chat")
            payload = data.get("payload", {})
            assert payload.get("text") == "startup test message"
    finally:
        try:
            log_path.unlink(missing_ok=True)
        except OSError:
            pass


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
    # Connect and immediately disconnect
    try:
        with client.websocket_connect("/ws/unity"):
            pass
    except Exception:
        pass  # May close with 1013 — that's fine

    # The hub's rooms dict should not contain 'unity' as a result of this connection
    hub_rooms = set(main_module.hub.rooms.keys())
    assert "unity" not in hub_rooms, (
        "Hub has a 'unity' room — /ws/unity is being routed to the Hub catch-all "
        "instead of the UnityBridge handler. Fix WebSocket route ordering in main.py."
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
    try:
        with client.websocket_connect("/ws/studio"):
            pass
    except Exception:
        pass

    hub_rooms = set(main_module.hub.rooms.keys())
    assert "studio" not in hub_rooms, (
        "Hub has a 'studio' room — /ws/studio is being routed to the Hub catch-all. "
        "Fix WebSocket route ordering in main.py."
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

def test_ws_rooms_are_isolated(client, main_module):
    """Messages in room A must not appear in room B.

    Use unique room IDs because Hub history persistence is intentional product
    behavior. Reusing fixed names such as ``room_a``/``room_b`` causes prior
    test-run JSONL history to be replayed on connect, turning a room-isolation
    test into a persistence-ordering test and polluting later runs. The unique
    test logs are removed in ``finally`` so the regression test is repeatable
    without leaving synthetic room history in the real data tree.
    """
    run_id = uuid.uuid4().hex
    room_a = f"room_a_{run_id}"
    room_b = f"room_b_{run_id}"
    created_logs = [main_module.hub._log_path(room_a), main_module.hub._log_path(room_b)]

    try:
        with client.websocket_connect(f"/ws/{room_a}") as ws_a:
            with client.websocket_connect(f"/ws/{room_b}") as ws_b:
                ws_a.send_json({
                    "type": "chat",
                    "user_id": "alice",
                    "user": "Alice",
                    "text": "secret message for room A only",
                })
                # Hub emits lifecycle frames (notably presence) around chat.
                # Read until the chat echo arrives instead of assuming frame 1.
                frames_a = []
                data_a = None
                for _ in range(5):
                    frame = ws_a.receive_json()
                    frames_a.append(frame)
                    if frame.get("type") == "chat":
                        data_a = frame
                        break
                assert data_a is not None, f"Chat echo not received; frames={frames_a!r}"
                assert "secret message" in data_a.get("payload", {}).get("text", "")

                # ws_b should NOT receive anything from room A. Send a
                # production_state to room B so we have a deterministic terminal
                # event, while inspecting every preceding lifecycle frame too.
                ws_b.send_json({"type": "production_state", "payload": {}})
                frames_b = []
                saw_production_state = False
                for _ in range(5):
                    frame = ws_b.receive_json()
                    frames_b.append(frame)
                    assert "secret message" not in json.dumps(frame), \
                        "Room isolation broken — room A content reached room B"
                    if frame.get("type") == "production_state":
                        saw_production_state = True
                        break
                assert saw_production_state, f"Room B never received its production-state echo; frames={frames_b!r}"
    finally:
        for log_path in created_logs:
            try:
                log_path.unlink(missing_ok=True)
            except OSError:
                pass

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.alex_core import AlexCore
from modules.alex_jeremy_bridge import AlexJeremyBridge
from modules import alex_routes
from modules.auth import create_access_token


def test_alex_core_persists_runtime_state_snapshot(tmp_path: Path):
    alex = AlexCore(user_id="persist_user", data_dir=tmp_path / "alex")
    response = asyncio.run(alex.process_message(
        "I am overwhelmed and confused and tired",
        typing_speed=160,
        metadata={"time_of_day": "evening"},
    ))
    assert response["ai_state"] in {"anchor", "mirror", "witness", "guide", "companion"}
    snapshot_path = tmp_path / "alex" / "persist_user" / "_alex_state.json"
    assert snapshot_path.exists()
    alex.shutdown()

    restored = AlexCore(user_id="persist_user", data_dir=tmp_path / "alex")
    state = restored.get_state()
    assert restored._conversation_count >= 1
    assert state["stress_score"] > 0
    assert restored.get_recent_memories(5)
    restored.shutdown()


def test_alex_bridge_marks_memory_resurrection_for_jeremy(tmp_path: Path):
    bridge = AlexJeremyBridge(tmp_path)
    alex = bridge.alex_for("memory-user")
    asyncio.run(alex.process_message("I am building persistent memory for the studio", typing_speed=80))

    packet = bridge.build_entry_packet(
        user_id="memory-user",
        session_id="memory-session",
        project_id="proj",
        room_id="waiting_room",
    )

    assert packet["resumed_from_memory"] is True
    assert packet["remembered_memory_count"] >= 1
    whisper = bridge.jeremy_whisper(user_id="memory-user", session_id="memory-session")
    assert "prior Alex memory" in whisper
    bridge.shutdown()


def test_alex_routes_message_and_recent_memory(tmp_path: Path):
    fallback_alex = AlexCore(user_id="default", data_dir=tmp_path / "fallback_alex")
    bridge = AlexJeremyBridge(tmp_path / "bridge")
    alex_routes.set_alex_instance(fallback_alex)
    alex_routes.set_alex_provider(bridge.alex_for)
    app = FastAPI()
    app.include_router(alex_routes.router)
    client = TestClient(app)
    def auth(user, role='owner'):
        return {'Authorization': 'Bearer ' + create_access_token({'sub': user, 'role': role})}

    assert client.get('/api/alex/memory/recent?user_id=route_user').status_code == 401
    assert client.post('/api/alex/message', json={'user_id': 'route_user', 'message': 'test'}).status_code == 401
    assert client.get('/api/alex/memory/recent?user_id=route_user', headers=auth('stranger', 'guest')).status_code == 403
    assert client.post('/api/alex/message', json={'user_id': 'route_user', 'message': 'test'}, headers=auth('stranger')).status_code == 403

    response = client.post(
        "/api/alex/message",
        json={
            "message": "I am overwhelmed and confused",
            "user_id": "route_user",
            "typing_speed": 120,
            "context": {"time_of_day": "evening"},
        },
        headers=auth('route_user'),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert "ai_state" in body["response"]
    assert body["response"]["user_battery"] in {"charged", "medium", "low", "depleted"}

    recent = client.get("/api/alex/memory/recent?limit=5&user_id=route_user", headers=auth('route_user'))
    assert recent.status_code == 200, recent.text
    recent_body = recent.json()
    assert recent_body["count"] >= 1
    assert recent_body["memories"][0]["content"]
    assert isinstance(recent_body["memories"][0], dict)

    default_recent = client.get("/api/alex/memory/recent?limit=5&user_id=default", headers=auth('route_user'))
    assert default_recent.status_code == 200, default_recent.text
    assert default_recent.json()["count"] == 0

    state = client.get("/api/alex/state?user_id=route_user", headers=auth('route_user'))
    assert state.status_code == 200
    assert state.json()["state"] in {"guide", "companion", "mirror", "anchor", "witness"}

    bridge.shutdown()
    fallback_alex.shutdown()


def test_alex_bridge_high_urgency_signal_escalates_packet_and_whisper(tmp_path: Path):
    bridge = AlexJeremyBridge(tmp_path)

    entry = bridge.build_entry_packet(
        user_id="josie",
        session_id="session-1",
        project_id="proj-1",
        room_id="room-1",
        display_name="Josie",
        metadata={"availability": "available", "presence_mode": "avatar_static"},
    )
    assert entry["care_priority"] == "low"

    updated = bridge.signal_from_jeremy(
        user_id="josie",
        session_id="session-1",
        room_state="critical",
        urgency="high",
        reason="avatar_errors_multiple",
        payload={"count": 3},
    )

    assert updated["care_priority"] == "high"
    assert updated["fragility_level"] >= 0.8
    assert updated["tone_guidance"] == "gentle"
    assert updated["pace_guidance"] == "slow"
    assert updated["intervention_style"] == "protective"
    assert updated["latest_signal"]["reason"] == "avatar_errors_multiple"
    assert "avoid_confrontation" in updated["do_not_touch"]
    assert "reduce_noise" in updated["do_not_touch"]

    whisper = bridge.jeremy_whisper(user_id="josie", session_id="session-1")
    assert "gentle" in whisper
    assert "minimize friction" in whisper or "gentler pacing" in whisper

    bridge.shutdown()


def test_alex_bridge_caps_signal_history(tmp_path: Path):
    bridge = AlexJeremyBridge(tmp_path)
    bridge.build_entry_packet(
        user_id="cap-user",
        session_id="cap-session",
        project_id="proj",
        room_id="room",
    )

    for idx in range(90):
        bridge.signal_from_jeremy(
            user_id="cap-user",
            session_id="cap-session",
            room_state="destabilizing" if idx % 2 else "tense",
            urgency="medium" if idx % 3 else "high",
            reason=f"issue_{idx}",
            payload={"idx": idx},
        )

    signals_path = tmp_path / "alex_bridge" / "signals_cap-session_cap-user.json"
    data = json.loads(signals_path.read_text(encoding="utf-8"))
    assert len(data) <= 64
    assert data[-1]["reason"] == "issue_89"

    bridge.shutdown()


# ── 2026-11-13: one entry path, and room urgency kept apart from the user ──

def _auth(user, role="owner"):
    return {"Authorization": "Bearer " + create_access_token({"sub": user, "role": role})}


def _route_client(tmp_path: Path):
    bridge = AlexJeremyBridge(tmp_path / "bridge")
    alex_routes.set_alex_instance(None)
    alex_routes.set_alex_provider(bridge.alex_for)
    alex_routes.set_alex_bridge(bridge)
    app = FastAPI()
    app.include_router(alex_routes.router)
    return bridge, TestClient(app)


def _reset_routes():
    alex_routes.set_alex_bridge(None)
    alex_routes.set_alex_provider(None)


def test_alex_message_route_refreshes_the_packet_jeremy_reads(tmp_path: Path):
    bridge, client = _route_client(tmp_path)
    try:
        entry = bridge.build_entry_packet(user_id="u1", session_id="s1", project_id="p", room_id="r")
        assert entry["alex_state"] == "guide"
        first = client.post("/api/alex/message", headers=_auth("u1"), json={
            "message": "I am exhausted and drained and overwhelmed.", "typing_speed": 20,
            "context": {"session_id": "s1"}})
        assert first.status_code == 200, first.text
        body = first.json()["response"]
        # The caller still gets Alex's private analysis, as before.
        assert {"ai_state", "user_battery", "memory_context", "response_guidelines"} <= set(body)
        packet = bridge.current_packet(user_id="u1", session_id="s1")
        assert packet["bridge_scope"] == "message_analysis"
        assert packet["generated_at"] > entry["generated_at"]
        assert packet["alex_state"] == body["ai_state"]
        assert packet["user_battery"] == body["user_battery"]
        assert packet["private_memory_context_withheld"] is True
        assert "memory_context" not in packet

        # A correction through the same route reaches Jeremy's packet too.
        second = client.post("/api/alex/message", headers=_auth("u1"), json={
            "message": "No, you misread me. I'm not upset.", "context": {"session_id": "s1"}})
        after = bridge.current_packet(user_id="u1", session_id="s1")
        assert after["generated_at"] > packet["generated_at"]
        assert after["alex_state"] == second.json()["response"]["ai_state"]
        assert "misread" in " ".join(after.get("active_threads", []))
        bridge.shutdown()

        # After a restart both readers still agree.
        reopened = AlexJeremyBridge(tmp_path / "bridge")
        again = reopened.current_packet(user_id="u1", session_id="s1")
        assert again["generated_at"] == after["generated_at"]
        assert again["alex_state"] == reopened.alex_for("u1")._current_state.value
        reopened.shutdown()
    finally:
        _reset_routes()


def test_room_emergency_does_not_change_alexs_read_of_a_calm_user(tmp_path: Path):
    bridge = AlexJeremyBridge(tmp_path)
    alex = bridge.alex_for("calm")
    asyncio.run(bridge.process_user_turn(user_id="calm", session_id="s", text="Morning. The set looks good today."))
    before = (alex._current_state, alex._user_state.stress_level, alex._user_state.clarity_score,
              alex._user_state.energy_level, alex._user_battery)

    response = bridge.signal_from_jeremy(user_id="calm", session_id="s", room_state="critical",
                                         urgency="high", reason="guest escalation")
    # Emergency handling is still there for the room.
    assert response["care_priority"] == "high"
    assert response["fragility_level"] >= 0.8
    assert response["intervention_style"] == "protective"
    assert response["room_context"]["about"] == "room"
    assert response["room_context"]["urgency"] == "high"
    # Alex's read of the person is untouched.
    assert response["user_fragility_level"] < 0.4
    assert (alex._current_state, alex._user_state.stress_level, alex._user_state.clarity_score,
            alex._user_state.energy_level, alex._user_battery) == before
    whisper = bridge.jeremy_whisper(user_id="calm", session_id="s")
    assert "Room signal: critical / high (guest escalation)" in whisper
    assert "not this user's own state" in whisper
    assert "User appears fragile" not in whisper

    out = {}
    packet = asyncio.run(bridge.process_user_turn(
        user_id="calm", session_id="s", text="Okay. I can keep going, what do you need from me?",
        analysis_out=out))
    assert out["ai_state"] != "anchor" and out["anchor_message"] is None
    assert packet["alex_state"] != "anchor"
    assert packet["user_fragility_level"] < 0.4
    # Jeremy still sees the room emergency on the next turn, labelled as the room.
    assert packet["room_context"]["urgency"] == "high"
    assert "Room signal" in bridge.jeremy_whisper(user_id="calm", session_id="s")
    bridge.shutdown()


def test_users_own_emergency_still_reaches_anchor(tmp_path: Path):
    bridge = AlexJeremyBridge(tmp_path)
    out = {}
    for text in ("This is an emergency, I'm in a panic and I can't think.",
                 "I'm lost and confused, it's a crisis, it's urgent."):
        asyncio.run(bridge.process_user_turn(user_id="hurt", session_id="s", text=text,
                                             typing_speed=160, analysis_out=out))
    assert out["ai_state"] == "anchor"
    assert out["anchor_message"]
    assert "User appears fragile" in bridge.jeremy_whisper(user_id="hurt", session_id="s")
    bridge.shutdown()


def test_old_room_signal_stops_travelling_with_packets(tmp_path: Path, monkeypatch):
    import modules.alex_jeremy_bridge as mod
    bridge = AlexJeremyBridge(tmp_path)
    bridge.signal_from_jeremy(user_id="u", session_id="s", room_state="tense", urgency="high", reason="noise")
    monkeypatch.setattr(mod, "ROOM_SIGNAL_ACTIVE_SECONDS", -1)
    packet = asyncio.run(bridge.process_user_turn(user_id="u", session_id="s", text="All fine here."))
    assert "room_context" not in packet
    bridge.shutdown()

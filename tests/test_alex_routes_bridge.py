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

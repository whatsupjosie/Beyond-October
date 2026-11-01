from __future__ import annotations

import json
from pathlib import Path

import main
from modules.ai_runtime import load_ai_runtime_config, validate_ai_runtime_config
from modules.inference import InferenceManager

# NOTE: these tests use the shared session-scoped `client` fixture from
# conftest.py (which runs the app's real lifespan once for the whole test
# session) instead of each creating their own TestClient(main.app). Booting
# the lifespan more than once in the same process corrupts this app's
# module-level singleton state and causes RecursionError failures that only
# show up when the full suite runs together — booting once and sharing the
# client is both faster and avoids that class of bug entirely.


def test_startup_and_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "ai_providers" in payload


def test_key_static_pages_load(client):
    for path in ["/", "/control", "/world", "/builder"]:
        response = client.get(path)
        assert response.status_code == 200, path


def test_websocket_round_trip(client):
    with client.websocket_connect("/ws/control") as ws:
        ws.send_text(json.dumps({"type": "chat", "text": "smoke test"}))
        seen_chat = False
        for _ in range(5):
            message = json.loads(ws.receive_text())
            if message.get("type") == "chat":
                seen_chat = True
                assert message["payload"]["text"] == "smoke test"
                break
        assert seen_chat


def test_pubpartner_turns_live_preserves_messages_in_real_spine(client):
    """The 2i writer's-room app (and other external clients) speak the
    `messages: [{role, content}]` turn-array shape. This route must adapt
    that to the vessel spine's message/history shape and retain a reply alias.
    The mock provider below is an explicit test adapter, not a live AI test.
    """
    response = client.post(
        "/api/pubpartner/turns/live",
        json={"provider": {"provider": "mock"}, "messages": [
            {"role": "user", "content": "first message, must be preserved"},
            {"role": "assistant", "content": "an assistant turn, must be preserved"},
            {"role": "user", "content": "Hello Alex, are you there?"},
        ]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "reply" in payload and payload["reply"]
    assert payload["role"] == "pub_partner_alex"
    assert len(payload["fcp1"]["history"]) == 2
    assert payload["receipt_chain"]["ok"] is True


def test_pubpartner_turns_live_handles_empty_messages(client):
    response = client.post("/api/pubpartner/turns/live", json={"messages": []})
    assert response.status_code == 400
    assert "messages" in response.json()["detail"]


def test_inference_status_exposes_config(client):
    response = client.get("/api/inference/status")
    assert response.status_code == 200
    payload = response.json()
    assert "profile" in payload
    assert "available_profiles" in payload


def test_inference_status_handles_invalid_config_path(monkeypatch):
    monkeypatch.setenv("PUBCAST_AI_CONFIG_PATH", r"C:\outside\forbidden.json")
    manager = InferenceManager.__new__(InferenceManager)
    manager._base_dir = Path(main.__file__).resolve().parent
    manager._worker_alive = False
    manager._started_at = None
    manager._last_error = ""
    monkeypatch.delenv("PUBCAST_AI_CONFIG_PATH", raising=False)
    manager._config = validate_ai_runtime_config(load_ai_runtime_config(manager._base_dir))
    monkeypatch.setenv("PUBCAST_AI_CONFIG_PATH", r"C:\outside\forbidden.json")
    payload = InferenceManager.status(manager)
    assert payload["worker_alive"] is False
    assert payload["profile"] is None
    assert "outside the repo root" in payload["last_error"]


def test_bot_crud_and_speak_endpoint(client):
    create_response = client.post(
        "/api/bots",
        json={
            "bot_id": "smoke-bot",
            "name": "Smoke Bot",
            "provider": "ollama",
            "model": "llama3",
            "api_key_env": "PUBCAST_OLLAMA_KEY",
            "rooms": ["control"],
            "system_prompt": "Stay brief.",
            "auto_reply": True,
            "mention_only": False,
            "shadow_presence": True,
        },
    )
    assert create_response.status_code == 200

    speak_response = client.post(
        "/api/bots/smoke-bot/speak",
        json={"room": "control", "text": "hello from smoke bot"},
    )
    assert speak_response.status_code == 200
    assert speak_response.json()["ok"] is True

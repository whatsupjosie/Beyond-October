import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import pubpartner_routes
from modules.pubpartner_provider import PubPartnerProviderDispatcher
from modules.pubpartner_voice import FriendVoiceRestorer


def _client(tmp_path):
    app = FastAPI()
    pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path)
    app.include_router(pubpartner_routes.router)
    return TestClient(app)


@pytest.mark.asyncio
async def test_pubpartner_run_turn_mock_provider_generates_friend_response(tmp_path):
    from modules.pubpartner_core import PubPartnerSpine

    spine = PubPartnerSpine(tmp_path)
    result = await spine.run_turn(
        user_id="josie",
        session_id="live1",
        message="Help me keep building the spine.",
        friend={"friend_id": "craig", "display_name": "Craig", "tone": ["warm", "dry"]},
        provider={"provider": "mock", "model": "mock-v1"},
        task={"mode": "build", "goal": "next vertebra"},
    )

    assert result["live_loop"] is True
    assert result["provider_result"]["ok"] is True
    assert result["provider_result"]["provider"] == "mock"
    assert result["friend_response"]
    assert "Sure" not in result["friend_response"]
    assert result["provenance"]["source_ref"]["sha256"] == result["source"]["sha256"]
    assert result["provenance"]["verbatim_restores"] is True


@pytest.mark.asyncio
async def test_live_loop_long_lyrics_remain_ref_only_and_restorable(tmp_path):
    from modules.pubpartner_core import PubPartnerSpine

    spine = PubPartnerSpine(tmp_path)
    exact = "Chorus:\n" + "Do not rewrite my gold zebra line.\n" * 120
    result = await spine.run_turn(
        user_id="josie",
        session_id="lyrics",
        message=exact,
        content_kind="lyrics",
        provider={"provider": "mock"},
        prompt_mode="auto",
        task={"mode": "songwriting", "goal": "comment_without_rewriting"},
    )

    assert result["prompt_policy"]["include_source_text"] is False
    assert "Do not rewrite my gold zebra line" not in result["llm_prompt_text"]
    assert "quote_only_after_restoring_msg_ref" in json.dumps(result["fcp1"]["source_policy"])
    restored = spine.restore_source(user_id="josie", session_id="lyrics", source_id=result["source"]["id"])
    assert restored["text"] == exact
    assert result["friend_response"]


def test_voice_restorer_preserves_code_fences_and_trims_boilerplate():
    restorer = FriendVoiceRestorer()
    raw = "Sure, here's the answer:\n```python\nprint('do not change')\n```\nHope this helps!"
    result = restorer.restore(raw, friend={"cad": ["low_fluff"], "avoid": ["generic_assistant"]})

    assert result.ok is True
    assert "Sure" not in result.friend_response
    assert "```python\nprint('do not change')\n```" in result.friend_response
    assert "Hope this helps" not in result.friend_response
    assert result.protected_blocks[0]["type"] == "code_fence"


@pytest.mark.asyncio
async def test_provider_missing_openai_key_reports_unavailable_and_offline_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from modules.pubpartner_core import PubPartnerSpine

    spine = PubPartnerSpine(tmp_path)
    result = await spine.run_turn(
        user_id="u",
        session_id="s",
        message="hello",
        provider={"provider": "openai", "model": "gpt-test"},
        allow_fallback=True,
    )

    assert result["provider_fallback"] is not None
    assert result["provider_fallback"]["available"] is False
    assert "missing env" in result["provider_fallback"]["error"]
    assert result["provider_result"]["provider"] == "offline"
    assert result["provider_result"]["ok"] is True
    assert result["provenance"]["fallback_used"] is True


def test_routes_live_turn_and_provider_status(tmp_path):
    client = _client(tmp_path)
    status = client.get("/api/pubpartner/status")
    assert status.status_code == 200
    assert status.json()["live_loop"] is True
    assert "mock" in status.json()["providers"]

    prov = client.get("/api/pubpartner/providers/status", params={"provider": "mock"})
    assert prov.status_code == 200
    assert prov.json()["available"] is True

    response = client.post(
        "/api/pubpartner/turns/live",
        json={
            "user_id": "u",
            "session_id": "route_live",
            "message": "Build the loop.",
            "provider": {"provider": "mock"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["live_loop"] is True
    assert payload["friend_response"]
    assert payload["provider_result"]["provider"] == "mock"


def test_generate_response_flag_on_existing_turn_route(tmp_path):
    client = _client(tmp_path)
    response = client.post(
        "/api/pubpartner/turns",
        json={"user_id": "u", "session_id": "genflag", "message": "hi", "generate_response": True, "provider": {"provider": "mock"}},
    )
    assert response.status_code == 200
    assert response.json()["live_loop"] is True

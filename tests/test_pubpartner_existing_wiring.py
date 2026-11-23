"""Focused wiring regressions for existing PubPartner components.

Tests use the deterministic mock dispatch and temporary storage, no LLM API.
"""
import json

import pytest
from fastapi.testclient import TestClient

from modules.pubpartner_core import PubPartnerSpine
from modules.pubpartner_provider import ProviderResult


def test_standalone_host_mounts_existing_cartridge_workflow(tmp_path, monkeypatch):
    import pubpartner_app
    monkeypatch.setattr(pubpartner_app, "DATA_DIR", tmp_path)
    paths = set(pubpartner_app.app.openapi()["paths"])
    assert "/api/pubpartner/cartridges" in paths
    assert "/api/pubpartner/cartridges/{cartridge_id}" in paths
    assert "/api/avatars/imports" in paths
    with TestClient(pubpartner_app.app) as client:
        response = client.get("/api/pubpartner/cartridges", headers={"X-Client-Id": "owner"})
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True


@pytest.mark.asyncio
async def test_existing_guidance_not_injected_into_shared_rooms(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    spine.add_guidance(user_id="owner", friend_id="alex",
                       text="Never publish my private preference", kind="preference")
    private = await spine.build_turn_packet(
        user_id="owner", session_id="private-session", message="Hello",
        friend="alex", provider={"provider": "mock"}, room_id="phone")
    public = await spine.build_turn_packet(
        user_id="owner", session_id="public-session", message="Hello",
        friend="alex", provider={"provider": "mock"}, room_id="stage")
    assert any("Never publish" in str(row) for row in private["fcp1"]["guide"])
    assert not any("Never publish" in str(row) for row in public["fcp1"]["guide"])


@pytest.mark.asyncio
async def test_resumed_session_reuses_provider_connection_without_secret(tmp_path, monkeypatch):
    spine = PubPartnerSpine(tmp_path)
    await spine.create_session(
        user_id="owner", session_id="resume", friend="alex",
        provider={
            "provider": "ollama", "model": "example-local",
            "host": "http://127.0.0.1:12345",
            "credential_model_id": "saved-reference",
            "api_key": "NEVER_WRITE_THIS",
        },
    )
    state = spine._read_session_state("owner", "resume")
    assert state["provider_runtime"]["host"] == "http://127.0.0.1:12345"
    assert state["provider_runtime"]["credential_model_id"] == "saved-reference"
    assert "NEVER_WRITE_THIS" not in json.dumps(state)
    observed = []

    async def fake_dispatch(turn, config):
        observed.append(config)
        return ProviderResult(ok=True, provider="ollama", model="example-local",
                              raw_response="I remember the connection.")

    monkeypatch.setattr(spine.provider_dispatcher, "dispatch", fake_dispatch)
    result = await spine.run_turn(user_id="owner", session_id="resume", message="Hello",
                                  allow_fallback=False)
    assert result["provider_result"]["ok"] is True
    assert observed[0]["host"] == "http://127.0.0.1:12345"
    assert observed[0]["credential_model_id"] == "saved-reference"
    assert "api_key" not in observed[0]

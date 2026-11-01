"""Actual portable CLI and minimal application entry points, offline providers."""
from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import sys

from fastapi.testclient import TestClient

from modules.pubpartner_provider import ProviderResult
from pubpartner.cartridge import init_cartridge, load_cartridge
from pubpartner.cli import _cmd_chat
import pubpartner_app


def test_cartridge_cli_uses_portable_runtime_and_preserves_input(tmp_path, monkeypatch):
    init_cartridge(tmp_path / "alex", name="Alex", summary="Curious and attentive.", cadence="short", vocabulary="plain")
    text = "  I am frustrated. Can you help me plan?  "
    client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Compare three practical choices.")]))))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda **_: client))
    monkeypatch.setattr("builtins.input", Mock(side_effect=[text, EOFError()]))
    assert _cmd_chat(Namespace(cartridge=str(tmp_path / "alex"), budget=4000,
        model="local-test", max_tokens=512)) == 0
    sent = client.messages.create.call_args.kwargs
    assert "companion_advisory=" in sent["system"]
    assert sent["messages"][0]["content"] == text
    with load_cartridge(tmp_path / "alex") as cartridge:
        assert cartridge.memory.count() == 1
        assert cartridge.memory.all()[0].text == "User said: " + text


def test_minimal_pubpartner_host_runs_new_advice_with_existing_authority(tmp_path, monkeypatch):
    monkeypatch.setattr(pubpartner_app, "DATA_DIR", tmp_path)
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    with TestClient(pubpartner_app.app) as client:
        spine = pubpartner_app.app.state.pubpartner_spine
        bridge = pubpartner_app.app.state.alex_bridge
        spine.provider_dispatcher.dispatch = AsyncMock(return_value=ProviderResult(
            ok=True, provider="mock", raw_response="Compare three practical choices."))
        response = client.post("/api/pubpartner/turns/live", headers={"X-Client-Id": "owner"},
            json={"message": "I am frustrated. Can you help me plan?", "session_id": "s",
                  "provider": {"provider": "mock"}, "allow_fallback": False})
        assert response.status_code == 200
        result = response.json()
        assert result["ok"]
        assert result["companion_advisory"]["applied"]
        assert result["companion_review"]["response_modified"] is False
        assert spine.alex_bridge is bridge
        assert spine.provider_dispatcher.dispatch.await_count == 1
        assert spine.verify_receipts(user_id="owner", session_id="s")["ok"]

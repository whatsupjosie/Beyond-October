from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import pubpartner_routes
from modules.byok_manager import BYOKManager
from modules.provider_capabilities import canonical_provider, provider_catalog
from modules.provider_neutralizer import ProviderNeutralizer
from modules.pubpartner_provider import PubPartnerProviderDispatcher
from modules.pubpartner_voice import AlexPersonalizationEngine

ROOT = Path(__file__).resolve().parents[1]


def test_provider_aliases_and_catalog_cover_named_families():
    assert canonical_provider("ChatGPT") == "openai"
    assert canonical_provider("Claude") == "anthropic"
    assert canonical_provider("Google") == "gemini"
    assert canonical_provider("LM-Studio") == "openai_compatible"
    ids = {row["provider_id"] for row in provider_catalog()}
    assert {"openai", "anthropic", "gemini", "mistral", "ollama", "openai_compatible", "opencode_zen"} <= ids


def test_neutralizer_is_noop_when_answer_is_already_clean():
    raw = "Yes. The one you started with is blue."
    result = ProviderNeutralizer().neutralize(raw, provider="claude", model="test")
    assert result.neutral_response == raw
    assert result.change_level == "none"
    assert result.provider == "anthropic"


def test_neutralizer_removes_provider_presentation_but_not_meaning():
    raw = "Certainly, the answer is four.\n\nHope this helps!"
    result = ProviderNeutralizer().neutralize(raw, provider="openai")
    assert result.neutral_response == "the answer is four."
    assert result.change_level == "presentation_only"
    assert "remove_provider_boilerplate_prefix" in result.applied
    assert "remove_provider_stock_closing" in result.applied


def test_neutralizer_preserves_code_fence_byte_for_byte():
    code = "```python\nprint('exact')\n```"
    result = ProviderNeutralizer().neutralize("Sure, " + code + "\nHope this helps!", provider="gemini")
    assert code in result.neutral_response
    assert result.protected_text_preserved is True


def test_alex_receipt_exposes_separate_provider_neutralization_stage():
    result = AlexPersonalizationEngine().restore(
        "Absolutely, here's the answer.\nHope this helps!",
        friend={"id": "alex"},
        provider={"provider": "anthropic", "model": "claude-test"},
    )
    assert result.personalization_applied is True
    assert result.provider_neutralization["provider"] == "anthropic"
    assert result.provider_neutralization["change_level"] == "presentation_only"
    assert result.friend_response == "here's the answer."


@pytest.mark.asyncio
async def test_universal_provider_dispatch_reuses_pubcast_adapter(monkeypatch):
    class FakeAdapter:
        def is_available(self):
            return True

        async def complete(self, prompt, **kwargs):
            assert "FCP1" in prompt
            assert kwargs["model"] == "claude-test"
            return "Certainly, useful result."

    import modules.llm_framework as framework

    monkeypatch.setattr(framework, "get_adapter_for_provider", lambda provider, api_key="": FakeAdapter())
    dispatcher = PubPartnerProviderDispatcher()
    turn = {"fcp1": {"u": {"id": "u"}}, "llm_prompt_text": "FCP1 test packet"}
    result = await dispatcher.dispatch(
        turn,
        {"provider": "anthropic", "model": "claude-test", "api_key": "secret", "allow_inline_key": True},
    )
    assert result.ok is True
    assert result.provider == "anthropic"
    assert result.raw_response == "Certainly, useful result."
    assert result.usage["credential_source"] == "internal_inline"


@pytest.mark.asyncio
async def test_openai_compatible_local_endpoint_contract(monkeypatch):
    class FakeCompatible:
        def __init__(self, **kwargs):
            assert kwargs["base_url"] == "http://127.0.0.1:1234/v1"
            assert kwargs["require_api_key"] is False

        def is_available(self):
            return True

        async def complete(self, prompt, **kwargs):
            assert kwargs["model"] == "local-model"
            return "Local endpoint response."

    import modules.openai_compatible_provider as compat

    monkeypatch.setattr(compat, "OpenAICompatibleBotAdapter", FakeCompatible)
    dispatcher = PubPartnerProviderDispatcher()
    turn = {"fcp1": {"u": {"id": "u"}}, "llm_prompt_text": "FCP1 local"}
    result = await dispatcher.dispatch(
        turn,
        {
            "provider": "openai_compatible",
            "model": "local-model",
            "base_url": "http://127.0.0.1:1234/v1",
            "require_api_key": False,
        },
    )
    assert result.ok is True
    assert result.provider == "openai_compatible"
    assert result.usage["base_url_configured"] is True


def test_byok_key_wrappers_do_not_mutate_process_environment(monkeypatch):
    from modules.llm_framework import _KeyedAnthropicAdapter, _KeyedGeminiAdapter, _KeyedOpenAIAdapter

    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "environment-anthropic")
    monkeypatch.setenv("GEMINI_API_KEY", "environment-gemini")
    assert _KeyedOpenAIAdapter("user-openai")._resolve_key() == "user-openai"
    assert _KeyedAnthropicAdapter("user-anthropic")._resolve_key() == "user-anthropic"
    assert _KeyedGeminiAdapter("user-gemini")._resolve_key() == "user-gemini"
    assert os.environ["OPENAI_API_KEY"] == "environment-openai"
    assert os.environ["ANTHROPIC_API_KEY"] == "environment-anthropic"
    assert os.environ["GEMINI_API_KEY"] == "environment-gemini"


def test_provider_credential_routes_store_encrypted_key_without_echo(tmp_path):
    app = FastAPI()
    pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path)
    byok = BYOKManager(tmp_path / "byok")
    pubpartner_routes.configure_pubpartner_byok(byok)
    app.include_router(pubpartner_routes.router)
    client = TestClient(app)

    key = "anthropic-secret-do-not-echo"
    saved = client.post(
        "/api/pubpartner/providers/credentials",
        json={
            "user_id": "u",
            "provider": "anthropic",
            "model": "claude-test",
            "api_key": key,
            "run_fidelity": False,
        },
    )
    assert saved.status_code == 200
    payload = saved.json()
    assert payload["api_key_stored"] is True
    assert key not in saved.text
    model_id = payload["credential_model_id"]

    listed = client.get(
        "/api/pubpartner/providers/credentials",
        params={"user_id": "u", "provider": "anthropic"},
    )
    assert listed.status_code == 200
    assert listed.json()["configured"][0]["model_id"] == model_id
    assert key not in listed.text

    resolved = byok.resolve_model_credentials("u", model_id, expected_provider="anthropic")
    assert resolved is not None
    assert resolved[1]["api_key"] == key


def test_provider_ui_prepares_cloud_and_local_models_without_client_side_key_storage():
    html = (ROOT / "static" / "pubpartner.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "pubpartner.js").read_text(encoding="utf-8")
    for provider in ("openai", "anthropic", "gemini", "mistral", "ollama", "openai_compatible"):
        assert f'value="{provider}"' in html
    assert 'id="providerCredential"' in html
    assert 'id="providerApiKey" type="password"' in html
    assert "/api/pubpartner/providers/credentials" in js
    assert "providerApiKey" not in "\n".join(line for line in js.splitlines() if "localStorage" in line)

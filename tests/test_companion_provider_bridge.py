"""Runtime profiles use the canonical spine with explicit fallback reporting."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from modules.pubpartner_core import PubPartnerSpine
from modules import ai_providers, ai_runtime


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_fails", [False, True])
async def test_runtime_profile_dispatch_keeps_guidance_and_reports_fallback(tmp_path, monkeypatch, primary_fails):
    config = SimpleNamespace(profiles={name: SimpleNamespace(name=name, enabled=True,
        backend="ollama", model=name) for name in ("primary", "fallback")})
    monkeypatch.setattr(ai_runtime, "load_ai_runtime_config", lambda _: config)
    response = SimpleNamespace(text="We can compare concrete choices.", model="selected", backend="ollama")
    generate = AsyncMock(side_effect=[RuntimeError("local primary unavailable"), response]
        if primary_fails else [response])
    monkeypatch.setattr(ai_providers, "generate_with_profile", generate)
    spine = PubPartnerSpine(tmp_path)
    spine.provider_dispatcher.runtime_repo_root = tmp_path
    result = await spine.run_turn(user_id="u", session_id="s", message="Can you help me plan?",
        provider={"provider": "runtime_profile", "profile": "primary", "fallback_profile": "fallback"},
        allow_fallback=False)
    assert result["provider_result"]["ok"]
    assert result["provider_result"]["usage"]["fallback_used"] is primary_fails
    assert generate.await_count == (2 if primary_fails else 1)
    assert "companion_advisory" in generate.call_args.args[2]
    assert result["friend_response"] == response.text


@pytest.mark.asyncio
async def test_runtime_profile_never_presents_echo_as_a_live_companion(tmp_path, monkeypatch):
    config = SimpleNamespace(profiles={"echo": SimpleNamespace(name="echo", enabled=True, backend="echo")})
    monkeypatch.setattr(ai_runtime, "load_ai_runtime_config", lambda _: config)
    generate = AsyncMock()
    monkeypatch.setattr(ai_providers, "generate_with_profile", generate)
    spine = PubPartnerSpine(tmp_path)
    spine.provider_dispatcher.runtime_repo_root = tmp_path
    result = await spine.run_turn(user_id="u", session_id="s", message="Hello",
        provider={"provider": "runtime_profile", "profile": "echo"}, allow_fallback=False)
    assert not result["provider_result"]["ok"]
    assert generate.await_count == 0

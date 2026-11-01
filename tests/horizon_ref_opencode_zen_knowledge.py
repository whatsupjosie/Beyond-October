from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.llm_framework import OpenCodeZenBotAdapter, get_adapter_for_provider
from modules.opencode_zen import BIG_PICKLE_MODEL_ID, OpenCodeZenClient, official_zen_spec
from modules.pubpartner_core import PubPartnerSpine
from modules.pubpartner_knowledge import PubPartnerKnowledgeBroker
from modules import pubpartner_routes


@pytest.mark.asyncio
async def test_zen_client_uses_official_models_and_chat_endpoints():
    seen = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.headers.get("authorization")))
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "big-pickle"}, {"id": "other"}]})
        if request.url.path.endswith("/chat/completions"):
            payload = __import__("json").loads(request.content)
            assert payload["model"] == "big-pickle"
            assert payload["stream"] is False
            return httpx.Response(
                200,
                headers={"x-request-id": "zen_req_1"},
                json={
                    "model": "big-pickle",
                    "choices": [{"message": {"content": "Kinshasa was the capital of Zaire."}}],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 9},
                },
            )
        return httpx.Response(404)

    client = OpenCodeZenClient("zen-test-key", transport=httpx.MockTransport(handler), max_retries=0)
    models = await client.list_models()
    assert models.ok is True
    assert "big-pickle" in models.available_models

    response = await client.chat(
        messages=[{"role": "user", "content": "What was the capital of Zaire?"}],
        model=BIG_PICKLE_MODEL_ID,
    )
    assert response.ok is True
    assert response.text == "Kinshasa was the capital of Zaire."
    assert response.request_id == "zen_req_1"
    assert all(auth == "Bearer zen-test-key" for _, _, auth in seen)
    assert any(path.endswith("/models") for _, path, _ in seen)
    assert any(path.endswith("/chat/completions") for _, path, _ in seen)


def test_official_spec_and_byok_adapter_are_wired():
    spec = official_zen_spec()
    assert spec["base_url"] == "https://opencode.ai/zen/v1"
    assert spec["big_pickle"]["model_id"] == "big-pickle"
    assert "limited" in spec["big_pickle"]["availability_note"]
    adapter = get_adapter_for_provider("opencode_zen", api_key="private-key")
    assert isinstance(adapter, OpenCodeZenBotAdapter)
    assert adapter.is_available() is True


@dataclass
class _Stored:
    provider: str = "opencode_zen"
    model_name: str = "big-pickle"


class _FakeBYOK:
    def __init__(self, key: str = "zen-key") -> None:
        self.key = key
        self.registered = []

    def resolve_model_credentials(self, user_id: str, model_id: str, expected_provider: str = ""):
        if self.key and model_id == "zen-model" and expected_provider == "opencode_zen":
            return _Stored(), {"api_key": self.key}
        return None

    async def register_key(self, **kwargs):
        self.registered.append(kwargs)
        return "zen-model"

    def list_user_models(self, user_id: str):
        return [{
            "model_id": "zen-model",
            "provider": "opencode_zen",
            "display_name": "OpenCode Zen — Big Pickle",
            "model_name": "big-pickle",
            "status": "ready",
            "last_verified": None,
            "last_error": None,
            "fidelity_rating": "untested",
            "fidelity_verdict": "",
        }]


class _FakeZenClient:
    captured: Dict[str, Any] = {}

    def __init__(self, api_key: str, **kwargs: Any) -> None:
        self.api_key = api_key
        self.kwargs = kwargs

    async def list_models(self):
        class R:
            ok = True
            available_models = ["big-pickle"]
            latency_ms = 1
            error = ""
            request_id = "status-1"
        return R()

    async def chat(self, *, messages, model, temperature, max_tokens):
        _FakeZenClient.captured = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "api_key": self.api_key,
        }
        class R:
            ok = True
            model = "big-pickle"
            text = "Reference note: use a leather needle appropriate to the measured hide thickness."
            error = ""
            latency_ms = 3
            usage = {"prompt_tokens": 30, "completion_tokens": 14}
            request_id = "chat-1"
        return R()


@pytest.mark.asyncio
async def test_knowledge_broker_sends_current_question_only_and_redacts_secrets():
    broker = PubPartnerKnowledgeBroker(byok_manager=_FakeBYOK(), client_factory=_FakeZenClient)
    result = await broker.query(
        user_id="josie",
        message="My email is josie@example.com. What needle works for garment deer hide? api_key=secret12345",
        config={"mode": "shadow", "credential_model_id": "zen-model"},
        task={"mode": "sewing_reference"},
    )
    assert result.ok is True
    assert result.used_in_prompt is False
    assert set(result.redactions) >= {"email", "api_key_assignment"}
    sent = "\n".join(m["content"] for m in _FakeZenClient.captured["messages"])
    assert "josie@example.com" not in sent
    assert "secret12345" not in sent
    assert "birthday" not in sent.lower()
    assert "relationship" not in sent.lower()
    assert "Current question only" in sent


@pytest.mark.asyncio
async def test_assisted_zen_reference_is_injected_but_not_made_the_friend(tmp_path: Path):
    spine = PubPartnerSpine(tmp_path)
    spine.set_byok_manager(_FakeBYOK())
    spine.knowledge.client_factory = _FakeZenClient

    result = await spine.run_turn(
        user_id="josie",
        session_id="zen-assisted",
        message="What was the capital of Zaire?",
        friend={"id": "alex", "display_name": "Alex", "voice": ["warm", "direct"]},
        provider={"provider": "mock", "model": "mock-v1"},
        knowledge={
            "mode": "assisted",
            "provider": "opencode_zen",
            "model": "big-pickle",
            "credential_model_id": "zen-model",
        },
    )
    knowledge = result["knowledge_result"]
    assert knowledge["ok"] is True
    assert knowledge["used_in_prompt"] is True
    assert knowledge["provider"] == "opencode_zen"
    assert "@EXTERNAL_REFERENCE" in result["llm_prompt_text"]
    assert "unverified_reference_only" in result["llm_prompt_text"]
    assert result["provider_result"]["provider"] == "mock"
    assert result["friend_response"]
    assert result["provenance"]["knowledge_used"] is True
    assert result["receipt"]["knowledge"]["text_sha256"]


@pytest.mark.asyncio
async def test_shadow_mode_never_changes_primary_prompt(tmp_path: Path):
    spine = PubPartnerSpine(tmp_path)
    spine.set_byok_manager(_FakeBYOK())
    spine.knowledge.client_factory = _FakeZenClient
    result = await spine.run_turn(
        user_id="josie",
        session_id="zen-shadow",
        message="Give me two ways to phrase this sentence.",
        provider={"provider": "mock"},
        knowledge={"mode": "shadow", "credential_model_id": "zen-model"},
    )
    assert result["knowledge_result"]["ok"] is True
    assert result["knowledge_result"]["shadow_only"] is True
    assert result["knowledge_result"]["used_in_prompt"] is False
    assert "@EXTERNAL_REFERENCE" not in result["llm_prompt_text"]


@pytest.mark.asyncio
async def test_missing_zen_key_does_not_block_friend_loop(tmp_path: Path):
    spine = PubPartnerSpine(tmp_path)
    spine.set_byok_manager(_FakeBYOK(key=""))
    result = await spine.run_turn(
        user_id="josie",
        session_id="zen-missing",
        message="What was the capital of Zaire?",
        provider={"provider": "mock"},
        knowledge={"mode": "assisted", "credential_model_id": "missing"},
    )
    assert result["provider_result"]["ok"] is True
    assert result["knowledge_result"]["ok"] is False
    assert "not configured" in result["knowledge_result"]["error"]
    assert result["knowledge_result"]["used_in_prompt"] is False


def test_knowledge_routes_store_key_without_echoing_it(tmp_path: Path):
    fake = _FakeBYOK()
    pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path)
    pubpartner_routes.configure_pubpartner_byok(fake)
    app = FastAPI()
    app.include_router(pubpartner_routes.router)
    client = TestClient(app)

    specs = client.get("/api/pubpartner/knowledge/specs")
    assert specs.status_code == 200
    assert specs.json()["providers"][0]["big_pickle"]["model_id"] == "big-pickle"

    created = client.post(
        "/api/pubpartner/knowledge/credentials",
        json={"user_id": "josie", "api_key": "never-return-this-key"},
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["credential_model_id"] == "zen-model"
    assert "never-return-this-key" not in created.text
    assert fake.registered[0]["provider"] == "opencode_zen"
    assert fake.registered[0]["model_name"] == "big-pickle"
    assert fake.registered[0]["run_fidelity"] is False

@pytest.mark.asyncio
async def test_protected_exact_source_and_personal_health_turns_do_not_leave_device():
    broker = PubPartnerKnowledgeBroker(byok_manager=_FakeBYOK(), client_factory=_FakeZenClient)
    lyrics = await broker.query(
        user_id="josie",
        message="Unpublished lyric line that must stay exact",
        config={"mode": "assisted", "credential_model_id": "zen-model"},
        task={"mode": "writing", "content_kind": "lyrics"},
    )
    assert lyrics.ok is False
    assert "protected exact-source" in lyrics.error

    health = await broker.query(
        user_id="josie",
        message="My medication dose is 4 mg. Is that what you remember?",
        config={"mode": "assisted", "credential_model_id": "zen-model"},
        task={"mode": "conversation", "content_kind": "message"},
    )
    assert health.ok is False
    assert "personal health" in health.error


@pytest.mark.asyncio
async def test_real_byok_store_encrypts_zen_key_and_resolves_server_side(tmp_path: Path):
    from modules.byok_manager import BYOKManager

    manager = BYOKManager(tmp_path / "byok")
    model_id = await manager.register_key(
        user_id="josie",
        provider="opencode_zen",
        model_name="big-pickle",
        api_key="zen-secret-value",
        display_name="Big Pickle",
        run_fidelity=False,
    )
    public_rows = manager.list_user_models("josie")
    assert public_rows[0]["model_id"] == model_id
    assert "zen-secret-value" not in repr(public_rows)
    stored, secrets = manager.resolve_model_credentials(
        "josie", model_id, expected_provider="opencode_zen"
    )
    assert stored.provider == "opencode_zen"
    assert secrets["api_key"] == "zen-secret-value"
    assert manager.resolve_model_credentials("josie", model_id, expected_provider="openai") is None


def test_pubpartner_ui_exposes_optional_zen_reference_desk_without_storing_key_client_side():
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "pubpartner.html").read_text(encoding="utf-8")
    js = (root / "static" / "pubpartner.js").read_text(encoding="utf-8")
    assert 'id="knowledgeMode"' in html
    assert 'id="knowledgeCredential"' in html
    assert 'id="zenApiKey"' in html
    assert 'id="saveZenKey"' in html
    assert 'id="testZen"' in html
    assert "knowledge: knowledgeConfig()" in js
    assert "/api/pubpartner/knowledge/credentials" in js
    assert "/api/pubpartner/knowledge/test" in js
    assert "window.ReachAuth.saveSession" in js
    assert "localStorage.setItem(legacyAuthTokenKey" not in js
    assert "localStorage.setItem(legacyAuthUserKey" not in js
    assert "zenApiKey" not in "\n".join(
        line for line in js.splitlines() if "localStorage.setItem" in line
    )


def test_secured_knowledge_credentials_are_scoped_to_authenticated_user(tmp_path: Path, monkeypatch):
    from modules.auth import create_access_token

    fake = _FakeBYOK()
    pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path)
    pubpartner_routes.configure_pubpartner_byok(fake)
    app = FastAPI()
    app.include_router(pubpartner_routes.router)
    client = TestClient(app)
    token = create_access_token({"sub": "josie", "role": "owner"})
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")

    forbidden = client.get(
        "/api/pubpartner/knowledge/credentials?user_id=someone-else",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert forbidden.status_code == 403

    allowed = client.get(
        "/api/pubpartner/knowledge/credentials?user_id=josie",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["count"] == 1

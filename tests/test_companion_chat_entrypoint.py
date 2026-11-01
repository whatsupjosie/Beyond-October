"""Execute the real private-chat handler without booting unrelated studio services."""
import ast
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
import pytest

from modules.route_security import bound_actor, current_identity
from modules.pubpartner_core import PubPartnerSpine
from modules.pubpartner_provider import ProviderResult


@pytest.fixture
def endpoint(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = ast.parse((root / "main.py").read_text())
    function = next(node for node in source.body if isinstance(node, ast.AsyncFunctionDef)
                    and node.name == "pub_partner_chat_message")
    # Mount the actual decorated handler and real identity binding, provider
    # adapter and spine. Only unrelated application lifespan is excluded.
    app = FastAPI()
    spine = PubPartnerSpine(tmp_path)
    spine.provider_dispatcher.dispatch = AsyncMock(return_value=ProviderResult(
        ok=True, provider="runtime_profile", raw_response="We can compare three choices."))
    app.state.pubpartner_spine = spine
    async def json_dict(request):
        return await request.json()
    namespace = dict(app=app, Request=Request, Depends=Depends,
        HTTPException=HTTPException, current_identity=current_identity,
        bound_actor=bound_actor, _json_dict=json_dict, Path=Path,
        DATA_DIR=tmp_path, alex_bridge=None, blackbox_witness=None,
        __file__=str(root / "main.py"))
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(root / "main.py"), "exec"), namespace)
    app.dependency_overrides[current_identity] = lambda: {
        "authenticated": True, "user_id": "owner", "role": "owner"}
    with TestClient(app) as client:
        yield app, client, spine


def test_host_chat_uses_one_canonical_turn_with_advice_and_lossless_source(endpoint):
    _, client, spine = endpoint
    text = "  I am frustrated. Can you help me plan?\n"
    response = client.post("/api/pub-partner-chat/message", json={"message": text, "session_id": "s"})
    assert response.status_code == 200
    result = response.json()
    assert result["canonical_pipeline"] is True
    assert result["reply"] == "We can compare three choices."
    assert spine.provider_dispatcher.dispatch.await_count == 1
    packet = spine.provider_dispatcher.dispatch.call_args.args[0]
    assert packet["companion_advisory"]["applied"]
    assert packet["companion_advisory"]["scope"]["user_id"] == "owner"
    restored = spine.restore_source(user_id="owner", session_id="s", source_id=packet["source"]["id"])
    assert restored["text"] == text
    assert spine.verify_receipts(user_id="owner", session_id="s")["ok"]


def test_host_chat_rejects_owner_identity_override_even_for_owner_role(endpoint):
    _, client, spine = endpoint
    response = client.post("/api/pub-partner-chat/message", json={"message": "Hello", "user_id": "other"})
    assert response.status_code == 403
    assert spine.provider_dispatcher.dispatch.await_count == 0


def test_host_chat_requires_authenticated_identity(endpoint):
    app, client, spine = endpoint
    app.dependency_overrides[current_identity] = lambda: {"authenticated": False, "user_id": "anon"}
    response = client.post("/api/pub-partner-chat/message", json={"message": "Hello"})
    assert response.status_code == 401
    assert spine.provider_dispatcher.dispatch.await_count == 0


def test_host_chat_forwards_declared_writing_kind_without_advice(endpoint):
    _, client, spine = endpoint
    response = client.post("/api/pub-partner-chat/message", json={
        "message": "I am sad\nmy authored words\n", "content_kind": "poetry"})
    assert response.status_code == 200
    packet = spine.provider_dispatcher.dispatch.call_args.args[0]
    assert packet["source"]["kind"] == "poetry"
    assert not packet["companion_advisory"]["applied"]

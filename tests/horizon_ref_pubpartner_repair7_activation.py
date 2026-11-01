import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import pubpartner_routes
from modules.pubpartner_core import PubPartnerSpine


def _client(tmp_path):
    app = FastAPI()
    pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path)
    app.include_router(pubpartner_routes.router)
    return TestClient(app)


def test_profile_store_seeds_and_routes_list_craig(tmp_path):
    client = _client(tmp_path)
    response = client.get("/api/pubpartner/profiles/friend")
    assert response.status_code == 200
    ids = {p.get("id") for p in response.json()["profiles"]}
    assert "craig" in ids

    craig = client.get("/api/pubpartner/profiles/friend/craig")
    assert craig.status_code == 200
    assert craig.json()["profile"]["display_name"] == "Craig"


@pytest.mark.asyncio
async def test_guidance_is_injected_into_fcp1_and_prompt(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    spine.add_guidance(
        user_id="josie",
        friend_id="craig",
        project_id="pubpartner",
        text="For lyrics, never alter exact user text; restore spans before quoting.",
        kind="exact_text_rule",
        priority=9,
        applies_to=["lyrics"],
    )
    result = await spine.run_turn(
        user_id="josie",
        session_id="guide",
        message="Chorus:\nGold zebra stays gold",
        friend="craig",
        provider="mock",
        project_id="pubpartner",
        content_kind="lyrics",
    )
    assert result["guidance_count"] >= 1
    assert result["fcp1"]["guide"][0]["k"] == "exact_text_rule"
    assert "guide=" in result["llm_prompt_text"]
    assert "never alter exact user text" in result["llm_prompt_text"]


@pytest.mark.asyncio
async def test_receipt_chain_is_written_and_verifies(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    first = await spine.run_turn(user_id="josie", session_id="receipts", message="one", friend="craig", provider="mock")
    second = await spine.run_turn(user_id="josie", session_id="receipts", message="two", friend="craig", provider="mock")
    assert first["receipt_chain"]["receipt_chain_hash"]
    assert second["receipt_chain"]["prev_receipt_hash"] == first["receipt_chain"]["receipt_chain_hash"]
    listed = spine.list_receipts(user_id="josie", session_id="receipts")
    assert listed["verify"]["ok"] is True
    assert listed["verify"]["entries"] == 2


@pytest.mark.asyncio
async def test_token_comparison_reports_ref_only_savings_for_long_exact_source(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    exact = "Verse:\n" + "A very exact line that must not move.\n" * 200
    result = await spine.run_turn(
        user_id="josie",
        session_id="tokens",
        message=exact,
        friend="craig",
        provider="mock",
        content_kind="lyrics",
        prompt_mode="auto",
    )
    assert result["prompt_policy"]["include_source_text"] is False
    comparison = result["token_comparison"]
    assert comparison["estimated_tokens_saved"] > 0
    assert comparison["estimated_savings_ratio"] > 0.25


def test_guidance_and_receipt_routes(tmp_path):
    client = _client(tmp_path)
    add = client.post("/api/pubpartner/guidance", json={
        "user_id": "josie",
        "friend_id": "craig",
        "project_id": "pubpartner",
        "priority": 8,
        "text": "When I am building, show proof before optimism.",
    })
    assert add.status_code == 200
    listed = client.get("/api/pubpartner/guidance", params={"user_id": "josie", "friend_id": "craig", "project_id": "pubpartner"})
    assert listed.status_code == 200
    assert listed.json()["guidance"][0]["text"].startswith("When I am building")

    turn = client.post("/api/pubpartner/turns/live", json={
        "user_id": "josie",
        "session_id": "route_receipts",
        "message": "Build with receipts.",
        "friend": "craig",
        "provider": "mock",
    })
    assert turn.status_code == 200
    receipts = client.get("/api/pubpartner/receipts", params={"user_id": "josie", "session_id": "route_receipts"})
    assert receipts.status_code == 200
    assert receipts.json()["verify"]["ok"] is True
    assert receipts.json()["receipts"][0]["event"] == "pubpartner.turn.live"


def test_provider_test_and_token_estimate_routes(tmp_path):
    client = _client(tmp_path)
    tok = client.post("/api/pubpartner/tokens/estimate", json={"text": "hello world", "provider": "mock"})
    assert tok.status_code == 200
    assert tok.json()["token_estimate"]["estimated_tokens"] >= 1

    test = client.post("/api/pubpartner/providers/test", json={"provider": "mock", "user_id": "josie"})
    assert test.status_code == 200
    assert test.json()["provider_result"]["provider"] == "mock"
    assert test.json()["receipt"]["event"] == "pubpartner.turn.live" if "event" in test.json()["receipt"] else True


def test_static_pubpartner_ui_exists_and_mentions_friend_layer():
    ui = Path("static/pubpartner.html")
    assert ui.exists()
    text = ui.read_text(encoding="utf-8")
    assert "friend layer" in text.lower()
    assert "/api/pubpartner/turns/live" in text

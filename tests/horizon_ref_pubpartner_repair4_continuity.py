import json

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


@pytest.mark.asyncio
async def test_created_session_defaults_are_reused_by_live_turn(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    await spine.create_session(
        user_id="josie",
        session_id="continuity",
        project_id="pubpartner",
        room_id="phone",
        friend={"friend_id": "craig", "display_name": "Craig", "tone": ["warm", "dry"], "cadence": ["low_fluff"]},
        provider={"provider": "mock", "model": "mock-session"},
        user_primer={"rules": ["direct", "no_fake_done"], "workflow": ["preserve_exact_text"]},
    )

    result = await spine.run_turn(
        user_id="josie",
        session_id="continuity",
        message="Keep building from the saved session defaults.",
    )

    assert result["fcp1"]["f"]["id"] == "craig"
    assert result["fcp1"]["proj"]["id"] == "pubpartner"
    assert result["fcp1"]["proj"]["room"] == "phone"
    assert result["provider_result"]["provider"] == "mock"
    assert result["provider_result"]["model"] == "mock-session"
    assert result["receipt"]["source_sha256"] == result["source"]["sha256"]
    assert result["receipt"]["friend_response_sha256"]


@pytest.mark.asyncio
async def test_live_turn_writes_one_turn_log_with_receipt_not_duplicate_packet(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    result = await spine.run_turn(
        user_id="josie",
        session_id="singlelog",
        message="One live turn should create one log row.",
        provider={"provider": "mock"},
    )
    log_path = tmp_path / "pubpartner" / "sessions" / "josie_singlelog_turns.jsonl"
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["turn_id"] == result["turn_id"]
    assert rows[0]["live_loop"] is True
    assert rows[0]["receipt"]["turn_id"] == result["turn_id"]
    assert "message" not in rows[0]


def test_verify_quote_exact_and_misquote_detection(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    exact = "Line one\nGold zebra stays gold\nLine three"
    rec = spine.vault.store(user_id="josie", session_id="quotes", text=exact, kind="lyrics")

    good = spine.verify_quote(user_id="josie", session_id="quotes", source_id=rec.source_id, quote="Gold zebra stays gold")
    assert good["ok"] is True
    assert good["exact_match"] is True
    assert good["matches"][0]["start"] == exact.index("Gold")

    bad = spine.verify_quote(user_id="josie", session_id="quotes", source_id=rec.source_id, quote="Gold zebra stays golden")
    assert bad["ok"] is False
    assert bad["match_count"] == 0


def test_routes_reuse_session_and_verify_quote(tmp_path):
    client = _client(tmp_path)
    created = client.post(
        "/api/pubpartner/sessions",
        json={
            "user_id": "josie",
            "session_id": "route_continuity",
            "project_id": "pubpartner",
            "room_id": "phone",
            "friend": {"friend_id": "craig", "display_name": "Craig"},
            "provider": {"provider": "mock", "model": "route-mock"},
        },
    )
    assert created.status_code == 200

    read = client.get("/api/pubpartner/sessions/route_continuity", params={"user_id": "josie"})
    assert read.status_code == 200
    assert read.json()["session"]["friend"]["id"] == "craig"

    exact = "First\nDo not misquote this lyric\nLast"
    turn = client.post(
        "/api/pubpartner/turns/live",
        json={"user_id": "josie", "session_id": "route_continuity", "message": exact, "content_kind": "lyrics", "prompt_mode": "ref_only"},
    )
    assert turn.status_code == 200
    payload = turn.json()
    assert payload["fcp1"]["f"]["id"] == "craig"
    assert payload["provider_result"]["provider"] == "mock"
    source_id = payload["source"]["id"]

    verified = client.post(
        f"/api/pubpartner/sources/{source_id}/verify-quote",
        params={"user_id": "josie", "session_id": "route_continuity"},
        json={"quote": "Do not misquote this lyric"},
    )
    assert verified.status_code == 200
    assert verified.json()["ok"] is True

    misquote = client.post(
        f"/api/pubpartner/sources/{source_id}/verify-quote",
        params={"user_id": "josie", "session_id": "route_continuity"},
        json={"quote": "Do not misquote that lyric"},
    )
    assert misquote.status_code == 200
    assert misquote.json()["ok"] is False

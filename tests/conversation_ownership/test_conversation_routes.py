import io
import zipfile
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.conversation_routes import create_conversation_router


def client_for(tmp_path):
    app = FastAPI()
    app.include_router(create_conversation_router(tmp_path))
    return TestClient(app)


def headers(user="josie"):
    return {"X-Client-Id": user, "X-Dev-Role": "guest"}


def test_conversation_routes_preserve_exact_text_and_owner_boundary(tmp_path):
    client = client_for(tmp_path)
    created = client.post(
        "/api/conversations",
        headers=headers(),
        json={"title": "Cold Start", "discussion_type": "chat"},
    )
    assert created.status_code == 200
    cid = created.json()["conversation_id"]

    exact = "  Do NOT trim me.\nSecond line — 東京  "
    saved = client.post(
        f"/api/conversations/{cid}/messages",
        headers=headers(),
        json={"speaker": "Josie", "exact_text": exact},
    )
    assert saved.status_code == 200
    assert saved.json()["message"]["exact_text"] == exact

    loaded = client.get(f"/api/conversations/{cid}", headers=headers())
    assert loaded.status_code == 200
    assert loaded.json()["conversation"]["messages"][0]["exact_text"] == exact

    assert client.get(f"/api/conversations/{cid}", headers=headers("someone-else")).status_code == 404


def test_search_and_download_exports(tmp_path):
    client = client_for(tmp_path)
    cid = client.post(
        "/api/conversations", headers=headers(), json={"title": "Archive Search"}
    ).json()["conversation_id"]
    client.post(
        f"/api/conversations/{cid}/messages",
        headers=headers(),
        json={"speaker": "Alex", "exact_text": "Needle phrase exactly here."},
    )

    found = client.get("/api/conversations/search", params={"q": '"Needle phrase"'}, headers=headers())
    assert found.status_code == 200
    assert found.json()["results"][0]["exact_text"] == "Needle phrase exactly here."

    txt = client.post(f"/api/conversations/{cid}/exports/txt", headers=headers())
    assert txt.status_code == 200
    assert b"Needle phrase exactly here." in txt.content
    assert "attachment" in txt.headers.get("content-disposition", "")

    zipped = client.post(f"/api/conversations/{cid}/exports/zip", headers=headers())
    assert zipped.status_code == 200
    assert zipped.content[:2] == b"PK"
    assert "attachment" in zipped.headers.get("content-disposition", "")


def test_config_declares_separate_authority(tmp_path):
    client = client_for(tmp_path)
    data = client.get("/api/conversations/config", headers=headers()).json()
    assert data["authority"] == "conversation-archive"
    assert data["program"] == "general-chat"
    assert data["manuscript_authority"] is False


def test_turn_route_returns_exact_pair(tmp_path, monkeypatch):
    from modules.conversation_archive import ArchivedMessage
    from modules.general_chat_service import GeneralChatTurn

    client = client_for(tmp_path)
    cid = client.post(
        "/api/conversations", headers=headers(), json={"title": "AI turn"}
    ).json()["conversation_id"]

    async def fake_turn(**kwargs):
        archive = kwargs["archive"]
        user = archive.append_message(
            cid, speaker="User", exact_text=kwargs["exact_user_text"],
            room="general-chat", program="general-chat"
        )
        assistant = archive.append_message(
            cid, speaker="Assistant", exact_text="  provider reply  ",
            parent_message_id=user.message_id, room="general-chat", program="general-chat"
        )
        return GeneralChatTurn(user, assistant, "test", "echo", "test-model")

    monkeypatch.setattr("modules.conversation_routes.run_general_chat_turn", fake_turn)
    response = client.post(
        f"/api/conversations/{cid}/turns",
        headers=headers(),
        json={"exact_text": "  exact request  "},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_message"]["exact_text"] == "  exact request  "
    assert data["assistant_message"]["exact_text"] == "  provider reply  "


def test_turn_route_reports_saved_user_on_provider_failure(tmp_path, monkeypatch):
    from modules.conversation_archive import ArchivedMessage
    from modules.general_chat_service import GeneralChatProviderError

    client = client_for(tmp_path)
    cid = client.post(
        "/api/conversations", headers=headers(), json={"title": "AI failure"}
    ).json()["conversation_id"]

    # Use the router's archive through the public append endpoint to construct
    # the same durable-user state the service guarantees before provider I/O.
    saved = client.post(
        f"/api/conversations/{cid}/messages", headers=headers(),
        json={"speaker": "User", "exact_text": "saved before outage"},
    ).json()["message"]
    saved_message = ArchivedMessage(**saved)

    async def fail_turn(**kwargs):
        raise GeneralChatProviderError("model host unavailable", user_message=saved_message)

    monkeypatch.setattr("modules.conversation_routes.run_general_chat_turn", fail_turn)
    response = client.post(
        f"/api/conversations/{cid}/turns", headers=headers(),
        json={"exact_text": "saved before outage"},
    )
    assert response.status_code == 503
    data = response.json()
    assert data["error"] == "provider_unavailable"
    assert data["user_saved"] is True
    assert data["user_message"]["exact_text"] == "saved before outage"


def test_save_all_routes_are_owner_scoped_and_verified(tmp_path):
    client = client_for(tmp_path)
    for user, title, text in [
        ("josie", "One", "josie one"),
        ("josie", "Two", "josie two"),
        ("other", "Private", "must not leak"),
    ]:
        cid = client.post("/api/conversations", headers=headers(user), json={"title": title}).json()["conversation_id"]
        client.post(
            f"/api/conversations/{cid}/messages",
            headers=headers(user),
            json={"speaker": user, "exact_text": text},
        )

    raw = client.post("/api/conversations/exports/all/raw", headers=headers("josie"))
    assert raw.status_code == 200
    assert raw.json()["conversation_count"] == 2
    assert raw.json()["verified"] is True

    zipped = client.post("/api/conversations/exports/all/zip", headers=headers("josie"))
    assert zipped.status_code == 200
    assert zipped.content[:2] == b"PK"
    assert len(zipped.headers["x-pubcast-sha256"]) == 64
    with zipfile.ZipFile(io.BytesIO(zipped.content)) as package:
        contents = b"\n".join(package.read(name) for name in package.namelist() if name.endswith(".json"))
        assert b"josie one" in contents
        assert b"josie two" in contents
        assert b"must not leak" not in contents


def test_search_limit_applies_after_owner_filter(tmp_path):
    client = client_for(tmp_path)
    for user, count in [("other", 12), ("josie", 2)]:
        cid = client.post("/api/conversations", headers=headers(user), json={"title": user}).json()["conversation_id"]
        for i in range(count):
            response = client.post(
                f"/api/conversations/{cid}/messages", headers=headers(user),
                json={"speaker": "User", "exact_text": f"sharedneedle {user} {i}"},
            )
            assert response.status_code == 200
    response = client.get("/api/conversations/search", params={"q": "sharedneedle", "limit": 2}, headers=headers("josie"))
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    assert all("josie" in item["exact_text"] for item in results)
    assert all("other" not in item["exact_text"] for item in results)


def test_parent_validation_returns_client_error(tmp_path):
    client = client_for(tmp_path)
    first = client.post("/api/conversations", headers=headers(), json={"title": "first"}).json()["conversation_id"]
    second = client.post("/api/conversations", headers=headers(), json={"title": "second"}).json()["conversation_id"]
    parent = client.post(
        f"/api/conversations/{first}/messages", headers=headers(),
        json={"speaker": "User", "exact_text": "parent"},
    ).json()["message"]["message_id"]
    result = client.post(
        f"/api/conversations/{second}/messages", headers=headers(),
        json={"speaker": "Assistant", "exact_text": "wrong parent", "parent_message_id": parent},
    )
    assert result.status_code == 400
    assert client.get(f"/api/conversations/{second}", headers=headers()).json()["conversation"]["messages"] == []


def test_archive_survives_router_restart_and_retains_parent_relationship(tmp_path):
    first_client = client_for(tmp_path)
    cid = first_client.post("/api/conversations", headers=headers(), json={"title": "restart"}).json()["conversation_id"]
    parent = first_client.post(
        f"/api/conversations/{cid}/messages", headers=headers(),
        json={"speaker": "User", "exact_text": "  keep exact text\n  "},
    ).json()["message"]["message_id"]
    second_client = client_for(tmp_path)
    loaded = second_client.get(f"/api/conversations/{cid}", headers=headers())
    assert loaded.status_code == 200
    assert loaded.json()["conversation"]["messages"][0]["exact_text"] == "  keep exact text\n  "
    child = second_client.post(
        f"/api/conversations/{cid}/messages", headers=headers(),
        json={"speaker": "Assistant", "exact_text": "resumed", "parent_message_id": parent},
    )
    assert child.status_code == 200
    third_client = client_for(tmp_path)
    messages = third_client.get(f"/api/conversations/{cid}", headers=headers()).json()["conversation"]["messages"]
    assert [m["ordinal"] for m in messages] == [1, 2]
    assert messages[1]["parent_message_id"] == parent


def test_malformed_fts_query_is_a_client_error(tmp_path):
    client = client_for(tmp_path)
    response = client.get("/api/conversations/search", params={"q": '"unclosed'}, headers=headers())
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid search expression"


def test_owner_listing_excludes_other_users(tmp_path):
    client = client_for(tmp_path)
    for user in ("josie", "other"):
        created = client.post("/api/conversations", headers=headers(user), json={"title": user})
        assert created.status_code == 200
    listing = client.get("/api/conversations", headers=headers("josie"))
    assert listing.status_code == 200
    assert [row["title"] for row in listing.json()["conversations"]] == ["josie"]

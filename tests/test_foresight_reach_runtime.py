"""Counter routing and identity checks through the real Reach ASGI lifespan.

Uses the repository's isolated-data client fixture. No service or model response
is substituted. This does not test network binding, a physical GPU or inference.
"""

from pathlib import Path

from modules.auth import create_access_token


def test_counter_and_character_services_with_real_startup(request, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    client = request.getfixturevalue("client")
    headers = {
        "Authorization": "Bearer "
        + create_access_token({"sub": "audit-owner", "role": "owner"})
    }
    page = client.get("/foresight-counter")
    assert page.status_code == 200
    assert (
        page.content
        == (
            Path(__file__).resolve().parents[1] / "static/foresight_counter.html"
        ).read_bytes()
    )
    assert client.get("/static/foresight_counter.js").status_code == 200
    for path in ["/api/pubpartner/status", "/api/foresight/bridge/api/chat/characters"]:
        assert client.get(path).status_code == 401, path
        response = client.get(path, headers=headers)
        assert response.status_code == 200, (path, response.text)
    health = client.get("/api/foresight/bridge/health")
    assert health.status_code == 200 and health.json()["ok"]
    assert health.json()["services"]["character_count"] > 0

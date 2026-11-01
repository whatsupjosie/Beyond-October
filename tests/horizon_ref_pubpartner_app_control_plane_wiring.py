from __future__ import annotations

from fastapi.testclient import TestClient

import pubpartner_app


def test_canonical_pubpartner_app_mounts_alex_jeremy_pub_manager_and_governance(tmp_path, monkeypatch):
    monkeypatch.setattr(pubpartner_app, "DATA_DIR", tmp_path)
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")

    with TestClient(pubpartner_app.app) as client:
        # OpenAPI is the stable public route inventory. Newer supported
        # FastAPI/Starlette releases keep included routers as lazy route
        # containers, which intentionally do not expose a direct `.path`.
        paths = set(pubpartner_app.app.openapi()["paths"])
        assert "/api/alex/state" in paths
        assert "/api/pubmanager/policy" in paths
        assert "/api/pubmanager/authority/requests" in paths
        assert "/api/governance/freeze" in paths

        policy = client.get("/api/pubmanager/policy", headers={"X-Client-Id": "owner"})
        assert policy.status_code == 200
        actions = policy.json()["policy"]["actions"]
        assert "freeze_actor" in actions
        assert "ban_user" in actions

        ban = client.post(
            "/api/pubmanager/authority/requests",
            headers={"X-Client-Id": "owner"},
            json={
                "action": "ban_user",
                "target_user_id": "target",
                "packet_user_id": "target",
                "session_id": "session",
                "requested_by": "owner",
                "urgency": "critical",
                "evidence": {"severity": 1.0, "confidence": 1.0, "security_risk": True},
                "ai_advisory": {"approved": True, "recommendation": "approve"},
            },
        )
        assert ban.status_code == 200
        assert ban.json()["request"]["approved"] is False
        assert ban.json()["request"]["status"] == "human_required"

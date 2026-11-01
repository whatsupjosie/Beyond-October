"""Authenticated HTTP control tests for vessel inspection and correction."""

from __future__ import annotations

from fastapi.testclient import TestClient

import pubpartner_app


def test_vessel_claim_can_be_inspected_rejected_and_stops_retrieving(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(pubpartner_app, "DATA_DIR", tmp_path)
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    headers = {"X-Client-Id": "owner"}

    with TestClient(pubpartner_app.app) as client:
        mounted = client.get("/api/pubpartner/vessel", headers=headers)
        assert mounted.status_code == 200
        assert mounted.json()["vessel"]["friend_id"] == "alex"

        learned = client.post(
            "/api/pubpartner/turns/live",
            headers=headers,
            json={
                "user_id": "owner",
                "session_id": "vessel-route",
                "message": "Remember that I played softball once.",
                "friend": "alex",
                "provider": {"provider": "mock"},
                "room_id": "phone",
            },
        )
        assert learned.status_code == 200
        vessel_claims = learned.json()["relationship"]["vessel_claims"]
        assert len(vessel_claims) == 1
        claim_id = vessel_claims[0]["claim_id"]

        listed = client.get(
            "/api/pubpartner/vessel/memory/claims",
            headers=headers,
            params={"status": "confirmed"},
        )
        assert listed.status_code == 200
        assert any(row["claim_id"] == claim_id for row in listed.json()["claims"])

        corrected = client.post(
            f"/api/pubpartner/vessel/memory/claims/{claim_id}/corrections",
            headers=headers,
            json={"action": "reject", "reason": "That was not a defining fact."},
        )
        assert corrected.status_code == 200
        assert corrected.json()["claim"]["status"] == "rejected"

        later = client.post(
            "/api/pubpartner/turns",
            headers=headers,
            json={
                "user_id": "owner",
                "session_id": "vessel-route",
                "message": "What did I tell you about softball?",
                "friend": "alex",
                "provider": {"provider": "mock"},
                "room_id": "phone",
            },
        )
        assert later.status_code == 200
        assert later.json()["fcp1"]["vessel"]["claims"] == []

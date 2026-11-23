"""Model-free integration: calibration feedback is user-approved and reversible."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import pubpartner_routes


def test_explicit_calibration_approval_reaches_existing_relationship_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    spine = pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path)
    app = FastAPI()
    app.include_router(pubpartner_routes.router)
    with TestClient(app) as client:
        headers = {"X-Client-Id": "alice"}
        started = client.post("/api/pubpartner/calibration/interviews", headers=headers,
                              json={"mode": "system", "partner_id": "alex"}).json()
        interview_id = started["id"]
        endpoint = f"/api/pubpartner/calibration/interviews/{interview_id}"
        question = client.post(endpoint + "/events", headers=headers, json={
            "action": "main_question", "text": "How did I come across?"
        }).json()
        qid = question["questions"][0]["id"]
        client.post(endpoint + "/events", headers=headers, json={
            "action": "answer", "question_id": qid, "text": "You interrupted me."
        })
        # Merely answering an interview must never silently change personality.
        assert spine.relationship.list_lessons(user_id="alice", friend_id="alex")["lessons"] == []
        denied = client.post(endpoint + "/approve", headers=headers, json={
            "question_id": qid, "text": "Wait until I've finished before responding."
        })
        assert denied.status_code == 400
        approved = client.post(endpoint + "/approve", headers=headers, json={
            "question_id": qid, "text": "Wait until I've finished before responding.",
            "approve": True
        })
        assert approved.status_code == 200, approved.text
        row = approved.json()["lesson"]
        assert row["kind"] == "workflow"
        assert row["status"] == "confirmed"
        assert any("calibration:" in ref for ref in row["evidence_ids"])
        # Reapproval is idempotent (evidence is linked, no duplicate lesson).
        again = client.post(endpoint + "/approve", headers=headers, json={
            "question_id": qid, "text": "Wait until I've finished before responding.",
            "approve": True
        })
        assert again.status_code == 200
        assert again.json()["created"] is False

        # Owner can later reject the learned behavior via the existing API.
        changed = client.patch(f"/api/pubpartner/relationship/lessons/{row['lesson_id']}",
                               headers=headers, json={"friend_id": "alex", "status": "rejected"})
        assert changed.status_code == 200
        assert spine.relationship.compact(user_id="alice", friend_id="alex", query="respond") == []


def test_cross_owner_approval_and_unanswered_reference_fail(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path)
    app = FastAPI()
    app.include_router(pubpartner_routes.router)
    with TestClient(app) as client:
        own = {"X-Client-Id": "alice"}
        other = {"X-Client-Id": "bob"}
        doc = client.post("/api/pubpartner/calibration/interviews", headers=own,
                          json={"mode": "user", "partner_id": "alex"}).json()
        endpoint = f"/api/pubpartner/calibration/interviews/{doc['id']}"
        q = client.post(endpoint + "/events", headers=own, json={
            "action": "main_question", "text": "What were you feeling at that time?"
        }).json()["questions"][0]["id"]
        assert client.post(endpoint + "/approve", headers=own, json={
            "approve": True, "text": "My voice gets quiet when I need time.", "question_id": q
        }).status_code == 400
        assert client.post(endpoint + "/approve", headers=other, json={
            "approve": True, "text": "Copy Alice's private experience", "question_id": q
        }).status_code == 404
        client.post(endpoint + "/events", headers=own, json={
            "action": "answer", "question_id": q, "text": "I was frightened."
        })
        approved = client.post(endpoint + "/approve", headers=own, json={
            "approve": True, "text": "Ask me before making guesses about my feelings.", "question_id": q
        })
        assert approved.status_code == 200
        assert approved.json()["lesson"]["kind"] == "preference"

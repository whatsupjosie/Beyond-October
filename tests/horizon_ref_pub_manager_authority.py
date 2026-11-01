from __future__ import annotations

from pathlib import Path

from modules.pub_manager_authority import PubManagerAuthorityStore


def test_pub_manager_reviewer_requires_exact_approved_request(tmp_path: Path):
    store = PubManagerAuthorityStore(tmp_path)
    row = store.create_request(
        action="freeze_actor", target_user_id="target", session_id="s1",
        packet_user_id="target", requested_by="jeremy", reason="review",
    )
    signal = {
        "user_id": "target", "session_id": "s1",
        "payload": {"requested_action": "freeze_actor", "authority_request_id": row["request_id"]},
    }
    assert store.reviewer(signal)["approved"] is False
    store.decide(row["request_id"], approved=True, reviewer="owner")
    assert store.reviewer(signal)["approved"] is True

    wrong = dict(signal)
    wrong["session_id"] = "different"
    assert store.reviewer(wrong)["approved"] is False

"""Blackbox Light integration contracts. No duplicate archive schema."""
from pathlib import Path
import pytest

from modules.pubpartner_blackbox_light import PubPartnerBlackboxLight, BlackboxLightError
from modules.pubpartner_backup import create_friend_backup, verify_friend_backup


def test_full_exchange_search_and_owner_partner_isolation(tmp_path):
    light = PubPartnerBlackboxLight(tmp_path)
    saved = light.capture_exchange(
        user_id="one", friend_id="alex", session_id="s1",
        source_id="src-1", user_text="I am genuinely excited",
        friend_response="That sounds like a wonderful day!",
        provider="test", model="unit")
    assert saved["ok"]
    cid = saved["conversation_id"]
    result = light.get_conversation(user_id="one", friend_id="alex", conversation_id=cid)
    assert [row["speaker"] for row in result["messages"]] == ["User", "Partner"]
    assert result["messages"][0]["exact_text"] == "I am genuinely excited"
    assert len(light.search(user_id="one", friend_id="alex", query="wonderful")) == 1
    assert light.search(user_id="two", friend_id="alex", query="wonderful") == []
    assert light.search(user_id="one", friend_id="craig", query="wonderful") == []
    with pytest.raises(KeyError):
        light.get_conversation(user_id="two", friend_id="alex", conversation_id=cid)
    with pytest.raises(KeyError):
        light.get_conversation(user_id="one", friend_id="craig", conversation_id=cid)


def test_replay_is_idempotent_but_mismatched_source_rejected(tmp_path):
    light = PubPartnerBlackboxLight(tmp_path)
    kwargs = dict(user_id="owner", friend_id="alex", session_id="s",
                  source_id="record1", user_text="Hello.", friend_response="Hi.")
    light.capture_exchange(**kwargs)
    result = light.capture_exchange(**kwargs)
    assert result["idempotent"] is True
    cid = result["conversation_id"]
    assert len(light.get_conversation(user_id="owner", friend_id="alex", conversation_id=cid)["messages"]) == 2
    with pytest.raises(BlackboxLightError):
        light.capture_exchange(**{**kwargs, "user_text": "Changed!"})


def test_backup_excludes_other_user_and_partner_sessions(tmp_path):
    root = tmp_path / "pubpartner"
    for owner, friend in (("alice", "alex"), ("alice", "craig"), ("bob", "alex")):
        folder = root / "sessions"
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{owner}_{friend}_session"
        (folder / f"{name}.json").write_text(
            __import__("json").dumps({"user_id": owner, "session_id": name, "friend": {"id": friend}}),
            encoding="utf-8")
        (folder / f"{name}_turns.jsonl").write_text(
            __import__("json").dumps({"fcp1": {"f": {"id": friend}}, "source": {"id": "src"}}) + "\n",
            encoding="utf-8")
    output = create_friend_backup(tmp_path, user_id="alice", friend_id="alex")
    assert verify_friend_backup(output["path"])["ok"] is True
    import zipfile
    with zipfile.ZipFile(output["path"]) as zf:
        names = zf.namelist()
        assert any("alice_alex_session" in x for x in names)
        assert not any("bob_" in x or "alice_craig_" in x for x in names)


def test_canonical_pipeline_is_wired_and_public_rooms_skipped():
    core = (Path(__file__).resolve().parents[1] / "modules" / "pubpartner_core.py").read_text(encoding="utf-8")
    assert "self.blackbox_light.capture_exchange(" in core
    assert '_turn_audience(task, room_id) == "private"' in core
    assert 'live_result["blackbox_light"] = archive_result' in core


def test_backup_contains_only_requested_partner_full_dialogue(tmp_path):
    light = PubPartnerBlackboxLight(tmp_path)
    for owner, friend, word in (("alice", "alex", "dazzling"), ("alice", "craig", "sunflower"), ("bob", "alex", "midnight")):
        light.capture_exchange(user_id=owner, friend_id=friend, session_id="s",
                               source_id="src", user_text=f"User says {word}",
                               friend_response=f"Partner replies {word}")
    output = create_friend_backup(tmp_path, user_id="alice", friend_id="alex")
    assert verify_friend_backup(output["path"])["ok"] is True
    import zipfile
    import json
    with zipfile.ZipFile(output["path"]) as zf:
        data = json.loads(zf.read("pubpartner/blackbox_light/conversations.json"))
    serialized = json.dumps(data)
    assert data["owner"] == "alice" and data["partner_id"] == "alex"
    assert "dazzling" in serialized
    assert "sunflower" not in serialized and "midnight" not in serialized

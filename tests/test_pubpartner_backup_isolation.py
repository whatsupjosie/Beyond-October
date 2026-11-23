"""No-model checks: PubPartner backups must never leak other owners/partners."""
from __future__ import annotations

import json
import sqlite3
import zipfile

from modules.pubpartner_backup import create_friend_backup, verify_friend_backup
from modules.pubpartner_calibration import CalibrationStore
from modules.pubpartner_cartridges import CartridgeStudio
from modules.pubpartner_core import VerbatimVault
from pubpartner.cartridge import load_cartridge


def _session(root, owner, session_id, friend, turns=None):
    folder = root / "sessions"
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{owner}_{session_id}"
    (folder / f"{stem}.json").write_text(json.dumps({
        "user_id": owner, "session_id": session_id, "friend": {"id": friend}
    }), encoding="utf-8")
    if turns is not None:
        (folder / f"{stem}_turns.jsonl").write_text(
            "".join(json.dumps({"fcp1": {"f": {"id": f}}}) + "\n" for f in turns),
            encoding="utf-8")


def test_partner_backup_excludes_other_guidance_sessions_audio_and_sources(tmp_path):
    root = tmp_path / "pubpartner"
    (root / "guidance").mkdir(parents=True)
    rows = [
        {"user_id": "alice", "friend_id": "alex", "text": "ALEX_ONLY"},
        {"user_id": "alice", "friend_id": "craig", "text": "CRAIG_ONLY"},
        {"user_id": "alice", "friend_id": "*", "text": "ALICE_GLOBAL"},
        {"user_id": "bob", "friend_id": "alex", "text": "BOB_ONLY"},
    ]
    (root / "guidance" / "alice.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    _session(root, "alice", "ours", "alex", turns=["alex"])
    _session(root, "alice", "other", "craig", turns=["craig"])
    _session(root, "bob", "his", "alex", turns=["alex"])
    # The current session state alone cannot prove that its earlier turns
    # belong to the same friend. It is deliberately excluded wholesale.
    _session(root, "alice", "mixed", "alex", turns=["alex", "craig"])

    vault = VerbatimVault(tmp_path)
    vault.store(user_id="alice", session_id="ours", text="ALEX_SOURCE",
                metadata={"friend_id": "alex"})
    vault.store(user_id="alice", session_id="other", text="CRAIG_SOURCE",
                metadata={"friend_id": "craig"})
    vault.store(user_id="alice", session_id="mixed", text="MIXED_SOURCE",
                metadata={"friend_id": "craig"})
    calibration = CalibrationStore(tmp_path)
    a = calibration.start(user_id="alice", partner_id="alex", mode="user")
    b = calibration.start(user_id="alice", partner_id="craig", mode="user")
    calibration.save_audio(user_id="alice", interview_id=a["id"],
                           data=b"ALICE_ALEX_AUDIO", content_type="audio/webm")
    calibration.save_audio(user_id="alice", interview_id=b["id"],
                           data=b"ALICE_CRAIG_AUDIO", content_type="audio/webm")

    result = create_friend_backup(tmp_path, user_id="alice", friend_id="alex")
    assert verify_friend_backup(result["path"])["ok"] is True
    with zipfile.ZipFile(result["path"]) as archive:
        names = archive.namelist()
        content = b"\n".join(archive.read(name) for name in names)
        guide = archive.read("pubpartner/guidance/alice.jsonl").decode()
    assert "ALEX_ONLY" in guide and "ALICE_GLOBAL" in guide
    for forbidden in ("CRAIG_ONLY", "BOB_ONLY", "CRAIG_SOURCE", "MIXED_SOURCE", "ALICE_CRAIG_AUDIO"):
        assert forbidden.encode() not in content
    assert any("alice_ours" in name for name in names)
    assert not any("alice_mixed" in name or "alice_other" in name or "bob_his" in name for name in names)


def test_live_cartridge_memory_is_consistently_snapshotted(tmp_path):
    studio = CartridgeStudio(tmp_path)
    friend = studio.create({"name": "Calypso", "summary": "Careful writer"}, owner="alice")
    with load_cartridge(studio.path_for(friend["id"])) as cartridge:
        cartridge.memory.add("The actual owner-only rehearsal notes", "episodic", importance=0.9)
    backup = create_friend_backup(tmp_path, user_id="alice", friend_id=friend["id"])
    with zipfile.ZipFile(backup["path"]) as archive:
        name = f"pubpartner/cartridges/{friend['id']}/memories.db"
        assert name in archive.namelist()
        extracted = tmp_path / "roundtrip.sqlite3"
        extracted.write_bytes(archive.read(name))
    with sqlite3.connect(extracted) as db:
        rows = db.execute("SELECT text FROM memories").fetchall()
    assert any("rehearsal" in row[0] for row in rows)
    assert verify_friend_backup(backup["path"])["ok"]


def test_backup_rejects_added_unmanifested_entry(tmp_path):
    backup = create_friend_backup(tmp_path, user_id="alice", friend_id="alex")
    with zipfile.ZipFile(backup["path"], "a") as archive:
        archive.writestr("pubpartner/foreign_user/secrets.txt", "SECRET")
    assert verify_friend_backup(backup["path"])["ok"] is False


def test_backups_remain_user_scoped_even_for_same_friend(tmp_path):
    root = tmp_path / "pubpartner"
    for owner in ("alice", "bob"):
        _session(root, owner, "s1", "alex", turns=["alex"])
    archive = create_friend_backup(tmp_path, user_id="alice", friend_id="alex")
    with zipfile.ZipFile(archive["path"]) as zf:
        assert not any("bob_s1" in name for name in zf.namelist())
        assert zf.read("PUBPARTNER_BACKUP_MANIFEST.json").find(b'"user_id": "alice"') >= 0


def test_dot_segment_cannot_escape_partner_directory(tmp_path):
    root = tmp_path / "pubpartner"
    folder = root / "relationship" / "alice" / "alex"
    folder.mkdir(parents=True)
    (folder / "lessons.json").write_text("PRIVATE_ALEX_RELATIONSHIP", encoding="utf-8")
    backup = create_friend_backup(tmp_path, user_id="alice", friend_id="..")
    with zipfile.ZipFile(backup["path"]) as archive:
        names = archive.namelist()
        assert not any("lessons.json" in name for name in names)
        assert b"PRIVATE_ALEX_RELATIONSHIP" not in b"".join(
            archive.read(name) for name in names
        )


def test_calibration_user_storage_rejects_dot_segment_traversal(tmp_path):
    store = CalibrationStore(tmp_path)
    doc = store.start(user_id="..", partner_id="alex", mode="user")
    expected = tmp_path / "pubpartner" / "calibration" / "anon" / (doc["id"] + ".json")
    assert expected.is_file()
    assert store.get(user_id="..", interview_id=doc["id"])["id"] == doc["id"]


def test_guidance_slug_collision_does_not_expose_other_account(tmp_path):
    from modules.pubpartner_guidance import PubPartnerGuidanceStore
    guidance = PubPartnerGuidanceStore(tmp_path)
    guidance.add(user_id="a!b", friend_id="alex", text="SECRET_FOR_FIRST_OWNER")
    guidance.add(user_id="a_b", friend_id="alex", text="SECOND_OWNER_ONLY")
    first = guidance.list(user_id="a!b", friend_id="alex")["guidance"]
    second = guidance.list(user_id="a_b", friend_id="alex")["guidance"]
    assert [row["text"] for row in first] == ["SECRET_FOR_FIRST_OWNER"]
    assert [row["text"] for row in second] == ["SECOND_OWNER_ONLY"]

import json
import zipfile

import pytest

from modules.conversation_archive import ConversationArchive, sha256_file
from modules.package_service import PackageService, PackageVerificationError


def owned_conversation(archive, owner, title, text):
    cid = archive.create_conversation(title=title, metadata={"owner": owner})
    archive.append_message(cid, speaker="Josie", exact_text=text)
    return cid


def test_library_raw_is_structured_verified_and_owner_scoped(tmp_path):
    archive = ConversationArchive(tmp_path / "archive.sqlite3")
    first = owned_conversation(archive, "josie", "Alpha / One", "  exact α\n")
    second = owned_conversation(archive, "josie", "Beta", "exact β")
    service = PackageService(archive)

    result = service.save_library_raw([first, second], tmp_path / "exports", owner_id="josie")
    manifest = json.loads(result["manifest"].read_text(encoding="utf-8"))

    assert result["verified"] is True
    assert manifest["schema"] == "pubcast.conversation.library.v1"
    assert manifest["conversation_count"] == 2
    assert [item["conversation_id"] for item in manifest["conversations"]] == [first, second]
    assert all(item["path"].startswith("Chats/") for item in manifest["conversations"])
    assert result["checksums"].is_file()
    assert not any("pending-" in p.name for p in result["root"].parent.iterdir())


def test_library_export_rejects_cross_owner_before_publish(tmp_path):
    archive = ConversationArchive(tmp_path / "archive.sqlite3")
    mine = owned_conversation(archive, "josie", "Mine", "mine")
    theirs = owned_conversation(archive, "other", "Theirs", "theirs")
    service = PackageService(archive)
    destination = tmp_path / "exports"

    with pytest.raises(PermissionError):
        service.save_library_raw([mine, theirs], destination, owner_id="josie")

    assert list(destination.glob("PubCast_Conversation_Library_*")) == []


def test_library_zip_is_integral_safe_and_contains_library_manifest(tmp_path):
    archive = ConversationArchive(tmp_path / "archive.sqlite3")
    cid = owned_conversation(archive, "josie", "Portable", "verbatim — 東京")
    service = PackageService(archive)

    result = service.save_library_zip([cid], tmp_path / "exports", owner_id="josie")

    assert result["verified"] is True
    assert len(result["sha256"]) == 64
    assert result["sha256"] == sha256_file(result["zip"])
    with zipfile.ZipFile(result["zip"]) as package:
        assert package.testzip() is None
        assert "library_manifest.json" in package.namelist()
        assert "SHA256SUMS.txt" in package.namelist()
        assert all(not name.startswith("/") and ".." not in name.split("/") for name in package.namelist())


def test_inventory_verification_detects_tampering(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    target = root / "payload.txt"
    target.write_text("original", encoding="utf-8")
    inventory = [{"path": "payload.txt", "bytes": 8, "sha256": sha256_file(target)}]
    target.write_text("tampered", encoding="utf-8")

    with pytest.raises(PackageVerificationError, match="checksum mismatch"):
        PackageService._verify_inventory(root, inventory)

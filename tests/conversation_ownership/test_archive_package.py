import json
import zipfile

from modules.conversation_archive import ConversationArchive
from modules.package_service import PackageService


def test_verbatim_round_trip_and_search(tmp_path):
    archive = ConversationArchive(tmp_path / "archive.sqlite3")
    cid = archive.create_conversation(title="Exact Words")
    original = "  Keep THIS exactly.\nSecond line — café 🧵  "
    saved = archive.append_message(cid, speaker="Josie", exact_text=original, program="general-chat")
    loaded = archive.get_conversation(cid)
    assert loaded["messages"][0]["exact_text"] == original
    assert saved.exact_text == original
    results = archive.search('"Second line"')
    assert results[0]["message_id"] == saved.message_id
    assert results[0]["exact_text"] == original


def test_exports_preserve_exact_text_after_parsing(tmp_path):
    archive = ConversationArchive(tmp_path / "archive.sqlite3")
    cid = archive.create_conversation(title="Export Test")
    original = "leading space stays ->  \n\nUnicode: naïve — 東京"
    archive.append_message(cid, speaker="Alex", exact_text=original)
    paths = archive.export_documents(cid, tmp_path / "export")
    parsed = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert parsed["messages"][0]["exact_text"] == original
    jsonl = json.loads(paths["jsonl"].read_text(encoding="utf-8").splitlines()[0])
    assert jsonl["exact_text"] == original
    assert original in paths["txt"].read_text(encoding="utf-8")
    assert original in paths["md"].read_text(encoding="utf-8")


def test_raw_and_zip_have_manifest_hashes_and_valid_zip(tmp_path):
    archive = ConversationArchive(tmp_path / "archive.sqlite3")
    cid = archive.create_conversation(title="Package Me")
    archive.append_message(cid, speaker="Josie", exact_text="one")
    archive.append_message(cid, speaker="Alex", exact_text="two")
    service = PackageService(archive)
    raw = service.save_conversation_raw(cid, tmp_path / "raw")
    manifest = json.loads(raw["manifest"].read_text(encoding="utf-8"))
    assert {item["kind"] for item in manifest["files"]} == {"txt", "md", "json", "jsonl", "html"}
    assert raw["checksums"].exists()
    packaged = service.save_conversation_zip(cid, tmp_path / "download")
    assert packaged["verified"] is True
    assert len(packaged["sha256"]) == 64
    with zipfile.ZipFile(packaged["zip"]) as zf:
        assert zf.testzip() is None
        assert "manifest.json" in zf.namelist()
        assert "SHA256SUMS.txt" in zf.namelist()


def test_concurrent_appends_preserve_every_message_and_unique_ordinals(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    archive = ConversationArchive(tmp_path / "concurrent.sqlite3")
    cid = archive.create_conversation(title="Concurrent")
    def append(i):
        return archive.append_message(cid, speaker="User", exact_text=f"turn-{i}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(append, range(40)))
    assert len({r.message_id for r in results}) == 40
    loaded = archive.get_conversation(cid)["messages"]
    assert len(loaded) == 40
    assert [m["ordinal"] for m in loaded] == list(range(1, 41))
    assert {m["exact_text"] for m in loaded} == {f"turn-{i}" for i in range(40)}


def test_parent_message_must_belong_to_same_conversation(tmp_path):
    import pytest

    archive = ConversationArchive(tmp_path / "parents.sqlite3")
    first = archive.create_conversation(title="First")
    second = archive.create_conversation(title="Second")
    parent = archive.append_message(first, speaker="User", exact_text="original")
    child = archive.append_message(
        first, speaker="Assistant", exact_text="reply", parent_message_id=parent.message_id
    )
    assert child.parent_message_id == parent.message_id
    with pytest.raises(ValueError, match="same conversation"):
        archive.append_message(second, speaker="Assistant", exact_text="leak", parent_message_id=parent.message_id)
    with pytest.raises(ValueError, match="same conversation"):
        archive.append_message(first, speaker="Assistant", exact_text="orphan", parent_message_id="msg_missing")
    assert archive.get_conversation(second)["messages"] == []
    assert len(archive.get_conversation(first)["messages"]) == 2


def test_same_title_exports_do_not_overwrite_other_conversation(tmp_path):
    archive = ConversationArchive(tmp_path / "separate.sqlite3")
    first = archive.create_conversation(title="Shared title", metadata={"owner": "owner-a"})
    second = archive.create_conversation(title="Shared title", metadata={"owner": "owner-b"})
    archive.append_message(first, speaker="User", exact_text="private alpha")
    archive.append_message(second, speaker="User", exact_text="private beta")
    output = tmp_path / "exports"
    first_paths = archive.export_documents(first, output)
    second_paths = archive.export_documents(second, output)
    assert first_paths["json"] != second_paths["json"]
    assert "private alpha" in first_paths["json"].read_text(encoding="utf-8")
    assert "private beta" in second_paths["json"].read_text(encoding="utf-8")
    assert "private beta" not in first_paths["json"].read_text(encoding="utf-8")

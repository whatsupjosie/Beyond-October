"""A long title and external ID must never prevent an exact transcript export."""
import json
from modules.conversation_archive import ConversationArchive


def test_long_title_and_external_identifier_export_preserves_text(tmp_path):
    archive = ConversationArchive(tmp_path / "conversations.sqlite3")
    cid = archive.create_conversation(
        title="Very long manuscript " + "a" * 180,
        conversation_id="external_" + "b" * 160,
    )
    exact = "  leading space\n\n  second line — 東京  "
    archive.append_message(cid, speaker="User", exact_text=exact)
    paths = archive.export_documents(cid, tmp_path / "exports")
    assert set(paths) == {"txt", "md", "json", "jsonl", "html"}
    assert all(p.exists() and len(p.name.encode("utf-8")) <= 240 for p in paths.values())
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["messages"][0]["exact_text"] == exact
    assert exact in paths["txt"].read_text(encoding="utf-8")
    repeat = archive.export_documents(cid, tmp_path / "exports")
    assert all(paths[k] != repeat[k] and paths[k].read_bytes() == repeat[k].read_bytes() for k in paths)


def test_long_ids_with_shared_first_hundred_characters_do_not_alias(tmp_path):
    archive = ConversationArchive(tmp_path / "conversations.sqlite3")
    ids = ["same_" + "x" * 110 + ch for ch in ("a", "b")]
    names = []
    for cid in ids:
        archive.create_conversation(title="t" * 160, conversation_id=cid)
        archive.append_message(cid, speaker="User", exact_text=cid)
        exported = archive.export_documents(cid, tmp_path / "exports")
        names.append(exported["json"].name)
        assert cid in exported["json"].read_text(encoding="utf-8")
    assert names[0] != names[1]


def test_library_exports_accept_long_or_unsafe_external_ids_and_preserve_messages(tmp_path):
    from modules.package_service import PackageService
    import zipfile
    archive = ConversationArchive(tmp_path / "conversations.sqlite3")
    unusual_ids = ["import_" + "A" * 170, "external/../../outside"]
    for cid in unusual_ids:
        archive.create_conversation(
            title="Very long imported conversation " + "a" * 170,
            conversation_id=cid,
            metadata={"owner": "u"},
        )
        archive.append_message(cid, speaker="User", exact_text="verbatim:\n  " + cid)
    service = PackageService(archive)
    exported = service.save_library_raw(unusual_ids, tmp_path / "library", owner_id="u")
    assert exported["verified"] is True
    entries = json.loads(exported["manifest"].read_text(encoding="utf-8"))["conversations"]
    assert len(entries) == 2
    assert all(len((exported["root"] / entry["path"]).name.encode()) <= 220 for entry in entries)
    for entry in entries:
        assert (exported["root"] / entry["path"]).resolve().is_relative_to(exported["root"].resolve())
        transcript = next((exported["root"] / entry["path"] / "Transcript").glob("*.json"))
        payload = json.loads(transcript.read_text(encoding="utf-8"))
        assert payload["messages"][0]["exact_text"] == "verbatim:\n  " + entry["conversation_id"]
    packaged = service.save_library_zip(unusual_ids, tmp_path / "library_zip", owner_id="u")
    assert packaged["verified"]
    with zipfile.ZipFile(packaged["zip"]) as z:
        assert z.testzip() is None
        assert len([x for x in z.namelist() if x.endswith(".jsonl")]) == 2

"""Two simultaneous successful exports must never share an output path."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import json
import zipfile
import pytest

from modules.conversation_archive import ConversationArchive
from modules.package_service import PackageService


@pytest.mark.parametrize("format", ["zip", "raw", "library_zip", "library_raw"])
def test_parallel_publishes_preserve_both_complete_results(tmp_path, monkeypatch, format):
    archive = ConversationArchive(tmp_path / "archive.sqlite3")
    cid = archive.create_conversation(title="Same title", metadata={"owner": "u"})
    archive.append_message(cid, speaker="User", exact_text="do not overwrite")
    service = PackageService(archive)
    monkeypatch.setattr(service, "_stamp", lambda: "IDENTICAL_TIMESTAMP")
    barrier = Barrier(2)
    publication_method = "_publish_file" if "zip" in format else "_publish_tree"
    original = getattr(service, publication_method)

    def simultaneous_publisher(staged, final):
        barrier.wait(timeout=15)
        return original(staged, final)

    monkeypatch.setattr(service, publication_method, simultaneous_publisher)

    def export():
        if format == "zip":
            return service.save_conversation_zip(cid, tmp_path / "output")["zip"]
        if format == "raw":
            return service.save_conversation_raw(cid, tmp_path / "output")["root"]
        if format == "library_zip":
            return service.save_library_zip([cid], tmp_path / "output", owner_id="u")["zip"]
        return service.save_library_raw([cid], tmp_path / "output", owner_id="u")["root"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(export) for _ in range(2)]
        results = [f.result(timeout=20) for f in futures]
    assert results[0] != results[1], "two successful exports must not alias the same file"
    assert all(x.exists() for x in results)
    if "zip" in format:
        for path in results:
            with zipfile.ZipFile(path) as z:
                assert z.testzip() is None
                assert any(name.endswith(".jsonl") for name in z.namelist())
    else:
        for path in results:
            assert (path / "manifest.json").exists() or (path / "library_manifest.json").exists()


def test_no_hardlink_filesystem_still_publishes_without_overwrite(tmp_path, monkeypatch):
    """Phone/removable media can reject hardlinks: publication must still work."""
    import errno
    import modules.package_service as packages
    archive = ConversationArchive(tmp_path / "archive.sqlite3")
    cid = archive.create_conversation(title="Phone offline")
    archive.append_message(cid, speaker="User", exact_text="keep both")
    service = PackageService(archive)
    monkeypatch.setattr(service, "_stamp", lambda: "SAME_TIMESTAMP")
    barrier = Barrier(2)
    original = service._publish_file

    def no_hardlinks(*args, **kwargs):
        raise OSError(errno.EOPNOTSUPP, "hardlinks unavailable")

    monkeypatch.setattr(packages.os, "link", no_hardlinks)

    def forced_race(staged, target):
        barrier.wait(timeout=15)
        return original(staged, target)

    monkeypatch.setattr(service, "_publish_file", forced_race)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(service.save_conversation_zip, cid, tmp_path / "exports") for _ in range(2)]
        results = [f.result(timeout=20)["zip"] for f in futures]
    assert results[0] != results[1] and all(x.exists() for x in results)
    for path in results:
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None

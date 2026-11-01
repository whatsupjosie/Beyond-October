"""A recording export must preserve source bytes and relink on a fresh host."""
import hashlib
import json
import shutil
import wave
from pathlib import Path
from zipfile import ZipFile
from concurrent.futures import ThreadPoolExecutor

import pytest

from modules.cameras import create_default_cameras
from modules.recording import ContainerFormat, create_recording_service


def recording(tmp_path):
    service = create_recording_service(tmp_path / "first", create_default_cameras())
    session = service.start_session("portable-take", ["wide_shot"], profile_id="audio_only",
                                    operator="engineer", countdown_seconds=0)
    source = service._session_dir(session.session_id) / "dialogue.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\x12\x00" * 8000)
    service.register_artifact(session.session_id, source)
    service.stop_session(session.session_id)
    return service, session, source


def test_source_hashes_and_relink_on_independent_data_tree(tmp_path, monkeypatch):
    service, session, source = recording(tmp_path)
    monkeypatch.setattr(service, "_find_ffmpeg", lambda: None)
    original = source.read_bytes()
    archive = service.export_session(session.session_id, container=ContainerFormat.MP4)
    with ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read("EXPORT_MANIFEST.json"))
        metadata = json.loads(bundle.read(session.session_id + ".json"))
        member = metadata["artifacts"][0]["file_path"]
        assert member.startswith("media/")
        assert bundle.read(member) == original
        assert manifest["files"][member]["sha256"] == hashlib.sha256(original).hexdigest()
        assert manifest["warnings"]
    second = create_recording_service(tmp_path / "other-machine", create_default_cameras())
    imported = second.import_session(archive)
    assert imported.artifacts[0].file_path.read_bytes() == original
    assert imported.artifacts[0].file_path.is_relative_to(second.recordings_dir)
    assert source.read_bytes() == original


def test_conversion_is_separate_from_original_media(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg unavailable")
    service, session, source = recording(tmp_path)
    original = source.read_bytes()
    archive = service.export_session(session.session_id, container=ContainerFormat.WAV)
    with ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read("EXPORT_MANIFEST.json"))
        derived = manifest["derived"][0]
        assert derived["path"].startswith("renders/")
        assert bundle.read(derived["source_member"]) == original
        assert bundle.read(derived["path"]).startswith(b"RIFF")
    assert source.read_bytes() == original


def test_missing_media_never_produces_a_successful_incomplete_archive(tmp_path, monkeypatch):
    service, session, source = recording(tmp_path)
    monkeypatch.setattr(service, "_find_ffmpeg", lambda: None)
    source.unlink()
    with pytest.raises(ValueError, match="Missing"):
        service.export_session(session.session_id, container=ContainerFormat.MP4)
    assert not list(service.exports_dir.glob("*.zip"))


def test_tampered_bundle_is_rejected_without_partial_import(tmp_path, monkeypatch):
    service, session, _ = recording(tmp_path)
    monkeypatch.setattr(service, "_find_ffmpeg", lambda: None)
    archive = service.export_session(session.session_id, container=ContainerFormat.MP4)
    tampered = tmp_path / "tampered.zip"
    with ZipFile(archive) as original, ZipFile(tampered, "w") as output:
        for item in original.infolist():
            content = original.read(item)
            output.writestr(item, content + b"changed" if item.filename.startswith("media/") else content)
    second = create_recording_service(tmp_path / "second", create_default_cameras())
    with pytest.raises(ValueError, match="integrity"):
        second.import_session(tampered)
    assert not (second.recordings_dir / session.session_id).exists()
    assert second.list_sessions() == []


def test_same_named_sources_keep_distinct_bytes(tmp_path, monkeypatch):
    service, session, source = recording(tmp_path)
    monkeypatch.setattr(service, "_find_ffmpeg", lambda: None)
    other = tmp_path / "external" / source.name
    other.parent.mkdir()
    other.write_bytes(source.read_bytes() + b"different-camera")
    service.register_artifact(session.session_id, other)
    archive = service.export_session(session.session_id, container=ContainerFormat.MP4)
    second = create_recording_service(tmp_path / "second", create_default_cameras())
    imported = second.import_session(archive)
    assert len({a.file_path for a in imported.artifacts}) == 2
    assert {a.file_path.read_bytes() for a in imported.artifacts} == {source.read_bytes(), other.read_bytes()}


def test_missing_encoder_never_renames_original_bytes_as_converted_media(tmp_path, monkeypatch):
    service, session, source = recording(tmp_path)
    monkeypatch.setattr(service, "_find_ffmpeg", lambda: None)
    dest = tmp_path / "fake.mp4"
    assert service._transcode_artifact(source, dest, service.get_profile(session.profile_id)) is False
    assert not dest.exists()


def test_existing_take_directory_cannot_be_overwritten_after_restart(tmp_path):
    service, session, source = recording(tmp_path)
    old_metadata = (source.parent / (session.session_id + ".json")).read_bytes()
    restarted = create_recording_service(service.base_dir, create_default_cameras())
    with pytest.raises(ValueError, match="already"):
        restarted.start_session(session.session_id, ["wide_shot"], profile_id="audio_only", operator="other")
    assert (source.parent / (session.session_id + ".json")).read_bytes() == old_metadata
    assert restarted.get_session(session.session_id).artifacts[0].file_path.read_bytes() == source.read_bytes()


def test_interrupted_capture_is_restored_as_interrupted_not_live(tmp_path):
    service = create_recording_service(tmp_path, create_default_cameras())
    session = service.start_session("interrupted", ["wide_shot"], profile_id="audio_only",
                                    operator="engineer", countdown_seconds=0)
    restored = create_recording_service(tmp_path, create_default_cameras()).get_session(session.session_id)
    assert restored.state.value == "stopped"
    assert restored.recovery["interrupted"] is True
    assert restored.recovery["previous_state"] == "active"
    assert restored.artifacts == []


def test_storage_reports_observed_disk_space_without_invented_cloud_status(tmp_path, monkeypatch):
    service = create_recording_service(tmp_path, create_default_cameras())
    from types import SimpleNamespace
    monkeypatch.setattr("modules.recording.shutil.disk_usage", lambda path: SimpleNamespace(free=23 * 1024 ** 3))
    status = service.storage_status()
    assert status["local_free_gb"] == 23
    assert status["cloud_used_gb"] is None
    assert status["backup_status"] == "not configured"


def test_simultaneous_exports_have_independent_completed_archives(tmp_path, monkeypatch):
    service, session, source = recording(tmp_path)
    monkeypatch.setattr(service, "_find_ffmpeg", lambda: None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        archives = list(pool.map(lambda _: service.export_session(session.session_id, container=ContainerFormat.MP4), range(2)))
    assert len(set(archives)) == 2
    for archive in archives:
        with ZipFile(archive) as bundle:
            metadata = json.loads(bundle.read(session.session_id + ".json"))
            assert bundle.read(metadata["artifacts"][0]["file_path"]) == source.read_bytes()


def test_metadata_write_failure_preserves_previous_complete_file(tmp_path, monkeypatch):
    service, session, source = recording(tmp_path)
    metadata = source.parent / (session.session_id + ".json")
    previous = metadata.read_bytes()

    def failed_replace(*args):
        raise OSError("simulated interrupted publication")

    monkeypatch.setattr("modules.recording.os.replace", failed_replace)
    with pytest.raises(OSError):
        service.mark_moment(session.session_id, "new marker")
    assert metadata.read_bytes() == previous
    assert list(source.parent.glob("*.tmp")) == []


def test_legacy_windows_paths_relink_without_original_machine(tmp_path):
    service = create_recording_service(tmp_path / "second", create_default_cameras())
    archive = tmp_path / "legacy.zip"
    payload = {"session_id": "legacy", "profile_id": "audio_only", "state": "stopped",
               "artifacts": [{"name": "old audio", "format": "wav", "file_path": "C:\\PubCast\\dialogue.wav"}]}
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("legacy.json", json.dumps(payload))
        bundle.writestr("media/dialogue.wav", b"original-source")
    imported = service.import_session(archive)
    assert imported.artifacts[0].file_path.read_bytes() == b"original-source"


@pytest.mark.parametrize("member", ["media/../dialogue.wav", "media/sub/dialogue.wav", "media/C:dialogue.wav"])
def test_nonportable_archive_paths_are_rejected_before_publication(tmp_path, member):
    service = create_recording_service(tmp_path / "second", create_default_cameras())
    archive = tmp_path / "invalid.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("invalid.json", json.dumps({"session_id": "invalid", "profile_id": "audio_only", "state": "stopped"}))
        bundle.writestr(member, b"source")
    with pytest.raises(ValueError, match="path"):
        service.import_session(archive)
    assert not (service.recordings_dir / "invalid").exists()

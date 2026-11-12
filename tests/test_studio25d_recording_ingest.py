"""Original encoded video, durable/resumable commits and ownership boundaries."""
import hashlib
import io
import json
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from zipfile import ZipFile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.cameras import CameraSource, CameraTransport, create_default_cameras
from modules.production_routes import create_production_router
from modules.recording import create_recording_service
from modules.studio25d_recording_ingest import CHUNK_BYTES, CHAIN_SEED, extend_chain, create_studio25d_recording_router


def auth(actor="producer", role="owner"):
    return {"Authorization": "Bearer " + create_access_token({"sub": actor, "role": role})}


@pytest.fixture(scope="module")
def encoded_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("encoded-source") / "source.webm"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=15",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "1.5",
                    "-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8", "-b:v", "2M",
                    "-c:a", "libopus", str(path)], check=True, timeout=30)
    data = path.read_bytes()
    assert len(data) > CHUNK_BYTES
    return data


def make_spec(data):
    chain = CHAIN_SEED
    for offset in range(0, len(data), CHUNK_BYTES):
        piece = data[offset:offset+CHUNK_BYTES]
        chain = extend_chain(chain, hashlib.sha256(piece).hexdigest(), len(piece))
    return {"take_id": "pubcast25d-ingest-take-001", "production_id": "pubcast25d-ingest-production",
            "source_id": "p25d_news_wide", "mime": "video/webm;codecs=vp9,opus", "bytes": len(data),
            "chain": chain, "width": 1280, "height": 720, "duration_ms": 1500,
            "capture_incomplete": False, "manifest": {"packageId": "news", "events": [{"type": "camera.cut", "offsetMs": 500}]}}


def app_at(path):
    cameras = create_default_cameras()
    cameras.register(CameraSource("p25d_news_wide", "News wide", "studio25d", "actual browser source",
                                  CameraTransport.VIRTUAL, "virtual://p25d_news_wide", tags=["studio25d"]))
    recording = create_recording_service(path, cameras)
    app = FastAPI()
    app.include_router(create_studio25d_recording_router(recording))
    app.include_router(create_production_router(cameras, recording, None))
    return TestClient(app), recording


def begin(client, data, **overrides):
    result = client.post("/api/studio25d/recordings", json=make_spec(data) | overrides, headers=auth())
    result.raise_for_status()
    return result.json()["id"]


def put(client, take, data, index, headers=None):
    content = bytes(data[index*CHUNK_BYTES:(index+1)*CHUNK_BYTES])
    return client.put(f"/api/studio25d/recordings/{take}/chunks/{index}", content=content,
                      headers=(headers or auth()) | {"Content-Type": "application/octet-stream", "X-Chunk-SHA256": hashlib.sha256(content).hexdigest()})


def complete(client, take, data, headers=None):
    for index in range((len(data)+CHUNK_BYTES-1)//CHUNK_BYTES):
        put(client, take, data, index, headers).raise_for_status()
    result = client.post(f"/api/studio25d/recordings/{take}/complete", headers=headers or auth())
    result.raise_for_status()
    return result.json()


def test_original_video_survives_restart_and_exports_exact_bytes(tmp_path, encoded_video):
    client, _ = app_at(tmp_path)
    take = begin(client, encoded_video)
    first = put(client, take, encoded_video, 0).json()
    assert first["received_bytes"] == CHUNK_BYTES and first["next_index"] == 1
    # Recreate the canonical service from disk; no original in-memory objects.
    client.close()
    client, recording = app_at(tmp_path)
    restored = client.get(f"/api/studio25d/recordings/{take}", headers=auth()).json()
    assert restored["next_index"] == 1
    assert put(client, take, encoded_video, 0).json()["next_index"] == 1
    receipt = complete(client, take, encoded_video)
    assert receipt["sha256"] == hashlib.sha256(encoded_video).hexdigest()
    media = client.get(f"/api/studio25d/recordings/{take}/media", headers=auth())
    assert media.content == encoded_video and media.headers["X-Source-SHA256"] == receipt["sha256"]
    assert receipt["media"]["streams"][0]["width"] == 1280
    assert any(s["codec_type"] == "audio" for s in receipt["media"]["streams"])
    assert len(recording.get_session(take).artifacts) == 1
    bundle = client.post(f"/api/recording/{take}/export", headers=auth(), json={"format": "webm"})
    bundle.raise_for_status()
    with ZipFile(io.BytesIO(bundle.content)) as archive:
        source = next(n for n in archive.namelist() if n.startswith("media/"))
        assert archive.read(source) == encoded_video
        manifest = json.loads(archive.read("EXPORT_MANIFEST.json"))
        assert manifest["derived"] == []
        assert manifest["files"][source]["sha256"] == receipt["sha256"]
        metadata = json.loads(archive.read(take + ".json"))
        assert metadata["ingest"]["spec"]["manifest"]["events"][0]["type"] == "camera.cut"
    # Portable import binds access to the importing account and retains provenance.
    imported_client, _ = app_at(tmp_path / "independent-host")
    imported = imported_client.post("/api/recording/import", headers=auth("new-owner"), files={"file": ("source.zip", bundle.content, "application/zip")})
    imported.raise_for_status()
    assert imported.json()["ingest"]["original_operator"] == "producer"
    assert imported_client.get(f"/api/studio25d/recordings/{take}/media", headers=auth("new-owner")).content == encoded_video


def test_private_take_cannot_leak_through_legacy_routes(tmp_path, encoded_video, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    client, _ = app_at(tmp_path)
    assert client.post("/api/studio25d/recordings", json=make_spec(encoded_video)).status_code == 403
    assert client.post("/api/studio25d/recordings", json=make_spec(encoded_video), headers=auth("viewer", "viewer")).status_code == 403
    take = begin(client, encoded_video)
    complete(client, take, encoded_video)
    outsider = auth("other-producer")
    for suffix in ["", "/media"]:
        assert client.get(f"/api/studio25d/recordings/{take}"+suffix, headers=outsider).status_code == 404
    assert client.get("/api/studio25d/recordings", headers=outsider).json()["takes"] == []
    assert client.get("/api/recording/sessions", headers=outsider).json() == []
    assert client.get("/api/recording/sessions").json() == []
    for action in ["export", "stop", "pause", "marker", "activate"]:
        assert client.post(f"/api/recording/{take}/{action}", headers=outsider, json={"label": "stolen"}).status_code == 404
    assert client.post("/api/studio/actions/recording.stop", headers=outsider, json={"session_id": take, "confirm": True}).status_code == 404


def test_creator_keeps_read_export_and_resume_rights_after_operator_role_change(tmp_path, encoded_video):
    client, _ = app_at(tmp_path)
    take = begin(client, encoded_video)
    viewer = auth("producer", "viewer")
    assert client.get(f"/api/studio25d/recordings/{take}", headers=viewer).status_code == 200
    assert client.post("/api/studio25d/recordings", json=make_spec(encoded_video), headers=viewer).json()["id"] == take
    # Ownership can resume this reservation; it cannot allocate a new take.
    assert client.post("/api/studio25d/recordings", json=make_spec(encoded_video) | {"take_id": "pubcast25d-unapproved-new-take"}, headers=viewer).status_code == 403
    complete(client, take, encoded_video, headers=viewer)
    assert client.get(f"/api/studio25d/recordings/{take}/media", headers=viewer).content == encoded_video
    result = client.post(f"/api/studio25d/recordings/{take}/bundle", headers=viewer)
    result.raise_for_status()
    assert result.headers["Cache-Control"] == "private, no-store"
    with ZipFile(io.BytesIO(result.content)) as archive:
        source = next(n for n in archive.namelist() if n.startswith("media/"))
        assert archive.read(source) == encoded_video
    assert client.post(f"/api/studio25d/recordings/{take}/bundle", headers=auth("other", "viewer")).status_code == 404


def test_chunk_order_hash_conflict_and_concurrent_lost_ack_replays(tmp_path, encoded_video):
    client, _ = app_at(tmp_path)
    take = begin(client, encoded_video)
    assert put(client, take, encoded_video, 1).status_code == 409
    bad = client.put(f"/api/studio25d/recordings/{take}/chunks/0", content=encoded_video[:CHUNK_BYTES],
                     headers=auth() | {"Content-Type": "application/octet-stream", "X-Chunk-SHA256": "0"*64})
    assert bad.status_code == 422
    with ThreadPoolExecutor(max_workers=4) as executor:
        replies = list(executor.map(lambda _: put(client, take, encoded_video, 0), range(4)))
    assert all(r.status_code == 200 and r.json()["next_index"] == 1 for r in replies)
    different = bytearray(encoded_video); different[100] ^= 1
    assert put(client, take, different, 0).status_code == 409
    changed = client.post("/api/studio25d/recordings", headers=auth(), json=make_spec(encoded_video) | {"duration_ms": 2000})
    assert changed.status_code == 409
    assert client.post(f"/api/studio25d/recordings/{take}/complete", headers=auth()).status_code == 409


def test_chunk_metadata_failure_is_repaired_without_rewriting_source(tmp_path, encoded_video, monkeypatch):
    client, recording = app_at(tmp_path)
    take = begin(client, encoded_video)
    original = recording._write_metadata
    monkeypatch.setattr(recording, "_write_metadata", lambda _: (_ for _ in ()).throw(OSError("disk failure")))
    assert put(client, take, encoded_video, 0).status_code == 507
    piece = recording.recordings_dir / take / "pieces" / "00000000.part"
    inode = piece.stat().st_mtime_ns
    monkeypatch.setattr(recording, "_write_metadata", original)
    assert client.get(f"/api/studio25d/recordings/{take}", headers=auth()).json()["next_index"] == 0
    assert put(client, take, encoded_video, 0).json()["next_index"] == 1
    assert piece.stat().st_mtime_ns == inode


def test_invalid_video_and_later_tampering_never_pass_as_saved_media(tmp_path, encoded_video):
    client, recording = app_at(tmp_path)
    fake = b"This is not video"
    take = begin(client, fake)
    put(client, take, fake, 0).raise_for_status()
    assert client.post(f"/api/studio25d/recordings/{take}/complete", headers=auth()).status_code == 422
    assert not recording.get_session(take).artifacts
    assert client.get(f"/api/studio25d/recordings/{take}/media", headers=auth()).status_code == 409
    real = begin(client, encoded_video, take_id="pubcast25d-second-good-take")
    complete(client, real, encoded_video)
    recording.get_session(real).artifacts[0].file_path.write_bytes(encoded_video[:-10] + b"XXXXXXXXXX")
    assert client.get(f"/api/studio25d/recordings/{real}/media", headers=auth()).status_code == 409
    assert client.post(f"/api/studio25d/recordings/{real}/complete", headers=auth()).status_code == 409
    assert client.post(f"/api/recording/{real}/export", headers=auth(), json={"format": "webm"}).status_code == 400


def test_another_worker_discovers_a_committed_take_and_abandon_keeps_source(tmp_path, encoded_video):
    client, recording = app_at(tmp_path)
    other, second_service = app_at(tmp_path)
    take = begin(client, encoded_video)
    put(client, take, encoded_video, 0).raise_for_status()
    complete(client, take, encoded_video)
    assert second_service.get_session(take).ingest["state"] == "complete"
    result = other.post(f"/api/recording/{take}/export", headers=auth(), json={"format": "webm"})
    assert result.status_code == 200
    partial = begin(client, encoded_video, take_id="pubcast25d-abandoned-take")
    put(client, partial, encoded_video, 0).raise_for_status()
    piece = recording.recordings_dir / partial / "pieces" / "00000000.part"
    assert client.post(f"/api/studio25d/recordings/{partial}/abandon", headers=auth("outsider")).status_code == 404
    assert client.post(f"/api/studio25d/recordings/{partial}/abandon", headers=auth()).json()["state"] == "abandoned"
    assert piece.read_bytes() == encoded_video[:CHUNK_BYTES]
    assert put(client, partial, encoded_video, 1).status_code == 409
    assert client.post(f"/api/studio25d/recordings/{take}/abandon", headers=auth()).status_code == 409


def test_final_metadata_failure_keeps_original_and_completion_is_retryable(tmp_path, encoded_video, monkeypatch):
    client, recording = app_at(tmp_path)
    take = begin(client, encoded_video)
    for index in range((len(encoded_video)+CHUNK_BYTES-1)//CHUNK_BYTES):
        put(client, take, encoded_video, index).raise_for_status()
    original = recording._write_metadata
    monkeypatch.setattr(recording, "_write_metadata", lambda _: (_ for _ in ()).throw(OSError("disk failure")))
    assert client.post(f"/api/studio25d/recordings/{take}/complete", headers=auth()).status_code == 507
    source = recording.recordings_dir / take / "program-original.webm"
    assert source.read_bytes() == encoded_video
    timestamp = source.stat().st_mtime_ns
    monkeypatch.setattr(recording, "_write_metadata", original)
    assert client.post(f"/api/studio25d/recordings/{take}/complete", headers=auth()).json()["state"] == "complete"
    assert source.stat().st_mtime_ns == timestamp


def test_nonfinite_control_json_and_oversize_chunks_are_rejected(tmp_path, encoded_video):
    client, _ = app_at(tmp_path)
    spec = make_spec(encoded_video)
    raw = json.dumps(spec).replace('"manifest": {', '"manifest": {"bad": 1e999,')
    assert client.post("/api/studio25d/recordings", content=raw, headers=auth() | {"Content-Type": "application/json"}).status_code == 422
    take = begin(client, encoded_video)
    response = client.put(f"/api/studio25d/recordings/{take}/chunks/0", content=b"x"*(CHUNK_BYTES+1),
                          headers=auth() | {"Content-Type": "application/octet-stream", "X-Chunk-SHA256": "0"*64})
    assert response.status_code == 413
    assert client.get(f"/api/studio25d/recordings/{take}", headers=auth()).json()["next_index"] == 0


def test_disk_space_and_failed_reservation_keep_retry_possible(tmp_path, encoded_video, monkeypatch):
    client, recording = app_at(tmp_path)
    import modules.studio25d_recording_ingest as module
    usage = module.shutil.disk_usage
    monkeypatch.setattr(module.shutil, "disk_usage", lambda _: type("Full", (), {"free": 0})())
    assert client.post("/api/studio25d/recordings", headers=auth(), json=make_spec(encoded_video)).status_code == 507
    monkeypatch.setattr(module.shutil, "disk_usage", usage)
    original = recording._write_metadata
    monkeypatch.setattr(recording, "_write_metadata", lambda _: (_ for _ in ()).throw(OSError("disk failure")))
    assert client.post("/api/studio25d/recordings", headers=auth(), json=make_spec(encoded_video)).status_code == 507
    monkeypatch.setattr(recording, "_write_metadata", original)
    assert begin(client, encoded_video)


@pytest.mark.parametrize("ingest", [True, {}, {"schema": "wrong"}, {"schema": "pubcast-encoded-take/1", "state": "complete"}])
def test_import_rejects_malformed_encoded_metadata_without_publishing(tmp_path, ingest):
    _, recording = app_at(tmp_path)
    name = "enc_" + "c"*40
    archive = tmp_path / "invalid.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr(name + ".json", json.dumps({"session_id": name, "profile_id": "browser_original", "operator": "original", "state": "stopped", "ingest": ingest}))
    with pytest.raises(ValueError, match="metadata"):
        recording.import_session(archive, operator="importer")
    assert not (recording.recordings_dir / name).exists()


@pytest.mark.parametrize("clock_source", ["take_metadata", "production_offset", "legacy_single_take"])
def test_capture_clock_survives_delayed_upload_and_selects_the_correct_take(tmp_path, encoded_video, clock_source):
    client, recording = app_at(tmp_path)
    spec = make_spec(encoded_video)
    base = "2026-10-01T10:11:12.345Z"
    expected = datetime.fromisoformat(base.replace("Z", "+00:00")).timestamp()
    selected = {"id": spec["take_id"], "startedAt": base}
    manifest = {"id": spec["production_id"], "startedAt": base,
                "recordings": [selected, {"id": "later-unselected-take", "startedAt": "2026-10-20T00:00:00Z"}],
                "media": {"id": "later-unselected-take", "startedAt": "2026-10-20T00:00:00Z"}}
    if clock_source == "production_offset":
        selected.pop("startedAt");selected["offsetMs"] = 1234;expected += 1.234
    if clock_source == "legacy_single_take":
        spec["take_id"] = spec["production_id"]
        manifest = {"id": spec["production_id"], "startedAt": base, "media": {"startedAt": base}}
    spec["manifest"] = manifest
    response = client.post("/api/studio25d/recordings", headers=auth(), json=spec)
    response.raise_for_status();take = response.json()["id"]
    session = recording.get_session(take)
    assert session.started_at == pytest.approx(expected, rel=0, abs=1e-6)
    assert session.ended_at == pytest.approx(expected + 1.5, rel=0, abs=1e-6)
    assert session.ingest["upload_started_at"] > session.started_at
    receipt = complete(client, take, encoded_video)
    assert receipt["capture_started_at"] == pytest.approx(expected, rel=0, abs=1e-6)
    saved = recording.get_session(take)
    assert saved.started_at == pytest.approx(expected, rel=0, abs=1e-6)
    assert saved.ended_at == pytest.approx(expected + 1.5, rel=0, abs=1e-6)


def test_independent_voice_validates_exports_and_keeps_source_capture_clock(tmp_path):
    path=tmp_path/'voice.webm'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=880:sample_rate=48000',
                    '-t','1.5','-c:a','libopus',str(path)],check=True,timeout=20)
    data=path.read_bytes();client,recording=app_at(tmp_path/'server')
    spec=make_spec(data)|{'mime':'audio/webm;codecs=opus','width':0,'height':0,
        'manifest':{'sourceTracks':[{'id':make_spec(data)['take_id'],'startedAt':'2026-11-01T12:00:00Z',
            'parentTakeId':'program-take-001','preFader':True}]}}
    response=client.post('/api/studio25d/recordings',json=spec,headers=auth());assert response.status_code==200,response.text
    take=response.json()['id']
    for index in range((len(data)+CHUNK_BYTES-1)//CHUNK_BYTES):assert put(client,take,data,index).status_code==200
    response=client.post(f'/api/studio25d/recordings/{take}/complete',headers=auth());assert response.status_code==200,response.text
    result=response.json();assert result['state']=='complete'
    assert result['media']['streams'][0]['codec_type']=='audio'
    assert result['capture_started_at']==datetime.fromisoformat('2026-11-01T12:00:00+00:00').timestamp()
    media=client.get(f'/api/studio25d/recordings/{take}/media',headers=auth());assert media.content==data
    archive=client.post(f'/api/studio25d/recordings/{take}/bundle',headers=auth());assert archive.status_code==200
    with ZipFile(io.BytesIO(archive.content)) as zipped:
        assert data in [zipped.read(n) for n in zipped.namelist() if n.endswith('.webm')]


def test_video_bytes_cannot_be_accepted_as_independent_voice(tmp_path,encoded_video):
    client,_=app_at(tmp_path)
    take=begin(client,encoded_video,mime='audio/webm',width=0,height=0)
    for index in range((len(encoded_video)+CHUNK_BYTES-1)//CHUNK_BYTES):assert put(client,take,encoded_video,index).status_code==200
    assert client.post(f'/api/studio25d/recordings/{take}/complete',headers=auth()).status_code==422

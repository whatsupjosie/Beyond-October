from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.cameras import create_default_cameras
from modules.production_routes import create_production_router
from modules.recording import create_recording_service


class FakeBlackBox:
    def __init__(self):
        self.events = []

    def record_event(self, event_type, *, source, actor, data):
        self.events.append({"event_type": event_type, "source": source, "actor": actor, "data": data})


class FakeHub:
    def __init__(self):
        self.events = []

    async def broadcast_system_event(self, event):
        self.events.append(event)


def make_client(tmp_path: Path):
    cameras = create_default_cameras()
    recording = create_recording_service(tmp_path, cameras)
    blackbox = FakeBlackBox()
    hub = FakeHub()
    app = FastAPI()
    app.include_router(create_production_router(cameras, recording, hub=hub, blackbox=blackbox))
    return TestClient(app), cameras, blackbox, hub


def test_studio_actions_manifest_is_hotspot_ready(tmp_path: Path):
    client, _, _, _ = make_client(tmp_path)

    response = client.get("/api/studio/actions", headers={"X-Client-Id": "director"})

    assert response.status_code == 200
    ids = {item["action_id"] for item in response.json()["actions"]}
    assert "camera.switch.program" in ids
    assert "recording.preflight" in ids
    assert "audio.stop_all" in ids


def test_studio_action_route_executes_and_records_blackbox(tmp_path: Path):
    client, cameras, blackbox, hub = make_client(tmp_path)

    response = client.post(
        "/api/studio/actions/camera.switch.program",
        json={"source_id": "medium_shot"},
        headers={"X-Client-Id": "director"},
    )

    assert response.status_code == 200
    assert response.json()["result"]["source_id"] == "medium_shot"
    assert cameras.get_program_source().source_id == "medium_shot"
    assert blackbox.events[-1]["event_type"] == "studio.action"
    assert blackbox.events[-1]["data"]["action_id"] == "camera.switch.program"
    assert hub.events[-1]["type"] == "studio_action"
    assert hub.events[-1]["payload"]["action_id"] == "camera.switch.program"


def test_studio_action_route_rejects_unconfirmed_recording_start(tmp_path: Path):
    client, _, _, _ = make_client(tmp_path)

    response = client.post(
        "/api/studio/actions/recording.start",
        json={},
        headers={"X-Client-Id": "director"},
    )

    assert response.status_code == 400
    assert "confirm" in response.json()["detail"]


def test_panic_cuts_program_and_finishes_capture_even_if_metadata_is_unwritable(tmp_path, monkeypatch):
    from modules.capture import SessionCapture

    cameras = create_default_cameras()
    service = create_recording_service(tmp_path, cameras)
    take = service.start_session("pending-write", ["wide_shot"], profile_id="broadcast_mp4",
                                 operator="operator", countdown_seconds=0)
    capture = SessionCapture(cameras, service)
    hub = FakeHub()
    state = {}
    hub.update_production_state = state.update
    observed = []

    async def finish(session_id):
        observed.append((session_id, state.get("blackout")))
    monkeypatch.setattr(capture, "finish", finish)
    app = FastAPI()
    app.include_router(create_production_router(cameras, service, hub, capture=capture))
    with TestClient(app) as client, monkeypatch.context() as fault:
        def write_failure(*args):
            raise OSError("recording volume unavailable")
        fault.setattr(service, "_write_metadata", write_failure)
        result = client.post("/api/production/panic").json()
    service.stop_session(take.session_id)
    assert result["ok"] is False and result["audio_muted"] is True
    assert observed == [(take.session_id, True)]


async def test_stop_waits_for_inflight_start_and_retries_unsaved_media(tmp_path, monkeypatch):
    import asyncio
    import pytest
    from modules.capture import SessionCapture

    cameras = create_default_cameras()
    service = create_recording_service(tmp_path, cameras)
    session = service.start_session("race", ["wide_shot"], profile_id="broadcast_mp4", operator="op", countdown_seconds=0)
    capture = SessionCapture(cameras, service)
    entered, release = asyncio.Event(), asyncio.Event()
    output = service._session_dir("race") / "wide_shot.mp4"
    class Encoder:
        errors = {}
        available = True
        active = False
        async def start(self, *args):
            entered.set()
            await release.wait()
            self.active = True
            return [output]
        def is_capturing(self, sid):
            return self.active
        async def stop(self, sid):
            self.active = False
            output.write_bytes(b"test capture")
            return [output]
    capture.engine = Encoder()
    start = asyncio.create_task(capture.start(session))
    await asyncio.wait_for(entered.wait(), 2)
    try:
        with monkeypatch.context() as fault:
            def failed_registration(*args):
                raise OSError("metadata offline")
            fault.setattr(service, "register_artifact", failed_registration)
            stop = asyncio.create_task(capture.finish("race"))
            await asyncio.sleep(0)
            release.set()
            await start
            with pytest.raises(OSError, match="metadata offline"):
                await stop
        assert capture.engine.active is False
        saved = await capture.finish("race")
        assert len(saved) == 1 and saved[0]["size_bytes"] == output.stat().st_size
        assert len(service.get_session("race").artifacts) == 1
    finally:
        release.set()
        await start
        service.stop_session("race")


async def test_pause_controls_encoder_and_stopping_while_paused_keeps_media(tmp_path, monkeypatch):
    import asyncio
    import shutil
    import signal
    import subprocess
    import pytest
    from modules.capture import SessionCapture

    if not hasattr(signal, "SIGSTOP") or not shutil.which("ffprobe"):
        pytest.skip("requires POSIX process suspension and ffprobe")
    cameras = create_default_cameras()
    service = create_recording_service(tmp_path, cameras)
    capture = SessionCapture(cameras, service)
    if not capture.engine.available:
        pytest.skip("requires FFmpeg")
    take = service.start_session("pause-test", ["wide_shot"], profile_id="broadcast_mp4",
                                 operator="op", countdown_seconds=0)
    try:
        [output] = await capture.start(take)
        proc = capture.engine._active[take.session_id][0]
        for _ in range(200):
            if Path(output).exists() and Path(output).stat().st_size:
                break
            await asyncio.sleep(.05)
        await asyncio.sleep(.5)
        with monkeypatch.context() as fault:
            def fail_write(*args):
                raise OSError("volume offline")
            fault.setattr(service, "_write_metadata", fail_write)
            with pytest.raises(OSError, match="volume offline"):
                await capture.set_paused(take.session_id, True)
        assert not proc.paused and take.state.value == "active"
        await capture.set_paused(take.session_id, True)
        assert proc.paused and take.state.value == "paused"
        status = Path(f"/proc/{proc.proc.pid}/status")
        if status.exists():
            for _ in range(100):
                if "T (stopped)" in status.read_text():
                    break
                await asyncio.sleep(.01)
            assert "T (stopped)" in status.read_text()
        await capture.set_paused(take.session_id, False)
        assert not proc.paused and take.state.value == "active"
        await capture.set_paused(take.session_id, True)
        [artifact] = await asyncio.wait_for(capture.finish(take.session_id), timeout=10)
        subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=codec_name", artifact["file_path"]], check=True)
    finally:
        await capture.shutdown()
        service.stop_session(take.session_id)


def test_console_stop_finalizes_media_before_it_closes_the_take(tmp_path, monkeypatch):
    from modules.capture import SessionCapture

    cameras = create_default_cameras()
    service = create_recording_service(tmp_path, cameras)
    take = service.start_session("console-stop", ["wide_shot"], profile_id="broadcast_mp4",
                                 operator="op", countdown_seconds=0)
    capture = SessionCapture(cameras, service)
    observed = []

    async def finish(session_id):
        observed.append(service.get_session(session_id).state.value)
        output = service._session_dir(session_id) / "existing-take.mp4"
        output.write_bytes(b"capture fixture")
        service.register_artifact(session_id, output)
        return []

    monkeypatch.setattr(capture, "finish", finish)
    app = FastAPI()
    app.include_router(create_production_router(cameras, service, FakeHub(), capture=capture))
    with TestClient(app) as client:
        url = "/api/studio/actions/recording.stop"
        assert client.post(url, json={"session_id": take.session_id}).status_code == 400
        assert not observed
        response = client.post(url, json={"session_id": take.session_id, "confirm": True})
    assert observed == ["active"]
    assert response.json()["result"]["artifacts"][0]["size_bytes"] == len(b"capture fixture")


def test_console_requires_a_boolean_for_recording_override(tmp_path):
    client, _, _, _ = make_client(tmp_path)
    for action in ("recording.preflight", "recording.start"):
        result = client.post(f"/api/studio/actions/{action}", json={"confirm": True, "host_override": "false"})
        assert result.status_code == 400 and "boolean" in result.json()["detail"]


def test_multi_camera_stop_preserves_media_and_names_the_missing_source(tmp_path):
    import shutil
    import subprocess
    import time
    import pytest
    from modules.cameras import CameraTransport

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("requires FFmpeg and ffprobe")
    cameras = create_default_cameras()
    missing = cameras.get("medium_shot")
    missing.transport = CameraTransport.FILE
    missing.endpoint = str(tmp_path / "offline-camera.mp4")
    service = create_recording_service(tmp_path, cameras)
    hub = FakeHub()
    app = FastAPI()
    app.include_router(create_production_router(cameras, service, hub))
    with TestClient(app) as client:
        start = client.post("/api/recording/start", json={"session_id": "two-cams",
                            "sources": ["wide_shot", "medium_shot"], "countdown_seconds": 0})
        assert start.status_code == 200
        output = service._session_dir("two-cams") / "wide_shot.mp4"
        deadline = time.monotonic() + 15
        while (not output.exists() or not output.stat().st_size) and time.monotonic() < deadline:
            time.sleep(.05)
        time.sleep(.5)
        result = client.post("/api/recording/two-cams/stop").json()
    assert result["state"] == "stopped"
    assert [a["name"] for a in result["artifacts"]] == ["wide_shot.mp4"]
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(output), "-frames:v", "1", "-f", "null", "-"], check=True)
    assert set(result["capture_errors"]) == {"medium_shot"}
    assert hub.events[-1]["payload"]["capture_errors"] == result["capture_errors"]
    reopened = create_recording_service(tmp_path, cameras).get_session("two-cams")
    assert reopened.to_dict()["capture_errors"] == result["capture_errors"]



async def test_encoding_assigns_distinct_paths_to_sources_with_overlapping_names(tmp_path):
    import shutil
    import pytest
    from dataclasses import replace
    from modules.capture import FFmpegCaptureEngine

    if not shutil.which("ffmpeg"):
        pytest.skip("requires FFmpeg")
    cameras = create_default_cameras()
    service = create_recording_service(tmp_path / "data", cameras)
    base = cameras.get("wide_shot")
    sources = [replace(base, source_id=name) for name in ("A/B", "A:B", "A_B-2")]
    previous = tmp_path / "A_B.mp4"
    previous.write_bytes(b"old source")
    engine = FFmpegCaptureEngine()
    try:
        paths = await engine.start("collision", sources, service.get_profile("broadcast_mp4"), tmp_path)
        assert len({p.name.casefold() for p in paths}) == len(sources)
        assert previous not in paths
    finally:
        await engine.stop("collision")
    assert previous.read_bytes() == b"old source"

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

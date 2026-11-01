import asyncio
import subprocess
import time
from pathlib import Path

import pytest

from modules.cameras_advanced import CameraMetadata, CameraSource, CameraTransport, CameraStatus
from modules.mocap_integration import Joint, MocapFrame, MocapStreamManager
from modules import pubworld_router


def test_pubworld_state_uses_bound_authoritative_provider():
    expected = {"camera": "cam1", "live": True}
    pubworld_router.configure_pubworld_state_provider(lambda: expected.copy())
    result = asyncio.run(pubworld_router.pubworld_state())
    assert result["available"] is True
    assert result["state"] == expected
    assert result["camera"] == "cam1"


def test_pubworld_state_fails_honestly_without_provider():
    pubworld_router.configure_pubworld_state_provider(None)
    result = asyncio.run(pubworld_router.pubworld_state())
    assert result["available"] is False
    assert result["state"] is None


class _Hub:
    def __init__(self):
        self.events = []

    async def broadcast_system_event(self, event):
        self.events.append(event)


def test_mocap_broadcasts_real_frame_and_reports_unbound_capabilities():
    hub = _Hub()
    manager = MocapStreamManager(hub=hub, pete=None)
    frame = MocapFrame(
        timestamp=int(time.time() * 1000),
        rig_id="rig-test",
        frame_number=1,
        joints={"hips": Joint(0.0, 1.0, 0.0)},
    )
    asyncio.run(manager._on_frame_received(frame))
    status = manager.get_status()
    assert status["recording_started"] is False
    assert status["capabilities"] == {
        "hub_broadcast": True,
        "avatar_sink": False,
        "recording_hook": False,
        "render_sink": False,
    }
    assert hub.events and hub.events[-1]["type"] == "mocap_frame"
    assert hub.events[-1]["frame"]["rigId"] == "rig-test"


def test_mocap_callbacks_are_invoked_only_when_bound():
    hub = _Hub()
    called = {"avatar": 0, "record": 0, "render": 0}

    def avatar_sink(avatar_id, bones, frame):
        called["avatar"] += 1
        assert avatar_id == "avatar-1"
        assert "root" in bones

    def recording_hook(frame):
        called["record"] += 1

    def render_sink(frame_dict):
        called["render"] += 1
        assert frame_dict["rigId"] == "rig-test"

    manager = MocapStreamManager(
        hub=hub,
        pete=object(),
        avatar_frame_sink=avatar_sink,
        recording_start_callback=recording_hook,
        render_frame_sink=render_sink,
    )
    manager.set_active_avatar("avatar-1")
    frame = MocapFrame(
        timestamp=int(time.time() * 1000),
        rig_id="rig-test",
        frame_number=2,
        joints={"hips": Joint(0.0, 1.0, 0.0)},
    )
    asyncio.run(manager._on_frame_received(frame))
    assert called == {"avatar": 1, "record": 1, "render": 1}
    assert manager.get_status()["recording_started"] is True


@pytest.mark.skipif(not Path("/usr/bin/ffmpeg").exists(), reason="ffmpeg unavailable")
def test_advanced_camera_file_capture_uses_real_frames(tmp_path):
    source = tmp_path / "sample.mp4"
    subprocess.run([
        "/usr/bin/ffmpeg", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=64x48:rate=5",
        "-t", "1", "-pix_fmt", "yuv420p", str(source),
    ], check=True)
    metadata = CameraMetadata(
        name="file-test",
        transport=CameraTransport.FILE_PLAYBACK,
        connection_string=str(source),
        width=64,
        height=48,
        fps=5.0,
    )
    camera = CameraSource("file-test", metadata)

    async def exercise():
        assert await camera.connect() is True
        assert await camera.start_capture() is True
        deadline = time.time() + 5
        while camera.metadata.total_frames == 0 and time.time() < deadline:
            await asyncio.sleep(0.05)
        assert camera.metadata.total_frames > 0
        frame = camera.get_latest_frame()
        assert frame is not None and len(frame) == 64 * 48 * 3
        await camera.stop_capture()
        assert camera.metadata.status == CameraStatus.OFFLINE

    asyncio.run(exercise())


def test_ndi_does_not_report_connected_without_backend():
    camera = CameraSource(
        "ndi-test",
        CameraMetadata(name="ndi", transport=CameraTransport.NDI_SOURCE, connection_string="source"),
    )
    assert asyncio.run(camera.connect()) is False
    assert camera.metadata.status == CameraStatus.ERROR
    assert "not installed" in camera.metadata.error_message

from modules.studio_control import StudioControl, StudioState


class _PeteNoVoice:
    is_non_speaking_shim = True

    async def speak(self, *args, **kwargs):
        raise AssertionError("non-speaking shim must never be called")


def test_studio_preflight_fails_closed_without_real_telemetry(tmp_path, monkeypatch):
    control = StudioControl(hub=None, pete=_PeteNoVoice(), data_dir=tmp_path)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    result = asyncio.run(control.run_preflight_sequence())
    assert result is False
    assert control.state == StudioState.IDLE
    assert any(not item.passed for item in control._preflight_checks)
    assert all("verified" not in item.message.lower() or not item.passed for item in control._preflight_checks)


def test_studio_preflight_can_pass_with_real_audio_telemetry(tmp_path, monkeypatch):
    control = StudioControl(hub=None, pete=_PeteNoVoice(), data_dir=tmp_path)
    control.audio_matrix.mic_inputs.update_signal(-30.0)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    async def no_dead_man():
        return None
    control._dead_man_switch = no_dead_man
    result = asyncio.run(control.run_preflight_sequence())
    assert result is True
    assert control.state == StudioState.LIVE
    assert all(item.passed for item in control._preflight_checks)
    asyncio.run(control.stop_recording())
    assert control.state == StudioState.IDLE


def test_studio_checkpoint_does_not_claim_media_recording(tmp_path):
    control = StudioControl(hub=None, pete=_PeteNoVoice(), data_dir=tmp_path)
    path = asyncio.run(control._save_recording("test"))
    payload = __import__("json").loads(path.read_text())
    assert payload["media_recording_saved"] is False
    assert "RecordingService" in payload["note"]


def test_studio_control_html_never_synthesizes_audio_meter_data():
    html = (Path(__file__).resolve().parents[1] / "static" / "studio_control_room.html").read_text()
    assert "startAudioSimulation" not in html
    assert "Simulate active audio" not in html
    assert "NO METER DATA" in html
    assert "All inputs verified" not in html
    assert "No unexpected signals" not in html

import io
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

from modules.cameras_advanced import CameraMetadata, CameraSource, CameraTransport


def make_camera():
    camera = CameraSource("cleanup", CameraMetadata(name="cleanup",
        transport=CameraTransport.FILE_PLAYBACK, connection_string="unused", width=1, height=1))
    camera.is_capturing = True
    return camera


def test_capture_closes_owned_pipes_even_when_process_already_exited(monkeypatch):
    process = SimpleNamespace(stdout=io.BytesIO(), stderr=io.BytesIO(), stdin=None,
        poll=Mock(return_value=0), terminate=Mock(), wait=Mock(), kill=Mock())
    monkeypatch.setattr(subprocess, "Popen", Mock(return_value=process))
    camera = make_camera()
    camera._capture_frames(["-i", "unused"])
    assert process.stdout.closed and process.stderr.closed
    assert camera.capture_process is None
    assert not camera.is_capturing


def test_capture_reaps_forced_kill_and_closes_pipes(monkeypatch):
    process = SimpleNamespace(stdout=io.BytesIO(), stderr=io.BytesIO(), stdin=None,
        poll=Mock(return_value=None), terminate=Mock(),
        wait=Mock(side_effect=[subprocess.TimeoutExpired("ffmpeg", 2), 0]), kill=Mock())
    monkeypatch.setattr(subprocess, "Popen", Mock(return_value=process))
    make_camera()._capture_frames(["-i", "unused"])
    process.kill.assert_called_once()
    assert process.wait.call_count == 2
    assert process.stdout.closed and process.stderr.closed

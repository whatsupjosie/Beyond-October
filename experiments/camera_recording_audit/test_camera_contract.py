"""Camera/recording integration contract tests for October's isolated experiment branch.

Run from repository root:
    python -m pytest -q experiments/camera_recording_audit/test_camera_contract.py

These tests do NOT assert GPU frame proof. They test control and media inputs separately.
"""
from pathlib import Path
import asyncio
import subprocess
import shutil

import pytest
from modules.cameras import create_default_cameras, CameraSource, CameraTransport
from modules.twin_engine_service import TwinEngineService, TwinEngineMode
from modules.capture import _build_ffmpeg_input, FFmpegCaptureEngine


def test_program_preview_cut_and_pose_events():
    cameras = create_default_cameras()
    events = []
    cameras.subscribe(events.append)
    assert cameras.get_program_source().source_id == "wide_shot"
    assert cameras.get_preview_source().source_id == "medium_shot"
    assert cameras.take()
    assert cameras.get_program_source().source_id == "medium_shot"
    assert cameras.get_preview_source().source_id == "wide_shot"
    assert cameras.update_pose("medium_shot", position=[1, 2, 3], fov=42)
    assert cameras.get("medium_shot").position == [1.0, 2.0, 3.0]
    assert len(events) == 3
    with pytest.raises(ValueError):
        cameras.update_pose("medium_shot", fov=180)


@pytest.mark.asyncio
async def test_twin_engine_mirrors_camera_but_does_not_claim_renderer():
    cameras = create_default_cameras()
    twin = TwinEngineService(camera_manager=cameras)
    health = await twin.startup()
    assert twin.mode == TwinEngineMode.DISCONNECTED
    assert twin.active_camera_id == cameras.get_program_source().source_id
    cameras.take()
    await asyncio.sleep(0)
    assert twin.active_camera_id == cameras.get_program_source().source_id
    await twin.shutdown()


def test_virtual_capture_is_test_pattern_not_pubworld():
    args = _build_ffmpeg_input("virtual", "virtual://wide_shot")
    assert args[:3] == ["-f", "lavfi", "-i"]
    assert "testsrc" in " ".join(args)
    assert "virtual://wide_shot" not in " ".join(args)


def test_real_ffmpeg_test_pattern_can_be_encoded(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("ffmpeg/ffprobe not installed")
    target = tmp_path / "camera_test.mp4"
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc=size=320x180:rate=15",
                    "-t", "1", "-c:v", "mpeg4", str(target)], check=True, timeout=30)
    assert target.exists() and target.stat().st_size > 0
    result = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0",
                             "-show_entries", "stream=width,height,nb_frames",
                             "-of", "csv=p=0", str(target)],
                            check=True, capture_output=True, text=True, timeout=15)
    assert "320,180,15" in result.stdout

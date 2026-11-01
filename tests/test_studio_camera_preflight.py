from pathlib import Path

from modules.cameras import CameraSource, CameraTransport, create_default_cameras
from modules.recording import create_recording_service
from modules.studio_camera_preflight import all_camera_visibility, recording_preflight, studio_readiness


def test_default_cameras_are_visible_and_recordable(tmp_path: Path):
    cameras = create_default_cameras()
    recording = create_recording_service(tmp_path, cameras)

    report = all_camera_visibility(cameras)

    assert report["program"] == "wide_shot"
    assert any(item["source_id"] == "wide_shot" and item["visible"] for item in report["cameras"])
    assert recording_preflight(cameras, recording, sources=["wide_shot"], profile_id="broadcast_mp4")["ready"] is True


def test_recording_preflight_blocks_unknown_offline_and_private_policy(tmp_path: Path):
    cameras = create_default_cameras()
    recording = create_recording_service(tmp_path, cameras)
    cameras.register(
        CameraSource(
            source_id="dressing_cam",
            name="Dressing Room",
            location="dressing",
            description="Private room",
            transport=CameraTransport.VIRTUAL,
            endpoint="virtual://dressing_cam",
        )
    )
    cameras.set_status("wide_shot", online=False)

    offline = recording_preflight(cameras, recording, sources=["wide_shot"], profile_id="broadcast_mp4")
    private = recording_preflight(cameras, recording, sources=["dressing_cam"], profile_id="broadcast_mp4")
    missing = recording_preflight(cameras, recording, sources=["missing"], profile_id="broadcast_mp4")

    assert offline["ready"] is False
    assert any(issue["code"] == "source_not_recordable" for issue in offline["issues"])
    assert private["ready"] is False
    assert any(issue["code"] == "privacy_forbidden" for issue in private["issues"])
    assert any(issue["code"] == "unknown_source" for issue in missing["issues"])


def test_studio_readiness_uses_program_camera_and_profiles(tmp_path: Path):
    cameras = create_default_cameras()
    recording = create_recording_service(tmp_path, cameras)

    report = studio_readiness(cameras, recording, audio_status={"buses": {}})

    assert report["ready"] is True
    assert report["program"] == "wide_shot"
    assert report["recording_profiles"] >= 1
    assert report["audio_ready"] is True

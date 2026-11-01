"""Never promote a 2.5D JPEG confidence preview into server video-recording status."""
import pytest
from modules.cameras import CameraSource, CameraTransport, create_default_cameras
from modules.recording import create_recording_service
from modules.studio_camera_preflight import camera_visibility_report


def test_browser_confidence_feed_is_not_server_recordable(tmp_path):
    cameras=create_default_cameras()
    source=CameraSource(
        source_id="p25d_news_wide",name="News wide",
        description="Only confidence JPEGs",location="studio25d",
        transport=CameraTransport.VIRTUAL,
        endpoint="virtual://p25d_news_wide",tags=["studio25d","news"])
    cameras.register(source)
    report=camera_visibility_report(source,cameras.status(source.source_id))
    assert report["visible"] is False
    assert report["recordable"] is False
    assert any(issue["code"]=="confidence_only" for issue in report["issues"])
    recording=create_recording_service(tmp_path,cameras)
    with pytest.raises(ValueError,match="confidence"):
        recording.start_session(None,[source.source_id],profile_id="broadcast_mp4",
                                operator="director",countdown_seconds=0,host_override=True)
    # This limitation must not accidentally block established virtual cameras.
    ordinary=cameras.get("wide_shot")
    assert ordinary is not None
    assert camera_visibility_report(ordinary,cameras.status("wide_shot"))["recordable"] is True

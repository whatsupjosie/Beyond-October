"""Contracts for PubPartner calibration UI and existing pipeline integration.

These are static checks; they do not replace browser interaction or API tests.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_calibration_ui_loaded_from_shared_pubpartner_page():
    html = read("static/pubpartner.html")
    js = read("static/pubpartner_calibration_ui.js")
    assert 'id="openCalibrationMenu"' in html
    assert 'id="calibrationGate"' in html
    assert '/static/pubpartner_calibration_ui.js' in html
    for marker in ("calibrationStart", "calibrationSubmit", "calibrationFinish",
                   "calibrationExtra", "calibrationApplyLesson", "calibrationDictate", "calibrationRecordAudio", "calibrationResume"):
        assert marker in html and marker in js


def test_existing_canonical_api_registered_in_both_hosts():
    standalone = read("pubpartner_app.py")
    pubcast = read("main.py")
    routes = read("modules/pubpartner_routes.py")
    assert "app.include_router(pubpartner_routes.router)" in standalone
    assert "application.include_router(pubpartner_routes.router)" in pubcast
    for uri in ("/calibration/interviews", "/calibration/moments"):
        assert uri in routes


def test_archive_uses_authenticated_scope_and_verbatim_source():
    routes = read("modules/pubpartner_routes.py")
    segment = routes.split('async def calibration_moments(', 1)[1]
    assert "_scoped_user_id(request=request, identity=identity)" in segment
    assert "spine.restore_source(" in segment
    assert "source_id=source_id" in segment


def test_approved_correction_uses_existing_relationship_guidance():
    ui = read("static/pubpartner_calibration_ui.js")
    core = read("modules/pubpartner_core.py")
    relationship = read("modules/pubpartner_relationship.py")
    assert "'/relationship/lessons'" in ui
    assert "status: 'confirmed'" in ui
    assert "self.relationship.compact(" in core
    assert 'globally_applicable = kind in {"boundary", "workflow", "identity"}' in relationship
    assert "calibration_id" in ui


def test_audio_capture_not_falsely_claimed():
    html = read("static/pubpartner.html")
    assert "It does not preserve the original audio" in html
    assert "Record voice sample (max 60 seconds)" in html
    routes = read("modules/pubpartner_routes.py")
    assert '@router.post("/calibration/interviews/{interview_id}/audio")' in routes
    assert '@router.get("/calibration/interviews/{interview_id}/audio/{audio_ref}")' in routes

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def test_safe_console_routes_are_declared():
    assert '@app.get("/safe-console"' in MAIN
    assert '@app.get("/recovery"' in MAIN


def test_pub_manager_routes_are_declared():
    assert '@app.get("/api/pub-manager/status"' in MAIN
    assert '@app.post("/api/pub-manager/action"' in MAIN
    assert '@app.get("/api/pub-manager/issue-report"' in MAIN
    assert '@app.get("/api/pub-manager/safe-actions"' in MAIN


def test_ready_status_routes_are_declared():
    assert '@app.get("/api/menu/coverage"' in MAIN
    assert '@app.get("/api/runtime-spine/status"' in MAIN
    assert '@app.get("/api/switchblade/status"' in MAIN
    assert '@app.post("/api/switchblade/route-preview"' in MAIN
    assert '@app.get("/api/voxel/block-kit/status"' in MAIN
    assert '@app.get("/api/voxel/block-kit/preview/capabilities"' in MAIN
    assert '@app.post("/api/voxel/block-kit/preview"' in MAIN


def test_runtime_scripts_are_loaded_on_key_pages():
    for rel in ["static/control.html", "static/stage.html", "static/stage_3d.html", "static/avatar_walk_test.html"]:
        html = (ROOT / rel).read_text(encoding="utf-8")
        assert "/static/program_audio_runtime.js" in html, rel
        assert "/static/avatar_glb_motion_consumer.js" in html, rel
        assert "/static/voxel_block_preview_client.js" in html, rel


def test_safe_console_link_exists_on_key_pages():
    for rel in ["static/control.html", "static/stage.html", "static/stage_3d.html", "static/avatar_walk_test.html"]:
        html = (ROOT / rel).read_text(encoding="utf-8")
        assert "/safe-console" in html, rel

"""Real host + real browser acceptance of a relocated offline data checkpoint.

No test client, mocked routes, model, microphone, or owner data. The media fixture
is an explicitly generated two-second VP9/Opus test pattern, imported through the
real recording API and played by the real Gallery after restoration.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest

from modules.cameras import create_default_cameras
from modules.credentials import CredentialStore, StoredModel
from modules.recording import ContainerFormat, create_recording_service

ROOT = Path(__file__).resolve().parents[1]
GL_ARGS = ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader",
           "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
           "--autoplay-policy=no-user-gesture-required"]


def _inventory(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def _ok(response: httpx.Response, *codes: int):
    assert response.status_code in (codes or (200, 201)), response.text[:1000]
    return response.json()


class Host:
    def __init__(self, data: Path, log: Path):
        self.data, self.log_path = data, log
        self.process = None
        self.output = None
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.base = f"http://127.0.0.1:{self.port}"

    def start(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("PUBCAST_")}
        # The launcher must read the persisted secrets, not a test-supplied key.
        self.output = self.log_path.open("w", encoding="utf-8")
        self.process = subprocess.Popen(
            [sys.executable, "run_reach.py", "--data-dir", str(self.data),
             "--port", str(self.port), "--no-browser", "--no-legacy-2i"],
            cwd=ROOT, env=env, stdout=self.output, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 90
        with httpx.Client(base_url=self.base, trust_env=False, timeout=2) as client:
            while True:
                try:
                    if client.get("/health").status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                if self.process.poll() is not None or time.monotonic() > deadline:
                    self.stop()
                    pytest.fail("Real launcher did not become ready: " + self.log_path.read_text()[-5000:])
                time.sleep(.1)

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
                pytest.fail("Host did not shut down cleanly")
        if self.output:
            self.output.close()


def _checkpoint_cli(*arguments: str) -> dict:
    completed = subprocess.run([sys.executable, "tools/pubcast_checkpoint.py", *arguments],
                               cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def _media_bundle(root: Path, channels: int = 1) -> tuple[Path, bytes]:
    executable = shutil.which("ffmpeg")
    assert executable, "This full acceptance test requires ffmpeg; media was not verified"
    service = create_recording_service(root, create_default_cameras())
    service.register_profile(replace(service.get_profile("broadcast_mp4"), profile_id="checkpoint-test",
                                     resolution="320x180", frame_rate="12", video_bitrate="1Mbps"))
    session = service.start_session("checkpoint-acceptance", ["wide_shot"],
                                    profile_id="checkpoint-test", operator="restore-owner", countdown_seconds=0)
    source = service._session_dir(session.session_id) / "recovery-test.webm"
    completed = subprocess.run(
        [executable, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
         "testsrc2=size=320x180:rate=12", "-f", "lavfi", "-i",
         "sine=frequency=440:sample_rate=48000", "-t", "2", "-c:v", "libvpx-vp9",
         "-deadline", "realtime", "-cpu-used", "8", "-c:a", "libopus", "-ac", str(channels), str(source)],
        capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    service.register_artifact(session.session_id, source, format=ContainerFormat.WEBM)
    service.stop_session(session.session_id)
    return service.export_session(session.session_id, container=ContainerFormat.WEBM), source.read_bytes()


@pytest.mark.parametrize("channels", [1, 2])
def test_actual_webm_export_produces_a_derived_clip_and_preserves_original(tmp_path, channels):
    bundle, original = _media_bundle(tmp_path / "assembly", channels)
    with ZipFile(bundle) as archive:
        manifest = json.loads(archive.read("EXPORT_MANIFEST.json"))
        assert len(manifest["derived"]) == 1, manifest["warnings"]
        derivative = manifest["derived"][0]
        assert derivative["audio_bitrate_setting"] == ("256000" if channels == 1 else "320k")
        assert archive.read(derivative["source_member"]) == original
        rendered = tmp_path / "derived.webm"
        rendered.write_bytes(archive.read(derivative["path"]))
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(rendered), "-f", "null", "-"],
                             capture_output=True, text=True, timeout=30)
    assert decoded.returncode == 0, decoded.stderr


def test_restore_real_host_sign_in_open_work_and_play_recording(tmp_path):
    from playwright.sync_api import sync_playwright

    before_seed = _inventory(ROOT / "data")
    original = tmp_path / "original-data"
    original.mkdir()
    username = "restore-owner"
    password = secrets.token_urlsafe(24) + "Aa9!"
    private_secret = secrets.token_urlsafe(32)
    credentials = CredentialStore(original)
    credentials.upsert_model(username, StoredModel(model_id="recovery-key-check", provider="test-fixture"),
                             secrets={"api_key": private_secret})
    host = Host(original, tmp_path / "original-host.log")
    restored_host = None
    try:
        host.start()
        with httpx.Client(base_url=host.base, trust_env=False, timeout=30) as api:
            setup = _ok(api.post("/api/auth/setup", json={"username": username, "password": password,
                                                         "confirm_password": password}), 201)
            original_token = setup["access_token"]
            api.headers["Authorization"] = "Bearer " + original_token

            document = {"title": "Recovery acceptance manuscript",
                        "state": {"committed": ["  These words must survive. Café 🎭"],
                                  "buffer": ["An unfinished line"], "pool": []},
                        "expected_revision": 0}
            _ok(api.put("/api/writers-room/documents/checkpoint-manuscript", json=document))
            saved_document = _ok(api.get("/api/writers-room/documents/checkpoint-manuscript"))

            source_text = b"print('restored workspace')\n"
            _ok(api.post("/api/foresight/workspace/file", json={"path": "Scripts/recovery.py",
                                                               "data": base64.b64encode(source_text).decode()}))
            conversation = _ok(api.post("/api/conversations", json={"title": "Recovery conversation"}))["conversation_id"]
            exact_message = "  Keep the original spacing.\nCafé 🎭\n"
            _ok(api.post(f"/api/conversations/{conversation}/messages",
                         json={"speaker": username, "exact_text": exact_message}))
            saved_conversation = _ok(api.get(f"/api/conversations/{conversation}"))
            _ok(api.post("/api/pubpartner/sessions", json={"session_id": "checkpoint-session",
                                                          "friend": "alex", "provider": "echo"}))
            _ok(api.post("/api/pubpartner/turns", json={"session_id": "checkpoint-session", "friend": "alex",
                                                       "provider": "echo", "message": "Preserve this exact exchange."}))
            saved_turns = _ok(api.get("/api/pubpartner/sessions/checkpoint-session/turns"))
            progress = {"room": "green_room", "view": "main", "pos": [800., 590.], "char": "repeat"}
            _ok(api.put("/api/studio/progress", json={"progress": progress}))
            layout = {"v": 3, "theme": "tigereye", "inactivePolicy": "reduced", "selected": None, "trays": []}
            _ok(api.put("/api/foresight/counter-layout", json={"layout": layout, "client_saved_at": 1760000000000}))

            bundle, source_media = _media_bundle(tmp_path / "media-assembly")
            _ok(api.post("/api/recording/import", files={"file": (bundle.name, bundle.read_bytes(), "application/zip")}))
            media_url = "/api/vod/checkpoint-acceptance/recovery-test.webm"
            assert api.get(media_url).content == source_media
        host.stop()

        key_before = (original / "secure/jwt_secret.txt").read_bytes()
        archive = tmp_path / "checkpoint.zip"
        created = _checkpoint_cli("create", "--data-dir", str(original), "--output", str(archive), "--offline",
                                   "--source-revision", "gpt-work-recovery-acceptance")
        _checkpoint_cli("verify", "--archive", str(archive), "--expected-sha256", created["sha256"])
        # Restoration must not accidentally resolve any absolute path in the old tree.
        original.rename(tmp_path / "original-unavailable")
        assert not original.exists()
        result = _checkpoint_cli("restore", "--archive", str(archive), "--destination", str(tmp_path / "recovered"),
                                 "--expected-sha256", created["sha256"])
        recovered = Path(result["data_dir"])
        assert (recovered / "secure/jwt_secret.txt").read_bytes() == key_before
        assert CredentialStore(recovered).get_secret(username, "recovery-key-check", "api_key") == private_secret

        restored_host = Host(recovered, tmp_path / "restored-host.log")
        restored_host.start()
        with httpx.Client(base_url=restored_host.base, trust_env=False, timeout=30) as api:
            assert _ok(api.get("/api/auth/status"))["setup_required"] is False
            assert api.post("/api/auth/login", json={"username": username, "password": "wrong-password"}).status_code == 401
            assert api.get("/api/writers-room/documents/checkpoint-manuscript").status_code == 401
            api.headers["Authorization"] = "Bearer " + original_token
            assert _ok(api.get("/api/auth/verify"))["username"] == username
            assert _ok(api.get("/api/writers-room/documents/checkpoint-manuscript")) == saved_document
            assert _ok(api.get(f"/api/conversations/{conversation}")) == saved_conversation
            assert _ok(api.get("/api/pubpartner/sessions/checkpoint-session/turns")) == saved_turns
            stored_file = _ok(api.get("/api/foresight/workspace/file", params={"path": "Scripts/recovery.py"}))
            assert base64.b64decode(stored_file["data"]) == source_text
            assert _ok(api.get("/api/studio/progress"))["progress"] == progress
            assert _ok(api.get("/api/foresight/counter-layout"))["layout"] == layout
            assert api.get(media_url).content == source_media

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=GL_ARGS)
            try:
                context = browser.new_context(viewport={"width": 1280, "height": 900})
                context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(restored_host.base + "/") else route.abort())
                page = context.new_page()
                page.goto(restored_host.base + "/login?next=/writers-room")
                page.fill("#loginUser", username)
                page.fill("#loginPass", password)
                page.click("#loginBtn")
                page.wait_for_url("**/writers-room", timeout=30000)
                page.wait_for_function("window.reachStarted !== undefined")
                page.evaluate("window.reachStarted")
                page.click("#shelfBtn")
                page.click('[data-document-id="checkpoint-manuscript"]')
                page.wait_for_function("document.querySelector('#docTitleDisplay').textContent === 'Recovery acceptance manuscript'")
                assert page.evaluate("getDocState().committed") == document["state"]["committed"]
                # Exercise the actual Gallery's normal playback element.
                page.goto(restored_host.base + "/gallery")
                page.get_by_text("recovery-test.webm", exact=True).first.click()
                page.locator("#modalPreviewWrap video").evaluate("video => video.play()")
                page.wait_for_function("""() => {
                    const video=document.querySelector('#modalPreviewWrap video');
                    return video && video.videoWidth === 320 && video.videoHeight === 180 && video.currentTime > .2;
                }""", timeout=30000)
                playback = page.evaluate("""() => {
                    const video=document.querySelector('#modalPreviewWrap video');
                    return {width:video.videoWidth,height:video.videoHeight,time:video.currentTime,error:video.error?.code||null};
                }""")
                assert playback["error"] is None
                context.close()
            finally:
                browser.close()

        evidence = os.environ.get("PUBCAST_RECOVERY_EVIDENCE_DIR")
        if evidence:
            output = Path(evidence)
            output.mkdir(parents=True, exist_ok=True)
            (output / "host-recovery.json").write_text(json.dumps({
                "ok": True, "source": "gpt-work", "platform": sys.platform,
                "python": sys.version.split()[0], "checkpoint_files": created["file_count"],
                "old_data_path_unavailable": True, "actual_launcher_restarted": True,
                "original_jwt_still_valid": True, "encrypted_secret_decrypted": True,
                "documents_conversations_workspace_pubpartner_layout_progress_restored": True,
                "browser_password_sign_in": True, "browser_opened_original_manuscript": True,
                "recording_sha256": hashlib.sha256(source_media).hexdigest(),
                "recording_bytes_exact": True, "gallery_playback": playback,
                "physical_devices_and_windows": "not tested"}, indent=2) + "\n", encoding="utf-8")
    finally:
        host.stop()
        if restored_host:
            restored_host.stop()
        assert _inventory(ROOT / "data") == before_seed, "Acceptance changed packaged seed data"

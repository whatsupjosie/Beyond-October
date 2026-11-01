"""Real authenticated backend + Chromium acceptance for the television studio.

Run: python -m pytest -q tests/test_production25d_browser.py
No provider keys, microphone, display server or external services are required.
"""
from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
GL_ARGS = ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader",
           "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
           "--autoplay-policy=no-user-gesture-required"]
GENRES = ("news", "late_night", "debate", "political_discussion", "audience", "game", "variety", "general")


@pytest.fixture(scope="module")
def production_server(tmp_path_factory):
    root = tmp_path_factory.mktemp("studio25d-server")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "PUBCAST_DATA_DIR": str(root / "data"),
           "PUBCAST_ENFORCE_AUTH": "1", "PUBCAST_JWT_SECRET": secrets.token_urlsafe(48)}
    base = f"http://127.0.0.1:{port}"
    with (root / "server.log").open("w") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1",
                                    "--port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=base, timeout=2, trust_env=False) as api:
                deadline = time.monotonic() + 30
                while True:
                    try:
                        if api.get("/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if process.poll() is not None or time.monotonic() > deadline:
                        pytest.fail("Backend did not start: " + (root / "server.log").read_text()[-6000:])
                    time.sleep(.1)
                password = secrets.token_urlsafe(24) + "A9!"
                result = api.post("/api/auth/setup", json={"username": "engineer", "password": password,
                                                          "confirm_password": password})
                assert result.status_code == 201, result.text
                yield base, result.json(), api
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture(scope="module")
def production_browser():
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=GL_ARGS)
        except pw.Error as exc:
            pytest.skip("Chromium unavailable: " + str(exc).splitlines()[0])
        yield browser
        browser.close()


@pytest.fixture
def studio(production_server, production_browser):
    base, auth, _ = production_server
    context = production_browser.new_context(viewport={"width": 1440, "height": 1000})
    import json
    context.add_init_script("sessionStorage.setItem('pubcast_token'," + json.dumps(auth["access_token"]) + ");"
                            "sessionStorage.setItem('pubcast_user'," + json.dumps(json.dumps({"username": "engineer", "role": "owner"})) + ");")
    page = context.new_page()
    page.problems = []
    page.on("pageerror", lambda exc: page.problems.append(str(exc)))
    page.goto(base + "/static/production25d.html")
    page.wait_for_function("document.documentElement.dataset.production25d === 'ready'")
    yield page, context
    context.close()


def wait_for_actors(page):
    page.wait_for_function("""() => {
      const id = PubCast25DStudio.state().package;
      return !!window.PubCastGLB && PubCast25D.PACKAGES[id].performers.every(
        p => PubCastGLB.has('p25d-' + id + '-' + p.id));
    }""", timeout=30000)


@pytest.mark.parametrize("genre", GENRES)
def test_each_genre_loads_actual_glb_actors_and_distinct_camera_pixels(studio, genre):
    page, _ = studio
    page.evaluate("id => PubCast25DStudio.loadGenre(id)", genre)
    wait_for_actors(page)
    page.wait_for_function("document.querySelector('#program').getContext('2d').getImageData(40,40,1,1).data[3] > 0")
    assert page.evaluate("program.toDataURL() !== preview.toDataURL()")
    assert page.problems == []
    evidence = os.environ.get("PUBCAST_EVIDENCE_DIR")
    if evidence:
        Path(evidence).mkdir(parents=True, exist_ok=True)
        page.locator("#program").screenshot(path=str(Path(evidence) / (genre + ".png")))
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_makehuman_wave_advances_actual_rig_pixels(studio):
    page, _ = studio
    wait_for_actors(page)
    result = page.evaluate("""async () => {
      const g = PubCastGLB, id = 'gesture-probe';
      await g.load(id, './world/test_avatars/MakeHuman_Female.glb', 'Gesture probe');
      const canvas = document.createElement('canvas'); canvas.width = 400; canvas.height = 400;
      const ctx = canvas.getContext('2d');
      function draw(dt) {
        ctx.clearRect(0, 0, 400, 400);
        g.draw(ctx, id, 200, 380, 340, {moving:false, dt});
        return ctx.getImageData(0, 0, 400, 400).data;
      }
      const before = draw(0);
      const played = g.playClip(id, 'wave');
      for (let i=0;i<8;i++) draw(.1);
      const after = draw(0);
      let changed = 0;
      for (let i=0;i<before.length;i++) if (Math.abs(before[i]-after[i]) > 20) changed++;
      g.clear(id);
      return {played, changed};
    }""")
    assert result["played"]
    assert result["changed"] > 100, result
    assert page.problems == []


def test_two_real_pages_share_cut_and_actual_remote_frames(studio, production_server):
    page, context = studio
    wait_for_actors(page)
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    page.wait_for_function("document.querySelector('#liveMedia').textContent.includes('CONFIRMED')")
    director = context.new_page()
    director.problems = []
    director.on("pageerror", lambda exc: director.problems.append(str(exc)))
    director.goto(production_server[0] + "/static/director_switcher.html")
    director.wait_for_function("""() => {
      const img = document.querySelector('#programMonitor img');
      return img && !img.hidden && img.naturalWidth === 640;
    }""", timeout=20000)
    old = page.evaluate("PubCast25DStudio.state()")
    assert director.evaluate("cut()") is True
    page.wait_for_function("id => PubCast25DStudio.state().program === id", arg=old["preview"])
    director.wait_for_function("document.querySelector('#programSource').textContent.includes('REAL 2.5D FRAME')")
    page.click("#stop")
    page.wait_for_function("!PubCast25DStudio.state().session")
    director.wait_for_function("document.querySelector('#programMonitor img').hidden")
    assert page.problems == []
    assert director.problems == []


def test_real_recording_reopens_after_reload_and_plays(studio):
    page, _ = studio
    wait_for_actors(page)
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    page.click("#record")
    page.wait_for_function("PubCast25DStudio.state().recording")
    page.wait_for_timeout(1500)  # Capture genuine time-varying media, not a mocked blob.
    page.click("#recordStop")
    page.wait_for_function("!PubCast25DStudio.state().recording")
    page.click("#stop")
    page.wait_for_function("!PubCast25DStudio.state().session")
    page.reload()
    page.wait_for_function("document.documentElement.dataset.production25d === 'ready'")
    page.click("#sessionList button")
    page.wait_for_function("playback.readyState >= 2 && playback.videoWidth === 1280")
    page.evaluate("playback.play()")
    page.wait_for_function("playback.currentTime > .1")
    assert page.locator("#alert").inner_text() == ""
    assert page.problems == []


def test_anonymous_cannot_drive_shared_cameras(production_server):
    _, _, api = production_server
    assert api.post("/api/switcher/cut").status_code == 401
    assert api.get("/api/studio25d/media/status").status_code in {401, 403}


def record_short_take(page):
    page.click("#record")
    page.wait_for_function("PubCast25DStudio.state().recording")
    page.wait_for_timeout(1100)
    page.click("#recordStop")
    page.wait_for_function("!PubCast25DStudio.state().recording")


def test_multiple_takes_keep_original_media_bytes(studio):
    page, _ = studio
    wait_for_actors(page)
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    record_short_take(page)
    first = page.evaluate("""async () => {
      const session = (await PubCast25DStore.list())[0];
      const item = await PubCast25DStore.read(session.id);
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await item.blob.arrayBuffer()))).join(',');
      return {session:session.id, take:session.media.id || session.id, hash};
    }""")
    page.click("#moveRight")
    record_short_take(page)
    result = page.evaluate("""async first => {
      const item = await PubCast25DStore.read(first.session, first.take);
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await item.blob.arrayBuffer()))).join(',');
      return {count:item.session.recordings?.length || 0, hash};
    }""", first)
    assert result["hash"] == first["hash"], "Starting a second take replaced the first recording"
    assert result["count"] == 2
    page.click("#stop")
    page.wait_for_function("!PubCast25DStudio.state().session")
    page.reload()
    page.wait_for_function("document.documentElement.dataset.production25d === 'ready'")
    assert page.locator("#sessionList button").count() == 2


def test_failed_storage_keeps_a_downloadable_take_and_retries(studio, tmp_path):
    page, _ = studio
    wait_for_actors(page)
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    page.evaluate("""() => {
      window.originalStudioSave = PubCast25DStore.save;
      PubCast25DStore.save = (session, blob) => blob
        ? Promise.reject(new DOMException('Storage full', 'QuotaExceededError'))
        : originalStudioSave(session, blob);
    }""")
    record_short_take(page)
    assert page.locator("#recoveryPanel").is_visible()
    assert page.locator("#record").is_disabled()
    with page.expect_download() as download:
        page.click("#recoveryDownload")
    downloaded = download.value
    downloaded.save_as(tmp_path / "recovered.webm")
    assert (tmp_path / "recovered.webm").stat().st_size > 1000
    page.evaluate("() => { PubCast25DStore.save = originalStudioSave; }")
    page.click("#recoverySave")
    page.wait_for_function("document.querySelector('#recoveryPanel').hidden")
    page.click("#stop")
    page.wait_for_function("!PubCast25DStudio.state().session")
    page.click("#sessionList button")
    page.wait_for_function("playback.readyState >= 2 && playback.videoWidth === 1280")
    # The deliberate storage exception is logged; it must have a recovery path.
    assert page.locator("#alert").inner_text() == ""


def test_recorder_error_preserves_available_media_as_incomplete(studio):
    page, _ = studio
    wait_for_actors(page)
    page.evaluate("""() => {
      const NativeRecorder=window.MediaRecorder;
      window.MediaRecorder=class extends NativeRecorder {
        constructor(...args){super(...args);window.testRecorder=this;}
      };
    }""")
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    page.click("#record")
    page.wait_for_function("PubCast25DStudio.state().recording")
    page.wait_for_timeout(1100)
    page.evaluate("testRecorder.dispatchEvent(new Event('error'))")
    page.click("#recordStop")
    page.wait_for_function("!PubCast25DStudio.state().recording")
    result = page.evaluate("""async () => {
      const session=(await PubCast25DStore.list())[0];
      const item=await PubCast25DStore.read(session.id);
      return {incomplete:session.media.incomplete,bytes:item.blob.size};
    }""")
    assert result["incomplete"] is True and result["bytes"] > 1000
    assert "INCOMPLETE" in page.locator("#sessionList").inner_text()


def test_remote_panic_stops_real_capture_blacks_program_and_silences_audio(studio, production_server):
    page, _ = studio
    wait_for_actors(page)
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    page.click("#record")
    page.wait_for_function("PubCast25DStudio.state().recording")
    page.evaluate("""() => {
      const audio=PubcastProgramAudio, ctx=audio.context;
      const osc=ctx.createOscillator();osc.frequency.value=440;
      window.panicAnalyser=ctx.createAnalyser();panicAnalyser.fftSize=512;
      audio.master.connect(panicAnalyser);osc.connect(audio.master);osc.start();
      window.panicTone=osc;
      window.panicRMS=()=>{
        const values=new Float32Array(512);panicAnalyser.getFloatTimeDomainData(values);
        return Math.sqrt(values.reduce((sum,value)=>sum+value*value,0)/values.length);
      };
    }""")
    page.wait_for_function("panicRMS() > .1")
    page.wait_for_timeout(1100)
    _, auth, api = production_server
    response = api.post("/api/production/panic", headers={"Authorization": "Bearer " + auth["access_token"]})
    assert response.status_code == 200 and response.json()["ok"] is True
    page.wait_for_function("!PubCast25DStudio.state().recording")
    page.wait_for_function("panicRMS() < .00001")
    page.wait_for_function("program.getContext('2d').getImageData(640,360,1,1).data.slice(0,3).every(x=>x===0)")
    assert "PANIC" in page.locator("#state").inner_text()
    assert page.evaluate("async () => ((await PubCast25DStore.list())[0].media.bytes > 1000)")
    page.evaluate("panicTone.stop()")

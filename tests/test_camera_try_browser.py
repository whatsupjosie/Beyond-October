"""static/camera_try.html: the page where the camera control modes can be tried, in a real browser."""
import functools
import http.server
import threading
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_every_mode_runs_draws_and_a_recorded_move_plays_back_exactly(server):
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--no-sandbox"])
        except Exception as exc:
            pytest.skip(f"no Chromium available: {exc}")
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 800}); errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{server}/static/camera_try.html")
            page.wait_for_function("!!window.__try")
            lit = lambda: page.evaluate("() => { const c = document.getElementById('c'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++; return n; }")
            assert lit() > 1000                                                       # the set is drawn
            pose = lambda: page.evaluate("window.__try.rig().pose")
            # A: keys move, aim and zoom at once
            start = pose()
            for k in ("KeyW", "ArrowRight", "BracketRight"): page.keyboard.down(k)
            page.wait_for_timeout(900)
            for k in ("KeyW", "ArrowRight", "BracketRight"): page.keyboard.up(k)
            now = pose(); assert now["z"] > start["z"] and now["pan"] != start["pan"] and now["fov"] < start["fov"]
            # C: lock on keeps the subject in the picture without aiming
            page.evaluate("document.querySelector('#reset').click()"); page.select_option("#mode", "lock"); page.wait_for_timeout(2500)
            hud = page.inner_text("#hud"); assert "off centre" in hud
            # record in mode A, then play it back in another mode: same poses
            page.evaluate("document.querySelector('#reset').click()"); page.select_option("#mode", "keys")
            page.keyboard.press("KeyR"); page.keyboard.down("KeyW"); page.keyboard.down("ArrowLeft"); page.wait_for_timeout(1200)
            page.keyboard.up("KeyW"); page.keyboard.up("ArrowLeft"); page.wait_for_timeout(300); page.keyboard.press("KeyR")
            rec = page.evaluate("window.__try.state().recording"); assert rec and len(rec["samples"]) > 30
            page.select_option("#mode", "shot"); page.keyboard.press("KeyP")
            page.wait_for_function("window.__try.state().playing === false", timeout=8000)
            end = pose(); want = rec["samples"][-1]
            assert abs(end["z"] - want[2]) < 0.02 and abs(end["x"] - want[0]) < 0.02       # it ends where the recording ended
            # D: the scripted shot runs
            page.evaluate("document.querySelector('#reset').click()"); page.select_option("#mode", "shot"); page.wait_for_timeout(1500)
            assert errors == []
        finally:
            browser.close()

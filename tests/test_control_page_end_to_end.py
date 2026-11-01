"""The Control page in a real browser against the real app: a working Vision Mixer, key assignment that is kept, and the camera
operator station moving a real camera, recording the move, saving it and playing it back exactly.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def host(tmp_path_factory):
    data = tmp_path_factory.mktemp("control_page_e2e")
    port = _free_port()
    env = dict(os.environ, PUBCAST_DATA_DIR=str(data), PYTHONUNBUFFERED="1")
    env.pop("PUBCAST_ENFORCE_AUTH", None)
    log = open(data / "host.log", "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
                            cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            if proc.poll() is not None:
                log.flush()
                raise AssertionError("host exited:\n" + (data / "host.log").read_text(encoding="utf-8")[-3000:])
            try:
                if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                    break
            except httpx.RequestError:
                pass
            time.sleep(0.2)
        else:
            raise AssertionError("host did not come up")
        password = secrets.token_urlsafe(20)
        owner = httpx.post(base + "/api/auth/setup", json={"username": "control-owner", "password": password, "confirm_password": password}, timeout=10).json()
        yield base, owner["access_token"]
    finally:
        proc.terminate()
        try:
            proc.wait(15)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(5)
        log.close()


def state(base): return httpx.get(base + "/api/switcher/state", timeout=10).json()
def pose(base, cam): return httpx.get(base + f"/api/switcher/pose/{cam}", timeout=10).json()


@pytest.fixture()
def page(host):
    host, token = host
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--no-sandbox"])
        except Exception as exc:
            pytest.skip(f"no Chromium available: {exc}")
        ctx = browser.new_context(viewport={"width": 1500, "height": 950})
        ctx.add_init_script("sessionStorage.setItem('pubcast_token', %s); sessionStorage.setItem('pubcast_user', JSON.stringify({username:'control-owner',user_id:'control-owner',role:'owner'}));" % json.dumps(token))
        pg = ctx.new_page(); pg.problems = []
        pg.on("pageerror", lambda e: pg.problems.append(str(e)))
        pg.goto(host + "/control")
        pg.wait_for_function("!!window.PubCastControlKeys && !!window.PubCastSwitcher && !!window.PubCastCameraStation", timeout=30000)
        pg.click('.nav-btn[data-room="control"]')                          # the page opens on the Dressing room; the switcher is in the Control Room
        pg.wait_for_function("document.querySelectorAll('#cam-list button').length > 0", timeout=15000)
        pg.base = host; pg.token = token
        yield pg
        ctx.close(); browser.close()


def settle(page, ms=700): page.wait_for_timeout(ms)


def known_only(problems):
    """The page already threw 'Identifier WSHub has already been declared' before this work (base.html and control.html both load ws.js); that one is ignored, any other is a failure."""
    return [p for p in problems if 'WSHub' not in p]


def test_the_vision_mixer_works_by_mouse_and_by_key(page):
    base = page.base; srcs = state(base)["sources"]; assert len(srcs) >= 2, srcs
    a, b = srcs[0]["id"], srcs[1]["id"]
    page.locator(f'#cam-list button[data-source="{a}"]').click(); settle(page)
    assert state(base)["preview"] == a
    page.click("#vm-cut"); settle(page); assert state(base)["program"] == a                       # Cut: preview goes to program
    page.keyboard.press("Digit2"); settle(page); assert state(base)["preview"] == b                 # key 2: preview camera 2
    page.keyboard.press("Space"); settle(page); assert state(base)["program"] == b                  # Space: cut
    page.keyboard.press("Numpad1"); settle(page); assert state(base)["program"] == a                # Numpad 1: straight to program
    page.keyboard.press("Digit2"); settle(page)
    page.keyboard.press("KeyF"); settle(page, 900)                                                  # F: fade to the preview
    s = state(base); assert s["program"] == b and s["transition"]["type"] == "dissolve" and s["transition"]["duration_ms"] == 400
    assert "Space Cut" in page.inner_text(".muted.small[data-key-hint]")
    assert known_only(page.problems) == []


def test_assigning_a_key_asks_the_question_takes_the_answer_and_keeps_it(page):
    base = page.base; srcs = state(base)["sources"]; a = srcs[0]["id"]
    page.click("#ck-assign")
    page.click("#vm-cut")                                                                             # in assign mode a click asks, it does not cut
    assert page.locator(".pck-prompt").inner_text() == "Where would you like the Cut button?"
    before = state(base)["program"]
    page.keyboard.press("KeyX"); settle(page, 300)
    assert page.evaluate("PubCastControlKeys.km.bindings('switcher').cut") == "KeyX"
    assert page.locator("[data-code=KeyX] .pck-name").inner_text() == "Cut"
    assert state(base)["program"] == before
    page.click("#ck-assign")                                                                          # done assigning
    page.locator(f'#cam-list button[data-source="{a}"]').click(); settle(page)
    page.keyboard.press("Space"); settle(page); assert state(base)["program"] != a or before == a   # Space no longer cuts
    page.keyboard.press("KeyX"); settle(page); assert state(base)["program"] == a                    # X does
    assert "X Cut" in page.inner_text(".muted.small[data-key-hint]")
    # taking a key that is in use asks first
    page.click("#ck-assign"); page.click("#vm-take"); page.keyboard.press("KeyX")
    assert "already does something" in page.locator(".pck-prompt").inner_text()
    page.keyboard.press("Escape"); page.keyboard.press("Escape")
    assert page.evaluate("PubCastControlKeys.km.bindings('switcher').fade") == "KeyF"
    # it is kept on the host and survives a reload
    page.wait_for_timeout(1500)
    got = httpx.get(base + "/api/keymap", headers={"Authorization": "Bearer " + page.token}, timeout=10).json()
    assert got["keymap"] and got["keymap"]["switcher"]["cut"] == "KeyX", got
    page.reload(); page.wait_for_function("!!window.PubCastControlKeys", timeout=30000); page.wait_for_timeout(800)
    assert page.evaluate("PubCastControlKeys.km.bindings('switcher').cut") == "KeyX"
    assert known_only(page.problems) == []


def test_the_camera_station_moves_a_real_camera_records_saves_and_plays_back_exactly(page):
    base = page.base; cam = state(base)["sources"][0]["id"]
    page.click('[data-station="camera"]')
    assert page.is_visible("#station-camera") and page.evaluate("PubCastControlKeys.km.activeStation()") == "camera"
    page.select_option("#cs-camera", cam); page.wait_for_function("PubCastCameraStation.rig() !== null", timeout=10000); settle(page, 300)
    start = pose(base, cam)
    # held keys move and aim at once, and the real camera follows
    page.locator("#cs-hud").click()
    page.keyboard.down("KeyW"); page.keyboard.down("ArrowRight"); settle(page, 900); page.keyboard.up("KeyW"); page.keyboard.up("ArrowRight"); settle(page, 800)
    moved = pose(base, cam)
    assert moved["position"] != start["position"] and moved["rotation"][1] != start["rotation"][1]
    assert page.locator(".pck-prompt").is_visible() or page.locator(".pck-overlay").is_visible()      # the transparent keyboard shows at the camera station
    # record a move, stop, name it, save it
    page.click("#cs-record")
    page.keyboard.down("KeyD"); page.keyboard.down("BracketRight"); settle(page, 1000); page.keyboard.up("KeyD"); page.keyboard.up("BracketRight"); settle(page, 500)
    page.click("#cs-record"); page.fill("#cs-name", "slide and zoom"); page.click("#cs-save"); page.wait_for_timeout(600)
    assert "Saved" in page.inner_text("#cs-status")
    auth = {"Authorization": "Bearer " + page.token}
    listed = httpx.get(base + "/api/camera-moves", headers=auth, timeout=10).json()["moves"]; assert [m["name"] for m in listed] == ["slide and zoom"]
    rec = httpx.get(base + "/api/camera-moves/slide and zoom", headers=auth, timeout=10).json()
    end = rec["samples"][-1]
    # play it back: the camera returns to where the move began, then ends where it ended
    page.reload(); page.wait_for_function("!!window.PubCastCameraStation", timeout=30000); page.click('.nav-btn[data-room="control"]')
    page.click('[data-station="camera"]'); page.select_option("#cs-camera", cam); page.wait_for_function("PubCastCameraStation.rig() !== null", timeout=10000)
    page.wait_for_function("document.querySelectorAll('#cs-moves option').length > 0", timeout=10000)
    page.click("#cs-play"); page.wait_for_function("PubCastCameraStation.state().playing", timeout=10000)          # it starts once the saved move has been fetched
    page.wait_for_function("!PubCastCameraStation.state().playing", timeout=20000); settle(page, 800)
    final = pose(base, cam); D = 3.141592653589793 / 180
    assert abs(final["position"][0] - end[0]) < 0.02 and abs(final["position"][2] - end[2]) < 0.02, (final["position"], end[:3], rec["start"], len(rec["samples"]), moved["position"])
    assert abs(final["fov"] - end[6] / D) < 0.05
    # assign a camera key: ask, answer, hold it
    page.click('#station-camera button[data-key-action="pan_left"]')
    assert page.locator(".pck-prompt").inner_text() == "Where would you like the Pan left button?"
    page.keyboard.press("KeyJ"); settle(page, 200)
    p0 = pose(base, cam)["rotation"][1]; page.keyboard.down("KeyJ"); settle(page, 700); page.keyboard.up("KeyJ"); settle(page, 700)
    assert pose(base, cam)["rotation"][1] != p0
    # back to the Director tab: the camera's keys stop acting, the switcher's work again
    page.click('[data-station="director"]'); assert page.evaluate("PubCastControlKeys.km.activeStation()") == "switcher"
    p1 = pose(base, cam); page.keyboard.down("KeyW"); settle(page, 500); page.keyboard.up("KeyW"); settle(page, 500); assert pose(base, cam) == p1
    assert httpx.delete(base + "/api/camera-moves/slide and zoom", headers=auth, timeout=10).status_code == 200
    assert known_only(page.problems) == []

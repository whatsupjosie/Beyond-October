"""Key assignments on the host (modules/keymap_store.py) and the transparent keyboard in a real browser (static/keymap.js)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.keymap_store import create_keymap_router, validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def api(tmp_path):
    app = FastAPI(); app.include_router(create_keymap_router(tmp_path))
    with TestClient(app) as c:
        c.data_dir = tmp_path
        yield c


def h(user): return {"Authorization": "Bearer " + create_access_token({"sub": user, "role": "owner"})}


def test_assignments_round_trip_per_person_and_keep_cleared_keys(api):
    km = {"switcher": {"cut": "KeyQ", "fade_in": None, "fade_out": "KeyF"}, "audio": {"mute": "Space"}}
    assert api.get("/api/keymap", headers=h("josie")).json() == {"ok": True, "revision": 0, "keymap": None}
    assert api.put("/api/keymap", headers=h("josie"), json={"keymap": km}).json()["revision"] == 1
    assert api.get("/api/keymap", headers=h("josie")).json()["keymap"] == km
    assert api.get("/api/keymap", headers=h("kay")).json()["keymap"] is None
    assert api.put("/api/keymap", headers=h("josie"), json={"keymap": km, "expected_revision": 0}).status_code == 409


@pytest.mark.parametrize("bad", [
    {"switcher": {"cut": "Escape"}}, {"switcher": {"cut": "F5"}}, {"switcher": {"cut": "Tab"}}, {"switcher": {"cut": "ShiftLeft"}},
    {"switcher": {"cut": "KeyQ", "fade": "KeyQ"}}, {"switcher": {"cut": "Key Q"}}, {"switcher": {"cut": 5}}, {"Bad": {}}, {"switcher": {"Cut": "KeyQ"}},
    {"switcher": []}, [], "x", {"s": {"a": "../x"}}, {f"s{i}": {} for i in range(40)},
])
def test_a_hand_made_request_cannot_store_what_the_browser_would_refuse(api, bad):
    r = api.put("/api/keymap", headers=h("josie"), json={"keymap": bad})
    assert r.status_code == 400, (bad, r.text)
    assert not (api.data_dir / "keymaps" / "josie.json").exists()


def test_oversize_and_not_json_are_refused(api):
    assert api.put("/api/keymap", headers=h("josie"), content=b"x" * 70000).status_code == 413
    assert api.put("/api/keymap", headers={**h("josie"), "Content-Type": "application/json"}, content=b"nope").status_code == 400
    with pytest.raises(ValueError):
        validate(None)


sync_api = pytest.importorskip("playwright.sync_api")


def test_the_transparent_keyboard_asks_lights_and_answers(tmp_path):
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--no-sandbox"])
        except Exception as exc:
            pytest.skip(f"no Chromium available: {exc}")
        try:
            page = browser.new_page(viewport={"width": 1100, "height": 700}); errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.set_content("<body style='background:#345'><div id='host' style='position:relative;height:600px'></div></body>")
            page.add_script_tag(path=str(ROOT / "static" / "keymap.js"))
            page.evaluate("""() => {
              window.km = PubCastKeymap.create({ switcher: {
                cut: {label: 'Cut', key: 'Space'}, fade_out: {label: 'Fade out', key: 'KeyF'},
                program: {label: 'Program level', kind: 'fader', key: 'KeyP', min: 0, max: 10, step: 2, value: 4} } });
              window.log = []; km.onButton((s, a) => log.push(a)); km.attach(document);
              window.ov = PubCastKeymap.overlay(document.getElementById('host'), km);
            }""")
            hidden = lambda: page.evaluate("getComputedStyle(document.querySelector('.pck-overlay')).display") == "none"
            assert hidden()                                                  # nothing shows until a station is open
            page.evaluate("km.open('switcher')")
            assert not hidden()
            assert page.locator("[data-code=Space] .pck-name").inner_text() == "Cut"
            assert page.locator("[data-on='1']").count() == 3
            # a real key press is a real cut; the page's own handling is stopped
            page.keyboard.press("Space"); assert page.evaluate("log") == ["cut"]
            # ask: the question names the button, a pressed key answers it
            page.evaluate("km.ask('switcher', 'fade_out')")
            assert page.locator(".pck-prompt").inner_text() == "Where would you like the Fade out button?"
            page.keyboard.press("KeyQ")
            assert page.locator("[data-code=KeyQ] .pck-name").inner_text() == "Fade out" and page.locator("[data-code=KeyF] .pck-name").inner_text() == ""
            # ask again and answer by clicking the overlay key; a taken key asks for confirmation first
            page.evaluate("km.ask('switcher', 'cut')")
            page.locator("[data-code=KeyQ]").click()
            assert "already does something" in page.locator(".pck-prompt").inner_text()
            page.locator("[data-code=KeyQ]").click()
            assert page.evaluate("km.bindings('switcher').cut") == "KeyQ" and page.evaluate("km.bindings('switcher').fade_out") is None
            # a fader: select, step, let go
            page.keyboard.press("KeyP"); assert page.locator("[data-code=KeyP]").get_attribute("data-sel") == "1"
            page.keyboard.press("ArrowUp"); page.keyboard.press("ArrowUp")
            assert page.evaluate("km.value('switcher', 'program')") == 8 and "8" in page.locator(".pck-prompt").inner_text()
            page.keyboard.press("Escape"); assert page.locator("[data-code=KeyP]").get_attribute("data-sel") == "0"
            page.evaluate("km.close()"); assert hidden()
            assert errors == []
        finally:
            browser.close()


# ── the walker does not walk while a station is open ────────────────────────────

import functools
import http.server
import threading


@pytest.fixture(scope="module")
def static_server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_sitting_at_a_station_stops_the_walker_and_standing_up_lets_it_walk_again(static_server):
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--no-sandbox"])
        except Exception as exc:
            pytest.skip(f"no Chromium available: {exc}")
        try:
            page = browser.new_page(viewport={"width": 1500, "height": 900}); errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{static_server}/static/world_walk.html?view=writers_room/main")
            page.wait_for_function("document.documentElement.dataset.ready==='1' && !!window.PubCastKeymap", timeout=20000)
            page.evaluate("window.km = PubCastKeymap.create({switcher: {cut: {label: 'Cut', key: 'Space'}}}); km.attach(document); window.hits = []; km.onButton((s, a) => hits.push(a))")
            pos = lambda: page.evaluate("window.PubCastWalk.S.pos.slice()")
            page.evaluate("document.activeElement && document.activeElement.blur()")
            # walking by key works before sitting down
            start = pos(); page.keyboard.down("ArrowDown"); page.wait_for_timeout(700); page.keyboard.up("ArrowDown")
            assert pos() != start
            # sit down at the switcher: a held key stops, keys and clicks no longer walk, the station's keys work
            page.keyboard.down("ArrowLeft"); page.wait_for_timeout(200)
            page.evaluate("km.open('switcher')")
            stopped = pos(); page.wait_for_timeout(500); page.keyboard.up("ArrowLeft")
            assert pos() == stopped
            page.keyboard.down("ArrowRight"); page.wait_for_timeout(500); page.keyboard.up("ArrowRight")
            assert pos() == stopped
            sx, sy = page.evaluate("(p) => window.PubCastWalk.toScreen([p[0] + 150, p[1]])", stopped)
            box = page.locator("#c").bounding_box()
            page.mouse.click(box["x"] + sx, box["y"] + sy); page.wait_for_timeout(600)
            assert pos() == stopped and page.evaluate("window.PubCastWalk.S.target") is None
            page.keyboard.press("Space"); assert page.evaluate("hits") == ["cut"]
            # stand up: walking works again
            page.evaluate("km.close()")
            page.keyboard.down("ArrowRight"); page.wait_for_timeout(700); page.keyboard.up("ArrowRight")
            assert pos() != stopped
            assert errors == []
        finally:
            browser.close()

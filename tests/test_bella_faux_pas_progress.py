"""Bella Faux Pas Studio progress, kept on the Reach host (modules/studio_progress.py).

The store and its routes are checked directly. Then the real program is run in a browser:
1. Walk somewhere, change who you walk as, put a library avatar on, and tune the size.
2. Stop PubCast, start it again on the same data folder, and open the studio.
3. Everything you had must come back.
Browser parts skip when Playwright/Chromium is unavailable.
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
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.avatar_imports import INCH_M, measure_glb
from modules.studio_progress import create_studio_progress_router, validate

ROOT = Path(__file__).resolve().parents[1]
MANNEQUIN = ROOT / "static" / "world" / "test_avatars" / "Xbot.glb"


# ── the store and its routes ────────────────────────────────────────────────

@pytest.fixture()
def api(tmp_path):
    app = FastAPI()
    app.include_router(create_studio_progress_router(tmp_path))
    with TestClient(app) as client:
        client.data_dir = tmp_path
        yield client


def _auth(user):
    return {"Authorization": "Bearer " + create_access_token({"sub": user, "role": "owner"})}


def test_progress_round_trips_per_owner_with_a_revision_each_save(api):
    a, b = _auth("josie"), _auth("someone-else")
    assert api.get("/api/studio/progress", headers=a).json() == {"ok": True, "revision": 0, "progress": None}
    p1 = {"room": "green_room", "view": "main", "pos": [812.5, 590.25], "char": "repeat", "avatars": {"repeat": "test-mannequin"},
          "hologram": True, "tune": {"green_room/main": {"mult": 1.2}}, "cans": {}}
    r = api.put("/api/studio/progress", headers=a, json={"progress": p1})
    assert r.status_code == 200 and r.json()["revision"] == 1
    got = api.get("/api/studio/progress", headers=a).json()
    assert got["revision"] == 1 and got["progress"] == p1
    assert api.put("/api/studio/progress", headers=a, json={"progress": dict(p1, room="writers_room")}).json()["revision"] == 2
    # another person's progress is their own
    assert api.get("/api/studio/progress", headers=b).json()["progress"] is None
    # kept as one file per owner, replaced whole
    files = sorted(x.name for x in (api.data_dir / "studio_progress").iterdir())
    assert files == ["josie.json"]


@pytest.mark.parametrize("bad, word", [
    ({"room": "../etc"}, "room"), ({"pos": [1, float("nan")]}, None), ({"pos": [1]}, "pos"),
    ({"char": "godzilla"}, "char"), ({"avatars": {"pete": "../x"}}, "avatars"), ({"hologram": "yes"}, "hologram"),
    ({"tune": [1, 2]}, "tune"),
])
def test_bad_progress_is_refused_and_nothing_is_written(api, bad, word):
    if bad.get("pos") and len(bad["pos"]) == 2:                    # NaN cannot be sent as JSON: check the validator itself
        with pytest.raises(ValueError):
            validate(bad)
        return
    r = api.put("/api/studio/progress", headers=_auth("josie"), json={"progress": bad})
    assert r.status_code == 400 and word in r.json()["detail"]
    assert not (api.data_dir / "studio_progress" / "josie.json").exists()


def test_oversized_progress_is_refused(api):
    huge = {"tune": {f"room{i}/main": {"note": "x" * 2000} for i in range(200)}}
    assert api.put("/api/studio/progress", headers=_auth("josie"), json={"progress": huge}).status_code in (400, 413)


def test_a_stale_writer_is_told_instead_of_overwriting(api):
    a = _auth("josie")
    api.put("/api/studio/progress", headers=a, json={"progress": {"room": "green_room"}})
    r = api.put("/api/studio/progress", headers=a, json={"progress": {"room": "lobby"}, "expected_revision": 0})
    assert r.status_code == 409
    assert api.get("/api/studio/progress", headers=a).json()["progress"] == {"room": "green_room"}


# ── the real program, across a restart ───────────────────────────────────────

sync_api = pytest.importorskip("playwright.sync_api")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Host:
    """PubCast started the way Josie starts it (run_reach.py) on a fixed data folder, so it can be quit and started again.
    run_reach.py keeps the sign-in key in the data folder, so a session survives the restart as it does for her."""
    def __init__(self, data):
        self.data, self.port, self.proc = data, _free_port(), None
        self.base = f"http://127.0.0.1:{self.port}"

    def start(self):
        env = dict(os.environ)
        for k in ("PUBCAST_ENFORCE_AUTH", "PUBCAST_JWT_SECRET", "PUBCAST_DATA_DIR"):
            env.pop(k, None)
        self.log = open(self.data / "host.log", "a", encoding="utf-8")
        self.proc = subprocess.Popen([sys.executable, "run_reach.py", "--port", str(self.port), "--data-dir", str(self.data),
                                      "--no-browser", "--no-legacy-2i"], cwd=str(ROOT), env=env, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + 90
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise AssertionError("PubCast exited during startup")
            try:
                if httpx.get(self.base + "/health", timeout=0.5).status_code == 200:
                    return
            except httpx.RequestError:
                pass
            time.sleep(0.2)
        raise AssertionError("PubCast did not start")

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(20)
        except subprocess.TimeoutExpired:
            self.proc.kill(); self.proc.wait(5)
        self.log.close()


def test_studio_progress_and_avatar_come_back_after_pubcast_restarts(tmp_path):
    host = Host(tmp_path)
    host.start()
    try:
        password = secrets.token_urlsafe(20)
        owner = httpx.post(host.base + "/api/auth/setup", json={"username": "josie-check", "password": password, "confirm_password": password}, timeout=10).json()
        token = owner["access_token"]
        # an avatar in the library, at its own measured height (the library refuses one that does not match)
        data = MANNEQUIN.read_bytes()
        height_in = round(measure_glb(data)["height_m"] / INCH_M, 2)
        r = httpx.post(host.base + "/api/avatars/imports", params={"name": "Test mannequin", "height_in": height_in, "character_id": "repeat"},
                       content=data, headers={"Content-Type": "model/gltf-binary", "Authorization": "Bearer " + token}, timeout=30)
        assert r.status_code == 201, r.text
        avatar_id = r.json()["avatar"]["id"]

        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch(args=["--no-sandbox"])
            except Exception as exc:
                pytest.skip(f"no Chromium available: {exc}")
            try:
                def session_page():
                    ctx = browser.new_context(viewport={"width": 1400, "height": 860})
                    ctx.add_init_script("sessionStorage.setItem('pubcast_token', %s); sessionStorage.setItem('pubcast_user', JSON.stringify({username:'josie-check',user_id:'josie-check',role:'owner'}));"
                                        % json.dumps(token))
                    pg = ctx.new_page(); pg.problems = []
                    pg.on("pageerror", lambda e: pg.problems.append(str(e)))
                    pg.goto(host.base + "/walk")
                    pg.wait_for_function("document.documentElement.dataset.ready === '1' && window.PubCastLive && window.PubCastLive.state.host === true", timeout=30000)
                    return ctx, pg

                ctx, page = session_page()
                assert page.evaluate("window.PubCastWalk.S.room.id") == "dressing_room"           # first time: the dressing room
                # go to the green room and walk to a spot
                page.evaluate("window.PubCastWalk.goTo('green_room', 'dressing_room')")
                page.wait_for_function("window.PubCastWalk.S.room.id === 'green_room'")
                spot = page.evaluate("() => { const W = window.PubCastWalk, S = W.S; const q = W.snapToFloor(S.view, [S.view.w * 0.62, S.view.h * 0.8]); return q; }")
                sx, sy = page.evaluate("(p) => window.PubCastWalk.toScreen(p)", spot)
                box = page.locator("#c").bounding_box()
                page.mouse.click(box["x"] + sx, box["y"] + sy)
                page.wait_for_function("!window.PubCastWalk.S.target", timeout=40000)
                where = page.evaluate("window.PubCastWalk.S.pos.slice()")
                # walk as RePete, wearing the library avatar, a little bigger in this picture, hologram on
                page.check("input[name=char][value=repeat]")
                page.wait_for_function("!document.getElementById('glbLibraryRow').hidden", timeout=15000)
                page.select_option("#glbLibrary", avatar_id)
                page.wait_for_function("window.PubCastGLB && window.PubCastGLB.has('repeat')", timeout=30000)
                page.evaluate("() => { const r = document.querySelector('#tuner input[type=range]'); r.value = 1.25; r.dispatchEvent(new Event('input')); }")
                page.check("#glbHolo")
                # it saves on its own once you stand still
                page.wait_for_function("""() => window.PubCastLive.state.progressRevision >= 1 &&
                    window.PubCastLive.state.progressSavedAt && document.getElementById('progressInfo').textContent.includes('saved')""", timeout=15000)
                page.wait_for_timeout(2500)                                                     # let the last change go out
                assert page.problems == []
                ctx.close()
            finally:
                browser.close()

        # the progress is on the host, not only in that browser
        saved = httpx.get(host.base + "/api/studio/progress", headers={"Authorization": "Bearer " + token}).json()["progress"]
        assert saved["room"] == "green_room" and saved["char"] == "repeat" and saved["avatars"] == {"repeat": avatar_id}
        assert saved["hologram"] is True and saved["tune"]["green_room/main"]["mult"] == pytest.approx(1.25)
        assert saved["pos"] == pytest.approx(where, abs=0.02)

        # quit PubCast and start it again on the same data
        host.stop()
        host.start()
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            try:
                ctx = browser.new_context(viewport={"width": 1400, "height": 860})       # a fresh browser: nothing kept locally
                ctx.add_init_script("sessionStorage.setItem('pubcast_token', %s); sessionStorage.setItem('pubcast_user', JSON.stringify({username:'josie-check',user_id:'josie-check',role:'owner'}));"
                                    % json.dumps(token))
                page = ctx.new_page(); errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(host.base + "/walk")
                page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=30000)
                assert page.evaluate("window.PubCastWalk.S.room.id") == "green_room"
                assert page.evaluate("window.PubCastWalk.S.pos") == pytest.approx(where, abs=0.02)
                assert page.evaluate("window.PubCastWalk.S.char") == "repeat"
                assert page.is_checked("input[name=char][value=repeat]")
                assert page.evaluate("window.PubCastWalk.S.tune['green_room/main'].mult") == pytest.approx(1.25)
                page.wait_for_function("window.PubCastGLB && window.PubCastGLB.has('repeat')", timeout=30000)
                assert page.evaluate("window.PubCastGLB.state.hologram") is True
                assert page.input_value("#glbLibrary") == avatar_id
                # a link that names a room still goes there, with your other choices kept
                page.goto(host.base + "/walk?live=dressing")
                page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=30000)
                assert page.evaluate("window.PubCastWalk.S.room.id") == "dressing_room"
                assert page.evaluate("window.PubCastWalk.S.char") == "repeat"
                assert errors == []
            finally:
                browser.close()
    finally:
        host.stop()

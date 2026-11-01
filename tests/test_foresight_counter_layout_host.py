"""The Foresight Counter layout is kept on the Reach host as well as in the browser (modules/counter_layout.py).

The API is checked directly. Then the real program:
1. Start run_reach.py, sign in, and open 2i in a tray on the Counter.
2. Quit PubCast and start it again.
3. Sign in from a fresh browser that has no saved data of its own, and check the tray comes back.
A newer layout saved from another browser beats an older local copy. Browser parts skip without Playwright/Chromium.
"""
from __future__ import annotations

import os
import re
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
from modules.counter_layout import create_counter_layout_router

ROOT = Path(__file__).resolve().parents[1]


def _auth(user):
    return {"Authorization": "Bearer " + create_access_token({"sub": user, "role": "owner"})}


@pytest.fixture()
def api(tmp_path):
    app = FastAPI()
    app.include_router(create_counter_layout_router(tmp_path))
    with TestClient(app) as c:
        c.data_dir = tmp_path
        yield c


def test_layout_round_trips_per_owner(api):
    a = _auth("josie")
    assert api.get("/api/foresight/counter-layout", headers=a).json()["layout"] is None
    layout = {"v": 3, "theme": "walnut", "inactivePolicy": "dim", "selected": "tray1",
              "trays": [{"id": "tray1", "x": 400, "y": 300, "contents": [{"type": "program", "data": {"id": "writers_room"}, "state": None}]}]}
    r = api.put("/api/foresight/counter-layout", headers=a, json={"layout": layout, "client_saved_at": 1761600000000})
    assert r.status_code == 200 and r.json()["revision"] == 1
    got = api.get("/api/foresight/counter-layout", headers=a).json()
    assert got["layout"] == layout and got["client_saved_at"] == 1761600000000 and got["revision"] == 1
    assert api.get("/api/foresight/counter-layout", headers=_auth("someone-else")).json()["layout"] is None
    assert [p.name for p in (api.data_dir / "counter_layout").iterdir()] == ["josie.json"]


@pytest.mark.parametrize("bad", [None, [], {"v": 2, "trays": []}, {"v": 3}, {"v": 3, "trays": [1]}, {"v": 3, "trays": [{"contents": "x"}]}])
def test_bad_layouts_are_refused(api, bad):
    r = api.put("/api/foresight/counter-layout", headers=_auth("josie"), json={"layout": bad})
    assert r.status_code == 400
    assert not (api.data_dir / "counter_layout" / "josie.json").exists()


def test_stale_writer_and_oversize_are_refused(api):
    a = _auth("josie")
    api.put("/api/foresight/counter-layout", headers=a, json={"layout": {"v": 3, "trays": []}})
    assert api.put("/api/foresight/counter-layout", headers=a, json={"layout": {"v": 3, "trays": []}, "expected_revision": 0}).status_code == 409
    big = {"v": 3, "trays": [{"contents": [{"type": "note", "state": "x" * (2 * 1024 * 1024)}]}]}
    assert api.put("/api/foresight/counter-layout", headers=a, json={"layout": big}).status_code == 413


# ── the real Counter, across a restart ───────────────────────────────────────

sync_api = pytest.importorskip("playwright.sync_api")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Reach:
    def __init__(self, data):
        self.data, self.port = data, _free_port()
        self.base = f"http://127.0.0.1:{self.port}"

    def start(self):
        env = {k: v for k, v in os.environ.items() if k not in ("PUBCAST_ENFORCE_AUTH", "PUBCAST_JWT_SECRET", "PUBCAST_DATA_DIR")}
        self.log = open(self.data / "reach.log", "a", encoding="utf-8")
        self.proc = subprocess.Popen([sys.executable, "run_reach.py", "--port", str(self.port), "--data-dir", str(self.data),
                                      "--no-browser", "--no-legacy-2i"], cwd=str(ROOT), env=env, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + 120
        while time.time() < deadline:
            assert self.proc.poll() is None, "run_reach.py exited during startup"
            try:
                if httpx.get(self.base + "/health", timeout=0.5).status_code == 200:
                    return
            except httpx.RequestError:
                pass
            time.sleep(0.25)
        raise AssertionError("PubCast did not start")

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(20)
        except subprocess.TimeoutExpired:
            self.proc.kill(); self.proc.wait(5)
        self.log.close()


def _signed_in_counter(browser, base, user, password):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})        # its own empty localStorage
    page = ctx.new_page(); page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.goto(base + "/login?next=%2Fforesight-counter")
    page.fill("#loginUser", user); page.fill("#loginPass", password); page.keyboard.press("Enter")
    page.wait_for_url("**/foresight-counter**", timeout=20000)
    page.wait_for_function("!!window.__programs && !!window.__counter && !!window.__hostLayout", timeout=30000)
    page.wait_for_timeout(800)
    return ctx, page


def _titles(page):
    return page.evaluate("window.__counter.trays.filter(t => !t.closed).map(t => t.stack.map(c => c.title))")


def test_counter_layout_comes_back_after_a_restart_in_a_fresh_browser(tmp_path):
    reach = Reach(tmp_path)
    reach.start()
    try:
        user, password = "josie-check", secrets.token_urlsafe(20)
        r = httpx.post(reach.base + "/api/auth/setup", json={"username": user, "password": password, "confirm_password": password}, timeout=10)
        assert r.status_code in (200, 201), r.text
        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch(args=["--no-sandbox", "--disable-3d-apis"])
            except Exception as exc:
                pytest.skip(f"no Chromium available: {exc}")
            try:
                ctx, page = _signed_in_counter(browser, reach.base, user, password)
                assert _titles(page) == []
                page.evaluate("window.__counter.openPicker(null)"); page.wait_for_timeout(400)
                assert page.evaluate("(t) => window.__counter.debug.clickVeil(t)", "2i Writer's Room")
                page.wait_for_function("window.__counter.trays.length === 1", timeout=20000)
                page.wait_for_function("window.__counter.trays.length === 1 && !window.__counter.trays[0].closed", timeout=20000)
                # the open tray reaches the host on its own, shortly after it finishes opening
                token = page.evaluate("sessionStorage.getItem('pubcast_token')")
                deadline = time.time() + 15
                while True:
                    host = httpx.get(reach.base + "/api/foresight/counter-layout", headers={"Authorization": "Bearer " + token}).json()["layout"]
                    if host and len(host["trays"]) == 1 and not host["trays"][0]["closed"]:
                        break
                    assert time.time() < deadline, host
                    time.sleep(0.2)
                before = _titles(page)
                assert before and "Writer" in before[0][0]
                assert page.errors == []
                ctx.close()
            finally:
                browser.close()

        reach.stop()
        reach.start()
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox", "--disable-3d-apis"])
            try:
                ctx, page = _signed_in_counter(browser, reach.base, user, password)
                page.wait_for_function("window.__counter.trays.length === 1", timeout=20000)
                assert _titles(page) == before
                assert page.errors == []
                kept = ctx.storage_state()                       # this browser, with its own (now older) copy
                ctx.close()
                # meanwhile another browser (the same owner elsewhere) saves an empty Counter
                other, op = _signed_in_counter(browser, reach.base, user, password)
                token = op.evaluate("sessionStorage.getItem('pubcast_token')")
                other.close()
                hdr = {"Authorization": "Bearer " + token}
                host_layout = httpx.get(reach.base + "/api/foresight/counter-layout", headers=hdr).json()["layout"]
                r = httpx.put(reach.base + "/api/foresight/counter-layout", headers=hdr,
                              json={"layout": dict(host_layout, trays=[]), "client_saved_at": time.time() * 1000 + 60000})
                assert r.status_code == 200, r.text
                # back in the first browser: the newer copy from the host wins over its own
                ctx = browser.new_context(viewport={"width": 1440, "height": 900}, storage_state=kept)
                page = ctx.new_page(); page.errors = []
                page.on("pageerror", lambda e: page.errors.append(str(e)))
                page.goto(reach.base + "/login?next=%2Fforesight-counter")
                page.fill("#loginUser", user); page.fill("#loginPass", password); page.keyboard.press("Enter")
                page.wait_for_url("**/foresight-counter**", timeout=20000)
                page.wait_for_function("!!window.__counter && !!window.__hostLayout", timeout=30000)
                page.wait_for_timeout(800)
                assert page.evaluate("Object.keys(localStorage).some(k => k.startsWith('foresight.counter.v3:') && !k.endsWith(':saved_at'))")
                assert _titles(page) == []
                assert page.errors == []
            finally:
                browser.close()
    finally:
        reach.stop()

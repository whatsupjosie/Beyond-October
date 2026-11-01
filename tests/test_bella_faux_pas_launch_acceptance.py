"""Josie's acceptance check, run the way she starts PubCast: ``run_reach.py`` with a throwaway data folder.

It must start; signing in through the real login page lands on the empty Counter; the fan has the New blade and the
Bella Faux Pas blade; 2i and PubPartner open in trays from the Counter's Open picker; the Bella Faux Pas blade opens the
studio (the walkable world) in a tray, in the dressing room, connected live to the host.

The browser runs with 3D graphics switched off, so this also proves the Counter's Canvas 2D fallback starts the real
page with its animation loop running (the HDR renderer is used wherever WebGL2 exists). Skips without Playwright/Chromium.
"""
from __future__ import annotations

import re
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sync_api = pytest.importorskip("playwright.sync_api")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def reach(tmp_path_factory):
    data = tmp_path_factory.mktemp("reach_userdata")
    port = _free_port()
    log = open(data / "reach.log", "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "run_reach.py", "--port", str(port), "--data-dir", str(data),
                             "--no-browser", "--no-legacy-2i"], cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 120
        while time.time() < deadline:
            if proc.poll() is not None:
                log.flush()
                raise AssertionError("run_reach.py exited during startup:\n" + (data / "reach.log").read_text(encoding="utf-8")[-4000:])
            try:
                if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                    break
            except httpx.RequestError:
                pass
            time.sleep(0.3)
        else:
            raise AssertionError("PubCast did not start within 120 s")
        password = secrets.token_urlsafe(20)
        r = httpx.post(base + "/api/auth/setup", json={"username": "josie-check", "password": password, "confirm_password": password}, timeout=10)
        assert r.status_code in (200, 201), r.text
        yield base, "josie-check", password
    finally:
        proc.terminate()
        try:
            proc.wait(20)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(5)
        log.close()


def _frame(page, pattern):
    for _ in range(200):
        fr = next((f for f in page.frames if re.search(pattern, f.url)), None)
        if fr:
            return fr
        page.wait_for_timeout(100)
    raise AssertionError("no tray page matching " + pattern)


def test_start_sign_in_and_open_2i_pubpartner_and_the_studio(reach):
    base, user, password = reach
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--no-sandbox", "--disable-3d-apis"])
        except Exception as exc:
            pytest.skip(f"no Chromium available: {exc}")
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base + "/login?next=%2Fforesight-counter")
            page.fill("#loginUser", user)
            page.fill("#loginPass", password)
            page.keyboard.press("Enter")
            page.wait_for_url("**/foresight-counter**", timeout=20000)
            page.wait_for_function("!!window.__programs && !!window.__counter", timeout=30000)

            # the empty Counter, with Bella Faux Pas on the fan
            assert page.evaluate("window.__counter.trays.length") == 0
            assert page.evaluate("window.__counter.debug.blades().map(b => b.title)") == ["New", "Bella Faux Pas"]

            # 2i and PubPartner from File > Open...
            for title, pattern in (("2i Writer's Room", r"/writers-room\?"), ("PubPartner · Alex & Cartridges", r"/pubpartner$")):
                page.evaluate("window.__counter.openPicker(null)")
                page.wait_for_timeout(400)
                assert page.evaluate("(t) => window.__counter.debug.clickVeil(t)", title), title
                _frame(page, pattern).wait_for_load_state("load", timeout=30000)
            assert "Writer" in _frame(page, r"/writers-room\?").title()
            assert "PubPartner" in _frame(page, r"/pubpartner$").title()

            # the studio from its own blade, clicked where it is drawn
            blade = page.evaluate("window.__counter.debug.blades().find(b => b.title === 'Bella Faux Pas')")
            x, y = blade["tip"]
            px, py = 62 + (x - 62) * 0.66, 112 + (y - 112) * 0.66          # two thirds out from the fan's pivot
            assert page.evaluate("([x, y]) => window.__counter.debug.bladeAt(x, y)", [px, py]) == blade["i"]
            page.mouse.click(px, py)
            studio = _frame(page, r"/walk$")
            studio.wait_for_function("document.documentElement.dataset.ready === '1' && !!window.PubCastLive && window.PubCastLive.state.online === true", timeout=30000)
            assert studio.title() == "Bella Faux Pas Studio"
            assert studio.evaluate("window.PubCastWalk.S.room.id") == "dressing_room"
            assert studio.evaluate("window.PubCastLive.state.room") == "dressing"
            assert page.evaluate("window.__counter.trays.length") == 3

            # the blade again brings the open studio forward instead of opening a second one
            page.mouse.click(px, py)
            page.wait_for_timeout(600)
            assert page.evaluate("window.__counter.trays.length") == 3
            assert errors == []
        finally:
            browser.close()

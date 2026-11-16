"""2i layout inside the real host: nothing clipped, nothing overlapping, usable at phone width.

Starts ``run_reach.py`` with a throwaway data folder, creates the owner, signs in through the real login page and
opens /writers-room in Chromium. Checks, at laptop width: every menu is inside the menu bar (before, the bar needed
1,803 px of the 1,262 available and "View" onward was cut off); the scene line in Manuscript Control is styled and
does not sit on the Reference Archive; "My manuscripts" fits its button; Save is in the top bar. At phone width:
the page fills the screen (before, 10 px wide), both drawers open and close, and File is the document icon.
Skips without Playwright/Chromium.
"""
from __future__ import annotations

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

BOX = """(id) => { const e = document.getElementById(id), r = e.getBoundingClientRect();
  return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
          visible: getComputedStyle(e).visibility !== 'hidden' && getComputedStyle(e).display !== 'none'}; }"""


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
        r = httpx.post(base + "/api/auth/setup", json={"username": "layout-check", "password": password, "confirm_password": password}, timeout=10)
        assert r.status_code in (200, 201), r.text
        yield base, "layout-check", password
    finally:
        proc.terminate()
        try:
            proc.wait(20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(5)
        log.close()


def _open(p, reach, width, height, touch=False):
    base, user, password = reach
    try:
        browser = p.chromium.launch(args=["--no-sandbox"])
    except Exception as exc:
        pytest.skip(f"no Chromium available: {exc}")
    context = browser.new_context(viewport={"width": width, "height": height}, has_touch=touch, is_mobile=touch)
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base + "/login?next=%2Fwriters-room")
    page.fill("#loginUser", user)
    page.fill("#loginPass", password)
    page.keyboard.press("Enter")
    page.wait_for_url("**/writers-room**", timeout=20000)
    page.wait_for_function("!!document.getElementById('twoiMenuBar') && !!document.getElementById('narrativeBudget') && typeof initializing !== 'undefined' && !initializing", timeout=30000)
    page.wait_for_timeout(400)
    return browser, page, errors


def test_laptop_width_shows_every_menu_and_nothing_overlaps(reach):
    with sync_api.sync_playwright() as p:
        browser, page, errors = _open(p, reach, 1280, 800)
        try:
            menus = page.evaluate("""() => { const bar = document.getElementById('twoiMenuBar').getBoundingClientRect();
                return Array.from(document.getElementById('twoiMenuBar').children).map(e => { const r = e.getBoundingClientRect();
                    return {name: e.getAttribute('aria-label') || e.textContent.trim(), inside: r.left >= bar.left - 1 && r.right <= bar.right + 1 && r.bottom <= bar.bottom + 1 && r.width > 0}; }); }""")
            assert [m["name"] for m in menus][1:13] == ["File", "Edit", "Insert", "Format", "Layout", "References", "Manuscript", "Review", "View", "Tools", "Studio", "Help"]
            assert all(m["inside"] for m in menus), [m["name"] for m in menus if not m["inside"]]
            assert page.evaluate("document.getElementById('twoiMenuBar').scrollWidth <= document.getElementById('twoiMenuBar').clientWidth")

            # the scene line is small label text from the first moment, before any dialog has been opened
            assert page.evaluate("getComputedStyle(document.getElementById('narrativeBudget')).fontSize") == "10px"
            budget, ref, control = (page.evaluate(BOX, i) for i in ("narrativeBudget", "refSection", "mcSection"))
            assert budget["y"] + budget["h"] <= ref["y"] and control["y"] + control["h"] <= ref["y"] + 1
            # the left panel scrolls to the Reference Archive instead of squeezing it
            page.evaluate("document.getElementById('addRefBtn').scrollIntoView({block: 'end'})")
            add, panel = page.evaluate(BOX, "addRefBtn"), page.evaluate(BOX, "sidebar")
            assert add["y"] >= panel["y"] and add["y"] + add["h"] <= panel["y"] + panel["h"] + 1

            assert page.evaluate("(() => { const b = document.getElementById('shelfBtn'); return b.scrollWidth <= b.clientWidth + 1 && b.scrollHeight <= b.clientHeight + 1; })()")
            shelf, toggle = page.evaluate(BOX, "shelfBtn"), page.evaluate(BOX, "sidebarToggle")
            assert shelf["x"] + shelf["w"] <= toggle["x"]

            save, main = page.evaluate(BOX, "saveBtn"), page.evaluate(BOX, "mainArea")
            assert save["visible"] and save["y"] + save["h"] <= main["y"]
            assert page.evaluate("document.querySelector('.top-bar').contains(document.getElementById('saveBtn')) && document.querySelector('.top-bar').contains(document.getElementById('saveIndicator'))")
            # Save still saves from its new place
            page.click("#soloTextarea")
            page.keyboard.type("Saved from the top bar.")
            page.click("#saveBtn")
            page.wait_for_function("document.getElementById('saveIndicator').textContent.includes('Saved to Reach')", timeout=15000)
            assert page.evaluate("getComputedStyle(document.getElementById('twoiDrawerTabTools')).display") == "none"
            assert errors == []
        finally:
            browser.close()


def test_phone_width_gives_the_page_the_screen_with_two_drawers(reach):
    with sync_api.sync_playwright() as p:
        browser, page, errors = _open(p, reach, 390, 844, touch=True)
        try:
            frame, writing = page.evaluate(BOX, "notebookFrame"), page.evaluate(BOX, "soloTextarea")
            assert frame["x"] == 0 and frame["w"] == 390
            assert writing["w"] >= 300 and writing["h"] >= 400
            assert page.evaluate("[document.documentElement.scrollWidth, document.documentElement.scrollHeight]") == [390, 844]
            assert page.evaluate("document.getElementById('chatSection').parentElement.id") == "mainArea"
            for panel in ("sidebar", "chatSection"):
                assert not page.evaluate(BOX, panel)["visible"]

            file_menu = page.evaluate("""() => { const s = document.querySelector('#twoiMenuBar select[aria-label="File"]'), r = s.getBoundingClientRect(), c = getComputedStyle(s);
                return {w: Math.round(r.width), image: c.backgroundImage.startsWith('url('), title: s.title, firstCommand: s.options[1].textContent}; }""")
            assert file_menu == {"w": 40, "image": True, "title": "File", "firstCommand": "New"}

            page.tap("#soloTextarea")
            page.keyboard.type("Typed on the phone.")
            for tab, panel in (("twoiDrawerTabTools", "sidebar"), ("twoiDrawerTabPartner", "chatSection")):
                page.tap("#" + tab)
                page.wait_for_timeout(350)
                box = page.evaluate(BOX, panel)
                assert box["visible"] and box["x"] >= 0 and box["x"] + box["w"] <= 390, panel
                page.tap("#" + tab)
                page.wait_for_timeout(350)
                assert not page.evaluate(BOX, panel)["visible"], panel
            assert page.evaluate("soloTextarea.value") == "Typed on the phone."
            save, main = page.evaluate(BOX, "saveBtn"), page.evaluate(BOX, "mainArea")
            assert save["visible"] and save["h"] >= 40 and save["y"] + save["h"] <= main["y"]
            page.tap("#saveBtn")
            page.wait_for_function("document.getElementById('saveIndicator').textContent.includes('Saved to Reach')", timeout=15000)
            assert errors == []
        finally:
            browser.close()

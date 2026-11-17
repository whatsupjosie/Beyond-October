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


FACES = """() => Array.from(document.querySelectorAll('#twoiMenuBar select')).filter(s => s.getAttribute('aria-label') !== 'File').map(s => {
    const c = getComputedStyle(s), canvas = document.createElement('canvas').getContext('2d');
    canvas.font = `${c.fontStyle} ${c.fontWeight} ${c.fontSize} ${c.fontFamily}`;
    const face = s.options[s.selectedIndex].textContent;
    return {face, text: Math.ceil(canvas.measureText(face).width), box: Math.round(s.getBoundingClientRect().width)}; })"""


def _menu_names_fit_and_are_not_padded_out(page):
    """Each menu is sized from the length of its name. The name must fit beside the arrow, without a long empty box."""
    faces = page.evaluate(FACES)
    assert len(faces) == 12
    for f in faces:
        assert f["text"] + 22 <= f["box"] <= f["text"] + 60, f


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


def _open(p, reach, width, height, touch=False, path="/writers-room"):
    base, user, password = reach
    try:
        browser = p.chromium.launch(args=["--no-sandbox"])
    except Exception as exc:
        pytest.skip(f"no Chromium available: {exc}")
    context = browser.new_context(viewport={"width": width, "height": height}, has_touch=touch, is_mobile=touch)
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base + "/login?next=" + path.replace("/", "%2F"))
    page.fill("#loginUser", user)
    page.fill("#loginPass", password)
    page.keyboard.press("Enter")
    page.wait_for_url("**" + path + "**", timeout=20000)
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
            _menu_names_fit_and_are_not_padded_out(page)

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
            # the whole frame of the program is inside the window: its bottom edge used to be 16 px below it
            shell = page.evaluate("(() => { const r = document.querySelector('.app-shell').getBoundingClientRect(); return [Math.round(r.top), Math.round(r.bottom)]; })()")
            assert shell == [8, 792]
            frame = page.evaluate(BOX, "notebookFrame")
            assert frame["y"] + frame["h"] <= 792 and page.evaluate("document.querySelector('.status-bar')") is None
            # Save still saves from its new place
            page.click("#soloTextarea")
            page.keyboard.type("Saved from the top bar.")
            page.click("#saveBtn")
            page.wait_for_function("document.getElementById('saveIndicator').textContent.includes('Saved to Reach')", timeout=15000)
            # 2026-11-16: on the single page in Write the small side tabs are shown at laptop width too (Josie's
            # design); in the bound notebook, where the panels sit beside the page, they are not.
            assert page.evaluate("getComputedStyle(document.getElementById('twoiDrawerTabTools')).display") == "flex"
            page.evaluate("twoiSetPresentation('notebook')")
            assert page.evaluate("getComputedStyle(document.getElementById('twoiDrawerTabTools')).display") == "none"
            page.evaluate("twoiSetPresentation('standard')")
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
            _menu_names_fit_and_are_not_padded_out(page)

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


@pytest.mark.parametrize("path", ["/writers-room", "/2i", "/2i-v22"])
def test_every_host_address_for_2i_loads_its_companion_files(reach, path):
    """The page addresses its companion files relative to itself so that they also resolve from disk. All three
    host addresses that serve the page sit at the top level, so the same addresses must resolve on each of them."""
    with sync_api.sync_playwright() as p:
        browser, page, errors = _open(p, reach, 1280, 800, path=path)
        try:
            failed = page.evaluate("""() => performance.getEntriesByType('resource').filter(r => /2i-assets|static[/]/.test(r.name) && r.responseStatus >= 400).map(r => r.name)""")
            assert failed == []
            assert page.evaluate("[typeof TwoiFormatCore, typeof documentId, typeof PubcastSpeech, networked, document.querySelectorAll('#twoiMenuBar select').length]") == ["object", "string", "object", True, 13]
            assert page.evaluate("getComputedStyle(document.querySelector('.app-shell')).marginTop") == "8px"   # reach.css applied
            assert errors == []
        finally:
            browser.close()

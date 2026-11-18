"""2i (writers-room-v22.html) laid out on phones, tablets and desktops, in real Chromium.

The page is served the way the host serves it, with the real writers-room and
auth routes behind it (as in test_foresight_file_workspace.py). These checks
are about what a person sees and can reach: nothing runs off the side of the
screen, Save is always on screen, the editor is there, the per-pane text zoom
works with the Reach desk layer on top, the line numbers stay on their lines,
and the spiral coils are redrawn when the page changes size.
"""
from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from modules import userdb  # noqa: E402
from modules.auth import create_access_token  # noqa: E402
from modules.auth_routes import router as auth_router  # noqa: E402
from modules.writers_room import create_writers_room_router  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SIZES = [
    (320, 568), (360, 800), (390, 844), (430, 932), (600, 960), (768, 1024),
    (820, 1180), (1024, 768), (1180, 820), (1366, 768), (1920, 1080),
]


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    folder = tmp_path_factory.mktemp("2i-layout")
    original_db = userdb._DB_PATH
    userdb._DB_PATH = folder / "users.db"
    userdb._sync_init_db()
    assert userdb._sync_create_owner_via_setup("layout-writer", "layout-writer-password-1234")
    api = FastAPI()
    api.include_router(create_writers_room_router(folder))
    api.include_router(auth_router)
    client = TestClient(api)
    token = create_access_token({"sub": "layout-writer", "role": "owner"})
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # pragma: no cover - environment without a browser
            pytest.skip(f"Chromium unavailable for Playwright: {exc}")
        external = []

        def route(r):
            address = urlparse(r.request.url)
            if address.netloc != "localhost":
                external.append(r.request.url)
                r.abort()
                return
            path = address.path
            if path.startswith(("/api/writers-room/", "/api/auth/")):
                response = client.request(
                    r.request.method,
                    path + ("?" + address.query if address.query else ""),
                    content=r.request.post_data,
                    headers={k: v for k, v in r.request.headers.items() if k.lower() in {"authorization", "content-type"}},
                )
                r.fulfill(status=response.status_code, body=response.content,
                          content_type=response.headers.get("content-type", "application/json"))
                return
            if path == "/writers-room":
                file = ROOT / "2i" / "writers-room-v22.html"
            elif path.startswith("/static/"):
                file = ROOT / path.lstrip("/")
            elif path.startswith("/2i-assets/"):
                file = ROOT / "2i" / path.lstrip("/")
            else:
                r.fulfill(status=404, content_type="application/json", body=json.dumps({"detail": "Not found"}))
                return
            if file.is_file():
                r.fulfill(body=file.read_bytes(), content_type=mimetypes.guess_type(file.name)[0] or "application/octet-stream")
            else:
                r.fulfill(status=404, body="Not found")

        def open_page(width, height):
            mobile = width < 900
            context = browser.new_context(viewport={"width": width, "height": height}, is_mobile=mobile, has_touch=mobile)
            context.add_init_script("sessionStorage.setItem('pubcast_token', %s);" % json.dumps(token))
            context.route("**/*", route)
            page = context.new_page()
            page.goto("http://localhost/writers-room")
            page.wait_for_selector("#soloTextarea")
            page.wait_for_function("document.fonts.status === 'loaded'")
            return page

        yield open_page
        browser.close()
        assert not external, "2i reached outside the machine: " + repr(external)
    client.close()
    userdb._DB_PATH = original_db


LAYOUT = """() => {
    const box = id => document.getElementById(id).getBoundingClientRect();
    const onScreen = r => r.width > 0 && r.left >= -0.5 && r.right <= innerWidth + 0.5 && r.top >= -0.5 && r.bottom <= innerHeight + 0.5;
    const spill = [...document.querySelectorAll('.app-shell *')]
        .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.right > innerWidth + 0.5; })
        .map(e => e.id || e.className.toString());
    const shelf = document.getElementById('shelfBtn');
    return {
        spill,
        save: onScreen(box('saveBtn')),
        menu: onScreen(box('menuToggle')),
        settings: onScreen(box('sidebarToggle')),
        shelf: onScreen(box('shelfBtn')),
        shelfFits: shelf.scrollWidth <= shelf.clientWidth + 1 && shelf.scrollHeight <= shelf.clientHeight + 1,
        editorTop: box('soloTextarea').top,
        editorWidth: box('soloTextarea').width,
    };
}"""


@pytest.mark.parametrize("width,height", SIZES)
def test_nothing_runs_off_screen_and_save_and_the_menus_are_always_in_reach(served, width, height):
    page = served(width, height)
    layout = page.evaluate(LAYOUT)
    assert layout["spill"] == [], layout["spill"][:5]
    assert layout["save"] and layout["menu"] and layout["settings"] and layout["shelf"], layout
    assert layout["shelfFits"], "the My manuscripts label spills out of its button"
    assert layout["editorTop"] < height * 0.6, "the writing page must start on the first screen"
    # Stacked (under 900 px) the page takes most of the width; on the
    # three-panel desk it shares the width with the two side panels and must
    # still hold a comfortable line of writing.
    assert layout["editorWidth"] >= (width * 0.7 if width < 900 else 300), layout
    page.context.close()


@pytest.mark.parametrize("width,height", [(390, 844), (820, 1180)])
def test_save_stays_on_screen_after_scrolling_down_a_phone_or_tablet(served, width, height):
    page = served(width, height)
    page.evaluate("document.scrollingElement.scrollTo(0, 99999); document.body.scrollTo(0, 99999)")
    page.wait_for_timeout(100)
    assert page.evaluate(LAYOUT)["save"]
    page.context.close()


def test_the_reach_desk_layer_is_applied_after_the_page_styles(served):
    page = served(1366, 768)
    # The desk layer's top bar (76 px) and three-column desk only show if its
    # stylesheet comes after the page's own <style>.
    rows = page.evaluate("getComputedStyle(document.querySelector('.app-shell')).gridTemplateRows")
    assert rows.split()[0] == "76px", rows
    columns = page.evaluate("getComputedStyle(document.querySelector('.main-area')).gridTemplateColumns").split()
    assert len(columns) == 3, columns
    page.context.close()


@pytest.mark.parametrize("width,height", [(1366, 768), (390, 844)])
def test_text_zoom_works_and_line_numbers_stay_on_their_lines(served, width, height):
    page = served(width, height)
    measure = """() => {
        const t = getComputedStyle(document.getElementById('soloTextarea'));
        const n = getComputedStyle(document.getElementById('lineNumbers'));
        return [parseFloat(t.fontSize), parseFloat(t.lineHeight), parseFloat(n.lineHeight)];
    }"""
    base_font, base_line, base_numbers = page.evaluate(measure)
    assert base_numbers == pytest.approx(base_line, abs=0.05)
    for _ in range(3):
        page.evaluate("adjustZoom('manuscript', 1)")
    font, line, numbers = page.evaluate(measure)
    assert font > base_font * 1.2, (base_font, font)
    assert numbers == pytest.approx(line, abs=0.05), "line numbers drift off their lines when zoomed"
    page.evaluate("adjustZoom('chat', 1)")
    chat = page.evaluate("parseFloat(getComputedStyle(document.getElementById('chatInput')).fontSize)")
    page.evaluate("adjustZoom('chat', -1)")
    assert chat > page.evaluate("parseFloat(getComputedStyle(document.getElementById('chatInput')).fontSize)")
    page.evaluate("localStorage.removeItem('2i_zoom')")
    page.context.close()


def test_the_spiral_is_redrawn_when_the_page_changes_size(served):
    page = served(1366, 768)
    fit = """() => {
        const c = document.getElementById('spineCanvas'), r = c.parentElement.getBoundingClientRect();
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        return [c.width, Math.round(r.width * dpr), c.height, Math.round(r.height * dpr)];
    }"""
    width, want_width, height, want_height = page.evaluate(fit)
    assert abs(width - want_width) <= 1 and abs(height - want_height) <= 1
    page.click("#modeBadge")                      # Collab changes the page without resizing the window
    page.click("#sidebarToggle")
    page.wait_for_timeout(200)
    width, want_width, height, want_height = page.evaluate(fit)
    assert abs(width - want_width) <= 1 and abs(height - want_height) <= 1, (width, want_width, height, want_height)
    page.context.close()


def test_collab_on_a_phone_shows_the_draft_and_its_controls(served):
    page = served(390, 844)
    page.click("#modeBadge")
    page.wait_for_selector("#draftArea", state="visible")
    page.fill("#draftArea", "A line written on a phone.")
    assert page.input_value("#draftArea") == "A line written on a phone."
    assert page.evaluate(LAYOUT)["spill"] == []
    page.context.close()

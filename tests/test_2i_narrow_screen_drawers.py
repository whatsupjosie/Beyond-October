"""2i on a narrow screen: the page takes the screen and the side panels are drawers.

Before this, at 390 px wide the three panels stayed side by side and the writing page was squeezed to a sliver
(10 px inside the host). Below 850 px the page now fills the screen; the left panel (and, inside the host, the
conversation on the right) slide over it from tabs on the edges, closed until asked for.

These tests drive the real page in Chromium, opened from disk with the network blocked, at phone size with touch.
Inside the host reach.js moves the conversation panel out of the left panel into the main area; the tests that
need the right-hand drawer do that same single move themselves, and say so. The layout inside the real host is
checked separately in test_2i_hosted_layout.py. They skip when Playwright or its browser is unavailable.
"""
from __future__ import annotations

from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PAGE = Path(__file__).resolve().parents[1] / "2i" / "writers-room-v22.html"
PHONE = {"width": 390, "height": 844}

BOX = """(id) => { const r = document.getElementById(id).getBoundingClientRect();
  return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
          visible: getComputedStyle(document.getElementById(id)).visibility !== 'hidden' && getComputedStyle(document.getElementById(id)).display !== 'none'}; }"""


def _settle(page):
    page.wait_for_timeout(350)  # drawer transition is 220 ms


def _on_screen(box, viewport=PHONE):
    return box["visible"] and box["w"] > 0 and box["x"] >= 0 and box["x"] + box["w"] <= viewport["width"]


@pytest.fixture()
def phone():
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # browser binary not installed
            pytest.skip(f"Chromium unavailable for Playwright: {exc}")
        context = browser.new_context(viewport=PHONE, has_touch=True, is_mobile=True, device_scale_factor=2)
        context.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file:") else route.abort())
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(PAGE.as_uri())
        page.wait_for_function("typeof twoiDrawers === 'object' && typeof loadDocState === 'function'")
        page.evaluate("() => { if (coWriting) { coWriting = false; updateModeUI(); } }")
        yield page, errors
        assert errors == []
        browser.close()


def _like_the_host(page):
    """reach.js line: $('mainArea').appendChild($('chatSection')) — the conversation becomes its own panel."""
    page.evaluate("document.getElementById('mainArea').appendChild(document.getElementById('chatSection'))")


def test_the_page_fills_a_phone_screen_and_the_panels_start_closed(phone):
    page, _ = phone
    frame, writing, sidebar = (page.evaluate(BOX, i) for i in ("notebookFrame", "soloTextarea", "sidebar"))
    assert frame["x"] == 0 and frame["w"] == PHONE["width"]
    assert writing["w"] >= 200 and writing["h"] >= 400
    assert not sidebar["visible"] and sidebar["x"] + sidebar["w"] <= 0
    assert page.evaluate("document.body.dataset.twoiDrawer") is None
    assert page.evaluate("[document.documentElement.scrollWidth, document.documentElement.scrollHeight]") == [PHONE["width"], PHONE["height"]]
    save = page.evaluate(BOX, "saveBtn")
    assert save["visible"] and save["y"] + save["h"] <= PHONE["height"] and save["h"] >= 40


def test_the_edge_tab_never_covers_the_writing(phone):
    page, _ = phone
    tab, writing = page.evaluate(BOX, "twoiDrawerTabTools"), page.evaluate(BOX, "soloTextarea")
    assert tab["visible"] and tab["x"] == 0 and tab["h"] >= 96
    assert tab["x"] + tab["w"] <= writing["x"]


def test_the_tab_opens_the_drawer_and_the_same_tab_closes_it(phone):
    page, _ = phone
    page.tap("#twoiDrawerTabTools")
    _settle(page)
    assert page.evaluate("document.body.dataset.twoiDrawer") == "tools"
    assert _on_screen(page.evaluate(BOX, "sidebar"))
    assert page.get_attribute("#twoiDrawerTabTools", "aria-expanded") == "true"
    assert page.evaluate("document.getElementById('notebookFrame').inert") is True
    # focus lands on a button, not a text field, so the phone keyboard does not rise over the drawer
    assert page.evaluate("document.activeElement.tagName") == "BUTTON"
    tab, drawer = page.evaluate(BOX, "twoiDrawerTabTools"), page.evaluate(BOX, "sidebar")
    assert tab["x"] == drawer["x"] + drawer["w"] and tab["x"] + tab["w"] <= PHONE["width"]
    page.tap("#twoiDrawerTabTools")
    _settle(page)
    assert page.evaluate("document.body.dataset.twoiDrawer") is None
    assert not page.evaluate(BOX, "sidebar")["visible"]
    assert page.get_attribute("#twoiDrawerTabTools", "aria-expanded") == "false"
    assert page.evaluate("document.getElementById('notebookFrame').inert") is False
    assert page.evaluate("document.activeElement.id") == "twoiDrawerTabTools"


def test_escape_and_the_dimmed_page_both_close_the_drawer(phone):
    page, _ = phone
    page.tap("#twoiDrawerTabTools")
    _settle(page)
    page.keyboard.press("Escape")
    _settle(page)
    assert page.evaluate("document.body.dataset.twoiDrawer") is None
    page.tap("#twoiDrawerTabTools")
    _settle(page)
    page.touchscreen.tap(PHONE["width"] - 8, 200)  # the dimmed page beside the drawer
    _settle(page)
    assert page.evaluate("document.body.dataset.twoiDrawer") is None


def test_writing_survives_every_drawer_movement(phone):
    page, _ = phone
    page.tap("#soloTextarea")
    page.keyboard.type("A line typed before any drawer moved.")
    for _ in range(3):
        page.tap("#twoiDrawerTabTools")
        _settle(page)
        page.tap("#twoiDrawerTabTools")
        _settle(page)
    assert page.evaluate("soloTextarea.value") == "A line typed before any drawer moved."
    assert page.evaluate("getDocState().committed") == ["A line typed before any drawer moved."]
    page.tap("#soloTextarea")
    page.keyboard.type(" More.")
    assert page.evaluate("getDocState().committed") == ["A line typed before any drawer moved. More."]


def test_the_menu_button_opens_the_same_drawer_on_a_phone(phone):
    page, _ = phone
    page.tap("#sidebarToggle")
    _settle(page)
    assert page.evaluate("document.body.dataset.twoiDrawer") == "tools"
    assert "sidebar-hidden" not in page.get_attribute("#mainArea", "class")
    page.tap("#sidebarToggle")
    _settle(page)
    assert page.evaluate("document.body.dataset.twoiDrawer") is None


def test_opening_a_reference_closes_the_drawer_so_the_reference_can_be_read(phone):
    page, _ = phone
    page.evaluate("""() => { references.push({id: 'r1', name: 'Town map', content: 'The mill is north of the bridge.', type: 'notes'}); renderRefs(); }""")
    page.tap("#twoiDrawerTabTools")
    _settle(page)
    page.evaluate("viewRef('r1')")
    _settle(page)
    assert page.evaluate("document.body.dataset.twoiDrawer") is None
    assert "open" in page.get_attribute("#refViewer", "class")
    assert page.inner_text("#refViewerBody") == "The mill is north of the bridge."


def test_from_disk_there_is_one_drawer_because_the_conversation_lives_in_the_left_panel(phone):
    page, _ = phone
    assert page.evaluate("document.getElementById('chatSection').parentElement.id") == "sidebar"
    assert page.evaluate("getComputedStyle(document.getElementById('twoiDrawerTabPartner')).display") == "none"
    assert page.evaluate("twoiDrawers.open('partner')") is False
    page.tap("#twoiDrawerTabTools")
    _settle(page)
    assert _on_screen(page.evaluate(BOX, "chatSection"))  # reachable inside the left drawer


def test_inside_the_host_the_conversation_is_a_second_drawer_on_the_right(phone):
    page, _ = phone
    _like_the_host(page)
    _settle(page)
    tab = page.evaluate(BOX, "twoiDrawerTabPartner")
    assert tab["visible"] and tab["x"] + tab["w"] == PHONE["width"]
    assert not page.evaluate(BOX, "chatSection")["visible"]
    page.tap("#twoiDrawerTabPartner")
    _settle(page)
    chat = page.evaluate(BOX, "chatSection")
    assert _on_screen(chat) and chat["x"] + chat["w"] == PHONE["width"]
    assert not page.evaluate(BOX, "sidebar")["visible"]
    assert not page.evaluate(BOX, "twoiDrawerTabTools")["visible"]  # the other tab steps aside
    page.fill("#chatInput", "half-typed message")
    page.tap("#twoiDrawerTabPartner")
    _settle(page)
    assert page.evaluate("document.body.dataset.twoiDrawer") is None
    page.tap("#twoiDrawerTabTools")  # only one drawer is ever open
    _settle(page)
    assert page.evaluate("document.body.dataset.twoiDrawer") == "tools"
    page.tap("#twoiDrawerTabTools")
    _settle(page)
    page.tap("#twoiDrawerTabPartner")
    _settle(page)
    assert page.input_value("#chatInput") == "half-typed message"


def test_a_short_screen_can_still_reach_the_message_box(phone):
    page, _ = phone
    _like_the_host(page)
    page.set_viewport_size({"width": 320, "height": 420})
    _settle(page)
    before = page.evaluate(BOX, "notebookFrame")
    page.tap("#twoiDrawerTabPartner")
    _settle(page)
    page.focus("#chatInput")
    _settle(page)
    box = page.evaluate(BOX, "chatInput")
    main = page.evaluate(BOX, "mainArea")
    assert box["y"] >= main["y"] and box["y"] + box["h"] <= main["y"] + main["h"]
    # reaching it scrolled the drawer, not the page underneath
    assert page.evaluate(BOX, "notebookFrame") == before
    assert page.evaluate("[document.documentElement.scrollTop, document.body.scrollTop, document.getElementById('mainArea').scrollTop]") == [0, 0, 0]


def test_widening_the_window_puts_the_panels_back_beside_the_page(phone):
    page, _ = phone
    page.tap("#soloTextarea")
    page.keyboard.type("Kept.")
    page.tap("#twoiDrawerTabTools")
    _settle(page)
    page.set_viewport_size({"width": 1280, "height": 800})
    _settle(page)
    wide = {"width": 1280, "height": 800}
    assert page.evaluate("document.body.dataset.twoiDrawer") is None
    assert page.evaluate("document.getElementById('notebookFrame').inert") is False
    sidebar, frame = page.evaluate(BOX, "sidebar"), page.evaluate(BOX, "notebookFrame")
    assert _on_screen(sidebar, wide) and _on_screen(frame, wide) and sidebar["x"] + sidebar["w"] <= frame["x"]
    assert page.evaluate("getComputedStyle(document.getElementById('twoiDrawerTabTools')).display") == "none"
    assert page.evaluate("twoiDrawers.open('tools')") is False  # drawers do nothing on a wide screen
    page.click("#sidebarToggle")  # and the menu button is the old sidebar switch again
    assert "sidebar-hidden" in page.get_attribute("#mainArea", "class")
    assert page.evaluate("soloTextarea.value") == "Kept."


def test_from_disk_the_writing_box_fills_the_page(phone):
    page, _ = phone
    page.set_viewport_size({"width": 1280, "height": 800})
    _settle(page)
    writing, sheets = page.evaluate(BOX, "soloTextarea"), page.evaluate(BOX, "pageSheets")
    assert writing["h"] >= sheets["h"] - 60  # before: about two lines tall inside a full-height page

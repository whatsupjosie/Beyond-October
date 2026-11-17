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
        # Only the page itself is served: its companion files (2i-assets, static) and the network are all blocked.
        context.route("**/*", lambda route: route.continue_() if route.request.url.split("?")[0] == PAGE.as_uri() else route.abort())
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


def test_the_tabs_are_small_sit_just_under_the_top_and_never_cover_the_page(phone):
    page, _ = phone
    _like_the_host(page)
    _settle(page)
    main, sheets = page.evaluate(BOX, "mainArea"), page.evaluate(BOX, "pageSheets")
    left, right = page.evaluate(BOX, "twoiDrawerTabTools"), page.evaluate(BOX, "twoiDrawerTabPartner")
    for tab in (left, right):
        assert tab["visible"] and tab["w"] <= 32 and tab["h"] <= 32
        assert 2 <= tab["y"] - main["y"] <= 8          # a small gap under whatever is above the main area
        assert tab["y"] + tab["h"] <= sheets["y"]      # the page starts below the tabs
    assert left["x"] == 0 and right["x"] + right["w"] == PHONE["width"]
    # and the notebook (its spiral and its page) runs the full width; no side rails are kept for the tabs
    notebook_width = page.evaluate("Math.round(document.querySelector('.notebook-inner').getBoundingClientRect().width)")
    assert notebook_width >= PHONE["width"] - 20
    # the touch area is larger than the visible tab: a finger 10 px to the side still lands on it
    assert page.evaluate("([x, y]) => document.elementFromPoint(x, y).id", [left["x"] + left["w"] + 10, left["y"] + 15]) == "twoiDrawerTabTools"
    assert page.evaluate("([x, y]) => document.elementFromPoint(x, y).id", [right["x"] - 10, right["y"] + 15]) == "twoiDrawerTabPartner"


def test_save_is_at_the_top_with_its_state_and_is_not_in_the_bottom_bar(phone):
    page, _ = phone
    save, state, main = page.evaluate(BOX, "saveBtn"), page.evaluate(BOX, "saveIndicator"), page.evaluate(BOX, "mainArea")
    assert save["visible"] and save["h"] >= 40 and save["y"] + save["h"] <= main["y"]
    assert state["visible"] and state["y"] + state["h"] <= main["y"]
    assert page.evaluate("document.querySelectorAll('#saveBtn').length") == 1


def test_nothing_sits_under_the_page_and_the_bottom_bar_items_have_new_homes(phone):
    page, _ = phone
    assert page.evaluate("document.querySelector('.status-bar')") is None
    frame = page.evaluate(BOX, "notebookFrame")
    assert frame["y"] + frame["h"] == PHONE["height"]          # the page runs to the bottom of the screen
    top = page.evaluate("Math.round(document.querySelector('.top-bar').getBoundingClientRect().bottom)")
    title = page.evaluate(BOX, "docTitleDisplay")
    assert title["visible"] and title["w"] > 0 and title["y"] + title["h"] <= top
    assert page.inner_text("#docTitleDisplay") == page.evaluate("documentTitle")
    page.tap("#soloTextarea")
    page.keyboard.type("four words right here")
    # the count follows the typing by itself (until 2026-11-16 it stood still until the page re-rendered)
    page.wait_for_function("document.getElementById('wordCount').textContent === '4 words'", timeout=3000)
    assert page.evaluate("document.getElementById('chatSection').contains(document.getElementById('llmPill'))")
    # the status word is hidden while idle and shown while something is happening
    assert page.evaluate("document.getElementById('statusLive').hidden") is True
    page.evaluate("() => { generating = true; render(); }")
    assert page.evaluate("[document.getElementById('statusLive').hidden, document.getElementById('statusText').textContent]") == [False, "generating…"]
    page.evaluate("() => { generating = false; render(); }")
    assert page.evaluate("document.getElementById('statusLive').hidden") is True
    # read-aloud controls belong to Collab, as before; they are at the top now
    assert not page.evaluate(BOX, "playbackControls")["visible"]
    page.evaluate("() => { coWriting = true; updateModeUI(); render(); }")
    controls = page.evaluate(BOX, "playbackControls")
    top = page.evaluate("Math.round(document.querySelector('.top-bar').getBoundingClientRect().bottom)")
    assert controls["visible"], controls
    assert controls["y"] + controls["h"] <= top + 1, (controls, top)   # +1: the two numbers are rounded separately
    assert page.evaluate(BOX, "playBtn")["h"] >= 40


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


def test_the_stylesheet_and_the_script_agree_on_where_narrow_begins(phone):
    """The 850 px boundary is written once in the stylesheet and once in the script; they must not drift apart."""
    page, _ = phone
    for width, narrow in ((850, True), (851, False)):
        page.set_viewport_size({"width": width, "height": 800})
        _settle(page)
        assert page.evaluate("twoiDrawers.narrow") is narrow, width
        assert (page.evaluate("getComputedStyle(document.getElementById('twoiDrawerTabTools')).display") != "none") is narrow, width
        assert page.evaluate("twoiDrawers.open('tools')") is narrow, width
        assert (page.evaluate("document.body.dataset.twoiDrawer") == "tools") is narrow, width
        _settle(page)
        sidebar = page.evaluate(BOX, "sidebar")
        assert sidebar["visible"] and sidebar["x"] >= 0, width   # open drawer at 850, ordinary side panel at 851
        page.evaluate("twoiDrawers.close(false)")
        _settle(page)


def test_a_new_line_in_the_conversation_marks_the_tab_until_that_drawer_is_opened(phone):
    """Menu commands report failures as a line in the conversation; in a closed drawer that would be silent."""
    page, _ = phone
    unseen = "[document.getElementById('twoiDrawerTabTools').dataset.unseen || null, document.getElementById('twoiDrawerTabPartner').dataset.unseen || null]"
    assert page.evaluate(unseen) == [None, None]
    page.evaluate("addChat('notice', 'That command is unavailable in the current editor state.')")
    _settle(page)
    assert page.evaluate(unseen) == ["true", None]      # from disk the conversation is in the left drawer
    page.tap("#twoiDrawerTabTools")
    _settle(page)
    assert page.evaluate(unseen) == [None, None]
    page.evaluate("addChat('notice', 'Seen at once: the drawer is open.')")
    _settle(page)
    assert page.evaluate(unseen) == [None, None]
    page.tap("#twoiDrawerTabTools")
    _settle(page)
    _like_the_host(page)                                   # now the conversation is the right-hand drawer
    page.evaluate("addChat('notice', 'A second message.')")
    _settle(page)
    assert page.evaluate(unseen) == [None, "true"]
    page.tap("#twoiDrawerTabTools")                        # opening the other drawer does not clear it
    _settle(page)
    page.tap("#twoiDrawerTabTools")
    _settle(page)
    assert page.evaluate(unseen) == [None, "true"]
    page.tap("#twoiDrawerTabPartner")
    _settle(page)
    assert page.evaluate(unseen) == [None, None]
    page.tap("#twoiDrawerTabPartner")
    _settle(page)
    page.evaluate("addChat('notice', 'Wide screens show the conversation, so nothing is marked.')")
    page.set_viewport_size({"width": 1280, "height": 800})
    _settle(page)
    assert page.evaluate(unseen) == [None, None]

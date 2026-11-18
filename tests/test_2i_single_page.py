"""The single-page notebook (the look 2i opens in outside the studio) and the typewriter from any window.

Josie's design, in her words: "a single notebook page, centered, adjustable margins, faintly blue-lined, with the
spiral notebook image kept at the side"; "only the top menu and the writing show (no AI window, no other panels)";
the drawer tabs "small, with an arrow"; opening the AI side "starts Collab automatically"; "In any open 2i window
she can switch between the notebook, the typewriter and the single-page notebook from the menu"; "audio effects
must be optional"; the page "should not be pure computer white".

Real Chromium, the real page opened from disk with its companion files, network blocked. Skips without Playwright.
"""
from __future__ import annotations

from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
PAGE = Path(__file__).resolve().parents[1] / "2i" / "writers-room-v22.html"
SHOWN = "id => { const e = document.getElementById(id), r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && r.right > 0 && r.left < innerWidth; }"


def _open(p, **context):
    try:
        browser = p.chromium.launch()
    except Exception as error:
        pytest.skip(f"Chromium is not available: {error}")
    ctx = browser.new_context(**context)
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file:") else route.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(PAGE.as_uri())
    page.wait_for_function("typeof initializing !== 'undefined' && !initializing && typeof twoiSetPresentation === 'function'", timeout=20000)
    return browser, page, errors


@pytest.fixture()
def laptop():
    with sync_api.sync_playwright() as p:
        browser, page, errors = _open(p, viewport={"width": 1280, "height": 800})
        yield page
        assert errors == []
        browser.close()


@pytest.fixture()
def phone():
    with sync_api.sync_playwright() as p:
        browser, page, errors = _open(p, viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        yield page
        assert errors == []
        browser.close()


def test_outside_the_studio_it_opens_as_the_single_page_with_only_the_writing_showing(laptop):
    page = laptop
    assert page.evaluate("document.body.dataset.twoiDesk") == "standard"
    assert page.evaluate(SHOWN, "soloTextarea")
    assert not page.evaluate(SHOWN, "sidebar")
    assert page.evaluate(SHOWN, "twoiMenuBar") and page.evaluate(SHOWN, "saveBtn")
    # centred: equal space either side of the bound page
    left, right = page.evaluate("(() => { const r = document.querySelector('.notebook-inner').getBoundingClientRect(); return [r.left, innerWidth - r.right]; })()")
    assert abs(left - right) <= 2 and left > 40
    # the binding stands at the page's side and is drawn
    assert page.evaluate(SHOWN, "spineCanvas") and page.evaluate("spineCanvas.width > 0")
    # tinted paper, not pure white, and faint rules under the writing
    paper = page.evaluate("getComputedStyle(document.getElementById('pageSheets')).backgroundColor")
    assert paper not in ("rgb(255, 255, 255)", "rgba(0, 0, 0, 0)"), paper
    assert "gradient" in page.evaluate("getComputedStyle(soloTextarea).backgroundImage")


def test_the_left_tab_brings_the_tools_out_and_puts_them_away(laptop):
    page = laptop
    tab = page.locator("#twoiDrawerTabTools")
    assert tab.is_visible() and tab.bounding_box()["width"] <= 32
    tab.click()
    assert page.evaluate(SHOWN, "sidebar") and tab.get_attribute("aria-expanded") == "true"
    assert page.evaluate(SHOWN, "soloTextarea")           # the page is still there, beside the tools
    tab.click()
    assert not page.evaluate(SHOWN, "sidebar") and tab.get_attribute("aria-expanded") == "false"


def test_the_right_tab_opens_the_ai_side_and_that_starts_collab(laptop):
    page = laptop
    page.click("#soloTextarea")
    page.keyboard.insert_text("One line kept.")
    page.click("#twoiDrawerTabPartner")
    page.wait_for_function("coWriting === true", timeout=3000)
    assert page.evaluate(SHOWN, "sidebar")                # in Collab the panels are where they always were
    assert page.evaluate("committed.join('\\n')") == "One line kept."
    assert not page.locator("#twoiDrawerTabPartner").is_visible()
    page.evaluate("document.getElementById('modeBadge').click()")   # back to Write: only the writing again
    assert not page.evaluate(SHOWN, "sidebar") and page.evaluate("soloTextarea.value") == "One line kept."


def test_margins_change_the_space_beside_the_writing_and_are_remembered(laptop):
    page = laptop
    pad = lambda: page.evaluate("[parseFloat(getComputedStyle(soloTextarea).paddingLeft), parseFloat(getComputedStyle(soloTextarea).paddingRight)]")
    normal = pad()
    page.select_option("#twoiMarginSelect", "144")
    assert pad() == [144, 144] and normal == [56, 56]
    page.select_option("#twoiMarginSelect", "24")
    assert pad() == [24, 24]
    assert page.evaluate("localStorage.getItem('twoi.page.margin.v1')") == "24"
    page.reload()
    page.wait_for_function("typeof initializing !== 'undefined' && !initializing && typeof twoiSetPresentation === 'function'", timeout=20000)
    assert page.evaluate("document.getElementById('twoiMarginSelect').value") == "24" and pad() == [24, 24]


def test_on_a_phone_the_single_page_takes_the_whole_width(phone):
    page = phone
    assert not page.evaluate(SHOWN, "spineCanvas")
    box = page.evaluate("(() => { const r = soloTextarea.getBoundingClientRect(); return [r.width, parseFloat(getComputedStyle(soloTextarea).paddingLeft)]; })()")
    assert box[0] >= 300 and box[1] <= 14
    page.evaluate("(() => { const s = document.getElementById('twoiMarginSelect'); s.value = '144'; s.dispatchEvent(new Event('change')); })()")
    assert page.evaluate("parseFloat(getComputedStyle(soloTextarea).paddingLeft)") <= 14     # a wide margin never squeezes a phone
    assert page.evaluate("[document.documentElement.scrollWidth, innerWidth]") == [390, 390]


def test_the_typewriter_can_be_chosen_from_any_window_and_its_sounds_start_off(laptop):
    page = laptop
    assert page.evaluate("twoiCanPresent('typewriter')") is True
    view = page.evaluate("[...document.querySelectorAll('#twoiMenuBar select')].flatMap(s => [...s.options].map(o => o.textContent))")
    assert any("Typewriter view" in label for label in view)
    page.evaluate("twoiSetPresentation('typewriter')")
    assert page.evaluate("document.body.dataset.twoiDesk") == "typewriter"
    assert page.evaluate(SHOWN, "soloTextarea")
    # The art and optional audio controls must exist outside studio seats too.
    scene = page.locator("#twoiDeskScene")
    assert scene.is_visible()
    assert page.locator("#twoiAudioOptions").is_visible()
    # Offline standalone 2i resolves companion artwork without a running host.
    assert scene.locator("img").evaluate("(image) => image.complete && image.naturalWidth > 0")
    assert page.locator("#twoiPaperPreview").get_attribute("aria-hidden") == "true"
    stored = page.evaluate("localStorage.getItem('twoi.typewriter.audio.v1')")
    assert stored is None or '"click":false' in stored
    page.evaluate("twoiSetPresentation('notebook')")
    assert not scene.is_visible()
    assert page.evaluate("document.body.dataset.twoiDesk") == "notebook" and page.evaluate("spineCanvas.width > 0")

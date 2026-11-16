"""2i opened on its own, from disk, must work without its separate script files.

The page loads /2i-assets/format-core.js and its other helpers by absolute path. Opened from disk those paths do
not resolve, so none of them load. Commit 8ab7945 made the page's own script use the formatting core without
checking for it, and from disk the whole script stopped at that line: no typing, no saving, no reading aloud.

These tests drive the real page in Chromium, from disk, with every network request blocked. They check that the
page starts without a script error, that writing reaches the document, that formatting commands report themselves
as off, and that formatting already saved in a document survives a save in this mode unchanged (it is neither
dropped nor rewritten, because the code that understands it is absent). They skip, like the other optional
browser checks, when Playwright or its browser is unavailable.
"""
from __future__ import annotations

from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PAGE = Path(__file__).resolve().parents[1] / "2i" / "writers-room-v22.html"
LINES = ["INT. KITCHEN - NIGHT", "She sets the kettle down.", "MARA", "Not tonight."]
FORMATTING = {
    "version": 1,
    "profile": "film",
    "page": {"size": "letter", "orientation": "portrait", "margin": 1},
    "rows": [{"index": 0, "text": "INT. KITCHEN - NIGHT", "style": {"role": "scene"}}],
    "unmapped": [],
    "annotations": [],
}


@pytest.fixture()
def opened():
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # browser binary not installed
            pytest.skip(f"Chromium unavailable for Playwright: {exc}")
        context = browser.new_context()
        context.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file:") else route.abort())
        pg = context.new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(PAGE.as_uri())
        pg.wait_for_load_state("load")
        pg.wait_for_timeout(300)
        yield pg, errors
        browser.close()


def test_page_starts_from_disk_without_a_script_error(opened):
    page, errors = opened
    assert errors == []
    assert page.evaluate("typeof TwoiFormatCore") == "undefined"  # the precondition this file is about
    assert page.evaluate("typeof loadDocState === 'function' && typeof getDocState === 'function'")


def test_formatting_reports_itself_off_instead_of_failing(opened):
    page, errors = opened
    assert page.evaluate("[formatCoreLoaded, nativeFormatting, manuscriptFormat, getFormatContext()]") == [False, False, None, None]
    assert page.evaluate("document.getElementById('twoiMenuBar')") is None
    assert errors == []


def test_typing_reaches_the_document(opened):
    page, errors = opened
    page.evaluate("() => { if (coWriting) { coWriting = false; updateModeUI(); } }")
    page.click("#soloTextarea")
    page.keyboard.type("First line.")
    page.keyboard.press("Enter")
    page.keyboard.type("Second line.")
    assert page.evaluate("getDocState().committed") == ["First line.", "Second line."]
    assert errors == []


def test_saved_formatting_is_carried_through_unchanged(opened):
    page, errors = opened
    saved = page.evaluate(
        """([lines, formatting]) => {
            loadDocState({committed: lines, coWriting: false, formatting});
            render();
            return getDocState();
        }""",
        [LINES, FORMATTING],
    )
    assert saved["committed"] == LINES
    assert saved["formatting"] == FORMATTING
    assert page.evaluate("docPayload().state.formatting") == FORMATTING
    assert errors == []


def test_carried_formatting_survives_an_edit_and_an_undo_point(opened):
    page, errors = opened
    saved = page.evaluate(
        """([lines, formatting]) => {
            loadDocState({committed: lines, coWriting: false, formatting});
            render();
            soloTextarea.value += '\\nA new last line.';
            soloTextarea.dispatchEvent(new Event('input', {bubbles: true}));
            return getDocState();
        }""",
        [LINES, FORMATTING],
    )
    assert saved["committed"] == LINES + ["A new last line."]
    assert saved["formatting"] == FORMATTING
    assert errors == []


def test_a_document_without_formatting_gains_none(opened):
    page, errors = opened
    saved = page.evaluate("(lines) => { loadDocState({committed: lines, coWriting: false}); return getDocState(); }", LINES)
    assert "formatting" not in saved
    assert errors == []


def test_formatting_does_not_leak_into_the_next_document(opened):
    page, errors = opened
    page.evaluate("([lines, formatting]) => loadDocState({committed: lines, coWriting: false, formatting})", [LINES, FORMATTING])
    assert "formatting" not in page.evaluate("(lines) => { loadDocState({committed: lines, coWriting: false}); return getDocState(); }", LINES[:1])
    page.evaluate("([lines, formatting]) => loadDocState({committed: lines, coWriting: false, formatting})", [LINES, FORMATTING])
    page.evaluate("() => { documentDirty = false; newDocument(); }")
    after_new = page.evaluate("getDocState()")
    assert after_new["committed"] == []
    assert "formatting" not in after_new
    assert errors == []

"""2i data-safety regression: a restored manuscript must be visible in solo mode.

Before the fix, loadDocState() restored `committed` in memory but left the solo
textarea blank; the textarea's input handler rebuilds `committed` from its value,
so the writer's first keystroke replaced the whole manuscript with that keystroke.
This drives the real page in Chromium. It skips, like the other optional browser
checks, when Playwright or its browser is unavailable.
"""
from __future__ import annotations

from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PAGE = Path(__file__).resolve().parents[1] / "2i" / "writers-room-v22.html"
MANUSCRIPT = ["It was the first line.", "And this, the second.", "", "A third after a gap."]


@pytest.fixture()
def page():
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # browser binary not installed
            pytest.skip(f"Chromium unavailable for Playwright: {exc}")
        context = browser.new_context()
        # Offline: block every network request; the page is opened from disk.
        context.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file:") else route.abort())
        pg = context.new_page()
        pg.goto(PAGE.as_uri())
        pg.wait_for_function("typeof loadDocState === 'function' && typeof soloTextarea !== 'undefined'")
        yield pg
        browser.close()


def _restore(pg):
    pg.evaluate(
        """(lines) => {
            if (coWriting) { coWriting = false; updateModeUI(); }
            loadDocState({committed: lines, coWriting: false});
        }""",
        MANUSCRIPT,
    )


def test_restored_manuscript_is_written_into_solo_textarea(page):
    _restore(page)
    assert page.evaluate("soloTextarea.value") == "\n".join(MANUSCRIPT)


def test_first_keystroke_after_restore_keeps_the_manuscript(page):
    _restore(page)
    page.evaluate(
        """() => {
            soloTextarea.focus();
            soloTextarea.setSelectionRange(soloTextarea.value.length, soloTextarea.value.length);
        }"""
    )
    page.keyboard.type("!")
    committed = page.evaluate("committed")
    assert committed[:-1] == MANUSCRIPT[:-1]
    assert committed[-1] == MANUSCRIPT[-1] + "!"

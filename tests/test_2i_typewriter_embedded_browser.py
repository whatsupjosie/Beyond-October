"""Real host/browser acceptance for Claude's interactive typewriter inside 2i.

Exercises the iframe and actual Save Now path. Never replaces the user's data:
the imported 'reach' fixture creates a disposable host, account and data folder.
Run: python -m pytest tests/test_2i_typewriter_embedded_browser.py -v
"""
from __future__ import annotations

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
from tests.test_2i_hosted_layout import reach, _open  # existing disposable authenticated host


def test_typewriter_edits_real_manuscript_and_survives_save_reload(reach):
    with sync_api.sync_playwright() as p:
        browser, page, errors = _open(p, reach, 1280, 800)
        try:
            page.evaluate("twoiSetPresentation('typewriter')")
            page.wait_for_function(
                "document.querySelector('#twoiTypewriterConsole')?.dataset.ready === 'true'",
                timeout=20000,
            )
            frame = page.frame_locator("#twoiTypewriterConsole")
            assert frame.locator("[data-typewriter-paper]").count() == 1
            # Keys come from Claude's original hotspot map, not an invented keyboard.
            frame.locator('[data-key-char="A"]').first.click()
            frame.locator('[data-key-char="B"]').first.click()
            page.wait_for_function("soloTextarea.value.endsWith('ab')")
            assert page.evaluate("committed.join('\\n')").endswith("ab")
            assert page.evaluate("documentDirty") is True
            frame.locator("[data-typewriter-paper]").wait_for()
            assert frame.locator("[data-typewriter-paper]").inner_text().endswith("ab")
            page.locator("#saveBtn").click()
            page.wait_for_function(
                "document.getElementById('saveIndicator').textContent.includes('Saved to Reach')",
                timeout=15000,
            )
            original = page.evaluate("soloTextarea.value")
            page.reload()
            page.wait_for_function(
                "typeof initializing !== 'undefined' && !initializing && !!document.getElementById('soloTextarea')",
                timeout=20000,
            )
            assert page.evaluate("soloTextarea.value") == original
            assert errors == []
        finally:
            browser.close()


def test_typewriter_retains_caret_and_parent_ignores_unrelated_messages(reach):
    with sync_api.sync_playwright() as p:
        browser, page, errors = _open(p, reach, 1280, 800)
        try:
            page.evaluate("twoiSetPresentation('typewriter')")
            page.wait_for_function(
                "document.querySelector('#twoiTypewriterConsole')?.dataset.ready === 'true'",
                timeout=20000,
            )
            page.locator("#soloTextarea").fill("ab")
            page.evaluate("soloTextarea.focus(); soloTextarea.setSelectionRange(1,1)")
            frame = page.frame_locator("#twoiTypewriterConsole")
            frame.locator('[data-key-char="X"]').first.click()
            page.wait_for_function("soloTextarea.value === 'axb'")
            # The listener must authenticate the source window, not just a message's shape.
            page.evaluate("""() => window.postMessage({
              type:'pubcast:2i-key',key:{char:'Z',text:'z',source:'pointer'}
            },location.origin)""")
            assert page.evaluate("soloTextarea.value") == "axb"
            assert errors == []
        finally:
            browser.close()

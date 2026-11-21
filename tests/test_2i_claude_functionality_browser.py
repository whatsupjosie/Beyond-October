"""Browser acceptance for Claude's functional 2i fixes on the integrated editor.

Uses the served standalone 2i file with real companion scripts and real Chromium.
No accounts, remote resources or GitHub Actions are needed for the test itself.
"""
from __future__ import annotations

from pathlib import Path
import pytest

sync_api = pytest.importorskip("playwright.sync_api")
PAGE = Path(__file__).resolve().parents[1] / "2i" / "writers-room-v22.html"


@pytest.fixture()
def editor():
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"Chromium unavailable: {exc}")
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file:") else route.abort())
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(PAGE.as_uri())
        page.wait_for_function("typeof initializing !== 'undefined' && !initializing && !!document.getElementById('soloTextarea')", timeout=20000)
        yield page
        assert not errors, errors
        browser.close()


def _write(page, text):
    page.locator("#soloTextarea").click()
    page.keyboard.press("Control+a")
    page.keyboard.insert_text(text)


def test_unlock_by_write_caret_without_selected_collab_line(editor):
    page = editor
    _write(page, "A\nB\nC")
    page.locator("#lockAllBtn").click()
    page.evaluate("""() => {
      const t = document.getElementById('soloTextarea');
      t.focus(); t.setSelectionRange(3,3);
    }""")
    page.locator("#unlockBtn").click()
    assert sorted(page.evaluate("[...lockedLines]")) == [0,2]
    assert page.input_value("#soloTextarea") == "A\nB\nC"


def test_undo_lock_preserves_later_text_then_redo_relocks(editor):
    page = editor
    _write(page, "First.")
    page.locator("#lockSceneBtn").click()
    assert page.evaluate("[...lockedLines]") == [0]
    page.evaluate("""() => {
      const t = document.getElementById('soloTextarea');
      t.focus(); t.setSelectionRange(t.value.length,t.value.length);
    }""")
    page.keyboard.press("Enter")
    page.keyboard.insert_text("Second paragraph written after the lock.")
    assert page.input_value("#soloTextarea") == "First.\nSecond paragraph written after the lock."
    page.locator("#saveBtn").focus()
    page.keyboard.press("Control+z")
    assert page.evaluate("[...lockedLines]") == []
    assert page.input_value("#soloTextarea") == "First.\nSecond paragraph written after the lock."
    page.keyboard.press("Control+Shift+z")
    assert page.evaluate("[...lockedLines]") == [0]
    assert page.input_value("#soloTextarea") == "First.\nSecond paragraph written after the lock."


@pytest.mark.parametrize("field", ["#frFind","#renameInput"])
def test_undo_in_find_or_rename_does_not_rewind_manuscript(editor, field):
    page = editor
    _write(page, "Before.")
    page.locator("#lockAllBtn").click()
    page.evaluate("""() => {
      const t = document.getElementById('soloTextarea');
      t.focus();t.setSelectionRange(t.value.length,t.value.length);
    }""")
    page.keyboard.press("Enter")
    page.keyboard.insert_text("After.")
    before = page.input_value("#soloTextarea")
    if field == "#frFind":
        page.evaluate("openModal('frModalBackdrop')")
    else:
        page.evaluate("openModal('renameModalBackdrop')")
    page.locator(field).click()
    page.keyboard.insert_text("find text")
    for combo in ("Control+z","Control+y","Control+Shift+z"):
        page.keyboard.press(combo)
        assert page.input_value("#soloTextarea") == before, combo


def test_replace_all_counts_once_and_preserves_locked_lines(editor):
    page = editor
    _write(page, "the cat sat\nthe cat is locked\na cat and a cat")
    page.evaluate("lockedLines.add(1)")
    page.evaluate("openModal('frModalBackdrop')")
    page.locator("#frFind").fill("cat")
    page.locator("#frReplace").fill("fox")
    page.locator("#frReplaceAllBtn").click()
    assert page.input_value("#soloTextarea") == "the fox sat\nthe cat is locked\na fox and a fox"
    assert page.evaluate("committed.join('\\n')") == page.input_value("#soloTextarea")
    assert "3 replacement" in page.inner_text("#frResult")


def test_cancel_chapter_does_not_add_an_undo_point(editor):
    page = editor
    before = page.evaluate("undoStack.length")
    page.on("dialog", lambda d: d.dismiss())
    page.locator("#newChapterBtn").click()
    assert page.evaluate("undoStack.length") == before

"""2i opened straight from its file, with its companion files beside it and no host running.

Josie: "If it has no menus, we need to add those menus ... the menus have to work."

Before this, the page addressed its companion files in a way that only resolved when the host served them, so from
disk none of them loaded: no menu bar, no view switch, no versions. They are now addressed so that they resolve
both on the host and from disk. reach.js already had a deliberate path for running without a host (it keeps a
recovery copy in the browser and marks host-only work unavailable); from disk that path now runs.

What these tests hold, in real Chromium with the network blocked:
- the menus are there and a command chosen from one really runs; commands that need the host are offered as
  unavailable, not as working;
- Save writes the manuscript FILE. A browser file picker cannot be driven by an automated test, so the picker is
  replaced by a stand-in that records what is written to the file it hands back. The code under test is the real
  page and the real reach.js;
- automatic saves never write the file or raise a picker; closing the picker saves nothing and downloads nothing;
  a browser without a file picker gets a downloaded copy;
- what was typed comes back after a reload, from the browser's recovery copy.
They skip when Playwright or its browser is unavailable.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PAGE = Path(__file__).resolve().parents[1] / "2i" / "writers-room-v22.html"

# Stand-in for the browser's file pickers. Everything written to the "file" is recorded on window.__file.
PICKERS = """
window.__file = {writes: [], savePickers: 0, openPickers: 0, cancel: false, toOpen: null};
function __handle(name) {
  return {name, kind: 'file',
    async createWritable() { let data = ''; return {async write(d) { data += d; }, async close() { window.__file.writes.push({name, data}); }}; },
    async getFile() { return new File([window.__file.toOpen], name, {type: 'application/json'}); }};
}
window.showSaveFilePicker = async () => { window.__file.savePickers++;
  if (window.__file.cancel) throw new DOMException('The user aborted a request.', 'AbortError');
  return __handle('story.2i'); };
window.showOpenFilePicker = async () => { window.__file.openPickers++;
  if (window.__file.cancel) throw new DOMException('The user aborted a request.', 'AbortError');
  return [__handle('opened.2i')]; };
"""
NO_PICKERS = "delete window.showSaveFilePicker; delete window.showOpenFilePicker; Object.defineProperty(window, 'showSaveFilePicker', {value: undefined, configurable: true}); delete window.showSaveFilePicker;"


def _open(p, script, viewport=None, touch=False):
    try:
        browser = p.chromium.launch()
    except Exception as exc:  # browser binary not installed
        pytest.skip(f"Chromium unavailable for Playwright: {exc}")
    context = browser.new_context(viewport=viewport or {"width": 1280, "height": 800}, has_touch=touch, is_mobile=touch, accept_downloads=True)
    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file:") else route.abort())
    context.add_init_script(script)
    page = context.new_page()
    errors: list[str] = []
    downloads: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("download", lambda d: downloads.append(d.suggested_filename))
    page.goto(PAGE.as_uri())
    page.wait_for_function("!!document.getElementById('twoiMenuBar') && typeof initializing !== 'undefined' && !initializing", timeout=20000)
    page.evaluate("() => { if (coWriting) { coWriting = false; updateModeUI(); } }")
    return browser, page, errors, downloads


@pytest.fixture()
def disk():
    with sync_api.sync_playwright() as p:
        browser, page, errors, downloads = _open(p, PICKERS)
        yield page, errors, downloads
        assert errors == []
        browser.close()


def _type(page, text):
    page.click("#soloTextarea")
    page.keyboard.type(text)


def _choose(page, menu, command):
    selector = f'#twoiMenuBar select[aria-label="{menu}"]'
    page.evaluate(f"document.querySelector('{selector}').dispatchEvent(new Event('focus'))")
    index = page.evaluate(f"Array.from(document.querySelector('{selector}').options).findIndex(o => o.textContent === {json.dumps(command)})")
    assert index > 0, (menu, command)
    return selector, index


def _available(page, menu, command):
    selector, index = _choose(page, menu, command)
    return not page.evaluate(f"document.querySelector('{selector}').options[{index}].disabled")


def test_the_menus_are_there_with_no_host_and_nothing_fails(disk):
    page, errors, _ = disk
    page.wait_for_timeout(2600)  # start-up checks that would reach for a host have run by now
    assert errors == []
    names = page.evaluate("Array.from(document.querySelectorAll('#twoiMenuBar select')).map(s => s.getAttribute('aria-label'))")
    assert names[:12] == ["File", "Edit", "Insert", "Format", "Layout", "References", "Manuscript", "Review", "View", "Tools", "Studio", "Help"]
    assert page.evaluate("[networked, serverReady, typeof documentId, typeof TwoiFormatCore, typeof PubcastSpeech]") == [False, False, "string", "object", "undefined"]
    assert page.evaluate("document.body.dataset.twoiDesk") == "standard"


def test_commands_that_need_the_host_are_offered_as_unavailable_and_the_rest_are_available(disk):
    page, _, _ = disk
    _type(page, "Something to work on.")
    for menu, command in (("Review", "Revision history"), ("Review", "Story versions"), ("Studio", "Inbox"), ("Studio", "Write note"), ("Studio", "Place sticky note")):
        assert not _available(page, menu, command), (menu, command)
    for menu, command in (("File", "New"), ("File", "Save"), ("File", "Save a copy (.2i)"), ("Insert", "New chapter"), ("Layout", "Page setup"),
                          ("References", "Browse or search references"), ("Tools", "Word and character count"), ("View", "Notebook view"), ("Help", "Keyboard shortcuts")):
        assert _available(page, menu, command), (menu, command)


def test_a_command_chosen_from_a_menu_really_runs(disk):
    page, _, _ = disk
    _type(page, "Six words are on this page.")
    selector, index = _choose(page, "View", "Notebook view")
    page.select_option(selector, index=index)
    page.wait_for_timeout(200)
    assert page.evaluate("document.body.dataset.twoiDesk") == "notebook"
    assert page.evaluate("soloTextarea.value") == "Six words are on this page."
    selector, index = _choose(page, "Tools", "Word and character count")
    page.select_option(selector, index=index)
    page.wait_for_timeout(300)
    assert page.evaluate("!!document.querySelector('dialog[open]')")
    assert "6" in page.inner_text("dialog[open]")
    selector, index = _choose(page, "Insert", "New chapter")
    page.evaluate("document.querySelectorAll('dialog[open]').forEach(d => d.close())")
    before = page.evaluate("chapters.length")
    asked: list[str] = []
    page.once("dialog", lambda d: (asked.append(d.type), d.accept("The second chapter")))   # it asks for the chapter's name
    page.select_option(selector, index=index)
    page.wait_for_timeout(400)
    assert page.evaluate("chapters.length") == before + 1, asked


def test_save_writes_the_manuscript_file_and_later_saves_go_to_the_same_file(disk):
    page, _, downloads = disk
    _type(page, "The first saved line.")
    page.click("#saveBtn")
    page.wait_for_function("window.__file.writes.length === 1")
    first = page.evaluate("window.__file")
    assert first["savePickers"] == 1 and first["writes"][0]["name"] == "story.2i"
    saved = json.loads(first["writes"][0]["data"])
    assert saved["format"] == "2i-document" and saved["state"]["committed"] == ["The first saved line."]
    assert page.inner_text("#saveIndicator") == "Saved to story.2i"

    _type(page, " More.")
    page.wait_for_timeout(1500)  # the automatic save has run
    after_typing = page.evaluate("window.__file")
    assert len(after_typing["writes"]) == 1 and after_typing["savePickers"] == 1   # it did not touch the file or ask anything
    assert page.inner_text("#saveIndicator") == "Kept in this browser · Save to update story.2i"

    page.click("#saveBtn")
    page.wait_for_function("window.__file.writes.length === 2")
    second = page.evaluate("window.__file")
    assert second["savePickers"] == 1                                              # same file, no second picker
    assert json.loads(second["writes"][1]["data"])["state"]["committed"] == ["The first saved line. More."]
    assert page.inner_text("#saveIndicator") == "Saved to story.2i"
    assert downloads == []


def test_the_file_menu_and_the_keyboard_save_the_same_way_as_the_button(disk):
    page, _, _ = disk
    _type(page, "Saved from the menu.")
    selector, index = _choose(page, "File", "Save")
    page.select_option(selector, index=index)
    page.wait_for_function("window.__file.writes.length === 1")
    _type(page, " And the keyboard.")
    page.keyboard.press("Control+s")
    page.wait_for_function("window.__file.writes.length === 2")
    assert json.loads(page.evaluate("window.__file.writes[1].data"))["state"]["committed"] == ["Saved from the menu. And the keyboard."]
    assert page.evaluate("window.__file.savePickers") == 1


def test_closing_the_picker_saves_nothing_downloads_nothing_and_says_so(disk):
    page, _, downloads = disk
    _type(page, "Not saved yet.")
    page.wait_for_timeout(400)
    page.evaluate("window.__file.cancel = true")
    page.click("#saveBtn")
    page.wait_for_function("window.__file.savePickers === 1")
    page.wait_for_timeout(500)
    assert page.evaluate("window.__file.writes.length") == 0 and downloads == []
    assert page.inner_text("#saveIndicator") == "Not saved to a file · kept in this browser"
    assert page.evaluate("documentDirty") is True
    page.evaluate("window.__file.cancel = false")
    page.click("#saveBtn")                                                         # and Save still works afterwards
    page.wait_for_function("window.__file.writes.length === 1")


def test_opening_a_file_keeps_it_as_the_file_that_save_writes_to(disk):
    page, _, _ = disk
    document = {"format": "2i-document", "version": 4, "title": "Opened story",
                "state": {"committed": ["Line from the opened file."], "buffer": [], "pool": [], "pointer": 0,
                          "chapters": [{"title": "Chapter One", "subtitle": "", "startLine": 0}], "lockedLines": [], "coWriting": False, "references": []}}
    page.evaluate("(text) => { window.__file.toOpen = text; }", json.dumps(document))
    page.evaluate("openDocument()")
    page.wait_for_function("committed.join('') === 'Line from the opened file.'")
    page.wait_for_function("document.getElementById('saveIndicator').textContent === 'Opened opened.2i'")
    assert page.evaluate("[documentTitle, window.__file.openPickers]") == ["Opened story", 1]
    _type(page, " Edited.")
    page.click("#saveBtn")
    page.wait_for_function("window.__file.writes.length === 1")
    written = page.evaluate("window.__file")
    assert written["writes"][0]["name"] == "opened.2i" and written["savePickers"] == 0
    assert page.inner_text("#saveIndicator") == "Saved to opened.2i"


def test_what_was_typed_comes_back_after_a_reload(disk):
    page, _, _ = disk
    _type(page, "Typed before the page was reloaded.")
    page.wait_for_timeout(600)  # the recovery copy is written 120 ms after the last keystroke
    page.reload()
    page.wait_for_function("typeof initializing !== 'undefined' && !initializing", timeout=20000)
    assert page.evaluate("soloTextarea.value") == "Typed before the page was reloaded."
    assert page.evaluate("getDocState().committed") == ["Typed before the page was reloaded."]


def test_a_browser_without_a_file_picker_gets_a_downloaded_copy():
    with sync_api.sync_playwright() as p:
        browser, page, errors, downloads = _open(p, NO_PICKERS)
        try:
            assert page.evaluate("'showSaveFilePicker' in window") is False
            page.evaluate("documentTitle = 'Phone story'")
            _type(page, "Written where there is no file picker.")
            with page.expect_download() as waiting:
                page.click("#saveBtn")
            assert waiting.value.suggested_filename == "Phone story.2i"
            saved = json.loads(Path(waiting.value.path()).read_text(encoding="utf-8"))
            assert saved["state"]["committed"] == ["Written where there is no file picker."]
            assert page.inner_text("#saveIndicator") == "Copy downloaded · Phone story.2i"
            assert errors == []
        finally:
            browser.close()


def test_on_a_phone_from_disk_the_page_has_the_screen_and_both_drawers_work():
    with sync_api.sync_playwright() as p:
        browser, page, errors, _ = _open(p, NO_PICKERS, viewport={"width": 390, "height": 844}, touch=True)
        try:
            box = "(id) => { const e = document.getElementById(id), r = e.getBoundingClientRect(); return {x: Math.round(r.x), w: Math.round(r.width), visible: getComputedStyle(e).visibility !== 'hidden'}; }"
            frame = page.evaluate(box, "notebookFrame")
            assert frame["x"] == 0 and frame["w"] == 390
            page.tap("#soloTextarea")
            page.keyboard.type("Typed on a phone, from disk.")
            for tab, panel in (("twoiDrawerTabTools", "sidebar"), ("twoiDrawerTabPartner", "chatSection")):
                page.tap("#" + tab)
                page.wait_for_timeout(350)
                shown = page.evaluate(box, panel)
                assert shown["visible"] and shown["x"] >= 0 and shown["x"] + shown["w"] <= 390, panel
                page.tap("#" + tab)
                page.wait_for_timeout(350)
                assert not page.evaluate(box, panel)["visible"], panel
            assert page.evaluate("soloTextarea.value") == "Typed on a phone, from disk."
            assert page.evaluate("document.querySelectorAll('#twoiMenuBar select').length") == 13
            assert errors == []
        finally:
            browser.close()

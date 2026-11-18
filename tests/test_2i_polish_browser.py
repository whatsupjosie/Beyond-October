"""2i (writers-room-v22.html) on phones, tablets and desktops, in real Chromium.

The page is served the way the host serves it, with the real writers-room and
auth routes behind it (as in test_foresight_file_workspace.py). These checks
are about what a person sees and can reach: nothing runs off the side of the
screen, Save is always on screen, the editor is there, the per-pane text zoom
works with the Reach desk layer on top, the line numbers stay on their lines,
the spiral coils are redrawn when the page changes size, and keyboard
shortcuts never reach past the text box being typed in.
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


# ---- Keyboard: undo belongs to the box you are typing in ---------------------

def _write_then_lock(page, text):
    page.click("#soloTextarea")
    page.keyboard.press("Control+a")
    page.keyboard.press("Delete")
    page.keyboard.type(text)
    page.click("#lockSceneBtn")          # a manuscript action: records a manuscript undo step


@pytest.mark.parametrize("box", ["#frFind", "#renameInput", "#refSearchInput", "#chatInput"])
def test_ctrl_z_in_any_text_box_never_rolls_back_the_manuscript(served, box):
    page = served(1366, 768)
    _write_then_lock(page, "Alpha.")
    page.click("#soloTextarea")
    page.keyboard.press("Control+End")
    page.keyboard.press("Enter")                       # the locked line stays as it is; write below it
    page.keyboard.type("Beta gamma delta.")
    if box == "#frFind":
        page.keyboard.press("Control+f")
    elif box == "#renameInput":
        page.evaluate("openModal('renameModalBackdrop')")
    page.wait_for_selector(box, state="visible")
    page.click(box)
    page.keyboard.type("xyz")
    # Checked after every key: a redo straight after a wrong undo would hide it.
    for shortcut in ("Control+z", "Control+Shift+Z", "Control+y"):
        page.keyboard.press(shortcut)
        assert page.evaluate("committed.join('\\n')") == "Alpha.\nBeta gamma delta.", shortcut
    page.context.close()


def test_ctrl_z_outside_a_text_box_still_undoes_a_manuscript_action(served):
    page = served(1366, 768)
    _write_then_lock(page, "Alpha.")
    assert page.evaluate("[...lockedLines]") == [0]
    page.focus("#saveBtn")
    page.keyboard.press("Control+z")
    assert page.evaluate("[...lockedLines]") == []
    page.keyboard.press("Control+Shift+Z")             # the usual redo on a Mac and in most editors
    assert page.evaluate("[...lockedLines]") == [0]
    page.context.close()


def test_shortcuts_work_with_caps_lock_on(served):
    page = served(1366, 768)
    page.focus("#saveBtn")
    page.evaluate("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'F', ctrlKey: true, bubbles: true, cancelable: true}))")
    page.wait_for_selector("#frModalBackdrop.open")
    page.context.close()


def test_the_lantern_light_canvas_follows_the_page_size(served):
    page = served(1366, 768)
    page.click("#sidebarToggle")
    page.wait_for_timeout(200)
    canvas, frame = page.evaluate("[document.getElementById('lanternCanvas').width, document.getElementById('notebookFrame').clientWidth]")
    assert canvas == frame
    page.context.close()


# ---- Locks in Write mode, Replace all, who speaks ------------------------------

def _write(page, lines):
    page.click("#soloTextarea")
    page.keyboard.press("Control+a")
    page.keyboard.press("Delete")
    page.keyboard.type("\n".join(lines))


def _caret_to(page, line, column=0):
    page.evaluate(
        """([line, column]) => { const t = document.getElementById('soloTextarea');
            const lines = t.value.split('\\n'); let at = 0;
            for (let i = 0; i < line; i++) at += lines[i].length + 1;
            t.focus(); t.setSelectionRange(at + column, at + column); }""",
        [line, column],
    )


def _lock_line(page, index):
    page.evaluate("i => { lockedLines.add(i); render(); }", index)


def test_a_locked_line_cannot_be_typed_into_cut_or_pasted_over_in_write_mode(served):
    page = served(1366, 768)
    _write(page, ["One.", "Two is locked.", "Three."])
    _lock_line(page, 1)
    text = "One.\nTwo is locked.\nThree."
    _caret_to(page, 1, 3)
    page.keyboard.type("XX")
    assert page.input_value("#soloTextarea") == text
    assert page.evaluate("committed.join('\\n')") == text
    page.evaluate("document.getElementById('soloTextarea').setSelectionRange(2, 12)")   # spans lines 1-2
    page.keyboard.press("Backspace")
    assert page.input_value("#soloTextarea") == text
    page.evaluate("document.getElementById('soloTextarea').setSelectionRange(0, 30)")
    page.keyboard.insert_text("pasted over everything")
    assert page.input_value("#soloTextarea") == text
    assert "Line 2 is locked" in page.inner_text("#chatLog")
    _caret_to(page, 2, 6)
    page.keyboard.type(" Free")                                       # an unlocked line still edits
    assert page.input_value("#soloTextarea") == "One.\nTwo is locked.\nThree. Free"
    page.context.close()


def test_a_lock_moves_with_its_line_when_lines_are_added_or_removed_above(served):
    page = served(1366, 768)
    _write(page, ["A", "B locked", "C"])
    _lock_line(page, 1)
    _caret_to(page, 0, 0)
    page.keyboard.press("Enter")                                      # new line above everything
    assert page.evaluate("[...lockedLines]") == [2]
    _caret_to(page, 2, len("B locked"))
    page.keyboard.press("Enter")                                      # a new line after a locked line is fine
    page.keyboard.type("D")
    assert page.input_value("#soloTextarea") == "\nA\nB locked\nD\nC"
    assert page.evaluate("[...lockedLines]") == [2]
    _caret_to(page, 0, 0)
    page.keyboard.press("Delete")                                     # remove the empty first line
    assert page.evaluate("[...lockedLines]") == [1]
    assert '<span class="ln-locked"' in page.inner_html("#lineNumbers")
    page.context.close()


def test_unlock_in_write_mode_unlocks_the_line_with_the_cursor(served):
    page = served(1366, 768)
    _write(page, ["A", "B", "C"])
    page.click("#lockAllBtn")
    _caret_to(page, 1, 1)
    page.click("#unlockBtn")
    assert sorted(page.evaluate("[...lockedLines]")) == [0, 2]
    page.context.close()


def test_replace_all_counts_each_occurrence_once_and_leaves_locked_lines_alone(served):
    page = served(1366, 768)
    _write(page, ["the cat sat", "the cat is locked", "a cat and a cat"])
    _lock_line(page, 1)
    page.keyboard.press("Control+f")
    page.fill("#frFind", "cat")
    page.fill("#frReplace", "fox")
    page.click("#frReplaceAllBtn")
    assert page.inner_text("#frResult") == "3 replacements made; 1 in locked lines left as they are"
    assert page.input_value("#soloTextarea") == "the fox sat\nthe cat is locked\na fox and a fox"
    assert page.evaluate("committed.join('\\n')") == page.input_value("#soloTextarea")
    page.context.close()


def test_undoing_a_lock_in_write_mode_keeps_the_words_typed_since(served):
    page = served(1366, 768)
    _write(page, ["First."])
    page.click("#lockSceneBtn")
    _caret_to(page, 0, len("First."))
    page.keyboard.press("Enter")
    page.keyboard.type("Second, typed after the lock.")
    page.focus("#saveBtn")
    page.keyboard.press("Control+z")
    assert page.evaluate("[...lockedLines]") == []
    assert page.input_value("#soloTextarea") == "First.\nSecond, typed after the lock."
    assert page.evaluate("getDocState().committed.join('\\n')") == page.input_value("#soloTextarea")
    page.context.close()


def test_interface_messages_come_from_the_writers_room_not_the_partner(served):
    page = served(1366, 768)
    _write(page, ["A"])
    page.evaluate("lockedLines.add(0); render()")
    _caret_to(page, 0, 1)
    page.keyboard.type("x")
    last = page.locator("#chatLog .chat-msg").last
    assert last.locator(".who").inner_text().lower() == "writer’s room"
    assert "notice" in last.get_attribute("class")
    page.context.close()


def test_cancelling_new_chapter_leaves_nothing_to_undo(served):
    page = served(1366, 768)
    page.on("dialog", lambda dialog: dialog.dismiss())
    before = page.evaluate("undoStack.length")
    page.click("#newChapterBtn")
    assert page.evaluate("undoStack.length") == before
    assert page.evaluate("chapters.length") == 1
    page.context.close()


def test_an_edit_that_never_happened_cannot_bring_back_old_words(served):
    page = served(1366, 768)
    _write(page, ["Old document."])
    _lock_line(page, 0)
    # An undo with nothing to undo announces an edit (beforeinput) that never comes.
    page.evaluate("""() => { const t = document.getElementById('soloTextarea');
        t.dispatchEvent(new InputEvent('beforeinput', {inputType: 'historyUndo', bubbles: true, cancelable: true})); }""")
    # Another document is opened: the page's words change without any typing.
    page.evaluate("loadDocState({committed: ['New document.'], coWriting: false, lockedLines: [0]})")
    _caret_to(page, 0, 0)
    page.keyboard.press("Enter")
    assert page.input_value("#soloTextarea") == "\nNew document."
    page.context.close()

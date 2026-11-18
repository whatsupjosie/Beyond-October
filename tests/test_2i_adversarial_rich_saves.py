"""Adversarial save tests for the optional rich DOCX editor inside 2i file mode, in a real browser.

The rich engine is not committed. Build it first (offline afterwards):
    cd 2i/editor-engine; npm ci; node build.mjs
Without 2i/2i-assets/vendor/docx/engine.js these tests skip, and in the app "Open local rich editor"
reports "Local rich editing unavailable".

Oracle: the stored working DOCX is read raw from IndexedDB and parsed with python-docx, independent of the
editor and of Foresight's record().

Rich bytes come from the engine's asynchronous saveBytes(), so no synchronous exit copy is possible (unlike
plain text). Protection is: the 1.5 s autosave, a flush when the tab is hidden, and the browser's leave
warning while unsaved. These tests hold those three in place.
"""

import base64
import io
from pathlib import Path
from urllib.parse import urlparse

import pytest
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.foresight_file_formats import create_file_format_router
from modules.twoi_rich_document import pack
from tests.test_foresight_file_workspace import page  # noqa: F401
from tests.test_twoi_rich_document import rich  # noqa: F401

ENGINE = Path(__file__).resolve().parents[1] / "2i" / "2i-assets" / "vendor" / "docx" / "engine.js"
pytestmark = pytest.mark.skipif(not ENGINE.is_file(), reason="rich DOCX engine not built (see module docstring)")

RAW_DRAFT = """async (id) => {
  const dbs = (await indexedDB.databases()).filter(d => d.name && d.name.startsWith('pubcast-foresight-files-v1'));
  for (const info of dbs) {
    const db = await new Promise(ok => { const r = indexedDB.open(info.name); r.onsuccess = () => ok(r.result); });
    const rec = await new Promise(ok => { const q = db.transaction('files').objectStore('files').get(id); q.onsuccess = () => ok(q.result); });
    db.close();
    if (rec && rec.richDraft) { const b = new Uint8Array(await rec.richDraft.arrayBuffer()); let s = ''; for (const x of b) s += String.fromCharCode(x); return btoa(s); }
    if (rec) return '';
  }
  return null;
}"""

HIDE = """() => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => true});
  document.dispatchEvent(new Event('visibilitychange')); }"""


def stored_rich_text(frame, file_id):
    b64 = frame.evaluate(RAW_DRAFT, file_id)
    if not b64:
        return None
    return "\n".join(p.text for p in Document(io.BytesIO(base64.b64decode(b64))).paragraphs)


def open_rich_editor(page, rich):  # noqa: F811
    app = FastAPI()
    app.include_router(create_file_format_router())
    client = TestClient(app)

    def handle(route):
        address = urlparse(route.request.url)
        response = client.request(
            route.request.method, address.path, content=route.request.post_data,
            headers={k: v for k, v in route.request.headers.items() if k.lower() in {"authorization", "content-type"}},
        )
        route.fulfill(status=response.status_code, body=response.content,
                      content_type=response.headers.get("content-type", "application/json"))

    page.context.route("**/api/foresight/files/native-rich/**", handle)
    page.evaluate(
        """b64 => { const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
        const r = p.fromFile(new File([bytes], 'Manuscript.2i', {type: 'application/octet-stream'}));
        return mount(r.data, r.type); }""",
        base64.b64encode(pack(rich)).decode(),
    )
    tray = page.frame_locator("#host iframe")
    tray.get_by_role("button", name="Open local rich editor").click()
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('.docx-editor [contenteditable]') !== null",
        timeout=30000,
    )
    tray.locator(".docx-editor [contenteditable]").first.click()
    page.keyboard.press("Control+End")
    frame = next(f for f in page.frames if "writers-room" in f.url)
    return page.evaluate("c.data.fileId"), frame


def test_rich_edit_reaches_storage_after_autosave(page, rich):  # noqa: F811
    """Control: an ordinary edit is stored by the rich autosave."""
    file_id, frame = open_rich_editor(page, rich)
    page.keyboard.type(" AUTOSAVED-RICH", delay=5)
    page.wait_for_timeout(4000)
    text = stored_rich_text(frame, file_id)
    assert text is not None and "AUTOSAVED-RICH" in text


def test_rich_unsaved_edit_raises_leave_warning_and_stay_keeps_it(page, rich):  # noqa: F811
    """Reload with an unsaved rich edit: the browser must ask first; staying keeps the text in the editor."""
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.type), d.dismiss()))
    file_id, frame = open_rich_editor(page, rich)
    page.keyboard.type(" UNSAVED-RICH", delay=5)
    try:
        page.reload(timeout=4000)
    except Exception:  # a dismissed leave warning cancels the reload, so the navigation never completes
        pass
    assert dialogs == ["beforeunload"], f"no leave warning with unsaved rich text: {dialogs}"
    assert "UNSAVED-RICH" in frame.evaluate("document.querySelector('.docx-editor').innerText")


def test_rich_unsaved_edit_is_stored_when_tab_is_hidden(page, rich):  # noqa: F811
    """Phones background tabs before killing them: hiding must store the edit while the page is alive."""
    file_id, frame = open_rich_editor(page, rich)
    page.keyboard.type(" HIDDEN-RICH", delay=5)
    frame.evaluate(HIDE)
    page.wait_for_timeout(1500)  # shorter than the 1.5 s autosave plus engine serialisation would need on its own
    text = stored_rich_text(frame, file_id)
    assert text is not None and "HIDDEN-RICH" in text

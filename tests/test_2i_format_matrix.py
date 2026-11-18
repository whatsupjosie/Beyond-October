"""Every file format 2i and Foresight claim to handle, opened in a real browser from real producers' files.

Fixtures in tests/fixtures/formats/ come from LibreOffice, pandoc, ffmpeg and Pillow (tools/make_format_fixtures.py,
MANIFEST.json). Oracles are independent of the code under test: original bytes are read raw from IndexedDB,
exported DOCX is parsed with python-docx, downloads are compared byte for byte.
"""

import base64
import io
import json
import mimetypes
from pathlib import Path

import pytest
from docx import Document

from tests.test_foresight_file_workspace import page  # noqa: F401  (fixture re-used on purpose)

FIX = Path(__file__).parent / "fixtures" / "formats"
LINE1, LINE2 = json.loads((FIX / "MANIFEST.json").read_text(encoding="utf-8"))["text"]

TEXT = ["txt", "md", "csv", "json", "html", "fountain"]
CONVERTED = ["docx", "odt", "rtf", "epub", "pdf", "pptx", "odp", "xlsx", "ods"]
SPREADSHEETS = {"xlsx", "ods"}
SLIDES = {"pptx", "odp"}
IMAGES = ["png", "jpg", "gif", "webp", "bmp", "svg"]
MEDIA = ["wav", "mp3", "ogg", "opus", "flac", "m4a", "mp4", "webm", "mov"]
UNSUPPORTED = {
    "bin": "not text that 2i can edit",
    "doc": "Older Word .doc files cannot be opened here",
}

RAW_ORIGINAL = """async (id) => {
  const dbs = (await indexedDB.databases()).filter(d => d.name && d.name.startsWith('pubcast-foresight-files-v1'));
  for (const info of dbs) {
    const db = await new Promise(ok => { const r = indexedDB.open(info.name); r.onsuccess = () => ok(r.result); });
    const rec = await new Promise(ok => { const q = db.transaction('files').objectStore('files').get(id); q.onsuccess = () => ok(q.result); });
    db.close();
    if (rec && rec.original) { const b = new Uint8Array(await rec.original.arrayBuffer()); let s = ''; for (const x of b) s += String.fromCharCode(x); return btoa(s); }
  }
  return null;
}"""


@pytest.fixture(autouse=True)
def real_format_routes(page):  # noqa: F811
    """The shared fixture routes only /convert; serve the real export (and rich) routes too, with auth."""
    from urllib.parse import urlparse
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from modules.foresight_file_formats import create_file_format_router

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

    page.context.route("**/api/foresight/files/export", handle)
    page.context.route("**/api/foresight/files/native-rich/**", handle)
    yield
    client.close()


def open_fixture(page, name):
    raw = (FIX / name).read_bytes()
    page.evaluate(
        """([b64, name, mime]) => { const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
        const r = p.fromFile(new File([bytes], name, {type: mime}));
        localStorage.setItem('file-data', JSON.stringify(r.data)); localStorage.setItem('file-type', r.type);
        return mount(r.data, r.type); }""",
        [base64.b64encode(raw).decode(), name, mimetypes.guess_type(name)[0] or ""],
    )
    return raw


def workspace(page, timeout=20000):
    """The frame holding the Foresight file workspace (the 2i iframe for documents)."""
    page.wait_for_function(
        """() => [document, ...[...document.querySelectorAll('iframe')].map(f => { try { return f.contentDocument } catch (e) { return null } })]
             .some(d => d && d.querySelector('.ff-workspace [role=status]') && d.querySelector('.ff-workspace [role=status]').textContent.trim()
                        && !/Opening|Converting|Verifying/.test(d.querySelector('.ff-workspace [role=status]').textContent))""",
        timeout=timeout,
    )
    for frame in page.frames:
        if frame.evaluate("!!document.querySelector('.ff-workspace')"):
            return frame
    raise AssertionError("no file workspace found")


def status(frame):
    return frame.evaluate("document.querySelector('.ff-workspace [role=status]').textContent")


def original_bytes(frame, page):
    b64 = frame.evaluate(RAW_ORIGINAL, page.evaluate("c.data.fileId"))
    return base64.b64decode(b64) if b64 else None


def editor_value(frame):
    return frame.evaluate("(document.querySelector('#soloTextarea') || document.querySelector('textarea[aria-label=\"File editor\"]')).value")


def set_editor(frame, text):
    frame.evaluate(
        """t => { const e = document.querySelector('#soloTextarea') || document.querySelector('textarea[aria-label="File editor"]');
           e.value = t; e.dispatchEvent(new Event('input', {bubbles: true})); }""",
        text,
    )


def reopen(page):
    page.reload()
    page.evaluate("restore()")
    return workspace(page)


@pytest.mark.parametrize("ext", TEXT)
def test_text_formats_open_exactly_edit_save_reopen_and_export(page, ext):
    name = "sample." + ext
    raw = open_fixture(page, name)
    frame = workspace(page)
    assert editor_value(frame) == raw.decode("utf-8")
    edited = raw.decode("utf-8") + "Edited in 2i — ✓\n"
    set_editor(frame, edited)
    page.wait_for_timeout(1200)
    exported = page.evaluate("async()=>{const f=await p.exportContent(c);return {name:f.name,text:await f.data.text()}}")
    assert exported == {"name": name, "text": edited}
    frame = reopen(page)
    assert editor_value(frame) == edited
    assert original_bytes(frame, page) == raw, "original bytes changed"


@pytest.mark.parametrize("ext", CONVERTED)
def test_documents_convert_to_an_editable_copy_and_export_docx(page, ext):
    name = "sample." + ext
    raw = open_fixture(page, name)
    frame = workspace(page)
    text = editor_value(frame)
    if ext in SPREADSHEETS:
        assert "café" in text and "naïve" in text, text
    elif ext in SLIDES:
        assert "Beyond October fixture" in text and LINE2 in text, text
    else:
        assert LINE1 in text and LINE2 in text, text
    assert "original is unchanged" in status(frame).lower() or "original unchanged" in status(frame).lower(), status(frame)
    set_editor(frame, text + "\nEdited after conversion")
    page.wait_for_timeout(1200)
    with page.expect_download() as download:
        frame.get_by_role("button", name="Export DOCX").click()
    exported = "\n".join(p.text for p in Document(download.value.path()).paragraphs)
    assert "Edited after conversion" in exported
    frame = reopen(page)
    assert editor_value(frame).endswith("Edited after conversion")
    assert original_bytes(frame, page) == raw, "original bytes changed"


@pytest.mark.parametrize("ext", IMAGES)
def test_images_display_rotate_and_keep_the_original(page, ext):
    raw = open_fixture(page, "sample." + ext)
    frame = workspace(page)
    assert "Image ready" in status(frame)
    assert frame.evaluate("document.querySelector('.ff-workspace canvas').width") == 40
    frame.get_by_role("button", name="Rotate 90°").click()
    frame.wait_for_function("document.querySelector('.ff-workspace canvas').width === 20")
    page.wait_for_timeout(1200)
    frame = reopen(page)
    frame.wait_for_function("document.querySelector('.ff-workspace canvas')?.width === 20", timeout=10000)
    assert original_bytes(frame, page) == raw, "original bytes changed"


@pytest.mark.parametrize("ext", MEDIA)
def test_audio_and_video_decode_and_play_length(page, ext):
    open_fixture(page, "sample." + ext)
    page.wait_for_function(
        """() => [document, ...[...document.querySelectorAll('iframe')].map(f => { try { return f.contentDocument } catch (e) { return null } })]
             .some(d => { const m = d && d.querySelector('video, audio'); return m && m.readyState >= 1; })""",
        timeout=20000,
    )
    state = page.evaluate(
        """() => { for (const d of [document, ...[...document.querySelectorAll('iframe')].map(f => f.contentDocument)]) {
             const m = d && d.querySelector('video, audio'); if (m) return {error: m.error && m.error.code, duration: m.duration}; } }"""
    )
    assert state["error"] is None, state
    assert 0.9 <= state["duration"] <= 1.2, state


@pytest.mark.parametrize("ext", sorted(UNSUPPORTED))
def test_unsupported_files_say_why_and_return_the_original_untouched(page, ext):
    raw = open_fixture(page, "sample." + ext)
    frame = workspace(page)
    message = status(frame)
    assert UNSUPPORTED[ext] in message and "has not been altered" in message, message
    assert "TextDecoder" not in message
    with page.expect_download() as download:
        frame.get_by_role("button", name="Download original").click()
    assert Path(download.value.path()).read_bytes() == raw
    assert original_bytes(frame, page) == raw
